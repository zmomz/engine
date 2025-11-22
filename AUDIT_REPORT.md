# Trading Engine SoW Compliance Audit Report

## Executive Summary

**Compliance Percentage:** ~75%
**Overall Status:** Functional Core / Incomplete Integration

The Trading Engine demonstrates a robust implementation of the core trading logic, including the sophisticated Risk Engine, DCA Grid calculations, and Position Management. The backend services for handling webhooks, calculating orders, and managing risk are well-structured and largely compliant with the Scope of Work (SoW).

However, significant gaps exist in the "outer shell" of the application:
1.  **Configuration Management:** While the database schema supports user configs, the application currently uses hardcoded defaults or placeholders in key services (`main.py`, `SignalRouter`). The "Single local JSON file" requirement is not strictly followed (using DB instead), and the UI-based editing is only partially hooked up.
2.  **Lifecycle Closure:** The logic to transition a position from `ACTIVE` to `CLOSED` (releasing the execution pool slot) is missing or incomplete.
3.  **Queue Management:** Edge cases for "Exit" signals arriving while a position is queued are not explicitly handled.
4.  **Frontend Integration:** The frontend exists as a React prototype but is not served by the backend as a single packaged unit, and deep integration with the specific config/log features is unverified.

**Recommendation:** Focus immediately on Phase 3 (Integration & Polish) to wire up the persistent configurations, complete the position lifecycle state transitions, and finalize the frontend-backend data flow.

---

## Detailed Findings

### 1. Core Execution Engine
**Compliance Status:** ✅ Fully Implemented

**Implemented Features:**
- [x] **Webhook Parsing:** `WebhookPayload` correctly parses TradingView JSON.
- [x] **Grid/DCA Logic:** `GridCalculatorService` implements the math for price levels, gaps, and weights.
- [x] **Precision:** `round_to_tick_size` and `round_to_step_size` are correctly used in calculations.
- [x] **Position Creation:** `PositionManagerService` correctly instantiates Groups, Pyramids, and DCA Orders.

**Code References:**
- `backend/app/services/grid_calculator.py`: Full math implementation.
- `backend/app/services/position_manager.py`: `create_position_group_from_signal`.

### 2. Pyramid + DCA System
**Compliance Status:** ⚠️ Partially Implemented

**Implemented Features:**
- [x] **Pyramid Handling:** `handle_pyramid_continuation` logic allows adding legs to existing groups.
- [x] **DCA Layers:** Configurable gaps and weights are respected.

**Missing/Partial:**
- **TP Modes:** Code hardcodes `tp_mode="per_leg"` in `PositionManager`. The SoW requires Aggregate and Hybrid modes.
- **Exit Handling:** `handle_exit_signal` cancels orders and places a market close, but state transition to `CLOSED` is not explicitly confirmed in the monitored loop.

### 3. Precision Validation
**Compliance Status:** ✅ Fully Implemented

**Implemented Features:**
- [x] **Validation:** `GridCalculator` validates `min_qty` and `min_notional`.
- [x] **Rounding:** Strict rounding to `tick_size` and `step_size` before order submission.

### 4. Risk Engine
**Compliance Status:** ✅ Fully Implemented (Core Logic)

**Implemented Features:**
- [x] **Selection Logic:** Correctly identifies losers (by %, $) and winners (by $) in `select_loser_and_winners`.
- [x] **Offset Execution:** `calculate_partial_close_quantities` correctly determines how much of a winner to close.
- [x] **Pre-Trade Checks:** Max positions, Max exposure, and Daily Loss Limit are enforced in `validate_pre_trade_risk`.

**Code References:**
- `backend/app/services/risk_engine.py`: Comprehensive implementation of the SoW Section 4 logic.

### 5. Execution Pool & Queue
**Compliance Status:** ⚠️ Partially Implemented

**Implemented Features:**
- [x] **Pool Limits:** `ExecutionPoolManager` enforces `max_open_groups`.
- [x] **Priority Queue:** `QueueManager` implements the 4-tier priority logic (Existing > Loss% > Replacement > FIFO).

**Missing/Partial:**
- **Queue Exit Signals:** If a "Close" signal arrives for a symbol that is currently in the `WAITING` queue, the system does not explicitly remove it. `SignalRouter` currently treats incoming payloads mostly as entry/continuation intents.
- **Slot Release:** The mechanism to implicitly release a slot (transitioning a group to `CLOSED` after a full exit) is missing in `OrderFillMonitor`.

### 6. Integrated Web Application
**Compliance Status:** ⚠️ Partially Implemented

**Implemented Features:**
- [x] **Dashboard UI:** React pages for Dashboard, Queue, Positions exist.
- [x] **Real-time Data:** `OrderFillMonitor` and API endpoints support polling.

**Missing/Partial:**
- **Single Packaged App:** Backend (`main.py`) does not mount/serve the Frontend static files. They are running as separate services (acceptable for Docker, but deviates slightly from "Single App" wording).
- **Config UI:** The Settings page exists but the API (`backend/app/api/settings.py`) only updates `User` fields, not the deep `RiskEngineConfig` or `DCAGridConfig` JSON structures required.

### 7. Configuration System
**Compliance Status:** ❌ Not Implemented / Deviated

**Implemented Features:**
- [x] **Database Storage:** `User` model has columns for configs.

**Missing:**
- **Single JSON File:** The project uses DB persistence (better for multi-user, but violates "Local JSON file" SoW requirement).
- **Active Loading:** Critical services (`SignalRouter`, `QueueManager`) currently use hardcoded placeholders or defaults (`RiskEngineConfig()`) instead of loading the user's config from the DB. **This is a critical functional gap.**

### 8. Exchange Support
**Compliance Status:** ✅ Fully Implemented

**Implemented Features:**
- [x] **Abstraction:** `ExchangeInterface` and `ccxt` integration allow for multi-exchange support.
- [x] **Mocking:** `MockExchange` is implemented for testing.

---

## Critical Issues Summary

1.  **Hardcoded Configurations:** The application is currently running on default settings. The code to load `risk_config` and `dca_grid_config` from the `User` database record into the active services is missing in `SignalRouter` and `main.py`.
2.  **Position Closure State:** A filled exit order does not trigger a state change to `CLOSED`. This means the Execution Pool will never free up slots, eventually deadlocking the system as "Active" groups pile up.
3.  **Queue Purging:** Absence of logic to handle "Close" signals for queued items means a user might exit a trade on TradingView, but the Engine effectively "ignores" it if the entry is still queued, potentially opening a trade later that should have been cancelled.

## Recommendations

1.  **Implement Config Loading:** Modify `SignalRouter.route` and `QueueManager.__init__` to load the `User.risk_config` and `User.dca_grid_config` from the database instead of using defaults.
2.  **Fix State Transitions:** Update `OrderFillMonitorService` or `OrderService` to detect when a position is fully closed (zero quantity remaining) and update `PositionGroup.status` to `CLOSED`.
3.  **Handle Queue Exits:** Update `SignalRouter` to check `execution_intent`. If "exit/flat", call `QueueManager.remove_by_symbol` to purge any pending entries.
4.  **Serve Frontend:** Add `StaticFiles` mounting to `backend/app/main.py` to serve the React build, fulfilling the "Self-contained" requirement.
