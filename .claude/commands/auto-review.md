---
description: "Toggle automatic code review on/off"
---

Toggle the automatic end-of-turn code review hook. Check the current state and flip it.

The automatic reviewer is **Codex** (`codex-consult.sh --mode diff`), driven by the Stop
hook `review_stop_hook.py`. That hook gates on the flag file `.claude/auto-review-disabled`
inside the repo root — this command must write/remove THAT exact path, not a /tmp path.

There are **three** states, because the hook also stands down on its own when the
`codex` CLI isn't installed (it blocks nothing and injects nothing in that case):

| State | Meaning |
|---|---|
| 🟢 **ON** | Flag absent + `codex` on PATH → review runs after every code-touching turn |
| 🟡 **ON but dormant** | Flag absent, `codex` NOT on PATH → hook stands down, nothing runs |
| 🔴 **OFF** | Flag present → review disabled regardless of whether `codex` is installed |

## Instructions

1. Run the Bash block below. It flips the flag (`.claude/auto-review-disabled`) and
   then prints the resulting state as one token: `ON_ACTIVE`, `ON_DORMANT`, or `OFF`.
2. Report the result to {{USER_NAME}} using that token:
   - `ON_ACTIVE` → "🟢 Auto Codex review ON"
   - `ON_DORMANT` → "🟡 Auto Codex review ON but dormant — the `codex` CLI isn't
     installed, so nothing will run. Install it with `npm install -g @openai/codex`
     (then `codex login`) and it activates by itself."
   - `OFF` → "🔴 Auto Codex review OFF"
3. If {{USER_NAME}} asked only for the current state (not a toggle), run the same block with
   the two toggle lines removed so nothing is flipped, and report the same three ways.

```bash
FLAG="${CATALYST_ROOT:-{{CATALYST_ROOT}}}/.claude/auto-review-disabled"

# Toggle
if [ -f "$FLAG" ]; then rm -f "$FLAG"; else touch "$FLAG"; fi

# Report the resulting state (flag wins; then Codex availability)
if [ -f "$FLAG" ]; then
  echo "OFF"
elif command -v codex >/dev/null 2>&1; then
  echo "ON_ACTIVE"
else
  echo "ON_DORMANT"
fi
```

Report the result with the appropriate emoji. Nothing else needed.
