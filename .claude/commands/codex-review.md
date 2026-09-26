---
description: "Manual Codex peer review consultation on specific files or changes"
---

# Codex Peer Review Command

You are being invoked to facilitate a manual Codex peer review consultation.

## Task

The user wants Codex's perspective on specific code, a design decision, or to validate findings from the automatic Code Reviewer.

## Your Role

1. **Understand the request:**
   - What file(s) or code sections need review?
   - What specific concerns or questions does the user have?
   - Is this about architecture, implementation, or both?

2. **Pick the right mode:**
   - Single file review → `--mode review --file <path>`
   - Review of pending changes → `--mode diff`
   - Free-form design question → default (`freeform`)
   - Validate a spec → `--mode spec --file <path>`

3. **Invoke `codex-consult.sh`:**
   ```bash
   {{CATALYST_ROOT}}/tools/codex-consult.sh --mode review --file <path> "your specific concerns / what to focus on"
   ```
   Or for a free-form question:
   ```bash
   {{CATALYST_ROOT}}/tools/codex-consult.sh --topic <slug> "your question"
   ```
   Logs land in `~/.cache/huxley/codex-consult/YYYY-MM-DD/`.

4. **Synthesize perspectives:**
   - Present Codex's concerns and recommendations
   - Compare with Code Reviewer findings if available
   - Highlight areas of agreement and disagreement
   - Provide clear recommendations

## Example Usage

```bash
/codex-review path/to/file.py
```

This is the **manual, on-demand** version. Codex is ALSO the automatic end-of-turn
reviewer: whenever a turn modifies code files, the Stop hook (`review_stop_hook.py`)
runs `codex-consult.sh --mode diff` automatically and auto-fixes Major/Minor findings.
Use this `/codex-review` command for targeted, mid-session reviews of a specific file
or design question. Toggle the automatic flow with `/auto-review`.

## When to Use

- Complex architectural decisions
- Critical code sections needing extra scrutiny
- Second opinion when Code Reviewer flags concerns
- Learning opportunity to understand different approaches
- Consensus building between AI perspectives

Proceed with facilitating the Codex consultation based on the user's request.
