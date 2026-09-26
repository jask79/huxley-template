"""Skill usage telemetry sidecar — Phase 4 of the Hermes cherry-pick.

Port of Hermes' tools/skill_usage.py, adapted to Huxley's `.claude/skills/`
layout. Reads/writes a sidecar JSON map at `.claude/skills/.usage.json` keyed
by skill name. Counters are best-effort: a corrupt sidecar never crashes the
caller. Atomic writes via tempfile + os.replace match Hermes' pattern.

Huxley differences from Hermes:
  - Provenance flag is `metadata.curated: true` in SKILL.md frontmatter
    (Huxley's bar from Q3 in ADR-hermes-cherrypick.md), not a `created_by`
    field in the sidecar. We still mirror `agent_created` into the sidecar
    for compatibility, but the source of truth is frontmatter.
  - We honor `metadata.pinned: true` in frontmatter as the "off-limits" flag.
  - No bundled-manifest concept — we use `metadata.curated` instead, which
    {{USER_NAME}} sets per-skill.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


STATE_ACTIVE = "active"
STATE_STALE = "stale"
STATE_ARCHIVED = "archived"
_VALID_STATES = {STATE_ACTIVE, STATE_STALE, STATE_ARCHIVED}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_timestamp(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp defensively. Returns None on failure."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ---------------------------------------------------------------------------
# Frontmatter parsing — we never edit frontmatter, only read it.
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(skill_md_text: str) -> Dict[str, Any]:
    """Tiny YAML parser sufficient for Huxley skill frontmatter.

    Handles flat key:value, nested `metadata:` block, and inline list values.
    Stdlib-only — no PyYAML dep. Falls back to {} on any malformed input.
    """
    m = _FRONTMATTER_RE.match(skill_md_text)
    if not m:
        return {}

    fm: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    current_block: Optional[str] = None  # 'metadata' if inside metadata: block

    for raw_line in m.group(1).splitlines():
        # Strip trailing comments
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        # Detect indentation — anything indented under a known block
        indent = len(line) - len(line.lstrip())
        stripped = line.lstrip()

        if indent == 0:
            current_block = None
            if stripped.startswith("metadata:"):
                # Could be inline (`metadata: {curated: true}`) or block
                rest = stripped.split(":", 1)[1].strip()
                if rest and rest != "":
                    # Inline form not supported here; ignore content beyond `metadata:`
                    pass
                current_block = "metadata"
                continue
            # Top-level scalar key
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                fm[key.strip()] = _coerce_yaml_scalar(val.strip())
        elif current_block == "metadata":
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                metadata[key.strip()] = _coerce_yaml_scalar(val.strip())

    if metadata:
        fm["metadata"] = metadata
    return fm


def _coerce_yaml_scalar(s: str) -> Any:
    """Convert YAML scalar strings to Python types."""
    if s == "":
        return ""
    # Strip quotes
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~"):
        return None
    # Number?
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def is_curated(frontmatter: Dict[str, Any]) -> bool:
    """A skill is curator-eligible iff metadata.curated == true."""
    md = frontmatter.get("metadata") or {}
    return bool(md.get("curated") is True)


def is_pinned(frontmatter: Dict[str, Any]) -> bool:
    """Pinned skills bypass all curator transitions."""
    md = frontmatter.get("metadata") or {}
    return bool(md.get("pinned") is True)


# ---------------------------------------------------------------------------
# Sidecar I/O
# ---------------------------------------------------------------------------


def empty_record() -> Dict[str, Any]:
    """Default usage record. Backfilled into existing records on read."""
    return {
        "use_count": 0,
        "view_count": 0,
        "patch_count": 0,
        "last_used_at": None,
        "last_viewed_at": None,
        "last_patched_at": None,
        "first_used_at": None,
        "created_at": _now_iso(),
        "state": STATE_ACTIVE,
        "feedback": [],  # list of {signal: pos|neg|neutral, ts: iso}
        "agent_created": False,  # mirror of metadata.curated for compat
        "archived_at": None,
    }


def load_usage(usage_path: Path) -> Dict[str, Dict[str, Any]]:
    """Read the entire .usage.json map. Returns empty dict on missing/corrupt."""
    if not usage_path.exists():
        return {}
    try:
        data = json.loads(usage_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Failed to read %s: %s", usage_path, e)
        return {}
    if not isinstance(data, dict):
        return {}
    clean: Dict[str, Dict[str, Any]] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            clean[str(k)] = v
    return clean


def save_usage(usage_path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    """Atomic write via tempfile + os.replace. Best-effort — errors logged."""
    try:
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(usage_path.parent), prefix=".usage_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, usage_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.debug("Failed to write %s: %s", usage_path, e, exc_info=True)


def get_record(usage: Dict[str, Dict[str, Any]], skill_name: str) -> Dict[str, Any]:
    """Return record for skill_name, backfilled with default keys."""
    rec = usage.get(skill_name)
    if not isinstance(rec, dict):
        return empty_record()
    base = empty_record()
    for k, v in base.items():
        rec.setdefault(k, v)
    return rec


# ---------------------------------------------------------------------------
# Helpers used by the scorer
# ---------------------------------------------------------------------------


def latest_activity_at(record: Dict[str, Any]) -> Optional[datetime]:
    """Newest of last_used / last_viewed / last_patched."""
    latest: Optional[datetime] = None
    for key in ("last_used_at", "last_viewed_at", "last_patched_at"):
        dt = _parse_iso_timestamp(record.get(key))
        if dt is None:
            continue
        if latest is None or dt > latest:
            latest = dt
    return latest


def first_activity_at(record: Dict[str, Any]) -> Optional[datetime]:
    """Oldest known activity (first_used or created)."""
    first = _parse_iso_timestamp(record.get("first_used_at"))
    if first:
        return first
    return _parse_iso_timestamp(record.get("created_at"))


def total_invocations(record: Dict[str, Any]) -> int:
    try:
        return int(record.get("use_count") or 0)
    except (TypeError, ValueError):
        return 0


def invocations_in_last_n_days(record: Dict[str, Any], n: int, now: datetime) -> int:
    """Best-effort estimate of invocations in last n days.

    The sidecar tracks total counts and last-used timestamps but doesn't
    bin per-day. We use a conservative heuristic: if last_used_at is within
    the window, return total use_count (assumes recent use). If outside the
    window, return 0. This mirrors Hermes' approximation and is good enough
    for the staleness threshold (which only checks "any use in 90 days").
    """
    last = _parse_iso_timestamp(record.get("last_used_at"))
    if last is None:
        return 0
    cutoff = now - timedelta(days=n)
    if last < cutoff:
        return 0
    return total_invocations(record)


def feedback_in_last_n_days(record: Dict[str, Any], n: int, now: datetime) -> List[Dict[str, Any]]:
    """Filter feedback entries to those within the last n days."""
    feedback = record.get("feedback") or []
    if not isinstance(feedback, list):
        return []
    cutoff = now - timedelta(days=n)
    out: List[Dict[str, Any]] = []
    for f in feedback:
        if not isinstance(f, dict):
            continue
        ts = _parse_iso_timestamp(f.get("ts"))
        if ts is None or ts < cutoff:
            continue
        out.append(f)
    return out
