# Project Blueprint

## 1. Project Overview
**Goal:** Build a "Risk-First" Trading Engine that ingests signals (TradingView), manages positions with a strict risk framework (DCA, Pyramiding, Max Drawdown), and executes on crypto exchanges (Binance, Bybit).
**Core Philosophy:** "Protect capital first, then profit."

## 2. Architecture & Tech Stack
*   **Backend:** Python (FastAPI), SQLAlchemy (Async), Pydantic.
*   **Database:** PostgreSQL (TimescaleDB optional for candles).
*   **Task Queue:** (Simpler start) In-memory/DB-backed priority queue or Redis (later).
*   **Exchange Integration:** CCXT (Unified API).
*   **Frontend:** React (for monitoring/dashboard).

## 3. Key Components (The "Engine")

### A. Signal Ingestion (The "Ear")
*   **Webhook Endpoint:** Receives JSON payloads from TradingView.
*   **Validation:** Checks signature/secret, parses payload (Symbol, Side, Entry, etc.).
*   **Queueing:** Pushes valid signals to a priority queue (DB table `queued_signals`).

### B. Position Manager (The "Brain")
*   **State Machine:** Manages lifecycle: `WAITING` -> `LIVE` -> `DCA_ACTIVE` -> `PROFIT_TAKING` -> `CLOSED`.
*   **PositionGroup:** A logical container for a trade (e.g., "Long BTC"). Can contain multiple "Pyramids".
*   **Pyramid:** A specific entry level. A PositionGroup can have multiple Pyramids (e.g., initial entry + 2 re-entries).

### C. Risk Engine (The "Shield") - *CRITICAL*
*   **Pre-Trade Checks:**
    *   Max Open Positions (Global & Per Pair).
    *   Max Exposure (Total $ allocated).
    *   Daily Loss Limit (Circuit Breaker).
*   **Post-Trade Monitoring:**
    *   **DCA Logic:** Calculates step-down levels (e.g., -1%, -2%, -5%) and sizes (Martingale or fixed).
    *   **Emergency Close:** Force close if global drawdown > X%.

### D. Execution (The "Hands")
*   **Order Manager:** Translates "intent" (Open Long, Place DCA Limit) into exchange API calls (via CCXT).
*   **Rate Limiting:** Respects exchange limits.
*   **Reconciliation:** Periodically checks if orders on exchange match DB state.

## 4. Data Models (Simplified)

*   **User:** API Keys (Encrypted), Preferences.
*   **QueuedSignal:** Raw signal data, priority, status.
*   **PositionGroup:** `user_id`, `symbol`, `side`, `status`, `stats` (PnL, etc.).
*   **Pyramid:** `group_id`, `entry_price`, `status`.
*   **DCAOrder:** `pyramid_id`, `price`, `amount`, `type` (Limit/Market), `status`.
*   **RiskAction:** Audit log of risk interventions (e.g., "Blocked signal due to max exposure").

## 5. Development Phases

### Phase 1: Skeleton & Signal Flow (Completed)
1.  [x] Setup Docker/Postgres/FastAPI.
2.  [x] Define DB Models (User, PositionGroup, etc.).
3.  [x] Implement Webhook Endpoint & Validation.
4.  [x] Implement Queue & Basic "Promoter" (Signal -> Position).
5.  [x] **Integration Test:** End-to-end flow (Webhook -> DB -> Mock Exchange).
6.  [x] **Stage 2 Integration:** Live Testnet Validation (Binance Spot).

### Phase 2: The Risk Engine (In Progress)
1.  [x] Define `RiskEngineService` structure and interface.
2.  [x] Integrate `RiskEngine` into `QueueManager` (Pre-trade hook).
3.  [ ] Implement Pre-trade logic (Max Positions, Max Exposure).
4.  [ ] Add "Circuit Breaker" (Daily Loss Limit).
5.  [ ] Unit/Integration Tests for Risk Logic.

### Phase 3: DCA & Pyramiding Logic
1.  [ ] Implement `GridCalculator` (calculate price levels/sizes).
2.  [ ] Logic for placing batch limit orders (DCA).
3.  [ ] Logic for "Pyramiding" (adding to winners).

### Phase 4: Execution & Monitoring
1.  [ ] Integrate CCXT (Binance Futures).
2.  [ ] WebSocket Listener (User Data Stream) for order updates.
3.  [ ] Reconciliation Worker (Sync DB with Exchange).

### Phase 5: Frontend Dashboard
1.  [ ] React setup.
2.  [ ] Dashboard: Active Positions, Equity Curve, Signal Log.
3.  [ ] Settings Page: API Keys, Risk Config.

## 6. Current Task
**Focus:** Phase 2 (Risk Engine Logic).
**Next:** Implement the actual checking logic for `max_open_positions` and `max_total_exposure_usd` inside `RiskEngineService`.
