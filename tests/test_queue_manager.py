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
from app.services.risk_engine import RiskEngineService # Added
from app.services.grid_calculator import GridCalculatorService # Added
from app.services.order_management import OrderService # Added
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.schemas.webhook_payloads import WebhookPayload # Added
from pydantic import BaseModel, Field # Added
from typing import Optional, Literal # Added

# Helper to convert Decimal to str for JSON serialization
def convert_decimals_to_str(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: convert_decimals_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimals_to_str(elem) for elem in obj]
    return obj

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
        risk_config=convert_decimals_to_str(risk_config_data),
        dca_grid_config=convert_decimals_to_str(dca_grid_config_data)
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
            exchange="mock",
            webhook_secret="mock_secret",
            risk_config=convert_decimals_to_str(risk_config_data),
            dca_grid_config=convert_decimals_to_str(dca_grid_config_data)
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
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.assert_called_once_with(
        symbol="LTCUSDT", timeframe=60, side="long"
    )

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
        signal_payload={},
        queued_at=datetime.utcnow() - timedelta(hours=1),
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
    
    await queue_manager_service.add_signal_to_queue(signal_payload)
    
    assert original_signal.entry_price == Decimal("105.0")
    assert original_signal.replacement_count == 1
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.assert_called_once_with(
        symbol="LTCUSDT", timeframe=60, side="long"
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
    user_mock.risk_config = RiskEngineConfig().model_dump() # Mock as a dictionary
    user_mock.dca_grid_config = DCAGridConfig(levels=[]).model_dump() # Mock as a dictionary with default levels
    
    mock_session.get.return_value = user_mock

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method
    
    # Assertions should check the state after promotion, not return value
    # The promoted signal will have its status updated to PROMOTED
    # Update is called 3 times: 2 for loss calc (signal1, signal2), 1 for promotion (signal1)
    assert mock_queued_signal_repository_class.return_value.update.call_count == 3
    assert signal1.status == QueueStatus.PROMOTED.value
    assert mock_exchange_connector.get_current_price.call_count == 2

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

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method

    mock_exchange_connector.get_current_price.assert_called_once_with("BTCUSDT")
    # Update called 2 times: 1 for loss calc, 1 for promotion
    assert mock_queued_signal_repository_class.return_value.update.call_count == 2
    assert signal_to_promote.status == QueueStatus.PROMOTED.value # Assert status change
    mock_execution_pool_manager.request_slot.assert_called_once_with(is_pyramid_continuation=False) # Removed session arg
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
    user_mock.risk_config = RiskEngineConfig().model_dump() # Mock as a dictionary
    user_mock.dca_grid_config = DCAGridConfig(levels=[]).model_dump() # Mock as a dictionary

    # Mock session.get
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    mock_session.get.return_value = user_mock

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method

    queue_manager_service.exchange_connector.get_current_price.assert_called_once_with("ETHUSDT")
    mock_execution_pool_manager.request_slot.assert_called_once_with(is_pyramid_continuation=False) # Removed session arg
    # Assert that update was called once for loss calc, but not for promotion
    assert mock_queued_signal_repository_class.return_value.update.call_count == 1
    assert signal_in_queue.status == QueueStatus.QUEUED # Status should NOT change

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
    user_mock.risk_config = RiskEngineConfig().model_dump() # Mock as a dictionary
    user_mock.dca_grid_config = DCAGridConfig(levels=[]).model_dump() # Mock as a dictionary

    # Mock session.get
    mock_session = queue_manager_service.session_factory.return_value.__aenter__.return_value
    mock_session.get.return_value = user_mock

    await queue_manager_service.promote_highest_priority_signal(session=mock_session) # Call the correct method

    queue_manager_service.exchange_connector.get_current_price.assert_called_once_with("SOLUSDT")
    # Update called 2 times: 1 for loss calc, 1 for promotion
    assert mock_queued_signal_repository_class.return_value.update.call_count == 2
    assert signal_pyramid.status == QueueStatus.PROMOTED.value
    mock_execution_pool_manager.request_slot.assert_called_once_with(is_pyramid_continuation=True)

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
