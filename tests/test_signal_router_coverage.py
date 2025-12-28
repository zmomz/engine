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
         patch("app.services.signal_router.ExchangeConfigService") as MockConfigService, \
         patch("app.services.signal_router.PositionManagerService") as MockPosManager, \
         patch("app.repositories.dca_configuration.DCAConfigurationRepository") as MockDCAConfigRepo:

        # Default success behavior for encryption service
        MockEnc.return_value.decrypt_keys.return_value = ("mock_key", "mock_secret")

        # Mock DCA configuration repository - return a valid config
        mock_dca_config = MagicMock()
        mock_dca_config.dca_levels = []
        mock_dca_config.tp_mode = "per_leg"
        mock_dca_config.tp_settings = {"tp_aggregate_percent": 0}
        mock_dca_config.max_pyramids = 5
        mock_dca_config.entry_order_type = "market"
        mock_dca_config.pyramid_specific_levels = {}
        # Add missing DCA config fields
        mock_dca_config.use_custom_capital = False
        mock_dca_config.custom_capital_usd = None
        mock_dca_config.pyramid_custom_capitals = {}
        mock_dca_repo_instance = MockDCAConfigRepo.return_value
        mock_dca_repo_instance.get_specific_config = AsyncMock(return_value=mock_dca_config)

        # Configure async methods on the *instance* returned by the mocked class
        mock_pool_instance = MockPool.return_value
        mock_pool_instance.request_slot = AsyncMock(return_value=True)

        # Create mock connector instance
        mock_connector_instance = AsyncMock()
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

        # Mock ExchangeConfigService.get_connector to return our mock connector
        MockConfigService.get_connector.return_value = mock_connector_instance

        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[])
        mock_repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

        mock_pos_manager_instance = MockPosManager.return_value  # Get the instance mock

        # Configure return value for create_position_group_from_signal
        mock_new_position_group = MagicMock(spec=PositionGroup)
        mock_new_position_group.status = PositionGroupStatus.LIVE  # Set a real status enum
        mock_pos_manager_instance.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

        # Configure return value for handle_pyramid_continuation
        mock_pos_manager_instance.handle_pyramid_continuation = AsyncMock(return_value=None)  # Or a mock group if needed

        mock_queue_instance = MockQueue.return_value
        mock_queue_instance.add_signal_to_queue = AsyncMock()

        yield {
            "repo": MockRepo,
            "pool": MockPool,
            "queue": MockQueue,
            "enc": MockEnc,
            "config_service": MockConfigService,
            "connector": mock_connector_instance,
            "pos_manager": MockPosManager,
            "dca_config_repo": MockDCAConfigRepo
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
            "max_total_exposure_usd": 100000,  # Increased to allow test signals (50k orders)
            "max_realized_loss_usd": 500,
            "loss_threshold_percent": -2.0
        }
    )
    return user

@pytest.mark.asyncio
async def test_route_missing_api_keys(sample_user, sample_signal, mock_async_session, mock_deps):
    from app.services.exchange_config_service import ExchangeConfigError

    # Setup: User has no keys for target exchange
    sample_user.encrypted_api_keys = {}

    # Configure ExchangeConfigService to raise error for missing API keys
    mock_deps["config_service"].get_connector.side_effect = ExchangeConfigError("No API keys for binance")

    # API keys are checked after DCA config check, so with valid DCA config we should get "No API keys" error
    service = SignalRouterService(sample_user)

    result = await service.route(sample_signal, mock_async_session)
    assert "Configuration Error: No API keys for binance" in result

@pytest.mark.asyncio
async def test_route_decryption_failure(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Decryption fails
    from app.services.exchange_config_service import ExchangeConfigError
    with patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncFactory, \
         patch('app.services.signal_router.ExchangeConfigService') as mock_config_service, \
         patch("app.services.signal_router.PositionManagerService", new=mock_deps["pos_manager"]):

        mock_enc_instance = MockEncFactory.return_value
        mock_enc_instance.decrypt_keys.side_effect = Exception("Decrypt fail")

        # Configure ExchangeConfigService.get_connector to raise an exception when called
        # to simulate decryption failure preventing connector initialization
        mock_config_service.get_connector.side_effect = ExchangeConfigError("Failed to initialize exchange connector")

        service = SignalRouterService(sample_user, encryption_service=mock_enc_instance)
        result = await service.route(sample_signal, mock_async_session)

        assert "Configuration Error: Failed to initialize exchange connector" in result

@pytest.mark.asyncio
async def test_route_fetch_balance_failure(sample_user, sample_signal, mock_async_session, mock_deps):
    # Setup: Exchange connector mock - configure the connector from fixture
    mock_deps["connector"].fetch_balance.side_effect = Exception("API Error")
    mock_deps["connector"].get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }

    # Setup: Mock repository to return empty list (New Position)
    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[])

    # Setup: Pool slot available
    mock_deps["pool"].return_value.request_slot = AsyncMock(return_value=True)

    # Setup: Pos Manager success
    pos_manager_mock = mock_deps["pos_manager"]  # The Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value

    # Configure return value for create_position_group_from_signal
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.LIVE  # Set a real status enum
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        # Should proceed despite balance fetch failure - capital comes from signal, not balance
        assert "New position created" in result
        pos_manager_instance_mock.create_position_group_from_signal.assert_called_once()
        # Verify capital is calculated from signal (order_size=1.0 * entry_price=50000 = 50000 USD)
        call_kwargs = pos_manager_instance_mock.create_position_group_from_signal.call_args.kwargs
        assert call_kwargs["total_capital_usd"] == Decimal("50000")

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
        total_invested_usd=Decimal("1000"),  # Required for risk check
        tp_mode="per_leg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[existing_group])
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=existing_group)

    # Configure mock connector from fixture
    mock_deps["connector"].fetch_balance.return_value = {'total': {'USDT': 5000}}
    mock_deps["connector"].get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }

    pos_manager_mock = mock_deps["pos_manager"]  # The Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.handle_pyramid_continuation = AsyncMock(return_value=None)  # Or a mock group if needed

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
        timeframe=int(sample_signal.tv.timeframe),
        side="long",
        status=PositionGroupStatus.LIVE,
        pyramid_count=5,  # Max pyramids reached
        max_pyramids=5,
        total_dca_legs=2,
        base_entry_price=Decimal("49000"),
        weighted_avg_entry=Decimal("49500"),
        total_invested_usd=Decimal("1000"),  # Required for risk check
        tp_mode="per_leg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[existing_group])
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=existing_group)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

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
        timeframe=int(sample_signal.tv.timeframe),  # Ensure int
        side="long",
        status=PositionGroupStatus.LIVE,
        pyramid_count=1,
        total_dca_legs=2,
        base_entry_price=Decimal("49000"),
        weighted_avg_entry=Decimal("49500"),
        total_invested_usd=Decimal("1000"),  # Required for risk check
        tp_mode="per_leg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[existing_group])
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=existing_group)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

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
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    # Fix: Mock create_position_group_from_signal as AsyncMock raising exception
    pos_manager_mock = mock_deps["pos_manager"] # The Mock class
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(side_effect=Exception("New Pos Error"))

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        assert "New position execution failed" in result


# --- Additional Coverage Tests ---

@pytest.mark.asyncio
async def test_route_exit_signal_success(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test successful exit signal handling."""
    # Change signal to exit type
    sample_signal.execution_intent.type = "exit"
    sample_signal.tv.action = "buy"  # Exit a long position

    existing_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=int(sample_signal.tv.timeframe),
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=1,
        total_dca_legs=2,
        base_entry_price=Decimal("49000"),
        weighted_avg_entry=Decimal("49500"),
        total_invested_usd=Decimal("1000"),  # Required for risk check
        tp_mode="per_leg"
    )

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_group_for_exit = AsyncMock(return_value=existing_group)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    mock_queue_instance = mock_deps["queue"].return_value
    mock_queue_instance.cancel_queued_signals_on_exit = AsyncMock(return_value=0)

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.handle_exit_signal = AsyncMock()

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        assert "Exit signal executed" in result
        pos_manager_instance_mock.handle_exit_signal.assert_called_once()


@pytest.mark.asyncio
async def test_route_exit_signal_no_position_found(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test exit signal when no active position exists."""
    sample_signal.execution_intent.type = "exit"
    sample_signal.tv.action = "sell"  # Exit a short position

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_group_for_exit = AsyncMock(return_value=None)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    mock_queue_instance = mock_deps["queue"].return_value
    mock_queue_instance.cancel_queued_signals_on_exit = AsyncMock(return_value=2)

    with patch("app.services.signal_router.PositionManagerService", new=mock_deps["pos_manager"]):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        assert "No active short position found" in result
        assert "2 queued signal(s) cancelled" in result


@pytest.mark.asyncio
async def test_route_no_dca_config(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test routing when no DCA configuration exists."""
    # Configure mock to return None for DCA config
    mock_dca_repo_instance = mock_deps["dca_config_repo"].return_value
    mock_dca_repo_instance.get_specific_config = AsyncMock(return_value=None)

    service = SignalRouterService(sample_user)
    result = await service.route(sample_signal, mock_async_session)

    assert "Configuration Error: No active DCA configuration" in result


@pytest.mark.asyncio
async def test_route_precision_validation_failure_with_blocking(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test precision validation failure when block_on_missing is True."""
    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {}  # No rules for symbol
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    sample_user.risk_config = {
        "max_open_positions_global": 5,
        "precision": {
            "block_on_missing_metadata": True,
            "fallback_rules": {
                "tick_size": 0.01,
                "step_size": 0.001,
                "min_qty": 0.00001,
                "min_notional": 10
            }
        }
    }

    service = SignalRouterService(sample_user)
    result = await service.route(sample_signal, mock_async_session)

    assert "Validation Error" in result


@pytest.mark.asyncio
async def test_route_precision_fetch_exception_with_fallback(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test precision fetch exception with fallback enabled."""
    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.side_effect = Exception("Network error")
    mock_exchange.fetch_balance = AsyncMock(return_value={'total': {'USDT': 1000}})
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    sample_user.risk_config = {
        "max_open_positions_global": 5,
        "precision": {
            "block_on_missing_metadata": False,  # Allow fallback
            "fallback_rules": {
                "tick_size": 0.01,
                "step_size": 0.001,
                "min_qty": 0.00001,
                "min_notional": 10
            }
        }
    }

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=True)

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.LIVE
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        # Should proceed with fallback rules
        assert "New position created" in result


@pytest.mark.asyncio
async def test_route_pool_full_queues_signal(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test that signal is queued when pool is full."""
    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[])
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=False)  # Pool full

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    mock_queue_instance = mock_deps["queue"].return_value
    mock_queue_instance.add_signal_to_queue = AsyncMock()

    with patch("app.services.signal_router.PositionManagerService", new=mock_deps["pos_manager"]):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        assert "Pool full" in result
        assert "Signal queued" in result
        mock_queue_instance.add_signal_to_queue.assert_called_once()


@pytest.mark.asyncio
async def test_route_pyramid_bypass_rule_disabled(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test pyramid when bypass rule is disabled but pool is full."""
    existing_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=int(sample_signal.tv.timeframe),
        side="long",
        status=PositionGroupStatus.LIVE,
        pyramid_count=1,
        total_dca_legs=2,
        base_entry_price=Decimal("49000"),
        weighted_avg_entry=Decimal("49500"),
        total_invested_usd=Decimal("1000"),  # Required for risk check
        tp_mode="per_leg"
    )

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[existing_group])
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=existing_group)

    # Configure risk config with same_pair_timeframe bypass disabled
    # but keep at least one other rule enabled to pass validation
    sample_user.risk_config = {
        "max_open_positions_global": 5,
        "max_total_exposure_usd": 100000,  # Must be high enough for the 50k order + 1k existing
        "priority_rules": {
            "priority_rules_enabled": {
                "same_pair_timeframe": False,  # Bypass disabled
                "waiting_time": True  # At least one enabled
            }
        }
    }

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=False)  # Pool full

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    mock_queue_instance = mock_deps["queue"].return_value
    mock_queue_instance.add_signal_to_queue = AsyncMock()

    with patch("app.services.signal_router.PositionManagerService", new=mock_deps["pos_manager"]):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        # Should queue because bypass is disabled and pool is full
        assert "Pool full (Rule Disabled)" in result
        mock_queue_instance.add_signal_to_queue.assert_called_once()


@pytest.mark.asyncio
async def test_route_risk_config_as_list_uses_default(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test that list risk_config uses default RiskEngineConfig."""
    sample_user.risk_config = []  # Invalid list format

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=True)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_exchange.fetch_balance = AsyncMock(return_value={'total': {'USDT': 1000}})
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.LIVE
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        # Should succeed with default config
        assert "New position created" in result


@pytest.mark.asyncio
async def test_route_new_position_failed_status(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test new position creation when order submission fails."""
    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[])
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=True)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.FAILED  # Order submission failed
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        assert "order submission failed" in result


@pytest.mark.asyncio
async def test_route_duplicate_position_exception(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test handling of DuplicatePositionException."""
    from app.services.position_manager import DuplicatePositionException

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_groups_for_user = AsyncMock(return_value=[])
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=True)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(
        side_effect=DuplicatePositionException("Active position already exists")
    )

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        assert "Duplicate position rejected" in result


@pytest.mark.asyncio
async def test_route_capital_cap_at_max_exposure(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test that capital is capped at max_total_exposure_usd."""
    sample_user.risk_config = {
        "max_open_positions_global": 5,
        "max_total_exposure_usd": 500  # Small cap
    }

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=True)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_exchange.fetch_balance = AsyncMock(return_value={'total': {'USDT': 10000}})  # Large balance
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.LIVE
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        # Verify capital was capped
        call_kwargs = pos_manager_instance_mock.create_position_group_from_signal.call_args.kwargs
        assert call_kwargs["total_capital_usd"] == Decimal("500")


@pytest.mark.asyncio
async def test_route_sell_action_maps_to_short(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test that 'sell' action is mapped to 'short' for entry signals."""
    sample_signal.tv.action = "sell"

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=True)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.LIVE
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        # Verify short was used
        call_args = pos_manager_instance_mock.create_position_group_from_signal.call_args
        signal_arg = call_args.kwargs["signal"]
        assert signal_arg.side == "short"


@pytest.mark.asyncio
async def test_route_legacy_string_api_keys(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test routing with legacy string format API keys."""
    sample_user.encrypted_api_keys = "legacy_encrypted_string"

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=True)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.LIVE
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        assert "New position created" in result


@pytest.mark.asyncio
async def test_route_risk_config_as_string(sample_user, sample_signal, mock_async_session, mock_deps):
    """Test routing with risk_config as JSON string."""
    import json
    sample_user.risk_config = json.dumps({
        "max_open_positions_global": 3,
        "max_total_exposure_usd": 1000
    })

    mock_pool_instance = mock_deps["pool"].return_value
    mock_pool_instance.request_slot = AsyncMock(return_value=True)

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules.return_value = {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    }
    mock_deps["config_service"].get_connector.return_value = mock_exchange

    repo_instance = mock_deps["repo"].return_value
    repo_instance.get_active_position_group_for_signal = AsyncMock(return_value=None)

    pos_manager_mock = mock_deps["pos_manager"]
    pos_manager_instance_mock = pos_manager_mock.return_value
    mock_new_position_group = MagicMock(spec=PositionGroup)
    mock_new_position_group.status = PositionGroupStatus.LIVE
    pos_manager_instance_mock.create_position_group_from_signal = AsyncMock(return_value=mock_new_position_group)

    with patch("app.services.signal_router.PositionManagerService", new=pos_manager_mock):
        service = SignalRouterService(sample_user)
        result = await service.route(sample_signal, mock_async_session)

        assert "New position created" in result