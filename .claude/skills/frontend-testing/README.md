# Frontend Testing Skill

Comprehensive frontend testing with quick verification loops and thorough test suites using Playwright.

## Two Modes

### Mode 1: Quick Verification (Dev Loop)
Fast smoke tests during development using Playwright MCP

```bash
# Launch server
./launch.sh ./dist 8080

# Use Playwright MCP tools (via {{ORCHESTRATOR_NAME}} or Playwright Agent):
# - mcp__playwright__browser_navigate
# - mcp__playwright__browser_snapshot
# - mcp__playwright__browser_console_messages
# - mcp__playwright__browser_take_screenshot

# Teardown
./teardown.sh 8080
```

### Mode 2: Comprehensive Testing (Quality Gates)
Thorough test suites for capsule completion using Playwright Agent

Delegate comprehensive testing scenarios to 🎭 Playwright Agent with 🌐 browser-automation output style for:
- Multi-step user flows
- Form validation testing
- Navigation testing
- Interactive element verification

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Complete MCP-based skill documentation |
| `README.md` | This file - quick reference |
| `launch.sh` | Start dev server |
| `teardown.sh` | Stop dev server |
| `examples/` | MCP testing examples and patterns |

## Quick Start

**Development workflow:**
1. Write UI code
2. `./launch.sh ./dist 8080`
3. Use Playwright MCP tools to verify (navigate, snapshot, screenshot)
4. Iterate on errors
5. `./teardown.sh 8080`
6. Commit when verified

**Quality gate workflow:**
1. Delegate comprehensive testing to Playwright Agent
2. All tests must pass
3. Screenshots captured for proof-of-work
4. Capsule marked complete

## Key Patterns

### Reconnaissance-Then-Action (MCP)
```markdown
# 1. Navigate and wait for stability
mcp__playwright__browser_navigate(url: "...")
mcp__playwright__browser_wait_for(time: 2)

# 2. Capture state
snapshot = mcp__playwright__browser_snapshot()

# 3. Take screenshot
mcp__playwright__browser_take_screenshot(filename: "state.png")

# 4. Act using refs from snapshot
mcp__playwright__browser_click(element: "...", ref: "...")
```

**Why:** Wait for page stability before capturing snapshots and element refs.

## Integration

Add to capsule quality gates:

```yaml
# capsules/[capsule]/ops/dod.yaml
testing:
  frontend:
    mode: "MCP-based validation using Playwright Agent"
    quick_verify:
      - name: "Homepage renders"
        method: "Use Playwright MCP: navigate + snapshot + screenshot"
        url: "http://localhost:3000"
    comprehensive:
      - name: "Checkout flow"
        method: "Delegate to Playwright Agent with comprehensive test scenario"
```

## Examples

See `examples/README.md` for MCP-based testing patterns and workflows.

## Version

**v2.0.0** - Enhanced with Playwright MCP integration (Huxley native architecture)
