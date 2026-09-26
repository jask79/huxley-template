#!/usr/bin/env bash
# codex-consult.sh — {{ORCHESTRATOR_NAME}} ↔ Codex peer consultation wrapper around `codex exec`.
#
# Replaces the deprecated BridgeHub CLI. Codex CLI v0.132+ has native sandboxing,
# session resume, and structured review built in, so this only adds:
#   1. Consistent prompt framing for the common consultation modes
#   2. Per-invocation logging for later audit
#
# Usage:
#   codex-consult.sh "free-form question for Codex"
#   codex-consult.sh --mode review --file path/to/code.ts "any extra context"
#   codex-consult.sh --mode diff "review the staged changes"
#   codex-consult.sh --mode diff --path src/a.ts --path src/b.ts "scoped review"
#   echo "long question" | codex-consult.sh --mode freeform
#
# Modes:
#   freeform  (default) — general question/discussion
#   review    — peer code review of --file (full contents attached)
#   diff      — peer review of git diff. Without --path: staged (HEAD vs index),
#               falling back to unstaged. With one or more --path: HEAD-relative
#               and scoped to those paths (git diff HEAD -- <paths>), capturing
#               both staged AND unstaged changes since the last commit.
#   spec      — validate a YAML/JSON spec at --file
#
# Options:
#   --path <p>  (diff mode, repeatable) — scope the diff to specific paths,
#               HEAD-relative. Safely quoted via a bash array (no word-splitting).
#
# Logs: ~/.cache/huxley/codex-consult/YYYY-MM-DD/<timestamp>-<mode>.log

set -euo pipefail

show_help() {
  cat <<'EOF'
codex-consult.sh — {{ORCHESTRATOR_NAME}} ↔ Codex peer consultation wrapper around `codex exec`.

Replaces the deprecated BridgeHub CLI. Codex CLI v0.132+ has native sandboxing,
session resume, and structured review built in, so this only adds:
  1. Consistent prompt framing for the common consultation modes
  2. Per-invocation logging for later audit

Usage:
  codex-consult.sh "free-form question for Codex"
  codex-consult.sh --mode review --file path/to/code.ts "any extra context"
  codex-consult.sh --mode diff "review the staged changes"
  codex-consult.sh --mode diff --path src/a.ts --path src/b.ts "scoped review"
  echo "long question" | codex-consult.sh --mode freeform

Modes:
  freeform  (default) — general question/discussion
  review    — peer code review of --file (full contents attached)
  diff      — peer review of git diff. Without --path: staged (HEAD vs index),
              falling back to unstaged. With one or more --path: HEAD-relative
              and scoped to those paths (git diff HEAD -- <paths>), capturing
              both staged AND unstaged changes since the last commit.
  spec      — validate a YAML/JSON spec at --file

Options:
  --path <p>  (diff mode, repeatable) — scope the diff to specific paths,
              HEAD-relative. Safely quoted via a bash array (no word-splitting).

Logs: ~/.cache/huxley/codex-consult/YYYY-MM-DD/<timestamp>-<mode>.log
EOF
}

MODE="freeform"
FILE=""
TOPIC=""
PATHS=()
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)  MODE="$2"; shift 2 ;;
    --file)  FILE="$2"; shift 2 ;;
    --path)  PATHS+=("$2"); shift 2 ;;
    --topic) TOPIC="$2"; shift 2 ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

# Preflight: without the Codex CLI on PATH this script does all of its work and
# then dies on its final line with a bare "command not found" (exit 127).
if ! command -v codex >/dev/null 2>&1; then
  cat >&2 <<'PREFLIGHT'
codex-consult: the `codex` CLI was not found on PATH.

  Install:      npm install -g @openai/codex
  Authenticate: codex login

Then re-run this command.
PREFLIGHT
  exit 127
fi

USER_MSG="${POSITIONAL[*]:-}"
# Note: for review/spec/diff modes, an empty USER_MSG is intentionally substituted
# with "(none)" later in the per-mode prompt construction (it's just extra context).
if [[ -z "$USER_MSG" && ! -t 0 ]]; then
  USER_MSG="$(cat)"
fi

# Appended to the review-mode prompts only. A review has twice modified files on
# disk (patched a script, wrote a new test file); reviews must be read-only and
# the caller applies fixes. This constrains Codex's ACTIONS, not its analysis —
# it is explicitly told to stay just as thorough.
READ_ONLY_NOTE=$'\n\nIMPORTANT — this is a READ-ONLY review. Report your findings as text only: do not modify, create, delete, move, or rename any file, do not apply patches or run a formatter, and do not add or edit tests. The caller applies every fix. Be exactly as thorough as if you were fixing it yourself: for each finding name the file and line and spell out the concrete change you would make, so nothing is lost by not editing.'

case "$MODE" in
  freeform)
    PROMPT="$USER_MSG"
    ;;
  review)
    if [[ -z "$FILE" || ! -f "$FILE" ]]; then
      echo "codex-consult: --mode review requires --file <path>" >&2
      exit 2
    fi
    PROMPT=$'You are a senior engineer doing peer review. Be direct and surgical.\n\nFile: '"$FILE"$'\n\n---\n'"$(cat "$FILE")"$'\n---\n\nExtra context: '"${USER_MSG:-(none)}"$'\n\nReport: (1) blocking issues, (2) suggested improvements, (3) anything you would push back on.'"$READ_ONLY_NOTE"
    ;;
  diff)
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
      echo "codex-consult: --mode diff requires running inside a git repository" >&2
      exit 2
    fi
    if [[ ${#PATHS[@]} -gt 0 ]]; then
      # Scoped, HEAD-relative diff: captures BOTH staged and unstaged changes
      # since the last commit for the given paths. The bash array prevents any
      # word-splitting or re-expansion of path values.
      DIFF="$(git diff HEAD -- "${PATHS[@]}" 2>/dev/null || true)"
      if [[ -z "$DIFF" ]]; then
        echo "codex-consult: no git diff (HEAD-relative) for the given --path(s) to review" >&2
        exit 2
      fi
    else
      DIFF="$(git diff --staged 2>/dev/null || true)"
      if [[ -z "$DIFF" ]]; then
        DIFF="$(git diff 2>/dev/null || true)"
      fi
      if [[ -z "$DIFF" ]]; then
        echo "codex-consult: no git diff (staged or unstaged) to review" >&2
        exit 2
      fi
    fi
    PROMPT=$'You are a senior engineer reviewing a git diff. Be direct.\n\n--- DIFF ---\n'"$DIFF"$'\n--- END DIFF ---\n\nExtra context: '"${USER_MSG:-(none)}"$'\n\nReport: (1) blocking issues, (2) suggested improvements, (3) anything risky or surprising.'"$READ_ONLY_NOTE"
    ;;
  spec)
    if [[ -z "$FILE" || ! -f "$FILE" ]]; then
      echo "codex-consult: --mode spec requires --file <path>" >&2
      exit 2
    fi
    PROMPT=$'Validate this spec for correctness, consistency, and completeness. File: '"$FILE"$'\n\n---\n'"$(cat "$FILE")"$'\n---\n\nExtra context: '"${USER_MSG:-(none)}"$'\n\nReport: schema/format issues, semantic inconsistencies, missing fields.'
    ;;
  *)
    echo "codex-consult: unknown mode '$MODE' (use freeform|review|diff|spec)" >&2
    exit 2
    ;;
esac

if [[ -z "$PROMPT" ]]; then
  echo "codex-consult: empty prompt" >&2
  exit 2
fi

LOG_DIR="${HOME}/.cache/huxley/codex-consult/$(date +%Y-%m-%d)"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
TOPIC_SLUG="$(echo "${TOPIC:-$MODE}" | tr -c '[:alnum:]._-' '_' | sed 's/_*$//')"
LOG_FILE="${LOG_DIR}/${STAMP}-${TOPIC_SLUG}.log"

{
  echo "=== codex-consult ==="
  echo "timestamp: $STAMP"
  echo "mode:      $MODE"
  echo "topic:     ${TOPIC:-(none)}"
  echo "file:      ${FILE:-(none)}"
  echo "cwd:       $(pwd)"
  echo "--- prompt ---"
  echo "$PROMPT"
  echo "--- response ---"
} > "$LOG_FILE"

codex exec --skip-git-repo-check "$PROMPT" 2>&1 | tee -a "$LOG_FILE"

echo "" >&2
echo "codex-consult: logged to $LOG_FILE" >&2
