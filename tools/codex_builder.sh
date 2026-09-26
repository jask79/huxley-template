#!/usr/bin/env bash
set -euo pipefail
python3 "$(cd "$(dirname "$0")/.." && pwd)/tools/compose_codex_context.py" >/dev/null 2>&1 || true
CTX="$HOME/.codex/context/builder_context.md"

# If your Codex CLI supports a --context-file flag, use it (uncomment and adapt):
# codex chat --model gpt-5 --context-file "$CTX" "$@"

# Fallback: banner + launch (you can paste context or use CLI's system message feature)
echo "=== Huxley Context prepared at: $CTX ==="
exec codex "$@"

