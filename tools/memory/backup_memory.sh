#!/bin/bash
# ${CATALYST_ROOT:-{{CATALYST_ROOT}}}/tools/memory/backup_memory.sh
# Backup and export Huxley MCP Memory data

set -euo pipefail

CATALYST_ROOT="${CATALYST_ROOT:-{{CATALYST_ROOT}}}"
MCP_MEMORY_DIR="$HOME/.claude/mcp-data"
MEMORY_FILE="$MCP_MEMORY_DIR/builder-memory.json"
BACKUP_DIR="$CATALYST_ROOT/global/backups/memory"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="$BACKUP_DIR/builder-memory-$TIMESTAMP.json"

echo "💾 Backing up Huxley MCP Memory..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Check if memory file exists
if [ ! -f "$MEMORY_FILE" ]; then
    echo "⚠️  Memory file not found: $MEMORY_FILE"
    echo "   Run tools/memory/setup_memory.sh first"
    exit 1
fi

# Copy memory file with timestamp
cp "$MEMORY_FILE" "$BACKUP_FILE"

# Create human-readable export
echo "📄 Creating human-readable export..."
if command -v jq >/dev/null 2>&1; then
    jq '.' "$MEMORY_FILE" > "$BACKUP_DIR/builder-memory-$TIMESTAMP-readable.json"
    
    # Extract just the key observations for quick review
    jq -r '.entities | to_entries[] | "\(.key): \(.value.observations[])"' "$MEMORY_FILE" > "$BACKUP_DIR/builder-memory-$TIMESTAMP-summary.txt"
fi

# Cleanup old backups (keep last 10)
find "$BACKUP_DIR" -name "builder-memory-*.json" -type f | sort -r | tail -n +11 | xargs rm -f 2>/dev/null || true

echo "✅ Memory backed up to:"
echo "   📁 $BACKUP_FILE"
if command -v jq >/dev/null 2>&1; then
    echo "   📄 $BACKUP_DIR/builder-memory-$TIMESTAMP-readable.json"
    echo "   📋 $BACKUP_DIR/builder-memory-$TIMESTAMP-summary.txt"
fi

# Show current memory size
MEMORY_SIZE=$(du -h "$MEMORY_FILE" | cut -f1)
echo "💭 Current memory size: $MEMORY_SIZE"

# Show backup count
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "builder-memory-*.json" -type f | wc -l)
echo "🗂️  Total backups: $BACKUP_COUNT"

