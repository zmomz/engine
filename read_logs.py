import os

file_path = 'backend_logs.txt'
file_size = os.path.getsize(file_path)
read_size = 10000

with open(file_path, 'rb') as f:
    if file_size > read_size:
        f.seek(file_size - read_size)
    content = f.read()
    print(content.decode('utf-8', errors='ignore'))
