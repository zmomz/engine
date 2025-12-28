import asyncio
import logging
import traceback
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import uuid

from app.db.database import get_db_session, AsyncSessionLocal
from app.schemas.position_group import PositionGroupSchema
from app.repositories.position_group import PositionGroupRepository
from app.services.order_management import OrderService # New import
from app.services.position_manager import PositionManagerService
from app.services.grid_calculator import GridCalculatorService
from app.api.dependencies.users import get_current_active_user # New import
from app.models.user import User # New import
from app.exceptions import APIError # New import
from app.services.exchange_config_service import ExchangeConfigService, ExchangeConfigError
from app.rate_limiter import limiter
from app.core.cache import get_cache

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_order_service(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
) -> OrderService:
    """Initialize OrderService with exchange connector from user credentials."""
    try:
        exchange_connector = ExchangeConfigService.get_connector(current_user)
    except ExchangeConfigError as e:
        logger.warning(f"Exchange config error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to initialize exchange connector: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize exchange connection. Please check your API credentials."
        )

    return OrderService(
        session=db,
        user=current_user,
        exchange_connector=exchange_connector
    )

@router.get("/{user_id}/history")
@limiter.limit("30/minute")
async def get_position_history(
    request: Request,
    user_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of records to return"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves historical (closed) position groups for a given user with pagination.

    Returns:
        - items: List of position groups
        - total: Total count of closed positions
        - limit: Number of items per page
        - offset: Current offset
    """
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user's history.")

    repo = PositionGroupRepository(db)
    positions, total = await repo.get_closed_by_user(user_id, limit=limit, offset=offset)
    return {
        "items": [PositionGroupSchema.from_orm(pos) for pos in positions],
        "total": total,
        "limit": limit,
        "offset": offset
    }

async def _calculate_position_pnl(
    pos,
    all_tickers: Dict[str, Any],
    connector
) -> None:
    """
    Calculate unrealized PnL for a single position.
    Designed to be called in parallel with asyncio.gather.
    """
    try:
        symbol = pos.symbol
        current_price = None

        # Try to get price from cached tickers first
        if symbol in all_tickers:
            current_price = float(all_tickers[symbol]['last'])
        elif symbol.replace('/', '') in all_tickers:
            current_price = float(all_tickers[symbol.replace('/', '')]['last'])
        else:
            # Fallback to individual price fetch - ensure float return
            price = await connector.get_current_price(symbol)
            current_price = float(price) if price is not None else None

        if current_price is None:
            return

        qty = float(pos.total_filled_quantity)
        avg_entry = float(pos.weighted_avg_entry)
        total_invested = float(pos.total_invested_usd)

        if qty > 0 and avg_entry > 0:
            if pos.side.lower() == "long":
                pnl = (current_price - avg_entry) * qty
            else:
                pnl = (avg_entry - current_price) * qty

            pos.unrealized_pnl_usd = Decimal(str(pnl))
            if total_invested > 0:
                pos.unrealized_pnl_percent = Decimal(str((pnl / total_invested) * 100))
            else:
                pos.unrealized_pnl_percent = Decimal("0")
    except Exception as e:
        logger.error(f"Error calculating PnL for position {pos.id} ({pos.symbol}): {e}")


@router.get("/active", response_model=List[PositionGroupSchema])
@limiter.limit("120/minute")
async def get_current_user_active_positions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieves all active position groups for the current authenticated user.
    Calculates unrealized PnL with current market prices.

    Performance optimizations:
    - Batch fetches all tickers once per exchange
    - Calculates PnL for all positions in parallel using asyncio.gather
    """
    repo = PositionGroupRepository(db)
    positions = await repo.get_active_position_groups_for_user(current_user.id)

    if not positions or not current_user.encrypted_api_keys:
        return [PositionGroupSchema.from_orm(pos) for pos in positions]

    # Group positions by exchange for efficient price fetching
    groups_by_exchange: Dict[str, List] = {}
    for pos in positions:
        ex = pos.exchange or current_user.exchange or "binance"
        if ex not in groups_by_exchange:
            groups_by_exchange[ex] = []
        groups_by_exchange[ex].append(pos)

    cache = await get_cache()

    # Process all exchanges in parallel
    async def process_exchange(exchange_name: str, exchange_positions: List):
        if not ExchangeConfigService.has_valid_config(current_user, exchange_name):
            logger.warning(f"No valid API keys for exchange '{exchange_name}' to update PnL for {len(exchange_positions)} positions.")
            return

        connector = None
        try:
            connector = ExchangeConfigService.get_connector(current_user, exchange_name)

            # Try to get cached tickers first
            all_tickers = await cache.get_tickers(exchange_name)
            if not all_tickers:
                try:
                    all_tickers = await connector.get_all_tickers()
                    logger.debug(f"Fetched {len(all_tickers)} tickers from {exchange_name}")
                    await cache.set_tickers(exchange_name, all_tickers)
                except Exception as e:
                    logger.warning(f"Could not fetch tickers from {exchange_name}: {e}")
                    all_tickers = {}

            # Calculate PnL for all positions in parallel
            await asyncio.gather(*[
                _calculate_position_pnl(pos, all_tickers, connector)
                for pos in exchange_positions
            ], return_exceptions=True)

        except Exception as e:
            logger.error(f"Error fetching prices from {exchange_name}: {e}")
        # Note: Don't close connector - it's cached for reuse by the factory

    # Process all exchanges in parallel
    await asyncio.gather(*[
        process_exchange(exchange_name, exchange_positions)
        for exchange_name, exchange_positions in groups_by_exchange.items()
    ], return_exceptions=True)

    return [PositionGroupSchema.from_orm(pos) for pos in positions]


@router.get("/history")
@limiter.limit("120/minute")
async def get_current_user_position_history(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of records to return"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieves historical (closed) position groups for the current authenticated user with pagination.

    Returns:
        - items: List of position groups
        - total: Total count of closed positions
        - limit: Number of items per page
        - offset: Current offset
    """
    repo = PositionGroupRepository(db)
    positions, total = await repo.get_closed_by_user(current_user.id, limit=limit, offset=offset)
    return {
        "items": [PositionGroupSchema.from_orm(pos) for pos in positions],
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/{user_id}", response_model=List[PositionGroupSchema])
@limiter.limit("30/minute")
async def get_all_positions(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves all active position groups for a given user.
    Calculates unrealized PnL with current market prices.

    Performance optimizations:
    - Batch fetches all tickers once per exchange
    - Calculates PnL for all positions in parallel using asyncio.gather
    """
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user's positions.")

    repo = PositionGroupRepository(db)
    positions = await repo.get_active_position_groups_for_user(user_id)

    if not positions or not current_user.encrypted_api_keys:
        return [PositionGroupSchema.from_orm(pos) for pos in positions]

    # Group positions by exchange for efficient price fetching
    groups_by_exchange: Dict[str, List] = {}
    for pos in positions:
        ex = pos.exchange or current_user.exchange or "binance"
        if ex not in groups_by_exchange:
            groups_by_exchange[ex] = []
        groups_by_exchange[ex].append(pos)

    cache = await get_cache()

    # Process all exchanges in parallel
    async def process_exchange(exchange_name: str, exchange_positions: List):
        if not ExchangeConfigService.has_valid_config(current_user, exchange_name):
            return

        connector = None
        try:
            connector = ExchangeConfigService.get_connector(current_user, exchange_name)

            # Try to get cached tickers first
            all_tickers = await cache.get_tickers(exchange_name)
            if not all_tickers:
                try:
                    all_tickers = await connector.get_all_tickers()
                    await cache.set_tickers(exchange_name, all_tickers)
                except Exception as e:
                    logger.warning(f"Could not fetch tickers from {exchange_name}: {e}")
                    all_tickers = {}

            # Calculate PnL for all positions in parallel
            await asyncio.gather(*[
                _calculate_position_pnl(pos, all_tickers, connector)
                for pos in exchange_positions
            ], return_exceptions=True)

        except Exception as e:
            logger.error(f"Error fetching prices from {exchange_name}: {e}")
        # Note: Don't close connector - it's cached for reuse by the factory

    # Process all exchanges in parallel
    await asyncio.gather(*[
        process_exchange(exchange_name, exchange_positions)
        for exchange_name, exchange_positions in groups_by_exchange.items()
    ], return_exceptions=True)

    return [PositionGroupSchema.from_orm(pos) for pos in positions]

@router.get("/{user_id}/{group_id}", response_model=PositionGroupSchema)
@limiter.limit("30/minute")
async def get_position_group(
    request: Request,
    user_id: uuid.UUID,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves a specific position group for a given user.
    """
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this position group.")

    repo = PositionGroupRepository(db)
    position = await repo.get_by_user_and_id(user_id, group_id)
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position group not found.")
    return PositionGroupSchema.from_orm(position)

@router.post("/{group_id}/close", response_model=PositionGroupSchema)
@limiter.limit("5/minute")
async def force_close_position(
    request: Request,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Initiates the force-closing process for an active position group.
    """
    repo = PositionGroupRepository(db)
    position_group = await repo.get_by_user_and_id(current_user.id, group_id)
    if not position_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position group not found.")

    exchange_connector = None
    try:
        # Get exchange connector for the position's exchange
        target_exchange = position_group.exchange
        try:
            exchange_connector = ExchangeConfigService.get_connector(current_user, target_exchange)
        except ExchangeConfigError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        order_service = OrderService(
            session=db,
            user=current_user,
            exchange_connector=exchange_connector
        )

        # 4. Mark as CLOSING
        updated_position = await order_service.execute_force_close(group_id)

        # 5. Execute the actual close logic
        position_manager = PositionManagerService(
            session_factory=lambda: db, # Pass the existing session
            user=current_user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=GridCalculatorService(),
            order_service_class=OrderService
        )

        # Pass the session explicitly to handle_exit_signal with manual exit reason
        await position_manager.handle_exit_signal(updated_position.id, session=db, exit_reason="manual")
        
        # Refresh to get the latest state after all operations
        await db.refresh(updated_position)

        return PositionGroupSchema.from_orm(updated_position)
    except APIError as e:
        await db.rollback()
        logger.error(f"API error force closing position {group_id}: {e}")
        raise HTTPException(status_code=e.status_code, detail="Failed to close position. Please try again.")
    except Exception as e:
        logger.error(f"Error force closing position {group_id}: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while closing the position.")
    finally:
        # Always close the exchange connector
        if exchange_connector:
            await exchange_connector.close()


@router.post("/{group_id}/sync")
@limiter.limit("5/minute")
async def sync_position_with_exchange(
    request: Request,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Synchronize a position's orders with exchange state.

    This is useful when:
    - Orders may have filled on exchange but local DB wasn't updated
    - Need to reconcile local state with exchange state
    - Debugging order status discrepancies
    """
    from app.services.exchange_sync import ExchangeSyncService

    repo = PositionGroupRepository(db)
    position_group = await repo.get_by_user_and_id(current_user.id, group_id)
    if not position_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position group not found.")

    exchange_connector = None
    try:
        # Get exchange connector for the position's exchange
        target_exchange = position_group.exchange
        try:
            exchange_connector = ExchangeConfigService.get_connector(current_user, target_exchange)
        except ExchangeConfigError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        sync_service = ExchangeSyncService(
            session=db,
            user=current_user,
            exchange_connector=exchange_connector
        )

        result = await sync_service.sync_orders_with_exchange(
            position_group_id=group_id,
            update_local=True
        )

        await db.commit()

        return {
            "status": "success",
            "message": f"Synchronized {result['synced']} orders, updated {result['updated']}, "
                      f"not found {result['not_found']}, errors {result['errors']}",
            "details": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing position {group_id}: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while syncing with exchange."
        )
    finally:
        if exchange_connector:
            await exchange_connector.close()


@router.post("/{group_id}/cleanup-stale")
@limiter.limit("3/minute")
async def cleanup_stale_orders(
    request: Request,
    group_id: uuid.UUID,
    stale_hours: int = Query(default=48, ge=1, le=168, description="Hours after which an order is considered stale"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Clean up stale orders for a position by checking their status on exchange.

    Useful for orders stuck in OPEN status that may have been cancelled
    or filled on the exchange.
    """
    from app.services.exchange_sync import ExchangeSyncService

    repo = PositionGroupRepository(db)
    position_group = await repo.get_by_user_and_id(current_user.id, group_id)
    if not position_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position group not found.")

    exchange_connector = None
    try:
        target_exchange = position_group.exchange
        try:
            exchange_connector = ExchangeConfigService.get_connector(current_user, target_exchange)
        except ExchangeConfigError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        sync_service = ExchangeSyncService(
            session=db,
            user=current_user,
            exchange_connector=exchange_connector
        )

        result = await sync_service.cleanup_stale_local_orders(
            position_group_id=group_id,
            stale_hours=stale_hours
        )

        await db.commit()

        return {
            "status": "success",
            "message": f"Checked {result['checked']} stale orders, cleaned {result['cleaned']}, errors {result['errors']}",
            "details": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up stale orders for position {group_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while cleaning up stale orders."
        )
    finally:
        if exchange_connector:
            await exchange_connector.close()