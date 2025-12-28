import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from app.services.exchange_abstraction.mock_connector import MockConnector
from app.exceptions import APIError, ExchangeConnectionError


def create_mock_response(status_code=200, json_data=None):
    """Helper to create a properly configured mock response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        resp.raise_for_status.side_effect = HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock(status_code=status_code)
        )
    return resp


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
    resp = create_mock_response(200, {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "9000"},
                    {"filterType": "MIN_NOTIONAL", "notional": "10"}
                ]
            }
        ]
    })
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
    resp = create_mock_response(200, {
        "orderId": "1",
        "clientOrderId": "client1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "origQty": "1.0",
        "price": "50000.0",
        "avgPrice": "50000.0",
        "status": "NEW",
        "executedQty": "0"
    })
    mock_client.post.return_value = resp

    order = await connector.place_order("BTCUSDT", "buy", "market", Decimal("1.0"))
    assert order["id"] == "1"
    assert order["status"] == "new"


@pytest.mark.asyncio
async def test_place_order_error(connector, mock_client):
    mock_client.post.side_effect = Exception("API Error")
    with pytest.raises(APIError):
        await connector.place_order("BTCUSDT", "buy", "market", Decimal("1.0"))


@pytest.mark.asyncio
async def test_get_order_status(connector, mock_client):
    resp = create_mock_response(200, {
        "orderId": "1",
        "status": "FILLED",
        "executedQty": "1.0",
        "origQty": "1.0",
        "price": "50000.0",
        "avgPrice": "50000.0"
    })
    mock_client.get.return_value = resp

    status = await connector.get_order_status("1")
    assert status["status"] == "filled"
    assert status["filled"] == 1.0


@pytest.mark.asyncio
async def test_get_order_status_404(connector, mock_client):
    # Mock exchange returns 400 with code -2013 for order not found
    resp = create_mock_response(400, {"detail": {"code": -2013, "msg": "Order not found"}})
    # Override raise_for_status since we handle 400 specially
    resp.raise_for_status = MagicMock()
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
    resp = create_mock_response(200, {"orderId": "1", "status": "CANCELED"})
    mock_client.delete.return_value = resp

    res = await connector.cancel_order("1")
    assert res["status"] == "canceled"


@pytest.mark.asyncio
async def test_cancel_order_404(connector, mock_client):
    resp = create_mock_response(400, {"detail": "Order not found"})
    # cancel_order handles 400 gracefully, so override raise_for_status
    resp.raise_for_status = MagicMock()
    mock_client.delete.return_value = resp

    res = await connector.cancel_order("1")
    assert res["status"] == "canceled"


@pytest.mark.asyncio
async def test_cancel_order_error(connector, mock_client):
    # cancel_order catches all exceptions and returns canceled status
    mock_client.delete.side_effect = Exception("Error")

    res = await connector.cancel_order("1")
    # cancel_order gracefully handles errors and returns canceled
    assert res["status"] == "canceled"


@pytest.mark.asyncio
async def test_get_current_price(connector, mock_client):
    resp = create_mock_response(200, {"price": "50000.0"})
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
    # fetch_balance expects array format from /fapi/v2/balance
    resp = create_mock_response(200, [
        {"asset": "USDT", "balance": "1000.0", "availableBalance": "1000.0"}
    ])
    mock_client.get.return_value = resp

    balance = await connector.fetch_balance()
    assert balance["USDT"] == Decimal("1000.0")


@pytest.mark.asyncio
async def test_fetch_balance_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.fetch_balance()