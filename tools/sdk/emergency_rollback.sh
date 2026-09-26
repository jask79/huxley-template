#!/usr/bin/env bash
# Emergency rollback stub — referenced by tools/sdk/autonomous_governance.yaml.
#
# TODO: implement a real rollback for YOUR deployment targets (git revert,
# service restart, capsule redeploy, ...). This stub only records that it
# fired, so a triggered emergency rollback is a logged no-op instead of a
# silent missing-file failure at exactly the moment it matters.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${CATALYST_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}/logs"
mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="${TMPDIR:-/tmp}"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"
MSG="[$STAMP] emergency_rollback.sh invoked (args: $*) — STUB: no rollback action is implemented yet"
printf '%s\n' "$MSG" >> "$LOG_DIR/emergency-rollback.log" 2>/dev/null || true
printf '%s\n' "$MSG" >&2
exit 0
