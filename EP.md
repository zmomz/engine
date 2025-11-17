# Execution Plan v5.0: Hardened & Clarified SoW-Compliant Execution Engine
## Comprehensive Development Roadmap

---

## 1.1 Executive Summary

This document provides a 100% complete, detailed execution plan to build the Execution Engine from the ground up to full SoW compliance. It has been upgraded to v5.0 to include a **Logic Annex** for clarifying ambiguities, a **UI/UX Design System** with wireframes, a comprehensive **Operational Manual** for environment setup, and a **Change Management Protocol**.

**This version now includes:**
- **Logic Annex:** Explicit definitions for ambiguous business rules, including queued signal loss calculation and a detailed exchange error mapping.
- **UI/UX Design System:** Low-fidelity wireframes, component architecture breakdowns, and defined micro-interactions for a polished user experience.
- **Operational Manual:** A bootstrap script and exact dependency versions to ensure a smooth, repeatable development setup.
- **Change Management Protocol:** A formal process for handling scope changes.
- **Detailed implementation guidance** with algorithm pseudocode
- **Complete data models** and state machines
- **Explicit Business Rules & Formulas:** Precise calculations for PnL, fees, and position sizing.
- **Enhanced acceptance criteria** with technical, performance, and test metrics
- **Validation checkpoints** after each phase
- **User Journey Flows:** Step-by-step descriptions of user interactions, from onboarding to error recovery.
- **Operational Runbooks:** Procedures for monitoring, alerting, data migration, and deployment rollbacks.
- **Quality Gates & Enhanced Testing:** Clear criteria for phase completion, including performance and security testing plans.
- **Configuration Templates & Troubleshooting:** Practical examples and guides for users and operators.
- **Full SoW Traceability:** A matrix linking every requirement to its implementation phase.

**Target Outcome:** Production-ready, robust, and user-friendly packaged web application for Windows and macOS.

---

## 1.2 Current State Assessment

### Backend Status
- ✅ Clean service-oriented architecture established
- ⚠️ Placeholder logic in core services (grid, risk, queue)
- ⚠️ Incomplete precision validation
- ⚠️ Missing exchange abstraction layer
- ⚠️ No price monitoring service

### Frontend Status
- ✅ Component-based architecture in place
- ⚠️ Most UI views are placeholders
- ⚠️ No real-time data synchronization
- ⚠️ Missing WebSocket integration
- ⚠️ No state management configured

---

## 2. Architectural Decisions & Decision Frameworks

To provide clear guidance, the following core architectural decisions have been made:

- **State Management (Frontend):** `Zustand` is chosen over Redux for its simplicity, minimal boilerplate, and hook-based API, which is well-suited for the real-time nature of the application without overwhelming complexity.
- **Component Library (Frontend):** `Material-UI (MUI)` is selected for its comprehensive set of components, robust theming capabilities, and adherence to established design principles, ensuring a professional and consistent UI.
- **Backend Framework:** `FastAPI` is used for its high performance, asynchronous support (critical for handling concurrent exchange communications), and automatic OpenAPI documentation generation.
- **ORM:** `SQLAlchemy` (asyncio version) is used for its power and flexibility, providing a robust data access layer that protects against SQL injection.
- **Exchange Integration:** `ccxt` is the chosen library for interacting with exchanges due to its broad support for multiple exchanges and standardization of their APIs. An abstraction layer will be built on top of it to ensure our application's business logic is decoupled from the library itself.

---

## 3. Business Rules & Formulas

This section explicitly defines the core financial logic required for the engine to operate correctly.

### 3.1 PnL Calculation
- **Unrealized PnL (USD):** `(Current Market Price - Weighted Average Entry Price) * Total Filled Quantity` (For shorts: `(Weighted Average Entry Price - Current Market Price) * ...`)
- **Unrealized PnL (%):** `(Unrealized PnL (USD) / Total Invested USD) * 100`
- **Realized PnL (USD):** Sum of PnL from all closed trades or partially closed quantities. For a single closing trade: `(Exit Price - Entry Price) * Closed Quantity - Fees`
- **Fee Handling:** All PnL calculations must subtract exchange fees. The `ccxt` library provides fee data in order responses, which must be fetched, stored against the `DCAOrder`, and factored into `Realized PnL`.

### 3.2 Capital Allocation & Position Sizing
- **Total Capital:** A user-configurable value representing the total capital to be used by the engine (e.g., `$10,000`).
- **Max Concurrent Positions:** A user-configurable number (e.g., `10`) that the Execution Pool enforces.
- **Capital Per Position Group:** `Total Capital / Max Concurrent Positions`. This is the total capital allocated to a single `PositionGroup`.
- **Position Sizing (Per DCA Leg):** The capital for each DCA leg is determined by its `weight_percent` applied to the `Capital Per Position Group`. Example: `($1000 per group) * (20% weight for DCA0) = $200` for the first leg. The quantity is then `Leg Capital / Entry Price`.

---

## 4. Logic Annex: Clarifications & Edge Case Definitions

This section provides explicit definitions for business logic to ensure deterministic behavior.

### 4.1 Calculation of "Current Loss %" for Queued Signals
For the purpose of queue prioritization (SoW 5.3), the "current loss percentage" of a signal that is not yet a live trade shall be calculated as follows:

- **Formula:** `Loss % = ((Current Market Price - Queued Signal Entry Price) / Queued Signal Entry Price) * 100`
- **Current Market Price:** The price will be fetched in real-time via the `Exchange Abstraction Layer` (`get_current_price(symbol)` method).
- **Implementation:** This calculation will be performed by the `QueueManagerService` just before it runs the promotion selection logic. The result is stored in the `current_loss_percent` field of the `QueuedSignal` model for the duration of the sorting process.

### 4.2 Definition of "Replacement Pyramid"
The term "replacement pyramid," used in the context of the Risk Engine's timer reset logic, is defined as:

- **Definition:** A new pyramid signal that arrives for a `PositionGroup` that has already reached its `max_pyramids` limit (e.g., 5 out of 5).
- **Timer Reset Logic:** The `risk.reset_timer_on_replacement` configuration flag, if `true`, will only reset the Risk Engine's timer if the timer is already active and running when the replacement pyramid signal is received. It has no effect if the timer has not yet started.

### 4.3 Exchange Error Mapping
To ensure consistent error handling and clear user feedback, `ccxt` exceptions will be caught and mapped to standardized application exceptions.

| `ccxt` Exception | Application Exception | UI Notification (Snackbar) |
|---|---|---|
| `AuthenticationError` | `InvalidCredentialsError` | **Error:** "Invalid API Credentials. Please check your keys in the Settings page." |
| `InsufficientFunds` | `InsufficientFundsError` | **Error:** "Insufficient funds on the exchange to place the order." |
| `InvalidOrder` | `OrderValidationError` | **Error:** "Order validation failed (e.g., invalid size or price). See logs for details." |
| `RateLimitExceeded` | `RateLimitError` | **Warning:** "Approaching exchange rate limits. Throttling requests." |
| `NetworkError` / `RequestTimeout` | `ExchangeConnectionError` | **Warning:** "Cannot connect to the exchange. Retrying..." |
| `ExchangeError` (Generic) | `GenericExchangeError` | **Error:** "An unknown exchange error occurred. See logs for the full response." |

---

## 5. Core Data Models & State Machines

### 5.1 PositionGroup Model

```python
from sqlalchemy import (Column, String, Integer, Numeric, DateTime, Boolean, JSON, ForeignKey, Enum as SQLAlchemyEnum)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal

# Assuming a Base declarative base is defined elsewhere
from .base import Base 

class PositionGroup(Base):
    """
    Represents a unique trading position defined by pair + timeframe.
    Contains multiple pyramids and DCA legs.
    """
    __tablename__ = "position_groups"
    
    # Identity
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    exchange = Column(String, nullable=False)  # "binance", "bybit", etc.
    symbol = Column(String, nullable=False)  # "BTCUSDT"
    timeframe = Column(Integer, nullable=False)  # in minutes (e.g., 15, 60, 240)
    side = Column(SQLAlchemyEnum("long", "short", name="position_side_enum"), nullable=False)
    
    # Status tracking
    status = Column(SQLAlchemyEnum(
        "waiting", "live", "partially_filled", "active", "closing", "closed", "failed",
        name="group_status_enum"
    ), nullable=False, default="waiting")
    
    # Pyramid tracking
    pyramid_count = Column(Integer, default=0)
    max_pyramids = Column(Integer, default=5)
    replacement_count = Column(Integer, default=0)
    
    # DCA tracking
    total_dca_legs = Column(Integer, nullable=False)
    filled_dca_legs = Column(Integer, default=0)
    
    # Financial metrics
    base_entry_price = Column(Numeric(20, 10), nullable=False)
    weighted_avg_entry = Column(Numeric(20, 10), nullable=False)
    total_invested_usd = Column(Numeric(20, 10), default=Decimal("0"))
    total_filled_quantity = Column(Numeric(20, 10), default=Decimal("0"))
    unrealized_pnl_usd = Column(Numeric(20, 10), default=Decimal("0"))
    unrealized_pnl_percent = Column(Numeric(10, 4), default=Decimal("0"))
    realized_pnl_usd = Column(Numeric(20, 10), default=Decimal("0"))
    
    # Take-profit configuration
    tp_mode = Column(SQLAlchemyEnum("per_leg", "aggregate", "hybrid", name="tp_mode_enum"), nullable=False)
    tp_aggregate_percent = Column(Numeric(10, 4))
    
    # Risk engine tracking
    risk_timer_start = Column(DateTime)
    risk_timer_expires = Column(DateTime)
    risk_eligible = Column(Boolean, default=False)
    risk_blocked = Column(Boolean, default=False)
    risk_skip_once = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime)
    
    # Relationships
    pyramids = relationship("Pyramid", back_populates="group", cascade="all, delete-orphan")
    dca_orders = relationship("DCAOrder", back_populates="group", cascade="all, delete-orphan")
    risk_actions = relationship("RiskAction", back_populates="group", cascade="all, delete-orphan")
```

### 5.2 Pyramid Model

```python
class Pyramid(Base):
    """
    Represents a single pyramid entry within a PositionGroup.
    """
    __tablename__ = "pyramids"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("position_groups.id"), nullable=False)
    pyramid_index = Column(Integer, nullable=False) # 0-4
    
    entry_price = Column(Numeric(20, 10), nullable=False)
    entry_timestamp = Column(DateTime, nullable=False)
    signal_id = Column(String) # TradingView signal ID
    
    status = Column(SQLAlchemyEnum("pending", "submitted", "filled", "cancelled", name="pyramid_status_enum"), nullable=False)
    dca_config = Column(JSON, nullable=False)
    
    group = relationship("PositionGroup", back_populates="pyramids")
    dca_orders = relationship("DCAOrder", back_populates="pyramid", cascade="all, delete-orphan")
```

### 5.3 DCAOrder Model

```python
class DCAOrder(Base):
    """
    Represents a single DCA order (limit order at specific price level).
    """
    __tablename__ = "dca_orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("position_groups.id"), nullable=False)
    pyramid_id = Column(UUID(as_uuid=True), ForeignKey("pyramids.id"), nullable=False)
    
    exchange_order_id = Column(String)
    leg_index = Column(Integer, nullable=False)
    
    symbol = Column(String, nullable=False)
    side = Column(SQLAlchemyEnum("buy", "sell", name="order_side_enum"), nullable=False)
    order_type = Column(SQLAlchemyEnum("limit", "market", name="order_type_enum"), default="limit")
    price = Column(Numeric(20, 10), nullable=False)
    quantity = Column(Numeric(20, 10), nullable=False)
    
    gap_percent = Column(Numeric(10, 4), nullable=False)
    weight_percent = Column(Numeric(10, 4), nullable=False)
    tp_percent = Column(Numeric(10, 4), nullable=False)
    tp_price = Column(Numeric(20, 10), nullable=False)
    
    status = Column(SQLAlchemyEnum("pending", "open", "partially_filled", "filled", "cancelled", "failed", name="order_status_enum"), nullable=False)
    filled_quantity = Column(Numeric(20, 10), default=Decimal("0"))
    avg_fill_price = Column(Numeric(20, 10))
    
    tp_hit = Column(Boolean, default=False)
    tp_order_id = Column(String)
    tp_executed_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime)
    filled_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    
    group = relationship("PositionGroup", back_populates="dca_orders")
    pyramid = relationship("Pyramid", back_populates="dca_orders")
```

### 5.4 QueuedSignal Model

```python
class QueuedSignal(Base):
    """
    Represents a signal waiting in the queue.
    """
    __tablename__ = "queued_signals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(Integer, nullable=False)
    side = Column(SQLAlchemyEnum("long", "short", name="signal_side_enum"), nullable=False)
    entry_price = Column(Numeric(20, 10), nullable=False)
    signal_payload = Column(JSON, nullable=False)
    
    queued_at = Column(DateTime, default=datetime.utcnow)
    replacement_count = Column(Integer, default=0)
    priority_score = Column(Numeric(20, 4), default=0.0)
    
    is_pyramid_continuation = Column(Boolean, default=False)
    current_loss_percent = Column(Numeric(10, 4))
    
    status = Column(SQLAlchemyEnum("queued", "promoted", "cancelled", name="queue_status_enum"), nullable=False)
    promoted_at = Column(DateTime)
```

### 5.5 RiskAction Model

```python
class RiskAction(Base):
    """
    Records actions taken by the Risk Engine.
    """
    __tablename__ = "risk_actions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("position_groups.id"), nullable=False)
    
    action_type = Column(SQLAlchemyEnum("offset_loss", "manual_block", "manual_skip", name="risk_action_type_enum"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Details for offset_loss
    loser_group_id = Column(UUID(as_uuid=True), ForeignKey("position_groups.id"))
    loser_pnl_usd = Column(Numeric(20, 10))
    
    # Details for winners (JSON array of {group_id, pnl_usd, quantity_closed})
    winner_details = Column(JSON)
    
    notes = Column(String)
    
    group = relationship("PositionGroup", foreign_keys=[group_id], back_populates="risk_actions")
    loser_group = relationship("PositionGroup", foreign_keys=[loser_group_id])
```

### 5.6 State Machine: PositionGroup Status

```
State Flow:
┌─────────┐
│ waiting │ (In queue, pool full)
└────┬────┘
     │ Pool slot available
     ↓
┌──────────┐
│   live   │ (Orders submitted, no fills yet)
└────┬─────┘
     │ First DCA filled
     ↓
┌──────────────────┐
│ partially_filled │ (Some DCA filled, some pending)
└────┬─────────────┘
     │ All DCA filled OR monitoring active
     ↓
┌──────────┐
│  active  │ (Full grid filled, TP monitoring running)
└────┬─────┘
     │ Exit signal OR TP hit OR Risk engine action
     ↓
┌─────────┐
│ closing │ (Exit orders being placed)
└────┬────┘
     │ All positions closed
     ↓
┌────────┐
│ closed │ (Final state, slot released)
└────────┘
```

### 5.7 State Machine: Order Status

```
Order Lifecycle:
┌─────────┐
│ pending │ (Created, not submitted)
└────┬────┘
     │ Submit to exchange
     ↓
┌──────┐
│ open │ (On exchange order book)
└──┬───┘
   │
   ├──→ partially_filled (Partial execution)
   │         │
   │         ├──→ filled (Rest filled)
   │         └──→ cancelled (User cancels)
   │
   ├──→ filled (Full execution)
   │
   └──→ cancelled (User/system cancels)
```

---

## 6. Algorithm Specifications

### 6.1 Queue Priority Calculation

```python
def calculate_queue_priority(signal: QueuedSignal, active_groups: List[PositionGroup]) -> float:
    """
    Four-tier priority system as per SoW Section 5.3:
    
    Priority 1 (Highest): Pyramid continuation of active group
    Priority 2: Deepest current loss percentage
    Priority 3: Highest replacement count
    Priority 4 (Lowest): FIFO (oldest first)
    
    Returns a composite score where higher = higher priority.
    """
    
    # Tier 1: Check if pyramid continuation
    existing_group = find_active_group(
        active_groups, 
        signal.symbol, 
        signal.timeframe
    )
    
    if existing_group:
        # Pyramid continuation - highest priority tier
        # Score: 1,000,000 + inverse age (newer = higher)
        time_in_queue = (datetime.utcnow() - signal.queued_at).total_seconds()
        return 1_000_000 + (10_000 - time_in_queue)
    
    # Tier 2: Loss percentage (higher loss = higher priority)
    # Score: 100,000 + (loss_percent * 1000)
    # Example: -8% loss = 100,000 + 8,000 = 108,000
    if signal.current_loss_percent:
        loss_score = abs(signal.current_loss_percent) * 1000
        return 100_000 + loss_score
    
    # Tier 3: Replacement count
    # Score: 10,000 + (replacement_count * 100)
    if signal.replacement_count > 0:
        return 10_000 + (signal.replacement_count * 100)
    
    # Tier 4: FIFO (oldest = highest priority in this tier)
    # Score: 1,000 + inverse timestamp
    # Earlier queued signals get higher scores
    time_in_queue = (datetime.utcnow() - signal.queued_at).total_seconds()
    fifo_score = min(time_in_queue, 999)  # Cap at 999 seconds
    return 1_000 + fifo_score


def promote_from_queue(queued_signals: List[QueuedSignal], 
                       active_groups: List[PositionGroup]) -> Optional[QueuedSignal]:
    """
    Select highest priority signal from queue.
    Pyramid continuations bypass max position limit.
    """
    if not queued_signals:
        return None
    
    # Calculate priority for all queued signals
    prioritized = [
        (signal, calculate_queue_priority(signal, active_groups))
        for signal in queued_signals
    ]
    
    # Sort by priority score (descending)
    prioritized.sort(key=lambda x: x[1], reverse=True)
    
    # Return highest priority signal
    selected_signal, priority_score = prioritized[0]
    
    logger.info(
        f"Promoting signal {selected_signal.id} "
        f"(priority: {priority_score}, "
        f"replacement_count: {selected_signal.replacement_count})"
    )
    
    return selected_signal
```

### 6.2 Risk Engine: Loser and Winner Selection

```python
def select_loser_and_winners(
    position_groups: List[PositionGroup],
    config: RiskEngineConfig
) -> Tuple[Optional[PositionGroup], List[PositionGroup], Decimal]:
    """
    Risk Engine selection logic (SoW Section 4.4 & 4.5):
    
    Loser Selection (by % loss):
    1. Highest loss percentage
    2. If tied → highest unrealized loss USD
    3. If tied → oldest trade
    
    Winner Selection (by $ profit):
    - Rank all winning positions by unrealized profit USD
    - Select up to max_winners_to_combine (default: 3)
    
    Offset Execution:
    - Calculate required_usd to cover loser
    - Close winners partially to realize that amount
    """
    
    # Filter eligible losers
    eligible_losers = []
    for pg in position_groups:
        # Must meet all conditions
        if not all([
            pg.status == "active",
            pg.pyramid_count >= 5 if config.require_full_pyramids else True,
            pg.risk_timer_expires and pg.risk_timer_expires <= datetime.utcnow(),
            pg.unrealized_pnl_percent <= config.loss_threshold_percent,
            not pg.risk_blocked,
            not pg.risk_skip_once
        ]):
            continue
        
        # Age filter (optional)
        if config.use_trade_age_filter:
            age_minutes = (datetime.utcnow() - pg.created_at).total_seconds() / 60
            if age_minutes < config.age_threshold_minutes:
                continue
        
        eligible_losers.append(pg)
    
    if not eligible_losers:
        return None, [], Decimal("0")
    
    # Sort losers by priority
    selected_loser = max(eligible_losers, key=lambda pg: (
        abs(pg.unrealized_pnl_percent),  # Primary: highest loss %
        abs(pg.unrealized_pnl_usd),      # Secondary: highest loss $
        -pg.created_at.timestamp()        # Tertiary: oldest
    ))
    
    required_usd = abs(selected_loser.unrealized_pnl_usd)
    
    # Select winners
    winning_positions = [
        pg for pg in position_groups
        if pg.status == "active" and pg.unrealized_pnl_usd > 0
    ]
    
    # Sort by USD profit (descending)
    winning_positions.sort(
        key=lambda pg: pg.unrealized_pnl_usd,
        reverse=True
    )
    
    # Take up to max_winners_to_combine
    selected_winners = winning_positions[:config.max_winners_to_combine]
    
    # Verify sufficient profit
    total_available_profit = sum(w.unrealized_pnl_usd for w in selected_winners)
    
    if total_available_profit < required_usd:
        logger.warning(
            f"Insufficient profit to cover loss. "
            f"Required: {required_usd}, Available: {total_available_profit}"
        )
        # Still return - caller decides whether to execute partial offset
    
    return selected_loser, selected_winners, required_usd


def calculate_partial_close_quantities(
    winners: List[PositionGroup],
    required_usd: Decimal,
    precision_rules: Dict
) -> List[Tuple[PositionGroup, Decimal]]:
    """
    Calculate how much to close from each winner to realize required_usd.
    
    Returns: List of (PositionGroup, quantity_to_close)
    """
    close_plan = []
    remaining_needed = required_usd
    
    for winner in winners:
        if remaining_needed <= 0:
            break
        
        # Calculate how much profit this winner can contribute
        available_profit = winner.unrealized_pnl_usd
        
        # Determine how much of this winner to close
        profit_to_take = min(available_profit, remaining_needed)
        
        # Calculate quantity to close to realize this profit
        # profit_per_unit = current_price - avg_entry
        current_price = get_current_price(winner.symbol)
        profit_per_unit = current_price - winner.weighted_avg_entry
        
        quantity_to_close = profit_to_take / profit_per_unit
        
        # Round to step size
        step_size = precision_rules[winner.symbol]["step_size"]
        quantity_to_close = round_to_step_size(quantity_to_close, step_size)
        
        # Check minimum notional
        notional_value = quantity_to_close * current_price
        min_notional = precision_rules[winner.symbol]["min_notional"]
        
        if notional_value < min_notional:
            logger.warning(
                f"Partial close for {winner.symbol} below min notional "
                f"({notional_value} < {min_notional}). Skipping."
            )
            continue
        
        close_plan.append((winner, quantity_to_close))
        remaining_needed -= profit_to_take
    
    return close_plan
```

### 6.3 Take-Profit Monitoring

```python
async def check_take_profit_conditions(
    position_group: PositionGroup,
    current_price: Decimal
) -> List[DCAOrder]:
    """
    Check TP conditions based on tp_mode.
    Returns list of DCA orders that hit their TP target.
    
    Three modes (SoW Section 2.4):
    1. per_leg: Each DCA closes independently
    2. aggregate: Entire position closes when avg entry reaches TP
    3. hybrid: Both logics run, whichever closes first
    """
    orders_to_close = []
    
    if position_group.tp_mode == "per_leg":
        # Check each filled DCA leg individually
        for order in position_group.dca_orders:
            if order.status == "filled" and not order.tp_hit:
                if is_tp_reached(order, current_price, position_group.side):
                    orders_to_close.append(order)
    
    elif position_group.tp_mode == "aggregate":
        # Check if weighted average entry reached aggregate TP
        target_price = calculate_aggregate_tp_price(
            position_group.weighted_avg_entry,
            position_group.tp_aggregate_percent,
            position_group.side
        )
        
        if is_price_beyond_target(current_price, target_price, position_group.side):
            # Close entire position
            orders_to_close = [
                order for order in position_group.dca_orders
                if order.status == "filled" and not order.tp_hit
            ]
    
    elif position_group.tp_mode == "hybrid":
        # Check both per-leg and aggregate
        # Whichever triggers first wins
        
        # Per-leg check
        per_leg_triggered = []
        for order in position_group.dca_orders:
            if order.status == "filled" and not order.tp_hit:
                if is_tp_reached(order, current_price, position_group.side):
                    per_leg_triggered.append(order)
        
        # Aggregate check
        aggregate_target = calculate_aggregate_tp_price(
            position_group.weighted_avg_entry,
            position_group.tp_aggregate_percent,
            position_group.side
        )
        aggregate_triggered = is_price_beyond_target(
            current_price, aggregate_target, position_group.side
        )
        
        if per_leg_triggered:
            # Per-leg TP hit - close those legs only
            orders_to_close = per_leg_triggered
        elif aggregate_triggered:
            # Aggregate TP hit - close entire position
            orders_to_close = [
                order for order in position_group.dca_orders
                if order.status == "filled" and not order.tp_hit
            ]
    
    return orders_to_close


def is_tp_reached(order: DCAOrder, current_price: Decimal, side: str) -> bool:
    """
    Check if current price reached the TP target for this order.
    TP is calculated from actual fill price, not original entry.
    """
    if side == "long":
        # Long: current_price >= tp_price
        return current_price >= order.tp_price
    else:
        # Short: current_price <= tp_price
        return current_price <= order.tp_price


def calculate_aggregate_tp_price(
    weighted_avg_entry: Decimal,
    tp_percent: Decimal,
    side: str
) -> Decimal:
    """
    Calculate aggregate TP price from weighted average entry.
    """
    if side == "long":
        return weighted_avg_entry * (1 + tp_percent / 100)
    else:
        return weighted_avg_entry * (1 - tp_percent / 100)
```

### 6.4 DCA Grid Calculation

```python
def calculate_dca_levels(
    base_price: Decimal,
    dca_config: List[Dict],
    side: Literal["long", "short"],
    precision_rules: Dict
) -> List[Dict]:
    """
    Calculate DCA price levels with per-layer configuration.
    
    dca_config format (SoW Section 2.3):
    [
        {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
        {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
        ...
    ]
    
    Returns list of:
    {
        "leg_index": 0,
        "price": Decimal("50000.00"),
        "quantity": Decimal("0.001"),
        "gap_percent": Decimal("0.0"),
        "weight_percent": Decimal("20"),
        "tp_percent": Decimal("1.0"),
        "tp_price": Decimal("50500.00")
    }
    """
    tick_size = precision_rules["tick_size"]
    step_size = precision_rules["step_size"]
    
    dca_levels = []
    
    for idx, layer in enumerate(dca_config):
        gap_percent = Decimal(str(layer["gap_percent"]))
        weight_percent = Decimal(str(layer["weight_percent"]))
        tp_percent = Decimal(str(layer["tp_percent"]))
        
        # Calculate DCA entry price
        if side == "long":
            # Long: negative gap means lower price (discount)
            dca_price = base_price * (1 + gap_percent / 100)
        else:
            # Short: negative gap means higher price
            dca_price = base_price * (1 - gap_percent / 100)
        
        # Round to tick size
        dca_price = round_to_tick_size(dca_price, tick_size)
        
        # Calculate TP price (from DCA entry, not base price)
        if side == "long":
            tp_price = dca_price * (1 + tp_percent / 100)
        else:
            tp_price = dca_price * (1 - tp_percent / 100)
        
        tp_price = round_to_tick_size(tp_price, tick_size)
        
        dca_levels.append({
            "leg_index": idx,
            "price": dca_price,
            "gap_percent": gap_percent,
            "weight_percent": weight_percent,
            "tp_percent": tp_percent,
            "tp_price": tp_price
        })
    
    return dca_levels


def calculate_order_quantities(
    dca_levels: List[Dict],
    total_capital_usd: Decimal,
    precision_rules: Dict
) -> List[Dict]:
    """
    Calculate order quantity for each DCA level based on weight allocation.
    """
    step_size = precision_rules["step_size"]
    min_qty = precision_rules["min_qty"]
    min_notional = precision_rules["min_notional"]
    
    for level in dca_levels:
        # Calculate capital for this leg
        leg_capital = total_capital_usd * (level["weight_percent"] / 100)
        
        # Calculate quantity: capital / price
        quantity = leg_capital / level["price"]
        
        # Round to step size
        quantity = round_to_step_size(quantity, step_size)
        
        # Validate minimum quantity
        if quantity < min_qty:
            raise ValidationError(
                f"Quantity {quantity} below minimum {min_qty}"
            )
        
        # Validate minimum notional
        notional = quantity * level["price"]
        if notional < min_notional:
            raise ValidationError(
                f"Notional {notional} below minimum {min_notional}"
            )
        
        level["quantity"] = quantity
    
    return dca_levels
```

---

## 7. UI/UX Design System & Component Architecture

This section provides low-fidelity wireframes and defines component structures and user interactions to guide frontend development.

### 7.1 Wireframes

#### 7.1.1 Dashboard Page (`/`)
```
+--------------------------------------------------------------------------------------------------+
| [Header: Engine Status: Running (Green)] [Total PnL: +$1,234.56 (+1.23%)] [Theme Toggle] [User]   |
+--------------------------------------------------------------------------------------------------+
| [Sidebar Nav] | [Widget: Pool Usage] [Widget: Queued Signals] [Widget: Risk Engine] [Widget: Last Webhook] |
|               | 8 / 10 (ProgressBar) | 3                     | Active (Green)      | 10 seconds ago     |
|               +----------------------+-----------------------+---------------------+--------------------+
|               |                                                                                      |
|               | [Chart: Equity Curve (Realized PnL)]                                                 |
|               |                                                                                      |
|               |                                                                                      |
|               +--------------------------------------------------------------------------------------+
|               | [Widget Group: PnL Metrics] [Widget Group: Win/Loss Stats] [Widget Group: Daily Summary] |
|               | Realized: $500          | Win Rate: 65%              | Trades: 15                     |
|               | Unrealized: $734.56     | Avg Win: $150              | Volume: $50,000                |
+--------------------------------------------------------------------------------------------------+
```

#### 7.1.2 Positions Page (`/positions`)
```
+--------------------------------------------------------------------------------------------------+
| [Header]                                                                                         |
+--------------------------------------------------------------------------------------------------+
| [Sidebar Nav] | [Toolbar: [Filter by Symbol...] [Filter by Status...] [Clear Filters]]            |
|               +----------------------------------------------------------------------------------+
|               | [DataGrid Header]                                                                |
|               | Pair/TF | Pyramids | DCA Filled | Avg Entry | Unrealized PnL | TP Mode | Status   |
|               +----------------------------------------------------------------------------------+
|               | BTCUSDT 1h| 5 / 5    | 3 / 7      | 65000.00  | +$500 (+2%)    | leg     | active   |
|               | ETHUSDT 15m| 2 / 5    | 1 / 7      | 3500.00   | -$100 (-1%)    | hybrid  | active   |
|               |   [v] Expand Row...                                                              |
|               |   +------------------------------------------------------------------------------+
|               |   | Leg ID | Fill Price | Weight | TP Target | Progress | Filled Size | State    |
|               |   +------------------------------------------------------------------------------+
|               |   | DCA0   | 3550.00    | 20%    | +1.0%     | 50%      | 200 USDT    | filled   |
|               |   | DCA1   | 3532.25    | 20%    | +0.5%     | 0%       | 0 USDT      | open     |
+--------------------------------------------------------------------------------------------------+
```

### 7.2 Micro-interaction Definitions

This defines the step-by-step UX for critical user actions.

**Action: "Force Add to Pool" (from Waiting Queue View)**
1.  **Trigger:** User clicks the "Force Add" icon button on a row in the waiting queue table.
2.  **Confirmation:** A modal dialog appears.
    -   **Title:** "Confirm Pool Override"
    -   **Text:** "This action will override the 'Max Open Groups' limit and immediately execute the signal for **BTCUSDT 15m**. Are you sure you want to proceed?"
    -   **Buttons:** "Cancel" (secondary), "Confirm & Execute" (primary, red color).
3.  **Loading State:** Upon clicking "Confirm & Execute," the modal closes, and the button that was clicked now shows a circular loading spinner. The row may be visually disabled.
4.  **Success Feedback:**
    -   A green "Snackbar" notification appears at the bottom-left of the screen: "Success: Position group for BTCUSDT 15m has been forced into the pool."
    -   The signal is removed from the Waiting Queue table and appears in the Positions table.
5.  **Failure Feedback:**
    -   A red "Snackbar" notification appears: "Error: Could not force position into the pool. See logs for details."
    -   The loading spinner on the button disappears, and the button becomes clickable again.

### 7.3 Component Architecture

**Page: `PositionsPage.tsx`**
-   **`PositionsPage` (Container Component):**
    -   Fetches data from the WebSocket/Zustand store.
    -   Manages page-level state (e.g., filters).
    -   Renders `PositionsTable`.
-   **`PositionsTable` (Presentational Component):**
    -   Receives positions data as props.
    -   Renders the main `MUI X Data Grid`.
    -   Renders `PositionsToolbar` in the toolbar slot.
    -   Renders `PositionRow` for each item.
-   **`PositionsToolbar`:**
    -   Contains input fields for filtering by symbol and status.
    -   Emits filter change events to the parent.
-   **`PositionRow`:**
    -   Renders the cells for a single position group.
    -   Uses `StatusChip` and `PnlCell` for specific columns.
    -   Manages the expanded/collapsed state for its `ExpandableRowContent`.
-   **`StatusChip`:**
    -   A small component that displays the position status with a color-coded background (e.g., green for "active", orange for "waiting").
-   **`PnlCell`:**
    -   Renders the PnL value, colored green for positive and red for negative.
-   **`ExpandableRowContent`:**
    -   Renders the `DcaLegsTable` when the row is expanded.
-   **`DcaLegsTable`:**
    -   A simple table displaying the details of each DCA leg for the selected position.

---

## 8. User Journeys

### 8.1 First-Time User Onboarding
1.  **Registration/Login:** User creates an account and logs in.
2.  **Welcome Screen:** A modal or welcome page appears, guiding the user through the initial setup.
3.  **Exchange API Setup:**
    - User is prompted to navigate to the "Settings" page.
    - User selects an exchange (e.g., Binance).
    - User enters their API Key and Secret Key.
    - The application performs a connectivity and permissions check (`fetchBalance`).
    - On success, the keys are encrypted and saved. On failure, a specific error is shown (e.g., "Invalid API Key" or "Missing 'Futures Trading' permission").
4.  **Initial Configuration:** The user is guided to set critical parameters like `Total Capital` and `Max Concurrent Positions`. A "Quick Start" configuration template is provided.
5.  **Dashboard Activation:** Once the API keys and initial configuration are saved, the main dashboard becomes active, and the engine starts its monitoring loops.

### 8.2 Error Recovery UX
- **Invalid API Key:** If an API call fails with an authentication error, the system will:
    - Immediately pause all trading activity for that user.
    - Set the "Engine Status" banner to "Error: Invalid API Credentials".
    - Display a persistent notification prompting the user to update their keys in the Settings page.
    - The `PositionGroup`s will enter a `failed` state.
- **Insufficient Funds:** When placing an order, if the exchange returns an insufficient funds error:
    - The order is marked as `failed`.
    - A high-priority alert is added to the "Logs & Alerts" page.
    - The user is notified via a UI notification.
    - The system will not attempt to place further orders for that `PositionGroup`.

---

## 9. Operational Manual & Environment Setup

This section provides concrete steps and configurations for bootstrapping and maintaining the development environment.

### 9.1 Initial Environment Bootstrap

To set up the development environment from a fresh clone of the repository, run the following script from the project root:

**`scripts/bootstrap.sh`**
```bash
#!/bin/bash
set -e

echo "Bootstrapping development environment..."

# 1. Check for Docker
if ! [ -x "$(command -v docker)" ]; then
  echo 'Error: docker is not installed.' >&2
  exit 1
fi

# 2. Copy .env file if it does not exist
if [ -f .env ]; then
    echo ".env file already exists. Skipping creation."
else
    echo "Creating .env from .env.example..."
    cp .env.example .env
    # In a real scenario, you might generate secrets here
    # For now, we assume the user will fill them in.
    echo "IMPORTANT: Please fill in the secret keys in the .env file."
fi

# 3. Build and start Docker containers
echo "Building Docker containers..."
docker compose build

echo "Starting services in detached mode..."
docker compose up -d

# 4. Apply initial database migrations
echo "Waiting for database to be ready..."
sleep 10 # Simple wait, a more robust script would poll the DB
echo "Applying initial database migrations..."
docker compose exec app alembic upgrade head

echo "Bootstrap complete. Application is running at http://localhost:8000"
```

### 9.2 Exact Dependency Versions

To ensure a reproducible build, the following package versions must be used.

**Backend (`requirements.txt`)**
```
fastapi==0.104.1
sqlalchemy==2.0.23
alembic==1.12.1
ccxt==4.1.59
pydantic==2.4.2
pytest==7.4.3
uvicorn==0.24.0
psycopg2-binary==2.9.9
python-dotenv==1.0.0
cryptography==41.0.5
slowapi==0.1.8
```

**Frontend (`package.json`)**
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@mui/material": "^5.14.18",
    "@mui/x-data-grid": "^6.18.2",
    "@emotion/react": "^11.11.1",
    "@emotion/styled": "^11.11.0",
    "zustand": "^4.4.7",
    "axios": "^1.6.2",
    "react-router-dom": "^6.20.0",
    "react-hook-form": "^7.48.2"
  }
}
```

---

## 10. Operational Runbook & Monitoring

### 10.1 Monitoring & Alerting
- **Health Checks:** The `/api/health` endpoint will be expanded to check:
    - Database connectivity (`SELECT 1`).
    - Exchange API connectivity (pinging the exchange).
    - Background task status (e.g., is the order monitor running?).
- **Performance Benchmarks:**
    - **Webhook to Order Placement Latency:** < 500ms.
    - **API Response Time (p95):** < 200ms for all GET requests.
    - **Price Update to TP Execution Latency:** < 1 second.
- **Alerting:** An external monitoring service (like UptimeRobot or Prometheus) should be configured to poll the health check endpoint. If the endpoint returns an unhealthy status or fails to respond for > 2 minutes, an alert (e.g., email, Slack) should be triggered.

### 10.2 Data Migration & Rollbacks
- **Data Migration:** All database schema changes **must** be handled through Alembic migrations. The process is:
    1.  Generate a new migration file: `docker compose exec app alembic revision --autogenerate -m "description"`.
    2.  Manually review and test the migration script in a staging environment.
    3.  Apply the migration during a scheduled maintenance window: `docker compose exec app alembic upgrade head`.
- **Deployment Rollback Procedure:**
    1.  If a new deployment is found to be faulty, the previous Docker container tag should be redeployed immediately.
    2.  If a database migration was part of the faulty deployment, the corresponding `docker compose exec app alembic downgrade -1` command must be run to revert the schema change. This is a critical step and requires that all migrations have a correctly implemented `downgrade` function.

---

## 11. Quality Gates & Testing Strategy

This section defines the quality assurance approach for the project, including clear gates that must be passed before moving between phases or deploying.

### 11.1 Quality Gates
Each major development phase (e.g., Backend Phase 1, Frontend Phase 1) will conclude with a Quality Gate review. To pass the gate, the following criteria must be met:
- **Code Review:** All code has been peer-reviewed and approved.
- **Unit Test Coverage:** All new code meets or exceeds the 85% unit test coverage threshold.
- **Integration Tests:** All related integration tests are passing.
- **SoW Compliance:** A check is performed to ensure all SoW requirements for that phase are met (verified against the Traceability Matrix).
- **Documentation:** All new components, services, and endpoints are documented.

### 11.2 Testing Strategy
- **Unit Testing:** `pytest` for the backend, `Jest` & `React Testing Library` for the frontend. Focuses on isolating and testing individual functions and components.
- **Integration Testing:** A dedicated `pytest` suite that runs against a Dockerized environment (app + DB + mock exchange). It tests the interactions between services (e.g., webhook ingestion to order placement).
- **Performance Testing:** A `locust.io` test suite will be created to simulate high-load scenarios, specifically:
    - High volume of incoming webhooks (100+ per minute).
    - High number of concurrent open positions (200+).
    - The test will measure API response times and PnL calculation latency under load to ensure they meet the benchmarks defined in the Operational Runbook.
- **Security Testing:**
    - **Dependency Scanning:** `pip-audit` will be integrated into the CI/CD pipeline to check for vulnerabilities in dependencies.
    - **Penetration Testing (Manual):** Before final release, a manual penetration test will be conducted focusing on:
        - SQL Injection (verifying ORM protection).
        - Cross-Site Scripting (XSS) in the frontend.
        - Insecure Direct Object References (e.g., ensuring a user cannot access another user's data via API).
- **User Acceptance Testing (UAT):** A set of test cases will be defined for end-users to perform in a staging environment. The application is considered "done" when:
    - Users can complete the entire onboarding journey without assistance.
    - Users can successfully create and monitor a position from a webhook signal.
    - The dashboard and PnL metrics correctly reflect the user's trading activity.
    - The user finds the UI intuitive and the provided documentation sufficient.

---

## 12. Configuration Templates & Troubleshooting

### 12.1 Example `.env` Configuration

```env
# --- Database ---
DATABASE_URL=postgresql://tv_user:your_password@db:5432/tv_engine_db

# --- Security ---
JWT_SECRET=a_very_strong_and_long_secret_key_for_jwt
ENCRYPTION_KEY=a_32_byte_long_secret_key_for_encrypting_api_keys

# --- Application Settings ---
LOG_LEVEL=INFO
# Set to "binance" or "bybit" to use a real exchange, or "mock" for testing
EXCHANGE_TYPE=mock 
```

### 12.2 Example User Configuration (JSON for UI Settings Panel)

```json
{
  "total_capital_usd": 10000,
  "max_open_groups": 10,
  "exchange_api": {
    "binance": {
      "api_key": "YOUR_BINANCE_API_KEY",
      "secret_key": "YOUR_BINANCE_SECRET_KEY"
    },
    "bybit": {
      "api_key": "YOUR_BYBIT_API_KEY",
      "secret_key": "YOUR_BYBIT_SECRET_KEY"
    }
  },
  "risk_engine": {
    "loss_threshold_percent": -5.0,
    "require_full_pyramids": true,
    "timer_start_condition": "after_all_dca_filled",
    "max_winners_to_combine": 3
  },
  "dca_grid_config_default": [
    {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
    {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
    {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
    {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
    {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
  ]
}
```

### 12.3 Troubleshooting Guide

| Symptom | Possible Cause | Troubleshooting Steps |
|---|---|---|
| **500 Internal Server Error on API** | A backend programming error occurred. | 1. Check the backend logs for a Python traceback: `docker compose logs app --tail=50`. <br> 2. The traceback will point to the exact file and line causing the error. |
| **403 Forbidden Error** | Your user role does not have permission for this action. | 1. Verify your user role in the database or via the `/api/auth/me` endpoint. <br> 2. This is expected if a "trader" tries to access an admin-only page. |
| **Engine Status is "Error: Invalid API Credentials"** | The saved API key/secret for your exchange is incorrect or has expired. | 1. Go to the Settings page. <br> 2. Re-enter your API Key and Secret for the configured exchange. <br> 3. The system will re-validate them. A success message will appear, and the engine status will return to "Running". |
| **Orders are not placing, "Insufficient Funds" in logs** | The exchange reports you do not have enough capital for the trade. | 1. Check your available balance on the exchange website. <br> 2. In the Settings panel, ensure your `total_capital_usd` and `max_open_groups` are set correctly, as this determines the capital allocated per trade. |

---

## 13. Development Plan

### Backend Phase 1: Database Architecture


#### Objectives
Design and implement the complete database schema, migrations, and data access layer.

#### Steps
0.  **Create Tests:** Write unit tests for the repository pattern and data models. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git) (Status: In Progress - Currently fixing unit test failures related to SQLAlchemy async mocking and indentation errors.)
1.  **Implement Models:** Translate the data models from Section 3 into SQLAlchemy code. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Generate Initial Migration:** Run `docker compose exec app alembic revision --autogenerate -m "initial_schema"`. Manually review and refine the generated script. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Create Repository Pattern:** Implement a `BaseRepository` and specific repositories (e.g., `PositionGroupRepository`) for all major models. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Configure Connection Pooling:** Set up the SQLAlchemy engine with `pool_size=20`, `max_overflow=10`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Implement Transaction Management:** Create a dependency-injected database session that ensures `commit` on success and `rollback` on failure. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Script Backup/Restore:** Create `scripts/backup_db.sh` and `scripts/restore_db.sh`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
7.  **Add Health Check Endpoint:** Create a `/api/health/db` endpoint that performs a `SELECT 1` query. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ Schema supports all SoW entities. Migrations are repeatable.
- **Technical:** ✅ Connection pooling is active. Transactions auto-rollback. Indexes are on `(user_id)`, `(symbol, timeframe, status)`.
- **Test Coverage:** ✅ >90% on all repository methods.
- **Performance:** ✅ `get_by_id` < 5ms. `get_active_groups` < 20ms.
- **Error Handling:** ✅ Handles DB connection timeouts with retries.

#### Validation Checkpoint
1.  **Demo:** Run migration, insert data, show rollback, demo health check.
2.  **Review:** [ ] Schema matches models. [ ] Indexes are correct.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.

### Backend Phase 2: Webhook & Signal Processing


#### Objectives
Build a secure and robust pipeline for ingesting, validating, and routing TradingView signals.

#### Steps
0.  **Create Tests:** Write unit tests for signature validation, payload parsing, and signal routing. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Implement Signature Validation:** Create a FastAPI dependency that compares a hash of the request body with a secret key. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Create Pydantic Parsers:** Define strict Pydantic models for all incoming webhook payloads to ensure type safety and validation. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Build Signal Validator Service:** Create `SignalValidatorService` to check for logical consistency (e.g., `action` matches `strategy`). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Implement Signal Router Service:** Create `SignalRouterService` that takes a validated signal and determines if it's a new group, a pyramid, or an exit, then calls the appropriate downstream service (`PositionManager`, `QueueManager`, etc.). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Add Rate Limiting:** Use a library like `slowapi` to limit incoming requests per user to prevent abuse. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ Only valid, signed webhooks are processed. Signals are correctly routed based on SoW logic.
- **Technical:** ✅ Pydantic models enforce payload structure. Services are decoupled and testable.
- **Test Coverage:** ✅ Unit tests for valid/invalid signatures, malformed payloads, and all routing logic paths.
- **Security:** ✅ Protected against replay attacks and unauthorized access via signature validation.

#### Validation Checkpoint
1.  **Demo:** Show valid webhook processing and invalid webhook rejection.
2.  **Review:** [ ] Signature validation is secure. [ ] All signal types are routed.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 3: Exchange Abstraction Layer

#### Objectives
Create a flexible and extensible exchange integration layer that can support multiple exchanges (Binance, Bybit initially), with robust error handling and precision management.

#### Steps
0.  **Create Tests:** Write unit tests for the `ExchangeInterface`, connector factory, and error mapping. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Design `ExchangeInterface`:** Create an Abstract Base Class (ABC) defining the contract for all exchange connectors. Methods will include `get_precision_rules`, `place_order`, `get_order_status`, `cancel_order`, `get_current_price`, `fetch_balance`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Implement Connector Factory:** Create a factory function or class that returns the correct connector instance (e.g., `BinanceConnector`) based on the user's configuration. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Implement `BinanceConnector`:** Implement the `ExchangeInterface` for the Binance exchange using the `ccxt` library. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Implement `BybitConnector`:** Implement the `ExchangeInterface` for the Bybit exchange. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Implement Precision Service:** Create a background service (`PrecisionService`) that periodically (e.g., every 60 minutes) fetches and caches precision rules for all symbols for all configured user exchanges. Implement an in-memory cache with a Time-To-Live (TTL). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Standardize Data Models:** Create internal Pydantic models for `Order`, `Fill`, and `Precision` to standardize the data returned from all connectors, decoupling the application from `ccxt`'s specific data structures. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
7.  **Implement Error Mapping:** Create a decorator or utility to wrap all `ccxt` calls. This wrapper will catch `ccxt` exceptions and map them to the custom application exceptions defined in the **Logic Annex**. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ The system can place orders, check status, and fetch precision on both Binance and Bybit testnets. ✅ Precision rules are fetched and cached automatically.
- **Technical:** ✅ All exchange interactions go through the abstraction layer. ✅ Connectors are interchangeable via the factory. ✅ The error mapping from the Logic Annex is fully implemented.
- **Test Coverage:** ✅ >90% unit test coverage for both `BinanceConnector` and `BybitConnector` using mock `ccxt` responses.
- **Performance:** ✅ `get_current_price` calls should resolve in < 150ms. ✅ Cached precision rule lookups should be < 1ms.
- **Error Handling:** ✅ All `ccxt` exceptions listed in the Logic Annex are correctly caught and mapped to standardized application exceptions.

#### Validation Checkpoint
1.  **Demo:**
    - Show the application fetching and caching precision rules from both Binance and Bybit testnets.
    - Place a test order on each exchange through the standardized interface.
    - Trigger an `InsufficientFunds` error from a mock exchange and show it is correctly mapped and logged.
2.  **Review:** [ ] The `ExchangeInterface` covers all required actions. [ ] The caching strategy for precision is sound. [ ] Error handling correctly captures and standardizes all specified exchange errors.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 4: Order Management Service

#### Objectives
Implement a robust and reliable order management system that can handle the full lifecycle of an order, including partial fills and startup reconciliation.

#### Steps
0.  **Create Tests:** Write unit tests for order state transitions, cancellation logic, and startup reconciliation. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Implement `OrderService`:** Create the service with methods for `submit_order`, `cancel_order`, and `check_order_status`. The `submit_order` method will include retry logic with exponential backoff for transient network errors. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Create Order Fill Monitor:** Implement a persistent background task (using `asyncio.Task`) that periodically queries the status of all `open` or `partially_filled` orders from the database. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Implement State Transitions:** Within the monitor, handle all possible state changes:
    - On `filled`, update the `DCAOrder` status, `filled_quantity`, `avg_fill_price`, and `filled_at` timestamp. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - On `partially_filled`, update only the `filled_quantity` and `avg_fill_price`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - On `canceled`, update the status and `cancelled_at` timestamp. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Ensure Atomicity:** All database updates to an order's status and its related `PositionGroup` must occur within a single database transaction to prevent inconsistent states. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Implement Cancellation Workflow:** The `cancel_order` method in the service will send the cancellation request to the exchange and update the order's status in the database. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Implement Startup Reconciliation:** On application startup, the `OrderService` will fetch all open orders from the exchange for the user and reconcile their status against the orders stored in the database to handle any state drift that occurred while the application was offline. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ System can reliably place, monitor, and cancel orders. ✅ Partial fills are correctly recorded and reflected in the position's average entry. ✅ System state is correctly reconciled after a restart.
- **Technical:** ✅ Order state transitions are managed by a robust state machine within the fill monitor. ✅ A single background task handles monitoring for all users/orders. ✅ Database updates are atomic.
- **Test Coverage:** ✅ >90% unit test coverage for all state transitions and order operations using a mock exchange.
- **Performance:** ✅ The order fill monitor completes its check for up to 200 open orders in < 2 seconds.
- **Error Handling:** ✅ The system correctly handles cases where an order cannot be cancelled (e.g., it was already filled).

#### Validation Checkpoint
1.  **Demo:**
    - Place a limit order, show it as `open` in the DB. Manually fill it on the exchange and show the monitor detecting the `filled` state.
    - Place another order and cancel it through the service.
    - Manually change an order's status in the DB to `open` while it's `filled` on the mock exchange, then restart the app and show the startup reconciliation logic correcting the status.
2.  **Review:** [ ] The state machine logic is robust and covers all edge cases. [ ] The startup reconciliation logic correctly handles discrepancies. [ ] Transactions are used correctly to ensure data integrity.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 5: Grid Trading Logic

#### Objectives
Implement the core trading strategy, including DCA calculation, all three take-profit modes, and the exit signal workflow.

#### Steps
0.  **Create Tests:** Write unit tests for the grid calculator, all three take-profit modes, and the exit logic. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Implement `GridCalculatorService`:** Create a pure service to implement the logic from `6.4 DCA Grid Calculation`, taking a base price and grid config, and returning a list of DCA levels with prices and quantities. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Implement Per-Layer Config Parser:** Use Pydantic to parse and validate the DCA configuration from the user settings, ensuring all required fields (`gap_percent`, `weight_percent`, `tp_percent`) are present. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Implement `TakeProfitService`:** Create a background service that continuously monitors the current market price for all `active` `PositionGroup`s. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Implement TP Modes:** Inside the `TakeProfitService`, implement the logic from `6.3 Take-Profit Monitoring` for all three modes (`per_leg`, `aggregate`, `hybrid`). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Use Actual Fill Price:** Ensure the `TakeProfitService` calculates TP targets based on the actual `avg_fill_price` of a DCA order, not its originally intended price. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Implement Exit Logic:** The `PositionManager` service will, upon receiving an "exit" signal, call the `OrderService` to first cancel all open DCA orders for that group, and then place a market order to close the remaining filled position. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ DCA levels are calculated correctly based on per-layer config. ✅ All three TP modes (`Per-Leg`, `Aggregate`, `Hybrid`) are implemented and functional as per the SoW. ✅ An exit signal correctly closes the entire position group.
- **Technical:** ✅ All financial calculations (e.g., price gaps, TP prices) must use Python's `Decimal` type to ensure precision. ✅ Services are decoupled and testable.
- **Test Coverage:** ✅ >95% unit test coverage for the `GridCalculatorService`. ✅ Unit tests for each of the three take-profit modes with various price scenarios.
- **Performance:** ✅ The `TakeProfitService` check for all active positions (up to 200) completes within the price monitoring interval (e.g., < 1 second).
- **Error Handling:** ✅ The system gracefully handles invalid grid configurations provided by the user.

#### Validation Checkpoint
1.  **Demo:**
    - Create a position and show the calculated DCA levels and TP prices in the logs/DB.
    - For each of the three TP modes, manually move the "current price" via a mock and show the TP service triggering the correct close action (single leg vs. whole position).
    - Send an exit signal and show that all open orders are cancelled and the position is market-closed.
2.  **Review:** [ ] The logic for all three TP modes is correctly implemented as per the SoW. [ ] Edge cases like partial fills are correctly handled in TP calculations. [ ] `Decimal` is used for all financial math.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 6: Execution Pool & Queue

#### Objectives
Implement the system for managing concurrent positions and prioritizing incoming signals according to the SoW's four-tier logic.

#### Steps
0.  **Create Tests:** Write unit tests for the queue priority calculator and integration tests for atomicity and signal replacement logic. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Implement `ExecutionPoolManager`:** A service that manages the number of active `PositionGroup`s. Its primary method, `request_slot()`, will atomically check the count against the `max_open_groups` setting. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Implement `QueueManagerService`:** A service that adds signals to the `QueuedSignal` table when the pool is full and retrieves signals for promotion. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Implement Priority Calculator:** Implement the `calculate_queue_priority` function from `6.1 Algorithm Specifications`. This includes fetching the real-time price to calculate `current_loss_percent` for queued signals. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Implement Queue Promotion Task:** Create a background task that runs when a pool slot is released. It will call the `QueueManagerService` to promote the highest-priority signal. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Ensure Atomicity:** Use pessimistic database locking (`SELECT ... FOR UPDATE`) when checking for a free pool slot and creating a new `PositionGroup` to prevent race conditions where two signals might be promoted simultaneously. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Handle Signal Replacement & Deletion:**
    - When a new signal arrives for a symbol/timeframe already in the queue, update the existing entry and increment its `replacement_count`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - When an exit signal arrives for a symbol/timeframe in the queue, delete the queued entry. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ The pool correctly limits active positions. ✅ Pyramid signals for existing positions correctly bypass the pool limit. ✅ The queue correctly prioritizes signals based on the four-tier system. ✅ Queued signals are correctly replaced or deleted by subsequent signals.
- **Technical:** ✅ Pool slot checks and queue promotion are atomic operations, preventing race conditions. ✅ The background promotion task is robust.
- **Test Coverage:** ✅ >95% unit test coverage for the priority calculation logic. ✅ Integration tests for race conditions, signal replacement, and pyramid bypass.
- **Performance:** ✅ A queue promotion check, including fetching prices for all queued items, completes in < 200ms.
- **Error Handling:** ✅ The system handles the case where a promoted signal fails to execute, releasing the slot for the next item in the queue.

#### Validation Checkpoint
1.  **Demo:**
    - Fill the execution pool to capacity.
    - Send a new signal and show it entering the queue.
    - Send a higher-priority signal (e.g., for a position with a deep loss) and show it being ranked higher.
    - Send a pyramid signal for an active position and show it bypasses the queue and executes immediately.
    - Release a pool slot and show the highest-priority signal being promoted.
    - Send an exit signal for a queued item and show it being removed from the queue.
2.  **Review:** [ ] The priority calculation algorithm exactly matches the SoW and the Logic Annex. [ ] The use of database locking to prevent race conditions is correct.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 7: Risk Engine

#### Objectives
Implement the sophisticated, multi-conditional Risk Engine to offset losing trades according to the strict rules defined in the SoW.

#### Steps
0.  **Create Tests:** Write unit tests for all risk conditions, timer modes, and the winner/loser selection algorithms. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Implement `RiskEngineService`:** Create a service that runs as a periodic background task (e.g., every 60 seconds) to evaluate all `active` positions for a user. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Implement Timer Logic:** When a `PositionGroup`'s state changes, check if a Risk Engine timer condition has been met (e.g., `after_5_pyramids`). If so, set the `risk_timer_expires` timestamp in the database. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Implement Selection Logic:** Implement the `select_loser_and_winners` function from `6.2 Algorithm Specifications`, ensuring it strictly follows the priority rules (loss %, then loss $, then age). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Implement Partial Close Calculator:** Implement the `calculate_partial_close_quantities` function, ensuring it correctly uses `Decimal` types and adheres to the symbol's precision rules (step size, min notional). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Execute Offset Atomically:** The service will, within a single database transaction:
    - Call the `OrderService` to place market orders to partially close the winners and fully close the loser. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Record the entire operation in the `RiskAction` table, linking to the loser and winner `PositionGroup`s. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - If any exchange order fails, the entire transaction must be rolled back to prevent a partial, inconsistent state. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Implement Manual Controls:** Add API endpoints (`/api/risk/{group_id}/block` and `/api/risk/{group_id}/skip`) that allow the UI to set the `risk_blocked` or `risk_skip_once` flags on a `PositionGroup`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ The risk engine correctly identifies and offsets losing trades based on all SoW rules (timer, loss threshold, age, etc.). ✅ All three timer start conditions are implemented and selectable. ✅ Manual block/skip controls work as expected.
- **Technical:** ✅ Risk engine evaluations are performed in an efficient background task. ✅ The entire offset execution (closing trades and logging the action) is atomic.
- **Test Coverage:** ✅ Unit tests for all risk conditions, timer modes, and the winner/loser selection algorithms. ✅ Tests for the manual control API endpoints.
- **Performance:** ✅ A full risk engine evaluation cycle for up to 200 positions completes in < 5 seconds.
- **Error Handling:** ✅ The engine is resilient to exchange errors during the closing of positions and correctly rolls back the state.

#### Validation Checkpoint
1.  **Demo:**
    - Create a scenario with one clear loser and several winners that meet all risk criteria.
    - Show the risk engine timer activate correctly based on a selected start condition.
    - Once expired, show the engine correctly selecting the loser and winners in the logs.
    - Show the calculation of partial close amounts and the execution of orders via the mock exchange.
    - Verify that the `RiskAction` log was written correctly and the transaction was successful.
2.  **Review:** [ ] The loser/winner selection logic exactly matches the SoW. [ ] The partial close calculations are precise and respect instrument precision. [ ] The atomicity of the offset operation is correctly implemented.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.


--- 

## 14. Frontend Development Plan

### Phase 1: Architecture & Foundation

#### Objectives
Set up a modern, scalable, and maintainable frontend architecture with robust state management, routing, and API integration.

#### Steps
0.  **Create Tests:** Write unit tests for the Zustand store, authentication hooks, and WebSocket service. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Initialize Project:** Use `create-react-app` with the TypeScript template. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Install Core Libraries:** Add `react-router-dom`, `axios`, `zustand`, `@mui/material`, `@mui/x-data-grid`, `@emotion/react`, `@emotion/styled`, `react-hook-form`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Set up Folder Structure:** Create a standard folder structure: `/components` (reusable), `/features` (feature-specific components), `/pages`, `/hooks`, `/services`, `/state`, `/theme`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Implement State Management:**
    - Set up a Zustand store (`/state/useStore.ts`) for global state: User, Auth Token, System Status, Positions, Queued Signals. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Define actions for logging in, logging out, and updating state from WebSocket events. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Configure API Client:** Create an `axios` instance in `/services/api.ts` with interceptors to:
    - Automatically add the JWT `Authorization` header from the Zustand store. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - On `401 Unauthorized` responses, automatically call the logout action to clear user state and redirect to the login page. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Implement Routing:** Set up `react-router-dom` with the following routes: `/login`, `/register`, and a `ProtectedRoute` component for `/`, `/positions`, `/queue`, `/risk`, `/logs`, `/settings`. A `NotFoundPage` will handle invalid routes. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
7.  **Create Theme:** Define a Material UI theme in `/theme/theme.ts` with light/dark mode palettes, typography, and global component overrides. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
8.  **Implement WebSocket Manager:** Create a `/services/websocket.ts` service and a `useWebSocket` hook. The service will manage the connection, handle automatic reconnection with exponential backoff, and call Zustand actions to update the store when new messages arrive. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ A user can log in, the JWT is stored, and subsequent API calls are authenticated. ✅ Protected routes redirect unauthenticated users to `/login`. ✅ The UI can toggle between light and dark themes.
- **Technical:** ✅ Zustand is the single source of truth for global state. ✅ The Axios interceptor correctly handles 401 errors by logging the user out. ✅ The WebSocket service automatically attempts to reconnect if the connection is lost. ✅ A global React Error Boundary is implemented to catch and display a fallback UI for rendering errors.
- **Test Coverage:** ✅ >90% unit test coverage for the Zustand store actions and the `useAuth` hook.
- **Performance:** ✅ Initial app load time (Time to Interactive) is < 2 seconds on a fast 3G connection.

#### Validation Checkpoint
1.  **Demo:**
    - Log in and show the JWT being stored in Zustand and sent in API headers.
    - Trigger a 401 error from the API and show the user is automatically redirected to the login page.
    - Stop the backend server and show the WebSocket service attempting to reconnect with increasing delays.
    - Toggle the theme to show it applies globally.
2.  **Review:** [ ] The folder structure is logical and scalable. [ ] The state management approach correctly separates concerns. [ ] The API client's error handling is robust.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 2: UI Components & Views

#### Objectives
Build all UI components and pages specified in the SoW, following the UI/UX Design System, with a focus on clarity, usability, and real-time data display.

#### Steps
0.  **Create Tests:** Write Jest and React Testing Library tests for all major UI components and pages. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Implement Layout:** Create a `MainLayout` component with a persistent sidebar, a header, and a main content area. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Build Dashboard Page:** Implement the `DashboardPage` by creating individual components for each widget (`PoolUsageWidget`, `PnlCard`, `EquityCurveChart`) as defined in the wireframes. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Build Positions Page:** Implement the `PositionsPage` following the defined component architecture (`PositionsTable`, `PositionRow`, `StatusChip`, `PnlCell`, `DcaLegsTable`). Use `MUI X Data Grid` for sortable, filterable columns. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Build Risk Engine & Queue Pages:** Implement the dedicated pages for the Risk Engine and Waiting Queue, including their data tables and action buttons with the exact micro-interactions defined in the UX section (e.g., confirmation modals, loading states). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Build Settings Page:** Implement the `SettingsPage` with tabbed navigation. Use `react-hook-form` for each settings section, providing real-time validation feedback for fields like API keys and numerical inputs. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Build Logs Page:** Implement the `SystemLogsPage` with a virtualized list to handle large numbers of logs efficiently. Include controls for filtering by log level and a text search input. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
7.  **Connect Components to State:** Refactor all pages and components to subscribe to the Zustand store for live data. Ensure components re-render efficiently when the relevant parts of the state change. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ All pages and components from the SoW are implemented and match the wireframes. ✅ Data updates across the entire application in real-time without requiring a page refresh. ✅ All forms provide clear validation and feedback.
- **Technical:** ✅ Components are reusable and follow the defined architecture. ✅ State changes from the WebSocket efficiently update only the necessary components (verified with React DevTools Profiler). ✅ The application is responsive and usable on screen widths down to 768px (tablet).
- **Test Coverage:** ✅ >80% Jest/React Testing Library test coverage for each major feature component, verifying rendering and basic interactions.
- **Performance:** ✅ The UI remains responsive (<16ms frame time) during high-frequency WebSocket updates (e.g., 10 messages per second).

#### Validation Checkpoint
1.  **Demo:**
    - Showcase each page of the application, demonstrating that it matches the wireframes.
    - Change data in the database (e.g., a position's PnL) and show it reflecting instantly on the Dashboard and Positions pages.
    - On the Settings page, enter an invalid value (e.g., a negative number for a percentage) and show the real-time validation error.
    - Demonstrate the confirmation modal and loading state for an action like "Force Add to Pool".
2.  **Review:** [ ] The UI matches the SoW requirements and wireframes. [ ] The component hierarchy is logical and promotes reusability. [ ] Real-time data handling is efficient and does not cause unnecessary re-renders.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Unit Test Coverage > 85%
    - [ ] SoW Requirements Met
    - [ ] Documentation Updated
4.  **End of Phase Action:** Push all commits to GitHub.

---

## 15. Cross-Cutting Phases

### Phase 1: Integration Testing

#### Objectives
Build a suite of end-to-end tests to verify that the entire application, from webhook ingestion to trade execution, works together as expected.

#### Steps
0.  **Define Test Cases:** Write end-to-end test cases in a feature file format (e.g., Gherkin). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Set up Test Environment:** Use `docker-compose.test.yml` to create an isolated test environment with the app, a test database, and a mock exchange server that can simulate order fills and API errors. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Write Test Scenarios:** Use `pytest` to write integration tests that make real API calls to the application running in the test environment. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Test Full Signal Flow:**
    - Send a valid webhook for a new position. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Verify a `PositionGroup` is created with status `live`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Verify the correct number of `DCAOrder`s are created with status `open` via the mock exchange. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Test Risk Engine Flow:**
    - Programmatically create one `PositionGroup` with a negative PnL below the threshold and two `PositionGroup`s with positive PnL. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Manually set the state to meet all risk criteria (timer expired, 5 pyramids). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Trigger the risk engine evaluation endpoint. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Verify that the mock exchange received a market close order for the loser and partial market close orders for the winners. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Test Queue Promotion Flow:**
    - Fill the execution pool by creating the max number of positions. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Send a new signal and verify it creates a `QueuedSignal` entry. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Send an exit signal for one of the live positions to free up a slot. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Verify the queued signal is promoted and executed on the mock exchange. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Test Recovery Flow:**
    - Start a trade and ensure orders are `open`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Forcefully restart the `app` container. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - Verify that the startup reconciliation logic correctly identifies the `open` orders and continues monitoring them. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ The main user flows (trading, risk management, queueing, recovery) are tested end-to-end.
- **Technical:** ✅ Tests run in an isolated, repeatable Docker environment. ✅ Tests automatically clean up the database after each run to ensure isolation. ✅ The mock exchange correctly simulates order fills, partial fills, and API rejections.
- **Test Coverage:** ✅ The integration test suite achieves >80% coverage of the backend API endpoints.

#### Validation Checkpoint
1.  **Demo:**
    - Run the entire `pytest` integration suite with coverage reporting and show the report.
    - Show the logs from the mock exchange server to confirm it received the expected order requests during the tests.
2.  **Review:** [ ] The test scenarios cover the most critical and complex workflows. [ ] The mock exchange is sufficient to simulate real-world conditions, including errors. [ ] Tests are properly isolated from one another.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Integration Tests Passing
    - [ ] SoW Requirements Met
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 2: Security & Error Handling

#### Objectives
Harden the application against common vulnerabilities and ensure it handles all errors gracefully.

#### Steps
0.  **Create Tests:** Write unit tests for encryption, RBAC, and the global exception handler. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Implement Encryption:** Use the `cryptography` library to encrypt all user API keys before they are stored in the database. Create utility functions `encrypt_key` and `decrypt_key`. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Implement Role-Based Access Control (RBAC):** Create a `RoleChecker` dependency that can be used as `Depends(RoleChecker(required_role='admin'))` on all admin-only API endpoints. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Implement Global Exception Handler:** Create a FastAPI middleware that catches all unhandled `Exception` types, logs the full traceback, and returns a standardized `JSONResponse` with a generic error message and a unique request ID for correlation. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Implement Circuit Breaker:** Use a library like `pybreaker` to wrap critical external calls in the `ExchangeConnector`s (e.g., `place_order`, `fetch_balance`). If an exchange API fails repeatedly, the circuit will open, preventing cascading failures. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Perform Dependency Audit:** Integrate `pip-audit` into the CI pipeline to automatically scan for known vulnerabilities in Python dependencies on every commit. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Harden Frontend Security:** Ensure all user-generated content (if any) is properly sanitized to prevent XSS. Implement CSRF protection if using cookie-based authentication. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ Sensitive data (API keys) is encrypted at rest and is never exposed in API responses. ✅ Users can only access endpoints permitted by their role.
- **Technical:** ✅ A central middleware handles all unhandled exceptions, preventing stack trace leaks. ✅ The circuit breaker prevents repeated calls to a failing external service. ✅ The CI pipeline will fail if a high-severity vulnerability is detected in a dependency.
- **Security:** ✅ Application is protected against basic SQL injection (via ORM), XSS, and unauthorized access (IDOR).

#### Validation Checkpoint
1.  **Demo:**
    - Show an encrypted API key in the database and demonstrate that it cannot be read directly.
    - Use `curl` or an API client to attempt to access an admin endpoint as a non-admin user and show the 403 Forbidden error.
    - Intentionally introduce a bug to trigger an unhandled Python exception and show the standardized 500 error JSON response.
2.  **Review:** [ ] The encryption method is strong and correctly implemented. [ ] The RBAC logic is correctly applied to all relevant endpoints. [ ] The global exception handler provides user-friendly responses while logging detailed technical information.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Security Scan Passing
    - [ ] SoW Requirements Met
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 3: Deployment & Packaging

#### Objectives
Package the application into self-contained, distributable installers for Windows and macOS.

#### Steps
0.  **Create Build Scripts:** Write build scripts to automate the packaging process for Windows and macOS. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Optimize Production Docker Image:** Create a multi-stage `Dockerfile` for the backend that uses a slim base image to create a small, secure production container. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Configure PyInstaller:** Create a `pyinstaller.spec` file to bundle the FastAPI backend, all its dependencies, and any necessary data files into a single executable. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Package Frontend:** Build the static React frontend (`npm run build`) and configure the FastAPI backend (using `StaticFiles`) to serve it from the executable. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Create Windows Installer:** Use Inno Setup to create a `.exe` installer. The script will bundle the executable, create shortcuts, and set up an uninstaller. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
5.  **Create macOS Installer:** Use `dmgbuild` to create a `.dmg` disk image for macOS that allows the user to drag-and-drop the application into their `/Applications` folder. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
6.  **Implement Update Mechanism:** Integrate a library like `PyUpdater` or a simple version check against a remote JSON file to notify the user when a new version is available and provide a download link. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ The application can be installed and run on clean Windows 10/11 and macOS (Intel & Apple Silicon) machines without requiring the user to install Python or Node.js. ✅ The uninstaller correctly removes all application files.
- **Technical:** ✅ The final output is a single `.exe` for Windows and a `.dmg` for macOS. ✅ The packaged application starts within 10 seconds. ✅ The production Docker image is less than 500MB.
- **Security:** ✅ The Windows installer is signed with a code signing certificate. ✅ The macOS `.dmg` is notarized by Apple to pass Gatekeeper checks.

#### Validation Checkpoint
1.  **Demo:**
    - Run the installer on a clean Windows VM without any development tools installed.
    - Run the `.dmg` on a clean macOS machine.
    - Launch the application from the installed shortcut/icon and verify it is fully functional.
    - Run the uninstaller and verify the application directory and shortcuts are removed.
2.  **Review:** [ ] The build scripts are reliable and documented. [ ] The update mechanism is user-friendly and secure. [ ] The final package size is reasonably optimized.
3.  **Quality Gate Checklist:**
    - [ ] Code Reviewed & Approved
    - [ ] Successful Builds for Win/macOS
    - [ ] SoW Requirements Met
4.  **End of Phase Action:** Push all commits to GitHub.

### Phase 4: Documentation

#### Objectives
Create clear, comprehensive documentation for end-users, developers, and API consumers.

#### Steps
0.  **Create Documentation Structure:** Set up the documentation structure and templates. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
1.  **Write User Guide:** Create a multi-page guide (e.g., using MkDocs or a simple Markdown site) with sections for:
    - 'Installation' (with screenshots for Windows and macOS). (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - 'Connecting Your Exchange'. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - 'Configuring the Grid Strategy'. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - 'Understanding the Risk Engine'. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
    - 'Troubleshooting Common Issues'. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
2.  **Write Developer Guide:** Heavily update the `README.md` to include a "Quick Start" section, detailed instructions for setting up the development environment, running all tests (unit, integration), and building the project for production. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
3.  **Document API:** Add detailed docstrings, descriptions, and examples to each FastAPI endpoint and Pydantic model to ensure the auto-generated OpenAPI (`/docs`) spec is rich and descriptive. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)
4.  **Document Architecture:** Create a high-level architecture diagram (e.g., using Mermaid.js in a Markdown file) and document the key design decisions and data flow in a `/docs` folder. (updating EP5.md with progress, updating GEMINI.md with learned lessons, staging+committing changes to git)

#### Acceptance Criteria
- **Functional:** ✅ A non-technical user can successfully install, configure, and run the application using only the User Guide. ✅ A new developer can set up and run the project and its tests in under 15 minutes using the Developer Guide.
- **Technical:** ✅ The OpenAPI documentation is automatically generated and includes example request/response bodies for every endpoint.
- **Clarity:** ✅ The documentation is clear, concise, and free of technical jargon where possible, especially in the User Guide.

#### Validation Checkpoint
1.  **Demo:**
    - Showcase the rendered User Guide website or document.
    - Showcase the live Swagger UI for the API and point out the detailed descriptions and examples.
    - Walk through the updated `README.md`.
2.  **Review:** [ ] The documentation is clear, comprehensive, and covers all major aspects of the application for its intended audience.
3.  **Quality Gate Checklist:**
    - [ ] Documentation Reviewed & Approved
    - [ ] SoW Requirements Met
4.  **End of Phase Action:** Push all commits to GitHub.

---

## 16. Change Management Protocol

To ensure project stability and clear communication, all changes to the scope of work must follow this protocol.

1.  **Formal Change Request:** Any proposed change to the `SoW.md` must be submitted as a "Change Request" issue in the project's version control system (e.g., GitHub Issues). The request must clearly state the desired change and the reason for it.
2.  **Impact Analysis & Plan Update:** The proposed change will be analyzed for its impact on the existing architecture and timeline. If approved, the `execution_plan.md` will be updated to reflect the change, and its version will be incremented (e.g., from v5.0 to v5.1).
3.  **AI Re-briefing:** The AI assistant must be explicitly instructed to re-read the updated `SoW.md` and the newly versioned `EPx.md` before proceeding with any implementation related to the change. This ensures the AI is operating on the latest approved specifications.

---

## 17. SoW Traceability Matrix

| SoW Section | SoW Requirement | Execution Plan Phase |
|-------------|-----------------|----------------------|
| 2.1         | TradingView Webhook Ingestion | Backend Phase 2      |
| 2.2         | First signal creates Position Group | Backend Phase 2      |
| 2.2         | Pyramids don't create new positions | Backend Phase 6      |
| 2.3         | DCA per-layer configuration | Backend Phase 5      |
| 2.4         | Take-Profit Modes (Per-Leg, Aggregate, Hybrid) | Backend Phase 5      |
| 2.5         | Exit Logic (Market Close) | Backend Phase 5      |
| 3           | Exchange Integration (Binance, Bybit) | Backend Phase 3      |
| 3.1         | Precision Validation | Backend Phase 3      |
| 4           | Risk Engine (Timer, Selection, Offset) | Backend Phase 7      |
| 5           | Execution Pool & Queue (Priority, Limits) | Backend Phase 6      |
| 6           | Order Management (Placement, Monitoring, Fills) | Backend Phase 4      |
| 7           | UI - Live Dashboard | Frontend Phase 2     |
| 7           | UI - Positions & Pyramids View | Frontend Phase 2     |
| 7           | UI - Risk Engine Panel | Frontend Phase 2     |
| 7           | UI - Waiting Queue View | Frontend Phase 2     |
| 7           | UI - Logs & Alerts | Frontend Phase 2     |
| 7           | UI - Settings Panel | Frontend Phase 2     |
| 7           | UI - Performance & Portfolio Dashboard | Frontend Phase 2     |
| 8           | Real-time Data Synchronization | Frontend Phase 2     |
| 9           | Authentication & Authorization | Frontend Phase 1, Cross-Cutting Phase 2 |
| 10          | Configuration Management | Cross-Cutting Phase 3 |
| 11          | Logging & Monitoring | Cross-Cutting Phase 1, 2 |
| 12          | Error Handling & Recovery | Cross-Cutting Phase 2 |
| 13          | Deployment & Packaging (Windows, macOS) | Cross-Cutting Phase 3 |
| 14          | Documentation (User, Developer, API) | Cross-Cutting Phase 4 |
