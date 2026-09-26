#!/usr/bin/env python3
"""Huxley compatibility hook stub.

This repo snapshot no longer carries legacy hook implementations. This stub keeps
Claude Code hook invocations non-failing so sessions can start and run.
"""

import json
import os
import sys
from datetime import datetime


def _log(msg: str) -> None:
    log_dir = os.environ.get("CLAUDE_HOOKS_LOG_DIR", "")
    if not log_dir:
        return
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "compat-hooks.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()}Z {msg}\n")
    except Exception:
        pass


def main() -> int:
    raw = ""
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""

    event = "unknown"
    if raw.strip():
        try:
            payload = json.loads(raw)
            event = payload.get("hook_event_name", "unknown")
        except Exception:
            event = "unparsed"

    _log(f"stub {os.path.basename(sys.argv[0])} event={event} args={' '.join(sys.argv[1:])}")
    # No output and success status => no-op hook.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
