# Execution Engine - Codebase Verification Prompts

Use these prompts to systematically verify if the codebase aligns with the specification. Copy and paste each section to an AI assistant with access to the codebase.

---

## 1. WEBHOOK & SIGNAL RECEPTION

### 1.1 Basic Signal Handling
```
Review the webhook endpoint that receives TradingView signals:
1. Does it validate the `secret` field against a configured webhook secret?
2. Does it parse all required fields from the JSON payload (tv.exchange, tv.symbol, tv.timeframe, tv.action, tv.market_position, etc.)?
3. What happens if a required field is missing or malformed?
4. Is the incoming signal logged before any processing?
5. Show me the exact validation logic and error responses.
```

### 1.2 Signal Authentication
```
How does the system verify that incoming webhooks are legitimate?
1. Is there webhook signature validation implemented?
2. Where is `security.webhook_signature_validation` checked?
3. What response does an unauthenticated request receive?
4. Are failed authentication attempts logged with details?
```

### 1.3 Signal Parsing
```
Trace the code path from webhook receipt to signal object creation:
1. How is the raw JSON transformed into an internal signal object?
2. Are all TradingView placeholders ({{ticker}}, {{interval}}, {{strategy.order.action}}) properly mapped?
3. How is `execution_intent.type` (signal, exit, reduce, reverse) handled differently?
4. Show me the signal parsing/mapping code.
```

---

## 2. POSITION GROUP MANAGEMENT

### 2.1 Position Group Creation
```
When a new signal arrives for a pair+timeframe that has NO existing Position Group:
1. What exact steps occur to create a new Position Group?
2. What data is stored in the Position Group record?
3. How is the "base entry price" determined and stored?
4. Is the Position Group immediately persisted to the database?
5. Show me the Position Group creation code.
```

### 2.2 Position Group Identity
```
How does the system determine Position Group identity?
1. Is a Position Group uniquely identified by pair + timeframe combination?
2. What happens if two signals arrive simultaneously for BTCUSDT 15m?
3. How are race conditions prevented when checking for existing groups?
4. Show me how the system looks up existing Position Groups.
```

### 2.3 Position Group States
```
Review the Position Group state machine:
1. Are all states implemented: Waiting, Live (Unfilled), Partially Filled, Active, Closing, Closed?
2. What triggers each state transition?
3. Can a Position Group ever go backwards in state (e.g., from Active back to Partially Filled)?
4. Where is state tracked and how is it persisted?
5. Show me the state transition logic.
```

---

## 3. PYRAMID LOGIC

### 3.1 Pyramid Detection
```
When a signal arrives for a pair+timeframe that ALREADY has an open Position Group:
1. How does the system detect this is a pyramid (not a new position)?
2. Is this pyramid added to the existing group without consuming a pool slot?
3. What is the maximum number of pyramids allowed (should be 5)?
4. What happens if a 6th pyramid signal arrives?
5. Show me the pyramid detection and handling code.
```

### 3.2 Pyramid Counting
```
How does the system track pyramid count?
1. Where is the pyramid counter stored (in Position Group record)?
2. Is pyramid count incremented atomically?
3. How can I query "how many pyramids does BTCUSDT 1h have"?
4. Does pyramid count affect Risk Engine activation (requires 5 pyramids)?
5. Show me pyramid counting logic.
```

### 3.3 Pyramid DCA Generation
```
When a pyramid is added:
1. Does each pyramid generate its own set of DCA orders?
2. Are DCA gaps calculated from the pyramid's entry price (not the original base entry)?
3. How are multiple DCA sets from multiple pyramids managed together?
4. Show me the DCA generation code for pyramids.
```

---

## 4. DCA (DOLLAR COST AVERAGING) LOGIC

### 4.1 DCA Layer Configuration
```
Review the DCA layer implementation:
1. How are DCA layers configured (price gap, capital weight, take profit)?
2. Is the configuration from `grid_strategy.max_dca_per_pyramid` respected?
3. Can DCA configuration be different per symbol or is it global?
4. Show me where DCA layer parameters are defined and loaded.
```

### 4.2 DCA Order Calculation
```
For a long entry at price $100 with DCA gaps of [0%, -0.5%, -1%, -1.5%, -2%]:
1. Show me the code that calculates DCA order prices.
2. Are prices calculated as: DCA1 = $99.50, DCA2 = $99.00, etc.?
3. How is capital weight applied to determine order size?
4. Is precision validation applied BEFORE order submission?
5. Walk through the exact calculation for one DCA layer.
```

### 4.3 DCA Order Placement
```
How are DCA orders placed on the exchange?
1. Are all DCA orders placed immediately when a signal arrives?
2. Or are they placed one at a time as price moves?
3. What order type is used (limit, market, stop-limit)?
4. How are partially filled DCA orders handled?
5. Show me the DCA order placement code.
```

### 4.4 DCA Fill Tracking
```
How does the system track DCA fills?
1. Is there a webhook/websocket listening for fill events from the exchange?
2. How is the "Filled Legs / Total Legs" count updated?
3. When a DCA fills, is the TP order placed immediately?
4. What happens if a DCA order is partially filled?
5. Show me the fill tracking mechanism.
```

### 4.5 DCA Cancellation
```
When should DCA orders be cancelled?
1. On exit signal - are ALL unfilled DCA orders cancelled?
2. On TP hit (per-leg mode) - is only that leg's order cancelled?
3. If price moves beyond the last DCA level, what happens?
4. Show me the DCA cancellation logic.
```

---

## 5. TAKE-PROFIT LOGIC

### 5.1 TP Mode Implementation
```
Are all three TP modes implemented?
1. Per-Leg TP: Each DCA closes independently based on its own TP
2. Aggregate TP: Entire position closes when avg entry reaches TP
3. Hybrid TP: Both logics run, whichever closes first applies

For each mode, show me:
- Where the mode is configured
- How TP price is calculated
- How the close is executed
```

### 5.2 Per-Leg TP Calculation
```
For Per-Leg TP mode:
1. Is each TP calculated from the ACTUAL FILL PRICE (not original entry)?
2. Example: DCA2 fills at $99.00 with TP of +1.5%. Is TP target $100.485?
3. How is the TP order placed (limit order at target price)?
4. What happens when only one leg hits TP - does only that leg close?
5. Show me the per-leg TP calculation code.
```

### 5.3 Aggregate TP Calculation
```
For Aggregate TP mode:
1. How is the weighted average entry price calculated?
2. When a new DCA fills, is the average recalculated?
3. Is the TP target based on this weighted average?
4. When aggregate TP hits, are ALL open legs closed together?
5. Show me the aggregate TP calculation code.
```

### 5.4 Hybrid TP Logic
```
For Hybrid TP mode:
1. Do both per-leg and aggregate TP systems run simultaneously?
2. What determines "first trigger wins"?
3. If per-leg TP hits first, does it only close that leg or everything?
4. How are the remaining legs handled after a partial close?
5. Show me the hybrid TP coordination logic.
```

### 5.5 TP Order Management
```
How are TP orders managed on the exchange?
1. Are TP orders placed as limit orders or monitored internally?
2. If price hits TP but order doesn't fill, what happens?
3. How is slippage handled (risk.max_slippage_percent)?
4. Show me the TP order placement and monitoring code.
```

---

## 6. EXIT LOGIC

### 6.1 Exit Signal Handling
```
When an exit signal (execution_intent.type = "exit") arrives:
1. What is the exact sequence of operations?
2. Are all unfilled DCA orders cancelled first?
3. Are all open legs market-closed?
4. Is the Position Group marked as Closed?
5. Is the pool slot released immediately?
6. Show me the complete exit signal handler.
```

### 6.2 First Trigger Wins
```
The spec states "First TP or exit signal always wins":
1. How is this implemented?
2. What happens if TP hits at the same moment as exit signal arrives?
3. Is there a lock/mutex to prevent double execution?
4. Show me the "first trigger wins" implementation.
```

### 6.3 Partial Exit
```
What happens during a partial exit (only some legs close)?
1. Does a partial close release the pool slot? (Should NOT)
2. Is the Position Group state updated to reflect partial close?
3. Are remaining DCA orders and TPs still active?
4. Show me how partial exits are handled.
```

---

## 7. PRECISION VALIDATION

### 7.1 Precision Data Fetching
```
How does the system fetch precision rules from exchanges?
1. Where is tick size, step size, min quantity, min notional fetched?
2. Is this data cached? For how long (exchange.precision_refresh_sec)?
3. What happens if the API call to fetch precision fails?
4. Is precision data fetched per-symbol or in bulk?
5. Show me the precision fetching code.
```

### 7.2 Price Precision
```
For price validation (tick size):
1. How is the price rounded to valid tick size?
2. Example: If tick size is 0.10 and calculated price is $99.537, what's the result?
3. Is rounding done up, down, or to nearest?
4. Show me the price precision code.
```

### 7.3 Quantity Precision
```
For quantity validation (step size):
1. How is quantity rounded to valid step size?
2. Example: If step size is 0.001 and calculated qty is 1.23456, what's the result?
3. Is there validation against minimum quantity?
4. Show me the quantity precision code.
```

### 7.4 Minimum Notional
```
For minimum notional validation:
1. Is price * quantity checked against minimum notional?
2. What happens if an order is below minimum notional?
3. Is the order blocked, or is quantity adjusted up?
4. Show me the minimum notional check.
```

### 7.5 Precision Failure Handling
```
What happens if precision metadata is missing or outdated?
1. Is the order held until precision is refreshed?
2. Is there a fallback mode (precision.fallback_rules)?
3. How is this situation logged and alerted?
4. Show me the precision failure handling code.
```

---

## 8. EXECUTION POOL

### 8.1 Pool Slot Tracking
```
How does the system track execution pool usage?
1. Where is the current count of open Position Groups stored?
2. How is execution_pool.max_open_groups enforced?
3. Is the slot count atomic (thread-safe)?
4. Show me the pool slot tracking code.
```

### 8.2 Pool Slot Consumption
```
What consumes a pool slot?
1. Is it ONLY first entry of new pair/timeframe? (Should be YES)
2. Do pyramids consume slots? (Should be NO)
3. Do DCA orders consume slots? (Should be NO)
4. Walk me through a scenario where pool is at 9/10, and two signals arrive.
```

### 8.3 Pool Slot Release
```
When is a pool slot released?
1. Only on FULL Position Group closure? (Should be YES)
2. NOT on partial close? (Should be correct)
3. NOT on risk engine partial close? (Should be correct)
4. Show me the pool slot release code.
```

### 8.4 Pool Full Behavior
```
What happens when the pool is full and a new signal arrives?
1. Is the signal added to waiting queue?
2. Is the signal rejected with an error?
3. Is proper logging in place?
4. Show me the "pool full" handling code.
```

---

## 9. WAITING QUEUE

### 9.1 Queue Entry
```
When a signal is added to the waiting queue:
1. What data is stored with the queued signal?
2. Is timestamp recorded for FIFO fallback?
3. Is the signal validated before queueing (or on dequeue)?
4. Show me the queue entry code.
```

### 9.2 Queue Priority Implementation
```
Is the queue selection priority correctly implemented?
Priority order should be:
1. Same pair + same timeframe (pyramid continuation) - AUTO PRIORITY
2. Deepest current loss percentage
3. Highest replacement count
4. FIFO (oldest first)

Show me the priority sorting/selection code and verify each rule.
```

### 9.3 Pyramid Continuation Priority
```
For Priority 1 (pyramid continuation):
1. If BTCUSDT 1h has an active group, and a new BTCUSDT 1h signal is queued...
2. Does it get auto-promoted regardless of pool status?
3. Does it bypass the max position limit?
4. Show me this specific logic.
```

### 9.4 Loss Percentage Priority
```
For Priority 2 (deepest loss):
1. How is "current loss percentage" calculated for a queued signal?
2. Is this based on current market price vs entry price in the signal?
3. Is this recalculated dynamically or fixed at queue time?
4. Show me this calculation.
```

### 9.5 Replacement Count Priority
```
For Priority 3 (replacement count):
1. How is replacement count tracked?
2. When does replacement occur (new signal for same pair+TF while queued)?
3. Does replacement update the entry price to the new signal's price?
4. Is the old signal discarded?
5. Show me the replacement logic.
```

### 9.6 Queue Promotion
```
When a pool slot becomes free:
1. What triggers queue evaluation?
2. How is the highest priority signal selected?
3. Is the signal re-validated before execution?
4. Show me the queue promotion code.
```

### 9.7 Exit While Queued
```
What happens if an exit signal arrives for a queued entry?
1. Is the queued entry deleted/cancelled?
2. Is this logged appropriately?
3. Show me this edge case handling.
```

---

## 10. RISK ENGINE

### 10.1 Activation Conditions
```
The Risk Engine should only activate when ALL conditions are true:
1. All 5 pyramids received - is this checked?
2. Post-full waiting time passed - is the timer implemented?
3. Loss percent below threshold - is this compared correctly?
4. (Optional) Trade age threshold met - is this configurable?

Show me where each condition is checked.
```

### 10.2 Timer Implementation
```
Review the Risk Engine timer:
1. Timer should NOT start at first entry. Is this correct?
2. What are the timer start modes? (after_5_pyramids, after_all_dca_submitted, after_all_dca_filled)
3. Is risk_engine.timer_start_condition respected?
4. Does timer reset on replacement pyramid (if configured)?
5. Show me the timer implementation.
```

### 10.3 Loser Selection (by Percent)
```
How does the Risk Engine select losing trades?
1. Are losers ranked by LOSS PERCENT (not dollar amount)?
2. If tied on percent, is highest dollar loss selected?
3. If still tied, is oldest trade selected?
4. Show me the loser selection/ranking code.
```

### 10.4 Offset Calculation (in USD)
```
How is the offset amount calculated?
1. Is required_usd = absolute unrealized loss of selected loser?
2. Are winners ranked by profit in USD?
3. Is up to max_winners_to_combine (3) winners used?
4. Is only the portion needed to cover loss closed?
5. Show me the offset calculation code.
```

### 10.5 Partial Close Execution
```
When the Risk Engine closes partial positions:
1. How is the partial close executed on the exchange?
2. Does partial close release pool slot? (Should be NO)
3. Is the remaining position structure preserved?
4. Are related DCA and TP orders adjusted?
5. Show me the partial close execution code.
```

### 10.6 Risk Engine Evaluation Trigger
```
When does the Risk Engine evaluate?
1. On fill events (risk_engine.evaluate_on_fill)?
2. On interval (risk_engine.evaluate_interval_sec)?
3. Both?
4. Show me what triggers risk evaluation.
```

---

## 11. EDGE CASES

### 11.1 Duplicate Entry Signal
```
What happens if a duplicate entry signal arrives?
"Duplicate" = same pair + timeframe + same direction, while position already open

1. Is it ignored?
2. Or treated as pyramid?
3. Is waiting_rule.queue_replace_same_symbol relevant here?
4. Show me duplicate detection logic.
```

### 11.2 Opposite Side Signal
```
What happens if signal arrives for opposite side?
Example: BTCUSDT 1h is LONG, and a SHORT signal arrives for BTCUSDT 1h

1. Is it queued until current side closes?
2. Is it rejected?
3. Does it trigger a close of current position?
4. Show me this handling.
```

### 11.3 Price Beyond Last DCA
```
What happens if price moves beyond the last DCA level?
Example: Last DCA at -2%, but price drops to -5%

1. Does the last DCA remain pending?
2. Or is it cancelled per config?
3. Is there a config option for this behavior?
4. Show me this logic.
```

### 11.4 Precision Fetch Failure
```
What happens if precision fetch fails mid-operation?
1. Is the order paused until metadata refreshed?
2. Is there a retry mechanism?
3. Is this logged as an error/warning?
4. Show me precision failure recovery.
```

### 11.5 Simultaneous Signals
```
What happens if multiple signals arrive at the exact same moment?
1. Is there a queue/lock to process sequentially?
2. Can race conditions cause duplicate Position Groups?
3. Show me concurrency handling for signals.
```

### 11.6 Exchange API Failure
```
What happens if exchange API fails during order placement?
1. Is there retry logic?
2. Is the signal re-queued?
3. How is this failure logged and alerted?
4. Show me API failure handling.
```

### 11.7 Partial Fill Edge Case
```
If a DCA order is partially filled, then an exit signal arrives:
1. Is the partial fill position closed?
2. Is the unfilled portion cancelled?
3. How is this handled differently from a full fill?
4. Show me partial fill + exit handling.
```

---

## 12. DATABASE & PERSISTENCE

### 12.1 What Is Persisted
```
What data is stored in PostgreSQL?
1. Closed trade history?
2. Performance stats?
3. Live position data?
4. Configuration?
5. List the database tables and their purposes.
```

### 12.2 Live Data Handling
```
How is live data managed?
1. Is live data kept in memory?
2. When is it synced to database?
3. What happens on engine shutdown - is data persisted?
4. What happens on engine startup - is data restored?
5. Show me the data persistence strategy.
```

### 12.3 Audit Trail
```
Is there a complete audit trail?
1. Are all orders logged with timestamps?
2. Are all risk actions logged?
3. Are all state changes logged?
4. Can I reconstruct a trade's history from logs?
5. Show me audit logging implementation.
```

---

## 13. CONFIGURATION

### 13.1 Config Loading
```
IMPLEMENTATION: Multi-tenant database approach (not single JSON file)

Configuration Sources:
1. Environment Variables (.env file) - Infrastructure settings:
   - DATABASE_URL, SECRET_KEY, ENCRYPTION_KEY, CORS_ORIGINS, ENVIRONMENT, LOG_LEVEL
   - Loaded via backend/app/core/config.py with fail-fast validation
   - Missing required vars = application fails to start with clear error

2. Database JSON Columns (users table) - Per-user settings:
   - risk_config: RiskEngineConfig as JSON (all risk engine parameters)
   - telegram_config: Telegram broadcasting settings
   - encrypted_api_keys: Exchange API credentials per exchange

3. DCA Configurations - Separate table (dca_configurations):
   - Per user/pair/timeframe/exchange combination
   - Unique constraint on (user_id, pair, timeframe, exchange)

Validation:
- Environment: Pydantic Settings with ValueError on missing required fields
- User configs: RiskEngineConfig.model_validate() with fallback to defaults
- Invalid user config = uses default RiskEngineConfig(), does not crash
```

### 13.2 Config Hot Reload
```
IMPLEMENTATION: Implicit hot reload via fresh database reads

Hot Reload (Immediate Effect):
- All user-specific configs (risk_config, telegram_config, DCA configs, API keys)
- Configs loaded from DB on each service instantiation
- No caching = changes via API are immediately effective
- No explicit "Apply & Restart" button needed

Full Restart Required:
- Environment variables (DATABASE_URL, SECRET_KEY, CORS_ORIGINS, etc.)
- These are loaded once at application startup

Mechanism:
- RiskEngineService loads config from user.risk_config on each instantiation
- See: backend/app/api/risk.py:45-47
- No explicit reload endpoint - database is source of truth
```

### 13.3 Config UI Sync
```
IMPLEMENTATION: API-based sync, no real-time push

UI -> Database:
- Frontend calls PUT /settings with updated config
- configStore.updateSettings() -> api.put('/settings')
- Backend updates users table JSON columns
- Changes persisted immediately

Database -> UI:
- UI fetches from authStore.user on page load
- Manual DB edits require page refresh or re-login to reflect
- No WebSocket/polling for config change notifications

Conflict Resolution:
- Last write wins (no optimistic locking)
- No version control on config updates
- Concurrent edits overwrite each other
```

---

## 14. API & FRONTEND

### 14.1 FastAPI Endpoints
```
List all FastAPI endpoints and their purposes:
1. Webhook receiver endpoint
2. Position/group query endpoints
3. Queue management endpoints
4. Risk engine control endpoints
5. Config management endpoints
6. Logs/alerts endpoints
Show me the route definitions.
```

### 14.2 WebSocket/Real-time Updates
```
How does the React frontend receive real-time updates?
1. Is WebSocket used?
2. Is polling used? At what interval (UI.realtime_update_ms)?
3. What data is pushed in real-time?
4. Show me the real-time update mechanism.
```

### 14.3 Authentication
```
How is the web interface secured?
1. Is there login/authentication?
2. Are API endpoints protected?
3. Is there a readonly mode for operators?
4. Show me the authentication implementation.
```

---

## 15. EXCHANGE INTEGRATION

### 15.1 Multi-Exchange Support
```
Is multi-exchange support implemented?
1. How is exchange.name used to route to correct adapter?
2. Are Binance, Bybit, OKX, KuCoin, MEXC, Gate.io supported?
3. Is there a common interface/adapter pattern?
4. Show me the exchange abstraction layer.
```

### 15.2 Testnet Support
```
Is testnet mode implemented?
1. How does exchange.testnet toggle between live and test?
2. Are testnet API endpoints correctly used?
3. Show me testnet configuration handling.
```

### 15.3 Rate Limiting
```
How is API rate limiting handled?
1. Is there rate limit tracking per exchange?
2. What happens when rate limit is hit?
3. Is this logged and displayed in UI?
4. Show me rate limiting implementation.
```

---

## 16. SECURITY

### 16.1 API Key Storage
```
How are API keys stored?
1. Are keys encrypted at rest?
2. Is security.store_secrets_encrypted respected?
3. What encryption method is used?
4. Are keys ever logged or visible in plain text?
5. Show me the secret storage implementation.
```

### 16.2 API Key Display
```
How are API keys displayed in UI?
1. Are they masked (****A4B19K***)?
2. Is there a way to reveal them?
3. Show me the UI masking code.
```

---

## 17. LOGGING

### 17.1 Log Categories
```
Are all log categories implemented?
- Engine Execution Logs
- Signal Logs
- Precision Validation Logs
- Order Logs
- Risk Engine Logs
- Error & Stack Traces

Show me examples of each log type.
```

### 17.2 Log Rotation
```
Is log rotation implemented?
1. Is logging.rotate_daily respected?
2. Is logging.keep_days enforced?
3. How are old logs pruned?
4. Show me log rotation configuration.
```

### 17.3 Log Export
```
Can logs be exported?
1. To CSV?
2. To JSON?
3. Is there a UI button for export?
4. Show me log export functionality.
```

---

## 18. QUICK VERIFICATION QUESTIONS

Use these for rapid spot-checks:

```
1. What happens if I send the exact same webhook twice in 1 second?

2. If pool is 10/10 full and signal arrives for existing BTCUSDT 1h group, what happens?

3. If DCA2 fills at $98.50 with 1.5% TP, what is the exact TP price calculated?

4. Show me the code path from webhook arrival to first order placed on exchange.

5. If Risk Engine closes 50% of a winning position to offset a loss, does pool slot change?

6. What is the exact SQL query to get all closed trades for BTCUSDT in the last 7 days?

7. If I change max_open_groups from 10 to 15 in UI, does it take effect immediately?

8. How many API calls to Binance does one new Position Group generate?

9. What happens if Binance returns "insufficient balance" on a DCA order?

10. If the server crashes mid-trade, what state is preserved on restart?
```

---

## HOW TO USE THESE PROMPTS

1. **Start with Section 1-2** to verify basic signal and position handling
2. **Move to Section 4-5** to verify core DCA and TP logic
3. **Section 9** is critical - queue priority is complex and error-prone
4. **Section 10** for Risk Engine verification
5. **Section 11** for edge cases that often have bugs
6. **Section 18** for quick sanity checks

For each prompt:
- Ask the AI to show actual code, not just explain
- Verify the code matches the spec requirements
- Note any deviations for discussion with developers