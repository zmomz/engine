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

### `verify_exchange_keys.py`
Verifies API keys for configured exchanges (Binance, Bybit, OKX, KuCoin) by attempting to fetch account balance.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/verify_exchange_keys.py --exchange binance --api-key <KEY> --secret-key <SECRET> [--testnet]
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

### `export_data.py`
Exports database records to JSON or CSV format.
Supported types: `positions`, `users`.
**Usage (inside Docker container):**
```bash
# Export positions to CSV (output redirected from container to host)
docker compose exec -T app python3 scripts/export_data.py --type positions --format csv > positions.csv

# Export users to JSON (output redirected from container to host, excludes sensitive data)
docker compose exec -T app python3 scripts/export_data.py --type users --format json > users.json
```

### `stress_test.py`
Performs a simple load test against a specific API endpoint.
**Usage (inside Docker container):**
```bash
docker compose exec -T app python3 scripts/stress_test.py --url http://localhost:8000/api/v1/health --requests 1000 --concurrency 50
```
