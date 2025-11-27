"""
Service for monitoring order fills and updating their status in the database.
Periodically polls the exchange for updates on open orders.
"""
import asyncio
import logging
from typing import List
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.user import UserRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.order_management import OrderService
from app.services.position_manager import PositionManagerService
from app.models.dca_order import DCAOrder, OrderStatus
from app.core.security import EncryptionService

logger = logging.getLogger(__name__)

class OrderFillMonitorService:
    def __init__(
        self,
        session_factory: callable,
        dca_order_repository_class: type[DCAOrderRepository],
        position_group_repository_class: type[PositionGroupRepository],
        order_service_class: type[OrderService],
        position_manager_service_class: type[PositionManagerService],
        polling_interval_seconds: int = 5
    ):
        self.session_factory = session_factory
        self.dca_order_repository_class = dca_order_repository_class
        self.position_group_repository_class = position_group_repository_class
        self.order_service_class = order_service_class
        self.position_manager_service_class = position_manager_service_class
        self.polling_interval_seconds = polling_interval_seconds
        self._running = False
        self._monitor_task = None
        try:
            self.encryption_service = EncryptionService()
        except Exception as e:
            logger.error(f"OrderFillMonitor failed to init encryption service: {e}")
            self.encryption_service = None

    async def _check_orders(self):
        """
        Fetches open orders from the DB and checks their status on the exchange.
        """
        if not self.encryption_service:
            logger.error("EncryptionService not available. Skipping order checks.")
            return

        async with self.session_factory() as session:
            try:
                user_repo = UserRepository(session)
                active_users = await user_repo.get_all_active_users()
                logger.info(f"OrderFillMonitor: Found {len(active_users)} active users.")

                for user in active_users:
                    try:
                        if not user.encrypted_api_keys:
                            logger.info(f"OrderFillMonitor: User {user.id} has no API keys, skipping.")
                            continue

                        dca_order_repo = self.dca_order_repository_class(session)
                        # Fetch all open orders for user, eagerly loading the position group
                        all_orders = await dca_order_repo.get_open_and_partially_filled_orders(user_id=user.id)
                        logger.info(f"OrderFillMonitor: User {user.id} - Found {len(all_orders)} open/partially filled orders.")

                        if not all_orders:
                            continue
                            
                        # Group orders by exchange
                        orders_by_exchange = {}
                        for order in all_orders:
                            logger.info(f"OrderFillMonitor: Processing order {order.id} with initial status {order.status}.")
                            if not order.group:
                                logger.error(f"Order {order.id} has no position group attached. This should not happen. Skipping.")
                                continue
                            ex = order.group.exchange
                            if ex not in orders_by_exchange:
                                orders_by_exchange[ex] = []
                            orders_by_exchange[ex].append(order)
                            
                        # Process each exchange
                        for raw_exchange_name, orders_to_check in orders_by_exchange.items():
                             exchange_name = raw_exchange_name.lower()
                             # Decrypt keys for this exchange
                             try:
                                 # Expecting user.encrypted_api_keys to be a dict of {'exchange_name': {'encrypted_data': '...'}}
                                 exchange_keys_data = user.encrypted_api_keys.get(exchange_name)

                                 if not exchange_keys_data:
                                     logger.warning(f"No API keys found for exchange {exchange_name} (from {raw_exchange_name}) for user {user.id}, skipping orders for this exchange.")
                                     continue
                                 
                                 api_key, secret_key = self.encryption_service.decrypt_keys(exchange_keys_data)
                                 
                                 connector = get_exchange_connector(
                                    exchange_name, 
                                    api_key=api_key, 
                                    secret_key=secret_key
                                 )
                             except Exception as e:
                                 logger.error(f"Failed to setup connector for {exchange_name}: {e}")
                                 continue
                             
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
                                order_service_class=None, 
                                exchange_connector=connector
                             )

                             for order in orders_to_check:
                                try:
                                    # If already filled, we are here to check the TP order
                                    if order.status == OrderStatus.FILLED.value:
                                        updated_order = await order_service.check_tp_status(order)
                                        if updated_order.tp_hit:
                                            logger.info(f"TP hit for order {order.id}. Updating position stats.")
                                            await position_manager.update_position_stats(updated_order.group_id, session=session)
                                        continue

                                    updated_order = await order_service.check_order_status(order)
                                    if updated_order.status in ["filled", "cancelled", "failed"]:
                                         logger.info(f"Order {order.id} status updated to {updated_order.status}")
                                         
                                    if updated_order.status == OrderStatus.FILLED.value:
                                        await position_manager.update_position_stats(updated_order.group_id, session=session)
                                        await order_service.place_tp_order(updated_order)
                                        logger.info(f"Placed TP order for {updated_order.id}")
                                        
                                except Exception as e:
                                    logger.error(f"Failed to check status for order {order.id}: {e}")
                        
                        await session.commit()
                    except Exception as e:
                        logger.error(f"Error checking orders for user {user.username}: {e}")
                        await session.rollback()

            except Exception as e:
                logger.error(f"Error in OrderFillMonitor check loop: {e}")
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
        while self._running:
            try:
                await self._check_orders()
                await asyncio.sleep(self.polling_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in OrderFillMonitor monitoring loop: {e}")
                await asyncio.sleep(self.polling_interval_seconds)

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
            logger.info("OrderFillMonitorService monitoring task stopped.")
