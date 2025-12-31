from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pyramid
from app.repositories.base import BaseRepository


class PyramidRepository(BaseRepository[Pyramid]):
    def __init__(self, session: AsyncSession):
        super().__init__(Pyramid, session)

    async def get_latest_pyramid_for_group(self, group_id: uuid.UUID) -> Optional[Pyramid]:
        """
        Get the most recently created pyramid for a position group.
        """
        stmt = (
            select(Pyramid)
            .where(Pyramid.group_id == group_id)
            .order_by(Pyramid.entry_timestamp.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
