"""
Mock Exchange Connector - Enhanced version compatible with the full mock exchange.
Implements the same interface as Binance/Bybit connectors.
"""
import os
import logging
import hashlib
import hmac
import time
from decimal import Decimal
from typing import Dict, Optional, Any, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    import httpx

from app.services.exchange_abstraction.interface import ExchangeInterface
from app.exceptions import ExchangeConnectionError, APIError

logger = logging.getLogger(__name__)


class MockConnector(ExchangeInterface):
    """
    Connector for the enhanced Mock Exchange.
    Communicates with the mock exchange server via REST API,
    mimicking Binance Futures API behavior.

    Supports error simulation for testing via inject_error() method.
    """

    def __init__(self, config: dict = None):
        """
        Initialize the mock connector.

        Args:
            config: Configuration dict containing:
                - api_key: Mock exchange API key
                - api_secret: Mock exchange API secret
                - base_url: Mock exchange URL (optional)
        """
        self.base_url = os.getenv("MOCK_EXCHANGE_URL", "http://mock-exchange:9000")

        # Extract API credentials from config
        if config:
            self.api_key = config.get("api_key", "mock_api_key_12345")
            self.api_secret = config.get("api_secret", "mock_api_secret_67890")
        else:
            self.api_key = "mock_api_key_12345"
            self.api_secret = "mock_api_secret_67890"

        self._precision_cache = None
        self._precision_cache_time = 0
        self._cache_ttl = 300  # 5 minutes

        # Shared HTTP client to avoid connection pool churn
        self._client: Optional["httpx.AsyncClient"] = None

        # Error simulation for testing
        self._error_injection: Dict[str, Any] = {}

    def inject_error(self, method: str, error_type: str = "exception", error_data: Any = None, one_shot: bool = True):
        """
        Inject an error to be raised on the next call to a method.

        Args:
            method: Method name to inject error for (e.g., 'place_order', 'get_current_price')
            error_type: Type of error - 'exception', 'timeout', 'insufficient_balance', 'rate_limit', 'api_error'
            error_data: Additional data for the error (message, code, etc.)
            one_shot: If True, error is cleared after first trigger
        """
        self._error_injection[method] = {
            "type": error_type,
            "data": error_data,
            "one_shot": one_shot
        }
        logger.debug(f"MockConnector: Injected {error_type} error for {method}")

    def clear_error(self, method: str = None):
        """Clear injected errors for a method or all methods."""
        if method:
            self._error_injection.pop(method, None)
        else:
            self._error_injection.clear()

    def _check_error_injection(self, method: str):
        """Check if an error should be raised for a method."""
        if method in self._error_injection:
            error_info = self._error_injection[method]
            if error_info["one_shot"]:
                del self._error_injection[method]

            error_type = error_info["type"]
            error_data = error_info.get("data", "Injected test error")

            if error_type == "exception":
                raise Exception(error_data)
            elif error_type == "timeout":
                raise ExchangeConnectionError("Connection timeout (simulated)")
            elif error_type == "insufficient_balance":
                raise APIError("Insufficient balance (simulated)")
            elif error_type == "rate_limit":
                raise APIError("Rate limit exceeded (simulated)")
            elif error_type == "api_error":
                raise APIError(error_data if error_data else "API error (simulated)")

    async def _get_client(self) -> "httpx.AsyncClient":
        """Get or create a shared async HTTP client."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                headers={"X-MBX-APIKEY": self.api_key},
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                    keepalive_expiry=30.0
                )
            )
        return self._client

    def _sign_request(self, params: dict) -> str:
        """Create HMAC-SHA256 signature for signed endpoints."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to exchange format (remove slash)."""
        return symbol.replace("/", "")

    async def get_precision_rules(self) -> Dict:
        """
        Fetch precision rules from the mock exchange.
        Returns a dict mapping symbol to precision info.
        """
        # Check cache
        current_time = time.time()
        if self._precision_cache and (current_time - self._precision_cache_time) < self._cache_ttl:
            return self._precision_cache

        try:
            client = await self._get_client()
            response = await client.get("/fapi/v1/exchangeInfo")
            response.raise_for_status()
            data = response.json()

            precision_rules = {}
            for symbol_info in data.get("symbols", []):
                symbol = symbol_info["symbol"]  # e.g., "BTCUSDT"
                filters = {f["filterType"]: f for f in symbol_info.get("filters", [])}

                rules = {
                    "tick_size": float(filters.get("PRICE_FILTER", {}).get("tickSize", "0.01")),
                    "step_size": float(filters.get("LOT_SIZE", {}).get("stepSize", "0.001")),
                    "min_qty": float(filters.get("LOT_SIZE", {}).get("minQty", "0.001")),
                    "max_qty": float(filters.get("LOT_SIZE", {}).get("maxQty", "9000")),
                    "min_notional": float(filters.get("MIN_NOTIONAL", {}).get("notional", "10")),
                }

                # Store under both formats: BTCUSDT and BTC/USDT
                precision_rules[symbol] = rules
                # Also store with slash format for compatibility with signal symbols
                if symbol.endswith("USDT"):
                    unified_symbol = symbol[:-4] + "/" + symbol[-4:]  # BTCUSDT -> BTC/USDT
                    precision_rules[unified_symbol] = rules

            self._precision_cache = precision_rules
            self._precision_cache_time = current_time
            return precision_rules

        except Exception as e:
            logger.error(f"MockConnector: Failed to fetch precision rules: {e}")
            raise ExchangeConnectionError(f"Failed to connect to mock exchange: {e}")

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None
    ) -> Dict:
        """
        Place an order on the mock exchange.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            side: 'buy' or 'sell'
            order_type: 'limit' or 'market'
            quantity: Order quantity
            price: Order price (required for limit orders)

        Returns:
            Order response dict with id, status, etc.
        """
        self._check_error_injection("place_order")
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            client = await self._get_client()
            payload = {
                "symbol": normalized_symbol,
                "side": side.upper(),
                "type": order_type.upper(),
                "quantity": float(quantity),
                "price": float(price) if price else 0.0,
                "timeInForce": "GTC" if order_type.upper() == "LIMIT" else None,
            }

            response = await client.post("/fapi/v1/order", json=payload)

            if response.status_code >= 400:
                error_data = response.json()
                raise APIError(f"Order rejected: {error_data.get('detail', error_data)}")

            response.raise_for_status()
            data = response.json()

            return {
                "id": str(data["orderId"]),
                "client_order_id": data.get("clientOrderId"),
                "symbol": data["symbol"],
                "side": data["side"].lower(),
                "type": data["type"].lower(),
                "quantity": float(data["origQty"]),
                "price": float(data["price"]),
                "avg_price": float(data.get("avgPrice", 0)),
                "status": data["status"].lower(),
                "filled": float(data.get("executedQty", 0)),
                "remaining": float(data["origQty"]) - float(data.get("executedQty", 0)),
            }

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"MockConnector place_order failed: {e}")

    async def get_order_status(self, order_id: str, symbol: str = None) -> Dict:
        """
        Get status of an order.

        Args:
            order_id: The order ID to check
            symbol: Trading pair (required for Binance-style API)

        Returns:
            Order status dict
        """
        self._check_error_injection("get_order_status")
        try:
            client = await self._get_client()
            params = {"orderId": order_id}
            if symbol:
                params["symbol"] = self._normalize_symbol(symbol)

            response = await client.get("/fapi/v1/order", params=params)

            if response.status_code == 400:
                error_data = response.json()
                if error_data.get("detail", {}).get("code") == -2013:
                    # Order not found
                    return {"status": "canceled", "id": order_id}
                raise APIError(f"Order query failed: {error_data}")

            response.raise_for_status()
            data = response.json()

            return {
                "id": str(data["orderId"]),
                "status": data["status"].lower(),
                "filled": float(data.get("executedQty", 0)),
                "price": float(data.get("avgPrice", 0)) or float(data.get("price", 0)),
                "average": float(data.get("avgPrice", 0)) or float(data.get("price", 0)),  # OrderService expects 'average' key
                "quantity": float(data["origQty"]),
            }

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"MockConnector get_order_status failed: {e}")

    async def cancel_order(self, order_id: str, symbol: str = None) -> Dict:
        """
        Cancel an open order.

        Args:
            order_id: The order ID to cancel
            symbol: Trading pair (required for Binance-style API)

        Returns:
            Cancellation result dict
        """
        self._check_error_injection("cancel_order")
        try:
            client = await self._get_client()
            params = {"orderId": order_id}
            if symbol:
                params["symbol"] = self._normalize_symbol(symbol)

            response = await client.delete("/fapi/v1/order", params=params)

            if response.status_code == 400:
                error_data = response.json()
                # Order not found or already canceled
                return {"id": order_id, "status": "canceled"}

            response.raise_for_status()
            return {"id": order_id, "status": "canceled"}

        except Exception as e:
            logger.warning(f"Cancel order {order_id} failed: {e}")
            return {"id": order_id, "status": "canceled"}

    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current price for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT' or 'BTC/USDT')

        Returns:
            Current price as Decimal
        """
        self._check_error_injection("get_current_price")
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            client = await self._get_client()
            response = await client.get("/fapi/v1/ticker/price", params={"symbol": normalized_symbol})
            response.raise_for_status()
            data = response.json()
            return Decimal(data["price"])

        except Exception as e:
            raise APIError(f"MockConnector get_current_price failed: {e}")

    async def get_all_tickers(self) -> Dict:
        """
        Get all ticker prices.

        Returns:
            Dict mapping symbol to ticker info
        """
        try:
            client = await self._get_client()
            response = await client.get("/fapi/v1/ticker/price")
            response.raise_for_status()
            data = response.json()

            return {
                item["symbol"].replace("USDT", "/USDT"): {"last": float(item["price"])}
                for item in data
            }

        except Exception as e:
            raise APIError(f"MockConnector get_all_tickers failed: {e}")

    async def fetch_balance(self) -> Dict:
        """
        Fetch total account balance.

        Returns:
            Dict mapping asset to total balance
        """
        self._check_error_injection("fetch_balance")
        try:
            client = await self._get_client()
            response = await client.get("/fapi/v2/balance")
            response.raise_for_status()
            data = response.json()

            return {
                item["asset"]: Decimal(item["balance"])
                for item in data
            }

        except Exception as e:
            raise APIError(f"MockConnector fetch_balance failed: {e}")

    async def fetch_free_balance(self) -> Dict:
        """
        Fetch available (free) balance.

        Returns:
            Dict mapping asset to available balance
        """
        self._check_error_injection("fetch_free_balance")
        try:
            client = await self._get_client()
            response = await client.get("/fapi/v2/balance")
            response.raise_for_status()
            data = response.json()

            return {
                item["asset"]: Decimal(item["availableBalance"])
                for item in data
            }

        except Exception as e:
            raise APIError(f"MockConnector fetch_free_balance failed: {e}")

    async def get_open_orders(self, symbol: str = None) -> list:
        """
        Get all open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open orders
        """
        try:
            client = await self._get_client()
            params = {}
            if symbol:
                params["symbol"] = symbol

            response = await client.get("/fapi/v1/openOrders", params=params)
            response.raise_for_status()
            data = response.json()

            return [
                {
                    "id": str(order["orderId"]),
                    "symbol": order["symbol"],
                    "side": order["side"].lower(),
                    "type": order["type"].lower(),
                    "price": float(order["price"]),
                    "quantity": float(order["origQty"]),
                    "filled": float(order.get("executedQty", 0)),
                    "status": order["status"].lower(),
                }
                for order in data
            ]

        except Exception as e:
            raise APIError(f"MockConnector get_open_orders failed: {e}")

    async def get_positions(self, symbol: str = None) -> list:
        """
        Get open positions.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of positions
        """
        try:
            client = await self._get_client()
            params = {}
            if symbol:
                params["symbol"] = symbol

            response = await client.get("/fapi/v2/positionRisk", params=params)
            response.raise_for_status()
            data = response.json()

            return [
                {
                    "symbol": pos["symbol"],
                    "side": "long" if float(pos["positionAmt"]) > 0 else "short",
                    "quantity": abs(float(pos["positionAmt"])),
                    "entry_price": float(pos["entryPrice"]),
                    "mark_price": float(pos["markPrice"]),
                    "unrealized_pnl": float(pos["unRealizedProfit"]),
                    "leverage": int(pos["leverage"]),
                }
                for pos in data
                if float(pos["positionAmt"]) != 0
            ]

        except Exception as e:
            raise APIError(f"MockConnector get_positions failed: {e}")

    async def close(self):
        """Cleanup the shared HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
