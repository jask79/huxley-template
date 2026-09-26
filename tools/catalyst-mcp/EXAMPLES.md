# Huxley MCP Server - Usage Examples

Real-world examples of using the Huxley MCP server with Claude Code.

---

## Example 1: Creating Tasks

### Natural Language

```
Create a high priority task in the example-mobile-capsule capsule to implement push notifications.
Assign it to Mobile Dev and tag it with "notifications" and "ios".
```

### What Happens

Claude Code will:
1. Parse your request
2. Call `create_task` tool with:
   ```json
   {
     "title": "Implement push notifications",
     "priority": "high",
     "capsule": "example-mobile-capsule",
     "assigned_agent": "📱 Mobile Dev",
     "tags": ["notifications", "ios"]
   }
   ```
3. Return the created task ID

### Result

```json
{
  "success": true,
  "task_id": "task-def456",
  "task": {
    "id": "task-def456",
    "description": "Implement push notifications",
    "status": "pending",
    "priority": "high",
    "capsule": "example-mobile-capsule",
    "assigned_agent": "📱 Mobile Dev",
    "created_at": "2025-01-27T14:00:00Z"
  }
}
```

---

## Example 2: Searching Tasks

### Natural Language

```
Search for all authentication-related tasks across all capsules.
```

### What Happens

Claude Code calls `search_tasks`:

```json
{
  "query": "authentication",
  "limit": 10
}
```

### Result

```json
{
  "success": true,
  "count": 3,
  "query": "authentication",
  "results": [
    {
      "id": "task-mobile001",
      "description": "Implement biometric authentication for iOS app",
      "status": "in_progress",
      "priority": "high",
      "capsule": "example-mobile-capsule",
      "tags": ["security", "authentication", "ios"]
    },
    {
      "id": "task-mobile002",
      "description": "Implement OAuth2 login flow",
      "status": "blocked",
      "priority": "high",
      "capsule": "example-mobile-capsule",
      "tags": ["authentication", "oauth", "blocked"]
    }
  ]
}
```

---

## Example 3: Viewing Task Hierarchy

### Natural Language

```
Show me the task tree for example-media-capsule capsule.
```

### What Happens

Claude Code calls `get_task_tree`:

```json
{
  "capsule": "example-media-capsule"
}
```

### Result

```json
{
  "success": true,
  "count": 1,
  "tree": [
    {
      "id": "task-media001",
      "description": "Automate media library organization",
      "status": "in_progress",
      "priority": "medium",
      "capsule": "example-media-capsule",
      "assigned_agent": "🤖 Automator",
      "child_count": 2,
      "children": [
        {
          "id": "task-media002",
          "description": "Create n8n workflow for file monitoring",
          "status": "completed",
          "priority": "medium"
        },
        {
          "id": "task-media003",
          "description": "Implement automatic metadata fetching",
          "status": "pending",
          "priority": "medium"
        }
      ]
    }
  ]
}
```

---

## Example 4: Updating Task Status

### Natural Language

```
Mark task-mobile001 as completed.
```

### What Happens

Claude Code calls `update_task_status`:

```json
{
  "task_id": "task-mobile001",
  "status": "completed"
}
```

### Result

```json
{
  "success": true,
  "task": {
    "id": "task-mobile001",
    "description": "Implement biometric authentication for iOS app",
    "status": "completed",
    "priority": "high",
    "capsule": "example-mobile-capsule",
    "updated_at": "2025-01-27T15:30:00Z",
    "completed_at": "2025-01-27T15:30:00Z"
  }
}
```

---

## Example 5: Linking Documents

### Natural Language

```
Link the spec document at {{CATALYST_ROOT}}/capsules/example-mobile-capsule/specs/auth-spec.md
to task-mobile001 as a spec.
```

### What Happens

Claude Code calls `link_document`:

```json
{
  "task_id": "task-mobile001",
  "file_path": "{{CATALYST_ROOT}}/capsules/example-mobile-capsule/specs/auth-spec.md",
  "link_type": "spec"
}
```

### Result

```json
{
  "success": true,
  "document_id": 5,
  "task_id": "task-mobile001",
  "file_path": "{{CATALYST_ROOT}}/capsules/example-mobile-capsule/specs/auth-spec.md",
  "link_type": "spec"
}
```

---

## Example 6: Using Resources

### Natural Language

```
Show me all active tasks in the example-mobile-capsule capsule.
```

### What Happens

Claude Code reads the resource `catalyst://tasks/active/example-mobile-capsule`

### Result

```json
{
  "capsule": "example-mobile-capsule",
  "count": 2,
  "tasks": [
    {
      "id": "task-mobile001",
      "description": "Implement biometric authentication for iOS app",
      "status": "in_progress",
      "priority": "high",
      "assigned_agent": "📱 Mobile Dev",
      "tags": ["security", "authentication", "ios"],
      "created_at": "2025-01-27T10:00:00Z"
    },
    {
      "id": "task-mobile002",
      "description": "Implement OAuth2 login flow",
      "status": "blocked",
      "priority": "high",
      "assigned_agent": "📱 Mobile Dev",
      "tags": ["authentication", "oauth", "blocked"],
      "created_at": "2025-01-27T11:00:00Z"
    }
  ]
}
```

---

## Example 7: Finding Blocked Tasks

### Natural Language

```
What tasks are currently blocked?
```

### What Happens

Claude Code reads the resource `catalyst://tasks/blocked`

### Result

```json
{
  "count": 1,
  "tasks": [
    {
      "id": "task-mobile002",
      "description": "Implement OAuth2 login flow",
      "priority": "high",
      "capsule": "example-mobile-capsule",
      "assigned_agent": "📱 Mobile Dev",
      "tags": ["authentication", "oauth", "blocked"],
      "notes": "Blocked waiting for backend OAuth endpoints to be deployed.",
      "created_at": "2025-01-27T11:00:00Z"
    }
  ]
}
```

---

## Example 8: Getting Full Task Context

### Natural Language

```
Show me the full context for task-mobile002 including dependencies and documents.
```

### What Happens

Claude Code reads the resource `catalyst://tasks/task-mobile002/context`

### Result

```json
{
  "task": {
    "id": "task-mobile002",
    "description": "Implement OAuth2 login flow",
    "status": "blocked",
    "priority": "high",
    "capsule": "example-mobile-capsule",
    "assigned_agent": "📱 Mobile Dev",
    "tags": ["authentication", "oauth", "blocked"],
    "notes": "Blocked waiting for backend OAuth endpoints to be deployed."
  },
  "dependencies": [
    {
      "depends_on_task_id": "task-backend001",
      "dependency_type": "required"
    }
  ],
  "documents": [],
  "children": []
}
```

---

## Example 9: Complex Workflow

### Natural Language

```
I need to add a new feature to the mobile app:
1. Create a parent task for "Implement user profile screen"
2. Create child tasks for design, implementation, and testing
3. Assign the design task to UI Designer
4. Tag them appropriately
```

### What Happens

Claude Code will make multiple `create_task` calls:

1. **Parent task:**
   ```json
   {
     "title": "Implement user profile screen",
     "capsule": "example-mobile-capsule",
     "priority": "medium",
     "tags": ["feature", "profile", "ui"]
   }
   ```

2. **Child task 1 (Design):**
   ```json
   {
     "title": "Design user profile screen UI",
     "parent_id": "task-abc123",
     "capsule": "example-mobile-capsule",
     "assigned_agent": "📐 UI Designer",
     "priority": "medium",
     "tags": ["design", "ui", "profile"]
   }
   ```

3. **Child task 2 (Implementation):**
   ```json
   {
     "title": "Implement user profile screen",
     "parent_id": "task-abc123",
     "capsule": "example-mobile-capsule",
     "assigned_agent": "📱 Mobile Dev",
     "priority": "medium",
     "tags": ["implementation", "ui", "profile"]
   }
   ```

4. **Child task 3 (Testing):**
   ```json
   {
     "title": "Test user profile screen functionality",
     "parent_id": "task-abc123",
     "capsule": "example-mobile-capsule",
     "priority": "medium",
     "tags": ["testing", "qa", "profile"]
   }
   ```

---

## Example 10: Advanced Search

### Natural Language

```
Find all high priority tasks that are currently in progress in the example-mobile-capsule capsule.
```

### What Happens

Claude Code combines `search_tasks` with filters:

```json
{
  "query": "high priority",
  "status": "in_progress",
  "capsule": "example-mobile-capsule",
  "limit": 20
}
```

Or alternatively, Claude might use the resource `catalyst://tasks/active/example-mobile-capsule` and filter the results.

---

## Tips for Best Results

### Be Specific

**Good:**
```
Create a critical priority task in example-media-capsule for fixing the download automation timing issue.
Assign to Automator and tag with bug and automation.
```

**Less Good:**
```
Add a task about the download thing.
```

### Use Natural Language

You don't need to format requests as JSON. Just talk naturally:

```
Show me what tasks are blocked right now.
```

```
I finished working on task-mobile001, mark it as completed.
```

```
Search for tasks related to security and authentication.
```

### Leverage Hierarchy

```
Create a parent task for "Migrate to Cloudflare Pages" with child tasks for:
- DNS configuration
- Build pipeline setup
- Environment variable migration
- Testing
```

### Combine Operations

```
Create a task for implementing rate limiting in the API, assign it to Backend Dev,
tag it with security and api, and link the security requirements doc.
```

---

## Sample Data in Database

The test database includes these sample tasks:

1. **task-mobile001** - Biometric authentication (in_progress, high priority)
2. **task-backend001** - Database backups to R2 (pending, critical priority)
3. **task-mobile002** - OAuth2 login (blocked, high priority, depends on task-backend001)
4. **task-mobile003** - Dark mode palette (completed)
5. **task-media001** - Media library automation (in_progress, has 2 children)
   - **task-media002** - n8n workflow (completed, child)
   - **task-media003** - Metadata fetching (pending, child)

Use these for testing and experimentation!

---

## Testing the MCP Server

You can verify the server works by asking Claude Code:

```
How many tasks are currently in the database?
```

```
Show me the active tasks for example-mobile-capsule.
```

```
What's the status of task-mobile001?
```

If these work, the MCP server is properly integrated!

---

**Explore the full capabilities and build amazing workflows with the Huxley task management system!**
