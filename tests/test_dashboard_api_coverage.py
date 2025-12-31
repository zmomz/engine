"""
Extended tests for dashboard.py API to improve coverage.
Covers lines: cached dashboard return, no configured exchanges, cached balance/tickers,
price variations, PnL calculation edge cases, stats calculation, analytics endpoint.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid

from app.main import app
from app.api.dependencies.users import get_current_active_user
from app.models.position_group import PositionGroup, PositionGroupStatus


class TestAccountSummaryCaching:
    """Tests for account-summary caching behavior."""

    @pytest.mark.asyncio
    async def test_returns_cached_dashboard(self, authorized_client):
        """Test that cached dashboard data is returned when available."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        async def mock_get_user():
            return mock_user

        mock_cache = AsyncMock()
        # Return cached data
        mock_cache.get_dashboard.return_value = {"tvl": 10000.0, "free_usdt": 5000.0}

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache):
                response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            assert data["tvl"] == 10000.0
            assert data["free_usdt"] == 5000.0
            # Verify cache was checked
            mock_cache.get_dashboard.assert_called_once()
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_no_api_keys_returns_zero(self, authorized_client):
        """Test that users without API keys get zero TVL."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = None  # No API keys

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            assert data["tvl"] == 0.0
            assert data["free_usdt"] == 0.0
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_no_configured_exchanges(self, authorized_client):
        """Test handling when no exchanges are configured."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        async def mock_get_user():
            return mock_user

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.get_all_configured_exchanges.return_value = {}  # No exchanges

                response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            assert data["tvl"] == 0.0
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_uses_cached_balance(self, authorized_client):
        """Test that cached balance is used when available."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        async def mock_get_user():
            return mock_user

        mock_connector = AsyncMock()
        mock_connector.get_all_tickers.return_value = {}

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.get_balance.return_value = {"total": {"USDT": 1000.0}, "free": {"USDT": 1000.0}}
        mock_cache.get_tickers.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.set_tickers.return_value = True

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            # Balance was fetched from cache, not exchange
            mock_connector.fetch_balance.assert_not_called()
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_uses_cached_tickers(self, authorized_client):
        """Test that cached tickers are used when available."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        async def mock_get_user():
            return mock_user

        mock_connector = AsyncMock()
        mock_connector.fetch_balance.return_value = {"total": {"USDT": 1000.0, "BTC": 0.1}, "free": {"USDT": 1000.0}}

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.get_balance.return_value = None
        mock_cache.get_tickers.return_value = {"BTC/USDT": {"last": 50000.0}}
        mock_cache.set_dashboard.return_value = True
        mock_cache.set_balance.return_value = True

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            # Tickers were fetched from cache, not exchange
            mock_connector.get_all_tickers.assert_not_called()
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_ticker_fetch_error_fallback(self, authorized_client):
        """Test fallback when ticker fetch fails."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        async def mock_get_user():
            return mock_user

        mock_connector = AsyncMock()
        mock_connector.fetch_balance.return_value = {"total": {"USDT": 1000.0}, "free": {"USDT": 1000.0}}
        mock_connector.get_all_tickers.side_effect = Exception("API error")

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.get_balance.return_value = None
        mock_cache.get_tickers.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.set_balance.return_value = True

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_price_fallback_to_individual_fetch(self, authorized_client):
        """Test that individual price fetch is used when ticker not in cache."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        async def mock_get_user():
            return mock_user

        mock_connector = AsyncMock()
        mock_connector.fetch_balance.return_value = {"total": {"USDT": 1000.0, "ETH": 1.0}, "free": {"USDT": 1000.0}}
        mock_connector.get_all_tickers.return_value = {}  # No tickers
        mock_connector.get_current_price.return_value = 3000.0  # Individual fetch

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.get_balance.return_value = None
        mock_cache.get_tickers.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.set_balance.return_value = True
        mock_cache.set_tickers.return_value = True

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            # TVL: 1000 USDT + 1 ETH * 3000 = 4000
            assert data["tvl"] == 4000.0
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_skips_dust_balances(self, authorized_client):
        """Test that dust balances below threshold are skipped."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}

        async def mock_get_user():
            return mock_user

        mock_connector = AsyncMock()
        # Small ETH balance that results in < $0.10 value
        mock_connector.fetch_balance.return_value = {"total": {"USDT": 100.0, "ETH": 0.00001}, "free": {"USDT": 100.0}}
        mock_connector.get_all_tickers.return_value = {"ETH/USDT": {"last": 3000.0}}

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.get_balance.return_value = None
        mock_cache.get_tickers.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.set_balance.return_value = True
        mock_cache.set_tickers.return_value = True

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            # Only USDT counted, ETH dust skipped (0.00001 * 3000 = 0.03 < 0.10)
            assert data["tvl"] == 100.0
        finally:
            del app.dependency_overrides[get_current_active_user]


class TestPnLEndpoint:
    """Tests for PnL endpoint."""

    @pytest.mark.asyncio
    async def test_returns_cached_pnl(self, authorized_client):
        """Test that cached PnL data is returned."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        async def mock_get_user():
            return mock_user

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = {
            "pnl": 150.0,
            "realized_pnl": 100.0,
            "unrealized_pnl": 50.0
        }

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache):
                response = await authorized_client.get("/api/v1/dashboard/pnl")

            assert response.status_code == 200
            data = response.json()
            assert data["pnl"] == 150.0
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_pnl_no_active_groups(self, authorized_client, db_session):
        """Test PnL when no active positions exist."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = None

        async def mock_get_user():
            return mock_user

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.set_dashboard.return_value = True

        mock_repo = AsyncMock()
        mock_repo.get_total_realized_pnl_only.return_value = Decimal("100")
        mock_repo.get_active_position_groups_for_user.return_value = []

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo):
                response = await authorized_client.get("/api/v1/dashboard/pnl")

            assert response.status_code == 200
            data = response.json()
            assert data["realized_pnl"] == 100.0
            assert data["unrealized_pnl"] == 0.0
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_pnl_with_no_valid_config(self, authorized_client, db_session):
        """Test PnL when user has no valid config for exchange."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {}}

        async def mock_get_user():
            return mock_user

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.get_tickers.return_value = None

        mock_position = MagicMock()
        mock_position.exchange = "binance"

        mock_repo = AsyncMock()
        mock_repo.get_total_realized_pnl_only.return_value = Decimal("100")
        mock_repo.get_active_position_groups_for_user.return_value = [mock_position]

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.has_valid_config.return_value = False  # No valid config

                response = await authorized_client.get("/api/v1/dashboard/pnl")

            assert response.status_code == 200
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_pnl_connector_creation_fails(self, authorized_client, db_session):
        """Test PnL when connector creation fails."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {}}

        async def mock_get_user():
            return mock_user

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.get_tickers.return_value = None

        mock_position = MagicMock()
        mock_position.exchange = "binance"

        mock_repo = AsyncMock()
        mock_repo.get_total_realized_pnl_only.return_value = Decimal("100")
        mock_repo.get_active_position_groups_for_user.return_value = [mock_position]

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.has_valid_config.return_value = True
                mock_config.get_connector.side_effect = Exception("Connector error")

                response = await authorized_client.get("/api/v1/dashboard/pnl")

            assert response.status_code == 200
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_pnl_uses_cached_tickers(self, authorized_client, db_session):
        """Test PnL calculation using cached tickers."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {}}

        async def mock_get_user():
            return mock_user

        mock_connector = AsyncMock()

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.get_tickers.return_value = {"BTC/USDT": {"last": 55000.0}}

        mock_position = MagicMock()
        mock_position.exchange = "binance"
        mock_position.symbol = "BTC/USDT"
        mock_position.side = "long"
        mock_position.total_filled_quantity = Decimal("0.1")
        mock_position.weighted_avg_entry = Decimal("50000")

        mock_repo = AsyncMock()
        mock_repo.get_total_realized_pnl_only.return_value = Decimal("0")
        mock_repo.get_active_position_groups_for_user.return_value = [mock_position]

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.has_valid_config.return_value = True
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.get("/api/v1/dashboard/pnl")

            assert response.status_code == 200
            data = response.json()
            # Unrealized PnL: (55000 - 50000) * 0.1 = 500
            assert data["unrealized_pnl"] == 500.0
            # Tickers from cache, no exchange call
            mock_connector.get_all_tickers.assert_not_called()
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_pnl_short_position(self, authorized_client, db_session):
        """Test PnL calculation for short position."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {}}

        async def mock_get_user():
            return mock_user

        mock_connector = AsyncMock()
        mock_connector.get_all_tickers.return_value = {"BTC/USDT": {"last": 45000.0}}

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.get_tickers.return_value = None
        mock_cache.set_tickers.return_value = True

        mock_position = MagicMock()
        mock_position.exchange = "binance"
        mock_position.symbol = "BTC/USDT"
        mock_position.side = "short"  # Short position
        mock_position.total_filled_quantity = Decimal("0.1")
        mock_position.weighted_avg_entry = Decimal("50000")

        mock_repo = AsyncMock()
        mock_repo.get_total_realized_pnl_only.return_value = Decimal("0")
        mock_repo.get_active_position_groups_for_user.return_value = [mock_position]

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.has_valid_config.return_value = True
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.get("/api/v1/dashboard/pnl")

            assert response.status_code == 200
            data = response.json()
            # Short PnL: (50000 - 45000) * 0.1 = 500 (profit when price drops)
            assert data["unrealized_pnl"] == 500.0
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_pnl_price_fetch_exception(self, authorized_client, db_session):
        """Test PnL handles price fetch errors gracefully."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {}}

        async def mock_get_user():
            return mock_user

        mock_connector = AsyncMock()
        mock_connector.get_all_tickers.return_value = {}
        mock_connector.get_current_price.side_effect = Exception("Price error")

        mock_cache = AsyncMock()
        mock_cache.get_dashboard.return_value = None
        mock_cache.set_dashboard.return_value = True
        mock_cache.get_tickers.return_value = None
        mock_cache.set_tickers.return_value = True

        mock_position = MagicMock()
        mock_position.exchange = "binance"
        mock_position.symbol = "BTC/USDT"
        mock_position.side = "long"
        mock_position.total_filled_quantity = Decimal("0.1")
        mock_position.weighted_avg_entry = Decimal("50000")

        mock_repo = AsyncMock()
        mock_repo.get_total_realized_pnl_only.return_value = Decimal("100")
        mock_repo.get_active_position_groups_for_user.return_value = [mock_position]

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.get_cache", return_value=mock_cache), \
                 patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo), \
                 patch("app.api.dashboard.ExchangeConfigService") as mock_config:
                mock_config.has_valid_config.return_value = True
                mock_config.get_connector.return_value = mock_connector

                response = await authorized_client.get("/api/v1/dashboard/pnl")

            assert response.status_code == 200
        finally:
            del app.dependency_overrides[get_current_active_user]


class TestStatsEndpoint:
    """Tests for stats endpoint."""

    @pytest.mark.asyncio
    async def test_stats_calculates_win_rate(self, authorized_client):
        """Test stats endpoint calculates win rate correctly."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        async def mock_get_user():
            return mock_user

        # Create mock positions
        win1 = MagicMock()
        win1.realized_pnl_usd = Decimal("100")
        win2 = MagicMock()
        win2.realized_pnl_usd = Decimal("50")
        loss1 = MagicMock()
        loss1.realized_pnl_usd = Decimal("-30")

        mock_repo = AsyncMock()
        mock_repo.get_closed_by_user_all.return_value = [win1, win2, loss1]

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo):
                response = await authorized_client.get("/api/v1/dashboard/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_trades"] == 3
            assert data["total_winning_trades"] == 2
            assert data["total_losing_trades"] == 1
            # Win rate: 2/3 * 100 = 66.67%
            assert abs(data["win_rate"] - 66.67) < 0.1
        finally:
            del app.dependency_overrides[get_current_active_user]

    @pytest.mark.asyncio
    async def test_stats_no_trades(self, authorized_client):
        """Test stats endpoint with no trades."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_closed_by_user_all.return_value = []

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo):
                response = await authorized_client.get("/api/v1/dashboard/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_trades"] == 0
            assert data["win_rate"] == 0.0
        finally:
            del app.dependency_overrides[get_current_active_user]


class TestActiveGroupsCount:
    """Tests for active-groups-count endpoint."""

    @pytest.mark.asyncio
    async def test_active_groups_count(self, authorized_client):
        """Test active groups count endpoint."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        async def mock_get_user():
            return mock_user

        mock_repo = AsyncMock()
        mock_repo.get_active_position_groups_for_user.return_value = [MagicMock(), MagicMock(), MagicMock()]

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.api.dashboard.PositionGroupRepository", return_value=mock_repo):
                response = await authorized_client.get("/api/v1/dashboard/active-groups-count")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 3
        finally:
            del app.dependency_overrides[get_current_active_user]


class TestAnalyticsEndpoint:
    """Tests for analytics endpoint."""

    @pytest.mark.asyncio
    async def test_analytics_endpoint(self, authorized_client):
        """Test comprehensive analytics endpoint."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        async def mock_get_user():
            return mock_user

        mock_analytics_data = {
            "tvl": 10000.0,
            "free_usdt": 5000.0,
            "total_pnl": 500.0,
            "realized_pnl": 300.0,
            "unrealized_pnl": 200.0,
            "win_rate": 65.0
        }

        app.dependency_overrides[get_current_active_user] = mock_get_user

        try:
            with patch("app.services.analytics_service.AnalyticsService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.get_comprehensive_dashboard_data.return_value = mock_analytics_data
                mock_service_class.return_value = mock_service

                response = await authorized_client.get("/api/v1/dashboard/analytics")

            assert response.status_code == 200
            data = response.json()
            assert data["tvl"] == 10000.0
            assert data["win_rate"] == 65.0
        finally:
            del app.dependency_overrides[get_current_active_user]
