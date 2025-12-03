#!/bin/bash
# quick_full_test.sh

echo "=== Starting Complete Test ==="

# 1. Clean
echo "Cleaning existing positions..."
docker compose exec app python3 scripts/clean_user_positions.py --username maaz --confirm true

# 2. Core flow
echo "Testing core position flow..."
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id c788bbcd-57e7-42f7-aa06-870a8dfc994f \
  --secret 453d64c9bda97b766a1500522dc3143d \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 70000

# 3. Fill pool
echo "Filling pool to capacity..."
for i in {1..9}; do
  symbols=("ETHUSDT" "SOLUSDT" "DOTUSDT" "XRPUSDT" "TRXUSDT" "DOGEUSDT" "ADAUSDT" "GALAUSDT")
  symbol_index=$((i % 8))
  docker compose exec app python3 scripts/simulate_webhook.py \
    --user-id c788bbcd-57e7-42f7-aa06-870a8dfc994f \
    --secret 453d64c9bda97b766a1500522dc3143d \
    --exchange binance \
    --symbol ${symbols[$symbol_index]} \
    --timeframe 60 \
    --side long \
    --type signal \
    --entry-price 1000
done

# 4. Queue test
echo "Testing queue..."
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id c788bbcd-57e7-42f7-aa06-870a8dfc994f \
  --secret 453d64c9bda97b766a1500522dc3143d \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 70000

echo "=== Test Complete ==="
echo "Check logs: docker compose logs --tail 100 app"
echo "Check positions: docker compose exec app python3 scripts/export_user_positions.py --type positions --format json"
