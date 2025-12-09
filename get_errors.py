import subprocess
import re

# Get last 200 lines of logs
result = subprocess.run(
    ['docker', 'logs', '--tail', '200', 'engine-app-1'],
    capture_output=True,
    text=True
)

logs = result.stdout + result.stderr

# Find all tracebacks
lines = logs.split('\n')
in_traceback = False
traceback_lines = []
current_traceback = []

for i, line in enumerate(lines):
    if 'Traceback' in line or 'ERROR' in line or 'Exception' in line:
        if current_traceback:
            traceback_lines.append('\n'.join(current_traceback))
        current_traceback = [line]
        in_traceback = True
    elif in_traceback:
        if line.strip() and (line.startswith(' ') or line.startswith('app-1')):
            current_traceback.append(line)
        else:
            if current_traceback:
                traceback_lines.append('\n'.join(current_traceback))
                current_traceback = []
            in_traceback = False

if current_traceback:
    traceback_lines.append('\n'.join(current_traceback))

# Print last 3 tracebacks
print("=" * 80)
print("LAST 3 ERROR TRACEBACKS:")
print("=" * 80)
for tb in traceback_lines[-3:]:
    print(tb)
    print("-" * 80)
