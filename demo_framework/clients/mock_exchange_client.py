"""
Mock Exchange Admin API Client.
"""

from typing import Dict, List, Optional

from .base_client import BaseClient, RetryConfig


class MockExchangeClient(BaseClient):
    """
    Client for Mock Exchange Admin API.

    Provides control over prices, orders, positions, and balances for testing.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:9000",
        timeout: float = 30.0,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(base_url, timeout, retry_config)

    # -------------------------------------------------------------------------
    # Admin Operations
    # -------------------------------------------------------------------------

    async def reset_exchange(self) -> Dict:
        """Reset all orders, positions, trades."""
        return await self.delete("/admin/reset")

    async def get_state(self) -> Dict:
        """Get full exchange state (symbols, orders, positions)."""
        return await self.get("/admin/state")

    # -------------------------------------------------------------------------
    # Symbol Operations
    # -------------------------------------------------------------------------

    async def get_symbols(self) -> List[Dict]:
        """Get all available symbols with their current prices."""
        return await self.get("/admin/symbols")

    async def get_symbol(self, symbol: str) -> Dict:
        """Get a specific symbol's data."""
        return await self.get(f"/admin/symbols/{symbol}")

    async def set_price(self, symbol: str, price: float) -> Dict:
        """
        Set price for a symbol.

        This may trigger order fills if the price crosses order levels.
        Returns info about any orders that were filled.
        """
        return await self.put(
            f"/admin/symbols/{symbol}/price",
            json={"price": price},
        )

    async def set_prices(self, prices: Dict[str, float]) -> Dict:
        """Set multiple prices at once."""
        results = {}
        for symbol, price in prices.items():
            results[symbol] = await self.set_price(symbol, price)
        return results

    # -------------------------------------------------------------------------
    # Order Operations
    # -------------------------------------------------------------------------

    async def get_all_orders(
        self,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[Dict]:
        """Get all orders with optional filters."""
        params = {}
        if status:
            params["status"] = status
        if symbol:
            params["symbol"] = symbol
        return await self.get("/admin/orders", params=params)

    async def get_order(self, order_id: str) -> Dict:
        """Get a specific order by ID."""
        return await self.get(f"/admin/orders/{order_id}")

    async def fill_order(
        self,
        order_id: str,
        fill_price: Optional[float] = None,
        fill_quantity: Optional[float] = None,
    ) -> Dict:
        """
        Manually fill an order (full or partial).

        Args:
            order_id: Order ID to fill
            fill_price: Price to fill at (defaults to order price)
            fill_quantity: Quantity to fill (defaults to remaining quantity)
        """
        params = {}
        if fill_price is not None:
            params["fill_price"] = fill_price
        if fill_quantity is not None:
            params["fill_quantity"] = fill_quantity
        return await self.post(f"/admin/orders/{order_id}/fill", params=params)

    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order."""
        return await self.post(f"/admin/orders/{order_id}/cancel")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open (NEW) orders."""
        return await self.get_all_orders(status="NEW", symbol=symbol)

    async def get_filled_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all filled orders."""
        return await self.get_all_orders(status="FILLED", symbol=symbol)

    # -------------------------------------------------------------------------
    # Position Operations
    # -------------------------------------------------------------------------

    async def get_positions(self) -> List[Dict]:
        """Get all positions on mock exchange."""
        return await self.get("/admin/positions")

    async def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for a specific symbol."""
        positions = await self.get_positions()
        for pos in positions:
            if pos.get("symbol") == symbol:
                return pos
        return None

    # -------------------------------------------------------------------------
    # Balance Operations
    # -------------------------------------------------------------------------

    async def get_balances(self) -> List[Dict]:
        """Get all balances."""
        return await self.get("/admin/balances")

    async def set_balance(self, asset: str, free: float, locked: float = 0) -> Dict:
        """Set balance for an asset."""
        return await self.put(
            f"/admin/balances/{asset}",
            json={"free": free, "locked": locked},
        )

    # -------------------------------------------------------------------------
    # Trade Operations
    # -------------------------------------------------------------------------

    async def get_trades(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all trades."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self.get("/admin/trades", params=params)

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    async def fill_all_orders(self, symbol: Optional[str] = None) -> int:
        """Fill all open orders. Returns number filled."""
        orders = await self.get_open_orders(symbol=symbol)
        filled = 0
        for order in orders:
            try:
                await self.fill_order(order["orderId"])
                filled += 1
            except Exception:
                pass
        return filled

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """Cancel all open orders. Returns number cancelled."""
        orders = await self.get_open_orders(symbol=symbol)
        cancelled = 0
        for order in orders:
            try:
                await self.cancel_order(order["orderId"])
                cancelled += 1
            except Exception:
                pass
        return cancelled

    async def move_price_to_fill(
        self,
        symbol: str,
        target_price: float,
        step_percent: float = 1.0,
        delay_seconds: float = 0.5,
    ) -> int:
        """
        Gradually move price to target, filling orders along the way.

        Args:
            symbol: Symbol to move price for
            target_price: Target price to reach
            step_percent: Percentage to move per step
            delay_seconds: Delay between steps

        Returns:
            Number of orders filled during the move
        """
        import asyncio

        current = await self.get_symbol(symbol)
        current_price = current["currentPrice"]

        filled_count = 0
        direction = 1 if target_price > current_price else -1

        while (direction > 0 and current_price < target_price) or \
              (direction < 0 and current_price > target_price):
            # Calculate next price
            step = current_price * (step_percent / 100) * direction
            next_price = current_price + step

            # Don't overshoot
            if (direction > 0 and next_price > target_price) or \
               (direction < 0 and next_price < target_price):
                next_price = target_price

            # Set price (may trigger fills)
            result = await self.set_price(symbol, next_price)
            if result.get("filledOrders"):
                filled_count += len(result["filledOrders"])

            current_price = next_price
            await asyncio.sleep(delay_seconds)

        return filled_count
