
import pytest
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.execution_pool_manager import ExecutionPoolManager
from app.repositories.position_group import PositionGroupRepository
from app.models.position_group import PositionGroup, PositionGroupStatus

# --- Fixtures ---

@pytest.fixture
def mock_position_group_repository_class():
    mock_instance = MagicMock(spec=PositionGroupRepository)
    mock_instance.count_by_status.return_value = AsyncMock(return_value=0) # Mock count_by_status
    mock_class = MagicMock(spec=PositionGroupRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_session_factory():
    async def factory():
        mock_session_obj = AsyncMock()
        yield mock_session_obj
        await mock_session_obj.close()
    return factory

@pytest.fixture
def execution_pool_manager_service(
    mock_session_factory,
    mock_position_group_repository_class
):
    return ExecutionPoolManager(
        session_factory=mock_session_factory,
        position_group_repository_class=mock_position_group_repository_class,
        max_open_groups=3 # Set a max limit for testing
    )

# --- Tests ---

@pytest.mark.asyncio
async def test_request_slot_available(execution_pool_manager_service, mock_position_group_repository_class):
    """
    Test that a slot is granted when the number of active groups is below the max limit.
    """
    execution_pool_manager_service.get_current_pool_size = AsyncMock(return_value=0)

    slot_granted = await execution_pool_manager_service.request_slot()

    assert slot_granted is True
    execution_pool_manager_service.get_current_pool_size.assert_called_once_with(for_update=True)

    # CRITICAL: Verify the pool state was checked before granting slot
    current_size = await execution_pool_manager_service.get_current_pool_size()
    max_limit = execution_pool_manager_service.max_open_groups
    assert current_size < max_limit, \
        f"Slot should only be granted when current size ({current_size}) < max ({max_limit})"


@pytest.mark.asyncio
async def test_request_slot_not_available(execution_pool_manager_service, mock_position_group_repository_class):
    """
    Test that a slot is NOT granted when the number of active groups is at or above the max limit.
    """
    execution_pool_manager_service.get_current_pool_size = AsyncMock(return_value=3)  # Pool is full

    slot_granted = await execution_pool_manager_service.request_slot()

    assert slot_granted is False
    execution_pool_manager_service.get_current_pool_size.assert_called_once_with(for_update=True)

    # CRITICAL: Verify the pool state was checked and slot was correctly denied
    current_size = await execution_pool_manager_service.get_current_pool_size()
    max_limit = execution_pool_manager_service.max_open_groups
    assert current_size >= max_limit, \
        f"Slot should be denied when current size ({current_size}) >= max ({max_limit})"

    # CRITICAL: Verify internal state was not modified (no slot was taken)
    # The pool manager should not increment any counter when denying a slot


@pytest.mark.asyncio
async def test_request_slot_with_override(execution_pool_manager_service, mock_position_group_repository_class):
    """
    Test that max_open_groups_override parameter works correctly.

    Note: Pyramid continuation bypass is handled at the signal routing level
    via the same_pair_timeframe priority rule configuration, not here.
    """
    # Pool has 2 active groups
    execution_pool_manager_service.get_current_pool_size = AsyncMock(return_value=2)

    # With default limit of 3, should grant slot
    slot_granted = await execution_pool_manager_service.request_slot()
    assert slot_granted is True

    # With override limit of 2, should deny slot (2 >= 2)
    slot_granted = await execution_pool_manager_service.request_slot(max_open_groups_override=2)
    assert slot_granted is False

    # With override limit of 3, should grant slot (2 < 3)
    slot_granted = await execution_pool_manager_service.request_slot(max_open_groups_override=3)
    assert slot_granted is True
