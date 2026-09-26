# Agent System Guide

Agents are the core building blocks of Huxley. Each agent is a specialist with a defined role, a set of skills, and clear boundaries on what it does and does not handle. The orchestrator ({{ORCHESTRATOR_NAME}}) reads incoming requests, identifies which agents are needed, and delegates work to them via Claude Code's Task tool.

## How Agents Work

An agent is a markdown file in `.claude/agents/`. When {{ORCHESTRATOR_NAME}} delegates a task using the Task tool:

```
Task(subagent_type="🏛️ Backend Developer", prompt="Create a REST API for user authentication...")
```

Claude Code spawns a subprocess with that agent's full markdown file as its system prompt. The agent has access to the project filesystem, configured tools, and any skills referenced in its definition. It executes the task and returns its output to the orchestrator.

Agents do not persist between invocations. Each Task call creates a fresh agent instance with no memory of previous runs. Persistent learning is handled separately by the Agent Memory system (a MCP server that stores patterns, anti-patterns, and outcomes).

## Agent Anatomy

Here is an annotated example of an agent definition file:

```markdown
---
# === FRONTMATTER (YAML) ===

name: 🏛️ Backend Developer                    # Display name with emoji (used in Task tool)
description: API design, backend systems...     # One-line summary
tools: "*"                                      # Tool access ("*" = all tools)
color: pink                                     # Terminal color for visual distinction
model: opus                                     # Model tier: opus | claude-sonnet-5 | claude-fable-5

# Mesh routing: collaboration declarations
mesh:
  can_request:                                  # Agents this one may ask for help
    - "🖥️ Frontend Developer"
    - "🛡️ Security Analyst"
  provides:                                     # Capabilities this agent offers to others
    - "api-design"
    - "database-schema"
    - "authentication"
---

# Backend Specialist

## Mission
[What this agent does and its primary focus areas]

## Context7 Language & Framework Expertise
[Instructions for querying up-to-date documentation via Context7 MCP]

## Domain Expertise
[Detailed list of technical capabilities]

## Architecture Checklist
[Quality checklist the agent follows for every task]

## Tool-Specific Protocols
[How to use specific tools like Supabase CLI, deployment platforms, etc.]

## Skills
[References to skill bundles this agent can use]

## Boundaries
[What this agent explicitly does NOT do -- delegation targets for out-of-scope work]
```

### Frontmatter Fields

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Full name with emoji prefix. Must match what the orchestrator passes to `subagent_type`. |
| `description` | Yes | One-line description shown in `/agents` command output. |
| `tools` | No | Tool access control. `"*"` grants all tools. Can be restricted to specific tools. |
| `color` | No | Terminal output color for visual distinction. |
| `model` | Yes | Model tier. `opus` for coding, `sonnet` for creative/strategic, `haiku` for lightweight. |
| `mesh` | No | Collaboration routing. `can_request` lists agents this one may ask for help; `provides` lists capabilities it offers. |

### Body Sections

The body is free-form markdown. Effective agent files typically include:

1. **Mission** -- One paragraph defining the agent's purpose and scope
2. **Expertise** -- Detailed capabilities list
3. **Protocols** -- Tool-specific instructions (how to use CLIs, APIs, frameworks)
4. **Checklists** -- Quality standards the agent applies to every task
5. **Skills** -- References to `.claude/skills/` bundles
6. **Boundaries** -- Explicit "do NOT do X, delegate to Y instead"

## Creating a New Agent

### Step 1: Define the role

Decide what this agent specializes in. Good agents have a clear boundary -- they own a specific domain and know when to delegate outside it.

### Step 2: Create the file

Create a new markdown file in `.claude/agents/`:

```
.claude/agents/my-specialist.md
```

### Step 3: Write the frontmatter

```yaml
---
name: 🔧 My Specialist
description: Brief description of what this agent does
tools: "*"
model: sonnet
mesh:
  can_request:
    - "🏛️ Backend Developer"
  provides:
    - "my-capability"
---
```

Choose the model tier based on cognitive demands:
- **opus** -- The agent writes or reviews code, debugs complex issues, or makes architectural decisions
- **sonnet** -- The agent does creative work, research, strategic analysis, or design
- **haiku** -- The agent does lightweight analysis, formatting, or lookup tasks

### Step 4: Write the body

```markdown
# My Specialist

## Mission
[Clear statement of purpose and scope]

## Expertise
- [Capability 1]
- [Capability 2]

## Protocols
[How this agent uses specific tools or follows specific workflows]

## Boundaries
- Do NOT do X -- delegate to [Other Agent]
- Do NOT do Y -- that is out of scope
```

### Step 5: Add to the routing map

Update the orchestrator's `CLAUDE.md` to include routing rules for the new agent. Add entries to:

1. **Agent Name Routing** -- Map friendly names to the full emoji name
2. **Specialist Routing Map** -- Add the agent to the appropriate category with a description of when to route to it

### Step 6: Wire skills (optional)

If the agent needs domain knowledge, add skill references to its body:

```markdown
## Skills

### My Custom Skill
**Skill location:** `.claude/skills/my-skill/SKILL.md`
[Instructions for when and how to use this skill]
```

### Step 7: Test

Invoke the agent through the orchestrator:

```
"Have My Specialist do [task]"
```

Or invoke directly with the Task tool for testing:

```
Task(subagent_type="🔧 My Specialist", prompt="Test task...")
```

## Agent Routing

The orchestrator uses a **routing map** to decide which agent handles a request. The map is defined in the main `CLAUDE.md` and works at two levels:

### Name Resolution

Users can refer to agents by friendly names. The orchestrator resolves these to the full emoji-prefixed name before calling the Task tool:

```
"Backend Dev"     -> "🏛️ Backend Developer"
"Frontend Dev"    -> "🖥️ Frontend Developer"
"Mobile Dev"      -> "📱 Mobile Developer"
"UI Designer"     -> "📐 UI Designer"
```

A complete alias mapping lives in `.claude-context/agent-name-routing.json`.

### Domain Routing

The orchestrator matches request content to agent domains:

| Signal in Request | Routes To |
|---|---|
| API, database, backend, migration, deployment, Cloudflare | 🏛️ Backend Developer |
| React, component, UI code, CSS, animation | 🖥️ Frontend Developer |
| iOS, Swift, mobile, simulator | 📱 Mobile Developer |
| Wireframe, prototype, UX, design system | 📐 UI Designer |
| Logo, brand, vector, infographic | 🎨 Graphic Designer |
| n8n, automation, workflow, shortcut | 🤖 Automator |
| Security audit, vulnerability, threat | 🛡️ Security Analyst |
| Marketing, ads, content, campaign | 📣 Chief Marketing Officer |

When a request spans multiple domains, the orchestrator delegates to multiple agents -- either sequentially (when one depends on the other's output) or in parallel (when they are independent).

### Explicit Delegation

When {{USER_NAME}} explicitly names an agent ("Have the backend dev do X"), the orchestrator must delegate to that exact agent. No judgment calls, no doing it itself.

## Model Tiers

| Tier | Agents | Rationale |
|---|---|---|
| **Opus** | Backend Dev, Frontend Dev, Mobile Dev, macOS Dev, Automator, Ecomm Bro, MCP Server Dude, Blockchain Agent, Bowser, 3D Developer, Code Reviewer, Debugger, Validator, Security Analyst, System Architect, BOSS | Code implementation, debugging, and security analysis require the highest reasoning capability |
| **Sonnet** | UI Designer, Graphic Designer, Camera Man, Studio Engineer, CMO, Product Strategist, Venture Analyst, Research Agent, AI Nerd | Creative work, strategic analysis, and research benefit from strong reasoning without needing peak code generation |
| **Haiku** | Brand Specialist, SEO Analyzer, Business Analyst, 2nd Brain Wizard | Lightweight analysis, formatting, and lookup tasks that do not require deep reasoning |

The `model:` field in agent frontmatter controls this. Change it anytime to adjust cost vs. capability per agent.

## Agent Roster

### Development Agents

| Agent | Name | Tier | Description |
|---|---|---|---|
| 🏛️ | Backend Developer | Opus | APIs, databases, backend systems, migrations, deployment infrastructure, all Cloudflare services |
| 🖥️ | Frontend Developer | Opus | React/Next.js, Vue, web components, accessibility, animation, CSS |
| 📱 | Mobile Developer | Opus | iOS Swift/SwiftUI, React Native, mobile testing, device deployment |
| 💻 | macOS Dev | Opus | Desktop apps with AppKit and SwiftUI |
| 🛒 | Ecomm Bro | Opus | E-commerce: headless Shopify (primary), Liquid themes (fallback) |
| 🤖 | Automator | Opus | Workflow automation, n8n, macOS Shortcuts |
| 🐲 | Bowser | Opus | Headless browser automation with Playwright, scraping, account creation |
| 🧊 | 3D Developer | Opus | Blender 3D modeling, animation, rendering, procedural generation |

### Creative Agents

| Agent | Name | Tier | Description |
|---|---|---|---|
| 📐 | UI Designer | Sonnet | Product UI/UX: user research, wireframes, prototypes, design systems |
| 🎨 | Graphic Designer | Sonnet | Brand identity, logos, vector graphics, infographics, templates |
| 📸 | Camera Man | Sonnet | AI-generated photorealistic images and video (Gemini, Sora, Veo) |
| 🎬 | Studio Engineer | Sonnet | OBS Studio, DaVinci Resolve, recording, streaming, video editing |

### Strategic Agents

| Agent | Name | Tier | Description |
|---|---|---|---|
| 👔 | BOSS | Opus | Huxley system oversight, strategic direction |
| 🏗️ | System Architect | Opus | Architecture design, system blueprints, technology decisions |
| 📣 | Chief Marketing Officer | Sonnet | Full-stack marketing: paid ads, content, social, analytics, CRO |
| 🎯 | Product Strategist | Sonnet | Product positioning, market analysis, roadmaps |
| 🧭 | Venture Analyst | Sonnet | Pre-build validation, market research, Go/No-Go decisions |

### Quality Agents

| Agent | Name | Tier | Description |
|---|---|---|---|
| 🧐 | Code Reviewer | Opus | Automated and manual code review, security/performance analysis |
| 👾 | Debugger | Opus | Systematic debugging, root cause analysis, observability |
| 🧪 | Validator | Opus | Functional testing, E2E validation, performance testing |

### Business Agents

| Agent | Name | Tier | Description |
|---|---|---|---|
| 📊 | Business Analyst | Haiku | KPI tracking, revenue analysis, growth projections |
| 🔍 | SEO Analyzer | Haiku | Technical SEO audits, meta optimization, Core Web Vitals |
| 🎯 | Brand Specialist | Haiku | Brand guidelines, voice and tone, consistency |

### Technical Agents

| Agent | Name | Tier | Description |
|---|---|---|---|
| 🏄🏼‍♂️ | MCP Server Dude | Opus | MCP server design and protocol compliance |
| ⛓️ | Blockchain Agent | Opus | Smart contracts, security audits, dApp integration |
| 🧠 | 2nd Brain Wizard | Haiku | Personal knowledge management (Drafts, Notes, Obsidian) |
| 🤓 | AI Nerd | Sonnet | AI model evaluation, ML trends, agent model mapping |

### Research & Security

| Agent | Name | Tier | Description |
|---|---|---|---|
| 🔍 | Research Agent | Sonnet | Multi-source research with academic-level methodology |
| 🛡️ | Security Analyst | Opus | Security audits, vulnerability assessment, threat modeling |

## Mesh Routing

Mesh routing is a collaboration system declared in agent frontmatter. It answers two questions:

1. **Who can this agent ask for help?** (`can_request`)
2. **What capabilities does this agent offer?** (`provides`)

### Example

```yaml
mesh:
  can_request:
    - "🖥️ Frontend Developer"
    - "🛡️ Security Analyst"
    - "📱 Mobile Developer"
  provides:
    - "api-design"
    - "api-contract"
    - "database-schema"
    - "authentication"
    - "deployment"
```

This tells the system:
- The Backend Developer may ask the Frontend Developer, Security Analyst, or Mobile Developer for input during complex tasks
- Other agents can expect the Backend Developer to provide API designs, database schemas, authentication implementations, and deployment work

### How Mesh Routing Is Used

Mesh declarations are **hints**, not enforcement. They help the orchestrator understand collaboration patterns and make better routing decisions. When a task requires capabilities from multiple agents, mesh routing helps determine which agents should work together and in what order.

For example, if the UI Designer declares `provides: ["wireframes", "design-system"]` and the Frontend Developer declares `can_request: ["📐 UI Designer"]`, the orchestrator knows to route design work to the UI Designer first, then hand the wireframes to the Frontend Developer for implementation.

### Agent Teams

For complex work that requires tight coordination between 3+ agents, Huxley supports **Agent Teams** -- multiple Claude Code processes that communicate via direct messaging and a shared task list. The orchestrator acts as team lead, spawning teammates and coordinating their work.

Teams are appropriate when:
- Three or more agents have interdependent tasks
- Agents need to iterate with each other (not just pass output)
- Work is cross-cutting (e.g., frontend + backend + tests for a single feature)

For most tasks, sequential or parallel Task tool calls are sufficient. Teams are the exception, not the default.
```

---