import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.exchange_abstraction.binance_connector import BinanceConnector

@pytest.fixture
def mock_ccxt_binance():
    """Fixture to mock the ccxt.binance instance."""
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker = AsyncMock(return_value={'last': 50000.0})
    return mock_exchange

@pytest.mark.asyncio
async def test_get_current_price_success(mock_ccxt_binance):
    """
    Test that get_current_price successfully retrieves the last price.
    """
    with patch('ccxt.async_support.binance', return_value=mock_ccxt_binance):
        connector = BinanceConnector(api_key="test_key", secret_key="test_secret")

        # This will call the mocked fetch_ticker
        price = await connector.get_current_price('BTC/USDT')

        # Assert that the ccxt method was called correctly
        mock_ccxt_binance.fetch_ticker.assert_awaited_once_with('BTC/USDT')

        # CRITICAL: Verify returned price matches exchange response
        assert price == 50000.0, "Price must match exchange response 'last' field"

        # CRITICAL: Verify price is the correct type for trading calculations
        assert isinstance(price, (int, float)), "Price must be numeric for calculations"

@pytest.mark.asyncio
async def test_fetch_balance_success(mock_ccxt_binance):
    """
    Test that fetch_balance successfully retrieves the total balance.
    """
    mock_balance_response = {
        'total': {
            'USDT': 1000.0,
            'BTC': 0.5
        },
        'free': {},
        'used': {}
    }
    mock_ccxt_binance.fetch_balance = AsyncMock(return_value=mock_balance_response)
    
    with patch('ccxt.async_support.binance', return_value=mock_ccxt_binance):
        connector = BinanceConnector(api_key="test_key", secret_key="test_secret")

        balance = await connector.fetch_balance()

        mock_ccxt_binance.fetch_balance.assert_awaited_once()

        # CRITICAL: Verify balance structure matches expected format
        assert balance == mock_balance_response['total'], \
            "Balance must return 'total' balance dict from exchange response"

        # CRITICAL: Verify all expected currencies are present
        assert 'USDT' in balance, "USDT balance must be present"
        assert 'BTC' in balance, "BTC balance must be present"

        # CRITICAL: Verify balance values are numeric for calculations
        assert balance['USDT'] == 1000.0, "USDT balance must match exchange response"
        assert balance['BTC'] == 0.5, "BTC balance must match exchange response"


@pytest.mark.asyncio
async def test_get_precision_rules_success(mock_ccxt_binance):
    """
    Test that get_precision_rules successfully retrieves market precision rules.
    """
    mock_markets_response = {
        'BTC/USDT': {
            'precision': {
                'amount': 8,
                'price': 2
            },
            'limits': {
                'amount': {'min': 0.00001},
                'cost': {'min': 5.0}
            }
        },
        'ETH/USDT': {
            'precision': {
                'amount': 6,
                'price': 2
            },
            'limits': {
                'amount': {'min': 0.0001},
                'cost': {'min': 5.0}
            }
        }
    }
    mock_ccxt_binance.load_markets = AsyncMock(return_value=mock_markets_response)

    # Mock the cache to return None (cache miss) so load_markets is called
    mock_cache = AsyncMock()
    mock_cache.get_precision_rules = AsyncMock(return_value=None)
    mock_cache.set_precision_rules = AsyncMock()

    with patch('ccxt.async_support.binance', return_value=mock_ccxt_binance), \
         patch('app.services.exchange_abstraction.binance_connector.get_cache', AsyncMock(return_value=mock_cache)):
        connector = BinanceConnector(api_key="test_key", secret_key="test_secret")

        rules = await connector.get_precision_rules()

        mock_ccxt_binance.load_markets.assert_awaited_once()

        expected_rules = {
            'BTC/USDT': {
                'tick_size': 0.01,
                'step_size': 1e-08,
                'min_qty': 1e-05,
                'min_notional': 5.0
            },
            'ETH/USDT': {
                'tick_size': 0.01,
                'step_size': 1e-06,
                'min_qty': 0.0001,
                'min_notional': 5.0
            }
        }
        # We expect keys for both symbol name and ID if they differ, but here they might overlap or be just one.
        # The connector logic adds both 'symbol' and 'id' keys.
        # In the mock, 'BTC/USDT' is the key. If 'id' is missing in the mock market value, it only adds the key.
        # Let's verify the values for the known keys.
        assert rules['BTC/USDT'] == expected_rules['BTC/USDT']
        assert rules['ETH/USDT'] == expected_rules['ETH/USDT']

        # CRITICAL: Verify precision rules structure contains required fields
        for symbol in ['BTC/USDT', 'ETH/USDT']:
            assert 'tick_size' in rules[symbol], f"{symbol} must have tick_size"
            assert 'step_size' in rules[symbol], f"{symbol} must have step_size"
            assert 'min_qty' in rules[symbol], f"{symbol} must have min_qty"
            assert 'min_notional' in rules[symbol], f"{symbol} must have min_notional"

        # CRITICAL: Verify cache was updated with rules
        mock_cache.set_precision_rules.assert_called_once()


@pytest.mark.asyncio
async def test_place_order_success(mock_ccxt_binance):
    """
    Test that place_order successfully creates an order.
    """
    mock_order_response = {
        'id': '12345',
        'symbol': 'BTC/USDT',
        'type': 'limit',
        'side': 'buy',
        'amount': 0.1,
        'price': 50000.0,
        'status': 'open'
    }
    mock_ccxt_binance.create_order = AsyncMock(return_value=mock_order_response)
    
    with patch('ccxt.async_support.binance', return_value=mock_ccxt_binance):
        connector = BinanceConnector(api_key="test_key", secret_key="test_secret")
        
        order = await connector.place_order(
            symbol='BTC/USDT',
            order_type='limit',
            side='buy',
            quantity=0.1,
            price=50000.0
        )
        
        mock_ccxt_binance.create_order.assert_awaited_once_with(
            symbol='BTC/USDT',
            type='limit',
            side='buy',
            amount=0.1,
            price=50000.0,
            params={'newOrderRespType': 'FULL'}
        )
        assert order == mock_order_response

        # CRITICAL: Verify order response contains required fields for tracking
        assert 'id' in order, "Order response must contain order ID"
        assert 'status' in order, "Order response must contain status"
        assert 'symbol' in order, "Order response must contain symbol"

        # CRITICAL: Verify order details match request
        assert order['symbol'] == 'BTC/USDT', "Order symbol must match request"
        assert order['side'] == 'buy', "Order side must match request"
        assert order['amount'] == 0.1, "Order amount must match request"
        assert order['price'] == 50000.0, "Order price must match request"


@pytest.mark.asyncio
async def test_get_order_status_success(mock_ccxt_binance):
    """
    Test that get_order_status successfully retrieves the status of an order.
    """
    mock_order_response = {'id': '12345', 'status': 'closed'}
    mock_ccxt_binance.fetch_order = AsyncMock(return_value=mock_order_response)
    
    with patch('ccxt.async_support.binance', return_value=mock_ccxt_binance):
        connector = BinanceConnector(api_key="test_key", secret_key="test_secret")

        status = await connector.get_order_status(order_id='12345', symbol='BTC/USDT')

        mock_ccxt_binance.fetch_order.assert_awaited_once_with('12345', 'BTC/USDT')
        assert status == mock_order_response  # The connector returns the full response, not just the status string

        # CRITICAL: Verify order status response contains required fields
        assert 'id' in status, "Order status response must contain order ID"
        assert 'status' in status, "Order status response must contain status"

        # CRITICAL: Verify order ID matches request
        assert status['id'] == '12345', "Order ID in response must match requested order"

        # CRITICAL: Verify status is a valid order state
        assert status['status'] == 'closed', "Order status must reflect exchange state"


@pytest.mark.asyncio
async def test_cancel_order_success(mock_ccxt_binance):
    """
    Test that cancel_order successfully cancels an order.
    """
    mock_cancel_response = {'id': '12345', 'status': 'canceled'}
    mock_ccxt_binance.cancel_order = AsyncMock(return_value=mock_cancel_response)
    
    with patch('ccxt.async_support.binance', return_value=mock_ccxt_binance):
        connector = BinanceConnector(api_key="test_key", secret_key="test_secret")

        response = await connector.cancel_order(order_id='12345', symbol='BTC/USDT')

        mock_ccxt_binance.cancel_order.assert_awaited_once_with('12345', 'BTC/USDT')
        assert response == mock_cancel_response

        # CRITICAL: Verify cancel response contains required fields
        assert 'id' in response, "Cancel response must contain order ID"
        assert 'status' in response, "Cancel response must contain status"

        # CRITICAL: Verify order ID matches request
        assert response['id'] == '12345', "Order ID in cancel response must match requested order"

        # CRITICAL: Verify status is 'canceled' after cancel operation
        assert response['status'] == 'canceled', \
            "Order status must be 'canceled' after successful cancel (catches status update bug)"
