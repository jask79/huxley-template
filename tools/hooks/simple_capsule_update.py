#!/usr/bin/env python3
"""
Simple Session End Hook - Update Capsule Session Log
Logs basic session info without requiring LLM processing

Creates/updates:
- context/session_log.md - Chronological log of all sessions with basic stats
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

CATALYST_ROOT = Path("{{CATALYST_ROOT}}")


def get_capsule_from_cwd(cwd: str) -> Optional[str]:
    """Determine capsule name from working directory."""
    cwd_path = Path(cwd)

    # Check if in a capsule
    if "capsules/" in str(cwd_path):
        parts = cwd_path.parts
        try:
            capsule_idx = parts.index("capsules")
            if capsule_idx + 1 < len(parts):
                return parts[capsule_idx + 1]
        except ValueError:
            pass

    # Check if in Huxley root
    if str(cwd_path) == str(CATALYST_ROOT):
        return "SYSTEM"

    return None


def get_context_dir(capsule: str) -> Optional[Path]:
    """Get capsule context directory."""
    if capsule == "SYSTEM":
        context_dir = CATALYST_ROOT / "context"
    else:
        capsule_dir = CATALYST_ROOT / "capsules" / capsule
        if not capsule_dir.exists():
            return None
        context_dir = capsule_dir / "context"

    context_dir.mkdir(exist_ok=True)
    return context_dir


def count_transcript_messages(transcript_path: str) -> int:
    """Count messages in transcript."""
    try:
        count = 0
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    json.loads(line.strip())
                    count += 1
                except json.JSONDecodeError:
                    continue
        return count
    except Exception:
        return 0


def extract_tools_used(transcript_path: str) -> list:
    """Extract tools used in session from transcript."""
    tools = set()
    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    msg = json.loads(line.strip())
                    if not isinstance(msg, dict):
                        continue
                    # Real transcript lines nest content under message.content;
                    # accept a top-level content list too (older/other shapes).
                    content = msg.get("content")
                    if not isinstance(content, list):
                        inner = msg.get("message")
                        content = inner.get("content") if isinstance(inner, dict) else None
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "tool_use":
                                tool_name = item.get("name", "unknown")
                                tools.add(tool_name)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return sorted(list(tools))[:10]  # Limit to top 10


def update_session_log(capsule: str, context_dir: Path, session_data: dict):
    """
    Update session_log.md with basic session info.
    """
    log_file = context_dir / "session_log.md"

    # Create header if file doesn't exist
    if not log_file.exists():
        content = f"""# Session Log - {capsule}

Chronological log of Claude Code sessions in this capsule.

---

"""
        log_file.write_text(content)

    # Build session entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    session_id = session_data.get("session_id", "unknown")
    message_count = session_data.get("message_count", 0)
    tools_used = session_data.get("tools_used", [])

    entry = f"""## {timestamp}

**Session ID:** `{session_id}`
**Messages:** {message_count}
**Tools:** {", ".join(tools_used) if tools_used else "None"}
**Working Directory:** {session_data.get("cwd", "unknown")}

---

"""

    # Append to log
    with open(log_file, 'a') as f:
        f.write(entry)


def main():
    try:
        # Read hook input
        input_data = json.load(sys.stdin)

        session_id = input_data.get("session_id", "unknown")
        cwd = input_data.get("cwd", str(Path.cwd()))
        transcript_path = input_data.get("transcript_path")

        # Determine capsule
        capsule = get_capsule_from_cwd(cwd)
        if not capsule:
            # Not in a capsule, skip
            sys.exit(0)

        # Get context directory
        context_dir = get_context_dir(capsule)
        if not context_dir:
            print(f"Could not create context directory for: {capsule}", file=sys.stderr)
            sys.exit(0)

        # Gather session stats
        message_count = 0
        tools_used = []

        if transcript_path and Path(transcript_path).exists():
            message_count = count_transcript_messages(transcript_path)
            tools_used = extract_tools_used(transcript_path)

        session_data = {
            "session_id": session_id,
            "cwd": cwd,
            "message_count": message_count,
            "tools_used": tools_used
        }

        # Update session log
        update_session_log(capsule, context_dir, session_data)

        print(f"✓ Updated session log for capsule: {capsule}")
        sys.exit(0)

    except Exception as e:
        # Don't fail the hook - this is non-critical
        print(f"Warning: Could not update capsule context: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
