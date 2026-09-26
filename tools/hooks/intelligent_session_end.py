#!/usr/bin/env python3
"""
Intelligent SessionEnd Hook - Updates YAML specs from natural language + code changes

This hook:
1. Analyzes conversation context from the session
2. Reviews git diff to see what actually changed
3. Uses Claude API to intelligently update specs/current.yaml
4. Regenerates CLAUDE.md from updated YAML
5. Appends session summary to context/session_log.md
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import os
import anthropic

# Add hook utilities to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import HookResult, get_catalyst_root, log_hook_execution


def get_git_diff(cwd: Path) -> str:
    """Get git diff for uncommitted changes"""
    try:
        result = subprocess.run(
            ['git', 'diff', 'HEAD'],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Error getting git diff: {e}"


def get_git_status(cwd: Path) -> str:
    """Get git status"""
    try:
        result = subprocess.run(
            ['git', 'status', '--short'],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout
    except Exception as e:
        return f"Error getting git status: {e}"


def load_yaml_spec(capsule_path: Path) -> dict:
    """Load current YAML spec"""
    import yaml

    spec_file = capsule_path / "specs" / "current.yaml"
    if not spec_file.exists():
        return None

    try:
        with open(spec_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML: {e}", file=sys.stderr)
        return None


def save_yaml_spec(capsule_path: Path, spec: dict) -> bool:
    """Save updated YAML spec"""
    import yaml

    spec_file = capsule_path / "specs" / "current.yaml"
    spec_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(spec_file, 'w') as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return True
    except Exception as e:
        print(f"Error saving YAML: {e}", file=sys.stderr)
        return False


def update_yaml_with_claude(spec: dict, git_diff: str, git_status: str, session_info: dict) -> dict:
    """Use Claude API to intelligently update YAML based on session context"""

    # Get API key from environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Warning: No ANTHROPIC_API_KEY found, skipping intelligent update", file=sys.stderr)
        return spec

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Construct prompt for Claude
        import yaml
        current_yaml = yaml.dump(spec, default_flow_style=False, sort_keys=False)

        prompt = f"""You are analyzing a Huxley capsule session to update its specifications.

**Current YAML Spec:**
```yaml
{current_yaml}
```

**Git Status:**
```
{git_status}
```

**Git Diff (changes made this session):**
```diff
{git_diff[:10000]}  # Limit diff size
```

**Session Info:**
- Capsule: {session_info.get('capsule', 'unknown')}
- Duration: Session just ended

**Task:**
Analyze the code changes and update the YAML spec to reflect:

1. **New capabilities added** - If new features were implemented, add to `capabilities` list
2. **Dependencies changed** - If new packages/services were added, update `technical.dependencies`
3. **Architecture modifications** - If major structural changes, update `technical.architecture.components`
4. **Status updates** - Update `current.last_updated` to today's date
5. **Auto metadata** - Update `_auto.last_session`, `_auto.last_commit`

**Important Rules:**
- Only update fields that clearly changed based on the git diff
- Preserve all existing data - don't remove things
- Be conservative - if unsure, don't change it
- Keep descriptions concise and factual
- Return ONLY the updated YAML, no explanations

**Output Format:**
Return the complete updated YAML spec (not just changes, the full spec).
"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Extract YAML from response
        response_text = message.content[0].text

        # Find YAML block
        if "```yaml" in response_text:
            yaml_start = response_text.find("```yaml") + 7
            yaml_end = response_text.find("```", yaml_start)
            yaml_text = response_text[yaml_start:yaml_end].strip()
        elif "```" in response_text:
            yaml_start = response_text.find("```") + 3
            yaml_end = response_text.find("```", yaml_start)
            yaml_text = response_text[yaml_start:yaml_end].strip()
        else:
            yaml_text = response_text.strip()

        # Parse updated YAML
        updated_spec = yaml.safe_load(yaml_text)

        # Ensure _auto section exists and is updated
        if '_auto' not in updated_spec:
            updated_spec['_auto'] = {}

        updated_spec['_auto']['last_session'] = datetime.now().isoformat()

        # Get last commit hash
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                updated_spec['_auto']['last_commit'] = result.stdout.strip()[:7]
        except:
            pass

        return updated_spec

    except Exception as e:
        print(f"Error calling Claude API: {e}", file=sys.stderr)
        return spec


def regenerate_claude_md(capsule_path: Path) -> bool:
    """Regenerate CLAUDE.md from YAML"""
    catalyst_root = get_catalyst_root()
    generator_script = catalyst_root / "tools" / "generate_claude_md.py"

    if not generator_script.exists():
        print("Warning: generate_claude_md.py not found", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            ['python3', str(generator_script), str(capsule_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error regenerating CLAUDE.md: {e}", file=sys.stderr)
        return False


def append_session_log(capsule_path: Path, summary: str, git_diff: str):
    """Append session summary to context/session_log.md"""
    context_dir = capsule_path / "context"
    context_dir.mkdir(exist_ok=True)

    log_file = context_dir / "session_log.md"

    # Create log file if it doesn't exist
    if not log_file.exists():
        with open(log_file, 'w') as f:
            f.write("# Session History\n\n")
            f.write("Auto-generated log of development sessions.\n\n")
            f.write("---\n\n")

    # Append new session
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Extract changed files from git diff
    changed_files = []
    for line in git_diff.split('\n'):
        if line.startswith('diff --git'):
            file_path = line.split()[-1].replace('b/', '')
            changed_files.append(file_path)

    with open(log_file, 'a') as f:
        f.write(f"## Session: {timestamp}\n\n")
        f.write(f"**Changes:**\n{summary}\n\n")

        if changed_files:
            f.write("**Files modified:**\n")
            for file in changed_files[:10]:  # Limit to 10 files
                f.write(f"- `{file}`\n")
            if len(changed_files) > 10:
                f.write(f"- *...and {len(changed_files) - 10} more files*\n")
            f.write("\n")

        f.write("---\n\n")


def main():
    # Read hook input from stdin (JSON format)
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        hook_input = {}

    cwd = Path(hook_input.get("cwd", Path.cwd()))
    session_id = hook_input.get("session_id", "unknown")

    # Determine capsule from cwd
    catalyst_root = get_catalyst_root()

    # Check if we're in a capsule
    if not str(cwd).startswith(str(catalyst_root / "capsules")):
        return HookResult(success=True, message="Not in a capsule, skipping spec update")

    try:
        relative = cwd.relative_to(catalyst_root / "capsules")
        capsule_name = str(relative.parts[0]) if relative.parts else None
        capsule_path = catalyst_root / "capsules" / capsule_name
    except:
        return HookResult(success=True, message="Could not determine capsule")

    if not capsule_name:
        return HookResult(success=True, message="Not in a capsule directory")

    print(f"\n🔄 Updating specs for {capsule_name}...", file=sys.stderr)

    # Get git changes
    git_diff = get_git_diff(capsule_path)
    git_status = get_git_status(capsule_path)

    if not git_diff.strip() and not git_status.strip():
        return HookResult(success=True, message=f"No changes detected in {capsule_name}")

    # Load current spec
    spec = load_yaml_spec(capsule_path)
    if spec is None:
        return HookResult(success=True, message=f"No YAML spec found for {capsule_name} (not yet migrated)")

    # Update YAML with Claude
    session_info = {
        'capsule': capsule_name,
        'session_id': session_id
    }

    updated_spec = update_yaml_with_claude(spec, git_diff, git_status, session_info)

    # Save updated YAML
    if not save_yaml_spec(capsule_path, updated_spec):
        return HookResult(success=False, message="Failed to save updated YAML", block=False)

    print(f"  ✅ Updated specs/current.yaml", file=sys.stderr)

    # Regenerate CLAUDE.md
    if regenerate_claude_md(capsule_path):
        print(f"  ✅ Regenerated CLAUDE.md", file=sys.stderr)
    else:
        print(f"  ⚠️  Failed to regenerate CLAUDE.md", file=sys.stderr)

    # Append session log
    summary = "Session updates applied"
    append_session_log(capsule_path, summary, git_diff)
    print(f"  ✅ Updated session log", file=sys.stderr)

    result = HookResult(success=True, message=f"✓ Specs updated for {capsule_name}")
    log_hook_execution("intelligent_session_end", result)
    return result


if __name__ == "__main__":
    result = main()
    if not result.success:
        print(result.message, file=sys.stderr)
    else:
        print(result.message)
    sys.exit(result.exit_code())
