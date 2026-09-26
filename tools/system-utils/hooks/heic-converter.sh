#!/bin/bash
# HEIC Converter Hook — UserPromptSubmit
# Detects .heic file references in user prompts, converts to PNG for Claude Code readability.
# Handles macOS non-breaking space filenames (AirDrop screenshots).

set -euo pipefail

OUTDIR="/tmp/catalyst-screenshots"
MAX_WIDTH=1920

# Read hook input (JSON with prompt on stdin)
INPUT=$(cat)
PROMPT=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('prompt',''))" 2>/dev/null || echo "")

# Check if prompt mentions .heic (case-insensitive)
if ! echo "$PROMPT" | grep -qi '\.heic'; then
    exit 0
fi

mkdir -p "$OUTDIR"

# Extract file paths containing .heic
# Handles paths with spaces (quoted or unquoted)
HEIC_PATHS=$(echo "$PROMPT" | grep -oE '(/[^ "]+\.heic|"[^"]+\.heic")' | tr -d '"' || true)

if [ -z "$HEIC_PATHS" ]; then
    # Try to find it by extracting partial filename hints
    FILENAME_HINT=$(echo "$PROMPT" | grep -oiE 'Screenshot[^"]*\.heic' | head -1 || true)
    if [ -n "$FILENAME_HINT" ]; then
        # Use glob to find the actual file (handles non-breaking spaces)
        FOUND=$(find ~/Downloads -maxdepth 1 -name "$(echo "$FILENAME_HINT" | sed 's/ /*/g')" -print -quit 2>/dev/null || true)
        if [ -n "$FOUND" ]; then
            HEIC_PATHS="$FOUND"
        fi
    fi
fi

if [ -z "$HEIC_PATHS" ]; then
    exit 0
fi

CONVERTED=0
while IFS= read -r heic_path; do
    [ -z "$heic_path" ] && continue

    # If file doesn't exist directly, try glob matching (handles Unicode spaces)
    if [ ! -f "$heic_path" ]; then
        DIR=$(dirname "$heic_path")
        BASE=$(basename "$heic_path")
        # Replace spaces with glob wildcards to match non-breaking spaces
        GLOB_PATTERN=$(echo "$BASE" | sed 's/ /*/g')
        ACTUAL=$(find "$DIR" -maxdepth 1 -name "$GLOB_PATTERN" -print -quit 2>/dev/null || true)
        if [ -z "$ACTUAL" ] || [ ! -f "$ACTUAL" ]; then
            continue
        fi
        heic_path="$ACTUAL"
    fi

    # Generate output filename
    BASENAME=$(basename "$heic_path" .heic)
    BASENAME=$(echo "$BASENAME" | tr -cd 'A-Za-z0-9._-')  # Sanitize
    PNG_PATH="$OUTDIR/${BASENAME}.png"

    # Convert with sips, resize to keep under 256KB Read limit
    if sips -s format png -Z "$MAX_WIDTH" "$heic_path" --out "$PNG_PATH" >/dev/null 2>&1; then
        # If still over 200KB, resize further
        SIZE=$(stat -f%z "$PNG_PATH" 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 204800 ]; then
            sips -Z 1280 "$PNG_PATH" --out "$PNG_PATH" >/dev/null 2>&1
        fi
        SIZE=$(stat -f%z "$PNG_PATH" 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 204800 ]; then
            sips -Z 960 "$PNG_PATH" --out "$PNG_PATH" >/dev/null 2>&1
        fi

        SIZE_KB=$(( $(stat -f%z "$PNG_PATH" 2>/dev/null || echo 0) / 1024 ))
        echo "📸 HEIC converted → $PNG_PATH (${SIZE_KB}KB)"
        CONVERTED=$((CONVERTED + 1))
    fi
done <<< "$HEIC_PATHS"

if [ "$CONVERTED" -gt 0 ]; then
    echo "Use Read tool on the PNG path(s) above instead of the original .heic file."
fi
