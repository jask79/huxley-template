#!/usr/bin/env bash
# agy-consult.sh — {{ORCHESTRATOR_NAME}} ↔ Antigravity (Gemini) peer consultation wrapper around `agy -p`.
#
# Sibling of codex-consult.sh. Use for a THIRD opinion (Gemini model family) in
# consensus reviews and for long-context reads. ADVISORY / READ-ONLY by design:
#   1. Runs agy with --sandbox (terminal restrictions)
#   2. Every mode's prompt forbids file modification
#   3. Per-invocation logging for later audit
#
# agy quirk: flags must come BEFORE -p, and the prompt AFTER it — Go flag
# parsing stops at the first positional arg, so `-p --model X "q"` silently
# drops the prompt. This wrapper handles the ordering.
#
# Usage:
#   agy-consult.sh "free-form question for Gemini"
#   agy-consult.sh --mode review --file path/to/code.ts "any extra context"
#   agy-consult.sh --mode diff "review the staged changes"
#   agy-consult.sh --mode diff --path src/a.ts --path src/b.ts "scoped review"
#   echo "long question" | agy-consult.sh --mode freeform
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
#   --path <p>   (diff mode, repeatable) — scope the diff to specific paths
#   --model <m>  agy model name (default: "Gemini 3.1 Pro (High)"; see `agy models`)
#   --topic <t>  slug for the log filename
#
# Logs: ~/.cache/huxley/agy-consult/YYYY-MM-DD/<timestamp>-<topic>.log

set -euo pipefail

show_help() {
  sed -n '2,36p' "$0" | sed 's/^# \{0,1\}//'
}

MODE="freeform"
FILE=""
TOPIC=""
MODEL="Gemini 3.1 Pro (High)"
PATHS=()
POSITIONAL=()

require_arg() {
  if [[ -z "${2-}" ]]; then
    echo "agy-consult: $1 requires a value" >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)  require_arg "$1" "${2-}"; MODE="$2"; shift 2 ;;
    --file)  require_arg "$1" "${2-}"; FILE="$2"; shift 2 ;;
    --path)  require_arg "$1" "${2-}"; PATHS+=("$2"); shift 2 ;;
    --topic) require_arg "$1" "${2-}"; TOPIC="$2"; shift 2 ;;
    --model) require_arg "$1" "${2-}"; MODEL="$2"; shift 2 ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

USER_MSG="${POSITIONAL[*]:-}"
# Note: for review/spec/diff modes, an empty USER_MSG is intentionally substituted
# with "(none)" later in the per-mode prompt construction (it's just extra context).
if [[ ! -t 0 ]]; then
  if [[ -z "$USER_MSG" ]]; then
    USER_MSG="$(cat)"
  else
    USER_MSG="$USER_MSG"$'\n'"$(cat)"
  fi
fi

READONLY_RULE=$'IMPORTANT: You are an advisory consultant. Do NOT create, modify, or delete any files, and do NOT run commands that change state. Read-only analysis only.'

case "$MODE" in
  freeform)
    if [[ -z "$USER_MSG" ]]; then
      echo "agy-consult: freeform mode requires a question (arg or stdin)" >&2
      exit 2
    fi
    PROMPT="$USER_MSG"$'\n\n'"$READONLY_RULE"
    ;;
  review)
    if [[ -z "$FILE" || ! -f "$FILE" ]]; then
      echo "agy-consult: --mode review requires --file <path>" >&2
      exit 2
    fi
    PROMPT="$READONLY_RULE"$'\n\nYou are a senior engineer doing peer review. Be direct and surgical.\n\nFile: '"$FILE"$'\n\n---\n'"$(cat "$FILE")"$'\n---\n\nExtra context: '"${USER_MSG:-(none)}"$'\n\nReport: (1) blocking issues, (2) suggested improvements, (3) anything you would push back on.'
    ;;
  diff)
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
      echo "agy-consult: --mode diff requires running inside a git repository" >&2
      exit 2
    fi
    if [[ ${#PATHS[@]} -gt 0 ]]; then
      DIFF="$(git diff HEAD -- "${PATHS[@]}" 2>/dev/null || true)"
      if [[ -z "$DIFF" ]]; then
        echo "agy-consult: no git diff (HEAD-relative) for the given --path(s) to review" >&2
        exit 2
      fi
    else
      DIFF="$(git diff --staged 2>/dev/null || true)"
      if [[ -z "$DIFF" ]]; then
        DIFF="$(git diff 2>/dev/null || true)"
      fi
      if [[ -z "$DIFF" ]]; then
        echo "agy-consult: no git diff (staged or unstaged) to review" >&2
        exit 2
      fi
    fi
    PROMPT="$READONLY_RULE"$'\n\nYou are a senior engineer reviewing a git diff. Be direct.\n\n--- DIFF ---\n'"$DIFF"$'\n--- END DIFF ---\n\nExtra context: '"${USER_MSG:-(none)}"$'\n\nReport: (1) blocking issues, (2) suggested improvements, (3) anything risky or surprising.'
    ;;
  spec)
    if [[ -z "$FILE" || ! -f "$FILE" ]]; then
      echo "agy-consult: --mode spec requires --file <path>" >&2
      exit 2
    fi
    PROMPT="$READONLY_RULE"$'\n\nValidate this spec for correctness, consistency, and completeness. File: '"$FILE"$'\n\n---\n'"$(cat "$FILE")"$'\n---\n\nExtra context: '"${USER_MSG:-(none)}"$'\n\nReport: schema/format issues, semantic inconsistencies, missing fields.'
    ;;
  *)
    echo "agy-consult: unknown mode '$MODE' (use freeform|review|diff|spec)" >&2
    exit 2
    ;;
esac

if [[ -z "$PROMPT" ]]; then
  echo "agy-consult: empty prompt" >&2
  exit 2
fi

LOG_DIR="${HOME}/.cache/huxley/agy-consult/$(date +%Y-%m-%d)"
umask 077
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
TOPIC_SLUG="$(echo "${TOPIC:-$MODE}" | tr -c '[:alnum:]._-' '_' | sed 's/_*$//')"
LOG_FILE="${LOG_DIR}/${STAMP}-${TOPIC_SLUG}.log"

{
  echo "=== agy-consult ==="
  echo "timestamp: $STAMP"
  echo "mode:      $MODE"
  echo "model:     $MODEL"
  echo "topic:     ${TOPIC:-(none)}"
  echo "file:      ${FILE:-(none)}"
  echo "cwd:       $(pwd)"
  echo "--- prompt ---"
  echo "$PROMPT"
  echo "--- response ---"
} > "$LOG_FILE"

# Flags BEFORE -p, prompt AFTER (see header). --sandbox = terminal restrictions.
agy --model "$MODEL" --sandbox --print-timeout 10m -p "$PROMPT" 2>&1 | tee -a "$LOG_FILE"

echo "" >&2
echo "agy-consult: logged to $LOG_FILE" >&2
