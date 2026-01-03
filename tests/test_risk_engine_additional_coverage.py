"""
Additional tests for RiskEngineService to cover remaining edge cases.
Focuses on: force_stop/start with JSON string config, pause_engine_for_loss_limit,
sync_with_exchange edge cases, and pre-trade risk checks for engine states.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
import json

from app.services.risk_engine import RiskEngineService
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.user import User
from app.schemas.grid_config import RiskEngineConfig


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
def mock_user():
    user_id = uuid.uuid4()
    user = MagicMock(spec=User)
    user.id = user_id
    user.risk_config = {}
    user.encrypted_api_keys = {"mock": {"api_key": "test"}}
    user.telegram_config = None
    return user


class TestForceStopEngineJsonConfig:
    """Tests for force_stop_engine with JSON string config."""

    @pytest.mark.asyncio
    async def test_force_stop_with_json_string_config(self, mock_config, mock_user):
        """Test force_stop_engine when risk_config is a JSON string."""
        mock_user.risk_config = json.dumps({"max_realized_loss_usd": 50})
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[])
        mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

        async def mock_session_factory():
            yield mock_session

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
                mock_queue_repo_instance = AsyncMock()
                mock_queue_repo_instance.get_all_queued_signals_for_user = AsyncMock(return_value=[])
                mock_queue_repo.return_value = mock_queue_repo_instance

                service = RiskEngineService(
                    session_factory=mock_session_factory,
                    position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                    risk_action_repository_class=MagicMock(),
                    dca_order_repository_class=MagicMock(),
                    order_service_class=MagicMock(),
                    risk_engine_config=mock_config,
                    user=mock_user
                )

                result = await service.force_stop_engine(mock_user, mock_session, send_notification=False)

                assert result["status"] == "force_stopped"
                mock_session.execute.assert_called_once()
                mock_session.commit.assert_called_once()


class TestForceStartEngineJsonConfig:
    """Tests for force_start_engine with JSON string config."""

    @pytest.mark.asyncio
    async def test_force_start_with_json_string_config(self, mock_config, mock_user):
        """Test force_start_engine when risk_config is a JSON string."""
        mock_user.risk_config = json.dumps({
            "engine_force_stopped": True,
            "engine_paused_by_loss_limit": False
        })
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[])
        mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

        async def mock_session_factory():
            yield mock_session

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
                mock_queue_repo_instance = AsyncMock()
                mock_queue_repo_instance.get_all_queued_signals_for_user = AsyncMock(return_value=[])
                mock_queue_repo.return_value = mock_queue_repo_instance

                service = RiskEngineService(
                    session_factory=mock_session_factory,
                    position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                    risk_action_repository_class=MagicMock(),
                    dca_order_repository_class=MagicMock(),
                    order_service_class=MagicMock(),
                    risk_engine_config=mock_config,
                    user=mock_user
                )

                result = await service.force_start_engine(mock_user, mock_session, send_notification=False)

                assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_force_start_after_loss_limit_pause(self, mock_config, mock_user):
        """Test force_start_engine shows correct reason after loss limit pause."""
        mock_user.risk_config = {
            "engine_force_stopped": False,
            "engine_paused_by_loss_limit": True  # Was paused by loss limit
        }
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[])
        mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

        async def mock_session_factory():
            yield mock_session

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
                mock_queue_repo_instance = AsyncMock()
                mock_queue_repo_instance.get_all_queued_signals_for_user = AsyncMock(return_value=[])
                mock_queue_repo.return_value = mock_queue_repo_instance

                service = RiskEngineService(
                    session_factory=mock_session_factory,
                    position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                    risk_action_repository_class=MagicMock(),
                    dca_order_repository_class=MagicMock(),
                    order_service_class=MagicMock(),
                    risk_engine_config=mock_config,
                    user=mock_user
                )

                result = await service.force_start_engine(mock_user, mock_session, send_notification=False)

                assert result["status"] == "running"


class TestPauseEngineForLossLimit:
    """Tests for pause_engine_for_loss_limit."""

    @pytest.mark.asyncio
    async def test_pause_engine_with_json_string_config(self, mock_config, mock_user):
        """Test pause_engine_for_loss_limit when config is a JSON string."""
        mock_user.risk_config = json.dumps({})
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[])
        mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("-150"))

        async def mock_session_factory():
            yield mock_session

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
                mock_queue_repo_instance = AsyncMock()
                mock_queue_repo_instance.get_all_queued_signals_for_user = AsyncMock(return_value=[])
                mock_queue_repo.return_value = mock_queue_repo_instance

                service = RiskEngineService(
                    session_factory=mock_session_factory,
                    position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                    risk_action_repository_class=MagicMock(),
                    dca_order_repository_class=MagicMock(),
                    order_service_class=MagicMock(),
                    risk_engine_config=mock_config,
                    user=mock_user
                )

                result = await service.pause_engine_for_loss_limit(
                    mock_user, mock_session, Decimal("-150")
                )

                assert result["status"] == "paused_by_loss_limit"


class TestSyncWithExchange:
    """Tests for sync_with_exchange."""

    @pytest.mark.asyncio
    async def test_sync_no_active_positions(self, mock_config, mock_user):
        """Test sync_with_exchange when there are no active positions."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[])

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

            result = await service.sync_with_exchange(mock_user, mock_session)

            assert result["status"] == "success"
            assert result["message"] == "No active positions to sync"
            assert result["corrections"] == []

    @pytest.mark.asyncio
    async def test_sync_position_not_found_on_exchange(self, mock_config, mock_user):
        """Test sync_with_exchange when position is not found on exchange."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_position = MagicMock()
        mock_position.symbol = "BTC/USDT"
        mock_position.exchange = "mock"
        mock_position.side = "long"
        mock_position.weighted_avg_entry = Decimal("50000")
        mock_position.total_filled_quantity = Decimal("0.1")
        mock_position.unrealized_pnl_usd = Decimal("100")

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[mock_position])

        mock_connector = AsyncMock()
        mock_connector.get_positions = AsyncMock(return_value=[])  # No positions on exchange
        mock_connector.close = AsyncMock()

        async def mock_session_factory():
            yield mock_session

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            with patch("app.services.risk.risk_engine.get_exchange_connector", return_value=mock_connector):
                service = RiskEngineService(
                    session_factory=mock_session_factory,
                    position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                    risk_action_repository_class=MagicMock(),
                    dca_order_repository_class=MagicMock(),
                    order_service_class=MagicMock(),
                    risk_engine_config=mock_config,
                    user=mock_user
                )

                result = await service.sync_with_exchange(mock_user, mock_session)

                assert result["status"] == "success"
                # Should report position not found warning
                assert any("not found on exchange" in c.get("warning", "") for c in result["corrections"])

    @pytest.mark.asyncio
    async def test_sync_pnl_correction_long(self, mock_config, mock_user):
        """Test sync_with_exchange corrects PnL for long position."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_position = MagicMock()
        mock_position.symbol = "BTC/USDT"
        mock_position.exchange = "mock"
        mock_position.side = "long"
        mock_position.weighted_avg_entry = Decimal("50000")
        mock_position.total_filled_quantity = Decimal("0.1")
        mock_position.unrealized_pnl_usd = Decimal("50")  # Old value

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[mock_position])

        mock_connector = AsyncMock()
        mock_connector.get_positions = AsyncMock(return_value=[
            {"symbol": "BTC/USDT", "markPrice": "51000"}  # Price went up
        ])
        mock_connector.close = AsyncMock()

        async def mock_session_factory():
            yield mock_session

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            with patch("app.services.risk.risk_engine.get_exchange_connector", return_value=mock_connector):
                service = RiskEngineService(
                    session_factory=mock_session_factory,
                    position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                    risk_action_repository_class=MagicMock(),
                    dca_order_repository_class=MagicMock(),
                    order_service_class=MagicMock(),
                    risk_engine_config=mock_config,
                    user=mock_user
                )

                result = await service.sync_with_exchange(mock_user, mock_session)

                assert result["status"] == "success"
                # New PnL should be (51000 - 50000) * 0.1 = 100
                assert mock_position.unrealized_pnl_usd == Decimal("100")

    @pytest.mark.asyncio
    async def test_sync_skips_exchange_without_keys(self, mock_config, mock_user):
        """Test sync_with_exchange skips exchanges user doesn't have keys for."""
        mock_user.encrypted_api_keys = {"mock": {"api_key": "test"}}  # Only mock exchange

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_position = MagicMock()
        mock_position.symbol = "BTC/USDT"
        mock_position.exchange = "binance"  # Different exchange
        mock_position.side = "long"
        mock_position.weighted_avg_entry = Decimal("50000")

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[mock_position])

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

            result = await service.sync_with_exchange(mock_user, mock_session)

            assert result["status"] == "success"
            assert "binance" not in result.get("exchanges_synced", [])


class TestValidatePreTradeRiskEngineStates:
    """Tests for validate_pre_trade_risk engine state checks."""

    @pytest.mark.asyncio
    async def test_rejects_when_engine_paused_by_loss_limit(self, mock_config, mock_user):
        """Test validate_pre_trade_risk rejects when engine is paused by loss limit."""
        mock_config.engine_paused_by_loss_limit = True

        mock_session = AsyncMock()
        mock_pos_repo = MagicMock()
        mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

        from app.models.queued_signal import QueuedSignal
        signal = QueuedSignal(user_id=mock_user.id, symbol="BTC/USD", exchange="mock", timeframe=60)

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            service = RiskEngineService(
                session_factory=MagicMock(),
                position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                risk_action_repository_class=MagicMock(),
                dca_order_repository_class=MagicMock(),
                order_service_class=MagicMock(),
                risk_engine_config=mock_config,
                user=mock_user
            )

            result = await service.validate_pre_trade_risk(
                signal, [], Decimal("100"), mock_session
            )

            assert result[0] is False
            assert "max realized loss" in result[1].lower()

    @pytest.mark.asyncio
    async def test_rejects_when_engine_force_stopped(self, mock_config, mock_user):
        """Test validate_pre_trade_risk rejects when engine is force stopped."""
        mock_config.engine_force_stopped = True

        mock_session = AsyncMock()
        mock_pos_repo = MagicMock()
        mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

        from app.models.queued_signal import QueuedSignal
        signal = QueuedSignal(user_id=mock_user.id, symbol="BTC/USD", exchange="mock", timeframe=60)

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            service = RiskEngineService(
                session_factory=MagicMock(),
                position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                risk_action_repository_class=MagicMock(),
                dca_order_repository_class=MagicMock(),
                order_service_class=MagicMock(),
                risk_engine_config=mock_config,
                user=mock_user
            )

            result = await service.validate_pre_trade_risk(
                signal, [], Decimal("100"), mock_session
            )

            assert result[0] is False
            assert "force stopped" in result[1].lower()

    @pytest.mark.asyncio
    async def test_uses_user_risk_config_when_available(self, mock_config, mock_user):
        """Test validate_pre_trade_risk uses user's risk config when available."""
        # Service config doesn't have engine stopped
        mock_config.engine_force_stopped = False

        # But user's config has it stopped
        mock_user.risk_config = {"engine_force_stopped": True}

        mock_session = AsyncMock()
        mock_pos_repo = MagicMock()
        mock_pos_repo.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))

        from app.models.queued_signal import QueuedSignal
        signal = QueuedSignal(user_id=mock_user.id, symbol="BTC/USD", exchange="mock", timeframe=60)

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            service = RiskEngineService(
                session_factory=MagicMock(),
                position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                risk_action_repository_class=MagicMock(),
                dca_order_repository_class=MagicMock(),
                order_service_class=MagicMock(),
                risk_engine_config=mock_config,
                user=mock_user
            )

            result = await service.validate_pre_trade_risk(
                signal, [], Decimal("100"), mock_session
            )

            assert result[0] is False
            assert "force stopped" in result[1].lower()


class TestSendEngineStateNotification:
    """Tests for _send_engine_state_notification."""

    @pytest.mark.asyncio
    async def test_skips_notification_when_no_telegram_config(self, mock_config, mock_user):
        """Test notification is skipped when user has no telegram config."""
        mock_user.telegram_config = None

        async def mock_session_factory():
            yield AsyncMock()

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

            # Should not raise
            await service._send_engine_state_notification(
                mock_user,
                "FORCE_STOPPED",
                "Test reason",
                {"open_positions": 0, "total_unrealized_pnl": 0, "queued_signals": 0,
                 "daily_realized_pnl": 0, "risk_engine_running": False}
            )

    @pytest.mark.asyncio
    async def test_skips_notification_when_telegram_disabled(self, mock_config, mock_user):
        """Test notification is skipped when telegram is disabled."""
        mock_user.telegram_config = {"enabled": False, "bot_token": "test", "chat_id": "123"}

        async def mock_session_factory():
            yield AsyncMock()

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

            # Should not raise
            await service._send_engine_state_notification(
                mock_user,
                "FORCE_STOPPED",
                "Test reason",
                {"open_positions": 0, "total_unrealized_pnl": 0, "queued_signals": 0,
                 "daily_realized_pnl": 0, "risk_engine_running": False}
            )


class TestGetCurrentStatusEdgeCases:
    """Tests for get_current_status edge cases."""

    @pytest.mark.asyncio
    async def test_raises_error_without_user_context(self, mock_config):
        """Test get_current_status raises error without user context."""
        async def mock_session_factory():
            yield AsyncMock()

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

            with pytest.raises(ValueError, match="User context required"):
                await service.get_current_status()


class TestReportHealth:
    """Tests for _report_health method."""

    @pytest.mark.asyncio
    async def test_report_health_success(self, mock_config):
        """Test _report_health updates cache."""
        async def mock_session_factory():
            yield AsyncMock()

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            service = RiskEngineService(
                session_factory=mock_session_factory,
                position_group_repository_class=MagicMock(),
                risk_action_repository_class=MagicMock(),
                dca_order_repository_class=MagicMock(),
                order_service_class=MagicMock(),
                risk_engine_config=mock_config
            )

            mock_cache = AsyncMock()
            mock_cache.update_service_health = AsyncMock()

            # The get_cache is imported at top of module, so patch from inside _report_health
            # It's imported inside the method, so use the core.cache path
            async def mock_get_cache():
                return mock_cache

            with patch("app.core.cache.get_cache", mock_get_cache):
                await service._report_health("running", {"cycle_count": 10})

                mock_cache.update_service_health.assert_called_once_with(
                    "risk_engine", "running", {"cycle_count": 10}
                )

    @pytest.mark.asyncio
    async def test_report_health_handles_cache_error(self, mock_config):
        """Test _report_health handles cache errors gracefully."""
        async def mock_session_factory():
            yield AsyncMock()

        with patch("app.services.exchange_abstraction.factory.EncryptionService"):
            service = RiskEngineService(
                session_factory=mock_session_factory,
                position_group_repository_class=MagicMock(),
                risk_action_repository_class=MagicMock(),
                dca_order_repository_class=MagicMock(),
                order_service_class=MagicMock(),
                risk_engine_config=mock_config
            )

            with patch("app.services.risk.risk_engine.get_cache", side_effect=Exception("Cache error")):
                # Should not raise
                await service._report_health("running", {})
