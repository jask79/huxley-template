#!/bin/bash
#
# Huxley Remote Dev - Server Install (server machine)
#
# Sets up the server machine as an always-on dev server:
#   - Tailscale (VPN/NAT traversal)
#   - SSH with key auth
#   - Syncthing (real-time file sync)
#   - Caffeinate LaunchAgent (prevent sleep)
#   - tmux (session persistence)
#   - Shell aliases
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
ZSHRC="$HOME/.zshrc"

echo "=================================================="
echo "  Huxley Remote Dev - Server Install (server machine)"
echo "=================================================="
echo
echo "  Machine:  $(scutil --get ComputerName 2>/dev/null || hostname)"
echo "  User:     $USER"
echo "  Huxley: $CATALYST_ROOT"
echo

# ──────────────────────────────────────────────
# Step 1: Install Tailscale + tmux
# ──────────────────────────────────────────────
echo -e "${BLUE}[1/7]${NC} Installing dependencies via Homebrew..."

if ! command -v brew &>/dev/null; then
    echo -e "${RED}Homebrew not found. Install from https://brew.sh${NC}"
    exit 1
fi

for pkg in tailscale tmux syncthing; do
    if brew list "$pkg" &>/dev/null; then
        echo -e "${GREEN}  Already installed:${NC} $pkg"
    else
        echo -e "${YELLOW}  Installing:${NC} $pkg"
        brew install "$pkg"
        echo -e "${GREEN}  Installed:${NC} $pkg"
    fi
done
echo

# ──────────────────────────────────────────────
# Step 2: Start Tailscale
# ──────────────────────────────────────────────
echo -e "${BLUE}[2/7]${NC} Starting Tailscale..."

if tailscale status &>/dev/null; then
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    echo -e "${GREEN}  Already connected.${NC} Tailscale IP: $TS_IP"
else
    echo "  Starting Tailscale service..."
    brew services start tailscale 2>/dev/null || true
    sleep 2
    echo ""
    echo -e "${YELLOW}  Run the following to authenticate:${NC}"
    echo "    sudo tailscale up"
    echo ""
    echo "  This will open a browser for login. After auth, re-run this script"
    echo "  or continue manually."
    echo ""
    read -p "  Press Enter after Tailscale auth completes (or Ctrl-C to exit)... "
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    echo -e "${GREEN}  Connected.${NC} Tailscale IP: $TS_IP"
fi

echo
echo -e "${YELLOW}  *** IMPORTANT ***${NC}"
echo -e "  Your Tailscale IP: ${GREEN}$TS_IP${NC}"
echo "  You'll need this when setting up the client machine."
echo

# ──────────────────────────────────────────────
# Step 3: Enable Remote Login (SSH)
# ──────────────────────────────────────────────
echo -e "${BLUE}[3/7]${NC} Enabling Remote Login (SSH)..."

if pgrep -x sshd &>/dev/null; then
    echo -e "${GREEN}  Already enabled.${NC} (sshd running)"
else
    echo "  Enabling SSH (requires sudo)..."
    # launchctl method works on Sequoia without Full Disk Access
    if sudo launchctl load -w /System/Library/LaunchDaemons/ssh.plist 2>/dev/null; then
        echo -e "${GREEN}  SSH enabled.${NC}"
    else
        echo -e "${YELLOW}  Could not enable automatically. Run manually:${NC}"
        echo "    sudo launchctl load -w /System/Library/LaunchDaemons/ssh.plist"
        echo "  Or enable in System Settings > General > Sharing > Remote Login"
    fi
fi

# Set up authorized_keys
echo "  Ensuring ~/.ssh/authorized_keys exists..."
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
echo -e "${GREEN}  SSH authorized_keys ready.${NC} (permissions: 600)"
echo

# ──────────────────────────────────────────────
# Step 4: Install Caffeinate LaunchAgent
# ──────────────────────────────────────────────
echo -e "${BLUE}[4/7]${NC} Installing caffeinate LaunchAgent..."

PLIST_SRC="$SCRIPT_DIR/launchagents/com.huxley.caffeinate.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.huxley.caffeinate.plist"

mkdir -p "$HOME/Library/LaunchAgents"

# Unload existing if present
if launchctl list 2>/dev/null | grep -q "com.huxley.caffeinate"; then
    echo -e "${YELLOW}  Unloading existing agent...${NC}"
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    sleep 1
fi

# Kill any ad-hoc caffeinate processes (not our LaunchAgent one)
if pgrep -f "caffeinate" &>/dev/null; then
    echo -e "${YELLOW}  Killing ad-hoc caffeinate processes...${NC}"
    pkill -f "caffeinate" 2>/dev/null || true
    sleep 1
fi

# Symlink plist
ln -sf "$PLIST_SRC" "$PLIST_DEST"
chmod 644 "$PLIST_SRC"

# Load agent
launchctl load "$PLIST_DEST"
sleep 1

if launchctl list 2>/dev/null | grep -q "com.huxley.caffeinate"; then
    echo -e "${GREEN}  LaunchAgent loaded.${NC} The server will not sleep."
else
    echo -e "${RED}  Failed to load LaunchAgent.${NC}"
fi
echo

# ──────────────────────────────────────────────
# Step 5: Start Syncthing
# ──────────────────────────────────────────────
echo -e "${BLUE}[5/7]${NC} Setting up Syncthing..."

# Deploy .stignore
STIGNORE_SRC="$SCRIPT_DIR/stignore"
STIGNORE_DEST="$CATALYST_ROOT/.stignore"
if [ -f "$STIGNORE_SRC" ]; then
    cp "$STIGNORE_SRC" "$STIGNORE_DEST"
    echo -e "${GREEN}  Deployed .stignore${NC}"
fi

# Start Syncthing service
if brew services list 2>/dev/null | grep -q "syncthing.*started"; then
    echo -e "${GREEN}  Syncthing already running.${NC}"
else
    brew services start syncthing 2>/dev/null || true
    sleep 2
    echo -e "${GREEN}  Syncthing started.${NC}"
fi

# Get device ID
if command -v syncthing &>/dev/null; then
    DEVICE_ID=$(syncthing --device-id 2>/dev/null || echo "unknown")
    echo -e "  Device ID: ${GREEN}${DEVICE_ID:0:20}...${NC}"
    echo ""
    echo -e "${YELLOW}  Manual step needed:${NC}"
    echo "    1. Open http://localhost:8384 in a browser"
    echo "    2. Add the client machine as a remote device (get its Device ID)"
    echo "    3. Share the Huxley folder (path: $CATALYST_ROOT)"
    echo "    4. Set folder type: Send & Receive"
    echo "    5. Disable Global Discovery and Relaying (peer-to-peer only)"
fi
echo

# ──────────────────────────────────────────────
# Step 6: Symlink tmux.conf
# ──────────────────────────────────────────────
echo -e "${BLUE}[6/7]${NC} Installing tmux configuration..."

TMUX_SRC="$SCRIPT_DIR/tmux.conf"
TMUX_DEST="$HOME/.tmux.conf"

if [ -f "$TMUX_DEST" ] && [ ! -L "$TMUX_DEST" ]; then
    echo -e "${YELLOW}  Backing up existing ~/.tmux.conf to ~/.tmux.conf.bak${NC}"
    cp "$TMUX_DEST" "$TMUX_DEST.bak"
fi

ln -sf "$TMUX_SRC" "$TMUX_DEST"
echo -e "${GREEN}  Linked:${NC} ~/.tmux.conf -> $TMUX_SRC"
echo

# ──────────────────────────────────────────────
# Step 7: Add shell alias
# ──────────────────────────────────────────────
echo -e "${BLUE}[7/7]${NC} Adding shell alias..."

ALIAS_BLOCK="# Huxley Remote Dev - {{ORCHESTRATOR_NAME_LOWER}}-tmux
alias {{ORCHESTRATOR_NAME_LOWER}}-tmux='tmux new-session -A -s {{ORCHESTRATOR_NAME_LOWER}} -c \"$CATALYST_ROOT\" \"claude\"'"

if grep -q "{{ORCHESTRATOR_NAME_LOWER}}-tmux" "$ZSHRC" 2>/dev/null; then
    echo -e "${GREEN}  Alias '{{ORCHESTRATOR_NAME_LOWER}}-tmux' already in ~/.zshrc${NC}"
else
    echo "" >> "$ZSHRC"
    echo "$ALIAS_BLOCK" >> "$ZSHRC"
    echo -e "${GREEN}  Added '{{ORCHESTRATOR_NAME_LOWER}}-tmux' alias to ~/.zshrc${NC}"
fi
echo

# ──────────────────────────────────────────────
# Done
# ──────────────────────────────────────────────
echo "=================================================="
echo -e "${GREEN}  Server Install Complete!${NC}"
echo "=================================================="
echo
echo "  Tailscale IP: $TS_IP"
echo "  (Give this to install-client.sh on the client machine)"
echo
echo "  Quick reference:"
echo "    {{ORCHESTRATOR_NAME_LOWER}}-tmux         Start/attach Claude Code in tmux"
echo "    tmux ls          List sessions"
echo "    tmux a -t {{ORCHESTRATOR_NAME_LOWER}}    Reattach to {{ORCHESTRATOR_NAME_LOWER}} session"
echo
echo "  Next steps:"
echo "    1. Run verify-server.sh to confirm everything"
echo "    2. Commit & push, then run install-client.sh on the client machine"
echo
