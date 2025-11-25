import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from decimal import Decimal
from datetime import datetime

from app.services.queue_manager import QueueManagerService
from app.models.user import User
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.position_group import PositionGroup

@pytest.fixture
def mock_deps():
    with patch("app.services.queue_manager.QueuedSignalRepository") as MockQueueRepo, \
         patch("app.services.queue_manager.PositionGroupRepository") as MockPosRepo, \
         patch("app.services.queue_manager.ExecutionPoolManager") as MockPool, \
         patch("app.services.position_manager.PositionManagerService") as MockPosManager, \
         patch("app.services.queue_manager.get_exchange_connector") as MockConnector, \
         patch("app.services.queue_manager.EncryptionService") as MockEnc:
        
        # Setup default behavior for synchronous service
        MockEnc.return_value.decrypt_keys.return_value = ("key", "secret")
        
        yield {
            "queue_repo": MockQueueRepo,
            "pos_repo": MockPosRepo,
            "pool": MockPool,
            "pos_manager": MockPosManager,
            "connector": MockConnector,
            "enc": MockEnc
        }

@pytest.fixture
def sample_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "test"
    user.email = "test@example.com"
    user.exchange = "binance"
    user.encrypted_api_keys = {"binance": {"encrypted_data": "dummy"}}
    user.risk_config = {
        "max_open_positions_global": 5,
        "max_open_positions_per_symbol": 1,
        "max_total_exposure_usd": 10000,
        "max_daily_loss_usd": 500,
        "loss_threshold_percent": -2.0,
        "min_close_notional": 10
    }
    user.dca_grid_config = []
    return user

@pytest.mark.asyncio
async def test_promote_signal_execution_new_position(sample_user, mock_async_session, mock_deps):
    # Setup: 1 Queued Signal
    signal = QueuedSignal(
        id=uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000"),
        status=QueueStatus.QUEUED,
        queued_at=datetime.utcnow(),
        replacement_count=0,
        signal_payload={}
    )
    
    # Mocks
    queue_repo = mock_deps["queue_repo"].return_value
    queue_repo.get_all_queued_signals = AsyncMock(return_value=[signal])
    queue_repo.update = AsyncMock() # Crucial: Make update awaitable
    
    pos_repo = mock_deps["pos_repo"].return_value
    pos_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])
    
    # Make sure session.get returns the sample_user
    # Make sure session.get returns the sample_user
    mock_async_session.__aenter__.return_value = mock_async_session
    mock_async_session.get = AsyncMock(return_value=sample_user)
    
    pool = mock_deps["pool"].return_value
    pool.request_slot = AsyncMock(return_value=True)
    
    connector = mock_deps["connector"].return_value
    connector.get_current_price = AsyncMock(return_value=Decimal("49000")) # Loss
    connector.fetch_balance = AsyncMock(return_value={'total': {'USDT': 1000}})

    pos_manager = mock_deps["pos_manager"].return_value
    pos_manager.create_position_group_from_signal = AsyncMock()

    service = QueueManagerService(
        session_factory=lambda: mock_async_session,
        user=sample_user,
        queued_signal_repository_class=mock_deps["queue_repo"],
        position_group_repository_class=mock_deps["pos_repo"],
        execution_pool_manager=pool,
        position_manager_service=pos_manager
    )
    
    # Execute
    await service.promote_highest_priority_signal()
    
    # Verify
    assert signal.status == QueueStatus.PROMOTED
    pos_manager.create_position_group_from_signal.assert_called_once()
    queue_repo.update.assert_called()

@pytest.mark.asyncio
async def test_promote_signal_execution_pyramid(sample_user, mock_async_session, mock_deps):
    # Setup: 1 Queued Signal matching existing group
    signal = QueuedSignal(
        id=uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000"),
        status=QueueStatus.QUEUED,
        queued_at=datetime.utcnow(),
        replacement_count=0,
        signal_payload={}
    )
    
    group = PositionGroup(
        id=uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        pyramid_count=1
    )
    
    # Mocks
    queue_repo = mock_deps["queue_repo"].return_value
    queue_repo.get_all_queued_signals = AsyncMock(return_value=[signal])
    queue_repo.update = AsyncMock() # Crucial
    
    pos_repo = mock_deps["pos_repo"].return_value
    pos_repo.get_active_position_groups_for_user = AsyncMock(return_value=[group])
    
    # Make sure session.get returns the sample_user
    mock_async_session.__aenter__.return_value = mock_async_session
    mock_async_session.get = AsyncMock(return_value=sample_user)
    
    pool = mock_deps["pool"].return_value
    pool.request_slot = AsyncMock(return_value=True)
    
    connector = mock_deps["connector"].return_value
    connector.get_current_price = AsyncMock(return_value=Decimal("51000")) 

    pos_manager = mock_deps["pos_manager"].return_value
    pos_manager.handle_pyramid_continuation = AsyncMock()

    service = QueueManagerService(
        session_factory=lambda: mock_async_session,
        user=sample_user,
        queued_signal_repository_class=mock_deps["queue_repo"],
        position_group_repository_class=mock_deps["pos_repo"],
        execution_pool_manager=pool,
        position_manager_service=pos_manager
    )
    
    # Execute
    await service.promote_highest_priority_signal()
    
    # Verify
    assert signal.status == QueueStatus.PROMOTED
    pos_manager.handle_pyramid_continuation.assert_called_once()

@pytest.mark.asyncio
async def test_promote_signal_price_fetch_failure(sample_user, mock_async_session, mock_deps):
    # Setup: 1 Queued Signal
    signal = QueuedSignal(
        id=uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000"),
        status=QueueStatus.QUEUED,
        queued_at=datetime.utcnow(),
        replacement_count=0,
        signal_payload={}
    )
    
    queue_repo = mock_deps["queue_repo"].return_value
    queue_repo.get_all_queued_signals = AsyncMock(return_value=[signal])
    queue_repo.update = AsyncMock() # Crucial
    
    pos_repo = mock_deps["pos_repo"].return_value
    pos_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])
    
    # Make sure session.get returns the sample_user
    mock_async_session.__aenter__.return_value = mock_async_session
    mock_async_session.get = AsyncMock(return_value=sample_user)
    
    connector = mock_deps["connector"].return_value
    connector.get_current_price.side_effect = Exception("API Error")
    
    pool = mock_deps["pool"].return_value
    pool.request_slot = AsyncMock(return_value=False) # Don't promote, just check price fetch loop

    service = QueueManagerService(
        session_factory=lambda: mock_async_session,
        user=sample_user,
        queued_signal_repository_class=mock_deps["queue_repo"],
        position_group_repository_class=mock_deps["pos_repo"],
        execution_pool_manager=pool,
        position_manager_service=mock_deps["pos_manager"].return_value
    )
    
    # Execute
    await service.promote_highest_priority_signal()
    
    # Should handle exception gracefully and attempt promotion logic (which fails due to slot)
    connector.get_current_price.assert_called_once()

@pytest.mark.asyncio
async def test_promote_signal_execution_exception(sample_user, mock_async_session, mock_deps):
    # Setup: 1 Queued Signal
    signal = QueuedSignal(
        id=uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000"),
        status=QueueStatus.QUEUED,
        queued_at=datetime.utcnow(),
        replacement_count=0,
        signal_payload={}
    )
    
    queue_repo = mock_deps["queue_repo"].return_value
    queue_repo.get_all_queued_signals = AsyncMock(return_value=[signal])
    queue_repo.update = AsyncMock() # Crucial
    
    pos_repo = mock_deps["pos_repo"].return_value
    pos_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])
    
    # Make sure session.get returns the sample_user
    mock_async_session.__aenter__.return_value = mock_async_session
    mock_async_session.get = AsyncMock(return_value=sample_user)
    
    pool = mock_deps["pool"].return_value
    pool.request_slot = AsyncMock(return_value=True)
    
    pos_manager = mock_deps["pos_manager"].return_value
    pos_manager.create_position_group_from_signal = AsyncMock(side_effect=Exception("Execution Failed"))

    service = QueueManagerService(
        session_factory=lambda: mock_async_session,
        user=sample_user,
        queued_signal_repository_class=mock_deps["queue_repo"],
        position_group_repository_class=mock_deps["pos_repo"],
        execution_pool_manager=pool,
        position_manager_service=pos_manager
    )
    
    # Execute
    await service.promote_highest_priority_signal()
    
    # Should catch exception and log error
    pos_manager.create_position_group_from_signal.assert_called_once()
    assert signal.status == QueueStatus.PROMOTED # Status was updated BEFORE execution attempt in the code