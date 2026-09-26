#!/bin/bash
#
# Huxley Remote Dev - Sync Secrets
#
# Syncs .env files from the server machine to the client machine (or vice versa) over Tailscale SSH.
# These files are gitignored, so they need manual sync.
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

# Default direction: pull from the server to local
DIRECTION="${1:-pull}"
REMOTE_HOST="${2:-{{ORCHESTRATOR_NAME_LOWER}}-server}"

# Remote Huxley path (server machine)
REMOTE_CATALYST="{{CATALYST_ROOT}}"

echo "=================================================="
echo "  Huxley - Sync Secrets (.env files)"
echo "=================================================="
echo

# Validate direction
if [[ "$DIRECTION" != "pull" && "$DIRECTION" != "push" ]]; then
    echo -e "${RED}Usage:${NC} $0 [pull|push] [remote-host]"
    echo "   pull  - Copy .env files FROM remote TO local (default)"
    echo "   push  - Copy .env files FROM local TO remote"
    echo "   remote-host - SSH host alias (default: {{ORCHESTRATOR_NAME_LOWER}}-server)"
    exit 1
fi

# Test SSH connectivity
echo -e "${BLUE}[1/3]${NC} Testing SSH connection to $REMOTE_HOST..."
if ! ssh -o ConnectTimeout=5 "$REMOTE_HOST" "echo ok" &>/dev/null; then
    echo -e "${RED}Cannot connect to $REMOTE_HOST${NC}"
    echo "   Make sure Tailscale is running and SSH is configured."
    exit 1
fi
echo -e "${GREEN}Connected.${NC}"
echo

# Find all .env files
echo -e "${BLUE}[2/3]${NC} Discovering .env files..."

# Build list of .env files (root + capsules)
ENV_FILES=()

if [ "$DIRECTION" = "pull" ]; then
    # Find .env files on remote
    while IFS= read -r line; do
        ENV_FILES+=("$line")
    done < <(ssh "$REMOTE_HOST" "find '$REMOTE_CATALYST' -name '.env' -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/.venv/*' 2>/dev/null" || true)
else
    # Find .env files locally
    while IFS= read -r line; do
        ENV_FILES+=("$line")
    done < <(find "$CATALYST_ROOT" -name '.env' -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/.venv/*' 2>/dev/null || true)
fi

if [ ${#ENV_FILES[@]} -eq 0 ]; then
    echo -e "${YELLOW}No .env files found.${NC}"
    exit 0
fi

echo "   Found ${#ENV_FILES[@]} .env file(s):"
for f in "${ENV_FILES[@]}"; do
    echo "   - $f"
done
echo

# Sync
echo -e "${BLUE}[3/3]${NC} Syncing ($DIRECTION)..."

SYNCED=0
for env_file in "${ENV_FILES[@]}"; do
    # Get relative path from catalyst root
    if [ "$DIRECTION" = "pull" ]; then
        REL_PATH="${env_file#$REMOTE_CATALYST/}"
        LOCAL_PATH="$CATALYST_ROOT/$REL_PATH"
        LOCAL_DIR="$(dirname "$LOCAL_PATH")"
        mkdir -p "$LOCAL_DIR"
        if rsync -az "$REMOTE_HOST:$env_file" "$LOCAL_PATH" 2>/dev/null; then
            echo -e "${GREEN}Synced:${NC} $REL_PATH"
            ((SYNCED++))
        else
            echo -e "${RED}Failed:${NC} $REL_PATH"
        fi
    else
        REL_PATH="${env_file#$CATALYST_ROOT/}"
        REMOTE_PATH="$REMOTE_CATALYST/$REL_PATH"
        REMOTE_DIR="$(dirname "$REMOTE_PATH")"
        ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_DIR'" 2>/dev/null
        if rsync -az "$env_file" "$REMOTE_HOST:$REMOTE_PATH" 2>/dev/null; then
            echo -e "${GREEN}Synced:${NC} $REL_PATH"
            ((SYNCED++))
        else
            echo -e "${RED}Failed:${NC} $REL_PATH"
        fi
    fi
done

echo
echo -e "${GREEN}Done.${NC} Synced $SYNCED/${#ENV_FILES[@]} .env file(s)."
