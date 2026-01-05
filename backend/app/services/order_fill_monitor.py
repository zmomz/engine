"""
FIXED Service for monitoring order fills and updating their status in the database.
Key fix: Properly handles the Bybit testnet workaround by continuing with position updates
even when check_order_status triggers the workaround.

Performance optimizations:
- Parallel processing of orders using asyncio.gather with semaphore
- Batch price fetching using get_all_tickers instead of per-order price calls
- Eager loading of pyramid relationships to avoid N+1 queries
"""
import asyncio
import logging
from typing import List, Dict, Any
import json
import ccxt
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.user import UserRepository
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.repositories.dca_configuration import DCAConfigurationRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.order_management import OrderService
from app.services.position_manager import PositionManagerService
from app.services.risk_engine import RiskEngineService
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.core.security import EncryptionService
from app.services.telegram_signal_helper import broadcast_dca_fill, broadcast_tp_hit

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent order processing (prevent overwhelming exchange APIs)
MAX_CONCURRENT_ORDERS = 10

class OrderFillMonitorService:
    def __init__(
        self,
        session_factory: callable,
        dca_order_repository_class: type[DCAOrderRepository],
        position_group_repository_class: type[PositionGroupRepository],
        order_service_class: type[OrderService],
        position_manager_service_class: type[PositionManagerService],
        risk_engine_config: RiskEngineConfig = None,
        polling_interval_seconds: int = 2
    ):
        self.session_factory = session_factory
        self.dca_order_repository_class = dca_order_repository_class
        self.position_group_repository_class = position_group_repository_class
        self.order_service_class = order_service_class
        self.position_manager_service_class = position_manager_service_class
        self.risk_engine_config = risk_engine_config or RiskEngineConfig()
        self.polling_interval_seconds = polling_interval_seconds
        self._running = False
        self._monitor_task = None
        try:
            self.encryption_service = EncryptionService()
        except Exception as e:
            logger.error(f"OrderFillMonitor failed to init encryption service: {e}")
            self.encryption_service = None

    async def _trigger_risk_evaluation_on_fill(self, user, session: AsyncSession):
        """
        Triggers risk engine evaluation if evaluate_on_fill is enabled.
        Called after a position fill is detected.
        """
        if not self.risk_engine_config.evaluate_on_fill:
            return

        try:
            from app.repositories.risk_action import RiskActionRepository

            risk_engine = RiskEngineService(
                session_factory=self.session_factory,
                position_group_repository_class=self.position_group_repository_class,
                risk_action_repository_class=RiskActionRepository,
                dca_order_repository_class=self.dca_order_repository_class,
                order_service_class=self.order_service_class,
                risk_engine_config=self.risk_engine_config,
                user=user
            )
            await risk_engine.evaluate_on_fill_event(user, session)
        except Exception as e:
            logger.error(f"OrderFillMonitor: Failed to trigger risk evaluation on fill for user {user.id}: {e}")

    async def _check_dca_beyond_threshold(
        self,
        order: DCAOrder,
        current_price: Decimal,
        order_service,
        session: AsyncSession
    ):
        """
        Check if a pending DCA order should be cancelled because price has moved
        beyond the configured threshold from the position's entry price.

        Args:
            order: The DCA order to check
            current_price: Current market price
            order_service: OrderService instance for cancellation
            session: Database session
        """
        if not order.group:
            return

        # Load DCA config for this position group to check threshold
        try:
            dca_config_repo = DCAConfigurationRepository(session)

            # Normalize pair format
            symbol = order.group.symbol
            normalized_pair = symbol
            if '/' not in normalized_pair:
                if normalized_pair.endswith('USDT'):
                    normalized_pair = normalized_pair[:-4] + '/' + normalized_pair[-4:]
                elif normalized_pair.endswith(('USD', 'BTC', 'ETH', 'BNB')):
                    normalized_pair = normalized_pair[:-3] + '/' + normalized_pair[-3:]

            specific_config = await dca_config_repo.get_specific_config(
                user_id=order.group.user_id,
                pair=normalized_pair,
                timeframe=order.group.timeframe,
                exchange=order.group.exchange.lower()
            )

            if not specific_config:
                return

            # Check if cancel_dca_beyond_percent is configured
            # It may be stored in the config or not exist at all
            cancel_threshold = None
            if hasattr(specific_config, 'cancel_dca_beyond_percent'):
                cancel_threshold = specific_config.cancel_dca_beyond_percent
            elif isinstance(specific_config, dict) and 'cancel_dca_beyond_percent' in specific_config:
                cancel_threshold = specific_config.get('cancel_dca_beyond_percent')

            if cancel_threshold is None:
                return

            cancel_threshold = Decimal(str(cancel_threshold))

            # Calculate how far price has moved from the position's weighted average entry
            entry_price = order.group.weighted_avg_entry
            if not entry_price or entry_price == 0:
                return

            # Calculate percent move
            if order.group.side == "long":
                # For long positions, we're concerned about price dropping too far
                price_change_percent = ((current_price - entry_price) / entry_price) * Decimal("100")
                # If price dropped beyond threshold (negative change exceeds negative threshold)
                beyond_threshold = price_change_percent < -cancel_threshold
            else:
                # For short positions, we're concerned about price rising too far
                price_change_percent = ((entry_price - current_price) / entry_price) * Decimal("100")
                # If price rose beyond threshold (negative change exceeds negative threshold)
                beyond_threshold = price_change_percent < -cancel_threshold

            if beyond_threshold and order.status in [OrderStatus.OPEN.value, OrderStatus.TRIGGER_PENDING.value]:
                logger.info(
                    f"DCA order {order.id} for {order.symbol} cancelled: price moved {price_change_percent:.2f}% "
                    f"beyond threshold of {cancel_threshold}%"
                )
                await order_service.cancel_order(order)

        except Exception as e:
            logger.warning(f"Failed to check DCA beyond threshold for order {order.id}: {e}")

    async def _process_single_order(
        self,
        order: DCAOrder,
        order_service: OrderService,
        position_manager: PositionManagerService,
        connector: ExchangeInterface,
        session: AsyncSession,
        user,
        prices_cache: Dict[str, Decimal],
        semaphore: asyncio.Semaphore
    ) -> None:
        """
        Process a single order. Called in parallel with other orders.
        Uses semaphore to limit concurrency.
        Handles deadlock errors gracefully by skipping the order for this cycle.
        """
        async with semaphore:
            try:
                # Refresh order to get latest state - skip if it's been modified elsewhere
                try:
                    await session.refresh(order)
                except Exception as refresh_err:
                    logger.debug(f"Could not refresh order {order.id}: {refresh_err} - skipping")
                    return

                # Get price from cache (batch fetched earlier)
                current_price = prices_cache.get(order.symbol)

                # Check if position group is closed or closing - skip and let exit handler manage
                if order.group and order.group.status in ['closed', 'closing']:
                    logger.debug(f"Order {order.id} belongs to {order.group.status} position - skipping")
                    return

                # If already filled, we are here to check/place TP orders
                if order.status == OrderStatus.FILLED.value:
                    # Skip tp_fill records (leg_index=999) - they are exit trades, not entries that need TPs
                    if order.leg_index == 999:
                        logger.debug(f"Order {order.id} is a TP fill record (leg_index=999) - skipping")
                        return

                    # First check if TP order needs to be placed (missing tp_order_id)
                    if not order.tp_order_id and order.group and order.group.tp_mode in ["per_leg", "hybrid"]:
                        logger.info(f"Order {order.id} is FILLED but has no TP order - placing TP now")
                        try:
                            await order_service.place_tp_order(order)
                            await session.flush()
                            logger.info(f"✓ Successfully placed missing TP order for {order.id}")
                        except Exception as tp_err:
                            logger.error(f"Failed to place missing TP order for {order.id}: {tp_err}")
                        return

                    # Check status of existing TP order
                    # Store IDs (not objects) - IDs are simple values that can't be expired by concurrent operations
                    order_group = order.group
                    order_pyramid_id = order.pyramid_id  # Store the ID, not the object
                    updated_order = await order_service.check_tp_status(order)
                    # Restore group relationship
                    updated_order.group = order_group

                    if updated_order.tp_hit:
                        logger.info(f"TP hit for order {order.id}. Updating position stats.")
                        await session.flush()
                        await position_manager.update_position_stats(updated_order.group_id, session=session)

                        # Broadcast per-leg TP hit notification
                        # Re-fetch pyramid since concurrent update_position_stats may have cleared it
                        pyramid = None
                        if order_pyramid_id:
                            from sqlalchemy import select
                            from app.models.pyramid import Pyramid
                            result = await session.execute(select(Pyramid).where(Pyramid.id == order_pyramid_id))
                            pyramid = result.scalar_one_or_none()

                        if updated_order.group and pyramid:
                            entry_price = updated_order.price
                            exit_price = updated_order.tp_price
                            if entry_price and exit_price:
                                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
                                pnl_usd = (exit_price - entry_price) * updated_order.filled_quantity
                                logger.info(f"Broadcasting per-leg TP hit for order {updated_order.id}")
                                await broadcast_tp_hit(
                                    position_group=updated_order.group,
                                    pyramid=pyramid,
                                    tp_type="per_leg",
                                    tp_price=exit_price,
                                    pnl_percent=pnl_percent,
                                    session=session,
                                    pnl_usd=pnl_usd,
                                    closed_quantity=updated_order.filled_quantity,
                                    leg_index=updated_order.leg_index
                                )
                        else:
                            logger.warning(f"Cannot broadcast TP hit for order {updated_order.id}: group={updated_order.group is not None}, pyramid={pyramid is not None}, pyramid_id={order_pyramid_id}")

                        await self._trigger_risk_evaluation_on_fill(user, session)
                    return

                # --- TRIGGER LOGIC ---
                if order.status == OrderStatus.TRIGGER_PENDING.value:
                    if current_price is None:
                        current_price = Decimal(str(await connector.get_current_price(order.symbol)))

                    should_trigger = False

                    await self._check_dca_beyond_threshold(order, current_price, order_service, session)
                    await session.refresh(order)
                    if order.status == OrderStatus.CANCELLED.value:
                        return

                    logger.debug(f"Checking Trigger for Order {order.id} ({order.side}): Target {order.price}, Current {current_price}")

                    # Market entry orders trigger based on their gap_percent:
                    # - gap_percent = 0 (at market): trigger immediately
                    # - gap_percent < 0 (below market): wait for price to drop to target
                    if order.order_type == "market" and order.leg_index == 0 and order.gap_percent == 0:
                        should_trigger = True
                        logger.info(f"Market entry order {order.id} (gap=0%) - triggering immediately at current price {current_price}")
                    elif order.side == "buy":
                        if current_price <= order.price:
                            should_trigger = True
                    else:
                        if current_price >= order.price:
                            should_trigger = True

                    if should_trigger:
                        logger.info(f"Trigger condition met for Order {order.id}. Submitting Market Order.")
                        await order_service.submit_order(order)
                        await session.refresh(order)
                        logger.info(f"Triggered Order {order.id} status is now {order.status}")

                        if order.status == OrderStatus.FILLED.value:
                            await position_manager.update_position_stats(order.group_id, session=session)
                            # Only place per-leg TP orders if tp_mode supports it
                            if order.group and order.group.tp_mode in ["per_leg", "hybrid"]:
                                await order_service.place_tp_order(order)

                            # Use eager-loaded pyramid
                            if order.group and order.pyramid:
                                await broadcast_dca_fill(
                                    position_group=order.group,
                                    order=order,
                                    pyramid=order.pyramid,
                                    session=session
                                )

                            await self._trigger_risk_evaluation_on_fill(user, session)
                    return

                # Check if OPEN DCA order should be cancelled due to price beyond threshold
                if order.status == OrderStatus.OPEN.value:
                    try:
                        if current_price is None:
                            current_price = Decimal(str(await connector.get_current_price(order.symbol)))
                        await self._check_dca_beyond_threshold(order, current_price, order_service, session)
                        await session.refresh(order)
                        if order.status == OrderStatus.CANCELLED.value:
                            return
                    except Exception as price_err:
                        logger.debug(f"Could not fetch price for DCA threshold check: {price_err}")

                # Check order status on exchange
                logger.info(f"Checking order {order.id} status on exchange...")
                # Preserve eager-loaded relationships before refresh (refresh clears them)
                order_group = order.group
                order_pyramid = order.pyramid
                updated_order = await order_service.check_order_status(order)
                await session.refresh(updated_order)
                # Restore relationships after refresh
                updated_order.group = order_group
                updated_order.pyramid = order_pyramid

                logger.info(f"Order {order.id} status after check: {updated_order.status}")

                if updated_order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED]:
                    logger.info(f"Order {order.id} status updated to {updated_order.status}")

                # Handle filled orders
                if updated_order.status == OrderStatus.FILLED.value:
                    await session.flush()

                    logger.info(f"Order {order.id} FILLED - updating position stats")
                    await position_manager.update_position_stats(updated_order.group_id, session=session)
                    # Only place per-leg TP orders if tp_mode supports it
                    if updated_order.group and updated_order.group.tp_mode in ["per_leg", "hybrid"]:
                        await order_service.place_tp_order(updated_order)
                        logger.info(f"✓ Successfully placed TP order for {updated_order.id}")

                    # Broadcast DCA fill notification
                    if updated_order.group and updated_order.pyramid:
                        logger.info(f"Broadcasting DCA fill for order {updated_order.id}")
                        await broadcast_dca_fill(
                            position_group=updated_order.group,
                            order=updated_order,
                            pyramid=updated_order.pyramid,
                            session=session
                        )
                    else:
                        logger.warning(f"Cannot broadcast DCA fill for order {updated_order.id}: group={updated_order.group is not None}, pyramid={updated_order.pyramid is not None}")

                    await self._trigger_risk_evaluation_on_fill(user, session)

                # Handle partially filled orders
                elif updated_order.status == OrderStatus.PARTIALLY_FILLED.value:
                    await session.flush()

                    if updated_order.filled_quantity and updated_order.filled_quantity > 0 and not updated_order.tp_order_id:
                        logger.info(
                            f"Order {order.id} PARTIALLY_FILLED ({updated_order.filled_quantity}/{updated_order.quantity}) "
                            f"- updating position stats"
                        )
                        await position_manager.update_position_stats(updated_order.group_id, session=session)
                        # Only place per-leg TP orders if tp_mode supports it
                        if updated_order.group and updated_order.group.tp_mode in ["per_leg", "hybrid"]:
                            await order_service.place_tp_order_for_partial_fill(updated_order)
                            logger.info(f"✓ Successfully placed partial TP order for {updated_order.id}")

                        # Broadcast DCA fill notification
                        if updated_order.group and updated_order.pyramid:
                            logger.info(f"Broadcasting DCA fill for partial order {updated_order.id}")
                            await broadcast_dca_fill(
                                position_group=updated_order.group,
                                order=updated_order,
                                pyramid=updated_order.pyramid,
                                session=session
                            )
                        else:
                            logger.warning(f"Cannot broadcast DCA fill for partial order {updated_order.id}: group={updated_order.group is not None}, pyramid={updated_order.pyramid is not None}")

                        await self._trigger_risk_evaluation_on_fill(user, session)

            except Exception as e:
                error_msg = str(e).lower()
                # Handle deadlock gracefully - skip this order for now, it will be retried next cycle
                if "deadlock" in error_msg or "pending" in error_msg and "rollback" in error_msg:
                    logger.warning(f"Deadlock detected processing order {order.id} - will retry next cycle")
                else:
                    logger.error(f"Error processing order {order.id}: {e}")
                    import traceback
                    traceback.print_exc()

    async def _fetch_all_prices(
        self,
        connector: ExchangeInterface,
        symbols: List[str]
    ) -> Dict[str, Decimal]:
        """
        Batch fetch all prices for given symbols using get_all_tickers.
        Returns a dict mapping symbol to current price.
        """
        prices = {}
        try:
            all_tickers = await connector.get_all_tickers()
            for symbol in symbols:
                if symbol in all_tickers:
                    prices[symbol] = Decimal(str(all_tickers[symbol].get('last', 0)))
                elif symbol.replace('/', '') in all_tickers:
                    prices[symbol] = Decimal(str(all_tickers[symbol.replace('/', '')].get('last', 0)))
        except Exception as e:
            logger.warning(f"Could not batch fetch tickers: {e}")
        return prices

    async def _check_orders(self):
        """
        Fetches open orders from the DB and checks their status on the exchange.
        Uses batch query to avoid N+1 query issues.

        Performance optimizations:
        - Batch fetches all prices upfront using get_all_tickers
        - Processes orders in parallel using asyncio.gather with semaphore
        - Uses eager-loaded pyramid relationships
        """
        if not self.encryption_service:
            logger.error("EncryptionService not available. Skipping order checks.")
            return

        async with self.session_factory() as session:
            try:
                user_repo = UserRepository(session)
                active_users = await user_repo.get_all_active_users()
                logger.debug(f"OrderFillMonitor: Found {len(active_users)} active users.")

                users_with_keys = [u for u in active_users if u.encrypted_api_keys]
                if not users_with_keys:
                    logger.debug("OrderFillMonitor: No users with API keys, skipping.")
                    return

                # Batch fetch all orders for all users in a single query (prevents N+1)
                dca_order_repo = self.dca_order_repository_class(session)
                user_ids = [str(u.id) for u in users_with_keys]
                orders_by_user = await dca_order_repo.get_all_open_orders_for_all_users(user_ids)
                logger.debug(f"OrderFillMonitor: Batch loaded orders for {len(orders_by_user)} users.")

                # Create semaphore for limiting concurrent order processing
                semaphore = asyncio.Semaphore(MAX_CONCURRENT_ORDERS)

                for user in users_with_keys:
                    try:
                        all_orders = orders_by_user.get(str(user.id), [])
                        logger.info(f"OrderFillMonitor: User {user.id} - Found {len(all_orders)} open/partially filled orders.")

                        if not all_orders:
                            # Even with no open orders, check TP for idle positions
                            logger.info(f"OrderFillMonitor: No open orders for user {user.id}, checking idle position TPs...")
                            await self._check_aggregate_tp_for_idle_positions(session, user)
                            await self._check_pyramid_aggregate_tp_for_idle_positions(session, user)
                            await self._check_per_leg_positions_all_tps_hit(session, user)
                            try:
                                await session.commit()
                                logger.debug(f"OrderFillMonitor: Committed changes for user {user.id} (idle check only)")
                            except Exception as commit_err:
                                error_msg = str(commit_err).lower()
                                if "deadlock" in error_msg or "rollback" in error_msg:
                                    await session.rollback()
                            continue

                        # Group orders by exchange
                        orders_by_exchange: Dict[str, List[DCAOrder]] = {}
                        for order in all_orders:
                            if not order.group:
                                logger.error(f"Order {order.id} has no position group attached. Skipping.")
                                continue
                            ex = order.group.exchange
                            if ex not in orders_by_exchange:
                                orders_by_exchange[ex] = []
                            orders_by_exchange[ex].append(order)

                        logger.info(f"OrderFillMonitor: Exchanges found: {list(orders_by_exchange.keys())}")

                        # Process each exchange
                        for raw_exchange_name, orders_to_check in orders_by_exchange.items():
                            exchange_name = raw_exchange_name.lower()
                            logger.info(f"OrderFillMonitor: Processing {len(orders_to_check)} orders for exchange '{exchange_name}'")

                            try:
                                # Setup connector
                                if exchange_name == "mock":
                                    exchange_keys_data = {
                                        "api_key": "mock_api_key_12345",
                                        "api_secret": "mock_api_secret_67890"
                                    }
                                else:
                                    exchange_keys_data = user.encrypted_api_keys.get(exchange_name)
                                    if not exchange_keys_data:
                                        logger.warning(f"No API keys for {exchange_name} for user {user.id}, skipping.")
                                        continue
                                    api_key, secret_key = self.encryption_service.decrypt_keys(exchange_keys_data)

                                connector = get_exchange_connector(exchange_name, exchange_config=exchange_keys_data)
                            except Exception as e:
                                logger.error(f"Failed to setup connector for {exchange_name}: {e}")
                                continue

                            try:
                                # Create services ONCE per exchange
                                order_service = self.order_service_class(
                                    session=session,
                                    user=user,
                                    exchange_connector=connector
                                )

                                position_manager = self.position_manager_service_class(
                                    session_factory=self.session_factory,
                                    user=user,
                                    position_group_repository_class=self.position_group_repository_class,
                                    grid_calculator_service=None,
                                    order_service_class=None
                                )

                                # Batch fetch all prices for all symbols in this exchange
                                symbols = list(set(order.symbol for order in orders_to_check))
                                prices_cache = await self._fetch_all_prices(connector, symbols)
                                logger.debug(f"Batch fetched prices for {len(prices_cache)} symbols")

                                # Process all orders in parallel with semaphore
                                tasks = [
                                    self._process_single_order(
                                        order=order,
                                        order_service=order_service,
                                        position_manager=position_manager,
                                        connector=connector,
                                        session=session,
                                        user=user,
                                        prices_cache=prices_cache,
                                        semaphore=semaphore
                                    )
                                    for order in orders_to_check
                                ]

                                # Execute all order processing in parallel
                                await asyncio.gather(*tasks, return_exceptions=True)

                            finally:
                                await connector.close()

                        # Check TP for positions without open orders
                        await self._check_aggregate_tp_for_idle_positions(session, user)
                        await self._check_pyramid_aggregate_tp_for_idle_positions(session, user)
                        await self._check_per_leg_positions_all_tps_hit(session, user)

                        # Try to commit, but handle deadlock/rollback errors gracefully
                        try:
                            await session.commit()
                            logger.debug(f"OrderFillMonitor: Committed changes for user {user.id}")
                        except Exception as commit_err:
                            error_msg = str(commit_err).lower()
                            if "deadlock" in error_msg or "rollback" in error_msg:
                                logger.warning(f"Deadlock during commit for user {user.id} - rolling back and retrying next cycle")
                                await session.rollback()
                            else:
                                raise

                    except Exception as e:
                        error_msg = str(e).lower()
                        if "deadlock" in error_msg or "rollback" in error_msg:
                            logger.warning(f"Deadlock detected for user {user.username} - will retry next cycle")
                        else:
                            logger.error(f"Error checking orders for user {user.username}: {e}")
                            import traceback
                            traceback.print_exc()
                        await session.rollback()

            except Exception as e:
                error_msg = str(e).lower()
                if "deadlock" in error_msg or "rollback" in error_msg:
                    logger.warning(f"Deadlock in OrderFillMonitor check loop - will retry next cycle")
                else:
                    logger.error(f"Error in OrderFillMonitor check loop: {e}")
                    import traceback
                    traceback.print_exc()
                await session.rollback()

    async def start_monitoring_task(self):
        """
        Starts the background task for Order Fill Monitoring.
        """
        if not self._running:
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitoring_loop())
            logger.info("OrderFillMonitorService monitoring task started.")

    async def _monitoring_loop(self):
        """
        The main loop for the Order Fill Monitoring task.
        """
        cycle_count = 0
        error_count = 0
        last_error = None

        while self._running:
            try:
                await self._check_orders()
                cycle_count += 1

                # Report health metrics
                await self._report_health(
                    status="running",
                    metrics={
                        "cycle_count": cycle_count,
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
                logger.error(f"Error in OrderFillMonitor monitoring loop: {e}")
                import traceback
                traceback.print_exc()

                await self._report_health(
                    status="error",
                    metrics={
                        "cycle_count": cycle_count,
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
            await cache.update_service_health("order_fill_monitor", status, metrics)
        except Exception as e:
            logger.debug(f"Failed to report health: {e}")

    async def stop_monitoring_task(self):
        """
        Stops the background Order Fill Monitoring task.
        """
        if self._running and self._monitor_task:
            self._running = False
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("OrderFillMonitorService monitoring task stopped.")

    async def _check_aggregate_tp_for_idle_positions(self, session: AsyncSession, user):
        """
        Check aggregate TP for positions that have no open orders.
        This ensures positions can close via aggregate TP even when no orders are pending.
        """
        try:
            position_group_repo = self.position_group_repository_class(session)

            # Get all active/partially_filled positions for this user with aggregate/hybrid TP mode
            result = await session.execute(
                select(PositionGroup)
                .where(
                    PositionGroup.user_id == user.id,
                    PositionGroup.status.in_([PositionGroupStatus.ACTIVE.value, PositionGroupStatus.PARTIALLY_FILLED.value]),
                    PositionGroup.tp_mode.in_(["aggregate", "hybrid"]),
                    PositionGroup.tp_aggregate_percent > 0,
                    PositionGroup.total_filled_quantity > 0
                )
                .options(selectinload(PositionGroup.dca_orders))
            )
            positions = result.scalars().all()

            if not positions:
                logger.info(f"OrderFillMonitor: No aggregate/hybrid positions found for user {user.id}")
                return

            logger.info(f"OrderFillMonitor: Checking aggregate TP for {len(positions)} positions")

            # Helper to check if order is open (handles both enum and string status)
            def is_open_order(status):
                status_str = str(status).lower()
                return any(s in status_str for s in ['open', 'trigger_pending', 'partially_filled'])

            # Group by exchange
            positions_by_exchange: Dict[str, List[PositionGroup]] = {}
            for pos in positions:
                # For hybrid mode, we still check aggregate TP even with open orders
                # For pure aggregate mode, skip if there are open orders (will be handled when all orders fill)
                if pos.tp_mode == "aggregate":
                    open_orders = [o for o in pos.dca_orders if is_open_order(o.status)]
                    if open_orders:
                        logger.info(f"OrderFillMonitor: Skipping aggregate TP for {pos.symbol} - has {len(open_orders)} open orders")
                        continue  # Skip aggregate mode - will be handled by order processing

                ex = pos.exchange.lower()
                if ex not in positions_by_exchange:
                    positions_by_exchange[ex] = []
                positions_by_exchange[ex].append(pos)

            for exchange_name, positions_to_check in positions_by_exchange.items():
                if not positions_to_check:
                    continue

                try:
                    # Setup connector
                    if exchange_name == "mock":
                        exchange_keys_data = {
                            "api_key": "mock_api_key_12345",
                            "api_secret": "mock_api_secret_67890"
                        }
                    else:
                        exchange_keys_data = user.encrypted_api_keys.get(exchange_name)
                        if not exchange_keys_data:
                            continue

                    connector = get_exchange_connector(exchange_name, exchange_config=exchange_keys_data)

                    try:
                        for pos in positions_to_check:
                            await self._check_single_position_aggregate_tp(
                                session, user, pos, connector, position_group_repo
                            )
                    finally:
                        await connector.close()

                except Exception as e:
                    logger.error(f"OrderFillMonitor: Error checking aggregate TP for {exchange_name}: {e}")

        except Exception as e:
            logger.error(f"OrderFillMonitor: Error in _check_aggregate_tp_for_idle_positions: {e}")

    async def _check_single_position_aggregate_tp(
        self,
        session: AsyncSession,
        user,
        position_group: PositionGroup,
        connector,
        position_group_repo
    ):
        """Check aggregate TP for a single position and execute if triggered."""
        try:
            current_price = Decimal(str(await connector.get_current_price(position_group.symbol)))
            current_avg_price = position_group.weighted_avg_entry
            current_qty = position_group.total_filled_quantity

            if current_qty <= 0 or current_avg_price <= 0:
                logger.info(f"OrderFillMonitor: Aggregate TP skip for {position_group.symbol} - qty={current_qty}, avg_price={current_avg_price}")
                return

            # Calculate aggregate TP target
            if position_group.side.lower() == "long":
                aggregate_tp_price = current_avg_price * (Decimal("1") + position_group.tp_aggregate_percent / Decimal("100"))
                should_execute_tp = current_price >= aggregate_tp_price
            else:
                aggregate_tp_price = current_avg_price * (Decimal("1") - position_group.tp_aggregate_percent / Decimal("100"))
                should_execute_tp = current_price <= aggregate_tp_price

            logger.info(
                f"OrderFillMonitor: Aggregate TP Check for {position_group.symbol} (ID: {str(position_group.id)[:8]}) - "
                f"avg_entry={current_avg_price:.4f}, tp_percent={position_group.tp_aggregate_percent}%, "
                f"tp_target={aggregate_tp_price:.4f}, current_price={current_price}, triggered={should_execute_tp}"
            )

            if not should_execute_tp:
                return

            logger.info(
                f"OrderFillMonitor: Aggregate TP Triggered for idle position {position_group.symbol} "
                f"(ID: {position_group.id}) at {current_price} (Target: {aggregate_tp_price})"
            )

            # Create order service and execute TP
            order_service = self.order_service_class(
                session=session,
                user=user,
                exchange_connector=connector
            )

            # Calculate PnL
            if position_group.side.lower() == "long":
                unrealized_pnl = (current_price - current_avg_price) * current_qty
            else:
                unrealized_pnl = (current_avg_price - current_price) * current_qty

            pnl_percent = position_group.tp_aggregate_percent

            # Broadcast TP hit
            await broadcast_tp_hit(
                position_group=position_group,
                pyramid=None,
                tp_type="aggregate",
                tp_price=aggregate_tp_price,
                pnl_percent=pnl_percent,
                session=session,
                pnl_usd=unrealized_pnl,
                closed_quantity=current_qty,
                remaining_pyramids=0
            )

            # Cancel any remaining open orders
            await order_service.cancel_open_orders_for_group(position_group.id)

            # Place market close order (don't record in DB - just execute on exchange)
            close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
            await order_service.place_market_order(
                user_id=user.id,
                exchange=position_group.exchange,
                symbol=position_group.symbol,
                side=close_side,
                quantity=current_qty,
                position_group_id=position_group.id,
                record_in_db=False
            )

            # Mark position as closed
            from datetime import datetime
            position_group.status = PositionGroupStatus.CLOSED
            position_group.closed_at = datetime.utcnow()
            position_group.total_filled_quantity = Decimal("0")
            position_group.unrealized_pnl_usd = Decimal("0")

            # Calculate realized PnL including hedge value
            total_exit_value = current_qty * current_price
            hedge_profit = (position_group.total_hedged_value_usd or Decimal("0")) - (
                (position_group.total_hedged_qty or Decimal("0")) * current_avg_price
            )
            realized_pnl = unrealized_pnl + hedge_profit
            position_group.realized_pnl_usd = realized_pnl

            await position_group_repo.update(position_group)

            logger.info(
                f"OrderFillMonitor: Executed Aggregate TP for idle position {position_group.symbol} "
                f"(ID: {position_group.id}) - Realized PnL: {realized_pnl}"
            )

        except Exception as e:
            logger.error(
                f"OrderFillMonitor: Error checking aggregate TP for position {position_group.id}: {e}"
            )

    async def _check_per_leg_positions_all_tps_hit(self, session: AsyncSession, user):
        """
        Check per_leg mode positions where all entry orders have their TPs hit.
        These positions should be closed since all exits have been executed.
        """
        try:
            position_group_repo = self.position_group_repository_class(session)

            # Get all active positions for this user with per_leg TP mode
            result = await session.execute(
                select(PositionGroup)
                .where(
                    PositionGroup.user_id == user.id,
                    PositionGroup.status == PositionGroupStatus.ACTIVE.value,
                    PositionGroup.tp_mode.in_(["per_leg", "hybrid"])
                )
                .options(selectinload(PositionGroup.dca_orders))
            )
            positions = result.scalars().all()

            if not positions:
                return

            from datetime import datetime

            for pos in positions:
                # Get entry orders (leg_index != 999)
                entry_orders = [o for o in pos.dca_orders if o.leg_index != 999]
                filled_entries = [o for o in entry_orders if o.status == OrderStatus.FILLED.value]

                if not filled_entries:
                    continue

                # Check if ALL filled entries have tp_hit = True
                all_tps_hit = all(o.tp_hit for o in filled_entries)

                if not all_tps_hit:
                    continue

                # Check if there are any open/pending orders
                has_pending_orders = any(
                    o.status in [OrderStatus.OPEN.value, OrderStatus.TRIGGER_PENDING.value, OrderStatus.PARTIALLY_FILLED.value]
                    for o in pos.dca_orders
                )

                if has_pending_orders:
                    continue

                # All TPs hit and no pending orders - position should be closed
                logger.info(
                    f"OrderFillMonitor: Closing idle per_leg position {pos.symbol} (ID: {pos.id}) "
                    f"- all {len(filled_entries)} TPs hit"
                )

                pos.status = PositionGroupStatus.CLOSED
                pos.closed_at = datetime.utcnow()
                pos.total_filled_quantity = Decimal("0")
                pos.unrealized_pnl_usd = Decimal("0")

                await position_group_repo.update(pos)

                logger.info(f"OrderFillMonitor: Position {pos.id} closed - all per-leg TPs hit")

        except Exception as e:
            logger.error(f"OrderFillMonitor: Error in _check_per_leg_positions_all_tps_hit: {e}")

    async def _check_pyramid_aggregate_tp_for_idle_positions(self, session: AsyncSession, user):
        """
        Check pyramid_aggregate TP for positions that have no open orders.
        Each pyramid is closed independently when its weighted average entry reaches the TP target.
        """
        try:
            from datetime import datetime
            position_group_repo = self.position_group_repository_class(session)

            logger.info(f"OrderFillMonitor: _check_pyramid_aggregate_tp_for_idle_positions called for user {user.id}")

            # Get all active/partially_filled positions for this user with pyramid_aggregate TP mode
            result = await session.execute(
                select(PositionGroup)
                .where(
                    PositionGroup.user_id == user.id,
                    PositionGroup.status.in_([PositionGroupStatus.ACTIVE.value, PositionGroupStatus.PARTIALLY_FILLED.value]),
                    PositionGroup.tp_mode == "pyramid_aggregate",
                    PositionGroup.tp_aggregate_percent > 0,
                    PositionGroup.total_filled_quantity > 0
                )
                .options(selectinload(PositionGroup.dca_orders))
            )
            positions = result.scalars().all()

            if not positions:
                logger.info(f"OrderFillMonitor: No pyramid_aggregate positions found for user {user.id}")
                return

            logger.info(
                f"OrderFillMonitor: Found {len(positions)} pyramid_aggregate positions for user {user.id}: "
                f"{[(p.symbol, str(p.id)[:8], p.total_filled_quantity, p.tp_mode) for p in positions]}"
            )

            # Group by exchange
            positions_by_exchange: Dict[str, List[PositionGroup]] = {}
            for pos in positions:
                ex = pos.exchange.lower()
                if ex not in positions_by_exchange:
                    positions_by_exchange[ex] = []
                positions_by_exchange[ex].append(pos)

            for exchange_name, positions_to_check in positions_by_exchange.items():
                if not positions_to_check:
                    continue

                try:
                    # Setup connector
                    if exchange_name == "mock":
                        exchange_keys_data = {
                            "api_key": "mock_api_key_12345",
                            "api_secret": "mock_api_secret_67890"
                        }
                    else:
                        exchange_keys_data = user.encrypted_api_keys.get(exchange_name)
                        if not exchange_keys_data:
                            continue

                    connector = get_exchange_connector(exchange_name, exchange_config=exchange_keys_data)

                    try:
                        for pos in positions_to_check:
                            await self._check_single_position_pyramid_aggregate_tp(
                                session, user, pos, connector, position_group_repo
                            )
                    finally:
                        await connector.close()

                except Exception as e:
                    logger.error(f"OrderFillMonitor: Error checking pyramid_aggregate TP for {exchange_name}: {e}")

        except Exception as e:
            logger.error(f"OrderFillMonitor: Error in _check_pyramid_aggregate_tp_for_idle_positions: {e}")

    async def _check_single_position_pyramid_aggregate_tp(
        self,
        session: AsyncSession,
        user,
        position_group: PositionGroup,
        connector,
        position_group_repo
    ):
        """Check pyramid aggregate TP for a single position and execute if triggered."""
        try:
            from datetime import datetime
            from app.services.telegram_signal_helper import broadcast_tp_hit
            from app.models.pyramid import Pyramid

            current_price = Decimal(str(await connector.get_current_price(position_group.symbol)))

            # Get all pyramids for this position
            result = await session.execute(
                select(Pyramid)
                .where(Pyramid.group_id == position_group.id)
                .options(selectinload(Pyramid.dca_orders))
            )
            pyramids = result.scalars().all()

            logger.info(
                f"OrderFillMonitor: Checking pyramid_aggregate TP for {position_group.symbol} "
                f"(ID: {str(position_group.id)[:8]}) - {len(pyramids)} pyramids, current_price={current_price}"
            )

            position_closed = False
            from app.models.pyramid import PyramidStatus

            for pyramid in pyramids:
                # Skip already closed pyramids
                if pyramid.status == PyramidStatus.CLOSED or str(pyramid.status) == 'closed':
                    logger.info(f"OrderFillMonitor: Pyramid {pyramid.pyramid_index} already CLOSED, skipping")
                    continue

                # Log all orders for this pyramid
                all_pyramid_orders = [o for o in position_group.dca_orders if o.pyramid_id == pyramid.id]
                logger.info(
                    f"OrderFillMonitor: Pyramid {pyramid.pyramid_index} (status={pyramid.status}) has {len(all_pyramid_orders)} orders. "
                    f"Statuses: {[(o.leg_index, str(o.status), o.tp_hit) for o in all_pyramid_orders]}"
                )

                # Get filled entry orders for this pyramid that haven't hit TP yet
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
                    o for o in position_group.dca_orders
                    if o.pyramid_id == pyramid.id
                    and is_filled(o.status)
                    and o.leg_index != 999
                    and not o.tp_hit
                ]

                logger.info(
                    f"OrderFillMonitor: Pyramid {pyramid.pyramid_index} - "
                    f"{len(pyramid_filled_orders)} filled orders eligible for TP check"
                )

                if not pyramid_filled_orders:
                    logger.info(f"OrderFillMonitor: Pyramid {pyramid.pyramid_index} - no eligible orders, skipping")
                    continue

                # Calculate weighted average entry for this pyramid
                total_qty = Decimal("0")
                total_value = Decimal("0")

                for order in pyramid_filled_orders:
                    qty = order.filled_quantity or order.quantity
                    price = order.avg_fill_price or order.price
                    total_qty += qty
                    total_value += qty * price
                    logger.info(
                        f"OrderFillMonitor: Order leg {order.leg_index} - qty={qty}, price={price}, "
                        f"filled_qty={order.filled_quantity}, avg_fill_price={order.avg_fill_price}"
                    )

                if total_qty <= 0:
                    logger.info(f"OrderFillMonitor: Pyramid {pyramid.pyramid_index} - total_qty <= 0, skipping")
                    continue

                pyramid_avg_entry = total_value / total_qty

                # Use tp_aggregate_percent for pyramid TP
                tp_percent = position_group.tp_aggregate_percent

                # Calculate pyramid TP target
                pyramid_tp_price = pyramid_avg_entry * (Decimal("1") + tp_percent / Decimal("100"))
                tp_triggered = current_price >= pyramid_tp_price

                logger.info(
                    f"OrderFillMonitor: Pyramid {pyramid.pyramid_index} TP Check - "
                    f"avg_entry={pyramid_avg_entry:.4f}, tp_percent={tp_percent}%, "
                    f"tp_target={pyramid_tp_price:.4f}, current_price={current_price}, "
                    f"triggered={tp_triggered}"
                )

                if not tp_triggered:
                    continue

                logger.info(
                    f"OrderFillMonitor: Pyramid Aggregate TP Triggered for Pyramid {pyramid.pyramid_index} "
                    f"in Group {position_group.id} at {current_price} (Target: {pyramid_tp_price})"
                )

                # Execute market sell for this pyramid's quantity
                order_service = self.order_service_class(
                    session=session,
                    user=user,
                    exchange_connector=connector
                )

                # Place market close order
                close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
                sell_result = await order_service.place_market_order(
                    user_id=user.id,
                    exchange=position_group.exchange,
                    symbol=position_group.symbol,
                    side=close_side,
                    quantity=total_qty,
                    position_group_id=position_group.id,
                    record_in_db=False,
                    pyramid_id=pyramid.id
                )

                if sell_result:
                    fill_price = Decimal(str(sell_result.get("avgPrice", sell_result.get("avg_fill_price", current_price))))
                    exit_fee = Decimal(str(sell_result.get("cumulative_fee", sell_result.get("fee", 0)) or 0))

                    # Calculate PnL
                    pnl_usd = (fill_price - pyramid_avg_entry) * total_qty - exit_fee

                    # Mark orders as TP hit
                    for order in pyramid_filled_orders:
                        order.tp_hit = True

                    # Mark pyramid as CLOSED and store closure details
                    from app.models.pyramid import PyramidStatus
                    pyramid.status = PyramidStatus.CLOSED
                    pyramid.closed_at = datetime.utcnow()
                    pyramid.exit_price = fill_price
                    pyramid.realized_pnl_usd = pnl_usd
                    pyramid.total_quantity = total_qty

                    # Update position stats
                    position_group.total_filled_quantity -= total_qty
                    position_group.realized_pnl_usd += pnl_usd
                    position_group.total_exit_fees_usd += exit_fee

                    # Count remaining open pyramids (not closed)
                    remaining_pyramids = len([p for p in pyramids if p.id != pyramid.id and
                        (p.status != PyramidStatus.CLOSED and p.status != PyramidStatus.CLOSED.value)])

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

                    logger.info(
                        f"OrderFillMonitor: Executed Pyramid Aggregate TP for Pyramid {pyramid.pyramid_index} "
                        f"- Realized PnL: {pnl_usd}, Exit Price: {fill_price}"
                    )

            # Check if all pyramids are closed
            if position_group.total_filled_quantity <= 0:
                position_group.status = PositionGroupStatus.CLOSED
                position_group.closed_at = datetime.utcnow()
                position_group.unrealized_pnl_usd = Decimal("0")
                position_closed = True

                # Cancel any remaining open orders on the exchange
                order_service = self.order_service_class(
                    session=session,
                    user=user,
                    exchange_connector=connector
                )
                await order_service.cancel_open_orders_for_group(position_group.id)

            await position_group_repo.update(position_group)

            if position_closed:
                logger.info(f"OrderFillMonitor: Position {position_group.id} closed - all pyramid TPs executed")

        except Exception as e:
            logger.error(
                f"OrderFillMonitor: Error checking pyramid_aggregate TP for position {position_group.id}: {e}"
            )