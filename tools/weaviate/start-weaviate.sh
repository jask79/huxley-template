#!/bin/bash
# Start Weaviate server for Bifrost semantic caching
# Port 8082 (to avoid conflict with Bifrost on 8080/8083 and other services on 8081)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATA_DIR="$SCRIPT_DIR/data"
LOG_FILE="{{CATALYST_ROOT}}/logs/weaviate.log"

# Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Check if already running
if lsof -Pi :8082 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "❌ Weaviate already running on port 8082"
    echo "   Use 'lsof -ti:8082 | xargs kill' to stop it first"
    exit 1
fi

echo "🚀 Starting Weaviate server..."
echo "   Port: 8082"
echo "   Data: $DATA_DIR"
echo "   Logs: $LOG_FILE"

# Start Weaviate with minimal configuration for caching
# - No vectorizer modules (Bifrost handles embeddings via OpenAI)
# - Authentication disabled for local use
# - Persistence enabled for cache durability
# - Disk check disabled (caching data is minimal, disk warnings not relevant)
cd "$SCRIPT_DIR"

# Get IP address for cluster hostname resolution
HOST_IP=$(ipconfig getifaddr en0 || echo "127.0.0.1")

STANDALONE_MODE=true \
PERSISTENCE_DATA_PATH="$DATA_DIR" \
AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
DEFAULT_VECTORIZER_MODULE=none \
ENABLE_MODULES="" \
CLUSTER_GOSSIP_BIND_PORT=7946 \
CLUSTER_DATA_BIND_PORT=7947 \
RAFT_BOOTSTRAP_EXPECT=1 \
RAFT_ENABLE_ONE_NODE_RECOVERY=true \
RAFT_JOIN="weaviate-localhost" \
CLUSTER_HOSTNAME=weaviate-localhost \
CLUSTER_ADVERTISE_ADDR="127.0.0.1" \
ORIGIN=http://127.0.0.1:8082 \
DISK_USE_WARNING_PERCENTAGE=100 \
DISK_USE_READONLY_PERCENTAGE=100 \
./weaviate --host=127.0.0.1 --port=8082 --scheme=http >> "$LOG_FILE" 2>&1 &

WEAVIATE_PID=$!
echo "   PID: $WEAVIATE_PID"

# Wait for startup (check logs for "Serving weaviate" message)
echo -n "   Waiting for Weaviate to be ready..."
for i in {1..40}; do
    # Check if process is still running
    if ! ps -p $WEAVIATE_PID > /dev/null 2>&1; then
        echo " ❌ Process died"
        echo "Check logs at: $LOG_FILE"
        tail -10 "$LOG_FILE"
        exit 1
    fi

    # Check if server is ready via HTTP endpoint
    if curl -s http://127.0.0.1:8082/v1/.well-known/ready > /dev/null 2>&1; then
        echo " ✅ Ready!"
        echo ""
        echo "Weaviate server running on http://127.0.0.1:8082"
        echo "API endpoint: http://127.0.0.1:8082/v1"
        echo "Process ID: $WEAVIATE_PID"
        echo ""
        echo "To stop: {{CATALYST_ROOT}}/tools/weaviate/stop-weaviate.sh"
        exit 0
    fi
    echo -n "."
    sleep 1
done

echo " ❌ Timeout waiting for server"
echo "Check logs at: $LOG_FILE"
tail -20 "$LOG_FILE"
exit 1
