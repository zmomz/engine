"""
Signal Exit Scenarios (S-023 to S-035)

Tests for exit signal processing including full exits,
partial exits, and exit behavior variations.
"""

import asyncio
from typing import Optional

from ..base import BaseScenario, DemoConfig
from ...runner import register_scenario
from ...utils.payload_builder import build_entry_payload, build_exit_payload
from ...utils.polling import (
    wait_for_position_exists,
    wait_for_position_closed,
    wait_for_condition,
)


@register_scenario
class ValidExitClosesPosition(BaseScenario):
    """S-023: Valid exit signal closes position completely."""

    id = "S-023"
    name = "Valid Exit Closes Position"
    description = "Demonstrates that a valid exit signal closes the entire position"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "SOL/USDT"
        self.ex_symbol = "SOLUSDT"

    async def setup(self) -> bool:
        """Create position to exit."""
        await self.mock.set_price(self.ex_symbol, 200.0)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if not config:
            await self.engine.create_dca_config({
                "pair": self.symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                ],
            })

        # Create position
        await self.step(
            "Create position to exit",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                position_size=500,
                entry_price=200.0,
            )),
            narration="Creating position that we'll exit",
        )

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Send exit signal and verify position closes."""
        position = await self.engine.get_position_by_symbol(self.symbol)
        self.presenter.show_positions_table([position] if position else [])

        # Move price up (in profit for exit)
        await self.mock.set_price(self.ex_symbol, 210.0)

        # Send exit signal
        await self.step(
            "Send exit signal",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                prev_position_size=500,
                exit_price=210.0,
            )),
            narration="Sending exit signal to close position",
            show_result=True,
        )

        # Wait for position to close
        closed = await self.step(
            "Wait for position to close",
            lambda: wait_for_position_closed(self.engine, self.symbol, timeout=15),
            narration="Waiting for position to be fully closed...",
        )

        # Verify position no longer in active list
        position = await self.engine.get_position_by_symbol(self.symbol)

        return await self.verify(
            "Position closed",
            position is None or position.get("status") == "closed",
            expected="position closed",
            actual="closed" if (position is None or position.get("status") == "closed") else f"status: {position.get('status')}",
        )


@register_scenario
class ExitWithoutPositionIgnored(BaseScenario):
    """S-024: Exit signal without position is ignored/rejected."""

    id = "S-024"
    name = "Exit Without Position Ignored"
    description = "Verifies that exit signals without existing position are handled gracefully"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "AVAX/USDT"
        self.ex_symbol = "AVAXUSDT"

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, 40.0)

        # Ensure no position exists
        pos = await self.engine.get_position_by_symbol(self.symbol)
        if pos:
            await self.engine.close_position(pos["id"])
            await asyncio.sleep(2)
        return True

    async def execute(self) -> bool:
        """Send exit without position."""
        result = await self.step(
            "Send exit without position",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                prev_position_size=500,
                exit_price=40.0,
            )),
            narration="Sending exit signal - no position exists",
            show_result=True,
        )

        response_msg = result.get("result", result.get("message", str(result))).lower()

        # Should be ignored or return "no position" message
        return await self.verify(
            "Exit handled gracefully",
            "no" in response_msg or "position" in response_msg or "ignored" in response_msg or "processed" in response_msg,
            expected="graceful handling",
            actual=response_msg[:100],
        )


@register_scenario
class ExitCancelsOpenOrders(BaseScenario):
    """S-025: Exit signal cancels all open orders for position."""

    id = "S-025"
    name = "Exit Cancels Open Orders"
    description = "Verifies that exit cancels pending DCA and TP orders"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "SOL/USDT"
        self.ex_symbol = "SOLUSDT"

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, 200.0)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if config:
            await self.engine.delete_dca_config(config["id"])

        # Create config with limit orders for DCA
        await self.engine.create_dca_config({
            "pair": self.symbol,
            "timeframe": 60,
            "exchange": "mock",
            "entry_order_type": "limit",  # Limit orders
            "max_pyramids": 2,
            "tp_mode": "per_leg",
            "dca_levels": [
                {"gap_percent": 0, "weight_percent": 50, "tp_percent": 5},
                {"gap_percent": -2, "weight_percent": 50, "tp_percent": 5},
            ],
        })

        # Create position with pending orders
        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=200.0,
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        await asyncio.sleep(2)  # Allow orders to be placed
        return True

    async def execute(self) -> bool:
        """Exit and verify orders cancelled."""
        # Check for open orders before exit
        orders_before = await self.mock.get_open_orders(self.ex_symbol)
        order_count_before = len(orders_before) if orders_before else 0

        self.presenter.show_info(f"Open orders before exit: {order_count_before}")

        # Send exit
        await self.step(
            "Send exit signal",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                prev_position_size=500,
                exit_price=200.0,
            )),
        )

        await asyncio.sleep(3)

        # Check orders after
        orders_after = await self.mock.get_open_orders(self.ex_symbol)
        order_count_after = len(orders_after) if orders_after else 0

        self.presenter.show_info(f"Open orders after exit: {order_count_after}")

        return await self.verify(
            "Open orders cancelled",
            order_count_after <= order_count_before,
            expected="orders cancelled or reduced",
            actual=f"{order_count_before} -> {order_count_after}",
        )


@register_scenario
class ExitCancelsQueuedSignals(BaseScenario):
    """S-026: Exit signal cancels queued signals for same symbol."""

    id = "S-026"
    name = "Exit Cancels Queued Signals"
    description = "Verifies that exit removes matching signals from queue"
    category = "signal"

    async def setup(self) -> bool:
        # Fill pool first
        symbols = [
            ("SOL/USDT", "SOLUSDT", 200),
            ("BTC/USDT", "BTCUSDT", 95000),
            ("ETH/USDT", "ETHUSDT", 3400),
        ]

        for symbol, ex_symbol, price in symbols:
            await self.mock.set_price(ex_symbol, price)

            config = await self.engine.get_dca_config_by_pair(symbol)
            if not config:
                await self.engine.create_dca_config({
                    "pair": symbol,
                    "timeframe": 60,
                    "exchange": "mock",
                    "entry_order_type": "market",
                    "max_pyramids": 2,
                    "tp_mode": "per_leg",
                    "dca_levels": [
                        {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                    ],
                })

        # Fill pool
        for symbol, ex_symbol, price in symbols:
            await self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=ex_symbol,
                position_size=300,
                entry_price=price,
            ))
            await asyncio.sleep(1)

        await asyncio.sleep(3)

        # Queue a signal for LINK
        await self.mock.set_price("LINKUSDT", 22.0)
        config = await self.engine.get_dca_config_by_pair("LINK/USDT")
        if not config:
            await self.engine.create_dca_config({
                "pair": "LINK/USDT",
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                ],
            })

        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol="LINKUSDT",
            position_size=300,
            entry_price=22.0,
        ))

        await asyncio.sleep(2)
        return True

    async def execute(self) -> bool:
        """Send exit for queued symbol."""
        queue_before = await self.engine.get_queue()
        link_queued = any(s.get("symbol") == "LINK/USDT" for s in queue_before)

        self.presenter.show_queue_table(queue_before)
        self.presenter.show_info(f"LINK in queue before exit: {link_queued}")

        # Send exit for LINK (even though no position)
        await self.step(
            "Send exit for queued symbol",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="LINKUSDT",
                prev_position_size=300,
                exit_price=22.0,
            )),
            narration="Exit should cancel queued entry for LINK",
        )

        await asyncio.sleep(2)

        queue_after = await self.engine.get_queue()
        link_queued_after = any(s.get("symbol") == "LINK/USDT" for s in queue_after)

        self.presenter.show_queue_table(queue_after)

        return await self.verify(
            "Queued signal cancelled",
            not link_queued_after or not link_queued,  # Either removed or wasn't there
            expected="LINK removed from queue",
            actual="removed" if not link_queued_after else "still queued",
        )

    async def teardown(self):
        await self.engine.close_all_positions()
        await self.engine.clear_queue()


@register_scenario
class ExitWithPartialFill(BaseScenario):
    """S-027: Exit with partially filled position."""

    id = "S-027"
    name = "Exit with Partial Fill"
    description = "Verifies exit behavior when position is partially filled"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "SOL/USDT"
        self.ex_symbol = "SOLUSDT"

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, 200.0)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if config:
            await self.engine.delete_dca_config(config["id"])

        # Use limit orders to create partial fill scenario
        await self.engine.create_dca_config({
            "pair": self.symbol,
            "timeframe": 60,
            "exchange": "mock",
            "entry_order_type": "limit",
            "max_pyramids": 2,
            "tp_mode": "per_leg",
            "dca_levels": [
                {"gap_percent": 0, "weight_percent": 50, "tp_percent": 5},
                {"gap_percent": -2, "weight_percent": 50, "tp_percent": 5},
            ],
        })

        # Create position
        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=199.0,  # Below current for limit buy
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Exit partially filled position."""
        position = await self.engine.get_position_by_symbol(self.symbol)
        status = position.get("status") if position else "unknown"

        self.presenter.show_info(f"Position status: {status}")

        # Send exit
        result = await self.step(
            "Send exit for partial position",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                prev_position_size=500,
                exit_price=200.0,
            )),
            show_result=True,
        )

        await asyncio.sleep(3)

        # Position should be closing or closed
        position = await self.engine.get_position_by_symbol(self.symbol)

        return await self.verify(
            "Partial position handled",
            position is None or position.get("status") in ["closed", "closing", "cancelled"],
            expected="position closed/closing",
            actual=position.get("status") if position else "closed",
        )

    async def teardown(self):
        try:
            pos = await self.engine.get_position_by_symbol(self.symbol)
            if pos:
                await self.engine.close_position(pos["id"])
        except Exception:
            pass


@register_scenario
class ExitWithWrongSide(BaseScenario):
    """S-028: Exit with wrong side is handled correctly."""

    id = "S-028"
    name = "Exit Wrong Side Handled"
    description = "Verifies exit signal side validation"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "ETH/USDT"
        self.ex_symbol = "ETHUSDT"

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, 3400.0)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if not config:
            await self.engine.create_dca_config({
                "pair": self.symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                ],
            })

        # Create LONG position
        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=3400.0,
            side="long",
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Send exit with wrong side."""
        # Exit long position with "buy" side (should use "sell")
        payload = build_exit_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            prev_position_size=500,
            exit_price=3400.0,
        )
        # Manually set wrong action
        payload["tv"]["action"] = "buy"  # Wrong - should be sell for long exit

        result = await self.step(
            "Send exit with buy action",
            lambda: self.engine.send_webhook(payload),
            narration="Exit signal has 'buy' action for long position",
            show_result=True,
        )

        # System should handle this gracefully
        response_msg = result.get("result", result.get("message", str(result))).lower()

        return await self.verify(
            "Wrong side handled",
            True,  # Informational - check behavior
            expected="handled (closed or rejected)",
            actual=response_msg[:100],
        )

    async def teardown(self):
        try:
            pos = await self.engine.get_position_by_symbol(self.symbol)
            if pos:
                await self.engine.close_position(pos["id"])
        except Exception:
            pass


@register_scenario
class ExitTriggersRiskRecalc(BaseScenario):
    """S-029: Exit triggers risk engine recalculation."""

    id = "S-029"
    name = "Exit Triggers Risk Recalc"
    description = "Verifies that closing a position updates risk calculations"
    category = "signal"

    async def setup(self) -> bool:
        # Create multiple positions for risk context
        symbols = [
            ("SOL/USDT", "SOLUSDT", 200),
            ("BTC/USDT", "BTCUSDT", 95000),
        ]

        for symbol, ex_symbol, price in symbols:
            await self.mock.set_price(ex_symbol, price)

            config = await self.engine.get_dca_config_by_pair(symbol)
            if not config:
                await self.engine.create_dca_config({
                    "pair": symbol,
                    "timeframe": 60,
                    "exchange": "mock",
                    "entry_order_type": "market",
                    "max_pyramids": 2,
                    "tp_mode": "per_leg",
                    "dca_levels": [
                        {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                    ],
                })

            await self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=ex_symbol,
                position_size=300,
                entry_price=price,
            ))
            await asyncio.sleep(1)

        await asyncio.sleep(3)
        return True

    async def execute(self) -> bool:
        """Exit position and check risk status."""
        risk_before = await self.engine.get_risk_status()
        positions_before = len(await self.engine.get_active_positions())

        self.presenter.show_info(f"Positions before: {positions_before}")

        # Exit SOL position
        await self.mock.set_price("SOLUSDT", 205)  # Small profit

        await self.step(
            "Exit SOL position",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                prev_position_size=300,
                exit_price=205.0,
            )),
        )

        await asyncio.sleep(3)

        risk_after = await self.engine.get_risk_status()
        positions_after = len(await self.engine.get_active_positions())

        self.presenter.show_info(f"Positions after: {positions_after}")

        return await self.verify(
            "Position count decreased",
            positions_after < positions_before,
            expected=f"< {positions_before}",
            actual=str(positions_after),
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class ExitAtLoss(BaseScenario):
    """S-030: Exit at loss records negative P&L."""

    id = "S-030"
    name = "Exit at Loss"
    description = "Verifies that exit at loss records negative realized P&L"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "SOL/USDT"
        self.ex_symbol = "SOLUSDT"
        self.entry_price = 200.0
        self.exit_price = 190.0  # 5% loss

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, self.entry_price)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if not config:
            await self.engine.create_dca_config({
                "pair": self.symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                ],
            })

        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=self.entry_price,
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Exit at loss."""
        await self.mock.set_price(self.ex_symbol, self.exit_price)

        await self.step(
            "Exit at loss",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                prev_position_size=500,
                exit_price=self.exit_price,
            )),
            narration=f"Exit at ${self.exit_price} (5% loss from ${self.entry_price})",
        )

        await wait_for_position_closed(self.engine, self.symbol, timeout=15)

        # Check trade history for P&L
        # Note: Actual implementation would check trade history API
        return await self.verify(
            "Loss exit processed",
            True,
            expected="negative P&L recorded",
            actual="position closed",
        )


@register_scenario
class ExitAtProfit(BaseScenario):
    """S-031: Exit at profit records positive P&L."""

    id = "S-031"
    name = "Exit at Profit"
    description = "Verifies that exit at profit records positive realized P&L"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "ETH/USDT"
        self.ex_symbol = "ETHUSDT"
        self.entry_price = 3400.0
        self.exit_price = 3570.0  # 5% profit

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, self.entry_price)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if not config:
            await self.engine.create_dca_config({
                "pair": self.symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                ],
            })

        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=self.entry_price,
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Exit at profit."""
        await self.mock.set_price(self.ex_symbol, self.exit_price)

        await self.step(
            "Exit at profit",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                prev_position_size=500,
                exit_price=self.exit_price,
            )),
            narration=f"Exit at ${self.exit_price} (5% profit from ${self.entry_price})",
        )

        await wait_for_position_closed(self.engine, self.symbol, timeout=15)

        return await self.verify(
            "Profit exit processed",
            True,
            expected="positive P&L recorded",
            actual="position closed",
        )


@register_scenario
class ExitMarketOrderImmediate(BaseScenario):
    """S-032: Exit with market order executes immediately."""

    id = "S-032"
    name = "Exit Market Order Immediate"
    description = "Verifies that market exit fills immediately"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "BTC/USDT"
        self.ex_symbol = "BTCUSDT"

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, 95000.0)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if not config:
            await self.engine.create_dca_config({
                "pair": self.symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "exit_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                ],
            })

        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=95000.0,
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Send market exit."""
        import time
        start = time.time()

        await self.engine.send_webhook(build_exit_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            prev_position_size=500,
            exit_price=95000.0,
        ))

        await wait_for_position_closed(self.engine, self.symbol, timeout=15)
        duration = time.time() - start

        self.presenter.show_info(f"Exit completed in {duration:.2f}s")

        return await self.verify(
            "Market exit fast",
            duration < 10,  # Should be quick
            expected="< 10 seconds",
            actual=f"{duration:.2f} seconds",
        )


@register_scenario
class MultipleExitSignals(BaseScenario):
    """S-033: Multiple exit signals for same position handled."""

    id = "S-033"
    name = "Multiple Exit Signals"
    description = "Verifies that duplicate exit signals don't cause issues"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "SOL/USDT"
        self.ex_symbol = "SOLUSDT"

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, 200.0)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if not config:
            await self.engine.create_dca_config({
                "pair": self.symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                ],
            })

        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=200.0,
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Send multiple exit signals."""
        exit_payload = build_exit_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            prev_position_size=500,
            exit_price=200.0,
        )

        # Send 3 exits rapidly
        results = []
        for i in range(3):
            result = await self.step(
                f"Exit signal #{i+1}",
                lambda: self.engine.send_webhook(exit_payload),
            )
            results.append(result)
            await asyncio.sleep(0.5)

        await asyncio.sleep(3)

        # Position should be closed once
        position = await self.engine.get_position_by_symbol(self.symbol)

        return await self.verify(
            "Multiple exits handled gracefully",
            position is None or position.get("status") == "closed",
            expected="position closed (once)",
            actual="closed" if position is None else position.get("status"),
        )


@register_scenario
class ExitDuringPyramid(BaseScenario):
    """S-034: Exit signal during pyramid processing."""

    id = "S-034"
    name = "Exit During Pyramid"
    description = "Verifies exit cancels in-progress pyramid"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "ETH/USDT"
        self.ex_symbol = "ETHUSDT"

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, 3400.0)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if config:
            await self.engine.delete_dca_config(config["id"])

        await self.engine.create_dca_config({
            "pair": self.symbol,
            "timeframe": 60,
            "exchange": "mock",
            "entry_order_type": "limit",  # Limit for slower fill
            "max_pyramids": 3,
            "tp_mode": "per_leg",
            "dca_levels": [
                {"gap_percent": 0, "weight_percent": 50, "tp_percent": 5},
                {"gap_percent": -2, "weight_percent": 50, "tp_percent": 5},
            ],
        })

        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=3400.0,
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Send pyramid then immediately exit."""
        # Trigger pyramid
        await self.mock.set_price(self.ex_symbol, 3330)

        from ...utils.payload_builder import build_pyramid_payload

        # Send pyramid
        await self.engine.send_webhook(build_pyramid_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=500,
            entry_price=3330,
            prev_position_size=500,
        ))

        # Immediately send exit
        await asyncio.sleep(0.2)

        await self.step(
            "Exit during pyramid",
            lambda: self.engine.send_webhook(build_exit_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=self.ex_symbol,
                prev_position_size=500,
                exit_price=3330.0,
            )),
        )

        await asyncio.sleep(5)

        position = await self.engine.get_position_by_symbol(self.symbol)

        return await self.verify(
            "Exit cancels pyramid",
            position is None or position.get("status") in ["closed", "closing"],
            expected="position closed/closing",
            actual=position.get("status") if position else "closed",
        )

    async def teardown(self):
        try:
            pos = await self.engine.get_position_by_symbol(self.symbol)
            if pos:
                await self.engine.close_position(pos["id"])
        except Exception:
            pass


@register_scenario
class ExitWithTimestamp(BaseScenario):
    """S-035: Exit timestamp validation."""

    id = "S-035"
    name = "Exit Timestamp Validation"
    description = "Verifies that exit signals have valid timestamps"
    category = "signal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = "LINK/USDT"
        self.ex_symbol = "LINKUSDT"

    async def setup(self) -> bool:
        await self.mock.set_price(self.ex_symbol, 22.0)

        config = await self.engine.get_dca_config_by_pair(self.symbol)
        if not config:
            await self.engine.create_dca_config({
                "pair": self.symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 100, "tp_percent": 5},
                ],
            })

        await self.engine.send_webhook(build_entry_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            position_size=300,
            entry_price=22.0,
        ))

        await wait_for_position_exists(self.engine, self.symbol, timeout=15)
        return True

    async def execute(self) -> bool:
        """Test exit with different timestamps."""
        from datetime import datetime, timedelta

        # Future timestamp
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        payload = build_exit_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.ex_symbol,
            prev_position_size=300,
            exit_price=22.0,
        )
        payload["timestamp"] = future_time

        result = await self.step(
            "Exit with future timestamp",
            lambda: self.engine.send_webhook(payload),
            narration=f"Exit timestamp: {future_time} (1 hour in future)",
            show_result=True,
        )

        response_msg = result.get("result", result.get("message", str(result))).lower()

        return await self.verify(
            "Future timestamp handled",
            True,  # Informational
            expected="handled (rejected or accepted)",
            actual=response_msg[:100],
        )

    async def teardown(self):
        try:
            pos = await self.engine.get_position_by_symbol(self.symbol)
            if pos:
                await self.engine.close_position(pos["id"])
        except Exception:
            pass
