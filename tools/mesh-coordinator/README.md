# Mesh Coordinator MCP Server

**Version:** 1.0.0
**MCP Spec:** 2025-06-18

## Overview

The Mesh Coordinator enables supervised peer-to-peer communication between Huxley specialist agents while maintaining {{ORCHESTRATOR_NAME}} oversight. All agent-to-agent requests are logged to `quality.db` for full auditability.

## Purpose

Instead of all communication going through {{ORCHESTRATOR_NAME}}, specialist agents can request help directly from peers for tactical collaboration while strategic oversight remains centralized. This reduces bottlenecks while maintaining governance.

**Example:** Frontend Developer can ask Backend Developer for API design help without waiting for {{ORCHESTRATOR_NAME}} to orchestrate the request.

## Architecture

```
┌──────────────┐         ┌──────────────────┐         ┌──────────────┐
│  Agent A     │────────>│ Mesh Coordinator │────────>│  Agent B     │
│ (requests)   │         │  (validates &    │         │ (receives)   │
└──────────────┘         │   logs)          │         └──────────────┘
                         └──────────────────┘
                                  │
                                  v
                         ┌──────────────────┐
                         │   quality.db     │
                         │ (audit trail)    │
                         └──────────────────┘
                                  │
                                  v
                         ┌──────────────────┐
                         │     {{ORCHESTRATOR_NAME}}       │
                         │  (oversight)     │
                         └──────────────────┘
```

## MCP Tools

### 1. `request_peer_help`

Request assistance from a peer agent.

**Parameters:**
- `from_agent` (string, required) - Requesting agent name with emoji (e.g., "🎨 Frontend Developer")
- `to_agent` (string, required) - Target agent name with emoji (e.g., "🏛️ Backend Developer")
- `request_type` (string, required) - Type of help needed (e.g., "api-design", "accessibility-audit")
- `context` (string, required) - Detailed context about what help is needed
- `urgency` (enum, optional) - One of: `blocking`, `nice_to_have`, `fyi` (default: `nice_to_have`)

**Returns:**
```json
{
  "session_id": "mesh-1234567890-abc123",
  "status": "allowed",
  "message": "Request approved. Session ID: mesh-1234567890-abc123. 🏛️ Backend Developer has been notified via {{ORCHESTRATOR_NAME}}."
}
```

**Blocked Example:**
```json
{
  "session_id": "mesh-1234567890-abc123",
  "status": "blocked",
  "message": "Request blocked: 👔 BOSS requires {{ORCHESTRATOR_NAME}} oversight",
  "block_reason": "Agent 👔 BOSS cannot be requested directly. All requests must go through {{ORCHESTRATOR_NAME}}."
}
```

### 2. `discover_capabilities`

Find which agent can help with a specific capability.

**Parameters:**
- `capability` (string, required) - Capability to search for (e.g., "authentication", "css-styling")

**Returns:**
```json
{
  "capability": "authentication",
  "agents": [
    {
      "agent_name": "🏛️ Backend Developer",
      "provides": ["api-design", "database-schema", "authentication", "cloudflare-config"]
    }
  ]
}
```

### 3. `broadcast_status`

Announce completion, blockers, or status updates.

**Parameters:**
- `from_agent` (string, required) - Broadcasting agent name with emoji
- `status` (string, required) - Status type (e.g., "completed", "blocked", "in_progress")
- `message` (string, required) - Status message details
- `session_id` (string, optional) - Related session ID if applicable

**Returns:**
```json
{
  "acknowledged": true,
  "message": "Status broadcast from 🎨 Frontend Developer logged. {{ORCHESTRATOR_NAME}} will be notified."
}
```

### 4. `get_mesh_activity`

Get recent mesh communications ({{ORCHESTRATOR_NAME}}-only).

**Parameters:**
- `limit` (number, optional) - Maximum records to return (default: 50)
- `since` (string, optional) - ISO timestamp - only return communications since this time

**Returns:**
```json
{
  "total": 3,
  "communications": [
    {
      "id": 1,
      "from_agent": "🎨 Frontend Developer",
      "to_agent": "🏛️ Backend Developer",
      "request_type": "api-design",
      "context": "Need REST endpoint for user preferences",
      "urgency": "blocking",
      "session_id": "mesh-1234567890-abc123",
      "status": "allowed",
      "timestamp": "2025-12-13T10:30:00Z"
    }
  ]
}
```

## Agent Capability Registry

The registry defines:
1. **What capabilities each agent provides**
2. **Which agents they can request help from**

Current mappings:

**Development Agents:**
- 🎨 Frontend Developer → Can request: Backend Developer, UI Designer, Mobile Developer
- 🏛️ Backend Developer → Can request: Frontend Developer, Security Analyst, Mobile Developer
- 📱 Mobile Developer → Can request: Backend Developer, UI Designer, Frontend Developer
- 📐 UI Designer → Can request: Frontend Developer, Mobile Developer

**Quality Agents:**
- 🧐 Code Reviewer → Can request: Debugger, Validator
- 👾 Debugger → Can request: Code Reviewer, Validator
- 🧪 Validator → Can request: Code Reviewer, Debugger

**Blocked Agents (must go through {{ORCHESTRATOR_NAME}}):**
- 👔 BOSS
- 🛡️ Security Analyst

## Governance Rules

1. **Blocked targets:** Requests to BOSS or Security Analyst are automatically blocked
2. **Capability mapping:** Agents can only request help from agents in their `can_request` list
3. **Full audit trail:** All requests (allowed and blocked) are logged to `quality.db`
4. **{{ORCHESTRATOR_NAME}} oversight:** All communications are visible to {{ORCHESTRATOR_NAME}} via `get_mesh_activity`

## Database Schema

Communications are logged to the `mesh_communications` table in `quality.db`:

```sql
CREATE TABLE IF NOT EXISTS mesh_communications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_agent TEXT NOT NULL,
  to_agent TEXT NOT NULL,
  request_type TEXT NOT NULL,
  context TEXT NOT NULL,
  urgency TEXT NOT NULL,
  session_id TEXT NOT NULL,
  status TEXT NOT NULL,
  block_reason TEXT,
  timestamp DATETIME NOT NULL
);
```

**Note:** The table will be created separately - this server assumes it exists.

## Installation

```bash
cd {{CATALYST_ROOT}}/tools/mesh-coordinator
npm install
npm run build
```

## Usage

### Stdio Transport (Standard for Huxley)

```bash
node {{CATALYST_ROOT}}/tools/mesh-coordinator/dist/index.js
```

### Environment Variables

- `CATALYST_QUALITY_DB` - Path to quality.db (default: `{{CATALYST_ROOT}}/monitoring/quality.db`)

## Example Workflows

### 1. Frontend Developer needs API design help

```typescript
// Frontend Developer calls:
request_peer_help({
  from_agent: "🎨 Frontend Developer",
  to_agent: "🏛️ Backend Developer",
  request_type: "api-design",
  context: "Need REST endpoint for user preferences with filtering and pagination",
  urgency: "blocking"
})

// Returns:
{
  "session_id": "mesh-1701234567-xyz789",
  "status": "allowed",
  "message": "Request approved. Session ID: mesh-1701234567-xyz789. 🏛️ Backend Developer has been notified via {{ORCHESTRATOR_NAME}}."
}
```

### 2. Code Reviewer finds issue, requests debugging

```typescript
// Code Reviewer calls:
request_peer_help({
  from_agent: "🧐 Code Reviewer",
  to_agent: "👾 Debugger",
  request_type: "bug-investigation",
  context: "Detected potential memory leak in auth middleware - need root cause analysis",
  urgency: "nice_to_have"
})
```

### 3. Agent broadcasts completion

```typescript
// Mobile Developer calls:
broadcast_status({
  from_agent: "📱 Mobile Developer",
  status: "completed",
  message: "iOS authentication flow implemented and tested. Ready for code review.",
  session_id: "mesh-1701234567-xyz789"
})
```

### 4. {{ORCHESTRATOR_NAME}} checks recent mesh activity

```typescript
// {{ORCHESTRATOR_NAME}} calls:
get_mesh_activity({
  limit: 20,
  since: "2025-12-13T00:00:00Z"
})
```

## Security

- **No external network access** - stdio transport only
- **Database integrity** - Uses WAL mode for concurrent access safety
- **Audit trail** - All communications logged with timestamps
- **Governance enforcement** - Blocked agents and capability restrictions enforced

## Production Deployment

This server is production-ready:
- ✅ Full TypeScript type safety
- ✅ Comprehensive error handling
- ✅ Graceful shutdown (SIGINT/SIGTERM)
- ✅ Input validation with Zod
- ✅ Database connection pooling
- ✅ Structured logging to stderr

## Extending the System

### Adding new agents to registry

Edit `src/registry.ts`:

```typescript
export const AGENT_CAPABILITIES: Record<string, AgentCapabilities> = {
  "🆕 New Agent": {
    provides: ["new-capability-1", "new-capability-2"],
    can_request: ["🏛️ Backend Developer", "🎨 Frontend Developer"]
  },
  // ... existing agents
};
```

### Adding new blocked agents

Edit `src/registry.ts`:

```typescript
export function isBlockedTarget(agent: string): boolean {
  const blockedAgents = [
    "👔 BOSS",
    "🛡️ Security Analyst",
    "🆕 New Blocked Agent"
  ];

  return blockedAgents.includes(agent);
}
```

## License

MIT

---

**Built for Huxley** - The one thing that builds all other things.
