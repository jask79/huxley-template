#!/usr/bin/env python3
"""
Add Agent Memory System sections to all agent files that don't have one.
"""

import os
import re
from pathlib import Path

AGENTS_DIR = Path("{{CATALYST_ROOT}}/.claude/agents")

# Generic memory section template
MEMORY_SECTION = """
## Agent Memory System

**You have access to persistent memory for learning and improvement.**

### Memory Capabilities

**Before starting work:**
- Use `search_memories` to find relevant patterns from past work
- Query: "[technology/pattern] implementation patterns"
- Example: Search for patterns relevant to your domain (authentication, animations, migrations, etc.)

**After completing work:**
- Store successful patterns for future reuse
- Use `create_memory` for novel or particularly effective approaches
- Include: technology stack, approach taken, why it worked
- Tag appropriately for easy retrieval

**Memory Quality:**
- ✅ Store: Successful integration patterns, novel solutions, anti-patterns (what failed)
- ❌ Don't store: One-off implementations, trivial patterns, project-specific details

**Example workflow:**
```
1. Task: Receive implementation request
2. Search: search_memories(query="<relevant domain> implementation patterns")
3. Review: Apply learned patterns if found
4. Implement: Complete the task with learned context
5. Store: If approach was novel or particularly effective, create_memory(...) for future
```

**You're not just completing tasks - you're building expertise over time.**

---
"""

def has_memory_section(content: str) -> bool:
    """Check if file already has Agent Memory System section."""
    return "## Agent Memory System" in content or "search_memories" in content

def add_memory_section(file_path: Path) -> bool:
    """Add memory section to an agent file."""
    print(f"Processing: {file_path.name}")

    # Read file
    content = file_path.read_text()

    # Check if already has memory section
    if has_memory_section(content):
        print(f"  ✓ Already has memory section, skipping")
        return False

    # Insert before the last line (usually a closing statement)
    lines = content.split('\n')

    # Find insertion point (before last non-empty line or before final statement)
    insertion_index = len(lines)

    # Look for common ending patterns
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if line and not line.startswith('---'):
            insertion_index = i
            break

    # Insert memory section
    lines.insert(insertion_index, MEMORY_SECTION.rstrip())

    # Write back
    new_content = '\n'.join(lines)
    file_path.write_text(new_content)

    print(f"  ✓ Added memory section")
    return True

def main():
    """Process all agent files."""
    agent_files = sorted(AGENTS_DIR.glob("*.md"))

    print(f"Found {len(agent_files)} agent files\n")

    modified = 0
    skipped = 0

    for agent_file in agent_files:
        if add_memory_section(agent_file):
            modified += 1
        else:
            skipped += 1

    print(f"\n✅ Complete!")
    print(f"Modified: {modified}")
    print(f"Skipped: {skipped}")
    print(f"Total: {len(agent_files)}")

if __name__ == "__main__":
    main()
