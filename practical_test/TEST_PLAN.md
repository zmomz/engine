## User CURRENT Configuration
Target User:
{
    "username": "maaz",
    "id": "e7d6ae10-2a7d-4383-90d3-461c986e1e71"
    "webhook_secret":"1b6d3edada59826e786088a2161d70b6"
    "configured_exchanges": [
      "bybit",
      "binance"
    ],
    "risk_config": {
      "max_open_positions_global": 3,
      "max_open_positions_per_symbol": 1,
      "max_total_exposure_usd": "1000",
      "max_daily_loss_usd": "500",
      "loss_threshold_percent": "-3",
      "timer_start_condition": "after_all_dca_filled",
      "post_full_wait_minutes": 2,
      "max_winners_to_combine": 3,
      "use_trade_age_filter": false,
      "age_threshold_minutes": 120,
      "require_full_pyramids": true,
      "reset_timer_on_replacement": false,
      "partial_close_enabled": true,
      "min_close_notional": "10"
    },
    "dca_grid_config": {
      "levels": [
        {
          "gap_percent": 0,
          "weight_percent": 20,
          "tp_percent": 1
        },
        {
          "gap_percent": -0.5,
          "weight_percent": 30,
          "tp_percent": 1
        },
        {
          "gap_percent": -1,
          "weight_percent": 50,
          "tp_percent": 2
        }
      ],
      }
      "tp_mode": "per_leg",
      "tp_aggregate_percent": 0
}

current prices use it as entry prices:
{
    "BTCUSDT": 95992.3,
    "ETHUSDT": 3394.0,
    "SOLUSDT": 125.97,
    "DOTUSDT": 2.075,
    "XRPUSDT": 1.874,
    "TRXUSDT": 0.2468,
    "DOGEUSDT": 0.195,
    "ADAUSDT": 0.387,
    "GALAUSDT": 0.0066
}

# Trading Engine Testing Plan - Multi-Exchange Workflow

## Overview
Comprehensive testing strategy for validating the automated trading execution engine across Binance Testnet and Bybit Testnet, with systematic monitoring of logs, UI, and exchange APIs.

---

## Phase 1: Single Exchange - Single Position Flow

### Test 1.1: Basic Entry Signal (Binance)
**Objective:** Verify signal reception, parsing, and first position creation

```bash
python3 scripts/simulate_webhook.py \
  --user-id <BINANCE_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BINANCE \
  --symbol BTCUSDT \
  --timeframe 60 \
  --action buy \
  --side long \
  --type signal \
  --entry-price 95992.3 \
  --close-price 95992.3 \
  --order-size 0.001
```

**Validation Checklist:**
- [ ] Backend logs show webhook received
- [ ] Signal parsed successfully (check logs for TV data extraction)
- [ ] Position Group created in database (verify with export script)
- [ ] Precision validation fetched (tick size, step size, min notional)
- [ ] Base entry order submitted to Binance Testnet
- [ ] UI Dashboard shows:
  - Active Positions: 1/3
  - New Position Group row (BTCUSDT 1h)
  - Status: "Waiting" or "Partially Filled"
  - Pyramid: 1/5
- [ ] Binance Testnet UI shows open order
- [ ] Database check:
  ```bash
  python scripts/export_data.py --type positions --format json
  # Verify position_group created with status 'open'
  ```

**Expected Issues to Fix:**
- Precision rounding errors
- API credential issues
- Webhook authentication failures
- Database connection problems

---

### Test 1.2: DCA Layer Triggering (Binance)
**Objective:** Validate DCA order placement after base entry fills

**Setup:** Manually fill base entry on Binance Testnet (if using market orders, it should auto-fill)

**Validation Checklist:**
- [ ] Backend logs show fill detection
- [ ] DCA orders (DCA1, DCA2, DCA3) placed automatically
- [ ] Each DCA has correct:
  - Price gap (-0.5%, -1%, -1.5% from base entry)
  - Quantity (20% of total capital per leg)
  - Take-profit target calculated
- [ ] UI shows:
  - DCA filled status: 1/3 or 2/3 (depending on price)
  - Individual DCA legs in expandable view
- [ ] Database shows DCA orders with `pending` status
- [ ] Binance Testnet shows limit orders at DCA price levels

**Trigger DCA Fill:**
- Manually adjust price on Binance Testnet or wait for market movement
- Alternatively, cancel and replace DCA orders at current market price for instant fill

**Post-Fill Validation:**
- [ ] Weighted average entry price recalculated
- [ ] Take-profit price adjusted
- [ ] DCA status updated to `filled`
- [ ] Logs show individual DCA fill events

---

### Test 1.3: Pyramid Signal (Binance)
**Objective:** Test pyramid continuation (bypasses pool limit)

```bash
python scripts/simulate_webhook.py \
  --user-id <BINANCE_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BINANCE \
  --symbol BTCUSDT \
  --timeframe 60 \
  --action buy \
  --side long \
  --type signal \
  --entry-price 95992.3 \
  --order-size 0.001
```

**Validation Checklist:**
- [ ] Signal recognized as pyramid (same pair + timeframe)
- [ ] Does NOT count toward pool limit (still 1/3 used)
- [ ] New pyramid created (Pyramid 2/5)
- [ ] Separate DCA grid spawned for Pyramid 2
- [ ] UI updates:
  - Pyramid count: 2/5
  - Total DCA increases (now 6 legs total)
- [ ] Database shows second pyramid entry
- [ ] Logs show "Pyramid continuation detected"

**Repeat 3 more times** to reach 5/5 pyramids:
- Pyramid 3: entry-price 52000
- Pyramid 4: entry-price 53000
- Pyramid 5: entry-price 54000

**Post-5-Pyramid Validation:**
- [ ] Pyramid status: 5/5 (full)
- [ ] Post-full timer starts (verify in logs)
- [ ] Risk engine activation conditions partially met
- [ ] No more pyramids accepted for this group

---

### Test 1.4: Take-Profit Closure (Leg Mode)
**Objective:** Validate individual DCA leg closure

**Setup:** Adjust market price or DCA TP targets to trigger closure

**Trigger Method:**
1. **Manual:** Sell DCA quantity on Binance Testnet at TP price
2. **Automatic:** Wait for market to hit TP target

**Validation Checklist:**
- [ ] TP target hit detected (logs show price comparison)
- [ ] Market sell order placed for that DCA leg only
- [ ] DCA leg status changes to `closed`
- [ ] Realized PnL calculated and updated
- [ ] UI shows:
  - DCA filled status decreases (e.g., 14/15)
  - Realized PnL increases
  - Unrealized PnL decreases
- [ ] Pool slot still NOT released (partial closure)
- [ ] Other DCA legs remain active

**Test Multiple Legs:**
- Close 2-3 more DCA legs individually
- Verify each closure independent
- Check weighted average entry remains correct

---

### Test 1.5: Full Exit Signal (Binance)
**Objective:** Close entire Position Group via exit signal

```bash
python scripts/simulate_webhook.py \
  --user-id <BINANCE_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BINANCE \
  --symbol BTCUSDT \
  --timeframe 60 \
  --action sell \
  --type exit
```

**Validation Checklist:**
- [ ] Exit signal recognized
- [ ] All open DCA orders cancelled
- [ ] Market sell orders placed for all remaining positions
- [ ] Position Group status changes to `closed`
- [ ] Final realized PnL calculated
- [ ] Pool slot released (Active Positions: 0/3)
- [ ] UI updates:
  - Position removed from active list
  - Closed position appears in history
  - Total PnL updated
- [ ] Database shows `closed_at` timestamp
- [ ] Binance Testnet shows all orders closed/cancelled

---

## Phase 2: Multi-Exchange Parallel Operations

### Test 2.1: Simultaneous Positions (Binance + Bybit)
**Objective:** Run positions on both exchanges concurrently

**Step 1:** Start Binance Position
```bash
python scripts/simulate_webhook.py \
  --user-id <BINANCE_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BINANCE \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 3000
```

**Step 2:** Start Bybit Position
```bash
python scripts/simulate_webhook.py \
  --user-id <BYBIT_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BYBIT \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 100
```

**Validation Checklist:**
- [ ] Both positions created independently
- [ ] Pool usage: 2/3
- [ ] Precision validation fetched per exchange
- [ ] Each exchange shows respective orders
- [ ] UI shows both Position Groups
- [ ] No cross-contamination (Binance orders don't go to Bybit)
- [ ] Logs clearly separate exchange operations

**Test Exchange-Specific Features:**
- [ ] Binance: Test BUSD pairs if available
- [ ] Bybit: Test inverse perpetuals (if supported)
- [ ] Verify API rate limits not exceeded

---

### Test 2.2: Pool Limit & Waiting Queue
**Objective:** Fill pool and test queueing logic

**Step 1:** Fill Pool (already have 2/3)
```bash
python scripts/simulate_webhook.py \
  --user-id <BINANCE_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BINANCE \
  --symbol XRPUSDT \
  --timeframe 15 \
  --side long \
  --type signal
```

**Pool Status:** 3/3 (full)

**Step 2:** Send Signal to Queue
```bash
python scripts/simulate_webhook.py \
  --user-id <BYBIT_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BYBIT \
  --symbol DOTUSDT \
  --timeframe 60 \
  --side long \
  --type signal
```

**Validation Checklist:**
- [ ] Signal queued (not executed)
- [ ] UI shows:
  - Waiting Queue: 1 signal
  - Queue details: DOTUSDT 60m, Priority rank
- [ ] Logs show "Pool full, signal queued"
- [ ] Database has queue entry
- [ ] No order sent to Bybit yet

**Step 3:** Test Queue Priority
Send another signal with higher loss % (simulate using existing data):
```bash
# This should rank higher if current positions have losses
python scripts/simulate_webhook.py \
  --user-id <BYBIT_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BYBIT \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --type signal
```

**Validation:**
- [ ] Queue now has 2 signals
- [ ] Priority order correct (check UI ranking)
- [ ] Logs show priority calculation

**Step 4:** Release Pool Slot
Close one active position (use exit signal from Test 1.5)

**Validation:**
- [ ] Queue automatically promotes top signal
- [ ] DOTUSDT or TRXUSDT (higher priority) starts execution
- [ ] Pool usage: 3/3 again
- [ ] Queue count: 1 remaining

---

### Test 2.3: Queue Replacement Logic
**Objective:** Test same-symbol queue replacement

**Setup:** Pool still full, queue has 1 signal (TRXUSDT)

**Send Duplicate Signal:**
```bash
python scripts/simulate_webhook.py \
  --user-id <BYBIT_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BYBIT \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 110  # Different price
```

**Validation Checklist:**
- [ ] Old TRXUSDT queue entry replaced
- [ ] Replacement count incremented
- [ ] New entry price stored
- [ ] Queue count remains 1 (not 2)
- [ ] Logs show "Queue entry replaced"
- [ ] UI shows replacement count badge

---

## Phase 3: Risk Engine Testing

### Test 3.1: Risk Engine Activation
**Objective:** Trigger risk engine to use winners to offset losers

**Setup Requirements:**
- At least 1 position with 5/5 pyramids
- Post-full timer expired
- Position in loss (> 3%)
- At least 1 winning position available

**Simulation Steps:**

**Step 1:** Create Winning Position
```bash
python scripts/simulate_webhook.py \
  --user-id <BINANCE_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BINANCE \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 0.08
```

**Manually adjust:** Make this position profitable (+10% unrealized PnL)
- Adjust TP targets or simulate price increase

**Step 2:** Create Losing Position (5 Pyramids)
```bash
# Send 5 signals for same symbol to create full pyramid
for i in {1..5}; do
  python scripts/simulate_webhook.py \
    --user-id <BINANCE_USER_UUID> \
    --secret <WEBHOOK_SECRET> \
    --exchange BINANCE \
    --symbol XRPUSDT \
    --timeframe 60 \
    --side long \
    --type signal \
    --entry-price $(echo "0.12 + $i * 0.001" | bc)
done
```

**Step 3:** Induce Loss
- Manually adjust market or DCA prices to create -5% loss
- Wait for post-full timer (2 minutes in test config)

**Step 4:** Trigger Risk Engine
Option A: Automatic (wait for scheduler)
Option B: Manual trigger via UI button (if implemented)

**Validation Checklist:**
- [ ] Risk engine detects conditions met
- [ ] Logs show:
  - "Risk engine activated"
  - Loser identified: XRPUSDT (-5%)
  - Winner selected: DOGEUSDT (+10%)
  - Partial close calculation (USD amounts)
- [ ] Partial close order executed on DOGEUSDT
- [ ] Partial close order executed on XRPUSDT
- [ ] Realized PnL updated for both
- [ ] Unrealized PnL reduced
- [ ] Pool slots NOT released (partial closure)
- [ ] UI shows risk engine action in logs panel

**Edge Case Test:**
- [ ] Risk engine with insufficient winners (should skip)
- [ ] Multiple losers ranked correctly
- [ ] 3-winner combination logic

---

## Phase 4: Edge Cases & Error Handling

### Test 4.1: Precision Validation Failures
**Objective:** Handle missing or invalid exchange metadata

**Test Cases:**

**A. Missing Tick Size**
- Mock API response to omit tick size
- Send signal
- **Expect:** Order paused, error logged, manual fetch required

**B. Quantity Below Minimum**
- Send signal with very small order size (0.00001 BTC)
- **Expect:** Order blocked, log shows "Below minimum notional"

**C. Invalid Decimals**
- Force invalid decimal precision in code (if possible)
- **Expect:** Order rejected, precision correction applied

**Validation:**
- [ ] All precision errors logged clearly
- [ ] UI shows warning/error alert
- [ ] System doesn't crash
- [ ] Orders retry after metadata refresh

---

### Test 4.2: API Failures & Retries
**Objective:** Handle exchange API downtime

**Test Methods:**
1. Disconnect internet briefly
2. Use invalid API keys temporarily
3. Rate limit trigger (send 100 signals rapidly)

**Validation:**
- [ ] Connection errors logged
- [ ] Orders queue for retry
- [ ] UI shows "Connection Lost" warning
- [ ] System recovers after reconnection
- [ ] No duplicate orders sent

---

### Test 4.3: Duplicate Signal Handling
**Objective:** Prevent duplicate position creation

**Test:**
```bash
# Send same signal twice quickly
python scripts/simulate_webhook.py \
  --user-id <BINANCE_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BINANCE \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --type signal &

python scripts/simulate_webhook.py \
  --user-id <BINANCE_USER_UUID> \
  --secret <WEBHOOK_SECRET> \
  --exchange BINANCE \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --type signal &
```

**Validation:**
- [ ] Only 1 position created
- [ ] Second signal ignored or flagged as duplicate
- [ ] Logs show "Duplicate signal rejected"
- [ ] No double orders on exchange

---

### Test 4.4: Exit While Queued
**Objective:** Handle exit signal for queued entry

**Setup:**
1. Fill pool (3/3)
2. Queue entry signal for TRXUSDT
3. Send exit signal for TRXUSDT before it executes

**Validation:**
- [ ] Queued entry removed
- [ ] Exit signal processed (no-op since position doesn't exist)
- [ ] Queue count decreases
- [ ] Logs show "Exit for queued signal, removing from queue"

---

### Test 4.5: Opposite Side Signal
**Objective:** Handle conflicting directions

**Setup:**
1. Active long position on BTCUSDT
2. Send short signal for BTCUSDT same timeframe

**Validation:**
- [ ] Short signal queued or rejected
- [ ] Long position remains active
- [ ] Logs show "Opposite side signal, queuing until closure"
- [ ] After long closes, short can execute

---

## Phase 5: UI & Dashboard Validation

### Test 5.1: Real-Time Updates
**Checklist:**
- [ ] Position status updates without refresh
- [ ] PnL updates live (polling or WebSocket)
- [ ] Queue changes reflected immediately
- [ ] Logs stream in real-time
- [ ] Error alerts appear instantly

### Test 5.2: Performance Metrics
**Validation:**
- [ ] Equity curve renders correctly
- [ ] Win/loss stats accurate
- [ ] Trade distribution histogram populated
- [ ] Max drawdown calculated correctly
- [ ] Export functions work (CSV, PNG)

### Test 5.3: Settings Panel
**Test:**
1. Change `max_open_groups` from 3 to 5
2. Apply changes
3. Verify config file updated
4. Test new limit by opening 5 positions

**Validation:**
- [ ] Config saves correctly
- [ ] Engine respects new limits
- [ ] UI preview shows impact
- [ ] Backup/restore functions work

---

## Phase 6: Data Integrity & Persistence

### Test 6.1: Database Consistency
**After all tests, run:**
```bash
python scripts/export_data.py --type positions --format json --output positions_final.json
python scripts/export_data.py --type users --format json --output users_final.json
```

**Validation:**
- [ ] All Position Groups have valid state
- [ ] No orphaned DCA orders
- [ ] No orphaned pyramids
- [ ] Timestamps consistent (created < updated < closed)
- [ ] PnL calculations match manually verified totals

### Test 6.2: Data Cleanup
**Test:**
```bash
python scripts/clean_positions_for_user.py
# (Will clean 'zmomz' user as per script)
```

**Validation:**
- [ ] User positions deleted
- [ ] Associated DCA orders deleted
- [ ] Associated pyramids deleted
- [ ] Database constraints maintained
- [ ] No foreign key errors

---

## Phase 7: Stress Testing

### Test 7.1: Rapid Signal Burst
**Test:**
```bash
# Send 50 signals in 10 seconds
for i in {1..50}; do
  python scripts/simulate_webhook.py \
    --user-id <BINANCE_USER_UUID> \
    --secret <WEBHOOK_SECRET> \
    --exchange BINANCE \
    --symbol BTC${i}USDT \
    --timeframe 60 \
    --side long \
    --type signal &
done
```

**Validation:**
- [ ] System handles burst without crashing
- [ ] Queue processes signals in order
- [ ] Rate limits respected
- [ ] Memory usage stable
- [ ] No lost signals

### Test 7.2: Long-Running Stability
**Test:** Leave system running for 24 hours with periodic signals

**Validation:**
- [ ] No memory leaks
- [ ] Database connections stable
- [ ] Log rotation works
- [ ] UI remains responsive
- [ ] All positions tracked correctly

---

## Issue Tracking Template

For each test, document issues:

```markdown
### Issue #[NUMBER]: [Brief Description]
**Test:** Phase X.Y - [Test Name]
**Severity:** Critical / High / Medium / Low
**Exchange:** Binance / Bybit / Both

**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Behavior:**


**Actual Behavior:**


**Logs:**
```
[Paste relevant logs]
```

**Screenshots:**
[Attach UI screenshots]

**Fix Applied:**
- [ ] Code changes
- [ ] Config changes
- [ ] Documentation update

**Verification:**
- [ ] Re-tested successfully
- [ ] No regressions
```

---

## Success Criteria

### Phase Completion Checklist
- [ ] **Phase 1:** Single position lifecycle works flawlessly
- [ ] **Phase 2:** Multi-exchange operations isolated and correct
- [ ] **Phase 3:** Risk engine executes as designed
- [ ] **Phase 4:** All edge cases handled gracefully
- [ ] **Phase 5:** UI reflects reality accurately
- [ ] **Phase 6:** Data integrity maintained
- [ ] **Phase 7:** System stable under stress

### Final Validation
- [ ] Zero unhandled exceptions in 100 test signals
- [ ] 100% precision validation pass rate
- [ ] All DCA/TP calculations verified manually
- [ ] Both exchanges execute orders successfully
- [ ] UI matches database state at all times
- [ ] Logs provide clear audit trail
- [ ] Documentation reflects actual behavior

---

## Rollout Plan

### Post-Testing Steps
1. **Code Freeze:** Fix all critical and high-severity issues
2. **Regression Testing:** Re-run full test suite
3. **Performance Optimization:** Address any bottlenecks
4. **Documentation:** Update all guides with test findings
5. **Deployment:** Package for Windows + macOS
6. **Beta Testing:** Release to controlled user group
7. **Monitoring:** Establish production alerting
8. **Full Release:** Deploy to all users

---

## Additional Scripts Needed

Based on this plan, you may need these additional utility scripts:

### `create_test_user.py`
Creates test users with API credentials

### `simulate_price_movement.py`
Mocks exchange price changes for testing TP/DCA

### `verify_database_state.py`
Audits database for consistency issues

### `bulk_webhook_test.py`
Sends multiple signals from JSON configuration

### `exchange_health_check.py`
Validates API connectivity and credentials

### `reset_test_environment.py`
Cleans all test data and resets to initial state

---

## Notes

- **Testnet Funds:** Ensure both testnet accounts have sufficient balance
- **API Rate Limits:** Monitor closely, especially during stress tests
- **Logging Level:** Set to DEBUG during initial tests, INFO for later phases
- **Backup Frequently:** Export database and config after each phase
- **Parallel Testing:** Run Binance and Bybit tests simultaneously when possible
- **Documentation:** Update README with any discovered behavioral nuances

---

**Good luck with testing! This plan should help you systematically identify and fix issues before production deployment.**