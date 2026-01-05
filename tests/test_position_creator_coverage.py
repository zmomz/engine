"""
Additional tests for position_creator.py to improve coverage.
Focuses on: exchange connector helper, duplicate position handling,
alternative symbol formats, order status variations, and error handling.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid
import json

from app.services.position.position_creator import (
    _get_exchange_connector_for_user,
    create_position_group_from_signal,
    handle_pyramid_continuation,
    UserNotFoundException,
    DuplicatePositionException,
)
from app.models.user import User
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.queued_signal import QueuedSignal
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.schemas.grid_config import DCAGridConfig, RiskEngineConfig, DCALevelConfig


def create_mock_dca_config():
    """Create a valid DCAGridConfig for testing."""
    return DCAGridConfig(
        levels=[
            DCALevelConfig(gap_percent=0, weight_percent=50, tp_percent=2),
            DCALevelConfig(gap_percent=-2, weight_percent=50, tp_percent=2),
        ],
        tp_mode="per_leg",
        tp_aggregate_percent=0,
        max_pyramids=5,
        entry_order_type="market"
    )


class TestGetExchangeConnectorForUser:
    """Tests for _get_exchange_connector_for_user helper function."""

    def test_extracts_keys_from_dict_by_exchange_name(self):
        """Test extracting API keys from dict by exchange name."""
        mock_user = MagicMock(spec=User)
        mock_user.encrypted_api_keys = {
            "binance": {"api_key": "test_key", "secret_key": "test_secret"},
            "bybit": {"api_key": "other_key"}
        }

        with patch("app.services.position.position_creator.get_exchange_connector") as mock_get_conn:
            mock_connector = MagicMock()
            mock_get_conn.return_value = mock_connector

            result = _get_exchange_connector_for_user(mock_user, "binance")

            mock_get_conn.assert_called_once_with(
                "binance",
                {"api_key": "test_key", "secret_key": "test_secret"}
            )
            assert result == mock_connector

    def test_extracts_keys_from_dict_normalized_lowercase(self):
        """Test that exchange name is normalized to lowercase."""
        mock_user = MagicMock(spec=User)
        mock_user.encrypted_api_keys = {"binance": {"api_key": "test"}}

        with patch("app.services.position.position_creator.get_exchange_connector") as mock_get_conn:
            mock_get_conn.return_value = MagicMock()

            _get_exchange_connector_for_user(mock_user, "BINANCE")

            mock_get_conn.assert_called_once()
            # Exchange name passed should be BINANCE, but keys looked up as binance
            call_args = mock_get_conn.call_args
            assert call_args[0][0] == "BINANCE"

    def test_uses_encrypted_data_key_when_single_entry(self):
        """Test using encrypted_data key when it's the only entry."""
        mock_user = MagicMock(spec=User)
        mock_user.encrypted_api_keys = {"encrypted_data": "encrypted_string"}

        with patch("app.services.position.position_creator.get_exchange_connector") as mock_get_conn:
            mock_get_conn.return_value = MagicMock()

            _get_exchange_connector_for_user(mock_user, "binance")

            mock_get_conn.assert_called_once_with(
                "binance",
                {"encrypted_data": "encrypted_string"}
            )

    def test_handles_string_encrypted_data(self):
        """Test handling when encrypted_data is a string."""
        mock_user = MagicMock(spec=User)
        mock_user.encrypted_api_keys = "raw_encrypted_string"

        with patch("app.services.position.position_creator.get_exchange_connector") as mock_get_conn:
            mock_get_conn.return_value = MagicMock()

            _get_exchange_connector_for_user(mock_user, "binance")

            mock_get_conn.assert_called_once_with(
                "binance",
                {"encrypted_data": "raw_encrypted_string"}
            )

    def test_raises_error_when_exchange_not_in_keys(self):
        """Test error raised when exchange not found in API keys."""
        mock_user = MagicMock(spec=User)
        mock_user.encrypted_api_keys = {"binance": {"api_key": "test"}}

        with pytest.raises(ValueError) as exc_info:
            _get_exchange_connector_for_user(mock_user, "bybit")

        assert "No API keys found for exchange" in str(exc_info.value)

    def test_raises_error_when_invalid_format(self):
        """Test error raised when encrypted_api_keys has invalid format."""
        mock_user = MagicMock(spec=User)
        mock_user.encrypted_api_keys = 12345  # Invalid format

        with pytest.raises(ValueError) as exc_info:
            _get_exchange_connector_for_user(mock_user, "binance")

        assert "Invalid format" in str(exc_info.value)


class TestCreatePositionGroupFromSignal:
    """Tests for create_position_group_from_signal function."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create common mock dependencies."""
        mock_session = AsyncMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"mock": {"api_key": "test"}}
        mock_session.get = AsyncMock(return_value=mock_user)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_signal = MagicMock(spec=QueuedSignal)
        mock_signal.id = uuid.uuid4()
        mock_signal.exchange = "mock"
        mock_signal.symbol = "BTC/USDT"
        mock_signal.timeframe = 60
        mock_signal.side = "long"
        mock_signal.entry_price = Decimal("50000")

        mock_risk_config = RiskEngineConfig()
        mock_dca_config = create_mock_dca_config()

        mock_connector = AsyncMock()
        mock_connector.get_precision_rules = AsyncMock(return_value={
            "BTC/USDT": {"price_precision": 2, "quantity_precision": 4}
        })

        mock_grid_calc = MagicMock()
        mock_grid_calc.calculate_dca_levels.return_value = [
            {"price": Decimal("50000"), "gap_percent": Decimal("0"), "weight_percent": Decimal("50"),
             "tp_percent": Decimal("2"), "tp_price": Decimal("51000")},
            {"price": Decimal("49000"), "gap_percent": Decimal("-2"), "weight_percent": Decimal("50"),
             "tp_percent": Decimal("2"), "tp_price": Decimal("49980")}
        ]
        mock_grid_calc.calculate_order_quantities.return_value = [
            {"price": Decimal("50000"), "quantity": Decimal("0.01"), "gap_percent": Decimal("0"),
             "weight_percent": Decimal("50"), "tp_percent": Decimal("2"), "tp_price": Decimal("51000")},
            {"price": Decimal("49000"), "quantity": Decimal("0.01"), "gap_percent": Decimal("-2"),
             "weight_percent": Decimal("50"), "tp_percent": Decimal("2"), "tp_price": Decimal("49980")}
        ]

        mock_order_service = AsyncMock()
        mock_order_service.submit_order = AsyncMock()
        mock_order_service_class = MagicMock(return_value=mock_order_service)

        mock_pg_repo = AsyncMock()
        mock_pg_repo_class = MagicMock(return_value=mock_pg_repo)

        mock_update_timer = AsyncMock()
        mock_update_stats = AsyncMock()

        return {
            "session": mock_session,
            "user": mock_user,
            "signal": mock_signal,
            "risk_config": mock_risk_config,
            "dca_config": mock_dca_config,
            "connector": mock_connector,
            "grid_calc": mock_grid_calc,
            "order_service": mock_order_service,
            "order_service_class": mock_order_service_class,
            "pg_repo_class": mock_pg_repo_class,
            "update_timer": mock_update_timer,
            "update_stats": mock_update_stats
        }

    @pytest.mark.asyncio
    async def test_raises_user_not_found(self, mock_dependencies):
        """Test raises UserNotFoundException when user not found."""
        mock_dependencies["session"].get = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundException):
            await create_position_group_from_signal(
                session=mock_dependencies["session"],
                user_id=uuid.uuid4(),
                signal=mock_dependencies["signal"],
                risk_config=mock_dependencies["risk_config"],
                dca_grid_config=mock_dependencies["dca_config"],
                total_capital_usd=Decimal("1000"),
                position_group_repository_class=mock_dependencies["pg_repo_class"],
                grid_calculator_service=mock_dependencies["grid_calc"],
                order_service_class=mock_dependencies["order_service_class"],
                update_risk_timer_func=mock_dependencies["update_timer"],
                update_position_stats_func=mock_dependencies["update_stats"],
            )

    @pytest.mark.asyncio
    async def test_uses_alternative_symbol_format(self, mock_dependencies):
        """Test uses alternative symbol format when original not found."""
        mock_dependencies["signal"].symbol = "BTC/USDT"
        mock_dependencies["connector"].get_precision_rules = AsyncMock(return_value={
            "BTCUSDT": {"price_precision": 2, "quantity_precision": 4}  # Without slash
        })

        with patch("app.services.position.position_creator.get_exchange_connector",
                   return_value=mock_dependencies["connector"]):
            with patch("app.services.position.position_creator.broadcast_entry_signal", new_callable=AsyncMock):
                await create_position_group_from_signal(
                    session=mock_dependencies["session"],
                    user_id=mock_dependencies["user"].id,
                    signal=mock_dependencies["signal"],
                    risk_config=mock_dependencies["risk_config"],
                    dca_grid_config=mock_dependencies["dca_config"],
                    total_capital_usd=Decimal("1000"),
                    position_group_repository_class=mock_dependencies["pg_repo_class"],
                    grid_calculator_service=mock_dependencies["grid_calc"],
                    order_service_class=mock_dependencies["order_service_class"],
                    update_risk_timer_func=mock_dependencies["update_timer"],
                    update_position_stats_func=mock_dependencies["update_stats"],
                )

        # Should still complete successfully using alternative symbol format

    @pytest.mark.asyncio
    async def test_market_order_with_positive_gap_gets_submitted(self, mock_dependencies):
        """Test market orders with gap_percent >= 0 get PENDING status and are submitted."""
        mock_dependencies["dca_config"].entry_order_type = "market"
        mock_dependencies["grid_calc"].calculate_order_quantities.return_value = [
            {"price": Decimal("50000"), "quantity": Decimal("0.01"), "gap_percent": Decimal("0"),
             "weight_percent": Decimal("50"), "tp_percent": Decimal("2"), "tp_price": Decimal("51000")},
            {"price": Decimal("49000"), "quantity": Decimal("0.01"), "gap_percent": Decimal("2"),  # Positive gap
             "weight_percent": Decimal("50"), "tp_percent": Decimal("2"), "tp_price": Decimal("49980")}
        ]

        with patch("app.services.position.position_creator.get_exchange_connector",
                   return_value=mock_dependencies["connector"]):
            with patch("app.services.position.position_creator.broadcast_entry_signal", new_callable=AsyncMock):
                await create_position_group_from_signal(
                    session=mock_dependencies["session"],
                    user_id=mock_dependencies["user"].id,
                    signal=mock_dependencies["signal"],
                    risk_config=mock_dependencies["risk_config"],
                    dca_grid_config=mock_dependencies["dca_config"],
                    total_capital_usd=Decimal("1000"),
                    position_group_repository_class=mock_dependencies["pg_repo_class"],
                    grid_calculator_service=mock_dependencies["grid_calc"],
                    order_service_class=mock_dependencies["order_service_class"],
                    update_risk_timer_func=mock_dependencies["update_timer"],
                    update_position_stats_func=mock_dependencies["update_stats"],
                )

        # Both orders have gap_percent >= 0, so both should be submitted immediately
        # gap=0: at entry price -> submit
        # gap=2 (positive): price already better than target -> submit
        assert mock_dependencies["order_service"].submit_order.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_order_submission_failure(self, mock_dependencies):
        """Test handles order submission failure and broadcasts failure."""
        mock_dependencies["order_service"].submit_order = AsyncMock(
            side_effect=Exception("Order rejected")
        )

        with patch("app.services.position.position_creator.get_exchange_connector",
                   return_value=mock_dependencies["connector"]):
            with patch("app.services.position.position_creator.broadcast_failure", new_callable=AsyncMock) as mock_broadcast:
                with patch("app.services.position.position_creator.broadcast_entry_signal", new_callable=AsyncMock):
                    result = await create_position_group_from_signal(
                        session=mock_dependencies["session"],
                        user_id=mock_dependencies["user"].id,
                        signal=mock_dependencies["signal"],
                        risk_config=mock_dependencies["risk_config"],
                        dca_grid_config=mock_dependencies["dca_config"],
                        total_capital_usd=Decimal("1000"),
                        position_group_repository_class=mock_dependencies["pg_repo_class"],
                        grid_calculator_service=mock_dependencies["grid_calc"],
                        order_service_class=mock_dependencies["order_service_class"],
                        update_risk_timer_func=mock_dependencies["update_timer"],
                        update_position_stats_func=mock_dependencies["update_stats"],
                    )

                    # broadcast_failure should have been called
                    mock_broadcast.assert_called_once()
                    # Position status should be FAILED
                    assert result.status == PositionGroupStatus.FAILED

    @pytest.mark.asyncio
    async def test_handles_limit_entry_order_type(self, mock_dependencies):
        """Test handles limit entry order type."""
        mock_dependencies["dca_config"].entry_order_type = "limit"

        orders_created = []

        def capture_add(obj):
            if isinstance(obj, DCAOrder):
                orders_created.append(obj)

        mock_dependencies["session"].add = MagicMock(side_effect=capture_add)

        with patch("app.services.position.position_creator.get_exchange_connector",
                   return_value=mock_dependencies["connector"]):
            with patch("app.services.position.position_creator.broadcast_entry_signal", new_callable=AsyncMock):
                await create_position_group_from_signal(
                    session=mock_dependencies["session"],
                    user_id=mock_dependencies["user"].id,
                    signal=mock_dependencies["signal"],
                    risk_config=mock_dependencies["risk_config"],
                    dca_grid_config=mock_dependencies["dca_config"],
                    total_capital_usd=Decimal("1000"),
                    position_group_repository_class=mock_dependencies["pg_repo_class"],
                    grid_calculator_service=mock_dependencies["grid_calc"],
                    order_service_class=mock_dependencies["order_service_class"],
                    update_risk_timer_func=mock_dependencies["update_timer"],
                    update_position_stats_func=mock_dependencies["update_stats"],
                )

        # All orders should be limit type
        for order in orders_created:
            assert order.order_type == "limit"


class TestHandlePyramidContinuation:
    """Tests for handle_pyramid_continuation function."""

    @pytest.fixture
    def mock_pyramid_dependencies(self):
        """Create mock dependencies for pyramid continuation."""
        mock_session = AsyncMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"mock": {"api_key": "test"}}
        mock_session.get = AsyncMock(return_value=mock_user)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_signal = MagicMock(spec=QueuedSignal)
        mock_signal.id = uuid.uuid4()
        mock_signal.exchange = "mock"
        mock_signal.symbol = "BTC/USDT"
        mock_signal.timeframe = 60
        mock_signal.side = "long"
        mock_signal.entry_price = Decimal("48000")

        mock_existing_pg = MagicMock(spec=PositionGroup)
        mock_existing_pg.id = uuid.uuid4()
        mock_existing_pg.pyramid_count = 1
        mock_existing_pg.risk_timer_expires = None

        mock_risk_config = RiskEngineConfig()
        mock_dca_config = create_mock_dca_config()

        mock_connector = AsyncMock()
        mock_connector.get_precision_rules = AsyncMock(return_value={
            "BTC/USDT": {"price_precision": 2, "quantity_precision": 4}
        })

        mock_grid_calc = MagicMock()
        mock_grid_calc.calculate_dca_levels.return_value = [
            {"price": Decimal("48000"), "gap_percent": Decimal("0"), "weight_percent": Decimal("50"),
             "tp_percent": Decimal("2"), "tp_price": Decimal("48960")}
        ]
        mock_grid_calc.calculate_order_quantities.return_value = [
            {"price": Decimal("48000"), "quantity": Decimal("0.01"), "gap_percent": Decimal("0"),
             "weight_percent": Decimal("50"), "tp_percent": Decimal("2"), "tp_price": Decimal("48960")}
        ]

        mock_order_service = AsyncMock()
        mock_order_service.submit_order = AsyncMock()
        mock_order_service_class = MagicMock(return_value=mock_order_service)

        mock_pg_repo = AsyncMock()
        mock_pg_repo.increment_pyramid_count = AsyncMock(return_value=2)
        mock_pg_repo_class = MagicMock(return_value=mock_pg_repo)

        mock_update_timer = AsyncMock()
        mock_update_stats = AsyncMock()

        return {
            "session": mock_session,
            "user": mock_user,
            "signal": mock_signal,
            "existing_pg": mock_existing_pg,
            "risk_config": mock_risk_config,
            "dca_config": mock_dca_config,
            "connector": mock_connector,
            "grid_calc": mock_grid_calc,
            "order_service": mock_order_service,
            "order_service_class": mock_order_service_class,
            "pg_repo": mock_pg_repo,
            "pg_repo_class": mock_pg_repo_class,
            "update_timer": mock_update_timer,
            "update_stats": mock_update_stats
        }

    @pytest.mark.asyncio
    async def test_raises_user_not_found(self, mock_pyramid_dependencies):
        """Test raises UserNotFoundException when user not found."""
        mock_pyramid_dependencies["session"].get = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundException):
            await handle_pyramid_continuation(
                session=mock_pyramid_dependencies["session"],
                user_id=uuid.uuid4(),
                signal=mock_pyramid_dependencies["signal"],
                existing_position_group=mock_pyramid_dependencies["existing_pg"],
                risk_config=mock_pyramid_dependencies["risk_config"],
                dca_grid_config=mock_pyramid_dependencies["dca_config"],
                total_capital_usd=Decimal("1000"),
                position_group_repository_class=mock_pyramid_dependencies["pg_repo_class"],
                grid_calculator_service=mock_pyramid_dependencies["grid_calc"],
                order_service_class=mock_pyramid_dependencies["order_service_class"],
                update_risk_timer_func=mock_pyramid_dependencies["update_timer"],
                update_position_stats_func=mock_pyramid_dependencies["update_stats"],
            )

    @pytest.mark.asyncio
    async def test_resets_risk_timer_when_expires_set(self, mock_pyramid_dependencies):
        """Test risk timer is reset when expires is set."""
        from datetime import datetime

        mock_pyramid_dependencies["existing_pg"].risk_timer_expires = datetime.utcnow()

        with patch("app.services.position.position_creator._get_exchange_connector_for_user",
                   return_value=mock_pyramid_dependencies["connector"]):
            with patch("app.services.position.position_creator.broadcast_pyramid_added", new_callable=AsyncMock):
                with patch("app.services.position.position_creator.broadcast_entry_signal", new_callable=AsyncMock):
                    await handle_pyramid_continuation(
                        session=mock_pyramid_dependencies["session"],
                        user_id=mock_pyramid_dependencies["user"].id,
                        signal=mock_pyramid_dependencies["signal"],
                        existing_position_group=mock_pyramid_dependencies["existing_pg"],
                        risk_config=mock_pyramid_dependencies["risk_config"],
                        dca_grid_config=mock_pyramid_dependencies["dca_config"],
                        total_capital_usd=Decimal("1000"),
                        position_group_repository_class=mock_pyramid_dependencies["pg_repo_class"],
                        grid_calculator_service=mock_pyramid_dependencies["grid_calc"],
                        order_service_class=mock_pyramid_dependencies["order_service_class"],
                        update_risk_timer_func=mock_pyramid_dependencies["update_timer"],
                        update_position_stats_func=mock_pyramid_dependencies["update_stats"],
                    )

        # Risk timer should be reset
        assert mock_pyramid_dependencies["existing_pg"].risk_timer_start is None
        assert mock_pyramid_dependencies["existing_pg"].risk_timer_expires is None

    @pytest.mark.asyncio
    async def test_handles_order_submission_failure(self, mock_pyramid_dependencies):
        """Test raises exception on order submission failure."""
        mock_pyramid_dependencies["order_service"].submit_order = AsyncMock(
            side_effect=Exception("Order rejected")
        )

        with patch("app.services.position.position_creator._get_exchange_connector_for_user",
                   return_value=mock_pyramid_dependencies["connector"]):
            with pytest.raises(Exception) as exc_info:
                await handle_pyramid_continuation(
                    session=mock_pyramid_dependencies["session"],
                    user_id=mock_pyramid_dependencies["user"].id,
                    signal=mock_pyramid_dependencies["signal"],
                    existing_position_group=mock_pyramid_dependencies["existing_pg"],
                    risk_config=mock_pyramid_dependencies["risk_config"],
                    dca_grid_config=mock_pyramid_dependencies["dca_config"],
                    total_capital_usd=Decimal("1000"),
                    position_group_repository_class=mock_pyramid_dependencies["pg_repo_class"],
                    grid_calculator_service=mock_pyramid_dependencies["grid_calc"],
                    order_service_class=mock_pyramid_dependencies["order_service_class"],
                    update_risk_timer_func=mock_pyramid_dependencies["update_timer"],
                    update_position_stats_func=mock_pyramid_dependencies["update_stats"],
                )

            assert "Order rejected" in str(exc_info.value)
