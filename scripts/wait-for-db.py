import os
import time
import asyncio
import asyncpg
from asyncpg.exceptions import PostgresError, CannotConnectNowError
from urllib.parse import urlparse, parse_qs

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

def parse_db_url(url):
    parsed = urlparse(url)
    return {
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port,
        "database": parsed.path.lstrip("/"),
        **parse_qs(parsed.query) # For any additional query parameters
    }

db_params = parse_db_url(DATABASE_URL)

async def check_db_connection_direct_asyncpg():
    for _ in range(10):
        try:
            conn = await asyncpg.connect(**db_params)
            await conn.close()
            print("Database connection successful (direct asyncpg).")
            return True
        except (CannotConnectNowError, PostgresError) as e:
            print(f"Database connection failed (direct asyncpg): {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"An unexpected error occurred (direct asyncpg): {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2)
    return False

if __name__ == "__main__":
    if not asyncio.run(check_db_connection_direct_asyncpg()):
        print("Could not connect to the database after several retries. Exiting.")
        exit(1)