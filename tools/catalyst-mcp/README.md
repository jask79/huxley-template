# Huxley MCP Server

**Model Context Protocol (MCP) server for Huxley task management system**

Version: 1.0.0
MCP Spec: 2025-06-18
Protocol: JSON-RPC 2.0 over stdio transport

---

## Overview

The Huxley MCP Server exposes the Huxley task management system to Claude Code and other MCP-compatible tools. This allows AI agents to programmatically create, query, and manage tasks across all Huxley capsules.

**Key Features:**

- ✅ **5 Core Tools** - Full task lifecycle management
- ✅ **3 Resources** - Real-time task data access
- ✅ **Full-Text Search** - SQLite FTS5 for fast task discovery
- ✅ **Hierarchical Tasks** - Parent-child task relationships
- ✅ **Document Linking** - Connect specs, research, and outputs to tasks
- ✅ **Strict Validation** - Zod schemas for all inputs
- ✅ **Type Safety** - Full TypeScript implementation

---

## Quick Start

### 1. Install Dependencies

```bash
cd {{CATALYST_ROOT}}/tools/catalyst-mcp
npm install
npm run build
```

### 2. Initialize Database

The database schema is already initialized at `{{CATALYST_ROOT}}/tasks.db`.

To reinitialize:

```bash
sqlite3 {{CATALYST_ROOT}}/tasks.db < ../../api/db/schema.sql
```

### 3. Test the Server

```bash
# Start server manually (for testing)
./start.sh

# Or use npm script
npm run dev
```

### 4. Configure Claude Code

The MCP server is configured in `.mcp.json`:

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

**Claude Code will automatically start the server when needed.**

---

## MCP Tools

### 1. `create_task`

Create a new task in the Huxley task management system.

**Input:**

```typescript
{
  title: string;              // Required: Task title/description
  description?: string;       // Optional: Detailed description or notes
  priority?: 'low' | 'medium' | 'high' | 'critical';  // Default: 'medium'
  parent_id?: string;         // Optional: Parent task ID for hierarchy
  capsule: string;            // Required: Capsule name
  assigned_agent?: string;    // Optional: Agent emoji+name
  dependencies?: string[];    // Optional: Task IDs this depends on
  tags?: string[];            // Optional: Tags for categorization
}
```

**Example:**

```json
{
  "title": "Implement dark mode toggle",
  "description": "Add system appearance detection as default",
  "priority": "high",
  "capsule": "example-mobile-capsule",
  "assigned_agent": "📱 Mobile Dev",
  "tags": ["ui", "settings", "theming"]
}
```

**Output:**

```json
{
  "success": true,
  "task_id": "task-abc123",
  "task": {
    "id": "task-abc123",
    "description": "Implement dark mode toggle",
    "status": "pending",
    "priority": "high",
    "capsule": "example-mobile-capsule",
    "assigned_agent": "📱 Mobile Dev",
    "created_at": "2025-01-27T10:00:00Z"
  }
}
```

---

### 2. `update_task_status`

Update the status of an existing task.

**Input:**

```typescript
{
  task_id: string;           // Required: Task ID to update
  status: 'pending' | 'in_progress' | 'blocked' | 'completed' | 'archived';
  description?: string;      // Optional: Updated description
}
```

**Example:**

```json
{
  "task_id": "task-abc123",
  "status": "completed"
}
```

**Output:**

```json
{
  "success": true,
  "task": {
    "id": "task-abc123",
    "description": "Implement dark mode toggle",
    "status": "completed",
    "priority": "high",
    "capsule": "example-mobile-capsule",
    "updated_at": "2025-01-27T14:30:00Z",
    "completed_at": "2025-01-27T14:30:00Z"
  }
}
```

---

### 3. `get_task_tree`

Get hierarchical task tree structure with optional filtering.

**Input:**

```typescript
{
  root_id?: string;          // Optional: Root task ID (omit for top-level)
  capsule?: string;          // Optional: Filter by capsule name
}
```

**Example:**

```json
{
  "capsule": "example-mobile-capsule"
}
```

**Output:**

```json
{
  "success": true,
  "count": 3,
  "tree": [
    {
      "id": "task-abc123",
      "description": "Implement dark mode",
      "status": "in_progress",
      "priority": "high",
      "capsule": "example-mobile-capsule",
      "child_count": 2,
      "dependency_count": 0,
      "children": [
        {
          "id": "task-def456",
          "description": "Design color palette",
          "status": "completed",
          "priority": "medium",
          "children": []
        }
      ]
    }
  ]
}
```

---

### 4. `search_tasks`

Search tasks using full-text search with optional filters.

**Input:**

```typescript
{
  query: string;             // Required: Search query (FTS5)
  status?: string;           // Optional: Filter by status
  capsule?: string;          // Optional: Filter by capsule
  limit?: number;            // Optional: Max results (1-100, default 10)
}
```

**Example:**

```json
{
  "query": "dark mode authentication",
  "status": "in_progress",
  "limit": 5
}
```

**Output:**

```json
{
  "success": true,
  "count": 2,
  "query": "dark mode authentication",
  "results": [
    {
      "id": "task-abc123",
      "description": "Implement dark mode toggle",
      "status": "in_progress",
      "priority": "high",
      "capsule": "example-mobile-capsule",
      "assigned_agent": "📱 Mobile Dev",
      "tags": ["ui", "settings"],
      "created_at": "2025-01-27T10:00:00Z"
    }
  ]
}
```

---

### 5. `link_document`

Link a document (spec, research, reference, output) to a task.

**Input:**

```typescript
{
  task_id: string;           // Required: Task ID to link to
  file_path: string;         // Required: Absolute path to document
  link_type: 'spec' | 'research' | 'reference' | 'output';
}
```

**Example:**

```json
{
  "task_id": "task-abc123",
  "file_path": "{{CATALYST_ROOT}}/capsules/example-mobile-capsule/specs/dark-mode-spec.md",
  "link_type": "spec"
}
```

**Output:**

```json
{
  "success": true,
  "document_id": 42,
  "task_id": "task-abc123",
  "file_path": "{{CATALYST_ROOT}}/capsules/example-mobile-capsule/specs/dark-mode-spec.md",
  "link_type": "spec"
}
```

---

## MCP Resources

Resources provide read-only access to task data via URIs.

### 1. `catalyst://tasks/active`

Get all active tasks across all capsules.

**Example:**

```json
{
  "capsule": "all",
  "count": 15,
  "tasks": [...]
}
```

---

### 2. `catalyst://tasks/active/{capsule}`

Get active tasks for a specific capsule.

**Example URI:** `catalyst://tasks/active/example-mobile-capsule`

**Example:**

```json
{
  "capsule": "example-mobile-capsule",
  "count": 5,
  "tasks": [...]
}
```

---

### 3. `catalyst://tasks/blocked`

Get all blocked tasks.

**Example:**

```json
{
  "count": 3,
  "tasks": [...]
}
```

---

### 4. `catalyst://tasks/{task_id}/context`

Get full context for a specific task including dependencies and documents.

**Example URI:** `catalyst://tasks/task-abc123/context`

**Example:**

```json
{
  "task": {
    "id": "task-abc123",
    "description": "Implement dark mode toggle",
    "status": "in_progress",
    ...
  },
  "dependencies": [
    {
      "depends_on_task_id": "task-xyz789",
      "dependency_type": "required"
    }
  ],
  "documents": [
    {
      "file_path": "/path/to/spec.md",
      "link_type": "spec",
      "mime_type": "text/markdown"
    }
  ],
  "children": [...]
}
```

---

## Usage in Claude Code

Once configured, you can use the MCP tools directly in Claude Code:

### Create a Task

```
Create a task in the example-mobile-capsule capsule to implement biometric authentication with high priority.
```

Claude will use the `create_task` tool automatically.

### Search Tasks

```
Search for all tasks related to authentication in example-media-capsule capsule.
```

Claude will use the `search_tasks` tool.

### Get Task Tree

```
Show me the task hierarchy for example-mobile-capsule capsule.
```

Claude will use the `get_task_tree` tool.

### Update Task Status

```
Mark task-abc123 as completed.
```

Claude will use the `update_task_status` tool.

---

## Database Schema

The MCP server connects to `{{CATALYST_ROOT}}/tasks.db` (SQLite).

**Main Tables:**

- `tasks` - Core task storage with hierarchy support
- `task_dependencies` - Task dependency relationships
- `documents` - Document metadata
- `task_documents` - Task-document links
- `tasks_fts` - Full-text search index (FTS5)

**See:** `{{CATALYST_ROOT}}/api/db/schema.sql` for complete schema.

---

## Environment Variables

- `CATALYST_DB` - Path to SQLite database (default: `{{CATALYST_ROOT}}/tasks.db`)

---

## Development

### Build

```bash
npm run build
```

### Watch Mode

```bash
npm run watch
```

### Manual Testing

```bash
# Start server
./start.sh

# In another terminal, send MCP requests via stdin/stdout
```

### Logs

All logs are written to stderr (not stdout) to maintain MCP protocol integrity.

```bash
# View logs when running manually
./start.sh 2>&1 | grep "Huxley MCP"
```

---

## Troubleshooting

### Server Not Starting

**Check Node.js:**

```bash
node --version
# Should be v18+
```

**Check Database:**

```bash
ls -lh {{CATALYST_ROOT}}/tasks.db
sqlite3 {{CATALYST_ROOT}}/tasks.db "SELECT COUNT(*) FROM tasks;"
```

### Tools Not Appearing in Claude Code

1. Restart Claude Code
2. Check `.mcp.json` configuration
3. Check server logs for errors

### Database Errors

**Reinitialize schema:**

```bash
cd {{CATALYST_ROOT}}
sqlite3 tasks.db < api/db/schema.sql
```

**Check permissions:**

```bash
ls -la tasks.db
# Should be writable by your user
```

---

## Architecture

```
┌─────────────────┐
│   Claude Code   │
│   (MCP Client)  │
└────────┬────────┘
         │ JSON-RPC 2.0
         │ stdio transport
         ▼
┌─────────────────┐
│ Huxley MCP   │
│     Server      │
├─────────────────┤
│ • Tools (5)     │
│ • Resources (3) │
│ • Validation    │
└────────┬────────┘
         │ SQL
         ▼
┌─────────────────┐
│  tasks.db       │
│  (SQLite)       │
└─────────────────┘
```

---

## Files

- `src/index.ts` - Main MCP server implementation
- `src/tools.ts` - Tool handlers with Zod validation
- `src/resources.ts` - Resource handlers
- `src/database.ts` - Database connection and queries
- `start.sh` - Startup script
- `package.json` - Dependencies and scripts
- `tsconfig.json` - TypeScript configuration

---

## Related Documentation

- [TaskMaster Guide]({{CATALYST_ROOT}}/global/docs/TaskMaster_Guide.md) - Task management overview
- [MCP Specification](https://spec.modelcontextprotocol.io/) - Official MCP spec
- [Database Schema]({{CATALYST_ROOT}}/api/db/schema.sql) - SQLite schema

---

## Version History

**1.0.0** (2025-01-27)
- Initial release
- 5 core tools implemented
- 3 resources implemented
- Full-text search support
- Hierarchical tasks
- Document linking

---

**Built with the Model Context Protocol (MCP) for seamless AI integration.**
