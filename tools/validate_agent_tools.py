#!/usr/bin/env python3
"""
Validate that all agent files have tools configured.

This script checks all agents in .claude/agents/ and ensures they have
the 'tools' field in their frontmatter. Agents without tools cannot
perform file operations and will silently fail.

Usage:
    python3 validate_agent_tools.py

Exit codes:
    0 - All agents have tools configured
    1 - One or more agents missing tools field
"""

import os
import sys
import re
from pathlib import Path

def parse_frontmatter(file_path):
    """Extract YAML frontmatter from agent markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match YAML frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, flags=re.DOTALL)
    if not match:
        return None

    try:
        import yaml
        return yaml.safe_load(match.group(1))
    except ImportError:
        print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
        sys.exit(2)

def validate_agents(agents_dir):
    """Check all agent files for tools configuration."""
    agents_dir = Path(agents_dir)

    if not agents_dir.exists():
        print(f"ERROR: Agents directory not found: {agents_dir}", file=sys.stderr)
        return False

    all_valid = True
    missing_tools = []

    for agent_file in sorted(agents_dir.glob("*.md")):
        frontmatter = parse_frontmatter(agent_file)

        if not frontmatter:
            print(f"⚠️  {agent_file.name}: No frontmatter found", file=sys.stderr)
            all_valid = False
            continue

        # Check for tools field
        if 'tools' not in frontmatter:
            print(f"❌ {agent_file.name}: Missing 'tools' field", file=sys.stderr)
            missing_tools.append(agent_file.name)
            all_valid = False
        elif not frontmatter['tools']:
            print(f"❌ {agent_file.name}: Empty 'tools' field", file=sys.stderr)
            missing_tools.append(agent_file.name)
            all_valid = False
        else:
            tools = frontmatter['tools']
            if isinstance(tools, str):
                # Single wildcard or tool
                print(f"✅ {agent_file.name}: tools: {tools}")
            elif isinstance(tools, list):
                # List of tools
                print(f"✅ {agent_file.name}: tools: {', '.join(tools[:3])}{'...' if len(tools) > 3 else ''}")
            else:
                print(f"⚠️  {agent_file.name}: Invalid tools format: {type(tools)}", file=sys.stderr)
                all_valid = False

    if missing_tools:
        print(f"\n❌ VALIDATION FAILED: {len(missing_tools)} agent(s) missing tools", file=sys.stderr)
        print("\nAgents without tools cannot:", file=sys.stderr)
        print("  • Read files", file=sys.stderr)
        print("  • Write files", file=sys.stderr)
        print("  • Edit files", file=sys.stderr)
        print("  • Execute bash commands", file=sys.stderr)
        print("  • Use git", file=sys.stderr)
        print("\nAdd minimum tools to each agent:", file=sys.stderr)
        print("  tools: read, write, edit, bash, grep, glob, webfetch, git, mcp:context7", file=sys.stderr)
    else:
        print(f"\n✅ All agents have tools configured")

    return all_valid

def main():
    # Default to Huxley agents directory
    catalyst_root = Path(__file__).resolve().parent.parent
    agents_dir = catalyst_root / ".claude" / "agents"

    # Allow override via argument
    if len(sys.argv) > 1:
        agents_dir = Path(sys.argv[1])

    print(f"Validating agents in: {agents_dir}\n")

    if validate_agents(agents_dir):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
