import subprocess
import time

# Trigger an error by making a request
print("Making request to trigger error...")
subprocess.run(
    ['docker', 'exec', 'engine-app-1', 'python', '-c', 
     'import requests; r = requests.get("http://localhost:8000/api/v1/dashboard/stats", headers={"Authorization": "Bearer fake"}); print(r.status_code, r.text[:500])'],
    capture_output=False
)

# Wait a moment for logs to flush
time.sleep(1)

# Get the very latest logs
print("\n\n=== LATEST BACKEND LOGS ===")
result = subprocess.run(
    ['docker', 'logs', '--tail', '50', '--since', '5s', 'engine-app-1'],
    capture_output=True,
    text=True
)

print(result.stdout)
print(result.stderr)
