"""
Service for managing the execution pool, limiting the number of active position groups.
"""
import asyncio
import logging
from typing import Optional, Callable # Added Callable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.repositories.position_group import PositionGroupRepository

logger = logging.getLogger(__name__)

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
            logger.info(f"ExecutionPoolManager: Counted {count} active groups with statuses {active_statuses}")
            return count

    async def request_slot(self, max_open_groups_override: Optional[int] = None) -> bool:
        """
        Requests a slot in the execution pool.
        Returns True if a slot is granted, False otherwise.

        Note: Pyramid continuation bypass is handled at the signal routing level
        via the `same_pair_timeframe` priority rule configuration, not here.
        When the rule is enabled, pyramids skip calling this method entirely.

        Args:
            max_open_groups_override: Optional override for max open groups limit
        """
        current_size = await self.get_current_pool_size(for_update=True)
        limit = max_open_groups_override if max_open_groups_override is not None else self.max_open_groups

        logger.info(f"ExecutionPoolManager: Requesting slot. Current: {current_size}, Max: {limit}")

        if current_size < limit:
            return True
        else:
            return False
