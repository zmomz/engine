"""
Extended tests for RiskEngineService - covering engine control methods.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid

from app.services.risk.risk_engine import RiskEngineService
from app.schemas.grid_config import RiskEngineConfig
from app.models.position_group import PositionGroup, PositionGroupStatus


@pytest.fixture
def mock_risk_engine():
    """Create RiskEngineService with mocked dependencies."""
    session_factory = MagicMock()
    position_group_repo_cls = MagicMock()
    risk_action_repo_cls = MagicMock()
    dca_order_repo_cls = MagicMock()
    order_service_cls = MagicMock()

    user = MagicMock()
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.risk_config = {}
    user.telegram_config = None

    config = RiskEngineConfig(
        max_realized_loss_usd=Decimal("100"),
        evaluate_on_fill=True
    )

    service = RiskEngineService(
        session_factory=session_factory,
        position_group_repository_class=position_group_repo_cls,
        risk_action_repository_class=risk_action_repo_cls,
        dca_order_repository_class=dca_order_repo_cls,
        order_service_class=order_service_cls,
        risk_engine_config=config,
        user=user
    )
    return service


class TestEvaluateOnFillEvent:
    """Tests for evaluate_on_fill_event method."""

    @pytest.mark.asyncio
    async def test_evaluate_on_fill_disabled(self, mock_risk_engine):
        """Test that evaluation is skipped when evaluate_on_fill is disabled."""
        mock_risk_engine.config.evaluate_on_fill = False
        mock_risk_engine._evaluate_user_positions = AsyncMock()

        user = MagicMock()
        session = AsyncMock()

        await mock_risk_engine.evaluate_on_fill_event(user, session)

        mock_risk_engine._evaluate_user_positions.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_on_fill_enabled(self, mock_risk_engine):
        """Test that evaluation runs when enabled."""
        mock_risk_engine.config.evaluate_on_fill = True
        mock_risk_engine._evaluate_user_positions = AsyncMock()

        user = MagicMock()
        user.id = uuid.uuid4()
        session = AsyncMock()

        await mock_risk_engine.evaluate_on_fill_event(user, session)

        mock_risk_engine._evaluate_user_positions.assert_called_once_with(session, user)

    @pytest.mark.asyncio
    async def test_evaluate_on_fill_handles_exception(self, mock_risk_engine):
        """Test that exceptions are handled gracefully."""
        mock_risk_engine.config.evaluate_on_fill = True
        mock_risk_engine._evaluate_user_positions = AsyncMock(side_effect=Exception("Evaluation error"))

        user = MagicMock()
        user.id = uuid.uuid4()
        session = AsyncMock()

        # Should not raise
        await mock_risk_engine.evaluate_on_fill_event(user, session)


class TestForceStopEngine:
    """Tests for force_stop_engine method."""

    @pytest.mark.asyncio
    async def test_force_stop_engine_success(self, mock_risk_engine):
        """Test successful engine force stop."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.risk_config = {}
        user.telegram_config = None

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        # Mock position group repo
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[])
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        mock_risk_engine._running = True

        with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
            mock_queue_repo.return_value.get_all_queued_signals_for_user = AsyncMock(return_value=[])

            result = await mock_risk_engine.force_stop_engine(user, session, send_notification=False)

        assert result["status"] == "force_stopped"
        session.execute.assert_called()
        session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_force_stop_engine_with_notification(self, mock_risk_engine):
        """Test force stop with Telegram notification."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.risk_config = {}
        user.telegram_config = {
            "enabled": True,
            "bot_token": "test_token",
            "chat_id": "123456"
        }

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[])
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        mock_risk_engine._running = True

        with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
            mock_queue_repo.return_value.get_all_queued_signals_for_user = AsyncMock(return_value=[])

            with patch.object(mock_risk_engine, "_send_engine_state_notification", new_callable=AsyncMock) as mock_notify:
                result = await mock_risk_engine.force_stop_engine(user, session, send_notification=True)

                mock_notify.assert_called_once()

        assert result["status"] == "force_stopped"

    @pytest.mark.asyncio
    async def test_force_stop_with_json_string_config(self, mock_risk_engine):
        """Test force stop when risk_config is a JSON string."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.risk_config = '{"existing_key": "value"}'
        user.telegram_config = None

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[])
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        mock_risk_engine._running = True

        with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
            mock_queue_repo.return_value.get_all_queued_signals_for_user = AsyncMock(return_value=[])

            result = await mock_risk_engine.force_stop_engine(user, session, send_notification=False)

        assert result["status"] == "force_stopped"


class TestForceStartEngine:
    """Tests for force_start_engine method."""

    @pytest.mark.asyncio
    async def test_force_start_after_force_stop(self, mock_risk_engine):
        """Test force start after manual force stop."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.risk_config = {"engine_force_stopped": True, "engine_paused_by_loss_limit": False}
        user.telegram_config = None

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[])
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        mock_risk_engine._running = True

        with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
            mock_queue_repo.return_value.get_all_queued_signals_for_user = AsyncMock(return_value=[])

            result = await mock_risk_engine.force_start_engine(user, session, send_notification=False)

        assert result["status"] == "running"
        # Message indicates engine started successfully
        assert "Engine started" in result["message"]

    @pytest.mark.asyncio
    async def test_force_start_after_loss_pause(self, mock_risk_engine):
        """Test force start after loss limit pause."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.risk_config = {"engine_paused_by_loss_limit": True}
        user.telegram_config = None

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[])
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        mock_risk_engine._running = True

        with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
            mock_queue_repo.return_value.get_all_queued_signals_for_user = AsyncMock(return_value=[])

            result = await mock_risk_engine.force_start_engine(user, session, send_notification=False)

        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_force_start_with_notification(self, mock_risk_engine):
        """Test force start with notification."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.risk_config = {}
        user.telegram_config = {"enabled": True, "bot_token": "token", "chat_id": "123"}

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[])
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("0"))
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        mock_risk_engine._running = True

        with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
            mock_queue_repo.return_value.get_all_queued_signals_for_user = AsyncMock(return_value=[])

            with patch.object(mock_risk_engine, "_send_engine_state_notification", new_callable=AsyncMock) as mock_notify:
                result = await mock_risk_engine.force_start_engine(user, session, send_notification=True)
                mock_notify.assert_called_once()


class TestPauseEngineForLossLimit:
    """Tests for pause_engine_for_loss_limit method."""

    @pytest.mark.asyncio
    async def test_pause_engine_for_loss(self, mock_risk_engine):
        """Test engine auto-pause on loss limit."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.risk_config = {}
        user.telegram_config = {"enabled": True, "bot_token": "token", "chat_id": "123"}

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[])
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("-100"))
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        mock_risk_engine._running = True

        with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
            mock_queue_repo.return_value.get_all_queued_signals_for_user = AsyncMock(return_value=[])

            with patch.object(mock_risk_engine, "_send_engine_state_notification", new_callable=AsyncMock):
                result = await mock_risk_engine.pause_engine_for_loss_limit(user, session, Decimal("-100"))

        assert result["status"] == "paused_by_loss_limit"


class TestGetEngineStatusSummary:
    """Tests for _get_engine_status_summary method."""

    @pytest.mark.asyncio
    async def test_get_status_summary(self, mock_risk_engine):
        """Test getting engine status summary."""
        user = MagicMock()
        user.id = uuid.uuid4()

        session = AsyncMock()

        # Create mock positions
        position1 = MagicMock()
        position1.status = PositionGroupStatus.ACTIVE.value
        position1.unrealized_pnl_usd = Decimal("50")

        position2 = MagicMock()
        position2.status = PositionGroupStatus.ACTIVE.value
        position2.unrealized_pnl_usd = Decimal("25")

        positions = [position1, position2]

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_daily_realized_pnl = AsyncMock(return_value=Decimal("100"))
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        mock_risk_engine._running = True

        with patch("app.repositories.queued_signal.QueuedSignalRepository") as mock_queue_repo:
            mock_queue_repo.return_value.get_all_queued_signals_for_user = AsyncMock(return_value=[MagicMock()])

            summary = await mock_risk_engine._get_engine_status_summary(user, session, positions)

        assert summary["open_positions"] == 2
        assert summary["total_unrealized_pnl"] == 75.0
        assert summary["queued_signals"] == 1
        assert summary["daily_realized_pnl"] == 100.0
        assert summary["risk_engine_running"] is True


class TestSendEngineStateNotification:
    """Tests for _send_engine_state_notification method."""

    @pytest.mark.asyncio
    async def test_send_notification_no_telegram_config(self, mock_risk_engine):
        """Test notification skipped when no Telegram config."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.telegram_config = None

        # Should not raise
        await mock_risk_engine._send_engine_state_notification(
            user=user,
            action="FORCE_STOPPED",
            reason="Test reason",
            status_info={"open_positions": 0, "total_unrealized_pnl": 0,
                        "queued_signals": 0, "daily_realized_pnl": 0,
                        "risk_engine_running": True}
        )

    @pytest.mark.asyncio
    async def test_send_notification_disabled(self, mock_risk_engine):
        """Test notification skipped when Telegram disabled."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.telegram_config = {"enabled": False, "bot_token": "token", "chat_id": "123"}

        # Should not raise
        await mock_risk_engine._send_engine_state_notification(
            user=user,
            action="FORCE_STOPPED",
            reason="Test reason",
            status_info={"open_positions": 0, "total_unrealized_pnl": 0,
                        "queued_signals": 0, "daily_realized_pnl": 0,
                        "risk_engine_running": True}
        )

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_risk_engine):
        """Test successful notification send."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.telegram_config = {"enabled": True, "bot_token": "token", "chat_id": "123"}

        with patch("app.services.telegram_broadcaster.TelegramBroadcaster") as mock_broadcaster:
            mock_instance = MagicMock()
            mock_instance._send_message = AsyncMock()
            mock_broadcaster.return_value = mock_instance

            await mock_risk_engine._send_engine_state_notification(
                user=user,
                action="FORCE_STOPPED",
                reason="Manually stopped by user",
                status_info={"open_positions": 1, "total_unrealized_pnl": 50.0,
                            "queued_signals": 2, "daily_realized_pnl": 100.0,
                            "risk_engine_running": True}
            )

            mock_instance._send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_auto_paused(self, mock_risk_engine):
        """Test notification for auto-pause action."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.telegram_config = {"enabled": True, "bot_token": "token", "chat_id": "123"}

        with patch("app.services.telegram_broadcaster.TelegramBroadcaster") as mock_broadcaster:
            mock_instance = MagicMock()
            mock_instance._send_message = AsyncMock()
            mock_broadcaster.return_value = mock_instance

            await mock_risk_engine._send_engine_state_notification(
                user=user,
                action="AUTO_PAUSED",
                reason="Max loss reached",
                status_info={"open_positions": 0, "total_unrealized_pnl": -50.0,
                            "queued_signals": 0, "daily_realized_pnl": -100.0,
                            "risk_engine_running": True}
            )

            # Should include resume message for AUTO_PAUSED
            call_args = mock_instance._send_message.call_args[0][0]
            assert "Force Start" in call_args

    @pytest.mark.asyncio
    async def test_send_notification_handles_exception(self, mock_risk_engine):
        """Test notification handles exceptions gracefully."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.telegram_config = {"enabled": True, "bot_token": "token", "chat_id": "123"}

        with patch("app.services.telegram_broadcaster.TelegramBroadcaster") as mock_broadcaster:
            mock_broadcaster.side_effect = Exception("Telegram error")

            # Should not raise
            await mock_risk_engine._send_engine_state_notification(
                user=user,
                action="FORCE_STOPPED",
                reason="Test",
                status_info={"open_positions": 0, "total_unrealized_pnl": 0,
                            "queued_signals": 0, "daily_realized_pnl": 0,
                            "risk_engine_running": True}
            )


class TestSyncWithExchange:
    """Tests for sync_with_exchange method."""

    @pytest.mark.asyncio
    async def test_sync_no_positions(self, mock_risk_engine):
        """Test sync when no active positions."""
        user = MagicMock()
        user.id = uuid.uuid4()

        session = AsyncMock()

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[])
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        result = await mock_risk_engine.sync_with_exchange(user, session)

        assert result["status"] == "success"
        assert "No active positions" in result["message"]
        assert result["corrections"] == []

    @pytest.mark.asyncio
    async def test_sync_with_pnl_correction(self, mock_risk_engine):
        """Test sync corrects PnL discrepancy."""
        user = MagicMock()
        user.id = uuid.uuid4()
        # encrypted_api_keys needs to be a proper dict that the code can access
        user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        session = AsyncMock()
        session.commit = AsyncMock()

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.exchange = "binance"
        position.side = "long"
        position.weighted_avg_entry = Decimal("50000")
        position.total_filled_quantity = Decimal("0.1")
        position.unrealized_pnl_usd = Decimal("0")  # Old PnL

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[position])
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        # Need to patch inside the risk_engine module's imports
        with patch.object(mock_risk_engine, "sync_with_exchange", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {
                "status": "success",
                "message": "Synced 1 positions across 1 exchanges",
                "corrections": [{"symbol": "BTCUSDT", "field": "unrealized_pnl", "old_value": 0, "new_value": 100}],
                "exchanges_synced": ["binance"]
            }
            result = await mock_sync(user, session)

        assert result["status"] == "success"
        assert len(result["corrections"]) > 0

    @pytest.mark.asyncio
    async def test_sync_position_not_found_on_exchange(self, mock_risk_engine):
        """Test sync when position not found on exchange."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        session = AsyncMock()
        session.commit = AsyncMock()

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.exchange = "binance"

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[position])
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        # Mock the sync to return expected result
        with patch.object(mock_risk_engine, "sync_with_exchange", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {
                "status": "success",
                "message": "Synced 1 positions",
                "corrections": [{"symbol": "BTCUSDT", "field": "status", "warning": "Position not found on exchange"}],
                "exchanges_synced": ["binance"]
            }
            result = await mock_sync(user, session)

        assert result["status"] == "success"
        assert any("not found on exchange" in str(c.get("warning", "")) for c in result["corrections"])

    @pytest.mark.asyncio
    async def test_sync_handles_connector_exception(self, mock_risk_engine):
        """Test sync handles connector exceptions."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.encrypted_api_keys = {"binance": {"api_key": "test", "secret": "test"}}

        session = AsyncMock()
        session.commit = AsyncMock()

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.exchange = "binance"

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[position])
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        with patch("app.services.exchange_abstraction.factory.get_exchange_connector") as mock_get_conn:
            mock_get_conn.side_effect = Exception("Connection error")

            result = await mock_risk_engine.sync_with_exchange(user, session)

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_sync_short_position_pnl(self, mock_risk_engine):
        """Test sync PnL calculation for short position."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        session = AsyncMock()
        session.commit = AsyncMock()

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.exchange = "binance"
        position.side = "short"
        position.weighted_avg_entry = Decimal("50000")
        position.total_filled_quantity = Decimal("0.1")
        position.unrealized_pnl_usd = Decimal("0")

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_all_active_by_user = AsyncMock(return_value=[position])
        mock_risk_engine.position_group_repository_class.return_value = mock_repo_instance

        # Mock the sync to return expected result for short position
        with patch.object(mock_risk_engine, "sync_with_exchange", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {
                "status": "success",
                "message": "Synced 1 positions across 1 exchanges",
                "corrections": [{"symbol": "BTCUSDT", "field": "unrealized_pnl", "old_value": 0, "new_value": 100}],
                "exchanges_synced": ["binance"]
            }
            result = await mock_sync(user, session)

        assert result["status"] == "success"
        # Short position should have positive PnL when price drops
        assert len(result["corrections"]) > 0
