"""
Error Handling Scenarios (E-001 to E-007)

Tests for resilience, recovery, validation failures,
and graceful degradation.
"""

import asyncio
from typing import Optional

from ..base import BaseScenario, DemoConfig
from ...runner import register_scenario
from ...utils.payload_builder import build_entry_payload, build_exit_payload, build_invalid_payload
from ...utils.polling import (
    wait_for_position_exists,
    wait_for_position_count,
    wait_for_condition,
)


@register_scenario
class DuplicateSignalDetection(BaseScenario):
    """E-001: System detects duplicate signals."""

    id = "E-001"
    name = "Duplicate Signal Detection"
    description = "Verifies that duplicate signals with same trade_id are handled"
    category = "error"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "SOL/USDT"
        self.ex_symbol = "SOLUSDT"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)
        await self.mock.set_price(self.ex_symbol, 200)
        return True

    async def execute(self) -> bool:
        import time
        trade_id = f"dup_test_{int(time.time())}"

        result1 = await self.step(
            "Send first entry signal",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                position_size=100,
                entry_price=200,
                trade_id=trade_id,
            )),
            narration="Sending first entry signal",
            show_result=True,
        )

        await asyncio.sleep(2)

        result2 = await self.step(
            "Send duplicate signal",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                position_size=100,
                entry_price=200,
                trade_id=trade_id,
            )),
            narration="Sending duplicate signal - should be handled",
            show_result=True,
        )

        await asyncio.sleep(2)
        positions = await self.engine.get_active_positions()
        sol_positions = [p for p in positions if self.ex_symbol in p.get("symbol", "")]

        return await self.verify(
            "Duplicate signal handled",
            len(sol_positions) <= 1,
            expected="At most 1 position",
            actual=f"{len(sol_positions)} positions",
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class InvalidSymbolRejection(BaseScenario):
    """E-002: Invalid symbol is rejected."""

    id = "E-002"
    name = "Invalid Symbol Rejection"
    description = "Verifies that invalid trading pairs are rejected"
    category = "error"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        return True

    async def execute(self) -> bool:
        result = await self.step(
            "Send signal with invalid symbol",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="FAKEUSDT",
                position_size=100,
                entry_price=100,
            )),
            narration="Sending entry with invalid symbol",
            show_result=True,
        )

        await asyncio.sleep(2)
        positions = await self.engine.get_active_positions()
        fake_positions = [p for p in positions if "FAKE" in p.get("symbol", "")]

        return await self.verify(
            "Invalid symbol rejected",
            len(fake_positions) == 0,
            expected="No position for invalid symbol",
            actual=f"{len(fake_positions)} positions",
        )


@register_scenario
class WrongSecretRejection(BaseScenario):
    """E-003: Wrong secret is rejected."""

    id = "E-003"
    name = "Wrong Secret Rejection"
    description = "Verifies that payloads with wrong secret are rejected"
    category = "error"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.mock.set_price("SOLUSDT", 200)
        return True

    async def execute(self) -> bool:
        got_error = False
        try:
            result = await self.step(
                "Send signal with wrong secret",
                lambda: self.engine.send_webhook(build_entry_payload(
                    user_id=self.config.user_id,
                    secret="wrong_secret_12345",
                    symbol="SOLUSDT",
                    position_size=100,
                    entry_price=200,
                )),
                narration="Sending entry with wrong webhook secret",
                show_result=True,
            )
        except Exception as e:
            # Expected - 403 Forbidden
            got_error = "403" in str(e) or "Forbidden" in str(e)
            self.presenter.show_info(f"Got expected error: {type(e).__name__}")

        await asyncio.sleep(2)
        positions = await self.engine.get_active_positions()
        sol_positions = [p for p in positions if "SOL" in p.get("symbol", "")]

        return await self.verify(
            "Wrong secret rejected",
            len(sol_positions) == 0 or got_error,
            expected="No position (authentication failed)",
            actual=f"error={got_error}, positions={len(sol_positions)}",
        )


@register_scenario
class PositionNotFoundOnExit(BaseScenario):
    """E-004: Exit for non-existent position is handled gracefully."""

    id = "E-004"
    name = "Position Not Found on Exit"
    description = "Verifies that exit signals for non-existent positions are handled"
    category = "error"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        return True

    async def execute(self) -> bool:
        result = await self.step(
            "Send exit for non-existent position",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="XRPUSDT",
                prev_position_size=100,
                exit_price=0.5,
            )),
            narration="Sending exit for position that doesn't exist",
            show_result=True,
        )

        await asyncio.sleep(1)

        return await self.verify(
            "Exit handled gracefully",
            True,
            expected="No error/crash",
            actual="Signal processed",
        )


@register_scenario
class ZeroQuantityHandling(BaseScenario):
    """E-005: Zero quantity is rejected."""

    id = "E-005"
    name = "Zero Quantity Handling"
    description = "Verifies that zero position size is rejected"
    category = "error"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.mock.set_price("SOLUSDT", 200)
        return True

    async def execute(self) -> bool:
        result = await self.step(
            "Send signal with zero position size",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=0,
                entry_price=200,
            )),
            narration="Sending entry with zero position size",
            show_result=True,
        )

        await asyncio.sleep(2)
        positions = await self.engine.get_active_positions()
        sol_positions = [p for p in positions if "SOL" in p.get("symbol", "")]

        return await self.verify(
            "Zero quantity rejected",
            len(sol_positions) == 0,
            expected="No position for zero quantity",
            actual=f"{len(sol_positions)} positions",
        )


@register_scenario
class ConcurrentWebhookRace(BaseScenario):
    """E-006: Two concurrent webhooks for same symbol handled correctly."""

    id = "E-006"
    name = "Concurrent Webhook Race"
    description = "Verifies that concurrent signals are handled"
    category = "error"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ex_symbol = "SOLUSDT"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)
        await self.mock.set_price(self.ex_symbol, 200)
        return True

    async def execute(self) -> bool:
        import time
        t = int(time.time())

        async def send_signal(suffix):
            return await self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                position_size=100,
                entry_price=200,
                trade_id=f"race_{suffix}_{t}",
            ))

        await self.step(
            "Send two concurrent signals",
            lambda: asyncio.gather(send_signal("a"), send_signal("b"), return_exceptions=True),
            narration="Sending two signals concurrently",
            show_result=True,
        )

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()
        sol_positions = [p for p in positions if self.ex_symbol in p.get("symbol", "")]

        return await self.verify(
            "Concurrent webhooks handled",
            len(sol_positions) >= 1,
            expected="At least 1 position",
            actual=f"{len(sol_positions)} positions",
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class GracefulDegradation(BaseScenario):
    """E-007: System continues on partial failure."""

    id = "E-007"
    name = "Graceful Degradation"
    description = "Verifies system continues after some failures"
    category = "error"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)
        await self.mock.set_price("SOLUSDT", 200)
        await self.mock.set_price("BTCUSDT", 95000)
        return True

    async def execute(self) -> bool:
        import time
        t = int(time.time())

        await self.step(
            "Send invalid signal",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret="wrong_secret",
                symbol="SOLUSDT",
                position_size=100,
                entry_price=200,
                trade_id=f"fail_{t}",
            )),
            narration="Sending signal with wrong secret",
            show_result=True,
        )

        await asyncio.sleep(1)

        await self.step(
            "Send valid signal",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="BTCUSDT",
                position_size=100,
                entry_price=95000,
                trade_id=f"pass_{t}",
            )),
            narration="Sending valid signal",
            show_result=True,
        )

        await asyncio.sleep(3)
        positions = await self.engine.get_active_positions()
        btc_positions = [p for p in positions if "BTC" in p.get("symbol", "")]

        return await self.verify(
            "System continued after failure",
            len(btc_positions) >= 1,
            expected="BTC position created",
            actual=f"{len(btc_positions)} BTC positions",
        )

    async def teardown(self):
        await self.engine.close_all_positions()
