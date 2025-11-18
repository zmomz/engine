import asyncio
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dca_order import DCAOrderRepository
from app.repositories.user import UserRepository
from app.models.dca_order import DCAOrder
from app.services.order_management import OrderService
from app.services.exchange_abstraction.interface import ExchangeInterface

class OrderFillMonitorService:
    """
    Monitors open and partially filled DCA orders for all users and updates their status.
    """
    def __init__(
        self,
        dca_order_repository_class: type[DCAOrderRepository],
        user_repository_class: type[UserRepository],
        order_service_class: type[OrderService],
        exchange_connector: ExchangeInterface,
        session_factory: callable,
        polling_interval_seconds: int = 15
    ):
        self.dca_order_repository_class = dca_order_repository_class
        self.user_repository_class = user_repository_class
        self.order_service_class = order_service_class
        self.exchange_connector = exchange_connector
        self.session_factory = session_factory
        self.polling_interval_seconds = polling_interval_seconds
        self._running = False
        self._monitor_task = None

    async def _monitor_loop(self):
        """
        The main monitoring loop that periodically checks order statuses for all users.
        """
        while self._running:
            async with self.session_factory() as session:
                user_repo = self.user_repository_class(session)
                users = await user_repo.get_all()
                for user in users:
                    # TODO: Load user-specific exchange connector
                    order_service = self.order_service_class(session, user, self.exchange_connector)
                    dca_order_repo = self.dca_order_repository_class(session)
                    open_orders = await dca_order_repo.get_open_and_partially_filled_orders_for_user(user.id)
                    for order in open_orders:
                        try:
                            await order_service.check_order_status(order)
                        except Exception as e:
                            print(f"Error checking order {order.id} for user {user.id}: {e}")
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