#!/bin/bash
# Test gpt-5-codex routing through Bifrost Responses API

set -euo pipefail

echo "Testing gpt-5-codex via Claude Code Router → Bifrost → OpenAI Responses API"
echo "============================================================================"
echo ""

# Test with a simple prompt
curl -s http://127.0.0.1:3456/v1/responses \
  -H "Content-Type: application/json" \
  -H "x-api-key: dummy" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "openai/gpt-5-codex",
    "max_tokens": 100,
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": "Say hello and confirm you are gpt-5-codex. Just 1-2 sentences."
          }
        ]
      }
    ]
  }' | python3 -m json.tool

echo ""
echo "============================================================================"
echo "Test complete. Check above for response from gpt-5-codex."
