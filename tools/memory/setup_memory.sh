#!/bin/bash
# ${CATALYST_ROOT:-{{CATALYST_ROOT}}}/tools/memory/setup_memory.sh
# Setup MCP Memory server with Huxley-specific configuration

set -euo pipefail

CATALYST_ROOT="${CATALYST_ROOT:-{{CATALYST_ROOT}}}"
MCP_MEMORY_DIR="$HOME/.claude/mcp-data"
MEMORY_FILE="$MCP_MEMORY_DIR/builder-memory.json"

echo "🧠 Setting up Huxley MCP Memory system..."

# Create MCP data directory
mkdir -p "$MCP_MEMORY_DIR"

# Configure MCP Memory server with Huxley-specific settings
echo "📝 Configuring MCP Memory server..."

# Add MCP Memory server to Claude configuration
echo "Adding MCP Memory server to Claude Code configuration..."

# Install the MCP memory server first
if ! npm list -g @modelcontextprotocol/server-memory >/dev/null 2>&1; then
    echo "Installing MCP Memory server..."
    npm install -g @modelcontextprotocol/server-memory
fi

# Add to Claude MCP configuration
export MEMORY_FILE_PATH="$MEMORY_FILE"
claude mcp add builder-memory npx @modelcontextprotocol/server-memory

# Create initial memory structure for Huxley
cat > "$MEMORY_FILE" << 'EOF'
{
  "entities": {
    "Huxley": {
      "type": "system",
      "observations": [
        "Two-lane automation pipeline (standard vs standard)",
        "Production capsules: 4, Test capsules: 18 (isolated)",
        "Daily automation at 9:10 AM via LaunchAgent",
        "Context preservation via CLAUDE.md + MCP memory"
      ]
    }
  },
  "relations": {},
  "observations": {}
}
EOF

echo "✅ MCP Memory server configured"
echo "📍 Memory file: $MEMORY_FILE"
echo "🔧 Use tools/memory/backup_memory.sh to export data"
echo "🗑️  Use tools/memory/clear_memory.sh to reset memory"
echo ""
echo "Next: Restart Claude Code to activate memory system"

