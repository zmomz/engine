#!/bin/bash
set -e

echo "Running integration tests..."
# Delegate to the main test runner script, targeting the integration test suite
./scripts/run-tests.sh tests/integration "$@"