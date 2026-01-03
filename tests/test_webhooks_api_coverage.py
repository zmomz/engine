"""
Tests for webhook API endpoints.
Focuses on short signal rejection and spot trading validation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
import uuid

from app.api.webhooks import tradingview_webhook


class TestShortSignalRejection:
    """Tests verifying that short signals are properly rejected in spot trading."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request with payload."""
        request = MagicMock()
        return request

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        """Create mock authenticated user."""
        user = MagicMock()
        user.id = uuid.uuid4()
        return user

    @pytest.mark.asyncio
    async def test_rejects_sell_action_without_exit_intent(self, mock_request, mock_db, mock_user):
        """Test that sell action without exit intent is rejected (short signal)."""
        # Setup payload that represents a short signal
        mock_request.json = AsyncMock(return_value={
            "user_id": str(mock_user.id),
            "secret": "test_secret",
            "source": "tradingview",
            "timestamp": "2025-01-01T00:00:00",
            "tv": {
                "exchange": "mock",
                "symbol": "BTC/USDT",
                "timeframe": 60,
                "action": "sell",  # Short signal
                "market_position": "short",
                "market_position_size": 100,
                "prev_market_position": "flat",
                "prev_market_position_size": 0,
                "entry_price": 50000,
                "close_price": 50000,
                "order_size": 100
            },
            "strategy_info": {
                "trade_id": "test",
                "alert_name": "Test",
                "alert_message": "Test"
            },
            "execution_intent": {
                "type": "signal",  # Not exit - this makes it a short signal
                "side": "sell",
                "position_size_type": "quote"
            },
            "risk": {"max_slippage_percent": 1.0}
        })

        with pytest.raises(HTTPException) as exc_info:
            await tradingview_webhook(mock_request, mock_db, mock_user)

        assert exc_info.value.status_code == 400
        assert "Spot trading does not support short positions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_allows_sell_action_with_exit_intent(self, mock_request, mock_db, mock_user):
        """Test that sell action with exit intent is allowed (closing a long position)."""
        mock_request.json = AsyncMock(return_value={
            "user_id": str(mock_user.id),
            "secret": "test_secret",
            "source": "tradingview",
            "timestamp": "2025-01-01T00:00:00",
            "tv": {
                "exchange": "mock",
                "symbol": "BTC/USDT",
                "timeframe": 60,
                "action": "sell",  # Selling to close position
                "market_position": "flat",
                "market_position_size": 0,
                "prev_market_position": "long",
                "prev_market_position_size": 100,
                "entry_price": 50000,
                "close_price": 51000,
                "order_size": 100
            },
            "strategy_info": {
                "trade_id": "test",
                "alert_name": "Test",
                "alert_message": "Test"
            },
            "execution_intent": {
                "type": "exit",  # Exit intent - closing a long position
                "side": "sell",
                "position_size_type": "quote"
            },
            "risk": {"max_slippage_percent": 1.0}
        })

        mock_cache = AsyncMock()
        mock_cache.acquire_lock = AsyncMock(return_value=True)
        mock_cache.release_lock = AsyncMock(return_value=True)

        mock_signal_router = MagicMock()
        mock_signal_router.route = AsyncMock(return_value="Position closed")

        with patch("app.api.webhooks.get_cache", return_value=mock_cache):
            with patch("app.api.webhooks.SignalRouterService", return_value=mock_signal_router):
                result = await tradingview_webhook(mock_request, mock_db, mock_user)

        # Should succeed - exit intent is allowed
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_allows_buy_action_for_long_entry(self, mock_request, mock_db, mock_user):
        """Test that buy action is allowed (entering a long position)."""
        mock_request.json = AsyncMock(return_value={
            "user_id": str(mock_user.id),
            "secret": "test_secret",
            "source": "tradingview",
            "timestamp": "2025-01-01T00:00:00",
            "tv": {
                "exchange": "mock",
                "symbol": "BTC/USDT",
                "timeframe": 60,
                "action": "buy",  # Long entry
                "market_position": "long",
                "market_position_size": 100,
                "prev_market_position": "flat",
                "prev_market_position_size": 0,
                "entry_price": 50000,
                "close_price": 50000,
                "order_size": 100
            },
            "strategy_info": {
                "trade_id": "test",
                "alert_name": "Test",
                "alert_message": "Test"
            },
            "execution_intent": {
                "type": "signal",
                "side": "buy",
                "position_size_type": "quote"
            },
            "risk": {"max_slippage_percent": 1.0}
        })

        mock_cache = AsyncMock()
        mock_cache.acquire_lock = AsyncMock(return_value=True)
        mock_cache.release_lock = AsyncMock(return_value=True)

        mock_signal_router = MagicMock()
        mock_signal_router.route = AsyncMock(return_value="Position created")

        with patch("app.api.webhooks.get_cache", return_value=mock_cache):
            with patch("app.api.webhooks.SignalRouterService", return_value=mock_signal_router):
                result = await tradingview_webhook(mock_request, mock_db, mock_user)

        # Should succeed - buy is allowed
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_rejects_short_with_signal_type_and_sell_side(self, mock_request, mock_db, mock_user):
        """Test that sell action with signal type intent (not exit) is rejected as short signal."""
        mock_request.json = AsyncMock(return_value={
            "user_id": str(mock_user.id),
            "secret": "test_secret",
            "source": "tradingview",
            "timestamp": "2025-01-01T00:00:00",
            "tv": {
                "exchange": "mock",
                "symbol": "BTC/USDT",
                "timeframe": 60,
                "action": "sell",
                "market_position": "short",
                "market_position_size": 100,
                "prev_market_position": "flat",
                "prev_market_position_size": 0,
                "entry_price": 50000,
                "close_price": 50000,
                "order_size": 100
            },
            "strategy_info": {
                "trade_id": "test",
                "alert_name": "Test",
                "alert_message": "Test"
            },
            "execution_intent": {
                "type": "signal",  # Signal type + sell = short entry = rejected
                "side": "short",
                "position_size_type": "quote"
            },
            "risk": {"max_slippage_percent": 1.0}
        })

        with pytest.raises(HTTPException) as exc_info:
            await tradingview_webhook(mock_request, mock_db, mock_user)

        assert exc_info.value.status_code == 400
        assert "Spot trading does not support short positions" in exc_info.value.detail


class TestWebhookLocking:
    """Tests for webhook distributed locking."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request with payload."""
        request = MagicMock()
        request.json = AsyncMock(return_value={
            "user_id": str(uuid.uuid4()),
            "secret": "test_secret",
            "source": "tradingview",
            "timestamp": "2025-01-01T00:00:00",
            "tv": {
                "exchange": "mock",
                "symbol": "BTC/USDT",
                "timeframe": 60,
                "action": "buy",
                "market_position": "long",
                "market_position_size": 100,
                "prev_market_position": "flat",
                "prev_market_position_size": 0,
                "entry_price": 50000,
                "close_price": 50000,
                "order_size": 100
            },
            "strategy_info": {
                "trade_id": "test",
                "alert_name": "Test",
                "alert_message": "Test"
            },
            "execution_intent": {
                "type": "signal",
                "side": "buy",
                "position_size_type": "quote"
            },
            "risk": {"max_slippage_percent": 1.0}
        })
        return request

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        """Create mock authenticated user."""
        user = MagicMock()
        user.id = uuid.uuid4()
        return user

    @pytest.mark.asyncio
    async def test_rejects_when_lock_not_acquired(self, mock_request, mock_db, mock_user):
        """Test that webhook returns 409 when lock cannot be acquired."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock = AsyncMock(return_value=False)  # Lock not acquired

        with patch("app.api.webhooks.get_cache", return_value=mock_cache):
            with pytest.raises(HTTPException) as exc_info:
                await tradingview_webhook(mock_request, mock_db, mock_user)

        assert exc_info.value.status_code == 409
        assert "Another webhook" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_releases_lock_on_success(self, mock_request, mock_db, mock_user):
        """Test that lock is released after successful processing."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock = AsyncMock(return_value=True)
        mock_cache.release_lock = AsyncMock(return_value=True)

        mock_signal_router = MagicMock()
        mock_signal_router.route = AsyncMock(return_value="Success")

        with patch("app.api.webhooks.get_cache", return_value=mock_cache):
            with patch("app.api.webhooks.SignalRouterService", return_value=mock_signal_router):
                result = await tradingview_webhook(mock_request, mock_db, mock_user)

        mock_cache.release_lock.assert_called_once()
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_releases_lock_on_failure(self, mock_request, mock_db, mock_user):
        """Test that lock is released even when processing fails."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock = AsyncMock(return_value=True)
        mock_cache.release_lock = AsyncMock(return_value=True)

        mock_signal_router = MagicMock()
        mock_signal_router.route = AsyncMock(side_effect=Exception("Processing failed"))

        with patch("app.api.webhooks.get_cache", return_value=mock_cache):
            with patch("app.api.webhooks.SignalRouterService", return_value=mock_signal_router):
                with pytest.raises(Exception):
                    await tradingview_webhook(mock_request, mock_db, mock_user)

        # Lock should still be released even after exception
        mock_cache.release_lock.assert_called_once()
