#!/bin/bash
set -euo pipefail

# Ensure gateway running
ROUTER_HEALTH="http://127.0.0.1:3456/health"
GATEWAY_START="{{CATALYST_ROOT}}/tools/start-infinity-gateway.sh"

if ! curl -s --max-time 2 "$ROUTER_HEALTH" >/dev/null 2>&1; then
  nohup "$GATEWAY_START" >/tmp/infinity-gateway-start.log 2>&1 &
  sleep 2
fi

# Export Infinity env
export ANTHROPIC_BASE_URL="http://127.0.0.1:3456"
export ANTHROPIC_API_KEY="dev-router-key"
export CLAUDE_GATEWAY_MODE="infinity"
export CLAUDE_GATEWAY_STACK="bifrost"

# Launch Claude Code CLI
exec {{HOME_DIR}}/.local/bin/claude "$@"
