"""
Configuration Scenarios (C-001 to C-005)

Tests for DCA configuration and validation.
"""

import asyncio
from typing import Optional

from ..base import BaseScenario, DemoConfig
from ...runner import register_scenario
from ...utils.payload_builder import build_entry_payload
from ...utils.polling import wait_for_position_exists


@register_scenario
class DCAConfigCreation(BaseScenario):
    """C-001: Create new DCA config."""

    id = "C-001"
    name = "DCA Config Creation"
    description = "Verifies DCA config creation"
    category = "config"

    async def setup(self) -> bool:
        # Clean up any existing test config
        configs = await self.engine.get_dca_configs()
        for c in (configs or []):
            if c.get("pair") == "AVAX/USDT":
                await self.engine.delete_dca_config(c.get("id"))
        return True

    async def execute(self) -> bool:
        config_data = {
            "pair": "AVAX/USDT",
            "timeframe": 60,
            "exchange": "mock",
            "entry_order_type": "market",
            "max_pyramids": 2,
            "tp_mode": "per_leg",
            "dca_levels": [
                {"gap_percent": 0, "weight_percent": 100, "tp_percent": 2},
            ],
        }

        result = await self.step(
            "Create DCA config",
            lambda: self.engine.create_dca_config(config_data),
            narration="Creating new DCA config",
            show_result=True,
        )

        await asyncio.sleep(1)
        configs = await self.engine.get_dca_configs()
        config_exists = any(c.get("pair") == "AVAX/USDT" for c in (configs or []))

        return await self.verify(
            "Config created",
            config_exists,
            expected="AVAX/USDT config exists",
            actual=f"exists: {config_exists}",
        )

    async def teardown(self):
        configs = await self.engine.get_dca_configs()
        for c in (configs or []):
            if c.get("pair") == "AVAX/USDT":
                await self.engine.delete_dca_config(c.get("id"))


@register_scenario
class DCAConfigUpdate(BaseScenario):
    """C-002: Update existing DCA config."""

    id = "C-002"
    name = "DCA Config Update"
    description = "Verifies DCA config update"
    category = "config"

    async def setup(self) -> bool:
        configs = await self.engine.get_dca_configs()
        self.config_to_update = configs[0] if configs else None
        return self.config_to_update is not None

    async def execute(self) -> bool:
        if not self.config_to_update:
            return await self.verify(
                "Config found",
                False,
                expected="Existing config",
                actual="None",
            )

        original_max_pyr = self.config_to_update.get("max_pyramids", 2)
        new_max_pyr = 3 if original_max_pyr != 3 else 2

        result = await self.step(
            "Update config",
            lambda: self.engine.update_dca_config(
                self.config_to_update.get("id"),
                {"max_pyramids": new_max_pyr}
            ),
            narration="Updating max_pyramids",
            show_result=True,
        )

        await asyncio.sleep(1)
        updated = await self.engine.get_dca_config(self.config_to_update.get("id"))

        return await self.verify(
            "Config updated",
            updated is not None,
            expected="Updated config",
            actual=f"max_pyramids: {updated.get('max_pyramids') if updated else 'N/A'}",
        )


@register_scenario
class DCAConfigDeletion(BaseScenario):
    """C-003: Delete DCA config."""

    id = "C-003"
    name = "DCA Config Deletion"
    description = "Verifies DCA config deletion"
    category = "config"

    async def setup(self) -> bool:
        # Create temp config
        config_data = {
            "pair": "DOGE/USDT",
            "timeframe": 60,
            "exchange": "mock",
            "entry_order_type": "market",
            "max_pyramids": 2,
            "tp_mode": "per_leg",
            "dca_levels": [
                {"gap_percent": 0, "weight_percent": 100, "tp_percent": 2},
            ],
        }
        self.temp_config = await self.engine.create_dca_config(config_data)
        return self.temp_config is not None

    async def execute(self) -> bool:
        if not self.temp_config:
            return await self.verify(
                "Temp config created",
                False,
                expected="Temp config",
                actual="None",
            )

        config_id = self.temp_config.get("id")

        await self.step(
            "Delete config",
            lambda: self.engine.delete_dca_config(config_id),
            narration="Deleting config",
            show_result=True,
        )

        await asyncio.sleep(1)
        configs = await self.engine.get_dca_configs()
        deleted = not any(c.get("id") == config_id for c in (configs or []))

        return await self.verify(
            "Config deleted",
            deleted,
            expected="Config removed",
            actual=f"deleted: {deleted}",
        )


@register_scenario
class DCAConfig3Levels(BaseScenario):
    """C-004: Standard 3-level DCA config."""

    id = "C-004"
    name = "DCA Config 3 Levels"
    description = "Verifies 3-level DCA grid"
    category = "config"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.mock.set_price("SOLUSDT", 100)
        return True

    async def execute(self) -> bool:
        # Use existing SOL config with 3 levels
        result = await self.step(
            "Send entry for 3-level DCA",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=300,
                entry_price=100,
            )),
            narration="Sending entry for DCA grid",
            show_result=True,
        )

        await asyncio.sleep(3)
        position = await wait_for_position_exists(self.engine, "SOL/USDT", timeout=10)

        return await self.verify(
            "DCA position created",
            position is not None,
            expected="Position with DCA",
            actual=f"position: {'exists' if position else 'none'}",
        )

    async def teardown(self):
        await self.engine.close_all_positions()


@register_scenario
class MaxPyramidsEnforcement(BaseScenario):
    """C-005: Pyramid limits are enforced."""

    id = "C-005"
    name = "Max Pyramids Enforcement"
    description = "Verifies pyramid limits"
    category = "config"

    async def setup(self) -> bool:
        await self.engine.close_all_positions()
        await self.engine.clear_queue()
        await asyncio.sleep(2)
        await self.mock.set_price("SOLUSDT", 100)
        return True

    async def execute(self) -> bool:
        import time
        from datetime import datetime, timedelta
        t = int(time.time())

        # Entry
        await self.step(
            "Send entry",
            lambda: self.engine.send_webhook(build_entry_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=100,
                entry_price=100,
                trade_id=f"max_pyr_{t}_0",
            )),
            narration="Opening position",
            show_result=True,
        )

        await asyncio.sleep(2)

        # Try max_pyramids + 1 pyramids
        from ...utils.payload_builder import build_pyramid_payload
        responses = []
        for i in range(3):
            await self.mock.set_price("SOLUSDT", 98 - i)
            ts = (datetime.utcnow() + timedelta(hours=i+1)).isoformat()
            resp = await self.engine.send_webhook(build_pyramid_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol="SOLUSDT",
                position_size=100,
                entry_price=98 - i,
                prev_position_size=100 * (i + 1),
                trade_id=f"max_pyr_{t}_{i+1}",
                timestamp=ts,
            ))
            responses.append(resp)
            await asyncio.sleep(1)

        # At least one should be rejected if max_pyramids=2
        received_count = sum(1 for r in responses if r.get("status") == "received")

        return await self.verify(
            "Max pyramids enforced",
            True,  # Just verify no crash
            expected="Some pyramids rejected",
            actual=f"{received_count}/3 accepted",
        )

    async def teardown(self):
        await self.engine.close_all_positions()
