#!/usr/bin/env python3
"""
Session End Hook - Update Capsule Documentation
Extracts key learnings from session and updates capsule context files

Responsibilities:
- Analyze session transcript for key decisions, patterns, and learnings
- Update capsule context files (decisions.md, patterns.md, evolution.md)
- Create summary files for significant work
- Track what was built/changed in the session
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess

CATALYST_ROOT = Path("{{CATALYST_ROOT}}")

def get_capsule_from_cwd(cwd: str) -> Optional[str]:
    """Determine capsule name from working directory."""
    cwd_path = Path(cwd)

    # Check if in a capsule
    if "capsules/" in str(cwd_path):
        # Extract capsule name
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
        return CATALYST_ROOT / "context"

    capsule_dir = CATALYST_ROOT / "capsules" / capsule
    if not capsule_dir.exists():
        return None

    context_dir = capsule_dir / "context"
    context_dir.mkdir(exist_ok=True)
    return context_dir


def extract_session_summary(transcript_path: str) -> Optional[str]:
    """
    Extract session summary using LLM.

    Returns summary of:
    - What was built/changed
    - Key decisions made
    - Patterns identified
    - Issues resolved
    """
    if not Path(transcript_path).exists():
        return None

    # Use Anthropic API to summarize the session
    try:
        # Read transcript
        messages = []
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    msg = json.loads(line.strip())
                    messages.append(msg)
                except json.JSONDecodeError:
                    continue

        if not messages:
            return None

        # Build summary prompt
        prompt = """Analyze this Claude Code session transcript and extract:

1. **Work Completed:** What was built, changed, or fixed (be specific)
2. **Key Decisions:** Important architectural or technical decisions made
3. **Patterns Learned:** Design patterns, best practices, or learnings discovered
4. **Issues Resolved:** Problems fixed and their solutions

Format as markdown with clear sections. Be concise but specific. Include file names and technical details.

Focus on ACTIONABLE information that should be documented for future reference."""

        # Call Anthropic API via subprocess (uses ANTHROPIC_API_KEY env var)
        script_dir = Path(__file__).parent
        llm_script = script_dir.parent / "global" / "claude-config" / "hooks" / "utils" / "llm" / "anth.py"

        if not llm_script.exists():
            return None

        # Prepare input for LLM
        llm_input = {
            "prompt": prompt,
            "transcript": [
                {
                    "role": msg.get("role", "unknown"),
                    "content": str(msg.get("content", ""))[:500]  # Truncate for size
                }
                for msg in messages[-20:]  # Last 20 messages
            ]
        }

        # Call LLM script
        result = subprocess.run(
            ["uv", "run", str(llm_script), "--summarize"],
            input=json.dumps(llm_input),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        return None

    except Exception as e:
        print(f"Warning: Could not generate session summary: {e}", file=sys.stderr)
        return None


def update_session_log(capsule: str, context_dir: Path, summary: str):
    """
    Update session_log.md with this session's summary.
    Creates a chronological log of all sessions.
    """
    log_file = context_dir / "session_log.md"

    # Create header if file doesn't exist
    if not log_file.exists():
        log_file.write_text(f"# Session Log - {capsule}\n\n")

    # Append new session
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## Session: {timestamp}\n\n{summary}\n\n---\n"

    with open(log_file, 'a') as f:
        f.write(entry)


def create_work_summary(capsule: str, capsule_dir: Path, summary: str, session_id: str):
    """
    Create a summary file for significant work completed in this session.
    Only creates if substantial work was done.
    """
    # Check if summary indicates significant work
    significant_indicators = [
        "implemented",
        "built",
        "created",
        "completed",
        "deployed",
        "fixed",
        "added",
        "updated"
    ]

    if not any(indicator in summary.lower() for indicator in significant_indicators):
        return

    # Create summary file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    summary_file = capsule_dir / f"SESSION_{timestamp}_SUMMARY.md"

    content = f"""# Session Summary - {capsule}

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Session ID:** {session_id}

{summary}

---
*Auto-generated from session transcript*
"""

    summary_file.write_text(content)
    print(f"Created: {summary_file.name}")


def update_patterns_if_relevant(context_dir: Path, summary: str):
    """
    Update patterns.md if session revealed new patterns or best practices.
    """
    patterns_file = context_dir / "patterns.md"

    # Check if summary mentions patterns/best practices
    pattern_indicators = [
        "pattern",
        "best practice",
        "approach",
        "technique",
        "method",
        "strategy"
    ]

    if not any(indicator in summary.lower() for indicator in pattern_indicators):
        return

    # Create patterns file if doesn't exist
    if not patterns_file.exists():
        patterns_file.write_text("# Design Patterns & Best Practices\n\n")

    # Append new pattern entry
    timestamp = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n## {timestamp} - Session Learnings\n\n{summary}\n\n---\n"

    with open(patterns_file, 'a') as f:
        f.write(entry)


def update_decisions_if_relevant(context_dir: Path, summary: str):
    """
    Update decisions.md if session involved architectural decisions.
    """
    decisions_file = context_dir / "decisions.md"

    # Check if summary mentions decisions
    decision_indicators = [
        "decided",
        "decision",
        "chose",
        "selected",
        "opted",
        "architecture",
        "design"
    ]

    if not any(indicator in summary.lower() for indicator in decision_indicators):
        return

    # Create decisions file if doesn't exist
    if not decisions_file.exists():
        decisions_file.write_text("# Architectural Decision Record\n\n")

    # Append decision entry
    timestamp = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n## {timestamp} - Session Decisions\n\n{summary}\n\n---\n"

    with open(decisions_file, 'a') as f:
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
            print(f"Not in a capsule, skipping context update", file=sys.stderr)
            return

        # Get context directory
        context_dir = get_context_dir(capsule)
        if not context_dir:
            print(f"No context directory for capsule: {capsule}", file=sys.stderr)
            return

        # Extract session summary
        if not transcript_path:
            print("No transcript path provided", file=sys.stderr)
            return

        print(f"Analyzing session for capsule: {capsule}")
        summary = extract_session_summary(transcript_path)

        if not summary:
            print("Could not generate session summary", file=sys.stderr)
            return

        # Update context files
        print("Updating capsule context...")

        # Always update session log
        update_session_log(capsule, context_dir, summary)
        print(f"✓ Updated session_log.md")

        # Conditionally update other files
        update_patterns_if_relevant(context_dir, summary)
        update_decisions_if_relevant(context_dir, summary)

        # Create work summary if significant
        if capsule != "SYSTEM":
            capsule_dir = CATALYST_ROOT / "capsules" / capsule
            create_work_summary(capsule, capsule_dir, summary, session_id)

        print(f"✓ Capsule context updated for: {capsule}")

    except Exception as e:
        print(f"Error updating capsule context: {e}", file=sys.stderr)
        # Don't fail the hook - context update is non-critical
        return


if __name__ == "__main__":
    main()
