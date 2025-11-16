from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.models.dca_order import DCAOrder, OrderStatus
from app.repositories.base import BaseRepository


class DCAOrderRepository(BaseRepository[DCAOrder]):
    def __init__(self, session: AsyncSession):
        super().__init__(DCAOrder, session)

    async def get_open_and_partially_filled_orders(self) -> List[DCAOrder]:
        result = await self.session.execute(
            select(self.model).where(
                self.model.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
            )
        )
        return result.scalars().all()

    async def get_all_open_orders(self) -> List[DCAOrder]:
        result = await self.session.execute(
            select(self.model).where(self.model.status == OrderStatus.OPEN)
        )
        return result.scalars().all()
