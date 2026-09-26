#!/bin/bash
#
# Huxley Remote Dev - Verify Client (client machine)
#
# Connectivity check for the client machine setup.
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REMOTE_HOST="${1:-{{ORCHESTRATOR_NAME_LOWER}}-server}"

PASS=0
FAIL=0
WARN=0

check_pass() { echo -e "${GREEN}  PASS${NC} $1"; PASS=$((PASS + 1)); }
check_fail() { echo -e "${RED}  FAIL${NC} $1"; FAIL=$((FAIL + 1)); }
check_warn() { echo -e "${YELLOW}  WARN${NC} $1"; WARN=$((WARN + 1)); }

echo "=================================================="
echo "  Huxley Remote Dev - Client Connectivity Check"
echo "=================================================="
echo

# 1. Local tools
echo -e "${BLUE}[Local Tools]${NC}"
if command -v tailscale &>/dev/null; then
    check_pass "tailscale installed"
else
    check_warn "tailscale not installed locally (not required if using direct IP)"
fi

if command -v tmux &>/dev/null; then
    check_pass "tmux installed locally"
else
    check_warn "tmux not installed locally (only needed on server)"
fi

if command -v claude &>/dev/null; then
    check_pass "claude CLI available locally"
else
    check_warn "claude CLI not found (needed for offline mode)"
fi
echo

# 2. SSH config
echo -e "${BLUE}[SSH Config]${NC}"
if grep -q "Host $REMOTE_HOST" "$HOME/.ssh/config" 2>/dev/null; then
    check_pass "SSH config entry for '$REMOTE_HOST' exists"
else
    check_fail "No SSH config entry for '$REMOTE_HOST'"
fi
echo

# 3. SSH connectivity
echo -e "${BLUE}[SSH Connectivity]${NC}"
echo "   Testing connection to $REMOTE_HOST..."
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "echo ok" &>/dev/null; then
    check_pass "SSH connection successful (key auth)"
else
    if ssh -o ConnectTimeout=5 "$REMOTE_HOST" "echo ok" &>/dev/null; then
        check_warn "SSH works but required password (add key with ssh-copy-id)"
    else
        check_fail "Cannot connect to $REMOTE_HOST"
    fi
fi
echo

# 4. Remote services
echo -e "${BLUE}[Remote Services]${NC}"
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "command -v tmux" &>/dev/null; then
    REMOTE_TMUX=$(ssh "$REMOTE_HOST" "tmux -V" 2>/dev/null || echo "unknown")
    check_pass "tmux on remote ($REMOTE_TMUX)"
else
    check_fail "tmux not found on remote"
fi

if ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "command -v claude" &>/dev/null; then
    check_pass "claude CLI on remote"
else
    check_fail "claude CLI not found on remote"
fi

# Check for existing tmux sessions
SESSIONS=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "tmux list-sessions 2>/dev/null" || true)
if [ -n "$SESSIONS" ]; then
    check_pass "Active tmux sessions on remote:"
    echo "$SESSIONS" | while IFS= read -r line; do
        echo "          $line"
    done
else
    echo -e "${BLUE}  INFO${NC} No active tmux sessions on remote"
fi
echo

# 5. Syncthing
echo -e "${BLUE}[Syncthing]${NC}"
if command -v syncthing &>/dev/null; then
    check_pass "syncthing installed locally"
else
    check_warn "syncthing not installed locally"
fi

if brew services list 2>/dev/null | grep -q "syncthing.*started"; then
    check_pass "syncthing service running locally"
else
    check_warn "syncthing service not running"
fi

CATALYST_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -f "$CATALYST_ROOT/.stignore" ]; then
    check_pass ".stignore deployed"
else
    check_warn ".stignore not found"
fi
echo

# 6. Shell aliases
echo -e "${BLUE}[Shell Aliases]${NC}"
for alias_name in {{ORCHESTRATOR_NAME_LOWER}}-remote {{ORCHESTRATOR_NAME_LOWER}}-attach {{ORCHESTRATOR_NAME_LOWER}}-server-status; do
    if grep -q "$alias_name" "$HOME/.zshrc" 2>/dev/null; then
        check_pass "alias '$alias_name' configured"
    else
        check_warn "alias '$alias_name' not found in ~/.zshrc"
    fi
done
echo

# Summary
echo "=================================================="
echo -e "  Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$WARN warnings${NC}"
echo "=================================================="

[ "$FAIL" -gt 0 ] && exit 1 || exit 0
