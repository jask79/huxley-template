#!/usr/bin/env bash
set -euo pipefail
ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
TOOLS="$ROOT/tools"
CAPSULE_PATH="${1:-}"

if [ -n "$CAPSULE_PATH" ]; then
  python3 "$TOOLS/secretctl.py" preflight "$CAPSULE_PATH"
else
  python3 "$TOOLS/secretctl.py" preflight || true
fi






