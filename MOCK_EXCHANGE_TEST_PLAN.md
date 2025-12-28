# Trading Engine Test Plan - Mock Exchange Scenario-Based Testing

## Overview

This test plan validates the trading engine through **scenario-based testing** where each test:
1. **Sets up specific DCA configurations** tailored for the test scenario
2. **Sends trading signals** via webhook simulation
3. **Manipulates prices** on the mock exchange to trigger fills, TPs, etc.
4. **Validates all outcomes** in the database and exchange state

**Environment:** Mock Exchange (localhost:9000)
**Approach:** Configuration-driven scenarios with price manipulation

---

## Test Infrastructure

### User Credentials
```
USER_ID: f937c6cb-f9f9-4d25-be19-db9bf596d7e1
WEBHOOK_SECRET: ecd78c38d5ec54b4cd892735d0423671
USERNAME: zmomz
```

### Mock Exchange Admin API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/symbols/{symbol}/price` | PUT | Set symbol price, triggers order matching |
| `/admin/symbols` | GET | Get all symbols with current prices |
| `/admin/reset` | DELETE | Clear all orders, trades, positions |
| `/admin/orders` | GET | View all orders with filters |
| `/admin/positions` | GET | View all open positions |
| `/admin/balances` | GET | View account balances |

### Database Tables for Validation

| Table | Key Fields |
|-------|------------|
| `position_groups` | status, pyramid_count, filled_dca_legs, total_invested_usd, realized_pnl_usd, unrealized_pnl_usd |
| `dca_orders` | leg_index, price, quantity, status, filled_quantity, tp_price, tp_hit |
| `pyramids` | pyramid_index, status, avg_entry_price |
| `dca_configurations` | pair, dca_levels, tp_mode, tp_settings, max_pyramids |

---

## Quick Start: Environment Setup

```bash
# Start services
docker compose up -d
sleep 15

# Verify health
curl -s http://127.0.0.1:9000/health
curl -s http://127.0.0.1:8000/health

# Clean slate
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"
```

---

## SCENARIO 1: Basic Limit Entry with Progressive DCA Fills

### Objective
Validate that limit orders are placed at correct DCA levels and fill progressively as price drops.

### DCA Configuration Setup

```bash
# Insert test configuration
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'BTC/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'BTC/USDT', 60, 'mock', 'limit',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"25\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-1\", \"weight_percent\": \"25\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-2\", \"weight_percent\": \"25\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-3\", \"weight_percent\": \"25\", \"tp_percent\": \"2\"}
  ]'::jsonb,
  'per_leg',
  '{\"tp_aggregate_percent\": 0}'::jsonb,
  2, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Step 1: Set initial price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" \
  -d '{"price": 100000}'

# Step 2: Send entry signal ($1000 position)
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {
      "exchange": "mock",
      "symbol": "BTC/USDT",
      "timeframe": 60,
      "action": "buy",
      "market_position": "long",
      "market_position_size": 1000,
      "close_price": 100000,
      "order_size": 1000
    },
    "strategy_info": {"trade_id": "test_1_1", "alert_name": "Limit Entry Test"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Step 3: Verify 4 DCA orders created at correct prices
echo "=== DCA Orders Created ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index,
       price,
       quantity,
       status,
       ROUND((100000 - price) / 100000 * 100, 2) as actual_gap_percent
FROM dca_orders
WHERE symbol = 'BTC/USDT'
ORDER BY leg_index;"
```

### Expected DCA Order Prices
| Leg | Gap % | Expected Price | Status |
|-----|-------|----------------|--------|
| 0 | 0% | 100000 | pending/open |
| 1 | -1% | 99000 | pending |
| 2 | -2% | 98000 | pending |
| 3 | -3% | 97000 | pending |

### Price Drop - Fill Orders Progressively

```bash
# Drop to 99500 - should NOT fill any (limit orders, price above leg 0)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 99500}'
sleep 3

echo "=== After price 99500 (no fills expected) ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, price, status, filled_quantity
FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Drop to 99000 - should fill leg 0 and leg 1
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 99000}'
sleep 5

echo "=== After price 99000 (legs 0,1 should fill) ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, price, status, filled_quantity, avg_fill_price
FROM dca_orders WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Verify position group updated
echo "=== Position Group Status ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status, filled_dca_legs, total_dca_legs,
       ROUND(total_invested_usd::numeric, 2) as invested,
       ROUND(weighted_avg_entry::numeric, 2) as avg_entry
FROM position_groups
WHERE symbol = 'BTC/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation Checklist

| Check | Query | Expected |
|-------|-------|----------|
| Leg 0 filled | `status = 'filled'` | Yes |
| Leg 1 filled | `status = 'filled'` | Yes |
| Leg 2 pending | `status = 'pending'` | Yes |
| Leg 3 pending | `status = 'pending'` | Yes |
| Position status | `status` | 'partially_filled' |
| Filled legs | `filled_dca_legs` | 2 |
| Weighted avg | `weighted_avg_entry` | ~99500 |

---

## SCENARIO 2: Market Entry with Immediate Fill

### Objective
Validate market order entry fills immediately at current price.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'ETH/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'ETH/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"40\", \"tp_percent\": \"1.5\"},
    {\"gap_percent\": \"-1\", \"weight_percent\": \"30\", \"tp_percent\": \"1.5\"},
    {\"gap_percent\": \"-2\", \"weight_percent\": \"30\", \"tp_percent\": \"1.5\"}
  ]'::jsonb,
  'aggregate',
  '{\"tp_aggregate_percent\": 3}'::jsonb,
  2, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Clean previous
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Set price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 4000}'

# Send market entry signal
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {
      "exchange": "mock",
      "symbol": "ETH/USDT",
      "timeframe": 60,
      "action": "buy",
      "market_position": "long",
      "market_position_size": 800,
      "close_price": 4000,
      "order_size": 800
    },
    "strategy_info": {"trade_id": "test_2_1", "alert_name": "Market Entry Test"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Verify leg 0 filled immediately (market order)
echo "=== DCA Orders - Leg 0 should be filled immediately ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, price, quantity, status, filled_quantity, avg_fill_price
FROM dca_orders WHERE symbol = 'ETH/USDT' ORDER BY leg_index;"

echo "=== Position Status ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status, filled_dca_legs, total_dca_legs,
       ROUND(total_invested_usd::numeric, 2) as invested,
       ROUND(weighted_avg_entry::numeric, 2) as avg_entry
FROM position_groups WHERE symbol = 'ETH/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation

| Check | Expected |
|-------|----------|
| Leg 0 status | 'filled' |
| Leg 0 filled_quantity | > 0 |
| Leg 0 avg_fill_price | ~4000 |
| Leg 1, 2 status | 'pending' or 'open' |
| Position filled_dca_legs | 1 |

---

## SCENARIO 3: Per-Leg Take Profit Execution

### Objective
Validate that per_leg TP mode creates individual TPs for each filled leg and executes them independently.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'SOL/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'SOL/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"50\", \"tp_percent\": \"3\"},
    {\"gap_percent\": \"-2\", \"weight_percent\": \"50\", \"tp_percent\": \"4\"}
  ]'::jsonb,
  'per_leg',
  '{\"tp_aggregate_percent\": 0}'::jsonb,
  1, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Set initial price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 200}'

# Send entry
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "SOL/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 400, "close_price": 200, "order_size": 400},
    "strategy_info": {"trade_id": "test_3_1", "alert_name": "Per Leg TP Test"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Fill all DCA orders (drop price below all levels)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 190}'
sleep 5

# Check TP prices created
echo "=== DCA Orders with TP Prices ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index,
       ROUND(price::numeric, 2) as entry_price,
       ROUND(tp_price::numeric, 2) as tp_price,
       ROUND((tp_price - price) / price * 100, 2) as tp_percent,
       status, tp_hit, tp_order_id
FROM dca_orders WHERE symbol = 'SOL/USDT' ORDER BY leg_index;"
```

### Expected TP Prices
| Leg | Entry Price | TP % | Expected TP Price |
|-----|-------------|------|-------------------|
| 0 | 200 | 3% | 206 |
| 1 | 196 (-2%) | 4% | 203.84 |

### Trigger TP for Leg 0 Only

```bash
# Raise price to 207 (above leg 0 TP but maybe below leg 1 TP)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 207}'
sleep 5

echo "=== After TP Trigger at 207 ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, status, tp_hit, tp_executed_at
FROM dca_orders WHERE symbol = 'SOL/USDT' ORDER BY leg_index;"

echo "=== Position Status ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status,
       ROUND(realized_pnl_usd::numeric, 2) as realized_pnl,
       ROUND(unrealized_pnl_usd::numeric, 2) as unrealized_pnl
FROM position_groups WHERE symbol = 'SOL/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation

| Check | Expected |
|-------|----------|
| Leg 0 tp_hit | true |
| Leg 0 status | 'filled' (TP executed) |
| Leg 1 tp_hit | false (price may not have reached) |
| Position status | 'active' or 'partially_filled' (still has unfilled TP) |
| Realized PnL | > 0 (from leg 0 TP) |

---

## SCENARIO 4: Aggregate Take Profit Closes Entire Position

### Objective
Validate aggregate TP mode calculates TP from weighted average entry and closes entire position.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'LINK/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'LINK/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"25\", \"tp_percent\": \"1\"},
    {\"gap_percent\": \"-1\", \"weight_percent\": \"25\", \"tp_percent\": \"1\"},
    {\"gap_percent\": \"-2\", \"weight_percent\": \"25\", \"tp_percent\": \"1\"},
    {\"gap_percent\": \"-3\", \"weight_percent\": \"25\", \"tp_percent\": \"1\"}
  ]'::jsonb,
  'aggregate',
  '{\"tp_aggregate_percent\": 5}'::jsonb,
  1, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Set price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LINKUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 20}'

# Entry
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "LINK/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 200, "close_price": 20, "order_size": 200},
    "strategy_info": {"trade_id": "test_4_1", "alert_name": "Aggregate TP Test"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Fill all orders (price drop)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LINKUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 18.5}'
sleep 5

# Check weighted average
echo "=== Position with Weighted Average ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol,
       ROUND(weighted_avg_entry::numeric, 4) as avg_entry,
       ROUND(weighted_avg_entry * 1.05, 4) as expected_tp_price,
       filled_dca_legs, total_dca_legs, status
FROM position_groups WHERE symbol = 'LINK/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"

# Trigger aggregate TP (5% above weighted avg)
# If avg entry is ~19.25, TP would be ~20.21
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LINKUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 21}'
sleep 5

echo "=== After Aggregate TP Trigger ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status, closed_at,
       ROUND(realized_pnl_usd::numeric, 2) as realized_pnl,
       ROUND(total_invested_usd::numeric, 2) as invested
FROM position_groups WHERE symbol = 'LINK/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"

# Verify no orphaned orders
echo "=== Exchange Orders (should be empty) ==="
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=LINKUSDT" \
  -H "X-MBX-APIKEY: mock_api_key_12345"
```

### Validation

| Check | Expected |
|-------|----------|
| Position status | 'closed' |
| closed_at | NOT NULL |
| realized_pnl_usd | > 0 (~5% of invested) |
| Exchange open orders | Empty (all cancelled/filled) |

---

## SCENARIO 5: Pyramid Aggregate TP Mode

### Objective
Validate pyramid_aggregate mode where each pyramid has its own TP that closes only that pyramid.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'TRX/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'TRX/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"50\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-1\", \"weight_percent\": \"50\", \"tp_percent\": \"2\"}
  ]'::jsonb,
  'pyramid_aggregate',
  '{\"tp_aggregate_percent\": 3, \"pyramid_tp_percents\": {\"0\": 3, \"1\": 2.5, \"2\": 2}}'::jsonb,
  3, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Set price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.15}'

# Pyramid 0 entry
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "TRX/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 300, "close_price": 0.15, "order_size": 300},
    "strategy_info": {"trade_id": "test_5_pyr0", "alert_name": "Pyramid 0"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Fill pyramid 0 orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.14}'
sleep 5

# Pyramid 1 entry (at lower price)
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "TRX/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 300, "close_price": 0.13, "order_size": 300},
    "strategy_info": {"trade_id": "test_5_pyr1", "alert_name": "Pyramid 1"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Fill pyramid 1 orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.12}'
sleep 5

# Check pyramids
echo "=== Pyramids Status ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT p.pyramid_index,
       ROUND(p.avg_entry_price::numeric, 6) as avg_entry,
       p.status
FROM pyramids p
JOIN position_groups pg ON p.position_group_id = pg.id
WHERE pg.symbol = 'TRX/USDT' AND pg.exchange = 'mock'
ORDER BY p.pyramid_index;"

# Trigger only pyramid 0's TP (3% above its avg entry ~0.1475 = 0.152)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.155}'
sleep 5

echo "=== After Pyramid 0 TP ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT p.pyramid_index, p.status,
       ROUND(p.avg_entry_price::numeric, 6) as avg_entry
FROM pyramids p
JOIN position_groups pg ON p.position_group_id = pg.id
WHERE pg.symbol = 'TRX/USDT' AND pg.exchange = 'mock'
ORDER BY p.pyramid_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status, pyramid_count,
       ROUND(realized_pnl_usd::numeric, 2) as realized_pnl
FROM position_groups WHERE symbol = 'TRX/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation

| Check | Expected |
|-------|----------|
| Pyramid 0 status | 'filled' (TP hit) |
| Pyramid 1 status | 'submitted' or 'active' |
| Position status | NOT 'closed' (pyramid 1 still open) |
| pyramid_count | 2 |
| realized_pnl | > 0 (from pyramid 0) |

---

## SCENARIO 6: Hybrid TP Mode

### Objective
Validate hybrid mode where both per-leg TPs AND aggregate TP can trigger, whichever comes first.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'XRP/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'XRP/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"50\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-2\", \"weight_percent\": \"50\", \"tp_percent\": \"3\"}
  ]'::jsonb,
  'hybrid',
  '{\"tp_aggregate_percent\": 4}'::jsonb,
  2, true, NOW(), NOW()
);"
```

### Test Execution - Per-Leg TP Triggers First

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Set price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 2.50}'

# Entry
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "XRP/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 250, "close_price": 2.50, "order_size": 250},
    "strategy_info": {"trade_id": "test_6_1", "alert_name": "Hybrid TP Test"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Fill all orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 2.40}'
sleep 5

echo "=== Orders with Both TP Types ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index,
       ROUND(price::numeric, 4) as entry,
       ROUND(tp_price::numeric, 4) as per_leg_tp,
       status
FROM dca_orders WHERE symbol = 'XRP/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT ROUND(weighted_avg_entry::numeric, 4) as avg_entry,
       ROUND(weighted_avg_entry * 1.04, 4) as aggregate_tp
FROM position_groups WHERE symbol = 'XRP/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"

# Trigger leg 0's per-leg TP only (2% above entry ~2.50 = 2.55)
# But NOT aggregate (4% above avg ~2.46 = 2.56)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/XRPUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 2.55}'
sleep 5

echo "=== After Per-Leg TP Trigger ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, status, tp_hit
FROM dca_orders WHERE symbol = 'XRP/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status,
       ROUND(realized_pnl_usd::numeric, 2) as realized_pnl
FROM position_groups WHERE symbol = 'XRP/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation

| Check | Expected |
|-------|----------|
| Leg 0 tp_hit | true |
| Leg 1 tp_hit | false |
| Position status | 'active' (not closed, leg 1 still needs TP) |
| Realized PnL | > 0 (from leg 0) |

---

## SCENARIO 7: Maximum Pyramids Limit Enforcement

### Objective
Validate that signals beyond max_pyramids are rejected.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'DOGE/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'DOGE/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"100\", \"tp_percent\": \"5\"}
  ]'::jsonb,
  'aggregate',
  '{\"tp_aggregate_percent\": 5}'::jsonb,
  2, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Set price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/DOGEUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.40}'

# Send 3 pyramid signals (max is 2)
for i in 1 2 3; do
  echo "=== Sending Pyramid $i ==="
  RESULT=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
      "secret": "ecd78c38d5ec54b4cd892735d0423671",
      "source": "tradingview",
      "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
      "tv": {"exchange": "mock", "symbol": "DOGE/USDT", "timeframe": 60, "action": "buy",
             "market_position": "long", "market_position_size": 100, "close_price": 0.40, "order_size": 100},
      "strategy_info": {"trade_id": "test_7_pyr'$i'", "alert_name": "Pyramid '$i'"},
      "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
      "risk": {"max_slippage_percent": 1.0}
    }')
  echo "$RESULT"
  sleep 3
done

# Check pyramid count
echo "=== Final Pyramid Count ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, pyramid_count, max_pyramids, status
FROM position_groups WHERE symbol = 'DOGE/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation

| Check | Expected |
|-------|----------|
| pyramid_count | 2 (max reached) |
| 3rd signal response | Error/rejected message |

---

## SCENARIO 8: Short Position Entry and TP

### Objective
Validate short positions with DCA levels going UP and TP triggering when price DROPS.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'LTC/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'LTC/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"50\", \"tp_percent\": \"3\"},
    {\"gap_percent\": \"2\", \"weight_percent\": \"50\", \"tp_percent\": \"4\"}
  ]'::jsonb,
  'aggregate',
  '{\"tp_aggregate_percent\": 5}'::jsonb,
  1, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Set price
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 100}'

# Short entry
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "LTC/USDT", "timeframe": 60, "action": "sell",
           "market_position": "short", "market_position_size": 500, "close_price": 100, "order_size": 500},
    "strategy_info": {"trade_id": "test_8_short", "alert_name": "Short Entry Test"},
    "execution_intent": {"type": "signal", "side": "sell", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Check DCA orders (for short, gap +2% means price level at 102)
echo "=== Short DCA Orders ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, ROUND(price::numeric, 2) as price,
       side, status, quantity
FROM dca_orders WHERE symbol = 'LTC/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, side, status FROM position_groups
WHERE symbol = 'LTC/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"

# Price rises to fill short DCA orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 105}'
sleep 5

echo "=== After Price Rise (filling short orders) ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, status, filled_quantity FROM dca_orders
WHERE symbol = 'LTC/USDT' ORDER BY leg_index;"

# Drop price to trigger short TP (5% below avg entry)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/LTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 95}'
sleep 5

echo "=== After Short TP Trigger ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, side, status, closed_at,
       ROUND(realized_pnl_usd::numeric, 2) as realized_pnl
FROM position_groups WHERE symbol = 'LTC/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation

| Check | Expected |
|-------|----------|
| DCA order side | 'sell' |
| DCA levels | Entry price and +2% (102) |
| Orders fill when | Price RISES above levels |
| TP triggers when | Price DROPS below entry |
| Position status after TP | 'closed' |
| realized_pnl | > 0 (profit from price drop) |

---

## SCENARIO 9: Exit Signal Closes Position Early

### Objective
Validate that an exit signal closes the position immediately, cancelling unfilled orders.

### Test Execution

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Use existing BTC config with limit orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 100000}'

# Entry signal
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "BTC/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 1000, "close_price": 100000, "order_size": 1000},
    "strategy_info": {"trade_id": "test_9_entry", "alert_name": "Exit Signal Test"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Fill only 2 of 4 orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 98500}'
sleep 5

echo "=== Before Exit - Partial Fill ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, status FROM dca_orders
WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status, filled_dca_legs, total_dca_legs
FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"

# Send EXIT signal
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "BTC/USDT", "timeframe": 60, "action": "sell",
           "market_position": "flat", "market_position_size": 0, "close_price": 98500, "order_size": 0},
    "strategy_info": {"trade_id": "test_9_exit", "alert_name": "Exit Signal"},
    "execution_intent": {"type": "exit", "side": "sell", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

echo "=== After Exit Signal ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status, closed_at,
       ROUND(realized_pnl_usd::numeric, 2) as realized_pnl
FROM position_groups WHERE symbol = 'BTC/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"

docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index, status FROM dca_orders
WHERE symbol = 'BTC/USDT' ORDER BY leg_index;"

# Check no orphaned orders on exchange
echo "=== Exchange Orders (should be empty) ==="
curl -s "http://127.0.0.1:9000/fapi/v1/openOrders?symbol=BTCUSDT" \
  -H "X-MBX-APIKEY: mock_api_key_12345"
```

### Validation

| Check | Expected |
|-------|----------|
| Position status | 'closed' |
| closed_at | NOT NULL |
| Unfilled order status | 'cancelled' |
| Exchange open orders | Empty |

---

## SCENARIO 10: Pool Capacity and Signal Queuing

### Objective
Validate that signals are queued when position pool is full, and promoted when slots open.

### Setup: Fill Pool to Capacity

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Check pool limit (should be 10 from risk_config)
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT (config_value->'max_open_positions_global')::int as pool_limit
FROM user_settings
WHERE user_id = 'f937c6cb-f9f9-4d25-be19-db9bf596d7e1'
AND setting_key = 'risk_config';"

# Create positions for multiple symbols using batch script
docker compose exec app python3 scripts/simulate_signals.py \
  --user zmomz \
  --exchange mock \
  --action buy \
  --capital 200 \
  --delay 2

sleep 10

# Check active position count
echo "=== Active Positions ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT COUNT(*) as active_positions
FROM position_groups
WHERE exchange = 'mock' AND status NOT IN ('closed', 'failed');"
```

### Test: Signal Queuing

```bash
# Try to add 11th position (should be queued)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 100000}'

RESULT=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "BTC/USDT", "timeframe": 240, "action": "buy",
           "market_position": "long", "market_position_size": 200, "close_price": 100000, "order_size": 200},
    "strategy_info": {"trade_id": "test_10_queued", "alert_name": "Should Queue"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }')

echo "Response: $RESULT"

# Check queued signals
echo "=== Queued Signals ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, timeframe, status, entry_price
FROM queued_signals WHERE exchange = 'mock'
ORDER BY created_at DESC LIMIT 5;"
```

### Test: Queue Promotion

```bash
# Close one position by triggering its TP
# Find a symbol with aggregate TP
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ADAUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 1.20}'
sleep 5

# Check if queued signal was promoted
echo "=== After Position Close ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, timeframe, status
FROM queued_signals WHERE exchange = 'mock'
ORDER BY created_at DESC LIMIT 5;"

docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT COUNT(*) as active_positions
FROM position_groups
WHERE exchange = 'mock' AND status NOT IN ('closed', 'failed');"
```

### Validation

| Check | Expected |
|-------|----------|
| Pool at capacity | 10 active positions |
| 11th signal | Queued (status = 'pending') |
| After position close | Queue promoted, pool stays at 10 |

---

## SCENARIO 11: PnL Calculation Accuracy

### Objective
Validate accurate calculation of invested amount, unrealized PnL, and realized PnL.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'AVAX/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels, tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'AVAX/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"40\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-2\", \"weight_percent\": \"30\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-4\", \"weight_percent\": \"30\", \"tp_percent\": \"2\"}
  ]'::jsonb,
  'aggregate',
  '{\"tp_aggregate_percent\": 5}'::jsonb,
  1, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Entry at $50
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/AVAXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 50}'

# Signal with $1000 capital
curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "AVAX/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 1000, "close_price": 50, "order_size": 1000},
    "strategy_info": {"trade_id": "test_11_pnl", "alert_name": "PnL Test"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'

sleep 5

# Fill all orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/AVAXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 46}'
sleep 5

# Check invested and entries
echo "=== After All Fills ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT leg_index,
       ROUND(price::numeric, 2) as price,
       ROUND(quantity::numeric, 4) as qty,
       ROUND((price * quantity)::numeric, 2) as value_usd
FROM dca_orders WHERE symbol = 'AVAX/USDT' ORDER BY leg_index;"

docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT ROUND(total_invested_usd::numeric, 2) as invested,
       ROUND(weighted_avg_entry::numeric, 4) as avg_entry,
       ROUND(total_filled_quantity::numeric, 4) as qty
FROM position_groups WHERE symbol = 'AVAX/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"

# Test unrealized PnL at different prices
for price in 44 48 52; do
  curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/AVAXUSDT/price" \
    -H "Content-Type: application/json" -d '{"price": '$price'}'
  sleep 2
  echo "=== Price at $price ==="
  docker compose exec db psql -U tv_user -d tv_engine_db -c "
  SELECT ROUND(unrealized_pnl_usd::numeric, 2) as unrealized_pnl,
         ROUND(unrealized_pnl_percent::numeric, 2) as unrealized_pct
  FROM position_groups WHERE symbol = 'AVAX/USDT' AND exchange = 'mock'
  ORDER BY created_at DESC LIMIT 1;"
done

# Trigger TP
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/AVAXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 55}'
sleep 5

echo "=== After TP - Final PnL ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT status,
       ROUND(total_invested_usd::numeric, 2) as invested,
       ROUND(realized_pnl_usd::numeric, 2) as realized_pnl,
       ROUND(realized_pnl_usd / total_invested_usd * 100, 2) as return_pct
FROM position_groups WHERE symbol = 'AVAX/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Expected Calculations

| Level | Weight | Price | Qty (for $1000 total) | Value |
|-------|--------|-------|----------------------|-------|
| 0 | 40% | 50.00 | 8.00 | $400 |
| 1 | 30% | 49.00 (-2%) | ~6.12 | $300 |
| 2 | 30% | 48.00 (-4%) | ~6.25 | $300 |

**Weighted Avg Entry:** (50*8 + 49*6.12 + 48*6.25) / (8+6.12+6.25) = ~49.1

**TP at 5% above avg:** 49.1 * 1.05 = ~51.55

**Realized PnL at price 55:** (55 - 49.1) * total_qty = ~$120 profit

---

## SCENARIO 12: Risk Engine Timer and Eligibility

### Objective
Validate risk timer starts when conditions are met and position becomes eligible after expiration.

### Setup: Create Losing Position with Max Pyramids

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Configure for 3 required pyramids (risk_config setting)
# Use TRX which has max_pyramids=4, pyramid_aggregate mode

curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.15}'

# Create 3 pyramids
for i in 1 2 3; do
  curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
      "secret": "ecd78c38d5ec54b4cd892735d0423671",
      "source": "tradingview",
      "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
      "tv": {"exchange": "mock", "symbol": "TRX/USDT", "timeframe": 60, "action": "buy",
             "market_position": "long", "market_position_size": 200, "close_price": 0.15, "order_size": 200},
      "strategy_info": {"trade_id": "test_12_pyr'$i'", "alert_name": "Risk Test Pyr '$i'"},
      "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
      "risk": {"max_slippage_percent": 1.0}
    }'
  sleep 3
done

# Fill all orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.12}'
sleep 5

# Create loss exceeding threshold (-1.5%)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.10}'
sleep 5

echo "=== Risk Timer Status ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, pyramid_count,
       ROUND(unrealized_pnl_percent::numeric, 2) as loss_pct,
       risk_timer_start,
       risk_timer_expires,
       risk_eligible
FROM position_groups WHERE symbol = 'TRX/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation

| Check | Expected |
|-------|----------|
| pyramid_count | 3 (meets required_pyramids_for_timer) |
| unrealized_pnl_percent | < -1.5% (exceeds loss_threshold) |
| risk_timer_start | NOT NULL |
| risk_timer_expires | timer_start + 15 minutes |
| risk_eligible | false (timer not expired) |

### Test Timer Reset on Recovery

```bash
# Improve price above threshold
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/TRXUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 0.145}'
sleep 5

echo "=== After Price Recovery ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol,
       ROUND(unrealized_pnl_percent::numeric, 2) as loss_pct,
       risk_timer_start,
       risk_eligible
FROM position_groups WHERE symbol = 'TRX/USDT' AND exchange = 'mock'
ORDER BY created_at DESC LIMIT 1;"
```

### Validation - Timer Reset

| Check | Expected |
|-------|----------|
| unrealized_pnl_percent | > -1.5% |
| risk_timer_start | NULL (reset) |
| risk_eligible | false |

---

## SCENARIO 13: Risk Offset Execution

### Objective
Validate that when eligible loser is offset, loser is closed and winners are partially closed.

### Setup: Create Loser and Winners

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Create LOSER position (BTC)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 100000}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "BTC/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 500, "close_price": 100000, "order_size": 500},
    "strategy_info": {"trade_id": "test_13_loser", "alert_name": "Loser"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'
sleep 3

# Create WINNER position (ETH)
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 4000}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "ETH/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 800, "close_price": 4000, "order_size": 800},
    "strategy_info": {"trade_id": "test_13_winner", "alert_name": "Winner"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'
sleep 5

# Fill orders
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 95000}'
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 3900}'
sleep 5

# Create loss on BTC, profit on ETH
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/BTCUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 85000}'
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/ETHUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 4500}'
sleep 5

echo "=== Before Offset ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status,
       ROUND(unrealized_pnl_usd::numeric, 2) as unrealized_pnl
FROM position_groups WHERE exchange = 'mock' AND status NOT IN ('closed', 'failed')
ORDER BY unrealized_pnl_usd ASC;"

# Make BTC loser eligible
docker compose exec db psql -U tv_user -d tv_engine_db -c "
UPDATE position_groups
SET risk_timer_start = NOW() - INTERVAL '20 minutes',
    risk_timer_expires = NOW() - INTERVAL '5 minutes',
    risk_eligible = true
WHERE symbol = 'BTC/USDT' AND exchange = 'mock' AND status NOT IN ('closed', 'failed');"

# Get auth token
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/users/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=zmomz&password=zm0mzzm0mz" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Trigger offset
curl -s -X POST "http://127.0.0.1:8000/api/v1/risk/run-evaluation" \
  -H "Authorization: Bearer $TOKEN"
sleep 5

echo "=== After Offset ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT symbol, status, closed_at,
       ROUND(realized_pnl_usd::numeric, 2) as realized_pnl
FROM position_groups WHERE exchange = 'mock'
ORDER BY created_at DESC;"

echo "=== Risk Actions Log ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT action_type,
       ROUND(loser_pnl_usd::numeric, 2) as loser_pnl,
       notes
FROM risk_actions ORDER BY timestamp DESC LIMIT 1;"
```

### Validation

| Check | Expected |
|-------|----------|
| BTC status | 'closed' |
| BTC realized_pnl | < 0 (loss) |
| ETH | Partially closed (hedge qty increased) or still open |
| Risk action logged | action_type = 'offset_loss' |

---

## SCENARIO 14: Pyramid-Specific DCA Levels

### Objective
Validate that pyramid_specific_levels override default dca_levels for specific pyramids.

### DCA Configuration Setup

```bash
docker compose exec db psql -U tv_user -d tv_engine_db -c "
DELETE FROM dca_configurations WHERE pair = 'SOL/USDT' AND exchange = 'mock' AND timeframe = 60;
INSERT INTO dca_configurations (
  id, user_id, pair, timeframe, exchange, entry_order_type,
  dca_levels,
  pyramid_specific_levels,
  tp_mode, tp_settings, max_pyramids, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'f937c6cb-f9f9-4d25-be19-db9bf596d7e1',
  'SOL/USDT', 60, 'mock', 'market',
  '[
    {\"gap_percent\": \"0\", \"weight_percent\": \"25\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-1\", \"weight_percent\": \"25\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-2\", \"weight_percent\": \"25\", \"tp_percent\": \"2\"},
    {\"gap_percent\": \"-3\", \"weight_percent\": \"25\", \"tp_percent\": \"2\"}
  ]'::jsonb,
  '{
    \"1\": [
      {\"gap_percent\": \"0\", \"weight_percent\": \"50\", \"tp_percent\": \"1.5\"},
      {\"gap_percent\": \"-0.5\", \"weight_percent\": \"50\", \"tp_percent\": \"1.5\"}
    ]
  }'::jsonb,
  'per_leg',
  '{\"tp_aggregate_percent\": 0}'::jsonb,
  2, true, NOW(), NOW()
);"
```

### Test Execution

```bash
# Clean
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

# Pyramid 0 entry
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 200}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "SOL/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 400, "close_price": 200, "order_size": 400},
    "strategy_info": {"trade_id": "test_14_pyr0", "alert_name": "Pyramid 0"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'
sleep 5

echo "=== Pyramid 0 DCA Orders (4 levels: 0%, -1%, -2%, -3%) ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT do.leg_index,
       ROUND(do.price::numeric, 2) as price,
       ROUND(do.weight_percent::numeric, 2) as weight,
       ROUND(do.tp_percent::numeric, 2) as tp_pct,
       p.pyramid_index
FROM dca_orders do
JOIN pyramids p ON do.pyramid_id = p.id
WHERE do.symbol = 'SOL/USDT'
ORDER BY p.pyramid_index, do.leg_index;"

# Pyramid 1 entry
curl -s -X PUT "http://127.0.0.1:9000/admin/symbols/SOLUSDT/price" \
  -H "Content-Type: application/json" -d '{"price": 190}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "ecd78c38d5ec54b4cd892735d0423671",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "SOL/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 400, "close_price": 190, "order_size": 400},
    "strategy_info": {"trade_id": "test_14_pyr1", "alert_name": "Pyramid 1"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }'
sleep 5

echo "=== Pyramid 1 DCA Orders (should have 2 levels: 0%, -0.5%) ==="
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT do.leg_index,
       ROUND(do.price::numeric, 2) as price,
       ROUND(do.weight_percent::numeric, 2) as weight,
       ROUND(do.tp_percent::numeric, 2) as tp_pct,
       p.pyramid_index
FROM dca_orders do
JOIN pyramids p ON do.pyramid_id = p.id
WHERE do.symbol = 'SOL/USDT'
ORDER BY p.pyramid_index, do.leg_index;"
```

### Validation

| Pyramid | Expected Levels | Expected Weights |
|---------|-----------------|------------------|
| 0 | 4 (0%, -1%, -2%, -3%) | 25% each |
| 1 | 2 (0%, -0.5%) | 50% each |

---

## SCENARIO 15: Webhook Authentication Failure

### Objective
Validate that invalid webhook secret is rejected.

### Test Execution

```bash
RESULT=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/webhooks/f937c6cb-f9f9-4d25-be19-db9bf596d7e1/tradingview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "f937c6cb-f9f9-4d25-be19-db9bf596d7e1",
    "secret": "wrong_secret_12345",
    "source": "tradingview",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'",
    "tv": {"exchange": "mock", "symbol": "BTC/USDT", "timeframe": 60, "action": "buy",
           "market_position": "long", "market_position_size": 100, "close_price": 100000, "order_size": 100},
    "strategy_info": {"trade_id": "test_15_bad_auth", "alert_name": "Bad Auth"},
    "execution_intent": {"type": "signal", "side": "buy", "position_size_type": "quote"},
    "risk": {"max_slippage_percent": 1.0}
  }')

echo "Response: $RESULT"

# Check no position created
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT COUNT(*) as positions
FROM position_groups
WHERE exchange = 'mock' AND status NOT IN ('closed', 'failed');"
```

### Validation

| Check | Expected |
|-------|----------|
| HTTP Response | 401 or 403 |
| Error message | Authentication/authorization error |
| Position created | No |

---

## CLEANUP SCRIPT

```bash
#!/bin/bash
# cleanup.sh - Reset environment to clean state

echo "Cleaning positions..."
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

echo "Clearing queue..."
docker compose exec db psql -U tv_user -d tv_engine_db -c "DELETE FROM queued_signals;"

echo "Resetting mock exchange..."
curl -s -X DELETE "http://127.0.0.1:9000/admin/reset"

echo "Verifying clean state..."
docker compose exec db psql -U tv_user -d tv_engine_db -c "
SELECT
  (SELECT COUNT(*) FROM position_groups WHERE status NOT IN ('closed', 'failed')) as active_positions,
  (SELECT COUNT(*) FROM queued_signals) as queued_signals,
  (SELECT COUNT(*) FROM dca_orders WHERE status NOT IN ('filled', 'cancelled')) as pending_orders;"

echo "Cleanup complete."
```

---

## TEST EXECUTION MATRIX

| Scenario | Description | Config Focus | Validation Focus |
|----------|-------------|--------------|------------------|
| 1 | Limit Entry Progressive Fills | entry_order_type=limit, 4 levels | Order placement, progressive fills |
| 2 | Market Entry Immediate Fill | entry_order_type=market | Immediate fill of leg 0 |
| 3 | Per-Leg TP | tp_mode=per_leg | Individual TP per leg |
| 4 | Aggregate TP | tp_mode=aggregate | Single TP closes all |
| 5 | Pyramid Aggregate TP | tp_mode=pyramid_aggregate | Per-pyramid TP |
| 6 | Hybrid TP | tp_mode=hybrid | Both TP types work |
| 7 | Max Pyramids | max_pyramids limit | Rejection of excess |
| 8 | Short Position | side=short | Inverse DCA/TP logic |
| 9 | Exit Signal | execution_intent.type=exit | Early close |
| 10 | Pool/Queue | Risk config limits | Queue behavior |
| 11 | PnL Accuracy | Multiple levels/weights | Calculation validation |
| 12 | Risk Timer | Risk config thresholds | Timer mechanics |
| 13 | Risk Offset | Eligible loser | Offset execution |
| 14 | Pyramid-Specific | pyramid_specific_levels | Config override |
| 15 | Auth Failure | Bad secret | Rejection |

---

## NOTES

1. **Wait Times**: Allow 3-5 seconds between price changes for order fill detection
2. **Order Fill Logic**:
   - Long limit orders fill when price drops to/below order price
   - Short limit orders fill when price rises to/above order price
3. **TP Trigger Logic**:
   - Long TP triggers when price rises above TP price
   - Short TP triggers when price drops below TP price
4. **Weighted Average**: Calculated from (sum of price*qty) / (sum of qty) for filled orders
5. **Risk Timer**: Requires both pyramids complete AND loss threshold exceeded to start
6. **Queue Priority**: Deepest loss %, then replacement count, then FIFO
7. **Mock Exchange**: Price changes via admin API immediately update mark price and trigger order matching
