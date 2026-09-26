#!/usr/bin/env python3
"""
Generate navigation skill files for all Huxley capsules.

Scans capsules/ directory and creates /capsulename nav skills for any
capsule that doesn't already have one. Re-run whenever new capsules are added.

Usage:
    python3 scripts/generate-nav-skills.py          # generate missing skills
    python3 scripts/generate-nav-skills.py --force   # regenerate all (overwrites)
    python3 scripts/generate-nav-skills.py --dry-run # preview what would be created
"""

import os
import re
import sys
from pathlib import Path
from datetime import date

CATALYST_ROOT = Path(__file__).resolve().parent.parent
CAPSULES_DIR = CATALYST_ROOT / "capsules"
SKILLS_DIR = CATALYST_ROOT / ".claude" / "skills"
TODAY = date.today().isoformat()


def extract_description(capsule_path: Path) -> str:
    """Extract a short description from capsule's CLAUDE.md or capsule.json."""
    claude_md = capsule_path / "CLAUDE.md"
    if claude_md.exists():
        text = claude_md.read_text()
        # Look for ## Purpose section
        purpose_match = re.search(r"## Purpose\s*\n(.+?)(?:\n\n|\n##)", text, re.DOTALL)
        if purpose_match:
            # Take first sentence
            purpose = purpose_match.group(1).strip()
            first_sentence = re.split(r"(?<=[.!?])\s", purpose)[0]
            # Truncate to ~100 chars
            if len(first_sentence) > 120:
                first_sentence = first_sentence[:117] + "..."
            return first_sentence

        # Fallback: look for first line after # heading
        heading_match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()

    capsule_json = capsule_path / "capsule.json"
    if capsule_json.exists():
        import json
        try:
            data = json.loads(capsule_json.read_text())
            if "description" in data:
                return data["description"]
        except (json.JSONDecodeError, KeyError):
            pass

    return "Huxley capsule"


def prettify_name(dirname: str) -> str:
    """Convert directory name to display name (e.g., 'acme-store' -> 'Acme Store')."""
    return dirname.replace("-", " ").title()


def generate_skill(capsule_name: str, description: str) -> str:
    """Generate skill.md content for a capsule navigation skill."""
    pretty = prettify_name(capsule_name)
    return f"""---
name: {capsule_name}
description: "Navigate to {pretty} capsule — {description}"
when: User types /{capsule_name} or mentions {capsule_name}
allowed-tools:
  - Bash
metadata:
  version: "1.0.0"
  capsule: "{capsule_name}"
  privacy: "normal"
  generated: true
  last_updated: "{TODAY}"
---

# /{capsule_name} — Navigate to {pretty}

## Purpose
Quick navigation to the **{pretty}** capsule.

**Capsule purpose:** {description}

## Trigger Conditions
- User types `/{capsule_name}`
- User mentions "{capsule_name}" or "{pretty.lower()}"
- User wants to work on {pretty}

## What This Skill Does

1. **Navigates to capsule:**
   ```bash
   cd {{{{CATALYST_ROOT}}}}/capsules/{capsule_name}
   ```

2. **Loads context** via `nav_with_context.py`

3. **Confirms navigation** with available next steps

## Navigation Command

```bash
cd {{{{CATALYST_ROOT}}}}/capsules/{capsule_name} && pwd
```

Then load capsule context:
```bash
python3 {{{{CATALYST_ROOT}}}}/tools/nav_with_context.py {capsule_name}
```

## Response Template

When this skill is invoked, respond with:

```
Navigated to {pretty} 📍

{{{{CATALYST_ROOT}}}}/capsules/{capsule_name}

**What would you like to work on?**
```

Then read the capsule's CLAUDE.md and offer relevant next steps.
"""


def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if not CAPSULES_DIR.exists():
        print(f"❌ Capsules directory not found: {CAPSULES_DIR}")
        sys.exit(1)

    # Get all capsule directories
    capsules = sorted(
        d.name for d in CAPSULES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    created = 0
    skipped = 0
    total = len(capsules)

    print(f"📦 Found {total} capsules\n")

    for capsule_name in capsules:
        skill_dir = SKILLS_DIR / capsule_name
        skill_file = skill_dir / "skill.md"

        if skill_file.exists() and not force:
            print(f"  ⏭️  {capsule_name:30s} — skill already exists")
            skipped += 1
            continue

        capsule_path = CAPSULES_DIR / capsule_name
        description = extract_description(capsule_path)
        content = generate_skill(capsule_name, description)

        if dry_run:
            print(f"  🔵 {capsule_name:30s} — would create ('{description[:60]}...')")
            created += 1
            continue

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content)
        print(f"  ✅ {capsule_name:30s} — created ('{description[:60]}...')")
        created += 1

    print(f"\n{'📋 DRY RUN — ' if dry_run else ''}Summary: {created} created, {skipped} skipped, {total} total")

    if not dry_run and created > 0:
        print(f"\n🎯 {created} new nav skills ready! Type /<capsulename> to jump to any capsule.")


if __name__ == "__main__":
    main()
