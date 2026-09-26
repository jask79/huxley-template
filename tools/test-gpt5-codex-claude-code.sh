#!/bin/bash
# Test gpt-5-codex routing through Claude Code Router (Anthropic API format)

set -euo pipefail

echo "Testing GPT-5 Codex via Claude Code Router (Anthropic Messages API)"
echo "=================================================================="
echo ""

# The router expects Anthropic Messages API format and will route based on Router.default
# which is currently set to: bifrost-responses,openai/gpt-5-codex

curl -s http://127.0.0.1:3456/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: dummy" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "default",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": "Say hello. Just 1 sentence."
      }
    ]
  }' | python3 -m json.tool

echo ""
echo "=================================================================="
echo "Test complete. The router should have routed this to bifrost-responses."
