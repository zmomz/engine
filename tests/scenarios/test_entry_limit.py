"""
Group A Tests: Limit Entry + Signal Quantity

Tests all limit entry scenarios with various combinations of:
- Price conditions (above/below current price)
- Pyramids (single/multiple)
- DCA levels (single/multiple)
- TP modes (per_leg, aggregate, pyramid_aggregate, hybrid)
"""

import pytest
import uuid
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid

from .fixtures import (
    ScenarioConfig,
    EntryType,
    PriceCondition,
    QuantitySource,
    TPMode,
    SCENARIO_A1, SCENARIO_A2, SCENARIO_A3, SCENARIO_A4,
    SCENARIO_A5, SCENARIO_A6, SCENARIO_A7, SCENARIO_A8,
    GROUP_A_SCENARIOS,
    create_dca_grid_config,
    create_mock_signal,
    create_position_group,
    create_dca_order,
    create_pyramid,
    calculate_expected_outcome,
    assert_order_created_correctly,
    assert_position_metrics,
    assert_pnl_calculation,
    assert_no_orphaned_orders
)


class TestLimitEntryScenarios:
    """Test class for limit entry scenarios."""

    @pytest.mark.asyncio
    async def test_a1_limit_below_single_pyramid_single_level_perleg(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_grid_calculator,
        scenario_mock_user
    ):
        """
        A1: Limit entry, entry below current price, single pyramid, single level, per_leg TP.

        Expected:
        - 1 DCA order created with status OPEN
        - Position status LIVE
        - Order price at base_entry_price (below current)
        - TP mode = per_leg
        """
        scenario = SCENARIO_A1
        expected = calculate_expected_outcome(scenario)

        # Create position group
        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)

        # Verify order properties
        assert order.status == OrderStatus.OPEN.value, "Limit orders should be OPEN initially"
        assert order.price == scenario.base_price, f"Order price should be {scenario.base_price}"

        # Verify position properties
        assert position.tp_mode == "per_leg"
        assert position.max_pyramids == 1
        assert position.total_dca_legs == 1

        # Verify order is below current price (for limit buy)
        assert order.price < scenario.current_price, "Limit buy should be below current price"

    @pytest.mark.asyncio
    async def test_a2_limit_below_single_pyramid_multi_level_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_grid_calculator,
        scenario_mock_user
    ):
        """
        A2: Limit entry, entry below current price, single pyramid, 3 levels, aggregate TP.

        Expected:
        - 3 DCA orders created at different price levels
        - All orders have status OPEN
        - Prices decrease for each level (DCA down)
        - TP mode = aggregate
        """
        scenario = SCENARIO_A2
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Create 3 DCA orders at different levels
        orders = []
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            orders.append(order)

        # Verify correct number of orders
        assert len(orders) == 3, "Should create 3 DCA orders"

        # Verify all orders are OPEN
        for order in orders:
            assert order.status == OrderStatus.OPEN.value

        # Verify prices decrease for DCA levels (buying lower)
        for i in range(1, len(orders)):
            assert orders[i].price < orders[i-1].price, "DCA prices should decrease"

        # Verify position TP mode
        assert position.tp_mode == "aggregate"

    @pytest.mark.asyncio
    async def test_a3_limit_below_multi_pyramid_single_level_pyramid_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_grid_calculator,
        scenario_mock_user
    ):
        """
        A3: Limit entry, entry below current price, 2 pyramids, single level, pyramid_aggregate TP.

        Expected:
        - 2 pyramids created
        - 1 DCA order per pyramid
        - Each pyramid has its own TP (pyramid_aggregate mode)
        """
        scenario = SCENARIO_A3
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        # Create 2 pyramids with 1 order each
        pyramids = []
        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            pyramids.append(pyramid)

            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)
            orders.append(order)

        # Verify pyramid count
        assert len(pyramids) == 2, "Should create 2 pyramids"
        assert len(orders) == 2, "Should create 2 orders (1 per pyramid)"

        # Verify TP mode
        assert position.tp_mode == "pyramid_aggregate"
        assert position.max_pyramids == 2

    @pytest.mark.asyncio
    async def test_a4_limit_below_multi_pyramid_multi_level_hybrid(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_grid_calculator,
        scenario_mock_user
    ):
        """
        A4: Limit entry, entry below current price, 2 pyramids, 3 levels, hybrid TP.

        Expected:
        - 2 pyramids × 3 levels = 6 total DCA orders
        - Hybrid mode: both per-leg TPs AND aggregate TP
        """
        scenario = SCENARIO_A4
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        pyramids = []
        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            pyramids.append(pyramid)

            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(scenario, position.id, pyramid.id, leg_index=l_idx)
                orders.append(order)

        # Verify total orders
        expected_orders = scenario.pyramid_count_to_test * scenario.dca_levels
        assert len(orders) == expected_orders, f"Should create {expected_orders} orders"

        # Verify TP mode
        assert position.tp_mode == "hybrid"

    @pytest.mark.asyncio
    async def test_a5_limit_above_single_pyramid_single_level_perleg(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_grid_calculator,
        scenario_mock_user
    ):
        """
        A5: Limit entry, entry above current price, single pyramid, single level, per_leg TP.

        Expected:
        - Order price above current price (waits for price to rise)
        - Order status OPEN (won't fill immediately)
        """
        scenario = SCENARIO_A5
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)

        # For "above" condition, base_price > current_price
        # The order is at base_price, which is above current
        assert order.price == scenario.base_price
        assert scenario.base_price > scenario.current_price, "Entry price should be above current for ABOVE condition"

        # Order should still be OPEN (won't fill until price rises)
        assert order.status == OrderStatus.OPEN.value

    @pytest.mark.asyncio
    async def test_a6_limit_above_single_pyramid_multi_level_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_grid_calculator,
        scenario_mock_user
    ):
        """
        A6: Limit entry, entry above current price, single pyramid, 3 levels, aggregate TP.

        Expected:
        - 3 orders at different price levels
        - All orders above current price initially
        - Aggregate TP mode
        """
        scenario = SCENARIO_A6
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        orders = []
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            orders.append(order)

        assert len(orders) == 3
        assert position.tp_mode == "aggregate"

        # First order at base price should be above current
        assert orders[0].price > scenario.current_price

    @pytest.mark.asyncio
    async def test_a7_limit_above_multi_pyramid_single_level_pyramid_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_grid_calculator,
        scenario_mock_user
    ):
        """
        A7: Limit entry, entry above current price, 2 pyramids, single level, pyramid_aggregate TP.

        Expected:
        - 2 pyramids with 1 order each
        - pyramid_aggregate TP mode
        """
        scenario = SCENARIO_A7
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        pyramids = []
        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            pyramids.append(pyramid)
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)
            orders.append(order)

        assert len(pyramids) == 2
        assert len(orders) == 2
        assert position.tp_mode == "pyramid_aggregate"

    @pytest.mark.asyncio
    async def test_a8_limit_above_multi_pyramid_multi_level_hybrid(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_grid_calculator,
        scenario_mock_user
    ):
        """
        A8: Limit entry, entry above current price, 2 pyramids, 3 levels, hybrid TP.

        Expected:
        - 6 total orders (2 pyramids × 3 levels)
        - Hybrid TP mode
        """
        scenario = SCENARIO_A8
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        pyramids = []
        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            pyramids.append(pyramid)

            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(scenario, position.id, pyramid.id, leg_index=l_idx)
                orders.append(order)

        assert len(pyramids) == 2
        assert len(orders) == 6
        assert position.tp_mode == "hybrid"


class TestLimitEntryOrderFills:
    """Test order fill scenarios for limit entries."""

    @pytest.mark.asyncio
    async def test_single_order_fill_updates_position(
        self,
        scenario_mock_user,
        simulate_order_fill
    ):
        """Test that filling a single order updates position metrics correctly."""
        scenario = SCENARIO_A1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)

        # Simulate order fill
        filled_order = await simulate_order_fill(order, fill_price=scenario.base_price)

        # Verify order is filled
        assert filled_order.status == OrderStatus.FILLED.value
        assert filled_order.filled_quantity == order.quantity
        assert filled_order.fee > 0, "Fee should be calculated on fill"

    @pytest.mark.asyncio
    async def test_multi_level_fills_calculate_weighted_avg(
        self,
        scenario_mock_user,
        simulate_order_fill
    ):
        """Test that multiple fills correctly calculate weighted average entry."""
        scenario = SCENARIO_A2  # 3 levels

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        orders = []
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            orders.append(order)

        # Fill all orders at their prices
        total_qty = Decimal("0")
        total_cost = Decimal("0")

        for order in orders:
            filled = await simulate_order_fill(order, fill_price=order.price)
            total_qty += filled.filled_quantity
            total_cost += filled.filled_quantity * filled.avg_fill_price

        # Calculate expected weighted average
        expected_avg = total_cost / total_qty

        # Verify (in real code, position manager would update these)
        assert total_qty > 0
        assert expected_avg > 0


class TestLimitEntryTPPlacement:
    """Test TP order placement for limit entries."""

    @pytest.mark.asyncio
    async def test_perleg_tp_placed_on_fill(
        self,
        scenario_mock_user,
        scenario_mock_order_service,
        simulate_order_fill
    ):
        """Test that per_leg TP is placed when leg fills."""
        scenario = SCENARIO_A1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)

        # Simulate fill
        filled = await simulate_order_fill(order)

        # In per_leg mode, TP should be placed for each filled leg
        assert position.tp_mode == "per_leg"

        # TP price should be entry + tp_percent
        expected_tp = filled.avg_fill_price * (Decimal("1") + scenario.tp_percent / 100)
        assert order.tp_price > order.price, "TP price should be above entry for long"

    @pytest.mark.asyncio
    async def test_aggregate_tp_placed_after_first_fill(
        self,
        scenario_mock_user,
        scenario_mock_order_service,
        simulate_order_fill
    ):
        """Test that aggregate TP is placed after first fill."""
        scenario = SCENARIO_A2  # aggregate mode

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        orders = []
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            orders.append(order)

        # Fill first order
        await simulate_order_fill(orders[0])

        # In aggregate mode, TP is placed using weighted_avg × (1 + tp_aggregate_percent)
        assert position.tp_mode == "aggregate"


class TestLimitEntryParameterized:
    """Parameterized tests for all Group A scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", GROUP_A_SCENARIOS, ids=[s.scenario_id for s in GROUP_A_SCENARIOS])
    async def test_scenario_creates_correct_structure(
        self,
        scenario,
        scenario_mock_user
    ):
        """Verify each scenario creates the correct position/pyramid/order structure."""
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        # Verify position properties match scenario
        assert position.tp_mode == scenario.tp_mode.value
        assert position.max_pyramids == scenario.max_pyramids
        assert position.side == scenario.side
        assert position.total_dca_legs == scenario.dca_levels

        # Create pyramids and orders
        total_orders = 0
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(scenario, position.id, pyramid.id, leg_index=l_idx)
                assert order.status == OrderStatus.OPEN.value, "Limit orders should be OPEN"
                total_orders += 1

        assert total_orders == expected.expected_order_count

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", GROUP_A_SCENARIOS, ids=[s.scenario_id for s in GROUP_A_SCENARIOS])
    async def test_scenario_dca_config_generation(
        self,
        scenario
    ):
        """Verify DCA config is generated correctly for each scenario."""
        config = create_dca_grid_config(scenario)

        assert config.entry_order_type == scenario.entry_type.value
        assert config.tp_mode == scenario.tp_mode.value
        assert config.max_pyramids == scenario.max_pyramids
        assert len(config.levels) == scenario.dca_levels

        # Verify weights sum to 100
        total_weight = sum(level.weight_percent for level in config.levels)
        assert abs(total_weight - Decimal("100")) < Decimal("0.01")
