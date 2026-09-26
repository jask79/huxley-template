"""Unit tests for the inactivity gate.

Run with:
    python3 tools/skill-curator/tests/test_inactivity.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from lib.inactivity import (  # noqa: E402
    FRESHNESS_WINDOW_MINUTES,
    IDLE_HOURS_REQUIRED,
    is_safe_to_run,
)


def _set_mtime(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


class InactivityGateTests(unittest.TestCase):
    def test_no_jsonl_files_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session_dir = Path(td)
            now = datetime.now(timezone.utc)
            safe, reason = is_safe_to_run(session_dir, now=now)
            self.assertTrue(safe)
            self.assertIn("no", reason.lower())

    def test_recent_jsonl_blocks_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session_dir = Path(td)
            now = datetime.now(timezone.utc)
            # Active session: jsonl modified 30 minutes ago
            f = session_dir / "sess.jsonl"
            f.write_text("{}\n", encoding="utf-8")
            _set_mtime(f, now - timedelta(minutes=30))
            safe, reason = is_safe_to_run(session_dir, now=now)
            self.assertFalse(safe)
            self.assertIn("active", reason.lower())

    def test_idle_jsonl_allows_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session_dir = Path(td)
            now = datetime.now(timezone.utc)
            # Idle: jsonl modified 4 hours ago
            f = session_dir / "sess.jsonl"
            f.write_text("{}\n", encoding="utf-8")
            _set_mtime(f, now - timedelta(hours=4))
            safe, reason = is_safe_to_run(session_dir, now=now)
            self.assertTrue(safe)

    def test_freshness_window_30min_strict_check(self) -> None:
        """Even if newest is > 2h ago, ANY .jsonl modified in last 30 min blocks."""
        with tempfile.TemporaryDirectory() as td:
            session_dir = Path(td)
            now = datetime.now(timezone.utc)
            # Old session — looks idle
            old = session_dir / "old.jsonl"
            old.write_text("{}\n", encoding="utf-8")
            _set_mtime(old, now - timedelta(hours=10))
            # But also a paused session, modified 10 minutes ago
            paused = session_dir / "paused.jsonl"
            paused.write_text("{}\n", encoding="utf-8")
            _set_mtime(paused, now - timedelta(minutes=10))
            safe, reason = is_safe_to_run(session_dir, now=now)
            # "newest" is paused (10 min ago) — should fail the 2h check first.
            self.assertFalse(safe)

    def test_only_old_freshness_passes(self) -> None:
        """Only files older than 30 min freshness window AND newest > 2h."""
        with tempfile.TemporaryDirectory() as td:
            session_dir = Path(td)
            now = datetime.now(timezone.utc)
            # Multiple files, all comfortably idle
            for i in range(3):
                f = session_dir / f"s{i}.jsonl"
                f.write_text("{}\n", encoding="utf-8")
                _set_mtime(f, now - timedelta(hours=5 + i))
            safe, reason = is_safe_to_run(session_dir, now=now)
            self.assertTrue(safe)

    def test_future_mtime_treated_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session_dir = Path(td)
            now = datetime.now(timezone.utc)
            f = session_dir / "weird.jsonl"
            f.write_text("{}\n", encoding="utf-8")
            _set_mtime(f, now + timedelta(hours=1))
            safe, reason = is_safe_to_run(session_dir, now=now)
            self.assertFalse(safe)
            self.assertIn("future", reason.lower())

    def test_lockfile_blocks_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session_dir = Path(td)
            now = datetime.now(timezone.utc)
            f = session_dir / "old.jsonl"
            f.write_text("{}\n", encoding="utf-8")
            _set_mtime(f, now - timedelta(hours=10))
            lockfile = Path(td) / "state.json.lock"
            lockfile.write_text("locked", encoding="utf-8")
            safe, reason = is_safe_to_run(session_dir, now=now, state_lockfile=lockfile)
            self.assertFalse(safe)
            self.assertIn("lockfile", reason.lower())

    def test_just_past_2h_threshold_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session_dir = Path(td)
            now = datetime.now(timezone.utc)
            f = session_dir / "session.jsonl"
            f.write_text("{}\n", encoding="utf-8")
            # Exactly 2h 5min ago, no recent modifications elsewhere
            _set_mtime(f, now - timedelta(hours=2, minutes=5))
            safe, reason = is_safe_to_run(session_dir, now=now)
            self.assertTrue(safe)


if __name__ == "__main__":
    unittest.main(verbosity=2)
