from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.models import PositionGroup
from app.repositories.base import BaseRepository


class PositionGroupRepository(BaseRepository[PositionGroup]):
    def __init__(self, session: AsyncSession):
        super().__init__(PositionGroup, session)

    async def get_by_symbol(self, symbol: str) -> list[PositionGroup]:
        """
        Retrieves all position groups for a given symbol.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.symbol == symbol)
        )
        return result.scalars().all()

    async def get_active_position_groups(self, for_update: bool = False) -> list[PositionGroup]:
        """
        Retrieves all position groups with status 'active'.
        """
        return await self.get_by_status(["active"], for_update=for_update)

    async def get_active_position_groups_for_user(self, user_id: uuid.UUID, for_update: bool = False) -> list[PositionGroup]:
        """
        Retrieves all active position groups for a given user.
        """
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status.in_(["live", "partially_filled", "active", "closing"])
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all_active_by_user(self, user_id: uuid.UUID) -> list[PositionGroup]:
        """
        Retrieves all active position groups for a given user.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.user_id == user_id, self.model.status == "active")
        )
        return result.scalars().all()

    async def get_by_user_and_id(self, user_id: uuid.UUID, group_id: uuid.UUID) -> PositionGroup | None:
        """
        Retrieves a specific position group for a given user and group ID.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.user_id == user_id, self.model.id == group_id)
        )
        return result.scalars().first()
