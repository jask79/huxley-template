# Huxley TaskMaster Guide

**Version:** 1.0
**Last Updated:** 2025-01-27
**Status:** Production

---

## Overview

**TaskMaster** is Huxley's work item tracking system for managing persistent tasks across all capsules. Each capsule maintains its own `tasks.json` file for tracking work items with full lifecycle management, audit trails, and framework integration.

**Important:** TaskMaster is separate from Claude Code's "Task tool" (which invokes specialist agents like Mobile Dev or Frontend Dev). TaskMaster manages persistent work items that you drop into capsules from the mobile app or web dashboard.

### Key Features

- **Standardized Format:** All capsules use the same YAML schema
- **Full Lifecycle:** Track tasks from creation through completion with audit history
- **Framework Integration:** Link tasks to specs, milestones, and quality standards
- **CLI Management:** Complete CRUD operations via `task_manager.py`
- **Queue-Ready:** Designed for future task dropping from Telegram/API
- **Multi-Capsule Views:** Aggregate statistics and filtering across all capsules

---

## Terminology

- **TaskMaster:** The work item tracking system (what this guide covers)
- **Task Tool:** Claude Code's agent invocation system (used by {{ORCHESTRATOR_NAME}} to coordinate specialists)
- **Work Item / Task:** Individual items tracked in tasks.json files

---

## Quick Start

### View All Tasks

```bash
# List all tasks across all capsules
python3 tools/task_manager.py list

# Filter by capsule
python3 tools/task_manager.py list --capsule example-media-capsule

# Filter by status
python3 tools/task_manager.py list --status pending

# Filter by priority
python3 tools/task_manager.py list --priority high

# Combine filters
python3 tools/task_manager.py list --capsule ops --status in_progress --priority high
```

### Add a Task

```bash
# Basic task
python3 tools/task_manager.py add example-mobile-capsule "Add dark mode toggle to settings"

# With priority and tags
python3 tools/task_manager.py add example-mobile-capsule \
  "Add dark mode toggle to settings" \
  --priority medium \
  --tags ui settings theming

# With agent assignment
python3 tools/task_manager.py add example-mobile-capsule \
  "Add dark mode toggle" \
  --priority high \
  --agent "📱 Mobile Dev" \
  --notes "Use system appearance detection as default"
```

### Update a Task

```bash
# Update status
python3 tools/task_manager.py update example-mobile-capsule task-abc123 --status in_progress

# Update priority
python3 tools/task_manager.py update example-mobile-capsule task-abc123 --priority high

# Assign to agent
python3 tools/task_manager.py update example-mobile-capsule task-abc123 --agent "📱 Mobile Dev"

# Update description
python3 tools/task_manager.py update example-mobile-capsule task-abc123 \
  --description "Add dark mode toggle with system sync"
```

### Complete a Task

```bash
# Mark as completed
python3 tools/task_manager.py complete example-media-capsule 62debbfe
```

### Delete a Task

```bash
# Permanently remove task
python3 tools/task_manager.py delete example-mobile-capsule task-abc123
```

### View Statistics

```bash
# Overall stats across all capsules
python3 tools/task_manager.py stats
```

### Smart Capsule Routing

```bash
# Suggest capsule based on task description
python3 tools/task_manager.py suggest "fix media-server download automation"
# Output: 💡 Suggested capsule: example-media-capsule

python3 tools/task_manager.py suggest "build mobile app feature"
# Output: 💡 Suggested capsule: example-mobile-capsule
```

---

## JSON Schema

### File Structure

Each capsule has a `tasks.json` file with this structure:

```json
// Huxley TaskMaster Schema v1.0
# Capsule: [capsule-name]
# Updated: [timestamp]

metadata:
  version: "1.0"
  capsule: "[capsule-name]"
  last_updated: "2025-01-27T00:00:00Z"
  task_count: 5
  active_count: 3
  completed_count: 2

tasks:
  - id: "task-abc123"
    description: "Human-readable task description"
    status: pending  # pending|in_progress|blocked|completed|archived
    priority: medium  # low|medium|high|critical

    created: "2025-01-27T10:00:00Z"
    updated: "2025-01-27T10:00:00Z"
    completed_at: null

    assigned_agent: null  # Agent emoji+name or null
    source: manual  # manual|telegram|api|automation|dependency

    dependencies:
      required: []  # Must complete before this task
      blocks: []    # This task blocks these tasks
      related: []   # Related but not blocking

    framework:
      spec_section: null        # Links to specs/current.yaml
      milestone: null           # Links to product.yaml
      standard_refs: []         # References to standards.yaml
      test_coverage: null       # Links to tests

    tags: []
    estimate_hours: null
    actual_hours: null

    notes: |
      Additional context, decisions, blockers

    history:
      - timestamp: "2025-01-27T10:00:00Z"
        event: created
        agent: "{{ORCHESTRATOR_NAME}}"
        details: "Task created from Telegram queue"

archived_tasks: []  # Completed tasks moved here

queue:
  enabled: true
  auto_assign: false
  priority_threshold: "medium"
```

### Task Statuses

- **pending:** Not yet started, waiting in queue
- **in_progress:** Currently being worked on
- **blocked:** Waiting on external dependency or blocker
- **completed:** Finished and verified
- **archived:** Historical record (moved to archived_tasks)

### Priority Levels

- **low:** Nice to have, no urgency
- **medium:** Normal priority, address when possible
- **high:** Important, should be addressed soon
- **critical:** Blocking or urgent, requires immediate attention

### Task Sources

- **manual:** Created directly by user via CLI
- **telegram:** Created via Telegram queue (future)
- **api:** Created via API call (future)
- **automation:** Auto-generated by system
- **dependency:** Created as dependency of another task

---

## Framework Integration

Tasks can link directly to capsule framework files for traceability.

### Linking to Specifications

```yaml
framework:
  spec_section: "authentication.oauth"  # References specs/current.yaml
```

In `specs/current.yaml`:
```yaml
authentication:
  oauth:
    providers: ["google", "github"]
    # Implementation tracked in tasks.yaml:task-abc123
```

### Linking to Milestones

```yaml
framework:
  milestone: "v1.0-mvp"  # References product.yaml
```

In `product.yaml`:
```yaml
milestones:
  - id: "v1.0-mvp"
    target: "2025-02-15"
    tasks_ref: "tasks.yaml"
    completion: "75%"
```

### Linking to Standards

```yaml
framework:
  standard_refs:
    - "security.auth-requirements"
    - "testing.coverage-80-percent"
```

In `standards.yaml`:
```yaml
security:
  auth-requirements:
    - "OAuth2 with PKCE"
    - "Secure token storage"
```

---

## Workflow Examples

### Example 1: Feature Development

```bash
# 1. Add task for new feature
python3 tools/task_manager.py add example-mobile-capsule \
  "Implement biometric authentication" \
  --priority high \
  --tags security auth feature

# 2. Start working on it
python3 tools/task_manager.py update example-mobile-capsule task-xyz789 \
  --status in_progress \
  --agent "📱 Mobile Dev"

# 3. Complete the task
python3 tools/task_manager.py complete example-mobile-capsule task-xyz789
```

### Example 2: Bug Fix

```bash
# 1. Add bug task
python3 tools/task_manager.py add example-media-capsule \
  "Fix download automation timing issue" \
  --priority critical \
  --tags bug automation \
  --notes "Downloads failing after 10pm due to scheduler conflict"

# 2. Assign to appropriate agent
python3 tools/task_manager.py update example-media-capsule task-bug456 \
  --agent "🤖 Automator"

# 3. Track progress
python3 tools/task_manager.py update example-media-capsule task-bug456 \
  --status in_progress

# 4. Complete
python3 tools/task_manager.py complete example-media-capsule task-bug456
```

### Example 3: Task Dependencies

Manually edit `tasks.yaml` to add dependencies:

```yaml
tasks:
  - id: "task-design"
    description: "Design dark mode color palette"
    status: completed
    # ... other fields

  - id: "task-implement"
    description: "Implement dark mode UI"
    status: in_progress
    dependencies:
      required: ["task-design"]  # Requires design task
      blocks: ["task-testing"]    # Blocks testing task
    # ... other fields

  - id: "task-testing"
    description: "Test dark mode on all screens"
    status: pending
    dependencies:
      required: ["task-implement"]  # Can't test until implemented
    # ... other fields
```

---

## Huxley System Tasks

System-level tasks (framework evolution, tooling, infrastructure) are tracked in a special capsule:

**Location:** `{{CATALYST_ROOT}}/capsules/example-capsule/tasks.yaml`

This separates Huxley system work from project-specific capsules.

### Example: Adding System Task

```bash
python3 tools/task_manager.py add example-capsule \
  "Implement automated capsule health checks" \
  --priority medium \
  --tags infrastructure monitoring automation \
  --agent "🏗️ System Architect"
```

---

## Migration from JSON

If you have existing `tasks.json` files, migrate them to YAML:

```bash
# Migrate single capsule
python3 tools/task_manager.py migrate example-media-capsule

# Migrate all capsules at once
python3 tools/task_manager.py migrate --all
```

**What migration does:**
1. Reads `tasks.json`
2. Creates `tasks.yaml` with full schema structure
3. Preserves all task data and metadata
4. Backs up original JSON to `tasks.json.backup`

**Backward compatibility:**
- Tool automatically reads JSON if YAML doesn't exist
- No immediate migration required
- Files auto-upgrade to YAML on next save

---

## Future: Queue-Based Task Dropping

The schema is designed to support queue-based task creation from Telegram, APIs, and automation:

```yaml
queue:
  enabled: true
  auto_assign: true  # Auto-route to appropriate agent
  priority_threshold: "medium"  # Auto-surface tasks above this priority
```

### Planned Queue Features

- **Telegram Integration:** Send tasks to capsules via Telegram messages
- **Smart Routing:** {{ORCHESTRATOR_NAME}} automatically routes tasks to correct capsule
- **Auto-Assignment:** Tasks auto-assigned to appropriate specialist agents
- **Priority Surfacing:** High-priority tasks automatically notify user

---

## Best Practices

### Task Descriptions

**Good:**
- "Add dark mode toggle to settings screen"
- "Fix download automation timing issue after 10pm"
- "Implement OAuth2 authentication with Google provider"

**Bad:**
- "Fix bug" (too vague)
- "Update UI" (not specific)
- "Do the thing" (not actionable)

### Using Tags

```bash
# Feature categories
--tags feature ui mobile

# Bug tracking
--tags bug critical authentication

# Work types
--tags refactor optimization performance

# Components
--tags api database frontend
```

### Estimating Time

```yaml
estimate_hours: 4    # Initial estimate
actual_hours: 6.5    # Actual time spent
```

**Purpose:** Track estimates vs actuals to improve future planning.

### Writing Notes

```yaml
notes: |
  Context: User reported authentication failures on iOS 16.

  Investigation: Token refresh logic has race condition when app backgrounds.

  Solution: Implement token lock mechanism with retry backoff.

  Testing: Verified on iOS 16.1, 16.4, and 17.0.
```

### Audit History

History is auto-generated but can be manually added for important decisions:

```yaml
history:
  - timestamp: "2025-01-27T10:00:00Z"
    event: created
    agent: "{{ORCHESTRATOR_NAME}}"
    details: "Task created from Telegram"

  - timestamp: "2025-01-27T14:30:00Z"
    event: status_change
    agent: "📱 Mobile Dev"
    details: "Started implementation"

  - timestamp: "2025-01-28T09:00:00Z"
    event: updated
    agent: "📱 Mobile Dev"
    details: "Pivoted to alternative approach after discovering iOS SDK limitation"
```

---

## Troubleshooting

### Tasks Not Showing Up

**Problem:** `python3 tools/task_manager.py list` returns empty

**Solution:**
1. Check if `tasks.yaml` exists in capsule directory
2. Verify YAML syntax (use `yamllint` or Python YAML parser)
3. Ensure `tasks:` array exists in YAML structure

### Migration Failed

**Problem:** `migrate --all` reports errors

**Solution:**
1. Check that `tasks.json` exists in capsule directory
2. Verify JSON is valid
3. Check file permissions
4. Review error message for specific capsule

### Can't Update Task

**Problem:** Task update command returns "not found"

**Solution:**
1. Verify task ID is correct (`list` command shows IDs)
2. Check you're using correct capsule name
3. Ensure task hasn't been deleted or archived

---

## Schema Reference

**Complete schema:** `{{CATALYST_ROOT}}/recipes/schema/taskmaster-schema-v1.json`

**Template:** `{{CATALYST_ROOT}}/recipes/framework-templates/base/tasks.yaml.template`

**Tool:** `{{CATALYST_ROOT}}/tools/task_manager.py`

---

## Related Documentation

- **API Key Management:** `global/docs/API_Key_Management.md`
- **Capsule Framework:** `recipes/framework-templates/specs-current.yaml.template`
- **Agent Orchestration:** `global/docs/Agent_Orchestration_Guide.md` (Claude Code's Task tool for agent invocation)
- **CLAUDE.md:** Main Huxley operating instructions

---

*Last updated: 2025-01-27*
*Schema version: 1.0*
