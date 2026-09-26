#!/bin/bash
# Weaviate Startup Script for Bifrost Semantic Caching
# Ensures Weaviate is fully ready before Bifrost connects

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CATALYST_ROOT="$(dirname "$SCRIPT_DIR")"

# Weaviate configuration
WEAVIATE_HOST="127.0.0.1"
WEAVIATE_PORT="8082"
WEAVIATE_URL="http://${WEAVIATE_HOST}:${WEAVIATE_PORT}"
WEAVIATE_BIN="$SCRIPT_DIR/weaviate/weaviate"
LOGS_DIR="$CATALYST_ROOT/logs"

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

# Check if Weaviate is already running
if pgrep -f "weaviate --host" > /dev/null; then
    echo "⚠️  Weaviate is already running on port $WEAVIATE_PORT"

    # Verify it's responsive
    if curl -s "$WEAVIATE_URL/v1/.well-known/ready" > /dev/null 2>&1; then
        echo "✅ Weaviate is healthy and ready"
        exit 0
    else
        echo "⚠️  Weaviate process exists but not responding, restarting..."
        pkill -f "weaviate --host"
        sleep 2
    fi
fi

# Check if Weaviate binary exists
if [ ! -f "$WEAVIATE_BIN" ]; then
    echo "❌ Weaviate binary not found at $WEAVIATE_BIN"
    echo "   Please download from: https://github.com/weaviate/weaviate/releases"
    exit 1
fi

echo "🚀 Starting Weaviate..."
cd "$SCRIPT_DIR"
"$WEAVIATE_BIN" \
    --host="$WEAVIATE_HOST" \
    --port="$WEAVIATE_PORT" \
    --scheme=http \
    > "$LOGS_DIR/weaviate.log" 2>&1 &

WEAVIATE_PID=$!
echo "   Weaviate started (PID: $WEAVIATE_PID)"

# Wait for Weaviate to be ready (up to 30 seconds)
echo -n "   Waiting for Weaviate to be ready"
for i in {1..60}; do
    if curl -s "$WEAVIATE_URL/v1/.well-known/ready" > /dev/null 2>&1; then
        echo ""
        echo "✅ Weaviate is ready on $WEAVIATE_URL"
        echo "   Logs: $LOGS_DIR/weaviate.log"
        exit 0
    fi
    echo -n "."
    sleep 0.5
done

echo ""
echo "❌ Weaviate failed to start within 30 seconds"
echo "   Check logs: $LOGS_DIR/weaviate.log"
exit 1
