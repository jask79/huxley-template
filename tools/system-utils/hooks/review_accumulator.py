#!/usr/bin/env python3
"""PostToolUse hook — Accumulates code file changes for automatic review.

Fires after Edit/Write/NotebookEdit. Appends changed file paths to a
session-scoped queue file. The review_stop_hook.py reads this queue
when Claude is about to stop and triggers a lightweight code review.

Non-blocking, fast (~20ms). Pure filesystem operations.
"""

import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Extensions that warrant code review
REVIEWABLE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".mjs",
    ".cjs",
    ".swift",
    ".kt",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
    ".css",
    ".scss",
    ".less",
    ".html",
    ".vue",
    ".svelte",
    ".rb",
    ".php",
    ".ex",
    ".exs",
}

# Paths to always skip regardless of extension
SKIP_PATH_PATTERNS = (
    "/archive/",
    "/logs/",
    "/.claude/",
    "/memory/",
    "/node_modules/",
    "/__pycache__/",
    "/dist/",
    "/build/",
    "/.git/",
    "CLAUDE.md",
    "MEMORY.md",
    "session_log.md",
)

QUEUE_DIR = Path("/tmp/catalyst-review-queues")

# Only review files inside the Huxley repo. Skips throwaway scripts in
# ~/Downloads, /tmp, and other out-of-repo locations.
CATALYST_ROOT = Path(__file__).resolve().parents[3]

# Extensions handled by each static analysis tool
_RUFF_EXTS = {".py"}
_ESLINT_EXTS = {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}
_SHELLCHECK_EXTS = {".sh", ".bash", ".zsh"}

MAX_FINDINGS = 10  # cap stored details to keep queue files small


def run_static_analysis(file_path: str) -> dict | None:
    """Run a quick inline static analysis on *file_path*.

    Returns a dict with keys ``tool``, ``finding_count``, and ``findings``,
    or ``None`` if no analysis tool applies or execution fails.

    Constraints:
    - subprocess timeout: 5 s
    - never raises — all exceptions are caught silently
    - findings list is capped at MAX_FINDINGS entries
    """
    ext = Path(file_path).suffix.lower()

    try:
        if ext in _RUFF_EXTS:
            return _run_ruff(file_path)
        elif ext in _ESLINT_EXTS:
            return _run_eslint(file_path)
        elif ext in _SHELLCHECK_EXTS:
            return _run_shellcheck(file_path)
    except Exception:
        pass

    return None


def _run_ruff(file_path: str) -> dict | None:
    """Run `ruff check` on a Python file and return a normalised result dict."""
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", "--select=E,F,S", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    try:
        raw = json.loads(result.stdout or "[]")
    except Exception:
        return None

    findings = []
    for item in raw[:MAX_FINDINGS]:
        findings.append(
            {
                "line": item.get("location", {}).get("row"),
                "code": item.get("code", ""),
                "message": item.get("message", ""),
                "severity": "error" if (item.get("code") or "").startswith("E") else "warning",
            }
        )

    return {
        "tool": "ruff",
        "finding_count": len(raw),
        "findings": findings,
    }


def _run_eslint(file_path: str) -> dict | None:
    """Run `eslint --format=json` on a JS/TS file and return a normalised result dict."""
    try:
        result = subprocess.run(
            ["eslint", "--format=json", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    try:
        raw = json.loads(result.stdout or "[]")
    except Exception:
        return None

    # ESLint returns a list of file-result objects
    all_messages = []
    for file_result in raw:
        all_messages.extend(file_result.get("messages", []))

    total = len(all_messages)
    findings = []
    for msg in all_messages[:MAX_FINDINGS]:
        severity_val = msg.get("severity", 1)
        findings.append(
            {
                "line": msg.get("line"),
                "code": msg.get("ruleId", ""),
                "message": msg.get("message", ""),
                "severity": "error" if severity_val == 2 else "warning",
            }
        )

    return {
        "tool": "eslint",
        "finding_count": total,
        "findings": findings,
    }


def _run_shellcheck(file_path: str) -> dict | None:
    """Run `shellcheck -f json` on a shell script and return a normalised result dict."""
    try:
        result = subprocess.run(
            ["shellcheck", "-f", "json", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    try:
        raw = json.loads(result.stdout or "[]")
    except Exception:
        return None

    total = len(raw)
    findings = []
    for item in raw[:MAX_FINDINGS]:
        level = item.get("level", "warning")
        findings.append(
            {
                "line": item.get("line"),
                "code": f"SC{item.get('code', '')}",
                "message": item.get("message", ""),
                "severity": "error" if level in ("error",) else "warning",
            }
        )

    return {
        "tool": "shellcheck",
        "finding_count": total,
        "findings": findings,
    }


def should_review(file_path: str) -> bool:
    """Determine if a file change warrants code review."""
    if not file_path:
        return False

    # Only review files inside the Huxley repo
    try:
        if not Path(file_path).expanduser().resolve().is_relative_to(CATALYST_ROOT):
            return False
    except (OSError, ValueError):
        return False

    # Skip certain paths
    for pattern in SKIP_PATH_PATTERNS:
        if pattern in file_path:
            return False

    # Check extension
    ext = Path(file_path).suffix.lower()
    return ext in REVIEWABLE_EXTENSIONS


def append_to_queue(
    session_id: str, file_path: str, tool_name: str, static_analysis: dict | None = None
) -> None:
    """Atomically append a file entry to the session's review queue."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    queue_file = QUEUE_DIR / f"{session_id}.json"

    # Read existing queue with file lock
    fd = None
    try:
        fd = os.open(str(queue_file), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)

        # Read current content directly via the fd
        os.lseek(fd, 0, os.SEEK_SET)
        content = os.read(fd, 1024 * 1024).decode("utf-8", errors="replace")

        if content.strip():
            queue = json.loads(content)
        else:
            queue = {"session_id": session_id, "files": [], "last_review_timestamp": 0}

        # Stale check: reset if the newest file entry is older than 24 hours
        if (
            queue["files"]
            and max(f.get("timestamp", 0) for f in queue["files"]) < time.time() - 86400
        ):
            queue = {"session_id": session_id, "files": [], "last_review_timestamp": 0}

        # Deduplicate: if same file already unreviewed, update timestamp
        existing = None
        for entry in queue["files"]:
            if entry["path"] == file_path and not entry.get("reviewed", False):
                existing = entry
                break

        if existing:
            existing["timestamp"] = time.time()
            existing["tool"] = tool_name
            if static_analysis is not None:
                existing["static_analysis"] = static_analysis
        else:
            entry: dict = {
                "path": file_path,
                "tool": tool_name,
                "timestamp": time.time(),
                "reviewed": False,
            }
            if static_analysis is not None:
                entry["static_analysis"] = static_analysis
            queue["files"].append(entry)

        # Write back using the fd directly
        new_content = json.dumps(queue, indent=2)
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, new_content.encode())
    except Exception:
        # Non-blocking: if anything fails, skip silently
        pass
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except Exception:
                pass


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0

    if not raw.strip():
        return 0

    try:
        payload = json.loads(raw)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "NotebookEdit"):
        return 0

    session_id = payload.get("session_id", "unknown")

    # Extract file path from tool input
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        # Try tool_response for filePath
        tool_response = payload.get("tool_response", {})
        file_path = tool_response.get("filePath", "")

    if not should_review(file_path):
        return 0

    # Run inline static analysis (best-effort, never blocks)
    analysis = run_static_analysis(file_path)

    append_to_queue(session_id, file_path, tool_name, static_analysis=analysis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
