FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /data

# Set environment variables
ENV MOCK_EXCHANGE_DB=/data/mock_exchange.db
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 9000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
