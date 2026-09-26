#!/bin/bash
# ${CATALYST_ROOT:-{{CATALYST_ROOT}}}/tools/memory/clear_memory.sh
# Kill-switch: Clear Huxley MCP Memory data

set -euo pipefail

CATALYST_ROOT="${CATALYST_ROOT:-{{CATALYST_ROOT}}}"
MCP_MEMORY_DIR="$HOME/.claude/mcp-data"
MEMORY_FILE="$MCP_MEMORY_DIR/builder-memory.json"

echo "🗑️  Huxley Memory Kill-Switch"
echo "========================================="

# Check if memory file exists
if [ ! -f "$MEMORY_FILE" ]; then
    echo "ℹ️  No memory file found at: $MEMORY_FILE"
    echo "   Memory system is already clear"
    exit 0
fi

# Show current memory size
MEMORY_SIZE=$(du -h "$MEMORY_FILE" | cut -f1)
echo "📊 Current memory size: $MEMORY_SIZE"

# Safety confirmation
echo ""
echo "⚠️  This will permanently delete all Huxley MCP memory data!"
echo "   Memory file: $MEMORY_FILE"
echo ""
read -p "Are you sure? Type 'DELETE' to confirm: " CONFIRM

if [ "$CONFIRM" != "DELETE" ]; then
    echo "❌ Memory clear cancelled"
    exit 1
fi

# Create final backup before deletion
echo "💾 Creating final backup before deletion..."
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_DIR="$CATALYST_ROOT/global/backups/memory"
mkdir -p "$BACKUP_DIR"
cp "$MEMORY_FILE" "$BACKUP_DIR/builder-memory-final-$TIMESTAMP.json"

# Clear the memory
echo "🗑️  Clearing Huxley MCP memory..."

# Reset to minimal structure
cat > "$MEMORY_FILE" << 'EOF'
{
  "entities": {},
  "relations": {},
  "observations": {}
}
EOF

echo "✅ Huxley MCP memory cleared"
echo "💾 Final backup saved to: $BACKUP_DIR/builder-memory-final-$TIMESTAMP.json"
echo ""
echo "🔄 Restart Claude Code to reset memory system"
echo "🛠️  Run tools/memory/setup_memory.sh to reinitialize if needed"

