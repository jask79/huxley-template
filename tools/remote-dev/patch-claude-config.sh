#!/bin/bash
#
# Huxley Remote Dev - Patch Claude Config Paths
#
# Detects the current machine and rewrites hardcoded paths in
# .mcp.json and .claude/settings.json to match.
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CATALYST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MCP_JSON="$CATALYST_ROOT/.mcp.json"
SETTINGS_JSON="$CATALYST_ROOT/.claude/settings.json"

# Machine detection
CURRENT_USER="$USER"
CURRENT_HOME="$HOME"

# Known machine configs: "server" = the always-on box, "client" = the laptop.
# Defaults come from setup.sh; override any of them with environment variables.
SERVER_USER_DEFAULT="{{USER_LOGIN}}"
SERVER_USER="${SERVER_USER:-$SERVER_USER_DEFAULT}"
SERVER_HOME_DEFAULT="{{HOME_DIR}}"
SERVER_HOME="${SERVER_HOME:-$SERVER_HOME_DEFAULT}"
SERVER_CATALYST_DEFAULT="{{CATALYST_ROOT}}"
SERVER_CATALYST="${SERVER_CATALYST:-$SERVER_CATALYST_DEFAULT}"

CLIENT_USER="${CLIENT_USER:-your-client-login}"
CLIENT_HOME="${CLIENT_HOME:-/Users/$CLIENT_USER}"
CLIENT_CATALYST="${CLIENT_CATALYST:?set CLIENT_CATALYST to the checkout path on the client machine}"

echo "=================================================="
echo "  Huxley - Patch Claude Config Paths"
echo "=================================================="
echo

# Detect which machine we're on
if [ "$CURRENT_USER" = "$SERVER_USER" ]; then
    TARGET_HOME="$SERVER_HOME"
    TARGET_CATALYST="$SERVER_CATALYST"
    MACHINE_NAME="server machine"
    OTHER_HOME="$CLIENT_HOME"
    OTHER_CATALYST="$CLIENT_CATALYST"
elif [ "$CURRENT_USER" = "$CLIENT_USER" ]; then
    TARGET_HOME="$CLIENT_HOME"
    TARGET_CATALYST="$CLIENT_CATALYST"
    MACHINE_NAME="client machine"
    OTHER_HOME="$SERVER_HOME"
    OTHER_CATALYST="$SERVER_CATALYST"
else
    echo -e "${RED}Unknown machine (user: $CURRENT_USER)${NC}"
    echo "   Expected: $SERVER_USER (the server machine) or $CLIENT_USER (the client machine)"
    exit 1
fi

echo -e "${BLUE}Detected:${NC} $MACHINE_NAME (user: $CURRENT_USER)"
echo -e "${BLUE}Target paths:${NC}"
echo "   HOME:     $TARGET_HOME"
echo "   CATALYST: $TARGET_CATALYST"
echo

# Patch function
patch_file() {
    local file="$1"
    local filename
    filename="$(basename "$file")"

    if [ ! -f "$file" ]; then
        echo -e "${YELLOW}Skipped:${NC} $filename (not found)"
        return
    fi

    # Check if any paths need updating
    if grep -q "$OTHER_HOME" "$file" 2>/dev/null || grep -q "$OTHER_CATALYST" "$file" 2>/dev/null; then
        # Replace other machine's paths with this machine's paths
        sed -i '' "s|$OTHER_CATALYST|$TARGET_CATALYST|g" "$file"
        sed -i '' "s|$OTHER_HOME|$TARGET_HOME|g" "$file"
        echo -e "${GREEN}Patched:${NC} $filename"
    else
        echo -e "${GREEN}OK:${NC} $filename (paths already correct)"
    fi
}

# Patch config files
echo -e "${BLUE}Patching config files...${NC}"
patch_file "$MCP_JSON"
patch_file "$SETTINGS_JSON"

echo
echo -e "${GREEN}Done.${NC} Config paths set for $MACHINE_NAME."
