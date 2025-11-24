
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
from app.services.risk_engine import RiskEngineService, _filter_eligible_losers, calculate_partial_close_quantities, select_loser_and_winners
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.queued_signal import QueuedSignal
from app.schemas.grid_config import RiskEngineConfig
from app.models.user import User

# --- Fixtures ---

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
async def test_calculate_partial_close_quantities_success():
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.return_value = Decimal("100.0")
    
    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.weighted_avg_entry = Decimal("90.0")
    winner.side = "long"
    winner.total_filled_quantity = Decimal("10.0")
    
    precision_rules = {
        "ETH/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("5.0")}
    }
    
    required_usd = Decimal("20.0")
    
    plan = await calculate_partial_close_quantities(
        exchange_connector, [winner], required_usd, precision_rules
    )
    
    assert len(plan) == 1
    # Profit per unit = 100 - 90 = 10.
    # Required = 20. Qty = 20 / 10 = 2.0.
    assert plan[0][1] == Decimal("2.00")

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_zero_profit_per_unit():
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.return_value = Decimal("90.0") # Same as entry
    
    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("50.0")
    winner.weighted_avg_entry = Decimal("90.0")
    winner.side = "long"
    
    precision_rules = {}
    required_usd = Decimal("20.0")
    
    plan = await calculate_partial_close_quantities(
        exchange_connector, [winner], required_usd, precision_rules
    )
    
    assert len(plan) == 0

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_below_min_notional():
    exchange_connector = AsyncMock()
    exchange_connector.get_current_price.return_value = Decimal("100.0")
    
    winner = MagicMock()
    winner.symbol = "ETH/USD"
    winner.unrealized_pnl_usd = Decimal("0.5") # Very small profit available
    winner.weighted_avg_entry = Decimal("90.0")
    winner.side = "long"
    
    precision_rules = {
        "ETH/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("10.0")}
    }
    
    required_usd = Decimal("0.5")
    
    # Profit per unit = 10. Qty = 0.5 / 10 = 0.05.
    # Notional = 0.05 * 100 = 5.0. Min notional = 10.0. Should skip.
    
    plan = await calculate_partial_close_quantities(
        exchange_connector, [winner], required_usd, precision_rules
    )
    
    assert len(plan) == 0

# --- Tests for validate_pre_trade_risk ---

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_checks(mock_config):
    service = RiskEngineService(
        session_factory=AsyncMock(),
        position_group_repository_class=MagicMock(),
        risk_action_repository_class=MagicMock(),
        dca_order_repository_class=MagicMock(),
        exchange_connector=MagicMock(),
        order_service_class=MagicMock(),
        risk_engine_config=mock_config
    )
    
    signal = QueuedSignal(user_id="u1", symbol="BTC/USD")
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
    active_positions = [MagicMock(symbol=f"S{i}", total_invested_usd=Decimal("10")) for i in range(5)]
    result = await service.validate_pre_trade_risk(
        signal, active_positions, Decimal("100.0"), session
    )
    assert result is False
    
    # 3. Max Symbol Positions
    active_positions = [MagicMock(symbol="BTC/USD", total_invested_usd=Decimal("10")) for _ in range(2)]
    result = await service.validate_pre_trade_risk(
        signal, active_positions, Decimal("100.0"), session
    )
    assert result is False

    # 4. Max Total Exposure
    active_positions = [MagicMock(symbol="BTC/USD", total_invested_usd=Decimal("950.0"))] # + 100 > 1000
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

