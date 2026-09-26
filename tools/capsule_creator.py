#!/usr/bin/env python3
"""
Huxley Capsule Creator

Creates a complete capsule with:
1. Directory structure (specs, docs, CLAUDE.md, README.md, .gitignore)
2. Navigation shortcut skill (/[short-name])
3. CAPSULES_INDEX.md entry

Usage:
    python3 tools/capsule_creator.py --name "my-project" --purpose "Track project tasks"
    python3 tools/capsule_creator.py --name "journal" --purpose "Personal journal" --privacy high
    python3 tools/capsule_creator.py --name "my-project" --purpose "Track tasks" --skip-nav
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime


# Paths — derived from script location so it works on any machine
CATALYST_ROOT = Path(__file__).resolve().parent.parent
CAPSULES_DIR = CATALYST_ROOT / 'capsules'
SKILLS_DIR = CATALYST_ROOT / '.claude/skills'
CAPSULES_INDEX = CAPSULES_DIR / 'CAPSULES_INDEX.md'


def derive_names(capsule_name: str) -> dict:
    """Derive display name and short nav name from the capsule name."""
    parts = capsule_name.split('-')

    # Display name: Title Case
    display_name = ' '.join(word.capitalize() for word in parts)

    # Short name: first distinctive word (skip common prefixes)
    skip_words = {'my', 'the', 'a', 'an', 'personal', 'private'}
    short_name = None
    for part in parts:
        if part.lower() not in skip_words:
            short_name = part.lower()
            break
    short_name = short_name or parts[0].lower()

    return {
        'display_name': display_name,
        'short_name': short_name,
    }


def create_directory_structure(capsule_path: Path, capsule_name: str,
                               display_name: str, purpose: str, privacy: str):
    """Create capsule directory and standard files."""
    print("📁 Creating directory structure...")

    # Create directories
    capsule_path.mkdir(parents=True, exist_ok=True)
    (capsule_path / 'docs').mkdir(exist_ok=True)
    (capsule_path / 'specs').mkdir(exist_ok=True)

    if privacy == 'high':
        (capsule_path / 'notes').mkdir(exist_ok=True)
        (capsule_path / 'notes' / '.gitkeep').touch()

    # Create specs/current.yaml (the source of truth)
    spec_yaml = f'''name: {display_name}
version: 0.1.0
status: active
last_updated: {datetime.now().strftime("%Y-%m-%d")}

purpose:
  what: {purpose}
  why: To be defined
  for_whom: {{USER_NAME}}

current:
  phase: setup
  health: healthy

technical:
  stack:
    - To be defined
  dependencies:
    external: []
    internal: []

capabilities:
  - Initial setup complete

guardrails:
{"""  - All data stays local
  - No external API calls with sensitive data
  - Privacy-first design""" if privacy == "high" else """  - Standard security practices
  - Follow Huxley conventions"""}

development:
  workflow: Standard Huxley workflow
  tools:
    - Claude Code

vision:
  statement: To be defined
  roadmap: []

relationships:
  feeds_into: []
  consumes_from: []
  shared_with: []
'''
    (capsule_path / 'specs' / 'current.yaml').write_text(spec_yaml)
    print("   ✅ Created: specs/current.yaml")

    # Generate CLAUDE.md from specs — prefer the repo venv (setup.sh installs
    # tools/requirements.txt there, including PyYAML, which
    # generate_claude_md.py imports at module level); the bare system python3
    # typically lacks it and the generator would die at import.
    generator_script = CATALYST_ROOT / 'tools' / 'generate_claude_md.py'
    venv_python = CATALYST_ROOT / '.venv' / 'bin' / 'python3'
    interpreter = str(venv_python) if venv_python.exists() else sys.executable
    result = subprocess.run(
        [interpreter, str(generator_script), str(capsule_path)],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("   ✅ Generated: CLAUDE.md (from specs)")
    else:
        print(f"   ⚠️  CLAUDE.md generation had issues: {result.stderr}")

    # Create README.md
    readme = f'''# {display_name}

{purpose}

## Quick Start
1. Review `specs/current.yaml` for detailed specifications
2. Check `docs/` for documentation
3. Use `/{capsule_name.split('-')[0]}` to navigate here

## Structure
```
{capsule_path.name}/
├── CLAUDE.md        # Auto-generated from specs (don't edit directly)
├── README.md        # This file
├── specs/
│   └── current.yaml # Source of truth - edit this for context engineering
├── docs/            # Documentation
{"├── notes/           # Personal notes (local-only)" if privacy == "high" else ""}
```

## Context Engineering
Edit `specs/current.yaml` to update capsule context, then regenerate:
```bash
{{CATALYST_ROOT}}/.venv/bin/python3 {{CATALYST_ROOT}}/tools/generate_claude_md.py {capsule_path}
```

## Created
{datetime.now().strftime("%Y-%m-%d")}
'''
    (capsule_path / 'README.md').write_text(readme)

    # Create .gitignore
    gitignore_content = '''# Sensitive files
*.secret
*.private
.env.local

# Personal notes (if high privacy)
notes/*.md
!notes/.gitkeep

# OS files
.DS_Store
'''
    (capsule_path / '.gitignore').write_text(gitignore_content)

    # Create docs README
    docs_readme = f'''# {display_name} Documentation

Documentation for {purpose}.

## Contents
- (Add your docs here)
'''
    (capsule_path / 'docs' / 'README.md').write_text(docs_readme)

    print("   ✅ Created: CLAUDE.md, README.md, .gitignore, docs/")


def create_navigation_skill(capsule_name: str, short_name: str, display_name: str,
                            purpose: str, privacy: str):
    """Create navigation shortcut skill."""
    print(f"🔗 Creating navigation shortcut /{short_name}...")

    # Single-word shortcut name - no "navigation" suffix
    skill_dir = SKILLS_DIR / short_name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_content = f'''---
name: {short_name}
description: Navigate to {display_name} capsule - {purpose}
when: User types /{short_name} or mentions {capsule_name}
allowed-tools:
  - Bash
metadata:
  version: "1.0.0"
  capsule: "{capsule_name}"
  privacy: "{privacy}"
  last_updated: "{datetime.now().strftime("%Y-%m-%d")}"
---

# /{short_name} - Navigate to {display_name}

## Purpose
Quick navigation to the {display_name} capsule.

**Capsule purpose:** {purpose}

## Trigger Conditions
- User types `/{short_name}`
- User mentions "{capsule_name}"
- User wants to work on {display_name.lower()}

## What This Skill Does

1. **Navigates to capsule:**
   ```bash
   cd {{CATALYST_ROOT}}/capsules/{capsule_name}
   ```

2. **Confirms navigation:**
   - Reports current location
   - Shows available next steps
   {"- Reminds user of privacy protections" if privacy == "high" else ""}

## Navigation Command

```bash
cd {{CATALYST_ROOT}}/capsules/{capsule_name} && pwd
```

## Response Template

When this skill is invoked, respond with:

```
✓ Navigated to {display_name}

📍 {{CATALYST_ROOT}}/capsules/{capsule_name}

**What would you like to work on?**

- Review README.md for overview
- Check docs/ for documentation
- Start working on your task

{"🔒 Privacy: High - personal notes stay local-only" if privacy == "high" else ""}
```
'''

    (skill_dir / 'skill.md').write_text(skill_content)
    print(f"   ✅ Created: .claude/skills/{short_name}/skill.md")


def update_capsules_index(capsule_name: str, purpose: str,
                          short_name: str, privacy: str):
    """Add entry to CAPSULES_INDEX.md (created on first use)."""
    print("📋 Updating CAPSULES_INDEX.md...")

    if not CAPSULES_INDEX.exists():
        CAPSULES_INDEX.write_text(
            "# Capsules Index\n\n"
            "Master registry of all capsules. One entry per capsule; "
            "appended automatically by tools/capsule_creator.py.\n"
        )

    entry = f'''
### {capsule_name}/
**Purpose:** {purpose}
**Nav:** /{short_name}
{"**Privacy:** High - local-only by default" if privacy == "high" else ""}
'''

    with open(CAPSULES_INDEX, 'a') as f:
        f.write(entry)

    print("   ✅ Added entry to CAPSULES_INDEX.md")


def main():
    parser = argparse.ArgumentParser(description='Create a new Huxley capsule')

    parser.add_argument('--name', required=True, help='Capsule name (kebab-case)')
    parser.add_argument('--purpose', required=True, help='Brief description of purpose')
    parser.add_argument('--privacy', default='normal', choices=['normal', 'high'],
                        help='Privacy level (default: normal)')
    parser.add_argument('--skip-nav', action='store_true',
                        help='Skip navigation skill creation')

    args = parser.parse_args()

    # Normalize capsule name
    capsule_name = args.name.lower().replace(' ', '-').replace('_', '-')
    capsule_path = CAPSULES_DIR / capsule_name

    # Check if exists
    if capsule_path.exists():
        print(f"❌ Capsule already exists: {capsule_path}")
        sys.exit(1)

    # Derive names
    names = derive_names(capsule_name)
    display_name = names['display_name']
    short_name = names['short_name']

    print("=" * 60)
    print(f"Creating Capsule: {display_name}")
    print("=" * 60)
    print(f"  Name:     {capsule_name}")
    print(f"  Purpose:  {args.purpose}")
    print(f"  Privacy:  {args.privacy}")
    print(f"  Nav:      /{short_name}")
    print("=" * 60)
    print()

    # Step 1: Directory structure with specs/current.yaml
    create_directory_structure(capsule_path, capsule_name, display_name,
                               args.purpose, args.privacy)

    # Step 2: Navigation skill
    if not args.skip_nav:
        create_navigation_skill(capsule_name, short_name, display_name,
                                args.purpose, args.privacy)
    else:
        print("   ⏭️  Skipping navigation skill")

    # Step 3: Update index
    update_capsules_index(capsule_name, args.purpose, short_name, args.privacy)

    # Summary
    print()
    print("=" * 60)
    print("✅ Capsule Created Successfully!")
    print("=" * 60)
    print(f"📁 Location:   {capsule_path}")
    print(f"🔗 Navigation: /{short_name}")
    if args.privacy == 'high':
        print("🔒 Privacy:    High - notes stay local-only")
    print()
    print("Next steps:")
    print("  1. Edit specs/current.yaml to customize context (then regenerate CLAUDE.md)")
    print(f"  2. Use /{short_name} to navigate here")


if __name__ == '__main__':
    main()
