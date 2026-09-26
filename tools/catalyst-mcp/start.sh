#!/bin/bash
# Huxley MCP Server Startup Script

set -e

# Add Node to PATH
export PATH="/opt/homebrew/bin:$PATH"

# Set database path
export CATALYST_DB="${CATALYST_DB:-{{CATALYST_ROOT}}/tasks.db}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the MCP server
exec node "${SCRIPT_DIR}/dist/index.js"
