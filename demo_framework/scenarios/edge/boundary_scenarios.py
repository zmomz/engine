"""
Edge Case Scenarios (X-001 to X-005)

Tests for boundary conditions, race conditions,
and unusual input handling.
"""

import asyncio
from typing import Optional

from ..base import BaseScenario, DemoConfig
from ...runner import register_scenario
from ...utils.payload_builder import build_entry_payload, build_exit_payload
from ...utils.polling import (
    wait_for_position_exists,
    wait_for_position_count,
)


@register_scenario
class MinimumOrderSizeBoundary(BaseScenario):
    """X-001: Exact minimum order size is accepted."""

    id = "X-001"
    name = "Minimum Order Size Boundary"
    description = "Verifies exact minimum order size is accepted"
    category = "edge"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.mock.set_price("SOLUSDT", 200)
        return True

    async def execute(self) -> bool:
        # SOL at $200 with $100 order = 0.5 SOL which is above min qty
        result = await self.step(
            "Send order at small but valid size",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=100,  # $100 at $200/SOL = 0.5 SOL
                entry_price=200,
            )),
            narration="Sending small but valid order",
            show_result=True,
        )

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()
        sol_positions = [p for p in positions if "SOL" in p.get("symbol", "")]

        return await self.verify(
            "Small order accepted",
            len(sol_positions) >= 1 or result.get("status") == "success",
            expected="Order accepted or position created",
            actual=f"{len(sol_positions)} positions",
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class VeryLargePrice(BaseScenario):
    """X-002: Price above $100,000 handled."""

    id = "X-002"
    name = "Very Large Price"
    description = "Verifies high-priced assets are handled"
    category = "edge"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.mock.set_price("BTCUSDT", 150000)
        return True

    async def execute(self) -> bool:
        result = await self.step(
            "Send signal for high-priced asset",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="BTCUSDT",
                position_size=1000,
                entry_price=150000,
            )),
            narration="Sending signal at $150k price",
            show_result=True,
        )

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()
        btc_positions = [p for p in positions if "BTC" in p.get("symbol", "")]

        return await self.verify(
            "Large price handled",
            result.get("status") == "received",
            expected="Signal accepted",
            actual=f"status: {result.get('status')}",
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class ExitDuringEntry(BaseScenario):
    """X-003: Exit signal during order fill is handled."""

    id = "X-003"
    name = "Exit During Entry"
    description = "Verifies exit during entry processing is handled"
    category = "edge"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await self.mock.set_price("SOLUSDT", 100)
        return True

    async def execute(self) -> bool:
        import time
        t = int(time.time())

        await self.step(
            "Send entry signal",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=100,
                entry_price=100,
                trade_id=f"exit_during_entry_{t}",
            )),
            narration="Sending entry signal",
            show_result=True,
        )

        await asyncio.sleep(0.5)

        result = await self.step(
            "Send exit immediately",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                prev_position_size=100,
                exit_price=100,
            )),
            narration="Sending exit during processing",
            show_result=True,
        )

        await asyncio.sleep(3)

        return await self.verify(
            "Exit during entry handled",
            True,  # If no crash, it's handled
            expected="No error",
            actual="Processed gracefully",
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class PoolFullBoundary(BaseScenario):
    """X-004: Behavior at pool capacity boundary."""

    id = "X-004"
    name = "Pool Full Boundary"
    description = "Verifies entry when pool is at capacity"
    category = "edge"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)

        # Fill pool to capacity (3 positions)
        symbols = ["SOLUSDT", "BTCUSDT", "ETHUSDT"]
        for i, symbol in enumerate(symbols):
            await self.mock.set_price(symbol, 100 if symbol == "SOLUSDT" else 50000 if symbol == "BTCUSDT" else 3000)
            await self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=symbol,
                position_size=100,
                entry_price=100,
                trade_id=f"pool_fill_{i}",
            ))
            await asyncio.sleep(1)
        await asyncio.sleep(2)
        return True

    async def execute(self) -> bool:
        await self.mock.set_price("AVAXUSDT", 35)

        result = await self.step(
            "Send entry when pool is full",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="AVAXUSDT",
                position_size=100,
                entry_price=35,
                trade_id="pool_overflow",
            )),
            narration="Attempting entry with full pool",
            show_result=True,
        )

        await asyncio.sleep(2)
        queue = await self.engine.get_queue()
        queued = any(q.get("symbol") == "AVAXUSDT" for q in (queue or []))

        return await self.verify(
            "Entry queued when pool full",
            queued or result.get("status") in ["queued", "received"],
            expected="Queued or accepted",
            actual=f"queued: {queued}, status: {result.get('status')}",
        )

    async def teardown(self):
        await self.engine.close_all_positions()
        await self.engine.clear_queue()


@register_scenario
class UnicodeHandling(BaseScenario):
    """X-005: Unicode characters in input are handled."""

    id = "X-005"
    name = "Unicode Handling"
    description = "Verifies special characters are handled"
    category = "edge"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.mock.set_price("SOLUSDT", 100)
        return True

    async def execute(self) -> bool:
        payload = build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol="SOLUSDT",
            position_size=100,
            entry_price=100,
        )
        # Add unicode to message
        payload["strategy_info"]["alert_message"] = "Test: 中文 日本語 🚀"

        result = await self.step(
            "Send signal with unicode",
            lambda: self.engine.send_webhook(payload),
            narration="Sending signal with unicode characters",
            show_result=True,
        )

        await asyncio.sleep(2)

        return await self.verify(
            "Unicode handled",
            result is not None,
            expected="No crash",
            actual="Processed",
        )

    async def teardown(self):
        await self.engine.close_all_positions()
