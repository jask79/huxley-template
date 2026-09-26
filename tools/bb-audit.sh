#!/usr/bin/env bash
set -euo pipefail
ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CAPS="$ROOT/capsules"
REG="$ROOT/registry/projects.json"
printf "Capsule | spec | mcp | agent-os | src\n"
printf "%s\n" "--------------------------------------"
for c in "$CAPS"/*; do
  [ -d "$c" ] || continue; bn="$(basename "$c")"
  s=$([ -f "$c/spec/requirements.yaml" ] && echo ✓ || echo ✗)
  m=$([ -f "$c/.mcp.json" ] && echo ✓ || echo ✗)
  a=$([ -d "$c/.agent-os" ] && echo ✓ || echo ✗)
  r=$([ -d "$c/src" ] && echo ✓ || echo ✗)
  printf "%s | %s | %s | %s | %s\n" "$bn" "$s" "$m" "$a" "$r"
done
echo ""
if command -v jq >/dev/null 2>&1 && [ -f "$REG" ]; then
  echo -n "Registry entries: "; jq 'length' "$REG"
fi





