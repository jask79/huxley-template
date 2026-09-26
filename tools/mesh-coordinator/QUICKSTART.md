# Mesh Coordinator Quick Start

Get the mesh coordinator running in 3 steps.

## Step 0: Build the server

```bash
cd {{CATALYST_ROOT}}/tools/mesh-coordinator && npm install && npm run build
```

## Step 1: Create Database Table

```bash
sqlite3 {{CATALYST_ROOT}}/monitoring/quality.db < {{CATALYST_ROOT}}/tools/mesh-coordinator/schema.sql
```

**Verify:**
```bash
sqlite3 {{CATALYST_ROOT}}/monitoring/quality.db "SELECT name FROM sqlite_master WHERE type='table' AND name='mesh_communications';"
```

Should output: `mesh_communications`

## Step 2: Add to MCP Config

Edit your Claude Code config (usually `~/.claude/config.json` or global Huxley config):

```json
{
  "mcpServers": {
    "mesh-coordinator": {
      "command": "node",
      "args": ["{{CATALYST_ROOT}}/tools/mesh-coordinator/dist/index.js"],
      "env": {
        "CATALYST_QUALITY_DB": "{{CATALYST_ROOT}}/monitoring/quality.db"
      }
    }
  }
}
```

**Restart Claude Code** to load the new MCP server.

## Step 3: Test It

In a Claude Code session, call the mesh coordinator:

```typescript
// Example: Frontend Developer requests help from Backend Developer
mcp__mesh-coordinator__request_peer_help({
  from_agent: "🎨 Frontend Developer",
  to_agent: "🏛️ Backend Developer",
  request_type: "api-design",
  context: "Need REST endpoint for user preferences with filtering and pagination",
  urgency: "blocking"
})
```

**Expected response:**
```json
{
  "session_id": "mesh-1701234567-xyz789",
  "status": "allowed",
  "message": "Request approved. Session ID: mesh-1701234567-xyz789. 🏛️ Backend Developer has been notified via {{ORCHESTRATOR_NAME}}."
}
```

**Verify in database:**
```bash
sqlite3 {{CATALYST_ROOT}}/monitoring/quality.db "SELECT * FROM mesh_communications ORDER BY timestamp DESC LIMIT 5;"
```

## Common Issues

### Issue: "no such table: mesh_communications"

**Fix:** Run Step 1 again to create the table.

### Issue: MCP server not loading

**Fix:**
1. Check the server builds: `cd {{CATALYST_ROOT}}/tools/mesh-coordinator && npm run build`
2. Verify path in MCP config is correct
3. Restart Claude Code

### Issue: Request blocked

**Fix:** Check the capability mapping in `src/registry.ts`. Only certain agent pairs can communicate.

## What's Next?

- **Read README.md** - Comprehensive documentation
- **Read IMPLEMENTATION_SUMMARY.md** - Technical details
- **Check schema.sql** - Example queries for monitoring
- **Edit src/registry.ts** - Add more agents or capabilities

## Tool Reference

### request_peer_help
Request help from a peer agent.

### discover_capabilities
Find which agent has a specific capability.

### broadcast_status
Announce completion or blockers.

### get_mesh_activity
({{ORCHESTRATOR_NAME}} only) View all mesh communications.

---

**You're ready to enable mesh agent communication!**
