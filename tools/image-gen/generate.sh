#!/bin/bash
# Nano Banana Pro Image Generation via OpenRouter
# Usage: ./generate.sh "Your prompt here" [output_filename]

set -euo pipefail

PROMPT="${1:-}"
OUTPUT_NAME="${2:-generated_$(date +%Y%m%d_%H%M%S)}"
OUTPUT_DIR="${IMAGE_OUTPUT_DIR:-{{CATALYST_ROOT}}/generated-media}"
MODEL="${IMAGE_MODEL:-google/gemini-3-pro-image-preview}"

if [[ -z "$PROMPT" ]]; then
    echo "Usage: $0 \"prompt\" [output_filename]"
    echo ""
    echo "Environment variables:"
    echo "  OPENROUTER_API_KEY - Required"
    echo "  IMAGE_MODEL - Model to use (default: google/gemini-2.5-flash-image)"
    echo "  IMAGE_OUTPUT_DIR - Output directory (default: {{CATALYST_ROOT}}/generated-media)"
    echo ""
    echo "Available models:"
    echo "  google/gemini-3-pro-image-preview  - Nano Banana Pro (best quality, 4K)"
    echo "  google/gemini-2.5-flash-image      - Nano Banana (fast, good quality)"
    exit 1
fi

# Try environment first, then keychain
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    OPENROUTER_API_KEY=$(security find-generic-password -s "openrouter-api" -a "huxley" -w 2>/dev/null || true)
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "Error: OPENROUTER_API_KEY not set"
    echo "Set via environment or add to keychain:"
    echo "  security add-generic-password -s 'openrouter-api' -a 'huxley' -w 'your-key'"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Generating image with $MODEL..."
echo "Prompt: $PROMPT"

# OpenRouter uses chat completions format for Gemini image generation
RESPONSE=$(curl -s "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "HTTP-Referer: https://{{BRAND}}.example" \
  -H "X-Title: Huxley Image Generator" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [
      {
        \"role\": \"user\",
        \"content\": \"Generate an image: $PROMPT\"
      }
    ]
  }")

# Check for errors
if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo "Error from API:"
    echo "$RESPONSE" | jq -r '.error.message // .error // .'
    exit 1
fi

# Extract image from the new format: message.images[0].image_url.url
IMAGE_URL=$(echo "$RESPONSE" | jq -r '.choices[0].message.images[0].image_url.url // empty')

if [[ -n "$IMAGE_URL" && "$IMAGE_URL" == data:image/* ]]; then
    # Extract base64 data after the comma
    BASE64_DATA=$(echo "$IMAGE_URL" | sed 's/^data:image\/[^;]*;base64,//')
    OUTPUT_PATH="$OUTPUT_DIR/${OUTPUT_NAME}.png"
    echo "$BASE64_DATA" | base64 -d > "$OUTPUT_PATH"
    echo ""
    echo "Image saved to: $OUTPUT_PATH"

    # Get usage info
    TOKENS=$(echo "$RESPONSE" | jq -r '.usage.total_tokens // "unknown"')
    echo "Tokens used: $TOKENS"

    # Output just the path for scripting
    echo "$OUTPUT_PATH"
    exit 0
fi

# Fallback: check content field for base64
IMAGE_DATA=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')
if [[ -n "$IMAGE_DATA" && "$IMAGE_DATA" == data:image/* ]]; then
    BASE64_DATA=$(echo "$IMAGE_DATA" | sed 's/^data:image\/[^;]*;base64,//')
    OUTPUT_PATH="$OUTPUT_DIR/${OUTPUT_NAME}.png"
    echo "$BASE64_DATA" | base64 -d > "$OUTPUT_PATH"
    echo ""
    echo "Image saved to: $OUTPUT_PATH"
    echo "$OUTPUT_PATH"
    exit 0
fi

# If we got here, no image was found
echo "No image data in response"
echo "Raw response:"
echo "$RESPONSE" | jq .
exit 1
