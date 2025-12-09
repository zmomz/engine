import os
import re

file_path = 'logs/app.log'

try:
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        exit(1)

    file_size = os.path.getsize(file_path)
    read_len = min(file_size, 50000) # Read last 50KB
    
    with open(file_path, 'rb') as f:
        f.seek(file_size - read_len)
        content = f.read()
    
    decoded = content.decode('utf-8', errors='replace')
    
    # Find all occurrences of "ERROR" or "Exception" or "Traceback"
    matches = [m.start() for m in re.finditer(r'(ERROR|Exception|Traceback)', decoded)]
    
    if matches:
        last_match = matches[-1]
        print(f"Found error at index {last_match} (relative to read chunk):")
        # Print from the start of the last error to the end
        print(decoded[last_match:])
    else:
        print("No ERROR, Exception or Traceback found in last 50KB. Printing last 2000 chars:")
        print(decoded[-2000:])

except Exception as e:
    print(f"Error reading file: {e}")
