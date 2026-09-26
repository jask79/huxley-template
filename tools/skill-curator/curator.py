#!/usr/bin/env python3
"""Skill Curator — Phase 4 of the Hermes cherry-pick.

Weekly maintenance pass over `metadata.curated: true` skills. Scores each
skill (staleness, quality, redundancy), runs the 5-branch decision tree,
generates a dated report, and (in live mode, after the 30-day grace period)
applies ARCHIVE / MERGE / IMPROVE actions.

Hard invariants (enforced in code; see _assert_invariants):
  - NEVER deletes anything.
  - NEVER touches a skill where metadata.curated != true.
  - NEVER touches a skill where metadata.pinned == true.
  - NEVER touches the `_proposed/` or `_promoted/` subtrees.
  - NEVER live-runs before 30 days from initial deploy (hard date check).

Usage:
    python3 curator.py                  # run with current mode (dry/live)
    python3 curator.py --dry-run        # force dry-run (default before grace)
    python3 curator.py --force           # bypass inactivity gate (testing)
    python3 curator.py --skip-telegram   # skip Telegram notification
    python3 curator.py --skills-dir PATH # override skills location

Environment:
    CATALYST_CURATOR_LIVE=1   — opt into live mode (still gated by 30-day grace)
    CATALYST_ROOT             — override repo root
    CATALYST_CURATOR_GRACE_DAYS  — override 30-day grace (testing only)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime as dt, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow `python3 curator.py` and `python3 -m tools.skill_curator.curator`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib.decider import (
        ACTION_ARCHIVE,
        ACTION_IMPROVE,
        ACTION_KEEP,
        ACTION_MERGE,
        Decision,
        SimilarityPair,
        decide_all,
    )
    from lib.inactivity import is_safe_to_run
    from lib.scorer import (
        SkillRecord,
        compute_idf,
        extract_top_tools,
        tokenize_body,
        tokenize_description,
    )
    from lib.usage import (
        empty_record,
        get_record,
        is_curated,
        is_pinned,
        load_usage,
        parse_frontmatter,
        save_usage,
    )
else:
    from .lib.decider import (
        ACTION_ARCHIVE,
        ACTION_IMPROVE,
        ACTION_KEEP,
        ACTION_MERGE,
        Decision,
        SimilarityPair,
        decide_all,
    )
    from .lib.inactivity import is_safe_to_run
    from .lib.scorer import (
        SkillRecord,
        compute_idf,
        extract_top_tools,
        tokenize_body,
        tokenize_description,
    )
    from .lib.usage import (
        empty_record,
        get_record,
        is_curated,
        is_pinned,
        load_usage,
        parse_frontmatter,
        save_usage,
    )


# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

CATALYST_ROOT = Path(
    os.environ.get(
        "CATALYST_ROOT", str(Path(__file__).resolve().parent.parent.parent)
    )
)
SKILLS_DIR = CATALYST_ROOT / ".claude" / "skills"
ARCHIVE_DIR = SKILLS_DIR / ".archive"
CURATOR_DIR = SKILLS_DIR / ".curator"
REPORTS_DIR = CURATOR_DIR / "reports"
PROMPT_PATH = CURATOR_DIR / "PROMPT.md"
STATE_FILE = CURATOR_DIR / "state.json"
RESTORE_LOG = CURATOR_DIR / "restore.log"

SESSION_DIR = Path(
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

GRACE_DAYS_DEFAULT = 30
TELEGRAM_KEYCHAIN_SERVICE = "telegram-bot-token"
TELEGRAM_KEYCHAIN_ACCOUNT = "huxley"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

EXCLUDED_TOPLEVEL = {
    "_proposed",   # owned by Phase 2
    "_promoted",   # reserved for future
    ".archive",    # archive root, never recurses for curation
    ".curator",    # curator's own dir
    "node_modules",
    "__pycache__",
}


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------


def _now_utc() -> dt:
    return dt.now(timezone.utc)


def _default_state() -> Dict[str, Any]:
    return {
        "first_run_at": None,
        "last_run_at": None,
        "last_report_path": None,
        "runs_count": 0,
        "paused": False,
    }


def load_state(state_file: Path) -> Dict[str, Any]:
    if not state_file.exists():
        return _default_state()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_state()
    if not isinstance(data, dict):
        return _default_state()
    base = _default_state()
    base.update({k: v for k, v in data.items() if k in base})
    return base


def save_state(state_file: Path, state: Dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(state_file.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, state_file)


def grace_days() -> int:
    raw = os.environ.get("CATALYST_CURATOR_GRACE_DAYS")
    if raw is None:
        return GRACE_DAYS_DEFAULT
    try:
        return max(0, int(raw))
    except ValueError:
        return GRACE_DAYS_DEFAULT


def is_within_grace_period(state: Dict[str, Any], now: dt) -> bool:
    """True if first_run_at + grace_days has not yet elapsed."""
    raw = state.get("first_run_at")
    if not raw:
        return True  # never run before — definitely in grace
    try:
        first_run = dt.fromisoformat(str(raw))
        if first_run.tzinfo is None:
            first_run = first_run.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True
    elapsed = now - first_run
    return elapsed < timedelta(days=grace_days())


def determine_mode(
    state: Dict[str, Any], cli_dry_run: bool, env_live: bool, now: dt
) -> Tuple[str, str]:
    """Return (mode, reason). mode ∈ {'dry-run', 'live'}."""
    if cli_dry_run:
        return "dry-run", "explicit --dry-run flag"
    if is_within_grace_period(state, now):
        return "dry-run", (
            f"grace period active (first run was {state.get('first_run_at')}; "
            f"need ≥ {grace_days()} days of dry runs before live)"
        )
    if not env_live:
        return "dry-run", (
            "CATALYST_CURATOR_LIVE not set — live mode requires explicit opt-in "
            "even after grace period"
        )
    return "live", "grace period passed and CATALYST_CURATOR_LIVE=1"


# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------


def discover_skills(skills_dir: Path) -> List[Tuple[Path, str]]:
    """Walk skills_dir and return (skill_md_path, skill_name) for every skill.

    Excludes top-level dirs in EXCLUDED_TOPLEVEL. Does NOT filter on `curated`
    yet — caller does that. Returns the FULL set so the IDF corpus is stable.
    """
    if not skills_dir.exists():
        return []
    out: List[Tuple[Path, str]] = []
    for entry in skills_dir.iterdir():
        if not entry.is_dir() or entry.name in EXCLUDED_TOPLEVEL:
            continue
        for candidate in ("SKILL.md", "skill.md"):
            skill_md = entry / candidate
            if skill_md.exists():
                out.append((skill_md, entry.name))
                break
    return out


def load_skill_record(
    skill_md_path: Path, skill_name: str, usage_map: Dict[str, Any]
) -> Optional[SkillRecord]:
    """Read a SKILL.md, parse frontmatter, build a SkillRecord. None on read error."""
    try:
        body_text = skill_md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fm = parse_frontmatter(body_text)
    # Use frontmatter `name:` if set, otherwise dir name
    name = str(fm.get("name") or skill_name)
    record = SkillRecord(
        name=name,
        path=skill_md_path,
        body_text=body_text,
        frontmatter=fm,
        usage_record=get_record(usage_map, name),
    )
    record.top_tools = extract_top_tools(body_text)
    record.body_tokens = tokenize_body(body_text)
    record.desc_tokens = tokenize_description(str(fm.get("description") or ""))
    return record


# ---------------------------------------------------------------------------
# Invariant assertions — fail loud if broken
# ---------------------------------------------------------------------------


def _assert_invariants(decisions: List[Decision], curated_records: List[SkillRecord]) -> None:
    """Hard checks before we apply any mutation. Raises AssertionError."""
    curated_names = {r.name for r in curated_records}
    pinned_names = {
        r.name for r in curated_records if is_pinned(r.frontmatter)
    }
    non_curated_names = {
        r.name for r in curated_records if not is_curated(r.frontmatter)
    }

    for d in decisions:
        # Every decision must correspond to an input record
        assert d.skill_name in curated_names, (
            f"INVARIANT VIOLATED: decision for unknown skill '{d.skill_name}'"
        )
        # Pinned skills MUST always be KEEP
        if d.skill_name in pinned_names and d.action != ACTION_KEEP:
            raise AssertionError(
                f"INVARIANT VIOLATED: pinned skill '{d.skill_name}' got action={d.action}"
            )
        # Non-curated skills (defensive: should not be in input) MUST be KEEP
        if d.skill_name in non_curated_names and d.action != ACTION_KEEP:
            raise AssertionError(
                f"INVARIANT VIOLATED: non-curated '{d.skill_name}' got action={d.action}"
            )


# ---------------------------------------------------------------------------
# Mutation primitives — only called in live mode
# ---------------------------------------------------------------------------


def _live_run_allowed(state: Dict[str, Any], now: dt) -> bool:
    """Hard date check — even with env opt-in, we refuse to mutate during grace."""
    return not is_within_grace_period(state, now)


def archive_skill(
    record: SkillRecord, decision: Decision, archive_root: Path, now: dt
) -> Tuple[bool, str, Optional[Path]]:
    """Move skill dir to .archive/<YYYY-MM-DD-HHMM>/<skill-name>/. Reversible."""
    # Defensive guards
    if not is_curated(record.frontmatter):
        return False, "refused: not curated", None
    if is_pinned(record.frontmatter):
        return False, "refused: pinned", None

    skill_dir = record.path.parent
    if not skill_dir.exists():
        return False, "skill dir gone", None

    timestamp = now.strftime("%Y-%m-%d-%H%M")
    dest_root = archive_root / timestamp
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / skill_dir.name

    # Defensive: dest collision (same minute = unlikely but possible)
    suffix = 2
    final_dest = dest
    while final_dest.exists():
        final_dest = dest_root / f"{skill_dir.name}-{suffix}"
        suffix += 1

    try:
        shutil.move(str(skill_dir), str(final_dest))
    except OSError as e:
        return False, f"move failed: {e}", None

    # Write a manifest into the archived dir
    manifest = {
        "action": "ARCHIVE",
        "skill_name": record.name,
        "original_path": str(skill_dir),
        "archived_at": now.isoformat(),
        "decision": {
            "rationale": decision.rationale,
            "s_score": decision.s_score,
            "q_score": decision.q_score,
            "invocations_90d": decision.invocations_90d,
            "confidence": decision.confidence,
        },
    }
    try:
        (final_dest / "_archive_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    except OSError:
        pass

    return True, f"archived to {final_dest}", final_dest


def merge_skill(
    loser: SkillRecord,
    leader: SkillRecord,
    decision: Decision,
    archive_root: Path,
    now: dt,
) -> Tuple[bool, str, Optional[Path]]:
    """MERGE = archive the loser AND append a `<!-- merged-from -->` HTML comment
    to the leader's frontmatter section so future loads can trace lineage.

    Defensive: never modifies the leader's body, only adds a comment line
    immediately after the closing `---` of the frontmatter.
    """
    if is_pinned(leader.frontmatter):
        return False, "refused: leader is pinned (cannot annotate)", None

    # Step 1: archive the loser
    ok, msg, archived_to = archive_skill(loser, decision, archive_root, now)
    if not ok:
        return False, f"archive of loser failed: {msg}", None

    # Step 2: append merged-from comment to the leader
    comment = (
        f"<!-- merged-from: {loser.name} (R={decision.r_to_leader:.3f} "
        f"on {now.strftime('%Y-%m-%d')}) -->"
    )
    try:
        text = leader.path.read_text(encoding="utf-8")
        # Insert after closing ---. Idempotent: skip if already present.
        if comment not in text:
            parts = text.split("---", 2)
            if len(parts) >= 3:
                # parts[0] = "" (before first ---), parts[1] = frontmatter, parts[2] = body
                new_text = (
                    parts[0]
                    + "---"
                    + parts[1]
                    + "---\n"
                    + comment
                    + "\n"
                    + parts[2].lstrip("\n")
                )
                leader.path.write_text(new_text, encoding="utf-8")
    except OSError as e:
        # Loser is already archived; we can't roll back, but we did the safe
        # half. Report the partial state.
        return True, f"loser archived to {archived_to}; leader annotation failed: {e}", archived_to

    return True, f"loser archived to {archived_to}; leader annotated", archived_to


def call_gemini_improve(
    record: SkillRecord, decision: Decision, prompt_template: str
) -> Tuple[bool, str, int, int]:
    """Call Gemini with the IMPROVE prompt. Returns (ok, output, in_tok, out_tok)."""
    try:
        api_key = subprocess.check_output(
            [
                "security",
                "find-generic-password",
                "-s",
                "gemini-api",
                "-a",
                "huxley",
                "-w",
            ],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return False, f"gemini-api keychain read failed: {e}", 0, 0

    rel_path = str(record.path.relative_to(CATALYST_ROOT)) if CATALYST_ROOT in record.path.parents else str(record.path)
    prompt = (
        prompt_template.replace("{{SKILL_NAME}}", record.name)
        .replace("{{SKILL_PATH}}", rel_path)
        .replace("{{S_SCORE}}", f"{decision.s_score:.3f}")
        .replace("{{Q_SCORE}}", f"{decision.q_score:.3f}")
        .replace("{{N_POS}}", str(decision.n_pos))
        .replace("{{N_NEG}}", str(decision.n_neg))
        .replace("{{INVOCATIONS}}", str(record.usage_record.get("use_count", 0)))
        .replace("{{SKILL_BODY}}", record.body_text)
    )

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash-exp:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return False, f"gemini http error: {e}", 0, 0
    except json.JSONDecodeError as e:
        return False, f"gemini bad json: {e}", 0, 0

    candidates = data.get("candidates", [])
    if not candidates:
        return False, "gemini returned no candidates", 0, 0
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    usage = data.get("usageMetadata", {})
    in_tok = int(usage.get("promptTokenCount", 0))
    out_tok = int(usage.get("candidatesTokenCount", 0))
    return True, text, in_tok, out_tok


def write_improve_proposal(
    record: SkillRecord, proposal_text: str, now: dt
) -> Tuple[bool, str]:
    """Write Gemini's proposed rewrite to `_improve_proposal.md` next to the live SKILL.md.

    {{USER_NAME}} manually applies (or discards) — curator never overwrites SKILL.md itself.
    """
    target = record.path.parent / "_improve_proposal.md"
    header = (
        f"<!-- IMPROVE proposal generated {now.isoformat()} by skill curator. "
        f"Apply manually by replacing {record.path.name}. -->\n\n"
    )
    try:
        target.write_text(header + proposal_text, encoding="utf-8")
    except OSError as e:
        return False, f"write failed: {e}"
    return True, f"proposal written to {target}"


# ---------------------------------------------------------------------------
# Telegram notification (best-effort)
# ---------------------------------------------------------------------------


def _read_telegram_token() -> Optional[str]:
    try:
        return subprocess.check_output(
            [
                "security",
                "find-generic-password",
                "-s",
                TELEGRAM_KEYCHAIN_SERVICE,
                "-a",
                TELEGRAM_KEYCHAIN_ACCOUNT,
                "-w",
            ],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def post_telegram(message: str) -> Tuple[bool, str]:
    """Post a message to {{USER_NAME}}'s chat via the Telegram bot. Best-effort."""
    token = _read_telegram_token()
    if not token:
        return False, "Telegram token not in keychain"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("ok"):
                return True, "sent"
            return False, f"telegram api: {payload.get('description', '?')}"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return False, f"http error: {e}"
    except json.JSONDecodeError as e:
        return False, f"bad json: {e}"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def render_report(
    decisions: List[Decision],
    pairs: List[SimilarityPair],
    clusters: List[List[SkillRecord]],
    mode: str,
    mode_reason: str,
    skipped_pinned: List[str],
    skipped_non_curated: int,
    now: dt,
) -> str:
    """Generate the dated dry-run/live report markdown."""
    lines: List[str] = []
    lines.append(f"# Skill Curator Report — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append(f"**Mode:** `{mode}` — {mode_reason}")
    lines.append(f"**Curated skills reviewed:** {len(decisions)}")
    lines.append(f"**Pinned skills skipped:** {len(skipped_pinned)}")
    lines.append(f"**Non-curated skills skipped:** {skipped_non_curated}")
    lines.append("")

    # Summary counts
    by_action: Dict[str, List[Decision]] = {}
    for d in decisions:
        by_action.setdefault(d.action, []).append(d)

    lines.append("## Summary")
    lines.append("")
    for action in (ACTION_KEEP, ACTION_ARCHIVE, ACTION_IMPROVE, ACTION_MERGE):
        n = len(by_action.get(action, []))
        lines.append(f"- **{action}:** {n}")
    lines.append("")

    # Per-action sections
    for action in (ACTION_ARCHIVE, ACTION_IMPROVE, ACTION_MERGE, ACTION_KEEP):
        items = by_action.get(action, [])
        if not items:
            continue
        lines.append(f"## {action} ({len(items)})")
        lines.append("")
        items.sort(key=lambda d: -d.confidence)
        for d in items:
            conf_flag = " (low-confidence)" if d.confidence < 0.3 else ""
            lines.append(f"### `{d.skill_name}` — confidence {d.confidence:.2f}{conf_flag}")
            lines.append("")
            lines.append(f"- **Rationale:** {d.rationale}")
            lines.append(
                f"- **Scores:** S={d.s_score:.3f}, Q={d.q_score:.3f}, "
                f"inv_90d={d.invocations_90d}, n_pos={d.n_pos}, n_neg={d.n_neg}"
            )
            if d.action == ACTION_MERGE:
                lines.append(f"- **Merge into:** `{d.merge_leader}` (R={d.r_to_leader:.3f})")
                lines.append(
                    f"- **Cluster members:** {', '.join('`' + n + '`' for n in d.cluster_members)}"
                )
            lines.append("")

    # Skipped skills (transparency)
    if skipped_pinned:
        lines.append("## Pinned (skipped)")
        lines.append("")
        for name in skipped_pinned:
            lines.append(f"- `{name}`")
        lines.append("")

    # Full similarity matrix — Algo Wizard's Q2 says first dry-run must
    # include this for threshold tuning. We always include it.
    lines.append("## Similarity matrix (sorted by R, descending)")
    lines.append("")
    lines.append("| Skill A | Skill B | R | J (tools) | C (body) | D (desc) |")
    lines.append("|---|---|---|---|---|---|")
    for p in pairs[:200]:  # cap at 200 to keep reports bounded
        lines.append(
            f"| `{p.a}` | `{p.b}` | {p.r:.3f} | {p.j:.3f} | {p.c:.3f} | {p.d:.3f} |"
        )
    if len(pairs) > 200:
        lines.append(f"\n_(... {len(pairs) - 200} more pairs truncated)_")
    lines.append("")

    return "\n".join(lines)


def telegram_digest(
    decisions: List[Decision], mode: str, report_path: Path
) -> str:
    """One-line digest for the Telegram message."""
    counts: Dict[str, int] = {a: 0 for a in (ACTION_KEEP, ACTION_ARCHIVE, ACTION_IMPROVE, ACTION_MERGE)}
    for d in decisions:
        counts[d.action] = counts.get(d.action, 0) + 1
    icon = "🧹" if mode == "live" else "🧪"
    return (
        f"{icon} *Skill curator weekly* ({mode})\n"
        f"Reviewed: {len(decisions)} | "
        f"KEEP: {counts[ACTION_KEEP]} | "
        f"ARCHIVE: {counts[ACTION_ARCHIVE]} | "
        f"IMPROVE: {counts[ACTION_IMPROVE]} | "
        f"MERGE: {counts[ACTION_MERGE]}\n"
        f"Report: `{report_path}`"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_curator(
    skills_dir: Path,
    archive_root: Path,
    reports_dir: Path,
    state_file: Path,
    prompt_path: Path,
    session_dir: Path,
    cli_dry_run: bool,
    skip_telegram: bool,
    force: bool,
    quiet: bool,
) -> int:
    def say(msg: str) -> None:
        if not quiet:
            print(msg)

    now = _now_utc()

    # Inactivity gate
    if not force:
        safe, reason = is_safe_to_run(session_dir)
        if not safe:
            say(f"[curator] inactivity gate: {reason}")
            say("[curator] exiting silently — will retry next week")
            return 0
    else:
        say("[curator] --force: bypassing inactivity gate")

    # Load state and determine mode
    state = load_state(state_file)
    if state.get("paused"):
        say("[curator] state.paused=true — exiting")
        return 0

    if state.get("first_run_at") is None:
        # Seed first-run timestamp (per Hermes' deferred-first-run pattern,
        # adapted: we still run the first time, but in dry-run mode regardless).
        state["first_run_at"] = now.isoformat()

    env_live = os.environ.get("CATALYST_CURATOR_LIVE", "").strip() == "1"
    mode, mode_reason = determine_mode(state, cli_dry_run, env_live, now)
    say(f"[curator] mode={mode} ({mode_reason})")

    # Discover skills
    all_skills = discover_skills(skills_dir)
    say(f"[curator] found {len(all_skills)} skills total (pre-filter)")

    # Load usage map
    usage_path = skills_dir / ".usage.json"
    usage_map = load_usage(usage_path)

    # Build records for ALL skills (for IDF corpus stability per Algo Wizard Q1)
    all_records: List[SkillRecord] = []
    for skill_md, skill_name in all_skills:
        rec = load_skill_record(skill_md, skill_name, usage_map)
        if rec is not None:
            all_records.append(rec)

    # Filter to curated subset for actual decisions
    curated_records: List[SkillRecord] = []
    skipped_pinned: List[str] = []
    skipped_non_curated = 0
    for r in all_records:
        if not is_curated(r.frontmatter):
            skipped_non_curated += 1
            continue
        if is_pinned(r.frontmatter):
            skipped_pinned.append(r.name)
            curated_records.append(r)  # still scored, but always KEEP
            continue
        curated_records.append(r)

    say(
        f"[curator] curated subset: {len(curated_records)} "
        f"({len(skipped_pinned)} pinned, {skipped_non_curated} non-curated skipped)"
    )

    if not curated_records:
        say("[curator] no curated skills to review — exiting clean")
        # Still update state so the run counts
        state["last_run_at"] = now.isoformat()
        state["runs_count"] = int(state.get("runs_count", 0)) + 1
        save_state(state_file, state)
        return 0

    # Compute IDF over the FULL corpus (all_records), not just curated
    corpus_tokens = [r.body_tokens for r in all_records]
    idf = compute_idf(corpus_tokens)

    # Run the algorithm — but only on curated records
    decisions, pairs, clusters = decide_all(curated_records, idf, now)

    # Invariant check before any mutation
    _assert_invariants(decisions, curated_records)

    # Render the report
    report_text = render_report(
        decisions=decisions,
        pairs=pairs,
        clusters=clusters,
        mode=mode,
        mode_reason=mode_reason,
        skipped_pinned=skipped_pinned,
        skipped_non_curated=skipped_non_curated,
        now=now,
    )

    reports_dir.mkdir(parents=True, exist_ok=True)
    report_filename = f"{now.strftime('%Y-%m-%d')}-{mode}.md"
    report_path = reports_dir / report_filename
    # Avoid overwriting previous-same-day report
    counter = 2
    while report_path.exists():
        report_path = reports_dir / f"{now.strftime('%Y-%m-%d')}-{mode}-{counter}.md"
        counter += 1
    report_path.write_text(report_text, encoding="utf-8")
    say(f"[curator] report: {report_path}")

    # Apply mutations only in live mode AND only if grace period has passed
    applied: Dict[str, List[str]] = {ACTION_ARCHIVE: [], ACTION_MERGE: [], ACTION_IMPROVE: []}
    if mode == "live" and _live_run_allowed(state, now):
        # Build name -> record lookup for fast access during mutation
        name_to_record = {r.name: r for r in curated_records}
        # Load prompt template once
        try:
            prompt_template = prompt_path.read_text(encoding="utf-8")
        except OSError as e:
            say(f"[curator] WARN: prompt file missing ({e}); skipping IMPROVE actions")
            prompt_template = None

        for d in decisions:
            if d.action == ACTION_KEEP:
                continue
            record = name_to_record.get(d.skill_name)
            if record is None:
                continue

            if d.action == ACTION_ARCHIVE:
                ok, msg, _ = archive_skill(record, d, archive_root, now)
                say(f"[curator] ARCHIVE {d.skill_name}: {msg}")
                if ok:
                    applied[ACTION_ARCHIVE].append(d.skill_name)

            elif d.action == ACTION_MERGE:
                leader = name_to_record.get(d.merge_leader or "")
                if leader is None:
                    say(f"[curator] MERGE {d.skill_name}: leader missing, skipping")
                    continue
                ok, msg, _ = merge_skill(record, leader, d, archive_root, now)
                say(f"[curator] MERGE {d.skill_name} -> {d.merge_leader}: {msg}")
                if ok:
                    applied[ACTION_MERGE].append(d.skill_name)

            elif d.action == ACTION_IMPROVE:
                if prompt_template is None:
                    continue
                ok, text, in_tok, out_tok = call_gemini_improve(record, d, prompt_template)
                if not ok:
                    say(f"[curator] IMPROVE {d.skill_name}: {text}")
                    continue
                if text.strip().startswith("SKIP"):
                    say(f"[curator] IMPROVE {d.skill_name}: gemini skipped")
                    continue
                ok2, msg = write_improve_proposal(record, text, now)
                say(
                    f"[curator] IMPROVE {d.skill_name}: {msg} "
                    f"(in_tok={in_tok}, out_tok={out_tok})"
                )
                if ok2:
                    applied[ACTION_IMPROVE].append(d.skill_name)
    elif mode == "live" and not _live_run_allowed(state, now):
        say("[curator] mode=live but grace period not yet passed — refusing to mutate")

    # Persist state
    state["last_run_at"] = now.isoformat()
    state["last_report_path"] = str(report_path)
    state["runs_count"] = int(state.get("runs_count", 0)) + 1
    save_state(state_file, state)

    # Persist usage map (might have been touched defensively, even if unchanged)
    save_usage(usage_path, usage_map)

    # Telegram notification
    if not skip_telegram:
        digest = telegram_digest(decisions, mode, report_path)
        if mode == "live":
            counts_summary = (
                f"\nApplied: ARCHIVE×{len(applied[ACTION_ARCHIVE])}, "
                f"MERGE×{len(applied[ACTION_MERGE])}, "
                f"IMPROVE×{len(applied[ACTION_IMPROVE])}"
            )
            digest += counts_summary
        ok, msg = post_telegram(digest)
        say(f"[curator] telegram: {msg}")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Huxley skill curator")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force dry-run mode (default during 30-day grace period anyway)",
    )
    parser.add_argument(
        "--skip-telegram",
        action="store_true",
        help="Don't post a Telegram notification",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the inactivity gate (testing/debug only)",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=SKILLS_DIR,
        help="Override the skills directory location",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout (LaunchAgent-friendly)",
    )
    args = parser.parse_args(argv)

    skills_dir = args.skills_dir
    archive_root = skills_dir / ".archive"
    curator_dir = skills_dir / ".curator"
    reports_dir = curator_dir / "reports"
    state_file = curator_dir / "state.json"
    prompt_path = curator_dir / "PROMPT.md"

    return run_curator(
        skills_dir=skills_dir,
        archive_root=archive_root,
        reports_dir=reports_dir,
        state_file=state_file,
        prompt_path=prompt_path,
        session_dir=SESSION_DIR,
        cli_dry_run=args.dry_run,
        skip_telegram=args.skip_telegram,
        force=args.force,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    sys.exit(main())
