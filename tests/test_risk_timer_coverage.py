"""
Comprehensive tests for services/risk/risk_timer.py to achieve 100% coverage.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
import uuid

from app.services.risk.risk_timer import update_risk_timers
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.schemas.grid_config import RiskEngineConfig


@pytest.fixture
def mock_config():
    return RiskEngineConfig(
        max_open_positions_global=5,
        max_open_positions_per_symbol=2,
        max_total_exposure_usd=10000.0,
        max_realized_loss_usd=500.0,
        loss_threshold_percent=Decimal("-5.0"),
        max_winners_to_combine=3,
        required_pyramids_for_timer=2,
        post_pyramids_wait_minutes=15
    )


@pytest.fixture
def mock_position_group():
    """Create a mock position group."""
    pg = MagicMock(spec=PositionGroup)
    pg.id = uuid.uuid4()
    pg.symbol = "BTCUSDT"
    pg.status = PositionGroupStatus.ACTIVE.value
    pg.pyramid_count = 2
    pg.max_pyramids = 3
    pg.filled_dca_legs = 3
    pg.total_dca_legs = 3
    pg.unrealized_pnl_percent = Decimal("-6.0")
    pg.unrealized_pnl_usd = Decimal("-60.0")
    pg.risk_timer_start = None
    pg.risk_timer_expires = None
    pg.risk_eligible = False
    return pg


@pytest.mark.asyncio
async def test_update_risk_timers_skip_non_active(mock_config):
    """Test that non-active positions are skipped."""
    pg = MagicMock(spec=PositionGroup)
    pg.status = PositionGroupStatus.CLOSED.value
    pg.risk_timer_start = None

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock):
        await update_risk_timers([pg], mock_config, session)

    # Timer should not be touched
    assert pg.risk_timer_start is None


@pytest.mark.asyncio
async def test_update_risk_timers_start_timer(mock_config, mock_position_group):
    """Test that timer starts when both conditions are met."""
    mock_position_group.risk_timer_start = None
    mock_position_group.risk_timer_expires = None

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=True):
        await update_risk_timers([mock_position_group], mock_config, session)

    # Timer should have started
    assert mock_position_group.risk_timer_start is not None
    assert mock_position_group.risk_timer_expires is not None
    assert mock_position_group.risk_eligible is False
    mock_broadcast.assert_called_once()
    assert mock_broadcast.call_args[1]["event_type"] == "timer_started"


@pytest.mark.asyncio
async def test_update_risk_timers_timer_expires(mock_config, mock_position_group):
    """Test that position becomes eligible when timer expires."""
    now = datetime.utcnow()
    mock_position_group.risk_timer_start = now - timedelta(minutes=20)
    mock_position_group.risk_timer_expires = now - timedelta(minutes=5)  # Already expired
    mock_position_group.risk_eligible = False

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=True):
        await update_risk_timers([mock_position_group], mock_config, session)

    # Should now be eligible
    assert mock_position_group.risk_eligible is True
    mock_broadcast.assert_called_once()
    assert mock_broadcast.call_args[1]["event_type"] == "timer_expired"


@pytest.mark.asyncio
async def test_update_risk_timers_timer_already_eligible(mock_config, mock_position_group):
    """Test that broadcast is not sent if already eligible."""
    now = datetime.utcnow()
    mock_position_group.risk_timer_start = now - timedelta(minutes=20)
    mock_position_group.risk_timer_expires = now - timedelta(minutes=5)
    mock_position_group.risk_eligible = True  # Already eligible

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=True):
        await update_risk_timers([mock_position_group], mock_config, session)

    # Should not broadcast again
    mock_broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_update_risk_timers_timer_running_not_expired(mock_config, mock_position_group):
    """Test that timer running but not yet expired does nothing."""
    now = datetime.utcnow()
    mock_position_group.risk_timer_start = now - timedelta(minutes=5)
    mock_position_group.risk_timer_expires = now + timedelta(minutes=10)  # Still running
    mock_position_group.risk_eligible = False

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=True):
        await update_risk_timers([mock_position_group], mock_config, session)

    # Should not be eligible yet
    assert mock_position_group.risk_eligible is False
    mock_broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_update_risk_timers_reset_pyramids_incomplete(mock_config, mock_position_group):
    """Test that timer resets when pyramids become incomplete."""
    now = datetime.utcnow()
    mock_position_group.risk_timer_start = now - timedelta(minutes=5)
    mock_position_group.risk_timer_expires = now + timedelta(minutes=10)
    mock_position_group.risk_eligible = False
    mock_position_group.pyramid_count = 1  # Less than required

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=False):
        await update_risk_timers([mock_position_group], mock_config, session)

    # Timer should be reset
    assert mock_position_group.risk_timer_start is None
    assert mock_position_group.risk_timer_expires is None
    assert mock_position_group.risk_eligible is False
    mock_broadcast.assert_called_once()
    assert mock_broadcast.call_args[1]["event_type"] == "timer_reset"


@pytest.mark.asyncio
async def test_update_risk_timers_reset_loss_improved(mock_config, mock_position_group):
    """Test that timer resets when loss improves above threshold."""
    now = datetime.utcnow()
    mock_position_group.risk_timer_start = now - timedelta(minutes=5)
    mock_position_group.risk_timer_expires = now + timedelta(minutes=10)
    mock_position_group.unrealized_pnl_percent = Decimal("-2.0")  # Better than -5% threshold

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=True):
        await update_risk_timers([mock_position_group], mock_config, session)

    # Timer should be reset
    assert mock_position_group.risk_timer_start is None
    assert mock_position_group.risk_timer_expires is None
    mock_broadcast.assert_called_once()
    assert mock_broadcast.call_args[1]["event_type"] == "timer_reset"


@pytest.mark.asyncio
async def test_update_risk_timers_no_timer_conditions_not_met(mock_config, mock_position_group):
    """Test that timer doesn't start if conditions not met."""
    mock_position_group.risk_timer_start = None
    mock_position_group.unrealized_pnl_percent = Decimal("2.0")  # In profit

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=True):
        await update_risk_timers([mock_position_group], mock_config, session)

    # Timer should not have started
    assert mock_position_group.risk_timer_start is None
    mock_broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_update_risk_timers_reset_both_conditions_fail(mock_config, mock_position_group):
    """Test timer reset when both conditions fail."""
    now = datetime.utcnow()
    mock_position_group.risk_timer_start = now - timedelta(minutes=5)
    mock_position_group.risk_timer_expires = now + timedelta(minutes=10)
    mock_position_group.pyramid_count = 1  # Incomplete
    mock_position_group.unrealized_pnl_percent = Decimal("1.0")  # In profit

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=False):
        await update_risk_timers([mock_position_group], mock_config, session)

    # Timer should be reset
    assert mock_position_group.risk_timer_start is None
    mock_broadcast.assert_called_once()


@pytest.mark.asyncio
async def test_update_risk_timers_multiple_positions(mock_config):
    """Test processing multiple positions."""
    now = datetime.utcnow()

    # Position 1: Should start timer
    pg1 = MagicMock(spec=PositionGroup)
    pg1.id = uuid.uuid4()
    pg1.symbol = "BTCUSDT"
    pg1.status = PositionGroupStatus.ACTIVE.value
    pg1.pyramid_count = 2
    pg1.unrealized_pnl_percent = Decimal("-6.0")
    pg1.unrealized_pnl_usd = Decimal("-60.0")
    pg1.risk_timer_start = None
    pg1.risk_timer_expires = None
    pg1.risk_eligible = False

    # Position 2: Should expire
    pg2 = MagicMock(spec=PositionGroup)
    pg2.id = uuid.uuid4()
    pg2.symbol = "ETHUSDT"
    pg2.status = PositionGroupStatus.ACTIVE.value
    pg2.pyramid_count = 2
    pg2.unrealized_pnl_percent = Decimal("-7.0")
    pg2.unrealized_pnl_usd = Decimal("-70.0")
    pg2.risk_timer_start = now - timedelta(minutes=20)
    pg2.risk_timer_expires = now - timedelta(minutes=5)
    pg2.risk_eligible = False

    # Position 3: Non-active, should skip
    pg3 = MagicMock(spec=PositionGroup)
    pg3.status = PositionGroupStatus.CLOSING.value

    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast, \
         patch("app.services.risk.risk_timer._check_pyramids_complete", return_value=True):
        await update_risk_timers([pg1, pg2, pg3], mock_config, session)

    # pg1 should have timer started
    assert pg1.risk_timer_start is not None

    # pg2 should be eligible
    assert pg2.risk_eligible is True

    # Two broadcasts: timer_started and timer_expired
    assert mock_broadcast.call_count == 2


@pytest.mark.asyncio
async def test_update_risk_timers_empty_list(mock_config):
    """Test with empty position list."""
    session = AsyncMock()

    with patch("app.services.risk.risk_timer.broadcast_risk_event", new_callable=AsyncMock) as mock_broadcast:
        await update_risk_timers([], mock_config, session)

    mock_broadcast.assert_not_called()
