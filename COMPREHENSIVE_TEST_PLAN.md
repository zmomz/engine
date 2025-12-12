already set configuration:
{
  "exchange": "binance",
  "risk_config": {
    "max_open_positions_global": 10,
    "max_open_positions_per_symbol": 1,
    "max_total_exposure_usd": "999",
    "max_daily_loss_usd": "500",
    "risk_per_position_percent": "10.0",
    "risk_per_position_cap_usd": null,
    "loss_threshold_percent": "-1.5",
    "timer_start_condition": "after_all_dca_filled",
    "post_full_wait_minutes": 15,
    "max_winners_to_combine": 3,
    "use_trade_age_filter": false,
    "age_threshold_minutes": 120,
    "require_full_pyramids": true,
    "reset_timer_on_replacement": false,
    "partial_close_enabled": true,
    "min_close_notional": "10",
    "priority_rules": {
      "priority_rules_enabled": {
        "same_pair_timeframe": true,
        "deepest_loss_percent": true,
        "highest_replacement": true,
        "fifo_fallback": true
      },
      "priority_order": [
        "same_pair_timeframe",
        "deepest_loss_percent",
        "highest_replacement",
        "fifo_fallback"
      ]
    }
  },
  "dca_configurations": [
    {
      "pair": "BTC/USDT",
      "timeframe": 60,
      "exchange": "binance",
      "entry_order_type": "limit",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "25",
          "tp_percent": "1"
        },
        {
          "gap_percent": "-1",
          "weight_percent": "25",
          "tp_percent": "1"
        },
        {
          "gap_percent": "-2",
          "weight_percent": "25",
          "tp_percent": "1"
        },
        {
          "gap_percent": "-3",
          "weight_percent": "25",
          "tp_percent": "1"
        }
      ],
      "pyramid_specific_levels": {
        "1": [
          {
            "gap_percent": "0",
            "weight_percent": "50",
            "tp_percent": "1.5"
          },
          {
            "gap_percent": "-1",
            "weight_percent": "50",
            "tp_percent": "1.5"
          }
        ],
        "2": [
          {
            "gap_percent": "0",
            "weight_percent": "100",
            "tp_percent": "2"
          }
        ]
      },
      "tp_mode": "per_leg",
      "tp_settings": {
        "tp_aggregate_percent": 0
      },
      "max_pyramids": 2
    },
    {
      "pair": "ETH/USDT",
      "timeframe": 60,
      "exchange": "binance",
      "entry_order_type": "market",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "33",
          "tp_percent": "0.5"
        },
        {
          "gap_percent": "-0.5",
          "weight_percent": "33",
          "tp_percent": "0.5"
        },
        {
          "gap_percent": "-1",
          "weight_percent": "34",
          "tp_percent": "0.5"
        }
      ],
      "pyramid_specific_levels": {},
      "tp_mode": "aggregate",
      "tp_settings": {
        "tp_aggregate_percent": 5
      },
      "max_pyramids": 3
    },
    {
      "pair": "SOL/USDT",
      "timeframe": 60,
      "exchange": "bybit",
      "entry_order_type": "limit",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "20",
          "tp_percent": "2"
        },
        {
          "gap_percent": "-1",
          "weight_percent": "20",
          "tp_percent": "2"
        },
        {
          "gap_percent": "-2",
          "weight_percent": "20",
          "tp_percent": "2"
        },
        {
          "gap_percent": "-3",
          "weight_percent": "20",
          "tp_percent": "2"
        },
        {
          "gap_percent": "-4",
          "weight_percent": "20",
          "tp_percent": "2"
        }
      ],
      "pyramid_specific_levels": {
        "1": [
          {
            "gap_percent": "0",
            "weight_percent": "25",
            "tp_percent": "1"
          },
          {
            "gap_percent": "-1",
            "weight_percent": "25",
            "tp_percent": "1"
          },
          {
            "gap_percent": "-2",
            "weight_percent": "25",
            "tp_percent": "1"
          },
          {
            "gap_percent": "-3",
            "weight_percent": "25",
            "tp_percent": "1"
          }
        ]
      },
      "tp_mode": "aggregate",
      "tp_settings": {
        "tp_aggregate_percent": 3
      },
      "max_pyramids": 1
    },
    {
      "pair": "XRP/USDT",
      "timeframe": 60,
      "exchange": "binance",
      "entry_order_type": "market",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "50",
          "tp_percent": "1"
        },
        {
          "gap_percent": "-2",
          "weight_percent": "50",
          "tp_percent": "1"
        }
      ],
      "pyramid_specific_levels": {},
      "tp_mode": "hybrid",
      "tp_settings": {
        "tp_aggregate_percent": 2
      },
      "max_pyramids": 5
    },
    {
      "pair": "DOGE/USDT",
      "timeframe": 60,
      "exchange": "bybit",
      "entry_order_type": "limit",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "10",
          "tp_percent": "3"
        },
        {
          "gap_percent": "-0.5",
          "weight_percent": "15",
          "tp_percent": "3"
        },
        {
          "gap_percent": "-1",
          "weight_percent": "20",
          "tp_percent": "3"
        },
        {
          "gap_percent": "-1.5",
          "weight_percent": "25",
          "tp_percent": "3"
        },
        {
          "gap_percent": "-2",
          "weight_percent": "30",
          "tp_percent": "3"
        }
      ],
      "pyramid_specific_levels": {
        "1": [
          {
            "gap_percent": "0",
            "weight_percent": "30",
            "tp_percent": "2.5"
          },
          {
            "gap_percent": "-1",
            "weight_percent": "70",
            "tp_percent": "2.5"
          }
        ],
        "2": [
          {
            "gap_percent": "0",
            "weight_percent": "40",
            "tp_percent": "2"
          },
          {
            "gap_percent": "-0.5",
            "weight_percent": "60",
            "tp_percent": "2"
          }
        ],
        "3": [
          {
            "gap_percent": "0",
            "weight_percent": "100",
            "tp_percent": "1.5"
          }
        ]
      },
      "tp_mode": "per_leg",
      "tp_settings": {
        "tp_aggregate_percent": 0
      },
      "max_pyramids": 3
    },
    {
      "pair": "ADA/USDT",
      "timeframe": 60,
      "exchange": "binance",
      "entry_order_type": "market",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "100",
          "tp_percent": "0.5"
        }
      ],
      "pyramid_specific_levels": {},
      "tp_mode": "aggregate",
      "tp_settings": {
        "tp_aggregate_percent": 10
      },
      "max_pyramids": 1
    },
    {
      "pair": "DOT/USDT",
      "timeframe": 60,
      "exchange": "bybit",
      "entry_order_type": "limit",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "15",
          "tp_percent": "1"
        },
        {
          "gap_percent": "-0.3",
          "weight_percent": "15",
          "tp_percent": "1"
        },
        {
          "gap_percent": "-0.6",
          "weight_percent": "20",
          "tp_percent": "1"
        },
        {
          "gap_percent": "-1",
          "weight_percent": "20",
          "tp_percent": "1"
        },
        {
          "gap_percent": "-1.5",
          "weight_percent": "30",
          "tp_percent": "1"
        }
      ],
      "pyramid_specific_levels": {
        "1": [
          {
            "gap_percent": "0",
            "weight_percent": "35",
            "tp_percent": "0.8"
          },
          {
            "gap_percent": "-0.5",
            "weight_percent": "35",
            "tp_percent": "0.8"
          },
          {
            "gap_percent": "-1",
            "weight_percent": "30",
            "tp_percent": "0.8"
          }
        ],
        "2": [
          {
            "gap_percent": "0",
            "weight_percent": "50",
            "tp_percent": "0.6"
          },
          {
            "gap_percent": "-1.5",
            "weight_percent": "50",
            "tp_percent": "0.6"
          }
        ]
      },
      "tp_mode": "hybrid",
      "tp_settings": {
        "tp_aggregate_percent": 3
      },
      "max_pyramids": 2
    },
    {
      "pair": "TRX/USDT",
      "timeframe": 60,
      "exchange": "binance",
      "entry_order_type": "market",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "16.67",
          "tp_percent": "1.5"
        },
        {
          "gap_percent": "-0.5",
          "weight_percent": "16.67",
          "tp_percent": "1.5"
        },
        {
          "gap_percent": "-1",
          "weight_percent": "16.66",
          "tp_percent": "1.5"
        },
        {
          "gap_percent": "-1.5",
          "weight_percent": "16.67",
          "tp_percent": "1.5"
        },
        {
          "gap_percent": "-2",
          "weight_percent": "16.67",
          "tp_percent": "1.5"
        },
        {
          "gap_percent": "-2.5",
          "weight_percent": "16.66",
          "tp_percent": "1.5"
        }
      ],
      "pyramid_specific_levels": {},
      "tp_mode": "aggregate",
      "tp_settings": {
        "tp_aggregate_percent": 4
      },
      "max_pyramids": 4
    },
    {
      "pair": "MATIC/USDT",
      "timeframe": 60,
      "exchange": "bybit",
      "entry_order_type": "limit",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "40",
          "tp_percent": "0.8"
        },
        {
          "gap_percent": "-1.5",
          "weight_percent": "60",
          "tp_percent": "0.8"
        }
      ],
      "pyramid_specific_levels": {
        "1": [
          {
            "gap_percent": "0",
            "weight_percent": "100",
            "tp_percent": "1.2"
          }
        ]
      },
      "tp_mode": "per_leg",
      "tp_settings": {
        "tp_aggregate_percent": 0
      },
      "max_pyramids": 1
    },
    {
      "pair": "LINK/USDT",
      "timeframe": 60,
      "exchange": "binance",
      "entry_order_type": "market",
      "dca_levels": [
        {
          "gap_percent": "0",
          "weight_percent": "12.5",
          "tp_percent": "2.5"
        },
        {
          "gap_percent": "-0.4",
          "weight_percent": "12.5",
          "tp_percent": "2.5"
        },
        {
          "gap_percent": "-0.8",
          "weight_percent": "12.5",
          "tp_percent": "2.5"
        },
        {
          "gap_percent": "-1.2",
          "weight_percent": "12.5",
          "tp_percent": "2.5"
        },
        {
          "gap_percent": "-1.6",
          "weight_percent": "12.5",
          "tp_percent": "2.5"
        },
        {
          "gap_percent": "-2",
          "weight_percent": "12.5",
          "tp_percent": "2.5"
        },
        {
          "gap_percent": "-2.5",
          "weight_percent": "12.5",
          "tp_percent": "2.5"
        },
        {
          "gap_percent": "-3",
          "weight_percent": "12.5",
          "tp_percent": "2.5"
        }
      ],
      "pyramid_specific_levels": {
        "1": [
          {
            "gap_percent": "0",
            "weight_percent": "20",
            "tp_percent": "2"
          },
          {
            "gap_percent": "-0.5",
            "weight_percent": "20",
            "tp_percent": "2"
          },
          {
            "gap_percent": "-1",
            "weight_percent": "20",
            "tp_percent": "2"
          },
          {
            "gap_percent": "-1.5",
            "weight_percent": "20",
            "tp_percent": "2"
          },
          {
            "gap_percent": "-2",
            "weight_percent": "20",
            "tp_percent": "2"
          }
        ],
        "2": [
          {
            "gap_percent": "0",
            "weight_percent": "33.33",
            "tp_percent": "1.5"
          },
          {
            "gap_percent": "-1",
            "weight_percent": "33.33",
            "tp_percent": "1.5"
          },
          {
            "gap_percent": "-2",
            "weight_percent": "33.34",
            "tp_percent": "1.5"
          }
        ],
        "3": [
          {
            "gap_percent": "0",
            "weight_percent": "50",
            "tp_percent": "1"
          },
          {
            "gap_percent": "-1.5",
            "weight_percent": "50",
            "tp_percent": "1"
          }
        ]
      },
      "tp_mode": "aggregate",
      "tp_settings": {
        "tp_aggregate_percent": 7
      },
      "max_pyramids": 3
    }
  ]
}



---------
# 🧪 COMPREHENSIVE PRACTICAL TEST PLAN
## Trading Execution Engine - Full System Validation

**Date:** To be executed tomorrow
**Duration:** ~4-6 hours
**Environment:** Bybit and Binance Testnet
**Prerequisites:** Clean database, funded testnet accounts

**User Credentials:**
- USER_ID: `7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95`
- WEBHOOK_SECRET: `2884078ee5be6cf08ef525b7ea798e78`

---

## 📋 ALLOWED SCRIPTS ONLY

**The following scripts are the ONLY ones allowed for testing:**

```bash
# 1. Clean positions from database
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# 2. Clean positions from exchanges (Binance & Bybit)
docker compose exec app python3 scripts/clean_positions_in_exchanges.py

# 3. Check exchange positions, open orders, filled orders, closed orders and balances
docker compose exec app python3 scripts/verify_exchange_positions.py

# 4. Check queue (list queued signals)
docker compose exec app python3 scripts/list_queue.py

# 5. Simulate webhook (buy order)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 96000.0 \
  --order-size 0.001
```

---

## 📋 PRE-TEST SETUP

### 1. Environment Preparation (10 mins)

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

### 2. Verify Configuration (10 mins)

**GUI Verification:**

1. Open browser: `http://localhost:3000`
2. Login with credentials
3. Navigate to **Settings** page
4. Verify DCA configurations exist for test pairs
5. Note Risk Engine settings

**Expected Result:**

- ✅ DCA configs present for test pairs
- ✅ Risk engine configured
- ✅ Execution pool configured

---

## 🔥 TEST SUITE 1: BASIC SIGNAL INGESTION & EXECUTION (30 mins)

### Test 1.1: First Entry Signal - Single Position Creation

```bash
# Send entry signal for BTCUSDT on Binance (get current price first from exchange)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 96000.0 \
  --order-size 0.001

# Verify orders on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py

# Verify GUI: Open Dashboard -> should show 1 active position
```

**Expected Result:**

- ✅ Position group created in DB
- ✅ DCA orders submitted to exchange
- ✅ Dashboard shows 1 active position
- ✅ Positions page shows expandable BTCUSDT group
- ✅ All DCA legs visible with PENDING/OPEN status

**Verification Points:**

- Position group ID created
- Pyramid count = 1
- DCA orders count = number configured (e.g., 5 legs)
- Exchange has open limit orders

---

### Test 1.2: Pyramid Signal - Add to Existing Group

```bash
# Send another entry for same pair/timeframe (should pyramid)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95500.0 \
  --order-size 0.001

# Verify
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Same position group (not new one)
- ✅ Pyramid count = 2
- ✅ New set of DCA orders submitted
- ✅ Total DCA orders = 2 × DCA legs configured
- ✅ GUI shows pyramid count increased

---

### Test 1.3: Different Exchange - New Group

```bash
# Send entry for a different pair/exchange (SOLUSDT on Bybit)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange bybit \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 133.0 \
  --order-size 0.1

# Verify
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ NEW position group created (different exchange)
- ✅ Total active groups = 2
- ✅ Dashboard shows 2 active positions

---

### Test 1.4: Different Pair - New Group

```bash
# Send entry for different pair (Ethereum on Binance)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 3600.0 \
  --order-size 0.01

# Verify
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Total active groups = 3
- ✅ Dashboard shows 3 active positions
- ✅ Positions page shows all 3 groups

---

## 🔥 TEST SUITE 2: EXECUTION POOL & QUEUE SYSTEM (45 mins)

### Test 2.1: Fill Pool to Capacity

```bash
# We already have 3 positions. Add 2 more to reach limit of 5 (adjust based on your pool size).

# Position 4 - XRP (on Binance)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.5234 \
  --order-size 10

# Position 5 - DOGE (on Bybit)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange bybit \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.38456 \
  --order-size 100

# Verify pool is full
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Active positions = 5 (pool full)
- ✅ Dashboard shows pool usage: 5/5

---

### Test 2.2: Queue Entry When Pool Full

```bash
# Try to add 6th position (should queue)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 1.1 \
  --order-size 20

# Verify queued
docker compose exec app python3 scripts/list_queue.py
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Signal added to queue (not executed)
- ✅ Queue page shows 1 queued signal
- ✅ Active positions still = 5
- ✅ No orders on exchange for ADAUSDT

---

### Test 2.3: Queue Another Signal (Same Pair as Queued)

```bash
# Send another signal for ADAUSDT (should replace in queue)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 1.15 \
  --order-size 20

# Verify
docker compose exec app python3 scripts/list_queue.py
```

**Expected Result:**

- ✅ Queue still has 1 entry (not 2)
- ✅ Replacement count increased
- ✅ Latest price/data updated

---

### Test 2.4: Queue Promotion Test

```bash
# Manually close all positions to test queue promotion
docker compose exec app python3 scripts/clean_positions_in_exchanges.py
docker compose exec app python3 scripts/clean_positions_in_db.py --username zmomz --confirm true

# Verify ADAUSDT was promoted from queue
docker compose exec app python3 scripts/list_queue.py
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ After cleaning: pool freed
- ✅ ADAUSDT may be promoted automatically if queue promotion logic runs
- ✅ Verify via GUI Queue page

---

## 🔥 TEST SUITE 3: DCA FILLS & TAKE-PROFIT (Manual Testing via GUI)

### Test 3.1: Monitor DCA Order Fills

**Manual Verification:**

```bash
# Create a position with entry price very close to current market price
# First, check current prices on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py

# Place order with price 0.1% below current market (to get filled quickly)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 95800.0 \
  --order-size 0.001

# Wait a few minutes, then verify fills
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ DCA orders get filled as market moves
- ✅ Position shows weighted average entry updated
- ✅ Unrealized PnL calculated
- ✅ GUI shows fill progress in Positions page
- ✅ Filled orders show with timestamps

---

### Test 3.2: Take-Profit Order Creation

**Manual Observation:**

1. After DCA orders are filled, check exchange for TP orders
2. Verify TP orders are created automatically
3. Check GUI Positions page for TP order details

```bash
# Verify TP orders on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ TP orders created for filled DCA legs
- ✅ TP prices calculated correctly based on configuration
- ✅ GUI shows TP orders in position details
- ✅ When TP hits: position partially or fully closes

---

## 🔥 TEST SUITE 4: PRECISION VALIDATION (20 mins)

### Test 4.1: Valid Symbol - Orders Respect Precision

```bash
# Send signal for valid pair with precise decimal values
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 2.5234 \
  --order-size 10

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
# DOGEUSDT (typically 5 decimals for price)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange bybit \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.38456 \
  --order-size 100

# Verify
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Orders created with correct precision per symbol
- ✅ No exchange rejection errors
- ✅ All assets trade successfully

---

## 🔥 TEST SUITE 5: RISK ENGINE (Manual GUI Testing)

### Test 5.1: Risk Engine Monitoring

**Manual Verification via GUI:**

1. Navigate to **Risk Control Panel** page
2. Create losing and winning positions by placing orders
3. Observe Risk Engine status and evaluations

**What to Verify:**

- ✅ Risk Control Panel displays current risk status
- ✅ Shows identified losing positions
- ✅ Shows available winning positions
- ✅ Timer countdown visible (if configured)
- ✅ Eligible/Not Eligible status shown
- ✅ Projected offset plan displayed

---

### Test 5.2: Risk Actions via GUI

**Manual Testing:**

1. Use Risk Control Panel buttons:
   - **Block Button**: Prevents risk engine from closing position
   - **Skip Next Button**: Skips next evaluation cycle
   - **Run Evaluation Now**: Manually triggers risk evaluation

2. Observe behavior in GUI and exchange

```bash
# Verify actions on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Risk engine respects block/skip actions
- ✅ Manual evaluation triggers correctly
- ✅ Recent Actions table logs all risk actions
- ✅ Positions close when risk conditions met

---

## 🔥 TEST SUITE 6: WEB GUI VALIDATION (60 mins)

### Test 6.1: Dashboard Page

**Manual Verification in Browser:**

1. Open `http://localhost:3000` and navigate to Dashboard
2. Check **Live Dashboard** tab displays:
   - ✅ Engine Status: Running
   - ✅ Risk Engine Status
   - ✅ Total PnL calculated correctly
   - ✅ TVL shows testnet balance
   - ✅ Active Position Groups count
   - ✅ Queued Signals count
   - ✅ Capital Deployed percentage

3. Switch to **Performance Analytics** tab:
   - ✅ PnL metrics (Today, Week, Month, All Time)
   - ✅ Equity curve chart
   - ✅ Win/Loss statistics
   - ✅ Trade distribution charts

4. Verify real-time updates (auto-refresh)

---

### Test 6.2: Positions Page

**Manual Verification:**

1. Open Positions page
2. Verify table shows all active positions with:
   - ✅ Symbol, Timeframe, Exchange
   - ✅ Pyramids count
   - ✅ Average Entry price
   - ✅ Current Price (updating)
   - ✅ Unrealized PnL % and $ (color-coded)
   - ✅ Status, Risk Timer, Created At

3. Click expand button on a position:
   - ✅ Shows DCA legs with prices, quantities, status
   - ✅ Shows TP orders
   - ✅ Shows fill timestamps

```bash
# Verify positions match exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

---

### Test 6.3: Queue Page

**Manual Verification:**

1. Open Queue page (when queue has entries)
2. Verify table shows:
   - ✅ Symbol, Timeframe, Direction
   - ✅ Queue Age, Replacement Count
   - ✅ Priority Rank, Status

```bash
# Verify queue via script
docker compose exec app python3 scripts/list_queue.py
```

---

### Test 6.4: Settings Page

**Manual Verification:**

1. Open Settings page
2. Verify all configuration sections load:
   - ✅ Exchange API Settings
   - ✅ Execution Pool settings
   - ✅ Risk Engine Configuration
   - ✅ DCA Configurations table

3. Test functionality:
   - ✅ Modify settings and save
   - ✅ Add/Edit DCA configs
   - ✅ Verify changes persist after refresh

---

## 🔥 TEST SUITE 7: BASIC SYSTEM HEALTH (30 mins)

### Test 7.1: Clean Slate Test

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

### Test 7.2: Multiple Position Management

```bash
# Create multiple positions across both exchanges
# Bybit positions - DOGEUSDT
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange bybit \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.38456 \
  --order-size 100

docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange bybit \
  --symbol MATICUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.8 \
  --order-size 10

# Binance positions
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 96000.0 \
  --order-size 0.001

# Verify all positions
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Result:**

- ✅ Multiple positions created across both exchanges
- ✅ All positions visible in GUI
- ✅ Exchange orders match database records
- ✅ No conflicts or errors

---

## 🔥 TEST SUITE 8: SYSTEM PERSISTENCE (15 mins)

### Test 8.1: Application Restart Persistence

```bash
# Create some positions (DOGEUSDT on Bybit)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 7df5b1ed-b024-4c2a-9ac7-f67e09d5cb95 \
  --secret 2884078ee5be6cf08ef525b7ea798e78 \
  --exchange bybit \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --action buy \
  --entry-price 0.38456 \
  --order-size 100

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
- ✅ GUI reconnects and shows same state
- ✅ System continues functioning normally

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

### ✅ GUI Functionality

**Manual Checklist:**

- ✅ All pages load without errors (Dashboard, Positions, Queue, Settings, Risk)
- ✅ Real-time updates working (auto-refresh)
- ✅ All buttons and controls functional
- ✅ Data displays correctly
- ✅ No console errors in browser DevTools
- ✅ Position details expand/collapse correctly

---

### ✅ Queue System

```bash
# Verify queue state
docker compose exec app python3 scripts/list_queue.py
```

**Expected:**

- ✅ Queue page shows accurate data
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

### TEST SUITE 3: DCA Fills & Take-Profit
- [ ] Test 3.1: Monitor DCA Fills - ✅ PASS / ❌ FAIL
- [ ] Test 3.2: TP Order Creation - ✅ PASS / ❌ FAIL

### TEST SUITE 4: Precision Validation
- [ ] Test 4.1: Valid Symbol Precision - ✅ PASS / ❌ FAIL
- [ ] Test 4.2: Multiple Asset Precision - ✅ PASS / ❌ FAIL

### TEST SUITE 5: Risk Engine
- [ ] Test 5.1: Risk Engine Monitoring - ✅ PASS / ❌ FAIL
- [ ] Test 5.2: Risk Actions via GUI - ✅ PASS / ❌ FAIL

### TEST SUITE 6: Web GUI Validation
- [ ] Test 6.1: Dashboard Page - ✅ PASS / ❌ FAIL
- [ ] Test 6.2: Positions Page - ✅ PASS / ❌ FAIL
- [ ] Test 6.3: Queue Page - ✅ PASS / ❌ FAIL
- [ ] Test 6.4: Settings Page - ✅ PASS / ❌ FAIL

### TEST SUITE 7: Basic System Health
- [ ] Test 7.1: Clean Slate Test - ✅ PASS / ❌ FAIL
- [ ] Test 7.2: Multiple Position Management - ✅ PASS / ❌ FAIL

### TEST SUITE 8: System Persistence
- [ ] Test 8.1: Application Restart - ✅ PASS / ❌ FAIL

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

**Tests MUST pass:**

- ✅ All basic signal ingestion tests pass
- ✅ Pool and queue system works correctly
- ✅ DCA orders created and filled properly
- ✅ TP orders created correctly
- ✅ No data loss or corruption
- ✅ GUI fully functional
- ✅ Risk engine operates correctly
- ✅ Exchange precision validation prevents rejections

**GUI Requirements:**

- ✅ All pages accessible and functional
- ✅ Real-time data updates visible
- ✅ Position details show correctly
- ✅ Charts and analytics render properly

---

## 📝 NOTES

- Use only the 5 allowed scripts for all testing
- All webhook simulations use the provided user credentials
- Check both Bybit and Binance testnets
- Verify exchange state matches GUI and database
- Test with realistic market prices (check current prices first)

---

**Good luck with testing! 🚀**
