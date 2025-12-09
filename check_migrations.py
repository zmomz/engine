import os

file_path = 'backend_logs.txt'

try:
    if not os.path.exists(file_path):
        print("backend_logs.txt not found")
        exit(1)

    with open(file_path, 'rb') as f:
        # Read first 50KB (start of logs usually has migration info)
        content = f.read(50000)
    
    decoded = content.decode('utf-8', errors='replace')
    
    # Look for migration markers
    if "alembic" in decoded.lower():
        print("Found 'alembic' in first 50KB logs:")
        # Print lines containing alembic
        lines = decoded.split('\n')
        for line in lines:
            if "alembic" in line.lower() or "upgrade" in line.lower() or "error" in line.lower():
                print(line)
    else:
        print("Migration logs not found in first 50KB.")

except Exception as e:
    print(f"Error: {e}")
