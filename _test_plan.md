# **Complete Optimized Testing Plan**

## **Test User Credentials**
```
username : maaz
user-id : 491ba4af-56b9-46ea-922d-d58e077e9b9c 
secret : 2e86de391d459bd0d920e88dd1291798 
```
current prices use it as entry prices: { "BTCUSDT": 87145.3, "ETHUSDT": 2823.0, "SOLUSDT": 127.97, "DOTUSDT": 2.095, "XRPUSDT": 2.03, "TRXUSDT": 0.278, "DOGEUSDT": 0.1368, "ADAUSDT": 0.393, "GALAUSDT": 0.0067 }
---

## **Phase 1: Core Position Lifecycle (Single Exchange)**

### **Test 1.1: Basic Entry → DCA → Exit**

#### **Step 1: Create Base Position**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# 1. Check webhook response in logs
docker compose logs --tail 50 app | grep -E "(webhook|signal|position|BTCUSDT)"

# 2. Check database positions
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Verify exchange positions
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] Signal received & parsed successfully
- [ ] Position Group created with DCA grid (3 legs: 0%, -1%, -2% gaps)
- [ ] Pool count: 1/10
- [ ] Orders visible on Binance exchange

---

#### **Step 2: Add Pyramid (DCA)**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 87245.3
```

**Verification:**
```bash
# 1. Check logs for pyramid addition
docker compose logs --tail 50 app | grep -E "(pyramid|BTCUSDT)"

# 2. Check database
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Verify exchange positions
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] Pyramid added successfully (bypasses pool limit)
- [ ] Total pyramids: 2/5
- [ ] Pool count remains: 1/10 (same position group)
- [ ] Additional orders on exchange

---

#### **Step 2.5: Simulate Order Fills**
```bash
docker compose exec app python3 scripts/fill_dca_orders.py
```

**Verification:**
```bash
# 1. Check logs for order fills and stats update
docker compose logs --tail 100 app | grep -E "(filled|position_stats|risk_timer|BTCUSDT)"

# 2. Check database positions for filled quantity and updated status
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Verify exchange positions (open orders should be gone or reduced)
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] All open DCA orders marked as FILLED in the database.
- [ ] `total_filled_quantity` in PositionGroup > 0.
- [ ] `weighted_avg_entry` and `realized_pnl_usd` updated.
- [ ] Position status updated to `PARTIALLY_FILLED` or `ACTIVE`.
- [ ] Open orders on exchange are cancelled or filled.

---

#### **Step 3: Exit Entire Position Group**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --type exit
```

**Verification:**
```bash
# 1. Check logs for exit signal
docker compose logs --tail 50 app | grep -E "(exit|close|BTCUSDT)"

# 2. Check database
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Verify exchange positions (should be empty for BTCUSDT)
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] Complete exit closes all positions (DCA + Pyramids)
- [ ] Position status changed to 'closed'
- [ ] Pool slot released: 0/10
- [ ] No active BTCUSDT orders on exchange

---

## **Phase 2: Queue System Testing**

### **Test 2.1: Fill Pool & Activate Queue**

#### **Step 1: Fill Pool to Capacity (10 positions)**
```bash
# Create 10 different positions to fill the pool
declare -a symbols=("BTCUSDT" "ETHUSDT" "SOLUSDT" "DOTUSDT" "XRPUSDT" "TRXUSDT" "DOGEUSDT" "ADAUSDT" "GALAUSDT" "LINKUSDT")

for symbol in "${symbols[@]}"; do
  docker compose exec app python3 scripts/simulate_webhook.py \
    --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
    --secret 2e86de391d459bd0d920e88dd1291798 \
    --exchange binance \
    --symbol $symbol \
    --timeframe 60 \
    --side long \
    --type signal \
    --entry-price <todays_price>
  
  sleep 2
done
```

**Verification After Each Signal:**
```bash
# Check database positions
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# Check exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] All 10 positions created successfully
- [ ] Pool limit reached: 10/10
- [ ] All positions visible on exchange

---

#### **Step 2: Queue 11th Signal**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol BNBUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# 1. Check logs for queue message
docker compose logs --tail 50 app | grep -E "(queue|BNBUSDT)"

# 2. Verify pool count remains at 10
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Check exchange (BNBUSDT should NOT be there)
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] Signal queued (not executed)
- [ ] Pool remains: 10/10
- [ ] Queue count: 1
- [ ] BNBUSDT not on exchange

---

### **Test 2.2: Queue Replacement Logic**

#### **Step 1: Replace Queued Signal (Same Symbol)**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol BNBUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <new_price>
```

**Verification:**
```bash
# Check logs for queue update
docker compose logs --tail 50 app | grep -E "(queue|update|replace|BNBUSDT)"
```

**Expected Results:**
- [ ] Queue count remains: 1
- [ ] Entry price updated
- [ ] Same queue item (not duplicate)

---

#### **Step 2: Add Different Queued Signal**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol MATICUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# Check logs for second queue item
docker compose logs --tail 50 app | grep -E "(queue|MATICUSDT)"
```

**Expected Results:**
- [ ] Queue count: 2
- [ ] Both BNBUSDT and MATICUSDT queued
- [ ] Priority calculated correctly

---

### **Test 2.3: Auto-Promotion**

#### **Step 1: Release Pool Slot**
```bash
# Close one active position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --type exit
```

**Verification:**
```bash
# 1. Check logs for exit and promotion
docker compose logs --tail 100 app | grep -E "(exit|close|promote|queue)"

# 2. Wait for auto-promotion (10 seconds)
echo "Waiting for auto-promotion..."
sleep 10

# 3. Check database positions
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 4. Verify promoted position on exchange
docker compose exec app python3 scripts/verify_exchange_positions.py

# 5. Check logs for promotion activity
docker compose logs --tail 50 app | grep -E "(promoted|queue)"
```

**Expected Results:**
- [ ] BTCUSDT closed successfully
- [ ] Pool slot released: 9/10
- [ ] Highest priority queue item auto-promoted
- [ ] Pool refilled: 10/10
- [ ] Queue count decreased: 1
- [ ] Promoted position visible on exchange

---

## **Phase 3: Risk Engine Testing**

### **Test 3.1: Clean Slate & Setup**

#### **Step 1: Clean Previous Positions**
```bash
# Clean database positions
docker compose exec app python3 scripts/clean_positions_in_db.py --username maaz --confirm true

# Clean exchange positions
docker compose exec app python3 scripts/clean_positions_in_exchange.py

# Clean queue
docker compose exec app python3 scripts/clean_queue.py
```

**Verification:**
```bash
# 1. Check database is empty
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 2. Verify exchange is clean
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] All positions cleaned from database
- [ ] All positions cleaned from exchange
- [ ] Queue cleared
- [ ] Pool count: 0/10

---

#### **Step 2: Create LOSER Position (Full Pyramid)**
```bash
# Create base position
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 2.03

sleep 3

# Add pyramid 2/5
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 2.025

sleep 3

# Add pyramid 3/5
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 2.02

sleep 3

# Add pyramid 4/5
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 2.015

sleep 3

# Add pyramid 5/5 (FULL)
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol XRPUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price 2.01
```

**Verification After Full Pyramid:**
```bash
# 1. Check logs
docker compose logs --tail 50 app | grep -E "(pyramid|XRPUSDT|full)"

# 2. Check database
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Verify exchange positions
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] 5 pyramids created for XRPUSDT
- [ ] Post-full timer started
- [ ] Average entry price calculated
- [ ] All orders on exchange

---

#### **Step 3: Create WINNER Position**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol DOGEUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# 1. Check logs
docker compose logs --tail 50 app | grep -E "(DOGEUSDT|position)"

# 2. Check database
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Verify exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] DOGEUSDT position created
- [ ] Pool count: 2/10
- [ ] Both positions on exchange

---

#### **Step 4: Wait for Post-Full Timer**
```bash
echo "Waiting for post-full timer (2 minutes from config)..."
echo "Start time: $(date)"
sleep 130
echo "End time: $(date)"
```

**Verification:**
```bash
# Check logs for timer status
docker compose logs --tail 50 app | grep -E "(timer|post.*full)"
```

**Expected Results:**
- [ ] Post-full timer expired (≥120 seconds)
- [ ] System ready for risk engine check

---

### **Test 3.2: Trigger Risk Engine**

#### **Step 1: Monitor Risk Engine Activation**
```bash
# View recent risk engine activity
docker compose logs --tail 200 app | grep -E "(risk.*engine|loser|winner|partial.*close)"
```

**Verification:**
```bash
# 1. Check positions after risk engine action
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 2. Verify exchange positions
docker compose exec app python3 scripts/verify_exchange_positions.py

# 3. Check detailed logs
docker compose logs --tail 100 app | grep -E "(partial|close|quantity|realized)"
```

**Expected Results:**
- [ ] Risk engine triggered when:
  - Full pyramid (5/5) exists
  - Post-full timer expired (2+ min)
  - Loss > -1.5% (config threshold)
  - Winning position available
- [ ] Partial close orders executed on both:
  - Winner (DOGEUSDT)
  - Loser (XRPUSDT)
- [ ] Max 3 winners combined per config
- [ ] Realized PnL updated for both positions
- [ ] Pool slots NOT released (still 2/10)
- [ ] Reduced position sizes on exchange

---

## **Phase 4: Multi-Exchange Operations**

### **Test 4.1: Simultaneous Binance + Bybit**

#### **Step 1: Create Binance Position**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol ETHUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# 1. Check logs
docker compose logs --tail 50 app | grep -E "(ETHUSDT|binance)"

# 2. Check database
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Verify Binance
docker compose exec app python3 scripts/verify_exchange_positions.py
```

---

#### **Step 2: Create Bybit Position**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange bybit \
  --symbol SOLUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# 1. Check logs (should show Bybit-specific activity)
docker compose logs --tail 50 app | grep -E "(SOLUSDT|bybit)"

# 2. Check database (both exchanges)
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Verify both exchanges
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] Positions created on both exchanges
- [ ] No cross-exchange contamination
- [ ] Exchange-specific precision applied
- [ ] Pool tracking works across exchanges
- [ ] Independent order execution
- [ ] Global pool limit respected (combined count ≤ 10)

---

### **Test 4.2: Exchange-Specific Validation**

```bash
# Check precision handling
docker compose logs --tail 100 app | grep -E "(precision|decimal|quantity|price)"

# Verify no cross-contamination
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json
```

**Expected Results:**
- [ ] Binance positions only on Binance
- [ ] Bybit positions only on Bybit
- [ ] Correct precision per exchange
- [ ] No data mixing

---

## **Phase 5: Critical Edge Cases**

### **Test 5.1: Duplicate Signal Prevention**

#### **Step 1: Send Initial Signal**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# Check logs
docker compose logs --tail 50 app | grep -E "(ADAUSDT|signal)"

# Check database
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json
```

---

#### **Step 2: Send Duplicate Immediately**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol ADAUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# 1. Check logs for rejection
docker compose logs --tail 50 app | grep -E "(duplicate|already.*exists|ADAUSDT)"

# 2. Verify only one position exists
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# 3. Check exchange
docker compose exec app python3 scripts/verify_exchange_positions.py
```

**Expected Results:**
- [ ] Duplicate signal rejected or handled as pyramid
- [ ] System continues functioning
- [ ] No duplicate positions created

---

### **Test 5.2: Authentication Failure**

```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret WRONG_SECRET \
  --exchange binance \
  --symbol AVAXUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <todays_price>
```

**Verification:**
```bash
# Check logs for authentication error
docker compose logs --tail 50 app | grep -E "(auth|secret|unauthorized|error)"
```

**Expected Results:**
- [ ] Authentication failure detected
- [ ] Request rejected
- [ ] Clear error message logged
- [ ] No position created

---

## **Quick Reference: Essential Commands**

### **Cleanup Commands**
```bash
# Clean database positions
docker compose exec app python3 scripts/clean_positions_in_db.py --username maaz --confirm true

# Clean exchange positions
docker compose exec app python3 scripts/clean_positions_in_exchange.py

# Clean queue
docker compose exec app python3 scripts/clean_queue.py
```

### **Verification Commands**
```bash
# Check database positions
docker compose exec app python3 scripts/export_user_positions.py --type positions --format json

# Check exchange positions
docker compose exec app python3 scripts/verify_exchange_positions.py

# Check logs
docker compose logs --tail 50 app
docker compose logs --tail 50 app | grep -E "(keyword|keyword2)"
```

### **Signal Simulation Template**
```bash
docker compose exec app python3 scripts/simulate_webhook.py \
  --user-id 491ba4af-56b9-46ea-922d-d58e077e9b9c \
  --secret 2e86de391d459bd0d920e88dd1291798 \
  --exchange binance \
  --symbol BTCUSDT \
  --timeframe 60 \
  --side long \
  --type signal \
  --entry-price <price>
```

---

## **Testing Notes**

1. **Replace `<todays_price>`** with actual current market prices before running commands
2. **Wait times** between commands ensure proper state updates
3. **Log monitoring** should be done in real-time for critical tests
4. **Database verification** should be done after each major operation
5. **Exchange verification** confirms orders are actually placed
6. Use **`grep -E`** for multiple keyword searches in logs
7. All commands use **`docker compose`** (not `docker-compose`)

---

## **Success Criteria Summary**

- ✅ All position lifecycles complete without errors
- ✅ Queue system activates and promotes correctly
- ✅ Risk engine triggers with proper conditions
- ✅ Multi-exchange isolation maintained
- ✅ Edge cases handled gracefully
- ✅ Database and exchange states remain synchronized
- ✅ Pool limits respected globally
- ✅ No data contamination between exchanges