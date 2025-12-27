"""
Main Position Manager orchestrator service.
Coordinates position creation, pyramid management, and stats updates.
"""
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Callable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    broadcast_status_change,
    broadcast_tp_hit,
)

# Import from split modules
from app.services.position.position_creator import (
    UserNotFoundException,
    DuplicatePositionException,
    create_position_group_from_signal,
    handle_pyramid_continuation,
)
from app.services.position.position_closer import (
    execute_handle_exit_signal,
    save_close_action,
)

logger = logging.getLogger(__name__)

# Re-export exceptions
__all__ = [
    "PositionManagerService",
    "UserNotFoundException",
    "DuplicatePositionException",
]


class PositionManagerService:
    def __init__(
        self,
        session_factory: Callable[..., AsyncSession],
        user: "User",
        position_group_repository_class: type[PositionGroupRepository],
        grid_calculator_service: GridCalculatorService,
        order_service_class: type[OrderService],
    ):
        self.session_factory = session_factory
        self.user = user
        self.position_group_repository_class = position_group_repository_class
        self.grid_calculator_service = grid_calculator_service
        self.order_service_class = order_service_class
        self.order_service = None

    def _get_exchange_connector_for_user(self, user: User, exchange_name: str) -> ExchangeInterface:
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
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        signal: QueuedSignal,
        risk_config: RiskEngineConfig,
        dca_grid_config: DCAGridConfig,
        total_capital_usd: Decimal
    ) -> PositionGroup:
        """Create a new position group from a signal."""
        return await create_position_group_from_signal(
            session=session,
            user_id=user_id,
            signal=signal,
            risk_config=risk_config,
            dca_grid_config=dca_grid_config,
            total_capital_usd=total_capital_usd,
            position_group_repository_class=self.position_group_repository_class,
            grid_calculator_service=self.grid_calculator_service,
            order_service_class=self.order_service_class,
            update_risk_timer_func=self.update_risk_timer,
            update_position_stats_func=self.update_position_stats,
        )

    async def handle_pyramid_continuation(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        signal: QueuedSignal,
        existing_position_group: PositionGroup,
        risk_config: RiskEngineConfig,
        dca_grid_config: DCAGridConfig,
        total_capital_usd: Decimal
    ) -> PositionGroup:
        """Handle pyramid continuation for an existing position."""
        return await handle_pyramid_continuation(
            session=session,
            user_id=user_id,
            signal=signal,
            existing_position_group=existing_position_group,
            risk_config=risk_config,
            dca_grid_config=dca_grid_config,
            total_capital_usd=total_capital_usd,
            position_group_repository_class=self.position_group_repository_class,
            grid_calculator_service=self.grid_calculator_service,
            order_service_class=self.order_service_class,
            update_risk_timer_func=self.update_risk_timer,
            update_position_stats_func=self.update_position_stats,
        )

    async def handle_exit_signal(
        self,
        position_group_id: uuid.UUID,
        session: Optional[AsyncSession] = None,
        max_slippage_percent: float = 1.0,
        slippage_action: str = "warn",
        exit_reason: str = "engine"
    ):
        """
        Handles an exit signal for a position group.
        1. Cancels all open DCA orders.
        2. Places a market order to close the total filled quantity.
        """
        if session:
            await execute_handle_exit_signal(
                position_group_id=position_group_id,
                session=session,
                user=self.user,
                position_group_repository_class=self.position_group_repository_class,
                order_service_class=self.order_service_class,
                max_slippage_percent=max_slippage_percent,
                slippage_action=slippage_action,
                exit_reason=exit_reason,
            )
        else:
            async with self.session_factory() as new_session:
                await execute_handle_exit_signal(
                    position_group_id=position_group_id,
                    session=new_session,
                    user=self.user,
                    position_group_repository_class=self.position_group_repository_class,
                    order_service_class=self.order_service_class,
                    max_slippage_percent=max_slippage_percent,
                    slippage_action=slippage_action,
                    exit_reason=exit_reason,
                )
                await new_session.commit()

    async def update_risk_timer(self, position_group_id: uuid.UUID, risk_config: RiskEngineConfig, session: AsyncSession = None, position_group: Optional[PositionGroup] = None):
        if session:
            await self._execute_update_risk_timer(session, position_group_id, risk_config, position_group)
        else:
            async with self.session_factory() as new_session:
                await self._execute_update_risk_timer(new_session, position_group_id, risk_config, position_group)
                await new_session.commit()

    async def _execute_update_risk_timer(self, session: AsyncSession, position_group_id: uuid.UUID, risk_config: RiskEngineConfig, position_group: Optional[PositionGroup] = None):
        """
        Legacy timer check - the main timer logic is now handled by risk_engine.update_risk_timers().
        This just does a basic pyramid count check for initial setup.
        """
        position_group_repo = self.position_group_repository_class(session)
        if not position_group:
            position_group = await position_group_repo.get(position_group_id)

        if not position_group:
            return

        logger.debug(f"Risk timer update called for PositionGroup {position_group.id}. Timer management deferred to risk engine.")

    async def update_position_stats(self, group_id: uuid.UUID, session: AsyncSession = None) -> Optional[PositionGroup]:
        """Recalculates total filled quantity and weighted average entry price for a position group."""
        if session:
            return await self._execute_update_position_stats(session, group_id)
        else:
            async with self.session_factory() as new_session:
                position_group = await self._execute_update_position_stats(new_session, group_id)
                await new_session.commit()
                return position_group

    async def _execute_update_position_stats(self, session: AsyncSession, group_id: uuid.UUID) -> Optional[PositionGroup]:
        position_group_repo = self.position_group_repository_class(session)
        position_group = await position_group_repo.get_with_orders(group_id, refresh=True)
        if not position_group:
            logger.error(f"PositionGroup {group_id} not found for stats update.")
            return None

        all_orders = list(position_group.dca_orders)

        # --- 1. Update Pyramid Statuses ---
        pyramid_orders = {}
        for order in all_orders:
            if order.pyramid_id:
                pyramid_orders.setdefault(order.pyramid_id, []).append(order)

        for pyramid_id, orders_in_pyramid in pyramid_orders.items():
            pyramid = await session.get(Pyramid, pyramid_id)
            if not pyramid:
                continue

            any_order_submitted_or_filled = any(
                o.status in [OrderStatus.OPEN, OrderStatus.FILLED]
                for o in orders_in_pyramid
            )
            all_orders_for_pyramid_filled = all(o.status == OrderStatus.FILLED for o in orders_in_pyramid)

            if all_orders_for_pyramid_filled and pyramid.status != PyramidStatus.FILLED:
                pyramid.status = PyramidStatus.FILLED
                logger.info(f"Pyramid {pyramid.id} status updated to FILLED.")
                await broadcast_entry_signal(position_group, pyramid, session)

            elif any_order_submitted_or_filled and pyramid.status == PyramidStatus.PENDING:
                pyramid.status = PyramidStatus.SUBMITTED
                logger.info(f"Pyramid {pyramid.id} status updated to SUBMITTED.")

        # --- 2. Calculate Stats from Filled Orders ---
        filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
        filled_orders.sort(key=lambda x: x.filled_at or x.created_at or datetime.min)

        current_qty = Decimal("0")
        current_invested_usd = Decimal("0")
        total_realized_pnl = Decimal("0")
        current_avg_price = Decimal("0")

        for o in filled_orders:
            order_side = o.side.lower()
            group_side = position_group.side.lower()

            qty = o.filled_quantity
            price = o.avg_fill_price or o.price

            is_entry = False
            if group_side == "long" and order_side == "buy":
                is_entry = True
            elif group_side == "short" and order_side == "sell":
                is_entry = True

            if is_entry:
                new_invested = current_invested_usd + (qty * price)
                new_qty = current_qty + qty

                if new_qty > 0:
                    current_avg_price = new_invested / new_qty

                current_qty = new_qty
                current_invested_usd = new_invested
            else:
                if group_side == "long":
                    trade_pnl = (price - current_avg_price) * qty
                else:
                    trade_pnl = (current_avg_price - price) * qty

                total_realized_pnl += trade_pnl
                current_qty -= qty
                current_invested_usd = current_qty * current_avg_price

                if current_qty <= 0:
                    current_qty = Decimal("0")
                    current_invested_usd = Decimal("0")
                    current_avg_price = Decimal("0")

        # --- 3. Update Position Group Stats ---
        position_group.weighted_avg_entry = current_avg_price
        position_group.total_invested_usd = current_invested_usd
        position_group.total_filled_quantity = current_qty
        position_group.realized_pnl_usd = total_realized_pnl

        # Get user for exchange connector
        user = await session.get(User, position_group.user_id)
        if not user:
            logger.error(f"User {position_group.user_id} not found for position stats update.")
            return

        exchange_connector = self._get_exchange_connector_for_user(user, position_group.exchange)

        try:
            current_price = await exchange_connector.get_current_price(position_group.symbol)
            current_price = Decimal(str(current_price))

            if current_qty > 0 and current_avg_price > 0:
                if position_group.side.lower() == "long":
                    position_group.unrealized_pnl_usd = (current_price - current_avg_price) * current_qty
                else:
                    position_group.unrealized_pnl_usd = (current_avg_price - current_price) * current_qty

                if position_group.total_invested_usd > 0:
                    position_group.unrealized_pnl_percent = (position_group.unrealized_pnl_usd / position_group.total_invested_usd) * Decimal("100")
                else:
                    position_group.unrealized_pnl_percent = Decimal("0")
            else:
                position_group.unrealized_pnl_usd = Decimal("0")
                position_group.unrealized_pnl_percent = Decimal("0")

            # Update Legs Count
            filled_entry_legs = sum(1 for o in filled_orders if o.leg_index != 999 and not o.tp_hit)
            position_group.filled_dca_legs = filled_entry_legs

            # Status Transition Logic
            if position_group.status in [PositionGroupStatus.LIVE, PositionGroupStatus.PARTIALLY_FILLED]:
                old_status = position_group.status
                if filled_entry_legs >= position_group.total_dca_legs:
                    position_group.status = PositionGroupStatus.ACTIVE
                    logger.info(f"PositionGroup {group_id} transitioned to ACTIVE")
                    if position_group.pyramids:
                        active_pyramid = position_group.pyramids[0]
                        await broadcast_status_change(
                            position_group=position_group,
                            old_status=old_status,
                            new_status=PositionGroupStatus.ACTIVE,
                            pyramid=active_pyramid,
                            session=session
                        )
                elif filled_entry_legs > 0 and old_status != PositionGroupStatus.PARTIALLY_FILLED:
                    position_group.status = PositionGroupStatus.PARTIALLY_FILLED
                    if position_group.pyramids:
                        active_pyramid = position_group.pyramids[0]
                        await broadcast_status_change(
                            position_group=position_group,
                            old_status=old_status,
                            new_status=PositionGroupStatus.PARTIALLY_FILLED,
                            pyramid=active_pyramid,
                            session=session
                        )

            # Auto-close check - when all filled legs have been TP'd (qty = 0)
            if current_qty <= 0 and len(filled_orders) > 0 and position_group.status not in [PositionGroupStatus.CLOSED, PositionGroupStatus.CLOSING]:
                position_group.status = PositionGroupStatus.CLOSED
                position_group.closed_at = datetime.utcnow()

                # Cancel any remaining unfilled DCA orders
                order_service = self.order_service_class(
                    session=session,
                    user=user,
                    exchange_connector=exchange_connector
                )
                await order_service.cancel_open_orders_for_group(group_id)
                logger.info(f"Position {group_id} auto-closed (all TPs hit), cancelled remaining unfilled orders")

            await position_group_repo.update(position_group)

            # --- 4. TP Execution Logic ---
            if current_qty > 0 and position_group.status not in [PositionGroupStatus.CLOSING, PositionGroupStatus.CLOSED]:
                should_execute_tp = False

                if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
                    aggregate_tp_price = Decimal("0")
                    if position_group.side.lower() == "long":
                        aggregate_tp_price = current_avg_price * (Decimal("1") + position_group.tp_aggregate_percent / Decimal("100"))
                        if current_price >= aggregate_tp_price:
                            should_execute_tp = True
                    else:
                        aggregate_tp_price = current_avg_price * (Decimal("1") - position_group.tp_aggregate_percent / Decimal("100"))
                        if current_price <= aggregate_tp_price:
                            should_execute_tp = True

                    if should_execute_tp:
                        logger.info(f"Aggregate TP Triggered for Group {group_id} at {current_price} (Target: {aggregate_tp_price})")

                        order_service = self.order_service_class(
                            session=session,
                            user=user,
                            exchange_connector=exchange_connector
                        )

                        pnl_percent = position_group.tp_aggregate_percent
                        pnl_usd = position_group.unrealized_pnl_usd

                        await broadcast_tp_hit(
                            position_group=position_group,
                            pyramid=None,
                            tp_type="aggregate",
                            tp_price=aggregate_tp_price,
                            pnl_percent=pnl_percent,
                            session=session,
                            pnl_usd=pnl_usd,
                            closed_quantity=current_qty,
                            remaining_pyramids=0
                        )

                        await order_service.cancel_open_orders_for_group(group_id)

                        close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
                        await order_service.place_market_order(
                            user_id=user.id,
                            exchange=position_group.exchange,
                            symbol=position_group.symbol,
                            side=close_side,
                            quantity=current_qty,
                            position_group_id=group_id,
                            record_in_db=True
                        )

                        # After aggregate TP market close, position is fully closed
                        position_group.status = PositionGroupStatus.CLOSED
                        position_group.closed_at = datetime.utcnow()
                        position_group.total_filled_quantity = Decimal("0")
                        await position_group_repo.update(position_group)

                        logger.info(f"Executed Aggregate TP Market Close for Group {group_id} - Position CLOSED")

                # --- 5. Pyramid Aggregate TP Execution Logic ---
                elif position_group.tp_mode == "pyramid_aggregate" and position_group.tp_aggregate_percent > 0:
                    await self._check_pyramid_aggregate_tp(
                        session=session,
                        position_group=position_group,
                        filled_orders=filled_orders,
                        current_price=current_price,
                        user=user,
                        exchange_connector=exchange_connector,
                        position_group_repo=position_group_repo
                    )
        finally:
            await exchange_connector.close()

        return position_group

    async def _check_pyramid_aggregate_tp(
        self,
        session: AsyncSession,
        position_group: PositionGroup,
        filled_orders: List[DCAOrder],
        current_price: Decimal,
        user: User,
        exchange_connector: ExchangeInterface,
        position_group_repo: PositionGroupRepository
    ) -> None:
        """
        Check and execute pyramid-level aggregate TP.
        Each pyramid is closed independently when its weighted average entry reaches the TP target.
        """
        # Get all pyramids for this position group
        result = await session.execute(
            select(Pyramid)
            .where(Pyramid.group_id == position_group.id)
            .options(selectinload(Pyramid.dca_orders))
        )
        pyramids = result.scalars().all()

        for pyramid in pyramids:
            # Skip already closed pyramids or those with no filled orders
            pyramid_filled_orders = [
                o for o in filled_orders
                if o.pyramid_id == pyramid.id
                and o.status == OrderStatus.FILLED
                and o.leg_index != 999
                and not o.tp_hit
            ]

            if not pyramid_filled_orders:
                continue

            # Check if all orders in this pyramid have been TP'd
            pyramid_all_orders = [o for o in filled_orders if o.pyramid_id == pyramid.id and o.leg_index != 999]
            pyramid_tp_hit_orders = [o for o in pyramid_all_orders if o.tp_hit]

            if len(pyramid_tp_hit_orders) >= len(pyramid_all_orders) and len(pyramid_all_orders) > 0:
                continue

            # Calculate weighted average entry for this pyramid
            total_qty = Decimal("0")
            total_value = Decimal("0")

            for order in pyramid_filled_orders:
                qty = order.filled_quantity or order.quantity
                price = order.avg_fill_price or order.price
                total_qty += qty
                total_value += qty * price

            if total_qty <= 0:
                continue

            pyramid_avg_entry = total_value / total_qty

            # Calculate pyramid TP target
            pyramid_config = pyramid.dca_config or {}
            pyramid_tp_percents = pyramid_config.get("pyramid_tp_percents", {})
            pyramid_index_key = str(pyramid.pyramid_index)

            if pyramid_index_key in pyramid_tp_percents:
                tp_percent = Decimal(str(pyramid_tp_percents[pyramid_index_key]))
            else:
                tp_percent = position_group.tp_aggregate_percent

            if position_group.side.lower() == "long":
                pyramid_tp_price = pyramid_avg_entry * (Decimal("1") + tp_percent / Decimal("100"))
                tp_triggered = current_price >= pyramid_tp_price
            else:
                pyramid_tp_price = pyramid_avg_entry * (Decimal("1") - tp_percent / Decimal("100"))
                tp_triggered = current_price <= pyramid_tp_price

            if tp_triggered:
                logger.info(
                    f"Pyramid Aggregate TP Triggered for Pyramid {pyramid.pyramid_index} in Group {position_group.id} "
                    f"at {current_price} (Target: {pyramid_tp_price}, Avg Entry: {pyramid_avg_entry})"
                )

                # Calculate PnL for notification
                if position_group.side.lower() == "long":
                    pnl_usd = (current_price - pyramid_avg_entry) * total_qty
                else:
                    pnl_usd = (pyramid_avg_entry - current_price) * total_qty

                remaining_pyramids = len([p for p in pyramids if p.id != pyramid.id])

                await broadcast_tp_hit(
                    position_group=position_group,
                    pyramid=pyramid,
                    tp_type="pyramid_aggregate",
                    tp_price=pyramid_tp_price,
                    pnl_percent=tp_percent,
                    session=session,
                    pnl_usd=pnl_usd,
                    closed_quantity=total_qty,
                    remaining_pyramids=remaining_pyramids
                )

                order_service = self.order_service_class(
                    session=session,
                    user=user,
                    exchange_connector=exchange_connector
                )

                # Cancel any open orders for this pyramid's legs
                for order in pyramid_filled_orders:
                    if order.tp_order_id:
                        try:
                            await exchange_connector.cancel_order(
                                order.tp_order_id,
                                position_group.symbol
                            )
                            logger.info(f"Cancelled TP order {order.tp_order_id} for pyramid {pyramid.pyramid_index}")
                        except Exception as e:
                            logger.warning(f"Failed to cancel TP order {order.tp_order_id}: {e}")

                # Execute Market Close for pyramid quantity
                close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
                await order_service.place_market_order(
                    user_id=user.id,
                    exchange=position_group.exchange,
                    symbol=position_group.symbol,
                    side=close_side,
                    quantity=total_qty,
                    position_group_id=position_group.id,
                    record_in_db=True
                )

                # Mark pyramid orders as TP hit
                for order in pyramid_filled_orders:
                    order.tp_hit = True
                    order.tp_executed_at = datetime.utcnow()

                # Update pyramid status to FILLED (indicating TP executed and pyramid is closed)
                pyramid.status = PyramidStatus.FILLED
                logger.info(f"Pyramid {pyramid.pyramid_index} status updated to FILLED after aggregate TP execution")

                # Check if all pyramids are now closed
                all_pyramids_closed = all(
                    p.status == PyramidStatus.FILLED or
                    (p.id == pyramid.id)  # Current pyramid is being closed
                    for p in pyramids
                )

                if all_pyramids_closed:
                    # All pyramids have been TP'd, close the position
                    position_group.status = PositionGroupStatus.CLOSED
                    position_group.closed_at = datetime.utcnow()
                    await position_group_repo.update(position_group)
                    logger.info(f"All pyramids closed for Group {position_group.id} - Position CLOSED")

                logger.info(f"Executed Pyramid Aggregate TP Market Close for Pyramid {pyramid.pyramid_index}, Qty: {total_qty}")
