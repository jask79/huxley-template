# Skills System Guide

Skills are specialized knowledge bundles that give agents domain expertise. An agent without skills is a generalist; an agent *with* skills has access to curated documentation, patterns, and workflow instructions that make it effective in a specific domain.

## What Are Skills

A skill is a directory containing a `SKILL.md` file and optionally reference documents. The `SKILL.md` file tells Claude Code:

- What the skill does
- When it should activate
- What tools it can use
- Step-by-step instructions for the workflow

Skills are referenced from agent markdown files. When an agent is invoked, it sees its skill references and can follow the instructions within them.

Skills are **not** plugins, packages, or executables. They are structured context -- documentation that an agent reads and follows. Their power comes from giving agents precise, domain-specific instructions instead of relying on general training knowledge.

## Skill Anatomy

A skill lives in `.claude/skills/<skill-name>/`:

```
.claude/skills/new-capsule/
├── SKILL.md          # Skill definition (required)
└── (reference docs)  # Optional supporting documentation
```

### SKILL.md Structure

```markdown
---
name: new-capsule
description: Create a new Huxley capsule with navigation shortcut
when: User requests a new capsule, or says "create capsule [name]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Task
metadata:
  version: "2.0.0"
  automation: "Full"
  creates:
    - Capsule directory structure
    - Navigation shortcut skill
    - CAPSULES_INDEX.md entry
---

# Capsule Creator Skill

## Purpose
[What this skill accomplishes]

## When to Use
[Trigger conditions -- what user requests activate this skill]

## Required Inputs
[What information the skill needs from the user or orchestrator]

## Steps
1. [Step-by-step procedure the agent follows]
2. [Each step should be concrete and actionable]
3. [Include actual commands, file paths, or templates]

## Output
[What the skill produces when complete]

## Error Handling
[What to do when things go wrong]
```

### Frontmatter Fields

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Skill identifier (kebab-case) |
| `description` | Yes | One-line description of what the skill does |
| `when` | Yes | Natural language trigger conditions |
| `allowed-tools` | No | Restrict which Claude Code tools this skill can use |
| `metadata` | No | Version, automation level, and other metadata |

### Body Content

The body is free-form markdown with workflow instructions. Write it as if you are explaining a procedure to a competent developer who has never seen your system before. Be specific about:

- File paths (use absolute paths)
- Command syntax (show exact commands)
- Expected outputs (what success looks like)
- Error conditions (what can go wrong and how to handle it)

## Community Skills

The [skills.sh](https://skills.sh) ecosystem provides community-maintained skills that you can install into Huxley.

### Finding Skills

Search for skills using `npx`:

```bash
npx skills find <query>
```

This searches the skills.sh registry and returns matching skill packages.

### Installing Skills

Community skills are git repositories. The installation process:

1. **Clone the repository** into `.claude/skills/community/`:

```bash
git clone https://github.com/<org>/<repo>.git .claude/skills/community/<repo-name>
```

2. **Symlink specific skills** into `.claude/skills/`:

```bash
ln -s .claude/skills/community/<repo-name>/<skill-path> .claude/skills/<skill-name>
```

Community skill repositories often contain multiple skills. You symlink only the ones you want.

### Installed Community Sources

Huxley includes skills from these community repositories:

| Repository | Skills Provided |
|---|---|
| `vercel-labs` | Vercel deployment patterns |
| `anthropic` | Anthropic best practices |
| `avdlee-swiftui` | SwiftUI expert reference (14 docs) |
| `dimillian-skills` | Liquid Glass, Swift Concurrency, SwiftUI patterns |
| `expo` | Expo SDK patterns |
| `better-auth` | Authentication best practices |
| `addyosmani-web-quality` | SEO checklist, Core Web Vitals optimization |
| `wondelai-skills` | Award-winning design methodology, CRO process |
| `kv0906-cc-skills` | Premium frontend design patterns |
| `cloudflare-skills` | Web performance auditing |
| `remotion` | Programmatic video generation |
| `andreev-danila-skills` | Reanimated/Skia performance |
| `pluginagentmarketplace-rn` | React Native animation patterns |

## Creating Custom Skills

### Step 1: Create the skill directory

```bash
mkdir -p .claude/skills/my-skill
```

### Step 2: Write SKILL.md

```markdown
---
name: my-skill
description: What this skill does
when: When the user asks for X or says "do Y"
allowed-tools:
  - Bash
  - Read
  - Write
metadata:
  version: "1.0.0"
---

# My Skill

## Purpose
Automate the process of [specific thing].

## When to Use
- "Do [thing]"
- "Set up [thing]"

## Required Inputs
- **name**: The name of the thing (kebab-case)
- **type**: Optional type parameter (defaults to "standard")

## Steps

### 1. Validate inputs
Ensure the name is kebab-case and does not conflict with existing things.

### 2. Create the structure
```bash
mkdir -p /path/to/things/<name>
```

### 3. Generate configuration
Write the config file:
```yaml
name: <name>
type: <type>
created: <current date>
```

### 4. Register
Add an entry to the index file at `/path/to/index.md`.

## Output
- Directory created at `/path/to/things/<name>/`
- Configuration file written
- Index updated

## Error Handling
- If name conflicts: suggest alternative name
- If directory creation fails: check permissions
```

### Step 3: Add reference documents (optional)

If your skill needs supporting documentation, add files to the skill directory:

```
.claude/skills/my-skill/
├── SKILL.md
├── reference/
│   ├── api-patterns.md
│   └── common-mistakes.md
└── templates/
    └── config.template.yaml
```

Reference these from your SKILL.md body:

```markdown
### Reference
See `reference/api-patterns.md` for API design patterns used in this workflow.
```

## Wiring Skills to Agents

A skill is inert until an agent references it. To wire a skill to an agent, add a section to the agent's markdown file in `.claude/agents/`:

```markdown
## Skills

### Capsule Creator
**Skill location:** `.claude/skills/new-capsule/SKILL.md`
Use this skill when the user asks to create a new capsule. Follow the SKILL.md instructions exactly.

### Apple Provisioning
**Skill location:** `.claude/skills/apple-provision/SKILL.md`
Use this skill for Apple Developer portal automation -- provisioning profiles, bundle IDs, and certificates.
```

### Wiring Guidelines

- **Wire to the right agent.** A skill for iOS testing should be wired to the Mobile Developer, not the Backend Developer.
- **Wire to multiple agents if appropriate.** A design skill might be wired to both the UI Designer and the Frontend Developer if both need it.
- **Include usage guidance.** Do not just link the SKILL.md -- add a sentence explaining *when* the agent should reach for it.
- **Check coverage.** After installing a new skill, review all agents that work in that domain. It is a common mistake to wire a skill to one agent and forget another that also needs it.

### Example: Complete Agent Skill Section

From the Mobile Developer agent file:

```markdown
## Skills

### SwiftUI Expert
**Skill location:** `.claude/skills/community/avdlee-swiftui/`
14 reference documents covering SwiftUI patterns. Consult before implementing any SwiftUI view.

### iOS Device Deployment
**Skill location:** `.claude/skills/ios-device-deployment/SKILL.md`
Use for deploying builds to physical devices via Xcode CLI.

### iOS Testing
**Skill location:** `.claude/skills/ios-testing/SKILL.md`
Automated iOS testing via simulator -- screenshots, UI interaction, accessibility audits.

### Apple Provisioning
**Skill location:** `.claude/skills/apple-provision/SKILL.md`
Automate provisioning profiles, bundle IDs, and capabilities via App Store Connect API.
```

### Verifying Skill Wiring

After wiring, test by asking the orchestrator to do something that should trigger the skill:

```
"Create a new capsule called my-project"
```

The orchestrator should route this to an agent that has the `new-capsule` skill wired, and the agent should follow the SKILL.md instructions.

If the agent does not use the skill, check:
1. Is the skill referenced in the agent's markdown file?
2. Does the skill's `when` field match the request?
3. Is the orchestrator routing to the correct agent?
```

---

All four files are complete. Here is a summary of what each covers:

- **`ARCHITECTURE.md`** -- System overview, mermaid diagram, all six core concepts (capsules, agents, context loading, hooks, governance, skills), a detailed request flow walkthrough, annotated directory structure, customization guide, and design decision rationale.
- **`docs/AGENTS.md`** -- How agents work mechanically, annotated agent file anatomy, step-by-step creation guide, routing (name resolution + domain routing), model tier breakdown, full 29-agent roster table grouped by category, and mesh routing explanation.
- **`docs/HOOKS.md`** -- What hooks are, all six event types with descriptions, input/output protocol, every built-in Huxley hook, step-by-step custom hook creation guide, and full `settings.json` configuration reference.
- **`docs/SKILLS.md`** -- What skills are, SKILL.md anatomy with frontmatter reference, community skill discovery and installation, custom skill creation walkthrough, and detailed wiring-to-agents instructions with examples.

All files use `{{ORCHESTRATOR_NAME}}`, `{{USER_NAME}}`, and `{{PEER_AGENT_NAME}}` placeholders where personal names would appear.

