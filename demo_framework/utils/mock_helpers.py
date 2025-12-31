"""
Mock Exchange Helpers for scenario testing.

Provides helper functions for simulating various mock exchange behaviors
like partial fills, network errors, and precision rules.
"""

from typing import Optional
import aiohttp


class MockExchangeHelper:
    """
    Helper class for controlling mock exchange behavior during tests.

    Provides methods to simulate various trading conditions and errors.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:9000"):
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def set_error_mode(
        self,
        error_type: str,
        count: int = 1,
        message: Optional[str] = None,
    ) -> bool:
        """
        Configure mock exchange to simulate errors.

        Args:
            error_type: Type of error to simulate:
                - "network_timeout": Simulate connection timeout
                - "rate_limit": Return 429 Too Many Requests
                - "invalid_api_key": Return authentication error
                - "expired_api_key": Return expired credentials error
                - "exchange_offline": Return exchange unavailable
                - "exchange_error": Generic exchange error
                - "order_not_found_on_status": Order disappears during status check
                - "fail_second_order": Fail every second order
            count: Number of times to return this error (0 = forever)
            message: Optional custom error message

        Returns:
            True if configured successfully
        """
        session = await self._get_session()
        try:
            async with session.put(
                f"{self.base_url}/admin/error-mode",
                json={
                    "error_type": error_type,
                    "count": count,
                    "message": message,
                },
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def clear_error_mode(self) -> bool:
        """Clear any error simulation mode."""
        session = await self._get_session()
        try:
            async with session.delete(f"{self.base_url}/admin/error-mode") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def set_fill_delay(self, symbol: str, delay_seconds: float) -> bool:
        """
        Configure a delay before orders fill.

        Args:
            symbol: Trading symbol (e.g., "SOLUSDT")
            delay_seconds: Delay in seconds before order fills

        Returns:
            True if configured successfully
        """
        session = await self._get_session()
        try:
            async with session.put(
                f"{self.base_url}/admin/symbols/{symbol}/fill-delay",
                json={"delay_seconds": delay_seconds},
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def clear_fill_delay(self, symbol: Optional[str] = None) -> bool:
        """Clear fill delay for symbol or all symbols."""
        session = await self._get_session()
        try:
            if symbol:
                async with session.delete(
                    f"{self.base_url}/admin/symbols/{symbol}/fill-delay"
                ) as resp:
                    return resp.status == 200
            else:
                async with session.delete(
                    f"{self.base_url}/admin/fill-delay"
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def simulate_partial_fill(
        self,
        order_id: str,
        fill_percentage: float = 50.0,
    ) -> bool:
        """
        Partially fill an open order.

        Args:
            order_id: Order ID to partially fill
            fill_percentage: Percentage of order to fill (0-100)

        Returns:
            True if filled successfully
        """
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/admin/orders/{order_id}/partial-fill",
                json={"fill_percentage": fill_percentage},
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def set_precision_rules(
        self,
        symbol: str,
        quantity_precision: int = 8,
        price_precision: int = 8,
        min_quantity: Optional[float] = None,
        max_quantity: Optional[float] = None,
    ) -> bool:
        """
        Set precision rules for a symbol.

        Args:
            symbol: Trading symbol
            quantity_precision: Decimal places for quantity
            price_precision: Decimal places for price
            min_quantity: Minimum order quantity
            max_quantity: Maximum order quantity

        Returns:
            True if configured successfully
        """
        session = await self._get_session()
        payload = {
            "quantity_precision": quantity_precision,
            "price_precision": price_precision,
        }
        if min_quantity is not None:
            payload["min_quantity"] = min_quantity
        if max_quantity is not None:
            payload["max_quantity"] = max_quantity

        try:
            async with session.put(
                f"{self.base_url}/admin/symbols/{symbol}/precision",
                json=payload,
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def clear_precision_rules(self, symbol: Optional[str] = None) -> bool:
        """Clear precision rules for symbol or all symbols."""
        session = await self._get_session()
        try:
            if symbol:
                async with session.delete(
                    f"{self.base_url}/admin/symbols/{symbol}/precision"
                ) as resp:
                    return resp.status == 200
            else:
                async with session.delete(f"{self.base_url}/admin/precision") as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def set_min_notional(self, symbol: str, min_notional: float) -> bool:
        """
        Set minimum notional value for a symbol.

        Args:
            symbol: Trading symbol
            min_notional: Minimum order value in quote currency

        Returns:
            True if configured successfully
        """
        session = await self._get_session()
        try:
            async with session.put(
                f"{self.base_url}/admin/symbols/{symbol}/min-notional",
                json={"min_notional": min_notional},
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def clear_min_notional(self, symbol: Optional[str] = None) -> bool:
        """Clear minimum notional for symbol or all symbols."""
        session = await self._get_session()
        try:
            if symbol:
                async with session.delete(
                    f"{self.base_url}/admin/symbols/{symbol}/min-notional"
                ) as resp:
                    return resp.status == 200
            else:
                async with session.delete(f"{self.base_url}/admin/min-notional") as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def set_max_quantity(self, symbol: str, max_quantity: float) -> bool:
        """
        Set maximum quantity for a symbol.

        Args:
            symbol: Trading symbol
            max_quantity: Maximum order quantity

        Returns:
            True if configured successfully
        """
        return await self.set_precision_rules(symbol, max_quantity=max_quantity)

    async def clear_max_quantity(self, symbol: Optional[str] = None) -> bool:
        """Clear maximum quantity for symbol or all symbols."""
        return await self.clear_precision_rules(symbol)

    async def get_symbol_info(self, symbol: str) -> dict:
        """
        Get symbol information from mock exchange.

        Args:
            symbol: Trading symbol

        Returns:
            Symbol info dict or empty dict on error
        """
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/admin/symbols/{symbol}") as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
        except Exception:
            return {}

    async def trigger_tp_hit(self, symbol: str, tp_price: float) -> bool:
        """
        Trigger a take-profit hit by setting price to TP level.

        Args:
            symbol: Trading symbol
            tp_price: Price to set (should be at TP level)

        Returns:
            True if price set successfully
        """
        session = await self._get_session()
        try:
            async with session.put(
                f"{self.base_url}/admin/symbols/{symbol}/price",
                json={"price": tp_price},
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def set_balance(self, currency: str, amount: float) -> bool:
        """
        Set account balance for testing.

        Args:
            currency: Currency symbol (e.g., "USDT")
            amount: Balance amount

        Returns:
            True if set successfully
        """
        session = await self._get_session()
        try:
            async with session.put(
                f"{self.base_url}/admin/balance/{currency}",
                json={"amount": amount},
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def reset_balance(self) -> bool:
        """Reset balance to default values."""
        session = await self._get_session()
        try:
            async with session.post(f"{self.base_url}/admin/reset-balance") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def set_price(self, symbol: str, price: float) -> bool:
        """
        Set price for a symbol.

        Args:
            symbol: Trading symbol
            price: Price to set

        Returns:
            True if set successfully
        """
        session = await self._get_session()
        try:
            async with session.put(
                f"{self.base_url}/admin/symbols/{symbol}/price",
                json={"price": price},
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def reset_exchange(self) -> bool:
        """Reset mock exchange to initial state."""
        session = await self._get_session()
        try:
            async with session.post(f"{self.base_url}/admin/reset") as resp:
                return resp.status == 200
        except Exception:
            return False
