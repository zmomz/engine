g Project: Execution Engine v4.0

## Project Overview

This project is a fully automated trading execution engine with an integrated web UI. It's designed to receive TradingView webhooks, execute complex grid-based trading strategies (including pyramids and DCA), manage risk autonomously, and provide a real-time monitoring dashboard.

This `GEMINI.md` file serves as the primary operational guide for the AI development assistant, complementing the strategic roadmap outlined in `execution_plan.md`.

**Key Technologies:**
*   **Backend:** Python with FastAPI
*   **Frontend:** React (TypeScript) with Material-UI (MUI)
*   **State Management:** Zustand
*   **Database:** PostgreSQL
*   **Deployment:** Docker

---

## Core Business Logic & Rules

### PnL Calculation
- **Unrealized PnL (USD):** `(Current Market Price - Weighted Average Entry Price) * Total Filled Quantity` (For shorts: `(Weighted Average Entry Price - Current Market Price) * ...`)
- **Unrealized PnL (%):** `(Unrealized PnL (USD) / Total Invested USD) * 100`
- **Realized PnL (USD):** `(Exit Price - Entry Price) * Closed Quantity - Fees`. Must account for exchange fees provided by `ccxt`.

### Capital Allocation
- **Capital Per Position Group:** `Total Capital / Max Concurrent Positions`.
- **Position Sizing (Per DCA Leg):** `(Capital Per Position Group) * (DCA Leg Weight % / 100)`.

---

## AI Assistant Protocol (v4.0)

This protocol is designed to work with the phased approach in `execution_plan.md`.

### 1. Phase-Driven Workflow
- **Declare Phase:** At the beginning of a work session, state the specific phase and objective you are working on (e.g., "Starting Backend Phase 1: Database Architecture, Objective: Implement SQLAlchemy models.").
- **Adhere to Plan:** Follow the **Steps** outlined for the current phase in `execution_plan.md` sequentially. Do not skip steps or move to the next phase without explicit approval.
- **Implement Business Logic:** When implementing features, refer to the **Business Rules & Formulas** and **Algorithm Specifications** sections of the execution plan to ensure the logic is correct.

### 2. Test-Driven Development (TDD)
- **Write Tests First:** For any new business logic (e.g., a new service, a complex calculation), you must write the failing `pytest` unit tests *before* writing the implementation code.
- **Verify Coverage:** Before submitting work for a Quality Gate review, run a test coverage report and ensure the new code meets the >85% threshold.

### 3. Quality Gates
- **Request Review:** Upon completing all steps in a phase, formally request a "Quality Gate Review."
- **Provide Checklist:** Present the completed **Quality Gate Checklist** for that phase, confirming that all criteria (Code Review, Test Coverage, SoW Compliance, Documentation) have been met.
- **Await Approval:** Do not begin the next phase until the Quality Gate has been approved.

### 4. Operational & Error Handling
- **Follow Runbooks:** When performing operational tasks like database migrations or deployments, follow the procedures outlined in the **Operational Runbook**.
- **Implement for Recovery:** When building features, consider the **User Journeys** for error recovery. Ensure that the application provides clear feedback to the user in case of errors like invalid API keys or insufficient funds.
- **Troubleshooting:** If an error is encountered during development, first consult the **Troubleshooting Guide**. If the issue is not listed, diagnose the problem, propose a solution, and then add the new solution to the guide.

### 5. Verification and Committing
- **Verify Changes:** After every modification, confirm that the change was applied correctly, there are no syntax errors, services are running, and all relevant tests pass.
- **Atomic Commits:** Make small, atomic commits after each logical piece of work is complete. Commit messages should be clear and reference the relevant phase of the execution plan (e.g., `feat(backend-p1): Implement PositionGroup model`).

### 6. The "Three Strikes" Rule for Debugging
To prevent getting stuck in repetitive, failing loops, the following debugging protocol is mandatory:

- **Strike 1: Initial Attempt.** Make a direct, targeted attempt to fix a bug (e.g., using `replace`).
- **Strike 2: Re-evaluate and Retry.** If the first attempt fails, **stop**. Do not immediately retry the same tool call. Instead:
    1.  **Read** the relevant file(s) again to get the exact current state.
    2.  **Analyze** the error message carefully.
    3.  **Formulate a new hypothesis** for the failure.
    4.  Make a second, more informed attempt with a corrected tool call.
- **Strike 3: Escalate Strategy.** If the second attempt also fails, **stop and declare a "Strategy Escalation."** The current approach is considered flawed. The next action must be a fundamentally different and more comprehensive plan. Examples of escalated strategies include:
    - Rewriting the entire failing function or test case from scratch using `write_file`.
    - Refactoring the underlying service to improve its testability (e.g., by changing how dependencies are injected).
    - Creating a simplified, isolated test case in a new file to understand the core problem before applying the solution back to the main file.
- **Circuit Breaker:** If three consecutive attempts to fix the same test fail, I will stop, inform you that I am stuck, and ask for guidance.

---

## Key Commands & Procedures

- **Run Backend Tests:**
  ```bash
  docker compose -f docker-compose.test.yml run --rm app pytest -v
  ```
- **Run Backend Test Coverage:**
  ```bash
  docker compose -f docker-compose.test.yml run --rm app pytest --cov=app
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
- **Downgrade a Database Migration:**
  ```bash
  docker compose exec app alembic downgrade -1
  ```

---

## Lessons Learned (Live Log)

- **SQLAlchemy 2.0 Async Mocking:** Unit tests for services using `db.execute()` require a specific mocking pattern. The mock for `db.execute` must *not* be an `asyncio.Future` itself. Instead, it should be a `MagicMock` instance whose `scalars()` and `all()` methods are pre-configured. The application code's `await result.scalars().all()` will then resolve correctly without needing the mock to be a future.
  - **Correct Pattern:** `mock_result = MagicMock(); mock_result.scalars.return_value.all.return_value = [...]; mock_db_session.execute.return_value = mock_result`
- **Tool Brittleness:** The `replace` tool is extremely sensitive to whitespace and context. When fixing multiple similar errors across files, this led to repeated `IndentationError`s. The path forward is to be extremely precise with the `old_string` parameter, including significant and unique surrounding context, and to fix issues one file at a time, re-reading the file if a replacement fails.
- **Database Fixture Resolution:** Pytest fixtures that are `async_generator`s (like the `db_session` fixture) must be resolved within an `async for` loop in the test function (e.g., `async for session in db_session: ...`). Passing the generator directly to a service that expects a session object will cause `AttributeError`s.
- **Pytest in Docker with Poetry:** When running `pytest` inside a Docker container managed by Poetry, ensure `pytest` and its dependencies (like `httpx`) are correctly installed as dev dependencies. If `pytest` is not found in `$PATH`, use `poetry run pytest`. If `pyproject.toml` changes, run `poetry lock` followed by `poetry install` to update dependencies.
- **Circular Imports with FastAPI Dependencies:** Importing a `dependencies` module directly into `app/__init__.py` can lead to circular import errors during testing, especially when `conftest.py` imports models from `app`. It's better to import dependencies directly in the API routes where they are used, rather than in the package's `__init__.py` file.
- **`slowapi` and `Request` object:** When using `@limiter.limit` decorator from `slowapi`, the decorated function must accept a `request: Request` argument, even if not explicitly used, for `slowapi` to function correctly.
- **Docstring Syntax Error:** A `SyntaxError: unexpected character after line continuation character` can occur if a docstring contains an unescaped backslash followed by a newline character. Ensure docstrings are properly formatted.
- **Exchange Abstraction Layer:** Implementing an `ExchangeInterface` and a factory function (`get_exchange_connector`) allows for flexible and extensible exchange integration. Using `unittest.mock.patch` is crucial for testing `ccxt` integrations without making actual API calls.
- **Custom Exception Handling:** Defining custom exceptions (e.g., `InvalidCredentialsError`, `InsufficientFundsError`) and using a decorator (`map_exchange_errors`) to map `ccxt` exceptions to these custom exceptions provides a standardized way to handle and communicate errors throughout the application.
- **Mocking Async Generators for `async for` loops:** When a service consumes an `async for` loop (e.g., `async for session in self.session_factory():`), the `session_factory` fixture in tests must return an *async generator function*, not just an `AsyncMock`. The `AsyncMock` itself will be the `session` yielded by the generator.
  - **Correct Pattern:**
    ```python
    <!-- Import failed: pytest.fixture - ENOENT: no such file or directory, access '/home/maaz/engine/pytest.fixture' -->
    def mock_session_factory():
        async def factory():
            mock_session_obj = AsyncMock()
            yield mock_session_obj
            await mock_session_obj.close()
        return factory
    ```
- **Handling `asyncio.CancelledError` in Tests:** When testing asynchronous tasks that are cancelled (e.g., `asyncio.Task.cancel()`), directly `await`ing the cancelled task in the test function will raise `asyncio.CancelledError`, causing the test to fail. Instead, allow the service's `stop_monitoring` method to handle the awaiting and catching of `CancelledError` internally. In tests, ensure sufficient `asyncio.sleep` time after starting the monitoring task to allow it to initialize before cancellation.
  - **Correct Test Pattern:**
    ```python
    await service.start_monitoring()
    await asyncio.sleep(0.01) # Allow task to be created
    # ...
    service._monitor_task.cancel()
    await asyncio.sleep(0.2) # Allow task to be cancelled and cleanup
    ```
- **MUI Grid Deprecation Warnings:** The project uses `@mui/material` version `7.3.5`, which emits deprecation warnings for `item`, `xs`, and `md` props on the `Grid` component, suggesting a migration to Grid v2. Attempts to resolve these by removing `item` and explicitly using `Unstable_Grid2` or `ownerState` were unsuccessful, indicating the warnings are deeply rooted in this specific MUI version or its compatibility layer. As tests pass and functionality is unaffected, these warnings will be addressed in a future, dedicated MUI upgrade/refactoring phase.
- **`NameError` with FastAPI `HTTPException` and `status` in Service Files:** When using FastAPI's `HTTPException` and `status` (e.g., `status.HTTP_404_NOT_FOUND`) within a service file (not an API route file), these must be explicitly imported from `fastapi`. Even if they are imported in a related API route file or test file, they are not automatically available in the service file.
- **Pytest Async Event Loop Mismatch:** A `RuntimeError: got Future <Future pending> attached to a different loop` during teardown of async tests indicates a mismatch between the event loops used by different fixtures. This commonly occurs when a session-scoped fixture (like a database engine) is used by function-scoped tests. The fix is to ensure all related async fixtures share the same scope (e.g., changing the `event_loop` and `test_db_engine` fixtures from `scope="session"` to `scope="function"`).
- **FastAPI Dependency Overrides in Integration Tests:** When testing FastAPI applications with `httpx`, direct database assertions within the test function can fail due to transaction isolation. The test's `db_session` and the session used by the application (via `Depends`) are different. The correct pattern is to create a fixture that overrides the dependency for the duration of the test, ensuring both the test and the app endpoint use the *exact same* session object from the same transaction. This allows the test to reliably see data created by the endpoint.
- **Synchronous vs. Asynchronous `await` Errors:** A `TypeError: object bool can't be used in 'await' expression` is a clear sign that a synchronous function is being incorrectly awaited. This often happens during refactoring or when a function's signature is changed from `async def` to `def`. It's crucial to trace the call stack and remove the `await` keyword from the call site.
- **Frontend Test Failures:** Simple errors can have a cascading effect on frontend tests. A missing import for a component (`EquityCurveChart` in `DashboardPage.tsx`) or a simple text mismatch in a heading caused multiple test suites to fail. It's important to check for these basic errors before assuming a more complex issue.
- **Test Fixture Dependencies:** When creating new test files or moving test cases, ensure all required fixtures and their imports are also moved or made available. A `Fixture not found` error during test collection is a direct result of a missing fixture definition in the test file's scope.
- **Correctly Mocking Async Methods:** When mocking an asynchronous method, ensure the mock's `return_value` is an awaitable that resolves to the expected value (e.g., `AsyncMock(return_value=0)`). Also, within the test case, if a service's internal async method is being mocked, it's often more robust to mock that internal method directly on the service instance rather than relying on mocking a deeper dependency. This prevents `TypeError`s where `AsyncMock` objects are unexpectedly returned instead of resolved values.
- **Duplicate Test Files:** Maintaining two separate test files (`test_queue_manager.py` and `test_queue_manager_service.py`) for a single service (`QueueManagerService`) led to inconsistent assertions and increased maintenance overhead. One file expected a full payload to be stored while the other expected a nested payload, revealing a bug in one of the tests. Consolidating tests for a single unit into a single test file is crucial for maintaining a consistent and reliable test suite.
- **Jest Module Resolution with Create React App:** The default Jest configuration provided by `create-react-app` can fail to resolve ES modules from `node_modules`, leading to `Cannot find module` errors. This was particularly problematic for `react-router-dom` and its dependencies. The solution involved several steps:
  - **`transformIgnorePatterns`:** Overriding the default `transformIgnorePatterns` in `package.json` to force Jest to transform `react-router-dom`, `axios`, and their dependencies.
  - **`moduleNameMapper`:** When `transformIgnorePatterns` was not enough, `moduleNameMapper` was used to explicitly point Jest to the correct CommonJS entry points for the modules (e.g., `<rootDir>/node_modules/react-router-dom/dist/index.js`).
  - **Polyfills:** The JSDOM environment used by Jest lacks some browser APIs like `TextEncoder`. These need to be polyfilled in the `src/setupTests.ts` file.
  - **Zustand Mocking:** Mocking Zustand stores requires a specific pattern. The `jest.mock` call must be configured to correctly mock the `useAuthStore` hook, including handling selector functions, to avoid `TypeError`s in components that use the store.
- **Import/Export Mismatch in Jest:** A recurring and difficult-to-diagnose issue was a `TypeError` when mocking a Zustand store. The root cause was a mismatch between the export type in the store file (`export default useAuthStore`) and the import type in the component and test files (`import { useAuthStore }`). Correcting the imports to `import useAuthStore` (default) resolved the issue and allowed for a much simpler Jest mock using a simple `mockReturnValue`. This highlights the importance of verifying import/export consistency before attempting complex mock implementations.
--- End of Context from: GEMINI.md ---
