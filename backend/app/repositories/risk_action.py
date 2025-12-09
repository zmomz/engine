from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import RiskAction, PositionGroup
from app.repositories.base import BaseRepository


class RiskActionRepository(BaseRepository[RiskAction]):
    def __init__(self, session: AsyncSession):
        super().__init__(RiskAction, session)

    async def get_recent_by_user(self, user_id: str, limit: int = 10) -> List[RiskAction]:
        """Get recent risk actions for a user, ordered by timestamp descending."""
        result = await self.session.execute(
            select(self.model)
            .options(joinedload(self.model.loser_group))
            .join(PositionGroup, self.model.loser_group_id == PositionGroup.id)
            .where(PositionGroup.user_id == user_id)
            .order_by(self.model.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()
