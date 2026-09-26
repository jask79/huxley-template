#!/bin/bash
# Infinity Gateway Startup Script
# Starts Weaviate → Bifrost gateway → Claude Code Router → Bifrost Bridge Exporter

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CATALYST_ROOT="$(dirname "$SCRIPT_DIR")"

# Ensure Homebrew/node tools are resolvable when launched by iTerm profile.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Paths
WEAVIATE_SCRIPT="$SCRIPT_DIR/start-weaviate.sh"
BIFROST_DIR="$SCRIPT_DIR/gateways/bifrost-cli"
BIFROST_DATA="$SCRIPT_DIR/gateways/bifrost-data"
BIFROST_BIN_LEGACY="$BIFROST_DIR/node_modules/@maximhq/bifrost/bifrost-http"
BIFROST_BIN_JS="$BIFROST_DIR/node_modules/@maximhq/bifrost/bin.js"
ROUTER_DIR="$SCRIPT_DIR/gateways/claude-router"
ROUTER_SCRIPT="$ROUTER_DIR/start_router.sh"
LOGS_DIR="$CATALYST_ROOT/logs"

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

ENV_FILE="$CATALYST_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

# Ensure Bifrost dependency is installed locally.
if [ ! -x "$BIFROST_BIN_LEGACY" ] && [ ! -f "$BIFROST_BIN_JS" ]; then
    echo "⚠️  Bifrost binary missing. Installing dependencies in $BIFROST_DIR..."
    (cd "$BIFROST_DIR" && npm install --no-audit --no-fund) || {
        echo "❌ Failed to install Bifrost dependencies"
        exit 1
    }
fi

if [ -x "$BIFROST_BIN_LEGACY" ]; then
    BIFROST_LAUNCH=( "$BIFROST_BIN_LEGACY" -port 8083 -app-dir "$BIFROST_DATA" )
elif [ -f "$BIFROST_BIN_JS" ]; then
    BIFROST_LAUNCH=( node "$BIFROST_BIN_JS" -port 8083 -app-dir "$BIFROST_DATA" )
else
    echo "❌ Bifrost executable not found after install"
    exit 1
fi

# Prefer OpenAI Codex OAuth token from local OpenClaw/Codex auth profiles.
# This allows fallback mode to run without a static OPENAI_API_KEY.
OAUTH_SYNC_SCRIPT="$SCRIPT_DIR/sync-openai-codex-oauth.sh"
if [ -f "$OAUTH_SYNC_SCRIPT" ]; then
    # shellcheck disable=SC1090
    if source "$OAUTH_SYNC_SCRIPT" >/dev/null 2>&1; then
        echo "✅ Loaded OpenAI Codex OAuth token for gateway auth"
    else
        echo "⚠️  Could not load OpenAI Codex OAuth token; using OPENAI_API_KEY from environment"
    fi
fi

# Ensure OpenClaw local HTTP responses endpoint is enabled and restart if needed.
OPENCLAW_ENABLE_SCRIPT="$SCRIPT_DIR/enable-openclaw-http-endpoints.sh"
if [ -x "$OPENCLAW_ENABLE_SCRIPT" ]; then
    if "$OPENCLAW_ENABLE_SCRIPT" >/dev/null 2>&1; then
        echo "✅ OpenClaw OpenResponses endpoint is enabled"
    else
        echo "⚠️  Could not enable OpenClaw OpenResponses endpoint"
    fi
fi

# Load OpenClaw gateway auth token for local /v1/responses calls.
OPENCLAW_AUTH_SYNC_SCRIPT="$SCRIPT_DIR/sync-openclaw-gateway-auth.sh"
if [ -f "$OPENCLAW_AUTH_SYNC_SCRIPT" ]; then
    # shellcheck disable=SC1090
    if source "$OPENCLAW_AUTH_SYNC_SCRIPT" >/dev/null 2>&1; then
        echo "✅ Loaded OpenClaw gateway auth token for router"
    else
        echo "⚠️  Could not load OpenClaw gateway auth token"
    fi
fi

# Export fal.ai API key for image/video generation
# FAL_API_KEY loaded from .env file above (or set in environment)
export FAL_API_KEY="${FAL_API_KEY:-}"

# Step 1: Start Weaviate (required for semantic caching)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1/3: Starting Weaviate (Semantic Cache Vector Store)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -x "$WEAVIATE_SCRIPT" ]; then
    "$WEAVIATE_SCRIPT" || {
        echo "❌ Weaviate startup failed - semantic caching will be disabled"
        echo "   Bifrost will start without caching support"
    }
else
    echo "⚠️  Weaviate startup script not found at $WEAVIATE_SCRIPT"
    echo "   Semantic caching will be disabled"
fi
echo ""

# Step 2: Start Bifrost gateway
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2/3: Starting Bifrost Gateway"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if pgrep -f "bifrost-http" > /dev/null; then
    echo "⚠️  Bifrost is already running"
else
    echo "🚀 Starting Bifrost gateway..."
    cd "$BIFROST_DIR"
    "${BIFROST_LAUNCH[@]}" > "$LOGS_DIR/bifrost.log" 2>&1 &
    BIFROST_PID=$!
    echo "   Bifrost started (PID: $BIFROST_PID)"

    # Wait for Bifrost to be ready (check health endpoint)
    echo -n "   Waiting for Bifrost to be ready"
    for i in {1..20}; do
        if curl -s "http://localhost:8083/health" > /dev/null 2>&1; then
            echo ""
            echo "✅ Bifrost ready on http://localhost:8083"
            break
        fi
        echo -n "."
        sleep 0.5
    done
    echo ""
fi
echo ""

# Step 3: Start Claude Code Router
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/3: Starting Claude Code Router"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ! -x "$ROUTER_SCRIPT" ]; then
    echo "❌ Claude Code Router start script missing at $ROUTER_SCRIPT"
    exit 1
fi

echo "🚀 Starting Claude Code Router (Bifrost backend)..."
CLAUDE_ROUTER_CONFIG_TEMPLATE="config/infinity-bifrost.json" \
    "$ROUTER_SCRIPT"

ROUTER_HEALTH_URL="http://127.0.0.1:3456/health"
for _ in {1..20}; do
    if curl -s "$ROUTER_HEALTH_URL" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

if curl -s "$ROUTER_HEALTH_URL" > /dev/null 2>&1; then
    echo "✅ Claude Code Router responding on http://127.0.0.1:3456"
else
    echo "⚠️  Router health check failed; see ~/.claude-code-router/logs for details."
fi

# Step 4: Start Bifrost Bridge Exporter (OpenTelemetry metrics)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4/4: Starting Bifrost Bridge Exporter"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BRIDGE_EXPORTER="$CATALYST_ROOT/monitoring/exporters/start_bifrost_bridge.sh"
if [ -x "$BRIDGE_EXPORTER" ]; then
    "$BRIDGE_EXPORTER" > /dev/null 2>&1 || {
        echo "⚠️  Bifrost Bridge Exporter startup failed"
        echo "   Metrics collection will be unavailable"
    }

    # Verify it started
    if curl -s "http://localhost:9091/metrics" > /dev/null 2>&1; then
        echo "✅ Bifrost Bridge Exporter ready on http://localhost:9091/metrics"
    else
        echo "⚠️  Metrics endpoint not responding"
    fi
else
    echo "⚠️  Bifrost Bridge Exporter not found at $BRIDGE_EXPORTER"
    echo "   Metrics collection will be unavailable"
fi
echo ""

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Infinity Gateway Stack Ready"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Services:"
echo "  ✅ Weaviate:  http://localhost:8082 (Semantic cache vector store)"
echo "  ✅ Bifrost:   http://localhost:8083 (OpenAI-compatible gateway)"
echo "  ✅ Router:    http://127.0.0.1:3456 (Claude Code Router)"
echo "  ✅ Metrics:   http://localhost:9091/metrics (Prometheus/OpenTelemetry)"
echo ""
echo "Features:"
echo "  • Multi-provider routing (OpenAI, Groq, Fireworks)"
echo "  • Semantic caching (1h TTL, 0.85 similarity threshold)"
echo "  • Cost tracking and analytics"
echo "  • Load balancing across API keys"
echo ""
echo "Usage:"
echo "  export ANTHROPIC_BASE_URL=http://127.0.0.1:3456"
echo "  # Or use: source $CATALYST_ROOT/tools/use-infinity.sh"
echo ""
echo "Logs:"
echo "  • $LOGS_DIR/weaviate.log  (Vector store)"
echo "  • $LOGS_DIR/bifrost.log   (Gateway)"
echo "  • ~/.claude-code-router/logs/ccr-*.log (Router)"
echo "  • /tmp/bifrost_bridge.log (Metrics exporter)"
echo ""
echo "Dashboards:"
echo "  • http://localhost:8083 (Bifrost UI - usage stats, cost tracking)"
echo "  • http://localhost:9091/metrics (Prometheus metrics endpoint)"
echo ""
