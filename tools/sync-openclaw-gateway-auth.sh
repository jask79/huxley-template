#!/bin/bash
# Load OpenClaw gateway auth token + local responses URL into env.
# Intended to be sourced by gateway/router startup scripts.

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "sync-openclaw-gateway-auth: jq is required" >&2
  return 1 2>/dev/null || exit 1
fi

cfg="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
if [ ! -f "$cfg" ]; then
  echo "sync-openclaw-gateway-auth: config not found at $cfg" >&2
  return 1 2>/dev/null || exit 1
fi

token="$(jq -r '.gateway.auth.token // empty' "$cfg")"
port="$(jq -r '.gateway.port // 18789' "$cfg")"

if [ -z "$token" ]; then
  echo "sync-openclaw-gateway-auth: gateway auth token missing in $cfg" >&2
  return 1 2>/dev/null || exit 1
fi

export OPENCLAW_GATEWAY_TOKEN="$token"
export OPENCLAW_GATEWAY_PORT="$port"
export OPENCLAW_RESPONSES_BASE_URL="http://127.0.0.1:${port}/v1/responses"
export OPENCLAW_CHAT_COMPLETIONS_BASE_URL="http://127.0.0.1:${port}/v1/chat/completions"

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "OPENCLAW_GATEWAY_TOKEN loaded from $cfg"
  echo "OPENCLAW_RESPONSES_BASE_URL=$OPENCLAW_RESPONSES_BASE_URL"
  echo "OPENCLAW_CHAT_COMPLETIONS_BASE_URL=$OPENCLAW_CHAT_COMPLETIONS_BASE_URL"
fi
