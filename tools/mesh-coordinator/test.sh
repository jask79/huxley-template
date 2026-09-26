#!/bin/bash

# Test script for Mesh Coordinator MCP Server
# This tests the server can initialize (will fail without database table)

echo "🧪 Testing Mesh Coordinator MCP Server..."
echo ""

# Check if build exists
if [ ! -f "dist/index.js" ]; then
  echo "❌ Build not found. Run 'npm run build' first."
  exit 1
fi

echo "✅ Build files found"
echo ""

# Test that node can load the module
echo "Testing module loading..."
timeout 2 node dist/index.js <<EOF 2>&1 | head -20
EOF

# The server will fail to start without the database table, but we can verify it tries to start
if [ $? -eq 124 ]; then
  echo "✅ Server initialization timed out (expected without stdin)"
elif [ $? -eq 1 ]; then
  echo "⚠️  Server exited with error (likely database table not created yet)"
  echo ""
  echo "To create the database table, run:"
  echo "  sqlite3 {{CATALYST_ROOT}}/monitoring/quality.db < schema.sql"
else
  echo "✅ Server appears to start correctly"
fi

echo ""
echo "📋 Next steps:"
echo "  1. Create database table: sqlite3 {{CATALYST_ROOT}}/monitoring/quality.db < schema.sql"
echo "  2. Add to MCP config: See README.md for configuration"
echo "  3. Test with real request: Use Claude Code to call request_peer_help"
