---
name: orchestration
description: Enforced specialist routing for {{ORCHESTRATOR_NAME}} orchestration. Analyzes tasks, identifies required specialists, and auto-delegates to prevent {{ORCHESTRATOR_NAME}} from doing specialist work.
when: Starting any implementation task, when unsure which specialist to use, or when the pre-tool-use hook blocks execution
allowed-tools:
  - Read
  - Task
  - Bash
  - TodoWrite
metadata:
  version: "2.0.0"
  architecture: "File patterns + Claude reasoning (no keyword heuristics)"
  last_updated: "2025-01-19"
  enforcement_level: "blocking"
---

# Orchestration Skill

## Purpose

This skill enforces {{ORCHESTRATOR_NAME}}'s orchestration role through:
1. **File pattern matching** for obvious cases (fast path)
2. **Claude's reasoning** for ambiguous cases (intelligent path)
3. **Auto-delegation** to prevent {{ORCHESTRATOR_NAME}} from doing specialist work

**Key principle:** We use Opus 4.5's reasoning capability instead of crude keyword heuristics.

---

## When This Skill Activates

1. **Hook redirect**: Pre-tool-use hook blocks specialist work → skill auto-invoked
2. **Explicit invocation**: User runs `/orchestrate`
3. **Uncertainty**: {{ORCHESTRATOR_NAME}} is unsure which specialist should handle a task
4. **Override request**: {{ORCHESTRATOR_NAME}} needs to justify bypassing delegation

---

## Reasoning Protocol (Core Innovation)

Instead of keyword matching, this skill uses structured reasoning to determine routing.

### Step 1: Understand the Task

**Ask yourself:**
- What is the user actually trying to accomplish?
- What type of work does this involve? (implementation, design, research, coordination)
- What artifacts will be created or modified?

### Step 2: Classify the Work Type

| Work Type | Characteristics | Route To |
|-----------|-----------------|----------|
| **Code Implementation** | Creating/modifying code files | Implementation specialist |
| **Design Work** | Wireframes, mockups, UX decisions | UI Designer or Graphic Designer |
| **Research/Analysis** | Investigation, competitive analysis | Research Agent |
| **Infrastructure** | Deployment, CI/CD, hosting | Backend Developer |
| **Testing** | Writing/running tests | Validator |
| **Debugging** | Root cause analysis | Debugger (then implementation specialist for fix) |
| **Coordination** | Multi-specialist orchestration | {{ORCHESTRATOR_NAME}} (this IS my job) |

### Step 3: Apply Reasoning Questions

**For implementation work, ask:**
1. What technology/language is involved?
2. Is this frontend (browser), backend (server), or mobile (device)?
3. Does this modify user-facing UI or server-side logic?

**For design work, ask:**
1. Is this about user experience (UI Designer) or visual assets (Graphic Designer)?
2. Is this pre-implementation design or post-implementation refinement?

**For ambiguous cases, ask:**
1. If I ({{ORCHESTRATOR_NAME}}) do this, am I implementing or coordinating?
2. Would a specialist do this better/faster?
3. Is this my job or am I just capable of doing it?

### Step 4: Make the Routing Decision

**Route to specialist if:**
- Work involves creating/modifying specialist-owned artifacts
- A specialist would produce better results
- Work is clearly within a specialist's domain

**Handle directly (as {{ORCHESTRATOR_NAME}}) if:**
- Work is pure coordination/orchestration
- Work involves {{ORCHESTRATOR_NAME}}-owned infrastructure (CLAUDE.md, agents, skills)
- Work is synthesizing outputs from multiple specialists

---

## Specialist Domain Reference

### Implementation Specialists (they write code)

| Specialist | Domain | Key Signals |
|------------|--------|-------------|
| 🏛️ **Backend Developer** | Server-side code, APIs, databases, deployment, Cloudflare | Python, Go, SQL, Docker, CI/CD |
| 🎨 **Frontend Developer** | Web UI implementation | React, Next.js, Vue, TSX/JSX, components |
| 📱 **Mobile Developer** | iOS/Android apps | Swift, Kotlin, Xcode, simulators |
| 💻 **macOS Dev** | Desktop Mac apps | AppKit, macOS SwiftUI |
| 🤖 **Automator** | Workflow automation | n8n, shortcuts, automation scripts |
| 🛒 **Ecomm Bro** | E-commerce | Headless Shopify (primary), Liquid themes (fallback) |
| 🏄🏼‍♂️ **MCP Server Dude** | MCP servers | Protocol implementation, MCP tools |
| ⛓️ **Blockchain Agent** | Smart contracts | Solidity, Web3, blockchain |
| 🧪 **Validator** | Test implementation | Test files, test suites |

### Design Specialists (they create designs)

| Specialist | Domain | Key Signals |
|------------|--------|-------------|
| 📐 **UI Designer** | Product UI/UX | Wireframes, prototypes, design systems |
| 🎨 **Graphic Designer** | Visual assets | Logos, brand, marketing graphics |
| 🎬 **Visual Media Generator** | AI-generated media | Video/image generation requests |

### Analysis Specialists (they investigate/analyze)

| Specialist | Domain | Key Signals |
|------------|--------|-------------|
| 🔍 **Research Agent** | Research tasks | Competitive analysis, investigation |
| 📊 **Business Analyst** | Business metrics | KPIs, revenue analysis |
| 🧐 **Code Reviewer** | Code quality | Review requests |
| 👾 **Debugger** | Issue investigation | Bugs, errors, root cause |

### Strategic Specialists (invoke sparingly)

| Specialist | Domain | Key Signals |
|------------|--------|-------------|
| 👔 **BOSS** | System oversight | Strategic decisions (explicit request only) |
| 🏗️ **System Architect** | Architecture | System design (explicit request only) |

---

## Override Protocol

Overrides should be **extremely rare**. If you're overriding frequently, the routing is broken.

### When Override is Acceptable

1. **Agent failure**: Specialist agent crashed/errored twice
2. **Trivial fix**: Single-character typo in a file you just read (debatable)
3. **Emergency**: Time-critical fix with explicit user approval

### Override Requirements

```markdown
## ORCHESTRATION OVERRIDE

**File:** [path to file]
**Would route to:** [specialist name]
**Override reason:** [specific justification]
**Acknowledgment:** I am doing specialist work as {{ORCHESTRATOR_NAME}}. This is an exception, not the norm.

[Proceed with work]

**Post-override action:** [Log this, fix underlying issue if agent failure]
```

### Override Tracking

All overrides are logged to: `/tmp/orchestration_overrides.log`

Format:
```
TIMESTAMP | FILE | SPECIALIST | REASON | OUTCOME
```

---

## Metrics & Observability

Track orchestration health at `/tmp/orchestration_metrics.json`:

```json
{
  "delegations": {
    "🏛️ Backend Developer": 45,
    "🎨 Frontend Developer": 32,
    "📱 Mobile Developer": 12
  },
  "overrides": {
    "count": 2,
    "reasons": ["agent_failure", "trivial_fix"]
  },
  "blocks": {
    "count": 15,
    "converted_to_delegation": 14,
    "overridden": 1
  }
}
```

---

## Auto-Invocation Flow

When the pre-tool-use hook blocks an operation:

```
1. Hook detects Edit/Write on specialist-owned file
   ↓
2. Hook BLOCKS with exit code 2
   ↓
3. Hook message instructs: "Run /orchestrate for routing"
   ↓
4. This skill analyzes the situation using reasoning
   ↓
5. Skill outputs delegation command OR override justification
   ↓
6. {{ORCHESTRATOR_NAME}} executes the delegation/override
```

---

## Examples

### Example 1: Clear Backend Work

**Task:** "Add a new API endpoint for user preferences"

**Reasoning:**
- This creates server-side code (API endpoint)
- Involves backend logic and likely database changes
- Clear backend domain

**Decision:** Delegate to 🏛️ Backend Developer

```markdown
Task({
  subagent_type: "🏛️ Backend Developer",
  description: "Add user preferences API endpoint",
  prompt: "Create a new API endpoint for user preferences..."
})
```

### Example 2: Ambiguous Case

**Task:** "Fix the button styling on the settings page"

**Reasoning:**
- This modifies frontend code (React components)
- Involves CSS/styling changes
- Could be "trivial" but still frontend domain

**Decision:** Delegate to 🎨 Frontend Developer (even for "small" changes)

### Example 3: Coordination Task ({{ORCHESTRATOR_NAME}} handles)

**Task:** "Coordinate the launch of the new feature across backend and frontend"

**Reasoning:**
- This is orchestration, not implementation
- Requires coordinating multiple specialists
- No single specialist owns this

**Decision:** {{ORCHESTRATOR_NAME}} handles directly, delegating sub-tasks to specialists

### Example 4: Override Scenario

**Task:** "Fix typo in component" (but agent failed twice)

**Override:**
```markdown
## ORCHESTRATION OVERRIDE

**File:** src/components/Button.tsx
**Would route to:** 🎨 Frontend Developer
**Override reason:** Frontend Developer agent failed twice with connection error
**Acknowledgment:** I am doing specialist work as {{ORCHESTRATOR_NAME}}. Will investigate agent failure after.

[Make the fix]

**Post-override:** Logged to /tmp/orchestration_overrides.log, will check agent health.
```

---

## Integration Points

### Agent Memory System

Before delegating, search agent memory for relevant patterns:
```markdown
# Check if this specialist has handled similar tasks
mcp__agent-memory__search_memories({
  query: "user preferences API",
  agent_name: "🏛️ Backend Developer"
})
```

### Metrics Logging

After each delegation/override, update metrics:
```bash
# Append to metrics file
python3 -c "
import json
from pathlib import Path
metrics_path = Path('/tmp/orchestration_metrics.json')
# Update metrics...
"
```

---

## Quick Decision Tree

```
START
  │
  ├─ Is this implementation work (code, design, tests)?
  │   ├─ YES → Which domain? → Delegate to specialist
  │   └─ NO → Continue
  │
  ├─ Is this investigation/analysis?
  │   ├─ YES → Delegate to Debugger/Research Agent/Business Analyst
  │   └─ NO → Continue
  │
  ├─ Is this coordination of multiple specialists?
  │   ├─ YES → {{ORCHESTRATOR_NAME}} handles (this IS my job)
  │   └─ NO → Continue
  │
  ├─ Is this {{ORCHESTRATOR_NAME}}-owned infrastructure?
  │   ├─ YES → {{ORCHESTRATOR_NAME}} handles (CLAUDE.md, agents, skills, etc.)
  │   └─ NO → Continue
  │
  └─ Unsure? → Default to delegation. Better to over-delegate than under-delegate.
```

---

*This skill transforms {{ORCHESTRATOR_NAME}} from "tries to help but does too much" into "expert orchestrator who routes intelligently using genuine reasoning, not crude heuristics."*
