#!/bin/bash
# Huxley Capsule Navigation Wrapper
# Simplifies slash command token overhead while preserving full context loading
#
# STANDARD PATTERN FOR ALL CAPSULE NAVIGATION:
# When creating new capsule slash commands (.claude/commands/<name>.md):
#
# ---
# description: Navigate to <Capsule Name> capsule
# ---
#
# Run `bash tools/nav-capsule.sh <capsule-directory-name>` and present the capsule context output.
#
# This single-line format:
# - Reduces token overhead by ~30-40% vs multi-step instructions
# - Preserves full context loading (CLAUDE.md, MCP config, settings)
# - Maintains 30-minute TTL caching via nav_with_context.py
# - Automatically changes working directory

set -e

if [ -z "$1" ]; then
    echo "❌ Usage: nav-capsule.sh <capsule-name>"
    exit 1
fi

CAPSULE_NAME="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAV_SCRIPT="$SCRIPT_DIR/nav_with_context.py"

# Load context using Python script (with caching)
OUTPUT=$(python3 "$NAV_SCRIPT" "$CAPSULE_NAME" --format claude)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "$OUTPUT"
    exit $EXIT_CODE
fi

# Extract path from output and change directory
CAPSULE_PATH=$(echo "$OUTPUT" | grep "^📂 Path:" | sed 's/📂 Path: //')

if [ -n "$CAPSULE_PATH" ] && [ -d "$CAPSULE_PATH" ]; then
    cd "$CAPSULE_PATH"

    # Handle optional branch checkout (second argument)
    if [ -n "$2" ]; then
        BRANCH="$2"
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
        if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
            git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" 2>/dev/null
            echo ""
            echo "🔀 Switched to branch: $BRANCH"
        fi
    fi
fi

# Output the full context
echo "$OUTPUT"

# Show current branch status
if [ -n "$CAPSULE_PATH" ] && [ -d "$CAPSULE_PATH" ]; then
    cd "$CAPSULE_PATH"

    # Check for external repo config (capsules with their own GitHub repo)
    REPO_CONFIG="$CAPSULE_PATH/.capsule-repo"
    if [ -f "$REPO_CONFIG" ]; then
        EXT_BRANCH=$(grep '^branch=' "$REPO_CONFIG" | cut -d= -f2-)
        EXT_REPO=$(grep '^repo=' "$REPO_CONFIG" | cut -d= -f2-)
        EXT_REPO="${EXT_REPO:-unknown}"
        CURRENT_BRANCH="${EXT_BRANCH:-development}"
        echo ""
        echo "🌿 Branch: $CURRENT_BRANCH (repo: $EXT_REPO)"
    else
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        echo ""
        echo "🌿 Branch: $CURRENT_BRANCH"
    fi

    # Run capsule-specific on-navigate hook if it exists (non-fatal)
    ON_NAV_HOOK="$CAPSULE_PATH/.claude/hooks/on-navigate.sh"
    if [ -x "$ON_NAV_HOOK" ]; then
        echo ""
        bash "$ON_NAV_HOOK" || true
    fi
fi
