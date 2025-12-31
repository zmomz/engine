"""Extended tests for exchange_abstraction/factory.py coverage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.exchange_abstraction.factory import (
    get_exchange_connector,
    get_supported_exchanges,
    clear_connector_cache,
    _get_cache_key,
    _cleanup_expired_connectors,
    _connector_cache,
    CONNECTOR_CACHE_TTL,
    UnsupportedExchangeError,
)
from app.services.exchange_abstraction.mock_connector import MockConnector


class TestGetCacheKey:
    """Tests for _get_cache_key function."""

    def test_generates_unique_key(self):
        """Test that different parameters generate different keys."""
        # Use keys with different first 8 chars (the prefix used in cache key)
        key1 = _get_cache_key("binance", "12345678abcd", False, "UNIFIED", "spot")
        key2 = _get_cache_key("binance", "87654321abcd", False, "UNIFIED", "spot")
        key3 = _get_cache_key("bybit", "12345678abcd", False, "UNIFIED", "spot")

        assert key1 != key2  # Different API key prefix
        assert key1 != key3  # Different exchange
        assert key2 != key3

    def test_same_params_same_key(self):
        """Test that same parameters generate same key."""
        key1 = _get_cache_key("binance", "api_key_123", True, "UNIFIED", "future")
        key2 = _get_cache_key("binance", "api_key_123", True, "UNIFIED", "future")

        assert key1 == key2

    def test_testnet_difference(self):
        """Test that testnet flag creates different keys."""
        key1 = _get_cache_key("binance", "api_key_123", False, "UNIFIED", "spot")
        key2 = _get_cache_key("binance", "api_key_123", True, "UNIFIED", "spot")

        assert key1 != key2

    def test_account_type_difference(self):
        """Test that account_type creates different keys."""
        key1 = _get_cache_key("bybit", "api_key_123", False, "UNIFIED", "spot")
        key2 = _get_cache_key("bybit", "api_key_123", False, "CONTRACT", "spot")

        assert key1 != key2


class TestGetSupportedExchanges:
    """Tests for get_supported_exchanges function."""

    def test_returns_all_exchanges(self):
        """Test that all supported exchanges are returned."""
        exchanges = get_supported_exchanges()

        assert "binance" in exchanges
        assert "bybit" in exchanges
        assert "mock" in exchanges

    def test_returns_list(self):
        """Test that the return type is a list."""
        exchanges = get_supported_exchanges()
        assert isinstance(exchanges, list)

    def test_exchange_count(self):
        """Test that exactly 3 exchanges are supported."""
        exchanges = get_supported_exchanges()
        assert len(exchanges) == 3


class TestGetExchangeConnectorMock:
    """Tests for mock connector creation."""

    def test_mock_with_default_config(self):
        """Test mock connector with default config."""
        connector = get_exchange_connector("mock", {})

        assert isinstance(connector, MockConnector)
        assert connector.api_key == "mock_api_key_12345"
        assert connector.api_secret == "mock_api_secret_67890"

    def test_mock_with_custom_config(self):
        """Test mock connector with custom config."""
        config = {
            "api_key": "custom_key",
            "api_secret": "custom_secret",
        }
        connector = get_exchange_connector("mock", config)

        assert isinstance(connector, MockConnector)
        assert connector.api_key == "custom_key"
        assert connector.api_secret == "custom_secret"

    def test_mock_case_insensitive(self):
        """Test that exchange type is case insensitive."""
        connector1 = get_exchange_connector("MOCK", {})
        connector2 = get_exchange_connector("Mock", {})
        connector3 = get_exchange_connector("mock", {})

        assert isinstance(connector1, MockConnector)
        assert isinstance(connector2, MockConnector)
        assert isinstance(connector3, MockConnector)


class TestConnectorCaching:
    """Tests for connector caching behavior."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before and after each test."""
        _connector_cache.clear()
        yield
        _connector_cache.clear()

    def test_cache_hit(self):
        """Test that cached connector is returned on cache hit."""
        mock_encrypted_data = "dummy_encrypted_data"
        exchange_config = {
            "encrypted_data": mock_encrypted_data,
            "testnet": False,
            "default_type": "spot",
        }

        with patch("app.core.security.EncryptionService.decrypt_keys", return_value=("test_key", "test_secret")):
            with patch("ccxt.async_support.binance") as mock_binance:
                mock_binance.return_value = MagicMock()

                # First call creates connector
                connector1 = get_exchange_connector("binance", exchange_config)

                # Second call should return cached
                connector2 = get_exchange_connector("binance", exchange_config)

                assert connector1 is connector2
                # Binance constructor called only once
                assert mock_binance.call_count == 1

    def test_use_cache_false(self):
        """Test that use_cache=False creates new connector."""
        mock_encrypted_data = "dummy_encrypted_data"
        exchange_config = {
            "encrypted_data": mock_encrypted_data,
            "testnet": False,
            "default_type": "spot",
        }

        with patch("app.core.security.EncryptionService.decrypt_keys", return_value=("test_key", "test_secret")):
            with patch("ccxt.async_support.binance") as mock_binance:
                mock_binance.return_value = MagicMock()

                connector1 = get_exchange_connector("binance", exchange_config, use_cache=True)
                connector2 = get_exchange_connector("binance", exchange_config, use_cache=False)

                # Different instances
                assert connector1 is not connector2
                # Binance constructor called twice
                assert mock_binance.call_count == 2

    def test_cache_expires(self):
        """Test that expired cache entry is removed."""
        mock_encrypted_data = "dummy_encrypted_data"
        exchange_config = {
            "encrypted_data": mock_encrypted_data,
            "testnet": False,
            "default_type": "spot",
        }

        with patch("app.core.security.EncryptionService.decrypt_keys", return_value=("test_key", "test_secret")):
            with patch("ccxt.async_support.binance") as mock_binance:
                mock_binance.return_value = MagicMock()

                # First call
                connector1 = get_exchange_connector("binance", exchange_config)

                # Manually expire the cache entry
                for key in list(_connector_cache.keys()):
                    connector, _ = _connector_cache[key]
                    # Set created_time to past (expired)
                    _connector_cache[key] = (connector, datetime.utcnow() - CONNECTOR_CACHE_TTL - timedelta(minutes=1))

                # Second call should create new connector
                connector2 = get_exchange_connector("binance", exchange_config)

                assert connector1 is not connector2
                assert mock_binance.call_count == 2


class TestCleanupExpiredConnectors:
    """Tests for _cleanup_expired_connectors function."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before and after each test."""
        _connector_cache.clear()
        yield
        _connector_cache.clear()

    @pytest.mark.asyncio
    async def test_removes_expired_connectors(self):
        """Test that expired connectors are removed."""
        # Add an expired connector
        mock_connector = MagicMock()
        expired_time = datetime.utcnow() - CONNECTOR_CACHE_TTL - timedelta(minutes=1)
        _connector_cache["expired_key"] = (mock_connector, expired_time)

        # Add a valid connector
        valid_time = datetime.utcnow()
        _connector_cache["valid_key"] = (mock_connector, valid_time)

        await _cleanup_expired_connectors()

        assert "expired_key" not in _connector_cache
        assert "valid_key" in _connector_cache

    @pytest.mark.asyncio
    async def test_closes_connector_exchange(self):
        """Test that connector's exchange is closed on cleanup."""
        mock_exchange = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.exchange = mock_exchange

        expired_time = datetime.utcnow() - CONNECTOR_CACHE_TTL - timedelta(minutes=1)
        _connector_cache["expired_key"] = (mock_connector, expired_time)

        await _cleanup_expired_connectors()

        mock_exchange.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_close_exception(self):
        """Test that cleanup handles close exceptions gracefully."""
        mock_exchange = AsyncMock()
        mock_exchange.close.side_effect = Exception("Close failed")
        mock_connector = MagicMock()
        mock_connector.exchange = mock_exchange

        expired_time = datetime.utcnow() - CONNECTOR_CACHE_TTL - timedelta(minutes=1)
        _connector_cache["expired_key"] = (mock_connector, expired_time)

        # Should not raise
        await _cleanup_expired_connectors()

        assert "expired_key" not in _connector_cache

    @pytest.mark.asyncio
    async def test_handles_no_exchange(self):
        """Test cleanup handles connector without exchange attribute."""
        mock_connector = MagicMock(spec=[])  # No attributes

        expired_time = datetime.utcnow() - CONNECTOR_CACHE_TTL - timedelta(minutes=1)
        _connector_cache["expired_key"] = (mock_connector, expired_time)

        # Should not raise
        await _cleanup_expired_connectors()

        assert "expired_key" not in _connector_cache


class TestClearConnectorCache:
    """Tests for clear_connector_cache function."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before and after each test."""
        _connector_cache.clear()
        yield
        _connector_cache.clear()

    @pytest.mark.asyncio
    async def test_clears_all_connectors(self):
        """Test that all connectors are cleared."""
        # Add multiple connectors
        _connector_cache["key1"] = (MagicMock(), datetime.utcnow())
        _connector_cache["key2"] = (MagicMock(), datetime.utcnow())
        _connector_cache["key3"] = (MagicMock(), datetime.utcnow())

        await clear_connector_cache()

        assert len(_connector_cache) == 0

    @pytest.mark.asyncio
    async def test_closes_all_exchanges(self):
        """Test that all connector exchanges are closed."""
        mock_exchange1 = AsyncMock()
        mock_connector1 = MagicMock()
        mock_connector1.exchange = mock_exchange1

        mock_exchange2 = AsyncMock()
        mock_connector2 = MagicMock()
        mock_connector2.exchange = mock_exchange2

        _connector_cache["key1"] = (mock_connector1, datetime.utcnow())
        _connector_cache["key2"] = (mock_connector2, datetime.utcnow())

        await clear_connector_cache()

        mock_exchange1.close.assert_awaited_once()
        mock_exchange2.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_close_exception_on_clear(self):
        """Test that clear handles close exceptions gracefully."""
        mock_exchange = AsyncMock()
        mock_exchange.close.side_effect = Exception("Close failed")
        mock_connector = MagicMock()
        mock_connector.exchange = mock_exchange

        _connector_cache["key1"] = (mock_connector, datetime.utcnow())

        # Should not raise
        await clear_connector_cache()

        assert len(_connector_cache) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_cache(self):
        """Test that clearing empty cache works."""
        assert len(_connector_cache) == 0

        # Should not raise
        await clear_connector_cache()

        assert len(_connector_cache) == 0


class TestUnsupportedExchangeError:
    """Tests for UnsupportedExchangeError."""

    def test_error_message(self):
        """Test that error message is correct."""
        mock_encrypted_data = "dummy_encrypted_data"
        exchange_config = {"encrypted_data": mock_encrypted_data}

        with patch("app.core.security.EncryptionService.decrypt_keys", return_value=("key", "secret")):
            with pytest.raises(UnsupportedExchangeError, match="Exchange type 'invalid_exchange' is not supported"):
                get_exchange_connector("invalid_exchange", exchange_config)

    def test_error_is_exception(self):
        """Test that UnsupportedExchangeError is an Exception."""
        error = UnsupportedExchangeError("test")
        assert isinstance(error, Exception)


class TestBybitConnectorCreation:
    """Tests for Bybit connector creation with caching."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before and after each test."""
        _connector_cache.clear()
        yield
        _connector_cache.clear()

    def test_bybit_with_account_type(self):
        """Test bybit connector creation with specific account type."""
        mock_encrypted_data = "dummy_encrypted_data"
        exchange_config = {
            "encrypted_data": mock_encrypted_data,
            "testnet": False,
            "default_type": "spot",
            "account_type": "CONTRACT",
        }

        with patch("app.core.security.EncryptionService.decrypt_keys", return_value=("test_key", "test_secret")):
            with patch("ccxt.async_support.bybit") as mock_bybit:
                mock_exchange = MagicMock()
                mock_bybit.return_value = mock_exchange

                connector = get_exchange_connector("bybit", exchange_config)

                assert connector is not None
                # Verify account type was passed
                call_args = mock_bybit.call_args[0][0]
                assert call_args["options"]["accountType"] == "CONTRACT"


class TestBinanceConnectorCreation:
    """Tests for Binance connector creation."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before and after each test."""
        _connector_cache.clear()
        yield
        _connector_cache.clear()

    def test_binance_default_type_future(self):
        """Test binance connector with future default type."""
        mock_encrypted_data = "dummy_encrypted_data"
        exchange_config = {
            "encrypted_data": mock_encrypted_data,
            "testnet": False,
            "default_type": "future",
        }

        with patch("app.core.security.EncryptionService.decrypt_keys", return_value=("test_key", "test_secret")):
            with patch("ccxt.async_support.binance") as mock_binance:
                mock_exchange = MagicMock()
                mock_binance.return_value = mock_exchange

                connector = get_exchange_connector("binance", exchange_config)

                assert connector is not None
                call_args = mock_binance.call_args[0][0]
                assert call_args["options"]["defaultType"] == "future"

    def test_binance_with_testnet(self):
        """Test binance connector with testnet enabled."""
        mock_encrypted_data = "dummy_encrypted_data"
        exchange_config = {
            "encrypted_data": mock_encrypted_data,
            "testnet": True,
            "default_type": "spot",
        }

        with patch("app.core.security.EncryptionService.decrypt_keys", return_value=("test_key", "test_secret")):
            with patch("ccxt.async_support.binance") as mock_binance:
                mock_exchange = MagicMock()
                mock_binance.return_value = mock_exchange

                connector = get_exchange_connector("binance", exchange_config)

                assert connector is not None
