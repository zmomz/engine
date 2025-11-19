"""
Service for monitoring order fills and updating their status in the database.
Periodically polls the exchange for updates on open orders.
"""
import asyncio
import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.order_management import OrderService
from app.services.position_manager import PositionManagerService
from app.models.dca_order import DCAOrder, OrderStatus

logger = logging.getLogger(__name__)

class OrderFillMonitorService:
    def __init__(
        self,
        session_factory: callable,
        dca_order_repository_class: type[DCAOrderRepository],
        position_group_repository_class: type[PositionGroupRepository],
        exchange_connector: ExchangeInterface,
        order_service_class: type[OrderService],
        position_manager_service_class: type[PositionManagerService],
        polling_interval_seconds: int = 5
    ):
        self.session_factory = session_factory
        self.dca_order_repository_class = dca_order_repository_class
        self.position_group_repository_class = position_group_repository_class
        self.exchange_connector = exchange_connector
        self.order_service_class = order_service_class
        self.position_manager_service_class = position_manager_service_class
        self.polling_interval_seconds = polling_interval_seconds
        self._running = False
        self._monitor_task = None

    async def _check_orders(self):
        """
        Fetches open orders from the DB and checks their status on the exchange.
        """
        async for session in self.session_factory():
            try:
                dca_order_repo = self.dca_order_repository_class(session)
                
                order_service = self.order_service_class(
                    session=session,
                    user=None, # Not needed for check_order_status if connector is ready
                    exchange_connector=self.exchange_connector
                )
                
                # Instantiate PositionManagerService partially (only what's needed for update_position_stats)
                position_manager = self.position_manager_service_class(
                    session=session,
                    user=None, # Unused in update_position_stats
                    position_group_repository_class=self.position_group_repository_class,
                    grid_calculator_service=None, # Unused
                    order_service_class=None, # Unused
                    exchange_connector=None # Unused
                )

                # Get all open and partially filled orders globally (or we could shard by user)
                orders_to_check = await dca_order_repo.get_open_and_partially_filled_orders()

                if not orders_to_check:
                    # logger.debug("No open orders to check.")
                    return

                logger.info(f"OrderFillMonitor: Checking status for {len(orders_to_check)} orders.")

                for order in orders_to_check:
                    try:
                        # This updates the order in the session if changed
                        updated_order = await order_service.check_order_status(order)
                        if updated_order.status in ["filled", "cancelled", "failed"]:
                             logger.info(f"Order {order.id} status updated to {updated_order.status}")
                             
                        if updated_order.status == OrderStatus.FILLED.value:
                            # 1. Update Position Group Stats (Avg Entry, Total Qty)
                            await position_manager.update_position_stats(updated_order.group_id)
                            
                            # 2. Place TP Order
                            await order_service.place_tp_order(updated_order)
                            logger.info(f"Placed TP order for {updated_order.id}")
                            
                    except Exception as e:
                        logger.error(f"Failed to check status for order {order.id}: {e}")
                
                await session.commit()

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
