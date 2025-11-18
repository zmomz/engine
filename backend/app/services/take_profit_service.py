import asyncio
from decimal import Decimal
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.position_group import PositionGroupRepository
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.user import UserRepository
from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder, OrderStatus
from app.services.order_management import OrderService
from app.services.exchange_abstraction.interface import ExchangeInterface

# Helper functions from EP.md 6.3 Take-Profit Monitoring
def is_tp_reached(order: DCAOrder, current_price: Decimal, side: str) -> bool:
    if order.avg_fill_price and order.tp_percent:
        if side == "long":
            target_tp_price = order.avg_fill_price * (Decimal("1") + order.tp_percent / Decimal("100"))
            return current_price >= target_tp_price
        else: # short
            target_tp_price = order.avg_fill_price * (Decimal("1") - order.tp_percent / Decimal("100"))
            return current_price <= target_tp_price
    if side == "long":
        return current_price >= order.tp_price
    else:
        return current_price <= order.tp_price

def calculate_aggregate_tp_price(
    weighted_avg_entry: Decimal,
    tp_percent: Decimal,
    side: str
) -> Decimal:
    if side == "long":
        return weighted_avg_entry * (Decimal("1") + tp_percent / Decimal("100"))
    else:
        return weighted_avg_entry * (Decimal("1") - tp_percent / Decimal("100"))

def is_price_beyond_target(current_price: Decimal, target_price: Decimal, side: str) -> bool:
    if side == "long":
        return current_price >= target_price
    else:
        return current_price <= target_price

async def check_take_profit_conditions(
    position_group: PositionGroup,
    current_price: Decimal
) -> List[DCAOrder]:
    orders_to_close = []
    if position_group.tp_mode == "per_leg":
        for order in position_group.dca_orders:
            if order.status == OrderStatus.FILLED and not order.tp_hit:
                if is_tp_reached(order, current_price, position_group.side):
                    orders_to_close.append(order)
    elif position_group.tp_mode == "aggregate":
        target_price = calculate_aggregate_tp_price(
            position_group.weighted_avg_entry,
            position_group.tp_aggregate_percent,
            position_group.side
        )
        if is_price_beyond_target(current_price, target_price, position_group.side):
            orders_to_close = [
                order for order in position_group.dca_orders
                if order.status == OrderStatus.FILLED and not order.tp_hit
            ]
    elif position_group.tp_mode == "hybrid":
        per_leg_triggered = []
        for order in position_group.dca_orders:
            if order.status == OrderStatus.FILLED and not order.tp_hit:
                if is_tp_reached(order, current_price, position_group.side):
                    per_leg_triggered.append(order)
        aggregate_target = calculate_aggregate_tp_price(
            position_group.weighted_avg_entry,
            position_group.tp_aggregate_percent,
            position_group.side
        )
        aggregate_triggered = is_price_beyond_target(
            current_price, aggregate_target, position_group.side
        )
        if per_leg_triggered:
            orders_to_close = per_leg_triggered
        elif aggregate_triggered:
            orders_to_close = [
                order for order in position_group.dca_orders
                if order.status == OrderStatus.FILLED and not order.tp_hit
            ]
    return orders_to_close

class TakeProfitService:
    def __init__(
        self,
        position_group_repository_class: type[PositionGroupRepository],
        dca_order_repository_class: type[DCAOrderRepository],
        user_repository_class: type[UserRepository],
        order_service_class: type[OrderService],
        exchange_connector: ExchangeInterface,
        session_factory: callable,
        polling_interval_seconds: int = 5
    ):
        self.position_group_repository_class = position_group_repository_class
        self.dca_order_repository_class = dca_order_repository_class
        self.user_repository_class = user_repository_class
        self.order_service_class = order_service_class
        self.exchange_connector = exchange_connector
        self.session_factory = session_factory
        self.polling_interval_seconds = polling_interval_seconds
        self._running = False
        self._monitor_task = None

    async def _monitor_loop(self):
        while self._running:
            try:
                await self.check_all_users_positions()
                await asyncio.sleep(self.polling_interval_seconds)
            except asyncio.CancelledError:
                break

    async def check_all_users_positions(self):
        async with self.session_factory() as session:
            user_repo = self.user_repository_class(session)
            users = await user_repo.get_all()
            for user in users:
                await self.check_positions_for_user(session, user)

    async def check_positions_for_user(self, session: AsyncSession, user):
        position_group_repo = self.position_group_repository_class(session)
        dca_order_repo = self.dca_order_repository_class(session)
        # TODO: Load user-specific exchange connector
        order_service = self.order_service_class(session, user, self.exchange_connector)

        active_position_groups = await position_group_repo.get_active_position_groups_for_user(user.id)

        for group in active_position_groups:
            try:
                current_price = await self.exchange_connector.get_current_price(group.symbol)
                orders_to_close = await check_take_profit_conditions(group, current_price)

                for order in orders_to_close:
                    print(f"TP hit for order {order.id}. Closing position.")
                    order.tp_hit = True
                    await dca_order_repo.update(order)
            except Exception as e:
                print(f"Error checking TP for position group {group.id} for user {user.id}: {e}")

    async def start_monitoring(self):
        if not self._running:
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            print("TakeProfitService started.")

    async def stop_monitoring(self):
        if self._running and self._monitor_task:
            self._running = False
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            print("TakeProfitService stopped.")