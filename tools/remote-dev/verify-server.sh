#!/bin/bash
#
# Huxley Remote Dev - Verify Server (server machine)
#
# Health check for the server machine setup.
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

check_pass() { echo -e "${GREEN}  PASS${NC} $1"; PASS=$((PASS + 1)); }
check_fail() { echo -e "${RED}  FAIL${NC} $1"; FAIL=$((FAIL + 1)); }
check_warn() { echo -e "${YELLOW}  WARN${NC} $1"; WARN=$((WARN + 1)); }

echo "=================================================="
echo "  Huxley Remote Dev - Server Health Check"
echo "=================================================="
echo

# 1. Tailscale
echo -e "${BLUE}[Tailscale]${NC}"
if command -v tailscale &>/dev/null; then
    check_pass "tailscale installed"
else
    check_fail "tailscale not installed"
fi

if tailscale status &>/dev/null; then
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    check_pass "tailscale connected (IP: $TS_IP)"
else
    check_fail "tailscale not connected"
fi
echo

# 2. SSH
echo -e "${BLUE}[SSH / Remote Login]${NC}"
if nc -z localhost 22 &>/dev/null; then
    check_pass "SSH listening on port 22"
else
    check_warn "SSH not listening (enable in System Settings > General > Sharing > Remote Login)"
fi

if [ -f "$HOME/.ssh/authorized_keys" ]; then
    PERMS=$(stat -f "%Lp" "$HOME/.ssh/authorized_keys" 2>/dev/null || echo "unknown")
    if [ "$PERMS" = "600" ]; then
        check_pass "authorized_keys exists (permissions: $PERMS)"
    else
        check_warn "authorized_keys exists but permissions are $PERMS (should be 600)"
    fi
else
    check_warn "authorized_keys not found (remote key auth won't work)"
fi
echo

# 3. Caffeinate LaunchAgent
echo -e "${BLUE}[Caffeinate LaunchAgent]${NC}"
PLIST="$HOME/Library/LaunchAgents/com.huxley.caffeinate.plist"
if [ -f "$PLIST" ] || [ -L "$PLIST" ]; then
    check_pass "plist installed"
else
    check_fail "plist not found at $PLIST"
fi

if launchctl list 2>/dev/null | grep -q "com.huxley.caffeinate"; then
    check_pass "LaunchAgent loaded"
else
    check_fail "LaunchAgent not loaded"
fi

if pgrep -f "caffeinate -d -i -s" &>/dev/null; then
    check_pass "caffeinate process running"
else
    check_warn "caffeinate process not detected"
fi
echo

# 4. tmux
echo -e "${BLUE}[tmux]${NC}"
if command -v tmux &>/dev/null; then
    check_pass "tmux installed ($(tmux -V))"
else
    check_fail "tmux not installed"
fi

if [ -f "$HOME/.tmux.conf" ] || [ -L "$HOME/.tmux.conf" ]; then
    check_pass "tmux.conf linked"
else
    check_warn "tmux.conf not found at ~/.tmux.conf"
fi
echo

# 5. Syncthing
echo -e "${BLUE}[Syncthing]${NC}"
if command -v syncthing &>/dev/null; then
    check_pass "syncthing installed ($(syncthing --version 2>/dev/null | head -1 | awk '{print $2}'))"
else
    check_fail "syncthing not installed"
fi

if brew services list 2>/dev/null | grep -q "syncthing.*started"; then
    check_pass "syncthing service running"
else
    check_fail "syncthing service not running (brew services start syncthing)"
fi

if curl -sf http://127.0.0.1:8384/rest/system/ping &>/dev/null; then
    check_pass "syncthing API responding (port 8384)"
else
    check_warn "syncthing API not responding on port 8384"
fi

CATALYST_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -f "$CATALYST_ROOT/.stignore" ]; then
    check_pass ".stignore deployed"
else
    check_warn ".stignore not found (run install-server.sh)"
fi
echo

# 6. Claude Code
echo -e "${BLUE}[Claude Code]${NC}"
if command -v claude &>/dev/null; then
    check_pass "claude CLI available"
else
    check_fail "claude CLI not found in PATH"
fi
echo

# Summary
echo "=================================================="
echo -e "  Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$WARN warnings${NC}"
echo "=================================================="

[ "$FAIL" -gt 0 ] && exit 1 || exit 0
