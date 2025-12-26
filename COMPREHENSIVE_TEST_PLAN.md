# 🧪 COMPREHENSIVE PRACTICAL TEST PLAN
## Trading Execution Engine - Full System Validation

**Date:** Ready for execution
**Duration:** ~4-5 hours
**Environment:** Bybit and Binance Testnet
**Prerequisites:** Clean database, funded testnet accounts

**Testing Approach:** 100% Practical - All tests executed via scripts with exchange and database verification
**No Manual Testing:** All tests are command-line based and verified through scripts, exchange state, and database queries

**User Credentials:**
- USER_ID: `f937c6cb-f9f9-4d25-be19-db9bf596d7e1`
- WEBHOOK_SECRET: `ecd78c38d5ec54b4cd892735d0423671`

**Configured DCA Pairs (ONLY use these pairs in tests):**
- **Binance:** BTC/USDT, ETH/USDT, XRP/USDT, ADA/USDT, TRX/USDT, LINK/USDT
- **Bybit:** SOL/USDT, DOGE/USDT, DOT/USDT, MATIC/USDT

**IMPORTANT - Real Price Testing:**
To test order fills, TP execution, market orders, and risk engine behavior, you MUST use current live prices from the exchanges. See "Fetch Live Prices" section in pre-test setup.

Note: All test commands below use only these configured pairs. Using unconfigured pairs will result in errors.

---

## 📋 ALLOWED SCRIPTS FOR TESTING

**The following scripts are available for comprehensive testing:**

### Core Testing Scripts

```bash
# 1. Clean positions from database
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# 2. Clean positions from exchanges (Binance & Bybit)
docker compose exec app python3 scripts/clean_positions_in_exchanges.py

# 3. Check exchange positions, open orders, filled orders, closed orders and balances
docker compose exec app python3 scripts/verify_exchange_positions.py

# 4. Check queue (list queued signals)
docker compose exec app python3 scripts/list_queue.py

# 5. Simulate webhook (buy order) - Use only configured pairs from DCA configurations
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 136.82 \
  --order-size 0.4
```

### Queue Priority Testing Scripts (NEW)

```bash
# 6. Comprehensive system monitoring (pool, positions, queue, risk, TP modes)
docker compose exec app python3 scripts/monitor_all_tests.py

# 7. Queue priority calculation and promotion
docker compose exec app python3 scripts/promote_queue_signal.py

# 8. Interactive queue priority testing
docker compose exec app python3 scripts/test_queue_priorities.py
```

### Live Price Fetching Script (NEW) ⭐

```bash
# 9. Fetch live exchange prices for realistic testing
docker compose exec app python3 scripts/fetch_live_prices.py

# This script provides:
# - Current market prices from Binance and Bybit testnets
# - Strategic prices (0.1% above/below, 5% above/below)
# - Ready-to-use test commands with calculated prices
# - Bracket strategy suggestions for guaranteed fills
```

---

## 📋 PRE-TEST SETUP

### 1. Fetch Live Exchange Prices (5 mins) ⭐ CRITICAL

**Why:** To create realistic test orders that will actually fill, test TP execution, and verify risk engine behavior.

```bash
# Fetch current prices from both exchanges
docker compose exec app python3 scripts/fetch_live_prices.py
```

**This script provides:**
- ✅ Current market prices for all configured pairs
- ✅ Strategic prices for different test scenarios:
  - **0.1% above/below**: For orders that fill quickly (within minutes)
  - **5% above**: For creating losing positions (Risk Engine testing)
  - **5% below**: For creating winning positions (offset testing)
- ✅ Example commands ready to copy-paste
- ✅ Bracket strategy suggestions (one order above, one below)

**IMPORTANT Testing Strategies:**

1. **For Realistic Fills** - Use bracket strategy:
   - Place order 0.1% BELOW current price → fills on pump
   - Place order 0.1% ABOVE current price → fills on dip
   - At least ONE will fill within 5-10 minutes

2. **For Market Orders** - Use exact current price:
   - Fills immediately (within seconds)
   - Best for testing TP creation and DCA fills

3. **For Risk Engine** - Use 5% above current price:
   - Creates immediate losing position
   - Triggers risk_eligible status
   - Tests risk timer and closure

4. **For Dashboard/Analytics** - Mix of positions:
   - Some at 5% loss, some at 5% profit
   - Tests PnL calculations and display
   - Verifies offset calculations

**Save the output** - You'll reference these prices throughout testing!

---

### 2. Environment Preparation (10 mins)

```bash
# Start all services
docker compose down
docker compose up -d

# Clean slate - remove old positions from exchanges
docker compose exec app python3 scripts/clean_positions_in_exchanges.py

# Clean database positions
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Verify starting state - check exchanges and queue
docker compose exec app python3 scripts/verify_exchange_positions.py
docker compose exec app python3 scripts/list_queue.py
```

**Expected Result:**
- ✅ All services running
- ✅ Zero active positions on exchanges
- ✅ Empty queue
- ✅ Clean database

---

### 3. Verify Configuration (5 mins)

**Database Verification:**

```bash
# Verify DCA configurations loaded
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pair, exchange, entry_order_type, tp_mode, max_pyramids
   FROM dca_configurations
   WHERE user_id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1'
   ORDER BY pair;"

# Check Risk Engine settings
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT username, max_open_positions_global, enable_risk_engine
   FROM users
   WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1';"
```

**Expected Result:**

- ✅ 10 DCA configs present for test pairs
- ✅ Risk engine configured
- ✅ Execution pool limit set to 10

---

## ⚙️ PRACTICAL TEST CONFIGURATION - QUICK RISK ENGINE TESTING

### Overview

The Risk Engine has several configurable thresholds that determine when it activates. For **practical observable testing**, we need to temporarily reduce these values to trigger the Risk Engine quickly during testing.

**Default Production Values:**
- `loss_threshold_percent`: -1.5% (position must lose 1.5%+ to start timer)
- `required_pyramids_for_timer`: 3 (need 3 pyramids complete)
- `post_pyramids_wait_minutes`: 15 (wait 15 minutes after conditions met)

**Practical Testing Values:**
- `loss_threshold_percent`: -0.005% (triggers on 0.005% loss - very easy to hit)
- `required_pyramids_for_timer`: 1 (need only 1 pyramid - first entry)
- `post_pyramids_wait_minutes`: 1 (wait only 1 minute)

---

### Configure Risk Engine for Fast Testing

**STEP 1: Apply Test Configuration**

```bash
# View current Risk Engine config
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT risk_config FROM users WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1';"

# Update Risk Engine config for FAST TESTING
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE users SET risk_config = jsonb_set(
    jsonb_set(
      jsonb_set(
        risk_config,
        '{loss_threshold_percent}',
        '\"-0.005\"'
      ),
      '{required_pyramids_for_timer}',
      '1'
    ),
    '{post_pyramids_wait_minutes}',
    '1'
  )
  WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1'
  RETURNING risk_config->'loss_threshold_percent' as loss_threshold,
            risk_config->'required_pyramids_for_timer' as required_pyramids,
            risk_config->'post_pyramids_wait_minutes' as wait_minutes;"
```

**STEP 2: Verify Configuration Applied**

```bash
# Verify the new values
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    risk_config->>'loss_threshold_percent' as loss_threshold,
    risk_config->>'required_pyramids_for_timer' as required_pyramids,
    risk_config->>'post_pyramids_wait_minutes' as wait_minutes
   FROM users
   WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1';"
```

**Expected Output:**
```
 loss_threshold | required_pyramids | wait_minutes
----------------+-------------------+--------------
 -0.005         | 1                 | 1
```

---

### Restore Production Configuration (After Testing)

**IMPORTANT:** Always restore production values after testing!

```bash
# Restore PRODUCTION Risk Engine config
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE users SET risk_config = jsonb_set(
    jsonb_set(
      jsonb_set(
        risk_config,
        '{loss_threshold_percent}',
        '\"-1.5\"'
      ),
      '{required_pyramids_for_timer}',
      '3'
    ),
    '{post_pyramids_wait_minutes}',
    '15'
  )
  WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1'
  RETURNING 'Production config restored' as status;"
```

---

### Quick Reference: Configuration Commands

| Setting | Test Value | Production Value | Purpose |
|---------|------------|------------------|---------|
| `loss_threshold_percent` | -0.005 | -1.5 | % loss to trigger timer |
| `required_pyramids_for_timer` | 1 | 3 | Pyramids needed before timer |
| `post_pyramids_wait_minutes` | 1 | 15 | Minutes to wait after conditions met |

**Pro Tip:** Create positions at prices slightly above market price to immediately trigger loss conditions for testing.

---

## 🔥 TEST SUITE 1: BASIC SIGNAL INGESTION & EXECUTION (30 mins)

### Test 1.1: First Entry Signal - Single Position Creation

```bash
# Send entry signal for SOLUSDT on Bybit (configured with 5 DCA levels, max_pyramids=1)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 136.82 \
  --order-size 0.4

# Verify orders on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py

# Verify in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange, status, pyramid_count
   FROM position_groups
   WHERE symbol = 'SOLUSDT'
   ORDER BY created_at DESC LIMIT 1;"
```

**Expected Result:**

- ✅ Position group created in DB
- ✅ DCA orders submitted to exchange
- ✅ Exchange shows 5 open limit orders for SOLUSDT
- ✅ Database shows position with status='live'
- ✅ Pyramid count = 1

**Verification Points:**

- Position group ID created
- Pyramid count = 1
- DCA orders count = 5 legs (as configured for SOL/USDT)
- Exchange has open limit orders

---

### Test 1.2: Pyramid Signal - Add to Existing Group

```bash
# Send another entry for BTCUSDT on Binance (configured with 4 DCA levels, max_pyramids=2)
# This will test pyramid functionality
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92454.0 \
  --order-size 0.01

# Send second pyramid entry
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 91529.0 \
  --order-size 0.01

# Verify
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Same position group (not new one)
- ✅ Pyramid count = 2
- ✅ First pyramid uses pyramid_specific_levels[1] with 2 DCA legs
- ✅ Second pyramid uses pyramid_specific_levels[2] with 1 DCA leg
- ✅ Database shows pyramid_count = 2 for BTCUSDT

---

### Test 1.3: Different Pair - New Group

```bash
# Send entry for ETHUSDT on Binance (configured with 3 DCA levels, market orders, max_pyramids=3)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3232.0 \
  --order-size 0.04

# Verify
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ NEW position group created (different pair)
- ✅ Total active groups = 3 (SOLUSDT on Bybit, BTCUSDT on Binance, ETHUSDT on Binance)
- ✅ Exchange verification shows 3 positions

---

### Test 1.4: Different Pair - New Group

```bash
# Send entry for XRPUSDT on Binance (configured with 2 DCA levels, hybrid TP mode, max_pyramids=5)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.03 \
  --order-size 40

# Verify
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Total active groups = 4
- ✅ Exchange verification shows all 4 positions
- ✅ Database shows 4 active position groups

---

## 🔥 TEST SUITE 2: EXECUTION POOL & QUEUE SYSTEM (45 mins)

### Test 2.1: Fill Pool to Capacity

```bash
# We already have 4 positions. Add 6 more to reach limit of 10 (max_open_positions_global=10).

# Position 5 - DOGEUSDT on Bybit (5 DCA levels, limit orders, max_pyramids=3)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.14 \
  --order-size 400

# Position 6 - ADAUSDT on Binance (1 DCA level, market orders, max_pyramids=1)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.42 \
  --order-size 200

# Position 7 - DOTUSDT on Bybit (5 DCA levels, limit orders, max_pyramids=2)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol DOTUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.11 \
  --order-size 40

# Position 8 - TRXUSDT on Binance (6 DCA levels, market orders, max_pyramids=4)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.28 \
  --order-size 400

# Position 9 - MATICUSDT on Bybit (2 DCA levels, limit orders, max_pyramids=1)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol MATICUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.21 \
  --order-size 400

# Position 10 - LINKUSDT on Binance (8 DCA levels, market orders, max_pyramids=3)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol LINKUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 14.09 \
  --order-size 8

# Verify pool is full
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Active positions = 10 (pool full)
- ✅ Exchange verification shows 10 positions
- ✅ Monitor script shows pool: 10/10

---

### Test 2.2: Queue Entry When Pool Full

```bash
# Try to add 11th position (should queue) - Use a pair NOT yet in the system
# Note: We'll use DOGEUSDT on Bybit again to test queue replacement later
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.14 \
  --order-size 400

# Verify queued
docker compose exec app python3 scripts/list_queue.py
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Signal added to queue (not executed) OR pyramids onto existing DOGEUSDT position
- ✅ list_queue.py shows queued signal (if queued)
- ✅ Active positions still = 10 (if queued)
- ✅ Verify behavior based on whether pyramiding happens or signal is queued

---

### Test 2.3: Queue Another Signal (Test Queue Replacement)

```bash
# Send another signal for a new pair to test queue behavior
# Use DOTUSDT on Bybit (already has a position, test if it pyramids or queues)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol DOTUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.09 \
  --order-size 40

# Verify
docker compose exec app python3 scripts/list_queue.py
```

**Expected Result:**

- ✅ If DOTUSDT can pyramid (max_pyramids=2), it creates a second pyramid
- ✅ Otherwise, signal is queued or replaced in queue
- ✅ Queue behavior validated

---

### Test 2.4: Queue Promotion Test

```bash
# Manually close all positions to test queue promotion
docker compose exec app python3 scripts/clean_positions_in_exchanges.py
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Verify queued signals were promoted
docker compose exec app python3 scripts/list_queue.py
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ After cleaning: pool freed
- ✅ Queued signals may be promoted automatically if queue promotion logic runs
- ✅ Verify via list_queue.py and verify_exchange_positions.py

---

## 🔥 TEST SUITE 3: REALISTIC ORDER FILLS & MARKET ORDERS (30 mins) ⭐

### Overview

This test suite focuses on creating positions that ACTUALLY FILL on the exchange using live market prices. This enables real testing of:
- DCA order fills
- Take-profit order creation and execution
- Market order execution
- Dashboard PnL calculations
- Real-time position monitoring

**Prerequisites:**
- Live prices fetched from fetch_live_prices.py
- Clean exchange state
- Understanding of bracket strategy

---

### Test 3.1: Bracket Strategy - Guaranteed Fill

**Objective:** Create positions that are guaranteed to fill within 5-10 minutes

```bash
# STEP 1: Fetch current price (from fetch_live_prices.py output)
# Let's say ETHUSDT = $3,200.00

# STEP 2: Place TWO orders - one above, one below current price
# Order A: 0.1% below ($3,196.80) - fills when price pumps
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3196.80 \
  --order-size 0.04

# Order B: 0.1% above ($3,203.20) - fills when price dips
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.032 \
  --order-size 40

# Wait 5-10 minutes for fills
sleep 300

# Verify fills
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ At least ONE position shows filled DCA orders (status changes to FILLED)
- ✅ Weighted average entry price calculated
- ✅ Take-profit orders created automatically
- ✅ Unrealized PnL calculated and updating
- ✅ Dashboard shows real-time position data

**Verification:**

```bash
# Check which orders filled
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange, status, filled_quantity,
   weighted_avg_entry, unrealized_pnl_percent
   FROM position_groups
   WHERE symbol IN ('ETHUSDT', 'XRPUSDT')
   ORDER BY created_at DESC;"

# Check DCA order fills
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pg.symbol, do.level, do.status, do.filled_quantity, do.fill_price
   FROM dca_orders do
   JOIN position_groups pg ON do.position_group_id = pg.id
   WHERE pg.symbol IN ('ETHUSDT', 'XRPUSDT')
   ORDER BY pg.symbol, do.level;"
```

---

### Test 3.2: Market Orders - Instant Fill

**Objective:** Test market orders that fill immediately using exact current price

```bash
# STEP 1: Get exact current price (from fetch_live_prices.py)
# Use EXACT price for market order immediate fill

# BTCUSDT market order (should fill in seconds)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92454.00 \
  --order-size 0.01

# Wait 30 seconds for fill
sleep 30

# Verify instant fill
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Position filled within 30 seconds
- ✅ All DCA orders show FILLED status
- ✅ Take-profit orders created immediately
- ✅ Real-time PnL calculation active
- ✅ Position visible in monitoring script

---

### Test 3.3: Take-Profit Order Creation & Monitoring

**Objective:** Verify TP orders are created automatically after fills

```bash
# After Test 3.2 market order fills, check TP orders on exchange

# Verify TP orders exist
docker compose exec app python3 scripts/verify_exchange_positions.py

# Check TP orders in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pg.symbol, tpo.tp_percent, tpo.tp_price, tpo.status,
   tpo.quantity, tpo.order_id
   FROM take_profit_orders tpo
   JOIN position_groups pg ON tpo.position_group_id = pg.id
   WHERE pg.symbol = 'BTCUSDT'
   ORDER BY tpo.tp_percent;"
```

**Expected Result:**

- ✅ Take-profit orders created on exchange
- ✅ TP prices calculated correctly based on configuration
- ✅ TP orders show in exchange as OPEN limit orders
- ✅ Database reflects TP order details
- ✅ If price hits TP, orders execute and close position

**Monitor TP Execution:**

```bash
# Run this periodically to catch TP fills
watch -n 30 'docker compose exec app python3 scripts/verify_exchange_positions.py'

# Check for closed positions
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd, closed_at
   FROM position_groups
   WHERE status = 'closed'
   ORDER BY closed_at DESC
   LIMIT 10;"
```

---

### Test 3.4: Dashboard & Analytics with Real Data

**Objective:** Verify dashboard calculations with real filled orders

```bash
# Monitor comprehensive statistics
docker compose exec app python3 scripts/monitor_all_tests.py

# Check PnL calculations
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange,
   filled_quantity,
   weighted_avg_entry,
   current_price,
   unrealized_pnl_usd,
   unrealized_pnl_percent,
   CASE
     WHEN unrealized_pnl_percent > 0 THEN 'PROFIT'
     WHEN unrealized_pnl_percent < 0 THEN 'LOSS'
     ELSE 'BREAK-EVEN'
   END as status
   FROM position_groups
   WHERE status NOT IN ('closed', 'failed')
   ORDER BY unrealized_pnl_percent DESC;"
```

**Expected Result:**

- ✅ Real-time PnL calculations accurate
- ✅ Weighted average entry price correct
- ✅ Current price updates from exchange
- ✅ Winning/losing positions identified
- ✅ Total portfolio PnL calculated
- ✅ Monitor script shows comprehensive statistics

---

### Test 3.5: Multiple Fills Across Exchanges

**Objective:** Create realistic positions on both Binance and Bybit

```bash
# Use live prices for both exchanges

# Binance positions with bracket strategy
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol LINKUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price <USE_PRICE_FROM_SCRIPT_0.1%_BELOW> \
  --order-size 8

# Bybit positions with bracket strategy
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price <USE_PRICE_FROM_SCRIPT_0.1%_BELOW> \
  --order-size 0.4

# Wait for fills and verify
sleep 600  # Wait 10 minutes
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Positions created on both exchanges
- ✅ Multiple orders filled across exchanges
- ✅ Cross-exchange PnL tracked separately
- ✅ Both exchanges show in monitoring
- ✅ No conflicts between exchanges

---

## 🔥 TEST SUITE 4: PRECISION VALIDATION (20 mins)

### Test 4.1: Valid Symbol - Orders Respect Precision

```bash
# Send signal for valid pair with precise decimal values
# XRPUSDT on Binance (configured with 2 DCA levels, market orders)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.03 \
  --order-size 40

# Verify orders on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Orders submitted successfully
- ✅ Prices rounded to exchange tick size
- ✅ Quantities rounded to step size
- ✅ No exchange rejections
- ✅ Orders visible on exchange with correct precision

---

### Test 4.2: Multiple Asset Precision Test

```bash
# Test different assets with different precision requirements
# DOGEUSDT on Bybit (configured with 5 DCA levels, limit orders)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.14 \
  --order-size 400

# Test LINKUSDT on Binance (8 DCA levels, market orders)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol LINKUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 14.09 \
  --order-size 8

# Verify
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Orders created with correct precision per symbol
- ✅ No exchange rejection errors
- ✅ All assets trade successfully

---

## 🔥 TEST SUITE 5: RISK ENGINE (45 mins)

### Overview

The Risk Engine automatically manages losing positions by:
- Monitoring positions for losses exceeding configured thresholds
- Starting risk timers when positions become eligible
- Closing losing positions using winning positions as offsets
- Logging all risk actions for audit

**Prerequisites:**
- Risk engine enabled in user settings
- Mix of winning and losing positions
- Risk timer configured (e.g., 120 seconds)

---

### Test 5.1: Risk Engine Status Monitoring

**Objective:** Verify risk engine tracks position states correctly

```bash
# Create positions and check risk engine status
docker compose exec app python3 scripts/monitor_all_tests.py

# Check risk engine settings
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT username, enable_risk_engine, risk_loss_threshold_percent,
   risk_timer_seconds
   FROM users
   WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1';"

# Check positions with risk status
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange, unrealized_pnl_percent,
   risk_eligible, risk_blocked, risk_timer_start
   FROM position_groups
   WHERE status NOT IN ('closed', 'failed')
   ORDER BY unrealized_pnl_percent;"
```

**Expected Result:**

- ✅ Risk engine enabled in user settings
- ✅ Monitor script shows risk engine status
- ✅ Positions with losses > threshold marked as risk_eligible
- ✅ Risk timer starts when position becomes eligible
- ✅ Database accurately reflects risk states

---

### Test 5.2: Risk Timer Behavior

**Objective:** Verify risk timer starts and tracks correctly

```bash
# Create a losing position (use entry price above current market)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.50 \
  --order-size 200

# Wait for position to show loss, then check timer
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, unrealized_pnl_percent, risk_eligible,
   risk_timer_start,
   EXTRACT(EPOCH FROM (NOW() - risk_timer_start)) as timer_elapsed_seconds
   FROM position_groups
   WHERE symbol = 'ADAUSDT' AND exchange = 'binance';"

# Monitor over time
docker compose exec app python3 scripts/monitor_all_tests.py
```

**Expected Result:**

- ✅ Position created with entry above market price
- ✅ Position shows negative PnL
- ✅ risk_eligible = true when loss exceeds threshold
- ✅ risk_timer_start timestamp recorded
- ✅ Timer elapsed increases over time
- ✅ Monitor script shows timer countdown

---

### Test 5.3: Risk Actions - Block Position

**Objective:** Verify blocking prevents risk engine from closing position

```bash
# Mark a position as risk_blocked
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET risk_blocked = true
   WHERE symbol = 'ADAUSDT' AND exchange = 'binance'
   RETURNING symbol, risk_blocked, risk_eligible;"

# Verify block status
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_eligible, risk_blocked, unrealized_pnl_percent
   FROM position_groups
   WHERE risk_blocked = true;"

# Check monitor reflects blocked status
docker compose exec app python3 scripts/monitor_all_tests.py
```

**Expected Result:**

- ✅ Position marked as risk_blocked = true
- ✅ Risk engine respects block (won't close position)
- ✅ Database shows correct block status
- ✅ Monitor script shows blocked positions

---

### Test 5.4: Risk Actions History

**Objective:** Verify all risk actions are logged

```bash
# Check risk actions table
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT id, action_type, timestamp, notes,
   position_group_id
   FROM risk_actions
   ORDER BY timestamp DESC
   LIMIT 20;"

# Check actions for specific position
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT ra.action_type, ra.timestamp, ra.notes,
   pg.symbol, pg.exchange
   FROM risk_actions ra
   JOIN position_groups pg ON ra.position_group_id = pg.id
   WHERE pg.symbol = 'ADAUSDT'
   ORDER BY ra.timestamp DESC;"
```

**Expected Result:**

- ✅ All risk actions logged with timestamps
- ✅ Action types recorded (block, skip, evaluation, etc.)
- ✅ Notes field contains relevant information
- ✅ Actions linked to correct position groups
- ✅ History queryable for audit

---

### Test 5.5: Risk Engine Evaluation Cycle

**Objective:** Verify risk engine evaluates positions periodically

```bash
# Create mix of winning and losing positions
# Then monitor risk evaluations

# Check when last evaluation occurred
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT action_type, timestamp, notes
   FROM risk_actions
   WHERE action_type = 'evaluation'
   ORDER BY timestamp DESC
   LIMIT 5;"

# Monitor positions at risk
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
   COUNT(*) FILTER (WHERE risk_eligible = true AND risk_blocked = false) as eligible_positions,
   COUNT(*) FILTER (WHERE risk_blocked = true) as blocked_positions,
   COUNT(*) FILTER (WHERE unrealized_pnl_percent < -5) as losing_positions,
   COUNT(*) FILTER (WHERE unrealized_pnl_percent > 5) as winning_positions
   FROM position_groups
   WHERE status NOT IN ('closed', 'failed');"
```

**Expected Result:**

- ✅ Risk engine evaluates positions periodically
- ✅ Evaluation actions logged with timestamp
- ✅ Statistics show risk categorization
- ✅ Eligible positions identified correctly
- ✅ Blocked positions excluded from auto-closure

---

### Test 5.6: Risk Engine Offset Calculation

**Objective:** Verify risk engine identifies winning positions for offsets

```bash
# Create scenario with both winning and losing positions
# Check which positions would be used as offsets

# Query potential offset pairs
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "WITH losing AS (
     SELECT id, symbol, exchange, unrealized_pnl_percent,
            ABS(unrealized_pnl_usd) as loss_usd
     FROM position_groups
     WHERE status NOT IN ('closed', 'failed')
     AND unrealized_pnl_percent < -5
     AND risk_eligible = true
     AND risk_blocked = false
   ),
   winning AS (
     SELECT id, symbol, exchange, unrealized_pnl_percent,
            unrealized_pnl_usd as profit_usd
     FROM position_groups
     WHERE status NOT IN ('closed', 'failed')
     AND unrealized_pnl_percent > 5
   )
   SELECT
     l.symbol as losing_position,
     l.loss_usd,
     w.symbol as winning_position,
     w.profit_usd,
     CASE WHEN w.profit_usd >= l.loss_usd THEN 'Can Offset' ELSE 'Partial Offset' END as status
   FROM losing l
   CROSS JOIN winning w
   ORDER BY l.loss_usd DESC, w.profit_usd DESC;"
```

**Expected Result:**

- ✅ Query identifies losing positions requiring offset
- ✅ Query identifies winning positions available for offset
- ✅ Offset calculation shows if profit covers loss
- ✅ Risk engine has sufficient data to make decisions

---

### Test 5.7: Risk Engine - Position Closure

**Objective:** Verify risk engine can close positions (manual trigger for testing)

```bash
# Check positions eligible for closure
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange, unrealized_pnl_percent,
   risk_eligible, risk_blocked,
   EXTRACT(EPOCH FROM (NOW() - risk_timer_start)) as timer_elapsed
   FROM position_groups
   WHERE risk_eligible = true
   AND risk_blocked = false
   AND risk_timer_start IS NOT NULL;"

# After risk timer expires (e.g., 120 seconds), verify position closed
# Note: This requires risk engine background service to be running
# Or manual closure via API

# Verify closure on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py

# Check database status
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, closed_at, realized_pnl_usd
   FROM position_groups
   WHERE symbol = 'ADAUSDT' AND exchange = 'binance';"
```

**Expected Result:**

- ✅ Position closed after risk timer expires
- ✅ Closure recorded in database with timestamp
- ✅ Exchange shows position closed (no open orders)
- ✅ Realized PnL calculated and recorded
- ✅ Risk action logged for closure

---

## 🔥 TEST SUITE 5A: PRACTICAL RISK ENGINE TESTING (30 mins) ⭐ NEW

### Overview

This test suite provides **practical, observable Risk Engine tests** using reduced thresholds for quick feedback. Instead of waiting 15+ minutes with 3 pyramids at -1.5% loss, we configure:

- **Loss threshold**: -0.005% (triggers on almost any market movement)
- **Required pyramids**: 1 (first entry counts)
- **Wait time**: 1 minute (observable in real-time)

**IMPORTANT:** This suite requires running the configuration commands from the "Practical Test Configuration" section first!

---

### Test 5A.1: Setup - Apply Test Configuration

**Objective:** Configure Risk Engine for fast, observable testing

```bash
# STEP 1: Apply test configuration (REQUIRED before other tests)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE users SET risk_config = jsonb_set(
    jsonb_set(
      jsonb_set(
        risk_config,
        '{loss_threshold_percent}',
        '\"-0.005\"'
      ),
      '{required_pyramids_for_timer}',
      '1'
    ),
    '{post_pyramids_wait_minutes}',
    '1'
  )
  WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1'
  RETURNING 'Test config applied' as status;"

# STEP 2: Verify configuration
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    risk_config->>'loss_threshold_percent' as loss_threshold,
    risk_config->>'required_pyramids_for_timer' as required_pyramids,
    risk_config->>'post_pyramids_wait_minutes' as wait_minutes
   FROM users
   WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1';"

# STEP 3: Clean slate
docker compose exec app python3 scripts/clean_positions_in_exchanges.py
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
```

**Expected Result:**

- ✅ loss_threshold = -0.005
- ✅ required_pyramids = 1
- ✅ wait_minutes = 1
- ✅ Clean exchange and database state

---

### Test 5A.2: Create Losing Position - Observe Timer Start

**Objective:** Create a position that immediately shows loss and triggers risk timer

```bash
# Get current BTC price (approximate)
# Entry should be ABOVE current market to create instant loss

# Create position at price ABOVE market (instant loss)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 100000.0 \
  --order-size 0.001

# Wait 5 seconds for order submission
sleep 5

# Check timer started (should show risk_timer_start and risk_timer_expires)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    symbol,
    status,
    pyramid_count,
    unrealized_pnl_percent,
    risk_timer_start,
    risk_timer_expires,
    CASE
      WHEN risk_timer_expires IS NOT NULL
      THEN EXTRACT(EPOCH FROM (risk_timer_expires - NOW()))::int
      ELSE NULL
    END as seconds_until_expiry
   FROM position_groups
   WHERE symbol = 'BTCUSDT' AND status = 'live'
   ORDER BY created_at DESC LIMIT 1;"
```

**Expected Result:**

- ✅ Position created with entry price above market
- ✅ Position shows negative unrealized_pnl_percent
- ✅ risk_timer_start is NOT NULL (timer started)
- ✅ risk_timer_expires shows ~60 seconds in future
- ✅ seconds_until_expiry counts down from ~60

---

### Test 5A.3: Watch Risk Timer Countdown

**Objective:** Observe the risk timer counting down in real-time

```bash
# Run this command every 10 seconds to watch countdown
# Option 1: Manual checks
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    symbol,
    unrealized_pnl_percent as pnl_pct,
    EXTRACT(EPOCH FROM (risk_timer_expires - NOW()))::int as seconds_left,
    CASE
      WHEN risk_timer_expires < NOW() THEN 'EXPIRED - READY FOR CLOSURE'
      ELSE 'COUNTING DOWN'
    END as timer_status
   FROM position_groups
   WHERE risk_timer_start IS NOT NULL
   AND status = 'live';"

# Option 2: Use watch command (run for 90 seconds)
# watch -n 10 'docker compose exec db psql -U tv_user -d tv_engine_db -c "SELECT symbol, EXTRACT(EPOCH FROM (risk_timer_expires - NOW()))::int as seconds_left FROM position_groups WHERE risk_timer_start IS NOT NULL AND status = '\''live'\'';"'
```

**Expected Result:**

- ✅ Timer counts down from ~60 to 0
- ✅ When seconds_left reaches 0, shows "EXPIRED - READY FOR CLOSURE"
- ✅ Position remains open until Risk Engine evaluation runs

---

### Test 5A.4: Trigger Risk Engine Evaluation

**Objective:** Manually trigger risk evaluation to close expired position

```bash
# After timer expires, trigger risk evaluation via API
TOKEN="<your_jwt_token>"

# Method 1: Via API (if endpoint exists)
curl -X POST http://localhost:8000/api/v1/risk/run-evaluation \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Method 2: Check if background service auto-evaluates
# Wait 60-90 seconds after timer expires

# Verify position status changed
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    symbol,
    status,
    closed_at,
    realized_pnl_usd,
    close_reason
   FROM position_groups
   WHERE symbol = 'BTCUSDT'
   ORDER BY created_at DESC LIMIT 1;"

# Check risk actions logged
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    action_type,
    created_at,
    details
   FROM risk_actions
   ORDER BY created_at DESC LIMIT 5;"

# Verify orders cancelled on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Position status changed from 'live' to 'closing' or 'closed'
- ✅ closed_at timestamp recorded
- ✅ Risk action logged with action_type = 'timer_expired' or similar
- ✅ Exchange shows no open orders for this position
- ✅ All DCA orders cancelled

---

### Test 5A.5: Timer Reset on Pyramid

**Objective:** Verify pyramid continuation resets risk timer

```bash
# Create initial position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 4000.0 \
  --order-size 0.01

# Wait for timer to start
sleep 10

# Check initial timer
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_timer_start, risk_timer_expires FROM position_groups WHERE symbol = 'ETHUSDT' AND status = 'live';"

# Wait 30 seconds (halfway through timer)
sleep 30

# Add pyramid (should reset timer)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3950.0 \
  --order-size 0.01

# Check timer was reset (new risk_timer_start, new risk_timer_expires)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    symbol,
    pyramid_count,
    risk_timer_start,
    risk_timer_expires,
    EXTRACT(EPOCH FROM (risk_timer_expires - NOW()))::int as seconds_left
   FROM position_groups
   WHERE symbol = 'ETHUSDT' AND status = 'live';"
```

**Expected Result:**

- ✅ Initial timer started after first entry
- ✅ After pyramid, timer is RESET (risk_timer_start updated)
- ✅ New risk_timer_expires shows ~60 seconds from NOW
- ✅ Pyramid count incremented
- ✅ Position gets "fresh" 1 minute countdown

---

### Test 5A.6: Timer Stops When Loss Recovers

**Objective:** Verify timer clears if position returns to profit

```bash
# Create position at price slightly above market
# (small loss that might recover)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.10 \
  --order-size 20

# Wait for timer to start
sleep 10

# Check timer started
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, unrealized_pnl_percent, risk_timer_start, risk_timer_expires FROM position_groups WHERE symbol = 'XRPUSDT' AND status = 'live';"

# If price recovers and PnL goes above -0.005%, timer should clear
# (This depends on market movement - may need to manually update for testing)

# Simulate recovery by updating weighted_avg_entry to current market price
# docker compose exec db psql -U tv_user -d tv_engine_db -c \
#   "UPDATE position_groups SET weighted_avg_entry = <current_market_price> WHERE symbol = 'XRPUSDT';"

# Check timer cleared
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    symbol,
    unrealized_pnl_percent,
    risk_timer_start,
    risk_timer_expires,
    CASE
      WHEN risk_timer_start IS NULL THEN 'TIMER_CLEARED'
      ELSE 'TIMER_ACTIVE'
    END as timer_status
   FROM position_groups
   WHERE symbol = 'XRPUSDT' AND status = 'live';"
```

**Expected Result:**

- ✅ Timer starts when loss exceeds -0.005%
- ✅ Timer CLEARS (risk_timer_start = NULL) when loss recovers
- ✅ Position remains open (not closed by risk engine)
- ✅ If loss returns, timer restarts fresh

---

### Test 5A.7: Blocked Position Ignores Timer

**Objective:** Verify blocked positions don't close even with expired timer

```bash
# Create losing position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.60 \
  --order-size 50

# Wait for timer to start
sleep 5

# Block the position
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET risk_blocked = true
   WHERE symbol = 'ADAUSDT' AND status = 'live'
   RETURNING symbol, risk_blocked;"

# Wait for timer to expire (70+ seconds)
sleep 70

# Check position still open despite expired timer
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    symbol,
    status,
    risk_blocked,
    risk_timer_expires,
    EXTRACT(EPOCH FROM (risk_timer_expires - NOW()))::int as seconds_since_expiry
   FROM position_groups
   WHERE symbol = 'ADAUSDT';"

# Trigger risk evaluation
TOKEN="<your_jwt_token>"
curl -X POST http://localhost:8000/api/v1/risk/run-evaluation \
  -H "Authorization: Bearer $TOKEN"

# Verify still open
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, risk_blocked FROM position_groups WHERE symbol = 'ADAUSDT';"
```

**Expected Result:**

- ✅ Position blocked (risk_blocked = true)
- ✅ Timer expires (seconds_since_expiry shows negative)
- ✅ After risk evaluation, position STILL OPEN
- ✅ Status remains 'live' (not closed)
- ✅ Blocked positions protected from auto-closure

---

### Test 5A.8: Cleanup - Restore Production Config

**Objective:** Restore production risk engine configuration

```bash
# IMPORTANT: Always restore after testing!
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE users SET risk_config = jsonb_set(
    jsonb_set(
      jsonb_set(
        risk_config,
        '{loss_threshold_percent}',
        '\"-1.5\"'
      ),
      '{required_pyramids_for_timer}',
      '3'
    ),
    '{post_pyramids_wait_minutes}',
    '15'
  )
  WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1'
  RETURNING 'Production config restored' as status;"

# Verify restoration
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    risk_config->>'loss_threshold_percent' as loss_threshold,
    risk_config->>'required_pyramids_for_timer' as required_pyramids,
    risk_config->>'post_pyramids_wait_minutes' as wait_minutes
   FROM users
   WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1';"

# Clean up test positions
docker compose exec app python3 scripts/clean_positions_in_exchanges.py
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
```

**Expected Result:**

- ✅ loss_threshold = -1.5
- ✅ required_pyramids = 3
- ✅ wait_minutes = 15
- ✅ Production configuration restored
- ✅ Test positions cleaned

---

## 🔥 TEST SUITE 6: BASIC SYSTEM HEALTH (30 mins)

### Test 6.1: Clean Slate Test

```bash
# Clean everything and start fresh
docker compose exec app python3 scripts/clean_positions_in_exchanges.py
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Verify clean state
docker compose exec app python3 scripts/verify_exchange_positions.py
docker compose exec app python3 scripts/list_queue.py
```

**Expected Result:**

- ✅ All positions removed from exchanges
- ✅ Database cleaned
- ✅ Queue empty
- ✅ System ready for fresh testing

---

### Test 6.2: Multiple Position Management

```bash
# Create multiple positions across both exchanges using configured pairs
# Bybit positions
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 136.82 \
  --order-size 0.4

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.14 \
  --order-size 400

# Binance positions
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92454.0 \
  --order-size 0.01

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3232.0 \
  --order-size 0.04

# Verify all positions
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Multiple positions created across both exchanges
- ✅ All positions visible via verify_exchange_positions.py
- ✅ Exchange orders match database records
- ✅ No conflicts or errors

---

## 🔥 TEST SUITE 7: SYSTEM PERSISTENCE (15 mins)

### Test 7.1: Application Restart Persistence

```bash
# Create some positions using configured pairs
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92454.0 \
  --order-size 0.01

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange bybit \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 136.82 \
  --order-size 0.4

# Verify before restart
docker compose exec app python3 scripts/verify_exchange_positions.py

# Restart application
docker compose restart app

# Wait a moment for startup, then verify positions still exist
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ All positions persisted after restart
- ✅ No data loss
- ✅ Exchange state unchanged after restart
- ✅ System continues functioning normally

---

## 🔥 TEST SUITE 8: QUEUE PRIORITY SYSTEM (90 mins)

### Overview

The queue priority system uses 4 rules (in order of priority):
1. **Same Pair/Timeframe (Pyramid)** - Tier 0: Score 10,000,000+ (Highest)
2. **Deepest Loss Percent** - Tier 1: Score 1,000,000+
3. **Highest Replacement Count** - Tier 2: Score 10,000+
4. **FIFO Fallback** - Tier 3: Score 1,000+ (Lowest)

**Prerequisites:**
- Pool must be at 10/10 capacity
- Multiple signals queued
- 20 DCA configurations loaded

---

### Test 8.1: Queue Functionality - Basic Queuing

**Objective:** Verify signals queue correctly when pool is full

```bash
# Ensure pool is full (10/10)
docker compose exec app python3 scripts/monitor_all_tests.py

# If not full, create positions until pool = 10/10
# Then add signals to queue

# Add BNB signal (limit orders, hybrid TP)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BNBUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 700.0 \
  --order-size 0.1

# Add AVAX signal (market orders, per-leg TP)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol AVAXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 40.0 \
  --order-size 1.0

# Add LTC signal (limit orders, per-leg TP)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol LTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 100.0 \
  --order-size 0.5

# Verify signals queued
docker compose exec app python3 scripts/list_queue.py
```

**Expected Result:**

- ✅ Pool status shows 10/10 (FULL)
- ✅ All 3 signals added to queue with status='queued'
- ✅ Signals show in queue with timestamps
- ✅ No positions created (pool full)
- ✅ list_queue.py shows all queued signals

---

### Test 8.2: Priority Calculation - Deepest Loss Rule

**Objective:** Verify loss-based priority calculation

```bash
# Check priority scores
docker compose exec app python3 scripts/promote_queue_signal.py
```

**Expected Output:**
```
Queue Priority Order:
Rank | Symbol    | Priority Score          | Explanation
-----|-----------|------------------------|----------------------------------
1    | AVAXUSDT  | 1,660,000+             | Loss: -66.00%, Queued for Xs
2    | LTCUSDT   | 1,160,000+             | Loss: -16.00%, Queued for Xs
3    | BNBUSDT   | 1,000+                 | Queued for Xs
```

**Verification Points:**

- ✅ AVAXUSDT has highest priority (deepest loss)
- ✅ Priority scores show clear tier separation
- ✅ Loss percentage correctly incorporated into score
- ✅ FIFO tiebreaker applied when no loss (BNBUSDT)
- ✅ Priority explanations show active rules

**Manual Verification:**
```bash
# Check database for loss percentages
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, current_loss_percent, replacement_count, queued_at
   FROM queued_signals WHERE status = 'queued' ORDER BY queued_at;"
```

---

### Test 8.3: Priority Rule 1 - Pyramid Continuation

**Objective:** Verify pyramid signals receive highest priority (Tier 0)

```bash
# First, check current active positions for pyramid opportunities
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange, pyramid_count, max_pyramids
   FROM position_groups WHERE status NOT IN ('closed', 'failed');"

# Add signals - mix of new pairs and pyramid continuations
# Signal A: New pair (UNIUSDT)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol UNIUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 12.0 \
  --order-size 5.0

# Signal B: BTCUSDT pyramid (if BTCUSDT has < max_pyramids)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 91000.0 \
  --order-size 0.001

# Check priorities
docker compose exec app python3 scripts/promote_queue_signal.py
```

**Expected Result:**

- ✅ BTCUSDT (pyramid) has priority score 10,000,000+ (Tier 0)
- ✅ UNIUSDT (new pair) has priority score 1,000+ (Tier 3)
- ✅ Pyramid signals clearly separated from non-pyramid signals
- ✅ Priority explanation shows "Pyramid continuation for BTCUSDT"

---

### Test 8.4: Priority Rule 3 - Replacement Count

**Objective:** Verify replacement tracking and priority

```bash
# Add initial signal
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ATOMUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 10.0 \
  --order-size 2.0

# Wait 2 seconds
sleep 2

# Send replacement signals (same symbol/timeframe/side)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ATOMUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 10.05 \
  --order-size 2.0

sleep 2

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ATOMUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 10.10 \
  --order-size 2.0

# Check replacement count
docker compose exec app python3 scripts/list_queue.py
```

**Expected Result:**

- ✅ ATOMUSDT shows replacement_count = 2
- ✅ Entry price updated to latest (10.10)
- ✅ Original queued_at timestamp preserved
- ✅ Higher priority than signals with no replacements
- ✅ Priority explanation shows "2 replacements"

---

### Test 8.5: Priority Rule 4 - FIFO Fallback

**Objective:** Verify FIFO ordering when no other rules apply

```bash
# Add 3 signals with similar characteristics (no pyramid, no loss, no replacements)
# Use pairs that aren't in active positions

# First signal - APTUSDT
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol APTUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 8.0 \
  --order-size 5.0

# Wait to ensure different timestamps
sleep 3

# Second signal - ARBUSDT
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ARBUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 1.5 \
  --order-size 30.0

sleep 3

# Third signal - OPUSDT
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol OPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.5 \
  --order-size 20.0

# Check priorities
docker compose exec app python3 scripts/promote_queue_signal.py
```

**Expected Result:**

- ✅ All signals score ~1,000 points (FIFO tier)
- ✅ APTUSDT has slightly higher score (queued longest)
- ✅ Priority order matches queue order (FIFO)
- ✅ Time difference reflected in score (0.001 per second)

---

### Test 8.6: Queue History

**Objective:** Verify queue history tracking

```bash
# Check current queue history
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, queued_at, promoted_at, replacement_count
   FROM queued_signals
   WHERE status IN ('promoted', 'cancelled')
   ORDER BY promoted_at DESC NULLS LAST
   LIMIT 10;"

# After promoting or cancelling signals, verify history updates
# Promotion happens when pool space opens
```

**Expected Result:**

- ✅ History shows promoted signals with promoted_at timestamp
- ✅ History shows cancelled signals
- ✅ Replacement count preserved in history
- ✅ Queue history accessible via database query

---

### Test 8.7: Queue Promotion When Pool Frees

**Objective:** Test automatic/manual promotion based on priority

```bash
# Close a position to free pool space
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET status = 'closed', closed_at = NOW()
   WHERE symbol = 'XRPUSDT' AND exchange = 'binance'
   RETURNING symbol, status;"

# Check pool status
docker compose exec app python3 scripts/monitor_all_tests.py

# Manual promotion of highest priority signal
docker compose exec app python3 scripts/promote_queue_signal.py
```

**Expected Result:**

- ✅ Pool shows 9/10 (space available)
- ✅ Promotion script identifies highest priority signal
- ✅ Signal with deepest loss promoted first
- ✅ Signal status changes from 'queued' to 'promoted'
- ✅ Position created for promoted signal
- ✅ Queue count decreases by 1

**Note:** Automatic promotion requires background service (not yet implemented).
Currently requires manual promotion via API or script.

---

### Test 8.8: Comprehensive Monitoring

**Objective:** Verify all monitoring tools work correctly

```bash
# Run comprehensive monitoring
docker compose exec app python3 scripts/monitor_all_tests.py
```

**Expected Output Sections:**

1. **Execution Pool Status**
   - ✅ Shows X/10 active positions
   - ✅ Shows queued signal count
   - ✅ Pool status indicator (FULL/AVAILABLE)

2. **Positions by Status**
   - ✅ Counts by status (live, partially_filled, etc.)

3. **Positions by PnL**
   - ✅ Lists all positions with PnL%
   - ✅ Color coding (green profit, red loss)

4. **DCA Orders Status**
   - ✅ Counts by status (filled, open, trigger_pending)

5. **Take-Profit Modes**
   - ✅ Distribution of TP modes configured

6. **Queue Contents**
   - ✅ Lists queued signals
   - ✅ Shows age, replacement count
   - ✅ Priority scores (if calculated)

7. **Risk Engine Status**
   - ✅ Shows positions at risk
   - ✅ Shows risk timer status

8. **Order Type Distribution**
   - ✅ Shows market vs limit order configs

---

### Test 8.9: Multi-Rule Priority Scenario

**Objective:** Test complex scenario with multiple priority rules active

**Setup:**
```bash
# Create scenario with:
# 1. Pyramid signal (Tier 0)
# 2. Deep loss signal (Tier 1)
# 3. Replacement signal (Tier 2)
# 4. FIFO signal (Tier 3)

# Ensure mix of conditions in queue, then verify priority order
docker compose exec app python3 scripts/promote_queue_signal.py
```

**Expected Priority Order:**
1. Pyramid signal (10,000,000+ score)
2. Deep loss signal (1,000,000+ score)
3. Replacement signal (10,000+ score)
4. FIFO signal (1,000+ score)

**Verification:**

- ✅ Tier separation maintained (orders of magnitude)
- ✅ Within same tier, tiebreakers apply correctly
- ✅ All priority explanations accurate
- ✅ Manual promotion respects priority order

---

### Test 8.10: Queue Stress Test

**Objective:** Test queue with many signals

```bash
# Add 10+ signals to queue (use available DCA configs)
# Monitor queue performance and priority calculations

# Check queue contents
docker compose exec app python3 scripts/list_queue.py

# Check priorities
docker compose exec app python3 scripts/promote_queue_signal.py
```

**Expected Result:**

- ✅ All signals queued successfully
- ✅ Priority calculation works with large queue
- ✅ Queue ordered by priority correctly
- ✅ No performance degradation
- ✅ Scripts handle large queue display without errors

---

### Additional Monitoring Commands

```bash
# Check queue via database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange, status, replacement_count, current_loss_percent,
   queued_at, (EXTRACT(EPOCH FROM (NOW() - queued_at))/60)::int as age_minutes
   FROM queued_signals
   WHERE status = 'queued'
   ORDER BY queued_at;"

# Check DCA configurations
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pair, exchange, entry_order_type, tp_mode, max_pyramids
   FROM dca_configurations
   ORDER BY pair;"

# Check active positions for pyramid testing
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange, pyramid_count, max_pyramids,
   (max_pyramids - pyramid_count) as pyramids_available
   FROM position_groups
   WHERE status NOT IN ('closed', 'failed')
   ORDER BY symbol;"
```

---

## 📊 FINAL VERIFICATION CHECKLIST

### ✅ Exchange State Consistency

```bash
# Verify DB positions match exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected:**

- ✅ DB positions match exchange positions
- ✅ No unexpected orders on exchange
- ✅ All orders have correct precision
- ✅ Balances display correctly

---

### ✅ Queue System

```bash
# Verify queue state
docker compose exec app python3 scripts/list_queue.py
```

**Expected:**

- ✅ list_queue.py shows accurate data
- ✅ Queue promotion works when pool frees
- ✅ Queue replacement logic works correctly

---

## 📝 POST-TEST CLEANUP

```bash
# Clean all test data
docker compose exec app python3 scripts/clean_positions_in_exchanges.py
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Verify clean state
docker compose exec app python3 scripts/verify_exchange_positions.py
docker compose exec app python3 scripts/list_queue.py
```

---

## 📊 TEST RESULTS TEMPLATE

Create a file `TEST_RESULTS.md` with this template:

```markdown
# Test Execution Results

**Date:** YYYY-MM-DD
**Tester:** Your Name
**Environment:** Bybit and Binance Testnet
**Duration:** X hours

## Summary

- Total Tests: X
- Passed: X
- Failed: X
- Skipped: X

## Detailed Results

### TEST SUITE 1: Basic Signal Ingestion
- [ ] Test 1.1: First Entry Signal - ✅ PASS / ❌ FAIL
- [ ] Test 1.2: Pyramid Signal - ✅ PASS / ❌ FAIL
- [ ] Test 1.3: Different Exchange - ✅ PASS / ❌ FAIL
- [ ] Test 1.4: Different Pair - ✅ PASS / ❌ FAIL

### TEST SUITE 2: Execution Pool & Queue
- [ ] Test 2.1: Fill Pool to Capacity - ✅ PASS / ❌ FAIL
- [ ] Test 2.2: Queue Entry When Full - ✅ PASS / ❌ FAIL
- [ ] Test 2.3: Queue Replacement - ✅ PASS / ❌ FAIL
- [ ] Test 2.4: Queue Promotion - ✅ PASS / ❌ FAIL

### TEST SUITE 3: Realistic Order Fills & Market Orders
- [ ] Test 3.1: Bracket Strategy - Guaranteed Fill - ✅ PASS / ❌ FAIL
- [ ] Test 3.2: Market Orders - Instant Fill - ✅ PASS / ❌ FAIL
- [ ] Test 3.3: Take-Profit Order Creation & Monitoring - ✅ PASS / ❌ FAIL
- [ ] Test 3.4: Dashboard & Analytics with Real Data - ✅ PASS / ❌ FAIL
- [ ] Test 3.5: Multiple Fills Across Exchanges - ✅ PASS / ❌ FAIL

### TEST SUITE 4: Precision Validation
- [ ] Test 4.1: Valid Symbol Precision - ✅ PASS / ❌ FAIL
- [ ] Test 4.2: Multiple Asset Precision - ✅ PASS / ❌ FAIL

### TEST SUITE 5: Risk Engine
- [ ] Test 5.1: Risk Engine Status Monitoring - ✅ PASS / ❌ FAIL
- [ ] Test 5.2: Risk Timer Behavior - ✅ PASS / ❌ FAIL
- [ ] Test 5.3: Risk Actions - Block Position - ✅ PASS / ❌ FAIL
- [ ] Test 5.4: Risk Actions History - ✅ PASS / ❌ FAIL
- [ ] Test 5.5: Risk Engine Evaluation Cycle - ✅ PASS / ❌ FAIL
- [ ] Test 5.6: Risk Engine Offset Calculation - ✅ PASS / ❌ FAIL
- [ ] Test 5.7: Risk Engine Position Closure - ✅ PASS / ❌ FAIL

### TEST SUITE 6: Basic System Health
- [ ] Test 6.1: Clean Slate Test - ✅ PASS / ❌ FAIL
- [ ] Test 6.2: Multiple Position Management - ✅ PASS / ❌ FAIL

### TEST SUITE 7: System Persistence
- [ ] Test 7.1: Application Restart - ✅ PASS / ❌ FAIL

### TEST SUITE 8: Queue Priority System
- [ ] Test 8.1: Queue Functionality - ✅ PASS / ❌ FAIL
- [ ] Test 8.2: Priority Calculation - Deepest Loss - ✅ PASS / ❌ FAIL
- [ ] Test 8.3: Priority Rule 1 - Pyramid - ✅ PASS / ❌ FAIL
- [ ] Test 8.4: Priority Rule 3 - Replacement - ✅ PASS / ❌ FAIL
- [ ] Test 8.5: Priority Rule 4 - FIFO - ✅ PASS / ❌ FAIL
- [ ] Test 8.6: Queue History - ✅ PASS / ❌ FAIL
- [ ] Test 8.7: Queue Promotion - ✅ PASS / ❌ FAIL
- [ ] Test 8.8: Comprehensive Monitoring - ✅ PASS / ❌ FAIL
- [ ] Test 8.9: Multi-Rule Priority Scenario - ✅ PASS / ❌ FAIL
- [ ] Test 8.10: Queue Stress Test - ✅ PASS / ❌ FAIL

## Issues Found

1. **Issue #1**: Description
   - Severity: High/Medium/Low
   - Steps to reproduce
   - Expected vs Actual

## Notes

- Additional observations
- Suggestions for improvement
```

---

## 🎯 SUCCESS CRITERIA

**Core Tests MUST Pass:**

- ✅ All basic signal ingestion tests pass
- ✅ Pool and queue system works correctly
- ✅ **Queue priority calculation accurate**
- ✅ **Priority rules function as designed**
- ✅ **Risk engine monitors and manages positions**
- ✅ DCA orders created successfully
- ✅ No data loss or corruption
- ✅ Exchange precision validation prevents rejections
- ✅ System persistence after restart
- ✅ Multiple positions managed correctly

**Queue Priority System:**

- ✅ Signals queue when pool is full
- ✅ Priority scores calculated correctly
- ✅ Deepest loss signals prioritized
- ✅ Pyramid signals receive highest priority
- ✅ Replacement count tracked accurately
- ✅ FIFO fallback works when no other rules apply
- ✅ Queue history tracks promoted/cancelled signals

**Risk Engine:**

- ✅ Risk engine identifies losing positions
- ✅ Risk timers start and track correctly
- ✅ Risk blocking prevents unwanted closures
- ✅ All risk actions logged for audit
- ✅ Offset calculations identify winning positions
- ✅ Position closure works when timer expires

**Exchange & Database Consistency:**

- ✅ All exchange positions match database records
- ✅ Orders have correct precision per symbol
- ✅ No unexpected orders on exchanges
- ✅ Queue state consistent across database queries
- ✅ Risk states tracked accurately in database

---

## 🔥 TEST SUITE 9: API ENDPOINTS & AUTHENTICATION (60 mins)

### Overview

This test suite covers API endpoint functionality, authentication, and authorization mechanisms that are critical for the frontend and external integrations.

**Prerequisites:**
- Valid JWT token for authenticated requests
- User registered in system
- API keys configured

---

### Test 9.1: Health Check Endpoints

**Objective:** Verify system health monitoring endpoints

```bash
# Test root health check
curl http://localhost:8000/api/v1/health/

# Test database health check
curl http://localhost:8000/api/v1/health/db
```

**Expected Result:**

- ✅ Root health returns `{"status": "healthy"}`
- ✅ Database health returns `{"status": "healthy", "database": "connected"}`
- ✅ HTTP 200 status code
- ✅ Fast response time (< 100ms)

---

### Test 9.2: User Registration & Login

**Objective:** Test user management and JWT token generation

```bash
# Register new user
curl -X POST http://localhost:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'

# Login to get JWT token
curl -X POST http://localhost:8000/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePassword123!"
  }'

# Verify token in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT username, email, is_active, created_at
   FROM users
   WHERE username = 'testuser';"
```

**Expected Result:**

- ✅ Registration returns user object with UUID
- ✅ Password is hashed (not stored in plaintext)
- ✅ Login returns JWT access token
- ✅ Token can be decoded and contains user_id
- ✅ User marked as active in database
- ✅ Webhook secret generated automatically

---

### Test 9.3: Settings Management - API Keys

**Objective:** Test API key encryption/decryption and storage

```bash
# Get JWT token first (from Test 9.2)
TOKEN="<your_jwt_token>"

# Get current settings
curl http://localhost:8000/api/v1/settings \
  -H "Authorization: Bearer $TOKEN"

# Update settings with API keys
curl -X PUT http://localhost:8000/api/v1/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "binance_api_key": "test_binance_key",
    "binance_api_secret": "test_binance_secret",
    "bybit_api_key": "test_bybit_key",
    "bybit_api_secret": "test_bybit_secret"
  }'

# Verify encrypted storage
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT username, encrypted_api_keys::text
   FROM users
   WHERE username = 'testuser';"

# Delete specific exchange keys
curl -X DELETE http://localhost:8000/api/v1/settings/keys/binance \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Result:**

- ✅ Settings endpoint requires authentication
- ✅ API keys encrypted before storage (not plaintext)
- ✅ Keys retrievable and decrypted correctly
- ✅ Individual exchange keys can be deleted
- ✅ Unauthorized requests return 401
- ✅ Invalid token returns 401

---

### Test 9.4: Dashboard API Endpoints

**Objective:** Test analytics and dashboard data endpoints

```bash
TOKEN="<your_jwt_token>"

# Get account summary (TVL + free USDT)
curl http://localhost:8000/api/v1/dashboard/account-summary \
  -H "Authorization: Bearer $TOKEN"

# Get PnL metrics
curl http://localhost:8000/api/v1/dashboard/pnl \
  -H "Authorization: Bearer $TOKEN"

# Get trading statistics
curl http://localhost:8000/api/v1/dashboard/stats \
  -H "Authorization: Bearer $TOKEN"

# Get active positions count
curl http://localhost:8000/api/v1/dashboard/active-groups-count \
  -H "Authorization: Bearer $TOKEN"

# Get comprehensive analytics
curl http://localhost:8000/api/v1/dashboard/analytics \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Result:**

- ✅ Account summary returns TVL and free USDT across exchanges
- ✅ PnL endpoint returns realized, unrealized, and total PnL
- ✅ Stats endpoint returns win rate, total trades, avg PnL
- ✅ Active count matches database query
- ✅ Analytics returns live metrics and performance data
- ✅ All endpoints return JSON format
- ✅ Response times < 500ms

---

### Test 9.5: Position Management API

**Objective:** Test position retrieval and management endpoints

```bash
TOKEN="<your_jwt_token>"
USER_ID="f937c6cb-f9f9-4d25-be19-db9bf596d7e1"

# Get all active positions
curl http://localhost:8000/api/v1/positions/active \
  -H "Authorization: Bearer $TOKEN"

# Get positions for specific user
curl http://localhost:8000/api/v1/positions/$USER_ID \
  -H "Authorization: Bearer $TOKEN"

# Get specific position group
GROUP_ID="<position_group_id>"
curl http://localhost:8000/api/v1/positions/$USER_ID/$GROUP_ID \
  -H "Authorization: Bearer $TOKEN"

# Get closed positions history
curl http://localhost:8000/api/v1/positions/$USER_ID/history \
  -H "Authorization: Bearer $TOKEN"

# Force close position
curl -X POST http://localhost:8000/api/v1/positions/$GROUP_ID/close \
  -H "Authorization: Bearer $TOKEN"

# Verify closure on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Active positions endpoint returns current positions
- ✅ Position details include DCA orders, TP settings, PnL
- ✅ History endpoint returns closed positions with realized PnL
- ✅ Force close creates market sell orders on exchange
- ✅ Position status changes to 'closing' then 'closed'
- ✅ Unauthorized access returns 401

---

### Test 9.6: Risk Management API

**Objective:** Test risk engine control endpoints

```bash
TOKEN="<your_jwt_token>"
GROUP_ID="<position_group_id>"

# Get risk engine status
curl http://localhost:8000/api/v1/risk/status \
  -H "Authorization: Bearer $TOKEN"

# Manually trigger risk evaluation
curl -X POST http://localhost:8000/api/v1/risk/run-evaluation \
  -H "Authorization: Bearer $TOKEN"

# Block position from risk engine
curl -X POST http://localhost:8000/api/v1/risk/$GROUP_ID/block \
  -H "Authorization: Bearer $TOKEN"

# Verify block in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_blocked, risk_eligible
   FROM position_groups
   WHERE id = '$GROUP_ID';"

# Unblock position
curl -X POST http://localhost:8000/api/v1/risk/$GROUP_ID/unblock \
  -H "Authorization: Bearer $TOKEN"

# Skip next evaluation for position
curl -X POST http://localhost:8000/api/v1/risk/$GROUP_ID/skip \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Result:**

- ✅ Status endpoint returns risk engine configuration
- ✅ Manual evaluation triggers risk engine cycle
- ✅ Block prevents risk engine from closing position
- ✅ Unblock removes restriction
- ✅ Skip sets skip_once flag correctly
- ✅ All actions logged in risk_actions table

---

### Test 9.7: Queue Management API

**Objective:** Test queue control endpoints

```bash
TOKEN="<your_jwt_token>"
SIGNAL_ID="<queued_signal_id>"

# Get all queued signals
curl http://localhost:8000/api/v1/queue/ \
  -H "Authorization: Bearer $TOKEN"

# Get queue history
curl http://localhost:8000/api/v1/queue/history \
  -H "Authorization: Bearer $TOKEN"

# Promote specific signal
curl -X POST http://localhost:8000/api/v1/queue/$SIGNAL_ID/promote \
  -H "Authorization: Bearer $TOKEN"

# Delete queued signal
curl -X DELETE http://localhost:8000/api/v1/queue/$SIGNAL_ID \
  -H "Authorization: Bearer $TOKEN"

# Force add signal (bypass pool limit)
curl -X POST http://localhost:8000/api/v1/queue/$SIGNAL_ID/force-add \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Result:**

- ✅ Queue endpoint returns all queued signals with priorities
- ✅ History shows promoted and cancelled signals
- ✅ Promote creates position group (if space available)
- ✅ Delete removes signal from queue
- ✅ Force-add bypasses pool capacity limit
- ✅ All operations update queue status correctly

---

### Test 9.8: DCA Configuration API

**Objective:** Test DCA configuration CRUD operations

```bash
TOKEN="<your_jwt_token>"

# Get all DCA configurations
curl http://localhost:8000/api/v1/dca-configs/ \
  -H "Authorization: Bearer $TOKEN"

# Create new DCA configuration
curl -X POST http://localhost:8000/api/v1/dca-configs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pair": "BNBUSDT",
    "timeframe": 60,
    "exchange": "binance",
    "entry_order_type": "LIMIT",
    "dca_levels": [
      {"gap_percent": 0, "weight_percent": 50, "tp_percent": 2},
      {"gap_percent": -2, "weight_percent": 30, "tp_percent": 3},
      {"gap_percent": -4, "weight_percent": 20, "tp_percent": 4}
    ],
    "tp_mode": "PER_LEG",
    "max_pyramids": 2
  }'

# Update existing configuration
CONFIG_ID="<config_id>"
curl -X PUT http://localhost:8000/api/v1/dca-configs/$CONFIG_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "max_pyramids": 3,
    "tp_mode": "HYBRID"
  }'

# Delete configuration
curl -X DELETE http://localhost:8000/api/v1/dca-configs/$CONFIG_ID \
  -H "Authorization: Bearer $TOKEN"

# Verify in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pair, exchange, tp_mode, max_pyramids
   FROM dca_configurations
   ORDER BY created_at DESC LIMIT 5;"
```

**Expected Result:**

- ✅ GET returns all user's DCA configurations
- ✅ POST creates new configuration with validation
- ✅ PUT updates specific fields
- ✅ DELETE removes configuration
- ✅ Validation prevents invalid configurations
- ✅ Duplicate pair/exchange/timeframe rejected

---

### Test 9.9: Webhook Signature Validation

**Objective:** Test HMAC signature validation for TradingView webhooks

```bash
USER_ID="f937c6cb-f9f9-4d25-be19-db9bf596d7e1"
SECRET="ecd78c38d5ec54b4cd892735d0423671"

# Valid webhook with correct signature
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id $USER_ID \
  --secret $SECRET \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92000.0 \
  --order-size 0.001

# Invalid webhook with wrong secret (should fail)
curl -X POST http://localhost:8000/api/v1/webhooks/$USER_ID/tradingview \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: invalid_signature" \
  -d '{
    "user_id": "'$USER_ID'",
    "secret": "wrong_secret",
    "tv": {
      "exchange": "binance",
      "symbol": "BTCUSDT",
      "action": "buy"
    }
  }'
```

**Expected Result:**

- ✅ Valid signature allows webhook processing
- ✅ Invalid signature returns 401 Unauthorized
- ✅ Missing signature header returns 401
- ✅ Tampered payload rejected
- ✅ Valid webhook creates position/queues signal

---

### Test 9.10: Rate Limiting

**Objective:** Verify rate limits protect against abuse

```bash
# Test registration rate limit (5/min)
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/v1/users/register \
    -H "Content-Type: application/json" \
    -d '{
      "username": "test'$i'",
      "email": "test'$i'@example.com",
      "password": "Password123!"
    }'
  echo ""
done

# Test login rate limit (10/min)
for i in {1..12}; do
  curl -X POST http://localhost:8000/api/v1/users/login \
    -H "Content-Type: application/json" \
    -d '{
      "username": "testuser",
      "password": "wrong_password"
    }'
  echo ""
done
```

**Expected Result:**

- ✅ First 5 registration attempts succeed
- ✅ 6th registration returns 429 Too Many Requests
- ✅ First 10 login attempts processed
- ✅ 11th+ login returns 429
- ✅ Rate limits reset after 60 seconds
- ✅ Response includes Retry-After header

---

## 🔥 TEST SUITE 10: BACKGROUND WORKERS & SERVICES (45 mins)

### Overview

Critical background services that run continuously must be tested to ensure they function correctly.

**Prerequisites:**
- Application running with background workers enabled
- Active positions with open orders
- Queued signals in database

---

### Test 10.1: Order Fill Monitor Service

**Objective:** Verify order fill monitoring updates positions automatically

```bash
# Create position with limit orders
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price <USE_LIVE_PRICE_0.1%_BELOW> \
  --order-size 0.001

# Monitor order status updates
watch -n 5 'docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT do.level, do.status, do.filled_quantity, do.avg_fill_price, do.filled_at
   FROM dca_orders do
   JOIN position_groups pg ON do.position_group_id = pg.id
   WHERE pg.symbol = '\''BTCUSDT'\''
   ORDER BY do.level;"'

# Check application logs for monitoring activity
docker compose logs -f app | grep "order_fill_monitor"
```

**Expected Result:**

- ✅ Background worker starts on application startup
- ✅ Orders checked every 5 seconds (configurable)
- ✅ Order status updates from OPEN → FILLED automatically
- ✅ filled_quantity and avg_fill_price populated
- ✅ filled_at timestamp recorded
- ✅ Position weighted_avg_entry recalculated
- ✅ TP orders created after fills
- ✅ Worker handles multiple users concurrently
- ✅ Worker survives exchange API errors gracefully

---

### Test 10.2: Queue Promotion Service (Auto-Promotion)

**Objective:** Verify automatic queue promotion when pool has space

**Note:** This test assumes the background queue promotion service is implemented.

```bash
# Fill pool to capacity (10/10)
# ... create 10 positions ...

# Add signals to queue
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol LINKUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 14.0 \
  --order-size 2.0

# Verify signal queued
docker compose exec app python3 scripts/list_queue.py

# Close a position to free space
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET status = 'closed', closed_at = NOW()
   WHERE symbol = 'BTCUSDT' AND exchange = 'binance'
   RETURNING symbol, status;"

# Wait 15 seconds for promotion service to run (polls every 10s)
sleep 15

# Check if signal auto-promoted
docker compose exec app python3 scripts/list_queue.py
docker compose exec app python3 scripts/verify_exchange_positions.py

# Check logs for promotion activity
docker compose logs -f app | grep "queue_manager"
```

**Expected Result:**

- ✅ Background worker starts on application startup
- ✅ Checks queue every 10 seconds (configurable)
- ✅ Detects when pool has available slots
- ✅ Promotes highest priority signal automatically
- ✅ Signal status changes from 'queued' to 'promoted'
- ✅ Position created on exchange
- ✅ promoted_at timestamp recorded
- ✅ Handles multiple queued signals correctly
- ✅ Respects priority rules during auto-promotion

---

### Test 10.3: Background Worker Restart Resilience

**Objective:** Verify workers resume correctly after application restart

```bash
# Create active positions and queue signals
# ... setup test data ...

# Check workers are running
docker compose logs app | grep -E "(order_fill_monitor|queue_manager)" | tail -20

# Restart application
docker compose restart app

# Wait for startup
sleep 10

# Verify workers resumed
docker compose logs app | grep -E "(order_fill_monitor|queue_manager)" | tail -20

# Verify workers continue functioning
docker compose exec app python3 scripts/monitor_all_tests.py
```

**Expected Result:**

- ✅ Workers start automatically on application startup
- ✅ No data loss during restart
- ✅ Workers resume monitoring existing orders
- ✅ Queue promotion continues after restart
- ✅ No duplicate worker instances created
- ✅ Logs show clean startup

---

## 🔥 TEST SUITE 11: SECURITY & MULTI-USER ISOLATION (30 mins)

### Overview

Test security features and ensure users cannot access each other's data.

---

### Test 11.1: Multi-User Data Isolation

**Objective:** Ensure users can only access their own data

```bash
# Create two users
USER1_TOKEN="<user1_jwt>"
USER2_TOKEN="<user2_jwt>"

# User 1 creates position
curl -X POST http://localhost:8000/api/v1/webhooks/user1_id/tradingview \
  -H "Content-Type: application/json" \
  -d '{ ... }'

# User 2 tries to access User 1's positions
curl http://localhost:8000/api/v1/positions/active \
  -H "Authorization: Bearer $USER2_TOKEN"

# Verify database isolation
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT user_id, COUNT(*) as position_count
   FROM position_groups
   GROUP BY user_id;"
```

**Expected Result:**

- ✅ User 2 cannot see User 1's positions
- ✅ Each user sees only their own data
- ✅ Attempting to access other user's resources returns 403
- ✅ Database queries filtered by user_id
- ✅ Queue signals isolated per user
- ✅ DCA configs isolated per user

---

### Test 11.2: API Key Encryption

**Objective:** Verify API keys are encrypted at rest

```bash
# Set API keys for user
TOKEN="<jwt_token>"
curl -X PUT http://localhost:8000/api/v1/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "binance_api_key": "my_secret_key_123",
    "binance_api_secret": "my_secret_secret_456"
  }'

# Check database storage (should be encrypted)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT username, encrypted_api_keys::text
   FROM users
   WHERE username = 'testuser';" | grep -i "my_secret"
```

**Expected Result:**

- ✅ Plaintext API keys NOT visible in database
- ✅ encrypted_api_keys field contains encrypted data
- ✅ Keys retrievable and decrypted correctly via API
- ✅ Encryption uses AES with secret key from environment
- ✅ Cannot decrypt without ENCRYPTION_KEY

---

### Test 11.3: JWT Token Expiration

**Objective:** Verify expired tokens are rejected

```bash
# Login and get token
TOKEN="<jwt_token>"

# Use token immediately (should work)
curl http://localhost:8000/api/v1/positions/active \
  -H "Authorization: Bearer $TOKEN"

# Wait for token expiration (if configured)
# Or manually create expired token for testing

# Try to use expired token
curl http://localhost:8000/api/v1/positions/active \
  -H "Authorization: Bearer <expired_token>"
```

**Expected Result:**

- ✅ Fresh tokens accepted
- ✅ Expired tokens return 401 Unauthorized
- ✅ Error message indicates token expired
- ✅ User must re-authenticate to get new token

---

## 🔥 TEST SUITE 12: ERROR HANDLING & EDGE CASES (45 mins)

### Overview

Test system behavior under error conditions and edge cases.

---

### Test 12.1: Exchange API Failures

**Objective:** Verify graceful handling of exchange errors

```bash
# Test with invalid API keys (should fail gracefully)
# ... temporarily set invalid keys ...

# Try to create position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92000.0 \
  --order-size 0.001

# Check error handling
docker compose logs app | tail -50
```

**Expected Result:**

- ✅ Position group created in database
- ✅ Order submission retries with exponential backoff
- ✅ After max retries, position marked as 'failed'
- ✅ Error logged with details
- ✅ User notified (if notification system exists)
- ✅ System continues functioning for other operations
- ✅ No crashes or unhandled exceptions

---

### Test 12.2: Insufficient Balance

**Objective:** Handle insufficient balance errors

```bash
# Create position with order size larger than balance
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92000.0 \
  --order-size 1000.0  # Unrealistically large

# Check error handling
docker compose logs app | grep -i "insufficient\|balance"
```

**Expected Result:**

- ✅ Exchange returns insufficient balance error
- ✅ Error caught and handled gracefully
- ✅ Position status updated to 'failed'
- ✅ Error message stored/logged
- ✅ No crash or data corruption

---

### Test 12.3: Invalid DCA Configuration

**Objective:** Validate DCA configuration before processing

```bash
TOKEN="<jwt_token>"

# Try to create invalid configuration (negative values)
curl -X POST http://localhost:8000/api/v1/dca-configs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pair": "BTCUSDT",
    "exchange": "binance",
    "dca_levels": [
      {"gap_percent": 0, "weight_percent": -50, "tp_percent": 2}
    ]
  }'

# Try duplicate configuration
curl -X POST http://localhost:8000/api/v1/dca-configs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pair": "BTCUSDT",
    "exchange": "binance",
    "timeframe": 60,
    "dca_levels": [...]
  }'
```

**Expected Result:**

- ✅ Validation errors return 422 Unprocessable Entity
- ✅ Error messages clearly explain validation failures
- ✅ Negative values rejected
- ✅ Duplicate pair/exchange/timeframe rejected
- ✅ Missing required fields rejected
- ✅ Invalid enum values rejected (e.g., invalid tp_mode)

---

### Test 12.4: Database Connection Loss

**Objective:** Handle database disconnections gracefully

```bash
# Create position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92000.0 \
  --order-size 0.001

# Stop database temporarily
docker compose stop db

# Try to create another position (should fail gracefully)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3200.0 \
  --order-size 0.01

# Restart database
docker compose start db

# Verify system recovers
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Operations during db downtime return 503 Service Unavailable
- ✅ Application doesn't crash
- ✅ Connection pool handles reconnection
- ✅ System resumes normal operation after db recovery
- ✅ No data corruption

---

### Test 12.5: Different TP Modes Validation

**Objective:** Thoroughly test all TP modes (per_leg, aggregate, hybrid)

```bash
# Create position with PER_LEG TP mode
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.03 \
  --order-size 10

# Wait for fills, check TP orders created
sleep 60
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pg.symbol, pg.tp_mode, tpo.tp_percent, tpo.quantity, tpo.tp_price
   FROM take_profit_orders tpo
   JOIN position_groups pg ON tpo.position_group_id = pg.id
   WHERE pg.symbol = 'XRPUSDT'
   ORDER BY tpo.tp_percent;"

# Repeat for AGGREGATE mode (use ETHUSDT)
# Repeat for HYBRID mode (use BNBUSDT if configured)

# Verify TP calculation differences
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ **PER_LEG**: Each DCA leg has independent TP order
- ✅ **AGGREGATE**: Single TP at weighted average entry + target%
- ✅ **HYBRID**: Mix of per-leg and aggregate TPs
- ✅ TP quantities calculated correctly for each mode
- ✅ TP prices calculated correctly based on mode
- ✅ Exchange shows correct TP orders

---

## 📊 UPDATED TEST RESULTS TEMPLATE

Update the test results template to include new test suites:

```markdown
### TEST SUITE 9: API Endpoints & Authentication
- [ ] Test 9.1: Health Check Endpoints - ✅ PASS / ❌ FAIL
- [ ] Test 9.2: User Registration & Login - ✅ PASS / ❌ FAIL
- [ ] Test 9.3: Settings Management - API Keys - ✅ PASS / ❌ FAIL
- [ ] Test 9.4: Dashboard API Endpoints - ✅ PASS / ❌ FAIL
- [ ] Test 9.5: Position Management API - ✅ PASS / ❌ FAIL
- [ ] Test 9.6: Risk Management API - ✅ PASS / ❌ FAIL
- [ ] Test 9.7: Queue Management API - ✅ PASS / ❌ FAIL
- [ ] Test 9.8: DCA Configuration API - ✅ PASS / ❌ FAIL
- [ ] Test 9.9: Webhook Signature Validation - ✅ PASS / ❌ FAIL
- [ ] Test 9.10: Rate Limiting - ✅ PASS / ❌ FAIL

### TEST SUITE 10: Background Workers & Services
- [ ] Test 10.1: Order Fill Monitor Service - ✅ PASS / ❌ FAIL
- [ ] Test 10.2: Queue Promotion Service - ✅ PASS / ❌ FAIL
- [ ] Test 10.3: Background Worker Restart Resilience - ✅ PASS / ❌ FAIL

### TEST SUITE 11: Security & Multi-User Isolation
- [ ] Test 11.1: Multi-User Data Isolation - ✅ PASS / ❌ FAIL
- [ ] Test 11.2: API Key Encryption - ✅ PASS / ❌ FAIL
- [ ] Test 11.3: JWT Token Expiration - ✅ PASS / ❌ FAIL

### TEST SUITE 12: Error Handling & Edge Cases
- [ ] Test 12.1: Exchange API Failures - ✅ PASS / ❌ FAIL
- [ ] Test 12.2: Insufficient Balance - ✅ PASS / ❌ FAIL
- [ ] Test 12.3: Invalid DCA Configuration - ✅ PASS / ❌ FAIL
- [ ] Test 12.4: Database Connection Loss - ✅ PASS / ❌ FAIL
- [ ] Test 12.5: Different TP Modes Validation - ✅ PASS / ❌ FAIL
```

---

## 🎯 UPDATED SUCCESS CRITERIA

**Additional Success Criteria:**

**API & Authentication:**
- ✅ All API endpoints return correct status codes
- ✅ Authentication and authorization work correctly
- ✅ JWT tokens validated properly
- ✅ API keys encrypted at rest
- ✅ Rate limiting protects against abuse
- ✅ HMAC signature validation prevents unauthorized webhooks

**Background Services:**
- ✅ Order fill monitor updates order status automatically
- ✅ Queue promotion service promotes signals when space available
- ✅ Workers survive application restarts
- ✅ Workers handle errors gracefully without crashing

**Security:**
- ✅ Multi-user data isolation enforced
- ✅ Users cannot access other users' data
- ✅ Sensitive data encrypted in database
- ✅ Invalid/expired tokens rejected

**Error Handling:**
- ✅ Exchange API failures handled gracefully
- ✅ Insufficient balance errors caught and logged
- ✅ Invalid configurations rejected with clear errors
- ✅ Database connection issues don't crash application
- ✅ All TP modes (per_leg, aggregate, hybrid) work correctly

**Coverage:**
- ✅ **95%+ of application components tested**
- ✅ All critical paths covered
- ✅ Edge cases and error scenarios tested

---

## 📝 NOTES

### General Testing Notes
- Use the 8 available testing scripts (5 core + 3 queue scripts)
- All webhook simulations use the provided user credentials
- Check both Bybit and Binance testnets
- Verify exchange state matches GUI and database
- Test with realistic market prices (check current prices first)

### Queue Priority Testing Notes
- **20 DCA configurations required** for comprehensive queue testing
- Pool must be at 10/10 capacity to test queuing behavior
- Priority scores range from 1,000 to 10,000,000+ based on tier
- Manual promotion currently required (no automatic background processor)
- See **QUEUE_PRIORITY_TEST_RESULTS.md** for detailed test results
- Use `monitor_all_tests.py` for comprehensive system visibility

### Available Documentation
- `COMPREHENSIVE_TEST_PLAN.md` - This file (100% practical test procedures)
- `QUEUE_PRIORITY_TEST_RESULTS.md` - Detailed queue priority test results
- `TESTING_SUMMARY.md` - Executive summary of completed testing

---

**Good luck with testing! 🚀**

---

## 🔥 TEST SUITE 13: TELEGRAM NOTIFICATION SYSTEM (60 mins)

### Overview

The Telegram notification system provides comprehensive, smart notifications for all position lifecycle events. This test suite covers all 8 message types and their configuration options.

**Prerequisites:**
- Telegram bot token and channel configured
- Active positions for testing
- Risk engine enabled

---

### Test 13.1: Telegram Configuration API

**Objective:** Test Telegram configuration CRUD via API

```bash
TOKEN="<jwt_token>"

# Get current Telegram config
curl http://localhost:8000/api/v1/telegram/config \
  -H "Authorization: Bearer $TOKEN"

# Update Telegram configuration
curl -X PUT http://localhost:8000/api/v1/telegram/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "channel_id": "@test_channel",
    "channel_name": "Test Signals",
    "send_entry_signals": true,
    "send_exit_signals": true,
    "send_status_updates": true,
    "send_dca_fill_updates": true,
    "send_pyramid_updates": true,
    "send_tp_hit_updates": true,
    "send_failure_alerts": true,
    "send_risk_alerts": true,
    "update_existing_message": true,
    "show_unrealized_pnl": true,
    "show_invested_amount": true,
    "show_duration": true,
    "test_mode": true
  }'

# Verify config stored in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT telegram_config
   FROM users
   WHERE id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1';"
```

**Expected Result:**

- ✅ GET returns current configuration
- ✅ PUT updates configuration successfully
- ✅ All 20+ fields stored correctly
- ✅ Config persists after refresh
- ✅ Default values applied for missing fields

---

### Test 13.2: Telegram Connection Test

**Objective:** Test bot connection verification

```bash
TOKEN="<jwt_token>"

# Test connection to Telegram bot
curl -X POST http://localhost:8000/api/v1/telegram/test-connection \
  -H "Authorization: Bearer $TOKEN"

# Send test message
curl -X POST http://localhost:8000/api/v1/telegram/test-message \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Result:**

- ✅ Test connection returns bot info if successful
- ✅ Invalid token returns error with details
- ✅ Test message sent to configured channel
- ✅ Message format matches expected template

---

### Test 13.3: Entry Signal Notification

**Objective:** Verify entry signal broadcast with all context

```bash
# Create position with Telegram enabled
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92000.0 \
  --order-size 0.001

# Check Telegram channel for message
# Check database for telegram_message_id
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, telegram_message_id, status
   FROM position_groups
   WHERE symbol = 'BTCUSDT'
   ORDER BY created_at DESC LIMIT 1;"
```

**Expected Result:**

- ✅ Entry signal message sent to Telegram
- ✅ Message includes: 🆔 Position ID, symbol, exchange, timeframe
- ✅ DCA levels displayed with status (✅/⏳)
- ✅ TP mode displayed correctly (per_leg, aggregate, hybrid, pyramid_aggregate)
- ✅ Pyramid count shown (e.g., "🔷 Pyramid 1/5")
- ✅ Invested amount shown (if enabled)
- ✅ telegram_message_id stored in database

---

### Test 13.4: DCA Fill Update Notification

**Objective:** Verify DCA leg fill broadcasts

```bash
# Wait for DCA order to fill (use live price or market order)
# Monitor fills
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT do.leg_index, do.status, do.filled_quantity, do.avg_fill_price
   FROM dca_orders do
   JOIN position_groups pg ON do.group_id = pg.id
   WHERE pg.symbol = 'BTCUSDT'
   ORDER BY do.leg_index;"

# Check Telegram channel for DCA fill message
```

**Expected Result:**

- ✅ DCA fill notification sent when order fills
- ✅ Message includes: leg number, fill price, quantity
- ✅ Progress shown (e.g., "Filled: 2/3 legs (70%)")
- ✅ Avg entry and invested amount updated
- ✅ Message updates existing entry message (if update_existing_message=true)

---

### Test 13.5: Status Change Notification

**Objective:** Verify status transition broadcasts

```bash
# Verify status transitions trigger notifications
# LIVE → PARTIALLY_FILLED → ACTIVE

# Check position status history
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, updated_at
   FROM position_groups
   WHERE symbol = 'BTCUSDT'
   ORDER BY created_at DESC LIMIT 1;"
```

**Expected Result:**

- ✅ Status change notification sent on transition
- ✅ Shows old status → new status
- ✅ Position summary included (filled legs, avg entry)
- ✅ Time to fill shown (for PARTIALLY_FILLED → ACTIVE)

---

### Test 13.6: Pyramid Added Notification

**Objective:** Verify new pyramid broadcasts

```bash
# Add pyramid to existing position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 91000.0 \
  --order-size 0.001

# Check Telegram for pyramid notification
```

**Expected Result:**

- ✅ Pyramid added notification sent
- ✅ Shows new pyramid DCA levels
- ✅ Total pyramids displayed (e.g., "📊 Total pyramids: 2/5")
- ✅ Previous pyramid invested amount shown
- ✅ New TP target shown (for pyramid_aggregate mode)

---

### Test 13.7: Take-Profit Hit Notification

**Objective:** Verify TP hit broadcasts for different modes

```bash
# Wait for TP order to fill
# Or manually trigger TP for testing

# Check Telegram for TP hit message

# Verify for each TP mode:
# - PER_LEG: Individual leg TP hit
# - AGGREGATE: Full position TP hit
# - PYRAMID_AGGREGATE: Pyramid-level TP hit
# - HYBRID: Combination TP hit
```

**Expected Result:**

- ✅ TP hit notification sent when order fills
- ✅ **PER_LEG**: Shows leg entry, exit, profit %, remaining legs
- ✅ **AGGREGATE**: Shows avg entry, exit, total profit
- ✅ **PYRAMID_AGGREGATE**: Shows pyramid-specific TP, remaining pyramids
- ✅ Duration shown for closed legs/pyramids

---

### Test 13.8: Risk Alert Notifications

**Objective:** Verify risk engine event broadcasts

```bash
# Create losing position to trigger risk timer
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 4000.0 \
  --order-size 0.01

# Wait for risk timer to start (when required pyramids filled + loss threshold)

# Check Telegram for risk alerts:
# - Timer started
# - Timer expired
# - Offset executed (if applicable)
```

**Expected Result:**

- ✅ **Timer Started**: Shows loss %, countdown time, position info
- ✅ **Timer Expired**: Shows loss persisted, offset pending message
- ✅ **Offset Executed**: Shows entry/exit, loss, offset details, net result
- ✅ Risk alerts sent even during quiet hours (urgent)

---

### Test 13.9: Failure Alert Notification

**Objective:** Verify failure/error broadcasts

```bash
# Trigger an order failure (e.g., insufficient balance)
# Check Telegram for failure alert
```

**Expected Result:**

- ✅ Failure alert sent with error details
- ✅ Shows failed order info (price, qty, value)
- ✅ Actionable suggestion included
- ✅ Failure alerts sent even during quiet hours (urgent)

---

### Test 13.10: Exit Signal Notification

**Objective:** Verify position close broadcasts

```bash
# Close position (manual or TP/risk triggered)
curl -X POST http://localhost:8000/api/v1/positions/<GROUP_ID>/close \
  -H "Authorization: Bearer $TOKEN"

# Check Telegram for exit message
```

**Expected Result:**

- ✅ Exit signal sent with trade summary
- ✅ Shows entry, exit, profit/loss %, USD amount
- ✅ Position stats (pyramids used, DCA legs, TP mode)
- ✅ Duration shown
- ✅ Exit reason included (engine close, TP hit, manual, etc.)

---

### Test 13.11: Message Toggle Tests

**Objective:** Verify individual message type toggles work

```bash
TOKEN="<jwt_token>"

# Disable DCA fill updates
curl -X PUT http://localhost:8000/api/v1/telegram/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "send_dca_fill_updates": false
  }'

# Create position and verify NO DCA fill messages sent
# Re-enable and verify messages resume
```

**Expected Result:**

- ✅ Disabled message types not sent
- ✅ Other message types still work
- ✅ Toggle changes apply immediately
- ✅ All 8 toggles work independently

---

### Test 13.12: Quiet Hours Functionality

**Objective:** Verify quiet hours suppress non-urgent notifications

```bash
TOKEN="<jwt_token>"

# Enable quiet hours (current time within window)
curl -X PUT http://localhost:8000/api/v1/telegram/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "quiet_hours_enabled": true,
    "quiet_hours_start": "00:00",
    "quiet_hours_end": "23:59",
    "quiet_hours_urgent_only": true
  }'

# Create position - entry signal should NOT be sent
# Trigger failure - failure alert SHOULD be sent (urgent)
```

**Expected Result:**

- ✅ Non-urgent messages blocked during quiet hours
- ✅ Urgent messages (failures, risk alerts) still sent
- ✅ Quiet hours respect configured start/end times
- ✅ quiet_hours_urgent_only toggle works correctly

---

### Test 13.13: Threshold Alerts

**Objective:** Verify profit/loss threshold alerts

```bash
TOKEN="<jwt_token>"

# Set threshold alerts
curl -X PUT http://localhost:8000/api/v1/telegram/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_loss_threshold_percent": 5.0,
    "alert_profit_threshold_percent": 10.0
  }'

# Create position with loss > 5%
# Verify threshold alert sent

# Create position with profit > 10%
# Verify threshold alert sent
```

**Expected Result:**

- ✅ Loss threshold alert sent when loss exceeds configured %
- ✅ Profit threshold alert sent when profit exceeds configured %
- ✅ Threshold alerts work in addition to regular updates
- ✅ Null thresholds disable threshold alerts

---

### Test 13.14: Test Mode

**Objective:** Verify test mode logs without sending

```bash
TOKEN="<jwt_token>"

# Enable test mode
curl -X PUT http://localhost:8000/api/v1/telegram/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "test_mode": true
  }'

# Create position
# Check application logs for message content (not actually sent)
docker compose logs app | grep "telegram" | tail -20
```

**Expected Result:**

- ✅ Messages logged to console/log file
- ✅ Messages NOT sent to Telegram channel
- ✅ Message content visible in logs
- ✅ Useful for debugging message formatting

---

### Test 13.15: Message Update vs New Message

**Objective:** Verify message consolidation behavior

```bash
TOKEN="<jwt_token>"

# Enable update existing message
curl -X PUT http://localhost:8000/api/v1/telegram/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "update_existing_message": true,
    "update_on_pyramid": true
  }'

# Create position - check original message
# Wait for DCA fill - verify SAME message updated (not new message)
# Add pyramid - verify message updated

# Disable update_existing_message and repeat
# Verify NEW messages sent for each event
```

**Expected Result:**

- ✅ update_existing_message=true: Same message edited
- ✅ update_existing_message=false: New message for each event
- ✅ update_on_pyramid: Pyramid adds update existing or new based on setting
- ✅ Reduces channel spam with consolidation
- ✅ telegram_message_id tracks the main position message

---

## 🔥 TEST SUITE 14: FRONTEND UI TESTING (90 mins)

### Overview

This test suite covers frontend component testing across all pages. Tests should be executed in a browser or via automated UI testing framework.

**Prerequisites:**
- Frontend running at http://localhost:3000
- Backend API accessible
- Authenticated user session

---

### Test 14.1: Dashboard Page

**Objective:** Verify all dashboard components render and update correctly

**Test Steps:**

1. Navigate to `/dashboard`
2. Verify all status indicators display:
   - Engine status (running/stopped)
   - Risk engine status (active/inactive)
   - Queue status (running/paused/stopped)
3. Verify PnL metrics update:
   - Total PnL with trend indicator
   - Today's PnL
   - Win rate with win/loss counts
4. Verify capital section:
   - TVL displayed correctly
   - Free USDT balance
   - Deployment percentage
5. Test control buttons:
   - Start/Stop Queue
   - Sync Exchange
6. Verify live polling (data refreshes every 5 seconds)
7. Test keyboard shortcuts (R for refresh)

**Expected Result:**

- ✅ All metrics display correctly
- ✅ Status indicators reflect current state
- ✅ Data updates every 5 seconds
- ✅ Controls work as expected
- ✅ Mobile responsive layout works

---

### Test 14.2: Settings Page - Trading Tab

**Objective:** Verify trading settings functionality

**Test Steps:**

1. Navigate to `/settings`
2. Select "Trading" tab
3. Test active exchange selection
4. Test API key management:
   - Add new exchange keys
   - Edit existing keys
   - Delete keys
5. Test DCA configuration management:
   - Create new config
   - Edit existing config
   - Delete config
6. Verify form validation errors

**Expected Result:**

- ✅ Exchange selection persists
- ✅ API keys encrypted and stored
- ✅ DCA configs CRUD works
- ✅ Validation errors display clearly
- ✅ Success notifications shown

---

### Test 14.3: Settings Page - Risk Tab

**Objective:** Verify risk settings functionality

**Test Steps:**

1. Navigate to `/settings`
2. Select "Risk" tab
3. Test risk limit fields:
   - Max open positions (global)
   - Max positions per symbol
   - Max total exposure (USD)
   - Loss limit (circuit breaker)
4. Test queue priority settings:
   - Toggle each rule enabled/disabled
   - Drag-and-drop reordering
5. Test timer configuration fields

**Expected Result:**

- ✅ All fields validate correctly
- ✅ Priority rules drag-and-drop works
- ✅ At least one priority rule must be enabled
- ✅ Settings persist after save
- ✅ Changes reflected in backend

---

### Test 14.4: Settings Page - Alerts Tab (Telegram)

**Objective:** Verify Telegram configuration UI

**Test Steps:**

1. Navigate to `/settings`
2. Select "Alerts" tab
3. Test connection fields:
   - Bot token input
   - Channel ID input
   - Channel name input
4. Test message type toggles (8 toggles)
5. Test advanced controls (4 toggles)
6. Test threshold alerts:
   - Loss threshold %
   - Profit threshold %
7. Test quiet hours:
   - Enable/disable toggle
   - Start/end time pickers
   - Urgent only toggle
8. Test connection button
9. Test send test message button

**Expected Result:**

- ✅ All 20+ fields save correctly
- ✅ Toggles persist state
- ✅ Test connection shows result
- ✅ Test message sends successfully
- ✅ Form validation works
- ✅ Settings persist after refresh

---

### Test 14.5: Settings Page - Account Tab

**Objective:** Verify account settings functionality

**Test Steps:**

1. Navigate to `/settings`
2. Select "Account" tab
3. Verify username/email display
4. Test webhook URL copy functionality
5. Test backup export
6. Test configuration restore from file

**Expected Result:**

- ✅ Account info displays correctly
- ✅ Webhook URL copyable
- ✅ Backup exports valid JSON
- ✅ Restore parses uploaded file

---

### Test 14.6: Positions Page

**Objective:** Verify positions display and management

**Test Steps:**

1. Navigate to `/positions`
2. Test "Active" tab:
   - Position cards display
   - PnL calculations correct
   - Pyramid details expandable
   - DCA legs status shown
3. Test "History" tab:
   - Closed positions display
   - Realized PnL shown
4. Test position metrics cards
5. Test force close functionality (if available)

**Expected Result:**

- ✅ Active positions display correctly
- ✅ History shows closed positions
- ✅ Metrics calculate accurately
- ✅ Expandable details work
- ✅ Mobile responsive

---

### Test 14.7: Queue Page

**Objective:** Verify queue management UI

**Test Steps:**

1. Navigate to `/queue`
2. Verify queued signals display
3. Test promote signal action
4. Test remove signal action
5. Verify priority score breakdown displays
6. Test queue history tab

**Expected Result:**

- ✅ Queued signals display with all info
- ✅ Priority scores shown correctly
- ✅ Promote action works
- ✅ Remove action works
- ✅ History displays processed signals

---

### Test 14.8: Risk Page

**Objective:** Verify risk management UI

**Test Steps:**

1. Navigate to `/risk`
2. Verify identified loser display
3. Verify available winners display
4. Verify projected offset plan
5. Test at-risk positions list
6. Test timeline of recent actions
7. Test control buttons:
   - Run evaluation
   - Force start/stop
   - Block/unblock position
   - Skip position

**Expected Result:**

- ✅ Risk status displays correctly
- ✅ Offset plan calculated
- ✅ Control buttons work
- ✅ Timeline shows actions
- ✅ Updates in real-time

---

### Test 14.9: Analytics Page

**Objective:** Verify analytics and charts functionality

**Test Steps:**

1. Navigate to `/analytics`
2. Test time range selector (24h, 7d, 30d, all)
3. Verify key metrics cards:
   - Total PnL
   - Win rate
   - Profit factor
   - Avg hold time
4. Verify equity curve chart renders
5. Verify performance summary
6. Verify pair performance table
7. Verify PnL by day of week chart
8. Test CSV export (both full trades and summary)
9. Test pull-to-refresh on mobile

**Expected Result:**

- ✅ Time range filter works
- ✅ Metrics calculate correctly
- ✅ Charts render properly
- ✅ Tables display data
- ✅ CSV export downloads valid file
- ✅ Mobile responsive

---

### Test 14.10: Authentication Flow

**Objective:** Verify login/logout and token management

**Test Steps:**

1. Navigate to `/login` (unauthenticated)
2. Test login with valid credentials
3. Verify redirect to dashboard
4. Verify token stored in localStorage
5. Test logout functionality
6. Verify redirect to login
7. Test protected route access (without token)
8. Test token expiration handling

**Expected Result:**

- ✅ Login works with valid credentials
- ✅ Invalid credentials show error
- ✅ Token stored correctly
- ✅ Logout clears token
- ✅ Protected routes redirect to login
- ✅ Expired tokens trigger re-auth

---

### Test 14.11: Mobile Responsiveness

**Objective:** Verify mobile-friendly UI across all pages

**Test Steps:**

1. Use browser dev tools or mobile device
2. Test each page at mobile viewport:
   - Dashboard
   - Settings (all tabs)
   - Positions
   - Queue
   - Risk
   - Analytics
3. Verify bottom navigation works
4. Test pull-to-refresh gesture
5. Verify modals/dialogs work on mobile

**Expected Result:**

- ✅ All pages render correctly on mobile
- ✅ Bottom navigation visible
- ✅ Pull-to-refresh works
- ✅ Forms usable on mobile
- ✅ Tables/charts responsive

---

### Test 14.12: Error States and Loading

**Objective:** Verify error handling and loading states in UI

**Test Steps:**

1. Disconnect backend and test error states
2. Verify loading skeletons display during fetch
3. Test error banners/toasts
4. Verify empty states (no data scenarios)
5. Test API error response handling

**Expected Result:**

- ✅ Loading skeletons display during fetch
- ✅ Error messages display clearly
- ✅ Empty states show helpful message
- ✅ Network errors handled gracefully
- ✅ Retry mechanisms work

---

## 🔥 TEST SUITE 15: EXIT SIGNALS & POSITION CLOSURE (45 mins) ⭐ NEW

### Overview

This test suite covers all position closure scenarios including:
- Exit signals from TradingView
- Manual position closure via API/UI
- Take-profit triggered closures
- Risk engine forced closures

**Prerequisites:**
- Active positions on exchanges
- DCA orders filled (for TP testing)
- Risk engine configured

---

### Test 15.1: Exit Signal - Close All Position Orders

**Objective:** Verify exit signal closes position and cancels all orders

```bash
# Create a position first
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92000.0 \
  --order-size 0.001

# Wait for orders to be placed
sleep 5

# Verify position exists
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, pyramid_count FROM position_groups WHERE symbol = 'BTCUSDT' AND status = 'live';"

# Send EXIT signal (action=sell for long position)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action sell \
  --entry-price 92500.0 \
  --order-size 0.001

# Verify position closed
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, closed_at, close_reason FROM position_groups WHERE symbol = 'BTCUSDT' ORDER BY created_at DESC LIMIT 1;"

# Verify orders cancelled on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Position status changed to 'closing' then 'closed'
- ✅ All open DCA orders cancelled on exchange
- ✅ close_reason set to 'exit_signal'
- ✅ closed_at timestamp recorded
- ✅ Exchange shows no open orders for this position
- ✅ Telegram notification sent (if enabled)

---

### Test 15.2: Exit Signal with Partial Fills

**Objective:** Verify exit signal handles partially filled positions

```bash
# Create position with multiple DCA levels
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3200.0 \
  --order-size 0.02

# Wait for some orders to fill (may need to adjust entry price for fills)
sleep 60

# Check fill status
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT do.leg_index, do.status, do.filled_quantity
   FROM dca_orders do
   JOIN position_groups pg ON do.group_id = pg.id
   WHERE pg.symbol = 'ETHUSDT' AND pg.status = 'live'
   ORDER BY do.leg_index;"

# Send exit signal
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action sell \
  --entry-price 3250.0 \
  --order-size 0.02

# Verify filled quantity sold, unfilled orders cancelled
docker compose exec app python3 scripts/verify_exchange_positions.py

# Check realized PnL calculated
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, realized_pnl_usd, total_filled_quantity, status
   FROM position_groups WHERE symbol = 'ETHUSDT' ORDER BY created_at DESC LIMIT 1;"
```

**Expected Result:**

- ✅ Filled DCA orders result in market sell order
- ✅ Unfilled DCA orders cancelled (not sold)
- ✅ Realized PnL calculated from filled portion only
- ✅ Position marked as closed
- ✅ No orphaned orders on exchange

---

### Test 15.3: Manual Close via API

**Objective:** Test position closure through API endpoint

```bash
TOKEN="<your_jwt_token>"

# Create position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.00 \
  --order-size 20

# Get position group ID
GROUP_ID=$(docker compose exec db psql -U tv_user -d tv_engine_db -t -c \
  "SELECT id FROM position_groups WHERE symbol = 'XRPUSDT' AND status = 'live' LIMIT 1;" | tr -d ' ')

# Close via API
curl -X POST "http://localhost:8000/api/v1/positions/$GROUP_ID/close" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Verify closure
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, close_reason FROM position_groups WHERE id = '$GROUP_ID';"
```

**Expected Result:**

- ✅ API returns success response
- ✅ Position status changes to 'closing' then 'closed'
- ✅ close_reason set to 'manual_close'
- ✅ All orders cancelled on exchange
- ✅ Telegram notification sent (if enabled)

---

## 🔥 TEST SUITE 16: TAKE-PROFIT EXECUTION (60 mins) ⭐ NEW

### Overview

This test suite verifies Take-Profit order creation and execution for all 4 TP modes.

**Prerequisites:**
- Live prices from fetch_live_prices.py
- Understanding of each TP mode behavior

**Fill Strategies Used:**
1. **Market Orders (Instant Fill)**: Use ETH, ADA, TRX, LINK - configured with `entry_order_type: market`
2. **Bracket Strategy (5-10 min fill)**: Use entry price 0.1% below current market for quick fills

---

### Test 16.1: Per-Leg TP Mode - Individual TP Orders

**Objective:** Verify each DCA leg has independent TP order

**Fill Strategy:** Use ADAUSDT (market order config) for instant first-leg fill

```bash
# STEP 1: Get current ADA price
docker compose exec app python3 scripts/fetch_live_prices.py

# STEP 2: Create position - ADA has market order for leg 0 (instant fill)
# Use exact current price for market order fill
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.90 \
  --order-size 100

# First leg fills INSTANTLY via market order
sleep 5

# Check TP orders created for filled DCA leg
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    do.leg_index,
    do.status as dca_status,
    do.fill_price,
    do.tp_percent,
    do.tp_price,
    CASE
      WHEN do.fill_price IS NOT NULL
      THEN ROUND(do.fill_price * (1 + do.tp_percent/100), 4)
      ELSE NULL
    END as expected_tp_price
   FROM dca_orders do
   JOIN position_groups pg ON do.group_id = pg.id
   WHERE pg.symbol = 'ADAUSDT' AND pg.status = 'live'
   ORDER BY do.leg_index;"

# Verify TP orders on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Leg 0 fills instantly (market order)
- ✅ TP order created for filled leg
- ✅ TP price calculated from FILL PRICE (not entry price)
- ✅ TP order visible on exchange as limit sell order
- ✅ Unfilled DCA legs have no TP orders yet

---

### Test 16.2: Aggregate TP Mode - Single TP Order

**Objective:** Verify aggregate TP uses weighted average entry

**Fill Strategy:** Use ETHUSDT (market order config) for instant first-leg fill

```bash
# STEP 1: Get current ETH price
docker compose exec app python3 scripts/fetch_live_prices.py

# STEP 2: Create position - ETH has market order for leg 0 (instant fill)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.02

# First leg fills INSTANTLY via market order
sleep 5

# Check weighted average entry and aggregate TP
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    pg.symbol,
    pg.weighted_avg_entry,
    pg.tp_aggregate_percent,
    ROUND(pg.weighted_avg_entry * (1 + pg.tp_aggregate_percent/100), 2) as expected_tp_price,
    pg.total_filled_quantity
   FROM position_groups pg
   WHERE pg.symbol = 'ETHUSDT' AND pg.status = 'live';"

# Verify single TP order on exchange (not multiple per-leg TPs)
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Leg 0 fills instantly (market order)
- ✅ Single aggregate TP order created (not per-leg)
- ✅ TP price based on weighted_avg_entry + tp_aggregate_percent
- ✅ TP quantity = sum of all filled quantities

---

### Test 16.3: Pyramid Aggregate TP Mode - Multi-Pyramid Weighted Average

**Objective:** Verify pyramid_aggregate TP mode calculates weighted average across ALL pyramids

**Fill Strategy:** Use TRXUSDT (market order config) for instant fills on both pyramids

```bash
# First, check which pairs are configured with pyramid_aggregate TP mode
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pair, exchange, tp_mode, max_pyramids
   FROM dca_configurations
   WHERE tp_mode = 'pyramid_aggregate';"

# If none configured, temporarily update TRX for testing (has market orders):
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE dca_configurations SET tp_mode = 'pyramid_aggregate'
   WHERE pair = 'TRX/USDT' AND exchange = 'binance' RETURNING pair, tp_mode;"

# STEP 1: Get current TRX price
docker compose exec app python3 scripts/fetch_live_prices.py

# STEP 2: Create position with first pyramid - TRX has market order (instant fill)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.26 \
  --order-size 200

# First pyramid leg 0 fills INSTANTLY via market order
sleep 5

# Check weighted average after first pyramid
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count, weighted_avg_entry, tp_mode
   FROM position_groups WHERE symbol = 'TRXUSDT' AND status = 'live';"

# STEP 3: Add second pyramid at lower price (wait 30 sec between signals)
sleep 30
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.25 \
  --order-size 250

# Second pyramid leg 0 fills INSTANTLY via market order
sleep 5

# Check weighted average NOW INCLUDES BOTH PYRAMIDS
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    pg.symbol,
    pg.pyramid_count,
    pg.weighted_avg_entry as combined_avg,
    pg.tp_aggregate_percent,
    ROUND(pg.weighted_avg_entry * (1 + pg.tp_aggregate_percent/100), 4) as tp_target
   FROM position_groups pg
   WHERE pg.symbol = 'TRXUSDT' AND pg.status = 'live';"

# View individual pyramid entries for comparison
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    p.pyramid_index,
    p.entry_price as pyramid_entry,
    p.status
   FROM pyramids p
   JOIN position_groups pg ON p.group_id = pg.id
   WHERE pg.symbol = 'TRXUSDT' AND pg.status = 'live'
   ORDER BY p.pyramid_index;"

# Verify single aggregate TP order on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ tp_mode = 'pyramid_aggregate' for position
- ✅ weighted_avg_entry includes fills from ALL pyramids
- ✅ Pyramid 1 at $0.26 + Pyramid 2 at $0.25 = lower combined average (~$0.255)
- ✅ Single TP order based on combined weighted average
- ✅ TP order quantity = total filled across all pyramids
- ✅ When new pyramid added, weighted avg recalculated
- ✅ TP order updated with new combined average

**Key Difference from Regular Aggregate:**

- Regular `aggregate`: TP based on weighted avg of DCA levels within ONE pyramid
- `pyramid_aggregate`: TP based on weighted avg across ALL pyramids (entire position)

---

### Test 16.4: Hybrid TP Mode - Per-Leg AND Aggregate

**Objective:** Verify hybrid mode runs both TP systems simultaneously

**Fill Strategy:** Use LINKUSDT (market order config) for instant first-leg fill

```bash
# STEP 1: Check for hybrid TP mode configurations
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pair, exchange, tp_mode FROM dca_configurations WHERE tp_mode = 'hybrid';"

# If none configured, temporarily update LINK for testing (has market orders):
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE dca_configurations SET tp_mode = 'hybrid'
   WHERE pair = 'LINK/USDT' AND exchange = 'binance' RETURNING pair, tp_mode;"

# STEP 2: Get current LINK price
docker compose exec app python3 scripts/fetch_live_prices.py

# STEP 3: Create position - LINK has market order for leg 0 (instant fill)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol LINKUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 14.50 \
  --order-size 5

# First leg fills INSTANTLY via market order
sleep 5

# Check that BOTH per-leg AND aggregate TPs exist
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    do.leg_index,
    do.status,
    do.fill_price,
    do.tp_price as per_leg_tp,
    do.tp_percent as leg_tp_pct,
    pg.weighted_avg_entry,
    pg.tp_aggregate_percent,
    ROUND(pg.weighted_avg_entry * (1 + pg.tp_aggregate_percent/100), 4) as aggregate_tp
   FROM dca_orders do
   JOIN position_groups pg ON do.group_id = pg.id
   WHERE pg.symbol = 'LINKUSDT' AND pg.status = 'live'
   ORDER BY do.leg_index;"

# Verify exchange has BOTH types of TP orders
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Leg 0 fills instantly (market order)
- ✅ Per-leg TP order exists for filled DCA leg (based on fill price)
- ✅ Aggregate TP order exists for combined position (based on weighted avg)
- ✅ "First trigger wins" - whichever TP hits first closes that portion
- ✅ Both TP orders visible on exchange
- ✅ If per-leg hits first, only that leg closes
- ✅ If aggregate hits first, entire position closes

---

### Test 16.5: TP Order Fill Handling

**Objective:** Verify system handles TP order fills correctly

**Fill Strategy:** Use ETHUSDT with bracket strategy - enter 0.1% below market for quick fill, then wait for TP

```bash
# STEP 1: Get current ETH price
docker compose exec app python3 scripts/fetch_live_prices.py
# Note the ETH price (e.g., $3400)

# STEP 2: Calculate bracket entry (0.1% below current price)
# If ETH = $3400, then entry = $3396.60

# STEP 3: Create position with tight TP (0.2% to increase TP hit chance)
# First, temporarily set a very tight TP percent:
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pair, tp_aggregate_percent FROM dca_configurations
   WHERE pair = 'ETH/USDT' AND exchange = 'binance';"

# Optionally update TP to 0.2% for faster testing:
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE dca_configurations
   SET tp_aggregate_percent = 0.2
   WHERE pair = 'ETH/USDT' AND exchange = 'binance'
   RETURNING pair, tp_aggregate_percent;"

# STEP 4: Create position - ETH has market order (instant fill)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 240 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.015

# First leg fills INSTANTLY via market order
sleep 5

# STEP 5: Monitor for TP fills (TP at ~0.2% above fill price)
# With 0.2% TP, if fill was $3400, TP target is ~$3406.80
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT
    pg.symbol,
    pg.weighted_avg_entry as fill_price,
    pg.tp_aggregate_percent,
    ROUND(pg.weighted_avg_entry * (1 + pg.tp_aggregate_percent/100), 2) as tp_target,
    pg.status
   FROM position_groups pg
   WHERE pg.symbol = 'ETHUSDT' AND pg.status IN ('live', 'closed')
   ORDER BY pg.created_at DESC LIMIT 1;"

# STEP 6: Wait and monitor for TP hit (check every 30 seconds)
watch -n 30 'docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd, close_reason, closed_at
   FROM position_groups
   WHERE symbol = '\''ETHUSDT'\''
   ORDER BY created_at DESC LIMIT 1;"'

# Alternative: Check logs for TP fill events
docker compose logs -f app 2>&1 | grep -i "tp_fill\|take_profit\|position.*closed"
```

**Expected Result:**

- ✅ Entry leg fills instantly via market order
- ✅ TP order placed at calculated target price
- ✅ When price reaches TP target, TP order fills
- ✅ order_fill_monitor detects the TP fill
- ✅ Position status changes to 'closed'
- ✅ realized_pnl_usd calculated correctly (should be ~0.2% of position value)
- ✅ close_reason set to 'tp_hit'
- ✅ Remaining unfilled DCA orders cancelled
- ✅ Telegram notification sent (if enabled)

---

## 🔥 TEST SUITE 17: SIGNAL VALIDATION & TRANSFORMATION (30 mins) ⭐ NEW

### Overview

This test suite verifies signal validation, transformation, and rejection logic.

---

### Test 17.1: Missing Required Fields Rejection

**Objective:** Verify signals with missing fields are rejected

```bash
# Test with missing symbol (should fail)
curl -X POST http://localhost:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "tv": {
      "exchange": "binance",
      "timeframe": 60,
      "action": "buy"
    }
  }'
```

**Expected Result:**

- ✅ Returns 422 Unprocessable Entity
- ✅ Error message indicates missing 'symbol' field
- ✅ No position created
- ✅ Validation error logged

---

### Test 17.2: Invalid Exchange Rejection

**Objective:** Verify unsupported exchanges are rejected

```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange kraken \
  --symbol BTCUSD \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92000.0 \
  --order-size 0.001
```

**Expected Result:**

- ✅ Error returned for unsupported exchange
- ✅ No position created
- ✅ Only 'binance' and 'bybit' accepted

---

### Test 17.3: Exchange Name Normalization

**Objective:** Verify exchange names are normalized (case-insensitive)

```bash
# Test with uppercase BINANCE (should work)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange BINANCE \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 92000.0 \
  --order-size 0.001

# Verify position created with lowercase exchange
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, exchange FROM position_groups ORDER BY created_at DESC LIMIT 1;"
```

**Expected Result:**

- ✅ BINANCE normalized to 'binance'
- ✅ BYBIT normalized to 'bybit'
- ✅ Position created successfully

---

### Test 17.4: Unconfigured Pair Rejection

**Objective:** Verify signals for unconfigured pairs are rejected

```bash
# Try to create position for pair without DCA config
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange binance \
  --symbol PEPEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.00001 \
  --order-size 1000000
```

**Expected Result:**

- ✅ Error returned: "No DCA configuration found"
- ✅ No position created
- ✅ Only configured pairs allowed

---

## 📊 UPDATED TEST RESULTS TEMPLATE (v2)

Add these new test suites to the results template:

```markdown
### TEST SUITE 5A: Practical Risk Engine Testing
- [ ] Test 5A.1: Setup - Apply Test Configuration - ✅ PASS / ❌ FAIL
- [ ] Test 5A.2: Create Losing Position - Observe Timer - ✅ PASS / ❌ FAIL
- [ ] Test 5A.3: Watch Risk Timer Countdown - ✅ PASS / ❌ FAIL
- [ ] Test 5A.4: Trigger Risk Engine Evaluation - ✅ PASS / ❌ FAIL
- [ ] Test 5A.5: Timer Reset on Pyramid - ✅ PASS / ❌ FAIL
- [ ] Test 5A.6: Timer Stops When Loss Recovers - ✅ PASS / ❌ FAIL
- [ ] Test 5A.7: Blocked Position Ignores Timer - ✅ PASS / ❌ FAIL
- [ ] Test 5A.8: Cleanup - Restore Production Config - ✅ PASS / ❌ FAIL

### TEST SUITE 13: Telegram Notification System
- [ ] Test 13.1: Telegram Configuration API - ✅ PASS / ❌ FAIL
- [ ] Test 13.2: Telegram Connection Test - ✅ PASS / ❌ FAIL
- [ ] Test 13.3: Entry Signal Notification - ✅ PASS / ❌ FAIL
- [ ] Test 13.4: DCA Fill Update Notification - ✅ PASS / ❌ FAIL
- [ ] Test 13.5: Status Change Notification - ✅ PASS / ❌ FAIL
- [ ] Test 13.6: Pyramid Added Notification - ✅ PASS / ❌ FAIL
- [ ] Test 13.7: Take-Profit Hit Notification - ✅ PASS / ❌ FAIL
- [ ] Test 13.8: Risk Alert Notifications - ✅ PASS / ❌ FAIL
- [ ] Test 13.9: Failure Alert Notification - ✅ PASS / ❌ FAIL
- [ ] Test 13.10: Exit Signal Notification - ✅ PASS / ❌ FAIL
- [ ] Test 13.11: Message Toggle Tests - ✅ PASS / ❌ FAIL
- [ ] Test 13.12: Quiet Hours Functionality - ✅ PASS / ❌ FAIL
- [ ] Test 13.13: Threshold Alerts - ✅ PASS / ❌ FAIL
- [ ] Test 13.14: Test Mode - ✅ PASS / ❌ FAIL
- [ ] Test 13.15: Message Update vs New Message - ✅ PASS / ❌ FAIL

### TEST SUITE 14: Frontend UI Testing
- [ ] Test 14.1: Dashboard Page - ✅ PASS / ❌ FAIL
- [ ] Test 14.2: Settings Page - Trading Tab - ✅ PASS / ❌ FAIL
- [ ] Test 14.3: Settings Page - Risk Tab - ✅ PASS / ❌ FAIL
- [ ] Test 14.4: Settings Page - Alerts Tab - ✅ PASS / ❌ FAIL
- [ ] Test 14.5: Settings Page - Account Tab - ✅ PASS / ❌ FAIL
- [ ] Test 14.6: Positions Page - ✅ PASS / ❌ FAIL
- [ ] Test 14.7: Queue Page - ✅ PASS / ❌ FAIL
- [ ] Test 14.8: Risk Page - ✅ PASS / ❌ FAIL
- [ ] Test 14.9: Analytics Page - ✅ PASS / ❌ FAIL
- [ ] Test 14.10: Authentication Flow - ✅ PASS / ❌ FAIL
- [ ] Test 14.11: Mobile Responsiveness - ✅ PASS / ❌ FAIL
- [ ] Test 14.12: Error States and Loading - ✅ PASS / ❌ FAIL
```

---

## 🎯 FINAL SUCCESS CRITERIA (COMPLETE)

**Total Test Suites: 17**
**Total Individual Tests: 130+**

### Core Trading Engine

- ✅ Signal ingestion and position creation
- ✅ Pyramid management and DCA execution
- ✅ Queue system with priority rules
- ✅ Risk engine with offset logic (practical testing with reduced thresholds)
- ✅ All 4 TP modes (per_leg, aggregate, hybrid, pyramid_aggregate)
- ✅ Exit signal handling and position closure
- ✅ Signal validation and transformation

### API & Backend Services

- ✅ All 41 API endpoints functional
- ✅ Authentication and authorization
- ✅ Background workers (order monitor, queue promotion, risk engine)
- ✅ Multi-exchange support (Binance, Bybit)

### Telegram Notification System

- ✅ All 8 message types (entry, exit, DCA fill, status, pyramid, TP hit, risk, failure)
- ✅ Message consolidation (update existing vs new)
- ✅ Quiet hours with urgent-only mode
- ✅ Threshold alerts (loss/profit %)
- ✅ Per-message-type toggles
- ✅ Test mode for debugging

### Frontend Application

- ✅ All 9 pages functional
- ✅ Settings persistence (all 4 tabs)
- ✅ Real-time updates (polling)
- ✅ Mobile responsive design
- ✅ Error handling and loading states

### Security & Isolation

- ✅ Multi-user data isolation
- ✅ API key encryption
- ✅ JWT token validation
- ✅ Webhook signature verification

### Practical Risk Engine Testing (NEW)

- ✅ Configurable thresholds for quick testing (-0.005% loss, 1 min timer)
- ✅ Observable timer countdown
- ✅ Timer reset on pyramid
- ✅ Timer recovery when loss improves
- ✅ Blocked position protection
- ✅ Production config restoration

---

**Test Plan Version:** 2.1
**Last Updated:** December 2024
**Coverage:** Comprehensive (Backend + Frontend + Telegram + Practical Risk Engine)
