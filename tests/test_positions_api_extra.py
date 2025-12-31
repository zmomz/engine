"""
Extra tests for positions.py API to improve coverage.
Covers: get_order_service, force_close_position, sync_position_with_exchange, cleanup_stale_orders
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid

from app.main import app
from app.api.dependencies.users import get_current_active_user
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.exceptions import APIError
from app.services.exchange_config_service import ExchangeConfigError


@pytest.fixture
def mock_user():
    """Create mock user."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.is_superuser = False
    user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    return user


@pytest.fixture
def mock_position():
    """Create mock position group."""
    position = MagicMock(spec=PositionGroup)
    position.id = uuid.uuid4()
    position.user_id = uuid.uuid4()
    position.exchange = "binance"
    position.symbol = "BTC/USDT"
    position.side = "long"
    position.status = PositionGroupStatus.ACTIVE.value
    position.total_filled_quantity = Decimal("0.1")
    position.weighted_avg_entry = Decimal("50000")
    position.total_invested_usd = Decimal("5000")
    return position


class TestForceClosePosition:
    """Tests for force_close_position endpoint."""

    @pytest.mark.asyncio
    async def test_force_close_position_not_found(self, authorized_client, mock_user):
        """Test force close when position not found."""
        group_id = str(uuid.uuid4())

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = None

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo):
                response = await authorized_client.post(f"/api/v1/positions/{group_id}/close")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_force_close_exchange_config_error(self, authorized_client, mock_user, mock_position):
        """Test force close with ExchangeConfigError."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config:
                mock_config.get_connector.side_effect = ExchangeConfigError("Invalid API key")

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/close")

            # ExchangeConfigError gets caught by the outer exception handler
            assert response.status_code in [400, 500]
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_force_close_api_error(self, authorized_client, mock_user, mock_position):
        """Test force close with APIError."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        mock_connector = AsyncMock()
        mock_connector.close = AsyncMock()

        mock_order_service = AsyncMock()
        mock_order_service.execute_force_close.side_effect = APIError("Order execution failed", status_code=400)

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config, \
                 patch("app.api.positions.OrderService", return_value=mock_order_service):
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/close")

            assert response.status_code == 400
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_force_close_generic_exception(self, authorized_client, mock_user, mock_position):
        """Test force close with generic exception."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        mock_connector = AsyncMock()
        mock_connector.close = AsyncMock()

        mock_order_service = AsyncMock()
        mock_order_service.execute_force_close.side_effect = Exception("Unexpected error")

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config, \
                 patch("app.api.positions.OrderService", return_value=mock_order_service):
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/close")

            assert response.status_code == 500
        finally:
            del app.dependency_overrides[get_current_active_user]


class TestSyncPositionWithExchange:
    """Tests for sync_position_with_exchange endpoint."""

    @pytest.mark.asyncio
    async def test_sync_position_not_found(self, authorized_client, mock_user):
        """Test sync when position not found."""
        group_id = str(uuid.uuid4())

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = None

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo):
                response = await authorized_client.post(f"/api/v1/positions/{group_id}/sync")

            assert response.status_code == 404
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_sync_position_exchange_config_error(self, authorized_client, mock_user, mock_position):
        """Test sync with ExchangeConfigError."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config:
                mock_config.get_connector.side_effect = ExchangeConfigError("Invalid API key")

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/sync")

            assert response.status_code == 400
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_sync_position_success(self, authorized_client, mock_user, mock_position):
        """Test successful position sync."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        mock_connector = AsyncMock()
        mock_connector.close = AsyncMock()

        mock_sync_service = AsyncMock()
        mock_sync_service.sync_orders_with_exchange.return_value = {
            "synced": 5,
            "updated": 2,
            "not_found": 1,
            "errors": 0
        }

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config, \
                 patch("app.services.exchange_sync.ExchangeSyncService", return_value=mock_sync_service):
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/sync")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_sync_position_generic_exception(self, authorized_client, mock_user, mock_position):
        """Test sync with generic exception."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        mock_connector = AsyncMock()
        mock_connector.close = AsyncMock()

        mock_sync_service = AsyncMock()
        mock_sync_service.sync_orders_with_exchange.side_effect = Exception("Sync error")

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config, \
                 patch("app.services.exchange_sync.ExchangeSyncService", return_value=mock_sync_service):
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/sync")

            assert response.status_code == 500
        finally:
            del app.dependency_overrides[get_current_active_user]


class TestCleanupStaleOrders:
    """Tests for cleanup_stale_orders endpoint."""

    @pytest.mark.asyncio
    async def test_cleanup_position_not_found(self, authorized_client, mock_user):
        """Test cleanup when position not found."""
        group_id = str(uuid.uuid4())

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = None

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo):
                response = await authorized_client.post(f"/api/v1/positions/{group_id}/cleanup-stale")

            assert response.status_code == 404
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_cleanup_exchange_config_error(self, authorized_client, mock_user, mock_position):
        """Test cleanup with ExchangeConfigError."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config:
                mock_config.get_connector.side_effect = ExchangeConfigError("Invalid API key")

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/cleanup-stale")

            assert response.status_code == 400
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_cleanup_success(self, authorized_client, mock_user, mock_position):
        """Test successful cleanup."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        mock_connector = AsyncMock()
        mock_connector.close = AsyncMock()

        mock_sync_service = AsyncMock()
        mock_sync_service.cleanup_stale_local_orders.return_value = {
            "checked": 10,
            "cleaned": 3,
            "errors": 0
        }

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config, \
                 patch("app.services.exchange_sync.ExchangeSyncService", return_value=mock_sync_service):
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/cleanup-stale")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "3" in data["message"]
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_cleanup_generic_exception(self, authorized_client, mock_user, mock_position):
        """Test cleanup with generic exception."""
        mock_position.user_id = mock_user.id
        group_id = str(mock_position.id)

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_by_user_and_id.return_value = mock_position

        mock_connector = AsyncMock()
        mock_connector.close = AsyncMock()

        mock_sync_service = AsyncMock()
        mock_sync_service.cleanup_stale_local_orders.side_effect = Exception("Cleanup error")

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.positions.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.positions.ExchangeConfigService") as mock_config, \
                 patch("app.services.exchange_sync.ExchangeSyncService", return_value=mock_sync_service):
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.post(f"/api/v1/positions/{group_id}/cleanup-stale")

            assert response.status_code == 500
        finally:
            del app.dependency_overrides[get_current_active_user]


class TestGetOrderService:
    """Tests for get_order_service dependency."""

    @pytest.mark.asyncio
    async def test_get_order_service_exchange_config_error(self):
        """Test get_order_service raises HTTPException on ExchangeConfigError."""
        from app.api.positions import get_order_service
        from fastapi import HTTPException

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_request = MagicMock()
        mock_db = AsyncMock()

        with patch("app.api.positions.ExchangeConfigService") as mock_config:
            mock_config.get_connector.side_effect = ExchangeConfigError("No API keys")

            with pytest.raises(HTTPException) as exc_info:
                await get_order_service(mock_request, mock_db, mock_user)

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_order_service_generic_exception(self):
        """Test get_order_service raises HTTPException on generic exception."""
        from app.api.positions import get_order_service
        from fastapi import HTTPException

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_request = MagicMock()
        mock_db = AsyncMock()

        with patch("app.api.positions.ExchangeConfigService") as mock_config:
            mock_config.get_connector.side_effect = Exception("Unexpected error")

            with pytest.raises(HTTPException) as exc_info:
                await get_order_service(mock_request, mock_db, mock_user)

            assert exc_info.value.status_code == 500


class TestCalculatePositionPnL:
    """Tests for _calculate_position_pnl function."""

    @pytest.mark.asyncio
    async def test_calculate_pnl_from_tickers(self):
        """Test PnL calculation using cached tickers."""
        from app.api.positions import _calculate_position_pnl

        pos = MagicMock()
        pos.id = uuid.uuid4()
        pos.symbol = "BTC/USDT"
        pos.side = "long"
        pos.total_filled_quantity = Decimal("0.1")
        pos.weighted_avg_entry = Decimal("50000")
        pos.total_invested_usd = Decimal("5000")
        pos.unrealized_pnl_usd = None
        pos.unrealized_pnl_percent = None

        all_tickers = {"BTC/USDT": {"last": 55000.0}}
        mock_connector = AsyncMock()

        await _calculate_position_pnl(pos, all_tickers, mock_connector)

        # (55000 - 50000) * 0.1 = 500
        assert pos.unrealized_pnl_usd == Decimal("500.0")
        mock_connector.get_current_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_calculate_pnl_short_position(self):
        """Test PnL calculation for short position."""
        from app.api.positions import _calculate_position_pnl

        pos = MagicMock()
        pos.id = uuid.uuid4()
        pos.symbol = "BTC/USDT"
        pos.side = "short"
        pos.total_filled_quantity = Decimal("0.1")
        pos.weighted_avg_entry = Decimal("50000")
        pos.total_invested_usd = Decimal("5000")
        pos.unrealized_pnl_usd = None
        pos.unrealized_pnl_percent = None

        all_tickers = {"BTC/USDT": {"last": 45000.0}}
        mock_connector = AsyncMock()

        await _calculate_position_pnl(pos, all_tickers, mock_connector)

        # (50000 - 45000) * 0.1 = 500
        assert pos.unrealized_pnl_usd == Decimal("500.0")

    @pytest.mark.asyncio
    async def test_calculate_pnl_fallback_to_connector(self):
        """Test PnL calculation falls back to connector when ticker not in cache."""
        from app.api.positions import _calculate_position_pnl

        pos = MagicMock()
        pos.id = uuid.uuid4()
        pos.symbol = "ETH/USDT"
        pos.side = "long"
        pos.total_filled_quantity = Decimal("1.0")
        pos.weighted_avg_entry = Decimal("3000")
        pos.total_invested_usd = Decimal("3000")
        pos.unrealized_pnl_usd = None
        pos.unrealized_pnl_percent = None

        all_tickers = {}  # No tickers
        mock_connector = AsyncMock()
        mock_connector.get_current_price.return_value = 3500.0

        await _calculate_position_pnl(pos, all_tickers, mock_connector)

        # (3500 - 3000) * 1.0 = 500
        assert pos.unrealized_pnl_usd == Decimal("500.0")
        mock_connector.get_current_price.assert_called_once_with("ETH/USDT")

    @pytest.mark.asyncio
    async def test_calculate_pnl_zero_quantity(self):
        """Test PnL calculation with zero quantity."""
        from app.api.positions import _calculate_position_pnl

        pos = MagicMock()
        pos.id = uuid.uuid4()
        pos.symbol = "BTC/USDT"
        pos.side = "long"
        pos.total_filled_quantity = Decimal("0")  # Zero quantity
        pos.weighted_avg_entry = Decimal("50000")
        pos.total_invested_usd = Decimal("0")
        pos.unrealized_pnl_usd = None
        pos.unrealized_pnl_percent = None

        all_tickers = {"BTC/USDT": {"last": 55000.0}}
        mock_connector = AsyncMock()

        await _calculate_position_pnl(pos, all_tickers, mock_connector)

        assert pos.unrealized_pnl_usd == Decimal("0")

    @pytest.mark.asyncio
    async def test_calculate_pnl_none_price(self):
        """Test PnL calculation when price is None."""
        from app.api.positions import _calculate_position_pnl

        pos = MagicMock()
        pos.id = uuid.uuid4()
        pos.symbol = "UNKNOWN/USDT"
        pos.side = "long"
        pos.total_filled_quantity = Decimal("1.0")
        pos.weighted_avg_entry = Decimal("100")
        pos.total_invested_usd = Decimal("100")
        pos.unrealized_pnl_usd = None
        pos.unrealized_pnl_percent = None

        all_tickers = {}
        mock_connector = AsyncMock()
        mock_connector.get_current_price.return_value = None

        await _calculate_position_pnl(pos, all_tickers, mock_connector)

        # Should return early without setting PnL
        assert pos.unrealized_pnl_usd is None

    @pytest.mark.asyncio
    async def test_calculate_pnl_exception_handling(self):
        """Test PnL calculation handles exceptions gracefully."""
        from app.api.positions import _calculate_position_pnl

        pos = MagicMock()
        pos.id = uuid.uuid4()
        pos.symbol = "BTC/USDT"
        pos.side = "long"
        pos.total_filled_quantity = Decimal("0.1")
        pos.weighted_avg_entry = Decimal("50000")
        pos.total_invested_usd = Decimal("5000")

        all_tickers = {}
        mock_connector = AsyncMock()
        mock_connector.get_current_price.side_effect = Exception("API error")

        # Should not raise
        await _calculate_position_pnl(pos, all_tickers, mock_connector)

    @pytest.mark.asyncio
    async def test_calculate_pnl_ticker_without_slash(self):
        """Test PnL calculation with ticker key without slash."""
        from app.api.positions import _calculate_position_pnl

        pos = MagicMock()
        pos.id = uuid.uuid4()
        pos.symbol = "BTC/USDT"  # With slash
        pos.side = "long"
        pos.total_filled_quantity = Decimal("0.1")
        pos.weighted_avg_entry = Decimal("50000")
        pos.total_invested_usd = Decimal("5000")
        pos.unrealized_pnl_usd = None
        pos.unrealized_pnl_percent = None

        # Ticker without slash
        all_tickers = {"BTCUSDT": {"last": 55000.0}}
        mock_connector = AsyncMock()

        await _calculate_position_pnl(pos, all_tickers, mock_connector)

        assert pos.unrealized_pnl_usd == Decimal("500.0")