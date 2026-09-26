# Huxley MCP Server - Testing Guide

**How to verify the MCP server is working correctly**

---

## Quick Verification

### Test 1: Check MCP Server is Recognized

**Ask Claude:**
```
What MCP servers are currently available?
```

**Expected:** You should see `Huxley-tasks` in the list.

---

### Test 2: Query Task Count

**Ask Claude:**
```
How many tasks are currently in the Huxley task database?
```

**Expected:** Claude should respond with the current count (42+ tasks).

**What happens:** Claude reads the `catalyst://tasks/active` resource or uses `search_tasks`.

---

### Test 3: Create a Test Task

**Ask Claude:**
```
Create a test task in the test-capsule with medium priority.
The description should be "MCP integration test task".
```

**Expected:** Claude creates the task and returns a task ID.

**What happens:** Claude calls the `create_task` tool.

**Verify:**
```bash
sqlite3 {{CATALYST_ROOT}}/tasks.db \
  "SELECT * FROM tasks WHERE description LIKE '%MCP integration%';"
```

---

### Test 4: Search for Tasks

**Ask Claude:**
```
Search for all tasks related to authentication.
```

**Expected:** Claude returns a list of authentication-related tasks.

**What happens:** Claude calls `search_tasks` with "authentication" query.

---

### Test 5: View Task Hierarchy

**Ask Claude:**
```
Show me the task tree for example-media-capsule capsule.
```

**Expected:** Claude displays hierarchical task structure with parent/child relationships.

**What happens:** Claude calls `get_task_tree` with capsule filter.

---

### Test 6: Update Task Status

**Ask Claude:**
```
Create a task called "Test status update" in test-capsule.
Then mark it as completed.
```

**Expected:**
1. Task is created
2. Task status is updated to "completed"
3. `completed_at` timestamp is set

**What happens:**
1. Claude calls `create_task`
2. Claude calls `update_task_status`

---

### Test 7: View Blocked Tasks

**Ask Claude:**
```
Show me all tasks that are currently blocked.
```

**Expected:** Claude lists blocked tasks with their details.

**What happens:** Claude reads `catalyst://tasks/blocked` resource.

---

### Test 8: View Active Tasks for Capsule

**Ask Claude:**
```
What are the active tasks for example-mobile-capsule?
```

**Expected:** Claude lists active (pending/in_progress) tasks for that capsule.

**What happens:** Claude reads `catalyst://tasks/active/example-mobile-capsule` resource.

---

### Test 9: Get Full Task Context

**Ask Claude:**
```
Show me the full context for task-mobile001 including dependencies and documents.
```

**Expected:** Claude shows:
- Task details
- Dependencies
- Linked documents
- Child tasks

**What happens:** Claude reads `catalyst://tasks/task-mobile001/context` resource.

---

### Test 10: Link Document to Task

**Ask Claude:**
```
Create a test task in test-capsule.
Link the file at {{CATALYST_ROOT}}/CLAUDE.md to it as a reference document.
```

**Expected:**
1. Task is created
2. Document is linked with type "reference"

**What happens:**
1. Claude calls `create_task`
2. Claude calls `link_document`

**Verify:**
```bash
sqlite3 {{CATALYST_ROOT}}/tasks.db \
  "SELECT d.file_path, td.link_type FROM task_documents td
   JOIN documents d ON td.document_id = d.id
   WHERE d.file_path LIKE '%CLAUDE.md%';"
```

---

## Manual Server Testing

### Start Server Manually

```bash
cd {{CATALYST_ROOT}}/tools/catalyst-mcp
./start.sh
```

**Expected Output:**
```
[Huxley MCP] Starting Huxley MCP Server v1.0.0
[Huxley MCP] Database: {{CATALYST_ROOT}}/tasks.db
[Huxley MCP] Connected to database: {{CATALYST_ROOT}}/tasks.db
[Huxley MCP] Database initialized successfully
[Huxley MCP] Database schema initialized
[Huxley MCP] Server started and ready for requests
```

**Note:** Server will wait for stdin input (MCP protocol). Press Ctrl+C to exit.

---

## Integration Tests

### Run Full Test Suite

```bash
cd {{CATALYST_ROOT}}/tools/catalyst-mcp
./test-integration.sh
```

**Expected Output:**
```
====================================================
Huxley MCP Server Integration Test
====================================================

1. Verifying database...
   ✅ Database exists: {{CATALYST_ROOT}}/tasks.db

2. Checking database tables...
   ✅ Found tables:
      - documents
      - tasks
      - task_dependencies
      - task_documents
      - tasks_fts
      ...

3. Verifying build...
   ✅ Build verified

4. Testing database queries...
   ✅ Created test task
   ✅ Successfully queried test task
   ✅ Cleaned up test task

5. Checking TypeScript compilation...
   ✅ TypeScript compilation successful

====================================================
Integration Test Summary
====================================================
✅ Database: OK
✅ Schema: OK
✅ Build: OK
✅ Queries: OK

MCP Server is ready for use with Claude Code!
```

---

## Database Verification

### Check Task Statistics

```bash
sqlite3 {{CATALYST_ROOT}}/tasks.db \
  "SELECT status, COUNT(*) as count FROM tasks GROUP BY status;"
```

**Expected Output:**
```
blocked|1
completed|3
in_progress|4
pending|34
```

### View Recent Tasks

```bash
sqlite3 {{CATALYST_ROOT}}/tasks.db \
  "SELECT id, description, status, capsule FROM tasks
   ORDER BY created_at DESC LIMIT 5;"
```

### Test Full-Text Search

```bash
sqlite3 {{CATALYST_ROOT}}/tasks.db \
  "SELECT id, description FROM tasks_fts
   WHERE tasks_fts MATCH 'authentication'
   LIMIT 5;"
```

---

## Troubleshooting Tests

### Test Fails: Database Not Found

**Symptom:** `Database not found` error

**Fix:**
```bash
cd {{CATALYST_ROOT}}
sqlite3 tasks.db < api/db/schema.sql
```

### Test Fails: TypeScript Compilation

**Symptom:** `tsc` errors

**Fix:**
```bash
cd {{CATALYST_ROOT}}/tools/catalyst-mcp
rm -rf dist node_modules
npm install
npm run build
```

### Test Fails: Server Won't Start

**Symptom:** Server exits immediately or fails to start

**Check Node.js:**
```bash
node --version
# Should show v18 or higher
```

**Check Permissions:**
```bash
ls -la {{CATALYST_ROOT}}/tools/catalyst-mcp/start.sh
# Should be executable (-rwxr-xr-x)
```

**Check Database Permissions:**
```bash
ls -la {{CATALYST_ROOT}}/tasks.db
# Should be writable by your user
```

---

## Claude Code Verification

### Check MCP Configuration

```bash
cat {{CATALYST_ROOT}}/.mcp.json
```

**Expected:**
```json
{
  "mcpServers": {
    "Huxley-tasks": {
      "command": "{{CATALYST_ROOT}}/tools/catalyst-mcp/start.sh",
      "env": {
        "CATALYST_DB": "{{CATALYST_ROOT}}/tasks.db"
      }
    }
  }
}
```

### Restart Claude Code

After any configuration changes:
1. Quit Claude Code completely
2. Restart Claude Code
3. The MCP server should start automatically

### View MCP Logs in Claude Code

When using MCP tools, Claude Code may show server logs. Look for:
```
[Huxley MCP] Tool called: create_task
[Huxley MCP] Arguments: {...}
```

---

## Success Criteria

All tests should pass if:

✅ Database exists at `{{CATALYST_ROOT}}/tasks.db`
✅ Schema is initialized (10+ tables)
✅ TypeScript compiles without errors
✅ Server starts and listens for requests
✅ Claude Code recognizes the MCP server
✅ Tools can be called successfully
✅ Resources can be read successfully
✅ Database queries return expected results

---

## Sample Test Session

**Complete test flow in Claude Code:**

```
Me: How many tasks are in the database?
Claude: [Reads resource] There are 42 tasks in the database.

Me: Create a test task in test-capsule with description "Integration test"
Claude: [Calls create_task] Created task with ID task-xyz789

Me: Search for tasks about "test"
Claude: [Calls search_tasks] Found 3 tasks: ...

Me: Mark task-xyz789 as completed
Claude: [Calls update_task_status] Task marked as completed.

Me: Show me all blocked tasks
Claude: [Reads resource] There is 1 blocked task: ...
```

---

## Cleanup Test Data

After testing, you may want to clean up test tasks:

```bash
sqlite3 {{CATALYST_ROOT}}/tasks.db \
  "DELETE FROM tasks WHERE capsule = 'test-capsule';"
```

Or delete specific test tasks:

```bash
sqlite3 {{CATALYST_ROOT}}/tasks.db \
  "DELETE FROM tasks WHERE description LIKE '%test%';"
```

---

## Continuous Verification

### Daily Health Check

```bash
cd {{CATALYST_ROOT}}/tools/catalyst-mcp
./test-integration.sh
```

### Before Important Work

1. Run integration tests
2. Verify database integrity
3. Check task counts match expectations
4. Test a simple create/update/search flow

---

## What to Test After Updates

### After Code Changes

1. Run `npm run build`
2. Run integration tests
3. Test all 5 tools manually
4. Test all 4 resources manually

### After Database Schema Changes

1. Backup existing database
2. Run schema migration
3. Verify all indexes exist
4. Run integration tests
5. Test FTS5 search

### After MCP SDK Updates

1. Update package.json
2. Run `npm install`
3. Rebuild server
4. Test protocol compatibility
5. Verify all tools still work

---

## Getting Help

If tests fail:

1. **Check this guide** - Most common issues are documented
2. **Run integration tests** - They provide detailed error messages
3. **Check server logs** - Start server manually to see full output
4. **Verify database** - Use SQLite commands to check data
5. **Review documentation** - README.md has troubleshooting section

---

