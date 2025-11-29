#!/bin/sh

HOST="app"
PORT="8000"
TIMEOUT=60

URL="http://${HOST}:${PORT}/api/v1/health"

echo "Waiting for app service at ${URL}..."

start_time=$(date +%s)

while ! curl -s -f ${URL}; do
  if [ $(($(date +%s) - start_time)) -ge ${TIMEOUT} ]; then
    echo "Timeout: App service at ${URL} not reachable after ${TIMEOUT} seconds."
    exit 1
  fi
  echo "App service not yet available... retrying in 1 second."
  sleep 1
done

echo "App service is up and reachable!"

# Execute the original Nginx CMD
exec "$@"