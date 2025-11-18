
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import asyncio

from unittest.mock import AsyncMock, MagicMock, patch, ANY

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.queue_manager import QueueManagerService, calculate_queue_priority
from app.services.execution_pool_manager import ExecutionPoolManager
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.position_group import PositionGroup
from app.models.user import User # Import User model
from app.services.position_manager import PositionManagerService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig

# --- Fixtures for QueueManagerService ---

@pytest.fixture
async def user_id_fixture(db_session: AsyncMock):
    user = User(
        id=uuid.uuid4(),
        username="testuser_qm",
        email="test_qm@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id

@pytest.fixture
def mock_queued_signal_repository_class():
    mock_instance = MagicMock(spec=QueuedSignalRepository)
    mock_instance.create = AsyncMock()
    mock_instance.update = AsyncMock()
    mock_instance.delete = AsyncMock()
    mock_instance.get_by_id = AsyncMock(return_value=MagicMock(spec=QueuedSignal)) # Add this
    mock_instance.get_all_queued_signals = AsyncMock(return_value=[])
    mock_instance.get_by_symbol_timeframe_side = AsyncMock(return_value=None)
    mock_class = MagicMock(return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_position_group_repository_class():
    mock_instance = MagicMock(spec=PositionGroupRepository)
    mock_instance.get_active_position_groups = AsyncMock(return_value=[])
    mock_class = MagicMock(return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_exchange_connector():
    mock = AsyncMock(spec=ExchangeInterface)
    mock.get_current_price = AsyncMock(return_value=Decimal("50000")) # Default price
    return mock

@pytest.fixture
def mock_execution_pool_manager():
    mock = AsyncMock(spec=ExecutionPoolManager)
    mock.request_slot = AsyncMock(return_value=True) # Default to always granting slot
    return mock

@pytest.fixture
def mock_session_factory():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_session
    return MagicMock(return_value=mock_context_manager)

@pytest.fixture
def mock_position_manager_service():
    return AsyncMock(spec=PositionManagerService)

@pytest.fixture
def mock_risk_engine_config():
    return MagicMock(spec=RiskEngineConfig)

@pytest.fixture
def mock_dca_grid_config():
    return MagicMock(spec=DCAGridConfig)

@pytest.fixture
def queue_manager_service(
    mock_session_factory,
    mock_queued_signal_repository_class,
    mock_position_group_repository_class,
    mock_exchange_connector,
    mock_execution_pool_manager,
    mock_position_manager_service,
    mock_risk_engine_config,
    mock_dca_grid_config
):
    service = QueueManagerService(
        session_factory=mock_session_factory,
        queued_signal_repository_class=mock_queued_signal_repository_class,
        position_group_repository_class=mock_position_group_repository_class,
        exchange_connector=mock_exchange_connector,
        execution_pool_manager=mock_execution_pool_manager,
        position_manager_service=mock_position_manager_service,
        risk_engine_config=mock_risk_engine_config,
        dca_grid_config=mock_dca_grid_config,
        total_capital_usd=Decimal("10000"),
        polling_interval_seconds=0.01 # Fast polling for tests
    )
    # Stop the loop from running automatically in tests
    service._running = False
    return service

# --- Mock Models for calculate_queue_priority tests ---

class MockQueuedSignal:
    def __init__(self, queued_at, replacement_count=0, current_loss_percent=None, symbol="BTCUSDT", timeframe=15, side="long", entry_price=Decimal("50000")):
        self.id = uuid.uuid4()
        self.queued_at = queued_at
        self.replacement_count = replacement_count
        self.current_loss_percent = current_loss_percent
        self.symbol = symbol
        self.timeframe = timeframe
        self.side = side
        self.entry_price = entry_price
        self.is_pyramid_continuation = False # Default
        self.status = QueueStatus.QUEUED

class MockPositionGroup:
    def __init__(self, symbol="BTCUSDT", timeframe=15, side="long"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.side = side

# --- Tests for calculate_queue_priority (standalone function) ---

def test_priority_tier_4_fifo():
    """Test FIFO logic (oldest signal gets higher priority in its tier)."""
    now = datetime.utcnow()
    signal_1_older = MockQueuedSignal(queued_at=now - timedelta(seconds=100))
    signal_2_newer = MockQueuedSignal(queued_at=now - timedelta(seconds=10))
    
    priority_1 = calculate_queue_priority(signal_1_older, [])
    priority_2 = calculate_queue_priority(signal_2_newer, [])
    
    assert priority_1 > priority_2
    assert 1000 < priority_1 # Should be in Tier 4
    assert 1000 < priority_2

def test_priority_tier_3_replacement_count():
    """Test that higher replacement count wins over FIFO."""
    now = datetime.utcnow()
    signal_1_older_no_replace = MockQueuedSignal(queued_at=now - timedelta(seconds=100))
    signal_2_newer_with_replace = MockQueuedSignal(queued_at=now - timedelta(seconds=10), replacement_count=2)
    
    priority_1 = calculate_queue_priority(signal_1_older_no_replace, [])
    priority_2 = calculate_queue_priority(signal_2_newer_with_replace, [])
    
    assert priority_2 > priority_1
    assert priority_2 > 10000 # Tier 3
    assert priority_1 < 2000  # Tier 4

def test_priority_tier_2_loss_percentage():
    """Test that deeper loss percentage wins over replacement count and FIFO."""
    now = datetime.utcnow()
    signal_1_less_loss = MockQueuedSignal(
        queued_at=now - timedelta(seconds=10), 
        replacement_count=5, 
        current_loss_percent=Decimal("-2.5")
    )
    signal_2_deeper_loss = MockQueuedSignal(
        queued_at=now - timedelta(seconds=100), 
        replacement_count=1, 
        current_loss_percent=Decimal("-8.0")
    )
    
    priority_1 = calculate_queue_priority(signal_1_less_loss, [])
    priority_2 = calculate_queue_priority(signal_2_deeper_loss, [])
    
    assert priority_2 > priority_1
    assert priority_2 > 100000 # Tier 2
    assert priority_1 > 100000 # Tier 2, but lower score

def test_priority_tier_1_pyramid_continuation():
    """Test that pyramid continuation is the highest priority."""
    now = datetime.utcnow()
    active_group = MockPositionGroup(symbol="BTCUSDT", timeframe=15, side="long")
    
    signal_1_pyramid = MockQueuedSignal(
        queued_at=now - timedelta(seconds=10),
        symbol="BTCUSDT",
        timeframe=15,
        side="long"
    )
    signal_2_deepest_loss = MockQueuedSignal(
        queued_at=now - timedelta(seconds=1000),
        replacement_count=10,
        current_loss_percent=Decimal("-15.0"),
        symbol="ETHUSDT"
    )
    
    priority_1 = calculate_queue_priority(signal_1_pyramid, [active_group])
    priority_2 = calculate_queue_priority(signal_2_deepest_loss, [active_group])
    
    assert priority_1 > priority_2
    assert priority_1 > 1000000 # Tier 1

# --- Tests for QueueManagerService methods ---

@pytest.mark.asyncio
async def test_add_to_queue_new_signal(queue_manager_service, mock_queued_signal_repository_class, user_id_fixture):
    """
    Test adding a new signal to the queue.
    """
    signal_payload = {
        "user_id": str(user_id_fixture),
        "exchange": "binance",
        "symbol": "LTCUSDT",
        "timeframe": 60,
        "side": "long",
        "entry_price": "100.0",
        "signal_payload": {"key": "value"}
    }
    
    result = await queue_manager_service.add_to_queue(signal_payload)
    
    assert result is not None
    assert result.symbol == "LTCUSDT"
    assert result.status == "queued"
    mock_queued_signal_repository_class.return_value.create.assert_called_once()
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.assert_called_once_with("LTCUSDT", 60, "long")

@pytest.mark.asyncio
async def test_add_to_queue_replacement_signal(queue_manager_service, mock_queued_signal_repository_class, user_id_fixture):
    """
    Test adding a replacement signal to the queue (updates existing).
    """
    original_signal = QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="LTCUSDT",
        timeframe=60,
        side="long",
        entry_price=Decimal("90.0"),
        signal_payload={"original": "payload"},
        queued_at=datetime.utcnow() - timedelta(hours=1),
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.return_value = original_signal

    signal_payload = {
        "user_id": str(user_id_fixture),
        "exchange": "binance",
        "symbol": "LTCUSDT",
        "timeframe": 60,
        "side": "long",
        "entry_price": "105.0", # New entry price
        "signal_payload": {"new": "payload"}
    }
    
    result = await queue_manager_service.add_to_queue(signal_payload)
    
    assert result.id == original_signal.id
    assert result.entry_price == Decimal("105.0")
    assert result.replacement_count == 1
    assert result.signal_payload == signal_payload
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.assert_called_once_with("LTCUSDT", 60, "long")
    mock_queued_signal_repository_class.return_value.update.assert_called_once()

@pytest.mark.asyncio
async def test_remove_from_queue(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test removing a signal from the queue.
    """
    signal_id_to_remove = uuid.uuid4()
    await queue_manager_service.remove_from_queue(signal_id_to_remove)
    mock_queued_signal_repository_class.return_value.delete.assert_called_once_with(signal_id_to_remove)

@pytest.mark.asyncio
async def test_promote_from_queue_logic(queue_manager_service, mock_queued_signal_repository_class, mock_position_group_repository_class, mock_exchange_connector):
    """
    Test the logic of promote_from_queue to ensure it fetches prices,
    calculates priorities, and returns the highest priority signal.
    """
    now = datetime.utcnow()
    signal1 = QueuedSignal(id=uuid.uuid4(), symbol="BTCUSDT", queued_at=now - timedelta(seconds=100), entry_price=Decimal("50000"))
    signal2 = QueuedSignal(id=uuid.uuid4(), symbol="ETHUSDT", queued_at=now - timedelta(seconds=10), entry_price=Decimal("3000"))
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal1, signal2]
    
    async def price_side_effect(symbol):
        if symbol == "BTCUSDT":
            return Decimal("45000") # -10% loss
        if symbol == "ETHUSDT":
            return Decimal("2970") # -1% loss
        return Decimal("0")
    mock_exchange_connector.get_current_price.side_effect = price_side_effect

    mock_session = AsyncMock()
    promoted_signal = await queue_manager_service.promote_from_queue(
        mock_session,
        mock_queued_signal_repository_class.return_value,
        mock_position_group_repository_class.return_value
    )

    assert promoted_signal is not None
    assert promoted_signal.id == signal1.id # BTCUSDT has higher loss, so higher priority
    assert mock_exchange_connector.get_current_price.call_count == 2


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_no_signals(queue_manager_service, mock_queued_signal_repository_class, mock_execution_pool_manager):
    """
    Test promotion when no signals are in the queue.
    """
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = []
    
    mock_session = AsyncMock()
    await queue_manager_service._promote_highest_priority_signal(mock_session)
    
    mock_execution_pool_manager.request_slot.assert_not_called()

@pytest.mark.asyncio
async def test_promote_highest_priority_signal_slot_available(queue_manager_service, mock_queued_signal_repository_class, mock_position_group_repository_class, mock_exchange_connector, mock_execution_pool_manager, user_id_fixture):
    """
    Test promotion when a slot is available and a signal is promoted.
    """
    now = datetime.utcnow()
    signal_to_promote = QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000"),
        signal_payload={},
        queued_at=now - timedelta(seconds=100),
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal_to_promote]
    mock_execution_pool_manager.request_slot.return_value = True
    mock_exchange_connector.get_current_price.return_value = Decimal("49000") # Simulate loss

    mock_session = AsyncMock()
    await queue_manager_service._promote_highest_priority_signal(mock_session)

    mock_exchange_connector.get_current_price.assert_called_once_with("BTCUSDT")
    mock_queued_signal_repository_class.return_value.update.assert_called_with(
        signal_to_promote.id,
        {
            "status": "promoted",
            "promoted_at": ANY,
            "current_loss_percent": ANY,
        },
    )
    mock_execution_pool_manager.request_slot.assert_called_once_with(mock_session, is_pyramid_continuation=False)

@pytest.mark.asyncio
async def test_promote_highest_priority_signal_no_slot(queue_manager_service, mock_queued_signal_repository_class, mock_execution_pool_manager, user_id_fixture):
    """
    Test promotion when no slot is available.
    """
    now = datetime.utcnow()
    signal_in_queue = QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="ETHUSDT",
        timeframe=60,
        side="long",
        entry_price=Decimal("3000"),
        signal_payload={},
        queued_at=now - timedelta(seconds=50),
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal_in_queue]
    mock_execution_pool_manager.request_slot.return_value = False # No slot available
    
    mock_session = AsyncMock()
    await queue_manager_service._promote_highest_priority_signal(mock_session)

    queue_manager_service.exchange_connector.get_current_price.assert_called_once_with("ETHUSDT")
    mock_execution_pool_manager.request_slot.assert_called_once_with(mock_session, is_pyramid_continuation=False)
    # Assert that update was NOT called, as no slot was available
    mock_queued_signal_repository_class.return_value.update.assert_not_called()

@pytest.mark.asyncio
async def test_promote_highest_priority_signal_pyramid_continuation(queue_manager_service, mock_queued_signal_repository_class, mock_position_group_repository_class, mock_execution_pool_manager, user_id_fixture):
    """
    Test that a pyramid continuation signal bypasses the pool limit check.
    """
    now = datetime.utcnow()
    active_group = PositionGroup(symbol="SOLUSDT", timeframe=15, side="long", user_id=user_id_fixture, exchange="binance", total_dca_legs=5, base_entry_price=Decimal(100), weighted_avg_entry=Decimal(100), tp_mode="per_leg")
    signal_pyramid = QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="SOLUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("100"),
        signal_payload={},
        queued_at=now - timedelta(seconds=10),
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal_pyramid]
    mock_position_group_repository_class.return_value.get_active_position_groups.return_value = [active_group]
    mock_execution_pool_manager.request_slot.return_value = True # Should be granted for pyramid
    queue_manager_service.exchange_connector.get_current_price.return_value = Decimal("90") # Simulate loss

    mock_session = AsyncMock()
    await queue_manager_service._promote_highest_priority_signal(mock_session)

    queue_manager_service.exchange_connector.get_current_price.assert_called_once_with("SOLUSDT")
    mock_queued_signal_repository_class.return_value.update.assert_called_with(
        signal_pyramid.id,
        {
            "status": "promoted",
            "promoted_at": ANY,
            "current_loss_percent": ANY,
        },
    )
    mock_execution_pool_manager.request_slot.assert_called_once_with(mock_session, is_pyramid_continuation=True)

@pytest.mark.asyncio
async def test_start_and_stop_promotion_task(queue_manager_service):
    """
    Test starting and stopping the background promotion task.
    """
    await queue_manager_service.start_promotion_task()
    assert queue_manager_service._running is True
    assert queue_manager_service._promotion_task is not None
    assert not queue_manager_service._promotion_task.done() # Task should be running

    await queue_manager_service.stop_promotion_task()
    assert queue_manager_service._running is False
    await asyncio.sleep(0.05)
    assert queue_manager_service._promotion_task.done()

@pytest.mark.asyncio
async def test_promotion_loop_error_handling(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test that the promotion loop handles exceptions gracefully and continues running.
    """
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.side_effect = Exception("DB Error")

    await queue_manager_service.start_promotion_task()
    assert queue_manager_service._running is True

    await asyncio.sleep(queue_manager_service.polling_interval_seconds * 2)

    assert queue_manager_service._running is True
    assert not queue_manager_service._promotion_task.done()

    await queue_manager_service.stop_promotion_task()
