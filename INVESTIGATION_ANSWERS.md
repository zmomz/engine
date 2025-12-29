# Investigation Questions - Answers

Generated: 2025-12-29
Based on current codebase analysis

---

## 1. Webhook Endpoint & Authentication

### 1.1 Is there webhook signature validation implemented?
**Yes.** HMAC-SHA256 signature validation is implemented in `backend/app/api/webhooks.py`.

### 1.2 Where is security.webhook_signature_validation checked?
In `backend/app/api/webhooks.py:60-85`. The `validate_webhook_signature()` function computes HMAC-SHA256 using the user's webhook secret and compares it with the `X-Webhook-Signature` header.

### 1.3 What response does an unauthenticated request receive?
HTTP 401 Unauthorized with message: `"Invalid webhook signature"`

### 1.4 Are failed authentication attempts logged with details?
**Yes.** Failed attempts are logged with WARNING level including user_id and reason.

### 1.5 What rate limiting is applied to webhook endpoints?
20 requests per minute per IP using SlowAPI (`backend/app/api/webhooks.py:45`).

### 1.6 How is the webhook secret generated and stored per user?
- Generated via `secrets.token_hex(16)` during user creation
- Stored in `users.webhook_secret` column (VARCHAR 64)
- Can be regenerated via `/api/v1/users/webhook-secret/regenerate`

---

## 2. Signal Transformation

### 2.1 How is raw JSON transformed into an internal signal object?
1. Raw JSON → `TradingViewWebhook` Pydantic model (validation)
2. `TradingViewWebhook` → `QueuedSignal` via `signal_router.py:process_webhook()`
3. Field mapping occurs during transformation

### 2.2 Are TradingView placeholders properly mapped?
**Yes.** Key mappings in `backend/app/schemas/tradingview_webhook.py`:
- `{{exchange}}` → `tv.exchange`
- `{{ticker}}` → `tv.symbol`
- `{{strategy.order.action}}` → `tv.action`
- `{{strategy.position_size}}` → `tv.market_position_size`

### 2.3 How is execution_intent.type handled differently?
- `type: "signal"` → Processed as tradable signal
- `type: "alert"` → Logged only, no trade execution
- `type: "close"` → Triggers position close

### 2.4 What are the key transformations?
- Exchange name lowercased: `exchange.lower()`
- Action mapping: `buy` → `long`, `sell` → `short`
- Symbol normalization: `BTC/USDT` → `BTCUSDT` (exchange-specific)
- Decimal conversion for numeric fields

### 2.5 How are malformed/missing fields handled?
Pydantic validation raises `ValidationError` with detailed field-level errors. HTTP 422 returned with error details.

### 2.6 Is the raw payload logged before or after validation?
**Before.** Raw payload logged at DEBUG level before Pydantic parsing (`webhooks.py:75`).

---

## 3. User Authentication & Session Management

### 3.1 How is user registration handled?
`POST /api/v1/users/register` endpoint in `backend/app/api/users.py:45-80`.

### 3.2 What password hashing algorithm is used?
**bcrypt** via `passlib.context.CryptContext` (`backend/app/core/security.py:15`).

### 3.3 How are JWT tokens generated and validated?
- Generation: `create_access_token()` in `backend/app/core/security.py:45-65`
- Algorithm: HS256
- Validation: `get_current_user()` dependency extracts and validates token

### 3.4 What is the token expiration policy?
**30 minutes** default (`ACCESS_TOKEN_EXPIRE_MINUTES=30` in settings).

### 3.5 How are HTTP cookies secured?
```python
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=True,  # HTTPS only
    samesite="lax",
    max_age=1800
)
```

### 3.6 How is user logout handled?
`POST /api/v1/users/logout` clears the cookie by setting `max_age=0`.

### 3.7 What rate limiting is applied to login/registration?
- Login: 10 requests per minute
- Registration: 5 requests per minute

---

## 4. Exchange Integration & API Keys

### 4.1 Which exchanges are supported?
- **Binance** (spot and futures)
- **Bybit** (unified and contract)
- **Mock** (testing)

### 4.2 How are exchange API keys encrypted and stored?
- Encrypted using **Fernet symmetric encryption** (`backend/app/core/encryption.py`)
- Stored in `exchange_credentials` table
- Encryption key from `ENCRYPTION_KEY` environment variable

### 4.3 What encryption algorithm is used?
**Fernet** (AES-128-CBC with HMAC-SHA256).

### 4.4 How is testnet mode configured per exchange?
`testnet: bool` field in `exchange_credentials` table. Connector uses testnet URLs when `True`.

### 4.5 How does the exchange connector factory work?
`ExchangeConnectorFactory.get_connector()` in `backend/app/services/exchange_abstraction/factory.py`:
1. Looks up credentials by exchange name
2. Decrypts API keys
3. Returns appropriate connector class instance

### 4.6 What error mapping exists for exchange-specific errors?
`@map_exchange_errors` decorator in `backend/app/services/exchange_abstraction/error_mapping.py` maps CCXT exceptions to custom exceptions:
- `ccxt.AuthenticationError` → `ExchangeAuthError`
- `ccxt.InsufficientFunds` → `InsufficientFundsError`
- `ccxt.OrderNotFound` → `OrderNotFoundError`
- etc.

### 4.7 How are exchange precision rules fetched and cached?
- Fetched via CCXT `load_markets()`
- Cached in Redis with 48-hour TTL
- Key: `precision:{exchange}:{symbol}`

### 4.8 How is account type handled for Bybit?
`account_type` field in credentials: `UNIFIED` or `CONTRACT`. Affects API endpoint paths.

---

## 5. Position Group Creation

### 5.1 What are the steps to create a position group?
1. Signal passes risk validation
2. `PositionCreator.create_position_group()` called
3. Position group record created with WAITING status
4. DCA orders generated via `GridCalculator`
5. Orders submitted to exchange
6. Status updated to LIVE

### 5.2 What data is stored in a position group?
Key fields in `position_groups` table:
- `id`, `user_id`, `symbol`, `exchange`, `timeframe`, `side`
- `status`, `base_entry_price`, `weighted_avg_entry`
- `total_invested_usd`, `total_filled_quantity`
- `pyramid_count`, `max_pyramids`, `tp_mode`
- `realized_pnl_usd`, `unrealized_pnl_usd`, `unrealized_pnl_percent`
- `risk_blocked`, `risk_eligible`, `risk_timer_expires`
- `created_at`, `closed_at`

### 5.3 How is base entry price determined?
From signal's `entry_price` field, which comes from TradingView's `{{strategy.order.price}}`.

### 5.4 Is Position Group immediately persisted or flushed for ID?
**Immediately persisted** with `session.flush()` to get the UUID before creating DCA orders.

### 5.5 Where is the creation code located?
`backend/app/services/position/position_creator.py:85-180`

### 5.6 What validations occur before position creation?
1. Pre-trade risk validation (6 checks)
2. DCA configuration exists for symbol/timeframe/exchange
3. Sufficient balance on exchange
4. No duplicate position (unique constraint)

---

## 6. Position Identity & Lookup

### 6.1 Is a Position Group uniquely identified by pair + timeframe?
**No.** Full identity is: `user_id + symbol + exchange + timeframe + side`

### 6.2 What happens if two signals arrive simultaneously for BTCUSDT 15m?
1. First signal creates position group
2. Second signal detected as pyramid (same identity)
3. Pyramid added to existing position if under max_pyramids

### 6.3 How are race conditions prevented?
- Database partial unique index on active positions
- Redis distributed lock during signal processing
- `SELECT ... FOR UPDATE` in critical sections

### 6.4 What is the lookup mechanism?
`PositionGroupRepository.get_active_position_group_for_signal()`:
```python
query.filter(
    PositionGroup.user_id == user_id,
    PositionGroup.symbol == symbol,
    PositionGroup.exchange == exchange,
    PositionGroup.timeframe == timeframe,
    PositionGroup.side == side,
    PositionGroup.status.in_([ACTIVE, LIVE, PARTIALLY_FILLED, WAITING])
)
```

### 6.5 Is there a unique constraint on the database level?
**Yes.** Partial unique index:
```sql
CREATE UNIQUE INDEX ix_position_groups_active_unique
ON position_groups (user_id, symbol, exchange, timeframe, side)
WHERE status IN ('WAITING', 'LIVE', 'PARTIALLY_FILLED', 'ACTIVE');
```

---

## 7. Position State Machine

### 7.1 What states are defined?
```python
class PositionGroupStatus(str, Enum):
    WAITING = "WAITING"           # Created, orders being placed
    LIVE = "LIVE"                 # All orders placed, none filled
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Some orders filled
    ACTIVE = "ACTIVE"             # Entry complete, monitoring TPs
    CLOSING = "CLOSING"           # Exit initiated
    CLOSED = "CLOSED"             # Fully closed
    FAILED = "FAILED"             # Creation failed
```

### 7.2 Are all states implemented and used?
**Yes.** All states are used in the codebase with proper transitions.

### 7.3 What triggers state transitions?
- `WAITING → LIVE`: All orders submitted successfully
- `LIVE → PARTIALLY_FILLED`: First DCA order fills
- `PARTIALLY_FILLED → ACTIVE`: All DCA legs filled OR TP hit
- `ACTIVE → CLOSING`: Exit signal or TP triggered
- `CLOSING → CLOSED`: All positions closed on exchange
- `* → FAILED`: Error during creation/execution

### 7.4 Can states go backwards?
**No.** State machine is forward-only by design.

### 7.5 Where is state tracked and how is it persisted?
- `position_groups.status` column (VARCHAR)
- Updated via `PositionGroupRepository.update()`
- Transitions logged for audit trail

### 7.6 Where is the transition logic located?
- `backend/app/services/position/position_manager.py:update_position_state()`
- `backend/app/services/order_fill_monitor.py` (fill-triggered transitions)
- `backend/app/services/position/position_closer.py` (close transitions)

---

## 8. Pyramid Detection & Handling

### 8.1 How does the system detect this is a pyramid?
In `signal_router.py:process_signal()`:
```python
existing_group = await position_group_repo.get_active_position_group_for_signal(
    user_id, symbol, exchange, timeframe, side
)
if existing_group:
    # This is a pyramid continuation
    is_pyramid = True
```

### 8.2 Is this pyramid added without consuming a pool slot?
**Yes.** Pyramids bypass `max_open_positions_per_symbol` check via `is_pyramid_continuation=True` flag.

### 8.3 What is the maximum number of pyramids allowed?
Configured per DCA config: `dca_configurations.max_pyramids` (default: 5)

### 8.4 What happens if a 6th pyramid signal arrives (when max is 5)?
Signal is rejected with message: `"Max pyramids reached (5/5) for position {id}"`

### 8.5 How does pyramid continuation bypass work?
In `risk_engine.py:validate_pre_trade_risk()`:
```python
# 2. Max Open Positions Per Symbol/Timeframe/Exchange combination
if not is_pyramid_continuation:
    # Only check this limit for new positions
    matching_positions = [...]
    if len(matching_positions) >= self.config.max_open_positions_per_symbol:
        return False, f"Max positions for {position_key} reached"
```

---

## 9. Pyramid Counter & Storage

### 9.1 Where is the pyramid counter stored?
`position_groups.pyramid_count` column (INTEGER, default 0). Initial entry has `pyramid_count=0`, first pyramid continuation increments to 1, etc.

### 9.2 Is pyramid count incremented atomically?
**Yes.** Via SQL:
```python
position_group.pyramid_count += 1
session.commit()
```

### 9.3 How to query "how many pyramids does BTCUSDT 1h have"?
```python
group = await repo.get_active_position_group_for_signal(
    user_id, "BTCUSDT", "binance", 60, "long"
)
pyramid_count = group.pyramid_count
```

### 9.4 Does pyramid count affect Risk Engine activation?
**Yes.** Risk timer starts only when `pyramid_count >= required_pyramids_for_timer`.

### 9.5 How is pyramid index tracked per DCA order?
`dca_orders.pyramid_index` column stores which pyramid the order belongs to.

---

## 10. DCA Order Generation

### 10.1 Does each pyramid generate its own set of DCA orders?
**Yes.** Each pyramid creates a new set of DCA orders with its own `pyramid_index`.

### 10.2 Are DCA gaps calculated from the pyramid's entry price?
**Yes.** Each pyramid's DCA levels are calculated from that pyramid's entry price.

### 10.3 How are multiple DCA sets managed together?
- All DCA orders linked to same `position_group_id`
- Distinguished by `pyramid_index` and `dca_leg_index`
- Aggregate metrics calculated across all pyramids

### 10.4 How is DCA order quantity calculated from capital weight?
```python
# In grid_calculator.py
leg_capital = total_capital * (weight_percent / 100)
quantity = leg_capital / price
quantity = round_to_step_size(quantity, step_size)
```

---

## 11. DCA Configuration Management

### 11.1 How are DCA layers configured?
Via `dca_configurations` table with JSON `dca_levels` field:
```json
[
  {"gap_percent": 0, "weight_percent": 40, "tp_percent": 1.5},
  {"gap_percent": 1.5, "weight_percent": 30, "tp_percent": 2.0},
  {"gap_percent": 3.0, "weight_percent": 30, "tp_percent": 2.5}
]
```

### 11.2 Is grid_strategy.max_dca_per_pyramid respected?
**Yes.** Validated during DCA config creation and order generation.

### 11.3 Can DCA configuration be different per symbol/timeframe/exchange?
**Yes.** DCA configs are uniquely identified by `(user_id, pair, timeframe, exchange)`.

### 11.4 How are DCA configurations stored?
In `dca_configurations` table with fields:
- `pair`, `timeframe`, `exchange`
- `entry_order_type` (limit/market)
- `dca_levels` (JSON array)
- `tp_mode`, `tp_settings` (JSON)
- `max_pyramids`
- `pyramid_specific_levels` (JSON, optional)

### 11.5 What CRUD operations exist for DCA configs?
- `POST /api/v1/dca-configs` - Create
- `GET /api/v1/dca-configs` - List all
- `GET /api/v1/dca-configs/{id}` - Get one
- `PUT /api/v1/dca-configs/{id}` - Update
- `DELETE /api/v1/dca-configs/{id}` - Delete

### 11.6 How are pyramid-specific DCA levels configured?
`pyramid_specific_levels` JSON field:
```json
{
  "2": [{"gap_percent": 0.5, "weight_percent": 100, "tp_percent": 1.0}],
  "3": [{"gap_percent": 1.0, "weight_percent": 100, "tp_percent": 1.5}]
}
```

---

## 12. DCA Price & Size Calculation

### 12.1 How is the DCA price calculated from entry price?
```python
# For long positions
dca_price = entry_price * (1 - gap_percent / 100)
# For short positions
dca_price = entry_price * (1 + gap_percent / 100)
```

### 12.2 Are prices calculated as: DCA1 = entry - gap1%, DCA2 = entry - gap2%?
**Yes.** Each DCA level's gap is applied to the entry price independently.

### 12.3 How is capital weight applied to determine order size?
```python
leg_capital_usd = total_capital_usd * (weight_percent / 100)
quantity = leg_capital_usd / dca_price
```

### 12.4 Is precision validation applied BEFORE order submission?
**Yes.** In `grid_calculator.py`:
```python
price = round_to_tick_size(price, tick_size)
quantity = round_to_step_size(quantity, step_size)
# Validate min notional
if price * quantity < min_notional:
    raise ValueError("Order below minimum notional")
```

### 12.5 How are tick size and step size enforced?
```python
def round_to_tick_size(price, tick_size):
    return Decimal(str(price)).quantize(tick_size, rounding=ROUND_DOWN)

def round_to_step_size(quantity, step_size):
    return Decimal(str(quantity)).quantize(step_size, rounding=ROUND_DOWN)
```

---

## 13. DCA Order Placement

### 13.1 Are all DCA orders placed immediately when a signal arrives?
**Yes.** All DCA limit orders are placed immediately after position group creation.

### 13.2 Or are they placed one at a time as price moves?
**No.** All orders placed upfront as limit orders.

### 13.3 What order type is used?
- Entry: Configurable (`entry_order_type`: "limit" or "market")
- DCA legs: Always LIMIT orders
- TP orders: LIMIT orders

### 13.4 How are partially filled DCA orders handled?
- `dca_orders.filled_quantity` tracks partial fills
- Order remains open until fully filled or cancelled
- Position metrics updated on each partial fill

### 13.5 What retry logic exists for failed order submissions?
3 retries with exponential backoff (1s, 2s, 4s) in `order_management.py:submit_order()`.

### 13.6 How many retry attempts with what backoff strategy?
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(ExchangeError)
)
async def submit_order(...):
```

---

## 14. Order Fill Monitoring

### 14.1 Is there a webhook/websocket listening for fill events?
**No.** Polling-based monitoring is used.

### 14.2 Or is polling used? What is the polling interval?
**Yes.** `OrderFillMonitorService` polls every **2 seconds**.

### 14.3 How is "Filled Legs / Total Legs" count updated?
```python
position_group.filled_dca_legs = len([o for o in orders if o.status == 'FILLED'])
position_group.total_dca_legs = len(orders)
```

### 14.4 When a DCA fills, is the TP order placed immediately?
**Yes.** In `order_fill_monitor.py:_handle_order_fill()`:
```python
if order.order_type == "DCA" and order.status == "FILLED":
    await self._place_tp_order_for_leg(order, position_group)
```

### 14.5 What happens if a DCA order is partially filled?
- `filled_quantity` updated
- No TP placed until fully filled
- Position metrics recalculated with partial fill

### 14.6 How is the OrderFillMonitorService started and managed?
Started in `backend/app/main.py` on application startup:
```python
@app.on_event("startup")
async def startup():
    order_fill_monitor = OrderFillMonitorService(...)
    asyncio.create_task(order_fill_monitor.start())
```

---

## 15. DCA Cancellation

### 15.1 On exit signal - are ALL unfilled DCA orders cancelled?
**Yes.** In `position_closer.py:close_position()`:
```python
unfilled_orders = await dca_repo.get_unfilled_orders(position_group_id)
for order in unfilled_orders:
    await connector.cancel_order(order.exchange_order_id, symbol)
```

### 15.2 On TP hit (per-leg mode) - is only that leg's order cancelled?
**No cancellation needed** - the TP order fills, not cancels. But if aggregate TP hits, all unfilled DCA orders are cancelled.

### 15.3 If price moves beyond the last DCA level, what happens?
All DCA orders remain unfilled. Position continues with whatever was filled. Aggregate TP still monitors based on filled positions.

### 15.4 How is order-not-found handled during cancellation?
Caught and logged but doesn't fail the close operation:
```python
try:
    await connector.cancel_order(order_id, symbol)
except OrderNotFoundError:
    logger.warning(f"Order {order_id} already cancelled or filled")
```

---

## 16. Take-Profit Modes Overview

### 16.1 What TP modes are supported?
1. **per_leg**: Individual TP per filled DCA leg
2. **aggregate**: Single TP based on weighted average entry
3. **hybrid**: Both per_leg and aggregate, first trigger wins
4. **pyramid_aggregate**: Per-pyramid aggregate TPs

### 16.2 Where is the TP mode configured?
In `dca_configurations.tp_mode` field.

### 16.3 How is TP mode stored in DCA configuration?
```python
class DCAConfiguration(Base):
    tp_mode: str  # "per_leg", "aggregate", "hybrid", "pyramid_aggregate"
    tp_settings: dict  # {"tp_aggregate_percent": 2.0, "pyramid_tp_percents": {...}}
```

---

## 17. Per-Leg TP Mode

### 17.1 Is each TP calculated from the ACTUAL FILL PRICE?
**Yes.** TP price = fill_price * (1 + tp_percent/100) for longs.

### 17.2 Example calculation
DCA2 fills at $99.00 with TP of +1.5%:
```
TP target = $99.00 * 1.015 = $100.485
```

### 17.3 How is the TP order placed?
As a LIMIT SELL order at the calculated TP price.

### 17.4 What happens when only one leg hits TP?
Only that leg closes. Other legs remain open with their own TPs.

---

## 18. Aggregate TP Mode

### 18.1 How is the weighted average entry price calculated?
```python
weighted_avg = sum(fill_price * quantity for each order) / total_quantity
```

### 18.2 When a new DCA fills, is the average recalculated?
**Yes.** `position_manager.py:update_weighted_average()` called on each fill.

### 18.3 Is the TP target based on this weighted average?
**Yes.** `aggregate_tp_price = weighted_avg * (1 + tp_aggregate_percent/100)`

### 18.4 When aggregate TP hits, are ALL open legs closed together?
**Yes.** Single market sell order for entire position quantity.

---

## 19. Hybrid TP Mode

### 19.1 Do both per-leg and aggregate TP systems run simultaneously?
**Yes.** Both TP orders placed and monitored.

### 19.2 What determines "first trigger wins"?
Whichever price level is reached first by market.

### 19.3 If per-leg TP hits first, does it only close that leg or everything?
**Only that leg.** Aggregate TP is then recalculated for remaining quantity.

### 19.4 How are the remaining legs handled after a partial close?
Aggregate TP recalculated with remaining position. Per-leg TPs continue for unfilled legs.

---

## 20. Pyramid Aggregate TP Mode

### 20.1 What is Pyramid Aggregate TP Mode?
Each pyramid has its own aggregate TP based on that pyramid's weighted average entry.

### 20.2 How does it differ from regular Aggregate mode?
- Regular: One TP for entire position across all pyramids
- Pyramid Aggregate: Separate TP per pyramid

### 20.3 How are multiple pyramids' entries weighted together?
They're NOT weighted together. Each pyramid tracks its own weighted average and TP independently.

---

## 21. TP Order Execution

### 21.1 Are TP orders placed as limit orders or monitored internally?
**Limit orders** placed on exchange.

### 21.2 If price hits TP but order doesn't fill, what happens?
Order remains open. `OrderFillMonitor` continues polling until filled.

### 21.3 How is slippage handled?
`risk.max_slippage_percent` used for market orders only. Limit TPs don't have slippage (fill at limit price or better).

---

## 22. Queue Management System

### 22.1 How does the signal queue work?
1. Signal arrives via webhook
2. If pool full, signal added to `queued_signals` table with status `QUEUED`
3. `QueueManagerService` polls every 10 seconds
4. Highest priority signal promoted when slot available

### 22.2 What triggers a signal to be queued vs immediately executed?
- **Immediate**: Pool has available slot AND risk validation passes
- **Queued**: Pool full OR waiting for pyramid completion

### 22.3 How is execution pool size limit enforced?
`ExecutionPoolManager.request_slot()` checks current active position count against `max_open_positions_global`.

### 22.4 What is the QueueManagerService polling interval?
**10 seconds** (`QUEUE_MANAGER_POLL_INTERVAL_SECONDS = 10`).

---

## 23. Queue Priority Calculation

### 23.1 How is dynamic priority score calculated?
```python
def calculate_queue_priority(signal, active_positions):
    score = Decimal("0")

    # Time waiting bonus (older = higher priority)
    wait_minutes = (now - signal.queued_at).total_seconds() / 60
    score += wait_minutes * TIME_WEIGHT

    # Replacement count bonus
    score += signal.replacement_count * REPLACEMENT_WEIGHT

    # Current loss bonus (bigger loss = higher priority)
    if signal.current_loss_percent:
        score += abs(signal.current_loss_percent) * LOSS_WEIGHT

    # Pyramid continuation bonus
    if is_pyramid_for_active_position(signal, active_positions):
        score += PYRAMID_BONUS

    return score
```

### 23.2 What factors contribute to priority?
1. Time waiting in queue
2. Replacement count (re-queued signals)
3. Current loss percent
4. Pyramid continuation status

### 23.3 How is FIFO tiebreak handled?
`queued_at` timestamp as secondary sort key.

### 23.4 How does pyramid continuation affect priority?
+10000 bonus to ensure pyramids process before new positions.

---

## 24. Queue Operations

### 24.1 How is signal promotion from queue to active pool handled?
```python
async def promote_highest_priority_signal():
    signals = await repo.get_all_queued_signals()
    signals_with_priority = [(s, calculate_priority(s)) for s in signals]
    signals_with_priority.sort(key=lambda x: (-x[1], x[0].queued_at))

    for signal, priority in signals_with_priority:
        if await execution_pool.request_slot():
            signal.status = QueueStatus.PROMOTED
            signal.promoted_at = datetime.utcnow()
            await process_signal(signal)
            break
```

### 24.2 What happens when a queued signal is manually promoted?
`force_add_specific_signal_to_pool()` bypasses pool limit check and promotes immediately.

### 24.3 How does force-add work?
Sets `status = PROMOTED` without checking pool availability.

### 24.4 How is signal replacement handled?
If same symbol/timeframe/exchange signal arrives while one is queued:
1. Old signal status → `REPLACED`
2. New signal added with `replacement_count = old.replacement_count + 1`

### 24.5 Can queued signals be cancelled/removed?
**Yes.** `DELETE /api/v1/queue/{signal_id}` sets status to `CANCELLED`.

---

## 25. Risk Engine Overview

### 25.1 What is the Risk Engine's purpose?
1. Pre-trade risk validation (before position creation)
2. Loss offset strategy (close losers using winners' profits)
3. Risk timer management
4. Circuit breaker for daily loss limits

### 25.2 What is the polling/evaluation interval?
**60 seconds** for loss offset evaluation.

### 25.3 What triggers risk evaluation?
- Timer-based (every 60s)
- Manual trigger via API
- Position close events

### 25.4 How is RiskEngineService started and managed?
```python
@app.on_event("startup")
async def startup():
    risk_engine = RiskEngineService(...)
    asyncio.create_task(risk_engine.start_periodic_evaluation())
```

---

## 26. Offset Loss Strategy

### 26.1 What is the offset loss strategy?
Close a losing position by taking profits from winning positions to offset the loss.

### 26.2 How is a "losing" position identified for closure?
```python
def _filter_eligible_losers(positions, config):
    return [p for p in positions if
        p.status == ACTIVE and
        p.unrealized_pnl_percent <= config.loss_threshold_percent and
        p.risk_blocked == False and
        p.risk_timer_expires and p.risk_timer_expires <= now and
        _check_pyramids_complete(p, config.required_pyramids_for_timer)
    ]
```

### 26.3 What selection strategies exist?
**Largest loss first** - loser with biggest absolute loss selected.

### 26.4 How are "winning" positions selected for partial close?
```python
winners = [p for p in positions if p.unrealized_pnl_usd > 0]
winners.sort(key=lambda p: p.unrealized_pnl_usd, reverse=True)
return winners[:config.max_winners_to_combine]
```

### 26.5 What percentage of winners is closed to offset losses?
Calculated to exactly cover the loss:
```python
required_profit = abs(loser.unrealized_pnl_usd)
# Partial close winners until required_profit is reached
```

---

## 27. Risk Timers & Eligibility

### 27.1 How do risk timers work per position?
After pyramid completion, a timer starts. Position becomes risk-eligible when timer expires.

### 27.2 What is the default timer duration?
**15 minutes** (`post_pyramids_wait_minutes = 15`).

### 27.3 When does a position become eligible for risk evaluation?
When:
1. `pyramid_count >= required_pyramids_for_timer`
2. All DCA legs filled
3. `risk_timer_expires <= now`
4. `risk_blocked == False`

### 27.4 Does pyramid continuation reset the risk timer?
**Yes.** New pyramid resets timer to `now + post_pyramids_wait_minutes`.

### 27.5 How is timer state persisted?
```python
position_group.risk_timer_start = datetime.utcnow()
position_group.risk_timer_expires = datetime.utcnow() + timedelta(minutes=15)
position_group.risk_eligible = False  # Until timer expires
```

---

## 28. Risk Manual Controls

### 28.1 How does blocking a position work?
`PUT /api/v1/risk/positions/{id}/block`:
```python
position.risk_blocked = True
```
Blocked positions are excluded from loss offset evaluation.

### 28.2 How does unblocking work?
`PUT /api/v1/risk/positions/{id}/unblock`:
```python
position.risk_blocked = False
```

### 28.3 What does "skip next evaluation" do?
`PUT /api/v1/risk/positions/{id}/skip`:
```python
position.risk_skip_once = True
```
Position skipped in next evaluation cycle, then flag auto-clears.

### 28.4 How does force-stop affect the queue?
`POST /api/v1/risk/force-stop`:
```python
config.engine_force_stopped = True
```
All new signals rejected with "Engine force stopped by user".

### 28.5 How does force-start resume operations?
`POST /api/v1/risk/force-start`:
```python
config.engine_force_stopped = False
```

### 28.6 What is max realized loss threshold?
`max_realized_loss_usd` - Daily loss limit. When exceeded:
```python
config.engine_paused_by_loss_limit = True
```

---

## 29. Risk Actions Logging

### 29.1 How are risk actions recorded?
`risk_actions` table stores each action with full context.

### 29.2 What action types exist?
- `OFFSET_LOSS`
- `MANUAL_BLOCK`
- `MANUAL_UNBLOCK`
- `SKIP_EVALUATION`
- `FORCE_STOP`
- `FORCE_START`

### 29.3 What details are stored per action?
```python
class RiskAction(Base):
    id: UUID
    action_type: str
    loser_position_id: UUID  # For OFFSET_LOSS
    winner_position_ids: List[UUID]
    loser_pnl_usd: Decimal
    offset_amount_usd: Decimal
    created_at: datetime
    notes: str
```

### 29.4 How is risk action history queried?
`GET /api/v1/risk/actions?limit=50&offset=0`

---

## 30. Telegram Notification System

### 30.1 How is Telegram integration configured?
In `user_settings` table:
```json
{
  "telegram": {
    "bot_token": "xxx",
    "chat_id": "-100xxx",
    "enabled": true
  }
}
```

### 30.2 What notification types are supported?
- Signal received
- Order placed
- Order filled
- TP hit
- Position closed
- Risk action taken
- Error alerts

### 30.3 How are messages formatted?
Using `TelegramMessageBuilder` with emoji-rich templates:
```
📥 *Signal Received*
Symbol: BTCUSDT
Side: LONG
Entry: $95,000.00
```

---

## 31. Telegram Quiet Hours

### 31.1 How do quiet hours work?
During quiet hours, only urgent notifications are sent.

### 31.2 What is the urgent-only override?
`urgent: true` flag bypasses quiet hours for critical alerts (errors, large PnL).

### 31.3 How are quiet hours configured?
```json
{
  "telegram": {
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "quiet_hours_timezone": "UTC"
  }
}
```

---

## 32. Telegram Message Types

### 32.1 Signal reception message
```
📥 *New Signal*
Symbol: {symbol}
Side: {side}
Entry: ${entry_price}
```

### 32.2 Order fill message
```
✅ *Order Filled*
Symbol: {symbol}
Type: {order_type}
Price: ${fill_price}
Quantity: {quantity}
```

### 32.3 TP hit message
```
🎯 *Take Profit Hit*
Symbol: {symbol}
Entry: ${entry}
Exit: ${exit}
PnL: ${pnl} ({pnl_percent}%)
```

### 32.4 Risk engine action message
```
⚠️ *Risk Action*
Type: OFFSET_LOSS
Loser: {symbol} (${loss})
Winners: {winners}
```

### 32.5 Can message types be toggled?
**Yes.** `telegram.notification_types` array in settings.

---

## 33. Dashboard & Analytics

### 33.1 How is TVL calculated?
```python
tvl = sum(balance.free + balance.used for balance in exchange_balances)
```

### 33.2 How is free USDT balance fetched?
```python
balance = await connector.fetch_balance()
free_usdt = balance['USDT']['free']
```

### 33.3 How is unrealized PnL calculated?
```python
unrealized_pnl = sum(p.unrealized_pnl_usd for p in active_positions)
```

### 33.4 How is realized PnL aggregated?
```python
realized_pnl = sum(p.realized_pnl_usd for p in closed_positions)
```

### 33.5 How is win rate calculated?
```python
wins = count(p for p in closed_positions if p.realized_pnl_usd > 0)
win_rate = wins / total_closed * 100
```

### 33.6 What caching is applied?
Redis cache with 60-second TTL for dashboard data.

---

## 34. Position History & Metrics

### 34.1 How is position history stored?
Closed positions remain in `position_groups` table with `status = CLOSED`.

### 34.2 What pagination is applied?
`limit` and `offset` query parameters (default: limit=50, max=100).

### 34.3 How is position duration calculated?
```python
duration = closed_at - created_at
```

### 34.4 What metrics are tracked per closed position?
- `realized_pnl_usd`
- `realized_pnl_percent`
- `total_invested_usd`
- `total_filled_quantity`
- `pyramid_count`
- `filled_dca_legs`
- Duration

---

## 35. Settings Management

### 35.1 How are user settings structured?
JSON field in `users` table with nested categories.

### 35.2 What settings categories exist?
- `risk_engine`: Risk parameters
- `telegram`: Notification settings
- `trading`: Default trading parameters
- `display`: UI preferences

### 35.3 How are settings updated?
`PUT /api/v1/settings` with partial update support.

### 35.4 Are settings changes validated?
**Yes.** Pydantic schemas validate all settings before persistence.

---

## 36. API Security & Rate Limiting

### 36.1 What CORS configuration is applied?
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 36.2 What rate limits exist per endpoint?
- General: 100/min
- Login: 10/min
- Registration: 5/min
- Webhook: 20/min

### 36.3 How is rate limiting implemented?
SlowAPI library with Redis backend:
```python
limiter = Limiter(key_func=get_remote_address, storage_uri="redis://redis:6379")
```

### 36.4 Are sensitive endpoints more restricted?
**Yes.** Login, registration, and password reset have stricter limits.

---

## 37. Background Services Architecture

### 37.1 What background services run on startup?
1. **OrderFillMonitorService** (2s polling)
2. **QueueManagerService** (10s polling)
3. **RiskEngineService** (60s evaluation)

### 37.2 How are services started and stopped?
```python
@app.on_event("startup")
async def startup():
    services = [
        OrderFillMonitorService(...),
        QueueManagerService(...),
        RiskEngineService(...)
    ]
    for service in services:
        asyncio.create_task(service.start())

@app.on_event("shutdown")
async def shutdown():
    for service in services:
        await service.stop()
```

### 37.3 What happens if a background service crashes?
- Exception logged
- Service restarts after delay
- Health check marks service as unhealthy

### 37.4 How is service health monitored?
Redis heartbeat keys with TTL:
```python
await redis.set(f"health:{service_name}", "ok", ex=30)
```

---

## 38. Database & Persistence

### 38.1 What ORM is used?
**SQLAlchemy 2.0** with async support.

### 38.2 Is async database access supported?
**Yes.** Using `asyncpg` driver and `AsyncSession`.

### 38.3 How are database migrations handled?
**Alembic** with auto-generation:
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### 38.4 What indexes exist for performance?
- `ix_position_groups_user_status` (user_id, status)
- `ix_position_groups_active_unique` (partial unique)
- `ix_dca_orders_position_group` (position_group_id)
- `ix_queued_signals_status` (status, queued_at)
- Plus 8 more strategic indexes

### 38.5 How is connection pooling configured?
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30
)
```

---

## 39. Error Handling & Logging

### 39.1 How are errors logged?
Using Python `logging` with structured format:
```python
logger.error(f"Order submission failed", extra={
    "symbol": symbol,
    "error": str(e),
    "traceback": traceback.format_exc()
})
```

### 39.2 What log levels are used?
- DEBUG: Detailed debugging
- INFO: General operations
- WARNING: Recoverable issues
- ERROR: Failures requiring attention
- CRITICAL: System-wide failures

### 39.3 How is log rotation configured?
```python
handler = RotatingFileHandler(
    "logs/app.log",
    maxBytes=10_000_000,  # 10MB
    backupCount=5
)
```

### 39.4 Are logs structured?
**Yes.** JSON format for production:
```json
{"timestamp": "...", "level": "ERROR", "message": "...", "extra": {...}}
```

### 39.5 How can logs be viewed via API?
`GET /api/v1/logs?level=ERROR&limit=100` (admin only)

---

## 40. Frontend Architecture

### 40.1 What frontend framework is used?
**React 18** with TypeScript.

### 40.2 What state management is used?
**Zustand** with 9 specialized stores:
- `authStore`
- `positionsStore`
- `dashboardStore`
- `dcaConfigStore`
- `settingsStore`
- `queueStore`
- `riskStore`
- `historyStore`
- `notificationStore`

### 40.3 What pages exist?
- Dashboard (/)
- Positions (/positions)
- History (/history)
- Queue (/queue)
- DCA Configs (/dca-configs)
- Settings (/settings)
- Login (/login)

### 40.4 How is authentication handled?
HttpOnly cookies with automatic refresh. `authStore` tracks login state.

---

## 41. Frontend Features

### 41.1 Is mobile responsive design implemented?
**Yes.** MUI responsive breakpoints and mobile-first components.

### 41.2 Is dark mode supported?
**Yes.** Both dark and light themes are supported with a toggle button in the header. Theme preference is persisted to localStorage via `themeStore`.

### 41.3 Are keyboard shortcuts implemented?
**No.** Not currently implemented.

### 41.4 Is pull-to-refresh supported on mobile?
**No.** Manual refresh button instead.

### 41.5 How are loading states displayed?
MUI Skeleton components for card placeholders.

### 41.6 How are errors handled?
React Error Boundaries + toast notifications via `notificationStore`.

---

## 42. Position Close Scenarios

### 42.1 Manual close from UI
`POST /api/v1/positions/{id}/close`:
1. Cancel all unfilled orders
2. Place market sell order for filled quantity
3. Update status to CLOSING → CLOSED

### 42.2 TP-triggered close
1. TP limit order fills on exchange
2. `OrderFillMonitor` detects fill
3. Position metrics updated
4. Status → CLOSED (if all TPs filled)

### 42.3 Risk engine forced close
1. Loser selected for offset
2. Market sell placed
3. Status → CLOSING → CLOSED
4. RiskAction logged

### 42.4 Exit signal close
1. Exit signal received (action: "sell" for long)
2. Cancel all open orders
3. Place market close
4. Status → CLOSED

### 42.5 What cleanup occurs?
- All unfilled DCA orders cancelled
- All unfilled TP orders cancelled
- Position metrics finalized
- `closed_at` timestamp set

---

## 43. Exchange Synchronization

### 43.1 What does "sync with exchange" do?
Reconciles local database state with exchange order states.

### 43.2 How are states reconciled?
1. Fetch all open orders from exchange
2. Compare with local `dca_orders` and `tp_orders`
3. Update local status to match exchange
4. Cancel orphaned exchange orders

### 43.3 Orders exist on exchange but not locally?
Logged as warning and optionally cancelled.

### 43.4 Local orders don't exist on exchange?
Local status updated to CANCELLED.

---

## 44. Precision & Validation

### 44.1 How are exchange precision rules fetched?
Via CCXT `load_markets()` which returns tick_size, step_size, min_notional.

### 44.2 How is tick size enforced on prices?
```python
price = (price // tick_size) * tick_size
```

### 44.3 How is step size enforced on quantities?
```python
quantity = (quantity // step_size) * step_size
```

### 44.4 What happens if an order violates precision rules?
Order rejected before submission with validation error.

### 44.5 Is precision validation cached?
**Yes.** 48-hour Redis cache for market precision rules.

---

## 45. Multi-User Support

### 45.1 How are users isolated?
- All queries filtered by `user_id`
- Foreign key constraints enforce isolation
- Separate API keys per user per exchange

### 45.2 Can multiple users trade the same symbol?
**Yes.** Each user has independent positions.

### 45.3 How are user-specific configurations stored?
- `dca_configurations` has `user_id` FK
- `exchange_credentials` has `user_id` FK
- `user_settings` embedded in `users` table

### 45.4 Is there admin/superuser functionality?
**Yes.** `users.is_admin` flag enables admin endpoints.

---

## 46. Testing & Mock Exchange

### 46.1 Is there a mock exchange connector?
**Yes.** `MockExchangeConnector` in `backend/app/services/exchange_abstraction/mock_connector.py` and standalone `mock_exchange/` service.

### 46.2 How does testnet mode work?
Exchange credentials have `testnet: bool` flag. Connector uses testnet URLs when enabled.

### 46.3 What test coverage exists?
- **765+ tests** passing
- Unit tests for all services
- Integration tests with mock exchange
- API endpoint tests

### 46.4 How are integration tests structured?
```
tests/
├── integration/
│   ├── conftest.py
│   ├── test_api_actions.py
│   ├── test_api_endpoints.py
│   ├── test_full_signal_flow.py
│   └── test_resilience.py
├── test_*.py (unit tests)
```

Mock exchange provides:
- Admin endpoints for price control
- Order matching engine
- Full Binance-compatible REST API
