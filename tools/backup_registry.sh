#!/usr/bin/env bash
set -euo pipefail
ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DEST="${DEST:-$ROOT/sandbox/backups/registry}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${DEST}/registry-${STAMP}.tar.gz"
mkdir -p "$DEST"
tar -czf "$OUT" -C "$ROOT" registry
echo "Registry backup: $OUT"






