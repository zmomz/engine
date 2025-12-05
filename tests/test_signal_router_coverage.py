import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
import uuid
from datetime import datetime

from app.services.signal_router import SignalRouterService
from app.schemas.webhook_payloads import WebhookPayload
from app.models.user import User
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.db.database import AsyncSessionLocal
from app.services.position_manager import PositionManagerService # Import for patching

@pytest.fixture
def mock_deps():
    with patch("app.services.signal_router.PositionGroupRepository") as MockRepo, \
         patch("app.services.signal_router.ExecutionPoolManager") as MockPool, \
         patch("app.services.signal_router.QueueManagerService") as MockQueue, \
         patch("app.services.signal_router.EncryptionService") as MockEnc, \
         patch("app.services.signal_router.get_exchange_connector") as MockConnector, \
         patch("app.services.signal_router.PositionManagerService") as MockPosManager: # This is the Mock class
        
        # Default success behavior for encryption service
        MockEnc.return_value.decrypt_keys.return_value = ("mock_key", "mock_secret")

        # Configure async methods on the *instance* returned by the mocked class
        mock_pool_instance = MockPool.return_value
        mock_pool_instance.request_slot = AsyncMock(return_value=True)

        mock_connector_instance = MockConnector.return_value
        mock_connector_instance.get_precision_rules = AsyncMock(return_value={
            "BTCUSDT": {
                "tick_size": Decimal("0.01"),
                "step_size": Decimal("0.001"),
                "min_notional": Decimal("10.0"),
                "min_qty": Decimal("0.00001")
            }
        })
        mock_connector_instance.close = AsyncMock()
        mock_connector_instance.fetch_balance = AsyncMock(return_value={'total': {'USDT': 1000}})


        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[])

        mock_pos_manager_instance = MockPosManager.return_value # Get the instance mock
        
        # Configure return value for create_position_group_from_signal
        mock_new_position_group = MagicMock(spec=PositionGroup)
        mock_new_position_group.status = PositionGroupStatus.LIVE # Set a real status enum
        mock_pos_manager_instance.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)
        
        # Configure return value for handle_pyramid_continuation
        mock_pos_manager_instance.handle_pyramid_continuation = AsyncMock(return_value=None) # Or a mock group if needed
        
        mock_queue_instance = MockQueue.return_value
        mock_queue_instance.add_signal_to_queue = AsyncMock()

        yield {
            "repo": MockRepo,
            "pool": MockPool,
            "queue": MockQueue,
            "enc": MockEnc,
            "connector": MockConnector,
            "pos_manager": MockPosManager # This is the Mock class (the patch target)
        }

@pytest.fixture
def sample_signal():
    return WebhookPayload(
        user_id=uuid.uuid4(),
        secret="dummy_secret",
        source="TradingView",
        timestamp=datetime.utcnow(),
        tv={
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "15",
            "action": "long",
            "market_position": "long",
            "market_position_size": 1.0,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": 50000.0,
            "close_price": 50000.0,
            "order_size": 1.0,
        },
        strategy_info={
            "trade_id": "t1",
            "alert_name": "alert1",
            "alert_message": "msg"
        },
        execution_intent={
            "type": "signal",
            "side": "long",
            "position_size_type": "base",
            "precision_mode": "auto"
        },
        risk={
            "stop_loss": 49000.0,
            "take_profit": 51000.0,
            "max_slippage_percent": 0.5
        }
    )

@pytest.fixture
def sample_user():
    user = User(
        id="u1",
        username="test",
        email="test@example.com",
        hashed_password="hash",
        exchange="binance",
        encrypted_api_keys={"binance": {"encrypted_data": "dummy"}},
        risk_config={
            "max_open_positions_global": 5,
            "max_open_positions_per_symbol": 1,
            "max_total_exposure_usd": 10000,
            "max_daily_loss_usd": 500,
            "loss_threshold_percent": -2.0
        },
        dca_grid_config={
            "levels": [
                {"gap_percent": 1.0, "weight_percent": 50.0, "tp_percent": 1.0},
                {"gap_percent": 2.0, "weight_percent": 50.0, "tp_percent": 1.0}
            ],
            "tp_mode": "per_leg",
            "tp_aggregate_percent": Decimal("0"),
            "max_pyramids": 5 # Explicitly setting max_pyramids
        }
    )
    return user

@pytest.mark.asyncio
async def test_route_missing_api_keys(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: User has no keys for target exchange
    sample_user.encrypted_api_keys = {}
    
    service = SignalRouterService(sample_user)
    # Ensure mock_async_session is an AsyncMock if it's not already
    if not isinstance(mock_async_session, AsyncMock):
        mock_async_session = AsyncMock()
    
    # Patch PositionManagerService since SignalRouterService instantiates it internally
    with patch("app.services.signal_router.PositionManagerService", new=mock_deps["pos_manager"]):
        result = await service.route(sample_signal, mock_async_session)
        assert "Configuration Error: No API keys" in result

@pytest.mark.asyncio
async def test_route_decryption_failure(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Decryption fails
    with patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncFactory, \
         patch('app.services.signal_router.get_exchange_connector') as mock_get_exchange_connector, \
         patch("app.services.signal_router.PositionManagerService", new=mock_deps["pos_manager"]):
        
        mock_enc_instance = MockEncFactory.return_value
        mock_enc_instance.decrypt_keys.side_effect = Exception("Decrypt fail")
        
        # Configure mock_get_exchange_connector to raise an exception when called
        # to simulate decryption failure preventing connector initialization
        mock_get_exchange_connector.side_effect = Exception("Failed to initialize exchange connector")

        service = SignalRouterService(sample_user, encryption_service=mock_enc_instance)
        result = await service.route(sample_signal, mock_async_session)
        
        assert "Configuration Error: Failed to initialize exchange connector" in result

@pytest.mark.asyncio
async def test_route_fetch_balance_failure(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Exchange connector mock
    mock_exchange = AsyncMock()
    mock_exchange.fetch_balance.side_effect = Exception("API Error")
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["connector"].return_value = mock_exchange
    
    # Setup: Mock repository to return empty list (New Position)
    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[])
    
    # Setup: Pool slot available
    mock_deps["pool"].return_value.request_slot = AsyncMock(return_value=True)
    
    # Setup: Pos Manager success
    pos_manager_mock = mock_deps["pos_manager"] # The Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    
    # Configure return value for create_position_group_from_signal
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.LIVE # Set a real status enum
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)
        
        # Should proceed with default capital despite balance fetch failure
        assert "New position created" in result
        pos_manager_instance_mock.create_position_group_from_signal.assert_called_once()
        # Verify default capital was passed (1000)
        call_kwargs = pos_manager_instance_mock.create_position_group_from_signal.call_args.kwargs
        assert call_kwargs["total_capital_usd"] == Decimal("1000")

@pytest.mark.asyncio
async def test_route_pyramid_continuation(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Existing group
    existing_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=int(sample_signal.tv.timeframe),  # Ensure int
        side="long",
        status=PositionGroupStatus.LIVE,
        pyramid_count=1,
        total_dca_legs=2,
        base_entry_price=Decimal("49000"),
        weighted_avg_entry=Decimal("49500"),
        tp_mode="per_leg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[existing_group])
    
    mock_exchange = AsyncMock()
    mock_exchange.fetch_balance.return_value = {'total': {'USDT': 5000}}
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["connector"].return_value = mock_exchange
    
    pos_manager_mock = mock_deps["pos_manager"] # The Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.handle_pyramid_continuation = AsyncMock(return_value=None) # Or a mock group if needed

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)
        
        assert "Pyramid executed" in result
        pos_manager_instance_mock.handle_pyramid_continuation.assert_called_once()

@pytest.mark.asyncio
async def test_route_max_pyramids_reached(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Existing group with max pyramids
    existing_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=int(sample_signal.tv.timeframe), # Ensure int
        side="long",
        status=PositionGroupStatus.LIVE,
        pyramid_count=sample_user.dca_grid_config["max_pyramids"], # Max pyramids reached
        total_dca_legs=2,
        base_entry_price=Decimal("49000"),
        weighted_avg_entry=Decimal("49500"),
        tp_mode="per_leg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[existing_group])
    
    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["connector"].return_value = mock_exchange

    pos_manager_mock = mock_deps["pos_manager"] # The Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value # The mock instance

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)
        
        assert "Max pyramids reached" in result

@pytest.mark.asyncio
async def test_route_pyramid_exception(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Existing group
    existing_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=int(sample_signal.tv.timeframe), # Ensure int
        side="long",
        status=PositionGroupStatus.LIVE,
        pyramid_count=1,
        total_dca_legs=2,
        base_entry_price=Decimal("49000"),
        weighted_avg_entry=Decimal("49500"),
        tp_mode="per_leg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[existing_group])
    
    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["connector"].return_value = mock_exchange

    # Fix: Mock handle_pyramid_continuation as AsyncMock raising exception
    pos_manager_mock = mock_deps["pos_manager"] # The Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.handle_pyramid_continuation = AsyncMock(side_effect=Exception("Pyramid Error"))

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)
        
        assert "Pyramid execution failed" in result

@pytest.mark.asyncio
async def test_route_new_position_exception(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: No existing group
    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[])
    
    # Setup: Slot available
    mock_deps["pool"].return_value.request_slot = AsyncMock(return_value=True)
    
    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["connector"].return_value = mock_exchange

    # Fix: Mock create_position_group_from_signal as AsyncMock raising exception
    pos_manager_mock = mock_deps["pos_manager"] # The Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(side_effect=Exception("New Pos Error"))

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)
        
        assert "New position execution failed" in result