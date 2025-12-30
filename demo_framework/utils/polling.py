"""
Polling utilities for waiting on async conditions.

Replaces arbitrary sleeps with intelligent polling that waits
only as long as necessary for conditions to be met.
"""

import asyncio
import time
from typing import Any, Callable, List, Optional, TypeVar

T = TypeVar("T")


class PollingTimeout(Exception):
    """Raised when polling times out."""

    def __init__(self, message: str, last_value: Any = None):
        super().__init__(message)
        self.last_value = last_value


async def wait_for_condition(
    condition: Callable[[], Any],
    timeout: float = 30.0,
    poll_interval: float = 1.0,
    error_message: str = "Condition not met within timeout",
) -> Any:
    """
    Wait for an async condition to become truthy.

    Args:
        condition: Async callable that returns a value. Polling stops when truthy.
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls
        error_message: Message for timeout exception

    Returns:
        The truthy value returned by condition

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    start = time.time()
    last_value = None

    while (time.time() - start) < timeout:
        try:
            if asyncio.iscoroutinefunction(condition):
                value = await condition()
            else:
                value = condition()

            last_value = value

            if value:
                return value
        except Exception:
            pass  # Ignore errors and keep polling

        await asyncio.sleep(poll_interval)

    raise PollingTimeout(
        f"{error_message} (waited {timeout}s)",
        last_value=last_value,
    )


async def wait_for_position_count(
    engine_client,
    expected_count: int,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> List:
    """
    Wait for a specific number of active positions.

    Args:
        engine_client: EngineClient instance
        expected_count: Expected number of positions
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls

    Returns:
        List of positions when count matches

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        positions = await engine_client.get_active_positions()
        if len(positions) == expected_count:
            return positions
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Expected {expected_count} positions",
    )


async def wait_for_position_status(
    engine_client,
    symbol: str,
    expected_status: str,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
    timeframe: int = 60,
) -> Optional[dict]:
    """
    Wait for a position to reach a specific status.

    Args:
        engine_client: EngineClient instance
        symbol: Symbol to check (e.g., "SOL/USDT")
        expected_status: Expected status (e.g., "active", "closed")
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls
        timeframe: Timeframe to match

    Returns:
        Position dict when status matches, or None if position closed/doesn't exist

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        positions = await engine_client.get_active_positions()
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("timeframe") == timeframe:
                if pos.get("status") == expected_status:
                    return pos
                return None
        # If expected status is "closed" and position not found, that's success
        if expected_status == "closed":
            return {"symbol": symbol, "status": "closed"}
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Position {symbol} did not reach status '{expected_status}'",
    )


async def wait_for_position_exists(
    engine_client,
    symbol: str,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
    timeframe: int = 60,
) -> dict:
    """
    Wait for a position to exist for a symbol.

    Args:
        engine_client: EngineClient instance
        symbol: Symbol to check
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls
        timeframe: Timeframe to match

    Returns:
        Position dict when found

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        positions = await engine_client.get_active_positions()
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("timeframe") == timeframe:
                return pos
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Position for {symbol} not found",
    )


async def wait_for_position_closed(
    engine_client,
    symbol: str,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
    timeframe: int = 60,
) -> bool:
    """
    Wait for a position to be closed (not in active positions).

    Args:
        engine_client: EngineClient instance
        symbol: Symbol to check
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls
        timeframe: Timeframe to match

    Returns:
        True when position is closed

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        positions = await engine_client.get_active_positions()
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("timeframe") == timeframe:
                return False
        return True

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Position {symbol} still active",
    )


async def wait_for_queue_count(
    engine_client,
    expected_count: int,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> List:
    """
    Wait for a specific number of queued signals.

    Args:
        engine_client: EngineClient instance
        expected_count: Expected number of queued signals
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls

    Returns:
        List of queued signals when count matches

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        queue = await engine_client.get_queue()
        if len(queue) == expected_count:
            return queue
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Expected {expected_count} queued signals",
    )


async def wait_for_queued_signal(
    engine_client,
    symbol: str,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> dict:
    """
    Wait for a signal to appear in the queue.

    Args:
        engine_client: EngineClient instance
        symbol: Symbol to check
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls

    Returns:
        Queued signal dict when found

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        queue = await engine_client.get_queue()
        for sig in queue:
            if sig.get("symbol") == symbol:
                return sig
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Signal for {symbol} not found in queue",
    )


async def wait_for_order_fill(
    mock_client,
    symbol: str,
    min_filled: int = 1,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> List:
    """
    Wait for orders to be filled on mock exchange.

    Args:
        mock_client: MockExchangeClient instance
        symbol: Symbol to check
        min_filled: Minimum number of filled orders expected
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls

    Returns:
        List of filled orders

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        orders = await mock_client.get_filled_orders(symbol=symbol)
        if len(orders) >= min_filled:
            return orders
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Expected {min_filled}+ filled orders for {symbol}",
    )


async def wait_for_open_orders(
    mock_client,
    symbol: str,
    min_count: int = 1,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> List:
    """
    Wait for open orders to appear on mock exchange.

    Args:
        mock_client: MockExchangeClient instance
        symbol: Symbol to check
        min_count: Minimum number of open orders expected
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls

    Returns:
        List of open orders

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        orders = await mock_client.get_open_orders(symbol=symbol)
        if len(orders) >= min_count:
            return orders
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Expected {min_count}+ open orders for {symbol}",
    )


async def wait_for_pyramid_count(
    engine_client,
    symbol: str,
    expected_count: int,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
    timeframe: int = 60,
) -> dict:
    """
    Wait for a position to reach a specific pyramid count.

    Args:
        engine_client: EngineClient instance
        symbol: Symbol to check
        expected_count: Expected pyramid count
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls
        timeframe: Timeframe to match

    Returns:
        Position dict when pyramid count matches

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        positions = await engine_client.get_active_positions()
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("timeframe") == timeframe:
                if pos.get("pyramid_count", 0) == expected_count:
                    return pos
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Position {symbol} did not reach pyramid_count={expected_count}",
    )


async def wait_for_position_filled(
    engine_client,
    symbol: str,
    min_quantity: float = 0.0,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
    timeframe: int = 60,
) -> dict:
    """
    Wait for a position to have filled quantity > min_quantity.

    Args:
        engine_client: EngineClient instance
        symbol: Symbol to check
        min_quantity: Minimum filled quantity required
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls
        timeframe: Timeframe to match

    Returns:
        Position dict when filled quantity exceeds min_quantity

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        positions = await engine_client.get_active_positions()
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("timeframe") == timeframe:
                qty = float(pos.get("total_filled_quantity", 0) or 0)
                if qty > min_quantity:
                    return pos
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Position {symbol} did not fill (need qty > {min_quantity})",
    )


async def wait_for_risk_eligible(
    engine_client,
    symbol: str,
    timeout: float = 120.0,  # Longer for risk timer
    poll_interval: float = 5.0,
    timeframe: int = 60,
) -> dict:
    """
    Wait for a position to become risk eligible.

    Args:
        engine_client: EngineClient instance
        symbol: Symbol to check
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls
        timeframe: Timeframe to match

    Returns:
        Position dict when risk_eligible=True

    Raises:
        PollingTimeout: If timeout is exceeded
    """
    async def check():
        positions = await engine_client.get_active_positions()
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("timeframe") == timeframe:
                if pos.get("risk_eligible", False):
                    return pos
        return None

    return await wait_for_condition(
        check,
        timeout=timeout,
        poll_interval=poll_interval,
        error_message=f"Position {symbol} did not become risk_eligible",
    )
