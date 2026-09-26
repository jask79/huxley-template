#!/bin/bash
# Sora 2 Video Generation via OpenAI API
# Usage: ./generate-video.sh "Your prompt here" [output_filename] [duration] [resolution]

set -euo pipefail

PROMPT="${1:-}"
OUTPUT_NAME="${2:-video_$(date +%Y%m%d_%H%M%S)}"
DURATION="${3:-4}"
SIZE="${4:-1280x720}"
OUTPUT_DIR="${VIDEO_OUTPUT_DIR:-{{CATALYST_ROOT}}/generated-media}"
MODEL="${VIDEO_MODEL:-sora-2}"
POLL_INTERVAL=10
MAX_WAIT=300

# Validate duration - Sora API only accepts "4", "8", or "12" seconds
if [[ "$DURATION" != "4" && "$DURATION" != "8" && "$DURATION" != "12" ]]; then
    echo "Warning: Duration must be 4, 8, or 12 seconds. Using closest valid value."
    if [[ "$DURATION" -le 6 ]]; then
        DURATION="4"
    elif [[ "$DURATION" -le 10 ]]; then
        DURATION="8"
    else
        DURATION="12"
    fi
fi

if [[ -z "$PROMPT" ]]; then
    echo "Usage: $0 \"prompt\" [output_filename] [duration_seconds] [resolution]"
    echo ""
    echo "Arguments:"
    echo "  prompt          - Video description (max 500 chars)"
    echo "  output_filename - Name without extension (default: video_timestamp)"
    echo "  duration        - Length in seconds: 4, 8, or 12 only (default: 4)"
    echo "  size            - Video dimensions (default: 1280x720)"
    echo ""
    echo "Available sizes:"
    echo "  1280x720   - Landscape 720p (YouTube, general)"
    echo "  720x1280   - Portrait 720p (TikTok, Reels, Shorts)"
    echo "  1792x1024  - Wide landscape (cinematic, highest quality)"
    echo "  1024x1792  - Tall portrait (stories, highest quality vertical)"
    echo ""
    echo "Environment variables:"
    echo "  OPENAI_API_KEY   - Required"
    echo "  VIDEO_MODEL      - sora-2 (default)"
    echo "  VIDEO_OUTPUT_DIR - Output directory (default: {{CATALYST_ROOT}}/generated-media)"
    echo ""
    echo "Pricing (approximate):"
    echo "  4 seconds:  ~\$1.50"
    echo "  8 seconds:  ~\$2.50"
    echo "  12 seconds: ~\$3.50"
    exit 1
fi

# Try environment first, then keychain
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    OPENAI_API_KEY=$(security find-generic-password -s "openai-api" -a "huxley" -w 2>/dev/null || true)
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "Error: OPENAI_API_KEY not set"
    echo "Set via environment or add to keychain:"
    echo "  security add-generic-password -s 'openai-api' -a 'huxley' -w 'your-key'"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Generating video with $MODEL..."
echo "Prompt: $PROMPT"
echo "Duration: ${DURATION}s | Size: $SIZE"

# Create video generation job
# Note: OpenAI Sora API uses 'seconds' as a string ("4", "8", or "12")
RESPONSE=$(curl -s "https://api.openai.com/v1/videos" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"prompt\": \"$PROMPT\",
    \"seconds\": \"$DURATION\",
    \"size\": \"$SIZE\"
  }")

# Check for errors
if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo "Error from API:"
    echo "$RESPONSE" | jq -r '.error.message // .error // .'
    exit 1
fi

# Extract job ID
JOB_ID=$(echo "$RESPONSE" | jq -r '.id // .job_id // empty')

if [[ -z "$JOB_ID" ]]; then
    echo "Failed to get job ID"
    echo "Response: $RESPONSE"
    exit 1
fi

echo "Job submitted: $JOB_ID"
echo "Polling for completion (this may take a few minutes)..."

# Poll for completion
ELAPSED=0
while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))

    STATUS_RESPONSE=$(curl -s "https://api.openai.com/v1/videos/$JOB_ID" \
      -H "Authorization: Bearer $OPENAI_API_KEY")

    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status // empty')

    echo "  Status: $STATUS (${ELAPSED}s elapsed)"

    if [[ "$STATUS" == "completed" ]]; then
        OUTPUT_PATH="$OUTPUT_DIR/${OUTPUT_NAME}.mp4"
        echo "Downloading video..."

        # Download video content from /content endpoint
        curl -s "https://api.openai.com/v1/videos/$JOB_ID/content" \
          -H "Authorization: Bearer $OPENAI_API_KEY" \
          -o "$OUTPUT_PATH"

        if [[ -f "$OUTPUT_PATH" && -s "$OUTPUT_PATH" ]]; then
            echo ""
            echo "Video saved to: $OUTPUT_PATH"

            # Get file size
            FILE_SIZE=$(ls -lh "$OUTPUT_PATH" | awk '{print $5}')
            echo "File size: $FILE_SIZE"
            echo "$OUTPUT_PATH"
            exit 0
        else
            echo "Failed to download video content"
            exit 1
        fi
    elif [[ "$STATUS" == "failed" ]]; then
        echo "Video generation failed:"
        echo "$STATUS_RESPONSE" | jq -r '.error // .'
        exit 1
    fi
done

echo "Timeout waiting for video generation (${MAX_WAIT}s)"
echo "Job ID: $JOB_ID - check manually"
exit 1
