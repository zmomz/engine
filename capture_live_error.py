import subprocess
import time
import threading

# Start tailing logs in background
log_process = subprocess.Popen(
    ['docker', 'logs', '-f', '--tail', '0', 'engine-app-1'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Collect logs for a few seconds
logs = []
def collect_logs():
    for line in log_process.stdout:
        logs.append(line)
        if len(logs) > 100:  # Limit to last 100 lines
            logs.pop(0)

thread = threading.Thread(target=collect_logs, daemon=True)
thread.start()

# Wait a moment for log collection to start
time.sleep(1)

# Make a request that will fail
print("Triggering request...")
subprocess.run(
    ['docker', 'exec', 'engine-app-1', 'python', '-c',
     '''
import requests
import os
token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxNmMzZDc0ZS00ZGE3LTQ3NmYtYjRhZS01NWNlZjhmNDIzYzIiLCJleHAiOjk5OTk5OTk5OTl9.fake"
try:
    r = requests.get("http://localhost:8000/api/v1/dashboard/stats", headers={"Authorization": token}, timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:1000]}")
except Exception as e:
    print(f"Error: {e}")
'''],
    timeout=10
)

# Wait for logs to be captured
time.sleep(2)

# Kill log process
log_process.terminate()

# Print collected logs
print("\n\n=== CAPTURED LOGS ===")
for log in logs[-50:]:  # Last 50 lines
    print(log, end='')
