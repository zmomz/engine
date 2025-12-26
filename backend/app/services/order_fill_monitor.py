"""
FIXED Service for monitoring order fills and updating their status in the database.
Key fix: Properly handles the Bybit testnet workaround by continuing with position updates
even when check_order_status triggers the workaround.
"""
import asyncio
import logging
from typing import List
import json
import ccxt
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.user import UserRepository
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

    async def _check_orders(self):
        """
        Fetches open orders from the DB and checks their status on the exchange.
        Uses batch query to avoid N+1 query issues.
        """
        if not self.encryption_service:
            logger.error("EncryptionService not available. Skipping order checks.")
            return

        async with self.session_factory() as session:
            try:
                user_repo = UserRepository(session)
                active_users = await user_repo.get_all_active_users()
                logger.debug(f"OrderFillMonitor: Found {len(active_users)} active users.")

                # Filter users with API keys and get their IDs
                users_with_keys = [u for u in active_users if u.encrypted_api_keys]
                if not users_with_keys:
                    logger.debug("OrderFillMonitor: No users with API keys, skipping.")
                    return

                # Batch fetch all orders for all users in a single query (prevents N+1)
                dca_order_repo = self.dca_order_repository_class(session)
                user_ids = [str(u.id) for u in users_with_keys]
                orders_by_user = await dca_order_repo.get_all_open_orders_for_all_users(user_ids)
                logger.debug(f"OrderFillMonitor: Batch loaded orders for {len(orders_by_user)} users.")

                for user in users_with_keys:
                    try:
                        # Get pre-fetched orders for this user
                        all_orders = orders_by_user.get(str(user.id), [])
                        logger.debug(f"OrderFillMonitor: User {user.id} - Found {len(all_orders)} open/partially filled orders.")

                        if not all_orders:
                            continue
                            
                        # Group orders by exchange
                        orders_by_exchange = {}
                        for order in all_orders:
                            logger.debug(f"OrderFillMonitor: Processing order {order.id} with initial status {order.status}.")
                            if not order.group:
                                logger.error(f"Order {order.id} has no position group attached. This should not happen. Skipping.")
                                continue
                            ex = order.group.exchange
                            if ex not in orders_by_exchange:
                                orders_by_exchange[ex] = []
                            orders_by_exchange[ex].append(order)
                            
                        # Process each exchange - reuse connector for all orders on same exchange
                        for raw_exchange_name, orders_to_check in orders_by_exchange.items():
                             exchange_name = raw_exchange_name.lower()
                             # Decrypt keys for this exchange - done once per exchange
                             try:
                                 exchange_keys_data = user.encrypted_api_keys.get(exchange_name)

                                 if not exchange_keys_data:
                                     logger.warning(f"No API keys found for exchange {exchange_name} (from {raw_exchange_name}) for user {user.id}, skipping orders for this exchange.")
                                     continue

                                 api_key, secret_key = self.encryption_service.decrypt_keys(exchange_keys_data)

                                 # Create connector ONCE per exchange per monitoring cycle
                                 logger.debug(f"Setting up connector for {exchange_name} (will be reused for {len(orders_to_check)} orders)")
                                 connector = get_exchange_connector(
                                    exchange_name,
                                    exchange_config=exchange_keys_data
                                 )
                             except Exception as e:
                                 logger.error(f"Failed to setup connector for {exchange_name}: {e}")
                                 continue

                             try:
                                 # Create services ONCE per exchange - reused for all orders
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

                                 for order in orders_to_check:
                                    try:
                                        # If already filled, we are here to check the TP order
                                        if order.status == OrderStatus.FILLED.value:
                                            updated_order = await order_service.check_tp_status(order)
                                            if updated_order.tp_hit:
                                                logger.info(f"TP hit for order {order.id}. Updating position stats.")
                                                # Flush tp_hit update before recalculating stats
                                                await session.flush()
                                                await position_manager.update_position_stats(updated_order.group_id, session=session)

                                                # Broadcast per-leg TP hit notification
                                                if updated_order.group and updated_order.pyramid_id:
                                                    pyramid = await session.get(Pyramid, updated_order.pyramid_id)
                                                    if pyramid:
                                                        # Calculate PnL for this leg
                                                        entry_price = updated_order.price
                                                        exit_price = updated_order.tp_price
                                                        if entry_price and exit_price:
                                                            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
                                                            pnl_usd = (exit_price - entry_price) * updated_order.filled_quantity
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

                                                # Trigger risk evaluation on TP hit (position closed/reduced)
                                                await self._trigger_risk_evaluation_on_fill(user, session)
                                            continue
                                        
                                        # --- NEW TRIGGER LOGIC ---
                                        if order.status == OrderStatus.TRIGGER_PENDING.value:
                                            # Watch price
                                            current_price = Decimal(str(await connector.get_current_price(order.symbol)))
                                            should_trigger = False

                                            # Check if DCA should be cancelled due to price moving beyond threshold
                                            await self._check_dca_beyond_threshold(order, current_price, order_service, session)
                                            # Refresh order status in case it was cancelled
                                            await session.refresh(order)
                                            if order.status == OrderStatus.CANCELLED.value:
                                                continue

                                            logger.debug(f"Checking Trigger for Order {order.id} ({order.side}): Target {order.price}, Current {current_price}")

                                            if order.side == "buy":
                                                if current_price <= order.price:
                                                    should_trigger = True
                                            else: # sell
                                                if current_price >= order.price:
                                                    should_trigger = True

                                            if should_trigger:
                                                logger.info(f"Trigger condition met for Order {order.id}. Submitting Market Order.")
                                                # Submit now. OrderService handles placing market order.
                                                await order_service.submit_order(order)
                                                # After submit, status should be FILLED (market) or OPEN.
                                                await session.refresh(order)
                                                logger.info(f"Triggered Order {order.id} status is now {order.status}")

                                                if order.status == OrderStatus.FILLED.value:
                                                    await position_manager.update_position_stats(order.group_id, session=session)
                                                    # So we need to call `place_tp_order` if filled.
                                                    await order_service.place_tp_order(order)

                                                    # Broadcast DCA fill notification for triggered market order
                                                    if order.group and order.pyramid_id:
                                                        pyramid = await session.get(Pyramid, order.pyramid_id)
                                                        if pyramid:
                                                            await broadcast_dca_fill(
                                                                position_group=order.group,
                                                                order=order,
                                                                pyramid=pyramid,
                                                                session=session
                                                            )

                                                    # Trigger risk evaluation on fill
                                                    await self._trigger_risk_evaluation_on_fill(user, session)
                                            continue
                                        # -------------------------

                                        # Check if OPEN DCA order should be cancelled due to price beyond threshold
                                        if order.status == OrderStatus.OPEN.value:
                                            try:
                                                current_price = Decimal(str(await connector.get_current_price(order.symbol)))
                                                await self._check_dca_beyond_threshold(order, current_price, order_service, session)
                                                await session.refresh(order)
                                                if order.status == OrderStatus.CANCELLED.value:
                                                    continue
                                            except Exception as price_err:
                                                logger.debug(f"Could not fetch price for DCA threshold check: {price_err}")

                                        # Attempt to get order status from the exchange
                                        # This may trigger the Bybit workaround which marks order as FILLED
                                        logger.info(f"Checking order {order.id} status on exchange...")
                                        updated_order = await order_service.check_order_status(order)
                                        
                                        # Refresh order from DB to get latest status (in case workaround updated it)
                                        await session.refresh(updated_order)
                                        
                                        logger.info(f"Order {order.id} status after check: {updated_order.status}")
                                        
                                        # Check if status changed to filled, cancelled, or failed
                                        if updated_order.status == OrderStatus.FILLED or updated_order.status == OrderStatus.CANCELLED or updated_order.status == OrderStatus.FAILED:
                                            logger.info(f"Order {order.id} status updated to {updated_order.status}")

                                        # Handle filled orders
                                        if updated_order.status == OrderStatus.FILLED.value:

                                            # CRITICAL: Flush order status and filled details update before recalculating stats
                                            await session.flush()

                                            logger.info(f"Order {order.id} FILLED - updating position stats and placing TP order")
                                            await position_manager.update_position_stats(updated_order.group_id, session=session)
                                            await order_service.place_tp_order(updated_order)
                                            logger.info(f"✓ Successfully placed TP order for {updated_order.id}")

                                            # Broadcast DCA fill notification
                                            if updated_order.group and updated_order.pyramid_id:
                                                pyramid = await session.get(Pyramid, updated_order.pyramid_id)
                                                if pyramid:
                                                    await broadcast_dca_fill(
                                                        position_group=updated_order.group,
                                                        order=updated_order,
                                                        pyramid=pyramid,
                                                        session=session
                                                    )

                                            # Trigger risk evaluation on fill
                                            await self._trigger_risk_evaluation_on_fill(user, session)

                                        # Handle partially filled orders - place TP for filled portion
                                        elif updated_order.status == OrderStatus.PARTIALLY_FILLED.value:
                                            await session.flush()

                                            # Only place partial TP if we have filled quantity and no TP order yet
                                            if updated_order.filled_quantity and updated_order.filled_quantity > 0 and not updated_order.tp_order_id:
                                                logger.info(
                                                    f"Order {order.id} PARTIALLY_FILLED ({updated_order.filled_quantity}/{updated_order.quantity}) "
                                                    f"- updating position stats and placing partial TP order"
                                                )
                                                await position_manager.update_position_stats(updated_order.group_id, session=session)
                                                await order_service.place_tp_order_for_partial_fill(updated_order)
                                                logger.info(f"✓ Successfully placed partial TP order for {updated_order.id}")

                                                # Broadcast DCA fill notification for partial fill
                                                if updated_order.group and updated_order.pyramid_id:
                                                    pyramid = await session.get(Pyramid, updated_order.pyramid_id)
                                                    if pyramid:
                                                        await broadcast_dca_fill(
                                                            position_group=updated_order.group,
                                                            order=updated_order,
                                                            pyramid=pyramid,
                                                            session=session
                                                        )

                                                # Trigger risk evaluation on partial fill
                                                await self._trigger_risk_evaluation_on_fill(user, session)
                                                
                                    except Exception as e:
                                        logger.error(f"Error processing loop for order {order.id}: {e}")
                                        import traceback
                                        traceback.print_exc()
                             finally:
                                 await connector.close()
                        
                        await session.commit()
                        logger.debug(f"OrderFillMonitor: Committed changes for user {user.id}")
                        
                    except Exception as e:
                        logger.error(f"Error checking orders for user {user.username}: {e}")
                        import traceback
                        traceback.print_exc()
                        await session.rollback()

            except Exception as e:
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