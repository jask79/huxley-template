#!/usr/bin/env python3
"""OnStop hook - Generates documentation when session ends"""

import sys
import json
from pathlib import Path

# Add hook utilities to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import HookResult, get_catalyst_root, run_tool, log_hook_execution


def main():
    # Read hook input from stdin (JSON format)
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        hook_input = {}

    cwd = hook_input.get("cwd", str(Path.cwd()))

    # Determine capsule from cwd
    catalyst_root = get_catalyst_root()
    if str(cwd).startswith(str(catalyst_root / "capsules")):
        relative = Path(cwd).relative_to(catalyst_root / "capsules")
        capsule = str(relative.parts[0]) if relative.parts else None
    else:
        return HookResult(success=True, message="Not in a capsule, skipping doc generation")

    if not capsule:
        return HookResult(success=True, message="Could not determine capsule")

    # Run doc generation
    doc_generator = catalyst_root / "tools" / "generate_spec_docs.py"
    if not doc_generator.exists():
        return HookResult(success=False, message="Doc generator not found", block=False)

    # Pass capsule path directly (tool expects path as first argument, not --capsule flag)
    capsule_path = catalyst_root / "capsules" / capsule
    returncode, stdout, stderr = run_tool(str(doc_generator), str(capsule_path), timeout=10)

    if returncode == 0:
        result = HookResult(success=True, message=f"✓ Documentation updated for {capsule}")
    else:
        # Doc generation failure is non-blocking
        error_msg = stderr.strip() or stdout.strip() or "Generation failed"
        result = HookResult(
            success=False,
            message=f"⚠ Doc generation warning: {error_msg}",
            block=False  # Don't block session end
        )

    log_hook_execution("on_stop", result)
    return result


if __name__ == "__main__":
    result = main()
    if not result.success:
        print(result.message, file=sys.stderr)
    else:
        print(result.message)
    sys.exit(result.exit_code())