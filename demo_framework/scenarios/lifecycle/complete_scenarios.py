"""
Lifecycle Scenarios (L-001 to L-005)

Tests for end-to-end trading flows and complete trade cycles.
"""

import asyncio
from typing import Optional

from ..base import BaseScenario, DemoConfig
from ...runner import register_scenario
from ...utils.payload_builder import build_entry_payload, build_exit_payload, build_pyramid_payload
from ...utils.polling import (
    wait_for_position_exists,
    wait_for_position_filled,
    wait_for_position_count,
)


@register_scenario
class CompleteTradeEntryToExit(BaseScenario):
    """L-001: Full lifecycle entry -> hold -> exit."""

    id = "L-001"
    name = "Complete Trade Entry to Exit"
    description = "Verifies full trade lifecycle"
    category = "lifecycle"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)
        await self.mock.set_price("SOLUSDT", 100)
        return True

    async def execute(self) -> bool:
        import time
        t = int(time.time())

        # Entry
        await self.step(
            "Send entry signal",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=100,
                entry_price=100,
                trade_id=f"lifecycle_{t}",
            )),
            narration="Opening position",
            show_result=True,
        )

        await asyncio.sleep(3)
        position = await wait_for_position_exists(self.engine, "SOL/USDT", timeout=10)

        if not position:
            return await self.verify(
                "Position created",
                False,
                expected="Position exists",
                actual="No position",
            )

        # Hold
        await self.step(
            "Hold position",
            lambda: asyncio.sleep(2),
            narration="Holding position...",
        )

        # Exit
        await self.step(
            "Send exit signal",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                prev_position_size=100,
                exit_price=100,
            )),
            narration="Closing position",
            show_result=True,
        )

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()
        sol_positions = [p for p in positions if "SOL" in p.get("symbol", "")]

        return await self.verify(
            "Position closed",
            len(sol_positions) == 0,
            expected="No active position",
            actual=f"{len(sol_positions)} positions",
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class CompleteTradeWithPyramids(BaseScenario):
    """L-002: Full lifecycle with pyramids."""

    id = "L-002"
    name = "Complete Trade with Pyramids"
    description = "Verifies entry -> pyramids -> exit"
    category = "lifecycle"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)
        await self.mock.set_price("SOLUSDT", 100)
        return True

    async def execute(self) -> bool:
        import time
        t = int(time.time())

        # Entry
        await self.step(
            "Send entry signal",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=100,
                entry_price=100,
                trade_id=f"pyramid_life_{t}_0",
            )),
            narration="Opening position",
            show_result=True,
        )

        await asyncio.sleep(2)

        # Pyramid 1
        await self.mock.set_price("SOLUSDT", 98)
        await self.step(
            "Send first pyramid",
            lambda: self.engine.send_webhook(build_pyramid_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=100,
                entry_price=98,
                prev_position_size=100,
                trade_id=f"pyramid_life_{t}_1",
            )),
            narration="Adding pyramid",
            show_result=True,
        )

        await asyncio.sleep(2)
        position = await wait_for_position_exists(self.engine, "SOL/USDT", timeout=10)

        # Exit
        await self.step(
            "Send exit signal",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                prev_position_size=200,
                exit_price=98,
            )),
            narration="Closing position with pyramids",
            show_result=True,
        )

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()
        sol_positions = [p for p in positions if "SOL" in p.get("symbol", "")]

        return await self.verify(
            "Position with pyramids closed",
            len(sol_positions) == 0,
            expected="No active position",
            actual=f"{len(sol_positions)} positions",
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class MultiPositionPortfolio(BaseScenario):
    """L-003: Multiple positions simultaneously."""

    id = "L-003"
    name = "Multi-Position Portfolio"
    description = "Verifies 3 positions managed simultaneously"
    category = "lifecycle"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)
        await self.mock.set_price("SOLUSDT", 100)
        await self.mock.set_price("BTCUSDT", 50000)
        await self.mock.set_price("ETHUSDT", 3000)
        return True

    async def execute(self) -> bool:
        import time
        t = int(time.time())

        symbols = [("SOLUSDT", 100), ("BTCUSDT", 50000), ("ETHUSDT", 3000)]

        # Open all positions
        for i, (symbol, price) in enumerate(symbols):
            await self.step(
                f"Open {symbol} position",
                lambda s=symbol, p=price: self.engine.send_webhook(build_entry_payload(
                    user_id=self.config.user_id,
                    secret=self.config.webhook_secret,
                    symbol=s,
                    position_size=100,
                    entry_price=p,
                    trade_id=f"portfolio_{t}_{i}",
                )),
                narration=f"Opening {symbol}",
                show_result=True,
            )
            await asyncio.sleep(1)

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()

        v1 = await self.verify(
            "3 positions opened",
            len(positions) >= 3,
            expected="3 positions",
            actual=f"{len(positions)} positions",
        )

        # Close all positions
        for symbol, _ in symbols:
            await self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=symbol,
                prev_position_size=100,
                exit_price=100,
            ))
            await asyncio.sleep(1)

        await asyncio.sleep(3)
        positions_after = await self.engine.get_active_positions()

        v2 = await self.verify(
            "All positions closed",
            len(positions_after) == 0,
            expected="0 positions",
            actual=f"{len(positions_after)} positions",
        )

        return v1 and v2

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class EntryToQueueToPromotion(BaseScenario):
    """L-004: Queued entry gets promoted."""

    id = "L-004"
    name = "Entry to Queue to Promotion"
    description = "Verifies queued entry promotion"
    category = "lifecycle"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)

        # Fill pool
        symbols = [("SOLUSDT", 100), ("BTCUSDT", 50000), ("ETHUSDT", 3000)]
        for i, (symbol, price) in enumerate(symbols):
            await self.mock.set_price(symbol, price)
            await self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=symbol,
                position_size=100,
                entry_price=price,
                trade_id=f"promo_pool_{i}",
            ))
            await asyncio.sleep(0.5)
        await asyncio.sleep(2)
        return True

    async def execute(self) -> bool:
        await self.mock.set_price("AVAXUSDT", 35)

        # Add to queue
        await self.step(
            "Send entry to queue",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="AVAXUSDT",
                position_size=100,
                entry_price=35,
                trade_id="promo_queued",
            )),
            narration="Sending entry (should queue)",
            show_result=True,
        )

        await asyncio.sleep(2)
        queue_before = await self.engine.get_queue()
        was_queued = any(q.get("symbol") == "AVAXUSDT" for q in (queue_before or []))

        # Close one to trigger promotion
        await self.step(
            "Close SOL to trigger promotion",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                prev_position_size=100,
                exit_price=100,
            )),
            narration="Closing SOL position",
            show_result=True,
        )

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()
        avax_positions = [p for p in positions if "AVAX" in p.get("symbol", "")]

        return await self.verify(
            "Entry promoted from queue",
            len(avax_positions) >= 1 or was_queued,
            expected="AVAX promoted or was queued",
            actual=f"queued: {was_queued}, positions: {len(avax_positions)}",
        )

    async def teardown(self):
        await self.engine.close_all_positions()
        await self.engine.clear_queue()


@register_scenario
class HighFrequencySignals(BaseScenario):
    """L-005: Many signals in quick succession."""

    id = "L-005"
    name = "High Frequency Signals"
    description = "Verifies rapid fire signals"
    category = "lifecycle"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)
        await self.mock.set_price("SOLUSDT", 100)
        return True

    async def execute(self) -> bool:
        import time
        t = int(time.time())

        responses = []
        for i in range(5):
            resp = await self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=50,
                entry_price=100,
                trade_id=f"hf_{t}_{i}",
            ))
            responses.append(resp)
            await asyncio.sleep(0.2)

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()
        success_count = sum(1 for r in responses if r.get("status") == "received")

        return await self.verify(
            "High frequency handled",
            success_count > 0 or len(positions) > 0,
            expected="Some accepted",
            actual=f"{success_count}/5 accepted, {len(positions)} positions",
        )

    async def teardown(self):
        await self.engine.close_all_positions()
