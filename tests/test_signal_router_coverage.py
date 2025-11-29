import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from app.services.signal_router import SignalRouterService
from app.schemas.webhook_payloads import WebhookPayload
from app.models.user import User
from app.models.position_group import PositionGroup
from app.db.database import AsyncSessionLocal

@pytest.fixture
def mock_deps():
    with patch("app.services.signal_router.PositionGroupRepository") as MockRepo, \
         patch("app.services.signal_router.ExecutionPoolManager") as MockPool, \
         patch("app.services.signal_router.QueueManagerService") as MockQueue, \
         patch("app.services.signal_router.EncryptionService") as MockEnc, \
         patch("app.services.signal_router.get_exchange_connector") as MockConnector, \
         patch("app.services.signal_router.PositionManagerService") as MockPosManager:
        
        # Default success behavior for encryption service
        MockEnc.return_value.decrypt_keys.return_value = ("mock_key", "mock_secret")

        yield {
            "repo": MockRepo,
            "pool": MockPool,
            "queue": MockQueue,
            "enc": MockEnc,
            "connector": MockConnector,
            "pos_manager": MockPosManager
        }

@pytest.fixture
def sample_signal():
    import uuid
    from datetime import datetime
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
            "tp_aggregate_percent": Decimal("0")
        }
    )
    return user

@pytest.mark.asyncio
async def test_route_missing_api_keys(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: User has no keys for target exchange
    sample_user.encrypted_api_keys = {}
    
    service = SignalRouterService(sample_user)
    result = await service.route(sample_signal, mock_async_session)
    
    assert "Configuration Error: No API keys" in result

@pytest.mark.asyncio
async def test_route_decryption_failure(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Decryption fails
    mock_deps["enc"].return_value.decrypt_keys.side_effect = Exception("Decrypt fail")
    
    service = SignalRouterService(sample_user)
    result = await service.route(sample_signal, mock_async_session)
    
    assert "Configuration Error: Failed to decrypt keys" in result

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
    pos_manager_instance = mock_deps["pos_manager"].return_value
    pos_manager_instance.create_position_group_from_signal = AsyncMock()

    service = SignalRouterService(sample_user)
    result = await service.route(sample_signal, mock_async_session)
    
    # Should proceed with default capital despite balance fetch failure
    assert "New position created" in result
    pos_manager_instance.create_position_group_from_signal.assert_called_once()
    # Verify default capital was passed (1000)
    call_kwargs = pos_manager_instance.create_position_group_from_signal.call_args.kwargs
    assert call_kwargs["total_capital_usd"] == Decimal("1000")

@pytest.mark.asyncio
async def test_route_pyramid_continuation(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Existing group
    existing_group = MagicMock(spec=PositionGroup)
    existing_group.symbol = "BTCUSDT"
    existing_group.timeframe = 15
    existing_group.side = "long"
    existing_group.pyramid_count = 1
    
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
    
    pos_manager_instance = mock_deps["pos_manager"].return_value
    pos_manager_instance.handle_pyramid_continuation = AsyncMock()

    service = SignalRouterService(sample_user)
    result = await service.route(sample_signal, mock_async_session)
    
    assert "Pyramid executed" in result
    pos_manager_instance.handle_pyramid_continuation.assert_called_once()

@pytest.mark.asyncio
async def test_route_max_pyramids_reached(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Existing group with max pyramids
    existing_group = MagicMock(spec=PositionGroup)
    existing_group.symbol = "BTCUSDT"
    existing_group.timeframe = 15
    existing_group.side = "long"
    existing_group.pyramid_count = 5 # Max
    
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

@pytest.mark.asyncio
async def test_route_pyramid_exception(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Existing group
    existing_group = MagicMock(spec=PositionGroup)
    existing_group.symbol = "BTCUSDT"
    existing_group.timeframe = 15
    existing_group.side = "long"
    existing_group.pyramid_count = 1
    
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

    service = SignalRouterService(sample_user)
    result = await service.route(sample_signal, mock_async_session)
    
    assert "New position execution failed" in result
