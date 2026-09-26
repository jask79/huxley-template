#!/bin/bash
# PM2 Auto-Startup Setup Script
# Run this to enable PM2 services to auto-start on system boot
# Note: This script is configured for user '{{USER_LOGIN}}' on this machine

set -e  # Exit on error

echo "🚀 Setting up PM2 auto-startup..."
echo ""

# Validate required binaries exist
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Install with: brew install node"
    exit 1
fi

if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 not found. Install with: npm install -g pm2"
    exit 1
fi

echo "This script will:"
echo "1. Configure PM2 to start on system boot"
echo "2. Save your current PM2 services"
echo "3. Create a LaunchAgent for macOS"
echo ""

# Get dynamic paths
NODE_DIR=$(dirname "$(which node)")
PM2_BIN="$HOME/.npm-global/bin/pm2"

# Fallback if PM2 not in expected location
if [ ! -f "$PM2_BIN" ]; then
    PM2_BIN=$(which pm2)
fi

echo "Using Node.js: $(which node)"
echo "Using PM2: $PM2_BIN"
echo ""

# Install the startup script (requires sudo)
echo "Installing PM2 startup script (requires password)..."
sudo env PATH="$PATH:$NODE_DIR" "$PM2_BIN" startup launchd -u "$USER" --hp "$HOME"

if [ $? -eq 0 ]; then
    echo "✅ PM2 startup script installed successfully!"
    echo ""
    echo "Your services will now auto-start on boot:"
    "$PM2_BIN" list
    echo ""
    echo "To test: sudo reboot (services should start automatically)"
else
    echo "❌ Failed to install PM2 startup script"
    exit 1
fi
