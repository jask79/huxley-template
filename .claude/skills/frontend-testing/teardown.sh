#!/bin/bash
#
# Frontend Proof Loop - Teardown Script
#
# Usage: ./teardown.sh [port]
# Example: ./teardown.sh 8080

set -e

PORT="${1:-8080}"
PIDFILE="/tmp/dev-server-${PORT}.pid"
LOGFILE="/tmp/dev-server-${PORT}.log"

if [ ! -f "$PIDFILE" ]; then
    echo "ℹ️  No dev server PID file found for port $PORT"
    exit 0
fi

PID=$(cat "$PIDFILE")

if ! kill -0 $PID 2>/dev/null; then
    echo "ℹ️  Dev server (PID: $PID) is not running"
    rm -f "$PIDFILE" "$LOGFILE"
    exit 0
fi

echo "🛑 Stopping dev server (PID: $PID) on port $PORT..."
kill $PID 2>/dev/null || true

# Wait for process to terminate
for i in {1..5}; do
    if ! kill -0 $PID 2>/dev/null; then
        echo "✅ Dev server stopped successfully"
        rm -f "$PIDFILE" "$LOGFILE"
        exit 0
    fi
    sleep 0.5
done

# Force kill if still running
echo "⚠️  Force killing dev server..."
kill -9 $PID 2>/dev/null || true
rm -f "$PIDFILE" "$LOGFILE"
echo "✅ Dev server stopped (forced)"
