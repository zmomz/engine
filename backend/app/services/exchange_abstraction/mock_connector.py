
from decimal import Decimal
from typing import Dict, Optional
import httpx

from app.services.exchange_abstraction.interface import ExchangeInterface

class MockConnector(ExchangeInterface):
    def __init__(self, base_url: str = "http://mock-exchange:9000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def get_precision_rules(self) -> Dict:
        # Return a hardcoded set for testing purposes, matching the flat structure expected by GridCalculatorService
        return {
            "BTCUSDT": {
                "tick_size": 0.01,
                "step_size": 0.001,
                "min_qty": 0.001,
                "min_notional": 10.0,
            }
        }

    async def place_order(self, symbol: str, side: str, order_type: str, quantity: Decimal, price: Optional[Decimal] = None) -> Dict:
        order_data = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": float(quantity),
            "price": float(price) if price else 0.0,
        }
        response = await self.client.post(f"{self.base_url}/orders", json=order_data)
        response.raise_for_status()
        return response.json()

    async def get_order_status(self, order_id: str) -> Dict:
        response = await self.client.get(f"{self.base_url}/orders/{order_id}")
        response.raise_for_status()
        return response.json()

    async def cancel_order(self, order_id: str) -> Dict:
        response = await self.client.delete(f"{self.base_url}/orders/{order_id}")
        response.raise_for_status()
        return response.json()

    async def get_current_price(self, symbol: str) -> Decimal:
        response = await self.client.get(f"{self.base_url}/symbols/{symbol}/price")
        response.raise_for_status()
        return Decimal(str(response.json()["price"]))

    async def fetch_balance(self) -> Dict:
        response = await self.client.get(f"{self.base_url}/balance")
        response.raise_for_status()
        return response.json()
