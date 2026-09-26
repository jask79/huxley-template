#!/bin/bash
# Uninstall Huxley Task Dashboard LaunchAgent

set -e

PLIST_NAME="com.huxley.taskdashboard.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "🗑️  Uninstalling Huxley Task Dashboard LaunchAgent..."

if [[ ! -f "$PLIST_DEST" ]]; then
    echo "⚠️  LaunchAgent not installed. Nothing to uninstall."
    exit 0
fi

# Unload the agent
echo "🔄 Unloading LaunchAgent..."
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Remove plist file
echo "📄 Removing $PLIST_NAME..."
rm "$PLIST_DEST"

echo ""
echo "✅ Uninstallation complete!"
echo ""
echo "Dashboard can still be run manually with:"
echo "  cd {{CATALYST_ROOT}}/tools/task_dashboard && npm run dev"
