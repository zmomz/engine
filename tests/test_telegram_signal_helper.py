"""Tests for Telegram signal helper functions"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid

from app.services.telegram_signal_helper import broadcast_entry_signal, broadcast_exit_signal
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.user import User
from app.models.dca_configuration import DCAConfiguration, TakeProfitMode


@pytest.fixture
def sample_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.telegram_config = {
        "enabled": True,
        "bot_token": "test_token",
        "channel_id": "-100123",
        "send_entry_signals": True,
        "send_exit_signals": True,
        "test_mode": True
    }
    return user


@pytest.fixture
def sample_user_no_config():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.telegram_config = None
    return user


@pytest.fixture
def sample_user_disabled():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.telegram_config = {
        "enabled": False,
        "bot_token": "test_token",
        "channel_id": "-100123"
    }
    return user


@pytest.fixture
def sample_position_group(sample_user):
    pg = MagicMock()  # Removed spec=PositionGroup to allow adding any attributes
    pg.id = uuid.uuid4()
    pg.user_id = sample_user.id
    pg.exchange = "binance"
    pg.symbol = "BTCUSDT"
    pg.timeframe = 15
    pg.side = "long"
    pg.status = PositionGroupStatus.LIVE
    pg.pyramid_count = 1
    pg.weighted_avg_entry = Decimal("50000")
    pg.tp_mode = "per_leg"
    pg.total_invested_usd = Decimal("1000")
    pg.max_pyramids = 5
    pg.created_at = None
    pg.closed_at = None
    return pg


@pytest.fixture
def sample_pyramid(sample_position_group):
    pyramid = MagicMock(spec=Pyramid)
    pyramid.id = uuid.uuid4()
    pyramid.group_id = sample_position_group.id
    pyramid.pyramid_index = 0
    pyramid.entry_price = Decimal("50000")
    pyramid.status = PyramidStatus.FILLED
    return pyramid


@pytest.fixture
def sample_dca_orders(sample_pyramid):
    orders = []
    for i, (price, qty) in enumerate([(50000, 0.1), (49500, 0.2), (49000, 0.3)]):
        order = MagicMock(spec=DCAOrder)
        order.id = uuid.uuid4()
        order.pyramid_id = sample_pyramid.id
        order.leg_index = i
        order.price = Decimal(str(price))
        order.quantity = Decimal(str(qty))
        order.status = OrderStatus.FILLED
        orders.append(order)
    return orders


@pytest.fixture
def sample_dca_config(sample_user, sample_position_group):
    config = MagicMock(spec=DCAConfiguration)
    config.user_id = sample_user.id
    config.pair = "BTC/USDT"
    config.timeframe = sample_position_group.timeframe
    config.exchange = sample_position_group.exchange
    config.dca_levels = [
        {"weight_percent": 20, "tp_percent": 1.0},
        {"weight_percent": 30, "tp_percent": 0.8},
        {"weight_percent": 50, "tp_percent": 0.5}
    ]
    config.tp_mode = TakeProfitMode.PER_LEG
    config.tp_settings = {}
    return config


class TestBroadcastEntrySignal:
    """Tests for broadcast_entry_signal function"""

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_user_not_found(self, sample_position_group, sample_pyramid):
        """Test broadcast when user is not found"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Should not raise, just log warning
        await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_no_telegram_config(
        self, sample_user_no_config, sample_position_group, sample_pyramid
    ):
        """Test broadcast when user has no telegram config"""
        sample_position_group.user_id = sample_user_no_config.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_no_config
        mock_session.execute.return_value = mock_result

        # Should not raise, just skip
        await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_telegram_disabled(
        self, sample_user_disabled, sample_position_group, sample_pyramid
    ):
        """Test broadcast when telegram is disabled"""
        sample_position_group.user_id = sample_user_disabled.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_disabled
        mock_session.execute.return_value = mock_result

        # Should not raise, just skip
        await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_entry_signals_disabled(
        self, sample_user, sample_position_group, sample_pyramid
    ):
        """Test broadcast when entry signals are disabled"""
        sample_user.telegram_config["send_entry_signals"] = False
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        # Should not raise, just skip
        await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_success_with_dca_config(
        self, sample_user, sample_position_group, sample_pyramid, sample_dca_config, sample_dca_orders
    ):
        """Test successful broadcast with DCA config"""
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()

        # First call returns user, second returns DCA config, third returns orders
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = sample_dca_config

        orders_result = MagicMock()
        orders_result.scalars.return_value.all.return_value = sample_dca_orders

        mock_session.execute.side_effect = [user_result, config_result, orders_result]

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_entry_signal = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

            mock_broadcaster.send_entry_signal.assert_called_once()

            # CRITICAL: Verify message ID was returned (needed for editing later)
            # The actual update happens elsewhere, but we verify the return value
            assert mock_broadcaster.send_entry_signal.return_value == 12345, \
                "Entry signal must return message ID for later updates"

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_success_without_dca_config(
        self, sample_user, sample_position_group, sample_pyramid, sample_dca_orders
    ):
        """Test successful broadcast without DCA config (uses fallback)"""
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None  # No DCA config

        orders_result = MagicMock()
        orders_result.scalars.return_value.all.return_value = sample_dca_orders

        mock_session.execute.side_effect = [user_result, config_result, orders_result]

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_entry_signal = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

            mock_broadcaster.send_entry_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_aggregate_tp_mode(
        self, sample_user, sample_position_group, sample_pyramid, sample_dca_config, sample_dca_orders
    ):
        """Test broadcast with aggregate TP mode"""
        sample_position_group.user_id = sample_user.id
        sample_dca_config.tp_mode = TakeProfitMode.AGGREGATE
        sample_dca_config.tp_settings = {"tp_aggregate_percent": 2.0}

        mock_session = AsyncMock()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = sample_dca_config

        orders_result = MagicMock()
        orders_result.scalars.return_value.all.return_value = sample_dca_orders

        mock_session.execute.side_effect = [user_result, config_result, orders_result]

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_entry_signal = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

            # Verify aggregate_tp was calculated and passed
            call_kwargs = mock_broadcaster.send_entry_signal.call_args.kwargs
            assert call_kwargs["tp_mode"] == "aggregate"

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_aggregate_tp_alternate_key(
        self, sample_user, sample_position_group, sample_pyramid, sample_dca_config, sample_dca_orders
    ):
        """Test broadcast with aggregate TP using alternate key name"""
        sample_position_group.user_id = sample_user.id
        sample_dca_config.tp_mode = TakeProfitMode.AGGREGATE
        sample_dca_config.tp_settings = {"aggregate_tp_percent": 2.5}  # Alternate key

        mock_session = AsyncMock()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = sample_dca_config

        orders_result = MagicMock()
        orders_result.scalars.return_value.all.return_value = sample_dca_orders

        mock_session.execute.side_effect = [user_result, config_result, orders_result]

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_entry_signal = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_send_failure(
        self, sample_user, sample_position_group, sample_pyramid, sample_dca_config, sample_dca_orders
    ):
        """Test broadcast when send fails"""
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = sample_dca_config

        orders_result = MagicMock()
        orders_result.scalars.return_value.all.return_value = sample_dca_orders

        mock_session.execute.side_effect = [user_result, config_result, orders_result]

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_entry_signal = AsyncMock(return_value=None)  # Failed
            MockBroadcaster.return_value = mock_broadcaster

            # Should not raise
            await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_entry_signal_exception(
        self, sample_user, sample_position_group, sample_pyramid
    ):
        """Test broadcast handles exceptions gracefully"""
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        # Should not raise, just log error
        await broadcast_entry_signal(sample_position_group, sample_pyramid, mock_session)


class TestBroadcastExitSignal:
    """Tests for broadcast_exit_signal function"""

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_user_not_found(self, sample_position_group):
        """Test broadcast when user is not found"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Should not raise
        await broadcast_exit_signal(sample_position_group, Decimal("51000"), mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_no_config(self, sample_user_no_config, sample_position_group):
        """Test broadcast when user has no config"""
        sample_position_group.user_id = sample_user_no_config.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_no_config
        mock_session.execute.return_value = mock_result

        # Should not raise
        await broadcast_exit_signal(sample_position_group, Decimal("51000"), mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_disabled(self, sample_user_disabled, sample_position_group):
        """Test broadcast when telegram is disabled"""
        sample_position_group.user_id = sample_user_disabled.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_disabled
        mock_session.execute.return_value = mock_result

        # Should not raise
        await broadcast_exit_signal(sample_position_group, Decimal("51000"), mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_exit_signals_disabled(self, sample_user, sample_position_group):
        """Test broadcast when exit signals are disabled"""
        sample_user.telegram_config["send_exit_signals"] = False
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        # Should not raise
        await broadcast_exit_signal(sample_position_group, Decimal("51000"), mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_success_long(self, sample_user, sample_position_group):
        """Test successful exit broadcast for long position"""
        sample_position_group.user_id = sample_user.id
        sample_position_group.side = "long"
        sample_position_group.weighted_avg_entry = Decimal("50000")
        sample_position_group.pyramid_count = 2
        sample_position_group.filled_dca_legs = 2
        sample_position_group.total_dca_legs = 5

        mock_session = AsyncMock()

        # Create separate results for user query and DCA config query
        call_count = [0]
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                # First call: User query
                mock_result.scalar_one_or_none.return_value = sample_user
            else:
                # Second call: DCA config query - return None
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_session.execute.side_effect = execute_side_effect

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_exit_signal = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_exit_signal(sample_position_group, Decimal("51000"), mock_session)

            mock_broadcaster.send_exit_signal.assert_called_once()
            call_kwargs = mock_broadcaster.send_exit_signal.call_args.kwargs
            assert call_kwargs["exit_price"] == Decimal("51000")
            assert call_kwargs["pnl_percent"] == Decimal("2")  # (51000-50000)/50000 * 100
            assert call_kwargs["pyramids_used"] == 2

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_success_short(self, sample_user, sample_position_group):
        """Test successful exit broadcast for short position"""
        sample_position_group.user_id = sample_user.id
        sample_position_group.side = "short"
        sample_position_group.weighted_avg_entry = Decimal("50000")
        sample_position_group.pyramid_count = 1
        sample_position_group.filled_dca_legs = 1
        sample_position_group.total_dca_legs = 3

        mock_session = AsyncMock()

        # Create separate results for user query and DCA config query
        call_count = [0]
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                # First call: User query
                mock_result.scalar_one_or_none.return_value = sample_user
            else:
                # Second call: DCA config query - return None
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_session.execute.side_effect = execute_side_effect

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_exit_signal = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_exit_signal(sample_position_group, Decimal("49000"), mock_session)

            # For short: (entry - exit) / entry * 100 = (50000-49000)/50000*100 = 2%
            call_kwargs = mock_broadcaster.send_exit_signal.call_args.kwargs
            assert call_kwargs["pnl_percent"] == Decimal("2")

            # CRITICAL: Verify PnL calculation is correct for short position
            # For short: profit when exit < entry
            # (entry_price - exit_price) / entry_price * 100 = (50000 - 49000) / 50000 * 100 = 2%
            assert call_kwargs["pnl_percent"] > 0, \
                "PnL must be positive for winning short trade (exit < entry)"

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_exception(self, sample_user, sample_position_group):
        """Test broadcast handles exceptions gracefully"""
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        # Should not raise
        await broadcast_exit_signal(sample_position_group, Decimal("51000"), mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_zero_entry_price(self, sample_user, sample_position_group):
        """Test exit signal with zero entry price"""
        sample_position_group.user_id = sample_user.id
        sample_position_group.weighted_avg_entry = Decimal("0")
        sample_position_group.realized_pnl_usd = Decimal("100")
        sample_position_group.filled_dca_legs = 1
        sample_position_group.total_dca_legs = 3

        mock_session = AsyncMock()
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_user
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_session.execute.side_effect = execute_side_effect

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_exit_signal = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_exit_signal(sample_position_group, Decimal("51000"), mock_session)

            call_kwargs = mock_broadcaster.send_exit_signal.call_args.kwargs
            assert call_kwargs["pnl_percent"] == Decimal("0")

    @pytest.mark.asyncio
    async def test_broadcast_exit_signal_with_duration(self, sample_user, sample_position_group):
        """Test exit signal calculates duration correctly"""
        from datetime import datetime, timedelta
        sample_position_group.user_id = sample_user.id
        sample_position_group.created_at = datetime.utcnow() - timedelta(hours=5)
        sample_position_group.closed_at = datetime.utcnow()
        sample_position_group.filled_dca_legs = 1
        sample_position_group.total_dca_legs = 3

        mock_session = AsyncMock()
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_user
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_session.execute.side_effect = execute_side_effect

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_exit_signal = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_exit_signal(sample_position_group, Decimal("51000"), mock_session)

            call_kwargs = mock_broadcaster.send_exit_signal.call_args.kwargs
            # Duration should be approximately 5 hours
            assert 4.9 < call_kwargs["duration_hours"] < 5.1


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelperFunctions:
    """Tests for helper functions in telegram_signal_helper"""

    def test_extract_weights_from_levels(self):
        """Test extracting weights from DCA levels"""
        from app.services.telegram_signal_helper import _extract_weights_from_levels

        levels = [
            {"weight_percent": 20.5},
            {"weight_percent": 30},
            {"weight_percent": 49.5}
        ]
        weights = _extract_weights_from_levels(levels)
        assert weights == [20, 30, 49]

    def test_extract_weights_from_levels_empty(self):
        """Test extracting weights from empty levels"""
        from app.services.telegram_signal_helper import _extract_weights_from_levels

        weights = _extract_weights_from_levels([])
        assert weights == []

    def test_extract_weights_from_levels_missing_weight(self):
        """Test extracting weights when weight_percent is missing"""
        from app.services.telegram_signal_helper import _extract_weights_from_levels

        levels = [{"other_field": 10}, {"weight_percent": 50}]
        weights = _extract_weights_from_levels(levels)
        assert weights == [0, 50]

    def test_calculate_tp_prices_per_leg(self):
        """Test calculating TP prices for per_leg mode"""
        from app.services.telegram_signal_helper import _calculate_tp_prices

        entry_prices = [Decimal("50000"), Decimal("49500"), None]
        dca_levels = [
            {"tp_percent": 2.0},
            {"tp_percent": 1.5},
            {"tp_percent": 1.0}
        ]
        tp_prices = _calculate_tp_prices(entry_prices, dca_levels, "per_leg")

        assert tp_prices[0] == Decimal("50000") * Decimal("1.02")
        assert tp_prices[1] == Decimal("49500") * Decimal("1.015")
        assert tp_prices[2] is None  # Entry price was None

    def test_calculate_tp_prices_not_per_leg(self):
        """Test that non per_leg modes return empty list"""
        from app.services.telegram_signal_helper import _calculate_tp_prices

        entry_prices = [Decimal("50000")]
        dca_levels = [{"tp_percent": 2.0}]

        assert _calculate_tp_prices(entry_prices, dca_levels, "aggregate") == []
        assert _calculate_tp_prices(entry_prices, dca_levels, "hybrid") == []

    def test_calculate_tp_prices_no_tp_percent(self):
        """Test when level has no tp_percent"""
        from app.services.telegram_signal_helper import _calculate_tp_prices

        entry_prices = [Decimal("50000")]
        dca_levels = [{"weight_percent": 50}]  # No tp_percent
        tp_prices = _calculate_tp_prices(entry_prices, dca_levels, "per_leg")

        assert tp_prices[0] is None

    def test_calculate_aggregate_tp(self):
        """Test aggregate TP calculation"""
        from app.services.telegram_signal_helper import _calculate_aggregate_tp

        avg_entry = Decimal("50000")
        tp_percent = Decimal("2")

        result = _calculate_aggregate_tp(avg_entry, tp_percent)
        assert result == Decimal("51000")

    def test_calculate_aggregate_tp_none_values(self):
        """Test aggregate TP with None values"""
        from app.services.telegram_signal_helper import _calculate_aggregate_tp

        assert _calculate_aggregate_tp(None, Decimal("2")) is None
        assert _calculate_aggregate_tp(Decimal("50000"), None) is None
        assert _calculate_aggregate_tp(None, None) is None


# ═══════════════════════════════════════════════════════════════════════════════
# DCA FILL TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBroadcastDcaFill:
    """Tests for broadcast_dca_fill function"""

    @pytest.fixture
    def sample_dca_order(self, sample_pyramid):
        order = MagicMock(spec=DCAOrder)
        order.id = uuid.uuid4()
        order.pyramid_id = sample_pyramid.id
        order.leg_index = 1
        order.price = Decimal("49500")
        order.quantity = Decimal("0.2")
        order.status = OrderStatus.FILLED
        return order

    @pytest.mark.asyncio
    async def test_broadcast_dca_fill_user_not_found(self, sample_position_group, sample_dca_order, sample_pyramid):
        """Test broadcast when user is not found"""
        from app.services.telegram_signal_helper import broadcast_dca_fill

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await broadcast_dca_fill(sample_position_group, sample_dca_order, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_dca_fill_disabled(self, sample_user, sample_position_group, sample_dca_order, sample_pyramid):
        """Test broadcast when DCA fill updates are disabled"""
        from app.services.telegram_signal_helper import broadcast_dca_fill

        sample_user.telegram_config["send_dca_fill_updates"] = False
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        await broadcast_dca_fill(sample_position_group, sample_dca_order, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_dca_fill_success(self, sample_user, sample_position_group, sample_dca_order, sample_pyramid):
        """Test successful DCA fill broadcast"""
        from app.services.telegram_signal_helper import broadcast_dca_fill

        sample_user.telegram_config["send_dca_fill_updates"] = True
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_user
            elif call_count[0] == 2:
                # Filled orders query
                mock_result.scalars.return_value.all.return_value = [sample_dca_order]
            else:
                # All orders query
                mock_result.scalars.return_value.all.return_value = [sample_dca_order, MagicMock(), MagicMock()]
            return mock_result

        mock_session.execute.side_effect = execute_side_effect

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_dca_fill = AsyncMock()
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_dca_fill(sample_position_group, sample_dca_order, sample_pyramid, mock_session)

            mock_broadcaster.send_dca_fill.assert_called_once()
            call_kwargs = mock_broadcaster.send_dca_fill.call_args.kwargs
            assert call_kwargs["filled_count"] == 1
            assert call_kwargs["total_count"] == 3

    @pytest.mark.asyncio
    async def test_broadcast_dca_fill_exception(self, sample_position_group, sample_dca_order, sample_pyramid):
        """Test DCA fill handles exceptions gracefully"""
        from app.services.telegram_signal_helper import broadcast_dca_fill

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        await broadcast_dca_fill(sample_position_group, sample_dca_order, sample_pyramid, mock_session)


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS CHANGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBroadcastStatusChange:
    """Tests for broadcast_status_change function"""

    @pytest.mark.asyncio
    async def test_broadcast_status_change_user_not_found(self, sample_position_group, sample_pyramid):
        """Test broadcast when user is not found"""
        from app.services.telegram_signal_helper import broadcast_status_change

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await broadcast_status_change(
            sample_position_group,
            PositionGroupStatus.PARTIALLY_FILLED,
            PositionGroupStatus.ACTIVE,
            sample_pyramid,
            mock_session
        )

    @pytest.mark.asyncio
    async def test_broadcast_status_change_disabled(self, sample_user, sample_position_group, sample_pyramid):
        """Test broadcast when status updates are disabled"""
        from app.services.telegram_signal_helper import broadcast_status_change

        sample_user.telegram_config["send_status_updates"] = False
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        await broadcast_status_change(
            sample_position_group,
            PositionGroupStatus.PARTIALLY_FILLED,
            PositionGroupStatus.ACTIVE,
            sample_pyramid,
            mock_session
        )

    @pytest.mark.asyncio
    async def test_broadcast_status_change_success(self, sample_user, sample_position_group, sample_pyramid, sample_dca_config):
        """Test successful status change broadcast"""
        from app.services.telegram_signal_helper import broadcast_status_change

        sample_user.telegram_config["send_status_updates"] = True
        sample_position_group.user_id = sample_user.id
        sample_position_group.filled_dca_legs = 2
        sample_position_group.total_dca_legs = 5

        mock_session = AsyncMock()
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_user
            else:
                mock_result.scalar_one_or_none.return_value = sample_dca_config
            return mock_result

        mock_session.execute.side_effect = execute_side_effect

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_status_change = AsyncMock()
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_status_change(
                sample_position_group,
                PositionGroupStatus.PARTIALLY_FILLED,
                PositionGroupStatus.ACTIVE,
                sample_pyramid,
                mock_session
            )

            mock_broadcaster.send_status_change.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_status_change_exception(self, sample_position_group, sample_pyramid):
        """Test status change handles exceptions gracefully"""
        from app.services.telegram_signal_helper import broadcast_status_change

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        await broadcast_status_change(
            sample_position_group,
            PositionGroupStatus.PARTIALLY_FILLED,
            PositionGroupStatus.ACTIVE,
            sample_pyramid,
            mock_session
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TP HIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBroadcastTpHit:
    """Tests for broadcast_tp_hit function"""

    @pytest.mark.asyncio
    async def test_broadcast_tp_hit_user_not_found(self, sample_position_group, sample_pyramid):
        """Test broadcast when user is not found"""
        from app.services.telegram_signal_helper import broadcast_tp_hit

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await broadcast_tp_hit(
            sample_position_group,
            sample_pyramid,
            "per_leg",
            Decimal("51000"),
            Decimal("2.0"),
            mock_session
        )

    @pytest.mark.asyncio
    async def test_broadcast_tp_hit_disabled(self, sample_user, sample_position_group, sample_pyramid):
        """Test broadcast when TP hit updates are disabled"""
        from app.services.telegram_signal_helper import broadcast_tp_hit

        sample_user.telegram_config["send_tp_hit_updates"] = False
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        await broadcast_tp_hit(
            sample_position_group,
            sample_pyramid,
            "per_leg",
            Decimal("51000"),
            Decimal("2.0"),
            mock_session
        )

    @pytest.mark.asyncio
    async def test_broadcast_tp_hit_success(self, sample_user, sample_position_group, sample_pyramid):
        """Test successful TP hit broadcast"""
        from app.services.telegram_signal_helper import broadcast_tp_hit

        sample_user.telegram_config["send_tp_hit_updates"] = True
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_tp_hit = AsyncMock()
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_tp_hit(
                sample_position_group,
                sample_pyramid,
                "per_leg",
                Decimal("51000"),
                Decimal("2.0"),
                mock_session,
                pnl_usd=Decimal("100"),
                closed_quantity=Decimal("0.1"),
                remaining_pyramids=2,
                leg_index=1
            )

            mock_broadcaster.send_tp_hit.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_tp_hit_exception(self, sample_position_group, sample_pyramid):
        """Test TP hit handles exceptions gracefully"""
        from app.services.telegram_signal_helper import broadcast_tp_hit

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        await broadcast_tp_hit(
            sample_position_group,
            sample_pyramid,
            "aggregate",
            Decimal("51000"),
            Decimal("2.0"),
            mock_session
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RISK EVENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBroadcastRiskEvent:
    """Tests for broadcast_risk_event function"""

    @pytest.mark.asyncio
    async def test_broadcast_risk_event_user_not_found(self, sample_position_group):
        """Test broadcast when user is not found"""
        from app.services.telegram_signal_helper import broadcast_risk_event

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await broadcast_risk_event(sample_position_group, "timer_started", mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_risk_event_disabled(self, sample_user, sample_position_group):
        """Test broadcast when risk alerts are disabled"""
        from app.services.telegram_signal_helper import broadcast_risk_event

        sample_user.telegram_config["send_risk_alerts"] = False
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        await broadcast_risk_event(sample_position_group, "timer_started", mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_risk_event_success(self, sample_user, sample_position_group):
        """Test successful risk event broadcast"""
        from app.services.telegram_signal_helper import broadcast_risk_event

        sample_user.telegram_config["send_risk_alerts"] = True
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_risk_event = AsyncMock()
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_risk_event(
                sample_position_group,
                "timer_started",
                mock_session,
                loss_percent=Decimal("5.0"),
                loss_usd=Decimal("500"),
                timer_minutes=30
            )

            mock_broadcaster.send_risk_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_risk_event_offset_executed(self, sample_user, sample_position_group):
        """Test risk event for offset execution"""
        from app.services.telegram_signal_helper import broadcast_risk_event

        sample_user.telegram_config["send_risk_alerts"] = True
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_risk_event = AsyncMock()
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_risk_event(
                sample_position_group,
                "offset_executed",
                mock_session,
                offset_position="ETHUSDT",
                offset_profit=Decimal("200"),
                net_result=Decimal("-300")
            )

            mock_broadcaster.send_risk_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_risk_event_exception(self, sample_position_group):
        """Test risk event handles exceptions gracefully"""
        from app.services.telegram_signal_helper import broadcast_risk_event

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        await broadcast_risk_event(sample_position_group, "timer_started", mock_session)


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBroadcastFailure:
    """Tests for broadcast_failure function"""

    @pytest.mark.asyncio
    async def test_broadcast_failure_user_not_found(self, sample_position_group):
        """Test broadcast when user is not found"""
        from app.services.telegram_signal_helper import broadcast_failure

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await broadcast_failure(sample_position_group, "order_failed", "Test error", mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_failure_disabled(self, sample_user, sample_position_group):
        """Test broadcast when failure alerts are disabled"""
        from app.services.telegram_signal_helper import broadcast_failure

        sample_user.telegram_config["send_failure_alerts"] = False
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        await broadcast_failure(sample_position_group, "order_failed", "Test error", mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_failure_success(self, sample_user, sample_position_group, sample_pyramid):
        """Test successful failure broadcast"""
        from app.services.telegram_signal_helper import broadcast_failure

        sample_user.telegram_config["send_failure_alerts"] = True
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        mock_order = MagicMock(spec=DCAOrder)

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_failure = AsyncMock()
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_failure(
                sample_position_group,
                "order_failed",
                "Insufficient balance",
                mock_session,
                pyramid=sample_pyramid,
                order=mock_order
            )

            mock_broadcaster.send_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_failure_exception(self, sample_position_group):
        """Test failure broadcast handles exceptions gracefully"""
        from app.services.telegram_signal_helper import broadcast_failure

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        await broadcast_failure(sample_position_group, "order_failed", "Test error", mock_session)


# ═══════════════════════════════════════════════════════════════════════════════
# PYRAMID ADDED TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBroadcastPyramidAdded:
    """Tests for broadcast_pyramid_added function"""

    @pytest.mark.asyncio
    async def test_broadcast_pyramid_added_user_not_found(self, sample_position_group, sample_pyramid):
        """Test broadcast when user is not found"""
        from app.services.telegram_signal_helper import broadcast_pyramid_added

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await broadcast_pyramid_added(sample_position_group, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_pyramid_added_disabled(self, sample_user, sample_position_group, sample_pyramid):
        """Test broadcast when pyramid updates are disabled"""
        from app.services.telegram_signal_helper import broadcast_pyramid_added

        sample_user.telegram_config["send_pyramid_updates"] = False
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        await broadcast_pyramid_added(sample_position_group, sample_pyramid, mock_session)

    @pytest.mark.asyncio
    async def test_broadcast_pyramid_added_success_with_config(
        self, sample_user, sample_position_group, sample_pyramid, sample_dca_config, sample_dca_orders
    ):
        """Test successful pyramid added broadcast with DCA config"""
        from app.services.telegram_signal_helper import broadcast_pyramid_added

        sample_user.telegram_config["send_pyramid_updates"] = True
        sample_position_group.user_id = sample_user.id
        sample_dca_config.tp_settings = {"pyramid_tp_percents": {"0": 2.0}}

        mock_session = AsyncMock()
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_user
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = sample_dca_config
            else:
                mock_result.scalars.return_value.all.return_value = sample_dca_orders
            return mock_result

        mock_session.execute.side_effect = execute_side_effect

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_pyramid_added = AsyncMock()
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_pyramid_added(sample_position_group, sample_pyramid, mock_session)

            mock_broadcaster.send_pyramid_added.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_pyramid_added_success_without_config(
        self, sample_user, sample_position_group, sample_pyramid, sample_dca_orders
    ):
        """Test successful pyramid added broadcast without DCA config"""
        from app.services.telegram_signal_helper import broadcast_pyramid_added

        sample_user.telegram_config["send_pyramid_updates"] = True
        sample_position_group.user_id = sample_user.id

        mock_session = AsyncMock()
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_user
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = None  # No DCA config
            else:
                mock_result.scalars.return_value.all.return_value = sample_dca_orders
            return mock_result

        mock_session.execute.side_effect = execute_side_effect

        with patch('app.services.telegram_signal_helper.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.send_pyramid_added = AsyncMock()
            MockBroadcaster.return_value = mock_broadcaster

            await broadcast_pyramid_added(sample_position_group, sample_pyramid, mock_session)

            mock_broadcaster.send_pyramid_added.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_pyramid_added_exception(self, sample_position_group, sample_pyramid):
        """Test pyramid added handles exceptions gracefully"""
        from app.services.telegram_signal_helper import broadcast_pyramid_added

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        await broadcast_pyramid_added(sample_position_group, sample_pyramid, mock_session)


# ═══════════════════════════════════════════════════════════════════════════════
# GET USER TELEGRAM CONFIG TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUserTelegramConfig:
    """Tests for _get_user_telegram_config function"""

    @pytest.mark.asyncio
    async def test_get_user_telegram_config_success(self, sample_user):
        """Test getting telegram config successfully"""
        from app.services.telegram_signal_helper import _get_user_telegram_config

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        config = await _get_user_telegram_config(sample_user.id, mock_session)

        assert config is not None
        assert config.enabled is True

    @pytest.mark.asyncio
    async def test_get_user_telegram_config_user_not_found(self):
        """Test getting config when user not found"""
        from app.services.telegram_signal_helper import _get_user_telegram_config

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        config = await _get_user_telegram_config(uuid.uuid4(), mock_session)

        assert config is None

    @pytest.mark.asyncio
    async def test_get_user_telegram_config_no_config(self, sample_user_no_config):
        """Test getting config when user has no config"""
        from app.services.telegram_signal_helper import _get_user_telegram_config

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_no_config
        mock_session.execute.return_value = mock_result

        config = await _get_user_telegram_config(sample_user_no_config.id, mock_session)

        assert config is None

    @pytest.mark.asyncio
    async def test_get_user_telegram_config_disabled(self, sample_user_disabled):
        """Test getting config when telegram is disabled"""
        from app.services.telegram_signal_helper import _get_user_telegram_config

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_disabled
        mock_session.execute.return_value = mock_result

        config = await _get_user_telegram_config(sample_user_disabled.id, mock_session)

        assert config is None

    @pytest.mark.asyncio
    async def test_get_user_telegram_config_exception(self):
        """Test getting config handles exceptions"""
        from app.services.telegram_signal_helper import _get_user_telegram_config

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        config = await _get_user_telegram_config(uuid.uuid4(), mock_session)

        assert config is None


# ═══════════════════════════════════════════════════════════════════════════════
# GET DCA CONFIG TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetDcaConfig:
    """Tests for _get_dca_config function"""

    @pytest.mark.asyncio
    async def test_get_dca_config_success(self, sample_position_group, sample_dca_config):
        """Test getting DCA config successfully"""
        from app.services.telegram_signal_helper import _get_dca_config

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_dca_config
        mock_session.execute.return_value = mock_result

        config = await _get_dca_config(sample_position_group, mock_session)

        assert config == sample_dca_config

    @pytest.mark.asyncio
    async def test_get_dca_config_not_found(self, sample_position_group):
        """Test getting DCA config when not found"""
        from app.services.telegram_signal_helper import _get_dca_config

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        config = await _get_dca_config(sample_position_group, mock_session)

        assert config is None

    @pytest.mark.asyncio
    async def test_get_dca_config_exception(self, sample_position_group):
        """Test getting DCA config handles exceptions"""
        from app.services.telegram_signal_helper import _get_dca_config

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        config = await _get_dca_config(sample_position_group, mock_session)

        assert config is None

    @pytest.mark.asyncio
    async def test_get_dca_config_non_usdt_symbol(self, sample_position_group, sample_dca_config):
        """Test getting DCA config for non-USDT symbol"""
        from app.services.telegram_signal_helper import _get_dca_config

        sample_position_group.symbol = "ETHBTC"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_dca_config
        mock_session.execute.return_value = mock_result

        config = await _get_dca_config(sample_position_group, mock_session)

        assert config == sample_dca_config
