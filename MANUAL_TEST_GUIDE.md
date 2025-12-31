# Manual Testing Guide (1 Hour)

**Prerequisites:**
- Engine running (`docker compose up`)
- Mock exchange running on port 9000
- Frontend running on port 3000

---

## PHASE 1: AUTHENTICATION (5 min)

### Test 1.1: Registration
1. Open browser → `http://localhost:3000`
2. Click **"Register"** link
3. Fill form:
   - Username: `testclient`
   - Email: `test@client.com`
   - Password: `TestPass123!`
4. Click **Register** button
5. ✅ **Expected:** Redirected to login page with success message

### Test 1.2: Login
1. Enter username: `testclient`
2. Enter password: `TestPass123!`
3. Click **Login** button
4. ✅ **Expected:** Redirected to Dashboard

### Test 1.3: Logout & Re-login
1. Click user menu (top right)
2. Click **Logout**
3. ✅ **Expected:** Redirected to login page
4. Login again with same credentials
5. ✅ **Expected:** Dashboard loads

---

## PHASE 2: SETTINGS CONFIGURATION (10 min)

### Test 2.1: Navigate to Settings
1. Click **Settings** in sidebar
2. ✅ **Expected:** Settings page loads with multiple sections

### Test 2.2: Add Mock Exchange API Keys
1. Find **Exchange API Keys** section
2. Select exchange: **Mock**
3. Enter API Key: `test_api_key`
4. Enter Secret: `test_secret`
5. Click **Save**
6. ✅ **Expected:** Success toast, key appears in list

### Test 2.3: Create DCA Configuration
1. Scroll to **DCA Configurations** section
2. Click **Add Configuration**
3. Fill form:
   - Pair: `BTC/USDT`
   - Timeframe: `1h` (60)
   - Exchange: `mock`
   - Entry Order Type: `Market`
   - Max Pyramids: `2`
   - TP Mode: `per_leg`
4. Add DCA Levels:
   - Level 1: Gap 0%, Weight 40%, TP 3%
   - Level 2: Gap -2%, Weight 30%, TP 3%
   - Level 3: Gap -4%, Weight 30%, TP 3%
5. Click **Save**
6. ✅ **Expected:** Config appears in list

### Test 2.4: Create Second DCA Config (for queue testing)
1. Click **Add Configuration**
2. Fill:
   - Pair: `ETH/USDT`
   - Timeframe: `1h` (60)
   - Exchange: `mock`
   - Same levels as above
3. Click **Save**
4. ✅ **Expected:** Second config in list

### Test 2.5: Configure Risk Settings
1. Scroll to **Risk Engine** section
2. Set:
   - Loss Threshold: `-3%`
   - Max Active Positions: `2`
3. Click **Save**
4. ✅ **Expected:** Settings saved

### Test 2.6: Configure Telegram (Optional)
1. Find **Telegram** section
2. Enter bot token and channel ID (if you have them)
3. Click **Test Connection**
4. ✅ **Expected:** Connection success/failure message

---

## PHASE 3: POSITION ENTRY TESTING (15 min)

### Test 3.1: Send Entry Signal via Mock Exchange Admin
1. Open new browser tab → `http://localhost:9000/docs` (Mock Exchange Swagger)
2. Find **POST /admin/webhook/send**
3. Set target_url: `http://app:8000/api/v1/webhooks/{YOUR_USER_ID}/tradingview`
   - (Get your user_id from Settings page or use the webhook URL shown there)
4. Send this payload:
```json
{
  "user_id": "YOUR_USER_ID",
  "secret": "YOUR_WEBHOOK_SECRET",
  "source": "tradingview",
  "timestamp": "2025-12-31T12:00:00",
  "tv": {
    "exchange": "mock",
    "symbol": "BTC/USDT",
    "timeframe": 60,
    "action": "buy",
    "market_position": "long",
    "market_position_size": 500,
    "prev_market_position": "flat",
    "prev_market_position_size": 0,
    "entry_price": 95000,
    "close_price": 95000,
    "order_size": 500
  },
  "strategy_info": {
    "trade_id": "test_btc_001",
    "alert_name": "BTC Test Entry",
    "alert_message": "Manual test entry"
  },
  "execution_intent": {
    "type": "signal",
    "side": "buy",
    "position_size_type": "quote",
    "precision_mode": "auto"
  },
  "risk": {
    "max_slippage_percent": 1.0
  }
}
```
5. Click **Execute**
6. ✅ **Expected:** 202 Accepted response

### Test 3.2: Verify Position Created
1. Go back to frontend → Click **Positions** in sidebar
2. ✅ **Expected:** BTC/USDT position appears with status "active" or "live"
3. Verify:
   - Symbol: BTC/USDT
   - Side: Long
   - Entry price shown
   - Unrealized PnL displayed

### Test 3.3: Send Second Entry (ETH)
1. Back to Mock Exchange Swagger
2. Send similar payload but with:
   - `"symbol": "ETH/USDT"`
   - `"entry_price": 3500`
   - `"trade_id": "test_eth_001"`
3. ✅ **Expected:** 202 Accepted

### Test 3.4: Verify Both Positions
1. Frontend → Positions page
2. ✅ **Expected:** Both BTC and ETH positions visible

---

## PHASE 4: QUEUE TESTING (10 min)

### Test 4.1: Hit Position Limit
1. Send a third entry signal (SOL/USDT) - but you need DCA config first
2. If no DCA config for SOL, the signal will be rejected
3. Create DCA config for SOL/USDT first (Settings page)
4. Then send signal for SOL/USDT
5. ✅ **Expected:** If max positions = 2, signal goes to queue

### Test 4.2: View Queue
1. Click **Queue** in sidebar
2. ✅ **Expected:** SOL signal appears in queue with priority score

### Test 4.3: View Priority Breakdown
1. Click on the queued signal row
2. ✅ **Expected:** Priority breakdown dialog/panel shows scoring factors

### Test 4.4: Force Promote Signal
1. Click **Force Add** button on SOL signal
2. ✅ **Expected:** Signal promoted, position created (overrides limit)

### Test 4.5: Remove Signal from Queue
1. Send another signal to fill queue again
2. Click **Remove** on the queued signal
3. ✅ **Expected:** Signal removed, appears in Queue History tab

---

## PHASE 5: PRICE MOVEMENT & PNL (10 min)

### Test 5.1: Set Price Up (Profit)
1. Mock Exchange Swagger → **PUT /admin/symbols/{symbol}/price**
2. Set BTCUSDT price to 98000 (was 95000 = +3.15%)
3. Click Execute

### Test 5.2: Verify Unrealized PnL
1. Frontend → Positions page
2. Click **Refresh** or wait for auto-refresh
3. ✅ **Expected:** BTC position shows positive unrealized PnL (green)

### Test 5.3: Set Price Down (Loss)
1. Mock Exchange → Set BTCUSDT price to 92000 (-3.15%)
2. Frontend → Refresh positions
3. ✅ **Expected:** BTC position shows negative unrealized PnL (red)

### Test 5.4: Verify Dashboard Updates
1. Click **Dashboard** in sidebar
2. ✅ **Expected:**
   - Unrealized PnL reflects current loss
   - Active positions count shown
   - TVL displayed

---

## PHASE 6: RISK ENGINE (10 min)

### Test 6.1: View Risk Status
1. Click **Risk** in sidebar
2. ✅ **Expected:** Risk page shows:
   - Engine status (running/stopped)
   - Active positions with loss potential
   - Risk actions (if any)

### Test 6.2: Identify Losers
1. With BTC in loss (price at 92000), check Risk page
2. ✅ **Expected:** BTC position flagged as potential loser

### Test 6.3: Block Position from Risk
1. Find BTC position in Risk page
2. Click **Block** button
3. ✅ **Expected:** Position marked as blocked (won't be auto-closed)

### Test 6.4: Unblock Position
1. Click **Unblock** on BTC
2. ✅ **Expected:** Position no longer blocked

### Test 6.5: Manual Risk Evaluation
1. Click **Run Evaluation** button
2. ✅ **Expected:** Risk engine evaluates positions, shows results

### Test 6.6: Force Stop Queue
1. Click **Force Stop** button
2. ✅ **Expected:** Queue stops promoting new signals
3. Dashboard shows queue stopped indicator

### Test 6.7: Force Start Queue
1. Click **Force Start** button
2. ✅ **Expected:** Queue resumes operation

---

## PHASE 7: POSITION CLOSING (5 min)

### Test 7.1: Force Close Position
1. Go to **Positions** page
2. Find ETH position
3. Click **Close** button
4. Confirm in dialog
5. ✅ **Expected:**
   - Position status changes to "closing" then "closed"
   - Position moves to History tab

### Test 7.2: View Position History
1. Click **History** tab on Positions page
2. ✅ **Expected:** Closed ETH position appears with:
   - Realized PnL
   - Entry/exit prices
   - Close timestamp

---

## PHASE 8: ANALYTICS (5 min)

### Test 8.1: View Analytics
1. Click **Analytics** in sidebar
2. ✅ **Expected:** Charts and statistics displayed

### Test 8.2: Filter by Time Range
1. Click time filter buttons (24h, 7d, 30d, All)
2. ✅ **Expected:** Data updates based on filter

### Test 8.3: Export CSV
1. Click **Export** button
2. ✅ **Expected:** CSV file downloads with position history

---

## PHASE 9: LOGS (Admin Only) (2 min)

### Test 9.1: View Logs
1. Click **Logs** in sidebar (if visible - admin only)
2. ✅ **Expected:** Application logs displayed
3. Try filtering by log level (ERROR, WARNING, INFO)

---

## QUICK REFERENCE: Mock Exchange Admin URLs

| Action | URL |
|--------|-----|
| Swagger Docs | `http://localhost:9000/docs` |
| Set Price | `PUT /admin/symbols/{symbol}/price` |
| Send Webhook | `POST /admin/webhook/send` |
| Get Symbols | `GET /admin/symbols` |
| Fill Orders | `POST /admin/orders/fill-all` |

---

## WEBHOOK PAYLOAD TEMPLATE

```json
{
  "user_id": "YOUR_USER_ID",
  "secret": "YOUR_WEBHOOK_SECRET",
  "source": "tradingview",
  "timestamp": "2025-12-31T12:00:00",
  "tv": {
    "exchange": "mock",
    "symbol": "BTC/USDT",
    "timeframe": 60,
    "action": "buy",
    "market_position": "long",
    "market_position_size": 500,
    "prev_market_position": "flat",
    "prev_market_position_size": 0,
    "entry_price": 95000,
    "close_price": 95000,
    "order_size": 500
  },
  "strategy_info": {
    "trade_id": "unique_id_here",
    "alert_name": "Test",
    "alert_message": "Test"
  },
  "execution_intent": {
    "type": "signal",
    "side": "buy",
    "position_size_type": "quote",
    "precision_mode": "auto"
  },
  "risk": {
    "max_slippage_percent": 1.0
  }
}
```

**For EXIT signal, change:**
- `"action": "sell"`
- `"market_position": "flat"`
- `"prev_market_position": "long"`

---

## CHECKLIST

| Phase | Test | Status |
|-------|------|--------|
| 1 | Registration | ☐ |
| 1 | Login | ☐ |
| 1 | Logout | ☐ |
| 2 | Add API Keys | ☐ |
| 2 | Create DCA Config | ☐ |
| 2 | Risk Settings | ☐ |
| 3 | Send Entry Signal | ☐ |
| 3 | Position Created | ☐ |
| 4 | Queue Signal | ☐ |
| 4 | Force Promote | ☐ |
| 5 | Price Up - Profit | ☐ |
| 5 | Price Down - Loss | ☐ |
| 6 | Risk Status | ☐ |
| 6 | Block/Unblock | ☐ |
| 6 | Force Stop/Start | ☐ |
| 7 | Close Position | ☐ |
| 7 | View History | ☐ |
| 8 | Analytics | ☐ |
| 9 | Logs | ☐ |

---

*Total estimated time: 60 minutes*
