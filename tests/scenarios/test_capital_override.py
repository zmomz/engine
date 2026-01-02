"""
Group C Tests: Capital Override

Tests scenarios where position size comes from DCA config (use_custom_capital=True)
instead of the TradingView signal's order_size.

Key verification:
- Order quantities calculated from custom_capital_usd / price / num_levels
- Signal's order_size is ignored when use_custom_capital=True
"""

import pytest
import uuid
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid

from .fixtures import (
    ScenarioConfig,
    EntryType,
    QuantitySource,
    TPMode,
    SCENARIO_C1, SCENARIO_C2, SCENARIO_C3, SCENARIO_C4,
    SCENARIO_C5, SCENARIO_C6, SCENARIO_C7, SCENARIO_C8,
    GROUP_C_SCENARIOS,
    create_dca_grid_config,
    create_mock_signal,
    create_position_group,
    create_dca_order,
    create_pyramid,
    calculate_expected_outcome
)


class TestCapitalOverrideScenarios:
    """Test class for capital override scenarios."""

    @pytest.mark.asyncio
    async def test_c1_limit_override_single_pyramid_single_level_perleg(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        C1: Limit entry, capital override, single pyramid, single level, per_leg TP.

        Expected:
        - Order quantity calculated from custom_capital_usd ($300) not signal ($500)
        - Quantity = $300 / price = 3.0 (at $100 price)
        """
        scenario = SCENARIO_C1
        expected = calculate_expected_outcome(scenario)

        # Verify config has capital override enabled
        config = create_dca_grid_config(scenario)
        assert config.use_custom_capital is True
        assert config.custom_capital_usd == scenario.custom_capital_usd

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)

        # Calculate expected quantity from override capital
        expected_qty = scenario.custom_capital_usd / scenario.base_price
        # Order quantity should match (approximately)
        assert abs(order.quantity - expected_qty) < Decimal("0.01"), \
            f"Expected qty ~{expected_qty}, got {order.quantity}"

    @pytest.mark.asyncio
    async def test_c2_limit_override_single_pyramid_multi_level_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        C2: Limit entry, capital override, single pyramid, 3 levels, aggregate TP.

        Expected:
        - Total capital split across 3 levels
        - Each level gets $100 (at equal weights)
        """
        scenario = SCENARIO_C2
        expected = calculate_expected_outcome(scenario)

        config = create_dca_grid_config(scenario)
        assert config.use_custom_capital is True

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        orders = []
        total_capital = Decimal("0")
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            orders.append(order)
            # Track capital per order (qty × price)
            total_capital += order.quantity * order.price

        # Total capital should approximately equal custom_capital_usd
        assert abs(total_capital - scenario.custom_capital_usd) < Decimal("1"), \
            f"Total capital {total_capital} should be ~{scenario.custom_capital_usd}"

        assert len(orders) == 3
        assert position.tp_mode == "aggregate"

    @pytest.mark.asyncio
    async def test_c3_limit_override_multi_pyramid_multi_level_pyramid_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        C3: Limit entry, capital override, 2 pyramids, 3 levels, pyramid_aggregate TP.

        Expected:
        - Each pyramid uses custom_capital_usd
        - Total position capital = custom_capital_usd × num_pyramids
        """
        scenario = SCENARIO_C3
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        total_orders = 0
        pyramid_capitals = []

        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            pyramid_capital = Decimal("0")

            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(scenario, position.id, pyramid.id, leg_index=l_idx)
                pyramid_capital += order.quantity * order.price
                total_orders += 1

            pyramid_capitals.append(pyramid_capital)

        # Each pyramid should have approximately custom_capital_usd
        for pc in pyramid_capitals:
            assert abs(pc - scenario.custom_capital_usd) < Decimal("1")

        assert total_orders == 6  # 2 pyramids × 3 levels
        assert position.tp_mode == "pyramid_aggregate"

    @pytest.mark.asyncio
    async def test_c4_limit_override_multi_pyramid_multi_level_hybrid(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        C4: Limit entry, capital override, 2 pyramids, 3 levels, hybrid TP.
        """
        scenario = SCENARIO_C4
        expected = calculate_expected_outcome(scenario)

        config = create_dca_grid_config(scenario)
        assert config.use_custom_capital is True
        assert config.tp_mode == "hybrid"

        position = create_position_group(scenario, scenario_mock_user.id)

        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(scenario, position.id, pyramid.id, leg_index=l_idx)
                orders.append(order)

        assert len(orders) == 6
        assert position.tp_mode == "hybrid"

    @pytest.mark.asyncio
    async def test_c5_market_override_single_pyramid_single_level_perleg(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        C5: Market entry, capital override, single pyramid, single level, per_leg TP.

        Expected:
        - TRIGGER_PENDING status (market entry)
        - Quantity from custom_capital_usd
        """
        scenario = SCENARIO_C5
        expected = calculate_expected_outcome(scenario)

        config = create_dca_grid_config(scenario)
        assert config.use_custom_capital is True
        assert config.entry_order_type == "market"

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(
            scenario, position.id, pyramid.id, leg_index=0,
            status=OrderStatus.TRIGGER_PENDING
        )

        # Verify market entry status
        assert order.status == OrderStatus.TRIGGER_PENDING.value

        # Verify capital override quantity
        expected_qty = scenario.custom_capital_usd / scenario.base_price
        assert abs(order.quantity - expected_qty) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_c6_market_override_single_pyramid_multi_level_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        C6: Market entry, capital override, single pyramid, 3 levels, aggregate TP.
        """
        scenario = SCENARIO_C6
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        orders = []
        for i in range(scenario.dca_levels):
            order = create_dca_order(
                scenario, position.id, pyramid.id, leg_index=i,
                status=OrderStatus.TRIGGER_PENDING
            )
            orders.append(order)

        assert len(orders) == 3
        assert all(o.status == OrderStatus.TRIGGER_PENDING.value for o in orders)
        assert position.tp_mode == "aggregate"

    @pytest.mark.asyncio
    async def test_c7_market_override_multi_pyramid_multi_level_pyramid_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        C7: Market entry, capital override, 2 pyramids, 3 levels, pyramid_aggregate TP.
        """
        scenario = SCENARIO_C7
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(
                    scenario, position.id, pyramid.id, leg_index=l_idx,
                    status=OrderStatus.TRIGGER_PENDING
                )
                orders.append(order)

        assert len(orders) == 6
        assert position.tp_mode == "pyramid_aggregate"

    @pytest.mark.asyncio
    async def test_c8_market_override_multi_pyramid_multi_level_hybrid(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        C8: Market entry, capital override, 2 pyramids, 3 levels, hybrid TP.
        """
        scenario = SCENARIO_C8
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(
                    scenario, position.id, pyramid.id, leg_index=l_idx,
                    status=OrderStatus.TRIGGER_PENDING
                )
                orders.append(order)

        assert len(orders) == 6
        assert position.tp_mode == "hybrid"


class TestCapitalOverrideQuantityCalculation:
    """Test quantity calculation when capital override is enabled."""

    @pytest.mark.asyncio
    async def test_signal_order_size_ignored_when_override_enabled(
        self,
        scenario_mock_user
    ):
        """Verify signal's order_size is ignored when use_custom_capital=True."""
        scenario = SCENARIO_C1

        # Signal has $500 order size
        signal = create_mock_signal(scenario)
        assert signal["tv"]["order_size"] == float(scenario.signal_order_size)
        assert float(scenario.signal_order_size) == 500.0

        # Config has $300 custom capital
        config = create_dca_grid_config(scenario)
        assert config.use_custom_capital is True
        assert config.custom_capital_usd == Decimal("300")

        # Order should use $300, not $500
        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)

        # Expected qty from $300
        expected_qty = Decimal("300") / scenario.base_price
        assert abs(order.quantity - expected_qty) < Decimal("0.01")

        # NOT expected qty from $500
        wrong_qty = Decimal("500") / scenario.base_price
        assert abs(order.quantity - wrong_qty) > Decimal("0.1")

    @pytest.mark.asyncio
    async def test_multi_level_capital_distribution(
        self,
        scenario_mock_user
    ):
        """Test that capital is correctly distributed across multiple levels."""
        scenario = SCENARIO_C2  # 3 levels

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        orders = []
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            orders.append(order)

        # Calculate total invested
        total_invested = sum(o.quantity * o.price for o in orders)

        # Should equal custom_capital_usd (approximately, due to DCA pricing)
        assert abs(total_invested - scenario.custom_capital_usd) < Decimal("5")

    @pytest.mark.asyncio
    async def test_pyramid_specific_capital_override(
        self,
        scenario_mock_user
    ):
        """Test per-pyramid capital configuration when available."""
        # Create a scenario with per-pyramid capitals
        scenario = ScenarioConfig(
            scenario_id="test_pyramid_capitals",
            description="Test per-pyramid capital override",
            entry_type=EntryType.LIMIT,
            quantity_source=QuantitySource.OVERRIDE,
            custom_capital_usd=Decimal("200"),  # Default
            max_pyramids=3,
            pyramid_count_to_test=3,
            dca_levels=1,
            tp_mode=TPMode.PYRAMID_AGGREGATE
        )

        config = create_dca_grid_config(scenario)

        # Add per-pyramid capitals
        config.pyramid_custom_capitals = {
            "0": Decimal("200"),  # First entry
            "1": Decimal("300"),  # First pyramid
            "2": Decimal("400"),  # Second pyramid
        }

        # Verify get_capital_for_pyramid works
        assert config.get_capital_for_pyramid(0) == Decimal("200")
        assert config.get_capital_for_pyramid(1) == Decimal("300")
        assert config.get_capital_for_pyramid(2) == Decimal("400")

        # Non-configured pyramid falls back to default
        assert config.get_capital_for_pyramid(3) == config.custom_capital_usd


class TestCapitalOverrideParameterized:
    """Parameterized tests for all Group C scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", GROUP_C_SCENARIOS, ids=[s.scenario_id for s in GROUP_C_SCENARIOS])
    async def test_scenario_uses_custom_capital(
        self,
        scenario,
        scenario_mock_user
    ):
        """Verify all C scenarios use custom capital."""
        config = create_dca_grid_config(scenario)

        assert config.use_custom_capital is True, f"{scenario.scenario_id} should use custom capital"
        assert config.custom_capital_usd == scenario.custom_capital_usd

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", GROUP_C_SCENARIOS, ids=[s.scenario_id for s in GROUP_C_SCENARIOS])
    async def test_scenario_total_capital_matches_config(
        self,
        scenario,
        scenario_mock_user
    ):
        """Verify total position capital matches custom_capital_usd per pyramid."""
        position = create_position_group(scenario, scenario_mock_user.id)

        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            pyramid_capital = Decimal("0")

            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(scenario, position.id, pyramid.id, leg_index=l_idx)
                pyramid_capital += order.quantity * order.price

            # Each pyramid should use approximately custom_capital_usd
            tolerance = Decimal("5")  # Allow small variance due to DCA pricing
            assert abs(pyramid_capital - scenario.custom_capital_usd) < tolerance, \
                f"Pyramid {p_idx} capital {pyramid_capital} should be ~{scenario.custom_capital_usd}"
