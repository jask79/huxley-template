#!/usr/bin/env bash
set -euo pipefail
ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DEST="${ROOT}/sandbox/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${DEST}/builder-${STAMP}.tar.gz"
mkdir -p "$DEST"
tar --exclude='.trash' -czf "$OUT" -C "$(dirname "$ROOT")" "$(basename "$ROOT")"
echo "Snapshot: $OUT"





