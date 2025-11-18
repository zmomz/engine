# Execution Plan Frontend (EPF) v1.0

## 1.0 Executive Summary

This document outlines a comprehensive, phase-driven execution plan for building the frontend of the Execution Engine application. The primary goal is to create a user-friendly, robust, and real-time interface that provides full monitoring and control over the backend services.

This plan is designed to work in conjunction with the main `EP.md` and focuses exclusively on the frontend implementation, adhering to the architectural decisions and UI/UX wireframes already established.

**Core Technologies:**
- **Framework:** React (with TypeScript)
- **Component Library:** Material-UI (MUI)
- **State Management:** Zustand
- **API Communication:** Axios (for REST) and native WebSockets
- **Routing:** React Router DOM
- **Forms:** React Hook Form
- **Testing:** Jest & React Testing Library

**Target Outcome:** A polished, intuitive, and fully functional single-page application (SPA) that seamlessly interacts with the FastAPI backend, providing real-time data synchronization and a professional user experience with both light and dark themes.

---

## 2.0 Core Architectural Principles

1.  **Component-Based Architecture:** Following the structure in `EP.md`, the UI will be built from a combination of reusable, presentational components (`/components`) and feature-specific, container components (`/features` or `/pages`).
2.  **Centralized State Management:** Zustand will be the single source of truth for all global application state, including user authentication, system status, and real-time trading data (positions, queue, etc.). This ensures data consistency across the application.
3.  **Real-time First:** The UI will be designed to reflect backend state changes instantly without requiring manual refreshes. This will be achieved through a robust WebSocket integration that updates the Zustand store.
4.  **Test-Driven Development (TDD):** Every new component or major piece of functionality will begin with the creation of a failing test, which will then be made to pass by the implementation. This guarantees high test coverage and code quality from the start.

---

## 3.0 State Management Strategy (Zustand)

The Zustand store will be divided into logical slices to manage different parts of the application state.

**`store/authStore.ts`:**
- **State:** `user`, `token`, `isAuthenticated`, `status ('loading' | 'authenticated' | 'unauthenticated')`
- **Actions:** `login`, `register`, `logout`, `checkAuthStatus`

**`store/systemStore.ts`:**
- **State:** `engineStatus`, `riskEngineStatus`, `lastWebhookTimestamp`, `alerts`, `theme ('light' | 'dark')`
- **Actions:** `setEngineStatus`, `addAlert`, `clearAlerts`, `toggleTheme`

**`store/dataStore.ts`:**
- **State:** `positionGroups`, `queuedSignals`, `poolUsage`, `pnlMetrics`
- **Actions:** `updatePositionGroups` (from WebSocket), `updateQueuedSignals` (from WebSocket), `setInitialData` (on load)

---

## 4.0 Development Plan

### Phase 1: Foundation & Core Setup (Complete)

This phase establishes the architectural backbone of the application.

- **Objectives:** Set up the project, install dependencies, configure routing, establish state management, create the API client, and implement theming.
- **Steps:**
    1.  [x] **Initialize Project:** Use `create-react-app` with TypeScript.
    2.  [x] **Install Dependencies:** Add `react-router-dom`, `axios`, `zustand`, `@mui/material`, `@mui/x-data-grid`, `react-hook-form`.
    3.  [x] **Folder Structure:** Create `/pages`, `/components`, `/services`, `/store`, `/theme`.
    4.  [x] **Theming:** Create `theme/theme.ts` with light/dark mode palettes.
    5.  [x] **API Client:** Create `services/api.ts` with an Axios instance and interceptors for auth headers and 401 handling.
    6.  [x] **State Management:** Set up initial Zustand stores.
    7.  [x] **Routing:** Implement `App.tsx` with `react-router-dom`, defining public routes and a `ProtectedRoute` component.

### Phase 2: Authentication & Application Layout (Complete)

- **Objectives:** Build the user-facing authentication pages and the main application shell (header, sidebar).
- **Steps:**
    1.  [x] **Create Tests:** Write tests for `LoginPage`, `RegistrationPage`, and `MainLayout`.
    2.  [x] **Build `LoginPage`:** Create the login form using MUI components and `react-hook-form` for validation. On successful login, call the `authStore` action and redirect.
    3.  [x] **Build `RegistrationPage`:** Create the registration form, similar to the login page.
    4.  [x] **Implement `ProtectedRoute`:** Flesh out the logic to redirect unauthenticated users to `/login`.
    5.  [x] **Build `MainLayout`:** Create a layout component using MUI's `AppBar` (header) and `Drawer` (sidebar).
        - The `AppBar` will contain the theme toggle button and a user menu with a logout option.
        - The `Drawer` will contain navigation links to all main pages (Dashboard, Positions, etc.).

### Phase 3: Dashboard & Data Visualization

- **Objectives:** Implement the main Dashboard page, providing a high-level overview of the engine's status and performance.
- **Steps:**
    1.  [x] **Create Tests:** Write tests for the `DashboardPage` and all its child widget components.
    2.  [x] **Build `DashboardPage` Layout:** Create a grid-based layout using MUI's `<Grid>` component to arrange the widgets as per the wireframe in `EP.md`.
    3.  [x] **Build `PoolUsageWidget`:**
        - Create a component that subscribes to `dataStore`.
        - Display "X / Y" active positions.
        - Use MUI's `<LinearProgress>` or `<CircularProgress>` component to visualize the pool usage.
    4.  [x] **Build `SystemStatusWidget`:**
        - Display `engineStatus`, `riskEngineStatus`, and `lastWebhookTimestamp` from `systemStore`.
        - Use color-coded MUI `<Chip>` components for status indicators (e.g., green for "Running", red for "Error").
    5.  [x] **Build `PnlCard` Widget:**
        - Display key PnL metrics from `dataStore`.
        - Use green/red coloring for positive/negative values.
    6.  **Build `EquityCurveChart`:**
        - Integrate a lightweight charting library (e.g., `Recharts` or `Chart.js`).
        - Create a placeholder component that will eventually be fed historical PnL data.

### Phase 4: Real-time Data Tables & Interactions

- **Objectives:** Build the core data-heavy pages for monitoring positions and the queue, and integrate WebSocket for real-time updates.
- **Steps:**
    1.  **Create Tests:** Write Jest and React Testing Library tests for `PositionsPage`, `QueuePage`, and the WebSocket integration.
    2.  **Implement WebSocket Service:**
        - Create `services/websocket.ts` to manage the WebSocket connection.
        - Implement automatic reconnection logic with exponential backoff.
        - On message receipt, parse the data and call the appropriate `dataStore` action to update the state.
        - Create a `useWebSocket` hook to initialize the connection from the main application component.
    3.  **Build `PositionsPage`:**
        - Use `MUI X Data Grid` to display the `positionGroups` from `dataStore`.
        - Implement columns as defined in the `EP.md` wireframe.
        - Create custom cell renderer components like `PnlCell` (for color) and `StatusChip`.
        - Implement the expandable row feature to show the `DcaLegsTable` for a selected position.
    4.  **Build `QueuePage`:**
        - Use `MUI X Data Grid` to display `queuedSignals` from `dataStore`.
        - Implement columns for `symbol`, `replacement_count`, `priority_score`, etc.
        - Add action buttons to each row (`Promote`, `Force Add`).
        - Implement the confirmation modal micro-interaction as defined in `EP.md` for the "Force Add" action, including loading and feedback states.

### Phase 5: Configuration & Utility Pages

- **Objectives:** Build the pages for managing settings and viewing logs.
- **Steps:**
    1.  **Create Tests:** Write Jest and React Testing Library tests for `SettingsPage` and `LogsPage`.
    2.  **Build `SettingsPage`:**
        - Use MUI `<Tabs>` to separate configuration sections (Exchange API, Risk Engine, etc.).
        - For each section, create a form using `react-hook-form` to manage state and validation.
        - On submit, call the backend API to save the configuration. Provide feedback (e.g., a snackbar) on success or failure.
    3.  **Build `LogsPage`:**
        - Fetch and display log data from the backend.
        - To handle potentially large datasets, use a virtualized list component (e.g., `react-window` or `react-virtualized`).
        - Add MUI `<TextField>` and `<Select>` components for filtering logs by text and severity level.

### Phase 6: Final Polish & Error Handling

- **Objectives:** Ensure the application is robust, provides clear feedback for all states, and is visually polished.
- **Steps:**
    1.  **Create Tests:** Write Jest and React Testing Library tests for global error boundaries, loading indicators, and responsiveness.
    2.  **Implement Global Error Handling:**
        - Create a global `ErrorBoundary` component to catch rendering errors and display a fallback UI.
        - Implement a standardized way to display API errors to the user using MUI's `<Snackbar>` for non-critical notifications and `<Dialog>` for critical errors.
    3.  **Implement Loading States:**
        - Use MUI `<Skeleton>` components to provide a good user experience on initial page loads while data is being fetched.
        - Use MUI `<CircularProgress>` indicators on buttons and within components during API calls or actions.
    4.  **Responsiveness:** Review all pages and ensure they are usable on tablet-sized screens (down to 768px width). Adjust layouts as needed using MUI's grid system and responsive helpers.
    5.  **Final UX Review:** Conduct a full application walkthrough to identify and fix any confusing workflows, missing feedback, or visual inconsistencies.
