#!/usr/bin/env python3
"""Wait for database to be ready before starting the app."""
import os
import time
import socket
from urllib.parse import urlparse

def wait_for_db(timeout=60):
    database_url = os.environ.get("DATABASE_URL", "")
    
    if not database_url:
        print("DATABASE_URL not set, skipping DB wait")
        return True
    
    # Parse the database URL
    parsed = urlparse(database_url.replace("postgresql+asyncpg://", "postgresql://"))
    host = parsed.hostname or "db"
    port = parsed.port or 5432
    
    print(f"Waiting for database at {host}:{port}...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                print(f"Database is ready!")
                return True
        except Exception as e:
            pass
        time.sleep(1)
        print(f"Database not ready, retrying...")
    
    print(f"Timeout waiting for database after {timeout} seconds")
    return False

if __name__ == "__main__":
    import sys
    if not wait_for_db():
        sys.exit(1)
