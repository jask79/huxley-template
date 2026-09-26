#!/bin/bash
# Huxley helper to bootstrap and launch Claude Code Router
set -euo pipefail

# Ensure Node.js is in PATH (Homebrew on Apple Silicon)
export PATH="/opt/homebrew/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROUTER_DIR="$SCRIPT_DIR"
CONFIG_TEMPLATE_DEFAULT="$ROUTER_DIR/config/catalyst.json"
CONFIG_TEMPLATE="${CLAUDE_ROUTER_CONFIG_TEMPLATE:-$CONFIG_TEMPLATE_DEFAULT}"
if [[ "$CONFIG_TEMPLATE" != /* ]]; then
  CONFIG_TEMPLATE="$ROUTER_DIR/$CONFIG_TEMPLATE"
fi
if [ ! -f "$CONFIG_TEMPLATE" ]; then
  echo "❌ Claude Code Router config template not found at $CONFIG_TEMPLATE"
  exit 1
fi

ROUTER_HOME="${HOME}/.claude-code-router"
CLI_PATH="$ROUTER_DIR/dist/cli.js"
ENV_FILE="{{CATALYST_ROOT}}/.env"
CONFIG_REFRESHED=0

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-scoped-lite-unknown}"

render_config() {
  local destination="$1"
  local tmpfile
  tmpfile="$(mktemp)"
  python3 - "$CONFIG_TEMPLATE" "$tmpfile" <<'PY'
import os
import sys
from pathlib import Path

template_path, destination_path = sys.argv[1:]
text = Path(template_path).read_text()
text = os.path.expandvars(text)
Path(destination_path).write_text(text)
PY
  if [ ! -f "$destination" ] || ! cmp -s "$tmpfile" "$destination"; then
    mv "$tmpfile" "$destination"
    CONFIG_REFRESHED=1
  else
    rm -f "$tmpfile"
  fi
}

if ! command -v pnpm >/dev/null 2>&1; then
  echo "❌ pnpm is required to build Claude Code Router. Install via 'corepack enable' or 'npm install -g pnpm'."
  exit 1
fi

if [ ! -d "$ROUTER_DIR/node_modules" ]; then
  echo "📦 Installing Claude Code Router dependencies..."
  (cd "$ROUTER_DIR" && pnpm install)
fi

if [ ! -f "$CLI_PATH" ]; then
  echo "🛠️  Building Claude Code Router CLI..."
  (cd "$ROUTER_DIR" && pnpm run build)
fi

mkdir -p "$ROUTER_HOME"

CONFIG_PATH="$ROUTER_HOME/config.json"
CONFIG_PREEXISTING=0
if [ -f "$CONFIG_PATH" ]; then
  CONFIG_PREEXISTING=1
fi

render_config "$CONFIG_PATH"

if [ "$CONFIG_REFRESHED" -eq 1 ]; then
  if [ "$CONFIG_PREEXISTING" -eq 1 ]; then
    echo "🔄 Refreshing router configuration at $CONFIG_PATH."
  else
    echo "📝 Initializing router configuration at $CONFIG_PATH."
  fi
fi

PID_FILE="$ROUTER_HOME/.claude-code-router.pid"
ROUTER_RUNNING=0
if [ -f "$PID_FILE" ]; then
  if kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
    ROUTER_RUNNING=1
  else
    rm -f "$PID_FILE"
  fi
fi

if [ "$ROUTER_RUNNING" -eq 1 ] && [ "$CONFIG_REFRESHED" -eq 1 ]; then
  ROUTER_PID="$(cat "$PID_FILE")"
  echo "♻️  Restarting Claude Code Router to apply refreshed configuration (PID: $ROUTER_PID)."
  kill "$ROUTER_PID" >/dev/null 2>&1 || true
  sleep 1
  if kill -0 "$ROUTER_PID" >/dev/null 2>&1; then
    echo "⚠️  Router still running after TERM; forcing stop."
    kill -KILL "$ROUTER_PID" >/dev/null 2>&1 || true
    sleep 1
  fi
  rm -f "$PID_FILE"
  ROUTER_RUNNING=0
fi

if [ "$ROUTER_RUNNING" -eq 0 ]; then
  echo "🚀 Starting Claude Code Router service..."
  (cd "$ROUTER_DIR" && node dist/cli.js start >/dev/null 2>&1 &)
  sleep 1
else
  echo "✅ Claude Code Router already running."
fi
