#!/bin/bash
# Ensure OpenClaw OpenResponses endpoint is enabled for local gateway usage.
# Intended to be sourced or executed by Infinity startup scripts.

set -euo pipefail

CFG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"

if ! command -v jq >/dev/null 2>&1; then
  echo "enable-openclaw-http-endpoints: jq is required" >&2
  exit 1
fi

if [ ! -f "$CFG" ]; then
  echo "enable-openclaw-http-endpoints: config not found at $CFG" >&2
  exit 1
fi

tmp="$(mktemp)"
jq '
  .gateway = (.gateway // {}) |
  .gateway.http = (.gateway.http // {}) |
  .gateway.http.endpoints = (.gateway.http.endpoints // {}) |
  .gateway.http.endpoints.chatCompletions = (.gateway.http.endpoints.chatCompletions // {}) |
  .gateway.http.endpoints.chatCompletions.enabled = true |
  .gateway.http.endpoints.responses = (.gateway.http.endpoints.responses // {}) |
  .gateway.http.endpoints.responses.enabled = true
' "$CFG" > "$tmp"

changed=0
if ! cmp -s "$CFG" "$tmp"; then
  mv "$tmp" "$CFG"
  changed=1
else
  rm -f "$tmp"
fi

if [ "$changed" -eq 1 ]; then
  echo "✅ Enabled OpenClaw OpenResponses endpoint in $CFG"
  if command -v openclaw >/dev/null 2>&1; then
    openclaw gateway restart >/dev/null 2>&1 || {
      echo "⚠️  Updated config, but OpenClaw gateway restart failed" >&2
      exit 1
    }
  fi
fi

port="$(jq -r '.gateway.port // 18789' "$CFG")"
echo "OPENCLAW_PORT=$port"
echo "OPENCLAW_RESPONSES_URL=http://127.0.0.1:${port}/v1/responses"
