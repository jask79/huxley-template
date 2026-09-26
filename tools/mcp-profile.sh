#!/bin/bash
# MCP Profile Switcher
# Usage: mcp-profile.sh <profile-name>
# Profiles: minimal, ios-development, web-development, automation, full

PROFILES_DIR="{{CATALYST_ROOT}}/config/mcp-profiles"
MCP_CONFIG="{{CATALYST_ROOT}}/.mcp.json"
BACKUP_DIR="{{CATALYST_ROOT}}/config/mcp-profiles"

show_usage() {
    echo "MCP Profile Switcher"
    echo ""
    echo "Usage: mcp-profile.sh <profile>"
    echo ""
    echo "Available profiles:"
    echo "  minimal          - Essential only (~300 MB)"
    echo "  ios-development  - iOS/macOS dev (~500 MB)"
    echo "  web-development  - Web frontend (~700 MB)"
    echo "  automation       - Browser/workflow (~800 MB)"
    echo "  full             - All MCPs (~3.4 GB)"
    echo ""
    echo "Current profile:"
    if [ -f "$MCP_CONFIG" ]; then
        grep -o '"description": "[^"]*"' "$MCP_CONFIG" | head -1 | sed 's/"description": "//;s/"//'
    fi
}

if [ -z "$1" ]; then
    show_usage
    exit 0
fi

PROFILE="$1"

case "$PROFILE" in
    minimal|ios-development|web-development|automation)
        SOURCE="$PROFILES_DIR/$PROFILE.json"
        ;;
    full)
        # Find the most recent full backup
        SOURCE=$(ls -t "$BACKUP_DIR"/../.mcp.json.backup-full-* 2>/dev/null | head -1)
        if [ -z "$SOURCE" ]; then
            echo "Error: No full backup found"
            exit 1
        fi
        ;;
    *)
        echo "Error: Unknown profile '$PROFILE'"
        show_usage
        exit 1
        ;;
esac

if [ ! -f "$SOURCE" ]; then
    echo "Error: Profile file not found: $SOURCE"
    exit 1
fi

# Copy the profile
cp "$SOURCE" "$MCP_CONFIG"
echo "✅ Switched to '$PROFILE' profile"
echo ""
echo "⚠️  Restart Claude Code session to apply changes"
echo ""
echo "MCPs in this profile:"
grep '"[a-z-]*":' "$MCP_CONFIG" | grep -v version | grep -v description | sed 's/.*"\([^"]*\)".*/  - \1/'
