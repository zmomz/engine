#!/usr/bin/env python3
"""
Runs the test suite using Docker Compose.

Usage:
    python scripts/run_tests.py [--type {all,unit,integration}] [--coverage] [--keep] [pytest_args ...]
"""
import os
import subprocess
import argparse
import sys
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

COMPOSE_FILE = "docker-compose.test.yml"
SERVICE_APP = "app"
PROJECT_NAME = "execution_engine_test"

def run_command(cmd, check=True, capture_output=False, env=None):
    if isinstance(cmd, str):
        cmd = cmd.split()
    logger.info(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=True, env=env)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--type', choices=['all', 'unit', 'integration'], default='all', help='Type of tests to run')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--keep', action='store_true', help='Keep containers after tests finish')
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER, help='Additional arguments for pytest')
    
    args = parser.parse_args()
    
    # Generate a dummy valid Fernet key for testing if not set
    # 32 bytes = 44 base64 chars
    test_env = os.environ.copy()
    if "ENCRYPTION_KEY" not in test_env:
        logger.info("ENCRYPTION_KEY not found. Using a dummy key for testing.")
        test_env["ENCRYPTION_KEY"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    
    # Ensure Binance keys are clean for skipping logic if not present on host
    if "TEST_BINANCE_API_KEY" not in os.environ:
        test_env.pop("TEST_BINANCE_API_KEY", None)
    if "TEST_BINANCE_SECRET_KEY" not in os.environ:
        test_env.pop("TEST_BINANCE_SECRET_KEY", None)
    
    # Determine pytest target
    targets = []
    if args.type == 'all':
        targets = [] # pytest default (all)
    elif args.type == 'unit':
        targets = ["tests", "--ignore=tests/integration"]
    elif args.type == 'integration':
        targets = ["tests/integration"]

    pytest_cmd = ["poetry", "run", "pytest", "-v", "-s"]
    if args.coverage:
        pytest_cmd.extend(["--cov=app", "--cov-report=term-missing"])
    
    pytest_cmd.extend(targets)
    pytest_cmd.extend(args.pytest_args)

    # 1. Cleanup
    logger.info("Cleaning up previous test runs...")
    run_command(["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "down", "--volumes", "--remove-orphans"], check=False, env=test_env)

    exit_code = 0
    try:
        # 2. Start services
        logger.info("Starting test services...")
        test_env["TESTING"] = "true"
        run_command(["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "build", "--no-cache", SERVICE_APP], check=True, env=test_env)
        run_command(["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "up", "-d"], check=True, env=test_env)

        # 3. Wait for DB
        logger.info("Waiting for database (with a 10s delay to allow app container to start)...")
        time.sleep(10) # Give the app container time to fully start
        run_command(
            ["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "exec", "-u", "root", SERVICE_APP, "python3", "/app/scripts/wait-for-db.py"],
            check=True, env=test_env
        )

        # 4. Run Tests
        # Join the pytest command parts into a single string for the shell execution inside docker if needed,
        # or pass as list. Docker exec expects command parts.
        # 'poetry run pytest ...'
        full_test_cmd = [
            "docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "exec", 
            "-u", "root", 
            "-e", f"ENCRYPTION_KEY={test_env['ENCRYPTION_KEY']}", # Explicitly pass the key
            SERVICE_APP
        ] + pytest_cmd
        
        run_command(full_test_cmd, check=True, env=test_env)
        logger.info("Tests passed!")

    except subprocess.CalledProcessError as e:
        logger.error(f"Test execution failed: {e}")
        exit_code = e.returncode if e.returncode else 1
    finally:
        # 5. Cleanup
        if not args.keep:
            logger.info("Tearing down services...")
            run_command(["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "down", "--rmi", "local", "--volumes"], check=False, env=test_env)
        else:
            logger.info("Skipping teardown (--keep specified).")

    return exit_code

if __name__ == "__main__":
    sys.exit(main())