# Huxley MCP Server - Quick Reference

**Fast reference for common operations**

---

## Usage in Claude Code

Just ask naturally! Claude will use the MCP tools automatically.

### Common Requests

```
Create a task...
Show me tasks for [capsule]...
Search for tasks about [topic]...
Mark task-[id] as completed
What tasks are blocked?
Show me active tasks
```

---

## MCP Tools (5)

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `create_task` | Create new task | title, capsule, priority, assigned_agent |
| `update_task_status` | Update status | task_id, status |
| `get_task_tree` | Task hierarchy | root_id (optional), capsule (optional) |
| `search_tasks` | Full-text search | query, status, capsule, limit |
| `link_document` | Link file to task | task_id, file_path, link_type |

---

## MCP Resources (4)

| URI Pattern | Description |
|-------------|-------------|
| `catalyst://tasks/active` | All active tasks |
| `catalyst://tasks/active/{capsule}` | Active tasks for capsule |
| `catalyst://tasks/blocked` | All blocked tasks |
| `catalyst://tasks/{task_id}/context` | Full task context |

---

## Task Statuses

- `pending` - Not started
- `in_progress` - Currently working
- `blocked` - Waiting on dependency
- `completed` - Finished
- `archived` - Historical record

---

## Priority Levels

- `low` - Nice to have
- `medium` - Normal priority
- `high` - Important
- `critical` - Urgent/blocking

---

## Common Capsules

- `example-mobile-capsule` - Mobile app
- `example-capsule` - Huxley system
- `example-media-capsule` - Media server
- `capsules/design-system` - Design system
- `example-social-capsule` - Social media tool

---

## Link Types (for documents)

- `spec` - Specification document
- `research` - Research notes
- `reference` - Reference material
- `output` - Generated output

---

## Database Location

```
{{CATALYST_ROOT}}/tasks.db
```

---

## Configuration File

```
{{CATALYST_ROOT}}/.mcp.json
```

---

## Useful Commands

```bash
# View all tasks
sqlite3 tasks.db "SELECT * FROM tasks;"

# Count by status
sqlite3 tasks.db "SELECT status, COUNT(*) FROM tasks GROUP BY status;"

# Rebuild MCP server
cd tools/catalyst-mcp && npm run build

# Run integration tests
cd tools/catalyst-mcp && ./test-integration.sh

# View server logs (when running manually)
cd tools/catalyst-mcp && ./start.sh
```

---

## Example: Create Task Workflow

**1. Ask Claude:**
```
Create a high priority task in example-mobile-capsule for implementing biometric auth.
Assign to Mobile Dev and tag with security and ios.
```

**2. Claude calls `create_task`:**
```json
{
  "title": "Implement biometric authentication",
  "priority": "high",
  "capsule": "example-mobile-capsule",
  "assigned_agent": "📱 Mobile Dev",
  "tags": ["security", "ios"]
}
```

**3. You get back:**
```json
{
  "success": true,
  "task_id": "task-abc123"
}
```

**4. Later, mark it done:**
```
Mark task-abc123 as completed.
```

---

## Troubleshooting

**Server not starting?**
```bash
node --version  # Check Node.js
ls -la {{CATALYST_ROOT}}/tasks.db  # Check database
cat .mcp.json  # Check config
```

**Tools not appearing?**
1. Restart Claude Code
2. Check MCP settings in Claude Code
3. Verify `.mcp.json` exists

**Database errors?**
```bash
sqlite3 tasks.db "PRAGMA integrity_check;"
```

---

## Key Files

```
tools/catalyst-mcp/
├── README.md              - Full documentation
├── EXAMPLES.md            - Usage examples
├── QUICK_REFERENCE.md     - This file
├── start.sh               - Startup script
├── src/
│   ├── index.ts          - Main server
│   ├── tools.ts          - 5 tools
│   ├── resources.ts      - 3 resources
│   └── database.ts       - DB queries
└── .mcp.json      - Claude config
```

---

## Agent Name Format

When assigning tasks to agents, use emoji + name:

- `📱 Mobile Dev`
- `🏛️ Backend Developer`
- `🎨 Frontend Developer`
- `📐 UI Designer`
- `🤖 Automator`
- `🐲 Bowser`

---

## Next Steps After Integration

1. Ask Claude: "How many tasks are in the database?"
2. Create a real task for current work
3. Search for tasks by keyword
4. View task hierarchy for a capsule
5. Link spec documents to tasks

---

**For full documentation, see README.md**
**For examples, see EXAMPLES.md**
