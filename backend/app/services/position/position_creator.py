"""
Position and pyramid creation logic.
Handles creating new positions from signals and adding pyramids.
"""
import asyncio
import json
import logging
import uuid
from decimal import Decimal
from typing import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.queued_signal import QueuedSignal
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.schemas.grid_config import DCAGridConfig, RiskEngineConfig
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.grid_calculator import GridCalculatorService
from app.services.order_management import OrderService
from app.services.telegram_signal_helper import (
    broadcast_entry_signal,
    broadcast_failure,
    broadcast_pyramid_added,
)

logger = logging.getLogger(__name__)


class UserNotFoundException(Exception):
    """Exception raised when a user is not found."""
    pass


class DuplicatePositionException(Exception):
    """Exception raised when attempting to create a duplicate active position."""
    pass


def _get_exchange_connector_for_user(user: User, exchange_name: str) -> ExchangeInterface:
    """Get exchange connector for a user."""
    encrypted_data = user.encrypted_api_keys
    exchange_key = exchange_name.lower()

    if isinstance(encrypted_data, dict):
        if exchange_key in encrypted_data:
            exchange_config = encrypted_data[exchange_key]
        elif "encrypted_data" in encrypted_data and len(encrypted_data) == 1:
            exchange_config = encrypted_data
        else:
            raise ValueError(f"No API keys found for exchange {exchange_name} (normalized: {exchange_key}). Available: {list(encrypted_data.keys()) if encrypted_data else 'None'}")
    elif isinstance(encrypted_data, str):
        exchange_config = {"encrypted_data": encrypted_data}
    else:
        raise ValueError("Invalid format for encrypted_api_keys. Expected dict or str.")

    return get_exchange_connector(exchange_name, exchange_config)


async def create_position_group_from_signal(
    session: AsyncSession,
    user_id: uuid.UUID,
    signal: QueuedSignal,
    risk_config: RiskEngineConfig,
    dca_grid_config: DCAGridConfig,
    total_capital_usd: Decimal,
    position_group_repository_class: type[PositionGroupRepository],
    grid_calculator_service: GridCalculatorService,
    order_service_class: type[OrderService],
    update_risk_timer_func: Callable,
    update_position_stats_func: Callable,
) -> PositionGroup:
    """
    Create a new position group from a signal.

    Args:
        session: Database session
        user_id: User ID
        signal: The queued signal to create position from
        risk_config: Risk engine configuration
        dca_grid_config: DCA grid configuration
        total_capital_usd: Total capital to allocate
        position_group_repository_class: Repository class for position groups
        grid_calculator_service: Service for calculating DCA grids
        order_service_class: Service class for order management
        update_risk_timer_func: Function to update risk timer
        update_position_stats_func: Function to update position stats

    Returns:
        The created PositionGroup
    """
    logger.debug(f"Entering create_position_group_from_signal for user {user_id}")

    # 1. Get user
    user = await session.get(User, user_id)
    if not user:
        logger.debug("User not found")
        raise UserNotFoundException(f"User {user_id} not found")

    # Dynamically get exchange connector
    exchange_name = signal.exchange.lower()
    encrypted_data = user.encrypted_api_keys
    exchange_config = {}

    if isinstance(encrypted_data, dict):
        if exchange_name in encrypted_data:
            exchange_config = encrypted_data[exchange_name]
        elif "encrypted_data" in encrypted_data and len(encrypted_data) == 1:
            exchange_config = encrypted_data
        else:
            raise ValueError(f"No API keys found for exchange {exchange_name} (normalized: {exchange_name}). Available: {list(encrypted_data.keys()) if encrypted_data else 'None'}")
    elif isinstance(encrypted_data, str):
        exchange_config = {"encrypted_data": encrypted_data}
    else:
        raise ValueError("Invalid format for encrypted_api_keys")

    exchange_connector = get_exchange_connector(signal.exchange, exchange_config)
    logger.debug(f"Got exchange connector: {exchange_connector.__class__.__name__}")

    # 2. Fetch precision rules
    precision_rules = await exchange_connector.get_precision_rules()
    symbol_precision = precision_rules.get(signal.symbol, {})
    logger.debug(f"Fetched precision rules for {signal.symbol}: {symbol_precision}")

    # Check if the symbol exists in precision rules
    if signal.symbol not in precision_rules:
        logger.error(f"Symbol {signal.symbol} not found in precision rules!")
        alt_symbol = signal.symbol.replace("/", "")
        logger.debug(f"Trying alternative symbol format: {alt_symbol}")
        if alt_symbol in precision_rules:
            symbol_precision = precision_rules[alt_symbol]
            logger.debug(f"Using alternative symbol format for precision rules")

    # 3. Calculate DCA levels and quantities
    dca_levels = grid_calculator_service.calculate_dca_levels(
        base_price=signal.entry_price,
        dca_config=dca_grid_config,
        side=signal.side,
        precision_rules=symbol_precision,
        pyramid_index=0
    )
    logger.debug(f"Calculated {len(dca_levels)} levels")

    dca_levels = grid_calculator_service.calculate_order_quantities(
        dca_levels=dca_levels,
        total_capital_usd=total_capital_usd,
        precision_rules=symbol_precision
    )

    # 4. Create PositionGroup
    new_position_group = PositionGroup(
        user_id=user_id,
        exchange=signal.exchange.lower(),
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        side=signal.side,
        status=PositionGroupStatus.LIVE,
        total_dca_legs=len(dca_levels),
        base_entry_price=signal.entry_price,
        weighted_avg_entry=signal.entry_price,
        tp_mode=dca_grid_config.tp_mode,
        tp_aggregate_percent=dca_grid_config.tp_aggregate_percent,
        pyramid_count=0,
        max_pyramids=dca_grid_config.max_pyramids,
        risk_timer_start=None,
        risk_timer_expires=None
    )
    session.add(new_position_group)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        if 'uix_active_position_group' in str(e.orig):
            logger.warning(
                f"Duplicate position rejected: {signal.symbol} {signal.side} "
                f"on {signal.exchange} tf={signal.timeframe} for user {user_id}"
            )
            raise DuplicatePositionException(
                f"Active position already exists for {signal.symbol} {signal.side} "
                f"on timeframe {signal.timeframe}"
            )
        raise
    logger.debug(f"Created PG {new_position_group.id}")

    # 5. Create Initial Pyramid
    new_pyramid = Pyramid(
        group_id=new_position_group.id,
        pyramid_index=0,
        entry_price=signal.entry_price,
        status=PyramidStatus.PENDING,
        dca_config=json.loads(dca_grid_config.json())
    )
    session.add(new_pyramid)
    await session.flush()

    # 6. Instantiate OrderService
    order_service = order_service_class(
        session=session,
        user=user,
        exchange_connector=exchange_connector
    )

    # 7. Create DCAOrder objects
    orders_to_submit = []
    order_side = "buy" if signal.side == "long" else "sell"

    entry_type = dca_grid_config.entry_order_type

    for i, level in enumerate(dca_levels):
        # Apply entry_order_type to ALL DCA orders, not just the first one
        if entry_type == "market":
            current_order_type = "market"
            gap_pct = level.get('gap_percent', Decimal("0"))
            if gap_pct <= 0:
                # Market orders with gap_percent<=0 should be submitted immediately
                # gap_percent=0: entry at current price
                # gap_percent<0: price is already better than target (submit now)
                current_status = OrderStatus.PENDING
            else:
                # DCA legs with gap_percent > 0 wait for order_fill_monitor to trigger
                current_status = OrderStatus.TRIGGER_PENDING
        else:
            current_order_type = "limit"
            current_status = OrderStatus.PENDING

        dca_order = DCAOrder(
            group_id=new_position_group.id,
            pyramid_id=new_pyramid.id,
            leg_index=i,
            symbol=signal.symbol,
            side=order_side,
            order_type=current_order_type,
            price=level['price'],
            quantity=level['quantity'],
            quote_amount=level.get('quote_amount'),  # USDT amount for market orders
            status=current_status,
            gap_percent=level.get('gap_percent', Decimal("0")),
            weight_percent=level.get('weight_percent', Decimal("0")),
            tp_percent=level.get('tp_percent', Decimal("0")),
            tp_price=level.get('tp_price', Decimal("0")),
        )
        session.add(dca_order)

        if current_status == OrderStatus.PENDING:
            orders_to_submit.append(dca_order)
        else:
            logger.info(f"Order leg {i} set to {current_status} (Market Watch). Not submitting yet.")

    logger.debug(f"About to submit {len(orders_to_submit)} orders")

    # 8. Submit orders sequentially to avoid SQLAlchemy session conflicts
    # Note: Parallel submission causes "Session is already flushing" errors
    # because multiple coroutines try to update the shared session concurrently
    try:
        if orders_to_submit:
            logger.debug(f"Submitting {len(orders_to_submit)} orders sequentially")
            for order in orders_to_submit:
                try:
                    await order_service.submit_order(order)
                except Exception as e:
                    logger.error(f"Order {order.leg_index} failed: {e}")
                    raise e
    except Exception as e:
        logger.error(f"Failed to submit orders for PositionGroup {new_position_group.id}: {e}")
        new_position_group.status = PositionGroupStatus.FAILED
        await broadcast_failure(
            position_group=new_position_group,
            error_type="order_failed",
            error_message=str(e),
            session=session,
            pyramid=new_pyramid
        )
        pass

    # Update pyramid status after orders are submitted
    new_pyramid.status = PyramidStatus.SUBMITTED
    await session.flush()
    logger.info(f"Pyramid {new_pyramid.id} status updated to SUBMITTED after order submission.")

    logger.info(f"Created new PositionGroup {new_position_group.id} and submitted {len(orders_to_submit)} DCA orders.")

    await update_risk_timer_func(new_position_group.id, risk_config, session=session)
    await update_position_stats_func(new_position_group.id, session=session)

    # Broadcast initial entry signal to Telegram (fire-and-forget for performance)
    asyncio.create_task(broadcast_entry_signal(new_position_group, new_pyramid, session))

    return new_position_group


async def handle_pyramid_continuation(
    session: AsyncSession,
    user_id: uuid.UUID,
    signal: QueuedSignal,
    existing_position_group: PositionGroup,
    risk_config: RiskEngineConfig,
    dca_grid_config: DCAGridConfig,
    total_capital_usd: Decimal,
    position_group_repository_class: type[PositionGroupRepository],
    grid_calculator_service: GridCalculatorService,
    order_service_class: type[OrderService],
    update_risk_timer_func: Callable,
    update_position_stats_func: Callable,
) -> PositionGroup:
    """
    Handle pyramid continuation for an existing position.

    Args:
        session: Database session
        user_id: User ID
        signal: The queued signal for pyramid
        existing_position_group: Existing position group to add pyramid to
        risk_config: Risk engine configuration
        dca_grid_config: DCA grid configuration
        total_capital_usd: Total capital to allocate
        position_group_repository_class: Repository class for position groups
        grid_calculator_service: Service for calculating DCA grids
        order_service_class: Service class for order management
        update_risk_timer_func: Function to update risk timer
        update_position_stats_func: Function to update position stats

    Returns:
        The updated PositionGroup
    """
    # 1. Get user
    user = await session.get(User, user_id)
    if not user:
        raise UserNotFoundException(f"User {user_id} not found")

    # Dynamically get exchange connector
    exchange_connector = _get_exchange_connector_for_user(user, signal.exchange)

    # 2. Fetch precision rules
    precision_rules = await exchange_connector.get_precision_rules()
    symbol_precision = precision_rules.get(signal.symbol, {})

    # 3. Calculate DCA levels for this NEW pyramid
    next_pyramid_index = existing_position_group.pyramid_count + 1
    dca_levels = grid_calculator_service.calculate_dca_levels(
        base_price=signal.entry_price,
        dca_config=dca_grid_config,
        side=signal.side,
        precision_rules=symbol_precision,
        pyramid_index=next_pyramid_index
    )
    dca_levels = grid_calculator_service.calculate_order_quantities(
        dca_levels=dca_levels,
        total_capital_usd=total_capital_usd,
        precision_rules=symbol_precision
    )

    # 4. Update PositionGroup Stats
    pg_repo = position_group_repository_class(session)
    new_pyramid_count = await pg_repo.increment_pyramid_count(
        group_id=existing_position_group.id,
        additional_dca_legs=len(dca_levels)
    )
    await session.refresh(existing_position_group)

    # Reset risk timer on new pyramid
    if existing_position_group.risk_timer_expires is not None:
        existing_position_group.risk_timer_start = None
        existing_position_group.risk_timer_expires = None
        logger.info(f"Risk timer reset for PositionGroup {existing_position_group.id} due to new pyramid")

    # 5. Create New Pyramid
    new_pyramid = Pyramid(
        group_id=existing_position_group.id,
        pyramid_index=existing_position_group.pyramid_count,
        entry_price=signal.entry_price,
        status=PyramidStatus.PENDING,
        dca_config=json.loads(dca_grid_config.json())
    )
    session.add(new_pyramid)
    await session.flush()

    # 6. Instantiate OrderService
    order_service = order_service_class(
        session=session,
        user=user,
        exchange_connector=exchange_connector
    )

    # 7. Create DCAOrder objects
    orders_to_submit = []
    order_side = "buy" if signal.side == "long" else "sell"

    # Use entry_order_type from DCA config (same logic as initial pyramid creation)
    entry_type = dca_grid_config.entry_order_type

    for i, level in enumerate(dca_levels):
        # Apply entry_order_type to ALL DCA orders, not just the first one
        if entry_type == "market":
            current_order_type = "market"
            gap_pct = level.get('gap_percent', Decimal("0"))
            if gap_pct <= 0:
                # Market orders with gap_percent<=0 should be submitted immediately
                current_status = OrderStatus.PENDING
            else:
                # DCA legs with gap_percent > 0 wait for order_fill_monitor to trigger
                current_status = OrderStatus.TRIGGER_PENDING
        else:
            current_order_type = "limit"
            current_status = OrderStatus.PENDING

        dca_order = DCAOrder(
            group_id=existing_position_group.id,
            pyramid_id=new_pyramid.id,
            leg_index=i,
            symbol=signal.symbol,
            side=order_side,
            order_type=current_order_type,
            price=level['price'],
            quantity=level['quantity'],
            quote_amount=level.get('quote_amount'),  # USDT amount for market orders
            status=current_status,
            gap_percent=level.get('gap_percent', Decimal("0")),
            weight_percent=level.get('weight_percent', Decimal("0")),
            tp_percent=level.get('tp_percent', Decimal("0")),
            tp_price=level.get('tp_price', Decimal("0")),
        )
        session.add(dca_order)

        if current_status == OrderStatus.PENDING:
            orders_to_submit.append(dca_order)
        else:
            logger.info(f"Pyramid order leg {i} set to {current_status} (Market Watch). Not submitting yet.")

    # Submit orders sequentially to avoid SQLAlchemy session conflicts
    if orders_to_submit:
        logger.debug(f"Submitting {len(orders_to_submit)} pyramid orders sequentially")
        for order in orders_to_submit:
            try:
                await order_service.submit_order(order)
            except Exception as e:
                logger.error(f"Pyramid order {order.leg_index} failed: {e}")
                raise e

    logger.info(f"Handled pyramid continuation for PositionGroup {existing_position_group.id} from signal {signal.id}. Created {len(orders_to_submit)} new orders.")

    await update_risk_timer_func(existing_position_group.id, risk_config, session=session)
    await update_position_stats_func(existing_position_group.id, session=session)

    # Broadcast notifications to Telegram (fire-and-forget for performance)
    asyncio.create_task(broadcast_pyramid_added(existing_position_group, new_pyramid, session))
    asyncio.create_task(broadcast_entry_signal(existing_position_group, new_pyramid, session))

    return existing_position_group
