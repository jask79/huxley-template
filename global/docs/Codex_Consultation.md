# Codex Consultation Guide

**Purpose:** How {{ORCHESTRATOR_NAME}} uses Codex as a peer for second opinions, code review, and validation.

---

## What this is

A thin wrapper (`tools/codex-consult.sh`) around `codex exec` that adds:

1. Consistent prompt framing for common consultation modes
2. Per-invocation logging at `~/.cache/huxley/codex-consult/YYYY-MM-DD/`

Codex CLI v0.132+ already provides sandboxing, session resume, and structured review natively, so the wrapper is intentionally minimal. This replaces the older BridgeHub CLI tool, which is no longer used.

---

## When to use

{{USER_NAME}} triggers consultation with phrases like:

- "Discuss with Codex"
- "Ask Codex about..."
- "Get Codex's opinion on..."
- "Have Codex review this"

Codex is a peer, not an authority — use it to test thinking, surface blind spots, and pressure-test decisions. Seek consensus, don't take marching orders.

---

## Modes

| Mode | Purpose | Required args |
|---|---|---|
| `freeform` (default) | General question or discussion | message (args or stdin) |
| `review` | Peer review of a single file | `--file <path>` |
| `diff` | Peer review of staged (or unstaged) git diff | runs in a git repo |
| `spec` | Validate a YAML/JSON spec | `--file <path>` |

---

## Usage

```bash
# Free-form question with a topic slug (used in the log filename)
tools/codex-consult.sh --topic rag-vs-fts "Trade-offs between vector DB and full-text search for RAG?"

# Peer review of a file with extra context
tools/codex-consult.sh --mode review --file src/auth/login.ts "Focus on the password handling path"

# Review whatever is currently staged
git add src/auth/login.ts
tools/codex-consult.sh --mode diff "Is the rate-limit key correct?"

# Validate a spec
tools/codex-consult.sh --mode spec --file specs/current.yaml

# Pipe a long question via stdin
cat long-question.txt | tools/codex-consult.sh --topic architecture
```

---

## Logs

Each invocation writes a log file:

```
~/.cache/huxley/codex-consult/<YYYY-MM-DD>/<timestamp>-<topic>.log
```

Contents: timestamp, mode, file, cwd, full prompt, full Codex response. Use these to audit "what did we ask Codex about X" later.

---

## Constraints

- Codex CLI runs in its own sandbox (read-only filesystem, restricted network by default — verify with `codex doctor`).
- Default timeout is whatever `codex exec` enforces. For long inputs, break the question into smaller pieces.
- Auth uses ChatGPT login (`codex login`). If consultations start failing, re-run `codex doctor` and `codex login`.

---

## Notes

- The `tools/bridgehub/mcp_server/` directory on disk is an unrelated Python LLM-provider router. It is **not** the {{ORCHESTRATOR_NAME}}↔Codex bridge and is not used by this consultation flow.
- The older `BridgeHub_Protocol.md` (with JSON action payloads and `JARVIS_PAYLOAD` responses) is retired. Anything referencing it should be updated to use `tools/codex-consult.sh`.
