#!/usr/bin/env python3
"""Stop hook — Triggers automatic code review + auto-fix when code files were changed.

Checks the review queue accumulated by review_accumulator.py. If unreviewed
code files exist, blocks Claude from stopping and injects review instructions
via the decision/reason JSON protocol.

Flow: review_accumulator (PostToolUse) → this hook (Stop) → Codex peer review
(codex-consult.sh --mode diff --path ... for tracked files, --mode review --file
for untracked files) → appropriate specialist agent (auto-fix Major/Minor) →
spot-check verification. Critical issues are surfaced to the user without auto-fix.

The automatic turn-review reviewer is CODEX, not the Claude Code Reviewer agent.
Toggle the whole flow with /auto-review (writes/removes .claude/auto-review-disabled).
If the `codex` CLI isn't on PATH the flow is dormant: this hook stands down
silently (allows the stop, blocks nothing) after one stderr notice per repo.

Five-guard loop prevention:
1. stop_hook_active flag (built-in) — exit immediately if true
2. File state tracking — files marked reviewed after block output
3. 30-second cooldown — skip if reviewed recently
4. last_assistant_message check — detect if review or auto-fix already ran
5. autofix_pending flag (deterministic) — if set, fix-phase edits are auto-marked reviewed
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

QUEUE_DIR = Path("/tmp/catalyst-review-queues")
CATALYST_ROOT = os.environ.get("CATALYST_ROOT", "{{CATALYST_ROOT}}")
DISABLED_FLAG = Path(os.path.join(CATALYST_ROOT, ".claude", "auto-review-disabled"))
# Written once, the first time we stand down because `codex` is missing, so the
# "install the Codex CLI" notice is printed exactly once per repo. Sits beside
# .claude/auto-review-disabled and follows the same convention: runtime state,
# never committed. The template's .gitignore ignores both; if this repo's own
# .gitignore does not, the file shows up as untracked when codex is absent.
CODEX_MISSING_MARKER = Path(
    os.path.join(CATALYST_ROOT, ".claude", "auto-review-codex-missing-notified")
)
COOLDOWN_SECONDS = 30
MAX_FILES_IN_REASON = 20


def codex_available() -> bool:
    """True if the `codex` CLI resolves on PATH.

    Matches codex-consult.sh's own preflight (`command -v codex`), which is the
    only resolution it does — it honors no override env var. Never raises: on an
    unexpected error we assume codex IS available, which preserves the hook's
    prior behavior for the owner (whose codex is installed) instead of silently
    switching the review off.
    """
    try:
        return shutil.which("codex") is not None
    except Exception:
        return True


def notify_codex_missing_once() -> None:
    """Print one discoverable stderr line per repo, then leave a marker.

    The marker is created FIRST and the line printed only if creation
    succeeded, so an unwritable .claude/ can never turn this into per-turn
    noise. Fully best-effort: every failure is swallowed.
    """
    try:
        CODEX_MISSING_MARKER.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create: two concurrent sessions can both pass an exists()
        # check and both print, so let the filesystem pick the single winner.
        with open(CODEX_MISSING_MARKER, "x", encoding="utf-8") as fh:
            fh.write(
                "Auto code review stood down once because the `codex` CLI was "
                "not on PATH.\nDelete this file to see the notice again.\n"
            )
    except FileExistsError:
        return
    except Exception:
        return

    try:
        print(
            "auto-review: dormant — the `codex` CLI is not on PATH, so the "
            "automatic per-turn code review is doing nothing. Enable it with "
            "`npm install -g @openai/codex` (then `codex login`), or leave it "
            "off. Toggle/inspect with /auto-review. (Shown once.)",
            file=sys.stderr,
        )
    except Exception:
        pass


def read_queue(session_id: str) -> dict | None:
    """Read the review queue for this session."""
    queue_file = QUEUE_DIR / f"{session_id}.json"
    if not queue_file.exists():
        return None

    try:
        with open(queue_file) as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.loads(f.read())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        return None


def mark_reviewed(session_id: str, set_autofix_pending: bool = False) -> None:
    """Mark all files as reviewed and set cooldown timestamp.

    If set_autofix_pending=True, sets a flag so the NEXT stop-hook cycle
    knows an auto-fix was dispatched and should not re-trigger review.
    """
    queue_file = QUEUE_DIR / f"{session_id}.json"
    if not queue_file.exists():
        return

    fd = None
    try:
        fd = os.open(str(queue_file), os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)

        os.lseek(fd, 0, os.SEEK_SET)
        content = os.read(fd, 1024 * 1024).decode("utf-8", errors="replace")
        queue = json.loads(content)

        for entry in queue.get("files", []):
            entry["reviewed"] = True

        queue["last_review_timestamp"] = time.time()

        if set_autofix_pending:
            queue["autofix_pending"] = True

        new_content = json.dumps(queue, indent=2)
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, new_content.encode())
    except Exception as e:
        print(f"Warning: failed to write review state: {e}", file=sys.stderr)
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except Exception:
                pass


def clear_autofix_pending(session_id: str) -> None:
    """Clear the autofix_pending flag and mark all files reviewed.

    Called when stop hook detects the auto-fix cycle completed (new files
    from fixer edits exist but autofix_pending is set). This is the
    deterministic loop-breaker.
    """
    queue_file = QUEUE_DIR / f"{session_id}.json"
    if not queue_file.exists():
        return

    fd = None
    try:
        fd = os.open(str(queue_file), os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)

        os.lseek(fd, 0, os.SEEK_SET)
        content = os.read(fd, 1024 * 1024).decode("utf-8", errors="replace")
        queue = json.loads(content)

        for entry in queue.get("files", []):
            entry["reviewed"] = True

        queue["autofix_pending"] = False
        queue["last_review_timestamp"] = time.time()

        new_content = json.dumps(queue, indent=2)
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, new_content.encode())
    except Exception as e:
        print(f"Warning: failed to write review state: {e}", file=sys.stderr)
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except Exception:
                pass


def _build_agent_routing_hints(file_paths: list[str]) -> str:
    """Build agent routing hints based on file extensions present."""
    ext_to_agent = {
        ".py": ("Backend Dev", "🏛️ Backend Developer"),
        ".go": ("Backend Dev", "🏛️ Backend Developer"),
        ".rs": ("Backend Dev", "🏛️ Backend Developer"),
        ".java": ("Backend Dev", "🏛️ Backend Developer"),
        ".sql": ("Backend Dev", "🏛️ Backend Developer"),
        ".rb": ("Backend Dev", "🏛️ Backend Developer"),
        ".php": ("Backend Dev", "🏛️ Backend Developer"),
        ".ex": ("Backend Dev", "🏛️ Backend Developer"),
        ".exs": ("Backend Dev", "🏛️ Backend Developer"),
        ".ts": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".tsx": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".js": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".jsx": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".mjs": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".cjs": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".vue": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".svelte": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".css": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".scss": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".less": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".html": ("Frontend Dev", "🖥️ Frontend Developer"),
        ".swift": ("Mobile Dev", "📱 Mobile Developer"),
        ".kt": ("Mobile Dev", "📱 Mobile Developer"),
        ".sh": ("Automator", "🤖 Automator"),
        ".bash": ("Automator", "🤖 Automator"),
        ".zsh": ("Automator", "🤖 Automator"),
        ".c": ("Backend Dev", "🏛️ Backend Developer"),
        ".cpp": ("Backend Dev", "🏛️ Backend Developer"),
        ".h": ("Backend Dev", "🏛️ Backend Developer"),
        ".hpp": ("Backend Dev", "🏛️ Backend Developer"),
    }

    # Collect unique agents needed
    agents_needed = {}
    for fp in file_paths:
        ext = Path(fp).suffix.lower()
        if ext in ext_to_agent:
            short, full = ext_to_agent[ext]
            agents_needed[full] = short

    if not agents_needed:
        return "      - Default: use 🏛️ Backend Developer for unknown file types"

    lines = []
    for full_name, short_name in agents_needed.items():
        lines.append(f"      - {full_name} ({short_name})")
    return "\n".join(lines)


def _is_tracked(path: str) -> bool:
    """Return True if `path` is tracked by git, defaulting to True on any error.

    Runs git with cwd=CATALYST_ROOT, a short timeout, and swallows all errors.
    `git ls-files --error-unmatch` exits 0 for tracked paths, non-zero otherwise.
    Defaulting unknowns to tracked keeps them in the (safe) --mode diff bucket.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=CATALYST_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return True


def _bucket_tracked(file_paths: list[str]) -> tuple[list[str], list[str]]:
    """Split paths into (tracked, untracked) buckets via git, deterministically."""
    tracked: list[str] = []
    untracked: list[str] = []
    for fp in file_paths:
        if _is_tracked(fp):
            tracked.append(fp)
        else:
            untracked.append(fp)
    return tracked, untracked


def build_review_reason(unreviewed_files: list[dict]) -> str:
    """Build the reason string that Claude will see as review instructions."""
    file_paths = [f["path"] for f in unreviewed_files]

    # Cap the list for token efficiency
    display_paths = file_paths[:MAX_FILES_IN_REASON]
    overflow = len(file_paths) - MAX_FILES_IN_REASON

    file_list = "\n".join(f"- {p}" for p in display_paths)
    if overflow > 0:
        file_list += f"\n- ... and {overflow} more files"

    # Sanitize paths — remove shell metacharacters
    import shlex

    # Deterministically bucket files into tracked (review via --mode diff) vs
    # untracked (review via --mode review --file). Computed in Python so the
    # model never has to "notice" untracked files at runtime.
    tracked_paths, untracked_paths = _bucket_tracked(file_paths)

    # Build the tracked-file diff command. Each path is passed as a SEPARATE
    # --path argv to codex-consult (shlex.quote each), so paths are never
    # interpolated into a double-quoted prompt where $()/backticks could expand.
    # The human-readable focus prompt deliberately contains NO raw paths.
    tracked_path_args = " ".join(f"--path {shlex.quote(p)}" for p in tracked_paths)
    diff_command = (
        f"{{CATALYST_ROOT}}/tools/codex-consult.sh "
        f"--mode diff {tracked_path_args} "
        f'"Review the changes in the file(s) scoped by the --path arguments '
        f'above (this turn\'s edits). Report blocking issues, suggested '
        f'improvements, and anything risky."'
    )

    # Build the per-untracked-file review commands (deterministic fallback —
    # untracked files won't appear in any git diff). Paths are separate --file
    # argv, again never interpolated into the prompt string.
    untracked_commands = "\n".join(
        f"   `{{CATALYST_ROOT}}/tools/codex-consult.sh "
        f'--mode review --file {shlex.quote(p)} "automatic turn-review"`'
        for p in untracked_paths
    )

    if tracked_paths:
        step1 = (
            f"1. Run Codex's peer review of this turn's TRACKED changes "
            f"(HEAD-relative, scoped to the changed files):\n"
            f"   `{diff_command}`\n"
            f"   - The changed tracked files are passed as separate --path "
            f"arguments; the focus prompt intentionally contains no raw paths.\n"
            f"   - Codex output is logged automatically under "
            f"~/.cache/huxley/codex-consult/."
        )
    else:
        step1 = (
            "1. No TRACKED files changed this turn — skip the --mode diff step "
            "entirely (there is no committed-vs-working diff to review)."
        )

    if untracked_paths:
        step2 = (
            f"2. Run Codex's peer review of each BRAND-NEW / untracked file "
            f"(these won't appear in any git diff), one command per file:\n"
            f"{untracked_commands}\n"
            f"   - Codex output is logged automatically under "
            f"~/.cache/huxley/codex-consult/."
        )
    else:
        step2 = "2. No untracked files this turn — skip the per-file --mode review step."

    review_steps = f"{step1}\n{step2}"

    # Build agent routing hint based on file extensions
    agent_hints = _build_agent_routing_hints(file_paths)

    # Collect static analysis results if present
    static_results = []
    for f in unreviewed_files:
        sa = f.get("static_analysis")
        if sa and sa.get("finding_count", 0) > 0:
            static_results.append(
                {
                    "file": f["path"],
                    "tool": sa.get("tool", "unknown"),
                    "findings": sa.get("findings", []),
                }
            )

    static_section = ""
    if static_results:
        static_section = (
            f"\n\nPre-populated static analysis results "
            f"(from accumulator hook):\n"
            f"{json.dumps(static_results, indent=2)}\n"
        )

    return f"""AUTOMATIC_TURN_REVIEW: {len(file_paths)} code file(s) were modified during this turn. Have CODEX do a peer code review AND auto-fix any issues found.

Files changed:
{file_list}{static_section}

The reviewer for automatic turn-review is CODEX (via codex-consult.sh), NOT the Claude Code Reviewer agent. Do not invoke the 🧐 Code Reviewer subagent here.

Instructions:
{review_steps}
3. Read Codex's freeform output and triage each item into a severity:
   - "Blocking issues" that break correctness, security, or data integrity → CRITICAL
   - Other blocking issues / risky-or-surprising items → MAJOR
   - "Suggested improvements" / style / minor nits → MINOR
   - Fold in the pre-populated static analysis results above (treat ruff/eslint/shellcheck errors as Major, warnings as Minor).
4. Present a brief summary to the user: severity breakdown + key items, attributed to Codex.
5. Log review to monitoring/code_reviews.db (best-effort): build structured findings and run
   `echo '$JSON' | python3 {{CATALYST_ROOT}}/monitoring/log_code_review.py`
   - Each finding: {{"file_path": "...", "line_number": N|null, "severity": "critical|major|minor", "category": "...", "description": "...", "pattern_id": null, "source": "codex_review"}}
6. AUTO-FIX PHASE (MANDATORY for ALL Major AND Minor issues):
   ⚠️ EVERY Major and Minor finding MUST be dispatched for auto-fix. Do NOT skip Minor issues. Do NOT just report them. Fix them.
   a. Group ALL findings (Major + Minor) by file/domain and select the appropriate specialist agent:
{agent_hints}
   b. Dispatch the specialist via Task tool (model="opus") with a prompt containing:
      - ALL findings to fix — both Major AND Minor (copy Codex's relevant items for those files)
      - The file paths involved
      - Instruction: "Fix ONLY the listed issues. Do not refactor, add features, or change unrelated code."
   c. If findings span multiple specialist domains, dispatch agents IN PARALLEL (one Task per domain).
   d. After fixes complete, do a QUICK verification: re-read the changed files and confirm each finding was addressed. Do NOT re-run Codex — just spot-check.
   e. Present a brief fix summary to the user: what was fixed, by which agent. You MUST include the phrase "✅ AUTO-FIX COMPLETE" in your response.
   f. If any Critical issues were found, do NOT auto-fix those — present them to the user for manual decision. Major and Minor are ALWAYS auto-fixed.
   g. If Codex found ZERO issues, skip the auto-fix phase entirely and say "✅ AUTO-FIX COMPLETE: No issues to fix."
7. This is INFORMATIONAL ONLY — do not block any user operations
8. After presenting findings and fixes, respond normally to complete your original task"""


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

    # GUARD 0: Disabled via /auto-review toggle (takes precedence over everything)
    if DISABLED_FLAG.exists():
        return 0

    # GUARD 1: Loop prevention — if stop_hook_active, exit immediately
    if payload.get("stop_hook_active", False):
        return 0

    session_id = payload.get("session_id", "unknown")

    # Read the queue
    queue = read_queue(session_id)
    if not queue:
        return 0

    # GUARD 2: Check for unreviewed files
    unreviewed = [f for f in queue.get("files", []) if not f.get("reviewed", False)]
    if not unreviewed:
        return 0

    # GUARD 2b: Codex CLI missing — the injected instructions would just fail
    # with "command not found", so stand down entirely: allow the stop, block
    # nothing, inject nothing. Deliberately placed AFTER the loop, queue and
    # unreviewed checks so a recursive stop or a turn with nothing to review
    # never burns the one-per-repo notice on a turn that would not have been
    # reviewed anyway. The /auto-review flag (GUARD 0) still outranks it.
    if not codex_available():
        notify_codex_missing_once()
        return 0

    # GUARD 3: Cooldown — skip if reviewed recently
    last_review = queue.get("last_review_timestamp", 0)
    if time.time() - last_review < COOLDOWN_SECONDS:
        return 0

    # GUARD 4: Check last_assistant_message for evidence review/fix already happened.
    # Only match specific sentinel phrases — avoid broad substrings that could
    # false-positive on conversational text containing "auto-fix".
    last_msg = payload.get("last_assistant_message", "")
    if any(
        marker in last_msg
        for marker in ("AUTOMATIC_TURN_REVIEW", "Review Results", "AUTO-FIX COMPLETE")
    ):
        # Review/fix cycle was already done, mark files and exit
        mark_reviewed(session_id)
        return 0

    # GUARD 5 (deterministic loop-breaker): If autofix_pending is set, the
    # previous cycle dispatched fix agents. Whether the fix succeeded or was
    # skipped (Critical-only, agent crash, etc.), the sentinel "AUTO-FIX
    # COMPLETE" would have been caught by Guard 4 above. If we reach here
    # with autofix_pending=True, either:
    #   a) Fix edits created new queue entries (normal case) — mark reviewed
    #   b) No sentinel found but flag is set — clear flag, mark reviewed
    # In both cases, we break the loop. A genuinely new review cycle will
    # start fresh on the NEXT user-initiated edit (autofix_pending cleared).
    if queue.get("autofix_pending", False):
        clear_autofix_pending(session_id)
        return 0

    # Write detailed instructions to file ({{ORCHESTRATOR_NAME}} reads this), keep terminal output minimal
    reason = build_review_reason(unreviewed)
    context_file = QUEUE_DIR / f"{session_id}_review_context.txt"
    try:
        tmp_file = context_file.with_suffix(".tmp")
        tmp_file.write_text(reason)
        tmp_file.rename(context_file)
    except Exception:
        pass

    file_count = len(unreviewed)
    decision = {
        "decision": "block",
        "reason": f"AUTOMATIC_TURN_REVIEW: {file_count} file(s). Details: {json.dumps(str(context_file))}",
    }

    print(json.dumps(decision))

    # Mark files as reviewed AFTER outputting block decision.
    # Set autofix_pending=True so that if the fix phase creates new file
    # edits (which review_accumulator will queue), Guard 5 catches them
    # on the next stop cycle instead of re-triggering a full review.
    mark_reviewed(session_id, set_autofix_pending=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
