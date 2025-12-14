"""
Comprehensive tests for BybitConnector.
Tests all exchange operations with mocked ccxt.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import ccxt.async_support as ccxt

from app.services.exchange_abstraction.bybit_connector import BybitConnector, OrderCancellationError


class TestBybitConnectorInit:
    """Tests for BybitConnector initialization."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        with patch.object(ccxt, 'bybit') as mock_bybit_class:
            mock_exchange = MagicMock()
            mock_exchange.options = {'testnet': False, 'defaultType': 'spot'}
            mock_exchange.urls = {'api': 'https://api.bybit.com'}
            mock_bybit_class.return_value = mock_exchange

            connector = BybitConnector(
                api_key="test_api_key",
                secret_key="test_secret_key"
            )

            assert connector.testnet_mode is False
            mock_bybit_class.assert_called_once()

    def test_init_testnet_mode(self):
        """Test initialization with testnet enabled."""
        with patch.object(ccxt, 'bybit') as mock_bybit_class:
            mock_exchange = MagicMock()
            mock_exchange.options = {'testnet': True, 'defaultType': 'spot'}
            mock_exchange.urls = {'api': 'https://api-testnet.bybit.com'}
            mock_bybit_class.return_value = mock_exchange

            connector = BybitConnector(
                api_key="test_api_key",
                secret_key="test_secret_key",
                testnet=True
            )

            assert connector.testnet_mode is True
            mock_exchange.set_sandbox_mode.assert_called_once_with(True)

    def test_init_custom_account_type(self):
        """Test initialization with custom account type."""
        with patch.object(ccxt, 'bybit') as mock_bybit_class:
            mock_exchange = MagicMock()
            mock_exchange.options = {'accountType': 'CONTRACT', 'defaultType': 'future'}
            mock_exchange.urls = {'api': 'https://api.bybit.com'}
            mock_bybit_class.return_value = mock_exchange

            connector = BybitConnector(
                api_key="test_api_key",
                secret_key="test_secret_key",
                default_type="future",
                account_type="CONTRACT"
            )

            assert connector.exchange is not None


@pytest.fixture
def mock_bybit_connector():
    """Fixture to create a BybitConnector with mocked exchange."""
    with patch.object(ccxt, 'bybit') as mock_bybit_class:
        mock_exchange = MagicMock()
        mock_exchange.options = {'testnet': False, 'defaultType': 'spot', 'accountType': 'UNIFIED'}
        mock_exchange.urls = {'api': 'https://api.bybit.com'}
        mock_bybit_class.return_value = mock_exchange

        connector = BybitConnector(
            api_key="test_api_key",
            secret_key="test_secret_key"
        )

        # Make exchange methods async
        mock_exchange.load_markets = AsyncMock()
        mock_exchange.create_order = AsyncMock()
        mock_exchange.fetch_order = AsyncMock()
        mock_exchange.cancel_order = AsyncMock()
        mock_exchange.fetch_ticker = AsyncMock()
        mock_exchange.fetch_tickers = AsyncMock()
        mock_exchange.fetch_balance = AsyncMock()
        mock_exchange.fetch_open_orders = AsyncMock()
        mock_exchange.fetch_my_trades = AsyncMock()
        mock_exchange.fetch_orders = AsyncMock()
        mock_exchange.cancelAllOrders = AsyncMock()
        mock_exchange.close = AsyncMock()

        yield connector


class TestGetPrecisionRules:
    """Tests for get_precision_rules method."""

    @pytest.mark.asyncio
    async def test_get_precision_rules_success(self, mock_bybit_connector):
        """Test successful retrieval of precision rules."""
        mock_markets = {
            'BTC/USDT': {
                'id': 'BTCUSDT',
                'precision': {'price': 2, 'amount': 6},
                'limits': {
                    'amount': {'min': 0.0001},
                    'cost': {'min': 10.0}
                }
            },
            'ETH/USDT': {
                'id': 'ETHUSDT',
                'precision': {'price': 0.01, 'amount': 0.001},
                'limits': {
                    'amount': {'min': 0.001},
                    'cost': {'min': 5.0}
                }
            }
        }
        mock_bybit_connector.exchange.load_markets.return_value = mock_markets

        rules = await mock_bybit_connector.get_precision_rules()

        assert 'BTC/USDT' in rules
        assert 'BTCUSDT' in rules  # ID should also be a key
        assert rules['BTC/USDT']['tick_size'] == 0.01  # 1 / 10^2
        assert rules['BTC/USDT']['step_size'] == 0.000001  # 1 / 10^6
        assert rules['BTC/USDT']['min_qty'] == 0.0001
        assert rules['BTC/USDT']['min_notional'] == 10.0

    @pytest.mark.asyncio
    async def test_get_precision_rules_float_precision(self, mock_bybit_connector):
        """Test precision rules with float precision values."""
        mock_markets = {
            'DOGE/USDT': {
                'id': 'DOGEUSDT',
                'precision': {'price': 0.0001, 'amount': 1.0},
                'limits': {}
            }
        }
        mock_bybit_connector.exchange.load_markets.return_value = mock_markets

        rules = await mock_bybit_connector.get_precision_rules()

        assert rules['DOGE/USDT']['tick_size'] == 0.0001
        assert rules['DOGE/USDT']['step_size'] == 1.0
        # Defaults when limits not provided
        assert rules['DOGE/USDT']['min_qty'] == 0.001
        assert rules['DOGE/USDT']['min_notional'] == 5.0


class TestPlaceOrder:
    """Tests for place_order method."""

    @pytest.mark.asyncio
    async def test_place_order_success(self, mock_bybit_connector):
        """Test successful order placement."""
        mock_bybit_connector.exchange.create_order.return_value = {
            'id': 'composite-123',
            'info': {'orderId': '123456789'},
            'status': 'open'
        }

        result = await mock_bybit_connector.place_order(
            symbol='BTC/USDT',
            order_type='limit',
            side='buy',
            quantity=0.01,
            price=50000.0
        )

        assert result['id'] == '123456789'  # Native Bybit ID
        mock_bybit_connector.exchange.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_order_with_reduce_only(self, mock_bybit_connector):
        """Test order placement with reduce_only parameter."""
        mock_bybit_connector.exchange.create_order.return_value = {
            'id': 'order-123',
            'info': {'orderId': '123456789'},
            'status': 'open'
        }

        await mock_bybit_connector.place_order(
            symbol='BTC/USDT',
            order_type='market',
            side='sell',
            quantity=0.01,
            reduce_only=True
        )

        call_args = mock_bybit_connector.exchange.create_order.call_args
        assert call_args.kwargs['params']['reduceOnly'] is True

    @pytest.mark.asyncio
    async def test_place_order_fallback_to_contract(self, mock_bybit_connector):
        """Test fallback to CONTRACT account type on error."""
        # First call fails with error 10005 (UNIFIED account issue)
        mock_bybit_connector.exchange.create_order.side_effect = [
            ccxt.ExchangeError("10005: Invalid permissions"),
            {'id': 'contract-order', 'info': {'orderId': '987654321'}, 'status': 'open'}
        ]

        result = await mock_bybit_connector.place_order(
            symbol='BTC/USDT',
            order_type='limit',
            side='buy',
            quantity=0.01,
            price=50000.0
        )

        assert result['id'] == '987654321'
        assert mock_bybit_connector.exchange.create_order.call_count == 2

    @pytest.mark.asyncio
    async def test_place_order_fallback_to_spot(self, mock_bybit_connector):
        """Test fallback to SPOT account type when CONTRACT also fails."""
        # First call fails (UNIFIED), second fails (CONTRACT), third succeeds (SPOT)
        mock_bybit_connector.exchange.create_order.side_effect = [
            ccxt.ExchangeError("10005: Invalid permissions"),
            Exception("CONTRACT failed"),
            {'id': 'spot-order', 'info': {'orderId': '111222333'}, 'status': 'open'}
        ]

        result = await mock_bybit_connector.place_order(
            symbol='BTC/USDT',
            order_type='limit',
            side='buy',
            quantity=0.01,
            price=50000.0
        )

        assert result['id'] == '111222333'
        assert mock_bybit_connector.exchange.create_order.call_count == 3

    @pytest.mark.asyncio
    async def test_place_order_all_fallbacks_fail(self, mock_bybit_connector):
        """Test exception when all fallbacks fail."""
        mock_bybit_connector.exchange.create_order.side_effect = [
            ccxt.ExchangeError("10005: Invalid permissions"),
            Exception("CONTRACT failed"),
            Exception("SPOT failed too")
        ]

        with pytest.raises(Exception, match="SPOT failed too"):
            await mock_bybit_connector.place_order(
                symbol='BTC/USDT',
                order_type='limit',
                side='buy',
                quantity=0.01,
                price=50000.0
            )


class TestGetOrderStatus:
    """Tests for get_order_status method."""

    @pytest.mark.asyncio
    async def test_get_order_status_success(self, mock_bybit_connector):
        """Test successful order status retrieval."""
        mock_bybit_connector.exchange.fetch_order.return_value = {
            'id': '123456',
            'status': 'open',
            'filled': 0.005
        }

        result = await mock_bybit_connector.get_order_status('123456', 'BTC/USDT')

        assert result['status'] == 'open'
        assert result['filled'] == 0.005

    @pytest.mark.asyncio
    async def test_get_order_status_retry_with_trigger(self, mock_bybit_connector):
        """Test retry with trigger param for conditional orders."""
        mock_bybit_connector.exchange.fetch_order.side_effect = [
            ccxt.OrderNotFound("Order not found"),
            {'id': '123456', 'status': 'triggered'}
        ]

        result = await mock_bybit_connector.get_order_status('123456', 'BTC/USDT')

        assert result['status'] == 'triggered'
        assert mock_bybit_connector.exchange.fetch_order.call_count == 2

    @pytest.mark.asyncio
    async def test_get_order_status_fallback_to_spot(self, mock_bybit_connector):
        """Test fallback to SPOT account type."""
        mock_bybit_connector.exchange.fetch_order.side_effect = [
            ccxt.OrderNotFound("Not found"),
            Exception("Trigger retry failed"),
            {'id': '123456', 'status': 'closed'}  # SPOT fallback
        ]

        result = await mock_bybit_connector.get_order_status('123456', 'BTC/USDT')

        assert result['status'] == 'closed'

    @pytest.mark.asyncio
    async def test_get_order_status_found_in_fetch_orders(self, mock_bybit_connector):
        """Test finding order via fetch_orders fallback."""
        mock_bybit_connector.exchange.fetch_order.side_effect = [
            ccxt.OrderNotFound("Not found"),
            Exception("Trigger failed"),
            ccxt.OrderNotFound("SPOT failed"),
            ccxt.OrderNotFound("CONTRACT failed")
        ]
        mock_bybit_connector.exchange.fetch_my_trades.return_value = []
        mock_bybit_connector.exchange.fetch_orders.return_value = [
            {'id': '999', 'status': 'open'},
            {'id': '123456', 'status': 'filled', 'info': {'orderId': '123456'}},
        ]

        result = await mock_bybit_connector.get_order_status('123456', 'BTC/USDT')

        assert result['id'] == '123456'
        assert result['status'] == 'filled'


class TestCancelOrder:
    """Tests for cancel_order method."""

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, mock_bybit_connector):
        """Test successful order cancellation."""
        mock_bybit_connector.exchange.cancel_order.return_value = {
            'id': '123456',
            'status': 'canceled'
        }

        result = await mock_bybit_connector.cancel_order('123456', 'BTC/USDT')

        assert result['status'] == 'canceled'

    @pytest.mark.asyncio
    async def test_cancel_order_already_cancelled(self, mock_bybit_connector):
        """Test cancellation of already cancelled order."""
        mock_bybit_connector.exchange.cancel_order.side_effect = ccxt.OrderNotFound("Order not found")
        mock_bybit_connector.exchange.fetch_order.return_value = {
            'id': '123456',
            'status': 'canceled'
        }

        result = await mock_bybit_connector.cancel_order('123456', 'BTC/USDT')

        assert result['status'] == 'canceled'

    @pytest.mark.asyncio
    async def test_cancel_order_already_filled(self, mock_bybit_connector):
        """Test cancellation of already filled order."""
        mock_bybit_connector.exchange.cancel_order.side_effect = ccxt.OrderNotFound("Order not found")
        mock_bybit_connector.exchange.fetch_order.return_value = {
            'id': '123456',
            'status': 'filled'
        }

        result = await mock_bybit_connector.cancel_order('123456', 'BTC/USDT')

        assert result['status'] == 'filled'

    @pytest.mark.asyncio
    async def test_cancel_order_returns_order_status_if_closed(self, mock_bybit_connector):
        """Test that cancel_order returns order status if order is already closed."""
        # Cancel fails on first try
        mock_bybit_connector.exchange.cancel_order.side_effect = ccxt.OrderNotFound("Order not found")
        # But get_order_status shows it's already filled
        mock_bybit_connector.exchange.fetch_order.return_value = {
            'id': '123456',
            'status': 'closed'
        }

        result = await mock_bybit_connector.cancel_order('123456', 'BTC/USDT')

        assert result['status'] == 'closed'


class TestGetCurrentPrice:
    """Tests for get_current_price method."""

    @pytest.mark.asyncio
    async def test_get_current_price_success(self, mock_bybit_connector):
        """Test successful price retrieval."""
        mock_bybit_connector.exchange.fetch_ticker.return_value = {
            'symbol': 'BTC/USDT',
            'last': 50123.45
        }

        price = await mock_bybit_connector.get_current_price('BTC/USDT')

        assert price == 50123.45


class TestGetAllTickers:
    """Tests for get_all_tickers method."""

    @pytest.mark.asyncio
    async def test_get_all_tickers_success(self, mock_bybit_connector):
        """Test successful retrieval of all tickers."""
        mock_tickers = {
            'BTC/USDT': {'last': 50000.0},
            'ETH/USDT': {'last': 3000.0}
        }
        mock_bybit_connector.exchange.fetch_tickers.return_value = mock_tickers

        tickers = await mock_bybit_connector.get_all_tickers()

        assert tickers == mock_tickers


class TestFetchBalance:
    """Tests for fetch_balance method."""

    @pytest.mark.asyncio
    async def test_fetch_balance_success(self, mock_bybit_connector):
        """Test successful balance retrieval."""
        mock_bybit_connector.exchange.fetch_balance.return_value = {
            'total': {'USDT': 10000.0, 'BTC': 0.5},
            'free': {'USDT': 9000.0, 'BTC': 0.4}
        }

        balance = await mock_bybit_connector.fetch_balance()

        assert balance['USDT'] == 10000.0
        assert balance['BTC'] == 0.5

    @pytest.mark.asyncio
    async def test_fetch_balance_fallback_to_spot(self, mock_bybit_connector):
        """Test fallback to SPOT account type."""
        mock_bybit_connector.exchange.fetch_balance.side_effect = [
            ccxt.ExchangeError("UNIFIED failed"),
            {'total': {'USDT': 5000.0}, 'free': {'USDT': 4000.0}}
        ]

        balance = await mock_bybit_connector.fetch_balance()

        assert balance['USDT'] == 5000.0


class TestFetchFreeBalance:
    """Tests for fetch_free_balance method."""

    @pytest.mark.asyncio
    async def test_fetch_free_balance_success(self, mock_bybit_connector):
        """Test successful free balance retrieval."""
        mock_bybit_connector.exchange.fetch_balance.return_value = {
            'total': {'USDT': 10000.0},
            'free': {'USDT': 8000.0, 'BTC': 0.3}
        }

        free_balance = await mock_bybit_connector.fetch_free_balance()

        assert free_balance['USDT'] == 8000.0
        assert free_balance['BTC'] == 0.3

    @pytest.mark.asyncio
    async def test_fetch_free_balance_fallback_to_contract(self, mock_bybit_connector):
        """Test fallback to CONTRACT account type."""
        mock_bybit_connector.exchange.fetch_balance.side_effect = [
            ccxt.ExchangeError("UNIFIED failed"),
            ccxt.ExchangeError("SPOT failed"),
            {'total': {'USDT': 5000.0}, 'free': {'USDT': 4500.0}}
        ]

        free_balance = await mock_bybit_connector.fetch_free_balance()

        assert free_balance['USDT'] == 4500.0


class TestFetchOpenOrders:
    """Tests for fetch_open_orders method."""

    @pytest.mark.asyncio
    async def test_fetch_open_orders_success(self, mock_bybit_connector):
        """Test successful retrieval of open orders."""
        mock_orders = [
            {'id': '1', 'symbol': 'BTC/USDT', 'status': 'open'},
            {'id': '2', 'symbol': 'BTC/USDT', 'status': 'open'}
        ]
        mock_bybit_connector.exchange.fetch_open_orders.return_value = mock_orders

        orders = await mock_bybit_connector.fetch_open_orders('BTC/USDT')

        assert len(orders) == 2

    @pytest.mark.asyncio
    async def test_fetch_open_orders_fallback(self, mock_bybit_connector):
        """Test fallback for open orders retrieval."""
        mock_bybit_connector.exchange.fetch_open_orders.side_effect = [
            ccxt.ExchangeError("UNIFIED failed"),
            [{'id': '1', 'status': 'open'}]
        ]

        orders = await mock_bybit_connector.fetch_open_orders('BTC/USDT')

        assert len(orders) == 1


class TestCancelAllOpenOrders:
    """Tests for cancel_all_open_orders method."""

    @pytest.mark.asyncio
    async def test_cancel_all_open_orders_with_symbol(self, mock_bybit_connector):
        """Test cancelling all orders for a specific symbol."""
        mock_bybit_connector.exchange.cancelAllOrders.return_value = [
            {'id': '1', 'status': 'canceled'},
            {'id': '2', 'status': 'canceled'}
        ]

        result = await mock_bybit_connector.cancel_all_open_orders('BTC/USDT')

        assert len(result) == 2
        mock_bybit_connector.exchange.cancelAllOrders.assert_called_once_with('BTC/USDT')

    @pytest.mark.asyncio
    async def test_cancel_all_open_orders_without_symbol(self, mock_bybit_connector):
        """Test cancelling all orders without symbol (iterates over open orders)."""
        mock_bybit_connector.exchange.fetch_open_orders.return_value = [
            {'id': '1', 'symbol': 'BTC/USDT'},
            {'id': '2', 'symbol': 'ETH/USDT'}
        ]
        mock_bybit_connector.exchange.cancel_order.side_effect = [
            {'id': '1', 'status': 'canceled'},
            {'id': '2', 'status': 'canceled'}
        ]

        result = await mock_bybit_connector.cancel_all_open_orders()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_cancel_all_open_orders_fallback(self, mock_bybit_connector):
        """Test fallback for cancel all orders."""
        mock_bybit_connector.exchange.cancelAllOrders.side_effect = [
            ccxt.ExchangeError("UNIFIED failed"),
            [{'id': '1', 'status': 'canceled'}]
        ]

        result = await mock_bybit_connector.cancel_all_open_orders('BTC/USDT')

        assert len(result) == 1


class TestClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close_connector(self, mock_bybit_connector):
        """Test closing the exchange connection."""
        await mock_bybit_connector.close()

        mock_bybit_connector.exchange.close.assert_called_once()
