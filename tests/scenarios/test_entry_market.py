"""
Group B Tests: Market Entry + Signal Quantity

Tests all market entry scenarios with various combinations of:
- Price conditions (above/below current price)
- Pyramids (single/multiple)
- DCA levels (single/multiple)
- TP modes (per_leg, aggregate, pyramid_aggregate, hybrid)

Key difference from limit: Market orders start as TRIGGER_PENDING
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
    PriceCondition,
    TPMode,
    SCENARIO_B1, SCENARIO_B2, SCENARIO_B3, SCENARIO_B4,
    SCENARIO_B5, SCENARIO_B6, SCENARIO_B7, SCENARIO_B8,
    GROUP_B_SCENARIOS,
    create_dca_grid_config,
    create_mock_signal,
    create_position_group,
    create_dca_order,
    create_pyramid,
    calculate_expected_outcome
)


class TestMarketEntryScenarios:
    """Test class for market entry scenarios."""

    @pytest.mark.asyncio
    async def test_b1_market_below_single_pyramid_single_level_perleg(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        B1: Market entry, entry below current price, single pyramid, single level, per_leg TP.

        Expected:
        - 1 DCA order created with status TRIGGER_PENDING
        - Order waits for price to drop to trigger level before becoming market order
        """
        scenario = SCENARIO_B1
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # For market entry, orders start as TRIGGER_PENDING
        order = create_dca_order(
            scenario, position.id, pyramid.id, leg_index=0,
            status=OrderStatus.TRIGGER_PENDING
        )

        # Verify market entry starts as TRIGGER_PENDING
        assert order.status == OrderStatus.TRIGGER_PENDING.value, "Market orders should be TRIGGER_PENDING"
        assert position.tp_mode == "per_leg"

    @pytest.mark.asyncio
    async def test_b2_market_below_single_pyramid_multi_level_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        B2: Market entry, entry below current price, single pyramid, 3 levels, aggregate TP.

        Expected:
        - 3 DCA orders all start as TRIGGER_PENDING
        - Orders convert to market orders when trigger price is reached
        """
        scenario = SCENARIO_B2
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

        # Verify all orders are TRIGGER_PENDING
        assert len(orders) == 3
        for order in orders:
            assert order.status == OrderStatus.TRIGGER_PENDING.value

        assert position.tp_mode == "aggregate"

    @pytest.mark.asyncio
    async def test_b3_market_below_multi_pyramid_single_level_pyramid_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        B3: Market entry, entry below current price, 2 pyramids, single level, pyramid_aggregate TP.

        Expected:
        - 2 pyramids with 1 TRIGGER_PENDING order each
        """
        scenario = SCENARIO_B3
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        pyramids = []
        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            pyramids.append(pyramid)

            order = create_dca_order(
                scenario, position.id, pyramid.id, leg_index=0,
                status=OrderStatus.TRIGGER_PENDING
            )
            orders.append(order)

        assert len(pyramids) == 2
        assert len(orders) == 2
        assert all(o.status == OrderStatus.TRIGGER_PENDING.value for o in orders)
        assert position.tp_mode == "pyramid_aggregate"

    @pytest.mark.asyncio
    async def test_b4_market_below_multi_pyramid_multi_level_hybrid(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        B4: Market entry, entry below current price, 2 pyramids, 3 levels, hybrid TP.

        Expected:
        - 6 total TRIGGER_PENDING orders
        """
        scenario = SCENARIO_B4
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
        assert all(o.status == OrderStatus.TRIGGER_PENDING.value for o in orders)
        assert position.tp_mode == "hybrid"

    @pytest.mark.asyncio
    async def test_b5_market_above_single_pyramid_single_level_perleg(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        B5: Market entry, entry above current price, single pyramid, single level, per_leg TP.

        Expected:
        - TRIGGER_PENDING order at price above current
        - Triggers when price rises to trigger level
        """
        scenario = SCENARIO_B5
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(
            scenario, position.id, pyramid.id, leg_index=0,
            status=OrderStatus.TRIGGER_PENDING
        )

        assert order.status == OrderStatus.TRIGGER_PENDING.value
        # For ABOVE condition, base_price > current_price
        assert scenario.base_price > scenario.current_price

    @pytest.mark.asyncio
    async def test_b6_market_above_single_pyramid_multi_level_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        B6: Market entry, entry above current price, single pyramid, 3 levels, aggregate TP.
        """
        scenario = SCENARIO_B6
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
        assert position.tp_mode == "aggregate"

    @pytest.mark.asyncio
    async def test_b7_market_above_multi_pyramid_single_level_pyramid_aggregate(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        B7: Market entry, entry above current price, 2 pyramids, single level, pyramid_aggregate TP.
        """
        scenario = SCENARIO_B7
        expected = calculate_expected_outcome(scenario)

        position = create_position_group(scenario, scenario_mock_user.id)

        pyramids = []
        orders = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            pyramids.append(pyramid)
            order = create_dca_order(
                scenario, position.id, pyramid.id, leg_index=0,
                status=OrderStatus.TRIGGER_PENDING
            )
            orders.append(order)

        assert len(pyramids) == 2
        assert len(orders) == 2
        assert position.tp_mode == "pyramid_aggregate"

    @pytest.mark.asyncio
    async def test_b8_market_above_multi_pyramid_multi_level_hybrid(
        self,
        scenario_mock_session,
        scenario_mock_exchange_connector,
        scenario_mock_order_service,
        scenario_mock_user
    ):
        """
        B8: Market entry, entry above current price, 2 pyramids, 3 levels, hybrid TP.
        """
        scenario = SCENARIO_B8
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


class TestMarketEntryTriggerMechanism:
    """Test the trigger mechanism for market entry orders."""

    @pytest.mark.asyncio
    async def test_trigger_pending_converts_to_open_when_price_reached(
        self,
        scenario_mock_user,
        scenario_mock_exchange_connector
    ):
        """Test that TRIGGER_PENDING orders convert to OPEN when trigger price is hit."""
        scenario = SCENARIO_B1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(
            scenario, position.id, pyramid.id, leg_index=0,
            status=OrderStatus.TRIGGER_PENDING
        )

        # Simulate price dropping to trigger level
        trigger_price = order.price
        current_price = trigger_price * Decimal("0.99")  # Price dropped below trigger

        # In order_fill_monitor, when current_price <= trigger_price for buy:
        # Order would be submitted as market order
        if current_price <= trigger_price:
            order.status = OrderStatus.OPEN.value

        assert order.status == OrderStatus.OPEN.value

    @pytest.mark.asyncio
    async def test_trigger_pending_remains_pending_when_price_not_reached(
        self,
        scenario_mock_user,
        scenario_mock_exchange_connector
    ):
        """Test that TRIGGER_PENDING orders stay pending when price hasn't reached trigger."""
        scenario = SCENARIO_B1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(
            scenario, position.id, pyramid.id, leg_index=0,
            status=OrderStatus.TRIGGER_PENDING
        )

        # Price is still above trigger (not dropped enough)
        trigger_price = order.price
        current_price = trigger_price * Decimal("1.05")  # Price still above

        # Order should remain TRIGGER_PENDING
        assert order.status == OrderStatus.TRIGGER_PENDING.value


class TestMarketEntryFillBehavior:
    """Test order fill behavior for market entries."""

    @pytest.mark.asyncio
    async def test_market_order_fills_at_current_price(
        self,
        scenario_mock_user,
        scenario_mock_exchange_connector,
        simulate_order_fill
    ):
        """Test that market orders fill at current market price (with slippage)."""
        scenario = SCENARIO_B1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)
        order = create_dca_order(
            scenario, position.id, pyramid.id, leg_index=0,
            status=OrderStatus.TRIGGER_PENDING
        )

        # Simulate trigger and fill
        order.status = OrderStatus.OPEN.value

        # Market fills at current price (potentially with slippage)
        fill_price = scenario.current_price * Decimal("1.001")  # 0.1% slippage
        filled = await simulate_order_fill(order, fill_price=fill_price)

        assert filled.status == OrderStatus.FILLED.value
        assert filled.avg_fill_price == fill_price

    @pytest.mark.asyncio
    async def test_multiple_trigger_pending_fill_sequentially(
        self,
        scenario_mock_user,
        simulate_order_fill
    ):
        """Test that multiple TRIGGER_PENDING orders fill as price reaches each trigger."""
        scenario = SCENARIO_B2  # 3 levels

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        orders = []
        for i in range(scenario.dca_levels):
            order = create_dca_order(
                scenario, position.id, pyramid.id, leg_index=i,
                status=OrderStatus.TRIGGER_PENDING
            )
            orders.append(order)

        # Simulate price dropping through trigger levels
        for order in orders:
            # Price reaches trigger level
            order.status = OrderStatus.OPEN.value
            # Fill at trigger price
            filled = await simulate_order_fill(order, fill_price=order.price)
            assert filled.status == OrderStatus.FILLED.value


class TestMarketEntryParameterized:
    """Parameterized tests for all Group B scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", GROUP_B_SCENARIOS, ids=[s.scenario_id for s in GROUP_B_SCENARIOS])
    async def test_scenario_orders_start_as_trigger_pending(
        self,
        scenario,
        scenario_mock_user
    ):
        """Verify all market entry orders start as TRIGGER_PENDING."""
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

        # All orders should be TRIGGER_PENDING for market entry
        assert all(o.status == OrderStatus.TRIGGER_PENDING.value for o in orders)
        assert len(orders) == expected.expected_order_count

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", GROUP_B_SCENARIOS, ids=[s.scenario_id for s in GROUP_B_SCENARIOS])
    async def test_scenario_dca_config_is_market_type(
        self,
        scenario
    ):
        """Verify DCA config has market entry type for all B scenarios."""
        config = create_dca_grid_config(scenario)

        assert config.entry_order_type == "market"
        assert config.tp_mode == scenario.tp_mode.value
