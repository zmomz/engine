# Scripts

This directory contains utility scripts for development, testing, and maintenance of the Execution Engine.

## Essential Scripts

### `wait-for-db.py`
Waits for the database connection to be available. Used primarily in Docker entrypoints or CI/CD pipelines to ensure the database is ready before starting the application.
**Usage:** `python scripts/wait-for-db.py`
**Env Vars:** `DATABASE_URL`

### `get_default_risk_config.py`
Outputs the default `RiskEngineConfig` structure as JSON. Useful for generating initial configuration files or inspecting defaults.
**Usage:** `python scripts/get_default_risk_config.py`

### `verify_binance_keys.py`
Verifies Binance API keys by attempting to connect and fetch balance for both Spot and Futures markets.
**Usage:** `python scripts/verify_binance_keys.py --api-key <KEY> --secret-key <SECRET> [--testnet]`

## Shell Scripts

### `run-tests.sh`
Runs the full test suite using Docker Compose.
**Usage:** `./scripts/run-tests.sh`

### `run_integration.sh`
Runs integration tests specifically.
**Usage:** `./scripts/run_integration.sh`

### `backup_db.sh`
Backs up the PostgreSQL database.
**Usage:** `./scripts/backup_db.sh`

### `restore_db.sh`
Restores the PostgreSQL database from a backup.
**Usage:** `./scripts/restore_db.sh`
