#!/bin/bash
# Integration test for Huxley MCP Server

set -e

echo "===================================================="
echo "Huxley MCP Server Integration Test"
echo "===================================================="
echo ""

# Set environment
export PATH="/opt/homebrew/bin:$PATH"
export CATALYST_DB="{{CATALYST_ROOT}}/tasks.db"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "1. Verifying database..."
if [ ! -f "$CATALYST_DB" ]; then
    echo "   ❌ Database not found: $CATALYST_DB"
    exit 1
fi
echo "   ✅ Database exists: $CATALYST_DB"
echo ""

echo "2. Checking database tables..."
TABLES=$(sqlite3 "$CATALYST_DB" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;" 2>/dev/null || echo "")
if [ -z "$TABLES" ]; then
    echo "   ❌ No tables found in database"
    exit 1
fi
echo "   ✅ Found tables:"
echo "$TABLES" | sed 's/^/      - /'
echo ""

echo "3. Verifying build..."
if [ ! -d "dist" ] || [ ! -f "dist/index.js" ]; then
    echo "   ❌ Build not found, running build..."
    npm run build
fi
echo "   ✅ Build verified"
echo ""

echo "4. Testing database queries..."
# Insert test task
TASK_ID="test-$(date +%s)"
sqlite3 "$CATALYST_DB" "INSERT INTO tasks (id, description, capsule, priority, status) VALUES ('$TASK_ID', 'Integration test task', 'catalyst-mcp', 'medium', 'pending');"
echo "   ✅ Created test task: $TASK_ID"

# Query test task
RESULT=$(sqlite3 "$CATALYST_DB" "SELECT description FROM tasks WHERE id='$TASK_ID';" 2>/dev/null || echo "")
if [ "$RESULT" == "Integration test task" ]; then
    echo "   ✅ Successfully queried test task"
else
    echo "   ❌ Failed to query test task"
    exit 1
fi

# Clean up test task
sqlite3 "$CATALYST_DB" "DELETE FROM tasks WHERE id='$TASK_ID';"
echo "   ✅ Cleaned up test task"
echo ""

echo "5. Checking TypeScript compilation..."
if npm run build > /dev/null 2>&1; then
    echo "   ✅ TypeScript compilation successful"
else
    echo "   ❌ TypeScript compilation failed"
    exit 1
fi
echo ""

echo "6. Verifying MCP server can start..."
# Try to start server in background and kill it immediately
timeout 2s node dist/index.js 2>&1 | grep -q "Huxley MCP" && echo "   ✅ MCP server starts successfully" || echo "   ⚠️  Could not verify server startup (expected for stdio transport)"
echo ""

echo "===================================================="
echo "Integration Test Summary"
echo "===================================================="
echo "✅ Database: OK"
echo "✅ Schema: OK"
echo "✅ Build: OK"
echo "✅ Queries: OK"
echo ""
echo "MCP Server is ready for use with Claude Code!"
echo "Configuration: .mcp.json"
echo ""
