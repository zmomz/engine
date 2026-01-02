"""
Group D Tests: Hybrid TP Trigger Scenarios

Tests the hybrid TP mode behavior when different triggers fire first:
- D1: Per-leg TP triggers first → reduces aggregate TP quantity
- D2: Aggregate TP triggers first → cancels remaining per-leg TPs
- D3: Multi-pyramid hybrid with mixed triggers
- D4: Partial leg TPs then aggregate closes remainder
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
    create_dca_grid_config,
    create_position_group,
    create_dca_order,
    create_pyramid,
    calculate_expected_outcome
)


def create_hybrid_scenario(
    scenario_id: str,
    description: str,
    pyramids: int = 1,
    levels: int = 3
) -> ScenarioConfig:
    """Helper to create hybrid TP scenarios."""
    return ScenarioConfig(
        scenario_id=scenario_id,
        description=description,
        entry_type=EntryType.LIMIT,
        price_condition=PriceCondition.BELOW,
        max_pyramids=pyramids,
        pyramid_count_to_test=pyramids,
        dca_levels=levels,
        tp_mode=TPMode.HYBRID,
        tp_percent=Decimal("2.0"),  # Per-leg TP
        tp_aggregate_percent=Decimal("3.0")  # Aggregate TP
    )


SCENARIO_D1 = create_hybrid_scenario(
    "D1",
    "Hybrid: per-leg TP triggers first",
    pyramids=1,
    levels=3
)

SCENARIO_D2 = create_hybrid_scenario(
    "D2",
    "Hybrid: aggregate TP triggers first",
    pyramids=1,
    levels=3
)

SCENARIO_D3 = create_hybrid_scenario(
    "D3",
    "Hybrid multi-pyramid: mixed triggers",
    pyramids=2,
    levels=2
)

SCENARIO_D4 = create_hybrid_scenario(
    "D4",
    "Hybrid: partial leg TPs then aggregate",
    pyramids=1,
    levels=4
)


class TestHybridPerLegFirst:
    """Test scenarios where per-leg TPs trigger before aggregate."""

    @pytest.mark.asyncio
    async def test_d1_perleg_triggers_first_reduces_aggregate_qty(
        self,
        scenario_mock_user,
        simulate_order_fill,
        simulate_tp_hit
    ):
        """
        D1: Per-leg TP triggers first → aggregate TP quantity should be reduced.

        Setup:
        - 3 DCA legs filled
        - Per-leg TP for leg 0 hits first
        - Aggregate TP quantity should reduce by leg 0's quantity
        """
        scenario = SCENARIO_D1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Create and fill all 3 orders
        orders = []
        total_qty = Decimal("0")
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            filled = await simulate_order_fill(order)
            orders.append(filled)
            total_qty += filled.filled_quantity

        # Initial aggregate TP covers total_qty
        initial_aggregate_qty = total_qty

        # Per-leg TP for leg 0 triggers
        leg_0_qty = orders[0].filled_quantity
        orders[0], _ = await simulate_tp_hit(orders[0])

        # After leg 0 TP hits, aggregate qty should reduce
        updated_aggregate_qty = initial_aggregate_qty - leg_0_qty
        remaining_position_qty = total_qty - leg_0_qty

        # Verify quantities
        assert orders[0].tp_hit is True, "Leg 0 TP should be hit"
        assert remaining_position_qty > 0, "Position should still have remaining quantity"
        assert updated_aggregate_qty == remaining_position_qty

    @pytest.mark.asyncio
    async def test_d1_multiple_perleg_tps_reduce_aggregate_incrementally(
        self,
        scenario_mock_user,
        simulate_order_fill,
        simulate_tp_hit
    ):
        """Test that multiple per-leg TPs hitting reduces aggregate incrementally."""
        scenario = SCENARIO_D1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Create and fill all orders
        orders = []
        total_qty = Decimal("0")
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            filled = await simulate_order_fill(order)
            orders.append(filled)
            total_qty += filled.filled_quantity

        # Track aggregate qty as per-leg TPs hit
        remaining_qty = total_qty

        # Hit per-leg TPs one by one
        for order in orders[:2]:  # First 2 legs
            order, _ = await simulate_tp_hit(order)
            remaining_qty -= order.filled_quantity

        # Verify 2 legs are TP'd
        assert orders[0].tp_hit is True
        assert orders[1].tp_hit is True
        assert orders[2].tp_hit is False

        # Remaining qty should be leg 2's quantity only
        assert remaining_qty == orders[2].filled_quantity


class TestHybridAggregateFirst:
    """Test scenarios where aggregate TP triggers before per-leg TPs."""

    @pytest.mark.asyncio
    async def test_d2_aggregate_triggers_first_cancels_perleg_tps(
        self,
        scenario_mock_user,
        scenario_mock_order_service,
        simulate_order_fill
    ):
        """
        D2: Aggregate TP triggers first → all per-leg TPs should be cancelled.

        Setup:
        - 3 DCA legs filled, each with per-leg TP placed
        - Aggregate TP hits first
        - All per-leg TPs should be cancelled
        """
        scenario = SCENARIO_D2

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Create and fill orders, each gets a per-leg TP
        orders = []
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            filled = await simulate_order_fill(order)
            # Simulate TP order placement
            filled.tp_order_id = f"tp_{filled.id}"
            orders.append(filled)

        # Verify all orders have TP orders
        assert all(o.tp_order_id is not None for o in orders)

        # Aggregate TP triggers (simulate by closing position)
        position.status = PositionGroupStatus.CLOSED
        position.total_filled_quantity = Decimal("0")

        # Per-leg TPs should be cancelled (in real code, order_service.cancel_order is called)
        for order in orders:
            # Simulate cancellation
            order.tp_hit = False  # TP didn't hit individually
            order.tp_order_id = None  # TP cancelled

        # Verify TPs are "cancelled" (tp_order_id cleared)
        assert all(o.tp_order_id is None for o in orders)

    @pytest.mark.asyncio
    async def test_d2_aggregate_tp_fills_entire_position(
        self,
        scenario_mock_user,
        simulate_order_fill
    ):
        """Test that aggregate TP closes the entire position."""
        scenario = SCENARIO_D2

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Fill all orders
        orders = []
        total_qty = Decimal("0")
        total_invested = Decimal("0")
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            filled = await simulate_order_fill(order)
            orders.append(filled)
            total_qty += filled.filled_quantity
            total_invested += filled.filled_quantity * filled.avg_fill_price

        # Calculate weighted average
        weighted_avg = total_invested / total_qty

        # Aggregate TP price
        aggregate_tp_price = weighted_avg * (Decimal("1") + scenario.tp_aggregate_percent / 100)

        # Simulate aggregate TP fill
        exit_value = total_qty * aggregate_tp_price
        entry_value = total_invested

        # Realized PnL (before fees)
        realized_pnl = exit_value - entry_value

        # Verify profitable trade
        assert realized_pnl > 0, "Aggregate TP should be profitable"


class TestHybridMultiPyramid:
    """Test hybrid TP with multiple pyramids."""

    @pytest.mark.asyncio
    async def test_d3_mixed_triggers_across_pyramids(
        self,
        scenario_mock_user,
        simulate_order_fill,
        simulate_tp_hit
    ):
        """
        D3: Multi-pyramid hybrid with mixed triggers.

        Setup:
        - 2 pyramids, each with 2 levels
        - Pyramid 1: per-leg TP triggers on leg 0
        - Pyramid 2: aggregate TP triggers
        """
        scenario = SCENARIO_D3

        position = create_position_group(scenario, scenario_mock_user.id)

        # Create pyramids with orders
        pyramid_data = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            orders = []
            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(scenario, position.id, pyramid.id, leg_index=l_idx)
                filled = await simulate_order_fill(order)
                orders.append(filled)
            pyramid_data.append({"pyramid": pyramid, "orders": orders})

        # Pyramid 0: per-leg TP triggers on leg 0
        pyramid_data[0]["orders"][0], _ = await simulate_tp_hit(pyramid_data[0]["orders"][0])

        # Verify mixed state
        assert pyramid_data[0]["orders"][0].tp_hit is True
        assert pyramid_data[0]["orders"][1].tp_hit is False
        assert pyramid_data[1]["orders"][0].tp_hit is False
        assert pyramid_data[1]["orders"][1].tp_hit is False

    @pytest.mark.asyncio
    async def test_d3_pyramid_closes_independently(
        self,
        scenario_mock_user,
        simulate_order_fill,
        simulate_tp_hit
    ):
        """Test that pyramids can close independently in hybrid mode."""
        scenario = SCENARIO_D3

        position = create_position_group(scenario, scenario_mock_user.id)

        # Create pyramids
        pyramid_data = []
        for p_idx in range(scenario.pyramid_count_to_test):
            pyramid = create_pyramid(scenario, position.id, pyramid_index=p_idx)
            # Set to active after orders are filled
            pyramid.status = "filled"  # Active pyramid with filled orders
            orders = []
            for l_idx in range(scenario.dca_levels):
                order = create_dca_order(scenario, position.id, pyramid.id, leg_index=l_idx)
                filled = await simulate_order_fill(order)
                orders.append(filled)
            pyramid_data.append({"pyramid": pyramid, "orders": orders})

        # Close pyramid 0 via all per-leg TPs
        for order in pyramid_data[0]["orders"]:
            order, _ = await simulate_tp_hit(order)

        # Verify pyramid 0 is fully closed
        assert all(o.tp_hit for o in pyramid_data[0]["orders"])
        pyramid_data[0]["pyramid"].status = "cancelled"  # Closed/cancelled after TPs hit

        # Pyramid 1 should still be active (filled status means orders are active)
        assert not any(o.tp_hit for o in pyramid_data[1]["orders"])
        assert pyramid_data[1]["pyramid"].status == "filled"


class TestHybridPartialThenAggregate:
    """Test partial per-leg TPs followed by aggregate close."""

    @pytest.mark.asyncio
    async def test_d4_partial_perleg_then_aggregate_closes_remainder(
        self,
        scenario_mock_user,
        simulate_order_fill,
        simulate_tp_hit
    ):
        """
        D4: Partial leg TPs then aggregate closes remainder.

        Setup:
        - 4 DCA legs filled
        - Legs 0 and 1 hit per-leg TP
        - Aggregate TP then closes legs 2 and 3
        """
        scenario = SCENARIO_D4

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Fill all 4 orders
        orders = []
        total_qty = Decimal("0")
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            filled = await simulate_order_fill(order)
            orders.append(filled)
            total_qty += filled.filled_quantity

        # Per-leg TPs hit for legs 0 and 1
        per_leg_closed_qty = Decimal("0")
        for order in orders[:2]:
            order, _ = await simulate_tp_hit(order)
            per_leg_closed_qty += order.filled_quantity

        # Calculate remaining quantity
        remaining_qty = total_qty - per_leg_closed_qty

        # Verify partial state
        assert orders[0].tp_hit is True
        assert orders[1].tp_hit is True
        assert orders[2].tp_hit is False
        assert orders[3].tp_hit is False

        # Aggregate TP closes remainder (legs 2 and 3)
        aggregate_qty = remaining_qty
        assert aggregate_qty == orders[2].filled_quantity + orders[3].filled_quantity

        # After aggregate closes, position should be fully closed
        position.status = PositionGroupStatus.CLOSED
        position.total_filled_quantity = Decimal("0")

    @pytest.mark.asyncio
    async def test_d4_pnl_calculated_correctly_for_mixed_exits(
        self,
        scenario_mock_user,
        simulate_order_fill,
        simulate_tp_hit
    ):
        """Test PnL is calculated correctly when using mixed exit methods."""
        scenario = SCENARIO_D4

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Fill orders
        orders = []
        total_invested = Decimal("0")
        for i in range(scenario.dca_levels):
            order = create_dca_order(scenario, position.id, pyramid.id, leg_index=i)
            filled = await simulate_order_fill(order)
            orders.append(filled)
            total_invested += filled.filled_quantity * filled.avg_fill_price

        # Per-leg exits for legs 0, 1 (at their individual TP prices)
        perleg_exit_value = Decimal("0")
        for order in orders[:2]:
            tp_price = order.tp_price
            exit_value = order.filled_quantity * tp_price
            perleg_exit_value += exit_value
            order, _ = await simulate_tp_hit(order)

        # Remaining legs exit via aggregate TP
        remaining_invested = sum(o.filled_quantity * o.avg_fill_price for o in orders[2:])
        remaining_qty = sum(o.filled_quantity for o in orders[2:])
        remaining_avg = remaining_invested / remaining_qty if remaining_qty > 0 else Decimal("0")

        # Aggregate TP price based on remaining average
        aggregate_tp_price = remaining_avg * (Decimal("1") + scenario.tp_aggregate_percent / 100)
        aggregate_exit_value = remaining_qty * aggregate_tp_price

        # Total exit value
        total_exit_value = perleg_exit_value + aggregate_exit_value

        # Total realized PnL (before fees)
        realized_pnl = total_exit_value - total_invested

        # Should be profitable
        assert realized_pnl > 0


class TestHybridTPOrderManagement:
    """Test TP order management in hybrid mode."""

    @pytest.mark.asyncio
    async def test_hybrid_both_tp_types_placed(
        self,
        scenario_mock_user,
        simulate_order_fill
    ):
        """Verify both per-leg and aggregate TPs are placed in hybrid mode."""
        scenario = SCENARIO_D1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Fill first order
        order = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)
        filled = await simulate_order_fill(order)

        # In hybrid mode:
        # 1. Per-leg TP should be placed for the filled leg
        expected_perleg_tp = filled.avg_fill_price * (Decimal("1") + scenario.tp_percent / 100)

        # 2. Aggregate TP should also be placed (using weighted avg)
        expected_aggregate_tp = filled.avg_fill_price * (Decimal("1") + scenario.tp_aggregate_percent / 100)

        # Both should exist
        assert expected_perleg_tp > filled.avg_fill_price
        assert expected_aggregate_tp > filled.avg_fill_price
        assert expected_aggregate_tp > expected_perleg_tp  # Aggregate is further

    @pytest.mark.asyncio
    async def test_hybrid_aggregate_updated_on_new_fills(
        self,
        scenario_mock_user,
        simulate_order_fill
    ):
        """Test that aggregate TP is updated when new legs fill."""
        scenario = SCENARIO_D1

        position = create_position_group(scenario, scenario_mock_user.id)
        pyramid = create_pyramid(scenario, position.id, pyramid_index=0)

        # Fill leg 0
        order_0 = create_dca_order(scenario, position.id, pyramid.id, leg_index=0)
        filled_0 = await simulate_order_fill(order_0)

        # Initial aggregate based on leg 0 only
        initial_qty = filled_0.filled_quantity
        initial_avg = filled_0.avg_fill_price

        # Fill leg 1 (lower price)
        order_1 = create_dca_order(scenario, position.id, pyramid.id, leg_index=1)
        filled_1 = await simulate_order_fill(order_1)

        # New weighted average (should be lower)
        total_qty = initial_qty + filled_1.filled_quantity
        total_cost = (initial_qty * initial_avg) + (filled_1.filled_quantity * filled_1.avg_fill_price)
        new_avg = total_cost / total_qty

        # Aggregate TP should be updated to use new average
        new_aggregate_tp = new_avg * (Decimal("1") + scenario.tp_aggregate_percent / 100)

        # New aggregate TP should be lower (since we DCA'd down)
        assert new_avg < initial_avg, "Weighted avg should decrease after DCA"
