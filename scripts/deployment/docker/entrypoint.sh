#!/bin/bash
set -e

# Initialize logging
echo "Starting MicroVM Sandbox container..."
echo "Command: $1"
echo "User: $(whoami)"
echo "Working directory: $(pwd)"

# Set up networking if running as privileged
if [ -w /proc/sys/net/bridge ]; then
    echo "Setting up networking..."
    # Only setup if bridge doesn't exist
    if ! ip link show chbr0 >/dev/null 2>&1; then
        ./scripts/setup/setup-networking.sh
    else
        echo "Bridge chbr0 already exists, skipping network setup"
    fi
else
    echo "Running in unprivileged mode, skipping network setup"
fi

# Ensure required directories exist
mkdir -p /app/data /app/logs /app/snapshots /tmp/ch-sockets

# Handle different commands
case "$1" in
    "server")
        echo "Starting FastAPI server..."
        exec python3 -m uvicorn src.api.server:app \
            --host 0.0.0.0 \
            --port 8000 \
            --workers 4 \
            --access-log \
            --log-level info
        ;;
    "worker")
        echo "Starting background worker..."
        exec python3 src/utils/worker.py
        ;;
    "shell")
        echo "Starting interactive shell..."
        exec /bin/bash
        ;;
    "test")
        echo "Running tests..."
        exec python3 -m pytest tests/ -v
        ;;
    *)
        echo "Usage: $0 {server|worker|shell|test}"
        echo "Available commands:"
        echo "  server - Start FastAPI server (default)"
        echo "  worker - Start background worker"
        echo "  shell  - Start interactive shell"
        echo "  test   - Run test suite"
        exit 1
        ;;
esac