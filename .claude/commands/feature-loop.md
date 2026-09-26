# Feature Loop - Autonomous Development Skill

Runs autonomous iterative development sessions until a PRD is complete.

## Usage

```bash
/feature-loop <prd-file-path>
```

## Arguments

- `prd-file-path` - Path to PRD JSON file (absolute or relative to Huxley root)

## Description

The Feature Loop skill enables autonomous feature development by:

1. **Loading PRD**: Reads task list, priorities, acceptance criteria
2. **Iterative Sessions**: Runs fresh Claude Code sessions until complete
3. **Specialist Delegation**: Routes tasks to appropriate agents
4. **Quality Gates**: Validates implementation before marking complete
5. **Learning Capture**: Stores patterns to Agent Memory
6. **Progress Tracking**: Maintains append-only audit trail

## How It Works

Each iteration:
- Identifies highest-priority incomplete task
- Delegates to specialist agent (Backend Dev, Frontend Dev, etc.)
- Runs validation checks (Code Reviewer → Validator)
- Updates PRD with results
- Stores learnings to Agent Memory
- Checks if all tasks pass → exit if complete
- Otherwise continues to next iteration

## Governance

- **Hard iteration cap**: Default 10, configurable per PRD
- **Cost awareness**: Alerts at configurable threshold
- **Validation requirement**: Optional quality gate enforcement
- **Notification**: Terminal alert on completion/failure
- **Audit trail**: All iterations logged with timestamps

## PRD Format

See `{{CATALYST_ROOT}}/tools/feature-loop/prd-schema.json` for full schema.

Example:
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
      "description": "Create endpoint for JWT generation with refresh tokens",
      "specialist": "Backend Dev",
      "priority": 1,
      "acceptanceCriteria": [
        "Returns valid JWT on successful auth",
        "Includes refresh token in response",
        "Tokens expire correctly"
      ],
      "passes": false
    }
  ]
}
```

## Examples

```bash
# Run feature loop for auth feature
/feature-loop tasks/auth-feature.json

# Run with custom max iterations
MAX_ITERATIONS=15 /feature-loop tasks/complex-feature.json

# Monitor progress
tail -f tools/feature-loop/runs/feature-user-auth/progress.log
```

## Implementation

The skill invokes `{{CATALYST_ROOT}}/tools/feature-loop/loop.sh` which:
- Validates PRD existence and schema
- Creates run directory for progress tracking
- Executes iterations using `claude` CLI
- Monitors for completion signal
- Handles failures and notifications

## Integration

- **Agent Memory**: Successful patterns stored after task completion
- **TodoWrite**: Active tasks visible during execution
- **Quality Stack**: Code Reviewer → Debugger → Validator workflow
- **Git**: All changes committed per iteration

## Safety

- Requires explicit PRD file (no default behavior)
- Iteration cap prevents runaway loops
- Cost tracking with configurable alerts
- Optional validation gates for safety-critical features
- Append-only logs for full audit trail

---

**See also:**
- PRD Schema: `tools/feature-loop/prd-schema.json`
- Example PRD: `tools/feature-loop/prd-example.json`
- Documentation: `tools/feature-loop/README.md`
