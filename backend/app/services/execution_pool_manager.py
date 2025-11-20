"""
Service for managing the execution pool, limiting the number of active position groups.
"""
import asyncio
from typing import Optional, Callable # Added Callable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.repositories.position_group import PositionGroupRepository

class ExecutionPoolManager:
    def __init__(
        self,
        session_factory: Callable[..., AsyncSession], # Changed to session_factory
        position_group_repository_class: type[PositionGroupRepository],
        max_open_groups: int = 10
    ):
        self.session_factory = session_factory # Stored session_factory
        self.position_group_repository_class = position_group_repository_class
        self.max_open_groups = max_open_groups
        # self.repo will be instantiated per session in methods


    async def get_current_pool_size(self, for_update: bool = False) -> int:
        """
        Returns the current number of active position groups in the pool.
        """
        async with self.session_factory() as session:
            repo = self.position_group_repository_class(session)
            active_statuses = [PositionGroupStatus.LIVE.value, PositionGroupStatus.PARTIALLY_FILLED.value, PositionGroupStatus.ACTIVE.value, PositionGroupStatus.CLOSING.value]
            # Always call with for_update=False for aggregate functions like count
            count = await repo.count_by_status(active_statuses, for_update=False)
            return count

    async def request_slot(self, is_pyramid_continuation: bool = False) -> bool:
        """
        Requests a slot in the execution pool within a given session.
        Pyramid continuations bypass the max position limit.
        Returns True if a slot is granted, False otherwise.
        """
        if is_pyramid_continuation:
            return True

        current_size = await self.get_current_pool_size(for_update=True)
        if current_size < self.max_open_groups:
            return True
        else:
            return False
