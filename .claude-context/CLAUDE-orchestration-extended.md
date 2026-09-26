# Orchestration Extended Protocols (Lazy-Loaded Section)
<!-- Template version: 2026-09-24 -->
<!-- Last updated: 2026-02-24 -->
<!-- Parent: .claude-context/CLAUDE-orchestration.md (core routing & delegation rules) -->

## Mesh Agent Communication Protocol

**NEW: Supervised Mesh Communication**

Huxley agents can now request help from peer agents directly via the `mesh-coordinator` MCP server. This enables faster coordination while maintaining {{ORCHESTRATOR_NAME}} oversight.

**MCP Server:** `mesh-coordinator` (tools/mesh-coordinator/)

**Available Tools:**
- `request_peer_help` - Agent requests assistance from specific peer
- `discover_capabilities` - Find which agent can help with a capability
- `broadcast_status` - Announce completion/blockers
- `get_mesh_activity` - {{ORCHESTRATOR_NAME}} oversight of all mesh communications

**How It Works:**
1. Agent A identifies need for peer expertise (e.g., Frontend Dev needs API contract)
2. Agent A calls `request_peer_help` with to_agent, request_type, context
3. Request is logged to `quality.db` (mesh_communications table)
4. {{ORCHESTRATOR_NAME}} can view all mesh activity via `get_mesh_activity`
5. Peer responds with assistance

**Allowed Mesh Patterns:**
- Frontend Dev ↔ Backend Dev (API contracts, data shapes)
- Frontend Dev ↔ UI Designer (design clarification)
- Mobile Dev ↔ Backend Dev (API needs)
- Code Reviewer → Debugger (issue handoff)
- Debugger → Validator (verification request)

**Blocked Requests (must go through {{ORCHESTRATOR_NAME}}):**
- Any agent → BOSS (strategic decisions)
- Any agent → Security Analyst (security escalations)
- Cross-domain requests outside capability mapping

**Agent Mesh Configuration:**
Agents with mesh capabilities have a `mesh:` block in their frontmatter:
```yaml
mesh:
  can_request:
    - "🏛️ Backend Developer"
    - "📐 UI Designer"
  provides:
    - "react-components"
    - "accessibility-audit"
```

**Governance:** All mesh communications are logged for audit. {{ORCHESTRATOR_NAME}} maintains full visibility and can intervene when needed.

## Agent Teams Protocol

**Agent Teams spawn separate Claude Code processes that coordinate via direct messaging and a shared task list. {{ORCHESTRATOR_NAME}} acts as team lead.**

Unlike subagents (Task tool) which report only to {{ORCHESTRATOR_NAME}}, and Mesh which is lightweight peer hints, Agent Teams are full independent Claude Code sessions that can iterate with each other in real time.

**Three-Tier Coordination Model:**

| Tier | Mechanism | Process Model | {{ORCHESTRATOR_NAME}} Role | Best For |
|------|-----------|---------------|-------------|----------|
| 1 | **Task tool (subagents)** | Single request-response | Caller | Focused single-specialist work (80% of tasks) |
| 2 | **Mesh Protocol** | MCP messages within session | Observer | Quick peer clarifications (API contracts, status) |
| 3 | **Agent Teams** | Separate Claude Code processes | Team lead | Cross-cutting multi-agent coordination |

### Assembly Mode Decision Framework

**{{ORCHESTRATOR_NAME}} evaluates every multi-specialist task through this 5-step framework. Named clusters are shortcuts, not the only options -- {{ORCHESTRATOR_NAME}} composes ad-hoc when no cluster fits.**

**Step 1: Count specialist domains**

How many distinct specialist agents does this task need?
- 1 domain → **Single subagent.** Stop here.
- 2+ domains → Continue to Step 2.

**Step 2: Assess interdependency pattern**

| Pattern | Description | Example |
|---------|-------------|---------|
| **Linear** | A produces → B consumes → C consumes. Clean handoffs, no feedback needed. | Architect designs → Backend builds → Validator tests |
| **Convergent** | A and B work independently → results merge at end. No mid-task interaction. | Research market + Research competitors → {{ORCHESTRATOR_NAME}} synthesizes |
| **Iterative** | A and B refine each other's work. Output of one changes the other's approach. | Architect designs pipeline ↔ AI Nerd adjusts model choice ↔ Algo Wizard redesigns retrieval |

**Step 3: Assess design uncertainty**

- **Low** -- Solution approach is well-known, just needs execution
- **High** -- Multiple valid approaches, tradeoffs unclear, needs exploration/iteration

**Step 4: Select assembly mode**

| Domains | Interdependency | Uncertainty | → Assembly Mode |
|---------|----------------|-------------|-----------------|
| 1 | -- | Any | **Single subagent** |
| 2 | Linear | Low | **Sequential chain** |
| 2+ | Convergent | Low | **Parallel subagents** |
| 2 | Linear | High | **Sequential chain** (add feedback step) |
| 2+ | Convergent | High | **Parallel subagents → merge review** |
| 2+ | Iterative | Any | **Team** |
| 3+ | Any | High | **Team** |

**Override triggers (skip the matrix):**
- {{USER_NAME}} says "team" or "swarm" → **Team**
- Task explicitly needs adversarial peer review → **Team**
- Single domain even if complex → **Single subagent** (don't over-engineer)

**Step 5: Check named clusters**

If Step 4 says "Team" and the domain combination matches a named cluster below, use it as a starting template. Add or remove agents based on actual requirements. If no cluster matches, compose ad-hoc from the specialist roster.

### Named Clusters (Team Shortcuts)

**Starting templates, not rigid prescriptions. {{ORCHESTRATOR_NAME}} adjusts composition based on the actual task.**

**Thinking & Design:**

| Cluster | Core Agents | Trigger Signals |
|---|---|---|
| **Technical Brain Trust** | 🏗️ System Architect + 🤓 AI Nerd + 🧮 Algo Wizard | AI/ML system design, model-integrated architecture, algorithm-intensive greenfield. Optional: +🔍 Research for landscape scanning |
| **Research Sprint** | 🔍 Research + 🏆 Product Strategist + 📊 Business Analyst | "Evaluate [opportunity]", competing hypotheses |
| **Design-to-Build** | 📐 UI Designer + 🖥️ Frontend + 📈 SEO Analyzer | "Design and build [page/feature]" |

**Building & Shipping:**

| Cluster | Core Agents | Trigger Signals |
|---|---|---|
| **Full-Stack Feature** | 🏛️ Backend + 🖥️ Frontend + 🧪 Validator | "Build [feature] with API and UI" |
| **Full-Stack + Mobile** | 🏛️ Backend + 🖥️ Frontend + 📱 Mobile + 🧪 Validator | Feature spans web + mobile |
| **Mobile Feature** | 📱 Mobile + 🏛️ Backend + 📐 UI Designer | Native mobile feature with API |
| **Algorithm-Heavy Feature** | 🧮 Algo Wizard + 🏛️ Backend + 🖥️ Frontend | Non-trivial algorithms (search, matching, scheduling, ranking) |

**Data & AI:**

| Cluster | Core Agents | Trigger Signals |
|---|---|---|
| **Data/ML Pipeline** | 🏛️ Backend + 🤓 AI Nerd + 🔍 Research + 🧪 Validator | Data pipeline with ML, model training, analytics |
| **Search/Match System** | 🧮 Algo Wizard + 🏛️ Backend + 🧪 Validator | Fuzzy matching, deduplication, similarity scoring |
| **Data Pipeline** | 🧮 Algo Wizard + 🏛️ Backend + 📊 Business Analyst | ETL optimization, streaming aggregation, data dedup at scale |
| **Performance Optimization** | 🧮 Algo Wizard + 🏛️ Backend + 🧪 Validator | Algorithm bottleneck, complexity reduction, hot path optimization |

**Quality & Security:**

| Cluster | Core Agents | Trigger Signals |
|---|---|---|
| **Security Review** | 🛡️ Security Analyst + 🧐 Code Reviewer + 👾 Debugger | "Security audit of [system]", pre-launch review |
| **Launch Readiness** | 🧪 Validator + 🛡️ Security + 📈 SEO + 🏛️ Backend | Pre-launch quality gate |
| **Incident Response** | 👾 Debugger + 🏛️ Backend + 🛡️ Security + 🧪 Validator | Production incident, outage triage |

**Infrastructure:**

| Cluster | Core Agents | Trigger Signals |
|---|---|---|
| **Infrastructure/Release** | 🏛️ Backend + 🧪 Validator + 🛡️ Security | Deploy pipeline, infra changes, release cut |
| **Migration/Refactor** | 🏛️ Backend + 🖥️ Frontend + 🧪 Validator | Cross-cutting refactor, dependency upgrade |

### Team Lifecycle Protocol

**Phase 1: Create Team**
```
TeamCreate:
  team_name: descriptive-kebab-case (e.g., "auth-feature-team")
  description: Brief purpose statement
```

**Phase 2: Create Tasks**

Break work into tasks via TaskCreate. Target **5-6 tasks per teammate** -- this keeps teammates productive and lets {{ORCHESTRATOR_NAME}} reassign work if someone gets stuck. Each task needs:
- `subject` (imperative: "Implement user auth API")
- `description` with acceptance criteria
- `activeForm` for progress display ("Implementing user auth API")
- Dependencies via `addBlockedBy` where tasks are sequential
- **Always include in description:** "When complete, send your findings/deliverables to team lead via SendMessage before marking task completed."

**Phase 3: Spawn Teammates**

Use the Task tool with BOTH `subagent_type` AND `team_name` to spawn typed teammates:

```
Task(
  subagent_type="🏛️ Backend Developer",
  team_name="auth-feature-team",
  name="backend-dev",
  prompt="You are the Backend Developer on the auth-feature-team.
    Team purpose: [description]
    Your role: [specific responsibility]
    Teammates: [list with roles]
    Work from the shared task list -- claim unblocked tasks, complete them, check for next.
    IMPORTANT: When you complete a task, send your findings/deliverables to team lead
    via SendMessage BEFORE marking the task completed. Do not just mark complete silently."
)
```

**How context loading works:**
- `subagent_type` loads the agent's `.claude/agents/*.md` file automatically (specialist knowledge, skills, conventions)
- `team_name` joins the teammate to the shared task list and messaging system
- CLAUDE.md, MCP servers, and skills load automatically (same as any session)
- The spawn `prompt` provides team-specific context (purpose, role, teammates)

**No manual context injection needed.** The `subagent_type` parameter handles specialist knowledge. The spawn prompt only needs team context.

**Phase 4: Assign Tasks**

Use TaskUpdate with `owner` to assign initial tasks. Teammates also self-assign unblocked tasks from the shared list.

**Phase 5: Monitor ({{ORCHESTRATOR_NAME}} as Lead in Delegate Mode)**

**CRITICAL: Use delegate mode to prevent {{ORCHESTRATOR_NAME}} from implementing tasks itself.**

Delegate mode restricts {{ORCHESTRATOR_NAME}} to coordination-only tools: spawning, messaging, shutting down teammates, and managing tasks. This aligns with {{ORCHESTRATOR_NAME}}'s existing "orchestrator not implementer" rule.

Monitoring rules:
- Teammate messages arrive automatically (no polling needed)
- **Idle notifications are noise -- do NOT respond to them.** Teammates go idle between turns; this is expected. An idle notification after sending a message is normal (they sent their message, now they're waiting). Only act on idle if a task is stuck with no progress.
- Intervene when: teammate blocked, escalation needed (spend/strategic), quality gate, cross-team coordination
- Do NOT micromanage -- let teammates self-coordinate via shared task list
- If {{ORCHESTRATOR_NAME}} starts implementing instead of delegating, stop and wait for teammates
- If a teammate marks a task complete but didn't send findings, send ONE nudge. Don't re-explain the task -- just ask for the report.

**Phase 6: Shutdown and Cleanup**

When all tasks are complete:
1. Verify all tasks show `completed` via TaskList
2. Send `shutdown_request` to each teammate via SendMessage
3. Wait for shutdown confirmations
4. Call TeamDelete to clean up team and task directories
5. Synthesize results and report to {{USER_NAME}}

### Team Governance Rules

**NON-NEGOTIABLE:**
- {{ORCHESTRATOR_NAME}} is ALWAYS team lead (never spawn a team without {{ORCHESTRATOR_NAME}} oversight)
- Privacy rules apply to all teammates (no secrets in messages)
- BOSS is NOT auto-included (only when {{USER_NAME}} explicitly requests). System Architect auto-invocation for new projects still applies (see "Mandatory System Architect Invocation" in core orchestration)
- Team task lists are ephemeral -- cleaned up after team completes
- All teammates run with bypass permissions (inherited from {{ORCHESTRATOR_NAME}} session)

**Team size:** Strong recommendation of 5 teammates max. Beyond 5, coordination overhead and token cost escalate sharply -- split into sub-teams or use pipeline playbooks. Override only with clear rationale and sub-team partitioning.

**File conflict prevention:**
- Each teammate must own a different set of files -- two teammates editing the same file causes overwrites
- Break work so file ownership is clear (e.g., Backend owns `src/api/`, Frontend owns `src/components/`)
- If shared files are unavoidable, make one teammate the sole writer and others read-only

**Communication discipline:**
- Use `SendMessage` type `message` for targeted teammate communication (default)
- Use `broadcast` only for critical blocking issues (expensive -- sends to everyone)
- Teammates use TaskUpdate for status, not status messages
- {{ORCHESTRATOR_NAME}} lets teammates self-coordinate -- intervene only when needed

### Risk Awareness

**Known risks and mitigations:**

| Risk | Mitigation |
|------|------------|
| Context drift (agent file updated but teammate has stale version) | Teams are ephemeral -- fresh spawn each time |
| Role ambiguity / duplicate work | Clear task ownership via TaskUpdate, file ownership per teammate |
| Chat storms (excessive messaging) | Prefer TaskUpdate for status, SendMessage for decisions only |
| Task list thrash (tasks constantly reassigned) | {{ORCHESTRATOR_NAME}} assigns initial tasks, teammates self-assign remainder |
| False consensus (teammates agree too quickly) | For research teams, explicitly assign adversarial roles |
| High token cost | Default to subagents, use teams only when coordination benefit justifies cost |

### Troubleshooting

**Teammate appears stalled:**
- Check if they're idle (normal between turns) -- send a message to wake them
- If truly stuck, check their task status and reassign the task
- Spawn a replacement teammate if recovery fails

**Lead implementing instead of delegating:**
- Use delegate mode (restricts {{ORCHESTRATOR_NAME}} to coordination-only tools)
- Tell {{ORCHESTRATOR_NAME}}: "Wait for teammates to complete their tasks before proceeding"

**Task status lagging:**
- Teammates sometimes fail to mark tasks completed, blocking dependent tasks
- Check if the work is actually done, then update task status manually via TaskUpdate

**Permission prompts interrupting flow:**
- Teammates inherit {{ORCHESTRATOR_NAME}}'s bypass permissions -- this should not occur
- If it does, verify `bypassPermissions` is set in settings.json

### Teams vs Pipeline Playbooks

**Pipeline Playbooks** (like Landing Page Pipeline) remain correct for well-understood sequential workflows where phases are predictable, output cleanly feeds the next step, and agents don't need real-time peer coordination.

**Agent Teams** are better when the workflow is exploratory, agents need to iterate with each other (not just hand off), or parallel work has interdependencies (shared API contracts, design tokens).

**Hybrid:** A Pipeline Playbook can use an Agent Team for individual phases. Example: Landing Page Pipeline Phase 3 (BUILD) could spawn a team of Frontend Dev + Graphic Designer if the build requires real-time design-code iteration.

## Collaboration Learning Loop

**The Assembly Mode Framework starts as static rules and evolves through empirical data.** After every multi-agent delegation (2+ agents on the same task), {{ORCHESTRATOR_NAME}} records how the collaboration went. Before future assembly decisions, {{ORCHESTRATOR_NAME}} consults that history to inform the framework.

**Optional -- not shipped in v0.1:** the `monitoring/` directory (and the original `collaboration_log.py` CLI that backed this loop) is not part of this template, so there is no command to run. Collaboration history is a nice-to-have, not a prerequisite for Agent Teams. Until you add your own tracker, keep the loop lightweight: store the entry shape below in the agent-memory MCP (see "Agent Memory Integration") or in a plain JSONL file you create under `monitoring/`, and review it by hand before assembling a repeat agent pair.

### After Multi-Agent Work Completes (Log)

Record one entry per multi-agent delegation with this shape:
```json
{
  "agents": ["System Architect", "AI Nerd", "Algo Wizard"],
  "assembly_mode": "team|sequential|parallel|parallel_merge|single",
  "cluster_name": "Technical Brain Trust",
  "interdependency": "linear|convergent|iterative|none",
  "uncertainty": "low|high",
  "revision_needed": false,
  "outcome": "success|partial|failure",
  "duration_ms": 45000,
  "task_summary": "Designed RAG pipeline for embeddings search",
  "notes": "AI Nerd model choice influenced Algo Wizard index design"
}
```

**`revision_needed`** is the most important signal. Set to `true` when:
- Agent B's output required going back to Agent A to redo work
- The architecture changed mid-build because a downstream agent surfaced a constraint
- {{ORCHESTRATOR_NAME}} had to re-delegate to an earlier agent after a later agent's output

High revision rates for a given agent combination in a given mode = the mode is wrong. Sequential with frequent revision → should be iterative/team.

### Before Assembly Decisions (Query)

When assembling 2+ agents, {{ORCHESTRATOR_NAME}} checks the history for that agent pair: which mode was used, success rate per mode, revision rate, and any escalation signals. If history says "sequential had 60% revision rate for this pair," {{ORCHESTRATOR_NAME}} upgrades to team.

**Integration with the 5-step framework:** Historical recommendations override the static matrix when data exists. The static matrix is the cold-start default; the learned data is the warm-start improvement.

### Periodic Insight Review

Periodically review the recorded entries for: mode distribution, revision hotspots (agent pairs that frequently need rework), and cluster usage patterns. {{ORCHESTRATOR_NAME}} proposes framework updates when patterns stabilize.

### Agent Memory Integration

When a collaboration reveals a novel, reusable pattern (not every log -- only significant ones), {{ORCHESTRATOR_NAME}} creates a memory via the agent-memory MCP:

```
create_pattern:
  agent: "{{ORCHESTRATOR_NAME_LOWER}}"
  pattern_type: "collaboration"
  description: "Architect + AI Nerd: sequential works for known stacks, team needed for novel AI integration"
  tags: ["collaboration", "system-architect", "ai-nerd", "assembly-mode"]
  impact_score: 0.7
```

This makes collaboration knowledge searchable semantically, not just by exact agent names.

## Pipeline Playbooks

**Pre-built multi-agent workflows for common complex tasks. {{ORCHESTRATOR_NAME}} follows these sequences when triggered.**

### Landing Page Pipeline

**Trigger:** "Build a landing page for X", "Create a marketing site", "Make a product page"

**Pipeline:** Sequential with parallel sub-steps where possible.

```
Phase 1: STRATEGY (📣 CMO)
├─ Task: "Define landing page strategy for [X]"
├─ Skills used: /copywriting, /marketing-psychology, /page-cro, cro-methodology
├─ Deliverables:
│   ├─ Target audience + persona
│   ├─ Value proposition (primary + supporting)
│   ├─ Objection/Counter-Objection table (from CRE methodology)
│   ├─ Persuasion assets inventory (testimonials, stats, guarantees)
│   ├─ Page structure recommendation (sections in order)
│   ├─ All copy: headline, subheadline, section copy, CTAs
│   └─ Conversion goal (single primary action)
├─ Handoff: Copy doc + strategy brief → Phase 2
│
Phase 2: DESIGN (📐 UI Designer)
├─ Task: "Design landing page using CMO's strategy brief"
├─ Skills used: top-design (scoring rubric + anti-patterns)
├─ Inputs: Copy doc + strategy brief from Phase 1
├─ Deliverables:
│   ├─ Design system (colors, typography, spacing)
│   ├─ Wireframe with section layout
│   ├─ Component specs (hero, social proof, pricing, CTA, footer)
│   ├─ Animation/interaction specifications
│   ├─ Responsive breakpoint strategy
│   └─ Design score self-evaluation (top-design 0-10 rubric)
├─ Quality gate: Design must score ≥7/10 on top-design rubric
├─ Handoff: Design specs + component specs → Phase 3
│
Phase 3: BUILD (🖥️ Frontend Dev)  [+ 🎨 Graphic Designer in parallel if needed]
├─ Task: "Implement landing page from UI Designer specs"
├─ Skills used: premium-frontend-design, top-design, addyosmani-seo, addyosmani-core-web-vitals
├─ Inputs: Design specs from Phase 2
├─ Deliverables:
│   ├─ Full page implementation (React/Next.js + Tailwind + shadcn/ui)
│   ├─ Animations (react-spring or Framer Motion per premium-frontend-design tiers)
│   ├─ SEO markup (meta tags, Open Graph, structured data per Addy Osmani SEO)
│   ├─ CWV-optimized (preloaded LCP, font-display, image srcset per Addy Osmani CWV)
│   ├─ Responsive implementation
│   └─ Build passes without errors
├─ Parallel: 🎨 Graphic Designer generates hero images/assets if needed
├─ Handoff: Built page → Phase 4
│
Phase 4: OPTIMIZE (📈 SEO Analyzer)
├─ Task: "Audit landing page for SEO + performance"
├─ Skills used: addyosmani-seo, addyosmani-core-web-vitals, cloudflare-web-perf
├─ Inputs: Built page from Phase 3
├─ Deliverables:
│   ├─ SEO audit (meta tags, schema, heading hierarchy, crawlability)
│   ├─ Core Web Vitals report (LCP, INP, CLS with specific fixes)
│   ├─ Performance trace (render-blocking resources, network chains)
│   ├─ Fix list prioritized by impact
│   └─ Fixes applied (or routed back to Frontend Dev)
├─ Handoff: Optimized page → Phase 5
│
Phase 5: DEPLOY (🏛️ Backend Dev)
├─ Task: "Deploy landing page to [platform]"
├─ Skills used: cloudflare-web-perf (post-deploy verification)
├─ Deliverables:
│   ├─ Deployed to Cloudflare Pages / Vercel
│   ├─ Custom domain configured (if applicable)
│   ├─ SSL verified
│   └─ Post-deploy performance check
└─ DONE: Landing page live
```

**Shortcut mode:** If {{USER_NAME}} says "quick landing page" or the scope is simple (single section, no custom design), {{ORCHESTRATOR_NAME}} can compress Phases 1-3 into a single Frontend Dev task with CMO copy guidance included in the prompt.

**Iteration mode:** After Phase 5, CMO can run CRO methodology (9-step process) to optimize the live page based on real visitor data.
