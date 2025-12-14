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

    async def get_by_symbol_timeframe_side(self, symbol: str, timeframe: int, side: str, exchange: str) -> QueuedSignal | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.symbol == symbol,
                self.model.timeframe == timeframe,
                self.model.side == side,
                self.model.exchange == exchange,
                self.model.status == QueueStatus.QUEUED.value
            )
        )
        return result.scalars().first()

    async def get_all_queued_signals_for_user(self, user_id: str, for_update: bool = False) -> List[QueuedSignal]:
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status == QueueStatus.QUEUED.value
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all_queued_signals(self, for_update: bool = False) -> List[QueuedSignal]:
        query = select(self.model).where(self.model.status == QueueStatus.QUEUED.value)
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_history_for_user(self, user_id: str, limit: int = 50) -> List[QueuedSignal]:
        result = await self.session.execute(
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.status != QueueStatus.QUEUED.value
            )
            .order_by(self.model.promoted_at.desc(), self.model.queued_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_history(self, limit: int = 50) -> List[QueuedSignal]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.status != QueueStatus.QUEUED.value)
            .order_by(self.model.promoted_at.desc(), self.model.queued_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_queued_signals_for_symbol(
        self,
        user_id: str,
        symbol: str,
        exchange: str,
        timeframe: int = None,
        side: str = None
    ) -> List[QueuedSignal]:
        """
        Get all queued signals for a specific symbol.
        Optionally filter by timeframe and/or side.
        """
        conditions = [
            self.model.user_id == user_id,
            self.model.symbol == symbol,
            self.model.exchange == exchange,
            self.model.status == QueueStatus.QUEUED.value
        ]
        if timeframe is not None:
            conditions.append(self.model.timeframe == timeframe)
        if side is not None:
            conditions.append(self.model.side == side)

        result = await self.session.execute(
            select(self.model).where(*conditions)
        )
        return result.scalars().all()

    async def cancel_queued_signals_for_symbol(
        self,
        user_id: str,
        symbol: str,
        exchange: str,
        timeframe: int = None,
        side: str = None
    ) -> int:
        """
        Cancel (delete) all queued signals for a specific symbol.
        Returns the number of signals cancelled.

        Used when an exit signal arrives to clean up any pending entries
        for the same symbol/timeframe.
        """
        signals = await self.get_queued_signals_for_symbol(
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            side=side
        )

        count = 0
        for signal in signals:
            await self.delete(signal.id)
            count += 1

        return count
