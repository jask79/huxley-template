#!/usr/bin/env python3
"""PostToolUse hook - Validates specs when YAML files are modified, verifies subagent work"""

import sys
import json
import re
import subprocess
from pathlib import Path

# Add hook utilities to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import HookResult, get_catalyst_root, get_current_capsule, run_tool, log_hook_execution


# The subagent tool is reported as "Task" by older Claude Code releases and as
# "Agent" by newer ones (2.1.x). Accept either name; exact match only, so an
# unrelated future tool whose name merely contains one of these is not caught.
SUBAGENT_TOOL_NAMES = {"Task", "Agent"}


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


def verify_subagent_work(hook_input):
    """Verify subagent (Task/Agent tool) actually completed claimed work."""
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", {})

    agent_name = tool_input.get("subagent_type", "Unknown Agent")
    agent_output = extract_response_text(tool_response)

    # Extract file claims from agent output
    modified_files = []
    created_files = []

    patterns = {
        'modified': [
            r'Modified:\s*([^\n]+)',
            r'Updated:\s*([^\n]+)',
            r'Edited:\s*([^\n]+)',
            r'Files modified:\s*([^\n]+)',
        ],
        'created': [
            r'Created:\s*([^\n]+)',
            r'Added:\s*([^\n]+)',
            r'New file:\s*([^\n]+)',
            r'Documentation created:\s*([^\n]+)',
        ]
    }

    for pattern in patterns['modified']:
        matches = re.findall(pattern, agent_output, re.IGNORECASE)
        modified_files.extend([f.strip().strip('`') for f in matches])

    for pattern in patterns['created']:
        matches = re.findall(pattern, agent_output, re.IGNORECASE)
        created_files.extend([f.strip().strip('`') for f in matches])

    if not modified_files and not created_files:
        # No file claims, allow
        return HookResult(success=True, message=f"Agent {agent_name}: No file claims")

    # Run verification tool
    verifier = get_catalyst_root() / "tools" / "verify_subagent_work.py"
    cwd = Path(hook_input.get("cwd", Path.cwd()))

    cmd = [str(verifier), '--agent', agent_name, '--base-dir', str(cwd)]
    if modified_files:
        cmd.extend(['--modified', ','.join(modified_files)])
    if created_files:
        cmd.extend(['--created', ','.join(created_files)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            # Verification passed
            return HookResult(success=True, message=f"✅ Verified {agent_name} work")
        else:
            # Verification FAILED - BLOCK
            return HookResult(
                success=False,
                message=f"⛔ SUBAGENT VERIFICATION FAILED\n\n{result.stdout}\n\n"
                        f"{{ORCHESTRATOR_NAME}}: You MUST implement the missing deliverables before reporting to {{USER_NAME}}.",
                block=True
            )
    except Exception as e:
        # On error, log but allow
        return HookResult(success=True, message=f"Verification error (allowing): {e}")


def main():
    # Read hook input from stdin (JSON format)
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        return HookResult(success=True, message="No hook input received")

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", {})

    # PRIORITY 1: Verify subagent tool completions ("Task" or "Agent")
    if tool_name in SUBAGENT_TOOL_NAMES:
        return verify_subagent_work(hook_input)

    # PRIORITY 2: Validate spec files on Edit/Write
    if tool_name not in ["Edit", "Write"]:
        return HookResult(success=True)

    # Get file path from tool response or input
    file_path = tool_response.get("filePath") or tool_input.get("file_path", "")

    if not file_path:
        return HookResult(success=True, message="No file path in hook input")

    # Check if it's a spec file
    is_spec = "specs/" in file_path and file_path.endswith(".yaml")
    is_standards = file_path.endswith("standards.yaml")

    if not is_spec and not is_standards:
        return HookResult(success=True, message="Not a spec file")

    # Get current capsule from cwd
    cwd = Path(hook_input.get("cwd", Path.cwd()))
    catalyst_root = get_catalyst_root()

    if str(cwd).startswith(str(catalyst_root / "capsules")):
        relative = cwd.relative_to(catalyst_root / "capsules")
        capsule = str(relative.parts[0]) if relative.parts else None
    else:
        return HookResult(success=True, message="Not in a capsule")

    if not capsule:
        return HookResult(success=True, message="Could not determine capsule")

    # Run validation
    validator = catalyst_root / "tools" / "validate_specs.py"
    if not validator.exists():
        return HookResult(success=False, message="Validator not found", block=False)

    # validate_specs.py takes a positional capsule path (it has no --capsule flag)
    returncode, stdout, stderr = run_tool(str(validator), str(catalyst_root / "capsules" / capsule), timeout=5)

    if returncode == 0:
        result = HookResult(success=True, message=f"✓ Specs validated for {capsule}")

        # After successful validation, trigger RAG incremental update
        try:
            rag_indexer = catalyst_root / "tools" / "rag" / "indexer.py"
            if rag_indexer.exists():
                # Trigger incremental update for the modified file
                import subprocess
                subprocess.Popen(
                    ["python3", str(rag_indexer), "--incremental", file_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
        except Exception:
            # RAG update is non-blocking - don't fail if it errors
            pass
    else:
        # Validation failed - block the operation
        error_msg = stderr.strip() or stdout.strip() or "Validation failed"
        result = HookResult(
            success=False,
            message=f"✗ Spec validation failed: {error_msg}",
            block=True  # Block Claude Code from continuing
        )

    log_hook_execution("post_tool_use", result)
    return result


if __name__ == "__main__":
    result = main()
    if not result.success:
        print(result.message, file=sys.stderr)
    else:
        print(result.message)
    sys.exit(result.exit_code())