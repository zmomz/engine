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


@pytest.mark.asyncio
async def test_get_all_tickers(connector, mock_client):
    resp = create_mock_response(200, [
        {"symbol": "BTCUSDT", "price": "50000.0"},
        {"symbol": "ETHUSDT", "price": "3000.0"}
    ])
    mock_client.get.return_value = resp

    tickers = await connector.get_all_tickers()
    assert "BTC/USDT" in tickers
    assert tickers["BTC/USDT"]["last"] == 50000.0
    assert tickers["ETH/USDT"]["last"] == 3000.0


@pytest.mark.asyncio
async def test_get_all_tickers_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.get_all_tickers()


@pytest.mark.asyncio
async def test_fetch_free_balance(connector, mock_client):
    resp = create_mock_response(200, [
        {"asset": "USDT", "balance": "1000.0", "availableBalance": "800.0"}
    ])
    mock_client.get.return_value = resp

    balance = await connector.fetch_free_balance()
    assert balance["USDT"] == Decimal("800.0")


@pytest.mark.asyncio
async def test_fetch_free_balance_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.fetch_free_balance()


@pytest.mark.asyncio
async def test_get_open_orders(connector, mock_client):
    resp = create_mock_response(200, [
        {
            "orderId": "123",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "price": "50000.0",
            "origQty": "1.0",
            "executedQty": "0.0",
            "status": "NEW"
        }
    ])
    mock_client.get.return_value = resp

    orders = await connector.get_open_orders("BTCUSDT")
    assert len(orders) == 1
    assert orders[0]["id"] == "123"
    assert orders[0]["side"] == "buy"
    assert orders[0]["status"] == "new"


@pytest.mark.asyncio
async def test_get_open_orders_no_symbol(connector, mock_client):
    resp = create_mock_response(200, [
        {"orderId": "1", "symbol": "BTCUSDT", "side": "BUY", "type": "MARKET",
         "price": "50000.0", "origQty": "1.0", "executedQty": "0.0", "status": "NEW"},
        {"orderId": "2", "symbol": "ETHUSDT", "side": "SELL", "type": "LIMIT",
         "price": "3000.0", "origQty": "2.0", "executedQty": "1.0", "status": "PARTIALLY_FILLED"}
    ])
    mock_client.get.return_value = resp

    orders = await connector.get_open_orders()
    assert len(orders) == 2
    assert orders[1]["filled"] == 1.0


@pytest.mark.asyncio
async def test_get_open_orders_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.get_open_orders()


@pytest.mark.asyncio
async def test_get_positions(connector, mock_client):
    resp = create_mock_response(200, [
        {
            "symbol": "BTCUSDT",
            "positionAmt": "1.0",
            "entryPrice": "50000.0",
            "markPrice": "51000.0",
            "unRealizedProfit": "1000.0",
            "leverage": "10"
        },
        {
            "symbol": "ETHUSDT",
            "positionAmt": "0",  # No position
            "entryPrice": "0",
            "markPrice": "3000.0",
            "unRealizedProfit": "0",
            "leverage": "10"
        }
    ])
    mock_client.get.return_value = resp

    positions = await connector.get_positions()
    # Only non-zero positions should be returned
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTCUSDT"
    assert positions[0]["side"] == "long"
    assert positions[0]["quantity"] == 1.0


@pytest.mark.asyncio
async def test_get_positions_short(connector, mock_client):
    resp = create_mock_response(200, [
        {
            "symbol": "BTCUSDT",
            "positionAmt": "-2.0",  # Short position
            "entryPrice": "50000.0",
            "markPrice": "49000.0",
            "unRealizedProfit": "2000.0",
            "leverage": "5"
        }
    ])
    mock_client.get.return_value = resp

    positions = await connector.get_positions("BTCUSDT")
    assert len(positions) == 1
    assert positions[0]["side"] == "short"
    assert positions[0]["quantity"] == 2.0


@pytest.mark.asyncio
async def test_get_positions_error(connector, mock_client):
    mock_client.get.side_effect = Exception("Error")
    with pytest.raises(APIError):
        await connector.get_positions()


@pytest.mark.asyncio
async def test_close(connector, mock_client):
    # First make a request to create the client
    resp = create_mock_response(200, {"price": "50000.0"})
    mock_client.get.return_value = resp
    await connector.get_current_price("BTCUSDT")

    # Client should exist
    assert connector._client is not None

    # Close should clean up
    await connector.close()
    assert connector._client is None


@pytest.mark.asyncio
async def test_close_no_client(connector):
    # Close when no client exists should not error
    connector._client = None
    await connector.close()
    assert connector._client is None


@pytest.mark.asyncio
async def test_precision_rules_cache_hit(connector, mock_client):
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

    # First call populates cache
    rules1 = await connector.get_precision_rules()
    assert "BTCUSDT" in rules1

    # Second call should use cache (mock_client.get called only once)
    rules2 = await connector.get_precision_rules()
    assert rules2 == rules1
    mock_client.get.assert_called_once()


def test_init_without_config():
    """Test connector initialization without config uses defaults."""
    with patch("httpx.AsyncClient"):
        connector = MockConnector()
        assert connector.api_key == "mock_api_key_12345"
        assert connector.api_secret == "mock_api_secret_67890"


def test_init_with_config():
    """Test connector initialization with custom config."""
    config = {
        "api_key": "custom_key",
        "api_secret": "custom_secret"
    }
    with patch("httpx.AsyncClient"):
        connector = MockConnector(config=config)
        assert connector.api_key == "custom_key"
        assert connector.api_secret == "custom_secret"


def test_normalize_symbol():
    """Test symbol normalization removes slash."""
    with patch("httpx.AsyncClient"):
        connector = MockConnector()
        assert connector._normalize_symbol("BTC/USDT") == "BTCUSDT"
        assert connector._normalize_symbol("BTCUSDT") == "BTCUSDT"


def test_sign_request():
    """Test request signing creates valid HMAC signature."""
    with patch("httpx.AsyncClient"):
        connector = MockConnector()
        params = {"symbol": "BTCUSDT"}
        signature = connector._sign_request(params)

        # Should be a hex string
        assert len(signature) == 64
        # Timestamp should have been added
        assert "timestamp" in params


@pytest.mark.asyncio
async def test_place_order_limit(connector, mock_client):
    """Test placing a limit order with price."""
    resp = create_mock_response(200, {
        "orderId": "2",
        "clientOrderId": "client2",
        "symbol": "BTCUSDT",
        "side": "SELL",
        "type": "LIMIT",
        "origQty": "0.5",
        "price": "55000.0",
        "avgPrice": "0",
        "status": "NEW",
        "executedQty": "0"
    })
    mock_client.post.return_value = resp

    order = await connector.place_order(
        "BTC/USDT", "sell", "limit", Decimal("0.5"), price=Decimal("55000.0")
    )
    assert order["id"] == "2"
    assert order["type"] == "limit"
    assert order["price"] == 55000.0


@pytest.mark.asyncio
async def test_place_order_rejected(connector, mock_client):
    """Test order rejection returns proper error."""
    resp = create_mock_response(400, {"detail": "Insufficient balance"})
    mock_client.post.return_value = resp

    with pytest.raises(APIError, match="Insufficient balance"):
        await connector.place_order("BTCUSDT", "buy", "market", Decimal("100.0"))


@pytest.mark.asyncio
async def test_get_order_status_error_response(connector, mock_client):
    """Test order status with error code raises APIError."""
    resp = create_mock_response(400, {"detail": {"code": -1000, "msg": "Unknown error"}})
    resp.raise_for_status = MagicMock()  # Don't raise for 400
    mock_client.get.return_value = resp

    with pytest.raises(APIError):
        await connector.get_order_status("1")


@pytest.mark.asyncio
async def test_precision_rules_symbol_formats(connector, mock_client):
    """Test precision rules stored in both BTCUSDT and BTC/USDT formats."""
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

    # Both formats should exist
    assert "BTCUSDT" in rules
    assert "BTC/USDT" in rules
    # Same values
    assert rules["BTCUSDT"]["tick_size"] == rules["BTC/USDT"]["tick_size"]