# Risk Engine Integration Fix Proposal

## Status: ✅ COMPLETED (2025-12-28)

The fix has been implemented and tested successfully.

---

## Executive Summary

The Risk Engine had several risk validation features that were **defined but never called** in the signal processing flow. This document explained the root cause and proposed a fix which has now been implemented.

---

## Root Cause

### The Unused Function

The function `validate_pre_trade_risk()` in [risk_engine.py:86-130](backend/app/services/risk/risk_engine.py#L86-L130) contains all the pre-trade risk validation logic:

```python
async def validate_pre_trade_risk(
    self,
    signal: QueuedSignal,
    active_positions: List[PositionGroup],
    allocated_capital_usd: Decimal,
    session: AsyncSession,
    is_pyramid_continuation: bool = False
) -> Tuple[bool, Optional[str]]:
    # 0. Check if engine is paused or force stopped
    if self.config.engine_paused_by_loss_limit:
        return False, "Engine paused due to max realized loss limit"
    if self.config.engine_force_stopped:
        return False, "Engine force stopped by user"

    # 1. Max Open Positions Global (redundant - already checked by exec_pool)
    # 2. Max Open Positions Per Symbol ← NOT IMPLEMENTED ELSEWHERE
    # 3. Max Total Exposure ← Partially implemented (caps but doesn't block)
    # 4. Max Realized Loss Circuit Breaker ← NOT IMPLEMENTED ELSEWHERE
```

**This function is NEVER CALLED from:**
- `signal_router.py` - Where signals are processed
- `queue_manager.py` - Where queued signals are promoted

### Why This Happened

The code was written with the intention to integrate risk validation, but the integration step was never completed. The signal_router uses:
- `ExecutionPoolManager.request_slot()` - Only checks `max_open_positions_global`
- Direct `max_total_exposure_usd` capping - But doesn't block, just caps

---

## Missing Features (Not Implemented)

| Feature | Config Field | Status |
|---------|--------------|--------|
| Max positions per symbol | `max_open_positions_per_symbol` | Code exists, never called |
| Circuit breaker (daily loss) | `max_realized_loss_usd` | Code exists, never called |
| Engine force stop | `engine_force_stopped` | Code exists, never checked |
| Engine pause on loss | `engine_paused_by_loss_limit` | Code exists, never checked |

---

## Proposed Fix

### Option A: Integrate `validate_pre_trade_risk()` into Signal Router (Recommended)

**File:** `backend/app/services/signal_router.py`

Add the risk validation call before executing new positions or pyramids:

```python
# At the top of the file, add import:
from app.services.risk.risk_engine import RiskEngineService

# In the route_signal method, before execute_new_position or execute_pyramid:

# Create RiskEngineService instance
risk_engine = RiskEngineService(
    session_factory=AsyncSessionLocal,
    user=self.user,
    risk_engine_config=risk_config
)

# Get active positions for validation
active_positions = await pg_repo.get_active_position_groups_for_user(self.user.id)

# Create a QueuedSignal for validation
qs = QueuedSignal(
    user_id=self.user.id,
    exchange=signal.tv.exchange.lower(),
    symbol=signal.tv.symbol,
    timeframe=signal.tv.timeframe,
    side=signal_side,
    entry_price=Decimal(str(signal.tv.entry_price)),
    signal_payload=signal.model_dump(mode='json')
)

# Validate pre-trade risk
is_allowed, rejection_reason = await risk_engine.validate_pre_trade_risk(
    signal=qs,
    active_positions=active_positions,
    allocated_capital_usd=total_capital,
    session=db_session,
    is_pyramid_continuation=(existing_group is not None)
)

if not is_allowed:
    logger.warning(f"Pre-trade risk validation failed: {rejection_reason}")
    return f"Risk validation failed: {rejection_reason}"

# Then proceed with execute_new_position() or execute_pyramid()
```

### Option B: Add to Queue Manager (For Queued Signal Promotion)

**File:** `backend/app/services/queue_manager.py`

In `promote_highest_priority_signal()` method, add validation before execution:

```python
# Before "Slot granted. Promoting signal..."
# Add risk validation

from app.services.risk.risk_engine import RiskEngineService

risk_engine = RiskEngineService(
    session_factory=self.session_factory,
    user=user,
    risk_engine_config=risk_config
)

is_allowed, rejection_reason = await risk_engine.validate_pre_trade_risk(
    signal=best_signal,
    active_positions=active_groups,
    allocated_capital_usd=total_capital,
    session=session,
    is_pyramid_continuation=False
)

if not is_allowed:
    logger.warning(f"Queue promotion blocked by risk: {rejection_reason}")
    best_signal.status = QueueStatus.REJECTED
    best_signal.rejection_reason = rejection_reason
    await queue_repo.update(best_signal)
    await session.commit()
    continue  # Try next signal
```

---

## Implementation Steps

1. **Add import** in signal_router.py:
   ```python
   from app.services.risk.risk_engine import RiskEngineService
   ```

2. **Create RiskEngineService instance** in `route_signal()`:
   ```python
   risk_engine = RiskEngineService(
       session_factory=AsyncSessionLocal,
       user=self.user,
       risk_engine_config=risk_config
   )
   ```

3. **Call validation before execution**:
   - Before `execute_new_position()`
   - Before `execute_pyramid()`
   - In queue_manager before promoting

4. **Handle rejection**:
   - Return error message to webhook caller
   - Log the rejection reason
   - For queue: mark signal as REJECTED with reason

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/services/signal_router.py` | Add risk validation before position/pyramid execution |
| `backend/app/services/queue_manager.py` | Add risk validation before queue promotion |

---

## Testing After Fix

1. **Test `max_open_positions_per_symbol`:**
   - Set limit to 1
   - Open position for BTC/USDT
   - Try to open another BTC/USDT position (different timeframe)
   - Expected: Rejected with "Max positions for BTC/USDT reached"

2. **Test `max_realized_loss_usd` circuit breaker:**
   - Set limit to $50
   - Close positions with total -$60 realized loss
   - Try to open new position
   - Expected: Rejected with "Max realized loss limit reached"

3. **Test `engine_force_stopped`:**
   - Set flag to true via API
   - Try to open new position
   - Expected: Rejected with "Engine force stopped by user"

---

## Priority

**HIGH** - These are critical risk management features that users expect to work based on the UI configuration options.
