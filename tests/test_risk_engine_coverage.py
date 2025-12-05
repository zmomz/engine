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
        max_daily_loss_usd=100.0,
        loss_threshold_percent=Decimal("-5.0"),
        max_winners_to_combine=3,
        require_full_pyramids=True,
        use_trade_age_filter=True,
        age_threshold_minutes=60
    )

@pytest.fixture
def mock_position_group():
    pg = MagicMock(spec=PositionGroup)
    pg.status = PositionGroupStatus.ACTIVE.value
    pg.pyramid_count = 1
    pg.max_pyramids = 1
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

def test_filter_eligible_losers_incomplete_pyramid(mock_position_group, mock_config):
    mock_position_group.pyramid_count = 0
    mock_position_group.max_pyramids = 2
    mock_config.require_full_pyramids = True
    results = _filter_eligible_losers([mock_position_group], mock_config)
    assert len(results) == 0

def test_filter_eligible_losers_age_filter(mock_position_group, mock_config):
    mock_position_group.created_at = datetime.utcnow() - timedelta(minutes=10) # Less than 60
    mock_config.use_trade_age_filter = True
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
        patch('app.services.risk_engine.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.risk_engine.EncryptionService') as MockEncryptionService
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
        patch('app.services.risk_engine.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.risk_engine.EncryptionService') as MockEncryptionService
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
        patch('app.services.risk_engine.get_exchange_connector', return_value=exchange_connector),
        patch('app.services.risk_engine.EncryptionService') as MockEncryptionService
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
    # Patch EncryptionService globally for this test
    with patch("app.services.risk_engine.EncryptionService") as MockEncryptionService:
        MockEncryptionService.return_value.decrypt_keys.return_value = ("decrypted_key", "decrypted_secret")
        service = RiskEngineService(
            session_factory=AsyncMock(),
            position_group_repository_class=MagicMock(),
            risk_action_repository_class=MagicMock(),
            dca_order_repository_class=MagicMock(),
            order_service_class=MagicMock(),
            risk_engine_config=mock_config
        )
        
        signal = QueuedSignal(user_id=uuid.uuid4(), symbol="BTC/USD", exchange="binance") # Added user_id and exchange
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
        assert result is True
        
        # 2. Max Global Positions
        active_positions = [MagicMock(symbol=f"S{i}", total_invested_usd=Decimal("10"), exchange="binance") for i in range(5)]
        result = await service.validate_pre_trade_risk(
            signal, active_positions, Decimal("100.0"), session
        )
        assert result is False
        
        # 3. Max Symbol Positions
        active_positions = [MagicMock(symbol="BTC/USD", total_invested_usd=Decimal("10"), exchange="binance") for _ in range(2)]
        result = await service.validate_pre_trade_risk(
            signal, active_positions, Decimal("100.0"), session
        )
        assert result is False

        # 4. Max Total Exposure
        active_positions = [MagicMock(symbol="BTC/USD", total_invested_usd=Decimal("950.0"), exchange="binance")] # + 100 > 1000
        result = await service.validate_pre_trade_risk(
            signal, active_positions, Decimal("100.0"), session
        )
        assert result is False
        
        # 5. Daily Loss Limit
        active_positions = []
        pos_repo_mock.get_daily_realized_pnl = AsyncMock(return_value=Decimal("-150.0")) # Limit is 100
        result = await service.validate_pre_trade_risk(
            signal, active_positions, Decimal("100.0"), session
        )
        assert result is False

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
    
    loser = MagicMock(spec=PositionGroup)
    loser.id = uuid.uuid4()
    loser.symbol = "BTC/USD"
    loser.exchange = "binance"
    loser.unrealized_pnl_usd = Decimal("-100")
    loser.side = "long"
    loser.total_filled_quantity = Decimal("1.0")
    loser.user_id = user.id
    
    winner = MagicMock(spec=PositionGroup)
    winner.id = uuid.uuid4()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("200")
    winner.side = "long"
    winner.user_id = user.id
    winner.exchange = "binance" # Added exchange for mock_user
    
    # Mocks
    mock_pos_repo = MagicMock()
    mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[loser, winner])
    
    mock_risk_repo = MagicMock()
    mock_risk_repo.create = AsyncMock()
    
    mock_order_service = MagicMock()
    mock_order_service_instance = mock_order_service.return_value
    mock_order_service_instance.place_market_order = AsyncMock()
    
    mock_exchange = AsyncMock()
    mock_exchange.get_precision_rules = AsyncMock(return_value={})
    mock_exchange.close = AsyncMock() # Added here
    
    # Patch dependencies
    with (
        patch("app.services.risk_engine.select_loser_and_winners") as mock_select,
        patch("app.services.risk_engine.EncryptionService") as MockEncryptionService,
        patch("app.services.risk_engine.get_exchange_connector") as mock_get_connector,
        patch("app.services.risk_engine.calculate_partial_close_quantities") as mock_calc_close
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
        
        # Assertions
        mock_order_service_instance.place_market_order.assert_any_call(
            user_id=loser.user_id,
            exchange=loser.exchange,
            symbol=loser.symbol,
            side="sell",
            quantity=loser.total_filled_quantity,
            position_group_id=loser.id,
            record_in_db=True
        )
        
        mock_order_service_instance.place_market_order.assert_any_call(
            user_id=winner.user_id,
            exchange=winner.exchange,
            symbol=winner.symbol,
            side="sell",
            quantity=Decimal("0.5"),
            position_group_id=winner.id,
            record_in_db=True
        )
        
        mock_risk_repo.create.assert_called_once()
        session.commit.assert_called_once()