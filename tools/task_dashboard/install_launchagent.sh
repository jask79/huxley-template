#!/bin/bash
# Install Huxley Task Dashboard LaunchAgent

set -e

PLIST_NAME="com.huxley.taskdashboard.plist"
PLIST_SRC="{{CATALYST_ROOT}}/tools/task_dashboard/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "📦 Installing Huxley Task Dashboard LaunchAgent..."

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# Copy plist file
echo "📄 Copying $PLIST_NAME to LaunchAgents..."
cp "$PLIST_SRC" "$PLIST_DEST"

# Unload if already loaded (ignore errors)
echo "🔄 Unloading previous version (if any)..."
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Load the agent
echo "✅ Loading LaunchAgent..."
launchctl load "$PLIST_DEST"

echo ""
echo "✨ Installation complete!"
echo ""
echo "Commands:"
echo "  Start:   launchctl start com.huxley.taskdashboard"
echo "  Stop:    launchctl stop com.huxley.taskdashboard"
echo "  Status:  launchctl list | grep catalyst"
echo "  Logs:    tail -f ~/Library/Logs/catalyst-taskdashboard.log"
echo ""
echo "Dashboard will be available at: http://localhost:3000"
echo ""
echo "Note: RunAtLoad is set to false - dashboard won't auto-start on boot."
echo "To enable auto-start, edit $PLIST_DEST and set RunAtLoad to true."
