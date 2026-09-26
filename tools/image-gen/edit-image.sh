#!/bin/bash
# Nano Banana Pro Image-to-Image Editing via OpenRouter
# Usage: ./edit-image.sh "input_image.png" "Edit instruction" [output_filename]

set -euo pipefail

INPUT_IMAGE="${1:-}"
EDIT_PROMPT="${2:-}"
OUTPUT_NAME="${3:-edited_$(date +%Y%m%d_%H%M%S)}"
OUTPUT_DIR="${IMAGE_OUTPUT_DIR:-{{CATALYST_ROOT}}/generated-media}"
MODEL="${IMAGE_MODEL:-google/gemini-3-pro-image-preview}"

if [[ -z "$INPUT_IMAGE" || -z "$EDIT_PROMPT" ]]; then
    echo "Usage: $0 \"input_image\" \"edit instruction\" [output_filename]"
    echo ""
    echo "Arguments:"
    echo "  input_image     - Path to image file to edit (PNG, JPG, WebP)"
    echo "  edit_prompt     - Natural language edit instruction"
    echo "  output_filename - Name without extension (default: edited_timestamp)"
    echo ""
    echo "Examples:"
    echo "  $0 photo.png \"Change the background to a sunset\""
    echo "  $0 logo.png \"Make the text blue instead of red\" logo_blue"
    echo "  $0 portrait.jpg \"Remove the person in the background\""
    echo "  $0 product.png \"Add a shadow underneath the product\""
    echo ""
    echo "Environment variables:"
    echo "  OPENROUTER_API_KEY - Required"
    echo "  IMAGE_MODEL - Model to use (default: google/gemini-3-pro-image-preview)"
    echo "  IMAGE_OUTPUT_DIR - Output directory (default: {{CATALYST_ROOT}}/generated-media)"
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

if [[ ! -f "$INPUT_IMAGE" ]]; then
    echo "Error: Input image not found: $INPUT_IMAGE"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Detect image type
MIME_TYPE="image/png"
case "${INPUT_IMAGE,,}" in
    *.jpg|*.jpeg) MIME_TYPE="image/jpeg" ;;
    *.webp) MIME_TYPE="image/webp" ;;
    *.gif) MIME_TYPE="image/gif" ;;
esac

echo "Editing image with $MODEL..."
echo "Input: $INPUT_IMAGE"
echo "Edit: $EDIT_PROMPT"

# Encode image to base64
BASE64_IMG=$(base64 -i "$INPUT_IMAGE")

# Create request JSON (use temp file to handle large images)
TEMP_REQUEST=$(mktemp)
cat > "$TEMP_REQUEST" << EOF
{
  "model": "$MODEL",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": {
            "url": "data:${MIME_TYPE};base64,${BASE64_IMG}"
          }
        },
        {
          "type": "text",
          "text": "Edit this image: $EDIT_PROMPT"
        }
      ]
    }
  ]
}
EOF

# Make API request
RESPONSE=$(curl -s "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "HTTP-Referer: https://{{BRAND}}.example" \
  -H "X-Title: Huxley Image Editor" \
  -d @"$TEMP_REQUEST")

rm "$TEMP_REQUEST"

# Check for errors
if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo "Error from API:"
    echo "$RESPONSE" | jq -r '.error.message // .error // .'
    exit 1
fi

# Extract image from response
IMAGE_URL=$(echo "$RESPONSE" | jq -r '.choices[0].message.images[0].image_url.url // empty')

if [[ -n "$IMAGE_URL" && "$IMAGE_URL" == data:image/* ]]; then
    # Determine output extension from response MIME type
    OUTPUT_EXT="png"
    if [[ "$IMAGE_URL" == data:image/jpeg* ]]; then
        OUTPUT_EXT="jpg"
    elif [[ "$IMAGE_URL" == data:image/webp* ]]; then
        OUTPUT_EXT="webp"
    fi

    # Extract base64 data and save
    BASE64_DATA=$(echo "$IMAGE_URL" | sed 's/^data:image\/[^;]*;base64,//')
    OUTPUT_PATH="$OUTPUT_DIR/${OUTPUT_NAME}.${OUTPUT_EXT}"
    echo "$BASE64_DATA" | base64 -d > "$OUTPUT_PATH"

    echo ""
    echo "Edited image saved to: $OUTPUT_PATH"

    # Get usage info
    TOKENS=$(echo "$RESPONSE" | jq -r '.usage.total_tokens // "unknown"')
    echo "Tokens used: $TOKENS"

    echo "$OUTPUT_PATH"
    exit 0
fi

# Fallback: check content field
IMAGE_DATA=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')
if [[ -n "$IMAGE_DATA" && "$IMAGE_DATA" == data:image/* ]]; then
    BASE64_DATA=$(echo "$IMAGE_DATA" | sed 's/^data:image\/[^;]*;base64,//')
    OUTPUT_PATH="$OUTPUT_DIR/${OUTPUT_NAME}.png"
    echo "$BASE64_DATA" | base64 -d > "$OUTPUT_PATH"
    echo ""
    echo "Edited image saved to: $OUTPUT_PATH"
    echo "$OUTPUT_PATH"
    exit 0
fi

echo "No image data in response"
echo "Raw response:"
echo "$RESPONSE" | jq .
exit 1
