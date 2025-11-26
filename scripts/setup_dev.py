#!/usr/bin/env python3
"""
Sets up the development environment.

Usage:
    python scripts/setup_dev.py [--force]
"""
import os
import shutil
import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def run_cmd(cmd, check=True):
    logger.info(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=check)

def main():
    # 1. Check for .env
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            logger.info("Creating .env from .env.example...")
            shutil.copy(".env.example", ".env")
            logger.warning("Please edit .env with your actual configuration!")
        else:
            logger.error(".env.example not found. Cannot create .env.")
            return 1
    else:
        logger.info(".env already exists.")

    # 2. Install dependencies
    logger.info("Installing Python dependencies with Poetry...")
    try:
        run_cmd(["poetry", "install"])
    except FileNotFoundError:
        logger.error("Poetry not found. Please install poetry.")
        return 1

    # 3. Start Database
    logger.info("Starting database container...")
    run_cmd(["docker", "compose", "up", "-d", "db"])

    # 4. Wait for DB
    logger.info("Waiting for database to be ready...")
    # Using our own script!
    try:
        run_cmd(["poetry", "run", "python", "scripts/wait-for-db.py"])
    except subprocess.CalledProcessError:
        logger.error("Database failed to start.")
        return 1
        
    # 5. Run Migrations
    logger.info("Running database migrations...")
    run_cmd(["poetry", "run", "alembic", "upgrade", "head"])

    logger.info("\nDevelopment environment setup complete!")
    logger.info("Run 'docker compose up' to start the application.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
