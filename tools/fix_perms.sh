#!/bin/bash
# {{CATALYST_ROOT}}/tools/fix_perms.sh
# Permissions and line ending hardening for Huxley tools

set -euo pipefail

BASE="{{CATALYST_ROOT}}"
TOOLS_DIR="$BASE/tools"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting permissions and CRLF hardening..."

# Create required directories
mkdir -p "$BASE/registry/daily"
mkdir -p "$BASE/testing/capsules"
mkdir -p "$BASE/testing/logs"
mkdir -p "$BASE/testing/registry"

# Fix permissions on scripts
echo "Setting executable permissions on tools..."
for script in "$TOOLS_DIR"/*.sh "$TOOLS_DIR"/*.py; do
    if [[ -f "$script" ]]; then
        chmod +x "$script"
        echo "  Made executable: $(basename "$script")"
    fi
done

# Remove CRLF line endings safely
echo "Normalizing line endings in shell scripts..."
for script in "$TOOLS_DIR"/*.sh; do
    if [[ -f "$script" ]]; then
        # Use awk to strip \r characters safely
        if awk 'BEGIN{RS="\r\n"; ORS="\n"} {print}' "$script" > "$script.tmp"; then
            mv "$script.tmp" "$script"
            echo "  Normalized: $(basename "$script")"
        else
            rm -f "$script.tmp"
            echo "  WARNING: Could not normalize $(basename "$script")"
        fi
    fi
done

# Ensure registry structure
touch "$BASE/registry/events.jsonl"
touch "$BASE/registry/daily/daily_audit.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Permissions hardening complete"




