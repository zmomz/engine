import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.factory import get_exchange_connector, UnsupportedExchangeError
from app.services.exchange_abstraction.binance_connector import BinanceConnector
from app.services.exchange_abstraction.bybit_connector import BybitConnector
from app.services.exchange_abstraction.precision_service import PrecisionService

class MockExchange(ExchangeInterface):
    async def get_precision_rules(self):
        return {"symbol_1": {"precision": 2}, "symbol_2": {"precision": 4}}
    async def place_order(self, symbol: str, order_type: str, side: str, quantity: float, price: float = None, **kwargs):
        pass
    async def get_order_status(self):
        pass
    async def cancel_order(self):
        pass
    async def get_current_price(self):
        pass
    async def get_all_tickers(self):
        return {"BTC/USDT": {"last": 50000.0}, "ETH/USDT": {"last": 3000.0}}
    async def fetch_balance(self):
        pass

    async def fetch_free_balance(self):
        pass

    async def close(self):
        pass

@pytest.mark.asyncio
async def test_exchange_interface_methods():
    """
    Test that the ExchangeInterface defines the required methods.
    """
    mock_exchange = MockExchange()
    assert hasattr(mock_exchange, "get_precision_rules")
    assert hasattr(mock_exchange, "place_order")
    assert hasattr(mock_exchange, "get_order_status")
    assert hasattr(mock_exchange, "cancel_order")
    assert hasattr(mock_exchange, "get_current_price")
    assert hasattr(mock_exchange, "fetch_balance")

@pytest.mark.asyncio
async def test_get_exchange_connector_mock():
    """
    Test that the factory returns a mock exchange for 'mock' type.
    """
    mock_encrypted_data = "dummy_encrypted_data"
    exchange_config = {'encrypted_data': mock_encrypted_data, 'testnet': False}

    with patch('app.core.security.EncryptionService.decrypt_keys', return_value=("mock_key", "mock_secret")):
        connector = get_exchange_connector("mock", exchange_config)
    assert isinstance(connector, ExchangeInterface)

    @pytest.mark.asyncio
    async def test_get_exchange_connector_binance():
        """
        Test that the factory returns a BinanceConnector for 'binance' type.
        """
        mock_encrypted_data = "dummy_encrypted_data"
        exchange_config = {
            "encrypted_data": mock_encrypted_data,
            "testnet": False,
            "default_type": "spot" # Changed to spot
        }

        with patch('app.core.security.EncryptionService.decrypt_keys', return_value=("test_key", "test_secret")) as mock_decrypt_keys:
            with patch('os.getenv', return_value="future"):
                with patch('ccxt.async_support.binance') as mock_binance_ccxt:
                    mock_exchange_instance = MagicMock()
                    mock_exchange_instance.load_markets = AsyncMock(return_value={})
                    mock_exchange_instance.create_order = AsyncMock()
                    mock_exchange_instance.fetch_order = AsyncMock(return_value={'status': 'open'})
                    mock_exchange_instance.cancel_order = AsyncMock()
                    mock_exchange_instance.fetch_ticker = AsyncMock(return_value={'last': 100.0})
                    mock_exchange_instance.fetch_balance = AsyncMock(return_value={'total': {}})
                    mock_binance_ccxt.return_value = mock_exchange_instance
                                                                                                                                          
                    connector = get_exchange_connector("binance", exchange_config)
                    assert isinstance(connector, BinanceConnector)
                    mock_decrypt_keys.assert_called_once_with(mock_encrypted_data)
                    mock_binance_ccxt.assert_called_once_with({
                        'apiKey': "test_key",
                        'secret': "test_secret",
                        'options': {
                            'defaultType': 'spot', # Changed to spot
                        },
                    })
                # Test that the methods are callable (even if they do nothing yet)
                await connector.get_precision_rules()
                await connector.place_order("BTC/USDT", "limit", "buy", 0.01)
                await connector.get_order_status("123", "BTC/USDT")
                await connector.cancel_order("123", "BTC/USDT")
                await connector.get_current_price("BTC/USDT")
                await connector.fetch_balance()

@pytest.mark.asyncio
async def test_get_exchange_connector_bybit():
    """
    Test that the factory returns a BybitConnector for 'bybit' type.
    """
    mock_encrypted_data = "dummy_encrypted_data"
    exchange_config = {
        "encrypted_data": mock_encrypted_data,
        "testnet": True, # Set to True for Bybit test
        "default_type": "spot", # Changed to spot
        "account_type": "UNIFIED"
    }

    with patch('app.core.security.EncryptionService.decrypt_keys', return_value=("test_key", "test_secret")) as mock_decrypt_keys:
        with patch('ccxt.async_support.bybit') as mock_bybit_ccxt:
            mock_exchange_instance = MagicMock()
            mock_exchange_instance.load_markets = AsyncMock(return_value={})
            mock_exchange_instance.create_order = AsyncMock()
            mock_exchange_instance.fetch_order = AsyncMock(return_value={'status': 'open'})
            mock_exchange_instance.cancel_order = AsyncMock()
            mock_exchange_instance.fetch_ticker = AsyncMock(return_value={'last': 100.0})
            mock_exchange_instance.fetch_balance = AsyncMock(return_value={'total': {}})
            mock_exchange_instance.set_sandbox_mode = MagicMock() # Mock set_sandbox_mode
            mock_bybit_ccxt.return_value = mock_exchange_instance

            connector = get_exchange_connector("bybit", exchange_config)
            assert isinstance(connector, BybitConnector)
            mock_decrypt_keys.assert_called_once_with(mock_encrypted_data)
            mock_bybit_ccxt.assert_called_once_with({
                'apiKey': "test_key",
                'secret': "test_secret",
                'options': {
                    'defaultType': 'spot',
                    'accountType': 'UNIFIED',
                    'recvWindow': 20000,
                    'testnet': True
                },
                'timeout': 60000,
                'enableRateLimit': True,
                'asyncio_loop': None,
                'verbose': False,  # Changed from True to match actual implementation
            })
            mock_exchange_instance.set_sandbox_mode.assert_called_once_with(True)

            # Test that the methods are callable (even if they do nothing yet)
            await connector.get_precision_rules()
            await connector.place_order("BTC/USDT", "limit", "buy", 0.01)
            await connector.get_order_status("123", "BTC/USDT")
            await connector.cancel_order("123", "BTC/USDT")
            await connector.get_current_price("BTC/USDT")
            await connector.fetch_balance()

@pytest.mark.asyncio
async def test_get_exchange_connector_unsupported():
    """
    Test that the factory raises an error for unsupported exchange types.
    """
    mock_encrypted_data = "dummy_encrypted_data"
    exchange_config = {"encrypted_data": mock_encrypted_data}

    with patch('app.core.security.EncryptionService.decrypt_keys', return_value=("mock_key", "mock_secret")):
        with pytest.raises(UnsupportedExchangeError, match="Exchange type 'unsupported' is not supported."):
            get_exchange_connector("unsupported", exchange_config)

@pytest.fixture
def mock_exchange_connector():
    connector = AsyncMock(spec=ExchangeInterface)
    connector.get_precision_rules.return_value = {"BTC/USDT": {"amount": 3, "price": 2}}
    return connector

@pytest.mark.asyncio
async def test_precision_service_fetch_and_cache(mock_exchange_connector):
    """
    Test that PrecisionService fetches and caches rules correctly.
    """
    service = PrecisionService(mock_exchange_connector)
    rules = await service.get_precision_rules(force_fetch=True)

    mock_exchange_connector.get_precision_rules.assert_awaited_once()
    assert rules == {"BTC/USDT": {"amount": 3, "price": 2}}
    assert service._cache == rules
    assert service._last_fetched is not None

@pytest.mark.asyncio
async def test_precision_service_get_from_cache(mock_exchange_connector):
    """
    Test that PrecisionService returns rules from cache if available and not stale.
    """
    service = PrecisionService(mock_exchange_connector)
    # Manually populate cache
    service._cache = {"ETH/USDT": {"amount": 4, "price": 3}}
    service._last_fetched = datetime.utcnow()

    rules = await service.get_precision_rules()

    mock_exchange_connector.get_precision_rules.assert_not_awaited()
    assert rules == {"ETH/USDT": {"amount": 4, "price": 3}}

@pytest.mark.asyncio
async def test_precision_service_cache_stale(mock_exchange_connector):
    """
    Test that PrecisionService refetches rules if the cache is stale.
    """
    service = PrecisionService(mock_exchange_connector)
    service._cache = {"old": "rules"}
    service._last_fetched = datetime.utcnow() - timedelta(minutes=61)  # Make it stale

    rules = await service.get_precision_rules()

    mock_exchange_connector.get_precision_rules.assert_awaited_once()
    assert rules == {"BTC/USDT": {"amount": 3, "price": 2}}
    assert service._cache == rules
    assert service._last_fetched is not None

@pytest.mark.asyncio
async def test_precision_service_force_fetch(mock_exchange_connector):
    """
    Test that PrecisionService forces a refetch when force_fetch is True.
    """
    service = PrecisionService(mock_exchange_connector)
    service._cache = {"some": "cached_data"}
    service._last_fetched = datetime.utcnow()

    rules = await service.get_precision_rules(force_fetch=True)

    mock_exchange_connector.get_precision_rules.assert_awaited_once()
    assert rules == {"BTC/USDT": {"amount": 3, "price": 2}}
    assert service._cache == rules
    assert service._last_fetched is not None
