# Agent MCP Integration Guide

> **Status:** Pattern reference. The template ships five MCP servers (`.mcp.json`): filesystem, builder-memory, iterm-mcp, context7, google-workspace. Every other server named below is one you would add yourself.

## Overview

Huxley agents are equipped with specialized MCPs (Model Context Protocol servers) that give them access to domain-specific tools, documentation, and capabilities.

## How It Works

### 1. Global MCPs (All Agents)
All agents automatically have access to these core MCPs:
- **builder-memory** - Persistent context across sessions
- **applescript** - macOS automation
- **context7** - Project knowledge management
- **git-mcp** - Git patterns and documentation
- **n8n-mcp** - Workflow automation (when relevant)
- **playwright** - Browser automation (when relevant)

### 2. Agent-Specific MCPs
Agents are equipped with specialized MCPs based on their domain:

#### 🎨 Frontend Specialist
```yaml
mcp_servers:
  - shadcn-ui: "Accessible React component library"
  - react-spring-mcp: "Physics-based animation documentation"
  - playwright: "Browser testing"
  - n8n-mcp: "Frontend workflow automation"
```

**When to use:**
- Building React/Next.js UI components → Query shadcn-ui MCP
- Implementing animations → Query react-spring-mcp for physics docs
- Testing web interfaces → Use playwright MCP

#### 📱 iOS Dev
```yaml
mcp_servers:
  - xcodebuildmcp: "Xcode build tools"
  - apple-doc-mcp: "Apple developer documentation"
```

**When to use:**
- Building iOS apps → Query apple-doc-mcp for Swift API docs
- Xcode project management → Use xcodebuildmcp

#### 🛒 Shopify Specialist
```yaml
mcp_servers:
  - shopify-mcp: "Shopify store operations"
  - shadcn-ui: "Storefront UI components"
  - playwright: "E-commerce testing"
```

**When to use:**
- Managing Shopify stores → Use shopify-mcp for product/order ops
- Building storefront UI → Query shadcn-ui for components
- Testing checkout flows → Use playwright

#### 🤖 Automation Specialist
```yaml
mcp_servers:
  - n8n-mcp: "Workflow automation platform"
  - applescript: "macOS automation"
  - apple-doc: "AppleScript API reference"
  - playwright: "Browser automation"
```

**When to use:**
- Creating n8n workflows → Use n8n-mcp
- macOS system automation → Use applescript MCP
- Web automation → Use playwright

## MCP Query Patterns

### shadcn-ui (Frontend Specialist)
```
"Show me the Button component API"
"How do I install the Dialog component?"
"What variants are available for Card?"
```

### react-spring-mcp (Frontend Specialist)
```
get_hook_api('useSpring')           # Get useSpring documentation
get_hook_api('config')               # Get physics config properties
get_concept('spring-physics')        # Deep physics understanding
```

**Returns:**
- Hook signatures with TypeScript types
- Parameter descriptions with physics explanations
- Code examples and common patterns
- 13 config properties (mass, tension, friction, bounce, etc.)

### apple-doc-mcp (iOS Dev)
```
"Show me SwiftUI View documentation"
"What's the API for URLSession?"
"How do I use Combine framework?"
```

### shopify-mcp (Shopify Specialist)
```
"List all products"
"Create a new product"
"Update inventory levels"
```

### n8n-mcp (Automation Specialist)
```
"List available workflows"
"Create a new workflow"
"Trigger workflow execution"
```

## Agent MCP Configuration Files

Agents declare their MCP access in frontmatter:

```yaml
---
name: 🎨 Frontend Specialist
description: UI/UX development specialist
color: orange
mcp_servers:
  - shadcn-ui: "Component library"
  - react-spring-mcp: "Animation docs"
---
```

## Capsule-Specific MCP Loading

MCPs can be capsule-specific and auto-load when working in that capsule:

### example-mobile-capsule
```json
{
  "mcpServers": {
    "xcodebuildmcp": {...},
    "apple-doc-mcp": {...}
  }
}
```

### ecommerce
```json
{
  "mcpServers": {
    "shopify-mcp": {...},
    "supabase": {...}
  }
}
```

### example-media-capsule
```json
{
  "mcpServers": {
    "obs-mcp": {...}
  }
}
```

## Best Practices

### For Agents

1. **Check MCP availability** before using specialized tools
2. **Query documentation** via MCP before implementation
3. **Use appropriate MCP** for the task domain
4. **Respect MCP boundaries** - don't use MCPs outside your authorization

### For Users

1. **Delegate to specialists** - Frontend work → Frontend Specialist (gets shadcn-ui)
2. **Work in correct capsule** - Capsule-specific MCPs auto-load
3. **Restart after MCP changes** - MCP configs load at session start

## MCP Registry

All MCP definitions and role mappings maintained in:
```
{{CATALYST_ROOT}}/global/mcp/server-registry.json
```

Agent-specific access defined in:
```
{{CATALYST_ROOT}}/.claude/agents/AGENT_MCP_ACCESS.yaml   # not shipped — create it when you need per-agent MCP scoping
```

## Troubleshooting

### Agent can't access MCP
1. Check agent's `mcp_servers` frontmatter
2. Verify MCP is in global or capsule-specific `.mcp.json`
3. Restart Claude Code to reload MCP configurations

### MCP not available
1. Check if MCP is built: `ls {{CATALYST_ROOT}}/global/[mcp-name]/dist/`
2. Verify path in `.mcp.json` is correct
3. Run `/mcp` to see loaded servers

### Wrong MCP documentation returned
1. Use correct query format for the MCP type
2. Check MCP server is running (no errors in session)
3. Verify MCP server version is current

## Examples

### Frontend Specialist Building UI
```
User: "Build a login form with validation"

Frontend Specialist:
1. Queries shadcn-ui MCP for Form, Input, Button components
2. Implements form with react-hook-form
3. Adds smooth validation animations using react-spring-mcp
4. Tests with playwright MCP
```

### iOS Dev Creating App
```
User: "Create a SwiftUI list view"

iOS Dev:
1. Queries apple-doc-mcp for List and ForEach APIs
2. Implements SwiftUI view
3. Uses xcodebuildmcp to build and test
```

### Automation Specialist Building Workflow
```
User: "Create workflow to sync data"

Automation Specialist:
1. Uses n8n-mcp to create workflow
2. Configures nodes via MCP
3. Uses applescript MCP for macOS integration
4. Tests automation with playwright if web-based
```

---

