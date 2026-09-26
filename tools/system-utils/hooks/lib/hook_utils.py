#!/usr/bin/env python3
"""Shared utilities for Claude Code hooks in Huxley"""

import subprocess
from pathlib import Path


class HookResult:
    """Standardized hook result for Claude Code"""

    def __init__(self, success: bool, message: str = "", block: bool = False):
        self.success = success
        self.message = message
        self.block = block  # If True, block the operation

    def exit_code(self) -> int:
        """Return appropriate exit code for Claude Code hooks"""
        if self.success:
            return 0
        elif self.block:
            return 2  # Blocking error
        else:
            return 1  # Non-blocking warning


def get_catalyst_root() -> Path:
    """Get Huxley root directory (hook_utils.py -> lib -> hooks -> tools -> Huxley root)"""
    return Path(__file__).resolve().parent.parent.parent.parent


def get_current_capsule() -> str | None:
    """Detect current capsule from working directory"""
    cwd = Path.cwd()
    catalyst_root = get_catalyst_root()

    # Check if we're in a capsule
    if str(cwd).startswith(str(catalyst_root / "capsules")):
        relative = cwd.relative_to(catalyst_root / "capsules")
        return str(relative.parts[0]) if relative.parts else None

    return None


def run_tool(tool_path: str, *args, timeout: int = 5) -> tuple[int, str, str]:
    """Run a Huxley tool with timeout"""
    try:
        result = subprocess.run(
            [tool_path] + list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=get_catalyst_root(),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Tool timed out after {timeout} seconds"
    except Exception as e:
        return 1, "", f"Tool execution failed: {str(e)}"


def send_notification(title: str, message: str):
    """Send macOS notification"""
    try:
        safe_message = (
            message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
        )
        safe_title = (
            title.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
        )
        subprocess.run(
            ["osascript", "-e", f'display notification "{safe_message}" with title "{safe_title}"'],
            check=False,
        )
    except Exception:
        pass  # Notifications are non-critical


def log_hook_execution(hook_name: str, result: HookResult):
    """Log hook execution to Huxley logs"""
    log_file = get_catalyst_root() / "registry" / "hooks.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(log_file, "a") as f:
            import datetime

            timestamp = datetime.datetime.now().isoformat()
            status = "SUCCESS" if result.success else "BLOCKED" if result.block else "WARNING"
            capsule = get_current_capsule() or "SYSTEM"
            f.write(f"{timestamp} | {capsule} | {hook_name} | {status} | {result.message}\n")
    except Exception:
        pass  # Logging failures shouldn't break hooks
