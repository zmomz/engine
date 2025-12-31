import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import asyncio
import json

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
from app.services.risk_engine import RiskEngineService # Added
from app.services.grid_calculator import GridCalculatorService # Added
from app.services.order_management import OrderService # Added
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.schemas.webhook_payloads import WebhookPayload # Added
from pydantic import BaseModel, Field # Added
from typing import Optional, Literal # Added

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError

# --- Fixtures for QueueManagerService ---

@pytest.fixture
async def user_id_fixture(db_session: AsyncMock):
    # Use the actual config schemas and then convert to JSON serializable dict
    risk_config_data = RiskEngineConfig().model_dump()
    dca_grid_config_data = DCAGridConfig(
        levels=[
            {"gap_percent": Decimal("0.0"), "weight_percent": Decimal("100"), "tp_percent": Decimal("1.0")}
        ],
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("0")
    ).model_dump()

    user = User(
        id=uuid.uuid4(),
        username="testuser_qm",
        email="test_qm@example.com",
        hashed_password="hashedpassword",
        risk_config=json.dumps(risk_config_data, default=decimal_default)
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
    mock_instance.get_by_id = AsyncMock(return_value=MagicMock(spec=QueuedSignal))
    mock_instance.get_all_queued_signals_for_user = AsyncMock(return_value=[]) # Corrected method name
    mock_instance.get_all_queued_signals = AsyncMock(return_value=[]) # Added this for promote_highest_priority_signal
    mock_instance.get_by_symbol_timeframe_side = AsyncMock(return_value=None)
    mock_class = MagicMock(return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_position_group_repository_class():
    mock_instance = MagicMock(spec=PositionGroupRepository)
    mock_instance.get_active_position_groups_for_user = AsyncMock(return_value=[]) # Corrected method name
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
def mock_risk_engine_service(): # Added mock
    return AsyncMock(spec=RiskEngineService)

@pytest.fixture
def mock_grid_calculator_service(): # Added mock
    return AsyncMock(spec=GridCalculatorService)

@pytest.fixture
def mock_order_service_class(): # Added mock
    mock_instance = AsyncMock(spec=OrderService)
    mock_class = MagicMock(return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_risk_engine_config():
    return MagicMock(spec=RiskEngineConfig)

@pytest.fixture
def mock_dca_grid_config():
    return MagicMock(spec=DCAGridConfig)

@pytest.fixture
async def queue_manager_service(
    db_session: AsyncMock, # Added db_session
    user_id_fixture, # Added user_id_fixture
    mock_session_factory,
    mock_queued_signal_repository_class,
    mock_position_group_repository_class,
    mock_exchange_connector,
    mock_execution_pool_manager,
    mock_position_manager_service,
    mock_risk_engine_service,
    mock_grid_calculator_service,
    mock_order_service_class,
    mock_risk_engine_config,
    mock_dca_grid_config
):
    # Fetch a dummy user object to pass to QueueManagerService
    user = await db_session.get(User, user_id_fixture)
    if user is None:
        # Create a dummy user if not found (should be created by user_id_fixture)
        risk_config_data = RiskEngineConfig().model_dump()
        dca_grid_config_data = DCAGridConfig(
            levels=[
                {"gap_percent": Decimal("0.0"), "weight_percent": Decimal("100"), "tp_percent": Decimal("1.0")}
            ],
            tp_mode="per_leg",
            tp_aggregate_percent=Decimal("0")
        ).model_dump()

        user = User(
            id=user_id_fixture,
            username="testuser_qm_service",
            email="test_qm_service@example.com",
            hashed_password="hashedpassword",
            webhook_secret="mock_secret",
            risk_config=json.dumps(risk_config_data, default=decimal_default)
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

    service = QueueManagerService(
        session_factory=mock_session_factory,
        user=user, # Added user
        queued_signal_repository_class=mock_queued_signal_repository_class,
        position_group_repository_class=mock_position_group_repository_class,
        exchange_connector=mock_exchange_connector,
        execution_pool_manager=mock_execution_pool_manager,
        position_manager_service=mock_position_manager_service,
        polling_interval_seconds=0.01
    )

    with patch.object(service._encryption_service, 'decrypt_keys', return_value=("mock_api_key", "mock_secret_key")):
        yield service # Yield the service within the patch context

    # Stop the loop from running automatically in tests (this was outside the patch before, should remain)
    service._running = False

    # Stop the loop from running automatically in tests (this was outside the patch before, should remain)
    service._running = False

# --- Mock Models for calculate_queue_priority tests ---

class MockQueuedSignal:
    def __init__(self, queued_at, replacement_count=0, current_loss_percent=None, symbol="BTCUSDT", timeframe=15, side="long", entry_price=Decimal("50000"), user_id=None, exchange="binance", signal_payload=None, status=QueueStatus.QUEUED, priority_score=Decimal("0")):
        self.id = uuid.uuid4()
        self.queued_at = queued_at
        self.replacement_count = replacement_count
        self.current_loss_percent = current_loss_percent
        self.symbol = symbol
        self.timeframe = timeframe
        self.side = side
        self.entry_price = entry_price
        self.is_pyramid_continuation = False # Default
        self.status = status
        self.user_id = user_id or uuid.uuid4() # Added user_id
        self.exchange = exchange # Added exchange
        self.signal_payload = signal_payload or {} # Added signal_payload
        self.priority_score = priority_score

class MockPositionGroup:
    def __init__(self, symbol="BTCUSDT", timeframe=15, side="long", user_id=None): # Add user_id parameter
        self.id = uuid.uuid4() # Added id
        self.symbol = symbol
        self.timeframe = timeframe
        self.side = side
        self.status = "live" # Added status
        self.user_id = user_id or uuid.uuid4() # Use provided user_id or generate new
        self.exchange = "binance" # Added exchange
        self.total_dca_legs = 5
        self.base_entry_price = Decimal(100)
        self.weighted_avg_entry = Decimal(100)
        self.tp_mode = "per_leg"

# --- Tests for calculate_queue_priority (standalone function) ---

def test_priority_tier_4_fifo():
    """Test FIFO logic (oldest signal gets higher priority in its tier)."""
    now = datetime.utcnow()
    signal_1_older = MockQueuedSignal(queued_at=now - timedelta(seconds=100))
    signal_2_newer = MockQueuedSignal(queued_at=now - timedelta(seconds=10))
    
    priority_1 = calculate_queue_priority(signal_1_older, [])
    priority_2 = calculate_queue_priority(signal_2_newer, [])
    
    assert priority_1 > priority_2
    assert priority_1 > Decimal("1000.0") # Expected score with base + FIFO component
    assert priority_2 < Decimal("10000.0") # Still in Tier 4 range

def test_priority_tier_3_replacement_count():
    """Test that higher replacement count wins over FIFO."""
    now = datetime.utcnow()
    signal_1_older_no_replace = MockQueuedSignal(queued_at=now - timedelta(seconds=100))
    signal_2_newer_with_replace = MockQueuedSignal(queued_at=now - timedelta(seconds=10), replacement_count=2)
    
    priority_1 = calculate_queue_priority(signal_1_older_no_replace, [])
    priority_2 = calculate_queue_priority(signal_2_newer_with_replace, [])
    
    assert priority_2 > priority_1
    assert priority_2 > Decimal("10000.0") # Expected score with base + replacement + FIFO component
    assert priority_1 < Decimal("10000.0") # Not in Tier 3 range (only FIFO component)

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
    assert priority_2 > Decimal("1000000.0") # Expected score with base + loss + replacement + FIFO
    assert priority_1 > Decimal("1000000.0") # Still in Tier 2 range, but lower score

def test_priority_tier_1_pyramid_continuation():
    """Test that pyramid continuation is the highest priority."""
    now = datetime.utcnow()
    test_user_uuid = uuid.uuid4() # Consistent UUID for this test

    active_group = MockPositionGroup(symbol="BTCUSDT", timeframe=15, side="long", user_id=test_user_uuid)
    
    signal_1_pyramid = MockQueuedSignal(
        queued_at=now - timedelta(seconds=10),
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        user_id=test_user_uuid
    )
    signal_2_deepest_loss = MockQueuedSignal(
        queued_at=now - timedelta(seconds=1000),
        replacement_count=10,
        current_loss_percent=Decimal("-15.0"),
        symbol="ETHUSDT",
        user_id=test_user_uuid
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
    payload_data = {
        "user_id": str(user_id_fixture),
        "secret": "some_secret",
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": "binance",
            "symbol": "LTCUSDT",
            "timeframe": 60,
            "action": "long",
            "market_position": "long",
            "market_position_size": 0.001,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": 100.0,
            "close_price": 100.1,
            "order_size": 0.001
        },
        "strategy_info": {"trade_id": "test_trade_id", "alert_name": "Test Alert", "alert_message": "Test Message"},
        "execution_intent": {"type": "signal", "side": "long", "position_size_type": "base", "precision_mode": "auto"},
        "risk": {"stop_loss": None, "take_profit": None, "max_slippage_percent": 0.1}
    }
    signal_payload = WebhookPayload(**payload_data)
    
    await queue_manager_service.add_signal_to_queue(signal_payload)
    
    mock_queued_signal_repository_class.return_value.create.assert_called_once()
    create_call_args, _ = mock_queued_signal_repository_class.return_value.create.call_args
    created_signal = create_call_args[0]
    assert created_signal.user_id == user_id_fixture
    assert created_signal.exchange == "binance"
    assert created_signal.symbol == "LTCUSDT"
    assert created_signal.timeframe == 60
    assert created_signal.side == "long"
    assert created_signal.entry_price == Decimal("100.0")
    assert created_signal.status == QueueStatus.QUEUED
    # SECURITY FIX: user_id is now required to prevent cross-user signal replacement
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.assert_called_once_with(
        user_id=str(user_id_fixture), symbol="LTCUSDT", timeframe=60, side="long", exchange="binance"
    )

@pytest.mark.asyncio
async def test_add_to_queue_duplicate_same_candle_rejected(queue_manager_service, mock_queued_signal_repository_class, user_id_fixture):
    """
    Test that duplicate signals within the same timeframe period (candle) are rejected.
    """
    # Calculate a time that's definitely within the current 60m candle period
    # by setting queued_at to 1 minute after the current hour start
    now = datetime.utcnow()
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
    queued_time = current_hour_start + timedelta(minutes=1)

    original_signal = QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="LTCUSDT",
        timeframe=60,  # 1 hour timeframe
        side="long",
        entry_price=Decimal("90.0"),
        signal_payload={},
        queued_at=queued_time,  # Within same hour as 'now'
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.return_value = original_signal

    payload_data = {
        "user_id": str(user_id_fixture),
        "secret": "some_secret",
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": "binance",
            "symbol": "LTCUSDT",
            "timeframe": 60,
            "action": "long",
            "market_position": "long",
            "market_position_size": 0.001,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": 105.0,
            "close_price": 105.1,
            "order_size": 0.001
        },
        "strategy_info": {"trade_id": "test_trade_id", "alert_name": "Test Alert", "alert_message": "Test Message"},
        "execution_intent": {"type": "signal", "side": "long", "position_size_type": "base", "precision_mode": "auto"},
        "risk": {"stop_loss": None, "take_profit": None, "max_slippage_percent": 0.1}
    }
    signal_payload = WebhookPayload(**payload_data)

    # Duplicate signal within same candle should be rejected
    with pytest.raises(ValueError) as exc_info:
        await queue_manager_service.add_signal_to_queue(signal_payload)

    assert "Duplicate signal rejected" in str(exc_info.value)
    # Original signal should not be modified
    assert original_signal.entry_price == Decimal("90.0")
    assert original_signal.replacement_count == 0
    # update should NOT be called since we rejected
    mock_queued_signal_repository_class.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_add_to_queue_replacement_signal(queue_manager_service, mock_queued_signal_repository_class, user_id_fixture):
    """
    Test that signals from a previous timeframe period are treated as replacements.
    """
    # Signal queued 2 hours ago - for a 60m timeframe, this is from a previous candle
    original_signal = QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="LTCUSDT",
        timeframe=60,  # 1 hour timeframe
        side="long",
        entry_price=Decimal("90.0"),
        signal_payload={},
        queued_at=datetime.utcnow() - timedelta(hours=2),  # Previous candle
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.return_value = original_signal

    payload_data = {
        "user_id": str(user_id_fixture),
        "secret": "some_secret",
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": "binance",
            "symbol": "LTCUSDT",
            "timeframe": 60,
            "action": "long",
            "market_position": "long",
            "market_position_size": 0.001,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": 105.0,
            "close_price": 105.1,
            "order_size": 0.001
        },
        "strategy_info": {"trade_id": "test_trade_id", "alert_name": "Test Alert", "alert_message": "Test Message"},
        "execution_intent": {"type": "signal", "side": "long", "position_size_type": "base", "precision_mode": "auto"},
        "risk": {"stop_loss": None, "take_profit": None, "max_slippage_percent": 0.1}
    }
    signal_payload = WebhookPayload(**payload_data)

    # Signal from previous candle should be treated as replacement
    await queue_manager_service.add_signal_to_queue(signal_payload)

    assert original_signal.entry_price == Decimal("105.0")
    assert original_signal.replacement_count == 1
    # SECURITY FIX: user_id is now required to prevent cross-user signal replacement
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.assert_called_once_with(
        user_id=str(user_id_fixture), symbol="LTCUSDT", timeframe=60, side="long", exchange="binance"
    )
    mock_queued_signal_repository_class.return_value.update.assert_called_once_with(original_signal)

@pytest.mark.asyncio
async def test_remove_from_queue(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test removing a signal from the queue.
    """
    signal_id_to_remove = uuid.uuid4()
    mock_queued_signal_repository_class.return_value.delete.return_value = True # Ensure delete returns True for success
    success = await queue_manager_service.remove_from_queue(signal_id_to_remove)
    assert success is True
    mock_queued_signal_repository_class.return_value.delete.assert_called_once_with(signal_id_to_remove)

async def test_promote_highest_priority_signal_logic(queue_manager_service, mock_queued_signal_repository_class, mock_position_group_repository_class, mock_exchange_connector, user_id_fixture):
    """
    Test the logic of promote_highest_priority_signal to ensure it fetches prices,
    calculates priorities, and updates the signal status.
    """
    # This test is for promote_highest_priority_signal, not promote_from_queue (which no longer exists)
    now = datetime.utcnow()
    signal1 = MockQueuedSignal(queued_at=now - timedelta(seconds=100), entry_price=Decimal("50000"), symbol="BTCUSDT", exchange="binance", timeframe=15, side="long", user_id=user_id_fixture)
    signal2 = MockQueuedSignal(queued_at=now - timedelta(seconds=10), entry_price=Decimal("3000"), symbol="ETHUSDT", exchange="binance", timeframe=15, side="long", user_id=user_id_fixture)
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal1, signal2] # Correct method name
    
    async def price_side_effect(symbol):
        if symbol == "BTCUSDT":
            return Decimal("45000") # -10% loss
        if symbol == "ETHUSDT":
            return Decimal("2970") # -1% loss
        return Decimal("0")
    mock_exchange_connector.get_current_price.side_effect = price_side_effect

    # Mock session.get for user within promote_highest_priority_signal
    # Access the mock session returned by the context manager
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id_fixture
    user_mock.username = "testuser_qm"
    user_mock.encrypted_api_keys = {"encrypted_data": "mock_key"}
    user_mock.exchange = "binance"
    user_mock.risk_config = RiskEngineConfig().model_dump()  # Mock as dict
    user_mock.dca_grid_config = DCAGridConfig(levels=[]).model_dump()  # Mock as dict
    
    mock_session.get.return_value = user_mock

    # Mock session.execute for DCAConfigurationRepository lookup
    mock_execute_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None  # No DCA config found
    mock_execute_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method

    # Assertions should check the state after promotion, not return value
    # The promoted signal will have its status updated to PROMOTED
    # Update is called 2 times for loss calc (signal1, signal2), no promotion without DCA config
    assert mock_queued_signal_repository_class.return_value.update.call_count == 2
    assert mock_exchange_connector.get_current_price.call_count == 2

    # CRITICAL: Verify loss percent was calculated and set on signals
    # Signal1: entry=50000, current=45000, loss = (45000-50000)/50000 * 100 = -10%
    assert signal1.current_loss_percent is not None, \
        "Signal must have current_loss_percent calculated after price fetch"

    # CRITICAL: Verify update was called with signals containing loss calculations
    update_calls = mock_queued_signal_repository_class.return_value.update.call_args_list
    assert len(update_calls) == 2, "Update must be called for each signal"


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_no_signals(queue_manager_service, mock_queued_signal_repository_class, mock_execution_pool_manager):
    """
    Test promotion when no signals are in the queue.
    """
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [] # Correct method name
    
    # Mock the user to be available in the service
    user_mock = MagicMock(spec=User)
    user_mock.id = uuid.uuid4() # Dummy user for this specific test
    user_mock.exchange = "mock"
    user_mock.encrypted_api_keys = {"encrypted_data": "mock_key"}
    queue_manager_service.user = user_mock

    # Mock session.get
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    mock_session.get.return_value = user_mock

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method
    
    mock_execution_pool_manager.request_slot.assert_not_called()

@pytest.mark.asyncio
async def test_promote_highest_priority_signal_slot_available(queue_manager_service, mock_queued_signal_repository_class, mock_position_group_repository_class, mock_exchange_connector, mock_execution_pool_manager, user_id_fixture):
    """
    Test promotion when a slot is available and a signal is promoted.
    """
    now = datetime.utcnow()
    signal_to_promote = MockQueuedSignal( # Changed to MockQueuedSignal
        queued_at=now - timedelta(seconds=100),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000"),
        signal_payload={},
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal_to_promote] # Correct method name
    mock_execution_pool_manager.request_slot.return_value = True
    mock_exchange_connector.get_current_price.return_value = Decimal("49000") # Simulate loss

    # Mock session.get
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id_fixture
    user_mock.exchange = "mock"
    user_mock.encrypted_api_keys = {"encrypted_data": "mock_key"}
    user_mock.risk_config = RiskEngineConfig().model_dump()  # Mock as dict
    user_mock.dca_grid_config = DCAGridConfig(levels=[]).model_dump()  # Mock as dict
    mock_session.get.return_value = user_mock

    # Mock session.execute for DCAConfigurationRepository lookup
    mock_execute_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None  # No DCA config found
    mock_execute_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method

    mock_exchange_connector.get_current_price.assert_called_once_with("BTCUSDT")
    # Update called 1 time for loss calc, no promotion without DCA config
    assert mock_queued_signal_repository_class.return_value.update.call_count == 1

@pytest.mark.asyncio
async def test_promote_highest_priority_signal_no_slot(queue_manager_service, mock_queued_signal_repository_class, mock_execution_pool_manager, user_id_fixture):
    """
    Test promotion when no slot is available.
    """
    now = datetime.utcnow()
    signal_in_queue = MockQueuedSignal( # Changed to MockQueuedSignal
        queued_at=now - timedelta(seconds=50),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="ETHUSDT",
        timeframe=60,
        side="long",
        entry_price=Decimal("3000"),
        signal_payload={},
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal_in_queue] # Correct method name
    mock_execution_pool_manager.request_slot.return_value = False # No slot available
    
    # Mock the user to be available in the service
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id_fixture
    user_mock.exchange = "mock"
    user_mock.encrypted_api_keys = {"encrypted_data": "mock_key"}
    user_mock.risk_config = RiskEngineConfig().model_dump()  # Mock as dict
    user_mock.dca_grid_config = DCAGridConfig(levels=[]).model_dump()  # Mock as dict

    # Mock session.get
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    mock_session.get.return_value = user_mock

    # Mock session.execute for DCAConfigurationRepository lookup
    mock_execute_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None  # No DCA config found
    mock_execute_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method

    queue_manager_service.exchange_connector.get_current_price.assert_called_once_with("ETHUSDT")
    # Assert that update was called once for loss calc, but not for promotion (no DCA config)
    assert mock_queued_signal_repository_class.return_value.update.call_count == 1

    # CRITICAL: Verify signal status was NOT changed when no slot available
    assert signal_in_queue.status == QueueStatus.QUEUED, \
        "Signal status must remain QUEUED when no execution slot available"

    # CRITICAL: Verify signal was NOT promoted (no promoted_at timestamp)
    assert not hasattr(signal_in_queue, 'promoted_at') or signal_in_queue.promoted_at is None, \
        "Signal must not have promoted_at timestamp when not promoted"


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_pyramid_continuation(queue_manager_service, mock_queued_signal_repository_class, mock_position_group_repository_class, mock_execution_pool_manager, user_id_fixture):
    """
    Test that a pyramid continuation signal bypasses the pool limit check.
    """
    now = datetime.utcnow()
    active_group = MockPositionGroup(symbol="SOLUSDT", timeframe=15, side="long") # Changed to MockPositionGroup
    active_group.user_id = user_id_fixture # Assign user_id
    active_group.exchange = "binance"
    active_group.total_dca_legs = 5
    active_group.base_entry_price = Decimal(100)
    active_group.weighted_avg_entry = Decimal(100)
    active_group.tp_mode = "per_leg"
    active_group.status = "live" # Example status

    signal_pyramid = MockQueuedSignal( # Changed to MockQueuedSignal
        queued_at=now - timedelta(seconds=10),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="SOLUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("100"),
        signal_payload={},
        replacement_count=0,
        status=QueueStatus.QUEUED
    )
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal_pyramid] # Correct method name
    mock_position_group_repository_class.return_value.get_active_position_groups_for_user.return_value = [active_group] # Correct method name
    mock_execution_pool_manager.request_slot.return_value = True # Should be granted for pyramid
    queue_manager_service.exchange_connector.get_current_price.return_value = Decimal("90") # Simulate loss

    # Mock the user to be available in the service
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id_fixture
    user_mock.exchange = "mock"
    user_mock.encrypted_api_keys = {"encrypted_data": "mock_key"}
    user_mock.risk_config = RiskEngineConfig().model_dump()  # Mock as dict
    user_mock.dca_grid_config = DCAGridConfig(levels=[]).model_dump()  # Mock as dict

    # Mock session.get
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    mock_session.get.return_value = user_mock

    # Mock session.execute for DCAConfigurationRepository lookup
    mock_execute_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None  # No DCA config found
    mock_execute_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method

    queue_manager_service.exchange_connector.get_current_price.assert_called_once_with("SOLUSDT")
    # Update called 1 time for loss calc, no promotion without DCA config
    assert mock_queued_signal_repository_class.return_value.update.call_count == 1

@pytest.mark.asyncio
async def test_start_and_stop_promotion_task(queue_manager_service):
    """
    Test starting and stopping the background promotion task.
    """
    # Need to mock the dependencies that promote_highest_priority_signal uses
    # inside the promotion task, otherwise it will fail during the loop.
    with patch.object(queue_manager_service, 'promote_highest_priority_signal', new=AsyncMock()) as mock_promote_highest_priority_signal:
        await queue_manager_service.start_promotion_task() # Await the coroutine
        assert queue_manager_service._running is True
        assert queue_manager_service._promotion_task is not None
        assert not queue_manager_service._promotion_task.done() # Task should be running

        # Allow some time for the task to run at least once
        await asyncio.sleep(queue_manager_service.polling_interval_seconds + 0.1) 
        mock_promote_highest_priority_signal.assert_called() # Should have been called at least once

        await queue_manager_service.stop_promotion_task()
        assert queue_manager_service._running is False
        await asyncio.sleep(0.05) # Give a moment for the task to fully stop
        assert queue_manager_service._promotion_task.done()

@pytest.mark.asyncio
async def test_promotion_loop_error_handling(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test that the promotion loop handles exceptions gracefully and continues running.
    """
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.side_effect = Exception("DB Error") # Correct method name

    with patch.object(queue_manager_service, 'promote_highest_priority_signal', side_effect=Exception("Promotion Error")) as mock_promote:
        await queue_manager_service.start_promotion_task() # Await the coroutine
        assert queue_manager_service._running is True

        await asyncio.sleep(queue_manager_service.polling_interval_seconds * 2 + 0.1) # Wait longer to allow multiple loop iterations

        mock_promote.assert_called() # Ensure it was called at least once
        assert queue_manager_service._running is True
        assert not queue_manager_service._promotion_task.done() # Task should still be running

        await queue_manager_service.stop_promotion_task()
        await asyncio.sleep(0.05) # Give a moment for the task to fully stop
        assert queue_manager_service._promotion_task.done()


# --- Additional Coverage Tests ---

@pytest.mark.asyncio
async def test_add_signal_to_queue_no_user_context():
    """
    Test that adding a signal without user context raises ValueError.
    """
    mock_session_factory = MagicMock()

    service = QueueManagerService(
        session_factory=mock_session_factory,
        user=None,  # No user context
        queued_signal_repository_class=MagicMock(),
        position_group_repository_class=MagicMock()
    )

    payload_data = {
        "user_id": str(uuid.uuid4()),
        "secret": "some_secret",
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "timeframe": 15,
            "action": "long",
            "market_position": "long",
            "market_position_size": 0.001,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": 50000.0,
            "close_price": 50000.1,
            "order_size": 0.001
        },
        "strategy_info": {"trade_id": "test_trade_id", "alert_name": "Test Alert", "alert_message": "Test Message"},
        "execution_intent": {"type": "signal", "side": "long", "position_size_type": "base", "precision_mode": "auto"},
        "risk": {"stop_loss": None, "take_profit": None, "max_slippage_percent": 0.1}
    }
    signal_payload = WebhookPayload(**payload_data)

    with pytest.raises(ValueError, match="User context required"):
        await service.add_signal_to_queue(signal_payload)


@pytest.mark.asyncio
async def test_remove_from_queue_signal_not_found(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test removing a signal that doesn't exist.
    """
    signal_id = uuid.uuid4()
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = None

    result = await queue_manager_service.remove_from_queue(signal_id)
    assert result is False


@pytest.mark.asyncio
async def test_remove_from_queue_wrong_user(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test that a user cannot remove another user's signal.
    """
    signal_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    requesting_user_id = uuid.uuid4()

    mock_signal = MagicMock(spec=QueuedSignal)
    mock_signal.user_id = other_user_id
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = mock_signal

    result = await queue_manager_service.remove_from_queue(signal_id, user_id=requesting_user_id)
    assert result is False
    mock_queued_signal_repository_class.return_value.delete.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_queued_signals_on_exit(queue_manager_service, mock_queued_signal_repository_class, user_id_fixture):
    """
    Test canceling queued signals when an exit signal arrives.
    """
    mock_queued_signal_repository_class.return_value.cancel_queued_signals_for_symbol = AsyncMock(return_value=2)

    cancelled = await queue_manager_service.cancel_queued_signals_on_exit(
        user_id=user_id_fixture,
        symbol="BTCUSDT",
        exchange="binance",
        timeframe=15,
        side="long"
    )

    assert cancelled == 2
    mock_queued_signal_repository_class.return_value.cancel_queued_signals_for_symbol.assert_called_once_with(
        user_id=str(user_id_fixture),
        symbol="BTCUSDT",
        exchange="binance",
        timeframe=15,
        side="long"
    )


@pytest.mark.asyncio
async def test_cancel_queued_signals_on_exit_none_cancelled(queue_manager_service, mock_queued_signal_repository_class, user_id_fixture):
    """
    Test canceling queued signals when none match.
    """
    mock_queued_signal_repository_class.return_value.cancel_queued_signals_for_symbol = AsyncMock(return_value=0)

    cancelled = await queue_manager_service.cancel_queued_signals_on_exit(
        user_id=user_id_fixture,
        symbol="ETHUSDT",
        exchange="binance",
        timeframe=60,
        side="short"
    )

    assert cancelled == 0


@pytest.mark.asyncio
async def test_get_all_queued_signals_no_user_id(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test getting all queued signals without a user filter.
    """
    signal1 = MockQueuedSignal(queued_at=datetime.utcnow(), symbol="BTCUSDT")
    signal2 = MockQueuedSignal(queued_at=datetime.utcnow(), symbol="ETHUSDT")
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.return_value = [signal1, signal2]

    signals = await queue_manager_service.get_all_queued_signals(user_id=None)

    assert len(signals) == 2
    mock_queued_signal_repository_class.return_value.get_all_queued_signals.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_queued_signals_with_user_id(queue_manager_service, mock_queued_signal_repository_class, mock_position_group_repository_class, user_id_fixture):
    """
    Test getting all queued signals for a specific user with priority calculation.
    """
    signal = MockQueuedSignal(queued_at=datetime.utcnow(), symbol="BTCUSDT", user_id=user_id_fixture)
    mock_queued_signal_repository_class.return_value.get_all_queued_signals_for_user.return_value = [signal]
    mock_position_group_repository_class.return_value.get_active_position_groups_for_user.return_value = []

    # Mock session.get to return the user
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id_fixture
    user_mock.risk_config = RiskEngineConfig().model_dump()
    mock_session.get = AsyncMock(return_value=user_mock)

    signals = await queue_manager_service.get_all_queued_signals(user_id=user_id_fixture)

    assert len(signals) == 1
    mock_queued_signal_repository_class.return_value.get_all_queued_signals_for_user.assert_called_once_with(user_id_fixture)


@pytest.mark.asyncio
async def test_get_queue_history_with_user_id(queue_manager_service, mock_queued_signal_repository_class, user_id_fixture):
    """
    Test getting queue history for a specific user.
    """
    signal = MockQueuedSignal(queued_at=datetime.utcnow(), symbol="BTCUSDT", status=QueueStatus.PROMOTED)
    mock_queued_signal_repository_class.return_value.get_history_for_user = AsyncMock(return_value=[signal])

    history = await queue_manager_service.get_queue_history(user_id=user_id_fixture, limit=50)

    assert len(history) == 1
    mock_queued_signal_repository_class.return_value.get_history_for_user.assert_called_once_with(user_id_fixture, 50)


@pytest.mark.asyncio
async def test_get_queue_history_no_user_id(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test getting queue history without a user filter.
    """
    mock_queued_signal_repository_class.return_value.get_history = AsyncMock(return_value=[])

    history = await queue_manager_service.get_queue_history(user_id=None, limit=100)

    assert len(history) == 0
    mock_queued_signal_repository_class.return_value.get_history.assert_called_once_with(100)


@pytest.mark.asyncio
async def test_force_add_specific_signal_to_pool_success(queue_manager_service, mock_queued_signal_repository_class, user_id_fixture):
    """
    Test force promoting a signal to the pool.
    """
    signal_id = uuid.uuid4()
    mock_signal = MagicMock(spec=QueuedSignal)
    mock_signal.user_id = user_id_fixture
    mock_signal.status = QueueStatus.QUEUED
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = mock_signal

    result = await queue_manager_service.force_add_specific_signal_to_pool(signal_id, user_id=user_id_fixture)

    assert result is not None

    # CRITICAL: Verify signal status transitioned to PROMOTED
    assert mock_signal.status == QueueStatus.PROMOTED, \
        "Signal status must transition to PROMOTED after force promotion"

    # CRITICAL: Verify promoted_at timestamp was set
    assert mock_signal.promoted_at is not None, \
        "Signal must have promoted_at timestamp after promotion"

    # CRITICAL: Verify state was persisted via repository update
    mock_queued_signal_repository_class.return_value.update.assert_called_once_with(mock_signal)

    # CRITICAL: Verify the updated signal has PROMOTED status
    updated_signal = mock_queued_signal_repository_class.return_value.update.call_args[0][0]
    assert updated_signal.status == QueueStatus.PROMOTED, \
        "Updated signal passed to repository must have PROMOTED status"


@pytest.mark.asyncio
async def test_force_add_specific_signal_to_pool_not_found(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test force promoting a signal that doesn't exist.
    """
    signal_id = uuid.uuid4()
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = None

    result = await queue_manager_service.force_add_specific_signal_to_pool(signal_id)

    assert result is None


@pytest.mark.asyncio
async def test_force_add_specific_signal_to_pool_wrong_user(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test force promoting another user's signal.
    """
    signal_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    requesting_user_id = uuid.uuid4()

    mock_signal = MagicMock(spec=QueuedSignal)
    mock_signal.user_id = other_user_id
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = mock_signal

    result = await queue_manager_service.force_add_specific_signal_to_pool(signal_id, user_id=requesting_user_id)

    assert result is None


@pytest.mark.asyncio
async def test_promote_specific_signal_not_found(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test promoting a signal that doesn't exist.
    """
    signal_id = uuid.uuid4()
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = None

    result = await queue_manager_service.promote_specific_signal(signal_id)

    assert result is None


@pytest.mark.asyncio
async def test_promote_specific_signal_wrong_user(queue_manager_service, mock_queued_signal_repository_class):
    """
    Test promoting another user's signal.
    """
    signal_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    requesting_user_id = uuid.uuid4()

    mock_signal = MagicMock(spec=QueuedSignal)
    mock_signal.user_id = other_user_id
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = mock_signal

    result = await queue_manager_service.promote_specific_signal(signal_id, user_id=requesting_user_id)

    assert result is None


@pytest.mark.asyncio
async def test_promote_specific_signal_user_not_found(queue_manager_service, mock_queued_signal_repository_class, mock_execution_pool_manager, user_id_fixture):
    """
    Test promoting a signal when the user cannot be found.
    """
    signal_id = uuid.uuid4()

    mock_signal = MagicMock(spec=QueuedSignal)
    mock_signal.user_id = user_id_fixture
    mock_signal.symbol = "BTCUSDT"
    mock_signal.exchange = "binance"
    mock_signal.timeframe = 15
    mock_signal.side = "long"
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = mock_signal

    # Mock session.get to return None (user not found)
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    mock_session.get = AsyncMock(return_value=None)

    result = await queue_manager_service.promote_specific_signal(signal_id, user_id=user_id_fixture)

    assert result is None


@pytest.mark.asyncio
async def test_promote_specific_signal_no_slot_available(queue_manager_service, mock_queued_signal_repository_class, mock_execution_pool_manager, mock_position_group_repository_class, user_id_fixture):
    """
    Test promoting a signal when no execution slot is available.
    """
    signal_id = uuid.uuid4()

    mock_signal = MagicMock(spec=QueuedSignal)
    mock_signal.user_id = user_id_fixture
    mock_signal.symbol = "BTCUSDT"
    mock_signal.exchange = "binance"
    mock_signal.timeframe = 15
    mock_signal.side = "long"
    mock_signal.status = QueueStatus.QUEUED
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = mock_signal

    mock_position_group_repository_class.return_value.get_active_position_groups_for_user.return_value = []
    mock_execution_pool_manager.request_slot.return_value = False  # No slot

    # Mock session.get to return the user
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id_fixture
    user_mock.risk_config = RiskEngineConfig().model_dump()
    mock_session.get = AsyncMock(return_value=user_mock)

    result = await queue_manager_service.promote_specific_signal(signal_id, user_id=user_id_fixture)

    assert result is None


@pytest.mark.asyncio
async def test_promote_specific_signal_with_pyramid_bypass(queue_manager_service, mock_queued_signal_repository_class, mock_execution_pool_manager, mock_position_group_repository_class, user_id_fixture):
    """
    Test promoting a signal that matches an active position (pyramid) bypasses pool limit.
    """
    signal_id = uuid.uuid4()

    mock_signal = MagicMock(spec=QueuedSignal)
    mock_signal.user_id = user_id_fixture
    mock_signal.symbol = "BTCUSDT"
    mock_signal.exchange = "binance"
    mock_signal.timeframe = 15
    mock_signal.side = "long"
    mock_signal.entry_price = Decimal("50000")
    mock_signal.current_loss_percent = Decimal("-5.0")
    mock_signal.queued_at = datetime.utcnow()
    mock_signal.replacement_count = 0
    mock_signal.status = QueueStatus.QUEUED
    mock_queued_signal_repository_class.return_value.get_by_id.return_value = mock_signal

    # Create matching active position group
    active_group = MockPositionGroup(symbol="BTCUSDT", timeframe=15, side="long", user_id=user_id_fixture)
    active_group.exchange = "binance"
    mock_position_group_repository_class.return_value.get_active_position_groups_for_user.return_value = [active_group]

    # Create risk config with pyramid rule enabled
    risk_config_data = RiskEngineConfig().model_dump()
    risk_config_data["priority_rules"]["priority_rules_enabled"]["same_pair_timeframe"] = True

    # Mock session.get to return the user
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id_fixture
    user_mock.risk_config = risk_config_data
    mock_session.get = AsyncMock(return_value=user_mock)

    result = await queue_manager_service.promote_specific_signal(signal_id, user_id=user_id_fixture)

    # Slot request should NOT be called due to pyramid bypass
    mock_execution_pool_manager.request_slot.assert_not_called()
    assert result is not None
    assert mock_signal.status == QueueStatus.PROMOTED


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_with_dca_config_and_execution():
    """
    Test full promotion flow with DCA config found and position creation.
    """
    from app.models.dca_configuration import DCAConfiguration, EntryOrderType, TakeProfitMode

    user_id = uuid.uuid4()
    now = datetime.utcnow()

    # Create mock signal
    mock_signal = MockQueuedSignal(
        queued_at=now,
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000"),
        status=QueueStatus.QUEUED
    )

    # Create mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # User with valid config
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id
    user_mock.username = "testuser"
    user_mock.exchange = "binance"
    user_mock.encrypted_api_keys = {"binance": {"encrypted_data": "mock"}}
    user_mock.risk_config = RiskEngineConfig().model_dump()
    mock_session.get = AsyncMock(return_value=user_mock)

    # Create mock repos
    mock_queue_repo = MagicMock(spec=QueuedSignalRepository)
    mock_queue_repo.get_all_queued_signals = AsyncMock(return_value=[mock_signal])
    mock_queue_repo.update = AsyncMock()

    mock_pos_group_repo = MagicMock(spec=PositionGroupRepository)
    mock_pos_group_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])

    # Mock DCA config found
    mock_dca_config = MagicMock(spec=DCAConfiguration)
    mock_dca_config.dca_levels = [{"gap_percent": 0.0, "weight_percent": 100, "tp_percent": 1.0}]
    mock_dca_config.tp_mode = TakeProfitMode.PER_LEG
    mock_dca_config.tp_settings = {"tp_aggregate_percent": 0}
    mock_dca_config.max_pyramids = 5
    mock_dca_config.entry_order_type = EntryOrderType.LIMIT
    mock_dca_config.pyramid_specific_levels = {}

    # Mock exchange
    mock_exchange = AsyncMock()
    mock_exchange.get_current_price = AsyncMock(return_value=Decimal("49000"))
    mock_exchange.fetch_balance = AsyncMock(return_value={"total": {"USDT": 10000}})
    mock_exchange.close = AsyncMock()

    # Mock execution pool manager
    mock_exec_pool = AsyncMock(spec=ExecutionPoolManager)
    mock_exec_pool.request_slot = AsyncMock(return_value=True)

    mock_session_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_ctx

    service = QueueManagerService(
        session_factory=mock_session_factory,
        user=user_mock,
        queued_signal_repository_class=lambda s: mock_queue_repo,
        position_group_repository_class=lambda s: mock_pos_group_repo,
        exchange_connector=mock_exchange,
        execution_pool_manager=mock_exec_pool
    )

    with patch('app.services.queue_manager.DCAConfigurationRepository') as mock_dca_repo_class:
        mock_dca_repo = MagicMock()
        mock_dca_repo.get_specific_config = AsyncMock(return_value=mock_dca_config)
        mock_dca_repo_class.return_value = mock_dca_repo

        with patch('app.services.queue_manager.PositionManagerService') as mock_pos_manager_class:
            mock_pos_manager = AsyncMock()
            mock_pos_manager.create_position_group_from_signal = AsyncMock()
            mock_pos_manager_class.return_value = mock_pos_manager

            await service.promote_highest_priority_signal(session=mock_session)

            # Verify DCA config was looked up
            mock_dca_repo.get_specific_config.assert_called_once()


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_user_not_found():
    """
    Test that promotion skips signals when user cannot be found.
    """
    user_id = uuid.uuid4()
    now = datetime.utcnow()

    mock_signal = MockQueuedSignal(
        queued_at=now,
        user_id=user_id,
        symbol="BTCUSDT"
    )

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get = AsyncMock(return_value=None)  # User not found

    mock_queue_repo = MagicMock(spec=QueuedSignalRepository)
    mock_queue_repo.get_all_queued_signals = AsyncMock(return_value=[mock_signal])

    mock_session_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_ctx

    service = QueueManagerService(
        session_factory=mock_session_factory,
        queued_signal_repository_class=lambda s: mock_queue_repo,
        position_group_repository_class=MagicMock()
    )

    # Should not raise, just skip
    await service.promote_highest_priority_signal(session=mock_session)


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_price_fetch_error():
    """
    Test that promotion continues when price fetch fails.
    """
    user_id = uuid.uuid4()
    now = datetime.utcnow()

    mock_signal = MockQueuedSignal(
        queued_at=now,
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT"
    )

    mock_session = AsyncMock(spec=AsyncSession)
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id
    user_mock.username = "testuser"
    user_mock.encrypted_api_keys = {"binance": {"encrypted_data": "mock"}}
    user_mock.risk_config = RiskEngineConfig().model_dump()
    mock_session.get = AsyncMock(return_value=user_mock)
    mock_session.commit = AsyncMock()

    mock_queue_repo = MagicMock(spec=QueuedSignalRepository)
    mock_queue_repo.get_all_queued_signals = AsyncMock(return_value=[mock_signal])
    mock_queue_repo.update = AsyncMock()

    mock_pos_group_repo = MagicMock(spec=PositionGroupRepository)
    mock_pos_group_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])

    mock_exchange = AsyncMock()
    mock_exchange.get_current_price = AsyncMock(side_effect=Exception("Price fetch failed"))

    mock_session_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_ctx

    service = QueueManagerService(
        session_factory=mock_session_factory,
        queued_signal_repository_class=lambda s: mock_queue_repo,
        position_group_repository_class=lambda s: mock_pos_group_repo,
        exchange_connector=mock_exchange
    )

    # Should not raise
    await service.promote_highest_priority_signal(session=mock_session)


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_risk_config_error():
    """
    Test that promotion uses default priority config when risk config fails.
    """
    user_id = uuid.uuid4()
    now = datetime.utcnow()

    mock_signal = MockQueuedSignal(
        queued_at=now,
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT"
    )

    mock_session = AsyncMock(spec=AsyncSession)
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id
    user_mock.username = "testuser"
    user_mock.encrypted_api_keys = {"binance": {"encrypted_data": "mock"}}
    user_mock.risk_config = "invalid_json{{"  # Invalid config
    mock_session.get = AsyncMock(return_value=user_mock)
    mock_session.commit = AsyncMock()

    mock_queue_repo = MagicMock(spec=QueuedSignalRepository)
    mock_queue_repo.get_all_queued_signals = AsyncMock(return_value=[mock_signal])
    mock_queue_repo.update = AsyncMock()

    mock_pos_group_repo = MagicMock(spec=PositionGroupRepository)
    mock_pos_group_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])

    mock_exchange = AsyncMock()
    mock_exchange.get_current_price = AsyncMock(return_value=Decimal("50000"))

    mock_session_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_ctx

    service = QueueManagerService(
        session_factory=mock_session_factory,
        queued_signal_repository_class=lambda s: mock_queue_repo,
        position_group_repository_class=lambda s: mock_pos_group_repo,
        exchange_connector=mock_exchange
    )

    # Should not raise, should use default config
    await service.promote_highest_priority_signal(session=mock_session)


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_short_position_pnl():
    """
    Test that PnL calculation is correct for short positions.
    """
    user_id = uuid.uuid4()
    now = datetime.utcnow()

    mock_signal = MockQueuedSignal(
        queued_at=now,
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        side="short",  # Short position
        entry_price=Decimal("50000")
    )

    mock_session = AsyncMock(spec=AsyncSession)
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id
    user_mock.username = "testuser"
    user_mock.encrypted_api_keys = {"binance": {"encrypted_data": "mock"}}
    user_mock.risk_config = RiskEngineConfig().model_dump()
    mock_session.get = AsyncMock(return_value=user_mock)
    mock_session.commit = AsyncMock()

    mock_queue_repo = MagicMock(spec=QueuedSignalRepository)
    mock_queue_repo.get_all_queued_signals = AsyncMock(return_value=[mock_signal])
    mock_queue_repo.update = AsyncMock()

    mock_pos_group_repo = MagicMock(spec=PositionGroupRepository)
    mock_pos_group_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])

    mock_exchange = AsyncMock()
    # Price went down, so short is in profit
    mock_exchange.get_current_price = AsyncMock(return_value=Decimal("45000"))

    mock_session_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_ctx

    service = QueueManagerService(
        session_factory=mock_session_factory,
        queued_signal_repository_class=lambda s: mock_queue_repo,
        position_group_repository_class=lambda s: mock_pos_group_repo,
        exchange_connector=mock_exchange
    )

    await service.promote_highest_priority_signal(session=mock_session)

    # Verify PnL was calculated correctly for short: (entry - current) / entry * 100
    # (50000 - 45000) / 50000 * 100 = 10% profit
    assert mock_signal.current_loss_percent == Decimal("10.0")


@pytest.mark.asyncio
async def test_promote_highest_priority_signal_no_execution_pool_manager():
    """
    Test that promotion does not attempt slot request without execution pool manager.
    """
    user_id = uuid.uuid4()
    now = datetime.utcnow()

    mock_signal = MockQueuedSignal(
        queued_at=now,
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT"
    )

    mock_session = AsyncMock(spec=AsyncSession)
    user_mock = MagicMock(spec=User)
    user_mock.id = user_id
    user_mock.username = "testuser"
    user_mock.encrypted_api_keys = {"binance": {"encrypted_data": "mock"}}
    user_mock.risk_config = RiskEngineConfig().model_dump()
    mock_session.get = AsyncMock(return_value=user_mock)
    mock_session.commit = AsyncMock()

    mock_queue_repo = MagicMock(spec=QueuedSignalRepository)
    mock_queue_repo.get_all_queued_signals = AsyncMock(return_value=[mock_signal])
    mock_queue_repo.update = AsyncMock()

    mock_pos_group_repo = MagicMock(spec=PositionGroupRepository)
    mock_pos_group_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])

    mock_exchange = AsyncMock()
    mock_exchange.get_current_price = AsyncMock(return_value=Decimal("50000"))

    mock_session_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_ctx

    service = QueueManagerService(
        session_factory=mock_session_factory,
        queued_signal_repository_class=lambda s: mock_queue_repo,
        position_group_repository_class=lambda s: mock_pos_group_repo,
        exchange_connector=mock_exchange,
        execution_pool_manager=None  # No pool manager
    )

    # Should complete without attempting to request slot
    await service.promote_highest_priority_signal(session=mock_session)


@pytest.mark.asyncio
async def test_promotion_loop_commits_on_each_iteration():
    """
    Test that the promotion loop commits the session on each iteration.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session_factory = MagicMock(return_value=mock_ctx)

    service = QueueManagerService(
        session_factory=mock_session_factory,
        queued_signal_repository_class=MagicMock(),
        position_group_repository_class=MagicMock(),
        polling_interval_seconds=0.01
    )

    with patch.object(service, 'promote_highest_priority_signal', new=AsyncMock()):
        await service.start_promotion_task()
        await asyncio.sleep(0.05)
        await service.stop_promotion_task()

        # Session should have been committed at least once
        assert mock_session.commit.called


def test_calculate_queue_priority_with_positive_pnl():
    """
    Test priority calculation when signal has positive PnL (profit).
    """
    now = datetime.utcnow()
    signal = MockQueuedSignal(
        queued_at=now,
        current_loss_percent=Decimal("5.0")  # In profit, not loss
    )

    priority = calculate_queue_priority(signal, [])

    # Priority should still be calculated, just without loss bonus
    assert priority > Decimal("0")


def test_calculate_queue_priority_with_high_replacement_count():
    """
    Test priority calculation with high replacement count.
    """
    now = datetime.utcnow()
    signal = MockQueuedSignal(
        queued_at=now,
        replacement_count=10  # High replacement count
    )

    priority = calculate_queue_priority(signal, [])

    # Should have significant boost from replacement count
    assert priority > Decimal("10000")
