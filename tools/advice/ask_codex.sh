#!/usr/bin/env bash
set -euo pipefail
SLUG="${1:-}"
PROMPT_HINT="${2:-}"   # optional, e.g. "risk review", "next steps"
if [ -z "$SLUG" ]; then
  echo "Usage: ask_codex.sh <capsule-slug> [prompt-hint]" >&2
  exit 2
fi

# Refresh Huxley context bundle (non-fatal if composer missing)
_CATALYST_ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
python3 "$_CATALYST_ROOT/tools/compose_codex_context.py" >/dev/null 2>&1 || true
CTX="$HOME/.codex/context/builder_context.md"

CAP="$_CATALYST_ROOT/capsules/$SLUG"
if [ ! -d "$CAP" ]; then
  echo "Capsule not found: $CAP" >&2
  exit 3
fi

STAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
OUTDIR="$_CATALYST_ROOT/registry/advice/codex/$SLUG"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/${STAMP}.md"

# Build a compact prompt: context header + capsule spec pointers
PROMPT_FILE="$(mktemp)"
{
  echo "You are an advisor for the Huxley system."
  echo "Read the capsule's spec files and provide concise, actionable advice."
  echo "Keep it under 300 words. No code. Focus on risks, validation checks, and next steps."
  if [ -n "$PROMPT_HINT" ]; then
    echo "Focus area: $PROMPT_HINT"
  fi
  echo ""
  echo "Capsule: $CAP"
  echo "If present, consider:"
  echo " - spec/requirements.yaml"
  echo " - spec/system.md"
  echo " - spec/test_plan.md"
  echo " - spec/market_validation.md"
  echo " - spec/context.jsonl"
  echo " - capsule.json (lane)"
} > "$PROMPT_FILE"

# Invoke Codex CLI with correct syntax
# Based on test results: codex-aarch64-apple-darwin --model <MODEL> --profile <CONFIG_PROFILE> <PROMPT>
{
  echo "# Codex Advice — $SLUG ($STAMP)"
  echo ""
  echo "## Prompt"
  cat "$PROMPT_FILE"
  echo ""
  echo "## Context Path"
  echo "$CTX"
  echo ""
  echo "## Advice"
  echo '```'
  # Use the prompt content directly as argument, not as file
  PROMPT_TEXT=$(cat "$PROMPT_FILE")
  codex --model gpt-4 --profile default "$PROMPT_TEXT" 2>&1 || echo "(codex invocation failed)"
  echo '```'
} > "$OUT"

rm -f "$PROMPT_FILE"
echo "Saved Codex advice: $OUT"

exit 0