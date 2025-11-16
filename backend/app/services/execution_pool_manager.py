"""
Service for managing the execution pool, limiting the number of active position groups.
"""
import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.repositories.position_group import PositionGroupRepository

class ExecutionPoolManager:
    def __init__(
        self,
        session_factory: callable,
        position_group_repository_class: type[PositionGroupRepository],
        max_open_groups: int = 10
    ):
        self.session_factory = session_factory
        self.position_group_repository_class = position_group_repository_class
        self.max_open_groups = max_open_groups

    async def get_current_pool_size(self, session: AsyncSession, for_update: bool = False) -> int:
        """
        Returns the current number of active position groups in the pool.
        """
        repo = self.position_group_repository_class(session)
        active_statuses = [PositionGroupStatus.LIVE, PositionGroupStatus.PARTIALLY_FILLED, PositionGroupStatus.ACTIVE, PositionGroupStatus.CLOSING]
        count = await repo.count_by_status(active_statuses, for_update=for_update)
        return count

    async def request_slot(self, session: AsyncSession, is_pyramid_continuation: bool = False) -> bool:
        """
        Requests a slot in the execution pool within a given session.
        Pyramid continuations bypass the max position limit.
        Returns True if a slot is granted, False otherwise.
        """
        if is_pyramid_continuation:
            return True

        current_size = await self.get_current_pool_size(session, for_update=True)
        if current_size < self.max_open_groups:
            return True
        else:
            return False

    async def release_slot(self, position_group_id: str):
        """
        Marks a position group as closed, effectively releasing its slot in the pool.
        This method would typically be called when a position group transitions to a 'closed' state.
        """
        # This method is more of a conceptual placeholder for now.
        # The actual release happens when a PositionGroup's status changes to 'closed'.
        # The pool manager primarily *checks* for available slots.
        pass
