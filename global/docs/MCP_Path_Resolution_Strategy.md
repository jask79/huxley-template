# MCP Server Path Resolution Strategy

**Last Updated:** 2025-11-11
**Owner:** Huxley Infrastructure

---

## Overview

This document defines the standardized path resolution strategy for all MCP (Model Context Protocol) servers in Huxley. This strategy was established after debugging Context7 MCP server failures caused by variable-based path resolution.

---

## Architecture Decision

**Strategy: Hybrid Absolute + Package Manager Approach**

### Core Principles

1. **Absolute paths for Node.js runtime**: Use `node`
2. **Absolute paths for local scripts**: Full paths to `.js` entry points
3. **Keep `npx` for package managers**: Let npm/npx handle their own resolution
4. **Environment variables ONLY for secrets**: API keys, tokens, sensitive config

---

## Rationale

### Why Absolute Paths for Node Binary?

**Problem identified:**
- Context7 MCP server failed with `"command": "node"` (PATH-based lookup)
- MCP server context may not inherit full shell PATH
- Inconsistent behavior across different invocation contexts

**Solution:**
- Use `node` explicitly
- Eliminates PATH resolution uncertainty
- Deterministic runtime location

**Trade-offs accepted:**
- Apple Silicon specific (M-series Mac Homebrew path)
- Not portable to Intel Macs (`/usr/local/bin/node`)
- **Acceptable:** Huxley is personal infrastructure, not distributed software

### Why Absolute Paths for Scripts?

**Eliminates variable resolution issues:**
- `${USER_HOME}` may not resolve in MCP context
- `${PROJECT_ROOT}` may not be defined
- Explicit paths are unambiguous

**Examples:**
```json
// ❌ BEFORE (unreliable)
"args": ["${USER_HOME}/mcp-servers/context7/dist/index.js"]

// ✅ AFTER (reliable)
"args": ["{{HOME_DIR}}/mcp-servers/context7/dist/index.js"]
```

### Why Keep `npx`?

**Package managers are self-contained:**
- `npx` handles its own dependency resolution
- Built-in PATH management
- Designed to "just work" across environments

**Examples:**
```json
// ✅ Keep npx for packages
"command": "npx",
"args": ["-y", "@modelcontextprotocol/server-filesystem"]
```

---

## Implementation Pattern

### Node.js Local Scripts

**Pattern:**
```json
{
  "server-name": {
    "command": "node",
    "args": ["/absolute/path/to/script.js"],
    "description": "Server description"
  }
}
```

**Examples:**

### NPM/NPX Packages

**Pattern:**
```json
{
  "server-name": {
    "command": "npx",
    "args": ["-y", "@scope/package-name"],
    "description": "Server description"
  }
}
```

**Examples:**
- filesystem: `npx -y @modelcontextprotocol/server-filesystem`
- playwright: `npx -y @playwright/mcp`
- supabase: `npx -y @supabase/mcp-server-supabase@latest`

### Python Scripts

**Pattern:**
```json
{
  "server-name": {
    "command": "/absolute/path/to/venv/bin/python3",
    "args": ["/absolute/path/to/script.py"],
    "description": "Server description"
  }
}
```

**Example:**

### Binary Commands

**Pattern:**
```json
{
  "server-name": {
    "command": "binary-name",
    "args": ["arg1", "arg2"],
    "env": {
      "SECRET": "${ENV_VAR}"
    }
  }
}
```

**Example:**
- airtable: `airtable-mcp-server` (globally installed binary)

---

## Environment Variables

### When to Use

**✅ Acceptable uses:**
- **Secrets:** API keys, tokens, passwords
- **Dynamic config:** URLs, project references that change per environment

**❌ Never use for:**
- File paths (use absolute paths)
- Binary locations (use absolute paths)
- Static configuration

### Pattern

```json
{
  "env": {
    "API_KEY": "${ENV_VAR_NAME}",
    "API_URL": "${SERVICE_URL}"
  }
}
```

**Examples:**
- `"AIRTABLE_API_KEY": "${AIRTABLE_API_KEY}"` ✅
- `"N8N_API_KEY": "${N8N_API_KEY}"` ✅
- `"SCRIPT_PATH": "${USER_HOME}/script.js"` ❌ (use absolute path instead)

---

## Security Considerations

### Critical Rules

1. **NEVER hardcode secrets in config files**
   - ❌ `"API_KEY": "patEXAMPLE0000000.EXAMPLE..."` (security violation)
   - ✅ `"API_KEY": "${API_KEY}"` (environment variable)

2. **API keys must use environment variables**
   - Store in `.env` file (not committed to git)
   - Reference via `${VAR_NAME}` in config

3. **Secrets in version control = security incident**
   - Immediately rotate compromised keys
   - Update config to use environment variables

### Example Fix

**Before (SECURITY VIOLATION):**
```json
"airtable": {
  "env": {
    "AIRTABLE_API_KEY": "patEXAMPLE0000000.EXAMPLE..."
  }
}
```

**After (SECURE):**
```json
"airtable": {
  "env": {
    "AIRTABLE_API_KEY": "${AIRTABLE_API_KEY}"
  }
}
```

---

## Configuration Files

### Active Files

**Primary runtime config:**
- `{{CATALYST_ROOT}}/.mcp.json` (15 servers)
- Platform-filtered for darwin (macOS)
- Development scope

**Global template:**
- `{{CATALYST_ROOT}}/global/claude-config/mcp_servers.json` (13 servers)
- Reference configuration
- Should stay synchronized with primary config

### Synchronization

Both files should follow the same path resolution strategy. When adding/modifying servers:

1. Update `.mcp.json` (primary)
2. Sync changes to `global/claude-config/mcp_servers.json` (template)
3. Verify consistency

---

## Validation Checklist

When adding or modifying MCP servers, verify:

### Path Resolution
- [ ] Node.js runtime uses `node`
- [ ] Script paths are absolute (no `${USER_HOME}` or `${PROJECT_ROOT}`)
- [ ] Package managers use `npx` (not absolute paths)
- [ ] Python uses absolute virtualenv paths

### Security
- [ ] No hardcoded API keys or secrets
- [ ] All secrets use environment variables
- [ ] Environment variable format: `${VAR_NAME}`

### Consistency
- [ ] Both config files updated if applicable
- [ ] Same pattern used across similar servers

---

## Troubleshooting

### Common Issues

**Problem: Server fails to start with "command not found"**
- **Cause:** PATH-based lookup failing
- **Solution:** Use absolute path to binary

**Problem: Script not found**
- **Cause:** Variable not resolving or incorrect path
- **Solution:** Use absolute path, verify file exists

**Problem: Environment variable not resolving**
- **Cause:** Variable not exported or incorrect syntax
- **Solution:** Verify `.env` file, check syntax: `${VAR_NAME}`

### Debugging Steps

1. **Check absolute paths exist:**
   ```bash
   ls -la node
   ```

2. **Verify environment variables:**
   ```bash
   echo $AIRTABLE_API_KEY
   echo $N8N_API_KEY
   ```

3. **Test server manually:**
   ```bash
   node /path/to/script.js
   ```

---

## Migration Guide

### Converting Existing Servers

**Step 1: Identify variable-based paths**
```bash
grep -E '\$\{USER_HOME\}|\$\{PROJECT_ROOT\}' .mcp.json
```

**Step 2: Replace with absolute paths**
```json
// Before
"command": "node",
"args": ["${USER_HOME}/script.js"]

// After
"command": "node",
"args": ["{{HOME_DIR}}/script.js"]
```

**Step 3: Fix hardcoded secrets**
```bash
# Find hardcoded secrets (look for long strings in env)
grep -E '"[A-Za-z0-9_]+": "pat[A-Za-z0-9.]+"' mcp_servers.json
```

**Step 4: Validate changes**
- Start Claude Code and verify all MCP servers load
- Test each server's functionality
- Check logs for errors

---

## References

- **Context7 Fix:** Changed from `node + ${USER_HOME}/...` to `node + /absolute/path`
- **MCP Specification:** [Model Context Protocol Docs](https://modelcontextprotocol.io)
- **Homebrew Paths:** Apple Silicon uses `/opt/homebrew`, Intel uses `/usr/local`

---

