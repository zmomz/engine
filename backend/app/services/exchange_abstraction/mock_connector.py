
import os
import logging
from decimal import Decimal
from typing import Dict, Optional, Any
import uuid

from app.services.exchange_abstraction.interface import ExchangeInterface
from app.exceptions import ExchangeConnectionError, APIError

logger = logging.getLogger(__name__)

class MockConnector(ExchangeInterface):
    def __init__(self):
        self.base_url = os.getenv("MOCK_EXCHANGE_URL", "http://mock-exchange:9000")

    async def _get_client(self):
        try:
            import httpx
            return httpx.AsyncClient(base_url=self.base_url)
        except ImportError:
            raise ImportError("httpx is required for MockConnector. Please install it.")

    async def get_precision_rules(self) -> Dict:
        async with await self._get_client() as client:
            try:
                # We'll just fetch for one symbol to check connectivity, but return hardcoded for now 
                # or fetch from the endpoint if extended.
                # The mock exchange has /symbols/{symbol}/precision
                # But we need ALL symbols. The mock exchange might not support listing all.
                # For safety and speed in this test phase, we'll keep the hardcoded list but maybe verify connectivity.
                
                # Verify connectivity
                resp = await client.get("/health")
                resp.raise_for_status()

                return {
                    "BTCUSDT": {
                        "tick_size": 0.01,
                        "step_size": 0.001,
                        "min_qty": 0.001,
                        "min_notional": 10.0,
                    },
                    "ETHUSDT": {
                        "tick_size": 0.01,
                        "step_size": 0.001,
                        "min_qty": 0.001,
                        "min_notional": 10.0,
                    },
                    "LTCUSDT": {
                        "tick_size": 0.01,
                        "step_size": 0.001,
                        "min_qty": 0.001,
                        "min_notional": 10.0,
                    },
                    "SOLUSDT": {
                        "tick_size": 0.01,
                        "step_size": 0.001,
                        "min_qty": 0.001,
                        "min_notional": 10.0,
                    }
                }
            except Exception as e:
                logger.error(f"MockConnector: Failed to connect to {self.base_url}: {e}")
                raise ExchangeConnectionError(f"Failed to connect to mock exchange: {e}")

    async def place_order(self, symbol: str, side: str, order_type: str, quantity: Decimal, price: Optional[Decimal] = None) -> Dict:
        async with await self._get_client() as client:
            try:
                payload = {
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "quantity": float(quantity),
                    "price": float(price) if price else 0.0
                }
                response = await client.post("/orders", json=payload)
                response.raise_for_status()
                data = response.json()
                
                return {
                    "id": data["id"],
                    "symbol": data["symbol"],
                    "side": data["side"],
                    "type": data["type"],
                    "quantity": float(data["quantity"]),
                    "price": float(data["price"]),
                    "status": data["status"],
                    "filled": 0.0,
                    "remaining": float(data["quantity"]),
                }
            except Exception as e:
                raise APIError(f"MockConnector place_order failed: {e}")

    async def get_order_status(self, order_id: str, symbol: str = None) -> Dict:
        async with await self._get_client() as client:
            try:
                response = await client.get(f"/orders/{order_id}")
                if response.status_code == 404:
                    # Map 404 to closed/canceled or specific error?
                    # The app expects a status string.
                    return {"status": "canceled"}
                
                response.raise_for_status()
                data = response.json()
                
                return {
                    "id": data["id"],
                    "status": data["status"],
                    "filled": float(data.get("quantity", 0)) if data["status"] == "filled" else 0.0, # Simplified
                    "price": float(data.get("price", 0)),
                }
            except Exception as e:
                raise APIError(f"MockConnector get_order_status failed: {e}")

    async def cancel_order(self, order_id: str, symbol: str = None) -> Dict:
        async with await self._get_client() as client:
            try:
                response = await client.delete(f"/orders/{order_id}")
                if response.status_code == 404:
                     return {"id": order_id, "status": "canceled"}
                
                response.raise_for_status()
                return {"id": order_id, "status": "canceled"}
            except Exception as e:
                raise APIError(f"MockConnector cancel_order failed: {e}")

    async def get_current_price(self, symbol: str) -> Decimal:
        async with await self._get_client() as client:
            try:
                response = await client.get(f"/symbols/{symbol}/price")
                response.raise_for_status()
                data = response.json()
                return Decimal(str(data["price"]))
            except Exception as e:
                raise APIError(f"MockConnector get_current_price failed: {e}")

    async def fetch_balance(self) -> Dict:
        async with await self._get_client() as client:
            try:
                response = await client.get("/balance")
                response.raise_for_status()
                data = response.json()
                # Convert floats to Decimals and return flat structure (totals only)
                # Matches BinanceConnector/BybitConnector behavior
                return {
                    k: Decimal(str(v["total"]))
                    for k, v in data.items()
                }
            except Exception as e:
                raise APIError(f"MockConnector fetch_balance failed: {e}")

    async def close(self):
        """
        No-op for MockConnector as it manages client context per request.
        """
        pass
