# Skill Curator

Two distinct pipelines live in this package:

- **Proposer** (`proposer.py`) — Phase 2. Watches Claude Code session
  trajectories and drafts candidate skills into `.claude/skills/_proposed/`.
  Manual review gate.
- **Curator** (`curator.py`) — Phase 4. Weekly maintenance pass over skills
  tagged `metadata.curated: true`. Scores staleness, quality, and pairwise
  redundancy; runs a 5-branch decision tree; archives, merges, or proposes
  improvements. **Never deletes.**

## What it does

At session end (via `tools/hooks/on_session_end.py`), the proposer reads the
session's JSONL transcript, applies a heuristic gate, and — if the session
looks worth saving — calls Gemini 2.0 Flash Exp to draft a candidate
`SKILL.md`. The draft lands in:

    .claude/skills/_proposed/<slug>/SKILL.md

**Drafts NEVER auto-promote.** {{USER_NAME}} approves manually (see "Approving a
proposal" below).

## The trigger heuristic

A session triggers a proposal only if **all four** hold:

1. **Volume:** ≥ 8 tool calls
2. **Diversity:** ≥ 3 distinct tool types
3. **Success signal:** *either*
   - explicit positive keyword in the last user message
     (`ship it`, `perfect`, `done`, `thanks`, `looks good`, etc.) — checked
     with word-boundary matching so `yes` doesn't match inside `eyes`, **or**
   - clean exit + no error markers (`<tool_use_error>`, `Traceback`,
     `Exception:`, "this failed", etc.) in the last 3 assistant turns
4. **Dedupe:** hash of the top-5 tools (sorted) doesn't match an existing
   skill in `.claude/skills/` AND doesn't match an existing draft in
   `.claude/skills/_proposed/`

If any check fails, the proposer exits silently — no log spam, no error.
Verbose decisions land in `logs/skill-curator/proposer.log`.

## How approval works (the manual gate)

1. **{{ORCHESTRATOR_NAME}} mentions pending proposals** at session start using the proposals log:
   `~/.claude/projects/{{CLAUDE_PROJECT_SLUG}}/memory/skill-proposals.log`
2. **Inspect the draft:**
   ```bash
   ls .claude/skills/_proposed/
   cat .claude/skills/_proposed/<slug>/SKILL.md
   ```
3. **To approve a proposal:**
   ```bash
   mv .claude/skills/_proposed/<slug> .claude/skills/<slug>
   ```
   That's it — the file moves into the live skills directory and {{ORCHESTRATOR_NAME}} loads it
   on the next session.
4. **To reject a proposal:**
   ```bash
   rm -rf .claude/skills/_proposed/<slug>
   ```
5. **To edit before approving:** open `_proposed/<slug>/SKILL.md`, edit it
   freely, then `mv` to `.claude/skills/<slug>`.

## Inspecting the proposal log

Two log surfaces exist:

- **User-facing summary log** (one line per proposal — {{ORCHESTRATOR_NAME}} reads this at
  session start):
  ```
  ~/.claude/projects/{{CLAUDE_PROJECT_SLUG}}/memory/skill-proposals.log
  ```
  Format: `<timestamp> | <slug> | <description>`
- **Internal verbose log** (every run, success or skip — for debugging):
  ```
  logs/skill-curator/proposer.log
  ```

There are also `logs/skill-curator/proposer.stdout.log` and
`proposer.stderr.log` capturing detached subprocess output from the hook.

## Disabling the proposer

Three options in escalating order:

1. **Temporary (skip a single session):**
   ```bash
   rm tools/skill-curator/proposer.py.disabled  # if it exists
   touch tools/skill-curator/.disabled          # not implemented; see code
   ```
   *Not yet implemented* — if needed, add a check at the top of `proposer.py`.
2. **Disable the hook integration:** open
   `tools/hooks/on_session_end.py` and comment out the
   `fire_skill_proposer(session_id, catalyst_root)` line.
3. **Block the proposer entirely:** rename `tools/skill-curator/proposer.py`
   to `proposer.py.disabled`. The hook checks for existence and exits
   silently if it's missing.

## Editing the synthesizer prompt

The Gemini prompt template lives in
`tools/skill-curator/prompts/proposer.md`. Edit it directly — no code
changes needed. Variables filled in by `lib/synthesizer.py`:

- `{{PROPOSED_AT}}` — ISO timestamp
- `{{SOURCE_SESSION}}` — UUID of the session
- `{{FINAL_USER_MESSAGE}}` — last user turn (capped at 1000 chars)
- `{{TOOL_SEQUENCE}}` — numbered list of tool calls (cap 40)
- `{{OUTCOME_SIGNAL}}` — `explicit-positive` or `clean-exit`

## Running it manually

```bash
# Latest session
python3 tools/skill-curator/proposer.py

# Specific session
python3 tools/skill-curator/proposer.py --session-id <uuid>

# Decide + log only, don't write anything
python3 tools/skill-curator/proposer.py --dry-run
```

## Tests

```bash
python3 tools/skill-curator/tests/test_trigger.py -v
python3 tools/skill-curator/tests/test_deduper.py -v
```

Fixtures live in `tests/fixtures/`:
- `should_propose.jsonl` — passes all gates
- `should_skip_low_volume.jsonl` — < 8 tool calls
- `should_skip_low_diversity.jsonl` — only 1 distinct tool
- `should_skip_error_exit.jsonl` — error markers in last assistant turns

## Cost per proposal

Gemini 2.0 Flash Exp pricing (check current pricing):
- Input: ~$0.075 per 1M tokens
- Output: ~$0.30 per 1M tokens

Typical proposal:
- Prompt template + tool sequence + final user msg ≈ 2-4K input tokens
- Drafted SKILL.md ≈ 400-800 output tokens

→ **~$0.0003-0.0005 per proposal.** With the heuristic gate, expect ≤ 1
proposal per qualifying session, so monthly cost is well under $1 even
with heavy use.

## Files

```
tools/skill-curator/
├── README.md                    # this file
├── proposer.py                  # main entry point
├── lib/
│   ├── __init__.py
│   ├── extractor.py             # JSONL → SessionSummary
│   ├── trigger.py               # heuristic gate
│   ├── synthesizer.py           # Gemini call + validation
│   └── deduper.py               # hash-based dedupe
├── prompts/
│   └── proposer.md              # editable Gemini prompt template
└── tests/
    ├── __init__.py
    ├── fixtures/                # JSONL fixtures for unit tests
    ├── test_trigger.py
    └── test_deduper.py
```

Hook integration: `tools/hooks/on_session_end.py` (see
`fire_skill_proposer()`).

## Out of scope (still — even after Phase 4)

- Auto-promotion of approved drafts (intentionally manual)
- Auto-applying IMPROVE proposals — {{USER_NAME}} manually applies them
- Cross-capsule namespacing (deferred)
- Retroactively tagging the skills already in the tree as `metadata.curated: true`

---

# Phase 4 — Skill Maintenance Curator

The curator runs weekly (LaunchAgent: `com.huxley.skill-curator-weekly`,
Mondays 4 AM) and reviews skills tagged `metadata.curated: true`. It does
**not** touch hand-built skills (anything without that frontmatter flag) or
pinned skills (`metadata.pinned: true`).

## Algorithm

The scoring algorithm:

1. **Staleness `S(s) ∈ [0,1]`** — exponential decay with adaptive half-life.
   Heavily-used skills age faster; never-hot skills age slower.
2. **Quality `Q(s) ∈ [0,1]`** — Laplace-smoothed pos/(pos+neg) over 180-day
   feedback. Cold-start (n<3) returns neutral 0.5.
3. **Redundancy `R(a,b) ∈ [0,1]`** — `0.30·J + 0.50·C + 0.20·D` where:
   - J = Jaccard on top-5 tools (reuses Phase 2 deduper)
   - C = TF-IDF cosine on body (IDF over ALL skills for stable corpus)
   - D = Jaccard on description tokens
4. **5-branch decision tree:** pinned → KEEP. In merge cluster (R≥0.75) →
   MERGE-WITH-leader. S≥0.7 + 0 invocations in 90d → ARCHIVE. Q≤0.3 +
   n_neg≥5 → IMPROVE. Else → KEEP.

## Modes

**Dry-run (default for the first 30 days after you first enable the curator):**
- Generates `.claude/skills/.curator/reports/{YYYY-MM-DD}-dryrun.md`
- Posts a one-line digest to Telegram via Telegram bot
- NO mutations. Report includes the full sorted similarity matrix so {{USER_NAME}}
  can tune the 0.75 merge threshold.

**Live mode** (requires `CATALYST_CURATOR_LIVE=1` AND grace period elapsed):
- ARCHIVE → moves dir to `.claude/skills/.archive/<YYYY-MM-DD-HHMM>/<name>/`
- MERGE → archives loser, annotates leader's frontmatter with `<!-- merged-from -->`
- IMPROVE → calls Gemini with the editable prompt, writes
  `.claude/skills/<name>/_improve_proposal.md`. {{USER_NAME}} manually applies.

## Inactivity Gate

Refuses to run if:
- Newest `.jsonl` in `~/.claude/projects/{{CLAUDE_PROJECT_SLUG}}/`
  is < 2 hours old, OR
- Any `.jsonl` was modified in the last 30 minutes.

## Hard Invariants (enforced in code)

- ❌ NEVER deletes a skill (no `os.remove`, `shutil.rmtree`, `Path.unlink`
  on skill dirs)
- ❌ NEVER touches `metadata.curated != true` skills
- ❌ NEVER touches `metadata.pinned == true` skills
- ❌ NEVER touches `_proposed/`, `_promoted/`, `.archive/`, or `.curator/`
  subtrees
- ❌ NEVER live-runs during the 30-day grace period (hard date check, not
  config-overridable)

Verify with: `python3 tools/skill-curator/tests/test_invariants.py -v`

## Restoration

```bash
python3 tools/skill-curator/restore.py --list                # list all archives
python3 tools/skill-curator/restore.py <skill-name>          # restore most recent
```

If a live skill with the same name exists, restore refuses — {{USER_NAME}} must
move/delete the live copy first.

## Editable Curator Prompt

The IMPROVE prompt lives at `.claude/skills/.curator/PROMPT.md`. The curator
reads it fresh on every run. Edit freely; no code change needed.

## State

- `.claude/skills/.curator/state.json` — `first_run_at`, `last_run_at`,
  `runs_count`, `paused`, `last_report_path` (gitignored — runtime state)
- `.claude/skills/.usage.json` — sidecar telemetry (counts + feedback +
  timestamps, gitignored)
- `.claude/skills/.curator/reports/` — dated reports (gitignored)
- `.claude/skills/.archive/` — archived skill snapshots (gitignored)
- `.claude/skills/.curator/restore.log` — restore audit trail (gitignored)

## Running it manually

```bash
# Dry-run, real skills dir, no Telegram
python3 tools/skill-curator/curator.py --dry-run --skip-telegram --force

# Live (after grace period), with env opt-in
CATALYST_CURATOR_LIVE=1 python3 tools/skill-curator/curator.py --skip-telegram

```

## Tests

```bash
python3 tools/skill-curator/tests/test_scorer.py -v       # 30 tests — S, Q, R formulas
python3 tools/skill-curator/tests/test_decider.py -v      # 12 tests — 5-branch tree
python3 tools/skill-curator/tests/test_inactivity.py -v   #  8 tests — idle gate
python3 tools/skill-curator/tests/test_invariants.py -v   # 14 tests — hard invariants
python3 tools/skill-curator/tests/test_integration.py -v  #  5 tests — end-to-end
```

## Cost per IMPROVE call

Gemini 2.0 Flash Exp pricing:
- Input: ~$0.075 / 1M tokens
- Output: ~$0.30 / 1M tokens

A typical IMPROVE call:
- Prompt template + skill body ≈ 2K input tokens
- Proposed rewrite ≈ 800 output tokens

→ **~$0.00039 per IMPROVE call**. With realistic curated-skill counts
(5–30) and IMPROVE rates (≤ 1 per skill per quarter), monthly Gemini spend
for the curator should be well under $0.10 even in steady state.
