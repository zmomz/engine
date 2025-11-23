#!/usr/bin/env python3
"""
Waits for the database to become available.

Usage:
    python scripts/wait-for-db.py
"""
import os
import asyncio
import logging
import sys
import argparse
from urllib.parse import urlparse, parse_qs
import asyncpg
from asyncpg.exceptions import PostgresError, CannotConnectNowError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_db_url(url):
    parsed = urlparse(url)
    return {
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port,
        "database": parsed.path.lstrip("/"),
    }

async def check_db_connection(db_params, retries=30, delay=2):
    for i in range(retries):
        try:
            conn = await asyncpg.connect(**db_params)
            await conn.close()
            logger.info("Database connection successful.")
            return True
        except (CannotConnectNowError, PostgresError, OSError) as e:
            logger.warning(f"Database connection failed (Attempt {i+1}/{retries}): {e}. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
    return False

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set.")
        return 1

    # Replace postgresql+asyncpg:// with postgresql:// for asyncpg if needed
    # But asyncpg usually expects postgres:// or postgresql://
    # SQLAlchemy uses postgresql+asyncpg://. asyncpg does not support '+asyncpg'.
    
    clean_url = database_url.replace("+asyncpg", "")
    db_params = parse_db_url(clean_url)

    if not asyncio.run(check_db_connection(db_params)):
        logger.error("Could not connect to the database after several retries. Exiting.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
