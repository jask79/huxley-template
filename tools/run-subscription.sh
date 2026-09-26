#!/usr/bin/env bash
set -euo pipefail

CATALYST_DIR="{{CATALYST_ROOT}}"
cd "$CATALYST_DIR"

export PATH="$HOME/.local/bin:$PATH"

# Guard for rare terminal profile auto-injected startup text.
# If iTerm sends a stale startup token (e.g., "Claude") right as the PTY opens,
# consume it before handing control to Claude Code.
prefill=""
if IFS= read -r -t 0.08 -n 128 prefill 2>/dev/null; then
  case "$prefill" in
    Claude|claude)
      ;;
    *)
      # Keep non-matching keystrokes by replaying into TTY.
      printf '%s' "$prefill" > /dev/tty 2>/dev/null || true
      ;;
  esac
fi

if [ -x "$HOME/.local/bin/claude" ]; then
  exec "$HOME/.local/bin/claude" "$@"
fi

if command -v claude >/dev/null 2>&1; then
  exec "$(command -v claude)" "$@"
fi

echo "Error: claude CLI not found. Install it or update tools/run-subscription.sh" >&2
exit 127
