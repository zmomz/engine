# Trading Engine Test Plan - Mock Exchange Only

## Full System Validation with Controlled Price Environment

**Date:** Ready for execution
**Duration:** ~4-5 hours
**Environment:** Mock Exchange (localhost:9000) - All tests run against mock exchange only
**Prerequisites:** Docker services running, clean database

**Testing Approach:** 100% Practical - All tests executed via commands with exchange and database verification
**Price Control:** All prices controlled via mock exchange admin API

**User Credentials:**

- USER_ID: `f937c6cb-f9f9-4d25-be19-db9bf596d7e1`
- WEBHOOK_SECRET: `ecd78c38d5ec54b4cd892735d0423671`

**Mock Exchange DCA Configurations:**

| Pair | Entry Type | TP Mode | Max Pyramids | DCA Levels |
|------|------------|---------|--------------|------------|
| BTC/USDT | limit | per_leg | 2 | 4 |
| ETH/USDT | market | aggregate | 3 | 3 |
| SOL/USDT | limit | aggregate | 2 | 5 |
| TRX/USDT | market | pyramid_aggregate | 4 | 6 |
| XRP/USDT | market | hybrid | 5 | 2 |
| LINK/USDT | market | hybrid | 3 | 8 |
| ADA/USDT | market | aggregate | 1 | 1 |
| AVAX/USDT | market | per_leg | 1 | 2 |
| DOGE/USDT | limit | per_leg | 3 | 5 |
| LTC/USDT | limit | per_leg | 2 | 4 |

---

## Quick Reference: Mock Exchange Commands

### Price Control

```bash
# Set symbol price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

# Get current price
curl -s "http://127.0.0.1:9000/fapi/v1/ticker/price?symbol=BTCUSDT"

# Reset all prices to defaults
curl -s -X POST "http://127.0.0.1:9000/admin/reset"
```

### Order Verification

```bash
# Check open orders for symbol
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=BTCUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool

# Check all open orders
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool

# Check account positions
curl -s "http://127.0.0.1:9000/fapi/v2/positionRisk" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

### Signal Sending (Using simulate_webhook.py)

```bash
# Send buy signal (template)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01
```

### Signal Sending (Using simulate_signals.py - Batch)

```bash
# Send signals to all mock exchange pairs
docker compose exec app python3 scripts/simulate_signals.py \
  --user zmomz \
  --exchange mock \
  --action buy \
  --capital 200 \
  --delay 2

# Send signal to specific symbols
docker compose exec app python3 scripts/simulate_signals.py \
  --user zmomz \
  --exchange mock \
  --symbols BTC/USDT ETH/USDT \
  --action buy \
  --capital 200
```

### Database Queries

```bash
# Check position groups
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, pyramid_count, filled_dca_legs, total_dca_legs FROM position_groups WHERE exchange = 'mock' ORDER BY created_at DESC;"

# Check DCA orders
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity, exchange_order_id FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Check pyramids
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pyramid_index, status, avg_entry_price FROM pyramids WHERE position_group_id = '<GROUP_ID>' ORDER BY pyramid_index;"
```

---

## PRE-TEST SETUP

### 1. Start Services (2 mins)

```bash
# Start all services
docker compose down
docker compose up -d

# Wait for services to be healthy
sleep 10
docker compose ps
```

**Expected:** All services running including `mock-exchange` on port 9000

### 2. Clean Slate (2 mins)

```bash
# Clean positions from database
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Clear queue
docker compose exec db psql -U tv_user -d tv_engine_db -c "DELETE FROM queued_signals;"

# Reset mock exchange
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Verify clean state
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT COUNT(*) as active_positions FROM position_groups WHERE status NOT IN ('closed', 'failed');"
```

**Expected:**

- active_positions = 0
- Mock exchange reset to default prices

### 3. Verify Configuration (2 mins)

```bash
# Check DCA configs for mock exchange
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pair, entry_order_type, tp_mode, max_pyramids, dca_levels
   FROM dca_configurations
   WHERE user_id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1'
   AND exchange = 'mock'
   ORDER BY pair;"
```

**Expected:** 10 DCA configurations for mock exchange pairs

---

## TEST SUITE 1: BASIC ENTRY TESTS

### Test 1.1: Limit Order Entry (BTC/USDT)

**Config:** BTC/USDT (limit, per_leg, max_pyramids=2)

```bash
# Step 1: Set initial price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

# Step 2: Send buy signal
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

# Step 3: Wait for processing
sleep 3

# Step 4: Verify in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, pyramid_count, total_dca_legs FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, exchange_order_id FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Step 5: Verify on mock exchange
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=BTCUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- Position group created with status='live'
- 4 DCA orders created (based on config)
- First order at entry price, others at DCA levels below
- Orders visible on mock exchange as LIMIT BUY

---

### Test 1.2: Market Order Entry (ETH/USDT)

**Config:** ETH/USDT (market, aggregate, max_pyramids=3)

```bash
# Step 1: Set initial price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3400}'

# Step 2: Send buy signal
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.05

# Step 3: Wait for processing
sleep 3

# Step 4: Verify in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, filled_dca_legs, total_dca_legs FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity FROM dca_orders WHERE symbol = 'ETH/USDT' ORDER BY leg_index;"
```

**Expected:**

- First DCA order filled immediately (market order)
- Remaining DCA orders placed as limits below entry
- Position status='partially_filled' or 'active'

---

### Test 1.3: Entry Rejected - No DCA Config

```bash
# Try signal for unconfigured pair/timeframe (timeframe 15 is not configured)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 15 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01
```

**Expected:** Signal rejected with "No active DCA configuration" error

---

### Test 1.4: Entry Rejected - Invalid Webhook Secret

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Send signal with wrong secret
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret wrong_secret_12345 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01
```

**Expected:** Signal rejected with authentication/authorization error (401 or 403)

---

### Test 1.5: Entry with Different Position Size Types

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Test with quote position size (USD value)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 200}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 200.0 \
  --order-size 500 \
  --pos-size-type quote

sleep 3

# Verify capital allocation matches
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, total_invested_usd FROM position_groups WHERE symbol = 'SOL/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Position created with ~$500 total investment spread across DCA levels

---

### Test 1.6: Entry with Very Small Order Size (Minimum Notional Test)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

# Try very small order (may be below minimum notional)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.00001
```

**Expected:** Either position created with adjusted size or rejected if below minimum

---

## TEST SUITE 2: ORDER FILL TESTS

### Test 2.1: Price Drop Fills Limit Orders

**Prerequisite:** Complete Test 1.1 (BTC/USDT position with limit orders)

```bash
# Step 1: Check current DCA levels
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Step 2: Drop price to fill first two orders (assuming DCA at 95000, 94050, 93100, 92150)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 93500}'

# Step 3: Wait for order fill monitor to detect fills
sleep 5

# Step 4: Verify fills in database
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity, fill_price FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, filled_dca_legs, total_filled_quantity FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 5: Check exchange for remaining open orders
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=BTCUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- Orders at 95000, 94050 should be filled
- Orders at 93100, 92150 still open
- Position status='partially_filled'
- filled_dca_legs=2

---

### Test 2.2: All DCA Orders Fill

```bash
# Continue from Test 2.1 - drop price below all DCA levels
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 91000}'

# Wait for fills
sleep 5

# Verify all orders filled
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, filled_dca_legs, total_dca_legs FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# No open orders should remain
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=BTCUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- All 4 DCA orders filled
- No open BUY orders on exchange (only TP SELL orders)
- Position fully filled

---

### Test 2.3: Immediate Market Fill on Entry

**Config:** ETH/USDT (market entry)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3400}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.05

sleep 3

# Verify first leg filled immediately
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity FROM dca_orders WHERE symbol = 'ETH/USDT' ORDER BY leg_index;"
```

**Expected:** Leg 0 filled immediately, remaining legs as pending limit orders

---

### Test 2.4: Price Exactly at Order Level

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 120}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol LTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 120.0 \
  --order-size 1

sleep 3

# Check DCA order prices
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price FROM dca_orders WHERE symbol = 'LTC/USDT' ORDER BY leg_index;"

# Move price exactly to leg 1's price (not below)
# Assuming leg 1 is at ~118.8 (1% below 120)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 118.8}'
sleep 5

# Check if order filled at exact price
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, fill_price FROM dca_orders WHERE symbol = 'LTC/USDT' ORDER BY leg_index;"
```

**Expected:** Order fills when price reaches exactly the order level

---

### Test 2.5: Fill with Weighted Average Calculation

```bash
# Continue from previous - fill multiple levels and verify avg
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, avg_entry_price, total_filled_quantity, total_invested_usd
   FROM position_groups WHERE symbol = 'LTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** avg_entry_price = weighted average of all filled DCA levels

---

## TEST SUITE 3: TAKE PROFIT TESTS - PER LEG MODE

### Test 3.1: Single Leg TP Triggers (BTC/USDT)

**Config:** BTC/USDT (per_leg mode)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Set price and create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Step 2: Fill first 2 DCA orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 93500}'
sleep 5

# Step 3: Check TPs created for filled legs
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status, tp_price, tp_order_id FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Step 4: Raise price to trigger leg 0's TP (at ~5% above entry)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 100000}'
sleep 5

# Step 5: Verify leg 0 TP executed
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status, filled_quantity, tp_status FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, total_filled_quantity FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- Leg 0's TP executes (status=closed or similar)
- Leg 1's TP still waiting
- Unfilled DCA orders (leg 2, 3) still on exchange
- Position stays open

---

### Test 3.2: All Per-Leg TPs Execute - Position Closes

**Config:** AVAX/USDT (per_leg, max_pyramids=1, 2 DCA levels)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/AVAXUSDT/price" -H "Content-Type: application/json" -d '{"price": 40}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol AVAXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 40.0 \
  --order-size 5

sleep 3

# Step 2: Fill all DCA orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/AVAXUSDT/price" -H "Content-Type: application/json" -d '{"price": 36}'
sleep 5

# Step 3: Verify all filled
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity FROM dca_orders WHERE symbol = 'AVAX/USDT' ORDER BY leg_index;"

# Step 4: Raise price to trigger ALL TPs
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/AVAXUSDT/price" -H "Content-Type: application/json" -d '{"price": 50}'
sleep 5

# Step 5: Verify position closed
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd, closed_at FROM position_groups WHERE symbol = 'AVAX/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 6: No orphaned orders
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=AVAXUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- All TPs execute
- Position status='closed'
- realized_pnl_usd shows profit
- No orphaned orders on exchange

---

### Test 3.3: Per-Leg TP with Unfilled DCA Orders

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.35}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.35 \
  --order-size 300

sleep 3

# Fill only first 2 legs (out of 5)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.335}'
sleep 5

# Trigger TP for filled legs only
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.40}'
sleep 5

# Check: filled legs closed, unfilled legs cancelled or still open?
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status, tp_status FROM dca_orders WHERE symbol = 'DOGE/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE symbol = 'DOGE/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Filled legs have TP executed, unfilled legs remain pending, position may still be open

---

## TEST SUITE 4: TAKE PROFIT TESTS - AGGREGATE MODE

### Test 4.1: Aggregate TP Closes Entire Position

**Config:** ETH/USDT (market, aggregate, max_pyramids=3)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3400}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.05

sleep 3

# Step 2: Fill some DCA orders (not all)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3200}'
sleep 5

# Step 3: Verify partial fills
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity FROM dca_orders WHERE symbol = 'ETH/USDT' ORDER BY leg_index;"

# Step 4: Check unfilled orders on exchange
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=ETHUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool

# Step 5: Raise price to trigger aggregate TP (5% above weighted avg)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3700}'
sleep 5

# Step 6: Verify position CLOSED
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd, closed_at FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 7: Verify unfilled DCA orders CANCELLED
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status FROM dca_orders WHERE symbol = 'ETH/USDT' ORDER BY leg_index;"

# Step 8: No orphaned orders on exchange
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=ETHUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- Position status='closed'
- All filled quantity sold via aggregate TP
- Unfilled DCA orders status='cancelled'
- NO orphaned orders on mock exchange

---

### Test 4.2: Aggregate TP with All Orders Filled (ADA/USDT)

**Config:** ADA/USDT (aggregate, max_pyramids=1, 1 DCA level)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Step 1: Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.90}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.90 \
  --order-size 100

sleep 3

# Step 2: Verify filled (market order, single level)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, filled_dca_legs, total_dca_legs FROM position_groups WHERE symbol = 'ADA/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 3: Trigger aggregate TP
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 1.00}'
sleep 5

# Step 4: Verify closed with profit
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd, closed_at FROM position_groups WHERE symbol = 'ADA/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- Position closes completely
- Profit realized (~10% on 100 ADA)

---

### Test 4.3: Aggregate TP Price Exactly at Target

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 200}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 200.0 \
  --order-size 1

sleep 3

# Get weighted avg and calculate exact TP price
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT avg_entry_price FROM position_groups WHERE symbol = 'SOL/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Assuming 5% TP and avg entry ~200, TP should be around 210
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 210}'
sleep 5

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE symbol = 'SOL/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** TP triggers at exactly the target price

---

## TEST SUITE 5: TAKE PROFIT TESTS - PYRAMID AGGREGATE MODE

### Test 5.1: Pyramid 0 TP Closes Only Pyramid 0

**Config:** TRX/USDT (pyramid_aggregate, max_pyramids=4)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create pyramid 0
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.25}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.25 \
  --order-size 500

sleep 3

# Step 2: Fill some pyramid 0 orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.23}'
sleep 5

# Step 3: Add pyramid 1
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.22 \
  --order-size 500

sleep 3

# Step 4: Check pyramids
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pg.symbol, pg.pyramid_count, p.pyramid_index, p.status
   FROM position_groups pg
   JOIN pyramids p ON p.position_group_id = pg.id
   WHERE pg.symbol = 'TRX/USDT' AND pg.exchange = 'mock'
   ORDER BY p.pyramid_index;"

# Step 5: Raise price to trigger only pyramid 0's TP
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.28}'
sleep 5

# Step 6: Verify pyramid 0 closed, pyramid 1 still active
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT p.pyramid_index, p.status, p.avg_entry_price
   FROM pyramids p
   JOIN position_groups pg ON p.position_group_id = pg.id
   WHERE pg.symbol = 'TRX/USDT' AND pg.exchange = 'mock'
   ORDER BY p.pyramid_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE symbol = 'TRX/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- Pyramid 0 status='filled' (closed)
- Pyramid 1 status='submitted' (still active)
- Position group still open
- Pyramid 1's orders remain on exchange

---

### Test 5.2: All Pyramids TP - Position Closes

```bash
# Continue from Test 5.1 - trigger pyramid 1's TP too
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.30}'
sleep 5

# Verify position closed
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, closed_at, realized_pnl_usd FROM position_groups WHERE symbol = 'TRX/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pyramid_index, status FROM pyramids p JOIN position_groups pg ON p.position_group_id = pg.id WHERE pg.symbol = 'TRX/USDT' AND pg.exchange = 'mock' ORDER BY pyramid_index;"

# No orphaned orders
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=TRXUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- All pyramids status='filled'
- Position status='closed'
- No orphaned orders

---

### Test 5.3: Pyramid with Different TP Percentages

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create position with pyramid 0
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.25}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.25 \
  --order-size 500

sleep 3

# Fill pyramid 0
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.22}'
sleep 5

# Add pyramid 1 at lower price
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.20 \
  --order-size 500

sleep 3

# Fill pyramid 1
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.18}'
sleep 5

# Check each pyramid's avg entry
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT p.pyramid_index, p.avg_entry_price, p.status
   FROM pyramids p
   JOIN position_groups pg ON p.position_group_id = pg.id
   WHERE pg.symbol = 'TRX/USDT' AND pg.exchange = 'mock'
   ORDER BY p.pyramid_index;"

# Note: Different avg entries mean different TP trigger prices
```

**Expected:** Each pyramid has its own avg_entry_price and independent TP trigger level

---

## TEST SUITE 6: TAKE PROFIT TESTS - HYBRID MODE

### Test 6.1: Per-Leg TP in Hybrid Mode (XRP/USDT)

**Config:** XRP/USDT (hybrid, max_pyramids=5)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" -H "Content-Type: application/json" -d '{"price": 2.50}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.50 \
  --order-size 50

sleep 3

# Step 2: Fill orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" -H "Content-Type: application/json" -d '{"price": 2.30}'
sleep 5

# Step 3: Raise price to trigger one leg's TP (but not aggregate)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" -H "Content-Type: application/json" -d '{"price": 2.65}'
sleep 5

# Step 4: Verify individual leg TP executed
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status, tp_status FROM dca_orders WHERE symbol = 'XRP/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE symbol = 'XRP/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- Individual leg TP executes
- Position stays open (hybrid mode - aggregate TP not yet reached)

---

### Test 6.2: Aggregate TP in Hybrid Mode (LINK/USDT)

**Config:** LINK/USDT (hybrid, max_pyramids=3)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LINKUSDT/price" -H "Content-Type: application/json" -d '{"price": 25}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol LINKUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 25.0 \
  --order-size 10

sleep 3

# Step 2: Fill orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LINKUSDT/price" -H "Content-Type: application/json" -d '{"price": 22}'
sleep 5

# Step 3: Trigger aggregate TP level (higher than individual TPs)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LINKUSDT/price" -H "Content-Type: application/json" -d '{"price": 30}'
sleep 5

# Step 4: Verify closed
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, closed_at FROM position_groups WHERE symbol = 'LINK/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# No orphaned orders
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=LINKUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- Aggregate TP closes entire position
- Unfilled orders cancelled
- No orphaned orders

---

### Test 6.3: Hybrid Mode - First Trigger Wins

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" -H "Content-Type: application/json" -d '{"price": 2.50}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.50 \
  --order-size 50

sleep 3

# Fill all orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" -H "Content-Type: application/json" -d '{"price": 2.20}'
sleep 5

# Jump price high enough to trigger BOTH per-leg and aggregate TPs simultaneously
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" -H "Content-Type: application/json" -d '{"price": 3.00}'
sleep 5

# Check final state
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd FROM position_groups WHERE symbol = 'XRP/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Position closes via whichever TP mechanism triggers first

---

## TEST SUITE 7: PYRAMID TESTS

### Test 7.1: Add Pyramid to Existing Position

**Config:** BTC/USDT (max_pyramids=2)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create initial position (pyramid 0)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Check pyramid count
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 2: Send second signal (should add pyramid 1)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 93000.0 \
  --order-size 0.01

sleep 3

# Step 3: Verify pyramid added
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT pyramid_index, entry_price, status FROM pyramids p JOIN position_groups pg ON p.position_group_id = pg.id WHERE pg.symbol = 'BTC/USDT' AND pg.exchange = 'mock' ORDER BY pyramid_index;"
```

**Expected:**

- Same position group (not new one)
- pyramid_count = 2
- Two pyramids listed with different entry prices

---

### Test 7.2: Pyramid Rejected - Max Reached

```bash
# Continue from Test 7.1 - try to add third pyramid (max=2)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 91000.0 \
  --order-size 0.01

# Verify rejected
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- Signal rejected with "Max pyramids reached"
- pyramid_count still = 2

---

### Test 7.3: Pyramid with Different Timeframe Rejected

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create position on 60m timeframe
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Try to add pyramid on different timeframe (should create new position or queue)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 240 \
  --side long \
  --action buy \
  --entry-price 93000.0 \
  --order-size 0.01

sleep 2

# Check: should NOT be a pyramid of original position
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, timeframe, pyramid_count, status FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC;"
```

**Expected:** Different timeframe creates separate position (or queued if pool full)

---

### Test 7.4: Pyramid on Opposite Side Rejected

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create LONG position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Try to add SHORT pyramid (should NOT be allowed as pyramid)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side short \
  --action sell \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 2

# Check: should either close long or be rejected
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, side, status FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC;"
```

**Expected:** Opposite side signal either closes existing position or is handled separately

---

### Test 7.5: Maximum Pyramids (TRX - 4 pyramids)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# TRX/USDT has max_pyramids=4
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.25}'

# Create 4 pyramids
for i in 1 2 3 4; do
  docker compose exec app python3 scripts/simulate_webhook.py \
    --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
    --secret ecd78c38d5ec54b4cd892735d0423671 \
    --exchange mock \
    --symbol TRXUSDT \
    --timeframe 60 \
    --side long \
    --action buy \
    --entry-price 0.25 \
    --order-size 100
  sleep 2
done

# Verify 4 pyramids
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count FROM position_groups WHERE symbol = 'TRX/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Try 5th (should be rejected)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.25 \
  --order-size 100

# Still 4
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count FROM position_groups WHERE symbol = 'TRX/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Exactly 4 pyramids allowed, 5th rejected

---

## TEST SUITE 8: POOL AND QUEUE TESTS

### Test 8.1: Fill Pool to Capacity

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create 10 positions (one for each configured pair) using simulate_signals.py
docker compose exec app python3 scripts/simulate_signals.py \
  --user zmomz \
  --exchange mock \
  --action buy \
  --capital 200 \
  --delay 2

# Verify pool full
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT COUNT(*) as active_positions FROM position_groups WHERE exchange = 'mock' AND status NOT IN ('closed', 'failed');"
```

**Expected:**

- active_positions = 10
- Pool at capacity

---

### Test 8.2: Signal Queued When Pool Full

```bash
# Try to create 11th position (should queue)
# Use a different timeframe to avoid pyramiding
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 240 \
  --side long \
  --action buy \
  --entry-price 94000.0 \
  --order-size 0.01

sleep 2

# Verify queued
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, timeframe, status FROM queued_signals ORDER BY created_at DESC LIMIT 5;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT COUNT(*) as active_positions FROM position_groups WHERE exchange = 'mock' AND status NOT IN ('closed', 'failed');"
```

**Expected:**

- Signal added to queue (status = 'pending')
- Active positions still = 10

---

### Test 8.3: Queue Promotion on Position Close

```bash
# Close one position by triggering TP
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 1.10}'
sleep 5

# Check if queued signal promoted
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, timeframe, status FROM queued_signals ORDER BY created_at DESC LIMIT 5;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT COUNT(*) as active_positions FROM position_groups WHERE exchange = 'mock' AND status NOT IN ('closed', 'failed');"
```

**Expected:**

- ADA position closed
- Queued signal promoted (status = 'executed')
- Pool back to 10

---

### Test 8.4: Pyramid Allowed When Pool Full

```bash
# Send pyramid signal to existing position (should NOT be blocked)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3200.0 \
  --order-size 0.05

sleep 2

# Verify pyramid added (not queued)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- Pyramid executes immediately (not queued)
- Pool still at capacity (pyramids don't count as new positions)

---

### Test 8.5: Queue Priority - Replacement Count

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Fill pool
docker compose exec app python3 scripts/simulate_signals.py \
  --user zmomz \
  --exchange mock \
  --action buy \
  --capital 200 \
  --delay 2

sleep 5

# Queue two signals for same symbol (second should replace first, incrementing replacement_count)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 240 \
  --side long \
  --action buy \
  --entry-price 94000.0 \
  --order-size 0.01

sleep 1

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 240 \
  --side long \
  --action buy \
  --entry-price 93000.0 \
  --order-size 0.01

sleep 1

# Check replacement count
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, timeframe, replacement_count, entry_price FROM queued_signals WHERE symbol = 'BTC/USDT' ORDER BY created_at DESC LIMIT 5;"
```

**Expected:** Single queue entry with replacement_count > 0 and updated entry_price

---

### Test 8.6: Queue with Loss Percentage Priority

```bash
# Queue multiple signals with different loss levels
# Then close positions and see which gets promoted first

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, timeframe, current_loss_percent, replacement_count, status
   FROM queued_signals
   ORDER BY current_loss_percent DESC, replacement_count DESC, queued_at ASC
   LIMIT 10;"
```

**Expected:** Signals ordered by deepest loss first

---

### Test 8.7: Queue Cancellation on Exit Signal

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Fill pool
docker compose exec app python3 scripts/simulate_signals.py \
  --user zmomz \
  --exchange mock \
  --action buy \
  --capital 200 \
  --delay 2

sleep 5

# Queue a signal
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 240 \
  --side long \
  --action buy \
  --entry-price 94000.0 \
  --order-size 0.01

sleep 1

# Send exit signal for same symbol/side
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 240 \
  --side long \
  --action sell \
  --type exit \
  --entry-price 94000.0 \
  --order-size 0.01

sleep 2

# Check if queued signal was cancelled
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, timeframe, status FROM queued_signals WHERE symbol = 'BTC/USDT' ORDER BY created_at DESC LIMIT 5;"
```

**Expected:** Queued signal cancelled when exit signal received

---

## TEST SUITE 9: POSITION LIFECYCLE TESTS

### Test 9.1: Complete Lifecycle - Entry to Close

**Config:** SOL/USDT (limit, aggregate, max_pyramids=2)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 200}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 200.0 \
  --order-size 1

sleep 3

# Step 2: Verify status='live'
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, pyramid_count FROM position_groups WHERE symbol = 'SOL/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 3: Fill all DCA orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 170}'
sleep 5

# Step 4: Verify status='partially_filled' or 'active'
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, filled_dca_legs, total_dca_legs FROM position_groups WHERE symbol = 'SOL/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 5: Trigger aggregate TP
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 230}'
sleep 5

# Step 6: Verify status='closed' with profit
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd, closed_at FROM position_groups WHERE symbol = 'SOL/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 7: No orphaned orders
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=SOLUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- Position goes: live -> partially_filled -> closed
- realized_pnl_usd shows profit
- No orphaned orders

---

### Test 9.2: Exit Signal Closes Position Early

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.35}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.35 \
  --order-size 300

sleep 3

# Step 2: Fill some orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.32}'
sleep 5

# Step 3: Send exit signal
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side sell \
  --action sell \
  --type exit \
  --entry-price 0.32 \
  --order-size 300

sleep 3

# Step 4: Verify closed
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, closed_at FROM position_groups WHERE symbol = 'DOGE/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 5: No orphaned orders
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=DOGEUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool
```

**Expected:**

- Position closes on exit signal
- Unfilled orders cancelled
- No orphaned orders

---

### Test 9.3: Exit Signal with No Filled Orders

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

# Create position with limit orders (no fills yet)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Send exit signal immediately (before any fills)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side sell \
  --action sell \
  --type exit \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Check position status
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, filled_dca_legs, closed_at FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Position closed with no realized PnL (nothing to sell)

---

### Test 9.4: Position Status Transitions Verification

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3400}'

# Create position (WAITING -> LIVE)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.05

sleep 1
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Wait for market order fill (LIVE -> PARTIALLY_FILLED)
sleep 5
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, filled_dca_legs FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Fill all orders (PARTIALLY_FILLED -> ACTIVE)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3100}'
sleep 5
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, filled_dca_legs, total_dca_legs FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Trigger TP (ACTIVE -> CLOSING -> CLOSED)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3700}'
sleep 5
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, closed_at FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Clear status transitions through the lifecycle

---

## TEST SUITE 10: EDGE CASES

### Test 10.1: Rapid Price Movement - Multiple Fills

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create position with 4 DCA levels
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 120}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol LTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 120.0 \
  --order-size 1

sleep 3

# Step 2: Drop price in one big move below all levels
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 100}'
sleep 5

# Step 3: Verify all filled correctly
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity FROM dca_orders WHERE symbol = 'LTC/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, filled_dca_legs, total_dca_legs FROM position_groups WHERE symbol = 'LTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- All 4 orders fill correctly
- No duplicate fills
- filled_dca_legs = 4

---

### Test 10.2: Price Oscillation

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 120}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol LTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 120.0 \
  --order-size 1

sleep 3

# Drop price to fill 2 orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 112}'
sleep 5

# Check fills
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status FROM dca_orders WHERE symbol = 'LTC/USDT' ORDER BY leg_index;"

# Raise price (but not to TP)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 118}'
sleep 3

# Drop again to fill more
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 105}'
sleep 5

# Verify each order fills only once
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity FROM dca_orders WHERE symbol = 'LTC/USDT' ORDER BY leg_index;"
```

**Expected:**

- Each order fills only once
- No duplicate fills from oscillation
- Position tracks correctly

---

### Test 10.3: TP and DCA Fill in Same Price Move

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Fill first order
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 94000}'
sleep 5

# Raise price sharply - should trigger leg 0 TP
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 100000}'
sleep 5

# Check state
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status, tp_status FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- Operations execute correctly without conflicts
- System handles concurrent events properly

---

### Test 10.4: Concurrent Signals Same Symbol

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

# Send two signals rapidly (simulating concurrent webhooks)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01 &

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 94500.0 \
  --order-size 0.01 &

wait
sleep 5

# Check: should have 1 position with 2 pyramids, not 2 positions
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 5;"
```

**Expected:** Proper handling of concurrent signals (one position with pyramids, not duplicate positions)

---

### Test 10.5: Price at Zero or Negative

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Try setting price to 0
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 0}'

# Try signal with 0 entry price
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0 \
  --order-size 0.01
```

**Expected:** Rejected or handled gracefully without crashing

---

### Test 10.6: Extremely Large Order Size

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

# Try very large order
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 1000000
```

**Expected:** Either capped to max exposure or rejected

---

## TEST SUITE 11: SHORT POSITION TESTS

### Test 11.1: Short Entry

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create short position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side short \
  --action sell \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Verify short position
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, side, status FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, side, status FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"
```

**Expected:**

- Position side = 'short'
- DCA orders are SELL orders

---

### Test 11.2: Short TP (Price Drops)

```bash
# Continue from Test 11.1

# Fill short orders (price rises above DCA levels)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 98000}'
sleep 5

# Drop price to trigger short TP
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 88000}'
sleep 5

# Verify closed with profit
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd, closed_at FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**

- TP executes (BUY to close short)
- Position closes with profit

---

### Test 11.3: Short DCA Order Fills (Price Rises)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3400}'

# Create short position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side short \
  --action sell \
  --entry-price 3400.0 \
  --order-size 0.05

sleep 3

# Check DCA prices (should be ABOVE entry for shorts)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price FROM dca_orders WHERE symbol = 'ETH/USDT' ORDER BY leg_index;"

# Price rises to fill DCA levels
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3600}'
sleep 5

# Verify fills
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, status, filled_quantity FROM dca_orders WHERE symbol = 'ETH/USDT' ORDER BY leg_index;"
```

**Expected:** Short DCA orders fill when price rises above their levels

---

### Test 11.4: Short Position Pyramid

```bash
# Continue from Test 11.3

# Add pyramid to short position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side short \
  --action sell \
  --entry-price 3700.0 \
  --order-size 0.05

sleep 3

# Verify pyramid added
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, side, pyramid_count FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Pyramid added to short position

---

### Test 11.5: Short Exit Signal

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 200}'

# Create short
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side short \
  --action sell \
  --entry-price 200.0 \
  --order-size 1

sleep 3

# Fill some
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 210}'
sleep 5

# Exit signal (buy to close short)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --type exit \
  --entry-price 210.0 \
  --order-size 1

sleep 3

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, side, status, closed_at FROM position_groups WHERE symbol = 'SOL/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Short position closed via exit signal

---

## TEST SUITE 12: PNL CALCULATION TESTS

### Test 12.1: Long Position Profit Calculation

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 1.00}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 1.00 \
  --order-size 100

sleep 3

# TP at 10% profit
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 1.10}'
sleep 5

# Check realized PnL
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, total_invested_usd, realized_pnl_usd,
          (realized_pnl_usd / NULLIF(total_invested_usd, 0) * 100) as pnl_percent
   FROM position_groups WHERE symbol = 'ADA/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** realized_pnl_usd ~ +$10 (10% of $100)

---

### Test 12.2: Long Position Loss Calculation

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 1.00}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 1.00 \
  --order-size 100

sleep 3

# Exit at loss
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.90}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side sell \
  --action sell \
  --type exit \
  --entry-price 0.90 \
  --order-size 100

sleep 3

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, total_invested_usd, realized_pnl_usd FROM position_groups WHERE symbol = 'ADA/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** realized_pnl_usd ~ -$10 (10% loss)

---

### Test 12.3: Short Position Profit Calculation

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 1.00}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side short \
  --action sell \
  --entry-price 1.00 \
  --order-size 100

sleep 3

# TP when price drops (profit for short)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.90}'
sleep 5

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, side, total_invested_usd, realized_pnl_usd FROM position_groups WHERE symbol = 'ADA/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Short position profit when price drops

---

### Test 12.4: Unrealized PnL Tracking

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Fill orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 93000}'
sleep 5

# Check unrealized PnL at different price levels
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 90000}'
sleep 2

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, avg_entry_price, unrealized_pnl_usd, unrealized_pnl_percent
   FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Now profit
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 98000}'
sleep 2

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, avg_entry_price, unrealized_pnl_usd, unrealized_pnl_percent
   FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Unrealized PnL updates correctly with price changes

---

## TEST SUITE 13: DCA LEVEL VERIFICATION

### Test 13.1: Verify DCA Price Spacing (Long)

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.40}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.40 \
  --order-size 300

sleep 3

# Check DCA level prices and gaps
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price,
          LAG(price) OVER (ORDER BY leg_index) as prev_price,
          ((LAG(price) OVER (ORDER BY leg_index) - price) / LAG(price) OVER (ORDER BY leg_index) * 100) as gap_percent
   FROM dca_orders WHERE symbol = 'DOGE/USDT' ORDER BY leg_index;"
```

**Expected:** DCA levels progressively lower with configured gap percentages

---

### Test 13.2: Verify DCA Weight Distribution

```bash
# Check that order quantities match configured weight distribution
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, quantity,
          SUM(quantity) OVER () as total_qty,
          (quantity / SUM(quantity) OVER () * 100) as weight_percent
   FROM dca_orders WHERE symbol = 'DOGE/USDT' ORDER BY leg_index;"
```

**Expected:** Quantities distributed according to DCA config weight percentages

---

### Test 13.3: Verify TP Prices per Leg

```bash
# Check TP prices for filled legs
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price as entry_price, tp_price,
          ((tp_price - price) / price * 100) as tp_percent
   FROM dca_orders WHERE symbol = 'DOGE/USDT' ORDER BY leg_index;"
```

**Expected:** TP prices at configured percentage above each entry

---

## TEST SUITE 14: SYSTEM RECOVERY TESTS

### Test 14.1: Service Restart with Active Positions

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create active position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Restart app service
docker compose restart app
sleep 15

# Verify position still tracked
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Verify order monitoring resumes
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 91000}'
sleep 5

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"
```

**Expected:** Position monitoring continues after restart

---

### Test 14.2: Orders Reconciliation After Restart

```bash
# Check exchange orders match DB state
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=BTCUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT exchange_order_id, status FROM dca_orders WHERE symbol = 'BTC/USDT' AND status NOT IN ('filled', 'cancelled') ORDER BY leg_index;"
```

**Expected:** Exchange orders match database records

---

## TEST SUITE 15: RISK ENGINE - TIMER MECHANICS

### Test 15.1: Risk Timer Start Conditions

**Scenario:** Timer starts when BOTH conditions are met: pyramids complete AND loss threshold exceeded

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create position with TRX/USDT (max_pyramids=4)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.25}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.25 \
  --order-size 500

sleep 3

# Step 2: Fill all DCA orders (drop price)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.20}'
sleep 5

# Step 3: Add more pyramids (simulate 3 total)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.19 \
  --order-size 500

sleep 3

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol TRXUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.18 \
  --order-size 500

sleep 5

# Step 4: Drop price to create significant loss (>1.5% threshold)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.15}'
sleep 5

# Step 5: Check risk timer status
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, pyramid_count, filled_dca_legs, total_dca_legs,
          risk_timer_start, risk_timer_expires, risk_eligible,
          unrealized_pnl_percent
   FROM position_groups
   WHERE symbol = 'TRX/USDT' AND exchange = 'mock'
   ORDER BY created_at DESC LIMIT 1;"

# Step 6: Get risk status via API
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=zmomz&password=pass" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- risk_timer_start IS NOT NULL
- risk_timer_expires = risk_timer_start + 15 minutes (default)
- risk_eligible = false (timer not expired yet)
- Timer status in API: "active" with timer_remaining_minutes > 0

---

### Test 15.2: Risk Timer Reset on Price Recovery

**Scenario:** Timer resets when loss improves above threshold

```bash
# Continue from Test 15.1 - timer is running

# Step 1: Record current timer state
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_timer_start, risk_timer_expires FROM position_groups
   WHERE symbol = 'TRX/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

# Step 2: Improve price (loss now less than -1.5%)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.24}'
sleep 5

# Step 3: Check timer reset
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_timer_start, risk_timer_expires, risk_eligible,
          unrealized_pnl_percent
   FROM position_groups
   WHERE symbol = 'TRX/USDT' AND exchange = 'mock'
   ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**
- risk_timer_start IS NULL (timer reset)
- risk_timer_expires IS NULL
- risk_eligible = false
- unrealized_pnl_percent > -1.5 (above threshold)

---

### Test 15.3: Risk Timer Expiration and Eligibility

**Scenario:** Position becomes eligible after timer expires

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create losing position with pyramids (setup similar to 15.1)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.25}'

# Send 3 pyramid signals
for i in 1 2 3; do
  docker compose exec app python3 scripts/simulate_webhook.py \
    --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
    --secret ecd78c38d5ec54b4cd892735d0423671 \
    --exchange mock \
    --symbol TRXUSDT \
    --timeframe 60 \
    --side long \
    --action buy \
    --entry-price 0.25 \
    --order-size 500
  sleep 3
done

# Fill orders and create loss
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.15}'
sleep 5

# Manually set timer to expired for testing (simulate 15 min passed)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET risk_timer_expires = NOW() - INTERVAL '1 minute'
   WHERE symbol = 'TRX/USDT' AND exchange = 'mock' AND risk_timer_expires IS NOT NULL;"

# Trigger risk evaluation
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/run-evaluation" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

sleep 3

# Check eligibility
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_timer_start, risk_timer_expires, risk_eligible
   FROM position_groups
   WHERE symbol = 'TRX/USDT' AND exchange = 'mock'
   ORDER BY created_at DESC LIMIT 1;"
```

**Expected:**
- risk_eligible = true (timer expired, conditions still met)
- Position appears in identified_loser in risk status

---

## TEST SUITE 16: RISK ENGINE - LOSER/WINNER SELECTION

### Test 16.1: Loser Selection by Highest Loss Percentage

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create 3 positions with different loss percentages
# Position A: BTC/USDT
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01 &

# Position B: ETH/USDT
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3400}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.1 &

# Position C: SOL/USDT
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 200}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 200.0 \
  --order-size 0.5 &

wait
sleep 5

# Step 2: Create different loss percentages
# BTC: -3% loss
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 92150}'
# ETH: -8% loss (highest)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3128}'
# SOL: -5% loss
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 190}'

sleep 5

# Step 3: Check risk status - ETH should be identified_loser
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, unrealized_pnl_percent, unrealized_pnl_usd
   FROM position_groups
   WHERE exchange = 'mock' AND status = 'active'
   ORDER BY unrealized_pnl_percent ASC;"
```

**Expected:**
- ETH/USDT identified as loser (highest loss % at -8%)
- Selection order: ETH (-8%) > SOL (-5%) > BTC (-3%)

---

### Test 16.2: Winner Selection - Top N by USD Profit

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create 1 loser and 4 winners
# Loser: BTC
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01
sleep 3

# Winner 1: ETH (+$600)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3000}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3000.0 \
  --order-size 0.1
sleep 3

# Winner 2: SOL (+$300)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 180}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 180.0 \
  --order-size 1
sleep 3

# Winner 3: XRP (+$100)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" -H "Content-Type: application/json" -d '{"price": 2.00}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.00 \
  --order-size 50
sleep 3

# Winner 4: DOGE (+$50)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.30}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.30 \
  --order-size 200
sleep 5

# Step 2: Fill orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 90000}'
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 93000}'
sleep 5

# Step 3: Set prices to create profits/losses
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 85000}'  # Loser
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3600}'   # +$600
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" -H "Content-Type: application/json" -d '{"price": 210}'    # +$300
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" -H "Content-Type: application/json" -d '{"price": 2.20}'   # +$100
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" -H "Content-Type: application/json" -d '{"price": 0.35}'  # +$50
sleep 5

# Step 4: Check risk status - should select top 3 winners
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- identified_winners includes ETH ($600), SOL ($300), XRP ($100)
- DOGE ($50) NOT included (max_winners_to_combine = 3)
- Winners ordered by profit: ETH > SOL > XRP

---

### Test 16.3: Loser Selection Tiebreaker - USD Amount

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create 2 positions with same loss % but different USD amounts
# Position A: BTC (-5%, $500 loss)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 100000}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 100000.0 \
  --order-size 0.1  # $10,000 position
sleep 3

# Position B: ETH (-5%, $150 loss)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3000}'
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3000.0 \
  --order-size 1  # $3,000 position
sleep 5

# Drop both by 5%
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'  # -5%
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 2850}'   # -5%
sleep 5

# Check which is selected
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, unrealized_pnl_percent, unrealized_pnl_usd
   FROM position_groups
   WHERE exchange = 'mock' AND status = 'active'
   ORDER BY unrealized_pnl_percent ASC, unrealized_pnl_usd ASC;"
```

**Expected:**
- BTC selected as loser (same -5% but higher USD loss $500 vs $150)

---

## TEST SUITE 17: RISK ENGINE - MANUAL CONTROLS

### Test 17.1: Block Position from Risk Evaluation

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create losing position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Create loss
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 85000}'
sleep 5

# Get position ID
GROUP_ID=$(docker compose exec db psql -U tv_user -d tv_engine_db -t -A -c \
  "SELECT id FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;")

echo "Position ID: $GROUP_ID"

# Block the position
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/$GROUP_ID/block" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Verify blocked
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_blocked FROM position_groups WHERE id = '$GROUP_ID';"

# Check risk status - should NOT appear as identified_loser
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- risk_blocked = true
- Position NOT in identified_loser (excluded from selection)

---

### Test 17.2: Unblock Position

```bash
# Continue from Test 17.1

# Unblock the position
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/$GROUP_ID/unblock" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Verify unblocked
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_blocked FROM position_groups WHERE id = '$GROUP_ID';"

# Check risk status - should NOW appear as identified_loser
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- risk_blocked = false
- Position appears in identified_loser if conditions met

---

### Test 17.3: Skip Next Evaluation

```bash
# Continue from Test 17.2 (position is unblocked)

# Skip next evaluation
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/$GROUP_ID/skip" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Verify skip flag
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_skip_once FROM position_groups WHERE id = '$GROUP_ID';"

# Run evaluation - position should be skipped
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/run-evaluation" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

sleep 3

# Check if skip flag was cleared after evaluation
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, risk_skip_once FROM position_groups WHERE id = '$GROUP_ID';"
```

**Expected:**
- risk_skip_once = true initially
- Position skipped during evaluation
- risk_skip_once = false after evaluation (auto-cleared)

---

### Test 17.4: Force Stop Engine

```bash
# Check current engine status
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Force stop the engine
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/force-stop" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Verify engine stopped
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; d=json.load(sys.stdin); print(f'engine_force_stopped: {d.get(\"engine_force_stopped\")}')"

# Try sending a new signal - should be blocked
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3400}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.1

# Check if signal was rejected or queued
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;"

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM queued_signals WHERE exchange = 'mock' ORDER BY created_at DESC LIMIT 5;"
```

**Expected:**
- engine_force_stopped = true
- New signals may be queued but not executed

---

### Test 17.5: Force Start Engine

```bash
# Continue from Test 17.4

# Force start the engine
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/force-start" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Verify engine started
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; d=json.load(sys.stdin); print(f'engine_force_stopped: {d.get(\"engine_force_stopped\")}')"

# Queued signals should now be processed
sleep 5

docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status FROM position_groups WHERE exchange = 'mock' ORDER BY created_at DESC LIMIT 5;"
```

**Expected:**
- engine_force_stopped = false
- Queue resumes processing

---

## TEST SUITE 18: RISK ENGINE - OFFSET LOSS EXECUTION

### Test 18.1: Basic Offset Loss - Loser Closed, Winners Partially Closed

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Step 1: Create a loser position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Step 2: Create a winner position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3000.0 \
  --order-size 0.5

sleep 5

# Step 3: Set prices - BTC losing, ETH winning
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 85000}'  # -$100 loss
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3500}'   # +$250 profit
sleep 5

# Step 4: Make loser eligible (set timer to expired)
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET risk_timer_start = NOW() - INTERVAL '20 minutes',
       risk_timer_expires = NOW() - INTERVAL '5 minutes',
       risk_eligible = true
   WHERE symbol = 'BTC/USDT' AND exchange = 'mock';"

# Step 5: Check status before offset
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, unrealized_pnl_usd, risk_eligible
   FROM position_groups WHERE exchange = 'mock' AND status = 'active';"

# Step 6: Trigger offset
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/run-evaluation" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

sleep 5

# Step 7: Verify offset result
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, status, realized_pnl_usd, closed_at
   FROM position_groups WHERE exchange = 'mock' ORDER BY created_at DESC;"

# Step 8: Check risk actions log
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT action_type, loser_pnl_usd, winner_details, notes, timestamp
   FROM risk_actions ORDER BY timestamp DESC LIMIT 1;"
```

**Expected:**
- BTC (loser) status = 'closed', realized_pnl_usd < 0
- ETH (winner) partially closed to offset BTC loss
- Risk action logged with action_type = 'offset_loss'

---

### Test 18.2: Offset with Multiple Winners

```bash
# Similar to 16.2 but execute the offset
# CLEAN START and setup positions...

# After setting up loser + multiple winners, make loser eligible
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET risk_timer_start = NOW() - INTERVAL '20 minutes',
       risk_timer_expires = NOW() - INTERVAL '5 minutes',
       risk_eligible = true
   WHERE symbol = 'BTC/USDT' AND exchange = 'mock';"

# Run offset
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/run-evaluation" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

sleep 5

# Check risk action - should show multiple winners
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT action_type, loser_pnl_usd, winner_details
   FROM risk_actions ORDER BY timestamp DESC LIMIT 1;"
```

**Expected:**
- winner_details JSON contains 2-3 winners
- Each winner shows quantity_closed and pnl_usd

---

### Test 18.3: Offset with No Winners Available

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create only losing positions
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3400}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.1

sleep 5

# Make both positions lose
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 85000}'
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3000}'
sleep 5

# Make loser eligible
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET risk_timer_start = NOW() - INTERVAL '20 minutes',
       risk_timer_expires = NOW() - INTERVAL '5 minutes',
       risk_eligible = true
   WHERE symbol = 'BTC/USDT' AND exchange = 'mock';"

# Run evaluation
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/run-evaluation" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- No offset executed (no winners available)
- Position remains open
- API returns message about no winners

---

## TEST SUITE 19: RISK ENGINE - MAX LOSS LIMIT

### Test 19.1: Max Realized Loss Threshold - Block New Trades

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Check current config
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; d=json.load(sys.stdin); print(f'max_realized_loss_usd: {d.get(\"max_realized_loss_usd\", \"N/A\")}')"

# Simulate daily realized loss by closing positions at loss
# Create and close a losing position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.1

sleep 3

# Fill and create big loss
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 89000}'
sleep 5

# Send exit signal to close at loss
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side sell \
  --action sell \
  --type exit \
  --entry-price 89000.0 \
  --order-size 0.1

sleep 5

# Check daily realized PnL
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT SUM(realized_pnl_usd) as daily_pnl
   FROM position_groups
   WHERE user_id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1'
   AND status = 'closed'
   AND closed_at >= CURRENT_DATE;"

# Check if engine is paused
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; d=json.load(sys.stdin); print(f'engine_paused_by_loss_limit: {d.get(\"engine_paused_by_loss_limit\")}')"
```

**Expected:**
- If daily_pnl exceeds max_realized_loss_usd: engine_paused_by_loss_limit = true
- New trades blocked until force-start

---

### Test 19.2: Force Start After Loss Limit Pause

```bash
# Continue from Test 19.1 (if paused)

# Force start
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/force-start" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Verify resumed
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; d=json.load(sys.stdin); print(f'engine_paused_by_loss_limit: {d.get(\"engine_paused_by_loss_limit\")}')"

# New trade should work now
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3400.0 \
  --order-size 0.1
```

**Expected:**
- engine_paused_by_loss_limit = false
- New trades allowed

---

## TEST SUITE 20: RISK ENGINE - RISK ACTIONS LOGGING

### Test 20.1: Verify Risk Action Record After Offset

```bash
# After running Test 18.1 (offset executed)

# Query risk actions
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT id, action_type, timestamp, loser_pnl_usd, notes
   FROM risk_actions
   WHERE action_type = 'offset_loss'
   ORDER BY timestamp DESC LIMIT 5;"

# Query with winner details
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT action_type,
          loser_pnl_usd,
          winner_details::text as winners,
          notes
   FROM risk_actions
   WHERE action_type = 'offset_loss'
   ORDER BY timestamp DESC LIMIT 1;"
```

**Expected:**
- Risk action record exists with action_type = 'offset_loss'
- loser_pnl_usd matches the loss amount
- winner_details JSON contains winner info
- notes contains execution summary

---

### Test 20.2: Risk Actions in Status API

```bash
# Get risk status with recent actions
curl -s "http://127.0.0.1:8000/api/v1/risk/status" \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
d = json.load(sys.stdin)
print('Recent Actions:')
for action in d.get('recent_actions', []):
    print(f\"  - {action.get('action_type')}: {action.get('loser_symbol')} (PnL: {action.get('loser_pnl_usd')})\")"
```

**Expected:**
- recent_actions includes recent offset actions
- Each action shows loser_symbol, loser_pnl_usd, action_type

---

## TEST SUITE 21: TELEGRAM NOTIFICATIONS

### Test 21.1: Telegram Test Connection

```bash
# Get auth token
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=zmomz&password=pass" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Get current Telegram config
curl -s "http://127.0.0.1:8000/api/v1/telegram/config" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Test connection (requires valid bot_token and channel_id)
curl -s -X POST "http://127.0.0.1:8000/api/v1/telegram/test-connection" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- Returns connection status (success/failure)
- If configured properly: `{"status": "success", "message": "Connected"}`

---

### Test 21.2: Telegram Test Message

```bash
# Send test message
curl -s -X POST "http://127.0.0.1:8000/api/v1/telegram/test-message" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- Test message sent to configured channel
- Returns message_id if successful

---

### Test 21.3: Update Telegram Settings

```bash
# Update Telegram config
curl -s -X PUT "http://127.0.0.1:8000/api/v1/telegram/config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "send_entry_signals": true,
    "send_dca_fill_updates": true,
    "send_tp_hit_updates": true,
    "send_risk_alerts": true,
    "send_failure_alerts": true,
    "quiet_hours_enabled": true,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "quiet_hours_urgent_only": true
  }' | python -m json.tool

# Verify config updated
curl -s "http://127.0.0.1:8000/api/v1/telegram/config" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- Settings updated successfully
- Quiet hours enabled from 22:00 to 08:00 UTC

---

### Test 21.4: Quiet Hours - Regular Messages Blocked

**Note:** This test requires modifying system time or mocking - documented for reference

```bash
# Config: quiet_hours_enabled=true, start="00:00", end="23:59" (always quiet for testing)
# Send entry signal during quiet hours
# Expected: Message NOT sent (logged but skipped)

# Verify via logs
docker compose logs app | grep -i "quiet hours" | tail -5
```

**Expected:**
- Non-urgent messages blocked during quiet hours
- Logs indicate message skipped due to quiet hours

---

### Test 21.5: Quiet Hours - Urgent Messages Allowed

**Note:** Risk alerts and failure alerts are URGENT and should always be sent

```bash
# With quiet_hours_enabled=true and quiet_hours_urgent_only=true
# Risk engine events should still trigger notifications

# Create a losing position and trigger risk alert
# (Follows Test 15.1 setup)

# Check logs for telegram notification
docker compose logs app | grep -i "telegram" | grep -i "risk" | tail -5
```

**Expected:**
- Risk alerts sent even during quiet hours
- Failure alerts sent even during quiet hours

---

## TEST SUITE 22: EXCHANGE SYNCHRONIZATION

### Test 22.1: Sync Position with Exchange

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create position
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Get position ID
GROUP_ID=$(docker compose exec db psql -U tv_user -d tv_engine_db -t -A -c \
  "SELECT id FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock' ORDER BY created_at DESC LIMIT 1;")

# Sync with exchange
curl -s -X POST "http://127.0.0.1:8000/api/v1/positions/$GROUP_ID/sync" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- Returns sync results: `{synced: N, updated: M, not_found: X, errors: Y}`
- Local order states match exchange states

---

### Test 22.2: Sync After Order Filled on Exchange

```bash
# Continue from 22.1 - drop price to fill orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 90000}'
sleep 5

# Check local state before sync
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status, filled_quantity FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Force sync
curl -s -X POST "http://127.0.0.1:8000/api/v1/positions/$GROUP_ID/sync" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Check local state after sync
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, status, filled_quantity, avg_fill_price FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"
```

**Expected:**
- Orders that filled on exchange are updated in database
- filled_quantity and avg_fill_price populated from exchange

---

### Test 22.3: Detect Orphaned Exchange Orders

```bash
# Check for orders on exchange not in local database
# This would typically require manually placing orders on mock exchange

# Via API (if endpoint exists)
curl -s "http://127.0.0.1:8000/api/v1/positions/orphaned-orders?symbol=BTCUSDT&exchange=mock" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Or check exchange directly
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=BTCUSDT" \
  -H "X-MBX-APIKEY: mock_api_key_12345" | python -m json.tool

# Compare with local orders
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT exchange_order_id, status FROM dca_orders WHERE symbol = 'BTC/USDT' AND status NOT IN ('filled', 'cancelled');"
```

**Expected:**
- Exchange orders match local database records
- Any orphaned orders detected and reported

---

### Test 22.4: Order Not Found on Exchange

```bash
# Simulate scenario where local order doesn't exist on exchange
# (e.g., order was cancelled directly on exchange)

# Create position and get order IDs
# Then manually cancel an order via mock exchange admin

# Sync should detect and mark as cancelled
curl -s -X POST "http://127.0.0.1:8000/api/v1/positions/$GROUP_ID/sync" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Expected:**
- not_found count > 0 in sync results
- Local order marked as CANCELLED if update_local=true

---

## TEST SUITE 23: PRECISION & VALIDATION

### Test 23.1: Verify Tick Size Enforcement on Prices

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Check mock exchange precision rules
curl -s "http://127.0.0.1:9000/fapi/v1/exchangeInfo" | python -c "
import sys, json
data = json.load(sys.stdin)
for s in data.get('symbols', []):
    if s['symbol'] == 'BTCUSDT':
        for f in s.get('filters', []):
            if f['filterType'] in ['PRICE_FILTER', 'LOT_SIZE', 'MIN_NOTIONAL']:
                print(f)
"

# Create position - DCA prices should be rounded to tick size
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000.125}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.125 \
  --order-size 0.01

sleep 3

# Verify DCA prices are properly rounded
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, price, tp_price FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"
```

**Expected:**
- All DCA prices rounded to valid tick size
- TP prices rounded to valid tick size

---

### Test 23.2: Verify Step Size Enforcement on Quantities

```bash
# Check order quantities match step size
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT leg_index, quantity FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Verify on exchange
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=BTCUSDT" -H "X-MBX-APIKEY: mock_api_key_12345" | python -c "
import sys, json
orders = json.load(sys.stdin)
for o in orders:
    print(f\"OrderId: {o['orderId']}, Qty: {o['origQty']}, Price: {o['price']}\")"
```

**Expected:**
- All quantities rounded to valid step size
- No precision errors from exchange

---

### Test 23.3: Min Quantity Validation

```bash
# Try creating position with very small capital (should fail if qty < min_qty)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.00001  # Very small order

# Check response for validation error
```

**Expected:**
- Order rejected if calculated quantity below min_qty
- Error message indicates minimum quantity requirement

---

### Test 23.4: Min Notional Validation

```bash
# Try creating position where qty * price < min_notional
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95000.0 \
  --order-size 0.0001  # $9.50 notional, likely below $10 minimum

# Check response for validation error
```

**Expected:**
- Order rejected if notional value below min_notional
- Error message indicates minimum notional requirement

---

### Test 23.5: Precision Rules Cache Behavior

```bash
# First call fetches fresh rules
# Second call within TTL uses cache
# Verify via application logs

docker compose logs app | grep -i "precision" | tail -10

# Check if precision rules are being fetched vs cached
```

**Expected:**
- Precision rules cached after initial fetch
- Cache refreshes after TTL expires (default 3600s)

---

## TEST SUITE 24: RISK ENGINE - SHORT POSITION HANDLING

### Test 24.1: Risk Offset with Short Position as Loser

```bash
# CLEAN START
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Create SHORT position (will be loser)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 95000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side short \
  --action sell \
  --entry-price 95000.0 \
  --order-size 0.01

sleep 3

# Create LONG position (will be winner)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3000}'

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \
  --secret ecd78c38d5ec54b4cd892735d0423671 \
  --exchange mock \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3000.0 \
  --order-size 0.5

sleep 5

# BTC price rises (SHORT loses), ETH price rises (LONG wins)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" -H "Content-Type: application/json" -d '{"price": 100000}'  # Short loses $50
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" -H "Content-Type: application/json" -d '{"price": 3500}'    # Long gains $250
sleep 5

# Make loser eligible
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "UPDATE position_groups
   SET risk_timer_start = NOW() - INTERVAL '20 minutes',
       risk_timer_expires = NOW() - INTERVAL '5 minutes',
       risk_eligible = true
   WHERE symbol = 'BTC/USDT' AND exchange = 'mock';"

# Verify positions before offset
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, side, status, unrealized_pnl_usd
   FROM position_groups WHERE exchange = 'mock' AND status = 'active';"

# Run offset
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/run-evaluation" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

sleep 5

# Check result
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT symbol, side, status, realized_pnl_usd
   FROM position_groups WHERE exchange = 'mock' ORDER BY created_at DESC;"
```

**Expected:**
- SHORT BTC closed (loser side="buy" to close short)
- LONG ETH partially closed (winner side="sell" to close long)
- Correct PnL calculations for both sides

---

## CLEANUP

### Post-Test Cleanup

```bash
# Clean all positions
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Clear queue
docker compose exec db psql -U tv_user -d tv_engine_db -c "DELETE FROM queued_signals;"

# Reset mock exchange
curl -s -X POST "http://127.0.0.1:9000/admin/reset"

# Verify clean
docker compose exec db psql -U tv_user -d tv_engine_db -c \
  "SELECT COUNT(*) as positions FROM position_groups WHERE status NOT IN ('closed', 'failed');"
```

---

## EXECUTION CHECKLIST

### Pre-Test

- [ ] Docker services running (`docker compose ps`)
- [ ] Mock exchange healthy (`curl http://127.0.0.1:9000/health`)
- [ ] Database clean (no active positions)
- [ ] Queue empty

### During Tests

- [ ] Record pass/fail for each test
- [ ] Note any unexpected behavior
- [ ] Check for orphaned orders after each TP test

### Post-Test

- [ ] Clean database
- [ ] Reset mock exchange
- [ ] Document any bugs found

---

## BUG TRACKING TEMPLATE

| Test # | Description | Expected | Actual | Status |
|--------|-------------|----------|--------|--------|
| 1.1 | Limit order entry | 4 DCA orders | | |
| 1.4 | Invalid secret | Auth error | | |
| 4.1 | Aggregate TP closes position | closed, no orphans | | |
| 5.1 | Pyramid TP updates status | pyramid=filled | | |
| 7.2 | Max pyramids rejection | Rejected, count=2 | | |
| 8.3 | Queue promotion | Signal executed | | |
| 10.4 | Concurrent signals | No duplicate positions | | |
| 11.2 | Short TP | Profit on price drop | | |
| 12.1 | PnL calculation | +10% profit | | |
| 15.1 | Risk timer start | Timer starts on conditions | | |
| 15.3 | Risk timer expiration | Position becomes eligible | | |
| 16.1 | Loser selection | Highest loss % selected | | |
| 17.1 | Block position | Position excluded from risk | | |
| 17.4 | Force stop engine | New trades blocked | | |
| 18.1 | Offset loss execution | Loser closed, winners partial | | |
| 19.1 | Max loss threshold | Engine paused on limit | | |
| 21.1 | Telegram test connection | Connection status returned | | |
| 22.1 | Exchange sync | Sync results returned | | |
| 23.1 | Tick size enforcement | Prices properly rounded | | |
| 24.1 | Short position offset | Correct close sides | | |

---

## TEST SUMMARY

| Suite | Tests | Description |
|-------|-------|-------------|
| 1 | 6 | Basic Entry Tests |
| 2 | 5 | Order Fill Tests |
| 3 | 3 | Per-Leg TP Mode |
| 4 | 3 | Aggregate TP Mode |
| 5 | 3 | Pyramid Aggregate TP Mode |
| 6 | 3 | Hybrid TP Mode |
| 7 | 5 | Pyramid Tests |
| 8 | 7 | Pool & Queue Tests |
| 9 | 4 | Position Lifecycle Tests |
| 10 | 6 | Edge Cases |
| 11 | 5 | Short Position Tests |
| 12 | 4 | PnL Calculation Tests |
| 13 | 3 | DCA Level Verification |
| 14 | 2 | System Recovery Tests |
| 15 | 3 | Risk Engine - Timer Mechanics |
| 16 | 3 | Risk Engine - Loser/Winner Selection |
| 17 | 5 | Risk Engine - Manual Controls |
| 18 | 3 | Risk Engine - Offset Execution |
| 19 | 2 | Risk Engine - Max Loss Limit |
| 20 | 2 | Risk Engine - Actions Logging |
| 21 | 5 | Telegram Notifications |
| 22 | 4 | Exchange Synchronization |
| 23 | 5 | Precision & Validation |
| 24 | 1 | Risk Engine - Short Positions |
| **Total** | **93** | **Comprehensive Coverage** |

---

## NOTES

1. **Price Precision:** Mock exchange accepts any price, but real exchanges have tick size requirements
2. **Order Timing:** Allow 5 seconds between price changes for order fill monitor to detect fills
3. **TP Calculation:** TP prices are calculated based on weighted average entry price and configured TP percentages
4. **Aggregate vs Per-Leg:**
   - Per-leg: Each filled DCA leg has its own TP
   - Aggregate: Single TP for entire position based on weighted avg
   - Pyramid Aggregate: Each pyramid has its own aggregate TP
   - Hybrid: Both individual TPs and an aggregate TP
5. **Mock Exchange Only:** All tests in this plan run against the mock exchange (localhost:9000) - no real exchange connections required
6. **Short Positions:** DCA levels go UP (price rises to fill), TP triggers when price DROPS
7. **Long Positions:** DCA levels go DOWN (price drops to fill), TP triggers when price RISES
8. **Concurrency:** System handles concurrent signals via database locking
9. **Queue Priority:** Based on loss %, replacement count, and FIFO order
10. **Pyramids:** Bypass pool limit when adding to existing position
11. **Risk Engine Timer:** Starts when pyramids complete AND loss exceeds threshold (default -1.5%)
12. **Risk Timer Duration:** Default 15 minutes (post_pyramids_wait_minutes config)
13. **Loser Selection Priority:** 1) Highest loss %, 2) Highest USD loss, 3) Oldest position
14. **Winner Selection:** Top N by USD profit (max_winners_to_combine, default 3)
15. **Offset Execution:** Loser fully closed, winners partially closed to cover loss
16. **Max Loss Limit:** Daily realized loss threshold that pauses queue (not risk engine)
17. **Risk Manual Controls:** Block, Unblock, Skip Once, Force Stop, Force Start
18. **Telegram Quiet Hours:** Non-urgent messages blocked, urgent (risk/failure) always sent
19. **Exchange Sync:** Reconciles local DB with actual exchange order states
20. **Precision Rules:** Tick size for prices, step size for quantities, cached for 1 hour
