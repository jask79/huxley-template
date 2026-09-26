#!/bin/bash
#
# Frontend Proof Loop - Launch Script
#
# Usage: ./launch.sh <directory> [port]
# Example: ./launch.sh ./dist 8080

set -e

DIR="${1:-.}"
PORT="${2:-8080}"
PIDFILE="/tmp/dev-server-${PORT}.pid"
LOGFILE="/tmp/dev-server-${PORT}.log"

# Check if server already running on this port
if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
    echo "✅ Dev server already running on port $PORT (PID: $(cat $PIDFILE))"
    exit 0
fi

# Check if port is in use by something else
if lsof -ti:$PORT >/dev/null 2>&1; then
    echo "❌ Port $PORT is already in use by another process"
    echo "Run: lsof -ti:$PORT | xargs kill"
    exit 1
fi

# Start dev server
echo "🚀 Starting dev server on port $PORT..."
python3 -m http.server $PORT --directory "$DIR" > "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"

# Wait for server to be ready
for i in {1..10}; do
    if curl -s http://localhost:$PORT >/dev/null 2>&1; then
        echo "✅ Dev server ready at http://localhost:$PORT"
        exit 0
    fi
    sleep 0.5
done

echo "❌ Dev server failed to start (check $LOGFILE)"
cat "$LOGFILE"
exit 1
