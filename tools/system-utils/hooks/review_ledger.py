#!/usr/bin/env python3
"""Review ledger — tracks which files have been manually reviewed in the current session.

Separate from the auto-review queue (review_accumulator + review_stop_hook).
This tracks manual /code-review invocations so the command can skip
already-reviewed files.

Usage:
    review_ledger.py unreviewed          # list changed files not yet manually reviewed
    review_ledger.py mark <file> [...]   # mark files as manually reviewed
    review_ledger.py mark --all          # mark all dirty files as reviewed
    review_ledger.py status              # show ledger summary
    review_ledger.py reset               # clear the ledger (new session)

Ledger file: /tmp/catalyst-manual-review-ledger.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

LEDGER_PATH = Path("/tmp/catalyst-manual-review-ledger.json")
CATALYST_ROOT = Path(os.environ.get("CATALYST_ROOT", "{{CATALYST_ROOT}}"))
QUEUE_DIR = Path("/tmp/catalyst-review-queues")
SESSION_ID_FILE = Path("/tmp/catalyst-current-session-id")  # legacy; still consulted as last resort
STAMP_DIR = Path("/tmp/catalyst-session-stamps")

# Max age before ledger auto-resets (8 hours — roughly one work session)
MAX_AGE_SECONDS = 8 * 3600

# Extensions worth reviewing (same as review_accumulator.py)
REVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs",
    ".swift", ".kt", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp",
    ".sh", ".bash", ".zsh", ".sql",
    ".css", ".scss", ".less", ".html",
    ".vue", ".svelte", ".rb", ".php", ".ex", ".exs",
}

SKIP_PATH_PATTERNS = (
    "/archive/", "/logs/", "/.claude/", "/memory/",
    "/node_modules/", "/__pycache__/", "/dist/", "/build/",
    "/.git/", "CLAUDE.md", "MEMORY.md", "session_log.md",
)


def _should_review(file_path: str) -> bool:
    for pattern in SKIP_PATH_PATTERNS:
        if pattern in file_path:
            return False
    return Path(file_path).suffix.lower() in REVIEWABLE_EXTENSIONS


def _get_ancestor_pids() -> list[int]:
    """Walk up the process tree from self to PID 1, returning each PPID visited."""
    pids = []
    pid = os.getpid()
    seen: set[int] = set()
    while pid and pid not in seen and pid != 1:
        seen.add(pid)
        try:
            result = subprocess.run(
                ["ps", "-o", "ppid=", "-p", str(pid)],
                capture_output=True, text=True, timeout=2,
            )
            ppid_str = result.stdout.strip()
            if not ppid_str:
                break
            ppid = int(ppid_str)
        except Exception:
            break
        pids.append(ppid)
        pid = ppid
    return pids


def _get_current_session_id() -> str | None:
    """Resolve the session_id for the current Claude Code session.

    Primary: walk the ancestor process tree and match against per-PPID stamp files
    written by pre_tool_use.py. This is race-free — each Claude Code process owns
    its own stamp file keyed by its PID, so concurrent sessions never collide.

    Fallback: the legacy single shared file /tmp/catalyst-current-session-id. This
    is inherently racy under concurrency but is kept so the transition period works
    and for environments where stamps haven't been written yet.
    """
    if STAMP_DIR.exists():
        for ppid in _get_ancestor_pids():
            stamp_file = STAMP_DIR / f"{ppid}.id"
            if stamp_file.exists():
                try:
                    sid = stamp_file.read_text().strip()
                    if sid:
                        return sid
                except Exception:
                    continue

    # Last-resort legacy fallback — unreliable under concurrency; documented as such.
    try:
        sid = SESSION_ID_FILE.read_text().strip()
        return sid if sid else None
    except Exception:
        return None


def _get_session_queue_files(session_id: str) -> list[str]:
    """Return relative file paths that Claude actually wrote in this session's queue."""
    queue_file = QUEUE_DIR / f"{session_id}.json"
    if not queue_file.exists():
        return []
    try:
        data = json.loads(queue_file.read_text())
        paths = []
        for entry in data.get("files", []):
            path = entry.get("path", "")
            if path.startswith(str(CATALYST_ROOT) + "/"):
                path = path[len(str(CATALYST_ROOT)) + 1:]
            if path and _should_review(path):
                paths.append(path)
        return sorted(set(paths))
    except Exception:
        return []


def _get_dirty_files_raw() -> list[str]:
    """Get all changed files (staged, unstaged, untracked) that are reviewable."""
    files = set()

    # Staged + unstaged changes
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=str(CATALYST_ROOT),
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    files.add(line.strip())
    except Exception:
        pass

    # Unstaged only (catches files not yet staged)
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=10,
            cwd=str(CATALYST_ROOT),
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    files.add(line.strip())
    except Exception:
        pass

    # Untracked files
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=10,
            cwd=str(CATALYST_ROOT),
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    files.add(line.strip())
    except Exception:
        pass

    return sorted(f for f in files if _should_review(f))


def _get_session_dirty_files(ledger: dict) -> list[str]:
    """Get only files that were actually modified during this session.

    Preferred: use the review_accumulator's session queue (scoped to the
    current Claude Code conversation UUID). Falls back to mtime comparison
    against the ledger baseline when no session_id is available.
    """
    session_id = _get_current_session_id()
    if session_id:
        # Use the accumulator queue — ground truth for what Claude touched this conversation
        queue_files = _get_session_queue_files(session_id)
        if queue_files:
            return queue_files
        # Queue exists but empty — no edits written this session yet. Correct: nothing to review.
        return []

    # No session_id resolved at all. Returning the repo-global mtime diff here would
    # silently leak files from other concurrent sessions into this review scope, which
    # is worse than a false empty result. Return empty and warn instead.
    print(
        "warning: no session stamp found; returning empty scope to avoid cross-session leakage",
        file=sys.stderr,
    )
    return []


def _get_file_mtime(file_path: str) -> float:
    """Get modification time of a file."""
    full = CATALYST_ROOT / file_path
    try:
        return full.stat().st_mtime
    except Exception:
        return 0.0


def _snapshot_baseline() -> dict[str, float]:
    """Capture mtime of every currently-dirty file as the session baseline."""
    dirty = _get_dirty_files_raw()
    return {f: _get_file_mtime(f) for f in dirty}


def _new_ledger() -> dict:
    """Create a fresh ledger with a baseline snapshot of current dirty files."""
    return {
        "created_at": time.time(),
        "reviewed": {},
        "baseline_mtimes": _snapshot_baseline(),
    }


def _read_ledger() -> dict:
    """Read the ledger, auto-reset if stale."""
    if not LEDGER_PATH.exists():
        ledger = _new_ledger()
        _write_ledger(ledger)
        return ledger

    try:
        data = json.loads(LEDGER_PATH.read_text())
    except Exception:
        ledger = _new_ledger()
        _write_ledger(ledger)
        return ledger

    # Auto-reset if ledger is too old
    if time.time() - data.get("created_at", 0) > MAX_AGE_SECONDS:
        ledger = _new_ledger()
        _write_ledger(ledger)
        return ledger

    # Backfill baseline for ledgers created before this feature
    if "baseline_mtimes" not in data:
        data["baseline_mtimes"] = _snapshot_baseline()
        _write_ledger(data)

    return data


def _write_ledger(data: dict) -> None:
    data.setdefault("created_at", time.time())
    data["updated_at"] = time.time()
    tmp = LEDGER_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(LEDGER_PATH)


def cmd_unreviewed(global_mode: bool = False) -> int:
    """List changed files that haven't been manually reviewed."""
    ledger = _read_ledger()
    all_dirty = _get_dirty_files_raw()
    scope = all_dirty if global_mode else _get_session_dirty_files(ledger)
    reviewed = ledger.get("reviewed", {})

    unreviewed = []
    for f in scope:
        if f not in reviewed:
            unreviewed.append(f)
        else:
            # File was reviewed, but modified since? Needs re-review.
            reviewed_at = reviewed[f].get("reviewed_at", 0)
            current_mtime = _get_file_mtime(f)
            if current_mtime > reviewed_at:
                unreviewed.append(f)

    result = {
        "unreviewed": unreviewed,
        "count": len(unreviewed),
        "scope": "global" if global_mode else "session",
        "scope_dirty": len(scope),
        "all_dirty": len(all_dirty),
        "already_reviewed": len(scope) - len(unreviewed),
    }
    print(json.dumps(result))
    return 0


def cmd_mark(args: list[str], global_mode: bool = False) -> int:
    """Mark files as reviewed."""
    ledger = _read_ledger()

    if "--all" in args or (not args and global_mode):
        # --all: mark all session-dirty files (or global-dirty if --global)
        args = [a for a in args if a != "--all"]
        scope = _get_dirty_files_raw() if global_mode else _get_session_dirty_files(ledger)
        files_to_mark = scope
    elif not args:
        print("Usage: review_ledger.py mark <file> [...] or mark --all [--global]", file=sys.stderr)
        return 1
    else:
        files_to_mark = args

    now = time.time()
    for f in files_to_mark:
        ledger.setdefault("reviewed", {})[f] = {
            "reviewed_at": now,
            "mtime_at_review": _get_file_mtime(f),
        }

    _write_ledger(ledger)
    print(json.dumps({"marked": len(files_to_mark), "files": files_to_mark}))
    return 0


def cmd_status() -> int:
    """Show ledger summary."""
    ledger = _read_ledger()
    session_dirty = _get_session_dirty_files(ledger)
    all_dirty = _get_dirty_files_raw()
    reviewed = ledger.get("reviewed", {})

    # Compute truly unreviewed (accounting for re-modifications)
    unreviewed_count = 0
    stale_count = 0
    for f in session_dirty:
        if f not in reviewed:
            unreviewed_count += 1
        else:
            reviewed_at = reviewed[f].get("reviewed_at", 0)
            if _get_file_mtime(f) > reviewed_at:
                unreviewed_count += 1
                stale_count += 1

    age_hours = (time.time() - ledger.get("created_at", time.time())) / 3600
    baseline_count = len(ledger.get("baseline_mtimes", {}))

    print(json.dumps({
        "session_dirty_files": len(session_dirty),
        "all_dirty_files": len(all_dirty),
        "baseline_files_excluded": baseline_count,
        "reviewed_in_session": len(reviewed),
        "unreviewed": unreviewed_count,
        "stale_reviews": stale_count,
        "ledger_age_hours": round(age_hours, 1),
        "auto_reset_hours": MAX_AGE_SECONDS / 3600,
    }, indent=2))
    return 0


def cmd_reset() -> int:
    """Clear the ledger and capture a fresh baseline."""
    ledger = _new_ledger()
    _write_ledger(ledger)
    baseline_count = len(ledger.get("baseline_mtimes", {}))
    print(json.dumps({"reset": True, "baseline_files": baseline_count}))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: review_ledger.py {unreviewed|mark|status|reset}", file=sys.stderr)
        return 1

    cmd = sys.argv[1]
    flags = [a for a in sys.argv[2:] if a.startswith("--")]
    positional = [a for a in sys.argv[2:] if not a.startswith("--")]

    if cmd == "unreviewed":
        return cmd_unreviewed(global_mode="--global" in flags)
    elif cmd == "mark":
        mark_args = positional + (["--all"] if "--all" in flags else [])
        return cmd_mark(mark_args, global_mode="--global" in flags)
    elif cmd == "status":
        return cmd_status()
    elif cmd == "reset":
        return cmd_reset()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
