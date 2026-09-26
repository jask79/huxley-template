#!/usr/bin/env bash
set -euo pipefail
ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
TLS="$ROOT/tools"
CAPS="$ROOT/capsules"
REG="$ROOT/registry/projects.json"

echo "== Huxley Preflight =="
[ -d "$CAPS" ] || { echo "No capsules/"; exit 1; }
# Audit at a glance
if [ -x "$TLS/bb-audit.sh" ]; then "$TLS/bb-audit.sh"; else echo "(bb-audit.sh not found)"; fi
# Lint specs
if [ -x "$TLS/lint_spec.py" ]; then
  echo ""; echo "== Lint specs =="; python3 "$TLS/lint_spec.py" || true
fi
# Registry vs disk
if command -v jq >/dev/null 2>&1 && [ -f "$REG" ]; then
  echo ""; echo "== Registry vs Disk =="
  caps_count=$(ls -1 "$CAPS" | wc -l | tr -d ' ')
  reg_count=$(jq 'length' "$REG")
  echo "capsules: $caps_count   registry: $reg_count"
  if [ "$caps_count" \!= "$reg_count" ]; then
    echo "WARN: count mismatch"
  fi
fi





