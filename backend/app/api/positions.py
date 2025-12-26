import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
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

@router.get("/active", response_model=List[PositionGroupSchema])
@limiter.limit("60/minute")
async def get_current_user_active_positions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieves all active position groups for the current authenticated user.
    """
    repo = PositionGroupRepository(db)
    # Use the more inclusive getter that matches dashboard logic (includes live, partially_filled, closing)
    positions = await repo.get_active_position_groups_for_user(current_user.id)
    return [PositionGroupSchema.from_orm(pos) for pos in positions]


@router.get("/history")
@limiter.limit("30/minute")
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
    """
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user's positions.")

    repo = PositionGroupRepository(db)
    # Use the more inclusive getter that matches dashboard logic
    positions = await repo.get_active_position_groups_for_user(user_id)
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