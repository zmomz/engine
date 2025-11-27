
#!/usr/bin/env python3
import requests
import sys
import time
import os

def wait_for_app(host, port, timeout=30):
    start_time = time.time()
    url = f"http://{host}:{port}/api/v1/health"
    print(f"Waiting for app service at {url}...")
    while True:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                print("App service is up and reachable!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        
        if time.time() - start_time > timeout:
            print(f"Timeout: App service at {url} not reachable after {timeout} seconds.")
            return False
            
        time.sleep(1)

if __name__ == "__main__":
    app_host = os.getenv("APP_HOST", "localhost")
    app_port = os.getenv("APP_PORT", "8000")
    if not wait_for_app(app_host, app_port):
        sys.exit(1)
