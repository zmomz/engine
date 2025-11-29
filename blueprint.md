# **📌 EXECUTION ENGINE — MASTER SUMMARY (Condensed & Complete)**

## **1. System Overview**

A fully automated trading engine that:

* Receives **TradingView webhooks** (entry + optional exit only)
* Executes **grid entries**, **pyramids**, and **DCA** locally
* Applies strict **precision validation** before every order (tick/step/min notional)
* Handles **TP**, **partial close**, **full close**, and **risk mitigation**
* Supports **multiple exchanges**
* Has an integrated **web app** (backend + frontend bundled)

TradingView only *starts or ends* positions — **DCA, TP, risk, and pyramids run inside the engine**.

---

## **2. Core Trading Logic**

### **Position Groups**

* Defined by **pair + timeframe**
* First signal → create group
* Additional same-side signals → create **pyramids**, not new positions

### **Pyramid & DCA Structure**

* Each pyramid = multiple DCA layers
* Each DCA layer includes:

  * **Price gap**
  * **Capital weight**
  * **Take-profit target**
* TP uses **actual fill price**, not original entry

### **Take Profit Modes**

1. **Per-Leg TP** (independent)
2. **Aggregate TP** (global avg TP)
3. **Hybrid** (whichever triggers first)

### **Exit Logic**

* TP or exit — **first trigger wins**
* Exit webhook → full close, cancel all unfilled DCA

---

## **3. Precision Engine**

Before any order:

* Fetch **tick size**, **step size**, **min qty**, **min notional**
* Enforce:

  * Price rounded to tick size
  * Qty rounded to step
  * Min notional respected
  * Block if metadata missing

Results:

* Zero exchange rejections
* Works across: **Binance, Bybit, OKX, KuCoin, etc.**

---

## **4. Risk Engine**

Purpose:

* Reduce floating losses using profits from winning trades
* Execute offsets in **USD**, not percent

### **Activation Conditions**

All must be true:

* **5 pyramids received**
* Post-full wait time passed
* Loss % below threshold
* Optional trade-age filter

### **Timer Conditions**

Timer starts only after one of:

* 5 pyramids reached
* All DCA submitted
* All DCA filled
  (Optional: reset on replacement)

### **Losing-Trade Selection**

Rank by:

1. Highest loss %
2. Highest loss in USD
3. Oldest trade

### **Offset Execution**

* Find required USD to cover losing trade
* Combine up to **3 winners**
* Partially close only what's required
* Partial close **does not** release pool slot
* Full close **does** release slot

---

## **5. Execution Pool & Queue**

Limits how many **Position Groups** can be active.

### **Counts toward pool?**

* New position group = **YES**
* Pyramids = **NO**
* DCA = **NO**
* Partial risk close = **NO**
* Full group close releases slot

### **Queue Behavior**

If pool is full:

* Signals queue
* Exit received in queue → deleted
* New pyramid signal replaces queued entry

### **Queue Priority**

1. Same pair/timeframe continuation → top priority
2. Highest loss %
3. Highest replacement count
4. FIFO

---

## **6. Full Execution Flow**

1. Receive TV signal
2. Validate + precision check
3. If pool free → execute
4. Else → queue
5. Track fills + TP logic
6. Exit or TP (first wins)
7. If risk engine active → offset
8. Log + update DB + update UI

---

## **7. Integrated Web UI**

**Single bundled app** (backend + frontend).

### **UI Features**

* Live monitoring of groups, pyramids, DCA
* Pool & queue visualization
* Risk engine panel (loss %, timer, winners used)
* Status console (API, precision, errors)
* Log viewer (filters, export, replay)
* Full config editor (no manual JSON editing)
* Theme: light/dark

---

## **8. Dashboard**

Includes:

* Realized & unrealized PnL
* Equity curve (downloadable)
* Win/loss statistics
* Trade distribution & heatmaps
* Risk metrics (DD, Sharpe, Sortino)
* Capital allocation
* Daily summary
* Real-time TVL gauge

---

## **9. Position Group Views**

Shows:

* Pyramids count
* DCA filled/total
* Avg entry
* Unrealized PnL
* TP mode
* Status (waiting → live → closing → closed)

Clicking a group shows each DCA leg:

* Fill price
* Weight
* TP target
* Progress
* State

---

## **10. Settings Panel**

Editable:

* Exchange API settings
* Precision options
* Execution pool
* Risk engine parameters
* TP mode
* Queue logic
* Logging
* Security
* UI preferences
* Packaging settings

Includes:

* Live preview
* Apply & restart engine
* Backup/restore JSON

---

## **11. Logging & Security**

### **Logging**

* Full local logs
* Export CSV/JSON
* Categories: system, webhook, order, precision, risk, error
* Rotation & retention control

### **Security**

* API keys encrypted
* Hidden keys in UI
* Webhook signature verification
* Local engine (no remote execution)

### **Local Storage**

* Logs → text/JSON
* Config → single JSON file
* Trade history → **PostgreSQL**

---

## **12. Exchange Support**

Spot & testnet:

* Binance (primary)
* Bybit
* OKX
* KuCoin
* MEXC
* Gate.io

Requirements:

* Exchange must provide tick/step metadata

---

## **13. Freelancer Deliverables**

* Full webapp package (backend + frontend)
* Database + persistence
* Config UI
* Execution engine
* Risk engine
* Logs
* Installers (Windows + macOS)
* Unit tests
* Docs (install, run, troubleshoot)

---

## **14. System Diagrams**

Included in original (Mermaid):

* Execution flow
* Risk engine flow
* Queue/pool flow

---

## **15. Terminology Clarification**

* **Position Group** = pair + timeframe
* **Pyramid** = additional entry
* **DCA Leg** = individual layered order
* **TP Leg** = exit target for DCA
* **Execution Pool** = active position limit
* **Waiting Queue** = pending entries
* **Replacement Signal** = updated queued entry
* **Risk Engine** = loss offset mechanism
* **Partial Close** = does not free pool slot

---
