"""
Main Risk Engine orchestrator service.
Coordinates timer management, loser/winner selection, and offset execution.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid
from app.models.queued_signal import QueuedSignal
from app.models.risk_action import RiskAction, RiskActionType
from app.models.user import User
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.repositories.user import UserRepository
from app.schemas.grid_config import RiskEngineConfig
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.order_management import OrderService
from app.services.telegram_signal_helper import broadcast_risk_event

# Import from split modules
from app.services.risk.risk_selector import (
    _check_pyramids_complete,
    _filter_eligible_losers,
    select_loser_and_winners,
)
from app.services.risk.risk_timer import update_risk_timers
from app.services.risk.risk_executor import calculate_partial_close_quantities

from fastapi import HTTPException, status

# Lock TTL for offset execution (60 seconds)
OFFSET_LOCK_TTL = 60

logger = logging.getLogger(__name__)


class RiskEngineService:
    def __init__(
        self,
        session_factory: callable,
        position_group_repository_class: type[PositionGroupRepository],
        risk_action_repository_class: type[RiskActionRepository],
        dca_order_repository_class: type[DCAOrderRepository],
        order_service_class: type[OrderService],
        risk_engine_config: RiskEngineConfig,
        polling_interval_seconds: int = None,
        user: Optional[User] = None
    ):
        self.session_factory = session_factory
        self.position_group_repository_class = position_group_repository_class
        self.risk_action_repository_class = risk_action_repository_class
        self.dca_order_repository_class = dca_order_repository_class
        self.order_service_class = order_service_class
        # Use config value if polling_interval_seconds not explicitly provided
        self.polling_interval_seconds = polling_interval_seconds if polling_interval_seconds is not None else risk_engine_config.evaluate_interval_seconds
        self.config = risk_engine_config
        self.user = user
        self._running = False
        self._monitor_task = None

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

    async def validate_pre_trade_risk(
        self,
        signal: QueuedSignal,
        active_positions: List[PositionGroup],
        allocated_capital_usd: Decimal,
        session: AsyncSession,
        is_pyramid_continuation: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Performs pre-trade risk checks before promoting a signal.

        Returns:
            Tuple of (is_allowed, rejection_reason)
        """
        # 0. Check if engine is paused or force stopped
        # SECURITY: Always check from USER's config to ensure proper per-user isolation
        # Do NOT rely on self.config as it may be a shared global instance
        user_config = self.config
        if self.user and self.user.risk_config:
            try:
                user_config = RiskEngineConfig(**self.user.risk_config)
            except Exception:
                pass  # Fall back to self.config

        if user_config.engine_paused_by_loss_limit:
            return False, "Engine paused due to max realized loss limit"
        if user_config.engine_force_stopped:
            return False, "Engine force stopped by user"

        # 1. Max Open Positions Global
        # NOTE: This check is now handled by ExecutionPoolManager.request_slot()
        # which queues signals when pool is full instead of rejecting them.
        # We skip this check here to allow proper queue behavior.
        # The pool manager will prevent actual execution if pool is full.

        # 2. Max Open Positions Per Symbol/Timeframe/Exchange combination
        if not is_pyramid_continuation:
            # Check for positions with same symbol, timeframe, AND exchange
            matching_positions = [
                p for p in active_positions
                if p.symbol == signal.symbol
                and p.timeframe == signal.timeframe
                and p.exchange.lower() == signal.exchange.lower()
            ]
            if len(matching_positions) >= self.config.max_open_positions_per_symbol:
                position_key = f"{signal.symbol}/{signal.timeframe}m/{signal.exchange}"
                return False, f"Max positions for {position_key} reached ({len(matching_positions)}/{self.config.max_open_positions_per_symbol})"

        # 3. Max Total Exposure
        current_exposure = sum(p.total_invested_usd for p in active_positions)
        if (current_exposure + allocated_capital_usd) > self.config.max_total_exposure_usd:
            return False, f"Max exposure reached ({current_exposure + allocated_capital_usd} > {self.config.max_total_exposure_usd})"

        # 4. Max Realized Loss Check (Circuit Breaker for Queue)
        position_group_repo = self.position_group_repository_class(session)
        daily_pnl = await position_group_repo.get_daily_realized_pnl(user_id=signal.user_id)

        if daily_pnl < 0 and abs(daily_pnl) >= self.config.max_realized_loss_usd:
            return False, f"Max realized loss limit reached ({daily_pnl} USD). Limit: {self.config.max_realized_loss_usd}"

        return True, None

    async def _evaluate_positions(self):
        """
        Evaluates all active positions for risk management and initiates offset if conditions are met.
        Iterates through all active users to ensure isolation.
        """
        async for session in self.session_factory():
            try:
                user_repo = UserRepository(session)
                active_users = await user_repo.get_all_active_users()

                for user in active_users:
                    try:
                        await self._evaluate_user_positions(session, user)
                    except Exception as e:
                        logger.error(f"Risk Engine: Error processing user {user.id}: {e}")
            except Exception as e:
                logger.error(f"Risk Engine: Critical error in evaluation loop: {e}")

    async def _evaluate_user_positions(self, session: AsyncSession, user: User):
        """
        Evaluates positions for a single user.

        Process:
        1. Update timers for all positions based on current conditions
        2. Select eligible loser and winners
        3. Execute offset (close loser and partial close winners SIMULTANEOUSLY)
        """
        try:
            position_group_repo = self.position_group_repository_class(session)
            risk_action_repo = self.risk_action_repository_class(session)

            # 1. Get User Positions
            all_positions = await position_group_repo.get_all_active_by_user(user.id)

            if not all_positions:
                return

            # 2. Determine Risk Config (User > Global)
            config = self.config
            if user.risk_config:
                try:
                    if isinstance(user.risk_config, dict):
                        config = RiskEngineConfig(**user.risk_config)
                except Exception as e:
                    logger.warning(f"Risk Engine: Invalid config for user {user.id}, using default. Error: {e}")

            # 3. Update risk timers for all positions
            await update_risk_timers(all_positions, config, session)
            await session.commit()

            # 4. Select Loser and Winners
            loser, winners, required_usd = select_loser_and_winners(all_positions, config)

            if loser and winners:
                # Capture the loss value BEFORE any position updates
                # (unrealized_pnl_usd gets reset to 0 when position is closed)
                captured_loser_pnl_usd = loser.unrealized_pnl_usd

                logger.info(
                    f"Risk Engine: Identified loser {loser.symbol} for user {user.id} "
                    f"(loss: {loser.unrealized_pnl_usd} USD) and {len(winners)} winners."
                )

                # Acquire distributed lock to prevent concurrent offset execution for same loser
                cache = await get_cache()
                lock_resource = f"risk_offset:{loser.id}"
                lock_id = str(uuid.uuid4())
                lock_acquired = await cache.acquire_lock(lock_resource, lock_id, OFFSET_LOCK_TTL)

                if not lock_acquired:
                    logger.warning(
                        f"Risk Engine: Another offset execution in progress for {loser.symbol}. Skipping."
                    )
                    return

                try:
                    # Get exchange connector
                    exchange_config = {}
                    encrypted_data = user.encrypted_api_keys
                    target_exchange = loser.exchange.lower()

                    if isinstance(encrypted_data, dict):
                        if target_exchange in encrypted_data:
                            exchange_config = encrypted_data[target_exchange]
                        elif "encrypted_data" not in encrypted_data:
                            logger.error(f"Risk Engine: Keys for {target_exchange} not found for user {user.id}. Skipping.")
                            await cache.release_lock(lock_resource, lock_id)
                            return
                        else:
                            exchange_config = {"encrypted_data": encrypted_data}
                    elif isinstance(encrypted_data, str):
                        exchange_config = {"encrypted_data": encrypted_data}
                    else:
                        logger.error(f"Risk Engine: Invalid format for encrypted_api_keys for user {user.id}. Skipping.")
                        await cache.release_lock(lock_resource, lock_id)
                        return

                    exchange_connector = get_exchange_connector(
                        exchange_type=loser.exchange,
                        exchange_config=exchange_config
                    )
                except Exception as e:
                    logger.error(f"Risk Engine: Failed to initialize exchange connector for user {user.id}: {e}")
                    await cache.release_lock(lock_resource, lock_id)
                    return

                # Fetch dynamic fee rate from exchange (fallback to 0.1% if unavailable)
                try:
                    fee_rate = Decimal(str(await exchange_connector.get_trading_fee_rate(loser.symbol)))
                except Exception:
                    fee_rate = Decimal("0.001")  # 0.1% fallback

                # Adjust required_usd to account for exit fees on both loser and winner
                # Loser exit fee: based on loser's position value
                # Winner exit fee: approximately equal to required_usd since we close that much value
                loser_exit_fee_estimate = (loser.total_invested_usd or Decimal("0")) * fee_rate
                winner_exit_fee_estimate = required_usd * fee_rate
                fee_adjusted_required_usd = required_usd + loser_exit_fee_estimate + winner_exit_fee_estimate
                logger.debug(
                    f"Risk Engine: Adjusting required_usd for fees. "
                    f"Original: {required_usd}, Loser exit fee: {loser_exit_fee_estimate}, "
                    f"Winner exit fee: {winner_exit_fee_estimate}, Adjusted: {fee_adjusted_required_usd}"
                )

                # Instantiate OrderService
                order_service = self.order_service_class(
                    session=session,
                    user=user,
                    exchange_connector=exchange_connector
                )

                # Calculate partial close quantities using fee-adjusted amount
                close_plan = await calculate_partial_close_quantities(user, winners, fee_adjusted_required_usd)

                if not close_plan and required_usd > 0:
                    logger.warning(f"Risk Engine: No winners could be partially closed for loser {loser.symbol}. Skipping offset.")
                    await cache.release_lock(lock_resource, lock_id)
                    return

                # Get pyramid for loser
                loser_pyramid_result = await session.execute(
                    select(Pyramid).where(Pyramid.group_id == loser.id).limit(1)
                )
                loser_pyramid = loser_pyramid_result.scalar_one_or_none()
                if not loser_pyramid:
                    logger.error(f"Risk Engine: No pyramid found for loser {loser.symbol}. Cannot place close order.")
                    await cache.release_lock(lock_resource, lock_id)
                    return

                # Mark loser as CLOSING before placing orders to prevent re-selection
                # IMPORTANT: We commit immediately so other risk engine evaluations
                # can see this status change and skip this loser
                loser.status = PositionGroupStatus.CLOSING.value
                await position_group_repo.update(loser)
                await session.commit()
                logger.info(f"Risk Engine: Loser {loser.symbol} marked as CLOSING and committed to prevent re-selection")

                # Cancel pending orders on loser before closing
                try:
                    await order_service.cancel_open_orders_for_group(loser.id)
                    logger.info(f"Risk Engine: Cancelled pending orders for loser {loser.symbol} (ID: {loser.id}).")
                except Exception as cancel_err:
                    logger.warning(f"Risk Engine: Failed to cancel orders for loser {loser.symbol}: {cancel_err}")

                # Prepare all close orders for SIMULTANEOUS execution
                close_tasks = []

                # Add loser close task
                close_tasks.append(
                    order_service.place_market_order(
                        user_id=loser.user_id,
                        exchange=loser.exchange,
                        symbol=loser.symbol,
                        side="sell" if loser.side == "long" else "buy",
                        quantity=loser.total_filled_quantity,
                        position_group_id=loser.id,
                        pyramid_id=loser_pyramid.id,
                        record_in_db=True
                    )
                )

                # Prepare winner close tasks
                winner_details = []
                # Track winner positions and their close quantities for hedge tracking
                winner_close_info = []  # List of (winner_pg, quantity_to_close, task_index)
                for winner_pg, quantity_to_close in close_plan:
                    # Get pyramid for winner
                    winner_pyramid_result = await session.execute(
                        select(Pyramid).where(Pyramid.group_id == winner_pg.id).limit(1)
                    )
                    winner_pyramid = winner_pyramid_result.scalar_one_or_none()
                    if not winner_pyramid:
                        logger.warning(f"Risk Engine: No pyramid found for winner {winner_pg.symbol}. Skipping.")
                        continue

                    # Cancel pending orders on winner before closing
                    try:
                        await order_service.cancel_open_orders_for_group(winner_pg.id)
                        logger.info(f"Risk Engine: Cancelled pending orders for winner {winner_pg.symbol} (ID: {winner_pg.id}).")
                    except Exception as cancel_err:
                        logger.warning(f"Risk Engine: Failed to cancel orders for winner {winner_pg.symbol}: {cancel_err}")

                    # Track task index (loser is at index 0, winners start at 1)
                    task_index = len(close_tasks)
                    winner_close_info.append((winner_pg, quantity_to_close, task_index))

                    # Add winner close task
                    close_tasks.append(
                        order_service.place_market_order(
                            user_id=winner_pg.user_id,
                            exchange=winner_pg.exchange,
                            symbol=winner_pg.symbol,
                            side="sell" if winner_pg.side == "long" else "buy",
                            quantity=quantity_to_close,
                            position_group_id=winner_pg.id,
                            pyramid_id=winner_pyramid.id,
                            record_in_db=True
                        )
                    )
                    winner_details.append({
                        "group_id": str(winner_pg.id),
                        "symbol": winner_pg.symbol,
                        "pnl_usd": str(winner_pg.unrealized_pnl_usd),
                        "quantity_closed": str(quantity_to_close)
                    })

                # Execute close orders SEQUENTIALLY to avoid session contention
                # (asyncio.gather with shared session causes "Session is already flushing" errors)
                logger.info(f"Risk Engine: Executing {len(close_tasks)} close orders sequentially...")
                results = []
                for task in close_tasks:
                    try:
                        result = await task
                        results.append(result)
                    except Exception as e:
                        results.append(e)

                # Check results
                success_count = 0
                error_count = 0
                loser_close_success = False
                for idx, result in enumerate(results):
                    if isinstance(result, Exception):
                        error_count += 1
                        logger.error(f"Risk Engine: Close order {idx} failed: {result}")
                    else:
                        success_count += 1
                        # First task (idx=0) is always the loser close
                        if idx == 0:
                            loser_close_success = True

                logger.info(f"Risk Engine: Sequential execution completed. Success: {success_count}, Errors: {error_count}")

                # Update loser status based on execution result
                if loser_close_success:
                    # Get current price for PnL calculation
                    try:
                        current_price = Decimal(str(await exchange_connector.get_current_price(loser.symbol)))
                    except Exception:
                        current_price = loser.weighted_avg_entry  # Fallback

                    # Calculate realized PnL with estimated exit fee
                    exit_value = loser.total_filled_quantity * current_price
                    cost_basis = loser.total_invested_usd  # Already includes entry fees
                    # Estimate exit fee using dynamic rate from exchange
                    estimated_exit_fee = exit_value * fee_rate
                    if loser.side == "long":
                        realized_pnl = exit_value - cost_basis - estimated_exit_fee
                    else:
                        realized_pnl = cost_basis - exit_value - estimated_exit_fee

                    # Mark loser as CLOSED
                    loser.status = PositionGroupStatus.CLOSED.value
                    loser.realized_pnl_usd = realized_pnl
                    loser.unrealized_pnl_usd = Decimal("0")
                    loser.total_exit_fees_usd = (loser.total_exit_fees_usd or Decimal("0")) + estimated_exit_fee
                    loser.closed_at = datetime.utcnow()
                    await position_group_repo.update(loser)
                    logger.info(f"Risk Engine: Loser {loser.symbol} marked as CLOSED. Realized PnL: {realized_pnl}, Exit fee: {estimated_exit_fee}")

                    # Update hedge tracking for successful winner closes
                    for winner_pg, qty_closed, task_idx in winner_close_info:
                        if not isinstance(results[task_idx], Exception):
                            # Get current price for this winner's symbol
                            # IMPORTANT: Use the winner's exchange connector, not the loser's
                            try:
                                if winner_pg.exchange.lower() != loser.exchange.lower():
                                    # Winner is on a different exchange - get appropriate connector
                                    winner_connector = self._get_exchange_connector_for_user(user, winner_pg.exchange)
                                    winner_price = Decimal(str(await winner_connector.get_current_price(winner_pg.symbol)))
                                    await winner_connector.close()
                                else:
                                    winner_price = Decimal(str(await exchange_connector.get_current_price(winner_pg.symbol)))
                            except Exception:
                                winner_price = winner_pg.weighted_avg_entry  # Fallback

                            # Calculate REALIZED PROFIT from the hedge (not notional value)
                            # Profit = (exit_price - entry_price) * quantity - exit_fee for long
                            # Profit = (entry_price - exit_price) * quantity - exit_fee for short
                            exit_value_winner = winner_price * qty_closed
                            estimated_winner_exit_fee = exit_value_winner * fee_rate
                            if winner_pg.side == "long":
                                hedge_profit = (winner_price - winner_pg.weighted_avg_entry) * qty_closed - estimated_winner_exit_fee
                            else:
                                hedge_profit = (winner_pg.weighted_avg_entry - winner_price) * qty_closed - estimated_winner_exit_fee

                            # Accumulate hedge tracking (add to existing values)
                            # total_hedged_qty: quantity that was closed for offset
                            # total_hedged_value_usd: PROFIT realized from the hedge (not notional)
                            winner_pg.total_hedged_qty = (winner_pg.total_hedged_qty or Decimal("0")) + qty_closed
                            winner_pg.total_hedged_value_usd = (winner_pg.total_hedged_value_usd or Decimal("0")) + hedge_profit
                            winner_pg.total_exit_fees_usd = (winner_pg.total_exit_fees_usd or Decimal("0")) + estimated_winner_exit_fee

                            # Proportionally reduce invested and entry fees based on closed fraction
                            # This keeps fee percentages accurate after partial closes
                            original_qty = winner_pg.total_filled_quantity  # Before reduction
                            if original_qty > 0:
                                close_fraction = qty_closed / original_qty
                                invested_to_remove = (winner_pg.total_invested_usd or Decimal("0")) * close_fraction
                                entry_fee_to_remove = (winner_pg.total_entry_fees_usd or Decimal("0")) * close_fraction
                                winner_pg.total_invested_usd = (winner_pg.total_invested_usd or Decimal("0")) - invested_to_remove
                                winner_pg.total_entry_fees_usd = (winner_pg.total_entry_fees_usd or Decimal("0")) - entry_fee_to_remove

                            # Also reduce the winner's total_filled_quantity by the closed amount
                            winner_pg.total_filled_quantity = winner_pg.total_filled_quantity - qty_closed

                            # Recalculate unrealized PnL based on remaining quantity
                            # If all quantity is closed, PnL should be 0
                            if winner_pg.total_filled_quantity <= 0:
                                winner_pg.unrealized_pnl_usd = Decimal("0")
                                winner_pg.unrealized_pnl_percent = Decimal("0")
                            else:
                                # Recalculate based on remaining quantity with estimated exit fee
                                remaining_qty = winner_pg.total_filled_quantity
                                remaining_exit_value = winner_price * remaining_qty
                                remaining_exit_fee = remaining_exit_value * fee_rate
                                if winner_pg.side == "long":
                                    winner_pg.unrealized_pnl_usd = (winner_price - winner_pg.weighted_avg_entry) * remaining_qty - remaining_exit_fee
                                else:
                                    winner_pg.unrealized_pnl_usd = (winner_pg.weighted_avg_entry - winner_price) * remaining_qty - remaining_exit_fee

                            await position_group_repo.update(winner_pg)
                            logger.info(
                                f"Risk Engine: Updated hedge tracking for winner {winner_pg.symbol}: "
                                f"qty_closed={qty_closed}, profit_realized=${hedge_profit:.2f}, "
                                f"cumulative_hedged_qty={winner_pg.total_hedged_qty}, "
                                f"cumulative_hedged_profit=${winner_pg.total_hedged_value_usd:.2f}"
                            )
                else:
                    # Loser close failed - revert to previous status so it can be retried
                    loser.status = PositionGroupStatus.ACTIVE.value
                    await position_group_repo.update(loser)
                    logger.error(f"Risk Engine: Loser {loser.symbol} close failed. Reverted to ACTIVE for retry.")

                # Record risk action with the captured loss value (before position was closed)
                risk_action = RiskAction(
                    group_id=loser.id,
                    action_type=RiskActionType.OFFSET_LOSS,
                    loser_group_id=loser.id,
                    loser_pnl_usd=captured_loser_pnl_usd,
                    winner_details=winner_details,
                    notes=f"Simultaneous execution: {success_count} success, {error_count} errors"
                )
                await risk_action_repo.create(risk_action)

                # Calculate total offset profit from winners
                total_offset_profit = sum(
                    Decimal(str(w.get('pnl_usd', 0)))
                    for w in winner_details if w.get('pnl_usd')
                ) if winner_details else Decimal("0")

                # Calculate net result
                net_result = total_offset_profit - abs(loser.unrealized_pnl_usd)

                # Get winner symbols for notification
                offset_positions = ", ".join([w.get('symbol', 'Unknown') for w in winner_details]) if winner_details else "None"

                # Broadcast offset executed event
                await broadcast_risk_event(
                    position_group=loser,
                    event_type="offset_executed",
                    session=session,
                    loss_percent=loser.unrealized_pnl_percent,
                    loss_usd=loser.unrealized_pnl_usd,
                    offset_position=offset_positions,
                    offset_profit=total_offset_profit,
                    net_result=net_result
                )

                # Clear skip_once flag if it was set
                if loser.risk_skip_once:
                    loser.risk_skip_once = False

                await session.commit()
                logger.info(f"Risk Engine: Offset for {loser.symbol} successfully executed and recorded.")

                # Cleanup exchange connector
                try:
                    await exchange_connector.close()
                except Exception as close_err:
                    logger.debug(f"Risk Engine: Error closing exchange connector: {close_err}")
                finally:
                    # Always release the distributed lock
                    released = await cache.release_lock(lock_resource, lock_id)
                    if not released:
                        logger.warning(f"Risk Engine: Failed to release offset lock for {loser.symbol}")
            else:
                logger.debug(f"Risk Engine: No eligible loser or winners found for user {user.id}.")
        except Exception as e:
            logger.error(f"Risk Engine: Error evaluating positions for user {user.id}. Rolling back: {e}")
            await session.rollback()

    async def start_monitoring_task(self):
        """Starts the background task for the Risk Engine."""
        if not self._running:
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitoring_loop())
            logger.info("RiskEngineService monitoring task started.")

    async def _monitoring_loop(self):
        """The main loop for the Risk Engine monitoring task."""
        cycle_count = 0
        error_count = 0
        last_error = None
        actions_count = 0

        while self._running:
            try:
                await self._evaluate_positions()
                cycle_count += 1

                # Report health metrics
                await self._report_health(
                    status="running",
                    metrics={
                        "cycle_count": cycle_count,
                        "actions_count": actions_count,
                        "error_count": error_count,
                        "last_error": last_error
                    }
                )

                await asyncio.sleep(self.polling_interval_seconds)
            except asyncio.CancelledError:
                await self._report_health(status="stopped", metrics={"cycle_count": cycle_count})
                break
            except Exception as e:
                error_count += 1
                last_error = str(e)
                logger.error(f"Error in Risk Engine monitoring loop: {e}")

                await self._report_health(
                    status="error",
                    metrics={
                        "cycle_count": cycle_count,
                        "actions_count": actions_count,
                        "error_count": error_count,
                        "last_error": last_error
                    }
                )

                await asyncio.sleep(self.polling_interval_seconds)

    async def _report_health(self, status: str, metrics: dict = None):
        """Report service health to cache."""
        try:
            from app.core.cache import get_cache
            cache = await get_cache()
            await cache.update_service_health("risk_engine", status, metrics)
        except Exception as e:
            logger.debug(f"Failed to report health: {e}")

    async def stop_monitoring_task(self):
        """Stops the background Risk Engine monitoring task."""
        if self._running and self._monitor_task:
            self._running = False
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("RiskEngineService monitoring task stopped.")

    async def set_risk_blocked(self, group_id: uuid.UUID, blocked: bool) -> PositionGroup:
        """Sets the risk_blocked flag for a specific PositionGroup."""
        async for session in self.session_factory():
            position_group_repo = self.position_group_repository_class(session)
            position_group = await position_group_repo.get(group_id)
            if not position_group:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PositionGroup not found")

            # Security Check
            if self.user and position_group.user_id != self.user.id:
                 raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this position group")

            position_group.risk_blocked = blocked
            await position_group_repo.update(position_group)
            await session.commit()
            await session.refresh(position_group)
            logger.info(f"PositionGroup {group_id} risk_blocked set to {blocked}")
            return position_group

    async def set_risk_skip_once(self, group_id: uuid.UUID, skip: bool) -> PositionGroup:
        """Sets the risk_skip_once flag for a specific PositionGroup."""
        async for session in self.session_factory():
            position_group_repo = self.position_group_repository_class(session)
            position_group = await position_group_repo.get(group_id)
            if not position_group:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PositionGroup not found")

            # Security Check
            if self.user and position_group.user_id != self.user.id:
                 raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this position group")

            position_group.risk_skip_once = skip
            await position_group_repo.update(position_group)
            await session.commit()
            await session.refresh(position_group)
            return position_group

    async def get_current_status(self) -> dict:
        """
        Returns the current state of the risk engine's evaluation without taking action.
        Identifies potential loser and winners based on current positions.

        SECURITY: Requires user context to prevent cross-user data access.
        """
        if not self.user:
            raise ValueError("User context required for get_current_status to ensure proper isolation")

        async for session in self.session_factory():
            position_group_repo = self.position_group_repository_class(session)
            risk_action_repo = self.risk_action_repository_class(session)

            all_positions = await position_group_repo.get_all_active_by_user(self.user.id)

            loser, winners, required_usd = select_loser_and_winners(all_positions, self.config)

            # Enhanced loser info with all spec fields
            loser_info = None
            if loser:
                # Calculate timer remaining
                timer_remaining = None
                timer_status = "inactive"
                if loser.risk_timer_expires:
                    now = datetime.utcnow()
                    if now >= loser.risk_timer_expires:
                        timer_status = "expired"
                        timer_remaining = 0
                    else:
                        timer_remaining = int((loser.risk_timer_expires - now).total_seconds() / 60)
                        timer_status = "active"

                # Check pyramid completion
                pyramids_complete = _check_pyramids_complete(loser, self.config.required_pyramids_for_timer)
                loss_exceeded = loser.unrealized_pnl_percent <= self.config.loss_threshold_percent

                loser_info = {
                    "id": str(loser.id),
                    "symbol": loser.symbol,
                    "unrealized_pnl_percent": float(loser.unrealized_pnl_percent),
                    "unrealized_pnl_usd": float(loser.unrealized_pnl_usd),
                    "risk_blocked": loser.risk_blocked,
                    "risk_skip_once": loser.risk_skip_once,
                    "risk_timer_expires": loser.risk_timer_expires.isoformat() if loser.risk_timer_expires else None,
                    "timer_remaining_minutes": timer_remaining,
                    "timer_status": timer_status,
                    "pyramids_complete": pyramids_complete,
                    "pyramid_count": loser.pyramid_count,
                    "required_pyramids": self.config.required_pyramids_for_timer,
                    "filled_dca_legs": loser.filled_dca_legs,
                    "total_dca_legs": loser.total_dca_legs,
                    "loss_threshold_exceeded": loss_exceeded,
                }

            # Enhanced winners info
            winners_info = []
            total_available_profit = 0
            for winner in winners:
                profit = float(winner.unrealized_pnl_usd)
                winners_info.append({
                    "id": str(winner.id),
                    "symbol": winner.symbol,
                    "unrealized_pnl_usd": profit,
                })
                total_available_profit += profit

            # Calculate projected offset plan
            projected_plan = []
            if loser and winners and required_usd > 0:
                remaining_needed = float(required_usd)
                for winner in winners:
                    if remaining_needed <= 0:
                        break
                    available = float(winner.unrealized_pnl_usd)
                    to_close = min(available, remaining_needed)
                    projected_plan.append({
                        "symbol": winner.symbol,
                        "profit_available": available,
                        "amount_to_close": to_close,
                        "partial": to_close < available
                    })
                    remaining_needed -= to_close

            # Get at-risk positions (eligible or close to eligible)
            eligible_losers = _filter_eligible_losers(all_positions, self.config)
            at_risk_positions = []
            for pos in all_positions:
                if pos.unrealized_pnl_percent < 0:
                    timer_status = "inactive"
                    timer_remaining = None
                    is_eligible = pos in eligible_losers

                    if pos.risk_timer_expires:
                        now = datetime.utcnow()
                        if now >= pos.risk_timer_expires:
                            timer_status = "expired"
                            timer_remaining = 0
                        else:
                            timer_remaining = int((pos.risk_timer_expires - now).total_seconds() / 60)
                            timer_status = "countdown"

                    pyramids_complete = _check_pyramids_complete(pos, self.config.required_pyramids_for_timer)
                    loss_exceeded = pos.unrealized_pnl_percent <= self.config.loss_threshold_percent

                    at_risk_positions.append({
                        "id": str(pos.id),
                        "symbol": pos.symbol,
                        "unrealized_pnl_percent": float(pos.unrealized_pnl_percent),
                        "unrealized_pnl_usd": float(pos.unrealized_pnl_usd),
                        "timer_status": timer_status,
                        "timer_remaining_minutes": timer_remaining,
                        "is_eligible": is_eligible,
                        "is_selected": loser and pos.id == loser.id,
                        "risk_blocked": pos.risk_blocked,
                        "pyramids_complete": pyramids_complete,
                        "pyramid_count": pos.pyramid_count,
                        "loss_exceeded": loss_exceeded,
                    })

            # Sort by loss percent (worst first)
            at_risk_positions.sort(key=lambda x: x["unrealized_pnl_percent"])

            # Get recent risk actions
            recent_actions = await risk_action_repo.get_recent_by_user(self.user.id, limit=10) if self.user else []
            recent_actions_info = []
            for action in recent_actions:
                recent_actions_info.append({
                    "id": str(action.id),
                    "timestamp": action.timestamp.isoformat() if action.timestamp else None,
                    "loser_symbol": action.loser_group.symbol if action.loser_group else "Unknown",
                    "loser_pnl_usd": float(action.loser_pnl_usd) if action.loser_pnl_usd else 0,
                    "winners_count": len(action.winner_details) if action.winner_details else 0,
                    "action_type": action.action_type.value if action.action_type else "unknown",
                })

            # Get daily realized PnL for loss limit status
            daily_realized_pnl = Decimal("0")
            if self.user:
                daily_realized_pnl = await position_group_repo.get_daily_realized_pnl(user_id=self.user.id)

            # Check actual risk engine running status from Redis health
            risk_engine_running = self._running  # Default to instance state
            try:
                from app.core.cache import get_cache
                cache = await get_cache()
                health_data = await cache.get_service_health("risk_engine")
                if health_data:
                    # Consider running if heartbeat within last 5 minutes
                    import time
                    last_heartbeat = health_data.get("last_heartbeat", 0)
                    if time.time() - last_heartbeat < 300:  # 5 minutes
                        risk_engine_running = health_data.get("status") == "running"
            except Exception:
                pass  # Fall back to instance state

            return {
                "identified_loser": loser_info,
                "identified_winners": winners_info,
                "required_offset_usd": float(required_usd),
                "total_available_profit": total_available_profit,
                "projected_plan": projected_plan,
                "at_risk_positions": at_risk_positions,
                "recent_actions": recent_actions_info,
                "risk_engine_running": risk_engine_running,
                "engine_paused_by_loss_limit": self.config.engine_paused_by_loss_limit,
                "engine_force_stopped": self.config.engine_force_stopped,
                "daily_realized_pnl": float(daily_realized_pnl),
                "max_realized_loss_usd": float(self.config.max_realized_loss_usd),
                "config": self.config.model_dump()
            }

    async def run_single_evaluation(self):
        """Triggers a single, immediate evaluation run of the risk engine."""
        if self.user:
            logger.info(f"Risk Engine: Manually triggered single evaluation for user {self.user.id}.")
            async for session in self.session_factory():
                await self._evaluate_user_positions(session, self.user)
        else:
            logger.info("Risk Engine: Manually triggered single evaluation (Global).")
            await self._evaluate_positions()
        return {"status": "Risk evaluation completed"}

    async def evaluate_on_fill_event(self, user: User, session: AsyncSession):
        """
        Triggered when a position fill occurs, if evaluate_on_fill is enabled.
        """
        if not self.config.evaluate_on_fill:
            return

        logger.info(f"Risk Engine: Fill-triggered evaluation for user {user.id}.")
        try:
            await self._evaluate_user_positions(session, user)
        except Exception as e:
            logger.error(f"Risk Engine: Fill-triggered evaluation failed for user {user.id}: {e}")

    async def force_stop_engine(self, user: User, session: AsyncSession, send_notification: bool = True) -> dict:
        """Force stop the queue from releasing trades."""
        # Update user's risk config
        risk_config_data = user.risk_config or {}
        if isinstance(risk_config_data, str):
            import json
            risk_config_data = json.loads(risk_config_data)

        risk_config_data['engine_force_stopped'] = True
        risk_config_data['engine_paused_by_loss_limit'] = False

        await session.execute(
            update(User).where(User.id == user.id).values(risk_config=risk_config_data)
        )
        await session.commit()

        # Update the user object's risk_config for this request context
        # SECURITY: Do NOT update self.config as it may be shared across users
        user.risk_config = risk_config_data

        logger.info(f"Engine force stopped by user {user.id}")

        position_group_repo = self.position_group_repository_class(session)
        all_positions = await position_group_repo.get_all_active_by_user(user.id)

        status_info = await self._get_engine_status_summary(user, session, all_positions)

        if send_notification:
            await self._send_engine_state_notification(
                user=user,
                action="FORCE_STOPPED",
                reason="Manually stopped by user",
                status_info=status_info
            )

        return {
            "status": "force_stopped",
            "message": "Engine force stopped. Queue will not release new trades. Risk engine continues running.",
            **status_info
        }

    async def force_start_engine(self, user: User, session: AsyncSession, send_notification: bool = True) -> dict:
        """Force start the queue after it was stopped."""
        risk_config_data = user.risk_config or {}
        if isinstance(risk_config_data, str):
            import json
            risk_config_data = json.loads(risk_config_data)

        was_paused_by_loss = risk_config_data.get('engine_paused_by_loss_limit', False)
        was_force_stopped = risk_config_data.get('engine_force_stopped', False)

        risk_config_data['engine_force_stopped'] = False
        risk_config_data['engine_paused_by_loss_limit'] = False

        await session.execute(
            update(User).where(User.id == user.id).values(risk_config=risk_config_data)
        )
        await session.commit()

        # Update the user object's risk_config for this request context
        # SECURITY: Do NOT update self.config as it may be shared across users
        user.risk_config = risk_config_data

        logger.info(f"Engine force started by user {user.id}")

        position_group_repo = self.position_group_repository_class(session)
        all_positions = await position_group_repo.get_all_active_by_user(user.id)

        status_info = await self._get_engine_status_summary(user, session, all_positions)

        if was_paused_by_loss:
            reason = "Resumed after max realized loss was reached"
        elif was_force_stopped:
            reason = "Resumed after manual force stop"
        else:
            reason = "Engine started"

        if send_notification:
            await self._send_engine_state_notification(
                user=user,
                action="FORCE_STARTED",
                reason=reason,
                status_info=status_info
            )

        return {
            "status": "running",
            "message": "Engine started. Queue will now release trades normally.",
            **status_info
        }

    async def pause_engine_for_loss_limit(self, user: User, session: AsyncSession, realized_loss: Decimal) -> dict:
        """Automatically pause the queue when max realized loss is reached."""
        risk_config_data = user.risk_config or {}
        if isinstance(risk_config_data, str):
            import json
            risk_config_data = json.loads(risk_config_data)

        risk_config_data['engine_paused_by_loss_limit'] = True

        await session.execute(
            update(User).where(User.id == user.id).values(risk_config=risk_config_data)
        )
        await session.commit()

        # Update the user object's risk_config for this request context
        # SECURITY: Do NOT update self.config as it may be shared across users
        user.risk_config = risk_config_data

        logger.warning(f"Engine auto-paused for user {user.id} due to max realized loss ({realized_loss} USD)")

        position_group_repo = self.position_group_repository_class(session)
        all_positions = await position_group_repo.get_all_active_by_user(user.id)

        status_info = await self._get_engine_status_summary(user, session, all_positions)

        await self._send_engine_state_notification(
            user=user,
            action="AUTO_PAUSED",
            reason=f"Max realized loss limit reached ({realized_loss} USD / {self.config.max_realized_loss_usd} USD)",
            status_info=status_info
        )

        return {
            "status": "paused_by_loss_limit",
            "message": f"Engine paused due to max realized loss ({realized_loss} USD)",
            **status_info
        }

    async def _get_engine_status_summary(self, user: User, session: AsyncSession, positions: List[PositionGroup]) -> dict:
        """Get a summary of the engine status for notifications."""
        from app.repositories.queued_signal import QueuedSignalRepository

        active_count = sum(1 for p in positions if p.status == PositionGroupStatus.ACTIVE.value)
        total_unrealized_pnl = sum(float(p.unrealized_pnl_usd) for p in positions)

        queue_repo = QueuedSignalRepository(session)
        queued_signals = await queue_repo.get_all_queued_signals_for_user(user.id)
        queue_count = len(queued_signals)

        position_group_repo = self.position_group_repository_class(session)
        daily_realized_pnl = await position_group_repo.get_daily_realized_pnl(user_id=user.id)

        return {
            "open_positions": active_count,
            "total_unrealized_pnl": total_unrealized_pnl,
            "queued_signals": queue_count,
            "daily_realized_pnl": float(daily_realized_pnl),
            "risk_engine_running": self._running,
        }

    async def _send_engine_state_notification(
        self,
        user: User,
        action: str,
        reason: str,
        status_info: dict
    ) -> None:
        """Send Telegram notification about engine state change."""
        from app.schemas.telegram_config import TelegramConfig
        from app.services.telegram_broadcaster import TelegramBroadcaster

        if not user.telegram_config:
            logger.debug(f"No Telegram config for user {user.id}, skipping notification")
            return

        try:
            telegram_config = TelegramConfig(**user.telegram_config)
            if not telegram_config.enabled:
                return

            broadcaster = TelegramBroadcaster(telegram_config)

            emoji_map = {
                "FORCE_STOPPED": "🛑",
                "FORCE_STARTED": "▶️",
                "AUTO_PAUSED": "⚠️"
            }
            emoji = emoji_map.get(action, "ℹ️")

            message = f"{emoji} Engine Status: {action}\n\n"
            message += f"📋 Reason: {reason}\n\n"
            message += "📊 Current Status:\n"
            message += f"  • Open Positions: {status_info['open_positions']}\n"
            message += f"  • Unrealized PnL: ${status_info['total_unrealized_pnl']:.2f}\n"
            message += f"  • Queued Signals: {status_info['queued_signals']}\n"
            message += f"  • Daily Realized PnL: ${status_info['daily_realized_pnl']:.2f}\n"
            message += f"  • Risk Engine: {'Running' if status_info['risk_engine_running'] else 'Stopped'}\n"

            if action == "AUTO_PAUSED":
                message += f"\n⚡ Use Force Start to resume trading."

            await broadcaster._send_message(message)
            logger.info(f"Sent engine state notification to user {user.id}: {action}")

        except Exception as e:
            logger.error(f"Failed to send engine state notification: {e}")

    async def sync_with_exchange(self, user: User, session: AsyncSession) -> dict:
        """Synchronize local position data with exchange data."""
        position_group_repo = self.position_group_repository_class(session)
        all_positions = await position_group_repo.get_all_active_by_user(user.id)

        if not all_positions:
            return {"status": "success", "message": "No active positions to sync", "corrections": []}

        corrections = []
        exchanges_synced = set()

        for pg in all_positions:
            exchange_name = pg.exchange.lower()

            try:
                exchange_config = {}
                encrypted_data = user.encrypted_api_keys

                if isinstance(encrypted_data, dict) and exchange_name in encrypted_data:
                    exchange_config = encrypted_data[exchange_name]
                else:
                    continue

                exchange_connector = get_exchange_connector(
                    exchange_type=exchange_name,
                    exchange_config=exchange_config
                )

                try:
                    exchange_positions = await exchange_connector.get_positions()
                    exchange_pos = next(
                        (p for p in exchange_positions if p.get('symbol') == pg.symbol),
                        None
                    )

                    if exchange_pos:
                        old_pnl = pg.unrealized_pnl_usd
                        current_price = Decimal(str(exchange_pos.get('markPrice', 0)))

                        if pg.side == "long":
                            new_pnl = (current_price - pg.weighted_avg_entry) * pg.total_filled_quantity
                            new_pnl_percent = ((current_price - pg.weighted_avg_entry) / pg.weighted_avg_entry * 100)
                        else:
                            new_pnl = (pg.weighted_avg_entry - current_price) * pg.total_filled_quantity
                            new_pnl_percent = ((pg.weighted_avg_entry - current_price) / pg.weighted_avg_entry * 100)

                        if abs(new_pnl - old_pnl) > Decimal("0.01"):
                            pg.unrealized_pnl_usd = new_pnl
                            pg.unrealized_pnl_percent = new_pnl_percent
                            corrections.append({
                                "symbol": pg.symbol,
                                "field": "unrealized_pnl",
                                "old_value": float(old_pnl),
                                "new_value": float(new_pnl)
                            })
                    else:
                        corrections.append({
                            "symbol": pg.symbol,
                            "field": "status",
                            "warning": "Position not found on exchange"
                        })

                except Exception as e:
                    logger.warning(f"Failed to fetch position for {pg.symbol}: {e}")

                exchanges_synced.add(exchange_name)
                await exchange_connector.close()

            except Exception as e:
                logger.error(f"Error syncing position {pg.symbol}: {e}")

        await session.commit()

        return {
            "status": "success",
            "message": f"Synced {len(all_positions)} positions across {len(exchanges_synced)} exchanges",
            "corrections": corrections,
            "exchanges_synced": list(exchanges_synced)
        }
