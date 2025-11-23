import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta
import uuid

from app.services.risk_engine import RiskEngineService, select_loser_and_winners, calculate_partial_close_quantities
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.queued_signal import QueuedSignal
from app.schemas.grid_config import RiskEngineConfig

# --- Fixtures ---

@pytest.fixture
def mock_config():
    return RiskEngineConfig(
        max_open_positions_global=2,
        max_open_positions_per_symbol=1,
        max_total_exposure_usd=1000.0,
        max_daily_loss_usd=500.0,
        loss_threshold_percent=-5.0,  # -5% loss triggers offset
        max_winners_to_combine=2,
        min_close_notional=10.0,
        require_full_pyramids=False # Simplified for testing
    )

@pytest.fixture
def risk_service(mock_config):
    return RiskEngineService(
        session_factory=AsyncMock(),
        position_group_repository_class=MagicMock(),
        risk_action_repository_class=MagicMock(),
        dca_order_repository_class=MagicMock(),
        exchange_connector=AsyncMock(),
        order_service_class=MagicMock(),
        risk_engine_config=mock_config,
        polling_interval_seconds=1
    )

@pytest.fixture
def mock_positions():
    p1 = PositionGroup(
        id=uuid.uuid4(),
        symbol="BTC/USD",
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        unrealized_pnl_percent=Decimal("-6.0"),
        unrealized_pnl_usd=Decimal("-60.0"),
        created_at=datetime.utcnow() - timedelta(hours=2),
        risk_timer_expires=datetime.utcnow() - timedelta(minutes=1),
        total_invested_usd=Decimal("1000.0"),
        total_filled_quantity=Decimal("0.1"),
        weighted_avg_entry=Decimal("10000.0"),
        risk_blocked=False,
        risk_skip_once=False,
        pyramid_count=5,
        max_pyramids=5,
        exchange="binance",
        user_id="user1"
    )
    p2 = PositionGroup(
        id=uuid.uuid4(),
        symbol="ETH/USD",
        side="short",
        status=PositionGroupStatus.ACTIVE.value,
        unrealized_pnl_percent=Decimal("3.0"),
        unrealized_pnl_usd=Decimal("90.0"),
        created_at=datetime.utcnow() - timedelta(hours=1),
        risk_timer_expires=datetime.utcnow() - timedelta(minutes=1),
        total_invested_usd=Decimal("3000.0"),
        total_filled_quantity=Decimal("1.0"),
        weighted_avg_entry=Decimal("3000.0"),
        risk_blocked=False,
        risk_skip_once=False,
        exchange="binance",
        user_id="user1"
    )
    return [p1, p2]

# --- Test Cases: Pre-Trade Risk Validation ---

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_max_global(risk_service, mock_config):
    """Test rejection when max global positions are exceeded."""
    active_positions = [MagicMock(), MagicMock()] # 2 positions
    # Config max is 2
    
    signal = QueuedSignal(symbol="SOL/USD", user_id="user1")
    
    result = await risk_service.validate_pre_trade_risk(
        signal, active_positions, Decimal("100"), AsyncMock(), is_pyramid_continuation=False
    )
    assert result is False

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_max_per_symbol(risk_service):
    """Test rejection when max positions per symbol are exceeded."""
    p1 = MagicMock(symbol="BTC/USD")
    active_positions = [p1]
    # Config max per symbol is 1
    
    signal = QueuedSignal(symbol="BTC/USD", user_id="user1")
    
    result = await risk_service.validate_pre_trade_risk(
        signal, active_positions, Decimal("100"), AsyncMock(), is_pyramid_continuation=False
    )
    assert result is False

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_max_exposure(risk_service):
    """Test rejection when total exposure limit is exceeded."""
    p1 = MagicMock(total_invested_usd=Decimal("950"))
    active_positions = [p1]
    # Config max exposure is 1000
    
    signal = QueuedSignal(symbol="SOL/USD", user_id="user1")
    
    # 950 + 100 = 1050 > 1000
    result = await risk_service.validate_pre_trade_risk(
        signal, active_positions, Decimal("100"), AsyncMock(), is_pyramid_continuation=False
    )
    assert result is False

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_daily_loss(risk_service):
    """Test rejection when daily loss limit is hit."""
    active_positions = []
    signal = QueuedSignal(symbol="SOL/USD", user_id="user1")
    
    # Mock repo call
    mock_session = AsyncMock()
    mock_repo = risk_service.position_group_repository_class.return_value
    mock_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("-600")) # Loss > 500
    
    result = await risk_service.validate_pre_trade_risk(
        signal, active_positions, Decimal("100"), mock_session, is_pyramid_continuation=False
    )
    assert result is False

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_pyramid_bypass(risk_service):
    """Test that pyramid continuations bypass position count limits."""
    # 2 positions (Limit reached), but low exposure so we pass that check
    p1 = MagicMock(total_invested_usd=Decimal("10"))
    p2 = MagicMock(total_invested_usd=Decimal("10"))
    active_positions = [p1, p2] 
    
    signal = QueuedSignal(symbol="BTC/USD", user_id="user1")
    
    # Max global positions reached, but is_pyramid_continuation=True
    # Mock daily loss to pass
    mock_repo = risk_service.position_group_repository_class.return_value
    mock_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

    result = await risk_service.validate_pre_trade_risk(
        signal, active_positions, Decimal("100"), AsyncMock(), is_pyramid_continuation=True
    )
    # Should only check exposure and daily loss, which pass here
    
    assert result is True

# --- Test Cases: Loser/Winner Selection (Pure Logic) ---

def test_select_loser_identifies_correct_loser(mock_config, mock_positions):
    """Verify correct identification of loser based on loss % threshold."""
    loser, winners, req_usd = select_loser_and_winners(mock_positions, mock_config)
    
    assert loser is not None
    assert loser.symbol == "BTC/USD"
    assert loser.unrealized_pnl_percent == Decimal("-6.0") # Exceeds -5.0
    assert req_usd == Decimal("60.0") # Matches loss USD
    assert len(winners) == 1
    assert winners[0].symbol == "ETH/USD"

def test_select_loser_respects_risk_timer(mock_config, mock_positions):
    """Verify loser is IGNORED if risk timer hasn't expired."""
    mock_positions[0].risk_timer_expires = datetime.utcnow() + timedelta(minutes=10) # Future
    
    loser, _, _ = select_loser_and_winners(mock_positions, mock_config)
    assert loser is None

def test_select_loser_respects_blocked_flag(mock_config, mock_positions):
    """Verify loser is IGNORED if manually blocked."""
    mock_positions[0].risk_blocked = True
    
    loser, _, _ = select_loser_and_winners(mock_positions, mock_config)
    assert loser is None

def test_select_loser_sorting_logic(mock_config):
    """Verify losers are sorted by Loss % -> Loss $ -> Age."""
    p1 = PositionGroup(
        id=uuid.uuid4(), symbol="A", status="active", unrealized_pnl_percent=Decimal("-7.0"), unrealized_pnl_usd=Decimal("-50"),
        created_at=datetime.utcnow(), risk_timer_expires=datetime.min, risk_blocked=False, risk_skip_once=False
    )
    p2 = PositionGroup(
        id=uuid.uuid4(), symbol="B", status="active", unrealized_pnl_percent=Decimal("-8.0"), unrealized_pnl_usd=Decimal("-40"),
        created_at=datetime.utcnow(), risk_timer_expires=datetime.min, risk_blocked=False, risk_skip_once=False
    )
    
    # P2 has higher loss % (-8 vs -7)
    loser, _, _ = select_loser_and_winners([p1, p2], mock_config)
    assert loser.symbol == "B"

# --- Test Cases: Offset Calculation ---

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_exact_coverage():
    """Test calculating closure amount when winner has enough profit."""
    winner = PositionGroup(
        id=uuid.uuid4(), symbol="ETH/USD", side="short",
        unrealized_pnl_usd=Decimal("100.0"), weighted_avg_entry=Decimal("3000.0"), exchange="binance"
    )
    
    exchange = AsyncMock()
    # Current price 2900 (Short profit = 3000 - 2900 = 100 per unit)
    exchange.get_current_price.return_value = Decimal("2900.0") 
    
    # Need 50 USD. Profit per unit is 100. Expect 0.5 units close.
    required_usd = Decimal("50.0")
    precision_rules = {"ETH/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("10")}}
    
    plan = await calculate_partial_close_quantities(exchange, [winner], required_usd, precision_rules)
    
    assert len(plan) == 1
    pg, qty = plan[0]
    assert pg.symbol == "ETH/USD"
    assert qty == Decimal("0.50")

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_insufficient_winner():
    """Test draining first winner and moving to second."""
    w1 = PositionGroup(
        id=uuid.uuid4(), symbol="ETH/USD", side="long",
        unrealized_pnl_usd=Decimal("40.0"), weighted_avg_entry=Decimal("1000.0"), exchange="binance"
    ) # Profit 40
    w2 = PositionGroup(
        id=uuid.uuid4(), symbol="BTC/USD", side="long",
        unrealized_pnl_usd=Decimal("100.0"), weighted_avg_entry=Decimal("10000.0"), exchange="binance"
    ) # Profit 100
    
    exchange = AsyncMock()
    # W1 Price: 1100 (Profit/unit = 100). To get 40, close 0.4
    # W2 Price: 11000 (Profit/unit = 1000). Needed remaining: 60 - 40 = 20. Close 0.02
    exchange.get_current_price.side_effect = [Decimal("1100.0"), Decimal("11000.0")]
    
    required_usd = Decimal("60.0")
    precision_rules = {
        "ETH/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("10")},
        "BTC/USD": {"step_size": Decimal("0.01"), "min_notional": Decimal("10")}
    }
    
    plan = await calculate_partial_close_quantities(exchange, [w1, w2], required_usd, precision_rules)
    
    assert len(plan) == 2
    assert plan[0][0].symbol == "ETH/USD"
    assert plan[0][1] == Decimal("0.40") # Takes all 40 USD profit
    
    assert plan[1][0].symbol == "BTC/USD"
    assert plan[1][1] == Decimal("0.02") # Takes remaining 20 USD profit

@pytest.mark.asyncio
async def test_calculate_partial_close_min_notional_skip():
    """Test skipping a winner if the calculated close quantity is too small."""
    winner = PositionGroup(
        id=uuid.uuid4(), symbol="DOGE/USD", side="long",
        unrealized_pnl_usd=Decimal("1.0"), weighted_avg_entry=Decimal("0.10"), exchange="binance"
    )
    
    exchange = AsyncMock()
    exchange.get_current_price.return_value = Decimal("0.11") # Profit 0.01 per unit
    
    # Need 0.5 USD. Qty = 0.5 / 0.01 = 50 units.
    # Notional = 50 * 0.11 = 5.5 USD.
    # Min notional is 10 USD. Should skip.
    
    required_usd = Decimal("0.5")
    precision_rules = {"DOGE/USD": {"step_size": Decimal("1"), "min_notional": Decimal("10")}}
    
    plan = await calculate_partial_close_quantities(exchange, [winner], required_usd, precision_rules)
    
    assert len(plan) == 0
