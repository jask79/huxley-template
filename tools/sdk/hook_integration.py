#!/usr/bin/env python3
"""
Hook Integration Layer for SDK Workflows

Enables SDK workflows to call Huxley validation hooks synchronously,
ensuring validation gates work with SDK-based automation. Raises exceptions
that halt SDK execution on validation failures.

Usage:
    from hook_integration import call_hook, HookValidationError

    # Post-tool-use validation
    try:
        result = call_hook(
            "post_tool_use",
            tool_name="Edit",
            tool_input={"file_path": "specs/current.yaml"},
            tool_response={"filePath": "specs/current.yaml"}
        )
    except HookValidationError as e:
        print(f"Validation failed: {e}")
        raise  # Halt SDK workflow
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any


class HookValidationError(Exception):
    """Raised when a hook blocks SDK workflow execution"""

    def __init__(self, hook_name: str, message: str):
        self.hook_name = hook_name
        super().__init__(f"Hook '{hook_name}' blocked execution: {message}")


class HookResult:
    """Result from hook execution"""

    def __init__(self, success: bool, message: str = "", block: bool = False):
        self.success = success
        self.message = message
        self.block = block

    def exit_code(self) -> int:
        """Return exit code (matches hook convention)"""
        if self.success:
            return 0
        elif self.block:
            return 2  # Blocking error
        else:
            return 1  # Non-blocking warning


def get_catalyst_root() -> Path:
    """Get Huxley root directory"""
    return Path("{{CATALYST_ROOT}}")


def call_hook(
    hook_name: str,
    tool_name: str = "",
    tool_input: Optional[Dict[str, Any]] = None,
    tool_response: Optional[Dict[str, Any]] = None,
    cwd: Optional[Path] = None,
    timeout: int = 10
) -> HookResult:
    """
    Call a Huxley hook synchronously from SDK workflow.

    Args:
        hook_name: Hook to call (e.g., "post_tool_use", "on_session_start")
        tool_name: Name of tool that triggered hook (e.g., "Edit", "Write")
        tool_input: Input parameters passed to the tool
        tool_response: Response from the tool
        cwd: Working directory for hook context (defaults to current)
        timeout: Maximum seconds to wait for hook (default 10)

    Returns:
        HookResult with success status and message

    Raises:
        HookValidationError: If hook blocks execution (validation failure)
        FileNotFoundError: If hook script not found
        subprocess.TimeoutExpired: If hook exceeds timeout

    Example:
        # Validate after editing a spec file
        result = call_hook(
            "post_tool_use",
            tool_name="Edit",
            tool_input={"file_path": "specs/current.yaml"},
            tool_response={"filePath": "specs/current.yaml"}
        )

        if result.block:
            raise HookValidationError("post_tool_use", result.message)
    """
    # Locate hook script
    catalyst_root = get_catalyst_root()
    hook_script = catalyst_root / "tools" / "hooks" / f"{hook_name}.py"

    if not hook_script.exists():
        raise FileNotFoundError(f"Hook script not found: {hook_script}")

    # Prepare hook input (JSON to stdin)
    hook_input = {
        "tool_name": tool_name,
        "tool_input": tool_input or {},
        "tool_response": tool_response or {},
        "cwd": str(cwd or Path.cwd())
    }

    # Execute hook synchronously
    try:
        result = subprocess.run(
            [sys.executable, str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=catalyst_root
        )

        # Parse result from exit code and output
        exit_code = result.returncode
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        message = stderr or stdout or "Hook completed"

        if exit_code == 0:
            # Success
            hook_result = HookResult(success=True, message=message)
        elif exit_code == 2:
            # Blocking error - halt SDK workflow
            hook_result = HookResult(success=False, message=message, block=True)
            raise HookValidationError(hook_name, message)
        else:
            # Non-blocking warning
            hook_result = HookResult(success=False, message=message, block=False)

        return hook_result

    except subprocess.TimeoutExpired:
        raise subprocess.TimeoutExpired(
            cmd=str(hook_script),
            timeout=timeout,
            output=f"Hook '{hook_name}' timed out after {timeout}s"
        )


def validate_tool_operation(
    tool_name: str,
    file_path: str,
    timeout: int = 5
) -> None:
    """
    Convenience wrapper for post-tool-use validation.

    Args:
        tool_name: Name of tool (e.g., "Edit", "Write")
        file_path: Path to file modified by tool
        timeout: Validation timeout (default 5s)

    Raises:
        HookValidationError: If validation fails and blocks execution

    Example:
        # After SDK workflow edits a spec file
        validate_tool_operation("Edit", "specs/current.yaml")
        # Raises HookValidationError if validation fails
    """
    call_hook(
        "post_tool_use",
        tool_name=tool_name,
        tool_input={"file_path": file_path},
        tool_response={"filePath": file_path},
        timeout=timeout
    )


def notify_session_start(context: Optional[Dict[str, Any]] = None) -> HookResult:
    """
    Call on_session_start hook for SDK workflow initialization.

    Args:
        context: Optional context data for session start

    Returns:
        HookResult (non-blocking)

    Example:
        notify_session_start({"workflow": "daily_audit", "capsule": "example-social-capsule"})
    """
    return call_hook(
        "on_session_start",
        tool_input=context or {}
    )


def notify_session_end(
    context: Optional[Dict[str, Any]] = None,
    timeout: int = 15
) -> HookResult:
    """
    Call on_session_end hook for SDK workflow completion.

    Args:
        context: Optional context data for session end
        timeout: Hook timeout (default 15s for doc generation)

    Returns:
        HookResult (non-blocking)

    Example:
        notify_session_end({
            "workflow": "daily_audit",
            "duration_seconds": 45,
            "success": True
        })
    """
    return call_hook(
        "on_session_end",
        tool_input=context or {},
        timeout=timeout
    )


def main():
    """CLI for testing hook integration"""
    import argparse

    parser = argparse.ArgumentParser(description="SDK Hook Integration Testing")
    parser.add_argument("hook", help="Hook name to test")
    parser.add_argument("--tool", default="", help="Tool name (for post_tool_use)")
    parser.add_argument("--file", help="File path (for post_tool_use)")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout in seconds")

    args = parser.parse_args()

    try:
        if args.file:
            # Test validation
            print(f"→ Testing validation: {args.hook} for {args.file}")
            validate_tool_operation(args.tool or "Edit", args.file, timeout=args.timeout)
            print("✓ Validation passed")
        else:
            # Test generic hook
            print(f"→ Testing hook: {args.hook}")
            result = call_hook(args.hook, timeout=args.timeout)
            if result.success:
                print(f"✓ Hook succeeded: {result.message}")
            else:
                print(f"⚠ Hook warning: {result.message}")

    except HookValidationError as e:
        print(f"✗ Validation failed: {e}", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as e:
        print(f"✗ Hook not found: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired as e:
        print(f"✗ Hook timeout: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Hook error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
