#!/bin/bash
# Enable Infinity Mode for Claude CLI
# Usage: source ./tools/use-infinity.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START_SCRIPT="$SCRIPT_DIR/start-infinity-gateway.sh"
ROUTER_HEALTH_URL="http://127.0.0.1:3456/health"

# Ensure Claude session has node/npx and standard tooling on PATH.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"

# Check if gateway is running
if ! pgrep -f "bifrost-http" > /dev/null; then
    echo "⚠️  Bifrost is not running. Starting Infinity Gateway..."
    "$START_SCRIPT"
    sleep 3
fi

# Ensure router is available; start gateway if needed
if ! curl -s --max-time 2 "$ROUTER_HEALTH_URL" > /dev/null 2>&1; then
    echo "⚠️  Claude Code Router not responding. Attempting restart..."
    "$START_SCRIPT"
    sleep 3
fi

# Verify router is responding
if curl -s --max-time 2 "$ROUTER_HEALTH_URL" > /dev/null 2>&1; then
    echo "✅ Infinity Gateway is online"
else
    echo "❌ Router unavailable. Check logs:"
    echo "   tail -f $SCRIPT_DIR/../logs/bifrost.log"
    echo "   tail -f \$HOME/.claude-code-router/logs/ccr-*.log"
    return 1
fi

# Set environment variable
export ANTHROPIC_BASE_URL=http://127.0.0.1:3456

# Router requires its API key for auth. Infinity profile should set this.
export ANTHROPIC_API_KEY="dev-router-key"

# Fast preflight: verify the current backend token can write via Responses API.
# Prevents Claude Code from entering long retry loops when OAuth lacks scopes.
PREFLIGHT_PAYLOAD='{"model":"claude-haiku-4-5-20251001","max_tokens":8,"messages":[{"role":"user","content":"ping"}]}'
PREFLIGHT_RAW=$(
  curl -s --max-time 10 -w $'\n%{http_code}' \
    -H "content-type: application/json" \
    -H "anthropic-version: 2023-06-01" \
    -H "x-api-key: dev-router-key" \
    -X POST "$ANTHROPIC_BASE_URL/v1/messages" \
    -d "$PREFLIGHT_PAYLOAD"
)
PREFLIGHT_CODE=$(printf '%s' "$PREFLIGHT_RAW" | tail -n 1)
PREFLIGHT_BODY=$(printf '%s' "$PREFLIGHT_RAW" | sed '$d')

if [ "$PREFLIGHT_CODE" != "200" ]; then
  if printf '%s' "$PREFLIGHT_BODY" | rg -q "api.responses.write|insufficient permissions|Missing scopes"; then
    echo "❌ Infinity preflight failed: OpenAI OAuth token lacks required API scope."
    echo "   Missing: api.responses.write"
    echo "   This OAuth account is not authorized for OpenAI Responses API write calls."
    echo ""
    echo "   Until scope is granted, Claude Code over Infinity will fail/retry."
    return 1
  fi
  if printf '%s' "$PREFLIGHT_BODY" | rg -q "Unauthorized|invalid gateway auth|invalid auth|authentication"; then
    echo "❌ Infinity preflight failed: OpenClaw gateway auth token was rejected."
    echo "   Run: openclaw gateway status"
    echo "   Then: ./tools/start-infinity-gateway.sh"
    return 1
  fi
  echo "❌ Infinity preflight failed (HTTP $PREFLIGHT_CODE)."
  echo "   Check router logs: tail -f \$HOME/.claude-code-router/logs/ccr-*.log"
  echo "   Check gateway logs: tail -f $SCRIPT_DIR/../logs/bifrost.log"
  return 1
fi

# Fetch current default model from router config
DEFAULT_MODEL=$(cat ~/.claude-code-router/config.json 2>/dev/null | jq -r '.Router.default' | cut -d',' -f2)
if [ -z "$DEFAULT_MODEL" ] || [ "$DEFAULT_MODEL" = "null" ]; then
  DEFAULT_MODEL="unknown"
fi

echo ""
echo "🎉 Infinity Mode ENABLED → $DEFAULT_MODEL"
echo ""
echo "To disable, run: unset ANTHROPIC_BASE_URL"
echo ""
