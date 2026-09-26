#!/usr/bin/env bash
# ============================================================================
# run-hook.sh — portable Claude Code hook runner
# ============================================================================
# Hook commands in .claude/settings.json call this wrapper instead of
# hardcoding absolute paths or a specific Python interpreter. It:
#   1. Resolves the repo root from its own location (tools/hooks/ -> root)
#   2. Prefers "$ROOT/.venv/bin/python3" when present, otherwise falls back
#      to the system python3
#   3. Execs the named hook script (path given relative to the repo root),
#      preserving stdin so the hook receives Claude Code's JSON payload
#
# Usage (in .claude/settings.json):
#   "${CLAUDE_PROJECT_DIR}/tools/hooks/run-hook.sh" tools/hooks/post_tool_use.py
#
# Three cases exit 0 so a partial install never breaks a Claude Code session:
# a hook script that is not present at all, a *.py hook with no python3
# available anywhere, and a hook that is neither *.py nor *.sh and has no
# executable bit (that last one also prints a warning to stderr, because a
# lost +x is a breakage rather than a missing file). That is the whole
# guarantee — it is about missing files, a missing interpreter and a missing
# permission bit, nothing more. A hook that does run and fails still exits
# nonzero, by design: an ImportError from a Python dependency that was never
# installed, a *.sh hook that errors, or an executable hook whose own shebang
# interpreter is missing are all broken hooks, not partial installs, and are
# meant to be visible.
#
# Hooks inherit this wrapper's working directory (whatever Claude Code ran it
# from), so a hook that needs the repo root should resolve it itself rather
# than assume a cwd.
# ============================================================================
set -uo pipefail

# If either directory cannot be resolved, bail out quietly (exit 0) rather
# than continuing with an empty variable and an unintended absolute path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)" || exit 0
ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)" || exit 0
[[ -n "$SCRIPT_DIR" && -n "$ROOT" ]] || exit 0

if [[ $# -lt 1 ]]; then
    echo "usage: run-hook.sh <hook-path-relative-to-repo-root> [args...]" >&2
    exit 0
fi

HOOK_REL="$1"
shift

HOOK="$ROOT/$HOOK_REL"

# Missing hooks must never break the session.
[[ -f "$HOOK" ]] || exit 0

case "$HOOK" in
    *.py)
        if [[ -x "$ROOT/.venv/bin/python3" ]]; then
            PY="$ROOT/.venv/bin/python3"
        else
            PY="$(command -v python3 || true)"
        fi
        [[ -n "${PY:-}" ]] || exit 0
        exec "$PY" "$HOOK" "$@"
        ;;
    *.sh)
        exec bash "$HOOK" "$@"
        ;;
    *)
        if [[ -x "$HOOK" ]]; then
            exec "$HOOK" "$@"
        fi
        # Present, but neither *.py nor *.sh nor executable: there is no
        # interpreter to pick and no permission to exec, so it cannot run.
        # Still exit 0 — a session must not block on this — but say so on
        # stderr: a lost executable bit is a real breakage, and silence here
        # would make a hook that never fires look like a hook that passed.
        echo "run-hook.sh: $HOOK_REL exists but is not executable (missing +x, and the" >&2
        echo "  name is neither .py nor .sh, so no interpreter can be chosen) — hook" >&2
        echo "  SKIPPED. Fix with: chmod +x '$HOOK'" >&2
        exit 0
        ;;
esac
