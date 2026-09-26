# Huxley

**A multi-agent operating layer for Claude Code: one orchestrator, 35 specialist agents, 48 bundled skills (plus 25 community skills a setup script links in), a set of CLI tools, and hooks that make them work as a team.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Built with Claude Code](https://img.shields.io/badge/Built_with-Claude_Code-blueviolet.svg)](https://claude.ai/claude-code)

---

Huxley turns a single Claude Code session into a coordinated team. You talk to one agent, the orchestrator, which you name during setup. It routes work to specialists, runs independent tasks in parallel, chains dependent ones, and verifies results before reporting back. Projects live in isolated capsules so each one gets its own context and credentials.

🎯 **Specialists.** 35 agents that know their domain, their tools and who they coordinate with. Say "have Backend Dev create an API" and the orchestrator resolves the name, loads the right context and delegates.

💊 **Capsules.** Each project is an isolated workspace with its own `CLAUDE.md`, `.env` and specs. Switch projects and the agents get fresh, relevant context, nothing from your other work.

⌨️ **CLI-first tooling.** Tools are standalone Python and shell scripts that agents call directly. MCP servers are used where they earn their keep (live docs, memory, terminal control); CLIs are the default.

🧠 **Memory.** A persistent knowledge graph out of the box, and an optional ChromaDB-backed layer that stores patterns, anti-patterns and task outcomes, retrieved before every delegation.

🧐 **Quality pipeline.** Code Reviewer, then Debugger, then Validator, as an explicit sequence or as an automatic post-turn review.

---

## Quick Start

1. On GitHub, click **Use this template** and create your own repository.
2. Clone it and run setup:

```bash
git clone https://github.com/<your-user>/<your-repo>.git
cd <your-repo>
./setup.sh          # asks your name, the orchestrator's name, and a few preferences
./setup-skills.sh   # community skills (several agents reference these symlinks)
claude              # the orchestrator loads via CLAUDE.md
```

3. Talk to it:

- *"Have Backend Dev create a REST API for user auth"*
- *"Ask the Security Analyst to audit this codebase"*
- *"Have the CMO draft launch copy for a product page"*
- *"Have Mobile Dev build an iOS app with push notifications"*

The full walkthrough, including API keys and the optional layers, is in [GETTING-STARTED.md](GETTING-STARTED.md).

---

## What's In Here

### Agents (`.claude/agents/`)

35 specialists, each a single markdown file with a defined role, model tier, tools and coordination rules. The orchestrator routes work to the right one; you can also name one explicitly.

**Build**

- 🏛️ **[Backend Developer](.claude/agents/backend-specialist.md)**: APIs, databases, migrations, and all deployment infrastructure (CI/CD, Vercel, Cloudflare Pages, Workers, R2, D1, DNS).
- 🖥️ **[Frontend Developer](.claude/agents/frontend-specialist.md)**: React, Next.js, Vue, shadcn/ui. The web code, not the hosting.
- 📱 **[Mobile Developer](.claude/agents/mobile-dev.md)**: iOS with Swift, React Native and Expo, simulator testing, device deployment.
- 💻 **[macOS Dev](.claude/agents/macos-specialist.md)**: Desktop apps with AppKit and SwiftUI, Mac App Store deployment.
- 🎮 **[Game Developer](.claude/agents/game-developer.md)**: Unity, Unreal, Godot and web engines. Mechanics, shaders, physics.
- 🤖 **[Automator](.claude/agents/automation-specialist.md)**: Python and shell automations, LaunchAgents, macOS shortcuts. Code first, not low-code.
- 🐲 **[Bowser](.claude/agents/bowser.md)**: Headless Playwright automation: scraping, account flows, CAPTCHA solving.
- 🛒 **[Ecomm Bro](.claude/agents/ecomm-bro.md)**: Platform-agnostic storefront optimisation, product page UX, checkout flows, social commerce.

**Design and media**

- 📐 **[UI Designer](.claude/agents/ui-designer.md)**: UI/UX across all platforms: research, wireframes, prototypes, design systems.
- 🎨 **[Graphic Designer](.claude/agents/graphic-designer.md)**: Logos, vectors, infographics, templates, social layouts.
- 📸 **[Camera Man](.claude/agents/visual-media-generator.md)**: AI-generated realistic media, product photography, video, upscaling.
- 🎬 **[Studio Engineer](.claude/agents/studio-engineer.md)**: OBS Studio and DaVinci Resolve automation, programmatic colour grading.
- 🧊 **[3D Developer](.claude/agents/3d-developer.md)**: Blender modelling, animation, rendering, procedural generation.

**Quality**

- 🧐 **[Code Reviewer](.claude/agents/code-reviewer.md)**: Reviews with conditional depth; lightweight for simple diffs, thorough for complex ones.
- 👾 **[Debugger](.claude/agents/debugger.md)**: Systematic investigation and root-cause analysis.
- 🧪 **[Validator](.claude/agents/validator.md)**: End-to-end testing: Playwright, iOS simulator, API and performance checks.

**Strategy and business**

- 👔 **[BOSS](.claude/agents/boss.md)**: System oversight and strategic decisions. Invoked only when you ask for it.
- 🏗️ **[System Architect](.claude/agents/system-architect.md)**: Landscape scan, stack assessment and build-vs-adopt call before any greenfield project.
- 🧭 **[Venture Analyst](.claude/agents/venture-analyst.md)**: Pre-build validation, market research, go/no-go.
- 🏆 **[Product Strategist](.claude/agents/product-strategist.md)**: Positioning, feature prioritisation, roadmaps.
- 📊 **[Business Analyst](.claude/agents/business-analyst.md)**: KPIs, revenue analysis, projections, cohorts.
- 📣 **[Chief Marketing Officer](.claude/agents/chief-marketing-officer.md)**: Paid ads, content, social, email, attribution, CRO. 23 marketing skills.
- 🎯 **[Brand Specialist](.claude/agents/brand-specialist.md)**: Brand consistency across projects: visual language, tone, identity.
- 📈 **[SEO Analyzer](.claude/agents/seo-analyzer.md)**: Technical SEO audits, Core Web Vitals, metadata.
- 📺 **[YouTube Strategist](.claude/agents/youtube-growth-strategist.md)**: Channel growth, monetisation, YouTube SEO, content pipelines.
- 🛍️ **[Sourcerer](.claude/agents/product-sourcing.md)**: Product sourcing: supplier discovery, landed cost, trade compliance, RFQs.

**Technical and research**

- 🧮 **[Algo Wizard](.claude/agents/algo-wizard.md)**: Algorithm design for search, matching, ranking, scheduling and scoring, consulted before anyone writes an O(N²) loop.
- 🛡️ **[Security Analyst](.claude/agents/security-analyst.md)**: Audits, threat modelling, vulnerability assessment.
- 🔬 **[Reverse Engineer](.claude/agents/reverse-engineer.md)**: Binary analysis, runtime instrumentation, protocol reverse engineering.
- 🏄🏼‍♂️ **[MCP Server Dude](.claude/agents/mcp-server-architect.md)**: MCP server design, transports, tool definitions.
- ⛓️ **[Blockchain Agent](.claude/agents/blockchain-web3-specialist.md)**: Smart contracts, audits, dApp integration.
- 🤓 **[AI Nerd](.claude/agents/ai-nerd.md)**: Model evaluation, gateway routing, AI feature implementation.
- 🔍 **[Research Agent](.claude/agents/research-agent.md)**: Multi-source research with transparent citations.
- 🧠 **[2nd Brain Wizard](.claude/agents/second-brain-wizard.md)**: Personal knowledge management: notes apps, Obsidian, photos.
- ⚗️ **[Formulator](.claude/agents/formulator.md)**: Clean formulation for supplements, skincare and fragrance; ingredient safety and compliance.

### Orchestration

`CLAUDE.md` is the orchestrator's rulebook, and Claude Code reads it every session. The core rules:

- **Delegate, don't implement.** The orchestrator routes, coordinates and synthesises. Specialists write the code. A post-tool-use hook reminds it when it drifts.
- **Name resolution.** "Backend Dev", "backend", "the backend guy" all resolve to `🏛️ Backend Developer` through `.claude-context/agent-name-routing.json`.
- **Parallel by default.** Independent tasks go out as multiple Task calls in one message; only true dependencies (design before build, review before fix) run as a pipeline.
- **Agent Teams.** For work spanning three or more domains, the orchestrator becomes team lead over separate Claude Code processes with a shared task list.
- **Automatic consultations.** New projects trigger the System Architect first; search, ranking or scheduling logic triggers the Algo Wizard first.

The extended guide is `.claude-context/CLAUDE-orchestration.md`.

### Capsules (`capsules/`)

Self-contained project workspaces. Each capsule has its own `CLAUDE.md`, `.env`, specs and source. You `cd` into one and start Claude Code; its `CLAUDE.md` loads on top of the root one, so agents get project context without seeing anything from your other projects.

```
┌─ Huxley ─────────────────────────────────────────────────────┐
│                                                              │
│  CLAUDE.md (orchestrator)     .claude/agents/ (35 agents)    │
│  .claude-context/ (deep ctx)  .claude/skills/ (48 skills)    │
│                                                              │
│  ┌─ capsules/ ────────────────────────────────────────────┐  │
│  │  ┌─ web-app ──────┐  ┌─ mobile-app ───┐               │  │
│  │  │ CLAUDE.md      │  │ CLAUDE.md      │               │  │
│  │  │ src/  .env     │  │ src/  .env     │               │  │
│  │  │ specs/         │  │ specs/         │               │  │
│  │  └────────────────┘  └────────────────┘               │  │
│  │  Each capsule = isolated project workspace              │  │
│  │  Agents work IN capsules but are defined GLOBALLY       │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ tools/ ───────────────────────────────────────────────┐  │
│  │  media-engine/  capsule_creator.py  codex-consult.sh   │  │
│  │  apple_provision.py  browser/  *-intel/  ...           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ global/ ──────────────────────────────────────────────┐  │
│  │  governance/guardrails.yaml  config/port-registry.yaml │  │
│  │  claude-config/agent_model_map.json  docs/  schemas/   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

Create one with `python3 tools/capsule_creator.py --name my-project --purpose "..."`, or copy `templates/capsule-base`. Starter templates for web, native iOS, React Native, automation and e-commerce live in `templates/`.

### Skills (`.claude/skills/`)

48 skill bundles ship in the tree, each a `SKILL.md` plus reference material, wired to the agents that need them: Postgres best practices, API security, copywriting, pricing strategy, product sourcing, Playwright automation, iOS testing and device deployment, systematic debugging, and a media engine. `./setup-skills.sh` clones 13 community skill repos and symlinks 25 more skills into place — SwiftUI patterns and audits, React and React Native best practice, Expo, Better Auth, Core Web Vitals, SEO, CRO methodology, MCP building — and several agents' skill tables reference those symlinks.

Slash commands in `.claude/commands/` cover the daily loop: `/build-feature`, `/code-review`, `/debug`, `/validate`, `/audit`, `/feature-loop`, `/capsules`, `/tools`, `/auto-review`, `/codex-review`, and more.

### CLI tools (`tools/`)

Standalone Python and shell scripts that agents (or you) call directly. The pattern is consistent: `--help` for docs, `--json` for scripting, `--dry-run` where anything is destructive.

| Tool | What it does |
|------|-------------|
| `media-engine/` | Config-driven image, video and vector generation with YAML workflow templates. |
| `capsule_creator.py` | Creates a capsule with specs, navigation skill and index entry. |
| `codex-consult.sh` | Peer consultation with the OpenAI Codex CLI: free-form, file review, diff review, spec check. |
| `catalyst-mcp/` | The framework's own MCP server for capsule and tool discovery. |
| `apple_provision.py` | Apple Developer portal automation: bundle IDs, capabilities, profiles. No Fastlane. |
| `davinci_resolve.py`, `color_grader.py` | DaVinci Resolve automation and programmatic colour grading. |
| `file-organizer/` | AI-powered file sorting with local models via Ollama. Ships with a placeholder `taxonomy.yaml`; edit it for your projects. |
| `browser/` | Playwright automation with stealth profiles and snapshot refs. |
| `image-gen/` | Shell wrappers for image generation providers. |
| `*-intel/` | Research CLIs: `youtube-intel`, `tiktok-intel`, `instagram-intel`. |
| `memory/` | Memory setup, status and backup scripts. |
| `secretctl.py`, `scan_secrets.sh`, `check-secrets.py` | Secret presence checks (environment via `secretctl.py`, Keychain via `check-secrets.py`) and pre-push secret scanning. |
| `skill-curator/`, `check-ports.sh` | Skill maintenance (Telegram digest optional) and port-registry checks. |

### MCP servers (`.mcp.json`)

| Server | What it does | Runs via |
|--------|-------------|----------|
| [Context7](https://github.com/upstash/context7) | Current library docs for any framework. Agents query it before answering technical questions. | `npx` |
| Memory (`builder-memory`) | Persistent knowledge graph across sessions. | `npx @modelcontextprotocol/server-memory` |
| Filesystem | Scoped file access for MCP-based workflows. | `npx @modelcontextprotocol/server-filesystem` |
| iTerm MCP | Interact with an already-running terminal process. | `npx iterm-mcp` |
| Google Workspace | Google mail, calendar and drive. Needs your own OAuth client; remove if unused. | `uvx` |

More server profiles are catalogued in `global/mcp/server-registry.json`.

### Hooks

Hooks live in `tools/hooks/` and `tools/system-utils/hooks/` and are wired through `.claude/settings.json`:

- **Routing reminders** after tool use, so the orchestrator delegates instead of implementing.
- **Auto code review** on Stop: a Codex diff review that fixes findings. It needs the OpenAI Codex CLI; without it the hook stands down and does nothing. Toggle with `/auto-review`.
- **Git checkpoint** on Stop, so every turn's work is recoverable.
- **Session context** on SessionEnd: capsule context and transcript export.

Voice output is not wired in v0.1; `docs/SETUP.md` describes the empty slot if you want to add it.

See `docs/HOOKS.md` for the full list and how to add your own.

### Memory

`builder-memory` works with no setup. The optional deeper layer is a ChromaDB-backed memory server: the orchestrator searches it for relevant patterns before delegating, stores reusable patterns and anti-patterns after novel tasks, and warns specialists proactively when a known pitfall applies. That server is **not bundled in v0.1**; the rules in `CLAUDE.md` reference it so the workflow is ready when you add one, and until then every memory step is skipped silently. `docs/AGENT_MEMORY.md` explains the two layers and how to add the second.

### Context management

The root `CLAUDE.md` stays lean. Deeper context lives in `.claude-context/` and loads on demand when a conversation touches the topic:

```
CLAUDE.md (always loaded)
  ├── .claude-context/CLAUDE-architecture.md    ← system patterns, capsules
  ├── .claude-context/CLAUDE-orchestration.md   ← delegation rules, teams
  ├── .claude-context/CLAUDE-integrations.md    ← memory, APIs, browsers
  ├── .claude-context/CLAUDE-navigation.md      ← capsule navigation
  ├── .claude-context/CLAUDE-operating.md       ← specs, validation, cost
  ├── .claude-context/CLAUDE-strategy.md        ← your north star, priorities (fill-in template)
  └── .claude-context/index.json                ← load triggers
```

### Governance

`global/governance/guardrails.yaml` classifies risk and sets the standing rules: never print secrets, never modify credentials, no external spend without approval. `global/config/port-registry.yaml` is the single source of truth for service ports; add a service there before starting it.

---

## Not Included in v0.1

The template is the framework, not the original owner's machine. These pieces were deliberately left out; each has a documented way back in.

- **Telegram bot stack** (driving Claude Code from your phone). Build your own bot with any Telegram library and point it at `claude -p`; the `TELEGRAM_BOT` / `TELEGRAM_CHAT_ID` answers from `setup.sh` are already available to it. A few shipped tools can still post a status line if you give them a bot token via the Keychain.
- **TTS voice hook** (spoken summaries at the end of each turn). `CLAUDE.md` keeps the protocol off by default; wire a Stop hook that speaks the `<tts-summary>` tag, as described in `docs/SETUP.md` → Voice.
- **`agent-memory` server** (ChromaDB-backed pattern memory). `builder-memory` ships and works; add the deeper layer by following `docs/AGENT_MEMORY.md`.
- **Music bridge** (controls a local music player from a session). Recreate it as a small CLI under `tools/` and wire it through a skill; nothing in the framework depends on it.
- **The previous operator's personal tools** (personal trackers and private dashboards). Out of scope for a framework; build your own as capsules or `tools/` scripts using the same CLI-first pattern.
- **GitNexus code intelligence** (a code graph the Debugger and Code Reviewer query over MCP). The CLI is external and not bundled, and `.mcp.json` does not register it; `CLAUDE.md`, two agents and four skills reference it and skip those steps until it exists. Install it, index with `tools/gitnexus-reindex.sh` and add the MCP entry as described in `docs/SETUP.md` → GitNexus.

---

## Grab What You Want

You don't have to use the whole system. Each piece works standalone.

```bash
# Just the agents
npx degit <your-user>/<your-repo>/.claude/agents

# Just the skills
npx degit <your-user>/<your-repo>/.claude/skills

# Just the tools
npx degit <your-user>/<your-repo>/tools

# Just the hooks
npx degit <your-user>/<your-repo>/tools/hooks
```

Drop agents into any `.claude/agents/`, hooks into any Claude Code config. No framework dependency.

---

## Docs

| Doc | What's in it |
|-----|-------------|
| [GETTING-STARTED.md](GETTING-STARTED.md) | First-day walkthrough: setup, keys, optional layers, first delegation |
| [docs/SETUP.md](docs/SETUP.md) | Longer setup guide, updating from the template, customisation |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the whole system fits together |
| [docs/AGENTS.md](docs/AGENTS.md) | How agents work and how to write your own |
| [docs/AGENT_MEMORY.md](docs/AGENT_MEMORY.md) | The two memory layers: what ships, what doesn't, how to add the rest |
| [docs/HOOKS.md](docs/HOOKS.md) | The hook system and creating custom hooks |
| [docs/SKILLS.md](docs/SKILLS.md) | Skills, community skills, wiring them to agents |
| [docs/EXAMPLES.md](docs/EXAMPLES.md) | Step-by-step usage scenarios |
| [docs/FAQ.md](docs/FAQ.md) | Common questions |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Conventions for agents, skills, capsules and PRs |

---

## License

MIT. See [LICENSE](LICENSE).
