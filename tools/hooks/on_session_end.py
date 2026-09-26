#!/usr/bin/env python3
"""OnSessionEnd hook - Runs session audit and logs activity"""

import sys
import json
import datetime
import subprocess
from pathlib import Path

# Add hook utilities to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import HookResult, get_catalyst_root, log_hook_execution


def fire_skill_proposer(session_id: str, catalyst_root: Path) -> None:
    """Best-effort fire-and-forget call to the skill proposer.

    Detached subprocess so it never blocks Claude Code's session-end flow.
    Hard-wrapped in try/except — proposer failures must NEVER fail the hook.
    Phase 2 of the Hermes cherry-pick (ADR-hermes-cherrypick.md, Pattern 1).
    """
    try:
        proposer = catalyst_root / "tools" / "skill-curator" / "proposer.py"
        if not proposer.exists():
            return
        venv_python = catalyst_root / ".venv" / "bin" / "python3"
        python_bin = str(venv_python) if venv_python.exists() else sys.executable
        cmd = [python_bin, str(proposer), "--quiet"]
        if session_id and session_id != "unknown":
            cmd.extend(["--session-id", session_id])
        log_dir = catalyst_root / "logs" / "skill-curator"
        log_dir.mkdir(parents=True, exist_ok=True)
        out_log = open(log_dir / "proposer.stdout.log", "ab")
        err_log = open(log_dir / "proposer.stderr.log", "ab")
        # Detached subprocess — proposer can take up to 30s for Gemini call.
        subprocess.Popen(
            cmd,
            stdout=out_log,
            stderr=err_log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(catalyst_root),
        )
    except Exception:
        # Never block the hook on proposer issues.
        pass


def main():
    # Read hook input from stdin (JSON format)
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        hook_input = {}

    session_id = hook_input.get("session_id", "unknown")
    cwd = hook_input.get("cwd", str(Path.cwd()))

    # Determine capsule from cwd
    catalyst_root = get_catalyst_root()
    if str(cwd).startswith(str(catalyst_root / "capsules")):
        relative = Path(cwd).relative_to(catalyst_root / "capsules")
        capsule = str(relative.parts[0]) if relative.parts else "SYSTEM"
    else:
        capsule = "SYSTEM"

    timestamp = datetime.datetime.now().isoformat()

    # Collect session metrics
    session_data = {
        "timestamp": timestamp,
        "session_id": session_id,
        "capsule": capsule,
        "cwd": cwd,
    }

    # Log session end
    audit_log = catalyst_root / "registry" / "daily" / "session_audit.log"
    audit_log.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(audit_log, 'a') as f:
            f.write(json.dumps(session_data) + "\n")

        result = HookResult(success=True, message=f"✓ Session audit logged for {capsule}")
    except Exception as e:
        result = HookResult(success=False, message=f"⚠ Audit logging failed: {str(e)}", block=False)

    # Fire skill proposer (best-effort, detached). Phase 2 of Hermes cherry-pick.
    fire_skill_proposer(session_id, catalyst_root)

    log_hook_execution("on_session_end", result)
    return result


if __name__ == "__main__":
    result = main()
    if not result.success:
        print(result.message, file=sys.stderr)
    else:
        print(result.message)
    sys.exit(result.exit_code())