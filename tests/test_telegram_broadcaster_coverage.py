"""
Comprehensive tests for services/telegram_broadcaster.py to achieve 100% coverage.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
import uuid
import asyncio

from app.services.telegram_broadcaster import TelegramBroadcaster
from app.schemas.telegram_config import TelegramConfig
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.dca_order import DCAOrder, OrderStatus


@pytest.fixture
def telegram_config():
    """Create a test Telegram config."""
    return TelegramConfig(
        enabled=True,
        bot_token="test_bot_token",
        channel_id="@test_channel",
        send_entry_signals=True,
        send_exit_signals=True,
        send_dca_fill_updates=True,
        send_status_updates=True,
        send_tp_hit_updates=True,
        send_risk_alerts=True,
        send_failure_alerts=True,
        send_pyramid_updates=True,
        update_existing_message=True,
        show_invested_amount=True,
        show_unrealized_pnl=True,
        show_duration=True,
        quiet_hours_enabled=False,
        quiet_hours_urgent_only=False,
        test_mode=True
    )


@pytest.fixture
def position_group():
    """Create a test position group."""
    return PositionGroup(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        total_dca_legs=5,
        filled_dca_legs=3,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("49500"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("0.02"),
        unrealized_pnl_usd=Decimal("50"),
        unrealized_pnl_percent=Decimal("5"),
        realized_pnl_usd=Decimal("0"),
        tp_mode="aggregate",
        tp_aggregate_percent=Decimal("3"),
        pyramid_count=1,
        max_pyramids=3,
        created_at=datetime.utcnow() - timedelta(hours=2)
    )


@pytest.fixture
def pyramid():
    """Create a test pyramid."""
    return Pyramid(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_index=0,
        status=PyramidStatus.FILLED,
        entry_price=Decimal("50000"),
        dca_config={}
    )


@pytest.fixture
def dca_order():
    """Create a test DCA order."""
    return DCAOrder(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_id=uuid.uuid4(),
        leg_index=0,
        side="buy",
        price=Decimal("50000"),
        quantity=Decimal("0.01"),
        filled_quantity=Decimal("0.01"),
        status=OrderStatus.FILLED
    )


@pytest.fixture
def broadcaster(telegram_config):
    """Create a TelegramBroadcaster instance."""
    return TelegramBroadcaster(telegram_config)


# --- Tests for helper methods ---

def test_format_duration_none(broadcaster):
    """Test _format_duration with None."""
    assert broadcaster._format_duration(None) == "N/A"


def test_format_duration_minutes(broadcaster):
    """Test _format_duration with less than an hour."""
    assert broadcaster._format_duration(0.5) == "30m"


def test_format_duration_hours(broadcaster):
    """Test _format_duration with hours."""
    assert broadcaster._format_duration(2.5) == "2.5h"


def test_format_duration_days(broadcaster):
    """Test _format_duration with days."""
    assert broadcaster._format_duration(48) == "2.0d"


def test_format_price_none(broadcaster):
    """Test _format_price with None."""
    assert broadcaster._format_price(None) == "TBD"


def test_format_price_with_decimals(broadcaster):
    """Test _format_price with decimals."""
    result = broadcaster._format_price(Decimal("50000.5"), 2)
    assert result == "50,000.50"


def test_format_pnl_percent_only(broadcaster):
    """Test _format_pnl with percent only."""
    result = broadcaster._format_pnl(Decimal("5.5"))
    assert result == "+5.50%"


def test_format_pnl_with_usd(broadcaster):
    """Test _format_pnl with USD value."""
    result = broadcaster._format_pnl(Decimal("5.5"), Decimal("55"))
    assert "+5.50%" in result
    assert "+55.00" in result


def test_format_pnl_negative(broadcaster):
    """Test _format_pnl with negative percent."""
    result = broadcaster._format_pnl(Decimal("-3.5"), Decimal("-35"))
    assert "-3.50%" in result
    assert "-35.00" in result


def test_get_position_id_short(broadcaster, position_group):
    """Test _get_position_id_short returns first 8 chars."""
    result = broadcaster._get_position_id_short(position_group)
    assert len(result) == 8


def test_get_header(broadcaster, position_group):
    """Test _get_header returns formatted header."""
    result = broadcaster._get_header(position_group)
    assert "BINANCE" in result
    assert "BTCUSDT" in result
    assert "60m" in result


def test_get_duration_hours(broadcaster, position_group):
    """Test _get_duration_hours calculates correctly."""
    result = broadcaster._get_duration_hours(position_group)
    assert result is not None
    assert result > 0


def test_get_duration_hours_with_closed_at(broadcaster, position_group):
    """Test _get_duration_hours with closed_at set."""
    position_group.closed_at = datetime.utcnow()
    result = broadcaster._get_duration_hours(position_group)
    assert result is not None


def test_get_duration_hours_no_created_at(broadcaster, position_group):
    """Test _get_duration_hours when created_at is None."""
    position_group.created_at = None
    result = broadcaster._get_duration_hours(position_group)
    assert result is None


# --- Tests for quiet hours ---

def test_is_quiet_hours_disabled(broadcaster):
    """Test _is_quiet_hours when quiet hours disabled."""
    broadcaster.config.quiet_hours_enabled = False
    assert broadcaster._is_quiet_hours() is False


def test_is_quiet_hours_no_times_set(broadcaster):
    """Test _is_quiet_hours when times not set."""
    broadcaster.config.quiet_hours_enabled = True
    broadcaster.config.quiet_hours_start = None
    broadcaster.config.quiet_hours_end = None
    assert broadcaster._is_quiet_hours() is False


def test_is_quiet_hours_invalid_format(broadcaster):
    """Test _is_quiet_hours with invalid time format."""
    broadcaster.config.quiet_hours_enabled = True
    broadcaster.config.quiet_hours_start = "invalid"
    broadcaster.config.quiet_hours_end = "invalid"
    assert broadcaster._is_quiet_hours() is False


def test_is_quiet_hours_same_day_range(broadcaster):
    """Test _is_quiet_hours with same day range."""
    broadcaster.config.quiet_hours_enabled = True
    broadcaster.config.quiet_hours_start = "00:00"
    broadcaster.config.quiet_hours_end = "23:59"
    # Should be within quiet hours
    assert broadcaster._is_quiet_hours() is True


def test_should_send_not_quiet_hours(broadcaster):
    """Test _should_send when not in quiet hours."""
    broadcaster.config.quiet_hours_enabled = False
    assert broadcaster._should_send() is True


def test_should_send_urgent_during_quiet(broadcaster):
    """Test _should_send for urgent messages during quiet hours."""
    broadcaster.config.quiet_hours_enabled = True
    broadcaster.config.quiet_hours_start = "00:00"
    broadcaster.config.quiet_hours_end = "23:59"
    broadcaster.config.quiet_hours_urgent_only = True
    assert broadcaster._should_send(is_urgent=True) is True


def test_should_send_non_urgent_during_quiet(broadcaster):
    """Test _should_send for non-urgent messages during quiet hours."""
    broadcaster.config.quiet_hours_enabled = True
    broadcaster.config.quiet_hours_start = "00:00"
    broadcaster.config.quiet_hours_end = "23:59"
    broadcaster.config.quiet_hours_urgent_only = True
    assert broadcaster._should_send(is_urgent=False) is False


# --- Tests for calculate_tp_percent ---

def test_calculate_tp_percent(broadcaster):
    """Test _calculate_tp_percent calculation."""
    result = broadcaster._calculate_tp_percent(Decimal("100"), Decimal("103"))
    assert result == 3.0


def test_calculate_tp_percent_none_entry(broadcaster):
    """Test _calculate_tp_percent with None entry."""
    result = broadcaster._calculate_tp_percent(None, Decimal("103"))
    assert result == 0.0


def test_calculate_tp_percent_zero_entry(broadcaster):
    """Test _calculate_tp_percent with zero entry."""
    result = broadcaster._calculate_tp_percent(Decimal("0"), Decimal("103"))
    assert result == 0.0


# --- Tests for message builders ---

def test_build_entry_message(broadcaster, position_group, pyramid):
    """Test _build_entry_message."""
    entry_prices = [Decimal("50000"), Decimal("49500"), None]
    weights = [30, 40, 30]

    result = broadcaster._build_entry_message(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=entry_prices,
        weights=weights,
        filled_count=2,
        total_count=3,
        tp_mode="aggregate",
        aggregate_tp=Decimal("51500")
    )

    assert "LONG Entry" in result
    assert "BTCUSDT" in result
    assert "DCA Levels" in result


def test_build_entry_message_per_leg_mode(broadcaster, position_group, pyramid):
    """Test _build_entry_message with per_leg TP mode."""
    entry_prices = [Decimal("50000")]
    weights = [100]
    tp_prices = [Decimal("51000")]

    result = broadcaster._build_entry_message(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=entry_prices,
        weights=weights,
        filled_count=1,
        total_count=1,
        tp_mode="per_leg",
        tp_prices=tp_prices
    )

    assert "TP" in result


def test_build_entry_message_hybrid_mode(broadcaster, position_group, pyramid):
    """Test _build_entry_message with hybrid TP mode."""
    entry_prices = [Decimal("50000")]
    weights = [100]

    result = broadcaster._build_entry_message(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=entry_prices,
        weights=weights,
        filled_count=1,
        total_count=1,
        tp_mode="hybrid",
        aggregate_tp=Decimal("51500")
    )

    assert "Fallback" in result


def test_build_entry_message_pyramid_aggregate_mode(broadcaster, position_group, pyramid):
    """Test _build_entry_message with pyramid_aggregate TP mode."""
    entry_prices = [Decimal("50000")]
    weights = [100]

    result = broadcaster._build_entry_message(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=entry_prices,
        weights=weights,
        filled_count=1,
        total_count=1,
        tp_mode="pyramid_aggregate",
        pyramid_tp_percent=Decimal("3")
    )

    assert "TP Target" in result


def test_build_dca_fill_message(broadcaster, position_group, dca_order, pyramid):
    """Test _build_dca_fill_message."""
    result = broadcaster._build_dca_fill_message(
        position_group=position_group,
        order=dca_order,
        filled_count=2,
        total_count=5,
        pyramid=pyramid
    )

    assert "Leg" in result
    assert "Filled" in result
    assert "Progress" in result


def test_build_status_message(broadcaster, position_group, pyramid):
    """Test _build_status_message."""
    result = broadcaster._build_status_message(
        position_group=position_group,
        old_status="LIVE",
        new_status="ACTIVE",
        pyramid=pyramid,
        filled_count=5,
        total_count=5,
        tp_mode="aggregate",
        tp_percent=Decimal("3")
    )

    assert "Status Changed" in result
    assert "LIVE" in result
    assert "ACTIVE" in result


def test_build_status_message_not_active(broadcaster, position_group, pyramid):
    """Test _build_status_message when new status is not ACTIVE."""
    result = broadcaster._build_status_message(
        position_group=position_group,
        old_status="LIVE",
        new_status="PARTIALLY_FILLED",
        pyramid=pyramid,
        filled_count=2,
        total_count=5
    )

    assert "2/5 DCA legs filled" in result


def test_build_tp_hit_message_per_leg(broadcaster, position_group, pyramid):
    """Test _build_tp_hit_message for per_leg type."""
    result = broadcaster._build_tp_hit_message(
        position_group=position_group,
        pyramid=pyramid,
        tp_type="per_leg",
        tp_price=Decimal("51000"),
        pnl_percent=Decimal("3"),
        pnl_usd=Decimal("30"),
        closed_quantity=Decimal("0.01"),
        remaining_pyramids=2,
        leg_index=0
    )

    assert "Per-Leg TP Hit" in result
    assert "Leg #0 closed" in result  # Uses 0-based indexing


def test_build_tp_hit_message_pyramid_aggregate(broadcaster, position_group, pyramid):
    """Test _build_tp_hit_message for pyramid_aggregate type."""
    result = broadcaster._build_tp_hit_message(
        position_group=position_group,
        pyramid=pyramid,
        tp_type="pyramid_aggregate",
        tp_price=Decimal("51000"),
        pnl_percent=Decimal("3"),
        remaining_pyramids=1
    )

    assert "Pyramid TP Hit" in result


def test_build_tp_hit_message_aggregate(broadcaster, position_group, pyramid):
    """Test _build_tp_hit_message for aggregate type."""
    result = broadcaster._build_tp_hit_message(
        position_group=position_group,
        pyramid=pyramid,
        tp_type="aggregate",
        tp_price=Decimal("51000"),
        pnl_percent=Decimal("3"),
        remaining_pyramids=0
    )

    assert "Aggregate TP Hit" in result


def test_build_risk_event_message_timer_started(broadcaster, position_group):
    """Test _build_risk_event_message for timer_started event."""
    result = broadcaster._build_risk_event_message(
        position_group=position_group,
        event_type="timer_started",
        loss_percent=Decimal("-5"),
        loss_usd=Decimal("-50"),
        timer_minutes=15
    )

    assert "Risk Timer Started" in result
    assert "15 minutes" in result


def test_build_risk_event_message_timer_expired(broadcaster, position_group):
    """Test _build_risk_event_message for timer_expired event."""
    result = broadcaster._build_risk_event_message(
        position_group=position_group,
        event_type="timer_expired",
        loss_percent=Decimal("-5"),
        timer_minutes=15
    )

    assert "Risk Timer Expired" in result


def test_build_risk_event_message_timer_reset(broadcaster, position_group):
    """Test _build_risk_event_message for timer_reset event."""
    result = broadcaster._build_risk_event_message(
        position_group=position_group,
        event_type="timer_reset"
    )

    assert "Risk Timer Reset" in result


def test_build_risk_event_message_offset_executed(broadcaster, position_group):
    """Test _build_risk_event_message for offset_executed event."""
    result = broadcaster._build_risk_event_message(
        position_group=position_group,
        event_type="offset_executed",
        loss_percent=Decimal("-5"),
        loss_usd=Decimal("-50"),
        offset_position="ETHUSDT",
        offset_profit=Decimal("60"),
        net_result=Decimal("10")
    )

    assert "Risk Offset Executed" in result
    assert "ETHUSDT" in result
    assert "Net result" in result


def test_build_risk_event_message_unknown_type(broadcaster, position_group):
    """Test _build_risk_event_message for unknown event type."""
    result = broadcaster._build_risk_event_message(
        position_group=position_group,
        event_type="unknown"
    )

    assert "Risk Alert" in result


def test_build_failure_message_order_failed(broadcaster, position_group, pyramid, dca_order):
    """Test _build_failure_message for order_failed type."""
    result = broadcaster._build_failure_message(
        position_group=position_group,
        error_type="order_failed",
        error_message="Insufficient balance",
        pyramid=pyramid,
        order=dca_order
    )

    assert "Order Failed" in result
    assert "balance" in result.lower()


def test_build_failure_message_position_failed(broadcaster, position_group):
    """Test _build_failure_message for position_failed type."""
    result = broadcaster._build_failure_message(
        position_group=position_group,
        error_type="position_failed",
        error_message="Connection timeout"
    )

    assert "Position Failed" in result
    assert "connectivity" in result.lower()


def test_build_failure_message_generic_error(broadcaster, position_group):
    """Test _build_failure_message for generic error."""
    result = broadcaster._build_failure_message(
        position_group=position_group,
        error_type="unknown",
        error_message="Something went wrong"
    )

    assert "Error" in result
    assert "Review error" in result


def test_build_pyramid_message(broadcaster, position_group, pyramid):
    """Test _build_pyramid_message."""
    entry_prices = [Decimal("50000"), Decimal("49500")]
    weights = [50, 50]

    result = broadcaster._build_pyramid_message(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=entry_prices,
        weights=weights,
        tp_percent=Decimal("3")
    )

    assert "Pyramid #0 Added" in result  # Uses 0-based indexing from pyramid.pyramid_index


def test_build_exit_message(broadcaster, position_group):
    """Test _build_exit_message."""
    result = broadcaster._build_exit_message(
        position_group=position_group,
        exit_price=Decimal("51000"),
        pnl_percent=Decimal("3"),
        pyramids_used=1,
        exit_reason="manual",
        pnl_usd=Decimal("30"),
        duration_hours=2.5,
        filled_legs=5,
        total_legs=5,
        tp_mode="aggregate"
    )

    assert "Position Closed" in result
    assert "Manual Close" in result


def test_build_exit_message_engine(broadcaster, position_group):
    """Test _build_exit_message for engine exit."""
    result = broadcaster._build_exit_message(
        position_group=position_group,
        exit_price=Decimal("51000"),
        pnl_percent=Decimal("3"),
        pyramids_used=1,
        exit_reason="engine"
    )

    assert "Engine Exit" in result


def test_build_exit_message_tp_hit(broadcaster, position_group):
    """Test _build_exit_message for tp_hit."""
    result = broadcaster._build_exit_message(
        position_group=position_group,
        exit_price=Decimal("51000"),
        pnl_percent=Decimal("3"),
        pyramids_used=1,
        exit_reason="tp_hit"
    )

    assert "Take Profit" in result


def test_build_exit_message_risk_offset(broadcaster, position_group):
    """Test _build_exit_message for risk_offset."""
    result = broadcaster._build_exit_message(
        position_group=position_group,
        exit_price=Decimal("49000"),
        pnl_percent=Decimal("-2"),
        pyramids_used=1,
        exit_reason="risk_offset"
    )

    assert "Risk Offset" in result


# --- Tests for send methods ---

@pytest.mark.asyncio
async def test_send_entry_signal_disabled(broadcaster, position_group, pyramid):
    """Test send_entry_signal when disabled."""
    broadcaster.config.enabled = False

    result = await broadcaster.send_entry_signal(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=[Decimal("50000")],
        weights=[100]
    )

    assert result is None


@pytest.mark.asyncio
async def test_send_entry_signal_send_entry_signals_disabled(broadcaster, position_group, pyramid):
    """Test send_entry_signal when send_entry_signals is disabled."""
    broadcaster.config.send_entry_signals = False

    result = await broadcaster.send_entry_signal(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=[Decimal("50000")],
        weights=[100]
    )

    assert result is None


@pytest.mark.asyncio
async def test_send_entry_signal_quiet_hours(broadcaster, position_group, pyramid):
    """Test send_entry_signal during quiet hours."""
    broadcaster.config.quiet_hours_enabled = True
    broadcaster.config.quiet_hours_start = "00:00"
    broadcaster.config.quiet_hours_end = "23:59"
    broadcaster.config.quiet_hours_urgent_only = True

    result = await broadcaster.send_entry_signal(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=[Decimal("50000")],
        weights=[100]
    )

    assert result is None


@pytest.mark.asyncio
async def test_send_entry_signal_test_mode(broadcaster, position_group, pyramid):
    """Test send_entry_signal in test mode."""
    result = await broadcaster.send_entry_signal(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=[Decimal("50000")],
        weights=[100]
    )

    assert result == 999999  # Test mode returns fake ID


@pytest.mark.asyncio
async def test_send_entry_signal_update_existing(broadcaster, position_group, pyramid):
    """Test send_entry_signal updates existing message."""
    position_group.telegram_message_id = 12345

    result = await broadcaster.send_entry_signal(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=[Decimal("50000")],
        weights=[100]
    )

    assert result == 12345


@pytest.mark.asyncio
async def test_send_exit_signal_test_mode(broadcaster, position_group):
    """Test send_exit_signal in test mode."""
    result = await broadcaster.send_exit_signal(
        position_group=position_group,
        exit_price=Decimal("51000"),
        pnl_percent=Decimal("3"),
        pyramids_used=1
    )

    assert result == 999999


@pytest.mark.asyncio
async def test_send_exit_signal_disabled(broadcaster, position_group):
    """Test send_exit_signal when disabled."""
    broadcaster.config.send_exit_signals = False

    result = await broadcaster.send_exit_signal(
        position_group=position_group,
        exit_price=Decimal("51000"),
        pnl_percent=Decimal("3"),
        pyramids_used=1
    )

    assert result is None


@pytest.mark.asyncio
async def test_send_dca_fill_test_mode(broadcaster, position_group, dca_order, pyramid):
    """Test send_dca_fill in test mode."""
    result = await broadcaster.send_dca_fill(
        position_group=position_group,
        order=dca_order,
        filled_count=1,
        total_count=5,
        pyramid=pyramid
    )

    assert result == 999999


@pytest.mark.asyncio
async def test_send_dca_fill_update_existing(broadcaster, position_group, dca_order, pyramid):
    """Test send_dca_fill updates existing message."""
    position_group.telegram_message_id = 12345

    result = await broadcaster.send_dca_fill(
        position_group=position_group,
        order=dca_order,
        filled_count=1,
        total_count=5,
        pyramid=pyramid
    )

    assert result == 12345


@pytest.mark.asyncio
async def test_send_status_change_test_mode(broadcaster, position_group, pyramid):
    """Test send_status_change in test mode."""
    result = await broadcaster.send_status_change(
        position_group=position_group,
        old_status="LIVE",
        new_status="ACTIVE",
        pyramid=pyramid,
        filled_count=5,
        total_count=5
    )

    assert result == 999999


@pytest.mark.asyncio
async def test_send_tp_hit_test_mode(broadcaster, position_group, pyramid):
    """Test send_tp_hit in test mode."""
    result = await broadcaster.send_tp_hit(
        position_group=position_group,
        pyramid=pyramid,
        tp_type="aggregate",
        tp_price=Decimal("51000"),
        pnl_percent=Decimal("3")
    )

    assert result == 999999


@pytest.mark.asyncio
async def test_send_risk_event_test_mode(broadcaster, position_group):
    """Test send_risk_event in test mode."""
    result = await broadcaster.send_risk_event(
        position_group=position_group,
        event_type="timer_started"
    )

    assert result == 999999


@pytest.mark.asyncio
async def test_send_failure_test_mode(broadcaster, position_group):
    """Test send_failure in test mode."""
    result = await broadcaster.send_failure(
        position_group=position_group,
        error_type="order_failed",
        error_message="Test error"
    )

    assert result == 999999


@pytest.mark.asyncio
async def test_send_pyramid_added_test_mode(broadcaster, position_group, pyramid):
    """Test send_pyramid_added in test mode."""
    result = await broadcaster.send_pyramid_added(
        position_group=position_group,
        pyramid=pyramid,
        entry_prices=[Decimal("50000")],
        weights=[100]
    )

    assert result == 999999


# --- Tests for API methods ---

@pytest.mark.asyncio
async def test_send_message_test_mode(broadcaster):
    """Test _send_message in test mode."""
    result = await broadcaster._send_message("Test message")
    assert result == 999999


@pytest.mark.asyncio
async def test_send_message_real_mode_success(telegram_config):
    """Test _send_message in real mode with success."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "result": {"message_id": 12345}
        })

        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_context_manager)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        result = await broadcaster._send_message("Test message")

        assert result == 12345


@pytest.mark.asyncio
async def test_send_message_real_mode_failure(telegram_config):
    """Test _send_message in real mode with failure."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")

        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_context_manager)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        result = await broadcaster._send_message("Test message")

        assert result is None


@pytest.mark.asyncio
async def test_send_message_timeout(telegram_config):
    """Test _send_message handles timeout."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session.post.side_effect = asyncio.TimeoutError()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        result = await broadcaster._send_message("Test message")

        assert result is None


@pytest.mark.asyncio
async def test_send_message_exception(telegram_config):
    """Test _send_message handles exceptions."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session.post.side_effect = Exception("Network error")

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        result = await broadcaster._send_message("Test message")

        assert result is None


@pytest.mark.asyncio
async def test_update_message_test_mode(broadcaster):
    """Test _update_message in test mode."""
    result = await broadcaster._update_message(12345, "Updated message")
    assert result == 12345


@pytest.mark.asyncio
async def test_update_message_timeout(telegram_config):
    """Test _update_message handles timeout."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session.post.side_effect = asyncio.TimeoutError()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        result = await broadcaster._update_message(12345, "Updated message")

        assert result is None


@pytest.mark.asyncio
async def test_update_message_exception(telegram_config):
    """Test _update_message handles exceptions."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session.post.side_effect = Exception("Network error")

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        result = await broadcaster._update_message(12345, "Updated message")

        assert result is None


@pytest.mark.asyncio
async def test_save_message_id(broadcaster, position_group):
    """Test _save_message_id success."""
    mock_session = AsyncMock()
    original_message_id = position_group.telegram_message_id

    await broadcaster._save_message_id(position_group, 12345, mock_session)

    # CRITICAL: Verify position_group state was updated
    assert position_group.telegram_message_id == 12345, \
        "Position group telegram_message_id must be updated after save"

    # CRITICAL: Verify state was persisted via session commit
    mock_session.commit.assert_called_once()

    # CRITICAL: Verify message ID changed from original
    assert position_group.telegram_message_id != original_message_id, \
        "Message ID must change after save operation"


@pytest.mark.asyncio
async def test_save_message_id_error(broadcaster, position_group):
    """Test _save_message_id handles error."""
    mock_session = AsyncMock()
    mock_session.commit.side_effect = Exception("DB error")

    # Should not raise
    await broadcaster._save_message_id(position_group, 12345, mock_session)


@pytest.mark.asyncio
async def test_test_connection_success(telegram_config):
    """Test test_connection success."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_get_response = MagicMock()
        mock_get_response.status = 200

        mock_post_response = MagicMock()
        mock_post_response.status = 200

        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_post_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.post = MagicMock(return_value=mock_post_context)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        success, message = await broadcaster.test_connection()

        assert success is True
        assert message == "OK"


@pytest.mark.asyncio
async def test_test_connection_bot_failure(telegram_config):
    """Test test_connection when bot check fails."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        success, message = await broadcaster.test_connection()

        assert success is False
        assert "Unauthorized" in message


@pytest.mark.asyncio
async def test_test_connection_channel_failure(telegram_config):
    """Test test_connection when channel check fails."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_get_response = MagicMock()
        mock_get_response.status = 200

        mock_post_response = MagicMock()
        mock_post_response.status = 403
        mock_post_response.text = AsyncMock(return_value="Forbidden")

        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_post_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.post = MagicMock(return_value=mock_post_context)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        success, message = await broadcaster.test_connection()

        assert success is False
        assert "Forbidden" in message


@pytest.mark.asyncio
async def test_test_connection_exception(telegram_config):
    """Test test_connection handles exception."""
    telegram_config.test_mode = False
    broadcaster = TelegramBroadcaster(telegram_config)

    with patch("app.services.telegram_broadcaster.aiohttp.ClientSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session_cm

        success, message = await broadcaster.test_connection()

        assert success is False
        assert "Network error" in message
