import os

file_path = 'backend_logs.txt'

try:
    with open(file_path, 'rb') as f:
        content = f.read()
    
    decoded = content.decode('utf-8', errors='replace')
    
    last_traceback = decoded.rfind('Traceback')
    if last_traceback != -1:
        print("Found Traceback:")
        print(decoded[last_traceback:])
    else:
        print("No traceback found. Printing last 2000 chars:")
        print(decoded[-2000:])

except Exception as e:
    print(f"Error reading file: {e}")
