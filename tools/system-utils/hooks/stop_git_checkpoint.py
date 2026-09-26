#!/usr/bin/env python3
"""Stop hook — Git auto-checkpoint on session end.

When Claude Code stops, this hook creates a git stash if the working tree
is dirty. Uses `git stash create` + `git stash store` (non-destructive):
the working tree is never modified, but the index is temporarily staged
and then restored with `git reset` after the stash object is built. The stash is recorded in the stash list for recovery.

Stash message format: "claude-checkpoint: 2026-04-13-143022"

Safety gates:
- No-op if working dir is not inside a git repo
- No-op if working tree is clean (nothing to stash)
- No-op if cwd is a scratch/temp dir (/tmp, /private/tmp, /var/folders,
  or any Claude Code claude-<uid> scratch path) — ephemeral clones, sync dirs
- Always exits 0 — Stop hooks must never block session end

Pruning strategy (run manually to keep stash list tidy):
    git stash list | grep "claude-checkpoint" | awk -F: '{print $1}' \
        | tail -n +21 | xargs -I{} git stash drop {}
This keeps the 20 most recent checkpoints and drops the rest.
"""

from __future__ import annotations

import os
import re
import subprocess  # noqa: S404 - hardcoded git commands only, no untrusted input
import sys
from datetime import datetime

MAX_CHECKPOINTS = 20
LABEL = "claude-checkpoint"

# Temp roots, in canonical (realpath) form. On macOS /tmp -> /private/tmp and
# /var/folders -> /private/var/folders, and os.getcwd() returns the canonical
# form, so both spellings are listed.
SCRATCH_ROOTS = (
    "/tmp",  # noqa: S108 - safety gate comparison, not a file path we write to
    "/private/tmp",
    "/var/tmp",  # noqa: S108 - safety gate comparison
    "/private/var/tmp",
    "/var/folders",
    "/private/var/folders",
)

# Claude Code scratch convention: a path segment like "claude-501" (claude-<uid>)
CLAUDE_SCRATCH_SEGMENT = re.compile(r"^claude-\d+$")


def run(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(  # noqa: S603 - cmd is always a hardcoded git invocation
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, "", ""


def find_git_root(cwd: str) -> str | None:
    """Return the git root for cwd, or None if not in a repo."""
    code, out, _ = run(["git", "rev-parse", "--show-toplevel"], cwd)
    return out if code == 0 and out else None


def is_dirty(git_root: str) -> bool:
    """Return True if the working tree has any tracked or untracked changes."""
    code, out, _ = run(["git", "status", "--porcelain"], git_root)
    return code == 0 and bool(out)


def create_stash(git_root: str, message: str) -> bool:
    """Create a stash entry non-destructively. Returns True on success."""
    # Stage tracked modifications temporarily for the stash snapshot.
    # NOTE: `git add -u` stages tracked changes only; untracked files are NOT
    # included, and the `git reset` below unstages everything when done.
    stage_code, _, _ = run(["git", "add", "-u"], git_root)
    # stash create builds a stash object without touching the working tree
    code, sha, _ = run(["git", "stash", "create"], git_root)
    if code != 0 or not sha:
        # Nothing to stash (race condition) or error — reset staging and bail
        run(["git", "reset", "HEAD"], git_root)
        return False
    # Record the stash object in the stash reflog
    store_code, _, _ = run(["git", "stash", "store", "-m", message, sha], git_root)
    # Restore index to pre-add state
    run(["git", "reset", "HEAD"], git_root)
    return store_code == 0


def prune_old_checkpoints(git_root: str) -> None:
    """Drop checkpoints beyond MAX_CHECKPOINTS, oldest first."""
    code, out, _ = run(["git", "stash", "list"], git_root)
    if code != 0 or not out:
        return
    lines = out.splitlines()
    # Lines look like: stash@{0}: On main: claude-checkpoint: 2026-...
    checkpoint_indices = [
        i for i, line in enumerate(lines) if LABEL in line
    ]
    # checkpoint_indices are already in stash@{N} order (0 = newest)
    if len(checkpoint_indices) <= MAX_CHECKPOINTS:
        return
    # Drop the oldest ones (highest stash@{N} values)
    to_drop = checkpoint_indices[MAX_CHECKPOINTS:]
    # Must drop from highest index to lowest to avoid shifting
    for idx in sorted(to_drop, reverse=True):
        run(["git", "stash", "drop", f"stash@{{{idx}}}"], git_root)


def is_scratch_dir(path: str) -> bool:
    """Return True if path lives in a temp/scratch location.

    Resolves symlinks first: on macOS /tmp is a symlink to /private/tmp, and
    os.getcwd() already returns the canonical form, so a raw startswith("/tmp")
    check never matched.
    """
    resolved = os.path.realpath(path)
    for root in SCRATCH_ROOTS:
        if resolved == root or resolved.startswith(root + os.sep):
            return True
    # Claude Code scratch dirs (claude-<uid>) may sit under a relocated TMPDIR
    return any(CLAUDE_SCRATCH_SEGMENT.match(part) for part in resolved.split(os.sep))


def main() -> int:
    cwd = os.getcwd()

    # Never run in scratch/temp dirs (ephemeral clones, sync dirs, throwaway work)
    if is_scratch_dir(cwd):
        print(
            f"[git-checkpoint] scratch/temp dir — no checkpoint created: {cwd}",
            file=sys.stderr,
        )
        return 0

    git_root = find_git_root(cwd)
    if not git_root:
        return 0

    if not is_dirty(git_root):
        return 0

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    message = f"{LABEL}: {timestamp}"

    success = create_stash(git_root, message)
    if success:
        print(f"[git-checkpoint] stashed dirty work → {message}", file=sys.stderr)
        prune_old_checkpoints(git_root)
    else:
        print("[git-checkpoint] stash create returned no SHA — skipped", file=sys.stderr)

    return 0  # Always exit 0; never block session end


if __name__ == "__main__":
    sys.exit(main())
