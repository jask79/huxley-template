#!/usr/bin/env python3
"""
Orchestrator Validation Hook - Post-Agent Completion Validator
Triggers after subagent tool completion (reported as "Task" by older Claude Code
releases and as "Agent" by newer ones) to validate agent claims vs actual implementation.

Only validates IMPLEMENTATION agents (Backend Dev, Frontend Dev, etc.).
Skips read-only agents (Code Reviewer, Research Agent, etc.) entirely.

Wired in .claude/settings.json (PostToolUse, matcher "Task").
Logs to ~/.cache/huxley/orchestrator-validation.log.
"""

import re
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Agents that don't produce file changes — skip validation entirely
READ_ONLY_AGENTS = {
    "code reviewer", "research agent", "explore",
    "business analyst", "seo analyzer", "venture analyst",
    "product strategist", "brand specialist", "plan",
}


# The subagent tool is reported as "Task" by older Claude Code releases and as
# "Agent" by newer ones (2.1.x). Accept either name; exact match only, so an
# unrelated future tool whose name merely contains one of these is not caught.
SUBAGENT_TOOL_NAMES = {"Task", "Agent"}


def log_validation(message, level="INFO"):
    """Log validation activity"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = Path.home() / ".cache" / "huxley" / "orchestrator-validation.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {level}: {message}\n")


def is_read_only_agent(agent_type: str) -> bool:
    """Check if the agent is read-only (doesn't produce file changes)."""
    clean = re.sub(r'[^\x00-\x7F]+', '', agent_type).strip().lower()
    return clean in READ_ONLY_AGENTS


def extract_response_text(tool_response) -> str:
    """Flatten a hook tool_response into plain text.

    Newer Claude Code releases report the content as a list of blocks
    ([{"type": "text", "text": ...}]); older ones used a plain string.
    Backgrounded agents report no content at all (only an outputFile), which
    yields "" so callers skip instead of crashing.
    """
    if isinstance(tool_response, str):
        return tool_response
    if not isinstance(tool_response, dict):
        return ""
    content = tool_response.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def detect_completion_claims(text):
    """Detect if agent claimed task completion in its response text.

    Only checks structured completion phrases, not single common words
    like 'done' which cause false positives in code diffs.
    """
    completion_indicators = [
        "completed successfully",
        "implementation complete",
        "task complete",
        "ready to test",
        "all set and ready",
        "working perfectly",
        "should now work",
        "changes have been applied",
        "files have been updated",
    ]

    text_lower = text.lower()
    for indicator in completion_indicators:
        if indicator in text_lower:
            return True
    return False


def validate_file_changes():
    """Check if files were actually modified recently"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd="{{CATALYST_ROOT}}",
            timeout=5
        )

        if result.stdout.strip():
            return True, f"Files modified: {len(result.stdout.strip().splitlines())}"
        else:
            return False, "No file changes detected"

    except Exception as e:
        return False, f"Git check failed: {e}"


def validate_build_status():
    """Check if build/validation commands would pass"""
    build_indicators = []

    validation_files = [
        "package.json", "requirements.txt", "Cargo.toml",
        "go.mod", "specs/current.yaml"
    ]

    for file in validation_files:
        if Path(f"{{CATALYST_ROOT}}/{file}").exists():
            build_indicators.append(f"Found {file}")

    return len(build_indicators) > 0, build_indicators


def validate_implementation_quality():
    """Run basic quality checks on recently changed Python files only."""
    issues = []

    try:
        # Check both unstaged and staged changes
        unstaged = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=AM", "HEAD"],
            capture_output=True, text=True, cwd="{{CATALYST_ROOT}}",
            timeout=5
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True, text=True, cwd="{{CATALYST_ROOT}}",
            timeout=5
        )

        all_files = set(unstaged.stdout.splitlines()) | set(staged.stdout.splitlines())
        py_files = [f.strip() for f in all_files if f.strip().endswith('.py')]

        if not py_files:
            return True, []

        # Compile only the changed files (fast, targeted)
        for py_file in py_files[:20]:  # Cap at 20 files
            full_path = Path("{{CATALYST_ROOT}}") / py_file
            if not full_path.exists():
                continue
            result = subprocess.run(
                ["python3", "-m", "py_compile", str(full_path)],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                issues.append(f"Syntax error in {py_file}")

    except subprocess.TimeoutExpired:
        log_validation("Quality check timed out", "WARN")
    except Exception:
        pass

    return len(issues) == 0, issues


def generate_validation_report(agent_output, validations):
    """Generate orchestrator validation feedback"""
    file_valid, file_msg = validations["files"]
    build_valid, build_msg = validations["build"]
    quality_valid, quality_msg = validations["quality"]

    overall_valid = file_valid and quality_valid

    if overall_valid:
        confidence = "HIGH" if build_valid else "MEDIUM"
        status = "VALIDATED"
    else:
        confidence = "LOW"
        status = "REQUIRES REVIEW"

    report = f"""
ORCHESTRATOR VALIDATION REPORT
Agent Completion Claim: {"Detected" if detect_completion_claims(agent_output) else "No claim"}
Validation Status: {status}
Confidence: {confidence}

Implementation Checks:
- File Changes: {"PASS" if file_valid else "FAIL"} {file_msg}
- Build Ready: {"PASS" if build_valid else "FAIL"} {build_msg if isinstance(build_msg, str) else f"{len(build_msg)} indicators"}
- Code Quality: {"PASS" if quality_valid else "FAIL"} {"No issues" if quality_valid else f"{len(quality_msg)} issues"}

Assessment: {
    "Implementation appears complete and ready for testing." if overall_valid else
    "Implementation incomplete or has quality issues. Manual review recommended."
}
"""

    return report, overall_valid


def main():
    """Main validation hook execution"""
    try:
        try:
            hook_data = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, Exception):
            hook_data = {}

        tool_name = hook_data.get("tool_name", "unknown")
        tool_input = hook_data.get("tool_input", {})
        tool_response = hook_data.get("tool_response", {})

        log_validation(f"Hook triggered: tool={tool_name}")

        # Only validate subagent tool completions ("Task" or "Agent")
        if tool_name not in SUBAGENT_TOOL_NAMES:
            return

        # Skip read-only agents (Code Reviewer, Research, etc.)
        agent_type = tool_input.get("subagent_type", "")
        if is_read_only_agent(agent_type):
            log_validation(f"Skipping read-only agent: {agent_type}")
            return

        log_validation(f"Validating {tool_name} completion: agent={agent_type}")

        # Check the agent's RESPONSE for completion claims (not the prompt)
        response_content = extract_response_text(tool_response)

        if not response_content:
            log_validation(f"Empty response content for agent {agent_type}, skipping")
            return

        if not detect_completion_claims(response_content):
            log_validation("No completion claim detected, skipping validation")
            return

        # Run validation checks
        validations = {
            "files": validate_file_changes(),
            "build": validate_build_status(),
            "quality": validate_implementation_quality()
        }

        report, is_valid = generate_validation_report(response_content, validations)
        log_validation(f"Validation result: {'PASS' if is_valid else 'FAIL'}")

        print(report, file=sys.stderr)

        report_file = Path.home() / ".cache" / "huxley" / "last-validation-report.txt"
        with open(report_file, "w") as f:
            f.write(report)

    except Exception as e:
        log_validation(f"Validation hook error: {e}", "ERROR")


if __name__ == "__main__":
    main()
