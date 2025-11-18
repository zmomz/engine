
import pytest
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.queue_manager import QueueManagerService
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.position_manager import PositionManagerService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.user import User # Import User model

# --- Fixtures ---

@pytest.fixture
async def user_id_fixture(db_session: AsyncMock):
    user = User(
        id=uuid.uuid4(),
        username="testuser_qms",
        email="test_qms@example.com",
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
    mock_instance.get_by_symbol_timeframe_side = AsyncMock(return_value=None)
    mock_class = MagicMock(spec=QueuedSignalRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_position_group_repository_class():
    mock_instance = MagicMock(spec=PositionGroupRepository)
    mock_class = MagicMock(spec=PositionGroupRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_exchange_connector():
    return MagicMock(spec=ExchangeInterface)

@pytest.fixture
def mock_execution_pool_manager():
    return MagicMock(spec=ExecutionPoolManager)

@pytest.fixture
def mock_position_manager_service():
    return MagicMock(spec=PositionManagerService)

@pytest.fixture
def mock_risk_engine_config():
    return MagicMock(spec=RiskEngineConfig)

@pytest.fixture
def mock_dca_grid_config():
    return MagicMock(spec=DCAGridConfig)

@pytest.fixture
def mock_total_capital_usd():
    return Decimal("10000")

@pytest.fixture
def mock_session_factory():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_session
    return MagicMock(return_value=mock_context_manager)

@pytest.fixture
def queue_manager_service(
    mock_session_factory,
    mock_queued_signal_repository_class,
    mock_position_group_repository_class,
    mock_exchange_connector,
    mock_execution_pool_manager,
    mock_position_manager_service,
    mock_risk_engine_config,
    mock_dca_grid_config,
    mock_total_capital_usd
):
    return QueueManagerService(
        session_factory=mock_session_factory,
        queued_signal_repository_class=mock_queued_signal_repository_class,
        position_group_repository_class=mock_position_group_repository_class,
        exchange_connector=mock_exchange_connector,
        execution_pool_manager=mock_execution_pool_manager,
        position_manager_service=mock_position_manager_service,
        risk_engine_config=mock_risk_engine_config,
        dca_grid_config=mock_dca_grid_config,
        total_capital_usd=mock_total_capital_usd
    )

@pytest.fixture
def sample_queued_signal_data(user_id_fixture):
    return {
        "user_id": str(user_id_fixture), # Convert UUID to string for payload
        "exchange": "binance",
        "symbol": "BTCUSDT",
        "timeframe": 15,
        "side": "long",
        "entry_price": Decimal("50000"),
        "signal_payload": {"some": "payload"}
    }

@pytest.fixture
def existing_queued_signal(sample_queued_signal_data):
    return QueuedSignal(
        id=uuid.uuid4(),
        user_id=uuid.UUID(sample_queued_signal_data["user_id"]),
        exchange=sample_queued_signal_data["exchange"],
        symbol=sample_queued_signal_data["symbol"],
        timeframe=sample_queued_signal_data["timeframe"],
        side=sample_queued_signal_data["side"],
        entry_price=Decimal("49000"), # Different entry price
        signal_payload={"old": "payload"},
        queued_at=datetime(2023, 1, 1),
        replacement_count=0,
        status=QueueStatus.QUEUED
    )

# --- Tests ---

@pytest.mark.asyncio
async def test_add_to_queue_new_signal(queue_manager_service, mock_queued_signal_repository_class, sample_queued_signal_data):
    """
    Test that a new signal can be successfully added to the queue.
    """
    await queue_manager_service.add_to_queue(sample_queued_signal_data)
    
    mock_queued_signal_repository_class.return_value.create.assert_called_once()
    created_signal_args = mock_queued_signal_repository_class.return_value.create.call_args[0][0]
    
    assert isinstance(created_signal_args, QueuedSignal)
    assert str(created_signal_args.user_id) == sample_queued_signal_data["user_id"]
    assert created_signal_args.symbol == sample_queued_signal_data["symbol"]
    assert created_signal_args.status == "queued"
    assert created_signal_args.queued_at is not None

@pytest.mark.asyncio
async def test_add_to_queue_replace_existing_signal(
    queue_manager_service,
    mock_queued_signal_repository_class,
    sample_queued_signal_data,
    existing_queued_signal
):
    """
    Test that an existing signal is replaced and updated if a new signal with the same
    symbol, timeframe, and side arrives.
    """
    # Configure the mock to return the existing signal
    mock_queued_signal_repository_class.return_value.get_by_symbol_timeframe_side.return_value = existing_queued_signal
    
    original_queued_at = existing_queued_signal.queued_at # Store original timestamp

    new_entry_price = Decimal("51000")
    updated_signal_data = sample_queued_signal_data.copy()
    updated_signal_data["entry_price"] = new_entry_price
    updated_signal_data["signal_payload"] = {"new": "payload"}

    returned_signal = await queue_manager_service.add_to_queue(updated_signal_data)
    
    # Assert that create was NOT called, but update WAS called
    mock_queued_signal_repository_class.return_value.create.assert_not_called()
    mock_queued_signal_repository_class.return_value.update.assert_called_once()
    
    # Assert the returned signal is the updated existing one
    assert returned_signal.id == existing_queued_signal.id
    assert returned_signal.replacement_count == 1
    assert returned_signal.entry_price == new_entry_price
    assert returned_signal.signal_payload == updated_signal_data
    assert returned_signal.queued_at > original_queued_at # Timestamp should be updated
