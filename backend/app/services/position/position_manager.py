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
    broadcast_exit_signal,
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
                update_position_stats_func=self.update_position_stats,
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
                    update_position_stats_func=self.update_position_stats,
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

        # Log order details for debugging
        buy_orders = [o for o in filled_orders if o.side.lower() == 'buy']
        sell_orders = [o for o in filled_orders if o.side.lower() == 'sell']
        logger.debug(
            f"Stats calculation for {group_id}: {len(filled_orders)} filled orders "
            f"({len(buy_orders)} buys, {len(sell_orders)} sells)"
        )

        current_qty = Decimal("0")
        current_invested_usd = Decimal("0")
        total_realized_pnl = Decimal("0")
        current_avg_price = Decimal("0")
        total_entry_fees = Decimal("0")
        total_exit_fees = Decimal("0")

        for o in filled_orders:
            order_side = o.side.lower()
            group_side = position_group.side.lower()

            qty = o.filled_quantity
            price = o.avg_fill_price or o.price
            order_fee = o.fee or Decimal("0")
            fee_currency = (o.fee_currency or "").upper()

            # Determine if fee is in quote currency (USDT/BUSD/USDC)
            # Only add fee to investment/PnL if it's in quote currency
            # If fee is in base currency (e.g., BTC) or BNB, it's already deducted from qty/separate
            quote_currencies = {"USDT", "BUSD", "USDC", "USD", "TUSD", "DAI"}
            fee_in_quote = fee_currency in quote_currencies

            # Convert fee to USD for tracking purposes
            # If fee is in base currency, multiply by price to get USD value
            if fee_in_quote:
                fee_usd = order_fee
            else:
                # Fee is in base currency (e.g., BTC) - convert to USD
                fee_usd = order_fee * price if price and price > 0 else order_fee

            # For SPOT trading: All positions are "long"
            # "buy" orders are entries, "sell" orders are exits
            is_entry = (order_side == "buy")

            if is_entry:
                # Investment = qty * price
                # Only add fee if it was paid in quote currency (USDT)
                # If fee was in base currency, qty already reflects net received
                if fee_in_quote:
                    new_invested = current_invested_usd + (qty * price) + order_fee
                else:
                    # Fee was in base currency or BNB - don't add to investment
                    # But we still track the USD value of the fee
                    new_invested = current_invested_usd + (qty * price)
                new_qty = current_qty + qty
                total_entry_fees += fee_usd  # Always store in USD

                if new_qty > 0:
                    current_avg_price = new_invested / new_qty

                current_qty = new_qty
                current_invested_usd = new_invested
            else:
                # For SPOT trading: All positions are "long"
                # PnL = (sell_price - avg_entry_price) * quantity
                # Only subtract fee if it was paid in quote currency
                if fee_in_quote:
                    trade_pnl = (price - current_avg_price) * qty - order_fee
                else:
                    # Fee was in base currency or BNB - don't subtract from PnL
                    # (it's already reflected in the received amount)
                    trade_pnl = (price - current_avg_price) * qty
                total_realized_pnl += trade_pnl
                total_exit_fees += fee_usd  # Always store in USD
                current_qty -= qty

                if current_qty <= 0:
                    current_qty = Decimal("0")
                    # Note: Do NOT zero out current_invested_usd and current_avg_price here
                    # These values are preserved for historical record when position is closed
                    # The invested amount represents what was put in, and avg_price is the entry
                else:
                    # Only recalculate invested when position still open
                    current_invested_usd = current_qty * current_avg_price

        # --- 3. Update Position Group Stats ---
        # For hybrid/per_leg modes: recalculate weighted_avg_entry based only on entries
        # that haven't hit their per-leg TP yet (tp_hit = false)
        if position_group.tp_mode in ["hybrid", "per_leg"] and current_qty > 0:
            remaining_qty = Decimal("0")
            remaining_value = Decimal("0")

            for o in filled_orders:
                if o.side.lower() == "buy" and not o.tp_hit:
                    qty = o.filled_quantity
                    price = o.avg_fill_price or o.price
                    remaining_qty += qty
                    remaining_value += qty * price

            if remaining_qty > 0:
                # Use the remaining position's weighted average for aggregate TP calculation
                current_avg_price = remaining_value / remaining_qty
                # Use actual position quantity for invested calculation
                current_invested_usd = current_qty * current_avg_price
                logger.debug(
                    f"Hybrid/Per-leg mode: Recalculated avg entry from remaining orders. "
                    f"Remaining qty: {remaining_qty}, Current qty: {current_qty}, Avg price: {current_avg_price}"
                )

        position_group.weighted_avg_entry = current_avg_price
        position_group.total_invested_usd = current_invested_usd
        position_group.total_filled_quantity = current_qty
        position_group.realized_pnl_usd = total_realized_pnl
        position_group.total_entry_fees_usd = total_entry_fees
        position_group.total_exit_fees_usd = total_exit_fees

        # Get user for exchange connector
        user = await session.get(User, position_group.user_id)
        if not user:
            logger.error(f"User {position_group.user_id} not found for position stats update.")
            return

        exchange_connector = self._get_exchange_connector_for_user(user, position_group.exchange)

        try:
            current_price = await exchange_connector.get_current_price(position_group.symbol)
            current_price = Decimal(str(current_price))

            # Fetch dynamic fee rate from exchange (fallback to 0.1% if unavailable)
            try:
                fee_rate = Decimal(str(await exchange_connector.get_trading_fee_rate(position_group.symbol)))
            except Exception:
                fee_rate = Decimal("0.001")  # 0.1% fallback

            if current_qty > 0 and current_avg_price > 0:
                # For SPOT trading: All positions are "long"
                # Unrealized PnL = (current_price - avg_entry) * quantity - estimated_exit_fee
                # Use dynamic fee rate from exchange
                estimated_exit_value = current_price * current_qty
                estimated_exit_fee = estimated_exit_value * fee_rate
                position_group.unrealized_pnl_usd = (current_price - current_avg_price) * current_qty - estimated_exit_fee

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
            logger.debug(
                f"Auto-close check for {group_id}: current_qty={current_qty}, "
                f"filled_orders={len(filled_orders)}, status={position_group.status}"
            )
            if current_qty <= 0 and len(filled_orders) > 0 and position_group.status not in [PositionGroupStatus.CLOSED, PositionGroupStatus.CLOSING]:
                logger.info(f"Position {group_id} auto-closing: all TPs hit (qty=0, {len(filled_orders)} filled orders)")
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

                # Send exit signal for auto-close (all TPs hit)
                try:
                    await broadcast_exit_signal(
                        position_group=position_group,
                        exit_price=current_price,
                        session=session,
                        exit_reason="tp_hit"
                    )
                except Exception as tg_err:
                    logger.warning(f"Failed to broadcast exit signal for auto-close: {tg_err}")

            await position_group_repo.update(position_group)

            # --- 4. TP Execution Logic ---
            if current_qty > 0 and position_group.status not in [PositionGroupStatus.CLOSING, PositionGroupStatus.CLOSED]:
                should_execute_tp = False

                if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
                    # For SPOT trading: All positions are "long"
                    # TP triggers when price rises above entry + TP%
                    aggregate_tp_price = current_avg_price * (Decimal("1") + position_group.tp_aggregate_percent / Decimal("100"))
                    if current_price >= aggregate_tp_price:
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

                        # For SPOT trading: All positions are "long", so we SELL to close
                        close_side = "SELL"
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

        logger.debug(
            f"_check_pyramid_aggregate_tp: Checking {len(pyramids)} pyramids for {position_group.symbol} "
            f"(ID: {position_group.id}), current_price={current_price}"
        )

        for pyramid in pyramids:
            # Debug: Log all orders for this pyramid
            all_pyramid_orders = [o for o in filled_orders if o.pyramid_id == pyramid.id]
            logger.debug(
                f"_check_pyramid_aggregate_tp: Pyramid {pyramid.pyramid_index} has {len(all_pyramid_orders)} filled orders. "
                f"Statuses: {[(o.leg_index, str(o.status), o.tp_hit) for o in all_pyramid_orders]}"
            )

            # Skip already closed pyramids or those with no filled orders
            # Handle both enum and string status comparison
            def is_filled(status):
                if status == OrderStatus.FILLED:
                    return True
                if hasattr(status, 'value') and status.value == 'filled':
                    return True
                if str(status).lower() == 'filled' or str(status) == 'OrderStatus.FILLED':
                    return True
                return False

            pyramid_filled_orders = [
                o for o in filled_orders
                if o.pyramid_id == pyramid.id
                and is_filled(o.status)
                and o.leg_index != 999
                and not o.tp_hit
            ]

            logger.debug(
                f"_check_pyramid_aggregate_tp: Pyramid {pyramid.pyramid_index} - "
                f"{len(pyramid_filled_orders)} orders eligible for TP check"
            )

            if not pyramid_filled_orders:
                continue

            # Check if all orders in this pyramid have been TP'd
            pyramid_all_orders = [o for o in filled_orders if o.pyramid_id == pyramid.id and o.leg_index != 999]
            pyramid_tp_hit_orders = [o for o in pyramid_all_orders if o.tp_hit]

            if len(pyramid_tp_hit_orders) >= len(pyramid_all_orders) and len(pyramid_all_orders) > 0:
                logger.debug(f"_check_pyramid_aggregate_tp: Pyramid {pyramid.pyramid_index} - all orders already TP'd, skipping")
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
                logger.debug(f"_check_pyramid_aggregate_tp: Pyramid {pyramid.pyramid_index} - total_qty <= 0, skipping")
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

            # For SPOT trading: All positions are "long"
            # TP triggers when price rises above entry + TP%
            pyramid_tp_price = pyramid_avg_entry * (Decimal("1") + tp_percent / Decimal("100"))
            tp_triggered = current_price >= pyramid_tp_price

            logger.info(
                f"_check_pyramid_aggregate_tp: Pyramid {pyramid.pyramid_index} TP Check - "
                f"avg_entry={pyramid_avg_entry:.4f}, tp_percent={tp_percent}%, "
                f"tp_target={pyramid_tp_price:.4f}, current_price={current_price}, "
                f"triggered={tp_triggered}"
            )

            if tp_triggered:
                logger.info(
                    f"Pyramid Aggregate TP Triggered for Pyramid {pyramid.pyramid_index} in Group {position_group.id} "
                    f"at {current_price} (Target: {pyramid_tp_price}, Avg Entry: {pyramid_avg_entry})"
                )

                # For SPOT trading: All positions are "long"
                # PnL = (current_price - avg_entry) * quantity
                pnl_usd = (current_price - pyramid_avg_entry) * total_qty

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

                # For SPOT trading: All positions are "long", so we SELL to close
                close_side = "SELL"
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
                    # Cancel any remaining open orders on the exchange
                    await order_service.cancel_open_orders_for_group(position_group.id)
                    await position_group_repo.update(position_group)
                    logger.info(f"All pyramids closed for Group {position_group.id} - Position CLOSED")

                logger.info(f"Executed Pyramid Aggregate TP Market Close for Pyramid {pyramid.pyramid_index}, Qty: {total_qty}")
