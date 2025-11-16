from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.models import QueuedSignal
from app.models.queued_signal import QueueStatus
from app.repositories.base import BaseRepository


class QueuedSignalRepository(BaseRepository[QueuedSignal]):
    def __init__(self, session: AsyncSession):
        super().__init__(QueuedSignal, session)

    async def get_by_id(self, model_id: str) -> QueuedSignal | None:
        return await self.get(model_id)

    async def get_by_symbol_timeframe_side(self, symbol: str, timeframe: int, side: str) -> QueuedSignal | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.symbol == symbol,
                self.model.timeframe == timeframe,
                self.model.side == side,
                self.model.status == QueueStatus.QUEUED
            )
        )
        return result.scalars().first()

    async def get_all_queued_signals(self, for_update: bool = False) -> List[QueuedSignal]:
        query = select(self.model).where(self.model.status == QueueStatus.QUEUED)
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()
