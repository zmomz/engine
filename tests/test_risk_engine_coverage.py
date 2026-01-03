import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
from app.services.risk_engine import RiskEngineService, _filter_eligible_losers, calculate_partial_close_quantities, select_loser_and_winners
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.queued_signal import QueuedSignal
from app.schemas.grid_config import RiskEngineConfig
from app.models.user import User
from app.core.security import EncryptionService # Import EncryptionService
from fastapi import HTTPException

# --- Fixtures ---

@pytest.fixture
def mock_user():
    user_id = uuid.uuid4()
    return MagicMock(
        id=user_id,
        encrypted_api_keys={
            "binance": {"encrypted_data": "dummy_binance_key", "testnet": True, "account_type": "SPOT"},
            "bybit": {"encrypted_data": "dummy_bybit_key", "testnet": False, "account_type": "UNIFIED"}
        }
    )

@pytest.fixture
def mock_config():
    return RiskEngineConfig(
        max_open_positions_global=5,
        max_open_positions_per_symbol=2,
        max_total_exposure_usd=1000.0,
        max_realized_loss_usd=100.0,
        loss_threshold_percent=Decimal("-5.0"),
        max_winners_to_combine=3,
        required_pyramids_for_timer=1,
        post_pyramids_wait_minutes=15
    )

@pytest.fixture
def mock_position_group():
    pg = MagicMock(spec=PositionGroup)
    pg.status = PositionGroupStatus.ACTIVE.value
    pg.pyramid_count = 1
    pg.max_pyramids = 1
    pg.filled_dca_legs = 1
    pg.total_dca_legs = 1
    pg.risk_timer_expires = datetime.utcnow() - timedelta(minutes=1)
    pg.unrealized_pnl_percent = Decimal("-6.0")
    pg.unrealized_pnl_usd = Decimal("-60.0")
    pg.risk_blocked = False
    pg.risk_skip_once = False
    pg.created_at = datetime.utcnow() - timedelta(minutes=120)
    pg.symbol = "BTC/USD"
    pg.total_invested_usd = Decimal("100.0")
    pg.exchange = "binance" # Added exchange for mock_user
    return pg

# --- Tests for _filter_eligible_losers ---

def test_filter_eligible_losers_all_pass(mock_position_group, mock_config):
    results = _filter_eligible_losers([mock_position_group], mock_config)
    assert len(results) == 1

def test_filter_eligible_losers_blocked(mock_position_group, mock_config):
    mock_position_group.risk_blocked = True
    results = _filter_eligible_losers([mock_position_group], mock_config)
    assert len(results) == 0

def test_filter_eligible_losers_skip_once(mock_position_group, mock_config):
    mock_position_group.risk_skip_once = True
    results = _filter_eligible_losers([mock_position_group], mock_config)
    assert len(results) == 0

def test_filter_eligible_losers_timer_active(mock_position_group, mock_config):
    mock_position_group.risk_timer_expires = datetime.utcnow() + timedelta(minutes=10)
    results = _filter_eligible_losers([mock_position_group], mock_config)
    assert len(results) == 0

def test_filter_eligible_losers_pnl_not_reached(mock_position_group, mock_config):
    mock_position_group.unrealized_pnl_percent = Decimal("-4.0") # Config is -5.0
    results = _filter_eligible_losers([mock_position_group], mock_config)
    assert len(results) == 0

def test_filter_eligible_losers_insufficient_pyramids(mock_position_group, mock_config):
    """Test that positions with insufficient pyramids are not eligible."""
    mock_position_group.pyramid_count = 1
    mock_position_group.max_pyramids = 5
    mock_config.required_pyramids_for_timer = 3  # Requires 3 pyramids
    results = _filter_eligible_losers([mock_position_group], mock_config)
    assert len(results) == 0

def test_filter_eligible_losers_timer_not_expired(mock_position_group, mock_config):
    """Test that positions with active (not expired) timers are not eligible."""
    mock_position_group.pyramid_count = 3
    mock_position_group.max_pyramids = 3
    mock_config.required_pyramids_for_timer = 3
    mock_position_group.risk_timer_expires = datetime.utcnow() + timedelta(minutes=10)  # Timer still active
    results = _filter_eligible_losers([mock_position_group], mock_config)
    assert len(results) == 0

# --- Tests for calculate_partial_close_quantities ---

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_success(mock_user):
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.return_value = Decimal("100.0")
    exchange_connector.get_precision_rules.return_value = {
        "ETH/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("5.0")}
    }
    
    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.weighted_avg_entry = Decimal("90.0")
    winner.side = "long"
    winner.total_filled_quantity = Decimal("10.0")
    winner.exchange = "binance" # Added exchange for mock_user
    
    required_usd = Decimal("20.0")
    
    with (
        patch('app.services.risk.risk_executor.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncryptionService
    ):
        MockEncryptionService.return_value.decrypt_keys.return_value = ("decrypted_key", "decrypted_secret")
        exchange_connector.close = AsyncMock() # Ensure close is also an AsyncMock
        plan = await calculate_partial_close_quantities(
            mock_user, [winner], required_usd
        )
    
    assert len(plan) == 1
    # Profit per unit = 100 - 90 = 10.
    # Required = 20. Qty = 20 / 10 = 2.0.
    assert plan[0][1] == Decimal("2.00")

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_zero_profit_per_unit(mock_user):
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.return_value = Decimal("90.0") # Same as entry
    exchange_connector.get_precision_rules.return_value = {}
    
    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.weighted_avg_entry = Decimal("90.0")
    winner.side = "long"
    winner.exchange = "binance" # Added exchange for mock_user
    
    required_usd = Decimal("20.0")
    
    with (
        patch('app.services.risk.risk_executor.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncryptionService
    ):
        MockEncryptionService.return_value.decrypt_keys.return_value = ("decrypted_key", "decrypted_secret")
        exchange_connector.close = AsyncMock() # Ensure close is also an AsyncMock
        plan = await calculate_partial_close_quantities(
            mock_user, [winner], required_usd
        )
    
    assert len(plan) == 0

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_below_min_notional(mock_user):
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.return_value = Decimal("100.0")
    exchange_connector.get_precision_rules.return_value = {
        "ETH/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("10.0")}
    }
    
    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("0.5") # Very small profit available
    winner.weighted_avg_entry = Decimal("90.0")
    winner.side = "long"
    winner.exchange = "binance" # Added exchange for mock_user
    
    required_usd = Decimal("0.5")
    
    # Profit per unit = 10. Qty = 0.5 / 10 = 0.05.
    # Notional = 0.05 * 100 = 5.0. Min notional = 10.0. Should skip.
    
    with (
        patch('app.services.risk.risk_executor.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncryptionService
    ):
        MockEncryptionService.return_value.decrypt_keys.return_value = ("decrypted_key", "decrypted_secret")
        exchange_connector.close = AsyncMock() # Ensure close is also an AsyncMock
        plan = await calculate_partial_close_quantities(
            mock_user, [winner], required_usd
        )
    
    assert len(plan) == 0

# --- Tests for validate_pre_trade_risk ---

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_checks(mock_config):
    """Test various pre-trade risk checks.

    Note: max_open_positions_global check is now handled by ExecutionPoolManager,
    so we only test the remaining checks.
    """
    # Patch EncryptionService globally for this test
    with patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService:
        MockEncryptionService.return_value.decrypt_keys.return_value = ("decrypted_key", "decrypted_secret")
        service = RiskEngineService(
            session_factory=AsyncMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        signal = QueuedSignal(user_id=uuid.uuid4(), symbol="BTC/USD", exchange="binance", timeframe=60)
        active_positions = []

        # 1. Success case
        session = AsyncMock()

        # Mock daily pnl
        pos_repo_mock = MagicMock()
        pos_repo_mock.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0.0"))
        service.position_group_repository_class.return_value = pos_repo_mock

        result = await service.validate_pre_trade_risk(
            signal, active_positions, Decimal("100.0"), session
        )
        assert result[0] is True

        # 2. Max Symbol Positions (same symbol/timeframe/exchange)
        active_positions = [MagicMock(symbol="BTC/USD", total_invested_usd=Decimal("10"), exchange="binance", timeframe=60) for _ in range(2)]
        result = await service.validate_pre_trade_risk(
            signal, active_positions, Decimal("100.0"), session
        )
        assert result[0] is False
        assert "BTC/USD/60m/binance" in result[1]

        # 3. Max Total Exposure
        active_positions = [MagicMock(symbol="ETH/USD", total_invested_usd=Decimal("950.0"), exchange="binance", timeframe=60)]
        result = await service.validate_pre_trade_risk(
            signal, active_positions, Decimal("100.0"), session
        )
        assert result[0] is False
        assert "Max exposure" in result[1]

        # 4. Daily Loss Limit
        active_positions = []
        pos_repo_mock.get_daily_realized_pnl = AsyncMock(return_value=Decimal("-150.0")) # Limit is 100
        result = await service.validate_pre_trade_risk(
            signal, active_positions, Decimal("100.0"), session
        )
        assert result[0] is False
        assert "Max realized loss" in result[1]

# --- Test for _evaluate_user_positions execution flow ---

@pytest.mark.asyncio
async def test_evaluate_user_positions_execution(mock_config):
    # Setup
    session = AsyncMock()
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "test"
    user.risk_config = mock_config.model_dump()
    user.encrypted_api_keys = {"binance": {"encrypted_data": "dummy"}}

    loser_pyramid_id = uuid.uuid4()
    winner_pyramid_id = uuid.uuid4()

    loser = MagicMock()
    loser.id = uuid.uuid4()
    loser.symbol = "BTC/USD"
    loser.exchange = "binance"
    loser.unrealized_pnl_usd = Decimal("-100")
    loser.unrealized_pnl_percent = Decimal("-2")
    loser.side = "long"
    loser.total_filled_quantity = Decimal("1.0")
    loser.total_invested_usd = Decimal("50000")
    loser.weighted_avg_entry = Decimal("50000")
    loser.user_id = user.id
    loser.risk_skip_once = False
    loser.status = "active"

    winner = MagicMock()
    winner.id = uuid.uuid4()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("200")
    winner.unrealized_pnl_percent = Decimal("10")
    winner.side = "long"
    winner.user_id = user.id
    winner.exchange = "binance"
    winner.total_filled_quantity = Decimal("1.0")
    winner.total_invested_usd = Decimal("2000")
    winner.weighted_avg_entry = Decimal("2000")
    winner.total_hedged_qty = Decimal("0")
    winner.total_hedged_value_usd = Decimal("0")

    # Create pyramid mocks
    loser_pyramid = MagicMock()
    loser_pyramid.id = loser_pyramid_id
    loser_pyramid.group_id = loser.id

    winner_pyramid = MagicMock()
    winner_pyramid.id = winner_pyramid_id
    winner_pyramid.group_id = winner.id

    # Mock session.execute to return pyramids based on group_id
    def mock_execute_side_effect(query):
        result = MagicMock()
        # Determine which pyramid to return based on the query
        # We'll return loser_pyramid first, then winner_pyramid
        return result

    # Use a list to track calls and return appropriate pyramids
    execute_call_count = [0]
    def make_execute_mock():
        async def execute_mock(query):
            result = MagicMock()
            if execute_call_count[0] == 0:
                result.scalar_one_or_none.return_value = loser_pyramid
            else:
                result.scalar_one_or_none.return_value = winner_pyramid
            execute_call_count[0] += 1
            return result
        return execute_mock

    session.execute = make_execute_mock()

    # Mocks
    mock_pos_repo = MagicMock()
    mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[loser, winner])
    mock_pos_repo.update = AsyncMock()

    mock_risk_repo = MagicMock()
    mock_risk_repo.create = AsyncMock()

    mock_order_service = MagicMock()
    mock_order_service_instance = mock_order_service.return_value
    mock_order_service_instance.place_market_order = AsyncMock()
    mock_order_service_instance.cancel_open_orders_for_group = AsyncMock()

    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules = AsyncMock(return_value={})
    mock_exchange.get_current_price = AsyncMock(return_value=Decimal("50000"))
    mock_exchange.close = AsyncMock()

    # Patch dependencies - use correct import paths
    with (
        patch("app.services.risk.risk_engine.select_loser_and_winners") as mock_select,
        patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService,
        patch("app.services.risk.risk_engine.get_exchange_connector") as mock_get_connector,
        patch("app.services.risk.risk_engine.calculate_partial_close_quantities") as mock_calc_close,
        patch("app.services.risk.risk_engine.update_risk_timers", new_callable=AsyncMock),
        patch("app.services.risk.risk_engine.broadcast_risk_event", new_callable=AsyncMock)
    ):

        mock_select.return_value = (loser, [winner], Decimal("100"))
        MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")
        mock_get_connector.return_value = mock_exchange
        mock_calc_close.return_value = [(winner, Decimal("0.5"))]

        service = RiskEngineService(
            session_factory=lambda: session,
            position_group_repository_class=MagicMock(return_value=mock_pos_repo),
            risk_action_repository_class=MagicMock(return_value=mock_risk_repo),
            dca_order_repository_class=MagicMock(),
            order_service_class=mock_order_service,
            risk_engine_config=mock_config
        )

        await service._evaluate_user_positions(session, user)

        # Assertions - include pyramid_id in the expected call
        mock_order_service_instance.place_market_order.assert_any_call(
            user_id=loser.user_id,
            exchange=loser.exchange,
            symbol=loser.symbol,
            side="sell",
            quantity=loser.total_filled_quantity,
            position_group_id=loser.id,
            pyramid_id=loser_pyramid_id,
            record_in_db=True
        )

        mock_order_service_instance.place_market_order.assert_any_call(
            user_id=winner.user_id,
            exchange=winner.exchange,
            symbol=winner.symbol,
            side="sell",
            quantity=Decimal("0.5"),
            position_group_id=winner.id,
            pyramid_id=winner_pyramid_id,
            record_in_db=True
        )

        mock_risk_repo.create.assert_called_once()
        # Commit is called multiple times during risk execution (offset close + position updates)
        assert session.commit.call_count >= 2, \
            f"Expected at least 2 commits, got {session.commit.call_count}"

        # CRITICAL: Verify position states were updated
        # Loser should have been updated (full close)
        assert mock_pos_repo.update.call_count >= 1, \
            "Position repository update must be called after hedge execution"

        # Verify cancel_open_orders_for_group was called for the loser
        mock_order_service_instance.cancel_open_orders_for_group.assert_called()

        # Verify risk action was created with correct data
        risk_action_call = mock_risk_repo.create.call_args[0][0]
        # RiskAction uses group_id and loser_group_id, not user_id and loser_position_id
        assert risk_action_call.group_id == loser.id
        assert risk_action_call.loser_group_id == loser.id
        # loser_pnl_usd should be the captured value BEFORE position was closed
        # (unrealized_pnl_usd gets reset to 0 when position is closed)
        assert risk_action_call.loser_pnl_usd == Decimal("-100")


# --- Additional Coverage Tests ---

@pytest.mark.asyncio
async def test_start_and_stop_monitoring_task(mock_config):
    """Test starting and stopping the monitoring task."""
    with patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService:
        MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")

        mock_session_factory = MagicMock()

        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            polling_interval_seconds=0.01
        )

        with patch.object(service, '_evaluate_positions', new=AsyncMock()) as mock_eval:
            await service.start_monitoring_task()
            assert service._running is True
            assert service._monitor_task is not None

            await asyncio.sleep(0.05)
            mock_eval.assert_called()

            await service.stop_monitoring_task()
            assert service._running is False


@pytest.mark.asyncio
async def test_monitoring_loop_error_handling(mock_config):
    """Test that monitoring loop handles errors gracefully."""
    with patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService:
        MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")

        mock_session_factory = MagicMock()

        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            polling_interval_seconds=0.01
        )

        with patch.object(service, '_evaluate_positions', side_effect=Exception("Test error")):
            await service.start_monitoring_task()
            await asyncio.sleep(0.05)
            # Should still be running despite errors
            assert service._running is True
            await service.stop_monitoring_task()


@pytest.mark.asyncio
async def test_set_risk_blocked_success(mock_config, mock_user):
    """Test setting risk_blocked flag on a position group."""
    group_id = uuid.uuid4()

    mock_position_group = MagicMock()
    mock_position_group.id = group_id
    mock_position_group.user_id = mock_user.id
    mock_position_group.risk_blocked = False

    mock_pos_repo = MagicMock()
    mock_pos_repo.get = AsyncMock(return_value=mock_position_group)
    mock_pos_repo.update = AsyncMock()

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(return_value=mock_pos_repo),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            user=mock_user
        )

        result = await service.set_risk_blocked(group_id, True)

        # CRITICAL: Verify state was actually changed
        assert mock_position_group.risk_blocked is True, \
            "Position risk_blocked must be set to True"

        # Verify repository update was called with correct position
        mock_pos_repo.update.assert_called_once_with(mock_position_group)

        # Verify the updated position has the correct flag
        updated_position = mock_pos_repo.update.call_args[0][0]
        assert updated_position.risk_blocked is True, \
            "Updated position must have risk_blocked=True"

        # Verify commit was called to persist the change
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_set_risk_blocked_not_found(mock_config, mock_user):
    """Test setting risk_blocked on non-existent position group."""
    group_id = uuid.uuid4()

    mock_pos_repo = MagicMock()
    mock_pos_repo.get = AsyncMock(return_value=None)

    mock_session = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(return_value=mock_pos_repo),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            user=mock_user
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.set_risk_blocked(group_id, True)

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_set_risk_blocked_unauthorized(mock_config, mock_user):
    """Test setting risk_blocked on another user's position group."""
    group_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    mock_position_group = MagicMock()
    mock_position_group.id = group_id
    mock_position_group.user_id = other_user_id  # Different user

    mock_pos_repo = MagicMock()
    mock_pos_repo.get = AsyncMock(return_value=mock_position_group)

    mock_session = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(return_value=mock_pos_repo),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            user=mock_user
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.set_risk_blocked(group_id, True)

        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_set_risk_skip_once_success(mock_config, mock_user):
    """Test setting risk_skip_once flag on a position group."""
    group_id = uuid.uuid4()

    mock_position_group = MagicMock()
    mock_position_group.id = group_id
    mock_position_group.user_id = mock_user.id
    mock_position_group.risk_skip_once = False

    mock_pos_repo = MagicMock()
    mock_pos_repo.get = AsyncMock(return_value=mock_position_group)
    mock_pos_repo.update = AsyncMock()

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(return_value=mock_pos_repo),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            user=mock_user
        )

        result = await service.set_risk_skip_once(group_id, True)

        assert mock_position_group.risk_skip_once is True
        mock_pos_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_get_current_status_with_loser_and_winners(mock_config, mock_user):
    """Test get_current_status returns proper status info."""
    loser = MagicMock(spec=PositionGroup)
    loser.id = uuid.uuid4()
    loser.symbol = "BTC/USD"
    loser.unrealized_pnl_percent = Decimal("-10.0")
    loser.unrealized_pnl_usd = Decimal("-100.0")
    loser.risk_blocked = False
    loser.risk_skip_once = False
    loser.risk_timer_expires = datetime.utcnow() - timedelta(minutes=5)
    loser.pyramid_count = 1
    loser.max_pyramids = 1
    loser.filled_dca_legs = 1
    loser.total_dca_legs = 1
    loser.created_at = datetime.utcnow() - timedelta(hours=2)

    winner = MagicMock(spec=PositionGroup)
    winner.id = uuid.uuid4()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.unrealized_pnl_percent = Decimal("5.0")  # Winner is in profit
    winner.risk_blocked = False
    winner.risk_timer_expires = None

    mock_pos_repo = MagicMock()
    mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[loser, winner])
    mock_pos_repo.get_all = AsyncMock(return_value=[loser, winner])
    mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0.0"))

    mock_risk_repo = MagicMock()
    mock_risk_repo.get_recent_by_user = AsyncMock(return_value=[])

    mock_session = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with (
        patch("app.services.exchange_abstraction.factory.EncryptionService"),
        patch("app.services.risk.risk_engine.select_loser_and_winners") as mock_select,
        patch("app.services.risk.risk_engine._check_pyramids_complete", return_value=True)
    ):
        mock_select.return_value = (loser, [winner], Decimal("100.0"))

        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(return_value=mock_pos_repo),
            risk_action_repository_class=MagicMock(return_value=mock_risk_repo),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            user=mock_user
        )

        result = await service.get_current_status()

        assert result["identified_loser"] is not None
        assert result["identified_loser"]["symbol"] == "BTC/USD"
        assert len(result["identified_winners"]) == 1
        assert result["required_offset_usd"] == 100.0
        assert result["risk_engine_running"] is False


@pytest.mark.asyncio
async def test_get_current_status_no_loser(mock_config, mock_user):
    """Test get_current_status when no loser is found."""
    winner = MagicMock(spec=PositionGroup)
    winner.id = uuid.uuid4()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.unrealized_pnl_percent = Decimal("5.0")

    mock_pos_repo = MagicMock()
    mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[winner])
    mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0.0"))

    mock_risk_repo = MagicMock()
    mock_risk_repo.get_recent_by_user = AsyncMock(return_value=[])

    mock_session = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with (
        patch("app.services.exchange_abstraction.factory.EncryptionService"),
        patch("app.services.risk_engine.select_loser_and_winners") as mock_select,
        patch("app.services.risk_engine._filter_eligible_losers", return_value=[])
    ):
        mock_select.return_value = (None, [], Decimal("0"))

        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(return_value=mock_pos_repo),
            risk_action_repository_class=MagicMock(return_value=mock_risk_repo),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            user=mock_user
        )

        result = await service.get_current_status()

        assert result["identified_loser"] is None
        assert result["identified_winners"] == []


@pytest.mark.asyncio
async def test_run_single_evaluation_with_user(mock_config, mock_user):
    """Test run_single_evaluation triggers evaluation for specific user."""
    mock_session = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            user=mock_user
        )

        with patch.object(service, '_evaluate_user_positions', new=AsyncMock()) as mock_eval:
            result = await service.run_single_evaluation()
            mock_eval.assert_called_once()
            assert result["status"] == "Risk evaluation completed"


@pytest.mark.asyncio
async def test_run_single_evaluation_without_user(mock_config):
    """Test run_single_evaluation triggers global evaluation."""
    mock_session = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=mock_session_factory,
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config,
            user=None  # No user context
        )

        with patch.object(service, '_evaluate_positions', new=AsyncMock()) as mock_eval:
            result = await service.run_single_evaluation()
            mock_eval.assert_called_once()
            assert result["status"] == "Risk evaluation completed"


@pytest.mark.asyncio
async def test_evaluate_on_fill_event_enabled(mock_config, mock_user):
    """Test evaluate_on_fill_event when enabled."""
    mock_config.evaluate_on_fill = True
    mock_session = AsyncMock()

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=MagicMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        with patch.object(service, '_evaluate_user_positions', new=AsyncMock()) as mock_eval:
            await service.evaluate_on_fill_event(mock_user, mock_session)
            mock_eval.assert_called_once_with(mock_session, mock_user)


@pytest.mark.asyncio
async def test_evaluate_on_fill_event_disabled(mock_config, mock_user):
    """Test evaluate_on_fill_event when disabled."""
    mock_config.evaluate_on_fill = False
    mock_session = AsyncMock()

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=MagicMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        with patch.object(service, '_evaluate_user_positions', new=AsyncMock()) as mock_eval:
            await service.evaluate_on_fill_event(mock_user, mock_session)
            mock_eval.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_on_fill_event_error_handling(mock_config, mock_user):
    """Test evaluate_on_fill_event handles errors gracefully."""
    mock_config.evaluate_on_fill = True
    mock_session = AsyncMock()

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=MagicMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        with patch.object(service, '_evaluate_user_positions', side_effect=Exception("Test error")):
            # Should not raise
            await service.evaluate_on_fill_event(mock_user, mock_session)


def test_get_exchange_connector_for_user_multi_key(mock_config, mock_user):
    """Test _get_exchange_connector_for_user with multi-key format."""
    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=MagicMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        with patch("app.services.risk.risk_engine.get_exchange_connector") as mock_connector:
            mock_connector.return_value = MagicMock()
            result = service._get_exchange_connector_for_user(mock_user, "binance")
            mock_connector.assert_called_once()


def test_get_exchange_connector_for_user_missing_exchange(mock_config):
    """Test _get_exchange_connector_for_user with missing exchange keys."""
    user = MagicMock()
    user.encrypted_api_keys = {"binance": {"encrypted_data": "key"}}  # Only binance

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=MagicMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        with pytest.raises(ValueError, match="No API keys found"):
            service._get_exchange_connector_for_user(user, "bybit")


def test_get_exchange_connector_for_user_legacy_string_format(mock_config):
    """Test _get_exchange_connector_for_user with legacy string format."""
    user = MagicMock()
    user.encrypted_api_keys = "legacy_encrypted_string"

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=MagicMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        with patch("app.services.risk.risk_engine.get_exchange_connector") as mock_connector:
            mock_connector.return_value = MagicMock()
            result = service._get_exchange_connector_for_user(user, "binance")
            mock_connector.assert_called_once_with("binance", {"encrypted_data": "legacy_encrypted_string"})


def test_get_exchange_connector_for_user_invalid_format(mock_config):
    """Test _get_exchange_connector_for_user with invalid format."""
    user = MagicMock()
    user.encrypted_api_keys = 12345  # Invalid format

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        service = RiskEngineService(
            session_factory=MagicMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        with pytest.raises(ValueError, match="Invalid format"):
            service._get_exchange_connector_for_user(user, "binance")


@pytest.mark.asyncio
async def test_evaluate_positions_iterates_users(mock_config):
    """Test _evaluate_positions iterates through all active users."""
    user1 = MagicMock()
    user1.id = uuid.uuid4()
    user2 = MagicMock()
    user2.id = uuid.uuid4()

    mock_user_repo = MagicMock()
    mock_user_repo.get_all_active_users = AsyncMock(return_value=[user1, user2])

    mock_session = AsyncMock()

    async def mock_session_factory():
        yield mock_session

    with patch("app.services.exchange_abstraction.factory.EncryptionService"):
        with patch("app.services.risk.risk_engine.UserRepository", return_value=mock_user_repo):
            service = RiskEngineService(
                session_factory=mock_session_factory,
                position_group_repository_class=MagicMock(),
                risk_action_repository_class=MagicMock(),
                dca_order_repository_class=MagicMock(),
                order_service_class=MagicMock(),
                risk_engine_config=mock_config
            )

            with patch.object(service, '_evaluate_user_positions', new=AsyncMock()) as mock_eval:
                await service._evaluate_positions()
                assert mock_eval.call_count == 2


@pytest.mark.asyncio
async def test_evaluate_user_positions_no_loser(mock_config, mock_user):
    """Test _evaluate_user_positions when no eligible loser found."""
    mock_session = AsyncMock()

    mock_pos_repo = MagicMock()
    mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[])

    with (
        patch("app.services.exchange_abstraction.factory.EncryptionService"),
        patch("app.services.risk_engine.select_loser_and_winners", return_value=(None, [], Decimal("0")))
    ):
        service = RiskEngineService(
            session_factory=MagicMock(),
            position_group_repository_class=MagicMock(return_value=mock_pos_repo),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )

        # Should complete without placing any orders
        await service._evaluate_user_positions(mock_session, mock_user)


def test_select_top_winners():
    """Test _select_top_winners helper function."""
    from app.services.risk_engine import _select_top_winners

    winner1 = MagicMock()
    winner1.status = PositionGroupStatus.ACTIVE.value
    winner1.unrealized_pnl_usd = Decimal("100")
    winner1.total_filled_quantity = Decimal("1.0")  # Required for filter

    winner2 = MagicMock()
    winner2.status = PositionGroupStatus.ACTIVE.value
    winner2.unrealized_pnl_usd = Decimal("200")
    winner2.total_filled_quantity = Decimal("1.0")  # Required for filter

    loser = MagicMock()
    loser.status = PositionGroupStatus.ACTIVE.value
    loser.unrealized_pnl_usd = Decimal("-50")
    loser.total_filled_quantity = Decimal("1.0")

    result = _select_top_winners([winner1, winner2, loser], 2)

    assert len(result) == 2
    assert result[0] == winner2  # Highest profit first
    assert result[1] == winner1


def test_select_loser_and_winners_no_eligible_losers(mock_config):
    """Test select_loser_and_winners when no positions are eligible."""
    position = MagicMock()
    position.status = PositionGroupStatus.ACTIVE.value
    position.unrealized_pnl_percent = Decimal("5.0")  # In profit, not a loser
    position.unrealized_pnl_usd = Decimal("50")
    position.pyramid_count = 1
    position.max_pyramids = 1
    position.filled_dca_legs = 1
    position.total_dca_legs = 1
    position.risk_timer_expires = datetime.utcnow() - timedelta(minutes=5)
    position.risk_blocked = False
    position.risk_skip_once = False
    position.created_at = datetime.utcnow() - timedelta(hours=2)

    loser, winners, required_usd = select_loser_and_winners([position], mock_config)

    assert loser is None
    assert winners == []
    assert required_usd == Decimal("0")


@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_long_position(mock_user):
    """Test calculate_partial_close_quantities for long positions.

    For SPOT trading: All positions are "long" (buy to enter, sell to exit).
    """
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.return_value = Decimal("100.0")  # Price went up
    exchange_connector.get_precision_rules.return_value = {
        "ETH/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("5.0")}
    }
    exchange_connector.close = AsyncMock()

    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.weighted_avg_entry = Decimal("90.0")  # Bought at 90
    winner.side = "long"  # Long position (spot trading)
    winner.total_filled_quantity = Decimal("10.0")
    winner.exchange = "binance"

    required_usd = Decimal("20.0")

    with (
        patch('app.services.risk.risk_executor.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncryptionService
    ):
        MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")
        plan = await calculate_partial_close_quantities(mock_user, [winner], required_usd)

    assert len(plan) == 1
    # Profit per unit for long = current - entry = 100 - 90 = 10
    # Qty = 20 / 10 = 2.0
    assert plan[0][1] == Decimal("2.00")


@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_skips_when_would_close_entire_position(mock_user):
    """Test that winner is skipped when calculation would close entire position.

    The risk executor protects winners by skipping them if the calculated
    quantity_to_close >= total_filled_quantity. This ensures we never
    fully close a winning position during offset.
    """
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.return_value = Decimal("100.0")
    exchange_connector.get_precision_rules.return_value = {
        "ETH/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("5.0")}
    }
    exchange_connector.close = AsyncMock()

    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("1000.0")  # Large profit
    winner.weighted_avg_entry = Decimal("90.0")
    winner.side = "long"
    winner.total_filled_quantity = Decimal("1.0")  # Only 1 unit available
    winner.exchange = "binance"

    required_usd = Decimal("500.0")  # Requires more than available profit

    with (
        patch('app.services.risk.risk_executor.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncryptionService
    ):
        MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")
        plan = await calculate_partial_close_quantities(mock_user, [winner], required_usd)

    # Winner is skipped because closing it entirely is not allowed
    # profit_per_unit = 100 - 90 = 10, qty = 500/10 = 50, but total_filled = 1
    assert len(plan) == 0, "Winner should be skipped when it would require closing entire position"


@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_price_fetch_error(mock_user):
    """Test handling of price fetch errors."""
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.side_effect = Exception("Price fetch failed")
    exchange_connector.get_precision_rules.return_value = {}
    exchange_connector.close = AsyncMock()

    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.exchange = "binance"

    with (
        patch('app.services.risk.risk_executor.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncryptionService
    ):
        MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")
        plan = await calculate_partial_close_quantities(mock_user, [winner], Decimal("20.0"))

    # Should return empty plan due to error
    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_connector_init_error(mock_user):
    """Test handling of exchange connector initialization errors."""
    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.exchange = "binance"

    with (
        patch('app.services.risk.risk_executor.get_exchange_connector', side_effect=Exception("Connector init failed")),
        patch('app.services.exchange_abstraction.factory.EncryptionService') as MockEncryptionService
    ):
        MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")
        plan = await calculate_partial_close_quantities(mock_user, [winner], Decimal("20.0"))

    # Should return empty plan due to error
    assert len(plan) == 0