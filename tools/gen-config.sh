#!/usr/bin/env bash
set -euo pipefail
CAP="${1:?capsule path required}"

# Create minimal .mcp.json for project-specific MCPs only
# Global MCPs are automatically inherited from ~/.claude/mcp_servers.json
[ -f "$CAP/.mcp.json" ] || printf '{ "version":1, "clients": { "default": { "mcpServers": {} } } }\n' > "$CAP/.mcp.json"

echo "[gen-config] Initialized MCP config for $(basename "$CAP") - inherits global MCPs from ~/.claude/mcp_servers.json"





