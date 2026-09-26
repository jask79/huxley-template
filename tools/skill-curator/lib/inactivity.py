"""Inactivity gate per Algo Wizard's ADR section 5.

Two checks (both must pass):
  1. Newest .jsonl mtime in the session dir is ≥ 2 hours ago.
  2. No .jsonl was modified in the last 30 minutes.

The 30-minute check is stricter — catches "session paused mid-conversation."

Edge cases:
  - No JSONL files → True (nothing to wait for).
  - Future mtime (clock skew) → False (treat as active).
  - Lockfile present → False (caller is mid-write).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple


IDLE_HOURS_REQUIRED = 2.0
FRESHNESS_WINDOW_MINUTES = 30


def _newest_jsonl_mtime(session_dir: Path) -> Optional[datetime]:
    """Return the newest mtime among *.jsonl files, or None if no files."""
    if not session_dir.exists() or not session_dir.is_dir():
        return None
    newest: Optional[datetime] = None
    for p in session_dir.glob("*.jsonl"):
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        except (OSError, ValueError):
            continue
        if newest is None or mtime > newest:
            newest = mtime
    return newest


def _any_jsonl_within_window(session_dir: Path, minutes: int, now: datetime) -> bool:
    """True if any .jsonl was modified in the last `minutes`."""
    if not session_dir.exists() or not session_dir.is_dir():
        return False
    cutoff = now - timedelta(minutes=minutes)
    for p in session_dir.glob("*.jsonl"):
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        except (OSError, ValueError):
            continue
        if mtime > cutoff:
            return True
    return False


def is_safe_to_run(
    session_dir: Path,
    now: Optional[datetime] = None,
    state_lockfile: Optional[Path] = None,
) -> Tuple[bool, str]:
    """Return (safe, reason).

    `safe` True iff the inactivity gate passes. `reason` is a short string
    describing the outcome (for logging).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Lockfile guard
    if state_lockfile is not None and state_lockfile.exists():
        return False, f"state lockfile present at {state_lockfile}"

    newest = _newest_jsonl_mtime(session_dir)
    if newest is None:
        # No sessions ever → definitely idle
        return True, "no .jsonl session files in dir (treated as idle)"

    # Future mtime → clock skew, refuse
    if newest > now:
        return False, f"newest .jsonl has future mtime {newest.isoformat()}"

    hours_idle = (now - newest).total_seconds() / 3600.0
    if hours_idle < IDLE_HOURS_REQUIRED:
        return False, (
            f"too active: newest .jsonl was {hours_idle:.2f}h ago "
            f"(need ≥ {IDLE_HOURS_REQUIRED}h)"
        )

    if _any_jsonl_within_window(session_dir, FRESHNESS_WINDOW_MINUTES, now):
        return False, (
            f"a .jsonl was modified within the last {FRESHNESS_WINDOW_MINUTES} minutes"
        )

    return True, f"idle: newest .jsonl was {hours_idle:.2f}h ago"
