"""
Tests for PositionCloser - Position exit and closing logic.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.position.position_closer import (
    _get_exchange_connector_for_user,
    save_close_action,
    execute_handle_exit_signal
)
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.risk_action import RiskAction, RiskActionType
from app.models.user import User


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.encrypted_api_keys = {
        "binance": {"encrypted_data": "mock_encrypted_data"}
    }
    return user


@pytest.fixture
def mock_position_group():
    pg = MagicMock(spec=PositionGroup)
    pg.id = uuid.uuid4()
    pg.user_id = uuid.uuid4()
    pg.exchange = "binance"
    pg.symbol = "BTCUSDT"
    pg.timeframe = 60
    pg.side = "long"
    pg.status = PositionGroupStatus.ACTIVE
    pg.pyramid_count = 1
    pg.weighted_avg_entry = Decimal("50000")
    pg.total_invested_usd = Decimal("1000")
    pg.total_filled_quantity = Decimal("0.02")
    pg.realized_pnl_usd = Decimal("0")
    pg.unrealized_pnl_usd = Decimal("0")
    pg.created_at = datetime.utcnow() - timedelta(hours=5)
    pg.closed_at = None
    return pg


class TestGetExchangeConnectorForUser:
    """Tests for _get_exchange_connector_for_user function."""

    def test_get_connector_dict_format(self, mock_user):
        """Test getting connector with dict format API keys."""
        with patch('app.services.position.position_closer.get_exchange_connector') as mock_get:
            mock_connector = MagicMock()
            mock_get.return_value = mock_connector

            result = _get_exchange_connector_for_user(mock_user, "binance")

            assert result == mock_connector
            mock_get.assert_called_once_with(
                "binance",
                {"encrypted_data": "mock_encrypted_data"}
            )

    def test_get_connector_dict_format_case_insensitive(self, mock_user):
        """Test getting connector with different case exchange name."""
        mock_user.encrypted_api_keys = {
            "binance": {"encrypted_data": "mock"}
        }

        with patch('app.services.position.position_closer.get_exchange_connector') as mock_get:
            mock_connector = MagicMock()
            mock_get.return_value = mock_connector

            result = _get_exchange_connector_for_user(mock_user, "BINANCE")

            assert result == mock_connector

    def test_get_connector_legacy_format(self, mock_user):
        """Test getting connector with legacy single encrypted_data format."""
        mock_user.encrypted_api_keys = {
            "encrypted_data": "legacy_encrypted_data"
        }

        with patch('app.services.position.position_closer.get_exchange_connector') as mock_get:
            mock_connector = MagicMock()
            mock_get.return_value = mock_connector

            result = _get_exchange_connector_for_user(mock_user, "binance")

            assert result == mock_connector

    def test_get_connector_string_format(self, mock_user):
        """Test getting connector with string format API keys."""
        mock_user.encrypted_api_keys = "string_encrypted_data"

        with patch('app.services.position.position_closer.get_exchange_connector') as mock_get:
            mock_connector = MagicMock()
            mock_get.return_value = mock_connector

            result = _get_exchange_connector_for_user(mock_user, "binance")

            mock_get.assert_called_once_with(
                "binance",
                {"encrypted_data": "string_encrypted_data"}
            )

    def test_get_connector_exchange_not_found(self, mock_user):
        """Test error when exchange not found in keys."""
        mock_user.encrypted_api_keys = {
            "bybit": {"encrypted_data": "mock"}
        }

        with pytest.raises(ValueError, match="No API keys found for exchange"):
            _get_exchange_connector_for_user(mock_user, "binance")

    def test_get_connector_invalid_format(self, mock_user):
        """Test error with invalid API keys format."""
        mock_user.encrypted_api_keys = 12345  # Invalid type

        with pytest.raises(ValueError, match="Invalid format for encrypted_api_keys"):
            _get_exchange_connector_for_user(mock_user, "binance")


class TestSaveCloseAction:
    """Tests for save_close_action function."""

    @pytest.mark.asyncio
    async def test_save_close_action_manual(self, mock_session, mock_position_group):
        """Test saving manual close action."""
        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("51000"),
                exit_reason="manual",
                realized_pnl=Decimal("100"),
                quantity_closed=Decimal("0.02")
            )

            mock_repo_instance.create.assert_called_once()
            mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_close_action_engine(self, mock_session, mock_position_group):
        """Test saving engine close action."""
        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("51000"),
                exit_reason="engine",
                realized_pnl=Decimal("100"),
                quantity_closed=Decimal("0.02")
            )

            mock_repo_instance.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_close_action_tp_hit(self, mock_session, mock_position_group):
        """Test saving TP hit close action."""
        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("52000"),
                exit_reason="tp_hit",
                realized_pnl=Decimal("200"),
                quantity_closed=Decimal("0.02")
            )

            mock_repo_instance.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_close_action_risk_offset(self, mock_session, mock_position_group):
        """Test saving risk offset close action."""
        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("49000"),
                exit_reason="risk_offset",
                realized_pnl=Decimal("-100"),
                quantity_closed=Decimal("0.02")
            )

            mock_repo_instance.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_close_action_short_position(self, mock_session, mock_position_group):
        """Test saving close action for short position."""
        mock_position_group.side = "short"

        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("49000"),
                exit_reason="engine",
                realized_pnl=Decimal("100"),
                quantity_closed=Decimal("0.02")
            )

            mock_repo_instance.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_close_action_zero_entry_price(self, mock_session, mock_position_group):
        """Test saving close action with zero entry price."""
        mock_position_group.weighted_avg_entry = Decimal("0")

        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("51000"),
                exit_reason="engine",
                realized_pnl=Decimal("0"),
                quantity_closed=Decimal("0.02")
            )

            mock_repo_instance.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_close_action_no_created_at(self, mock_session, mock_position_group):
        """Test saving close action when created_at is None."""
        mock_position_group.created_at = None

        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("51000"),
                exit_reason="engine",
                realized_pnl=Decimal("100"),
                quantity_closed=Decimal("0.02")
            )

            mock_repo_instance.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_close_action_unknown_reason(self, mock_session, mock_position_group):
        """Test saving close action with unknown exit reason."""
        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("51000"),
                exit_reason="unknown_reason",
                realized_pnl=Decimal("100"),
                quantity_closed=Decimal("0.02")
            )

            # Should default to ENGINE_CLOSE
            mock_repo_instance.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_close_action_exception_handled(self, mock_session, mock_position_group):
        """Test that exceptions are handled gracefully."""
        with patch('app.services.position.position_closer.RiskActionRepository') as MockRepo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.create.side_effect = Exception("Database error")
            MockRepo.return_value = mock_repo_instance

            # Should not raise
            await save_close_action(
                session=mock_session,
                position_group=mock_position_group,
                exit_price=Decimal("51000"),
                exit_reason="manual",
                realized_pnl=Decimal("100"),
                quantity_closed=Decimal("0.02")
            )


class TestExecuteHandleExitSignal:
    """Tests for execute_handle_exit_signal function."""

    @pytest.mark.asyncio
    async def test_execute_exit_position_not_found(self, mock_session, mock_user):
        """Test exit when position group not found."""
        mock_repo_class = MagicMock()
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_with_orders.return_value = None
        mock_repo_class.return_value = mock_repo_instance

        await execute_handle_exit_signal(
            position_group_id=uuid.uuid4(),
            session=mock_session,
            user=mock_user,
            position_group_repository_class=mock_repo_class,
            order_service_class=MagicMock()
        )

        # Should return early without errors

    @pytest.mark.asyncio
    async def test_execute_exit_already_closed(self, mock_session, mock_user, mock_position_group):
        """Test exit when position is already closed."""
        mock_position_group.status = PositionGroupStatus.CLOSED

        mock_repo_class = MagicMock()
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_with_orders.return_value = mock_position_group
        mock_repo_class.return_value = mock_repo_instance

        await execute_handle_exit_signal(
            position_group_id=mock_position_group.id,
            session=mock_session,
            user=mock_user,
            position_group_repository_class=mock_repo_class,
            order_service_class=MagicMock()
        )

        # Should return early without errors

    @pytest.mark.asyncio
    async def test_execute_exit_no_filled_quantity(self, mock_session, mock_user, mock_position_group):
        """Test exit when there is no filled quantity."""
        mock_position_group.total_filled_quantity = Decimal("0")
        mock_position_group.status = PositionGroupStatus.ACTIVE

        mock_repo_class = MagicMock()
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_with_orders.return_value = mock_position_group
        mock_repo_instance.update = AsyncMock()
        mock_repo_class.return_value = mock_repo_instance

        mock_order_service_class = MagicMock()
        mock_order_service_instance = AsyncMock()
        mock_order_service_instance.cancel_open_orders_for_group = AsyncMock()
        mock_order_service_class.return_value = mock_order_service_instance

        with patch('app.services.position.position_closer._get_exchange_connector_for_user') as mock_get_conn:
            mock_connector = AsyncMock()
            mock_connector.close = AsyncMock()
            mock_get_conn.return_value = mock_connector

            await execute_handle_exit_signal(
                position_group_id=mock_position_group.id,
                session=mock_session,
                user=mock_user,
                position_group_repository_class=mock_repo_class,
                order_service_class=mock_order_service_class
            )

            assert mock_position_group.status == PositionGroupStatus.CLOSED
            mock_connector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_exit_success_long_position(self, mock_session, mock_user, mock_position_group):
        """Test successful exit for long position."""
        mock_position_group.status = PositionGroupStatus.ACTIVE
        mock_position_group.side = "long"
        mock_position_group.total_filled_quantity = Decimal("0.02")

        mock_repo_class = MagicMock()
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_with_orders.return_value = mock_position_group
        mock_repo_instance.update = AsyncMock()
        mock_repo_class.return_value = mock_repo_instance

        mock_order_service_class = MagicMock()
        mock_order_service_instance = AsyncMock()
        mock_order_service_instance.cancel_open_orders_for_group = AsyncMock()
        mock_order_service_instance.close_position_market = AsyncMock()
        mock_order_service_class.return_value = mock_order_service_instance

        with patch('app.services.position.position_closer._get_exchange_connector_for_user') as mock_get_conn, \
             patch('app.services.position.position_closer.save_close_action') as mock_save:
            mock_connector = AsyncMock()
            mock_connector.get_current_price = AsyncMock(return_value=51000)
            mock_connector.close = AsyncMock()
            mock_get_conn.return_value = mock_connector

            await execute_handle_exit_signal(
                position_group_id=mock_position_group.id,
                session=mock_session,
                user=mock_user,
                position_group_repository_class=mock_repo_class,
                order_service_class=mock_order_service_class
            )

            assert mock_position_group.status == PositionGroupStatus.CLOSED
            mock_save.assert_called_once()
            mock_connector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_exit_success_short_position(self, mock_session, mock_user, mock_position_group):
        """Test successful exit for short position."""
        mock_position_group.status = PositionGroupStatus.ACTIVE
        mock_position_group.side = "short"
        mock_position_group.total_filled_quantity = Decimal("0.02")

        mock_repo_class = MagicMock()
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_with_orders.return_value = mock_position_group
        mock_repo_instance.update = AsyncMock()
        mock_repo_class.return_value = mock_repo_instance

        mock_order_service_class = MagicMock()
        mock_order_service_instance = AsyncMock()
        mock_order_service_instance.cancel_open_orders_for_group = AsyncMock()
        mock_order_service_instance.close_position_market = AsyncMock()
        mock_order_service_class.return_value = mock_order_service_instance

        with patch('app.services.position.position_closer._get_exchange_connector_for_user') as mock_get_conn, \
             patch('app.services.position.position_closer.save_close_action') as mock_save:
            mock_connector = AsyncMock()
            mock_connector.get_current_price = AsyncMock(return_value=49000)
            mock_connector.close = AsyncMock()
            mock_get_conn.return_value = mock_connector

            await execute_handle_exit_signal(
                position_group_id=mock_position_group.id,
                session=mock_session,
                user=mock_user,
                position_group_repository_class=mock_repo_class,
                order_service_class=mock_order_service_class
            )

            assert mock_position_group.status == PositionGroupStatus.CLOSED
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_exit_already_closing(self, mock_session, mock_user, mock_position_group):
        """Test exit when position is already in CLOSING status."""
        mock_position_group.status = PositionGroupStatus.CLOSING
        mock_position_group.total_filled_quantity = Decimal("0.02")

        mock_repo_class = MagicMock()
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_with_orders.return_value = mock_position_group
        mock_repo_instance.update = AsyncMock()
        mock_repo_class.return_value = mock_repo_instance

        mock_order_service_class = MagicMock()
        mock_order_service_instance = AsyncMock()
        mock_order_service_instance.cancel_open_orders_for_group = AsyncMock()
        mock_order_service_instance.close_position_market = AsyncMock()
        mock_order_service_class.return_value = mock_order_service_instance

        with patch('app.services.position.position_closer._get_exchange_connector_for_user') as mock_get_conn, \
             patch('app.services.position.position_closer.save_close_action') as mock_save:
            mock_connector = AsyncMock()
            mock_connector.get_current_price = AsyncMock(return_value=51000)
            mock_connector.close = AsyncMock()
            mock_get_conn.return_value = mock_connector

            await execute_handle_exit_signal(
                position_group_id=mock_position_group.id,
                session=mock_session,
                user=mock_user,
                position_group_repository_class=mock_repo_class,
                order_service_class=mock_order_service_class
            )

            # Should not call update to change status since already CLOSING
            assert mock_position_group.status == PositionGroupStatus.CLOSED
