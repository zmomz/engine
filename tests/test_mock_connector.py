import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from app.services.exchange_abstraction.mock_connector import MockConnector
from app.exceptions import APIError, ExchangeConnectionError

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    return client

@pytest.fixture
def connector(mock_client):
    with patch("httpx.AsyncClient", return_value=mock_client):
        yield MockConnector()

@pytest.mark.asyncio
async def test_get_precision_rules(connector, mock_client):
    resp = MagicMock()
    resp.status_code = 200
    mock_client.get.return_value = resp
    
    rules = await connector.get_precision_rules()
    assert "BTCUSDT" in rules
    assert rules["BTCUSDT"]["min_notional"] == 10.0

@pytest.mark.asyncio
async def test_get_precision_rules_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Connection failed")
    with pytest.raises(ExchangeConnectionError):
        await connector.get_precision_rules()

@pytest.mark.asyncio
async def test_place_order(connector, mock_client):
    resp = MagicMock()
    resp.json.return_value = {
        "id": "1", "symbol": "BTCUSDT", "side": "buy", "type": "market",
        "quantity": 1.0, "price": 50000.0, "status": "open"
    }
    mock_client.post.return_value = resp
    
    order = await connector.place_order("BTCUSDT", "buy", "market", Decimal("1.0"))
    assert order["id"] == "1"
    assert order["status"] == "open"

@pytest.mark.asyncio
async def test_place_order_error(connector, mock_client):
    mock_client.post.side_effect = Exception("API Error")
    with pytest.raises(APIError):
        await connector.place_order("BTCUSDT", "buy", "market", Decimal("1.0"))

@pytest.mark.asyncio
async def test_get_order_status(connector, mock_client):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"id": "1", "status": "filled", "quantity": 1.0, "price": 50000.0}
    mock_client.get.return_value = resp
    
    status = await connector.get_order_status("1")
    assert status["status"] == "filled"
    assert status["filled"] == 1.0

@pytest.mark.asyncio
async def test_get_order_status_404(connector, mock_client):
    resp = MagicMock()
    resp.status_code = 404
    mock_client.get.return_value = resp
    
    status = await connector.get_order_status("1")
    assert status["status"] == "canceled"

@pytest.mark.asyncio
async def test_get_order_status_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.get_order_status("1")

@pytest.mark.asyncio
async def test_cancel_order(connector, mock_client):
    resp = MagicMock()
    resp.status_code = 200
    mock_client.delete.return_value = resp
    
    res = await connector.cancel_order("1")
    assert res["status"] == "canceled"

@pytest.mark.asyncio
async def test_cancel_order_404(connector, mock_client):
    resp = MagicMock()
    resp.status_code = 404
    mock_client.delete.return_value = resp
    
    res = await connector.cancel_order("1")
    assert res["status"] == "canceled"

@pytest.mark.asyncio
async def test_cancel_order_error(connector, mock_client):
    mock_client.delete.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.cancel_order("1")

@pytest.mark.asyncio
async def test_get_current_price(connector, mock_client):
    resp = MagicMock()
    resp.json.return_value = {"price": 50000.0}
    mock_client.get.return_value = resp
    
    price = await connector.get_current_price("BTCUSDT")
    assert price == Decimal("50000.0")

@pytest.mark.asyncio
async def test_get_current_price_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.get_current_price("BTCUSDT")

@pytest.mark.asyncio
async def test_fetch_balance(connector, mock_client):
    resp = MagicMock()
    resp.json.return_value = {
        "USDT": {"free": 1000.0, "used": 0.0, "total": 1000.0}
    }
    mock_client.get.return_value = resp
    
    balance = await connector.fetch_balance()
    # Expect flat total
    assert balance["USDT"] == Decimal("1000.0")

@pytest.mark.asyncio
async def test_fetch_balance_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.fetch_balance()