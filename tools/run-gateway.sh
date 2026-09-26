#!/bin/bash
# Launch Claude Code in Gateway mode (Bifrost stack).
# Configures Router + Bifrost env vars for this process tree only.

set -euo pipefail

BIFROST_HEALTH_URL="http://localhost:8083/v1/models"
BIFROST_DIR="{{CATALYST_ROOT}}/tools/gateways/bifrost-cli"
ROUTER_START_SCRIPT="{{CATALYST_ROOT}}/tools/gateways/claude-router/start_router.sh"

DEFAULT_PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:/opt/homebrew/sbin"
PATH="${PATH:-$DEFAULT_PATH}"
export PATH="$HOME/.local/share/pnpm:$HOME/Library/pnpm:$PATH"

LOG_DIR="$HOME/Library/Logs/ClaudeInfinity"
LOG_FILE="$LOG_DIR/run-gateway.log"

mkdir -p "$LOG_DIR"

timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

log() {
    printf '[%s] %s\n' "$(timestamp)" "$*" >> "$LOG_FILE"
}

ENV_FILE="{{CATALYST_ROOT}}/.env"
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC2046,SC2002
    export $(grep -v '^#' "$ENV_FILE" | xargs)
    log "Loaded environment variables from $ENV_FILE."
else
    log "No .env file found at $ENV_FILE; continuing with existing environment."
fi

trap 'log "run-gateway.sh exiting with status $?."' EXIT

log "run-gateway.sh started (PID $$)."
log "PATH resolved to: $PATH"

# Check if Bifrost gateway is running
if ! curl -s "$BIFROST_HEALTH_URL" > /dev/null 2>&1; then
    echo "⚠️  Bifrost gateway not detected at $BIFROST_HEALTH_URL"
    echo "   Attempting to start Bifrost + Shim..."
    log "Bifrost not detected; attempting to start via start-infinity-gateway.sh."

    GATEWAY_START="{{CATALYST_ROOT}}/tools/start-infinity-gateway.sh"
    if [ ! -x "$GATEWAY_START" ]; then
        echo "❌ Gateway start script not found at $GATEWAY_START"
        log "Missing gateway start script."
        exit 1
    fi

    "$GATEWAY_START" >> "$LOG_FILE" 2>&1

    # Wait up to ~15s for Bifrost to report healthy
    for attempt in {1..15}; do
        if curl -s "$BIFROST_HEALTH_URL" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    if curl -s "$BIFROST_HEALTH_URL" > /dev/null 2>&1; then
        log "Bifrost gateway reported healthy after retry loop."
    else
        log "Bifrost gateway failed to report healthy after retry loop."
    fi

    if ! curl -s "$BIFROST_HEALTH_URL" > /dev/null 2>&1; then
        echo "❌ Bifrost gateway still unavailable after waiting. Check logs at {{CATALYST_ROOT}}/logs/bifrost.log"
        log "Bifrost gateway unavailable after waiting; exiting with failure."
        exit 1
    fi
else
    log "Bifrost gateway already healthy."
fi

# Start Claude Code Router
if [ ! -x "$ROUTER_START_SCRIPT" ]; then
    echo "❌ Claude Code Router start script not found at $ROUTER_START_SCRIPT"
    log "Missing router start script at $ROUTER_START_SCRIPT."
    exit 1
fi

"$ROUTER_START_SCRIPT"
log "Invoked router start script."

# Wait for router to be ready
ROUTER_HEALTH_URL="http://127.0.0.1:3456/health"
for _ in {1..10}; do
    if curl -s "$ROUTER_HEALTH_URL" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# Configure environment for Router → Bifrost stack
export ANTHROPIC_BASE_URL="http://127.0.0.1:3456"
export ANTHROPIC_AUTH_TOKEN="sk-local-infinity"
log "Router health check completed; environment variables exported."
export CLAUDE_GATEWAY_MODE="infinity"
export CLAUDE_GATEWAY_STACK="router-bifrost"

cd {{CATALYST_ROOT}}

echo ""
echo "✅ Infinity Gateway ready! (Router → Bifrost)"
echo ""
echo "Architecture:"
echo "  Claude CLI → Router (:3456) → Bifrost (:8083) → OpenAI"
echo ""
echo "Default Model: gpt-4o-mini"
echo "Logs: $LOG_FILE"
echo ""
echo "Launching shell..."
log "Gateway ready; launching interactive shell."

SHELL_BIN="${SHELL:-/bin/bash}"
exec "$SHELL_BIN" -l -i "$@"
