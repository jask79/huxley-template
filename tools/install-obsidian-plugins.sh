#!/bin/bash

# Obsidian Community Plugin Installer
# Downloads and installs Obsidian plugins from GitHub releases

set -e

VAULT_PATH="${OBSIDIAN_VAULT:-$HOME/Documents/Obsidian Vault}"
PLUGINS_DIR="$VAULT_PATH/.obsidian/plugins"
COMMUNITY_PLUGINS_JSON="$VAULT_PATH/.obsidian/community-plugins.json"

# Plugin definitions: "repo-name:plugin-id"
PLUGINS=(
    "SilentVoid13/Templater:templater-obsidian"
    "liamcain/obsidian-calendar-plugin:calendar"
    "liamcain/obsidian-periodic-notes:periodic-notes"
    "chhoumann/quickadd:quickadd"
    "blacksmithgu/obsidian-dataview:dataview"
    "phibr0/obsidian-charts:obsidian-charts"
    "pyrochlore/obsidian-tracker:obsidian-tracker"
    "obsidian-tasks-group/obsidian-tasks:obsidian-tasks-plugin"
    "mgmeyers/obsidian-kanban:obsidian-kanban"
    "Aetherinox/obsidian-mcp:magic-calendar"
)

echo "🔌 Installing Obsidian Community Plugins..."
echo ""

# Ensure plugins directory exists
mkdir -p "$PLUGINS_DIR"

# Read current community plugins list
if [ -f "$COMMUNITY_PLUGINS_JSON" ]; then
    CURRENT_PLUGINS=$(cat "$COMMUNITY_PLUGINS_JSON")
else
    CURRENT_PLUGINS="[]"
fi

# Install each plugin
for PLUGIN in "${PLUGINS[@]}"; do
    IFS=':' read -r REPO PLUGIN_ID <<< "$PLUGIN"

    echo "📦 Installing $PLUGIN_ID..."

    # Create plugin directory
    PLUGIN_DIR="$PLUGINS_DIR/$PLUGIN_ID"
    mkdir -p "$PLUGIN_DIR"

    # Get latest release info
    RELEASE_URL="https://api.github.com/repos/$REPO/releases/latest"
    echo "  Fetching release info from $REPO..."

    # Download manifest.json
    MANIFEST_URL="https://github.com/$REPO/releases/latest/download/manifest.json"
    if curl -fsSL "$MANIFEST_URL" -o "$PLUGIN_DIR/manifest.json" 2>/dev/null; then
        echo "  ✓ Downloaded manifest.json"
    else
        echo "  ⚠️  Failed to download manifest.json, trying alternate method..."
        # Try downloading from main branch
        curl -fsSL "https://raw.githubusercontent.com/$REPO/master/manifest.json" -o "$PLUGIN_DIR/manifest.json" || \
        curl -fsSL "https://raw.githubusercontent.com/$REPO/main/manifest.json" -o "$PLUGIN_DIR/manifest.json" || \
        echo "  ❌ Could not download manifest.json"
    fi

    # Download main.js
    MAIN_URL="https://github.com/$REPO/releases/latest/download/main.js"
    if curl -fsSL "$MAIN_URL" -o "$PLUGIN_DIR/main.js" 2>/dev/null; then
        echo "  ✓ Downloaded main.js"
    else
        echo "  ❌ Failed to download main.js (plugin may not be installable via API)"
        continue
    fi

    # Download styles.css (optional)
    STYLES_URL="https://github.com/$REPO/releases/latest/download/styles.css"
    if curl -fsSL "$STYLES_URL" -o "$PLUGIN_DIR/styles.css" 2>/dev/null; then
        echo "  ✓ Downloaded styles.css"
    else
        echo "  ℹ️  No styles.css (optional)"
    fi

    # Add to community-plugins.json if not already present
    if echo "$CURRENT_PLUGINS" | grep -q "\"$PLUGIN_ID\""; then
        echo "  ℹ️  Already registered in community-plugins.json"
    else
        echo "  ✓ Adding to community-plugins.json"
        CURRENT_PLUGINS=$(echo "$CURRENT_PLUGINS" | jq ". + [\"$PLUGIN_ID\"]")
    fi

    echo ""
done

# Write updated community-plugins.json
echo "$CURRENT_PLUGINS" | jq '.' > "$COMMUNITY_PLUGINS_JSON"

echo "✅ Plugin installation complete!"
echo ""
echo "📋 Installed plugins:"
jq -r '.[]' "$COMMUNITY_PLUGINS_JSON"
echo ""
echo "⚠️  NOTE: Restart Obsidian to activate the new plugins."
