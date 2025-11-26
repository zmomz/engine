#!/usr/bin/env python3
"""
Waits for the database to become available.

Usage:
    python scripts/wait-for-db.py [--max-retries N] [--delay N] [--verbose]
"""
import os
import asyncio
import logging
import sys
import argparse
from urllib.parse import urlparse
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

async def check_db_connection(db_params, max_retries=30, delay=2, verbose=False):
    for i in range(max_retries):
        try:
            if verbose:
                logger.info(f"Attempting connection to {db_params['host']}:{db_params['port']} (Attempt {i+1}/{max_retries})...")
            
            conn = await asyncpg.connect(**db_params)
            await conn.close()
            logger.info("Database connection successful.")
            return True
        except (CannotConnectNowError, PostgresError, OSError) as e:
            if verbose:
                logger.warning(f"Connection failed: {e}")
            else:
                logger.warning(f"Database unavailable (Attempt {i+1}/{max_retries}). Retrying in {delay}s...")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
    return False

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-retries', type=int, default=30, help='Maximum number of retries (default: 30)')
    parser.add_argument('--delay', type=int, default=2, help='Delay between retries in seconds (default: 2)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set.")
        return 1

    # Replace postgresql+asyncpg:// with postgresql:// for asyncpg if needed
    clean_url = database_url.replace("+asyncpg", "")
    
    try:
        db_params = parse_db_url(clean_url)
    except Exception as e:
        logger.error(f"Failed to parse DATABASE_URL: {e}")
        return 1

    if not asyncio.run(check_db_connection(db_params, args.max_retries, args.delay, args.verbose)):
        logger.error(f"Could not connect to the database after {args.max_retries} attempts. Exiting.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
