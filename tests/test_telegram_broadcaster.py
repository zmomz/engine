"""Tests for TelegramBroadcaster service"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid

from app.services.telegram_broadcaster import TelegramBroadcaster
from app.schemas.telegram_config import TelegramConfig
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid, PyramidStatus


@pytest.fixture
def telegram_config():
    return TelegramConfig(
        enabled=True,
        bot_token="test_bot_token_123",
        channel_id="-1001234567890",
        channel_name="Test Channel",
        send_entry_signals=True,
        send_exit_signals=True,
        update_on_pyramid=True,
        test_mode=False
    )


@pytest.fixture
def telegram_config_test_mode():
    return TelegramConfig(
        enabled=True,
        bot_token="test_bot_token_123",
        channel_id="-1001234567890",
        channel_name="Test Channel",
        send_entry_signals=True,
        send_exit_signals=True,
        update_on_pyramid=True,
        test_mode=True
    )


@pytest.fixture
def telegram_config_disabled():
    return TelegramConfig(
        enabled=False,
        bot_token="test_bot_token_123",
        channel_id="-1001234567890"
    )


@pytest.fixture
def sample_position_group():
    return PositionGroup(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.LIVE,
        pyramid_count=1,
        total_dca_legs=5,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("49500"),
        total_invested_usd=Decimal("10000")
    )


@pytest.fixture
def sample_pyramid():
    return Pyramid(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_index=0,
        entry_price=Decimal("50000"),
        status=PyramidStatus.FILLED
    )


class TestTelegramBroadcaster:
    """Tests for TelegramBroadcaster class"""

    def test_init(self, telegram_config):
        """Test broadcaster initialization"""
        broadcaster = TelegramBroadcaster(telegram_config)
        assert broadcaster.config == telegram_config
        assert "test_bot_token_123" in broadcaster.base_url
        assert broadcaster.message_ids == {}

    @pytest.mark.asyncio
    async def test_send_entry_signal_disabled(self, telegram_config_disabled, sample_position_group, sample_pyramid):
        """Test that entry signal is not sent when disabled"""
        broadcaster = TelegramBroadcaster(telegram_config_disabled)

        result = await broadcaster.send_entry_signal(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000"), Decimal("49500")],
            weights=[50, 50]
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_send_entry_signal_entry_signals_disabled(self, telegram_config, sample_position_group, sample_pyramid):
        """Test that entry signal is not sent when entry signals are disabled"""
        telegram_config.send_entry_signals = False
        broadcaster = TelegramBroadcaster(telegram_config)

        result = await broadcaster.send_entry_signal(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000")],
            weights=[100]
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_send_entry_signal_test_mode(self, telegram_config_test_mode, sample_position_group, sample_pyramid):
        """Test entry signal in test mode returns fake message ID"""
        broadcaster = TelegramBroadcaster(telegram_config_test_mode)

        result = await broadcaster.send_entry_signal(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000"), Decimal("49500")],
            weights=[50, 50],
            tp_prices=[Decimal("51000"), Decimal("50500")],
            tp_mode="per_leg"
        )

        assert result == 999999  # Fake message ID

    @pytest.mark.asyncio
    async def test_send_entry_signal_with_aggregate_tp(self, telegram_config_test_mode, sample_position_group, sample_pyramid):
        """Test entry signal with aggregate TP mode"""
        broadcaster = TelegramBroadcaster(telegram_config_test_mode)

        result = await broadcaster.send_entry_signal(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000"), Decimal("49500")],
            weights=[50, 50],
            tp_mode="aggregate",
            aggregate_tp=Decimal("52000")
        )

        assert result == 999999

    @pytest.mark.asyncio
    async def test_send_entry_signal_with_tbd_prices(self, telegram_config_test_mode, sample_position_group, sample_pyramid):
        """Test entry signal with TBD (None) prices"""
        broadcaster = TelegramBroadcaster(telegram_config_test_mode)

        result = await broadcaster.send_entry_signal(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000"), None, None],
            weights=[50, 25, 25]
        )

        assert result == 999999

    @pytest.mark.asyncio
    async def test_send_entry_signal_updates_existing(self, telegram_config_test_mode, sample_position_group, sample_pyramid):
        """Test that entry signal updates existing message when update_on_pyramid is True"""
        broadcaster = TelegramBroadcaster(telegram_config_test_mode)

        # First send
        result1 = await broadcaster.send_entry_signal(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000")],
            weights=[100]
        )

        assert result1 == 999999
        assert str(sample_position_group.id) in broadcaster.message_ids

        # Second send should update
        result2 = await broadcaster.send_entry_signal(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000"), Decimal("49500")],
            weights=[50, 50]
        )

        assert result2 == 999999

    @pytest.mark.asyncio
    async def test_send_exit_signal_disabled(self, telegram_config_disabled, sample_position_group):
        """Test that exit signal is not sent when disabled"""
        broadcaster = TelegramBroadcaster(telegram_config_disabled)

        result = await broadcaster.send_exit_signal(
            position_group=sample_position_group,
            exit_price=Decimal("51000"),
            pnl_percent=Decimal("2.5"),
            pyramids_used=2
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_send_exit_signal_exit_signals_disabled(self, telegram_config, sample_position_group):
        """Test that exit signal is not sent when exit signals are disabled"""
        telegram_config.send_exit_signals = False
        broadcaster = TelegramBroadcaster(telegram_config)

        result = await broadcaster.send_exit_signal(
            position_group=sample_position_group,
            exit_price=Decimal("51000"),
            pnl_percent=Decimal("2.5"),
            pyramids_used=2
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_send_exit_signal_test_mode(self, telegram_config_test_mode, sample_position_group):
        """Test exit signal in test mode"""
        broadcaster = TelegramBroadcaster(telegram_config_test_mode)

        # Add a message ID first
        broadcaster.message_ids[str(sample_position_group.id)] = 12345

        result = await broadcaster.send_exit_signal(
            position_group=sample_position_group,
            exit_price=Decimal("51000"),
            pnl_percent=Decimal("2.5"),
            pyramids_used=2
        )

        assert result == 999999
        # Message ID should be cleaned up
        assert str(sample_position_group.id) not in broadcaster.message_ids

    @pytest.mark.asyncio
    async def test_send_message_success(self, telegram_config):
        """Test successful message sending"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"result": {"message_id": 12345}})

            # Create proper async context manager for response
            mock_response_cm = MagicMock()
            mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response_cm.__aexit__ = AsyncMock(return_value=None)

            # Create session mock
            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response_cm)

            # Create session context manager
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session_cm

            result = await broadcaster._send_message("Test message")

            assert result == 12345

    @pytest.mark.asyncio
    async def test_send_message_failure(self, telegram_config):
        """Test message sending failure"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_response = MagicMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")

            mock_response_cm = MagicMock()
            mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response_cm)

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session_cm

            result = await broadcaster._send_message("Test message")

            assert result is None

    @pytest.mark.asyncio
    async def test_send_message_exception(self, telegram_config):
        """Test message sending with exception"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(side_effect=Exception("Network error"))
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_cm

            result = await broadcaster._send_message("Test message")

            assert result is None

    @pytest.mark.asyncio
    async def test_update_message_success(self, telegram_config):
        """Test successful message update"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_response = MagicMock()
            mock_response.status = 200

            mock_response_cm = MagicMock()
            mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response_cm)

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session_cm

            result = await broadcaster._update_message(12345, "Updated message")

            assert result == 12345

    @pytest.mark.asyncio
    async def test_update_message_failure(self, telegram_config):
        """Test message update failure"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_response = MagicMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")

            mock_response_cm = MagicMock()
            mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response_cm)

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session_cm

            result = await broadcaster._update_message(12345, "Updated message")

            assert result is None

    @pytest.mark.asyncio
    async def test_update_message_exception(self, telegram_config):
        """Test message update with exception"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(side_effect=Exception("Network error"))
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_cm

            result = await broadcaster._update_message(12345, "Updated message")

            assert result is None

    @pytest.mark.asyncio
    async def test_update_message_test_mode(self, telegram_config_test_mode):
        """Test message update in test mode"""
        broadcaster = TelegramBroadcaster(telegram_config_test_mode)

        result = await broadcaster._update_message(12345, "Updated message")

        assert result == 12345

    @pytest.mark.asyncio
    async def test_test_connection_success(self, telegram_config):
        """Test successful connection test"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_get_response = MagicMock()
            mock_get_response.status = 200

            mock_post_response = MagicMock()
            mock_post_response.status = 200

            # Create context managers for both responses
            mock_get_response_cm = MagicMock()
            mock_get_response_cm.__aenter__ = AsyncMock(return_value=mock_get_response)
            mock_get_response_cm.__aexit__ = AsyncMock(return_value=None)

            mock_post_response_cm = MagicMock()
            mock_post_response_cm.__aenter__ = AsyncMock(return_value=mock_post_response)
            mock_post_response_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_get_response_cm)
            mock_session.post = MagicMock(return_value=mock_post_response_cm)

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session_cm

            success, message = await broadcaster.test_connection()

            assert success is True
            assert message == "OK"

    @pytest.mark.asyncio
    async def test_test_connection_bot_token_invalid(self, telegram_config):
        """Test connection test with invalid bot token"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_response = MagicMock()
            mock_response.status = 401
            mock_response.text = AsyncMock(return_value="Unauthorized")

            mock_response_cm = MagicMock()
            mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response_cm)

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session_cm

            success, message = await broadcaster.test_connection()

            assert success is False
            assert "Unauthorized" in message

    @pytest.mark.asyncio
    async def test_test_connection_channel_access_denied(self, telegram_config):
        """Test connection test with channel access denied"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_get_response = MagicMock()
            mock_get_response.status = 200

            mock_post_response = MagicMock()
            mock_post_response.status = 403
            mock_post_response.text = AsyncMock(return_value="Forbidden")

            mock_get_response_cm = MagicMock()
            mock_get_response_cm.__aenter__ = AsyncMock(return_value=mock_get_response)
            mock_get_response_cm.__aexit__ = AsyncMock(return_value=None)

            mock_post_response_cm = MagicMock()
            mock_post_response_cm.__aenter__ = AsyncMock(return_value=mock_post_response)
            mock_post_response_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_get_response_cm)
            mock_session.post = MagicMock(return_value=mock_post_response_cm)

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session_cm

            success, message = await broadcaster.test_connection()

            assert success is False
            assert "Forbidden" in message

    @pytest.mark.asyncio
    async def test_test_connection_exception(self, telegram_config):
        """Test connection test with exception"""
        broadcaster = TelegramBroadcaster(telegram_config)

        with patch('app.services.telegram_broadcaster.aiohttp.ClientSession') as mock_session_class:
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_cm

            success, message = await broadcaster.test_connection()

            assert success is False
            assert "Connection refused" in message

    def test_build_entry_message_basic(self, telegram_config, sample_position_group, sample_pyramid):
        """Test building basic entry message"""
        broadcaster = TelegramBroadcaster(telegram_config)

        message = broadcaster._build_entry_message(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000"), Decimal("49500")],
            weights=[50, 50]
        )

        assert "Entry Setup" in message
        assert "BTCUSDT" in message
        assert "50000" in message
        assert "49500" in message
        assert "50 %" in message

    def test_build_entry_message_with_per_leg_tp(self, telegram_config, sample_position_group, sample_pyramid):
        """Test building entry message with per-leg TP"""
        broadcaster = TelegramBroadcaster(telegram_config)

        message = broadcaster._build_entry_message(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000")],
            weights=[100],
            tp_prices=[Decimal("51000")],
            tp_mode="per_leg"
        )

        assert "TP :" in message
        assert "51000" in message

    def test_build_entry_message_with_aggregate_tp(self, telegram_config, sample_position_group, sample_pyramid):
        """Test building entry message with aggregate TP"""
        broadcaster = TelegramBroadcaster(telegram_config)

        message = broadcaster._build_entry_message(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000")],
            weights=[100],
            tp_mode="aggregate",
            aggregate_tp=Decimal("52000")
        )

        assert "TP aggregate:" in message
        assert "52000" in message

    def test_build_entry_message_with_tbd(self, telegram_config, sample_position_group, sample_pyramid):
        """Test building entry message with TBD prices"""
        broadcaster = TelegramBroadcaster(telegram_config)

        message = broadcaster._build_entry_message(
            position_group=sample_position_group,
            pyramid=sample_pyramid,
            entry_prices=[Decimal("50000"), None],
            weights=[50, 50]
        )

        assert "TBD" in message

    def test_build_exit_message(self, telegram_config, sample_position_group):
        """Test building exit message"""
        broadcaster = TelegramBroadcaster(telegram_config)

        message = broadcaster._build_exit_message(
            position_group=sample_position_group,
            exit_price=Decimal("51000"),
            pnl_percent=Decimal("2.5"),
            pyramids_used=2
        )

        assert "Engine Exit" in message
        assert "51000" in message
        assert "2.5" in message
        assert "2" in message
