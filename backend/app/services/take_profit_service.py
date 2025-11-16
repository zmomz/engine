import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.position_group import PositionGroupRepository
from app.repositories.dca_order import DCAOrderRepository
from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder, OrderStatus
from app.services.order_management import OrderService
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.db.database import AsyncSessionLocal

# Helper functions from EP.md 6.3 Take-Profit Monitoring
def is_tp_reached(order: DCAOrder, current_price: Decimal, side: str) -> bool:
    """
    Check if current price reached the TP target for this order.
    TP is calculated from actual fill price, not original entry.
    """
    if order.avg_fill_price and order.tp_percent:
        if side == "long":
            target_tp_price = order.avg_fill_price * (Decimal("1") + order.tp_percent / Decimal("100"))
            return current_price >= target_tp_price
        else: # short
            target_tp_price = order.avg_fill_price * (Decimal("1") - order.tp_percent / Decimal("100"))
            return current_price <= target_tp_price
    
    # Fallback to pre-calculated tp_price if avg_fill_price is not available
    if side == "long":
        return current_price >= order.tp_price
    else:
        return current_price <= order.tp_price

def calculate_aggregate_tp_price(
    weighted_avg_entry: Decimal,
    tp_percent: Decimal,
    side: str
) -> Decimal:
    """
    Calculate aggregate TP price from weighted average entry.
    """
    if side == "long":
        return weighted_avg_entry * (Decimal("1") + tp_percent / Decimal("100"))
    else:
        return weighted_avg_entry * (Decimal("1") - tp_percent / Decimal("100"))

def is_price_beyond_target(current_price: Decimal, target_price: Decimal, side: str) -> bool:
    """
    Checks if the current price has moved beyond the target price based on the side.
    For long positions, current_price >= target_price.
    For short positions, current_price <= target_price.
    """
    if side == "long":
        return current_price >= target_price
    else:
        return current_price <= target_price

async def check_take_profit_conditions(
    position_group: PositionGroup,
    current_price: Decimal
) -> List[DCAOrder]:
    """
    Check TP conditions based on tp_mode.
    Returns list of DCA orders that hit their TP target.
    
    Three modes (SoW Section 2.4):
    1. per_leg: Each DCA closes independently
    2. aggregate: Entire position closes when avg entry reaches TP
    3. hybrid: Both logics run, whichever closes first
    """
    orders_to_close = []
    
    if position_group.tp_mode == "per_leg":
        # Check each filled DCA leg individually
        for order in position_group.dca_orders:
            if order.status == OrderStatus.FILLED and not order.tp_hit:
                if is_tp_reached(order, current_price, position_group.side):
                    orders_to_close.append(order)
    
    elif position_group.tp_mode == "aggregate":
        # Check if weighted average entry reached aggregate TP
        target_price = calculate_aggregate_tp_price(
            position_group.weighted_avg_entry,
            position_group.tp_aggregate_percent,
            position_group.side
        )
        
        if is_price_beyond_target(current_price, target_price, position_group.side):
            # Close entire position
            orders_to_close = [
                order for order in position_group.dca_orders
                if order.status == OrderStatus.FILLED and not order.tp_hit
            ]
    
    elif position_group.tp_mode == "hybrid":
        # Check both per-leg and aggregate
        # Whichever triggers first wins
        
        # Per-leg check
        per_leg_triggered = []
        for order in position_group.dca_orders:
            if order.status == OrderStatus.FILLED and not order.tp_hit:
                if is_tp_reached(order, current_price, position_group.side):
                    per_leg_triggered.append(order)
        
        # Aggregate check
        aggregate_target = calculate_aggregate_tp_price(
            position_group.weighted_avg_entry,
            position_group.tp_aggregate_percent,
            position_group.side
        )
        aggregate_triggered = is_price_beyond_target(
            current_price, aggregate_target, position_group.side
        )
        
        if per_leg_triggered:
            # Per-leg TP hit - close those legs only
            orders_to_close = per_leg_triggered
        elif aggregate_triggered:
            # Aggregate TP hit - close entire position
            orders_to_close = [
                order for order in position_group.dca_orders
                if order.status == OrderStatus.FILLED and not order.tp_hit
            ]
    
    return orders_to_close


class TakeProfitService:
    """
    Monitors active position groups for take-profit conditions and executes closing orders.
    """
    def __init__(
        self,
        position_group_repository_class: type[PositionGroupRepository],
        dca_order_repository_class: type[DCAOrderRepository],
        order_service_class: type[OrderService],
        exchange_connector: ExchangeInterface,
        session_factory: callable,
        polling_interval_seconds: int = 5
    ):
        self.position_group_repository_class = position_group_repository_class
        self.dca_order_repository_class = dca_order_repository_class
        self.order_service_class = order_service_class
        self.exchange_connector = exchange_connector
        self.session_factory = session_factory
        self.polling_interval_seconds = polling_interval_seconds
        self._running = False
        self._monitor_task = None

    async def _monitor_loop(self):
        """
        The main monitoring loop that periodically checks take-profit conditions.
        """
        while self._running:
            try:
                await self.check_positions()
                await asyncio.sleep(self.polling_interval_seconds)
            except asyncio.CancelledError:
                break

    async def check_positions(self):
        """
        Checks all active positions for TP conditions.
        This method is separate from the loop to allow for easier testing.
        """
        async with self.session_factory() as session:
            position_group_repo = self.position_group_repository_class(session)
            dca_order_repo = self.dca_order_repository_class(session)
            order_service = self.order_service_class(self.exchange_connector, dca_order_repo)

            active_position_groups = await position_group_repo.get_active_position_groups()

            for group in active_position_groups:
                try:
                    current_price = await self.exchange_connector.get_current_price(group.symbol)
                    orders_to_close = await check_take_profit_conditions(group, current_price)

                    for order in orders_to_close:
                        # Place market order to close the position/leg
                        # For simplicity, assuming market close for TP for now.
                        # The OrderService.close_position method would handle this.
                        print(f"TP hit for order {order.id}. Closing position.")
                        # await order_service.close_position(order) # This method needs to be implemented in OrderService
                        # For now, just mark as TP hit and log
                        order.tp_hit = True
                        await dca_order_repo.update(order.id, {"tp_hit": True})

                except Exception as e:
                    print(f"Error checking TP for position group {group.id}: {e}")

    async def start_monitoring(self):
        """
        Starts the background monitoring task.
        """
        if not self._running:
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            print("TakeProfitService started.")

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
            print("TakeProfitService stopped.")
