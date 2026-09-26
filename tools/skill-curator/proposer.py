#!/usr/bin/env python3
"""Skill Proposer — Phase 2 of the Hermes cherry-pick.

Runs at session end (via tools/hooks/on_session_end.py). Reads the latest session
JSONL, applies a heuristic gate, and — if the session looks skill-worthy — calls
Gemini 2.0 Flash to draft a candidate SKILL.md into `.claude/skills/_proposed/`.

Strict review gate: drafts NEVER auto-promote. {{USER_NAME}} manually moves approved
proposals from `_proposed/` into `.claude/skills/<name>/`.

Usage:
    python3 proposer.py                          # process the most recent session
    python3 proposer.py --session-id <uuid>      # process a specific session
    python3 proposer.py --dry-run                # decide + log only; don't write
    python3 proposer.py --quiet                  # suppress stdout (hook-friendly)
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

# Allow running both as `python3 proposer.py` and as `python3 -m
# tools.skill_curator.proposer`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib.deduper import has_duplicate, session_hash
    from lib.extractor import parse_session_jsonl
    from lib.synthesizer import synthesize
    from lib.trigger import evaluate
else:
    from .lib.deduper import has_duplicate, session_hash
    from .lib.extractor import parse_session_jsonl
    from .lib.synthesizer import synthesize
    from .lib.trigger import evaluate

# ---- Path config -----------------------------------------------------------

CATALYST_ROOT = Path(
    os.environ.get(
        "CATALYST_ROOT", str(Path(__file__).resolve().parent.parent.parent)
    )
)
SESSIONS_DIR = Path(
    os.environ.get(
        "CLAUDE_CODE_SESSIONS_DIR",
        str(
            Path.home()
            / ".claude"
            / "projects"
            / "{{CLAUDE_PROJECT_SLUG}}"
        ),
    )
)
SKILLS_DIR = CATALYST_ROOT / ".claude" / "skills"
PROPOSED_DIR = SKILLS_DIR / "_proposed"
PROPOSALS_LOG = SESSIONS_DIR / "memory" / "skill-proposals.log"
PROPOSER_LOG_DIR = CATALYST_ROOT / "logs" / "skill-curator"
PROPOSER_VERSION = "1.0"

PROPOSER_TIMEOUT_SEC = 30  # Hard cap; Gemini call has its own 30s timeout

# ---- Helpers ---------------------------------------------------------------


def find_latest_session() -> Path | None:
    """Return path to the most recently modified session JSONL, or None."""
    if not SESSIONS_DIR.exists():
        return None
    candidates = list(SESSIONS_DIR.glob("*.jsonl"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def find_session_by_id(session_id: str) -> Path | None:
    p = SESSIONS_DIR / f"{session_id}.jsonl"
    return p if p.exists() else None


SLUG_RE = re.compile(r"name:\s*([A-Za-z0-9_-]+)")


def slug_from_skill_md(skill_md: str) -> str:
    """Pull `name:` out of the frontmatter; fall back to a timestamp slug."""
    parts = skill_md.split("---", 2)
    if len(parts) >= 3:
        m = SLUG_RE.search(parts[1])
        if m:
            return m.group(1).strip().lower()
    return f"proposed-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"


def description_from_skill_md(skill_md: str) -> str:
    """Pull `description:` (single-line) out of frontmatter for the log entry."""
    parts = skill_md.split("---", 2)
    if len(parts) < 3:
        return "(no description)"
    for line in parts[1].splitlines():
        line = line.strip()
        if line.startswith("description:"):
            desc = line.split(":", 1)[1].strip()
            # Strip surrounding quotes if any
            if (desc.startswith('"') and desc.endswith('"')) or (
                desc.startswith("'") and desc.endswith("'")
            ):
                desc = desc[1:-1]
            return desc[:200]
    return "(no description)"


def append_proposal_log(slug: str, description: str) -> None:
    """One-line summary so {{ORCHESTRATOR_NAME}} can mention pending proposals at session start."""
    PROPOSALS_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"{ts} | {slug} | {description}\n"
    try:
        with open(PROPOSALS_LOG, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass  # Best-effort


def write_proposal_internal_log(record: dict) -> None:
    """Verbose internal log — every run, success or skip — for debugging."""
    PROPOSER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = PROPOSER_LOG_DIR / "proposer.log"
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    parts = [f"[{ts}]"]
    parts.append(f"session={record.get('session_id', '?')[:8]}")
    parts.append(f"action={record.get('action', '?')}")
    if "reason" in record:
        parts.append(f"reason={record['reason']}")
    if "tool_calls" in record:
        parts.append(f"tools={record['tool_calls']}")
    if "hash" in record:
        parts.append(f"hash={record['hash']}")
    if "input_tokens" in record:
        parts.append(f"in_tok={record['input_tokens']}")
    if "output_tokens" in record:
        parts.append(f"out_tok={record['output_tokens']}")
    line = " ".join(parts) + "\n"
    try:
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


def unique_slug(slug: str) -> str:
    """If `_proposed/<slug>/` already exists, append a numeric suffix."""
    base = PROPOSED_DIR / slug
    if not base.exists():
        return slug
    n = 2
    while (PROPOSED_DIR / f"{slug}-{n}").exists():
        n += 1
    return f"{slug}-{n}"


# ---- Main flow -------------------------------------------------------------


def run(session_path: Path, dry_run: bool, quiet: bool) -> int:
    def say(msg: str) -> None:
        if not quiet:
            print(msg)

    summary = parse_session_jsonl(session_path)
    say(
        f"[proposer] session={summary.session_id[:8]} "
        f"tools={summary.tool_call_count} "
        f"distinct={len(summary.distinct_tool_types)}"
    )

    # Gate 1+2+3: heuristic
    decision = evaluate(summary)
    if not decision.propose:
        for r in decision.reasons:
            say(f"  - {r}")
        say("[proposer] skip (heuristic gate)")
        write_proposal_internal_log(
            {
                "session_id": summary.session_id,
                "action": "skip-heuristic",
                "reason": ";".join(decision.reasons)[:200],
                "tool_calls": summary.tool_call_count,
            }
        )
        return 0

    # Gate 4: dedupe
    is_dup, h = has_duplicate(summary, SKILLS_DIR, PROPOSED_DIR)
    if is_dup:
        say(f"[proposer] skip (dedupe — hash {h} matches existing)")
        write_proposal_internal_log(
            {
                "session_id": summary.session_id,
                "action": "skip-dedupe",
                "hash": h,
                "tool_calls": summary.tool_call_count,
            }
        )
        return 0

    if dry_run:
        say(f"[proposer] DRY RUN — would propose. hash={h}")
        for r in decision.reasons:
            say(f"  - {r}")
        write_proposal_internal_log(
            {
                "session_id": summary.session_id,
                "action": "dry-run-would-propose",
                "hash": h,
                "tool_calls": summary.tool_call_count,
            }
        )
        return 0

    # Synthesize
    proposed_at = datetime.datetime.now().isoformat(timespec="seconds")
    outcome = (
        "explicit-positive"
        if any("explicit positive" in r for r in decision.reasons)
        else "clean-exit"
    )
    say("[proposer] calling Gemini 2.0 Flash...")
    result = synthesize(summary, proposed_at, outcome)
    if not result.ok:
        say(f"[proposer] synthesis failed: {result.error}")
        write_proposal_internal_log(
            {
                "session_id": summary.session_id,
                "action": "synth-error",
                "reason": result.error[:200],
                "tool_calls": summary.tool_call_count,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }
        )
        return 1
    if result.skipped:
        say("[proposer] Gemini judged: not reusable. Skipping.")
        write_proposal_internal_log(
            {
                "session_id": summary.session_id,
                "action": "skip-gemini-not-reusable",
                "tool_calls": summary.tool_call_count,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }
        )
        return 0

    # Write the proposal
    slug = slug_from_skill_md(result.skill_md)
    slug = unique_slug(slug)
    out_dir = PROPOSED_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "SKILL.md"
    out_path.write_text(result.skill_md, encoding="utf-8")

    description = description_from_skill_md(result.skill_md)
    append_proposal_log(slug, description)
    write_proposal_internal_log(
        {
            "session_id": summary.session_id,
            "action": "proposed",
            "hash": h,
            "tool_calls": summary.tool_call_count,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
    )
    say(f"[proposer] WROTE proposal: {out_path}")
    say(f"[proposer]   in_tok={result.input_tokens} out_tok={result.output_tokens}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Huxley skill proposer")
    parser.add_argument(
        "--session-id",
        help="Process a specific session JSONL (default: most recent)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Decide + log without calling Gemini or writing files",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout (hook-friendly)",
    )
    args = parser.parse_args(argv)

    if args.session_id:
        session_path = find_session_by_id(args.session_id)
        if session_path is None:
            print(
                f"[proposer] session {args.session_id} not found in {SESSIONS_DIR}",
                file=sys.stderr,
            )
            return 1
    else:
        session_path = find_latest_session()
        if session_path is None:
            print("[proposer] no session JSONL files found", file=sys.stderr)
            return 0  # Not an error — just nothing to do

    return run(session_path, dry_run=args.dry_run, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
