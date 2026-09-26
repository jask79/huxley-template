# System Architecture (Lazy-Loaded Section)
<!-- Template version: 2026-09-24 -->

## How The System Currently Works

### Architecture Pattern: Capsules
- Each project = self-contained capsule with full lifecycle folders
- Immutable once deployed for stability
- Clean isolation between projects
- **Framework Structure**: Every capsule includes:
  - `standards.yaml` - Quality/compliance framework
  - `product.yaml` - Capability roadmap & vision
  - `specs/current.yaml` & `specs/next.yaml` - Implementation specifications
  - `context/` - Decisions, patterns, and evolution documentation

### Workflow Pattern: Unified Pipeline
- Streamlined build process with consistent quality standards
- Automated validation and deployment pipeline
- **Spec-Kit Enhanced Tools**: Schema validation, documentation generation, and sophisticated template substitution

### Agent Pattern: Collaborative Intelligence
- Claude Code agents + human approval loops
- Context persists via CLAUDE.md + MCP memory
- **Memory Intelligence System**: builder-memory MCP (knowledge graph, bundled) plus an optional agent-memory MCP you add yourself (see `docs/AGENT_MEMORY.md`). Starts empty and grows with use.
- **Consultation Mode**: Provide reasoning and alternatives, not just compliance
- **Wisdom Over Agreement**: Challenge decisions when technical merit warrants it
- **Permissions mode**: Your choice in `.claude/settings.json`. With bypass permissions on, {{ORCHESTRATOR_NAME}} provides technical consultation and risk analysis and {{USER_NAME}} proceeds with full authority; with prompts on, every write asks first.

**Agent System Overview:**
- **Specialist agents** live in `.claude/agents/` (full domain list in the "Orchestration Self-Awareness" section of `.claude-context/CLAUDE-orchestration.md`)
- **Agent behavior** defined within each agent's prompt (specialized capabilities and standards)
- **Skills** live in `.claude/skills/` (custom + community) for workflow automation and specialist capabilities
- Agent names include emojis - use EXACT names when invoking via Task tool
- See Orchestration section for complete agent domain mapping

### Maintenance Pattern: Lifecycle Care
- Not just build-and-forget
- Ongoing health monitoring and refinement
- Optional daily audit via LaunchAgent (schedule it in `global/config/` when you're ready)

## Current State (What You're Working With)
- **Production:** Your capsules live in `capsules/` (empty on a fresh install; `/capsules` lists them)
- **Templates:** Starter templates in `templates/` (web, mobile, automation, MCP, e-commerce, research)
- **Health:** `./catalyst-doctor.sh` checks the install; daily audits once you schedule them
- **Integration:** Code-first automations (Python/LaunchAgents), shadcn-ui components, Xcode project linking
