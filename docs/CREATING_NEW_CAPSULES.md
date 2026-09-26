# Creating New Capsules with YAML Specs

## Quick Start

```bash
# Create a new capsule
python3 tools/capsule_creator.py --name my-project --purpose "One line on what it is for"

# High-privacy capsule (adds a local-only notes/ directory)
python3 tools/capsule_creator.py --name journal --purpose "Personal journal" --privacy high
```

Or just tell the orchestrator: *"create a capsule called my-project"* — the
`/new-capsule` skill runs the same script for you.

**Result:** `capsules/my-project/` with a machine-first YAML spec, an
auto-generated `CLAUDE.md`, a `/my` navigation shortcut, and an entry in
`capsules/CAPSULES_INDEX.md`.

## What You Get Automatically

### 1. YAML Specification
**File:** `specs/current.yaml` — the capsule's source of truth:
- Purpose (what / why / for whom)
- Technical stack and dependencies
- Capabilities, guardrails, vision, relationships
- Sensible defaults and "To be defined" placeholders

### 2. Auto-Generated CLAUDE.md
Generated from `specs/current.yaml` by `tools/generate_claude_md.py`. It
carries an auto-generation warning header — edit the YAML, not the CLAUDE.md.

### 3. Standard Files
- `README.md` — human-readable overview
- `.gitignore` — sensible defaults (secrets, local notes, OS junk)
- `docs/README.md` — documentation home
- `notes/` — only with `--privacy high`; local-only by default

### 4. Navigation Shortcut
A one-word skill at `.claude/skills/<short>/skill.md` so `/my-project`
becomes `/my` (first distinctive word of the capsule name).

## The Workflow

### 1. Create the capsule
```bash
python3 tools/capsule_creator.py --name my-awesome-project --purpose "Web dashboard for analytics"
```

### 2. Initial setup (natural language)
Open the capsule in Claude Code and describe what you're building:

```
You: "This is a web dashboard for analytics. It uses React, Next.js,
      and connects to Supabase. Target users are small business owners."
```

The orchestrator updates `specs/current.yaml` (stack, purpose, audience,
capabilities) as you go.

### 3. Regenerate CLAUDE.md after spec edits
```bash
python3 tools/generate_claude_md.py capsules/my-awesome-project

# Or regenerate every capsule at once
python3 tools/generate_claude_md.py --all
```

### 4. Every future session
- `CLAUDE.md` provides fresh context automatically
- Keep `specs/current.yaml` current as the project evolves

## Starter Templates

For richer starting points, copy a starter from `templates/` instead:

| Template | Use for |
|----------|---------|
| `templates/capsule-base/` | Minimal generic capsule |
| `templates/web-dev-starter/` | Web apps (React/Next.js) |
| `templates/native-ios-app/` | Native iOS (Swift) |
| `templates/react-native-app/` | Cross-platform mobile |
| `templates/automation-starter/` | Scripts and automations |
| `templates/ecommerce-*/` | E-commerce brand operations |

```bash
cp -r templates/web-dev-starter capsules/my-web-app
```

Then fill in the `{{ PLACEHOLDER }}` values in the copied spec files and
write the capsule's `CLAUDE.md` from `templates/capsule-claude-md.template.md`
(or run `tools/generate_claude_md.py` once `specs/current.yaml` is in place).

## Validating Specs

```bash
# Check required fields, data types, cross-file consistency
python3 tools/validate_specs.py my-awesome-project

# Or validate everything
python3 tools/validate_specs.py --all
```

## Tips

- **One capsule per project.** Capsules are the unit of navigation, context
  and credentials (each capsule keeps its own `.env`).
- **Kebab-case names.** `my-cool-project`, not `MyCoolProject`.
- **Edit the YAML, regenerate the CLAUDE.md.** Never hand-edit a generated
  `CLAUDE.md` — your changes will be overwritten.
- **Registry:** add the capsule to `global/config/capsule-registry.yaml`
  (copy `capsule-registry.example.yaml` first) so `/capsules` lists it.
