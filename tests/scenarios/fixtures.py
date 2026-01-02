"""
Scenario factory and helpers for comprehensive trading tests.

This module provides fixtures and utilities for testing all combinations of:
- Entry types: limit vs market
- Price conditions: above vs below current price
- Quantity source: signal vs capital override
- Pyramids: single vs multiple
- DCA levels: single vs multiple
- TP modes: per_leg, aggregate, pyramid_aggregate, hybrid
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from unittest.mock import AsyncMock, MagicMock

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid
from app.schemas.grid_config import DCAGridConfig, DCALevelConfig


class EntryType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class PriceCondition(str, Enum):
    ABOVE = "above"  # Entry price above current price (waits to fill)
    BELOW = "below"  # Entry price below current price (fills immediately for limit)


class QuantitySource(str, Enum):
    SIGNAL = "signal"  # Use order_size from webhook signal
    OVERRIDE = "override"  # Use capital_per_position from config


class TPMode(str, Enum):
    PER_LEG = "per_leg"
    AGGREGATE = "aggregate"
    PYRAMID_AGGREGATE = "pyramid_aggregate"
    HYBRID = "hybrid"


@dataclass
class ScenarioConfig:
    """Configuration for a single test scenario."""

    # Scenario identification
    scenario_id: str
    description: str

    # Entry configuration
    entry_type: EntryType = EntryType.LIMIT
    price_condition: PriceCondition = PriceCondition.BELOW
    side: Literal["long", "short"] = "long"

    # Quantity configuration
    quantity_source: QuantitySource = QuantitySource.SIGNAL
    signal_order_size: Decimal = Decimal("500")  # USD from signal
    custom_capital_usd: Decimal = Decimal("300")  # USD when override enabled

    # Pyramid configuration
    max_pyramids: int = 1
    pyramid_count_to_test: int = 1  # How many pyramids to create in test

    # DCA configuration
    dca_levels: int = 1
    level_step_percent: Decimal = Decimal("0.5")  # Gap between levels

    # TP configuration
    tp_mode: TPMode = TPMode.PER_LEG
    tp_percent: Decimal = Decimal("2.0")  # Per-leg TP percent
    tp_aggregate_percent: Decimal = Decimal("3.0")  # Aggregate TP percent

    # Price configuration for testing
    base_price: Decimal = Decimal("100.0")
    current_price: Decimal = Decimal("100.0")

    # Exchange
    exchange: str = "mock"
    symbol: str = "BTC/USDT"
    timeframe: int = 60

    def __post_init__(self):
        # Adjust current price based on price condition
        if self.price_condition == PriceCondition.BELOW:
            # For below: current price is higher than entry (limit fills on drop)
            self.current_price = self.base_price * Decimal("1.02")
        else:
            # For above: current price is lower than entry (limit fills on rise)
            self.current_price = self.base_price * Decimal("0.98")


@dataclass
class ExpectedOutcome:
    """Expected outcomes for a scenario."""

    # Order expectations
    expected_order_count: int = 1
    expected_initial_status: OrderStatus = OrderStatus.OPEN

    # Position expectations
    expected_position_status: PositionGroupStatus = PositionGroupStatus.LIVE
    expected_total_dca_legs: int = 1
    expected_filled_dca_legs: int = 0

    # Financial expectations (calculated from scenario)
    expected_total_invested: Optional[Decimal] = None
    expected_total_quantity: Optional[Decimal] = None
    expected_weighted_avg_entry: Optional[Decimal] = None

    # TP expectations
    expected_tp_orders: int = 0
    expected_tp_mode: str = "per_leg"


def create_dca_levels_config(
    num_levels: int = 1,
    step_percent: Decimal = Decimal("0.5"),
    tp_percent: Decimal = Decimal("2.0")
) -> List[DCALevelConfig]:
    """Create DCA level configurations with proper weight distribution."""
    levels = []
    weight_per_level = Decimal("100") / num_levels

    for i in range(num_levels):
        gap = Decimal("0") if i == 0 else -step_percent * i
        levels.append(DCALevelConfig(
            gap_percent=gap,
            weight_percent=weight_per_level,
            tp_percent=tp_percent
        ))

    return levels


def create_dca_grid_config(scenario: ScenarioConfig) -> DCAGridConfig:
    """Create a DCAGridConfig from a scenario configuration."""
    levels = create_dca_levels_config(
        num_levels=scenario.dca_levels,
        step_percent=scenario.level_step_percent,
        tp_percent=scenario.tp_percent
    )

    return DCAGridConfig(
        levels=levels,
        tp_mode=scenario.tp_mode.value,
        tp_aggregate_percent=scenario.tp_aggregate_percent,
        max_pyramids=scenario.max_pyramids,
        entry_order_type=scenario.entry_type.value,
        use_custom_capital=(scenario.quantity_source == QuantitySource.OVERRIDE),
        custom_capital_usd=scenario.custom_capital_usd
    )


def create_mock_signal(scenario: ScenarioConfig, pyramid_index: int = 0) -> Dict[str, Any]:
    """Create a mock webhook signal for a scenario."""
    action = "buy" if scenario.side == "long" else "sell"
    prev_position = "flat" if pyramid_index == 0 else scenario.side

    return {
        "user_id": str(uuid.uuid4()),
        "secret": "test_secret",
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": scenario.exchange,
            "symbol": scenario.symbol,
            "timeframe": scenario.timeframe,
            "action": action,
            "market_position": scenario.side,
            "market_position_size": float(scenario.signal_order_size),
            "prev_market_position": prev_position,
            "prev_market_position_size": float(scenario.signal_order_size) if pyramid_index > 0 else 0,
            "entry_price": float(scenario.base_price),
            "close_price": float(scenario.current_price),
            "order_size": float(scenario.signal_order_size),
        },
        "strategy_info": {
            "trade_id": f"test_{scenario.scenario_id}_{pyramid_index}",
            "alert_name": f"Test {scenario.scenario_id}",
            "alert_message": f"Test scenario {scenario.scenario_id}, pyramid {pyramid_index}"
        },
        "execution_intent": {
            "type": "signal",
            "side": action,
            "position_size_type": "quote",
            "precision_mode": "auto"
        },
        "risk": {
            "max_slippage_percent": 1.0
        }
    }


def create_position_group(
    scenario: ScenarioConfig,
    user_id: uuid.UUID,
    status: PositionGroupStatus = PositionGroupStatus.LIVE
) -> PositionGroup:
    """Create a PositionGroup instance for testing."""
    return PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id,
        exchange=scenario.exchange,
        symbol=scenario.symbol.replace("/", ""),
        timeframe=scenario.timeframe,
        side=scenario.side,
        status=status,
        pyramid_count=0,
        max_pyramids=scenario.max_pyramids,
        total_dca_legs=scenario.dca_levels,
        filled_dca_legs=0,
        base_entry_price=scenario.base_price,
        weighted_avg_entry=scenario.base_price,
        total_invested_usd=Decimal("0"),
        total_filled_quantity=Decimal("0"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode=scenario.tp_mode.value,
        tp_aggregate_percent=scenario.tp_aggregate_percent,
        created_at=datetime.utcnow(),
        risk_timer_start=datetime.utcnow(),
        risk_timer_expires=datetime.utcnow() + timedelta(hours=1)
    )


def create_dca_order(
    scenario: ScenarioConfig,
    group_id: uuid.UUID,
    pyramid_id: uuid.UUID,
    leg_index: int = 0,
    status: OrderStatus = OrderStatus.OPEN
) -> DCAOrder:
    """Create a DCAOrder instance for testing."""
    # Calculate gap_percent based on leg index
    gap_percent = Decimal("0") if leg_index == 0 else -scenario.level_step_percent * leg_index

    # Calculate price based on leg index (for long positions, DCA down)
    if scenario.side == "long":
        price = scenario.base_price * (Decimal("1") + gap_percent / 100)
    else:
        # For shorts, DCA up (sell higher)
        price = scenario.base_price * (Decimal("1") - gap_percent / 100)

    # Calculate quantity
    if scenario.quantity_source == QuantitySource.OVERRIDE:
        total_capital = scenario.custom_capital_usd
    else:
        total_capital = scenario.signal_order_size

    weight_percent = Decimal("100") / scenario.dca_levels
    quantity = (total_capital * weight_percent / 100) / price

    # Calculate TP price
    if scenario.side == "long":
        tp_price = price * (Decimal("1") + scenario.tp_percent / 100)
    else:
        tp_price = price * (Decimal("1") - scenario.tp_percent / 100)

    return DCAOrder(
        id=uuid.uuid4(),
        group_id=group_id,
        pyramid_id=pyramid_id,
        leg_index=leg_index,
        status=status.value,
        symbol=scenario.symbol.replace("/", ""),
        side="buy" if scenario.side == "long" else "sell",
        price=price,
        quantity=quantity,
        gap_percent=gap_percent,
        weight_percent=weight_percent,
        tp_percent=scenario.tp_percent,
        tp_price=tp_price,
        filled_quantity=Decimal("0"),
        tp_order_id=None,
        tp_hit=False,
        fee=Decimal("0"),
        fee_currency="USDT",
        created_at=datetime.utcnow()
    )


def create_pyramid(
    scenario: ScenarioConfig,
    group_id: uuid.UUID,
    pyramid_index: int = 0,
    status: str = "pending"
) -> Pyramid:
    """Create a Pyramid instance for testing."""
    # Create DCA config for pyramid
    levels = create_dca_levels_config(
        num_levels=scenario.dca_levels,
        step_percent=scenario.level_step_percent,
        tp_percent=scenario.tp_percent
    )

    dca_config = {
        "levels": [
            {
                "gap_percent": str(level.gap_percent),
                "weight_percent": str(level.weight_percent),
                "tp_percent": str(level.tp_percent)
            }
            for level in levels
        ],
        "tp_mode": scenario.tp_mode.value,
        "tp_aggregate_percent": str(scenario.tp_aggregate_percent)
    }

    return Pyramid(
        id=uuid.uuid4(),
        group_id=group_id,
        pyramid_index=pyramid_index,
        status=status,
        entry_price=scenario.base_price,
        entry_timestamp=datetime.utcnow(),
        signal_id=f"test_signal_{scenario.scenario_id}_{pyramid_index}",
        dca_config=dca_config
    )


def calculate_expected_outcome(scenario: ScenarioConfig) -> ExpectedOutcome:
    """Calculate expected outcomes based on scenario configuration."""
    # Determine expected order count
    order_count = scenario.dca_levels * scenario.pyramid_count_to_test

    # Determine initial order status
    if scenario.entry_type == EntryType.MARKET:
        initial_status = OrderStatus.TRIGGER_PENDING
    else:
        initial_status = OrderStatus.OPEN

    # Determine expected position status
    position_status = PositionGroupStatus.LIVE

    # Calculate expected quantities
    if scenario.quantity_source == QuantitySource.OVERRIDE:
        total_capital = scenario.custom_capital_usd
    else:
        total_capital = scenario.signal_order_size

    expected_quantity = total_capital / scenario.base_price

    # Determine expected TP orders based on mode
    if scenario.tp_mode == TPMode.PER_LEG:
        # TP orders placed per filled leg
        expected_tp_orders = 0  # Initially 0, increases as legs fill
    elif scenario.tp_mode == TPMode.AGGREGATE:
        expected_tp_orders = 0  # One aggregate TP after first fill
    elif scenario.tp_mode == TPMode.PYRAMID_AGGREGATE:
        expected_tp_orders = 0  # One per pyramid after first fill
    else:  # hybrid
        expected_tp_orders = 0  # Both types after first fill

    return ExpectedOutcome(
        expected_order_count=order_count,
        expected_initial_status=initial_status,
        expected_position_status=position_status,
        expected_total_dca_legs=scenario.dca_levels * scenario.pyramid_count_to_test,
        expected_filled_dca_legs=0,
        expected_total_invested=Decimal("0"),
        expected_total_quantity=Decimal("0"),
        expected_weighted_avg_entry=scenario.base_price,
        expected_tp_orders=expected_tp_orders,
        expected_tp_mode=scenario.tp_mode.value
    )


# ==========================================
# Pre-defined Scenario Templates
# ==========================================

# Group A: Limit Entry + Signal Quantity
SCENARIO_A1 = ScenarioConfig(
    scenario_id="A1",
    description="Limit entry, below price, single pyramid, single level, per_leg TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.BELOW,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=1,
    tp_mode=TPMode.PER_LEG
)

SCENARIO_A2 = ScenarioConfig(
    scenario_id="A2",
    description="Limit entry, below price, single pyramid, 3 levels, aggregate TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.BELOW,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=3,
    tp_mode=TPMode.AGGREGATE
)

SCENARIO_A3 = ScenarioConfig(
    scenario_id="A3",
    description="Limit entry, below price, 2 pyramids, single level, pyramid_aggregate TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.BELOW,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=1,
    tp_mode=TPMode.PYRAMID_AGGREGATE
)

SCENARIO_A4 = ScenarioConfig(
    scenario_id="A4",
    description="Limit entry, below price, 2 pyramids, 3 levels, hybrid TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.BELOW,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=3,
    tp_mode=TPMode.HYBRID
)

SCENARIO_A5 = ScenarioConfig(
    scenario_id="A5",
    description="Limit entry, above price, single pyramid, single level, per_leg TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.ABOVE,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=1,
    tp_mode=TPMode.PER_LEG
)

SCENARIO_A6 = ScenarioConfig(
    scenario_id="A6",
    description="Limit entry, above price, single pyramid, 3 levels, aggregate TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.ABOVE,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=3,
    tp_mode=TPMode.AGGREGATE
)

SCENARIO_A7 = ScenarioConfig(
    scenario_id="A7",
    description="Limit entry, above price, 2 pyramids, single level, pyramid_aggregate TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.ABOVE,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=1,
    tp_mode=TPMode.PYRAMID_AGGREGATE
)

SCENARIO_A8 = ScenarioConfig(
    scenario_id="A8",
    description="Limit entry, above price, 2 pyramids, 3 levels, hybrid TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.ABOVE,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=3,
    tp_mode=TPMode.HYBRID
)

# Group B: Market Entry + Signal Quantity
SCENARIO_B1 = ScenarioConfig(
    scenario_id="B1",
    description="Market entry, below price, single pyramid, single level, per_leg TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.BELOW,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=1,
    tp_mode=TPMode.PER_LEG
)

SCENARIO_B2 = ScenarioConfig(
    scenario_id="B2",
    description="Market entry, below price, single pyramid, 3 levels, aggregate TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.BELOW,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=3,
    tp_mode=TPMode.AGGREGATE
)

SCENARIO_B3 = ScenarioConfig(
    scenario_id="B3",
    description="Market entry, below price, 2 pyramids, single level, pyramid_aggregate TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.BELOW,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=1,
    tp_mode=TPMode.PYRAMID_AGGREGATE
)

SCENARIO_B4 = ScenarioConfig(
    scenario_id="B4",
    description="Market entry, below price, 2 pyramids, 3 levels, hybrid TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.BELOW,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=3,
    tp_mode=TPMode.HYBRID
)

SCENARIO_B5 = ScenarioConfig(
    scenario_id="B5",
    description="Market entry, above price, single pyramid, single level, per_leg TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.ABOVE,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=1,
    tp_mode=TPMode.PER_LEG
)

SCENARIO_B6 = ScenarioConfig(
    scenario_id="B6",
    description="Market entry, above price, single pyramid, 3 levels, aggregate TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.ABOVE,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=3,
    tp_mode=TPMode.AGGREGATE
)

SCENARIO_B7 = ScenarioConfig(
    scenario_id="B7",
    description="Market entry, above price, 2 pyramids, single level, pyramid_aggregate TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.ABOVE,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=1,
    tp_mode=TPMode.PYRAMID_AGGREGATE
)

SCENARIO_B8 = ScenarioConfig(
    scenario_id="B8",
    description="Market entry, above price, 2 pyramids, 3 levels, hybrid TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.ABOVE,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=3,
    tp_mode=TPMode.HYBRID
)

# Group C: Capital Override
SCENARIO_C1 = ScenarioConfig(
    scenario_id="C1",
    description="Limit entry, capital override, single pyramid, single level, per_leg TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.BELOW,
    quantity_source=QuantitySource.OVERRIDE,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=1,
    tp_mode=TPMode.PER_LEG
)

SCENARIO_C2 = ScenarioConfig(
    scenario_id="C2",
    description="Limit entry, capital override, single pyramid, 3 levels, aggregate TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.BELOW,
    quantity_source=QuantitySource.OVERRIDE,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=3,
    tp_mode=TPMode.AGGREGATE
)

SCENARIO_C3 = ScenarioConfig(
    scenario_id="C3",
    description="Limit entry, capital override, 2 pyramids, 3 levels, pyramid_aggregate TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.BELOW,
    quantity_source=QuantitySource.OVERRIDE,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=3,
    tp_mode=TPMode.PYRAMID_AGGREGATE
)

SCENARIO_C4 = ScenarioConfig(
    scenario_id="C4",
    description="Limit entry, capital override, 2 pyramids, 3 levels, hybrid TP",
    entry_type=EntryType.LIMIT,
    price_condition=PriceCondition.BELOW,
    quantity_source=QuantitySource.OVERRIDE,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=3,
    tp_mode=TPMode.HYBRID
)

SCENARIO_C5 = ScenarioConfig(
    scenario_id="C5",
    description="Market entry, capital override, single pyramid, single level, per_leg TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.BELOW,
    quantity_source=QuantitySource.OVERRIDE,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=1,
    tp_mode=TPMode.PER_LEG
)

SCENARIO_C6 = ScenarioConfig(
    scenario_id="C6",
    description="Market entry, capital override, single pyramid, 3 levels, aggregate TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.BELOW,
    quantity_source=QuantitySource.OVERRIDE,
    max_pyramids=1,
    pyramid_count_to_test=1,
    dca_levels=3,
    tp_mode=TPMode.AGGREGATE
)

SCENARIO_C7 = ScenarioConfig(
    scenario_id="C7",
    description="Market entry, capital override, 2 pyramids, 3 levels, pyramid_aggregate TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.BELOW,
    quantity_source=QuantitySource.OVERRIDE,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=3,
    tp_mode=TPMode.PYRAMID_AGGREGATE
)

SCENARIO_C8 = ScenarioConfig(
    scenario_id="C8",
    description="Market entry, capital override, 2 pyramids, 3 levels, hybrid TP",
    entry_type=EntryType.MARKET,
    price_condition=PriceCondition.BELOW,
    quantity_source=QuantitySource.OVERRIDE,
    max_pyramids=2,
    pyramid_count_to_test=2,
    dca_levels=3,
    tp_mode=TPMode.HYBRID
)

# Note: Short positions (Group E) are NOT supported in spot trading.
# Short position signals are rejected at the signal router level.
# See tests/scenarios/test_short_positions.py for rejection tests.

# All scenario templates grouped
GROUP_A_SCENARIOS = [
    SCENARIO_A1, SCENARIO_A2, SCENARIO_A3, SCENARIO_A4,
    SCENARIO_A5, SCENARIO_A6, SCENARIO_A7, SCENARIO_A8
]

GROUP_B_SCENARIOS = [
    SCENARIO_B1, SCENARIO_B2, SCENARIO_B3, SCENARIO_B4,
    SCENARIO_B5, SCENARIO_B6, SCENARIO_B7, SCENARIO_B8
]

GROUP_C_SCENARIOS = [
    SCENARIO_C1, SCENARIO_C2, SCENARIO_C3, SCENARIO_C4,
    SCENARIO_C5, SCENARIO_C6, SCENARIO_C7, SCENARIO_C8
]

# Note: GROUP_E_SCENARIOS (short positions) removed - not supported in spot trading

ALL_SCENARIOS = GROUP_A_SCENARIOS + GROUP_B_SCENARIOS + GROUP_C_SCENARIOS


# ==========================================
# Assertion Helpers
# ==========================================

def assert_order_created_correctly(
    order: DCAOrder,
    scenario: ScenarioConfig,
    expected_status: OrderStatus
):
    """Assert that an order was created with correct properties."""
    assert order is not None, "Order should not be None"
    assert order.status == expected_status.value, f"Expected status {expected_status.value}, got {order.status}"
    assert order.symbol == scenario.symbol.replace("/", ""), f"Expected symbol {scenario.symbol}, got {order.symbol}"

    expected_side = "buy" if scenario.side == "long" else "sell"
    assert order.side == expected_side, f"Expected side {expected_side}, got {order.side}"


def assert_position_metrics(
    position: PositionGroup,
    expected_status: PositionGroupStatus,
    expected_total_qty: Decimal,
    expected_invested: Decimal,
    tolerance: Decimal = Decimal("0.01")
):
    """Assert position metrics are within expected tolerance."""
    assert position.status == expected_status, f"Expected status {expected_status}, got {position.status}"

    qty_diff = abs(position.total_filled_quantity - expected_total_qty)
    assert qty_diff <= tolerance, f"Total qty mismatch: expected {expected_total_qty}, got {position.total_filled_quantity}"

    invested_diff = abs(position.total_invested_usd - expected_invested)
    assert invested_diff <= tolerance, f"Invested mismatch: expected {expected_invested}, got {position.total_invested_usd}"


def assert_pnl_calculation(
    position: PositionGroup,
    expected_unrealized_pnl: Decimal,
    expected_realized_pnl: Decimal,
    tolerance: Decimal = Decimal("0.01")
):
    """Assert PnL calculations are within expected tolerance."""
    unrealized_diff = abs(position.unrealized_pnl_usd - expected_unrealized_pnl)
    assert unrealized_diff <= tolerance, f"Unrealized PnL mismatch: expected {expected_unrealized_pnl}, got {position.unrealized_pnl_usd}"

    realized_diff = abs(position.realized_pnl_usd - expected_realized_pnl)
    assert realized_diff <= tolerance, f"Realized PnL mismatch: expected {expected_realized_pnl}, got {position.realized_pnl_usd}"


def assert_no_orphaned_orders(orders: List[DCAOrder], position: PositionGroup):
    """Assert there are no orphaned orders after position close."""
    if position.status == PositionGroupStatus.CLOSED:
        for order in orders:
            assert order.status in [
                OrderStatus.FILLED.value,
                OrderStatus.CANCELLED.value
            ], f"Orphaned order found: {order.id} with status {order.status}"
