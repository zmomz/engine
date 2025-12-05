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
    result = subprocess.run(cmd, check=check, capture_output=capture_output, text=True, env=env)
    if capture_output:
        return result.stdout
    return result

def wait_for_http_service(service_name, url, max_retries=30, delay=2, env=None):
    logger.info(f"Waiting for {service_name} at {url}...")
    for i in range(max_retries):
        try:
            # Command to run curl inside the 'app' container
            cmd = [
                "docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "exec",
                "-T",  # Disable pseudo-tty allocation
                SERVICE_APP,
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{url}/health"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
            http_code = result.stdout.strip()

            if http_code == "200":
                logger.info(f"{service_name} is available.")
                return True
            else:
                logger.warning(f"{service_name} not yet ready (HTTP {http_code}). Retrying in {delay}s...")
        except Exception as e:
            logger.warning(f"Error checking {service_name} health: {e}. Retrying in {delay}s...")
        time.sleep(delay)
    logger.error(f"{service_name} did not become available after {max_retries} attempts.")
    return False

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
    
    # Set LOG_LEVEL to DEBUG for detailed logging during tests
    test_env["LOG_LEVEL"] = "DEBUG"

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

    pytest_cmd = ["poetry", "run", "pytest", "-v", "-s", "--log-cli-level=DEBUG"]
    if args.coverage:
        pytest_cmd.extend(["--cov=app", "--cov-report=term-missing"])
    
    pytest_cmd.extend(targets)
    pytest_cmd.extend(args.pytest_args)

    # 1. Cleanup
    logger.info("Cleaning up previous test runs...")
    run_command(["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "down", "--volumes", "--remove-orphans"], check=False, env=test_env)
    # Explicitly remove the network in case of orphaned networks
    run_command(["docker", "network", "rm", f"{PROJECT_NAME}_test_net"], check=False, env=test_env)

    exit_code = 0
    try:
        # Build images first
        logger.info("Building Docker images...")
        run_command(["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "build"], check=True, env=test_env)

        # Then start the services
        logger.info("Starting Docker services...")
        run_command(["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "up", "-d"], check=True, env=test_env)


        # 3. Wait for services
        # Give the app container time to fully start its services, not just the DB
        logger.info("Giving containers time to initialize (10s delay)...")
        time.sleep(10) 
        
        logger.info("Waiting for database...")
        run_command(
            ["docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "exec", "-u", "root", SERVICE_APP, "python3", "/app/scripts/wait-for-db.py"],
            check=True, env=test_env
        )

        # 3.5. Wait for Mock Exchange
        # The mock-exchange service is defined in docker-compose.test.yml
        # Its internal hostname is 'mock-exchange' and it runs on port 9000
        mock_exchange_url = "http://mock-exchange:9000"
        if not wait_for_http_service("mock-exchange", mock_exchange_url, env=test_env):
            raise Exception("Mock exchange service did not become available.")

        # 4. Run Tests
        # Join the pytest command parts into a single string for the shell execution inside docker if needed,
        # or pass as list. Docker exec expects command parts.
        # 'poetry run pytest ...'
        full_test_cmd = [
            "docker", "compose", "-p", PROJECT_NAME, "-f", COMPOSE_FILE, "exec", 
            "-u", "root", 
            "-e", f"ENCRYPTION_KEY={test_env['ENCRYPTION_KEY']}", # Explicitly pass the key
            "-e", f"LOG_LEVEL={test_env['LOG_LEVEL']}", # Explicitly pass LOG_LEVEL
            SERVICE_APP
        ] + pytest_cmd
        
        run_command(full_test_cmd, check=True, env=test_env)
        logger.info("Tests passed!")

    except subprocess.CalledProcessError as e:
        logger.error(f"Test execution failed: {e}")
        exit_code = e.returncode if e.returncode else 1
    except Exception as e: # Catch the new exception from wait_for_http_service
        logger.error(f"Test setup failed: {e}")
        exit_code = 1 # Set exit code to indicate failure
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
