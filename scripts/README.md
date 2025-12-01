# Scripts

This directory contains utility scripts for development, testing, and maintenance of the Execution Engine.

**Important Note:**
- Scripts that interact directly with the running application or its database (e.g., fetching configs, verifying keys, health checks, data export, cleanup, webhook simulation, stress testing) must be run **inside the `app` Docker container** using `docker compose exec -T app python3 scripts/<script_name>.py`.
- Scripts that orchestrate Docker containers themselves (e.g., `setup_dev.py`, `run_tests.py`, `backup_db.py`, `restore_db.py`) must be run **on your host machine** using `python3 scripts/<script_name>.py`.

All scripts are written in Python for cross-platform compatibility.

## Setup & Configuration

### `get_default_config.py`
Generates default configuration files for various system components (Risk, Grid, etc.).
**Usage (inside Docker container):** 
```bash
# Print to stdout
docker compose exec -T app python3 scripts/get_default_config.py --schema risk
# Save to file (output redirected from container to host)
docker compose exec -T app python3 scripts/get_default_config.py --schema grid > config/grid.json
```



### `setup_dev.py`
Sets up the development environment by creating .env, installing dependencies, starting the database, and running migrations.
**Usage (on host machine):**
```bash
python3 scripts/setup_dev.py
```

## Development & Operations

### `health_check.py`
Checks the system health by querying the API health endpoints.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/health_check.py [--url http://localhost:8000]
```

### `simulate_webhook.py`
Simulates a TradingView webhook signal by sending a valid JSON payload to the API. Useful for testing signal processing logic without actual market events.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/simulate_webhook.py --user-id <UUID> --secret <SECRET> --symbol BTCUSDT --side buy
```

### `clean_user_positions.py`
Cleans all `PositionGroup` entries, `DCAOrder`s, and `Pyramid`s associated with a specific test user from the database. Useful for starting tests from a clean slate.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/clean_user_positions.py
```

### `clean_queue.py`
Clears all queued signals (`QueuedSignal` entries) from the database.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/clean_queue.py
```

### `fill_dca_orders.py`
Simulates the filling of all currently `OPEN` DCA orders in the database. It also triggers `update_position_stats` and `update_risk_timer` for the affected `PositionGroup`.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/fill_dca_orders.py
```

### `trigger_risk_engine.py`
Manually triggers an immediate evaluation of the risk engine for a specified user or all users.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/trigger_risk_engine.py
```

### `trigger_update_position_stats.py`
Manually triggers an update of position statistics for a specified `PositionGroup` or all active positions.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/trigger_update_position_stats.py
```

## Testing & Quality Assurance

### `run_tests.py`
Unified test runner that handles Docker orchestration (up/down) and executes the test suite.
**Usage (on host machine):**
```bash
# Run all tests
python3 scripts/run_tests.py

# Run only integration tests
python3 scripts/run_tests.py --type integration

# Run with coverage report
python3 scripts/run_tests.py --coverage
```

### `wait-for-db.py`
Waits for the database connection to be available. Primarily used in Docker entrypoints and CI/CD.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/wait-for-db.py --max-retries 30 --delay 2
```

### `wait-for-app.py`
Waits for the main application API to be healthy. Primarily used in Docker entrypoints and CI/CD to ensure dependent services start only after the app is ready.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/wait-for-app.py --url http://localhost:8000/health --max-retries 30 --delay 2
```

### `count_active_positions.py`
Displays the count of active position groups and their `filled_dca_legs` vs `total_dca_legs` for quick verification.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/count_active_positions.py
```

### `inspect_orders.py`
Displays detailed information about all `DCAOrder`s associated with a given `PositionGroup` ID.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/inspect_orders.py --group-id <UUID>
```

### `list_positions.py`
Lists all position groups, showing their ID, symbol, status, and user ID.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/list_positions.py
```

### `list_queue.py`
Lists all signals currently in the processing queue.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/list_queue.py
```

### `setup_risk_scenario_v3.py`
Sets up a complex risk scenario in the database by creating predefined `PositionGroup`s, `Pyramid`s, and `DCAOrder`s with specific statuses and values for multiple symbols (DOTUSDT, ETHUSDT, SOLUSDT). Useful for testing the risk engine's behavior under various conditions.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/setup_risk_scenario_v3.py
```

## Database Management

### `backup_db.py`
Backs up the PostgreSQL database from the running Docker container.
**Usage (on host machine):**
```bash
python3 scripts/backup_db.py [--output-dir ./backups]
```

### `restore_db.py`
Restores the PostgreSQL database from a backup file. **WARNING:** Overwrites existing data.
**Usage (on host machine):**
```bash
python3 scripts/restore_db.py backups/db_backup_20230101.sql
```

## Advanced Utilities

### `cleanup_stale_data.py`
Deletes old data (e.g., closed position groups) from the database to maintain performance.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/cleanup_stale_data.py --days 90 [--dry-run]
```

### `export_user_positions.py`
Exports detailed data for all user positions (active, closed, etc.) to the console, optionally in JSON format. Useful for inspecting the database state.
**Usage (inside Docker container):**
```bash
# Export positions to CSV (output redirected from container to host)
docker compose exec -T app python3 scripts/export_user_positions.py --type positions --format csv > positions.csv

# Export users to JSON (output redirected from container to host, excludes sensitive data)
docker compose exec -T app python3 scripts/export_user_positions.py --type users --format json > users.json
```

### `get_user_keys.py`
Retrieves and decrypts API keys for a specified user and exchange.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/get_user_keys.py --username <USERNAME>
```

### `exchange_api_tool.py`
A versatile tool to check exchange API key validity, display balances, and optionally convert all non-USDT assets to USDT on an exchange (supports dry-run). Also provides basic position cleaning functionality.
**Usage (inside Docker container):**
```bash
# Check balances and API key validity
docker compose exec -T app python3 scripts/exchange_api_tool.py <API_KEY> <SECRET> <EXCHANGE_NAME>
# Convert all assets to USDT (dry-run)
docker compose exec -T app python3 scripts/exchange_api_tool.py <API_KEY> <SECRET> <EXCHANGE_NAME> <PASSWORD> <TESTNET_BOOL> convert
```

### `stress_test.py`
Performs a simple load test against a specific API endpoint.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/stress_test.py --url http://localhost:8000/api/v1/health --requests 1000 --concurrency 50
```

---

## Documentation
- **TEST_PLAN.md**: The main document outlining the detailed test cases and steps to validate the trading engine, now located at `@/docs/TEST_PLAN.md`.
- **sow_summary.md**: Provides a summary of the Statement of Work (SOW) related to the project, now located at `@/docs/sow_summary.md`.
