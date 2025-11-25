from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup
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
                self.model.status.in_([OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value]),
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
