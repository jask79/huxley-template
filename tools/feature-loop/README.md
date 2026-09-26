# Feature Loop - Autonomous Development System

**Huxley skill for autonomous iterative feature development with AI agents.**

## Overview

The Feature Loop skill enables fully autonomous feature development by running iterative Claude Code sessions until a Product Requirements Document (PRD) is complete. It's Huxley's implementation of the "Ralph pattern" for AI-driven development with proper governance and quality gates.

## Key Concepts

### Ralph Pattern Adaptation

Inspired by [Ralph](https://github.com/snarktank/ralph), Feature Loop implements:

1. **Iterative execution**: Fresh Claude Code session per iteration
2. **Persistent state**: All state in PRD JSON file + git commits
3. **Append-only learning**: Progress logs capture learnings
4. **Autonomous operation**: No human intervention until complete
5. **Quality gates**: Code review and validation per task

### Huxley Enhancements

- **Specialist delegation**: Tasks routed to domain experts (Backend Dev, Frontend Dev, etc.)
- **Governance integration**: Configurable validation gates and cost controls
- **Agent memory**: Successful patterns stored for future reuse
- **Quality workflow**: Code Reviewer → Debugger → Validator pipeline
- **Progress tracking**: Detailed audit trail in append-only logs

## Installation

No installation needed - Feature Loop is a built-in Huxley skill.

Files:
- **Skill definition**: `.claude/commands/feature-loop.md`
- **Loop runner**: `tools/feature-loop/loop.sh`
- **Iteration prompt**: `tools/feature-loop/iteration-prompt.md`
- **PRD schema**: `tools/feature-loop/prd-schema.json`
- **Example PRD**: `tools/feature-loop/prd-example.json`

## Quick Start

### 1. Create a PRD

Create a JSON file describing your feature with tasks, priorities, and acceptance criteria:

```json
{
  "feature": "User Authentication",
  "branch": "feature/user-auth",
  "maxIterations": 10,
  "governance": {
    "requireValidation": true,
    "notifyOnComplete": true,
    "costAlertThreshold": 5
  },
  "tasks": [
    {
      "id": "AUTH-001",
      "title": "Implement JWT token generation",
      "description": "Create FastAPI endpoint for JWT generation...",
      "specialist": "Backend Dev",
      "priority": 1,
      "acceptanceCriteria": [
        "Returns valid JWT on successful auth",
        "Includes refresh token"
      ],
      "passes": false
    }
  ]
}
```

See `prd-example.json` for a complete example.

### 2. Run the Loop

```bash
# Via Claude Code skill
/feature-loop tasks/my-feature.json

# Or directly via script
./tools/feature-loop/loop.sh tasks/my-feature.json
```

### 3. Monitor Progress

```bash
# Watch the progress log
tail -f tools/feature-loop/runs/feature-my-feature/progress.log

# Check PRD status
cat tasks/my-feature.json | jq '.tasks[] | {id, title, passes}'
```

## PRD Format

### Required Fields

- **feature** (string): Feature name for human readability
- **tasks** (array): List of tasks to complete

### Optional Fields

- **branch** (string): Git branch name (default: sanitized feature name)
- **maxIterations** (integer): Max iterations before terminating (default: 10)
- **governance** (object): Quality and safety settings

### Governance Options

```json
{
  "governance": {
    "requireValidation": true,      // Run Validator before marking tasks complete
    "notifyOnComplete": true,       // macOS notification on completion/failure
    "costAlertThreshold": 5         // Warn when iteration count reaches this number
  }
}
```

### Task Schema

```json
{
  "id": "TASK-001",                 // Unique identifier (e.g., "AUTH-001")
  "title": "Short title",           // Human-readable title
  "description": "Full context...", // Detailed requirements
  "specialist": "Backend Dev",      // Huxley agent to delegate to
  "priority": 1,                    // 1 = highest priority
  "acceptanceCriteria": [           // List of criteria to verify
    "Criterion 1",
    "Criterion 2"
  ],
  "passes": false,                  // Set by loop when verified
  "completedAt": null,              // ISO 8601 timestamp (set by loop)
  "learnings": []                   // Key insights (appended by loop)
}
```

## How It Works

### Loop Execution

Each iteration:

1. **Load PRD**: Read current state from JSON file
2. **Select task**: Find highest-priority incomplete task (`passes: false`)
3. **Delegate**: Route task to specialist agent via Task tool
4. **Quality checks**: Run Code Reviewer → Validator (if required)
5. **Update PRD**: Mark `passes: true` if all acceptance criteria met
6. **Store learnings**: Append insights to Agent Memory
7. **Check completion**: If all tasks pass, output completion signal and exit
8. **Continue**: Otherwise, sleep and start next iteration

### Completion Signal

When all tasks have `passes: true`, the iteration outputs:

```
<loop-signal>COMPLETE</loop-signal>
```

The loop runner detects this signal and terminates successfully.

### State Management

**All state persists in the PRD JSON file:**
- No in-memory state between iterations
- Fresh Claude Code context per iteration
- Git commits provide version history
- Progress logs provide audit trail

**Run directory structure:**
```
tools/feature-loop/runs/feature-my-feature/
├── progress.log              # Append-only iteration log
├── prd-snapshot.json         # PRD state at loop start
├── iteration-1-output.txt    # Full output from iteration 1
├── iteration-2-output.txt    # Full output from iteration 2
└── ...
```

## Specialist Routing

Tasks are delegated to Huxley agents based on the `specialist` field:

| Specialist Value | Resolved Agent | Domain |
|------------------|----------------|--------|
| Backend Dev | 🏛️ Backend Developer | APIs, databases, backend |
| Frontend Dev | 🎨 Frontend Developer | React, Next.js, web UI |
| Mobile Dev | 📱 Mobile Developer | iOS, React Native |
| UI Designer | 📐 UI Designer | UX, wireframes, prototypes |
| Automator | 🤖 Automator | n8n, shortcuts, automation |

See `.claude-context/agent-name-routing.json` for complete mapping.

## Quality Workflow

### Standard Flow (No Critical Issues)

1. Specialist implements task
2. Code Reviewer scans for issues
3. If `requireValidation: true`, Validator verifies acceptance criteria
4. Task marked as `passes: true`

### Error Flow (Critical Issues Found)

1. Specialist implements task
2. Code Reviewer finds critical issues
3. Debugger investigates root cause
4. Fix applied
5. Re-verify with Code Reviewer
6. If `requireValidation: true`, Validator verifies
7. Task marked as `passes: true`

### Failure Handling

If a task cannot be completed in one iteration:
- Diagnostic info added to `learnings` array
- Task remains `passes: false`
- Next iteration will retry

## Agent Memory Integration

When a task completes successfully, learnings are stored to Agent Memory:

```bash
# Automatic storage via MCP
mcp__builder-memory__create_memory({
  "agent_name": "{{ORCHESTRATOR_NAME}}",
  "memory_type": "episodic",
  "content": "Successfully implemented JWT auth using PyJWT with RS256...",
  "tags": ["feature-loop", "AUTH-001", "jwt", "authentication"],
  "importance": 0.7
})
```

Future iterations can retrieve relevant patterns:

```bash
mcp__builder-memory__search_memories({
  "query": "JWT authentication implementation"
})
```

## Configuration

### Environment Variables

```bash
# Maximum iterations (overrides PRD maxIterations)
export MAX_ITERATIONS=15

# Sleep duration between iterations (seconds)
export SLEEP_BETWEEN=10
```

### PRD Overrides

Settings in PRD take precedence over environment variables:

```json
{
  "maxIterations": 20,  // Overrides MAX_ITERATIONS env var
  "governance": {
    "costAlertThreshold": 10  // Custom threshold for this feature
  }
}
```

## Governance & Safety

### Hard Limits

- **Iteration cap**: Default 10, max 100 (prevents runaway loops)
- **Cost alerts**: Warnings at configurable threshold
- **Validation gates**: Optional quality enforcement

### Audit Trail

All iterations logged with:
- Timestamp
- Status (success/failure)
- Output file reference
- Completion status

### Notifications

macOS notifications sent on:
- Feature completion (all tasks passing)
- Max iterations reached (incomplete feature)

Disable with `"notifyOnComplete": false` in governance section.

## Examples

### Simple Backend Feature

```json
{
  "feature": "User Profile API",
  "branch": "feature/user-profile",
  "maxIterations": 5,
  "tasks": [
    {
      "id": "PROFILE-001",
      "title": "Create GET /users/:id endpoint",
      "description": "FastAPI endpoint that returns user profile data from Supabase",
      "specialist": "Backend Dev",
      "priority": 1,
      "acceptanceCriteria": [
        "Returns 200 with user data for valid ID",
        "Returns 404 for non-existent users"
      ],
      "passes": false
    }
  ]
}
```

### Full-Stack Feature

```json
{
  "feature": "Product Catalog",
  "branch": "feature/product-catalog",
  "maxIterations": 10,
  "governance": {
    "requireValidation": true,
    "costAlertThreshold": 5
  },
  "tasks": [
    {
      "id": "CAT-001",
      "title": "Design product listing UI",
      "specialist": "UI Designer",
      "priority": 1,
      "acceptanceCriteria": ["Wireframes approved", "Design system tokens defined"],
      "passes": false
    },
    {
      "id": "CAT-002",
      "title": "Create products table",
      "specialist": "Backend Dev",
      "priority": 2,
      "acceptanceCriteria": ["Migration applied", "RLS policies configured"],
      "passes": false
    },
    {
      "id": "CAT-003",
      "title": "Build product list component",
      "specialist": "Frontend Dev",
      "priority": 3,
      "acceptanceCriteria": ["Renders product grid", "Pagination works"],
      "passes": false
    }
  ]
}
```

## Troubleshooting

### Loop Doesn't Start

```bash
# Check PRD syntax
jq empty tasks/my-feature.json

# Validate schema
# (TODO: Add JSON schema validation command)

# Check permissions
ls -la tools/feature-loop/loop.sh
# Should show -rwxr-xr-x
```

### Iteration Fails

```bash
# Check iteration output
cat tools/feature-loop/runs/my-feature/iteration-N-output.txt

# Review progress log
tail -50 tools/feature-loop/runs/my-feature/progress.log

# Check PRD state
cat tasks/my-feature.json | jq .
```

### Max Iterations Reached

Possible causes:
- Tasks too complex for single iteration
- Acceptance criteria too strict
- Specialist agent issues

Solutions:
- Increase `maxIterations` in PRD
- Break tasks into smaller subtasks
- Simplify acceptance criteria
- Check specialist agent health

### Task Stuck on `passes: false`

```bash
# Check what specialist attempted
cat tools/feature-loop/runs/my-feature/iteration-N-output.txt

# Look for patterns in learnings
cat tasks/my-feature.json | jq '.tasks[] | select(.id=="TASK-ID") | .learnings'

# Try manual delegation to debug
# (in Claude Code session)
```

## Advanced Usage

### Custom Iteration Prompt

Modify `tools/feature-loop/iteration-prompt.md` to customize agent behavior per iteration.

### Conditional Validation

```json
{
  "tasks": [
    {
      "id": "CRITICAL-001",
      "title": "Payment processing",
      "specialist": "Backend Dev",
      "priority": 1,
      "acceptanceCriteria": ["Handles payment errors", "Logs all transactions"],
      "passes": false,
      "metadata": {
        "requireExtraValidation": true  // Custom flag
      }
    }
  ]
}
```

Adapt iteration prompt to check metadata and adjust validation intensity.

### Multi-Feature Orchestration

Run multiple feature loops in parallel (different branches):

```bash
# Terminal 1
./tools/feature-loop/loop.sh tasks/feature-a.json

# Terminal 2
./tools/feature-loop/loop.sh tasks/feature-b.json
```

Each runs independently with separate state.

## Comparison to Ralph

| Feature | Ralph | Huxley Feature Loop |
|---------|-------|------------------------|
| Iteration model | Fresh context per iteration | ✅ Same |
| State persistence | Files + git | ✅ PRD JSON + git |
| Agent orchestration | Single LLM | ✅ Specialist delegation |
| Quality gates | Manual | ✅ Code Reviewer + Validator |
| Learning capture | Append-only logs | ✅ Logs + Agent Memory |
| Governance | None | ✅ Configurable limits |
| Skill integration | Standalone | ✅ Huxley native |

## Best Practices

### PRD Design

1. **Start small**: 3-5 tasks for first loop, expand later
2. **Clear acceptance criteria**: Specific, measurable, testable
3. **Logical dependencies**: Use priority to enforce order
4. **Single responsibility**: One task = one specialist
5. **Iterative refinement**: Run short loops, adjust PRD based on learnings

### Task Sizing

- ✅ **Good**: "Create JWT generation endpoint with refresh tokens"
- ❌ **Too large**: "Implement entire authentication system"
- ❌ **Too small**: "Add import statement for PyJWT"

### Specialist Selection

- Match specialist to task domain
- Don't use BOSS/System Architect (stewardship agents) for implementation
- Use UI Designer for design, not Frontend Dev
- Use Debugger for investigation, not direct implementation

### Governance Tuning

- Start with `requireValidation: true` for critical features
- Increase `costAlertThreshold` for complex features (more iterations expected)
- Use `notifyOnComplete: false` for background loops

## Roadmap

Future enhancements:

- [ ] JSON schema validation in loop.sh
- [ ] PRD generator (AI-assisted PRD creation from feature description)
- [ ] Multi-feature dependency management
- [ ] Cost tracking per iteration (API usage metrics)
- [ ] Learning retrieval before task delegation (query Agent Memory)
- [ ] Parallel task execution (when no dependencies)
- [ ] Web UI for loop monitoring

## FAQ

**Q: Can I run multiple loops simultaneously?**
A: Yes, as long as they operate on different branches/files. Each loop is independent.

**Q: What happens if a specialist agent fails?**
A: {{ORCHESTRATOR_NAME}} will retry once, then implement as fallback if second failure. See CLAUDE.md orchestration section.

**Q: Can I pause and resume a loop?**
A: Not directly. You can stop the loop (Ctrl+C), edit the PRD to adjust tasks, then restart. State is in PRD file.

**Q: How do I debug a failing task?**
A: Check the iteration output file for that iteration. Review learnings in PRD. Run task manually via Claude Code to diagnose.

**Q: Does this work for non-code tasks?**
A: Yes. UI Designer can create designs, Content Marketer can write copy, etc. Adapt acceptance criteria accordingly.

**Q: Can I use this for infrastructure/DevOps tasks?**
A: Yes. Delegate to Backend Dev for deployment, CI/CD, etc. Use validation to verify infrastructure state.

## See Also

- [Ralph - Autonomous AI Development](https://github.com/snarktank/ralph)
- [Huxley Orchestration Guide](.claude-context/CLAUDE-orchestration.md)
- [Agent Memory System](global/docs/Agent_Memory_System.md)
- [Quality Workflow](global/docs/Quality_Workflow.md)

---

**Feature Loop** - Autonomous development for Huxley. Build everything {{USER_NAME}} needs, when they need it.
