#!/usr/bin/env bash
set -euo pipefail

CATALYST_DIR="{{CATALYST_ROOT}}"
cd "$CATALYST_DIR"

export PATH="$HOME/.local/bin:$PATH"
# Ensure full toolchain PATH is present for Claude runtime features
# (MCP servers, agent orchestration, node/npx-backed tools).
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"

# Enable Infinity gateway env in this process.
# shellcheck disable=SC1091
source "$CATALYST_DIR/tools/use-infinity.sh"

if [ -x "$HOME/.local/bin/claude" ]; then
  exec "$HOME/.local/bin/claude" "$@"
fi

if command -v claude >/dev/null 2>&1; then
  exec "$(command -v claude)" "$@"
fi

echo "Error: claude CLI not found. Install Claude Code CLI or update tools/start-infinity-shell.sh" >&2
exit 127
