import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
import uuid
from datetime import datetime, timedelta

from app.services.risk_engine import (
    RiskEngineService,
    _check_pyramids_complete,
    _filter_eligible_losers,
    select_loser_and_winners,
    update_risk_timers
)
from app.models.queued_signal import QueuedSignal
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.schemas.grid_config import RiskEngineConfig


@pytest.fixture
def mock_risk_engine_service():
    risk_config = RiskEngineConfig(
        max_open_positions_global=2,
        max_open_positions_per_symbol=1,
        max_total_exposure_usd=Decimal("1000"),
        max_realized_loss_usd=Decimal("500"),
        required_pyramids_for_timer=3,
        loss_threshold_percent=Decimal("-1.5"),
        post_pyramids_wait_minutes=15
    )
    # Mock dependencies
    session_factory = MagicMock()

    # Mock repo class and instance
    position_group_repo_cls = MagicMock()
    position_group_repo_instance = MagicMock()
    position_group_repo_cls.return_value = position_group_repo_instance
    # Default behavior: 0 daily loss
    position_group_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

    risk_action_repo = MagicMock()
    dca_order_repo = MagicMock()
    exchange_connector = AsyncMock()
    order_service = MagicMock()

    service = RiskEngineService(
        session_factory=session_factory,
        position_group_repository_class=position_group_repo_cls,
        risk_action_repository_class=risk_action_repo,
        dca_order_repository_class=dca_order_repo,
        order_service_class=order_service,
        risk_engine_config=risk_config
    )
    return service


@pytest.fixture
def default_risk_config():
    return RiskEngineConfig(
        required_pyramids_for_timer=3,
        loss_threshold_percent=Decimal("-1.5"),
        post_pyramids_wait_minutes=15,
        max_winners_to_combine=3
    )


# --- Tests for _check_pyramids_complete ---

def test_check_pyramids_complete_true():
    """Test that pyramids are considered complete when all DCAs are filled."""
    pg = MagicMock()
    pg.pyramid_count = 3
    pg.filled_dca_legs = 9
    pg.total_dca_legs = 9

    assert _check_pyramids_complete(pg, required_pyramids=3) is True


def test_check_pyramids_complete_false_not_enough_pyramids():
    """Test that pyramids are incomplete when count is below requirement."""
    pg = MagicMock()
    pg.pyramid_count = 2
    pg.filled_dca_legs = 6
    pg.total_dca_legs = 6

    assert _check_pyramids_complete(pg, required_pyramids=3) is False


def test_check_pyramids_complete_false_dcas_not_filled():
    """Test that pyramids are incomplete when DCAs are not filled."""
    pg = MagicMock()
    pg.pyramid_count = 3
    pg.filled_dca_legs = 7
    pg.total_dca_legs = 9

    assert _check_pyramids_complete(pg, required_pyramids=3) is False


# --- Tests for _filter_eligible_losers ---

def test_filter_eligible_losers_returns_eligible(default_risk_config):
    """Test that eligible losers are returned."""
    now = datetime.utcnow()
    pg = MagicMock()
    pg.id = uuid.uuid4()
    pg.status = PositionGroupStatus.ACTIVE.value
    pg.pyramid_count = 3
    pg.filled_dca_legs = 9
    pg.total_dca_legs = 9
    pg.unrealized_pnl_percent = Decimal("-2.0")  # Below threshold
    pg.risk_blocked = False
    pg.risk_skip_once = False
    pg.risk_timer_expires = now - timedelta(minutes=1)  # Expired

    eligible = _filter_eligible_losers([pg], default_risk_config)
    assert len(eligible) == 1
    assert eligible[0].id == pg.id


def test_filter_eligible_losers_excludes_blocked(default_risk_config):
    """Test that blocked positions are excluded."""
    now = datetime.utcnow()
    pg = MagicMock()
    pg.status = PositionGroupStatus.ACTIVE.value
    pg.pyramid_count = 3
    pg.filled_dca_legs = 9
    pg.total_dca_legs = 9
    pg.unrealized_pnl_percent = Decimal("-2.0")
    pg.risk_blocked = True  # Blocked
    pg.risk_skip_once = False
    pg.risk_timer_expires = now - timedelta(minutes=1)

    eligible = _filter_eligible_losers([pg], default_risk_config)
    assert len(eligible) == 0


def test_filter_eligible_losers_excludes_timer_not_expired(default_risk_config):
    """Test that positions with active timer are excluded."""
    now = datetime.utcnow()
    pg = MagicMock()
    pg.status = PositionGroupStatus.ACTIVE.value
    pg.pyramid_count = 3
    pg.filled_dca_legs = 9
    pg.total_dca_legs = 9
    pg.unrealized_pnl_percent = Decimal("-2.0")
    pg.risk_blocked = False
    pg.risk_skip_once = False
    pg.risk_timer_expires = now + timedelta(minutes=10)  # Not expired

    eligible = _filter_eligible_losers([pg], default_risk_config)
    assert len(eligible) == 0


def test_filter_eligible_losers_excludes_loss_above_threshold(default_risk_config):
    """Test that positions above loss threshold are excluded."""
    now = datetime.utcnow()
    pg = MagicMock()
    pg.status = PositionGroupStatus.ACTIVE.value
    pg.pyramid_count = 3
    pg.filled_dca_legs = 9
    pg.total_dca_legs = 9
    pg.unrealized_pnl_percent = Decimal("-1.0")  # Above threshold (-1.5)
    pg.risk_blocked = False
    pg.risk_skip_once = False
    pg.risk_timer_expires = now - timedelta(minutes=1)

    eligible = _filter_eligible_losers([pg], default_risk_config)
    assert len(eligible) == 0


# --- Tests for select_loser_and_winners ---

def test_select_loser_and_winners(default_risk_config):
    """Test selection of loser and winners."""
    now = datetime.utcnow()

    # Loser
    loser = MagicMock()
    loser.id = uuid.uuid4()
    loser.status = PositionGroupStatus.ACTIVE.value
    loser.pyramid_count = 3
    loser.filled_dca_legs = 9
    loser.total_dca_legs = 9
    loser.unrealized_pnl_percent = Decimal("-2.0")
    loser.unrealized_pnl_usd = Decimal("-100")
    loser.risk_blocked = False
    loser.risk_skip_once = False
    loser.risk_timer_expires = now - timedelta(minutes=1)
    loser.created_at = now - timedelta(hours=1)

    # Winner - must include total_filled_quantity for _select_top_winners filter
    winner = MagicMock()
    winner.id = uuid.uuid4()
    winner.status = PositionGroupStatus.ACTIVE.value
    winner.unrealized_pnl_usd = Decimal("150")
    winner.total_filled_quantity = Decimal("1.0")  # Required for winner selection

    selected_loser, selected_winners, required_usd = select_loser_and_winners(
        [loser, winner], default_risk_config
    )

    assert selected_loser.id == loser.id
    assert len(selected_winners) == 1
    assert selected_winners[0].id == winner.id
    assert required_usd == Decimal("100")


# --- Tests for validate_pre_trade_risk ---

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_pass(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4())
    active_positions = []  # No active positions
    allocated_capital = Decimal("100")
    session = AsyncMock()

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is True
    assert reason is None

    # CRITICAL: Verify the service config state allows trading
    assert mock_risk_engine_service.config.engine_force_stopped is False, \
        "Engine must not be force stopped for trade to pass"
    assert mock_risk_engine_service.config.engine_paused_by_loss_limit is False, \
        "Engine must not be paused for trade to pass"


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_max_exposure(mock_risk_engine_service):
    """Test that max exposure limit is enforced by validate_pre_trade_risk.

    Note: max_open_positions_global check is now handled by ExecutionPoolManager,
    so we test max_total_exposure_usd instead.
    """
    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4())
    # Mock active positions with exposure near the limit (1000)
    active_positions = [
        PositionGroup(symbol="ETHUSDT", total_invested_usd=Decimal("900")),
    ]
    # This would exceed the 1000 limit
    allocated_capital = Decimal("200")
    session = AsyncMock()

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is False
    assert "Max exposure" in reason

    # CRITICAL: Verify exposure calculation
    current_exposure = sum(p.total_invested_usd for p in active_positions)
    max_allowed = mock_risk_engine_service.config.max_total_exposure_usd
    assert (current_exposure + allocated_capital) > max_allowed, \
        f"Test precondition: exposure ({current_exposure + allocated_capital}) must exceed max ({max_allowed})"


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_max_symbol_timeframe_exchange(mock_risk_engine_service):
    """Test that max position limit is per symbol/timeframe/exchange combination."""
    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4(), timeframe=60, exchange="binance")
    # Mock 1 active position for BTCUSDT/60/binance (limit is 1)
    active_positions = [
        PositionGroup(symbol="BTCUSDT", timeframe=60, exchange="binance", total_invested_usd=Decimal("100"))
    ]
    allocated_capital = Decimal("100")
    session = AsyncMock()

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is False
    assert "BTCUSDT/60m/binance" in reason

    # CRITICAL: Verify symbol/timeframe/exchange limit was enforced
    matching_positions = [
        p for p in active_positions
        if p.symbol == signal.symbol and p.timeframe == signal.timeframe and p.exchange.lower() == signal.exchange.lower()
    ]
    max_per_symbol = mock_risk_engine_service.config.max_open_positions_per_symbol
    assert len(matching_positions) >= max_per_symbol, \
        f"Test precondition: positions for {signal.symbol}/{signal.timeframe}/{signal.exchange} ({len(matching_positions)}) must be >= max ({max_per_symbol})"


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_pass_different_timeframe(mock_risk_engine_service):
    """Test that same symbol with different timeframe is allowed."""
    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4(), timeframe=15, exchange="binance")
    # Existing position is BTCUSDT/60/binance - different timeframe
    active_positions = [
        PositionGroup(symbol="BTCUSDT", timeframe=60, exchange="binance", total_invested_usd=Decimal("100"))
    ]
    allocated_capital = Decimal("100")
    session = AsyncMock()

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is True
    assert reason is None


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_pass_different_exchange(mock_risk_engine_service):
    """Test that same symbol/timeframe with different exchange is allowed."""
    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4(), timeframe=60, exchange="bybit")
    # Existing position is BTCUSDT/60/binance - different exchange
    active_positions = [
        PositionGroup(symbol="BTCUSDT", timeframe=60, exchange="binance", total_invested_usd=Decimal("100"))
    ]
    allocated_capital = Decimal("100")
    session = AsyncMock()

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is True
    assert reason is None


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_pass_pyramid(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4(), timeframe=60, exchange="binance")
    # Mock 1 active position for BTCUSDT/60/binance (limit is 1)
    active_positions = [
        PositionGroup(symbol="BTCUSDT", timeframe=60, exchange="binance", total_invested_usd=Decimal("100"))
    ]
    allocated_capital = Decimal("100")
    session = AsyncMock()

    # Should pass because it is a pyramid continuation (bypasses symbol/timeframe/exchange limit)
    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session, is_pyramid_continuation=True
    )
    assert result is True


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_exposure(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4())
    # Mock active positions with 900 exposure (limit is 1000)
    active_positions = [
        PositionGroup(symbol="ETHUSDT", total_invested_usd=Decimal("900"))
    ]
    # Requesting 200 more would exceed 1000
    allocated_capital = Decimal("200")
    session = AsyncMock()

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is False
    assert "Max exposure" in reason


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_realized_loss(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4())
    active_positions = []
    allocated_capital = Decimal("100")
    session = AsyncMock()

    # Mock realized loss of -600 (limit is 500)
    repo_instance = mock_risk_engine_service.position_group_repository_class(session)
    repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("-600"))

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is False
    assert "Max realized loss" in reason


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_engine_stopped(mock_risk_engine_service):
    """Test that validation fails when engine is force stopped."""
    mock_risk_engine_service.config.engine_force_stopped = True

    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4())
    active_positions = []
    allocated_capital = Decimal("100")
    session = AsyncMock()

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is False
    assert "force stopped" in reason


@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_engine_paused(mock_risk_engine_service):
    """Test that validation fails when engine is paused by loss limit."""
    mock_risk_engine_service.config.engine_paused_by_loss_limit = True

    signal = QueuedSignal(symbol="BTCUSDT", side="long", user_id=uuid.uuid4())
    active_positions = []
    allocated_capital = Decimal("100")
    session = AsyncMock()

    result, reason = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, session
    )
    assert result is False
    assert "paused" in reason