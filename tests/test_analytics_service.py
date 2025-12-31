"""
Tests for AnalyticsService to improve coverage.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from app.services.analytics_service import AnalyticsService
from app.models.position_group import PositionGroup, PositionGroupStatus


@pytest.fixture
def mock_session():
    """Create mock session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_user():
    """Create mock user."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    return user


@pytest.fixture
def analytics_service(mock_session, mock_user):
    """Create AnalyticsService instance."""
    return AnalyticsService(mock_session, mock_user)


class TestGetPriceFromCache:
    """Tests for _get_price_from_cache method."""

    def test_price_found_with_slash(self, analytics_service):
        """Test price lookup with symbol containing slash."""
        tickers = {"BTC/USDT": {"last": 50000.0}}
        result = analytics_service._get_price_from_cache("BTC/USDT", tickers)
        assert result == 50000.0

    def test_price_found_without_slash(self, analytics_service):
        """Test price lookup with normalized symbol."""
        tickers = {"BTCUSDT": {"last": 50000.0}}
        result = analytics_service._get_price_from_cache("BTC/USDT", tickers)
        assert result == 50000.0

    def test_price_not_found(self, analytics_service):
        """Test price lookup when not in cache."""
        tickers = {"ETH/USDT": {"last": 3000.0}}
        result = analytics_service._get_price_from_cache("BTC/USDT", tickers)
        assert result is None

    def test_price_none_in_ticker(self, analytics_service):
        """Test when last price is None in ticker."""
        tickers = {"BTC/USDT": {"last": None}}
        result = analytics_service._get_price_from_cache("BTC/USDT", tickers)
        assert result is None


class TestFetchDatabaseMetrics:
    """Tests for _fetch_database_metrics method."""

    @pytest.mark.asyncio
    async def test_fetch_metrics_with_positions(self, analytics_service, mock_session):
        """Test fetching metrics when positions exist."""
        # Mock position repo
        mock_position1 = MagicMock()
        mock_position1.created_at = datetime.utcnow()
        mock_position2 = MagicMock()
        mock_position2.created_at = datetime.utcnow() - timedelta(hours=1)

        with patch.object(analytics_service.position_repo, 'get_active_position_groups_for_user',
                         return_value=[mock_position1, mock_position2]), \
             patch.object(analytics_service.position_repo, 'get_closed_by_user_all',
                         return_value=[]):
            # Mock queued signals count
            mock_result = MagicMock()
            mock_result.scalar.return_value = 5
            mock_session.execute.return_value = mock_result

            active, closed, queued_count, last_time = await analytics_service._fetch_database_metrics()

            assert len(active) == 2
            assert queued_count == 5
            assert last_time is not None

    @pytest.mark.asyncio
    async def test_fetch_metrics_no_positions(self, analytics_service, mock_session):
        """Test fetching metrics when no positions exist."""
        with patch.object(analytics_service.position_repo, 'get_active_position_groups_for_user',
                         return_value=[]), \
             patch.object(analytics_service.position_repo, 'get_closed_by_user_all',
                         return_value=[]):
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0
            mock_session.execute.return_value = mock_result

            active, closed, queued_count, last_time = await analytics_service._fetch_database_metrics()

            assert len(active) == 0
            assert queued_count == 0
            assert last_time is None


class TestFetchExchangeDataOptimized:
    """Tests for _fetch_exchange_data_optimized method."""

    @pytest.mark.asyncio
    async def test_fetch_no_api_keys(self, mock_session):
        """Test fetching when user has no API keys."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.encrypted_api_keys = None

        service = AnalyticsService(mock_session, user)
        result = await service._fetch_exchange_data_optimized([])

        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_with_cached_data(self, analytics_service, mock_user):
        """Test fetching uses cached balance and tickers."""
        mock_position = MagicMock()
        mock_position.exchange = "binance"

        mock_cache = AsyncMock()
        mock_cache.get_balance.return_value = {"total": {"USDT": 1000}, "free": {"USDT": 1000}}
        mock_cache.get_tickers.return_value = {"BTC/USDT": {"last": 50000}}

        mock_connector = AsyncMock()

        with patch("app.services.analytics_service.get_cache", return_value=mock_cache), \
             patch("app.services.analytics_service.ExchangeConfigService") as mock_config:
            mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
            mock_config.has_valid_config.return_value = True
            mock_config.get_connector.return_value = mock_connector

            result = await analytics_service._fetch_exchange_data_optimized([mock_position])

            assert "binance" in result
            assert result["binance"]["balances"] == {"total": {"USDT": 1000}, "free": {"USDT": 1000}}
            # Should not call exchange for balance (cached)
            mock_connector.fetch_balance.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_from_exchange(self, analytics_service, mock_user):
        """Test fetching from exchange when not cached."""
        mock_position = MagicMock()
        mock_position.exchange = "binance"

        mock_cache = AsyncMock()
        mock_cache.get_balance.return_value = None  # Not cached
        mock_cache.get_tickers.return_value = None  # Not cached
        mock_cache.set_balance.return_value = True
        mock_cache.set_tickers.return_value = True

        mock_connector = AsyncMock()
        mock_connector.fetch_balance.return_value = {"total": {"USDT": 2000}, "free": {"USDT": 2000}}
        mock_connector.get_all_tickers.return_value = {"ETH/USDT": {"last": 3000}}

        with patch("app.services.analytics_service.get_cache", return_value=mock_cache), \
             patch("app.services.analytics_service.ExchangeConfigService") as mock_config:
            mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
            mock_config.has_valid_config.return_value = True
            mock_config.get_connector.return_value = mock_connector

            result = await analytics_service._fetch_exchange_data_optimized([mock_position])

            assert "binance" in result
            mock_connector.fetch_balance.assert_called_once()
            mock_connector.get_all_tickers.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_no_valid_config(self, analytics_service, mock_user):
        """Test skipping exchange with no valid config."""
        mock_position = MagicMock()
        mock_position.exchange = "binance"

        mock_cache = AsyncMock()

        with patch("app.services.analytics_service.get_cache", return_value=mock_cache), \
             patch("app.services.analytics_service.ExchangeConfigService") as mock_config:
            mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
            mock_config.has_valid_config.return_value = False  # No valid config

            result = await analytics_service._fetch_exchange_data_optimized([mock_position])

            assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_ticker_error(self, analytics_service, mock_user):
        """Test handling ticker fetch error."""
        mock_position = MagicMock()
        mock_position.exchange = "binance"

        mock_cache = AsyncMock()
        mock_cache.get_balance.return_value = None
        mock_cache.get_tickers.return_value = None
        mock_cache.set_balance.return_value = True

        mock_connector = AsyncMock()
        mock_connector.fetch_balance.return_value = {"total": {"USDT": 1000}, "free": {"USDT": 1000}}
        mock_connector.get_all_tickers.side_effect = Exception("API error")

        with patch("app.services.analytics_service.get_cache", return_value=mock_cache), \
             patch("app.services.analytics_service.ExchangeConfigService") as mock_config:
            mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
            mock_config.has_valid_config.return_value = True
            mock_config.get_connector.return_value = mock_connector

            result = await analytics_service._fetch_exchange_data_optimized([mock_position])

            assert "binance" in result
            assert result["binance"]["tickers"] == {}

    @pytest.mark.asyncio
    async def test_fetch_connector_error(self, analytics_service, mock_user):
        """Test handling connector error."""
        mock_position = MagicMock()
        mock_position.exchange = "binance"

        mock_cache = AsyncMock()

        with patch("app.services.analytics_service.get_cache", return_value=mock_cache), \
             patch("app.services.analytics_service.ExchangeConfigService") as mock_config:
            mock_config.get_all_configured_exchanges.return_value = {"binance": {}}
            mock_config.has_valid_config.return_value = True
            mock_config.get_connector.side_effect = Exception("Connection error")

            result = await analytics_service._fetch_exchange_data_optimized([mock_position])

            assert "binance" not in result


class TestCalculateLiveDashboard:
    """Tests for _calculate_live_dashboard method."""

    def test_live_dashboard_no_positions(self, analytics_service):
        """Test live dashboard with no positions."""
        result = analytics_service._calculate_live_dashboard(
            active_positions=[],
            closed_positions=[],
            queued_signals_count=0,
            last_webhook_time=None,
            exchange_data={}
        )

        assert result["total_active_position_groups"] == 0
        assert result["total_pnl_usd"] == 0.0
        assert result["win_rate"] == 0.0

    def test_live_dashboard_with_positions(self, analytics_service):
        """Test live dashboard with active and closed positions."""
        # Mock active position
        active = MagicMock()
        active.exchange = "binance"
        active.symbol = "BTC/USDT"
        active.side = "long"
        active.total_filled_quantity = Decimal("0.1")
        active.weighted_avg_entry = Decimal("50000")

        # Mock closed positions
        win = MagicMock()
        win.realized_pnl_usd = Decimal("100")
        win.closed_at = datetime.utcnow()

        loss = MagicMock()
        loss.realized_pnl_usd = Decimal("-50")
        loss.closed_at = datetime.utcnow() - timedelta(days=2)

        exchange_data = {
            "binance": {
                "balances": {"total": {"USDT": 1000, "BTC": 0.1}, "free": {"USDT": 1000}},
                "tickers": {"BTC/USDT": {"last": 55000.0}}
            }
        }

        result = analytics_service._calculate_live_dashboard(
            active_positions=[active],
            closed_positions=[win, loss],
            queued_signals_count=3,
            last_webhook_time=datetime.utcnow(),
            exchange_data=exchange_data
        )

        assert result["total_active_position_groups"] == 1
        assert result["queued_signals_count"] == 3
        assert result["total_trades"] == 2
        assert result["wins"] == 1
        assert result["losses"] == 1
        assert result["win_rate"] == 50.0
        assert result["unrealized_pnl_usd"] == 500.0  # (55000-50000) * 0.1

    def test_live_dashboard_short_position(self, analytics_service):
        """Test live dashboard with short position."""
        active = MagicMock()
        active.exchange = "binance"
        active.symbol = "BTC/USDT"
        active.side = "short"
        active.total_filled_quantity = Decimal("0.1")
        active.weighted_avg_entry = Decimal("50000")

        exchange_data = {
            "binance": {
                "balances": {"total": {"USDT": 1000}, "free": {"USDT": 1000}},
                "tickers": {"BTC/USDT": {"last": 45000.0}}  # Price dropped
            }
        }

        result = analytics_service._calculate_live_dashboard(
            active_positions=[active],
            closed_positions=[],
            queued_signals_count=0,
            last_webhook_time=None,
            exchange_data=exchange_data
        )

        # Short profit: (50000-45000) * 0.1 = 500
        assert result["unrealized_pnl_usd"] == 500.0

    def test_live_dashboard_pnl_calculation_error(self, analytics_service):
        """Test live dashboard handles PnL calculation errors."""
        active = MagicMock()
        active.exchange = "binance"
        active.symbol = "BTC/USDT"
        active.side = "long"
        active.total_filled_quantity = None  # Will cause error
        active.weighted_avg_entry = Decimal("50000")

        exchange_data = {
            "binance": {
                "balances": {"total": {"USDT": 1000}, "free": {"USDT": 1000}},
                "tickers": {"BTC/USDT": {"last": 55000.0}}
            }
        }

        # Should not raise
        result = analytics_service._calculate_live_dashboard(
            active_positions=[active],
            closed_positions=[],
            queued_signals_count=0,
            last_webhook_time=None,
            exchange_data=exchange_data
        )

        assert result["unrealized_pnl_usd"] == 0.0


class TestCalculatePerformanceDashboard:
    """Tests for _calculate_performance_dashboard method."""

    def test_performance_no_trades(self, analytics_service):
        """Test performance dashboard with no trades."""
        result = analytics_service._calculate_performance_dashboard(
            closed_positions=[],
            active_positions=[],
            exchange_data={}
        )

        assert result["win_loss_stats"]["total_trades"] == 0
        assert result["win_loss_stats"]["win_rate"] == 0.0
        assert result["risk_metrics"]["sharpe_ratio"] == 0.0

    def test_performance_with_trades(self, analytics_service):
        """Test performance dashboard with trades."""
        # Create mock closed positions
        positions = []
        now = datetime.utcnow()

        for i in range(5):
            pos = MagicMock()
            pos.symbol = "BTC/USDT"
            pos.timeframe = 60
            pos.realized_pnl_usd = Decimal("100" if i % 2 == 0 else "-50")
            pos.closed_at = now - timedelta(hours=i)
            positions.append(pos)

        result = analytics_service._calculate_performance_dashboard(
            closed_positions=positions,
            active_positions=[],
            exchange_data={}
        )

        assert result["win_loss_stats"]["total_trades"] == 5
        assert result["win_loss_stats"]["wins"] == 3  # 0, 2, 4
        assert result["win_loss_stats"]["losses"] == 2  # 1, 3
        assert result["pnl_metrics"]["pnl_by_pair"]["BTC/USDT"] == 200  # 3*100 - 2*50

    def test_performance_drawdown_calculation(self, analytics_service):
        """Test drawdown calculation."""
        positions = []
        now = datetime.utcnow()

        # Create sequence: +100, +100, -50, -100, +50
        pnls = [100, 100, -50, -100, 50]
        for i, pnl in enumerate(pnls):
            pos = MagicMock()
            pos.symbol = "BTC/USDT"
            pos.timeframe = 60
            pos.realized_pnl_usd = Decimal(str(pnl))
            pos.closed_at = now - timedelta(hours=len(pnls) - i)
            positions.append(pos)

        result = analytics_service._calculate_performance_dashboard(
            closed_positions=positions,
            active_positions=[],
            exchange_data={}
        )

        # Max equity was 200 (after first two), dropped to 50
        assert result["risk_metrics"]["max_drawdown"] == 150.0

    def test_performance_profit_factor(self, analytics_service):
        """Test profit factor calculation."""
        positions = []
        now = datetime.utcnow()

        # 2 wins of 100, 1 loss of 100
        pos1 = MagicMock()
        pos1.symbol = "BTC/USDT"
        pos1.timeframe = 60
        pos1.realized_pnl_usd = Decimal("100")
        pos1.closed_at = now - timedelta(hours=3)
        positions.append(pos1)

        pos2 = MagicMock()
        pos2.symbol = "BTC/USDT"
        pos2.timeframe = 60
        pos2.realized_pnl_usd = Decimal("100")
        pos2.closed_at = now - timedelta(hours=2)
        positions.append(pos2)

        pos3 = MagicMock()
        pos3.symbol = "BTC/USDT"
        pos3.timeframe = 60
        pos3.realized_pnl_usd = Decimal("-100")
        pos3.closed_at = now - timedelta(hours=1)
        positions.append(pos3)

        result = analytics_service._calculate_performance_dashboard(
            closed_positions=positions,
            active_positions=[],
            exchange_data={}
        )

        # Profit factor: 200/100 = 2.0
        assert result["risk_metrics"]["profit_factor"] == 2.0

    def test_performance_all_wins(self, analytics_service):
        """Test performance with all winning trades."""
        positions = []
        now = datetime.utcnow()

        for i in range(3):
            pos = MagicMock()
            pos.symbol = "ETH/USDT"
            pos.timeframe = 60
            pos.realized_pnl_usd = Decimal("50")
            pos.closed_at = now - timedelta(hours=i)
            positions.append(pos)

        result = analytics_service._calculate_performance_dashboard(
            closed_positions=positions,
            active_positions=[],
            exchange_data={}
        )

        assert result["win_loss_stats"]["win_rate"] == 100.0
        assert result["win_loss_stats"]["avg_loss"] == 0.0
        assert result["risk_metrics"]["sortino_ratio"] == 0.0  # No negative returns


class TestGetComprehensiveDashboardData:
    """Tests for get_comprehensive_dashboard_data method."""

    @pytest.mark.asyncio
    async def test_comprehensive_dashboard(self, analytics_service):
        """Test comprehensive dashboard data retrieval."""
        with patch.object(analytics_service, '_fetch_database_metrics') as mock_db, \
             patch.object(analytics_service, '_fetch_exchange_data_optimized') as mock_exchange:
            mock_db.return_value = ([], [], 0, None)
            mock_exchange.return_value = {}

            result = await analytics_service.get_comprehensive_dashboard_data()

            assert "live_dashboard" in result
            assert "performance_dashboard" in result
            assert "timestamp" in result
            mock_db.assert_called_once()
            mock_exchange.assert_called_once()