#!/bin/bash
#
# Huxley Remote Dev - Client Install (client machine)
#
# Sets up the client machine as a remote client for the server machine:
#   - SSH config with Tailscale IP
#   - Key-based auth
#   - Syncthing (real-time file sync)
#   - Shell aliases for remote/local Claude Code
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

# Login on the always-on server machine (override: export SERVER_USER=...)
SERVER_USER_DEFAULT="{{USER_LOGIN}}"
SERVER_USER="${SERVER_USER:-$SERVER_USER_DEFAULT}"

echo "=================================================="
echo "  Huxley Remote Dev - Client Install (client machine)"
echo "=================================================="
echo

# ──────────────────────────────────────────────
# Step 1: Get the server machine's Tailscale IP
# ──────────────────────────────────────────────
echo -e "${BLUE}[1/6]${NC} Server Tailscale IP"
echo "  Run 'tailscale ip -4' on the server machine to get this."
echo ""
read -p "  Enter the server machine's Tailscale IP: " SERVER_IP

if [[ ! "$SERVER_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}  Invalid IP address: $SERVER_IP${NC}"
    exit 1
fi
echo -e "${GREEN}  Using IP:${NC} $SERVER_IP"
echo

# ──────────────────────────────────────────────
# Step 2: Configure SSH
# ──────────────────────────────────────────────
echo -e "${BLUE}[2/6]${NC} Configuring SSH..."

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

SSH_CONFIG="$HOME/.ssh/config"
touch "$SSH_CONFIG"
chmod 600 "$SSH_CONFIG"

if grep -q "Host {{ORCHESTRATOR_NAME_LOWER}}-server" "$SSH_CONFIG" 2>/dev/null; then
    echo -e "${YELLOW}  SSH config for '{{ORCHESTRATOR_NAME_LOWER}}-server' already exists.${NC}"
    echo "  To update, edit ~/.ssh/config manually."
else
    cat >> "$SSH_CONFIG" <<EOF

# Huxley - server machine via Tailscale
Host {{ORCHESTRATOR_NAME_LOWER}}-server
    HostName $SERVER_IP
    User $SERVER_USER
    ForwardAgent yes
    ServerAliveInterval 30
    ServerAliveCountMax 5
    StrictHostKeyChecking accept-new
EOF
    echo -e "${GREEN}  Added SSH config for '{{ORCHESTRATOR_NAME_LOWER}}-server'${NC}"
fi
echo

# ──────────────────────────────────────────────
# Step 3: Copy SSH key
# ──────────────────────────────────────────────
echo -e "${BLUE}[3/6]${NC} Copying SSH key to the server machine..."

if ssh -o ConnectTimeout=5 -o BatchMode=yes {{ORCHESTRATOR_NAME_LOWER}}-server "echo ok" &>/dev/null; then
    echo -e "${GREEN}  Key auth already works.${NC}"
else
    echo "  Copying your public key (you may be prompted for the server machine password)..."
    if ssh-copy-id {{ORCHESTRATOR_NAME_LOWER}}-server 2>/dev/null; then
        echo -e "${GREEN}  SSH key copied.${NC}"
    else
        echo -e "${YELLOW}  ssh-copy-id failed. You can manually add your key:${NC}"
        echo "    cat ~/.ssh/id_ed25519.pub | ssh {{ORCHESTRATOR_NAME_LOWER}}-server 'cat >> ~/.ssh/authorized_keys'"
    fi
fi
echo

# ──────────────────────────────────────────────
# Step 4: Add shell aliases
# ──────────────────────────────────────────────
echo -e "${BLUE}[4/6]${NC} Setting up Syncthing..."

# Install Syncthing if needed
if ! command -v syncthing &>/dev/null; then
    echo "  Installing Syncthing via Homebrew..."
    brew install syncthing
fi
echo -e "${GREEN}  Syncthing installed.${NC}"

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
    echo "    1. Open http://localhost:8384 on this client machine"
    echo "    2. Add the server machine as a remote device"
    echo "    3. Accept the shared Huxley folder"
    echo "    4. Disable Global Discovery and Relaying"
fi
echo

# ──────────────────────────────────────────────
# Step 5: Add shell aliases
# ──────────────────────────────────────────────
echo -e "${BLUE}[5/6]${NC} Adding shell aliases..."

# Define aliases
ALIAS_BLOCK='# Huxley Remote Dev - aliases
alias {{ORCHESTRATOR_NAME_LOWER}}="cd '"$CATALYST_ROOT"' && claude"
alias {{ORCHESTRATOR_NAME_LOWER}}-remote="ssh -t {{ORCHESTRATOR_NAME_LOWER}}-server '\''tmux new-session -A -s {{ORCHESTRATOR_NAME_LOWER}} -c {{CATALYST_ROOT}} \"claude\"'\''"
alias {{ORCHESTRATOR_NAME_LOWER}}-attach="ssh -t {{ORCHESTRATOR_NAME_LOWER}}-server '\''tmux attach-session -t {{ORCHESTRATOR_NAME_LOWER}}'\''"
alias {{ORCHESTRATOR_NAME_LOWER}}-sync="cd '"$CATALYST_ROOT"' && git pull && bash tools/remote-dev/patch-claude-config.sh"
alias {{ORCHESTRATOR_NAME_LOWER}}-server-status="ssh -o ConnectTimeout=3 {{ORCHESTRATOR_NAME_LOWER}}-server '\''echo \"Connected: \$(hostname)\"; tailscale ip -4; tmux list-sessions 2>/dev/null || echo \"No tmux sessions\"'\''"'

# Check if already added
if grep -q "# Huxley Remote Dev - aliases" "$ZSHRC" 2>/dev/null; then
    echo -e "${YELLOW}  Aliases already in ~/.zshrc${NC}"
    echo "  To update, remove the '# Huxley Remote Dev - aliases' block and re-run."
else
    echo "" >> "$ZSHRC"
    echo "$ALIAS_BLOCK" >> "$ZSHRC"
    echo -e "${GREEN}  Added aliases to ~/.zshrc:${NC}"
    echo "    {{ORCHESTRATOR_NAME_LOWER}}          - Local Claude Code (offline fallback)"
    echo "    {{ORCHESTRATOR_NAME_LOWER}}-remote   - SSH into the server + tmux + Claude Code"
    echo "    {{ORCHESTRATOR_NAME_LOWER}}-attach   - Reattach to existing tmux session"
    echo "    {{ORCHESTRATOR_NAME_LOWER}}-sync     - Git pull + patch config paths"
    echo "    {{ORCHESTRATOR_NAME_LOWER}}-server-status  - Quick connectivity check"
fi
echo

# ──────────────────────────────────────────────
# Step 5: Test connectivity
# ──────────────────────────────────────────────
echo -e "${BLUE}[6/6]${NC} Testing connectivity..."

echo -n "  SSH connection... "
if ssh -o ConnectTimeout=5 -o BatchMode=yes {{ORCHESTRATOR_NAME_LOWER}}-server "echo ok" &>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo "  Check your SSH key and Tailscale connection."
fi

echo -n "  tmux on remote... "
if ssh -o ConnectTimeout=5 -o BatchMode=yes {{ORCHESTRATOR_NAME_LOWER}}-server "command -v tmux" &>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}NOT FOUND${NC} (run install-server.sh on the server machine first)"
fi

echo -n "  claude on remote... "
if ssh -o ConnectTimeout=5 -o BatchMode=yes {{ORCHESTRATOR_NAME_LOWER}}-server "command -v claude" &>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}NOT FOUND${NC} (install Claude Code on the server machine)"
fi
echo

# ──────────────────────────────────────────────
# Done
# ──────────────────────────────────────────────
echo "=================================================="
echo -e "${GREEN}  Client Install Complete!${NC}"
echo "=================================================="
echo
echo "  Usage:"
echo "    {{ORCHESTRATOR_NAME_LOWER}}-remote     SSH into the server, start Claude Code in tmux"
echo "    {{ORCHESTRATOR_NAME_LOWER}}-attach     Reconnect after disconnect"
echo "    {{ORCHESTRATOR_NAME_LOWER}}            Local offline mode"
echo "    {{ORCHESTRATOR_NAME_LOWER}}-sync       Pull latest code + fix paths"
echo "    {{ORCHESTRATOR_NAME_LOWER}}-server-status    Quick connectivity check"
echo
echo "  Reload shell: source ~/.zshrc"
echo
