# Comprehensive Frontend & API Expansion Plan (TDD)

This document outlines the actionable roadmap for building the "Complete Frontend" and expanding the Backend API to support it. This plan follows a **Test-Driven Development (TDD)** approach.

## 1. Core Tech Stack (Verified)
*   **Framework:** React 19 (Latest)
*   **UI Library:** Material UI (MUI) v6 + `@mui/x-data-grid` for high-performance tables.
*   **State Management:** Zustand (Lightweight, perfect for high-frequency polling updates).
*   **Forms:** React Hook Form + Zod (Schema validation for complex Config UI).
*   **Network:** Axios (with interceptors for JWT Auth).
*   **Visualizations:** `recharts` (Required for "Equity Curve" and "Trade Distribution" charts).

## 2. Component Hierarchy & Layout
*   **`App.tsx`**: Main router and ThemeProvider (Dark Mode default).
*   **`Layout/`**:
    *   **Sidebar**: Navigation (Dashboard, Positions, Queue, Risk, Logs, Settings).
    *   **Header**: System Status Banner (Engine Status: Running/Paused), Connection Health, User Profile.
*   **`pages/`**:
    *   **`Dashboard`**: High-level metrics (TVL Gauge, PnL Summary, Active Group Count) + Status Alerts.
    *   **`Positions`**:
        *   *Master Table*: PositionGroups (Pair, PnL, Status).
        *   *Detail View*: Expandable rows showing Pyramids and DCA Legs.
        *   *Actions*: "Force Close" button.
    *   **`Queue`**:
        *   *Table*: QueuedSignals with "Promote/Remove" actions.
        *   *Priority Logic Display*: Visualizing why a signal is ranked #1.
    *   **`Risk`**:
        *   *Monitor*: Current "Loser" vs "Winners" candidates.
        *   *Controls*: "Run Now", "Skip", "Block" buttons.
    *   **`Logs`**:
        *   *Console*: Filterable stream (Info, Error, Trade) with auto-scroll.
    *   **`Settings`**:
        *   *Form*: Categorized tabs (Exchange, Risk, Grid, App) mapping to the JSON config structure.

## 3. Data Management (Zustand Stores)
*   **`useAuthStore`**: Manages JWT tokens and login state.
*   **`useEngineStore`**:
    *   Handles Polling (e.g., every 2s) for live data (Positions, Queue, PnL).
    *   Avoids WebSockets for Phase 1 to ensure stability.
*   **`useConfigStore`**: Fetches and syncs the global JSON configuration.

---

## 4. Execution Roadmap (TDD)

### Phase 1: Backend API Expansion (Python)
*Goal: Expose missing data points required by the "Bigger Plan".*

**1.1 Historical Positions Endpoint**
*   **TDD Step:** Create `tests/integration/test_api_history.py`. Define a test case `test_get_position_history` that asserts retrieval of `CLOSED` positions. [COMPLETED]
*   **Implementation:**
    *   Update `PositionGroupRepository` with `get_closed_by_user`. [COMPLETED]
    *   Add `GET /api/positions/{user_id}/history` to `positions.py`. [COMPLETED]

**1.2 Force Close Endpoint**
*   **TDD Step:** Create `tests/integration/test_api_actions.py`. Define `test_force_close_position` which asserts an active position transitions to `CLOSING`. [COMPLETED]
*   **Implementation:**
    *   Add `POST /api/positions/{group_id}/close` to `positions.py`. [COMPLETED]
    *   Connect to `OrderService.execute_force_close`. [COMPLETED]

**1.3 Supported Exchanges Endpoint**
*   **TDD Step:** Create `tests/test_settings_api.py`. Assert `GET /api/settings/exchanges` returns `['binance', 'bybit']`. [COMPLETED]
*   **Implementation:** Add endpoint to `settings.py` reading from `exchange_factory`. [COMPLETED]

---

### Phase 2: Frontend Foundation (React)
*Goal: Setup project structure, routing, and authentication.*

**2.1 Project Scaffold & Dependencies**
*   **Action:** Install `recharts`, `axios`, `zustand`, `react-hook-form`, `zod`. [COMPLETED]
*   **Structure:** Create folders `components`, `pages`, `store`, `services`, `layouts`. [COMPLETED]

**2.2 Authentication Flow**
*   **TDD Step:** Create `src/pages/LoginPage.test.tsx`.
    *   Test 1: Renders login form.
    *   Test 2: Displays error on failed login (mocked 401).
    *   Test 3: Redirects to `/dashboard` on success.
*   **Implementation:**
    *   Build `useAuthStore` (Axios interceptors). [COMPLETED]
    *   Build `LoginPage.tsx`. [COMPLETED]
    *   Implement `ProtectedRoute` wrapper. [COMPLETED]

**2.3 Main Layout & Navigation**
*   **TDD Step:** Create `src/components/MainLayout.test.tsx`.
    *   Test: Check if Sidebar links render and navigate correctly.
*   **Implementation:** Build `Sidebar`, `Header`, and `Layout` using MUI `Drawer` and `AppBar`. [COMPLETED]

---

### Phase 3: Core Trading Dashboard
*Goal: Real-time monitoring and control.*

**3.1 Dashboard Widgets**
*   **TDD Step:** `src/pages/DashboardPage.test.tsx`.
    *   Test: Mock `useEngineStore` data and assert "TVL Gauge" and "PnL" values render.
*   **Implementation:**
    *   Create `useEngineStore` with polling logic. [COMPLETED]
    *   Build widgets: `TvlGauge`, `PnlCard`, `ActiveGroupsWidget`. [COMPLETED]

**3.2 Positions Table (Master-Detail)**
*   **TDD Step:** `src/pages/PositionsPage.test.tsx`.
    *   Test: Render table with mock positions. Click "Expand" -> Assert Pyramid details are visible. Click "Force Close" -> Assert API call.
*   **Implementation:**
    *   Use `MUI DataGrid`. [COMPLETED]
    *   Implement "Force Close" button logic connecting to API. [COMPLETED]

**3.3 Queue Management**
*   **TDD Step:** `src/pages/QueuePage.test.tsx`. [PASSED]
    *   Test: Render queue items. Click "Promote" -> Assert API call.
    *   *Status:* Tests passing.
*   **Implementation:**
    *   Build table with "Priority Score" column. [COMPLETED]
    *   Add Action buttons (Promote, Remove). [COMPLETED]

---

### Phase 4: Analytics & Risk
*Goal: Visual insights and safety controls.*

**4.1 Equity Curve Chart**
*   **TDD Step:** `src/pages/analytics/EquityCurve.test.tsx`. [PASSED]
    *   Test: Mock `/history` response. Assert `Recharts` component renders with correct data points.
    *   *Status:* Tests passing.
*   **Implementation:** Fetch historical data and render Line Chart. [COMPLETED]

**4.2 Risk Control Panel**
*   **TDD Step:** `src/components/RiskEnginePanel.test.tsx`.
    *   Test: Assert "Loser" and "Winner" candidates are displayed. Click "Run Now" -> Assert API call.
*   **Implementation:** Visualize the Risk Engine's state (potential offsets). [COMPLETED]

---

### Phase 5: Configuration
*Goal: Full system control via UI.*

**5.1 Settings Form**
*   **TDD Step:** `src/pages/SettingsPage.test.tsx`.
    *   Test: Input invalid API Key -> Assert Validation Error. Input "Weight Sum = 90%" -> Assert Error. Submit -> Assert API `PUT` call.
*   **Implementation:**
    *   Use `react-hook-form` + `zod`. [COMPLETED]
    *   Implement dynamic field array for `DCALevels`. [COMPLETED]
    *   Implement tabs for categorization. [COMPLETED]

---

## 5. Verification
*   **Backend:** Run `pytest tests/integration/` to ensure API changes don't break existing logic. [PASSED]
*   **Frontend:** Run `npm test` to verify all UI components and interactions. [PASSED]