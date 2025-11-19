# PROJECT BLUEPRINT: The Single Source of Truth

This document provides a complete, accurate, and actionable guide for the Execution Engine project. It consolidates all previous planning documents and serves as the single source of truth for development.

---

## PART 1: GROUND-TRUTH AUDIT & CURRENT STATE

This section provides a definitive audit of the project's true state as of the last analysis.

### **1.1 Executive Summary**

The project is a "hollow shell." It presents a sophisticated and well-designed exterior, but the core functionality that connects all the pieces is entirely missing. The backend has an excellent, production-ready architecture for decision-making but has **no capability to interact with an exchange.** The frontend, while appearing complete on the surface, lacks the fundamental state management and data-fetching logic to be anything more than a static mockup.

**The application is fundamentally non-functional and in an early-to-mid development stage.**

---

### **1.2 Backend Analysis (~75% Complete)**

The backend is a story of strong foundations and a critical missing link.

-   **Data Layer (90% Complete):**
    -   **Models (100%):** The SQLAlchemy models are perfectly implemented per the specifications.
    -   **Repositories (80%):** The repository pattern is well-executed. A `BaseRepository` provides generic functionality, and specific repositories (`PositionGroupRepository`, etc.) correctly implement custom, business-specific queries.

-   **API Layer (95% Complete):** The API is robust, secure, and fully implemented, providing a clean interface to the application's logic.

-   **Service Layer (60% Complete):**
    -   **Decision Logic (100%):** The services for *deciding* what to do (`GridCalculatorService`, `QueueManagerService`, `RiskEngineService`) are complete, complex, and production-ready.
    -   **Action Logic (15%):** The `PositionManagerService`, which should *act* on those decisions, is a scaffold and **cannot place trades.**

-   **Exchange Abstraction Layer (20% Complete): CRITICAL FAILURE.**
    -   The architecture (`Interface`, `Factory`) is sound.
    -   However, the only concrete implementation started, `BinanceConnector`, is a **stub.** It imports `ccxt` but none of the methods (`place_order`, `get_order_status`) are implemented. They are all marked with `TODO`.
    -   **Conclusion:** The backend has no ability to communicate with any crypto exchange.

---

### **1.3 Frontend Analysis (~30% Complete)**

The frontend follows the backend's pattern: a good-looking structure with no functional core.

-   **UI Implementation (80% Complete):**
    -   The pages (`DashboardPage`, `PositionsPage`, etc.) and components are built using Material-UI. The visual structure of the application is in place and matches the wireframes.

-   **State Management (10% Complete):** While store files exist, they are mostly boilerplate. There is little to no logic for handling real-time updates from a WebSocket or managing the complex state of position groups.

-   **Connectivity (10% Complete):** The `axios` and `websocket` service files are placeholders. The interceptors and real-time data handling logic are not implemented. The frontend cannot effectively communicate with the backend.

---

## PART 2: ACTIONABLE RECOVERY PLAN

This plan supersedes all previous development plans. It prioritizes the most critical missing pieces to make the application functional as quickly as possible.

### **Phase 1: Core Backend Functionality (The "Action" Layer)**

**Objective:** Enable the engine to execute a trade on an exchange based on a signal. This is the highest priority.

1.  **Implement Exchange Connectors (Starting with Binance):**
    -   Flesh out all methods in `backend/app/services/exchange_abstraction/binance_connector.py` as the first implementation.
    -   The architecture must support Binance, Bybit, OKX, and KuCoin.
    -   Implement `place_order`, `get_order_status`, `cancel_order`, and `get_current_price` using the `ccxt` library.
    -   Implement the `map_exchange_errors` decorator to catch `ccxt` exceptions and raise the standardized application exceptions.
    -   Write unit tests for the connector using mock `ccxt` responses, ensuring the test structure can be reused for other exchanges.

2.  **Complete `PositionManagerService`:**
    -   In `backend/app/services/position_manager.py`, remove the placeholder logic.
    -   Inject the `OrderService` and use it to place the DCA orders calculated by the `GridCalculatorService`.
    -   Implement the logic for handling pyramid signals and exit signals, ensuring they call the `OrderService` appropriately.
    -   Ensure all operations are performed within a single database transaction.

3.  **Write Integration Tests:**
    -   Create a new `pytest` integration test file.
    -   Write a test that sends a webhook to the running application and asserts that the mock exchange server receives the correct `place_order` calls. This will prove the entire backend loop is working.

### **Phase 2: Frontend-Backend Integration (The "Connectivity" Layer)**

**Objective:** Connect the frontend to the backend to enable real-time data flow and user actions.

1.  **Implement WebSocket Manager:**
    -   In `frontend/src/services/websocket.ts`, implement the connection logic, including automatic reconnection with exponential backoff.
    -   Add message handlers that parse incoming data and call actions on the Zustand stores.

2.  **Implement API Client:**
    -   In `frontend/src/services/api.ts`, fully implement the Axios interceptors to inject the auth token and handle 401/logout responses.

3.  **Flesh out Zustand Stores:**
    -   In `frontend/src/store/dataStore.ts` and `systemStore.ts`, create the actions that will be called by the WebSocket service to update position groups, queue status, etc.
    -   Ensure state updates are handled immutably.

### **Phase 3: Frontend UI Hydration (Making it "Live")**

**Objective:** Transform the static UI mockups into a dynamic, data-driven application.

1.  **Connect Components to Stores:**
    -   Refactor all pages (`DashboardPage`, `PositionsPage`, etc.) and components to subscribe to the Zustand stores using hooks.
    -   Remove all static or mock data and replace it with live data from the stores.
    -   Use selectors to ensure components only re-render when the specific data they need changes.

2.  **Implement User Actions:**
    -   Connect all buttons and forms to the backend.
    -   For example, the "Save Settings" button on the `SettingsPage` should call the `api.ts` service to send a PUT request.
    -   Actions like "Force Add to Pool" on the `QueuePage` should call the appropriate API endpoint and provide user feedback (loading spinners, success/error snackbars).

### **Phase 4: Full-System Hardening & Finalization**

**Objective:** Ensure the complete application is stable, tested, and reliable.

1.  **Expand Integration Test Suite:**
    -   Create end-to-end `pytest` scenarios for the Risk Engine, Queue Promotion, and Take-Profit logic.
    -   Write frontend integration tests using Jest and React Testing Library that mock the API/WebSocket layer to verify the UI responds correctly to different data scenarios.

2.  **User Acceptance Testing (UAT):**
    -   Perform a full walkthrough of the application, following the user journeys defined in `EP.md`.
    -   Identify and fix all bugs, UI inconsistencies, and confusing workflows.
    -   Ensure the application is polished and professional.

---

## PART 3: SYSTEM DESIGN & ARCHITECTURE

This section contains the detailed, durable specifications for the project's architecture, business logic, and data models.

### **3.1 Architectural Decisions**

- **State Management (Frontend):** `Zustand`
- **Component Library (Frontend):** `Material-UI (MUI)`
- **Backend Framework:** `FastAPI`
- **ORM:** `SQLAlchemy` (asyncio version)
- **Exchange Integration:** `ccxt`

### **3.2 Business Rules & Formulas**

- **Unrealized PnL (USD):** `(Current Market Price - Weighted Average Entry Price) * Total Filled Quantity`
- **Unrealized PnL (%):** `(Unrealized PnL (USD) / Total Invested USD) * 100`
- **Realized PnL (USD):** `(Exit Price - Entry Price) * Closed Quantity - Fees`
- **Capital Per Position Group:** `Total Capital / Max Concurrent Positions`
- **Position Sizing (Per DCA Leg):** `(Capital Per Position Group) * (DCA Leg Weight % / 100)`

### **3.3 Logic Annex: Clarifications**

- **"Current Loss %" for Queued Signals:** `((Current Market Price - Queued Signal Entry Price) / Queued Signal Entry Price) * 100`
- **Exchange Error Mapping:**
    | `ccxt` Exception | Application Exception |
    |---|---|
    | `AuthenticationError` | `InvalidCredentialsError` |
    | `InsufficientFunds` | `InsufficientFundsError` |
    | `InvalidOrder` | `OrderValidationError` |
    | `RateLimitExceeded` | `RateLimitError` |
    | `NetworkError` / `RequestTimeout` | `ExchangeConnectionError` |
    | `ExchangeError` | `GenericExchangeError` |

### **3.4 Core Data Models**

The SQLAlchemy models for `PositionGroup`, `Pyramid`, `DCAOrder`, `QueuedSignal`, and `RiskAction` are fully implemented as specified in the original `EP.md` document. They serve as a solid foundation.

### **3.5 Algorithm Specifications**

The pseudocode for the following algorithms is implemented in the codebase:
- **Queue Priority Calculation:** `calculate_queue_priority` in `QueueManagerService`.
- **Risk Engine Selection:** `select_loser_and_winners` in `RiskEngineService`.
- **Take-Profit Monitoring:** Logic exists in `TakeProfitService`.
- **DCA Grid Calculation:** `calculate_dca_levels` and `calculate_order_quantities` in `GridCalculatorService`.

### **3.6 UI/UX Design & Wireframes**

The UI mockups and component architecture from the original `EP.md` are still valid and serve as the blueprint for the frontend implementation in Phase 3 of the recovery plan.

---

## PART 4: OPERATIONAL MANUAL

This section contains practical information for developing, running, and troubleshooting the application.

### **4.1 Key Commands & Procedures**

- **Run Backend Tests:**
  ```bash
  docker compose -f docker-compose.test.yml run --rm app poetry run pytest -v
  ```
- **Run Backend Linting:**
  ```bash
  docker compose exec app ruff check .
  ```
- **Generate a Database Migration:**
  ```bash
  docker compose exec app alembic revision --autogenerate -m "Your migration message"
  ```
- **Apply Database Migrations:**
  ```bash
  docker compose exec app alembic upgrade head
  ```

### **4.2 Lessons Learned (Live Log)**

- **Frontend Build Failures (`CI=true`):** The frontend Docker build failed because the `CI=true` environment variable treats all ESLint warnings (like `no-unused-vars`) as build-breaking errors. The fix was to resolve all linting warnings in the React code.
- **Cascading Backend Import Errors:** A series of tests failed during `conftest.py` loading due to code refactoring (`TradingViewSignal` -> `WebhookPayload`, etc.). This highlights the need to trace and update dependencies across the entire application when making changes.
- **Pytest Mocking Precision:** Tests for `OrderFillMonitorService` failed due to multiple specific mock configuration errors (missing dependency, wrong method name, incomplete logic). Mocks must precisely replicate the conditions the service expects to encounter.
- **Docker Volume Mounts vs. Rebuilding:** It is **not** necessary to run `docker compose build` after every code change. The `docker-compose.test.yml` file correctly mounts the local source code into the container. Rebuilding is only for dependency or `Dockerfile` changes. This is a critical workflow optimization.
