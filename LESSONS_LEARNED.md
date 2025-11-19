# Lessons Learned

## 1. Database & ORM (SQLAlchemy + Asyncpg)
*   **Session Flushing:** When using `asyncio.gather` to run multiple service methods that interact with the *same* database session, you will encounter `InvalidRequestError: Session is already flushing`.
    *   **Solution:** Avoid parallel execution (`asyncio.gather`) for DB-write operations sharing a session. Use sequential `for` loops or give each task its own independent session.
*   **Data Types:** `decimal.Decimal` types must be explicitly handled when serializing to JSON for database `JSON` columns (e.g., `dca_config` in `Pyramid` model). SQLAlchemy/Asyncpg/Pydantic usually handle this, but manual `json.dumps` requires a custom encoder or converting Decimals to floats/strings first.
*   **Integrity Errors:** Always handle `IntegrityError` (duplicate keys) gracefully, especially in high-concurrency scenarios like webhook ingestion.

## 2. Testing & Mocking
*   **Mock Exchange vs. Real Testnet:**
    *   **Mock Exchange:** fast, deterministic, good for logic verification (state transitions, DB records).
    *   **Real Testnet (Stage 2):** Crucial for verifying connector implementations, authentication, API signatures, and handling of real-world data types (e.g., CCXT returning strings vs floats).
*   **Dependency Injection in Tests:** Overriding dependencies via `app.dependency_overrides` is powerful but requires careful setup of the override fixtures to match the signature of the real dependencies exactly (e.g., `QueueManager` needing `RiskEngineService`).
*   **Environment Variables:** Use `os.environ` patches in tests to toggle behavior (e.g., switching `EXCHANGE_TESTNET=true` for integration tests) without changing code.

## 3. Exchange Integration (CCXT)
*   **Order Types:** Binance (and many exchanges) expect uppercase order types (`LIMIT`, `MARKET`) and sides (`BUY`, `SELL`). CCXT might handle some normalization, but explicit uppercase is safer.
*   **Parameter Naming:** CCXT's `create_order` uses `amount` for quantity. Our internal models use `quantity`. Consistency in the connector layer mapping is key.
*   **Testnet Configuration:** Binance Testnet requires a specific URL or `exchange.set_sandbox_mode(True)`. It implies a different set of API keys.
*   **Error Handling:** CCXT errors (`OrderNotFound`, `AuthenticationError`) should be mapped to internal application exceptions for consistent handling.
*   **Precision Rules:** `load_markets()` returns precision as decimal places (int) for Binance, but `GridCalculator` expects step sizes (float/decimal). Conversion logic is required in the connector.

## 4. Pydantic & Configuration
*   **Validation:** `model_validate` is strict. When defining test data fixtures, ensure all fields (like `weight_percent` summing to 100) meet the validation rules defined in the schemas.
*   **Field Types:** Be careful with `Decimal` vs `float` in Pydantic models. Explicit type coercion (e.g., `@model_validator`) is often needed when data comes from mixed sources (JSON payloads vs DB).