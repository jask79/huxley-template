#!/bin/bash
# Stop Infinity Gateway stack (Router → Bifrost → Weaviate)

echo "🛑 Stopping Infinity Gateway stack..."
echo ""

# Stop services in reverse order (Router → Bifrost → Weaviate)

# Stop Claude Code Router (first, as it depends on Bifrost)

# Stop Claude Code Router
ROUTER_PID_FILE="$HOME/.claude-code-router/.claude-code-router.pid"
ROUTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/claude-router"
ROUTER_STOPPED=0
if [ -f "$ROUTER_PID_FILE" ] && kill -0 "$(cat "$ROUTER_PID_FILE")" >/dev/null 2>&1; then
    if command -v pnpm >/dev/null 2>&1; then
        (cd "$ROUTER_DIR" && pnpm exec node dist/cli.js stop >/dev/null 2>&1) || true
    fi
    if kill -0 "$(cat "$ROUTER_PID_FILE")" >/dev/null 2>&1; then
        kill "$(cat "$ROUTER_PID_FILE")" >/dev/null 2>&1 || true
        sleep 1
    fi
    ROUTER_STOPPED=1
    rm -f "$ROUTER_PID_FILE"
fi

if [ "$ROUTER_STOPPED" -eq 1 ] || pgrep -f "claude-code-router" > /dev/null; then
    pkill -f "claude-code-router" >/dev/null 2>&1 || true
    echo "✅ Claude Code Router stopped"
else
    echo "⚠️  Claude Code Router was not running"
fi

# Stop Bifrost Bridge Exporter (second, as it monitors Bifrost)
STOP_BRIDGE_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../monitoring/exporters/stop_bifrost_bridge.sh"
if [ -x "$STOP_BRIDGE_SCRIPT" ]; then
    "$STOP_BRIDGE_SCRIPT" > /dev/null 2>&1 || true
elif pgrep -f "bifrost_bridge.py" > /dev/null; then
    pkill -f "bifrost_bridge.py" >/dev/null 2>&1 || true
    rm -f /tmp/bifrost_bridge.pid
    echo "✅ Bifrost Bridge Exporter stopped"
fi

# Stop Bifrost (third, as it depends on Weaviate)
if pgrep -f "bifrost-http" > /dev/null; then
    pkill -f "bifrost-http"
    echo "✅ Bifrost stopped"
else
    echo "⚠️  Bifrost was not running"
fi

# Stop Weaviate (last, as nothing depends on it after Bifrost is down)
if pgrep -f "weaviate --host" > /dev/null; then
    pkill -f "weaviate --host"
    echo "✅ Weaviate stopped"
else
    echo "⚠️  Weaviate was not running"
fi

# Stop legacy Anthropic shim if still running
if pgrep -f "anthropic-shim" > /dev/null; then
    pkill -f "anthropic-shim" >/dev/null 2>&1 || true
    echo "✅ Anthropic shim stopped (legacy process cleanup)"
fi

echo ""
echo "✨ Gateway stack stopped"
