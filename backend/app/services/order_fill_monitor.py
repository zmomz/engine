import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dca_order import DCAOrderRepository
from app.models.dca_order import DCAOrder, OrderStatus
from app.services.order_management import OrderService
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.db.database import AsyncSessionLocal

class OrderFillMonitorService:
    """
    Monitors open and partially filled DCA orders and updates their status.
    """
    def __init__(
        self,
        dca_order_repository_class: type[DCAOrderRepository],
        order_service_class: type[OrderService],
        exchange_connector: ExchangeInterface,
        session_factory: callable
    ):
        self.dca_order_repository_class = dca_order_repository_class
        self.order_service_class = order_service_class
        self.exchange_connector = exchange_connector
        self.session_factory = session_factory
        self._running = False
        self._monitor_task = None

    async def _monitor_loop(self):
        """
        The main monitoring loop that periodically checks order statuses.
        """
        while self._running:
            async with self.session_factory() as session:
                dca_order_repo = self.dca_order_repository_class(session)
                order_service = self.order_service_class(self.exchange_connector, dca_order_repo)
                open_orders = await dca_order_repo.get_open_and_partially_filled_orders()
                for order in open_orders:
                    try:
                        await order_service.check_order_status(order) # This will update the order in DB
                    except Exception as e:
                        print(f"Error checking order {order.id}: {e}") # Log the error, but continue
            await asyncio.sleep(self.polling_interval_seconds)

    async def start_monitoring(self):
        """
        Starts the background monitoring task.
        """
        if not self._running:
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            print("OrderFillMonitorService started.")

    async def stop_monitoring(self):
        """
        Stops the background monitoring task.
        """
        if self._running and self._monitor_task:
            self._running = False
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            print("OrderFillMonitorService stopped.")
