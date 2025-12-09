import os

file_path = 'backend_logs.txt'

try:
    with open(file_path, 'rb') as f:
        content = f.read()
    
    decoded = content.decode('utf-8', errors='replace')
    
    # Find all occurrences of "ERROR" or "Exception"
    import re
    matches = [m.start() for m in re.finditer(r'(ERROR|Exception)', decoded)]
    
    if matches:
        last_match = matches[-1]
        print(f"Found error at index {last_match}:")
        # Print 500 chars before and 2000 chars after
        start = max(0, last_match - 500)
        end = min(len(decoded), last_match + 2000)
        print(decoded[start:end])
    else:
        print("No ERROR or Exception found. Printing last 5000 chars:")
        print(decoded[-5000:])

except Exception as e:
    print(f"Error reading file: {e}")
