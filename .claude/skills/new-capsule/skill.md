---
name: new-capsule
description: Create a new Huxley capsule with navigation shortcut
when: User requests a new capsule, or says "create capsule [name]" or "new capsule"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Task
metadata:
  version: "4.0.0"
  automation: "Full"
  creates:
    - Capsule directory structure
    - Navigation shortcut skill
    - CAPSULES_INDEX.md entry
---

# Capsule Creator Skill

## Purpose
Create complete Huxley capsules with all standard integrations:
1. **Directory structure** with CLAUDE.md, README.md
2. **Navigation shortcut** (`/[name]` command)
3. **Index registration** in CAPSULES_INDEX.md

## When to Use
- "Create a new capsule called [name]"
- "New capsule for [purpose]"
- "Set up a capsule for [project]"

## Required Inputs
- **name**: Capsule name (kebab-case, e.g., "my-project")
- **purpose**: Brief description of what the capsule is for
- **privacy** (optional): "normal" or "high" (default: normal)

## Execution Flow

### Step 1: Validate & Derive Names
```python
# From capsule name "my-cool-project":
capsule_name = "my-cool-project"
short_name = "cool"  # First unique word for nav shortcut
display_name = "My Cool Project"
nav_command = "/cool"
```

### Step 2: Create Capsule Directory with YAML Spec
```bash
mkdir -p {{CATALYST_ROOT}}/capsules/[capsule-name]/specs
mkdir -p {{CATALYST_ROOT}}/capsules/[capsule-name]/docs
```

Create standard files:
- `specs/current.yaml` - Source of truth for context engineering
- `CLAUDE.md` - Auto-generated from specs (via generate_claude_md.py)
- `README.md` - Human-readable overview
- `.gitignore` - Standard ignores
- `docs/` - Documentation directory

### Step 3: Create Navigation Shortcut
Create skill at `.claude/skills/[short]/skill.md`:

**IMPORTANT: Shortcut names are ONE WORD ONLY. Never include "navigate", "navigation", or similar words.**

```yaml
---
name: [short]
description: Navigate to [Display Name] capsule
when: User types /[short] or mentions [capsule-name]
allowed-tools:
  - Bash
metadata:
  capsule: "[capsule-name]"
---
```

### Step 4: Update CAPSULES_INDEX.md
Append entry:
```markdown
### [capsule-name]/
**Purpose:** [purpose]
**Nav:** /[short]
```

### Step 5: Report Success
```
✅ Capsule Created: [Display Name]

📁 Location: {{CATALYST_ROOT}}/capsules/[capsule-name]
🔗 Navigation: /[short]

Next steps:
1. Edit specs/current.yaml to customize context
2. Use /[short] to navigate here
```

## Full Automation Script

Run everything via:
```bash
# Standard capsule
python3 {{CATALYST_ROOT}}/tools/capsule_creator.py \
  --name "[capsule-name]" \
  --purpose "[description]" \
  --privacy "normal|high"

# Skip the navigation skill
python3 {{CATALYST_ROOT}}/tools/capsule_creator.py \
  --name "[capsule-name]" \
  --purpose "[description]" \
  --skip-nav
```

## Examples

**Example 1: Simple capsule**
```
User: Create a capsule for tracking my fitness goals
{{ORCHESTRATOR_NAME}}: Creating "fitness-tracker" capsule...

✅ Capsule Created: Fitness Tracker

📁 Location: capsules/fitness-tracker
🔗 Navigation: /fitness
```

**Example 2: Privacy-sensitive capsule**
```
User: Create a capsule for my therapy notes, high privacy
{{ORCHESTRATOR_NAME}}: Creating "therapy-notes" capsule with high privacy...

✅ Capsule Created: Therapy Notes

📁 Location: capsules/therapy-notes
🔗 Navigation: /therapy
🔒 Privacy: High (local-only by default)
```

## Directory Structure Created

```
capsules/[capsule-name]/
├── CLAUDE.md           # Auto-generated from specs (don't edit directly)
├── README.md           # Human-readable overview
├── .gitignore          # Ignore sensitive files
├── specs/
│   └── current.yaml    # Source of truth for context engineering
├── docs/
│   └── README.md       # Documentation home
└── notes/              # (if high privacy)
    └── .gitkeep
```

## Context Engineering with YAML Specs

Each capsule uses **YAML specifications** for context engineering. The `specs/current.yaml` is the source of truth:

```yaml
name: [Display Name]
version: 0.1.0
status: active
last_updated: [date]

purpose:
  what: [purpose description]
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
  - Standard security practices
  - Follow Huxley conventions

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
```

## Regenerating CLAUDE.md

After editing `specs/current.yaml`, regenerate CLAUDE.md:
```bash
python3 {{CATALYST_ROOT}}/tools/generate_claude_md.py {{CATALYST_ROOT}}/capsules/[capsule-name]
```

Or regenerate all capsules:
```bash
python3 {{CATALYST_ROOT}}/tools/generate_claude_md.py --all
```

## Integration Points

- **nav.py**: Capsule auto-discovered for keyword navigation
- **CAPSULES_INDEX.md**: Master registry of all capsules (created on first use)

## Error Handling

- If capsule already exists → Ask to overwrite or pick new name
- If `generate_claude_md.py` reports issues → Create `CLAUDE.md` by hand from `templates/capsule-claude-md.template.md`
