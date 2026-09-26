---
name: frontend-testing
description: Comprehensive frontend testing using Playwright MCP for quick verification loops and thorough validation
when: Generating or modifying frontend UI code, running capsule quality gates, or validating web applications
allowed-tools:
  - Bash
  - Read
  - Write
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_snapshot
  - mcp__playwright__browser_click
  - mcp__playwright__browser_type
  - mcp__playwright__browser_fill_form
  - mcp__playwright__browser_take_screenshot
  - mcp__playwright__browser_console_messages
  - mcp__playwright__browser_network_requests
metadata:
  version: "2.0.0"
  architecture: "Uses Playwright MCP (Huxley configured) not standalone libraries"
  browser: "Chromium (headless via MCP config)"
  last_updated: "2025-10-20"
---

# Frontend Testing Skill

## Purpose
Comprehensive frontend testing with two modes:
1. **Quick Verification** - Fast smoke tests during development (dev loop)
2. **Comprehensive Testing** - Thorough test suites for capsule quality gates

## Modes

### Mode 1: Quick Verification (Dev Loop)

**Use when:** Iterating on UI code, need immediate visual feedback

**Workflow:**
1. Spin up local dev server
2. Launch browser via Playwright
3. Run smoke checks (rendering, console, interactions)
4. Capture screenshot proof-of-work
5. Clean teardown

**Speed:** ~5-10 seconds per check

### Mode 2: Comprehensive Testing (Quality Gates)

**Use when:** Capsule completion, pre-deployment validation, regression testing

**Workflow:**
1. Start application server(s)
2. Run full test suite with reconnaissance pattern
3. Validate functionality, interactions, edge cases
4. Capture detailed results and screenshots
5. Generate test report

**Speed:** Variable (based on test suite size)

---

## Quick Verification (Mode 1)

### Step 1: Launch Dev Server

```bash
# Using helper script
./.claude/skills/frontend-testing/launch.sh <directory> [port]

# Example
./.claude/skills/frontend-testing/launch.sh ./dist 8080

# Manual launch (if needed)
python3 -m http.server 8080 --directory ./dist > /tmp/dev-server.log 2>&1 &
echo $! > /tmp/dev-server.pid
```

### Step 2: Run Quick Verification (Using Playwright MCP)

Use Playwright MCP tools to verify the frontend:

```markdown
1. Navigate to page:
   mcp__playwright__browser_navigate(url: "http://localhost:8080")

2. Capture accessibility snapshot:
   mcp__playwright__browser_snapshot()

3. Check console messages:
   mcp__playwright__browser_console_messages()

4. Take screenshot for proof-of-work:
   mcp__playwright__browser_take_screenshot(filename: "frontend-verify.png")

5. Verify interactive elements work:
   mcp__playwright__browser_click(element: "button", ref: "<ref-from-snapshot>")
```

### Step 3: Teardown

```bash
# Clean shutdown
./.claude/skills/frontend-testing/teardown.sh [port]

# Example
./.claude/skills/frontend-testing/teardown.sh 8080
```

### Quick Verification Checks

Using MCP tools, verify:
- ✅ Page loads successfully (navigate returns success)
- ✅ No console errors (console_messages shows no errors)
- ✅ Body has content (snapshot shows page structure)
- ✅ Interactive elements work (click succeeds)
- ✅ Screenshot captured (take_screenshot creates proof)

### When Quick Verification Fails

```bash
# Check console errors
cat /tmp/dev-server.log

# View screenshot to diagnose
open /tmp/playwright-mcp-output/frontend-verify.png

# Review network requests
# Use mcp__playwright__browser_network_requests() to see all requests

# Keep server running for debugging
# User decides when to teardown
```

---

## Comprehensive Testing (Mode 2)

### Decision Framework

**Is content static HTML?**
```
YES → Direct MCP inspection and automation
NO  → Is server already running?
      YES → Reconnaissance-then-action pattern with MCP
      NO  → Launch server first, then use MCP tools
```

### Core Pattern: Reconnaissance-Then-Action (Using MCP)

**CRITICAL:** Do NOT inspect DOM before page is fully loaded on dynamic apps!

**MCP-Based Testing Workflow:**

```markdown
# 1. RECONNAISSANCE - Navigate and wait for page stability
mcp__playwright__browser_navigate(url: "http://localhost:8080")

# Give dynamic apps time to fully render (especially React/Vue/Svelte apps)
mcp__playwright__browser_wait_for(time: 2)

# 2. CAPTURE - Take snapshot of rendered state
snapshot = mcp__playwright__browser_snapshot()
# Review the snapshot to understand page structure and get element refs

# 3. IDENTIFY - Take screenshot for documentation
mcp__playwright__browser_take_screenshot(filename: "page-state.png")

# 4. ACTION - Automate using discovered element refs from snapshot
mcp__playwright__browser_click(
  element: "Submit button",
  ref: "ref-from-snapshot"
)

# 5. VERIFY - Check result
mcp__playwright__browser_wait_for(text: "Success")
mcp__playwright__browser_take_screenshot(filename: "result.png")
```

**Why This Matters:**
> Premature DOM inspection on dynamic apps yields incomplete element references.
> Always wait for page stability before capturing snapshots and element refs.

### Server Lifecycle Management

**Manual Server Management:**

```bash
# Start server
./.claude/skills/frontend-testing/launch.sh ./dist 8080

# Run MCP-based tests (via {{ORCHESTRATOR_NAME}} or delegated agent)
# Use Playwright MCP tools for testing

# Stop server
./.claude/skills/frontend-testing/teardown.sh 8080
```

### Test Suite Structure

```
.claude/skills/frontend-testing/
├── SKILL.md           # This file - complete documentation
├── README.md          # Quick start guide
├── launch.sh          # Server launcher
├── teardown.sh        # Server cleanup
└── examples/
    └── README.md      # MCP-based testing examples
```

### Example: Landing Page Test (Using MCP)

**Manual MCP workflow for landing page validation:**

```markdown
Step 1: Launch server
$ ./.claude/skills/frontend-testing/launch.sh ./dist 8080

Step 2: Navigate to page
mcp__playwright__browser_navigate(url: "http://localhost:8080")

Step 3: Wait for page stability
mcp__playwright__browser_wait_for(time: 2)

Step 4: Capture page snapshot
snapshot = mcp__playwright__browser_snapshot()
# Review snapshot to verify:
# - Title contains "Welcome" or expected text
# - H1 element has correct content
# - CTA button is present

Step 5: Take screenshot for proof
mcp__playwright__browser_take_screenshot(filename: "landing-page-test.png")

Step 6: Check for console errors
errors = mcp__playwright__browser_console_messages(onlyErrors: true)
# Verify no errors present

Step 7: Test interaction
mcp__playwright__browser_click(
  element: "Get Started button",
  ref: "<ref-from-snapshot>"
)

Step 8: Verify navigation
mcp__playwright__browser_wait_for(text: "Sign Up")
mcp__playwright__browser_take_screenshot(filename: "signup-page.png")

Step 9: Teardown
$ ./.claude/skills/frontend-testing/teardown.sh 8080

Result: ✅ Landing page test PASSED
```

### Capsule Quality Gate Integration

**MCP-Based Testing in Quality Gates:**

```yaml
# capsules/ecommerce/ops/dod.yaml
testing:
  frontend:
    mode: "MCP-based validation using Playwright Agent"
    quick_verify:
      - name: "Homepage renders"
        method: "Use Playwright MCP: navigate + snapshot + screenshot"
        url: "http://localhost:3000"
      - name: "Product page loads"
        method: "Use Playwright MCP: navigate + verify content + screenshot"
        url: "http://localhost:3000/products"
    comprehensive:
      - name: "Product listing interactions"
        method: "Delegate to Playwright Agent with browser-automation output style"
        tests:
          - "Add to cart button works"
          - "Quantity selector functions"
          - "Price updates correctly"
      - name: "Checkout flow"
        method: "Delegate to Playwright Agent with comprehensive test scenario"
        tests:
          - "Cart page displays items"
          - "Shipping form validates"
          - "Payment page renders"
```

---

## Best Practices

### Selector Strategy (MCP)

**When using MCP snapshot refs:**
```markdown
# ✅ GOOD - Use refs from snapshot for reliability
mcp__playwright__browser_click(
  element: "Submit button",
  ref: "button-abc123"  # From snapshot output
)

# ✅ GOOD - Use descriptive element names
mcp__playwright__browser_type(
  element: "Email input field",
  ref: "input-email-xyz",
  text: "test@example.com"
)

# ⚠️ CAUTION - Generic selectors work but are less specific
# Prefer getting exact refs from snapshots
```

### Browser Configuration

**Huxley Playwright MCP is pre-configured:**
- Browser: Chromium
- Headless: No (visible for debugging)
- Viewport: 1280x720
- SlowMo: 100ms (for visibility)
- Output: /tmp/playwright-mcp-output/
- Traces: Enabled

**No additional configuration needed** - just use MCP tools directly.

### MCP Tool Lifecycle

**Browser lifecycle is managed automatically:**
- MCP server handles browser launch/close
- No manual cleanup required
- Just use the tools sequentially
- Browser persists across tool calls in same session

---

## Tool Files

### SKILL.md (This File)
- Complete skill documentation
- MCP-based testing workflows
- Examples and patterns
- Best practices

### README.md (Quick Reference)
- Quick start guide
- Common commands
- Integration patterns

### launch.sh (Server Launcher)
- Starts Python HTTP server
- Checks port availability
- Writes PID file
- Waits for server ready
- Usage: `./launch.sh <directory> [port]`

### teardown.sh (Server Cleanup)
- Stops dev server gracefully
- Cleans up PID and log files
- Force kill if needed
- Usage: `./teardown.sh [port]`

### MCP Tools Used
- `mcp__playwright__browser_navigate` - Navigate to URL
- `mcp__playwright__browser_snapshot` - Capture accessibility tree
- `mcp__playwright__browser_click` - Click elements
- `mcp__playwright__browser_type` - Type into inputs
- `mcp__playwright__browser_fill_form` - Fill multiple form fields
- `mcp__playwright__browser_take_screenshot` - Capture visual proof
- `mcp__playwright__browser_console_messages` - Check for errors
- `mcp__playwright__browser_network_requests` - Review network activity
- `mcp__playwright__browser_wait_for` - Wait for conditions

---

## Integration with Huxley

### Development Workflow

```
1. Write UI code
2. Launch server: ./launch.sh ./dist 8080
3. Quick verify using Playwright MCP:
   - Navigate to page
   - Capture snapshot
   - Check console
   - Take screenshot
4. Iterate on errors
5. Teardown: ./teardown.sh 8080
6. Commit when verified
```

### Capsule Completion Workflow

```
1. Delegate to Playwright Agent with comprehensive test scenario
2. All tests must PASS
3. Screenshots captured for proof-of-work
4. Test results documented in capsule
5. Capsule marked complete
```

---

## Quick Reference

**Quick verification (MCP):**
```bash
# Launch server
./launch.sh ./dist 8080

# Use MCP tools (via {{ORCHESTRATOR_NAME}} or Playwright Agent)
mcp__playwright__browser_navigate(url: "http://localhost:8080")
mcp__playwright__browser_snapshot()
mcp__playwright__browser_console_messages()
mcp__playwright__browser_take_screenshot(filename: "verify.png")

# Teardown
./teardown.sh 8080
```

**Comprehensive testing (MCP):**
```markdown
# 1. Navigate and wait for stability
mcp__playwright__browser_navigate(url: "...")
mcp__playwright__browser_wait_for(time: 2)

# 2. Capture state
snapshot = mcp__playwright__browser_snapshot()
mcp__playwright__browser_take_screenshot(filename: "state.png")

# 3. Identify elements from snapshot refs

# 4. Interact
mcp__playwright__browser_click(element: "...", ref: "...")

# 5. Verify result
mcp__playwright__browser_wait_for(text: "Success")
mcp__playwright__browser_take_screenshot(filename: "result.png")
```
