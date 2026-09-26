#!/bin/bash
# ${CATALYST_ROOT:-{{CATALYST_ROOT}}}/tools/memory/memory_status.sh
# Check Huxley MCP Memory system status

set -euo pipefail

CATALYST_ROOT="${CATALYST_ROOT:-{{CATALYST_ROOT}}}"
MCP_MEMORY_DIR="$HOME/.claude/mcp-data"
MEMORY_FILE="$MCP_MEMORY_DIR/builder-memory.json"
BACKUP_DIR="$CATALYST_ROOT/global/backups/memory"

echo "🧠 Huxley MCP Memory Status"
echo "========================================="

# Check if memory file exists
if [ ! -f "$MEMORY_FILE" ]; then
    echo "❌ Memory file not found: $MEMORY_FILE"
    echo "   Run tools/memory/setup_memory.sh to initialize"
    exit 1
fi

# Memory file info
MEMORY_SIZE=$(du -h "$MEMORY_FILE" | cut -f1)
MEMORY_MODIFIED=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$MEMORY_FILE" 2>/dev/null || date -r "$MEMORY_FILE" "+%Y-%m-%d %H:%M:%S")

echo "📁 Memory File:"
echo "   Location: $MEMORY_FILE"
echo "   Size: $MEMORY_SIZE"
echo "   Modified: $MEMORY_MODIFIED"

# Parse memory contents if jq is available
if command -v jq >/dev/null 2>&1 && [ -s "$MEMORY_FILE" ]; then
    echo ""
    echo "📊 Memory Contents:"
    
    ENTITY_COUNT=$(jq '.entities | length' "$MEMORY_FILE" 2>/dev/null || echo "0")
    RELATION_COUNT=$(jq '.relations | length' "$MEMORY_FILE" 2>/dev/null || echo "0")
    OBSERVATION_COUNT=$(jq '.observations | length' "$MEMORY_FILE" 2>/dev/null || echo "0")
    
    echo "   Entities: $ENTITY_COUNT"
    echo "   Relations: $RELATION_COUNT"
    echo "   Observations: $OBSERVATION_COUNT"
    
    # Show recent entities
    if [ "$ENTITY_COUNT" -gt 0 ]; then
        echo ""
        echo "🏷️  Recent Entities:"
        jq -r '.entities | to_entries[0:5] | .[] | "   • \(.key) (\(.value.type))"' "$MEMORY_FILE" 2>/dev/null || echo "   (parsing error)"
    fi
fi

# Backup info
if [ -d "$BACKUP_DIR" ]; then
    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "builder-memory-*.json" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo ""
    echo "💾 Backups:"
    echo "   Directory: $BACKUP_DIR"
    echo "   Count: $BACKUP_COUNT"
    
    if [ "$BACKUP_COUNT" -gt 0 ]; then
        echo "   Latest: $(find "$BACKUP_DIR" -name "builder-memory-*.json" -type f 2>/dev/null | sort -r | head -1 | xargs basename)"
    fi
fi

# MCP server status
echo ""
echo "🔌 MCP Integration:"
if claude mcp list 2>/dev/null | grep -q memory; then
    echo "   Status: ✅ MCP Memory server configured"
else
    echo "   Status: ⚠️  MCP Memory server not found"
    echo "   Run: claude mcp add memory-server ..."
fi

echo ""
echo "🛠️  Available Commands:"
echo "   tools/memory/backup_memory.sh  - Export memory data"
echo "   tools/memory/clear_memory.sh   - Kill-switch (delete all memory)"
echo "   tools/memory/setup_memory.sh   - Initialize/reinstall memory system"

