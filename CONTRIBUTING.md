# Contributing to Huxley

Thanks for your interest in improving Huxley. This framework is built for real use—contributions that enhance orchestration patterns, add valuable agents, or fix bugs are welcome.

---

## Getting Started

1. **Fork the repo** and clone your fork
2. **Run `./setup.sh`** to configure your environment
3. **Read the core docs:**
   - `CLAUDE.md` — Orchestrator context and principles
   - `ARCHITECTURE.md` — System design and patterns
   - `.claude-context/CLAUDE-orchestration.md` — Delegation guide
4. **Make your changes** in a feature branch
5. **Test your changes** — Run the affected agents/workflows
6. **Submit a PR** with a clear description

---

## What We're Looking For

**Good Contributions:**
- New specialist agents with clear, non-overlapping domains
- Improvements to orchestration patterns (routing logic, delegation triggers)
- Useful skills that solve common problems
- Bug fixes with test cases
- Documentation improvements (clarity, examples, missing context)
- Quality pipeline enhancements (better static analysis, new quality gates)
- Tool integrations that agents can use (CLIs, APIs, automation)

**Not Interested:**
- Enterprise bloat (dashboards, GUIs, "management layers")
- Generic "helper" agents without clear domain ownership
- Duplicate functionality that existing agents handle
- Breaking changes to core orchestration patterns without strong rationale
- PRs that ignore the existing code style

---

## Adding a New Agent

Agents live in `.claude/agents/` as markdown files. Here's the pattern:

1. **Create the agent file:**
   ```bash
   touch .claude/agents/your-agent-name.md
   ```

2. **Define the agent** using this template:
   ```markdown
   ---
   name: Your Agent Name
   model: claude-opus-4-6
   ---

   You are the [domain] specialist. You handle [specific responsibilities].

   **Core Capabilities:**
   - Capability 1
   - Capability 2
   - Capability 3

   **Tools:**
   - Tool 1
   - Tool 2

   **Coordinates with:**
   - Agent A (for X)
   - Agent B (for Y)

   **Boundaries:**
   - You DO: [clear scope]
   - You DON'T: [what other agents handle]
   ```

3. **Choose the right model tier:**
   - **Opus** — Coding/development agents (Backend, Frontend, Mobile, etc.)
   - **Sonnet** — Content/creative agents (UI Designer, CMO, Product Strategist)
   - **Haiku** — Research/analysis agents (SEO Analyzer, Business Analyst)

4. **Update the routing map** in `CLAUDE.md` under "Specialist Routing Map"

5. **Test delegation:**
   ```
   "Have [Your Agent Name] do [task in their domain]"
   ```

**Key principles:**
- **Non-overlapping domains** — No two agents should compete for the same work
- **Clear boundaries** — Explicitly state what the agent does AND doesn't do
- **Mesh coordination** — Define which agents this one collaborates with
- **Tool access** — List specific tools/CLIs/skills the agent uses

---

## Adding a New Skill

Skills are reusable workflows in `.claude/skills/`. Two types:

### Simple Skills (Markdown Reference)

```bash
mkdir -p .claude/skills/your-skill-name
```

Write clear instructions in `SKILL.md`:
```markdown
# Your Skill Name

**Purpose:** [One-line description]

**When to use:** [Trigger conditions]

## Quick Reference

[Key commands, patterns, or decision trees]

## Examples

[Concrete usage scenarios]
```

### Tool-Based Skills (CLI Wrapper)

If your skill wraps a CLI tool, SKILL.md should document:
- Tool location (e.g., `tools/your-tool.py`)
- Key commands with flags
- When to use this vs manual implementation
- Example workflows

---

## Adding a New Capsule

Capsules are self-contained project workspaces. Create from template:

```bash
mkdir -p capsules/your-project
cp templates/capsule-claude-md.template.md capsules/your-project/CLAUDE.md
```

Edit `CLAUDE.md` to include:
- **Project overview** — What this builds
- **Tech stack** — Frameworks, languages, key dependencies
- **Specifications** — Requirements, API contracts, data models
- **Key files** — Where things live
- **Agent preferences** — Which specialists handle what

**Don't commit secrets.** Use `.env.example` for credential templates.

---

## Code Style

### Markdown (Agent Definitions, Skills)
- YAML frontmatter for metadata (`name`, `model`)
- Clear sections with headers
- Bullet lists for capabilities, tools, boundaries
- Concrete examples, not just descriptions
- Direct tone. No corporate speak.

### YAML (Configs, Workflows)
- 2 spaces indentation (no tabs)
- Comments for non-obvious choices
- `kebab-case` for keys

### Python (Tools, CLIs)
- Type hints
- 4-layer architecture (parser -> handlers -> client -> connection)
- Graceful degradation, helpful error messages
- stdlib only unless absolutely necessary

### Shell Scripts
- `#!/usr/bin/env bash`
- `set -euo pipefail`
- Assume macOS unless stated otherwise

---

## Pull Request Guidelines

**Title format:**
- `feat: Add [Agent/Skill/Tool Name]` — New functionality
- `fix: [Brief description]` — Bug fixes
- `docs: [What you improved]` — Documentation
- `refactor: [What you cleaned up]` — Code improvement

**PR checklist:**
- [ ] Agent/skill/tool tested manually
- [ ] Documentation updated
- [ ] No secrets committed
- [ ] Follows code style conventions
- [ ] Routing map updated (if adding agent)
- [ ] No breaking changes to core orchestration (or clearly justified)

---

## Code of Conduct

**TL;DR:** Be direct, helpful, and professional.

- Critique the work, not the person
- Assume good intent
- Help newcomers understand the patterns
- Stay on topic

---

## Questions?

- **Open an issue** for bugs or feature requests
- **Check existing docs** before asking (ARCHITECTURE.md, FAQ.md, CLAUDE.md)

**Thanks for contributing.**
