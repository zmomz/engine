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
        
        # Assert that the method returned the correct price
        assert price == 50000.0

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
        assert balance == mock_balance_response['total']

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
            }
        },
        'ETH/USDT': {
            'precision': {
                'amount': 6,
                'price': 2
            }
        }
    }
    mock_ccxt_binance.load_markets = AsyncMock(return_value=mock_markets_response)
    
    with patch('ccxt.async_support.binance', return_value=mock_ccxt_binance):
        connector = BinanceConnector(api_key="test_key", secret_key="test_secret")
        
        rules = await connector.get_precision_rules()
        
        mock_ccxt_binance.load_markets.assert_awaited_once()
        assert rules == mock_markets_response

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
            amount=0.1,
            price=50000.0
        )
        
        mock_ccxt_binance.create_order.assert_awaited_once_with(
            symbol='BTC/USDT',
            type='limit',
            side='buy',
            amount=0.1,
            price=50000.0
        )
        assert order == mock_order_response

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
        assert status == 'closed'

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
