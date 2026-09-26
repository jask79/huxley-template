#!/usr/bin/env bash
set -euo pipefail
SLUG="${1:-unspecified}"
STAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
_CATALYST_ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
OUT="$_CATALYST_ROOT/registry/consensus/$SLUG/$STAMP"
mkdir -p "$OUT"

# Prompt files (you can tweak prompts later)
CLAUDE_PROMPT="$OUT/claude_prompt.txt"
CODEX_PROMPT="$OUT/codex_prompt.txt"
REPORT="$OUT/consensus_report.md"

cat >"$CLAUDE_PROMPT" <<'EOF'
You are the Claude Code advisor for the Huxley system. Read the capsule spec and propose risks, validation checks, and concrete next steps (no code), referencing the Two-Lane model and DoD. Keep it under 300 words.
EOF

cat >"$CODEX_PROMPT" <<'EOF'
You are the Codex advisor for the Huxley system. Read the capsule spec and propose risks, validation checks, and concrete next steps (no code). Keep it under 300 words.
EOF

echo "# Consensus Session" > "$REPORT"
echo "- slug: $SLUG" >> "$REPORT"
echo "- when: $STAMP" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Inputs" >> "$REPORT"
echo "- Capsule: $_CATALYST_ROOT/capsules/$SLUG" >> "$REPORT"
echo "- Compass: $_CATALYST_ROOT/PROJECT_COMPASS_Huxley.md" >> "$REPORT"
echo "" >> "$REPORT"

# 1) Ask Claude (bridge assumed available; adapt to your invoke)
# Save Claude advice
CLAUDE_OUT="$OUT/claude_advice.md"
echo "### Claude Advice" >> "$REPORT"
echo '```' >> "$REPORT"
# Replace with your actual Claude invocation; here we just cat a placeholder
# claude --advisor --capsule "$_CATALYST_ROOT/capsules/$SLUG" --prompt "$CLAUDE_PROMPT" > "$CLAUDE_OUT"
echo "(hook your Claude advisor invocation here)" > "$CLAUDE_OUT"
cat "$CLAUDE_OUT" >> "$REPORT"
echo '```' >> "$REPORT"
echo "" >> "$REPORT"

# 2) Ask Codex (via wrapper to include context)
CODEX_OUT="$OUT/codex_advice.md"
echo "### Codex Advice" >> "$REPORT"
echo '```' >> "$REPORT"
# Example; replace with your codex CLI invocation:
# $_CATALYST_ROOT/tools/codex_builder.sh chat --model gpt-5 --file "$HOME/.codex/context/builder_context.md" --prompt-file "$CODEX_PROMPT" > "$CODEX_OUT"
echo "(hook your Codex advisor invocation here)" > "$CODEX_OUT"
cat "$CODEX_OUT" >> "$REPORT"
echo '```' >> "$REPORT"

# 3) Diff & consensus skeleton
echo "" >> "$REPORT"
echo "## Consensus Skeleton" >> "$REPORT"
echo "- Agreements: (summarize overlapping risks/next steps)" >> "$REPORT"
echo "- Divergences: (list where they disagree)" >> "$REPORT"
echo "- Proposed Next Step: (pick the safer/smaller step)" >> "$REPORT"
echo "- Lane/DoD Impact: (any adjustments needed)" >> "$REPORT"

echo "Wrote $REPORT"
echo "Open it in your editor to finalize the consensus before execution."