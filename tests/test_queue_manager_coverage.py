import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from decimal import Decimal
from datetime import datetime

from app.services.queue_manager import QueueManagerService
from app.models.user import User
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.position_group import PositionGroup
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig

@pytest.fixture
def mock_deps():
    with patch("app.services.queue_manager.QueuedSignalRepository") as MockQueueRepo, \
         patch("app.services.queue_manager.PositionGroupRepository") as MockPosRepo, \
         patch("app.services.queue_manager.ExecutionPoolManager") as MockPool, \
         patch("app.services.queue_manager.PositionManagerService") as MockPosManager, \
         patch("app.services.queue_manager.get_exchange_connector") as MockConnector, \
         patch("app.services.queue_manager.EncryptionService") as MockEnc, \
         patch("app.services.queue_manager.DCAConfigurationRepository") as MockDCAConfigRepo:

        # Setup default behavior for synchronous service
        MockEnc.return_value.decrypt_keys.return_value = ("key", "secret")

        # Configure the return value of get_exchange_connector to have AsyncMock methods
        mock_exchange_connector_instance = MagicMock()
        mock_exchange_connector_instance.fetch_balance = AsyncMock(return_value={'total': {'USDT': Decimal('1000')}})
        mock_exchange_connector_instance.get_current_price = AsyncMock(return_value=Decimal("50000"))
        mock_exchange_connector_instance.close = AsyncMock() # Ensure close is also an AsyncMock
        MockConnector.return_value = mock_exchange_connector_instance

        # Setup DCA Config Repository mock
        mock_dca_config = MagicMock()
        mock_dca_config.dca_levels = [
            {"gap_percent": Decimal("0"), "weight_percent": Decimal("100"), "tp_percent": Decimal("1")}
        ]
        mock_dca_config.tp_mode = "per_leg"
        mock_dca_config.tp_settings = {"tp_aggregate_percent": Decimal("0")}
        mock_dca_config.max_pyramids = 5
        mock_dca_config.entry_order_type = "market"
        mock_dca_config.pyramid_specific_levels = {}
        mock_dca_config.use_custom_capital = False
        mock_dca_config.custom_capital_usd = None
        mock_dca_config.pyramid_custom_capitals = {}
        MockDCAConfigRepo.return_value.get_specific_config = AsyncMock(return_value=mock_dca_config)

        yield {
            "queue_repo": MockQueueRepo,
            "pos_repo": MockPosRepo,
            "pool": MockPool,
            "pos_manager": MockPosManager,
            "connector": MockConnector, # This is the mocked get_exchange_connector function
            "enc": MockEnc,
            "dca_config_repo": MockDCAConfigRepo
        }

@pytest.fixture
def sample_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "test"
    user.email = "test@example.com"
    user.exchange = "binance"
    user.encrypted_api_keys = {"binance": {"encrypted_data": "dummy"}}
    # risk_config should be a dict (the code handles both dict and JSON string formats)
    user.risk_config = RiskEngineConfig().model_dump()
    user.dca_grid_config = DCAGridConfig(levels=[]).model_dump()
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
    queue_repo.update = AsyncMock()  # Crucial: Make update awaitable

    pos_repo = mock_deps["pos_repo"].return_value
    pos_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])
    pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
    pos_repo.get_total_exposure_for_user = AsyncMock(return_value=Decimal("0"))
    pos_repo.get_open_positions_count_for_user = AsyncMock(return_value=0)
    pos_repo.get_open_positions_count_by_symbol = AsyncMock(return_value=0)

    # Make sure session.get returns the sample_user
    mock_async_session.__aenter__.return_value = mock_async_session
    mock_async_session.get = AsyncMock(return_value=sample_user)

    pool = mock_deps["pool"].return_value
    pool.request_slot = AsyncMock(return_value=True)

    # The connector mock returned by the fixture should already have AsyncMock methods
    connector_instance = mock_deps["connector"].return_value
    connector_instance.get_current_price.return_value = Decimal("49000")  # Loss for this specific test
    # fetch_balance is already mocked in the fixture with a default return value

    pos_manager_mock = mock_deps["pos_manager"]  # Get the Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock()

    service = QueueManagerService(
        session_factory=lambda: mock_async_session,
        user=sample_user,
        queued_signal_repository_class=mock_deps["queue_repo"],
        position_group_repository_class=mock_deps["pos_repo"],
        exchange_connector=connector_instance,  # Pass the mock connector instance
        execution_pool_manager=pool,
        position_manager_service=pos_manager_instance_mock  # This is still passed, but not used due to internal creation
    )

    # Execute
    await service.promote_highest_priority_signal(session=mock_async_session)

    # Verify
    assert signal.status == QueueStatus.PROMOTED
    pos_manager_instance_mock.create_position_group_from_signal.assert_called_once()
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
        pyramid_count=1,
        total_invested_usd=Decimal("100"),
        max_pyramids=5
    )
    
    # Mocks
    queue_repo = mock_deps["queue_repo"].return_value
    queue_repo.get_all_queued_signals = AsyncMock(return_value=[signal])
    queue_repo.update = AsyncMock()  # Crucial

    pos_repo = mock_deps["pos_repo"].return_value
    pos_repo.get_active_position_groups_for_user = AsyncMock(return_value=[group])
    pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
    pos_repo.get_total_exposure_for_user = AsyncMock(return_value=Decimal("0"))
    pos_repo.get_open_positions_count_for_user = AsyncMock(return_value=1)
    pos_repo.get_open_positions_count_by_symbol = AsyncMock(return_value=1)

    # Make sure session.get returns the sample_user
    mock_async_session.__aenter__.return_value = mock_async_session
    mock_async_session.get = AsyncMock(return_value=sample_user)

    pool = mock_deps["pool"].return_value
    pool.request_slot = AsyncMock(return_value=True)

    connector_instance = mock_deps["connector"].return_value
    connector_instance.get_current_price.return_value = Decimal("51000")
    # fetch_balance is already mocked in the fixture with a default return value

    pos_manager_mock = mock_deps["pos_manager"]  # Get the Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.handle_pyramid_continuation = AsyncMock()

    service = QueueManagerService(
        session_factory=lambda: mock_async_session,
        user=sample_user,
        queued_signal_repository_class=mock_deps["queue_repo"],
        position_group_repository_class=mock_deps["pos_repo"],
        exchange_connector=connector_instance,  # Pass the mock connector instance
        execution_pool_manager=pool,
        position_manager_service=pos_manager_instance_mock
    )

    # Execute
    await service.promote_highest_priority_signal(session=mock_async_session)

    # Verify
    assert signal.status == QueueStatus.PROMOTED
    pos_manager_instance_mock.handle_pyramid_continuation.assert_called_once()

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
    queue_repo.update = AsyncMock()  # Crucial

    pos_repo = mock_deps["pos_repo"].return_value
    pos_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])
    pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
    pos_repo.get_total_exposure_for_user = AsyncMock(return_value=Decimal("0"))
    pos_repo.get_open_positions_count_for_user = AsyncMock(return_value=0)
    pos_repo.get_open_positions_count_by_symbol = AsyncMock(return_value=0)

    # Make sure session.get returns the sample_user
    mock_async_session.__aenter__.return_value = mock_async_session
    mock_async_session.get = AsyncMock(return_value=sample_user)

    connector_instance = mock_deps["connector"].return_value
    connector_instance.get_current_price.side_effect = Exception("API Error")
    # fetch_balance is already mocked in the fixture with a default return value

    pool = mock_deps["pool"].return_value
    pool.request_slot = AsyncMock(return_value=False)  # Don't promote, just check price fetch loop

    # Also patch PositionManagerService here, even if not directly called in this specific test's flow
    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock()

    service = QueueManagerService(
        session_factory=lambda: mock_async_session,
        user=sample_user,
        queued_signal_repository_class=mock_deps["queue_repo"],
        position_group_repository_class=mock_deps["pos_repo"],
        exchange_connector=connector_instance,  # Pass the mock connector instance
        execution_pool_manager=pool,
        position_manager_service=pos_manager_instance_mock
    )

    # Execute
    await service.promote_highest_priority_signal(session=mock_async_session)

    # Should handle exception gracefully and attempt promotion logic (which fails due to slot)
    connector_instance.get_current_price.assert_called_once()

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
    queue_repo.update = AsyncMock()  # Crucial

    pos_repo = mock_deps["pos_repo"].return_value
    pos_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])
    pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
    pos_repo.get_total_exposure_for_user = AsyncMock(return_value=Decimal("0"))
    pos_repo.get_open_positions_count_for_user = AsyncMock(return_value=0)
    pos_repo.get_open_positions_count_by_symbol = AsyncMock(return_value=0)

    # Make sure session.get returns the sample_user
    mock_async_session.__aenter__.return_value = mock_async_session
    mock_async_session.get = AsyncMock(return_value=sample_user)

    pool = mock_deps["pool"].return_value
    pool.request_slot = AsyncMock(return_value=True)

    pos_manager_mock = mock_deps["pos_manager"]  # Get the Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(side_effect=Exception("Execution Failed"))

    connector_instance = mock_deps["connector"].return_value  # Get the mock instance from the fixture
    connector_instance.get_current_price.return_value = Decimal("49000")
    # fetch_balance is already mocked in the fixture with a default return value

    service = QueueManagerService(
        session_factory=lambda: mock_async_session,
        user=sample_user,
        queued_signal_repository_class=mock_deps["queue_repo"],
        position_group_repository_class=mock_deps["pos_repo"],
        exchange_connector=connector_instance,  # Pass the mock connector instance
        execution_pool_manager=pool,
        position_manager_service=pos_manager_instance_mock
    )

    # Execute
    await service.promote_highest_priority_signal(session=mock_async_session)

    # Should catch exception and log error
    pos_manager_instance_mock.create_position_group_from_signal.assert_called_once()
    assert signal.status == QueueStatus.PROMOTED  # Status was updated BEFORE execution attempt in the code
