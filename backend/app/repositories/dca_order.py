from sqlalchemy import select, or_, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup
from app.models.pyramid import Pyramid
from app.repositories.base import BaseRepository


class DCAOrderRepository(BaseRepository[DCAOrder]):
    def __init__(self, session: AsyncSession):
        super().__init__(DCAOrder, session)

    async def get_open_and_partially_filled_orders_for_user(self, user_id: str) -> List[DCAOrder]:
        # Assuming DCAOrder has a relationship 'group' to PositionGroup
        result = await self.session.execute(
            select(self.model)
            .options(joinedload(self.model.group))
            .join(PositionGroup, self.model.group_id == PositionGroup.id)
            .where(
                or_(
                    self.model.status.in_([OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value, OrderStatus.TRIGGER_PENDING.value]),
                    # Filled ENTRY orders with TP placed, waiting for TP to hit
                    # Exclude leg_index=999 which are TP fill records
                    and_(
                        self.model.status == OrderStatus.FILLED.value,
                        self.model.tp_order_id.isnot(None),
                        self.model.tp_hit == False,
                        self.model.leg_index != 999
                    )
                ),
                PositionGroup.user_id == user_id
            )
        )
        return result.scalars().all()

    async def get_open_and_partially_filled_orders(self, user_id: str = None) -> List[DCAOrder]:
        if user_id:
            return await self.get_open_and_partially_filled_orders_for_user(user_id)
        
        result = await self.session.execute(
            select(self.model).where(
                self.model.status.in_([OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value])
            )
        )
        return result.scalars().all()

    async def get_all_open_orders(self) -> List[DCAOrder]:
        result = await self.session.execute(
            select(self.model).where(self.model.status == OrderStatus.OPEN.value)
        )
        return result.scalars().all()

    async def get_open_orders_by_group_id(self, group_id: str) -> List[DCAOrder]:
        result = await self.session.execute(
            select(self.model).where(
                self.model.group_id == group_id,
                self.model.status.in_([OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value])
            )
        )
        return result.scalars().all()

    async def get_all_orders_by_group_id(self, group_id: str) -> List[DCAOrder]:
        result = await self.session.execute(
            select(self.model).where(
                self.model.group_id == group_id
            )
        )
        return result.scalars().all()

    async def get_all_open_orders_for_all_users(self, user_ids: List[str]) -> dict[str, List[DCAOrder]]:
        """
        Batch fetch all open/partially filled orders for multiple users in a single query.
        Returns a dictionary mapping user_id to list of orders.

        This prevents N+1 query issues when checking orders for multiple users.

        Also includes FILLED orders that:
        - Have a TP order placed (tp_order_id IS NOT NULL) but not hit yet
        - Need a TP order to be placed (tp_order_id IS NULL, per_leg/hybrid mode)
        """
        if not user_ids:
            return {}

        result = await self.session.execute(
            select(self.model)
            .options(
                joinedload(self.model.group),
                joinedload(self.model.pyramid)  # Eager load pyramid to avoid N+1 queries
            )
            .join(PositionGroup, self.model.group_id == PositionGroup.id)
            .where(
                or_(
                    # Open/pending orders that need status checking
                    self.model.status.in_([OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value, OrderStatus.TRIGGER_PENDING.value]),
                    # Filled ENTRY orders with TP placed, waiting for TP to hit
                    # Exclude leg_index=999 which are TP fill records, not entry orders
                    and_(
                        self.model.status == OrderStatus.FILLED.value,
                        self.model.tp_order_id.isnot(None),
                        self.model.tp_hit == False,
                        self.model.leg_index != 999  # Exclude TP fill records
                    ),
                    # Filled ENTRY orders that need TP orders placed (per_leg/hybrid modes)
                    # Exclude leg_index=999 which are TP fill records, not entry orders
                    and_(
                        self.model.status == OrderStatus.FILLED.value,
                        self.model.tp_order_id.is_(None),
                        self.model.tp_hit == False,
                        self.model.leg_index != 999,  # Exclude TP fill records
                        PositionGroup.tp_mode.in_(["per_leg", "hybrid"]),
                        PositionGroup.status.in_(["active", "partially_filled"])  # Include positions with pending DCA orders
                    )
                ),
                PositionGroup.user_id.in_(user_ids)
            )
        )
        orders = result.scalars().all()

        # Group orders by user_id
        orders_by_user: dict[str, List[DCAOrder]] = {}
        for order in orders:
            if order.group:
                uid = str(order.group.user_id)
                if uid not in orders_by_user:
                    orders_by_user[uid] = []
                orders_by_user[uid].append(order)

        return orders_by_user
