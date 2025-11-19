# Ground-Truth Codebase Audit & Actionable Recovery Plan

This document provides a definitive audit of the project's true state as of this analysis and outlines a clear, step-by-step plan to achieve full functionality.

---

## 1. Final Ground-Truth Codebase Audit

This audit synthesizes the findings from a multi-stage investigation of the codebase.

### **Executive Summary**

The project is a "hollow shell." It presents a sophisticated and well-designed exterior, but the core functionality that connects all the pieces is entirely missing. The backend has an excellent, production-ready architecture for decision-making but has **no capability to interact with an exchange.** The frontend, while appearing complete on the surface, lacks the fundamental state management and data-fetching logic to be anything more than a static mockup.

**The application is fundamentally non-functional and in an early-to-mid development stage, far from the "complete" status suggested by the `EPF.md` document.**

---

### **Backend Analysis (~75% Complete)**

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
    -   However, the only concrete implementation, `BinanceConnector`, is a **stub.** It imports `ccxt` but none of the methods (`place_order`, `get_order_status`) are implemented. They are all marked with `TODO`.
    -   **Conclusion:** The backend has no ability to communicate with any crypto exchange.

---

### **Frontend Analysis (~30% Complete)**

The frontend follows the backend's pattern: a good-looking structure with no functional core.

-   **UI Implementation (80% Complete):**
    -   The pages (`DashboardPage`, `PositionsPage`, etc.) and components are built using Material-UI. The visual structure of the application is in place and matches the wireframes.

-   **State Management (10% Complete):** While store files exist, they are mostly boilerplate. There is little to no logic for handling real-time updates from a WebSocket or managing the complex state of position groups.

-   **Connectivity (10% Complete):** The `axios` and `websocket` service files are placeholders. The interceptors and real-time data handling logic are not implemented. The frontend cannot effectively communicate with the backend.

---

## 2. Actionable Recovery Plan

This plan supersedes the development plans in `EP.md` and `EPF.md`. It prioritizes the most critical missing pieces to make the application functional as quickly as possible.

### **Phase 1: Core Backend Functionality (The "Action" Layer)**

**Objective:** Enable the engine to execute a trade on an exchange based on a signal. This is the highest priority.

1.  **Implement `BinanceConnector`:**
    -   Flesh out all methods in `backend/app/services/exchange_abstraction/binance_connector.py`.
    -   Implement `place_order`, `get_order_status`, `cancel_order`, and `get_current_price` using the `ccxt` library.
    -   Implement the `map_exchange_errors` decorator to catch `ccxt` exceptions and raise the standardized application exceptions.
    -   Write unit tests for the connector using mock `ccxt` responses.

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
