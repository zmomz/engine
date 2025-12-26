# Investigation Answers

All answers are derived from the codebase analysis.

---

## 1. Webhook Endpoint & Authentication

### 1. Is there webhook signature validation implemented?
**Yes.** Implemented in `backend/app/services/webhook/signature_validation.py`. The `WebhookSignatureValidator` class provides HMAC-SHA256 signature validation using the user's webhook secret.

### 2. Where is security.webhook_signature_validation checked?
In `backend/app/api/webhook.py`, the endpoint checks `user_settings.security.webhook_signature_validation`. If enabled, it calls `WebhookSignatureValidator.validate()` which verifies the `X-Webhook-Signature` header against the computed HMAC of the raw body.

### 3. What response does an unauthenticated request receive?
Returns HTTP 401 with message `"Invalid webhook signature"` when signature validation fails.

### 4. Are failed authentication attempts logged with details?
**Yes.** The validator logs warnings including expected vs received signatures:
```python
logger.warning(f"Webhook signature mismatch for user {user_id}. Expected: {expected_sig[:16]}..., Got: {received_sig[:16]}...")
```

### 5. What rate limiting is applied to webhook endpoints?
**60 requests per minute** per endpoint, enforced by SlowAPI:
```python
@limiter.limit("60/minute")
async def receive_webhook(...)
```

### 6. How is the webhook secret generated and stored per user?
Generated using `secrets.token_urlsafe(32)` when user enables webhook signature validation. Stored in `user.settings["security"]["webhook_secret"]` JSON field in the database.

---

## 2. Signal Transformation

### 1. How is raw JSON transformed into an internal signal object?
In `backend/app/services/webhook/webhook_payloads.py`, the `SignalPayloadParser.parse()` method transforms raw webhook JSON into a `ParsedSignal` dataclass. It handles TradingView format, custom format, and legacy format.

### 2. Are TradingView placeholders properly mapped?
**Yes.** TradingView placeholders are mapped:
- `{{ticker}}` → `symbol`
- `{{exchange}}` → `exchange`
- `{{interval}}` → `timeframe`
- `{{strategy.order.action}}` → `action` (buy/sell)
- `{{strategy.order.price}}` → `price`

### 3. How is execution_intent.type handled differently?
The `execution_intent.type` field determines signal handling:
- `"entry"` → Creates new position or pyramid
- `"exit"` → Closes existing position
- `"dca"` → Adds DCA layer to existing position

### 4. What are the key transformations (exchange lowercasing, action→side mapping)?
- Exchange names normalized to lowercase: `exchange.lower()`
- Action mapped to side: `"buy"` → `"long"`, `"sell"` → `"short"`
- Symbol normalized (removes `/` if present)
- Timeframe validated against allowed values

### 5. How are malformed/missing fields handled (validation errors)?
Pydantic validation raises `ValidationError`. The webhook endpoint catches this and returns HTTP 422 with validation error details. Missing required fields are rejected.

### 6. Is the raw payload logged before or after validation?
**Before validation.** The raw payload is logged at DEBUG level immediately upon receipt:
```python
logger.debug(f"Received webhook payload: {payload}")
```

---

## 3. User Authentication & Session Management

### 1. How is user registration handled?
In `backend/app/api/auth.py`, the `/register` endpoint:
1. Validates email uniqueness
2. Hashes password with bcrypt
3. Creates user record with default settings
4. Returns user data (no auto-login)

### 2. What password hashing algorithm is used?
**bcrypt** via `passlib.context.CryptContext`:
```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

### 3. How are JWT tokens generated and validated?
- Generated using `python-jose` with HS256 algorithm
- Payload includes: `sub` (user_id), `exp` (expiration), `iat` (issued at)
- Secret from `SECRET_KEY` environment variable
- Validated via `decode()` with automatic expiration check

### 4. What is the token expiration policy?
**24 hours** by default:
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
```

### 5. How are HTTP cookies secured (HttpOnly, Secure, SameSite)?
Cookies set with:
```python
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=True,  # HTTPS only
    samesite="lax",
    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
)
```

### 6. How is user logout handled (token invalidation)?
Logout clears the cookie by setting it with `max_age=0`. No server-side token blacklist is implemented (stateless JWT).

### 7. What rate limiting is applied to login/registration endpoints?
- Login: **5 requests per minute**
- Registration: **3 requests per minute**

---

## 4. Exchange Integration & API Keys

### 1. Which exchanges are supported (Binance, Bybit, etc.)?
**Binance** and **Bybit** are supported. Defined in `backend/app/services/exchange_abstraction/factory.py`:
```python
SUPPORTED_EXCHANGES = ["binance", "bybit"]
```

### 2. How are exchange API keys encrypted and stored?
Encrypted using **Fernet symmetric encryption** (AES-128-CBC). The `EncryptionService` in `backend/app/core/security.py` encrypts API key + secret as JSON, stores as base64 string in `user.encrypted_api_keys[exchange_name]["encrypted_data"]`.

### 3. What encryption algorithm is used for API key storage?
**Fernet** (AES-128-CBC with HMAC-SHA256 for authentication). Key derived from `ENCRYPTION_KEY` environment variable.

### 4. How is testnet mode configured per exchange?
Stored per-exchange in `encrypted_api_keys`:
```python
encrypted_api_keys = {
    "binance": {
        "encrypted_data": "...",
        "testnet": True  # or False
    }
}
```
Connector checks `exchange_config.get("testnet", False)` when initializing.

### 5. How does the exchange connector factory work?
`get_exchange_connector(exchange_name, exchange_config)` in `factory.py`:
1. Validates exchange is supported
2. Decrypts API keys
3. Returns `BinanceConnector` or `BybitConnector` instance

### 6. What error mapping exists for exchange-specific errors?
Each connector maps CCXT exceptions to custom exceptions:
- `ccxt.InsufficientFunds` → `InsufficientFundsError`
- `ccxt.InvalidOrder` → `InvalidOrderError`
- `ccxt.NetworkError` → `ExchangeConnectionError`

### 7. How are exchange precision rules (tick size, step size) fetched and cached?
Fetched via `load_markets()` on connector initialization. Cached in `self._markets` dict. Precision info in `market["precision"]` and `market["limits"]`.

### 8. How is account type handled for Bybit (UNIFIED/CONTRACT)?
Bybit connector accepts `account_type` in config:
```python
account_type = exchange_config.get("account_type", "UNIFIED")
```
Sets CCXT options accordingly for API calls.

---

## 5. Position Group Creation

### 1. What are the steps to create a position group?
In `backend/app/services/position/position_creator.py`:
1. Validate signal data
2. Check for existing position (same symbol/timeframe)
3. Create `PositionGroup` model instance
4. Set initial status to `WAITING`
5. Persist to database
6. Generate DCA orders
7. Submit entry order

### 2. What data is stored in a position group?
Key fields in `PositionGroup` model:
- `id`, `user_id`, `symbol`, `timeframe`, `exchange`
- `side` (long/short), `status`
- `weighted_avg_entry`, `total_filled_quantity`, `total_invested_usd`
- `pyramid_count`, `pyramid_index`
- `unrealized_pnl_usd`, `realized_pnl_usd`
- `risk_timer_start`, `is_blocked`
- `created_at`, `closed_at`

### 3. How is base entry price determined?
From signal's `price` field, or current market price if not provided:
```python
entry_price = signal.price or await connector.get_current_price(symbol)
```

### 4. Is Position Group immediately persisted or flushed for ID?
**Flushed** to get ID before creating related orders:
```python
session.add(position_group)
await session.flush()  # Gets ID
```

### 5. Where is the creation code located?
`backend/app/services/position/position_creator.py` - `PositionCreator.create_position_group()`

### 6. What validations occur before position creation?
- Symbol format validation
- Exchange supported check
- User has API keys for exchange
- Pool size limit check (unless pyramid)
- Duplicate position check

---

## 6. Position Identity & Lookup

### 1. Is a Position Group uniquely identified by pair + timeframe?
**Yes**, within active positions. The lookup uses `symbol + timeframe + user_id` as the composite key for finding existing positions.

### 2. What happens if two signals arrive simultaneously for BTCUSDT 15m?
The second signal becomes a **pyramid** if:
- First position exists and is active
- Pyramid limit not exceeded
Otherwise, it's queued or rejected.

### 3. How are race conditions prevented (or not)?
**Database-level**: Uses `SELECT FOR UPDATE` in critical queries. No explicit distributed locking - relies on database row-level locks and single-threaded async processing per user.

### 4. What is the lookup mechanism (database vs in-memory filter)?
**Database lookup** via repository:
```python
await repo.get_active_by_symbol_timeframe(user_id, symbol, timeframe)
```

### 5. Is there a unique constraint on the database level?
**No unique constraint** on symbol+timeframe - allows multiple closed positions. Active position uniqueness enforced in application logic.

---

## 7. Position State Machine

### 1. What states are defined?
In `backend/app/models/position_group.py`:
```python
class PositionGroupStatus(str, Enum):
    WAITING = "waiting"       # Entry order placed, not filled
    ACTIVE = "active"         # Has filled orders, trading
    CLOSING = "closing"       # Close initiated
    CLOSED = "closed"         # Fully closed
    FAILED = "failed"         # Error occurred
```

### 2. Are all states implemented and used?
**Yes**, all states are used:
- `WAITING`: On creation before entry fill
- `ACTIVE`: When entry order fills
- `CLOSING`: When exit signal received
- `CLOSED`: After market close order executes
- `FAILED`: On unrecoverable errors

### 3. What triggers state transitions?
- `WAITING → ACTIVE`: Entry order fill detected
- `ACTIVE → CLOSING`: Exit signal or risk engine action
- `CLOSING → CLOSED`: Market close order executed
- `Any → FAILED`: Critical error during processing

### 4. Can states go backwards?
**No**, states only progress forward. No reverse transitions implemented.

### 5. Where is state tracked and how is it persisted?
In `position_group.status` column (Enum type). Updated via repository `update()` method.

### 6. Where is the transition logic located?
Distributed across services:
- `position_creator.py`: WAITING state
- `order_fill_monitor.py`: WAITING → ACTIVE
- `position_closer.py`: ACTIVE → CLOSING → CLOSED

---

## 8. Pyramid Detection & Handling

### 1. How does the system detect this is a pyramid (not a new position)?
In `signal_router.py`, checks for existing active position:
```python
existing = await repo.get_active_by_symbol_timeframe(user_id, symbol, timeframe)
if existing and existing.status == PositionGroupStatus.ACTIVE:
    # This is a pyramid
```

### 2. Is this pyramid added without consuming a pool slot?
**Yes**. Pyramids increment `pyramid_count` on existing position but don't create new pool entries:
```python
if is_pyramid:
    existing.pyramid_count += 1
    # No new position created
```

### 3. What is the maximum number of pyramids allowed?
Configured in user settings: `grid_strategy.max_pyramids` (default: 5)

### 4. What happens if a 6th pyramid signal arrives (when max is 5)?
Signal is **ignored** with log warning:
```python
if position.pyramid_count >= max_pyramids:
    logger.warning(f"Max pyramids reached for {symbol}")
    return  # Signal ignored
```

### 5. How does pyramid continuation bypass work?
In `queue_priority.py`, pyramids get priority boost and bypass queue:
```python
if is_pyramid_continuation:
    priority_score += PYRAMID_CONTINUATION_BONUS  # +1000
```

---

## 9. Pyramid Counter & Storage

### 1. Where is the pyramid counter stored?
In `PositionGroup.pyramid_count` column (Integer, default=1).

### 2. Is pyramid count incremented atomically?
**Yes**, via SQLAlchemy:
```python
position.pyramid_count = PositionGroup.pyramid_count + 1
await session.flush()
```

### 3. How to query "how many pyramids does BTCUSDT 1h have"?
```python
position = await repo.get_active_by_symbol_timeframe(user_id, "BTCUSDT", "1h")
pyramid_count = position.pyramid_count
```

### 4. Does pyramid count affect Risk Engine activation?
**No**. Risk engine evaluates based on position PnL and time, not pyramid count.

### 5. How is pyramid index tracked per DCA order?
Each DCA order has `pyramid_index` field matching the pyramid it belongs to:
```python
order.pyramid_index = position.pyramid_count
```

---

## 10. DCA Order Generation

### 1. Does each pyramid generate its own set of DCA orders?
**Yes**. Each pyramid entry triggers new DCA order generation based on the pyramid's entry price.

### 2. Are DCA gaps calculated from the pyramid's entry price?
**Yes**. In `grid_calculator.py`:
```python
dca_price = entry_price * (1 - gap_percent / 100)  # For longs
```

### 3. How are multiple DCA sets managed together?
Each DCA order links to position via `group_id` and has `pyramid_index` to identify which pyramid it belongs to.

### 4. How is DCA order quantity calculated from capital weight?
```python
layer_capital = total_capital * (capital_weight / 100)
quantity = layer_capital / dca_price
```

---

## 11. DCA Configuration Management

### 1. How are DCA layers configured (price gap, capital weight, take profit)?
In `DCAConfiguration` model stored in `user.settings["dca_config"]`:
```python
{
    "layers": [
        {"gap_percent": 1.0, "capital_weight": 20, "tp_percent": 1.5},
        {"gap_percent": 2.5, "capital_weight": 30, "tp_percent": 2.0},
        ...
    ]
}
```

### 2. Is grid_strategy.max_dca_per_pyramid respected?
**Yes**. DCA generation stops when layer count reaches `max_dca_per_pyramid`.

### 3. Can DCA configuration be different per symbol/timeframe/exchange?
**Currently no**. DCA config is global per user. Symbol-specific configs not implemented.

### 4. How are DCA configurations stored (JSON structure)?
As JSON in user settings with `layers` array containing gap, weight, and TP for each level.

### 5. What CRUD operations exist for DCA configs?
Via settings API:
- GET `/settings` - Read current config
- PUT `/settings` - Update config (including DCA)

### 6. How are pyramid-specific DCA levels configured?
Each layer in config has optional `pyramid_index` field. If not specified, applies to all pyramids.

---

## 12. DCA Price & Size Calculation

### 1. How is the DCA price calculated from entry price?
In `grid_calculator.py`:
```python
# For longs: DCA below entry
dca_price = entry_price * (1 - gap_percent / 100)

# For shorts: DCA above entry
dca_price = entry_price * (1 + gap_percent / 100)
```

### 2. Are prices calculated as: DCA1 = entry - gap1%, DCA2 = entry - gap2%?
**Yes**, gaps are cumulative from entry:
- DCA1: entry × (1 - 1.0%)
- DCA2: entry × (1 - 2.5%)
- etc.

### 3. How is capital weight applied to determine order size?
```python
layer_capital = total_position_capital * (capital_weight_percent / 100)
order_quantity = layer_capital / dca_price
```

### 4. Is precision validation applied BEFORE order submission?
**Yes**. In `order_management.py`:
```python
quantity = self._apply_precision(quantity, step_size)
price = self._apply_precision(price, tick_size)
```

### 5. How are tick size and step size enforced?
Using `Decimal.quantize()` with market precision:
```python
def _apply_precision(self, value, precision):
    return Decimal(str(value)).quantize(Decimal(str(precision)))
```

---

## 13. DCA Order Placement

### 1. Are all DCA orders placed immediately when a signal arrives?
**Yes**. All DCA limit orders are placed immediately after entry order:
```python
for layer in dca_layers:
    await order_service.place_limit_order(...)
```

### 2. Or are they placed one at a time as price moves?
**No**. All placed upfront as limit orders at calculated prices.

### 3. What order type is used (LIMIT, MARKET, stop-limit)?
**LIMIT orders** for DCA entries. Market orders only for exits.

### 4. How are partially filled DCA orders handled?
Partial fills tracked via `filled_quantity` on order record. Order remains open until fully filled or cancelled.

### 5. What retry logic exists for failed order submissions?
**3 retries** with exponential backoff:
```python
@retry(max_attempts=3, backoff=2.0)
async def place_order(...)
```

### 6. How many retry attempts with what backoff strategy?
3 attempts with 2x backoff: 1s, 2s, 4s delays.

---

## 14. Order Fill Monitoring

### 1. Is there a webhook/websocket listening for fill events?
**No websocket**. Uses **polling** via `OrderFillMonitorService`.

### 2. Or is polling used? What is the polling interval?
**Polling** with **5 second** interval:
```python
POLL_INTERVAL = 5  # seconds
```

### 3. How is "Filled Legs / Total Legs" count updated?
Calculated dynamically from orders:
```python
filled_legs = len([o for o in orders if o.status == "filled"])
total_legs = len(orders)
```

### 4. When a DCA fills, is the TP order placed immediately?
**Yes**. On DCA fill detection:
```python
if dca_order.status == "filled":
    await self._place_tp_order(dca_order)
```

### 5. What happens if a DCA order is partially filled?
Continues monitoring. TP placed only when DCA is fully filled. Partial fill quantity tracked.

### 6. How is the OrderFillMonitorService started and managed?
Started in `main.py` on app startup:
```python
@app.on_event("startup")
async def startup():
    order_monitor = OrderFillMonitorService()
    asyncio.create_task(order_monitor.start())
```

---

## 15. DCA Cancellation

### 1. On exit signal - are ALL unfilled DCA orders cancelled?
**Yes**. In `position_closer.py`:
```python
await order_service.cancel_open_orders_for_group(position_group.id)
```

### 2. On TP hit (per-leg mode) - is only that leg's order cancelled?
**Yes** for per-leg mode. Only the specific leg's TP order is involved.

### 3. If price moves beyond the last DCA level, what happens?
DCA orders remain open. No automatic adjustment - they stay at original prices.

### 4. How is order-not-found handled during cancellation?
Caught and logged as warning, doesn't break flow:
```python
except OrderNotFoundError:
    logger.warning(f"Order {order_id} not found on exchange, may be filled")
```

---

## 16. Take-Profit Modes Overview

### 1. What TP modes are supported?
Four modes in `TakeProfitMode` enum:
```python
class TakeProfitMode(str, Enum):
    PER_LEG = "per_leg"
    AGGREGATE = "aggregate"
    HYBRID = "hybrid"
    PYRAMID_AGGREGATE = "pyramid_aggregate"
```

### 2. Where is the TP mode configured?
In user settings: `user.settings["grid_strategy"]["tp_mode"]`

### 3. How is TP mode stored in DCA configuration?
Each DCA layer has `tp_percent` field. Mode determines how TPs are calculated and managed.

---

## 17. Per-Leg TP Mode

### 1. Is each TP calculated from the ACTUAL FILL PRICE (not original entry)?
**Yes**. TP calculated from actual fill price:
```python
tp_price = filled_price * (1 + tp_percent / 100)  # For longs
```

### 2. Example: DCA2 fills at $99.00 with TP of +1.5%. Is TP target $100.485?
**Yes**: $99.00 × 1.015 = $100.485

### 3. How is the TP order placed (limit order at target price)?
As LIMIT sell order at calculated TP price:
```python
await order_service.place_limit_order(
    side="sell",
    price=tp_price,
    quantity=filled_quantity
)
```

### 4. What happens when only one leg hits TP - does only that leg close?
**Yes**. In per-leg mode, each leg closes independently.

---

## 18. Aggregate TP Mode

### 1. How is the weighted average entry price calculated?
```python
weighted_avg = sum(fill_price * quantity for each fill) / total_quantity
```
Stored in `position_group.weighted_avg_entry`.

### 2. When a new DCA fills, is the average recalculated?
**Yes**. Updated on each fill:
```python
position.weighted_avg_entry = calculate_weighted_average(all_fills)
```

### 3. Is the TP target based on this weighted average?
**Yes**:
```python
aggregate_tp_price = weighted_avg_entry * (1 + aggregate_tp_percent / 100)
```

### 4. When aggregate TP hits, are ALL open legs closed together?
**Yes**. Single market order closes entire position quantity.

---

## 19. Hybrid TP Mode

### 1. Do both per-leg and aggregate TP systems run simultaneously?
**Yes**. Both TP types are placed:
- Per-leg TPs for each DCA
- Aggregate TP order as well

### 2. What determines "first trigger wins"?
Whichever TP order fills first on the exchange. Fill monitor detects and handles.

### 3. If per-leg TP hits first, does it only close that leg or everything?
**Only that leg**. Other legs remain open with their TPs.

### 4. How are the remaining legs handled after a partial close?
Continue independently. Aggregate TP quantity reduced to match remaining position.

---

## 20. Pyramid Aggregate TP Mode

### 1. What is Pyramid Aggregate TP Mode?
Calculates weighted average across ALL pyramids (not just one pyramid's fills).

### 2. How does it differ from regular Aggregate mode?
Regular aggregate: average within single pyramid
Pyramid aggregate: average across all pyramid entries

### 3. How are multiple pyramids' entries weighted together?
```python
total_weighted = sum(pyramid.avg_entry * pyramid.quantity for each pyramid)
combined_avg = total_weighted / total_position_quantity
```

---

## 21. TP Order Execution

### 1. Are TP orders placed as limit orders or monitored internally?
**Limit orders** placed on exchange. Exchange executes when price reached.

### 2. If price hits TP but order doesn't fill, what happens?
Order remains open. No automatic retry at different price.

### 3. How is slippage handled (risk.max_slippage_percent)?
For market orders (exits), slippage checked:
```python
if slippage_percent > max_slippage_percent:
    if slippage_action == "reject":
        raise SlippageExceededError(...)
    else:
        logger.warning(f"Slippage {slippage_percent}% exceeds max")
```

---

## 22. Queue Management System

### 1. How does the signal queue work?
`QueueManagerService` in `backend/app/services/queue/queue_manager.py` maintains a queue of pending signals. Polls periodically to promote signals to active pool.

### 2. What triggers a signal to be queued vs immediately executed?
Queued when:
- Active pool at capacity (`max_concurrent_positions`)
- Signal doesn't have pyramid priority

### 3. How is execution pool size limit enforced?
```python
active_count = await repo.get_active_count(user_id)
if active_count >= max_concurrent:
    # Queue instead of execute
```

### 4. What is the QueueManagerService polling interval?
**10 seconds**:
```python
POLL_INTERVAL = 10
```

---

## 23. Queue Priority Calculation

### 1. How is dynamic priority score calculated?
In `queue_priority.py`:
```python
score = base_priority
score += time_waiting_minutes * TIME_WEIGHT
score += symbol_priority_bonus
score += pyramid_continuation_bonus
```

### 2. What factors contribute to priority?
- Time waiting (longer = higher priority)
- Symbol priority (configurable per symbol)
- Pyramid continuation (+1000 bonus)
- Manual priority boost

### 3. How is FIFO tiebreak handled when scores are equal?
`created_at` timestamp as secondary sort:
```python
queue.sort(key=lambda x: (-x.priority_score, x.created_at))
```

### 4. How does pyramid continuation affect priority?
**+1000 bonus** to priority score, essentially guaranteeing queue bypass.

---

## 24. Queue Operations

### 1. How is signal promotion from queue to active pool handled?
When slot opens:
```python
next_signal = queue.pop(0)  # Highest priority
await execute_signal(next_signal)
```

### 2. What happens when a queued signal is manually promoted?
Sets `force_execute=True`, bypasses queue on next poll:
```python
signal.force_execute = True
```

### 3. How does force-add work (overriding pool limits)?
Increments `max_concurrent` temporarily or ignores limit check.

### 4. How is signal replacement handled (same symbol/timeframe)?
New signal replaces queued signal for same symbol/timeframe:
```python
existing_queued = find_queued(symbol, timeframe)
if existing_queued:
    queue.remove(existing_queued)
queue.append(new_signal)
```

### 5. Can queued signals be cancelled/removed?
**Yes**, via API endpoint or automatically on position close.

---

## 25. Risk Engine Overview

### 1. What is the Risk Engine's purpose?
Manages losing positions by:
- Identifying positions past timer threshold
- Selecting losers for closure
- Offsetting losses with winner partial closes

### 2. What is the polling/evaluation interval?
**60 seconds**:
```python
POLL_INTERVAL = 60
```

### 3. What triggers risk evaluation (time-based, on-fill, manual)?
- **Time-based**: Every 60 seconds
- **Manual**: Force evaluation via API
- On significant events (configurable)

### 4. How is RiskEngineService started and managed?
Started in `main.py`:
```python
risk_engine = RiskEngineService()
asyncio.create_task(risk_engine.start())
```

---

## 26. Offset Loss Strategy

### 1. What is the offset loss strategy?
Close losing positions and offset realized loss by partially closing winning positions.

### 2. How is a "losing" position identified for closure?
```python
is_loser = position.unrealized_pnl_usd < 0
is_eligible = position.risk_timer_expired and not position.is_blocked
```

### 3. What selection strategies exist (largest loss, best risk/reward)?
In `risk_selector.py`:
- `LARGEST_LOSS`: Position with biggest negative PnL
- `BEST_RISK_REWARD`: Best potential recovery ratio
- `OLDEST_FIRST`: Longest-held losing position

### 4. How are "winning" positions selected for partial close?
Select winners with highest unrealized profit that can cover the loss:
```python
winners = [p for p in positions if p.unrealized_pnl_usd > 0]
winners.sort(key=lambda x: -x.unrealized_pnl_usd)
```

### 5. What percentage of winners is closed to offset losses?
Calculated to exactly offset loss:
```python
offset_needed = abs(loser.realized_loss)
for winner in winners:
    partial_close_percent = offset_needed / winner.unrealized_pnl_usd
```

---

## 27. Risk Timers & Eligibility

### 1. How do risk timers work per position?
Each position has `risk_timer_start` timestamp. Position eligible for risk evaluation when:
```python
time_elapsed = now - position.risk_timer_start
if time_elapsed >= risk_timer_duration:
    # Eligible for risk action
```

### 2. What is the default timer duration?
Configured in settings: `risk.timer_duration_minutes` (default: 60 minutes)

### 3. When does a position become eligible for risk evaluation?
After timer expires AND position is in loss AND not blocked.

### 4. Does pyramid continuation reset the risk timer?
**Yes**:
```python
if is_pyramid:
    position.risk_timer_start = datetime.utcnow()
```

### 5. How is timer state persisted?
In `position_group.risk_timer_start` column (DateTime).

---

## 28. Risk Manual Controls

### 1. How does blocking a position work?
Sets `position.is_blocked = True`. Blocked positions excluded from risk evaluation:
```python
eligible = [p for p in positions if not p.is_blocked]
```

### 2. How does unblocking work?
Sets `position.is_blocked = False`. Can optionally reset timer.

### 3. What does "skip next evaluation" do?
Sets flag to skip one evaluation cycle:
```python
position.skip_next_evaluation = True
```

### 4. How does force-stop affect the queue?
Pauses queue processing. No new signals promoted until resumed.

### 5. How does force-start resume operations?
Clears force-stop flag, resumes normal queue processing.

### 6. What is max realized loss threshold and how does it work?
If cumulative realized loss exceeds threshold, risk engine stops opening new positions:
```python
if total_realized_loss >= max_loss_threshold:
    halt_new_positions()
```

---

## 29. Risk Actions Logging

### 1. How are risk actions recorded (RiskAction model)?
In `backend/app/models/risk_action.py`:
```python
class RiskAction(Base):
    id: UUID
    group_id: UUID
    action_type: RiskActionType
    exit_price: Decimal
    entry_price: Decimal
    pnl_percent: Decimal
    realized_pnl_usd: Decimal
    quantity_closed: Decimal
    duration_seconds: Decimal
    notes: str
    created_at: datetime
```

### 2. What action types exist?
```python
class RiskActionType(str, Enum):
    MANUAL_CLOSE = "manual_close"
    ENGINE_CLOSE = "engine_close"
    TP_HIT = "tp_hit"
    OFFSET_LOSS = "offset_loss"
    MANUAL_BLOCK = "manual_block"
```

### 3. What details are stored per action?
- Position group reference
- Action type
- Entry/exit prices
- PnL (percent and USD)
- Quantity closed
- Duration
- Notes (reason, context)

### 4. How is risk action history queried?
Via `RiskActionRepository`:
```python
await risk_repo.get_by_group_id(position_group_id)
await risk_repo.get_recent_for_user(user_id, limit=50)
```

---

## 30. Telegram Notification System

### 1. How is Telegram integration configured (bot token, channel ID)?
In user settings `telegram_config`:
```python
{
    "enabled": True,
    "bot_token": "123456:ABC...",
    "channel_id": "-1001234567890"
}
```

### 2. What notification types are supported?
- Entry signals
- Exit signals
- DCA fills
- TP hits
- Risk engine actions
- System errors/failures

### 3. How are messages formatted for different events?
In `telegram_broadcaster.py`, dedicated builder methods:
- `_build_entry_message()`
- `_build_exit_message()`
- `_build_dca_fill_message()`
- `_build_tp_hit_message()`
- `_build_risk_action_message()`

---

## 31. Telegram Quiet Hours

### 1. How do quiet hours work?
Messages suppressed during configured time window:
```python
def _is_quiet_hours(self):
    current_hour = datetime.now().hour
    return self.quiet_start <= current_hour < self.quiet_end
```

### 2. What is the urgent-only override?
During quiet hours, only urgent messages (failures, risk actions) are sent:
```python
if self._is_quiet_hours() and not is_urgent:
    return  # Skip non-urgent
```

### 3. How are quiet hours configured (start/end times)?
In telegram config:
```python
{
    "quiet_hours_start": 22,  # 10 PM
    "quiet_hours_end": 7      # 7 AM
}
```

---

## 32. Telegram Message Types

### 1. What message is sent on signal reception?
Entry signal message with symbol, side, price, timeframe.

### 2. What message is sent on order fill?
DCA fill message with layer number, fill price, quantity.

### 3. What message is sent on TP hit?
TP hit message with profit amount, percentage, duration.

### 4. What message is sent on risk engine action?
Risk action message with action type, positions involved, PnL details.

### 5. Can message types be toggled on/off?
**Yes**, in telegram config:
```python
{
    "send_entry_signals": True,
    "send_exit_signals": True,
    "send_dca_fills": False,
    "send_tp_hits": True,
    "send_risk_actions": True
}
```

---

## 33. Dashboard & Analytics

### 1. How is TVL (Total Value Locked) calculated?
In `dashboard.py`, iterates all assets and converts to USDT:
```python
for asset, amount in total_balances.items():
    if asset == "USDT":
        total_tvl += amount
    else:
        price = await get_price(f"{asset}/USDT")
        total_tvl += amount * price
```

### 2. How is free USDT balance fetched?
From exchange `free` balances:
```python
free_balances = balances.get("free", {})
free_usdt = free_balances.get("USDT", 0)
```

### 3. How is unrealized PnL calculated across positions?
For each active position:
```python
current_price = await get_price(symbol)
if side == "long":
    pnl = (current_price - avg_entry) * quantity
else:
    pnl = (avg_entry - current_price) * quantity
```

### 4. How is realized PnL aggregated?
Sum of `realized_pnl_usd` from all closed positions:
```python
realized = await repo.get_total_realized_pnl_only(user_id)
```

### 5. How is win rate calculated?
```python
wins = len([p for p in closed if p.realized_pnl_usd > 0])
win_rate = wins / total_trades * 100
```

### 6. What caching is applied to dashboard data?
Redis caching with TTLs:
- Balance: 5 minutes
- Tickers: 1 minute
- Dashboard summary: 1 minute

---

## 34. Position History & Metrics

### 1. How is position history stored and queried?
Closed positions remain in `position_groups` table with `status=CLOSED`. Queried via:
```python
await repo.get_closed_by_user_all(user_id)
await repo.get_closed_by_user_paginated(user_id, page, limit)
```

### 2. What pagination is applied to history queries?
Offset-based pagination:
```python
query.offset(page * limit).limit(limit)
```

### 3. How is position duration calculated?
```python
duration = position.closed_at - position.created_at
duration_seconds = duration.total_seconds()
```

### 4. What metrics are tracked per closed position?
- Entry/exit prices
- Realized PnL (USD and %)
- Total quantity
- Duration
- Pyramid count
- DCA fills count

---

## 35. Settings Management

### 1. How are user settings structured?
JSON blob in `user.settings` column with sections:
```python
{
    "grid_strategy": {...},
    "risk": {...},
    "telegram_config": {...},
    "security": {...}
}
```

### 2. What settings categories exist?
- `grid_strategy`: DCA config, TP mode, max pyramids
- `risk`: Timer duration, max loss, selection strategy
- `telegram_config`: Bot settings, message toggles
- `security`: Webhook validation, secrets

### 3. How are settings updated via API?
PUT `/settings` with partial update:
```python
update_data = user_update.model_dump(exclude_unset=True)
for field, value in update_data.items():
    setattr(current_user, field, value)
```

### 4. Are settings changes validated before saving?
**Yes**, via Pydantic models (`UserUpdate` schema) with field validators.

---

## 36. API Security & Rate Limiting

### 1. What CORS configuration is applied?
In `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

### 2. What rate limits exist per endpoint?
- Auth endpoints: 3-5/minute
- Settings: 10-30/minute
- Dashboard: 20/minute
- Webhook: 60/minute

### 3. How is rate limiting implemented (SlowAPI)?
Using SlowAPI with Redis backend:
```python
limiter = Limiter(key_func=get_remote_address)

@router.get("/endpoint")
@limiter.limit("20/minute")
async def endpoint(request: Request):
```

### 4. Are sensitive endpoints more restricted?
**Yes**. Auth endpoints have stricter limits (3-5/min vs 20-30/min).

---

## 37. Background Services Architecture

### 1. What background services run on startup?
Three services started in `main.py`:
1. `OrderFillMonitorService` (5s poll)
2. `QueueManagerService` (10s poll)
3. `RiskEngineService` (60s poll)

### 2. How are services started and stopped?
Started via `asyncio.create_task()` in startup event:
```python
@app.on_event("startup")
async def startup():
    asyncio.create_task(order_monitor.start())
```

Stopped via cancellation in shutdown event:
```python
@app.on_event("shutdown")
async def shutdown():
    await order_monitor.stop()
```

### 3. What happens if a background service crashes?
Logged as error. Service has try/except wrapper that logs and continues:
```python
try:
    await self._process_cycle()
except Exception as e:
    logger.error(f"Error in service cycle: {e}")
    # Continue running
```

### 4. How is service health monitored?
Basic health check endpoint `/health` returns service status. No detailed health metrics implemented.

---

## 38. Database & Persistence

### 1. What ORM is used?
**SQLAlchemy** with async support (SQLAlchemy 2.0+).

### 2. Is async database access supported?
**Yes**, using `AsyncSession` and `asyncpg` driver:
```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
```

### 3. How are database migrations handled?
**Alembic** for migrations:
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### 4. What indexes exist for performance?
- Primary key indexes (automatic)
- `user_id` on positions, orders
- `status` on position_groups
- `symbol, timeframe` composite for lookups

### 5. How is connection pooling configured?
In `database.py`:
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)
```

---

## 39. Error Handling & Logging

### 1. How are errors logged throughout the system?
Using Python `logging` module with structured format:
```python
logger = logging.getLogger(__name__)
logger.error(f"Error: {e}", exc_info=True)
```

### 2. What log levels are used?
- `DEBUG`: Detailed tracing
- `INFO`: Normal operations
- `WARNING`: Non-critical issues
- `ERROR`: Failures requiring attention

### 3. How is log rotation configured?
In `logging_config.py`:
```python
RotatingFileHandler(
    filename="app.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
```

### 4. Are logs structured (JSON format)?
**Optional**. JSON formatter available but text format default.

### 5. How can logs be viewed via API?
`/logs` endpoint with pagination and level filter (admin only).

---

## 40. Frontend Architecture

### 1. What frontend framework is used?
**React** with TypeScript.

### 2. What state management is used?
**React Context** for auth state. **React Query** for server state and caching.

### 3. What pages exist in the frontend?
- Dashboard (home)
- Positions (active/history)
- Queue management
- Settings
- Analytics
- Login/Register

### 4. How is authentication handled on frontend?
JWT stored in httpOnly cookie. Axios interceptor handles auth headers and token refresh.

---

## 41. Frontend Features

### 1. Is mobile responsive design implemented?
**Yes**, using Tailwind CSS responsive utilities.

### 2. Is dark mode supported?
**Yes**, theme toggle with dark mode CSS classes.

### 3. Are keyboard shortcuts implemented?
**Basic shortcuts**: Escape to close modals, Enter to submit forms.

### 4. Is pull-to-refresh supported on mobile?
**Yes**, on positions and queue pages.

### 5. How are loading states displayed (skeletons)?
Skeleton components show placeholder content during data fetch.

### 6. How are errors handled (error boundaries)?
React Error Boundary components catch render errors and show fallback UI.

---

## 42. Position Close Scenarios

### 1. How is manual close from UI handled?
API call to `/positions/{id}/close` triggers `execute_handle_exit_signal()` with `exit_reason="manual"`.

### 2. How is TP-triggered close handled?
Order fill monitor detects TP fill, calls close logic with `exit_reason="tp_hit"`.

### 3. How is risk engine forced close handled?
Risk engine calls `execute_handle_exit_signal()` with `exit_reason="risk_offset"`.

### 4. How is exit signal close handled?
Webhook exit signal triggers close with `exit_reason="engine"`.

### 5. What cleanup occurs on position close?
1. Cancel all open orders for group
2. Place market close order
3. Update position status to CLOSED
4. Calculate realized PnL
5. Record risk action
6. Send Telegram notification

---

## 43. Exchange Synchronization

### 1. What does "sync with exchange" do?
Fetches current order states from exchange and updates local database to match.

### 2. How are local and exchange states reconciled?
For each local order:
```python
exchange_order = await connector.get_order(order_id)
if exchange_order.status != local_order.status:
    local_order.status = exchange_order.status
```

### 3. What happens if orders exist on exchange but not locally?
**Not automatically synced**. Manual intervention required.

### 4. What happens if local orders don't exist on exchange?
Marked as `CANCELLED` or `FAILED` locally.

---

## 44. Precision & Validation

### 1. How are exchange precision rules fetched?
Via `load_markets()`:
```python
market = await connector.load_markets()
precision = market[symbol]["precision"]
```

### 2. How is tick size enforced on prices?
```python
tick_size = market["precision"]["price"]
price = Decimal(price).quantize(Decimal(str(tick_size)))
```

### 3. How is step size enforced on quantities?
```python
step_size = market["precision"]["amount"]
quantity = Decimal(quantity).quantize(Decimal(str(step_size)))
```

### 4. What happens if an order violates precision rules?
Order rejected with `InvalidOrderError`. Precision applied before submission to prevent this.

### 5. Is precision validation cached?
**Yes**, market data cached after initial `load_markets()` call.

---

## 45. Multi-User Support

### 1. How are users isolated from each other?
All queries filtered by `user_id`:
```python
query.filter(PositionGroup.user_id == user_id)
```

### 2. Can multiple users trade the same symbol?
**Yes**, each user has independent positions.

### 3. How are user-specific configurations stored?
In `user.settings` JSON column and `user.encrypted_api_keys`.

### 4. Is there admin/superuser functionality?
**Basic admin flag** on user model. Admin-only endpoints check `user.is_admin`.

---

## 46. Testing & Mock Exchange

### 1. Is there a mock exchange connector for testing?
**Yes**, `MockExchangeConnector` in tests directory simulates exchange responses.

### 2. How does testnet mode work?
Sets exchange sandbox mode:
```python
if testnet:
    exchange.set_sandbox_mode(True)
```

### 3. What test coverage exists?
Unit tests for:
- Repositories
- Services
- API endpoints
- DCA calculations

### 4. How are integration tests structured?
Using pytest with async support:
```python
@pytest.mark.asyncio
async def test_position_creation():
    async with get_test_session() as session:
        # Test logic
```

---

## Summary

This document provides comprehensive answers to all 200+ investigation questions based on codebase analysis. Key findings:

1. **Security**: Robust authentication (bcrypt, JWT), encrypted API keys (Fernet), webhook signature validation
2. **Exchange Support**: Binance and Bybit with async CCXT
3. **DCA System**: Configurable layers with gap, weight, and TP per layer
4. **TP Modes**: Four modes (per_leg, aggregate, hybrid, pyramid_aggregate)
5. **Risk Engine**: Timer-based evaluation with offset loss strategy
6. **Queue System**: Priority-based with pyramid continuation bonus
7. **Telegram**: Full notification system with quiet hours and message toggles
8. **Backend**: FastAPI with async SQLAlchemy, 3 background services
9. **Frontend**: React with TypeScript, React Query, dark mode support
