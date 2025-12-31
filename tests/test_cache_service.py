"""
Tests for CacheService - Redis cache operations.
"""
import pytest
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cache import CacheService, DecimalEncoder, decimal_decoder


class TestDecimalEncoder:
    """Tests for DecimalEncoder."""

    def test_encode_decimal(self):
        """Test encoding Decimal values."""
        data = {"price": Decimal("50000.12345")}
        encoded = json.dumps(data, cls=DecimalEncoder)
        assert encoded == '{"price": "50000.12345"}'

    def test_encode_nested_decimal(self):
        """Test encoding nested Decimal values."""
        data = {
            "level1": {
                "price": Decimal("100.50"),
                "quantity": Decimal("0.001")
            }
        }
        encoded = json.dumps(data, cls=DecimalEncoder)
        assert '"price": "100.50"' in encoded
        assert '"quantity": "0.001"' in encoded

    def test_encode_mixed_types(self):
        """Test encoding mixed types."""
        data = {
            "name": "test",
            "count": 5,
            "price": Decimal("99.99"),
            "active": True
        }
        encoded = json.dumps(data, cls=DecimalEncoder)
        parsed = json.loads(encoded)
        assert parsed["name"] == "test"
        assert parsed["count"] == 5
        assert parsed["price"] == "99.99"
        assert parsed["active"] is True


class TestDecimalDecoder:
    """Tests for decimal_decoder."""

    def test_decode_float_string(self):
        """Test decoding float strings."""
        data = {"price": "50000.12345"}
        decoded = decimal_decoder(data)
        assert decoded["price"] == 50000.12345

    def test_decode_scientific_notation(self):
        """Test decoding scientific notation strings."""
        data = {"small_value": "1.5e-8"}
        decoded = decimal_decoder(data)
        assert decoded["small_value"] == 1.5e-8

    def test_decode_non_numeric_string(self):
        """Test that non-numeric strings are not converted."""
        data = {"name": "test_string", "symbol": "BTCUSDT"}
        decoded = decimal_decoder(data)
        assert decoded["name"] == "test_string"
        assert decoded["symbol"] == "BTCUSDT"

    def test_decode_mixed_values(self):
        """Test decoding mixed values."""
        data = {
            "name": "test",
            "price": "100.50",
            "count": 5
        }
        decoded = decimal_decoder(data)
        assert decoded["name"] == "test"
        assert decoded["price"] == 100.50
        assert decoded["count"] == 5


class TestCacheServiceInit:
    """Tests for CacheService initialization."""

    def test_init_default_state(self):
        """Test initial state of CacheService."""
        cache = CacheService()
        assert cache._redis is None
        assert cache._connected is False
        assert cache._connection_attempted is False


class TestCacheServiceConnect:
    """Tests for CacheService connect method."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful Redis connection."""
        cache = CacheService()

        with patch('app.core.cache.redis.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_from_url.return_value = mock_redis

            result = await cache.connect()

            assert result is True
            assert cache._connected is True
            assert cache._connection_attempted is True

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test Redis connection failure."""
        cache = CacheService()

        with patch('app.core.cache.redis.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping.side_effect = Exception("Connection refused")
            mock_from_url.return_value = mock_redis

            result = await cache.connect()

            assert result is False
            assert cache._connected is False
            assert cache._connection_attempted is True

    @pytest.mark.asyncio
    async def test_connect_already_attempted(self):
        """Test that connection is only attempted once."""
        cache = CacheService()
        cache._connection_attempted = True
        cache._connected = True

        # Should return cached result without trying to connect
        result = await cache.connect()

        assert result is True


class TestCacheServiceClose:
    """Tests for CacheService close method."""

    @pytest.mark.asyncio
    async def test_close_connected(self):
        """Test closing an active connection."""
        cache = CacheService()
        cache._redis = AsyncMock()
        cache._redis.close = AsyncMock()
        cache._connected = True

        await cache.close()

        cache._redis.close.assert_called_once()
        assert cache._connected is False

    @pytest.mark.asyncio
    async def test_close_not_connected(self):
        """Test closing when not connected."""
        cache = CacheService()

        # Should not raise
        await cache.close()


class TestCacheServiceMakeKey:
    """Tests for CacheService _make_key method."""

    def test_make_key_single_part(self):
        """Test making key with single part."""
        cache = CacheService()
        key = cache._make_key("prefix", "part1")
        assert key == "prefix:part1"

    def test_make_key_multiple_parts(self):
        """Test making key with multiple parts."""
        cache = CacheService()
        key = cache._make_key("precision", "binance", "BTCUSDT")
        assert key == "precision:binance:BTCUSDT"

    def test_make_key_with_uuid(self):
        """Test making key with UUID."""
        import uuid
        cache = CacheService()
        user_id = uuid.uuid4()
        key = cache._make_key("user", str(user_id))
        assert key == f"user:{user_id}"


class TestCacheServiceGet:
    """Tests for CacheService get method."""

    @pytest.mark.asyncio
    async def test_get_not_connected(self):
        """Test get when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_key_exists(self):
        """Test get when key exists."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.get.return_value = '{"price": "100.50"}'

        result = await cache.get("test_key")

        assert result == {"price": 100.50}

    @pytest.mark.asyncio
    async def test_get_key_not_exists(self):
        """Test get when key does not exist."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.get.return_value = None

        result = await cache.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_exception(self):
        """Test get when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.get.side_effect = Exception("Redis error")

        result = await cache.get("test_key")

        assert result is None


class TestCacheServiceSet:
    """Tests for CacheService set method."""

    @pytest.mark.asyncio
    async def test_set_not_connected(self):
        """Test set when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.set("test_key", {"data": "value"})

        assert result is False

    @pytest.mark.asyncio
    async def test_set_success(self):
        """Test successful set."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()

        result = await cache.set("test_key", {"price": Decimal("100.50")}, ttl=60)

        assert result is True
        cache._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_exception(self):
        """Test set when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex.side_effect = Exception("Redis error")

        result = await cache.set("test_key", {"data": "value"})

        assert result is False


class TestCacheServiceDelete:
    """Tests for CacheService delete method."""

    @pytest.mark.asyncio
    async def test_delete_not_connected(self):
        """Test delete when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.delete("test_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful delete."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.delete = AsyncMock()

        result = await cache.delete("test_key")

        assert result is True
        cache._redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_exception(self):
        """Test delete when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.delete.side_effect = Exception("Redis error")

        result = await cache.delete("test_key")

        assert result is False


class TestCacheServicePrecision:
    """Tests for precision-related cache methods."""

    @pytest.mark.asyncio
    async def test_get_precision_rules(self):
        """Test getting precision rules from cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        expected_rules = {
            "BTCUSDT": {"price_precision": 2, "qty_precision": 6}
        }
        cache._redis.get.return_value = json.dumps(expected_rules)

        result = await cache.get_precision_rules("binance")

        assert result is not None

    @pytest.mark.asyncio
    async def test_set_precision_rules(self):
        """Test setting precision rules in cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()

        rules = {
            "BTCUSDT": {"price_precision": 2, "qty_precision": 6}
        }

        result = await cache.set_precision_rules("binance", rules)

        assert result is True

    @pytest.mark.asyncio
    async def test_get_symbol_precision(self):
        """Test getting precision for a specific symbol."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        rules = {
            "BTCUSDT": {"price_precision": 2, "qty_precision": 6}
        }
        cache._redis.get.return_value = json.dumps(rules)

        result = await cache.get_symbol_precision("binance", "BTCUSDT")

        assert result is not None

    @pytest.mark.asyncio
    async def test_invalidate_precision_rules(self):
        """Test invalidating precision rules."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.delete = AsyncMock()

        result = await cache.invalidate_precision_rules("binance")

        assert result is True


class TestCacheServiceTickers:
    """Tests for ticker-related cache methods."""

    @pytest.mark.asyncio
    async def test_get_tickers(self):
        """Test getting tickers from cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        expected_tickers = {
            "BTCUSDT": {"last": "50000.00"},
            "ETHUSDT": {"last": "3000.00"}
        }
        cache._redis.get.return_value = json.dumps(expected_tickers)

        result = await cache.get_tickers("binance")

        assert result is not None

    @pytest.mark.asyncio
    async def test_set_tickers(self):
        """Test setting tickers in cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()

        tickers = {
            "BTCUSDT": {"last": "50000.00"},
            "ETHUSDT": {"last": "3000.00"}
        }

        result = await cache.set_tickers("binance", tickers)

        assert result is True


class TestCacheServiceBalance:
    """Tests for balance-related cache methods."""

    @pytest.mark.asyncio
    async def test_get_balance(self):
        """Test getting balance from cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        import uuid
        user_id = uuid.uuid4()
        expected_balance = {
            "USDT": 10000.00,
            "BTC": 0.5
        }
        cache._redis.get.return_value = json.dumps(expected_balance)

        result = await cache.get_balance(str(user_id), "binance")

        assert result is not None

    @pytest.mark.asyncio
    async def test_set_balance(self):
        """Test setting balance in cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()

        import uuid
        user_id = uuid.uuid4()
        balance = {
            "USDT": Decimal("10000.00"),
            "BTC": Decimal("0.5")
        }

        result = await cache.set_balance(str(user_id), "binance", balance)

        assert result is True


class TestCacheServiceDashboard:
    """Tests for dashboard-related cache methods."""

    @pytest.mark.asyncio
    async def test_get_dashboard(self):
        """Test getting dashboard data from cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        import uuid
        user_id = uuid.uuid4()
        expected_dashboard = {
            "total_positions": 5,
            "total_pnl": "500.00"
        }
        cache._redis.get.return_value = json.dumps(expected_dashboard)

        result = await cache.get_dashboard(str(user_id), "summary")

        assert result is not None

    @pytest.mark.asyncio
    async def test_set_dashboard(self):
        """Test setting dashboard data in cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()

        import uuid
        user_id = uuid.uuid4()
        dashboard = {
            "total_positions": 5,
            "total_pnl": Decimal("500.00")
        }

        result = await cache.set_dashboard(str(user_id), "summary", dashboard)

        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_user_dashboard(self):
        """Test invalidating dashboard cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        import uuid
        user_id = uuid.uuid4()

        # Mock scan_iter to return empty list (no keys to delete)
        async def mock_scan_iter(*args, **kwargs):
            return
            yield  # Make it an async generator

        cache._redis.scan_iter = mock_scan_iter

        result = await cache.invalidate_user_dashboard(str(user_id))

        assert result == 0  # No keys deleted


class TestCacheServiceTokenBlacklist:
    """Tests for token blacklist methods."""

    @pytest.mark.asyncio
    async def test_blacklist_token(self):
        """Test adding token to blacklist."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()

        result = await cache.blacklist_token("test_jti", 3600)

        assert result is True

    @pytest.mark.asyncio
    async def test_blacklist_token_not_connected(self):
        """Test blacklisting token when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.blacklist_token("test_jti", 3600)

        assert result is False

    @pytest.mark.asyncio
    async def test_blacklist_token_exception(self):
        """Test blacklisting token when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex.side_effect = Exception("Redis error")

        result = await cache.blacklist_token("test_jti", 3600)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_true(self):
        """Test checking if token is blacklisted (true)."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.exists.return_value = 1

        result = await cache.is_token_blacklisted("test_jti")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_false(self):
        """Test checking if token is blacklisted (false)."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.exists.return_value = 0

        result = await cache.is_token_blacklisted("test_jti")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_not_connected(self):
        """Test is_token_blacklisted when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.is_token_blacklisted("test_jti")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_exception(self):
        """Test is_token_blacklisted when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.exists.side_effect = Exception("Redis error")

        result = await cache.is_token_blacklisted("test_jti")

        assert result is False


class TestCacheServiceDistributedLock:
    """Tests for distributed lock methods."""

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self):
        """Test acquiring distributed lock."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.set.return_value = True

        result = await cache.acquire_lock("webhook:user123:BTCUSDT:15", "lock_id_123", 30)

        assert result is True
        cache._redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_lock_failure(self):
        """Test failing to acquire lock (already held)."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.set.return_value = None  # SET NX returns None if key exists

        result = await cache.acquire_lock("webhook:user123:BTCUSDT:15", "lock_id_123", 30)

        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_lock_not_connected(self):
        """Test acquiring lock when not connected (fallback to True)."""
        cache = CacheService()
        cache._connected = False

        result = await cache.acquire_lock("webhook:user123:BTCUSDT:15", "lock_id_123", 30)

        assert result is True  # Fallback allows operation

    @pytest.mark.asyncio
    async def test_acquire_lock_exception(self):
        """Test acquiring lock when exception occurs (fallback to True)."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.set.side_effect = Exception("Redis error")

        result = await cache.acquire_lock("webhook:user123:BTCUSDT:15", "lock_id_123", 30)

        assert result is True  # Fallback allows operation

    @pytest.mark.asyncio
    async def test_release_lock_success(self):
        """Test releasing distributed lock."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.eval.return_value = 1  # Lua script returns 1 on success

        result = await cache.release_lock("webhook:user123:BTCUSDT:15", "lock_id_123")

        assert result is True
        cache._redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_lock_wrong_lock_id(self):
        """Test releasing lock with wrong lock_id."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.eval.return_value = 0  # Lua script returns 0 if lock_id doesn't match

        result = await cache.release_lock("webhook:user123:BTCUSDT:15", "wrong_lock_id")

        assert result is False

    @pytest.mark.asyncio
    async def test_release_lock_not_connected(self):
        """Test releasing lock when not connected (fallback to True)."""
        cache = CacheService()
        cache._connected = False

        result = await cache.release_lock("webhook:user123:BTCUSDT:15", "lock_id_123")

        assert result is True

    @pytest.mark.asyncio
    async def test_release_lock_exception(self):
        """Test releasing lock when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.eval.side_effect = Exception("Redis error")

        result = await cache.release_lock("webhook:user123:BTCUSDT:15", "lock_id_123")

        assert result is False


class TestCacheServiceDCAConfig:
    """Tests for DCA config cache methods."""

    @pytest.mark.asyncio
    async def test_get_dca_config(self):
        """Test getting DCA config from cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        expected_config = {
            "enabled": True,
            "legs": 3,
            "spacing_percent": 1.0
        }
        cache._redis.get.return_value = json.dumps(expected_config)

        result = await cache.get_dca_config("user123", "BTCUSDT", "60", "binance")

        assert result is not None

    @pytest.mark.asyncio
    async def test_set_dca_config(self):
        """Test setting DCA config in cache."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()

        config = {
            "enabled": True,
            "legs": 3,
            "spacing_percent": Decimal("1.0")
        }

        result = await cache.set_dca_config("user123", "BTCUSDT", "60", "binance", config)

        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_user_dca_configs(self):
        """Test invalidating DCA configs for user."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        # Mock scan_iter to return empty list
        async def mock_scan_iter(*args, **kwargs):
            return
            yield

        cache._redis.scan_iter = mock_scan_iter

        result = await cache.invalidate_user_dca_configs("user123")

        assert result == 0


class TestCacheServiceServiceHealth:
    """Tests for service health cache methods."""

    @pytest.mark.asyncio
    async def test_update_service_health(self):
        """Test updating service health."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()

        result = await cache.update_service_health(
            "order_fill_monitor",
            "running",
            {"cycle_count": 100}
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_service_health_not_connected(self):
        """Test updating service health when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.update_service_health("order_fill_monitor", "running")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_service_health_exception(self):
        """Test updating service health when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.setex.side_effect = Exception("Redis error")

        result = await cache.update_service_health("order_fill_monitor", "running")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_service_health(self):
        """Test getting service health."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        expected_health = {
            "status": "running",
            "last_heartbeat": 1234567890.0,
            "metrics": {"cycle_count": 100}
        }
        cache._redis.get.return_value = json.dumps(expected_health)

        result = await cache.get_service_health("order_fill_monitor")

        assert result is not None
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_service_health_not_connected(self):
        """Test getting service health when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.get_service_health("order_fill_monitor")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_service_health_exception(self):
        """Test getting service health when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()
        cache._redis.get.side_effect = Exception("Redis error")

        result = await cache.get_service_health("order_fill_monitor")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_services_health(self):
        """Test getting all services health."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        # Mock scan_iter to return keys
        async def mock_scan_iter(*args, **kwargs):
            yield "service_health:order_fill_monitor"
            yield "service_health:risk_engine"

        cache._redis.scan_iter = mock_scan_iter
        cache._redis.get.side_effect = [
            json.dumps({"status": "running"}),
            json.dumps({"status": "running"})
        ]

        result = await cache.get_all_services_health()

        assert "order_fill_monitor" in result or "risk_engine" in result

    @pytest.mark.asyncio
    async def test_get_all_services_health_not_connected(self):
        """Test getting all services health when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.get_all_services_health()

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_all_services_health_exception(self):
        """Test getting all services health when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        async def mock_scan_iter_error(*args, **kwargs):
            raise Exception("Redis error")
            yield

        cache._redis.scan_iter = mock_scan_iter_error

        result = await cache.get_all_services_health()

        assert result == {}


class TestCacheServiceDeletePattern:
    """Tests for delete_pattern method."""

    @pytest.mark.asyncio
    async def test_delete_pattern_not_connected(self):
        """Test delete_pattern when not connected."""
        cache = CacheService()
        cache._connected = False

        result = await cache.delete_pattern("test:*")

        assert result == 0

    @pytest.mark.asyncio
    async def test_delete_pattern_no_keys(self):
        """Test delete_pattern when no keys match."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            return
            yield

        cache._redis.scan_iter = mock_scan_iter

        result = await cache.delete_pattern("test:*")

        assert result == 0

    @pytest.mark.asyncio
    async def test_delete_pattern_with_keys(self):
        """Test delete_pattern when keys match."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            yield "test:key1"
            yield "test:key2"

        cache._redis.scan_iter = mock_scan_iter
        cache._redis.delete.return_value = 2

        result = await cache.delete_pattern("test:*")

        assert result == 2

    @pytest.mark.asyncio
    async def test_delete_pattern_exception(self):
        """Test delete_pattern when exception occurs."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        async def mock_scan_iter_error(*args, **kwargs):
            raise Exception("Redis error")
            yield

        cache._redis.scan_iter = mock_scan_iter_error

        result = await cache.delete_pattern("test:*")

        assert result == 0


class TestCacheServiceInvalidateUserBalances:
    """Tests for invalidate_user_balances method."""

    @pytest.mark.asyncio
    async def test_invalidate_user_balances(self):
        """Test invalidating user balances."""
        cache = CacheService()
        cache._connected = True
        cache._redis = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            yield "balance:user123:binance"
            yield "balance:user123:bybit"

        cache._redis.scan_iter = mock_scan_iter
        cache._redis.delete.return_value = 2

        result = await cache.invalidate_user_balances("user123")

        assert result == 2
