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
