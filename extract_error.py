import subprocess
import re

# Get the last 200 lines of logs
result = subprocess.run(
    ['docker', 'logs', '--tail', '200', 'engine-app-1'],
    capture_output=True,
    text=True
)

logs = result.stdout + result.stderr

# Find the last traceback
lines = logs.split('\n')
traceback_start = -1
for i in range(len(lines) - 1, -1, -1):
    if 'Traceback (most recent call last)' in lines[i]:
        traceback_start = i
        break

if traceback_start >= 0:
    # Print from traceback start until we hit INFO or next traceback
    print("=== LAST ERROR TRACEBACK ===")
    for i in range(traceback_start, min(traceback_start + 50, len(lines))):
        line = lines[i]
        print(line)
        if i > traceback_start and ('INFO:' in line or 'Traceback (most recent call last)' in line):
            break
else:
    print("No traceback found. Last 50 lines:")
    for line in lines[-50:]:
        print(line)
