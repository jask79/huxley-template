#!/bin/bash
# Huxley Photoshop MCP — startup script
set -e

# Ensure node is on PATH (Homebrew install)
export PATH="/opt/homebrew/bin:$PATH"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Default Huxley root if not set
export CATALYST_ROOT="${CATALYST_ROOT:-{{CATALYST_ROOT}}}"

# Default Photoshop app name (override per machine)
export PHOTOSHOP_APP_NAME="${PHOTOSHOP_APP_NAME:-Adobe Photoshop 2026}"

exec node "${SCRIPT_DIR}/dist/index.js"
