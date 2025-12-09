import subprocess
import sys

# Get the last 500 lines of logs
result = subprocess.run(
    ['docker', 'logs', '--tail', '500', 'engine-app-1'],
    capture_output=True,
    text=True
)

all_output = result.stdout + result.stderr
lines = all_output.split('\n')

# Find the last ERROR or Exception
for i in range(len(lines) - 1, -1, -1):
    line = lines[i]
    if 'ERROR' in line or 'Exception' in line or 'Traceback' in line:
        # Print from this line and the next 30 lines
        start = max(0, i - 5)
        end = min(len(lines), i + 35)
        print('\n'.join(lines[start:end]))
        break
else:
    print("No recent errors found in last 500 lines")
    print("\nLast 20 lines of logs:")
    print('\n'.join(lines[-20:]))
