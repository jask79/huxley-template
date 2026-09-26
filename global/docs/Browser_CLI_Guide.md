# Browser Automation CLI Guide

## Principle: CLI First, MCP Last

CLIs are more stable, predictable, and debuggable than MCPs. For browser automation, Huxley follows this hierarchy:

1. **agent-browser CLI** — Quick tasks, page inspection
2. **Direct Playwright Library** — Complex automation, anti-detection
3. **Playwright MCP** — Last resort for other agents

---

## agent-browser CLI

**Installation:** `npm install -g agent-browser && agent-browser install`
**Location:** `/opt/homebrew/bin/agent-browser`
**Version:** 0.9.0+

### Core Concepts

**Accessibility Tree with Refs:**
agent-browser returns semantic element identifiers (`@e1`, `@e2`) instead of fragile CSS selectors. This is AI-optimized — agents can parse the tree and target elements by ref.

**Client-Daemon Pattern:**
A daemon persists between commands, making subsequent operations faster. No browser restart overhead.

**Session/Profile Persistence:**
- `--session <name>` — Named isolated browser instance
- `--profile <path>` — Persistent auth state across restarts

---

### Quick Reference

#### Navigation
```bash
agent-browser open https://example.com          # Open URL
agent-browser open https://example.com --headless  # Headless mode
agent-browser back                              # Go back
agent-browser forward                           # Go forward
agent-browser reload                            # Reload page
```

#### Page Inspection
```bash
agent-browser snapshot                          # Full accessibility tree
agent-browser snapshot -i                       # Interactive elements only
agent-browser snapshot -i --json                # JSON for AI parsing
agent-browser snapshot -c                       # Remove empty elements
agent-browser snapshot -d 3                     # Limit depth to 3 levels
agent-browser get text @e1                      # Get element text
agent-browser get html @e1                      # Get element HTML
```

#### Interaction
```bash
agent-browser click @e1                         # Click element by ref
agent-browser fill @e2 "hello@example.com"      # Fill input field
agent-browser type "password123"                # Type text (no target)
agent-browser press Enter                       # Press key
agent-browser hover @e3                         # Hover element
agent-browser select @e4 "option-value"         # Select dropdown option
```

#### Screenshots
```bash
agent-browser screenshot /tmp/page.png          # Full page screenshot
agent-browser screenshot /tmp/el.png -s @e1    # Element screenshot
```

#### Sessions & Profiles
```bash
# Named sessions (parallel isolated browsers)
agent-browser --session github open https://github.com
agent-browser --session gitlab open https://gitlab.com
agent-browser --session github snapshot -i      # Use specific session

# Persistent profiles (auth state survives restart)
agent-browser --profile ~/.profiles/github open https://github.com
# ... login manually or via automation ...
# Next time: already logged in
agent-browser --profile ~/.profiles/github open https://github.com/settings
```

#### Cookies & Storage
```bash
agent-browser cookies                           # List cookies
agent-browser cookies --set "name=value"        # Set cookie
agent-browser storage local                     # Get localStorage
agent-browser storage session                   # Get sessionStorage
```

---

### JSON Output for AI Agents

Use `--json` for machine-readable output:

```bash
agent-browser snapshot -i --json
```

Output:
```json
{
  "success": true,
  "data": {
    "refs": {
      "e1": {"name": "Sign in", "role": "link"},
      "e2": {"name": "Email", "role": "textbox"},
      "e3": {"name": "Password", "role": "textbox"},
      "e4": {"name": "Submit", "role": "button"}
    },
    "snapshot": "- link \"Sign in\" [ref=e1]\n- textbox \"Email\" [ref=e2]\n..."
  },
  "error": null
}
```

**AI Agent Pattern:**
1. Navigate to page
2. `snapshot -i --json` to get element refs
3. Parse JSON, identify target elements
4. Execute actions using refs (`click @e2`, `fill @e3 "value"`)
5. Re-snapshot if page updates

---

### When to Use agent-browser vs Direct Playwright

| Use Case | agent-browser CLI | Direct Playwright |
|----------|------------------|-------------------|
| Quick page inspection | ✅ | ❌ |
| Screenshot capture | ✅ | ✅ |
| Simple form filling | ✅ | ✅ |
| Account creation | ❌ | ✅ |
| Anti-detection needed | ❌ | ✅ (playwright-stealth) |
| CAPTCHA solving | ❌ | ✅ (playwright-recaptcha) |
| Human behavior simulation | ❌ | ✅ |
| Session persistence | ✅ (`--session/--profile`) | ✅ (via config) |
| Parallel browsers | ✅ (named sessions) | ✅ (multiple contexts) |

---

## Direct Playwright Library

**Location:** `{{CATALYST_ROOT}}/tools/registration_automation.py`

### Features Beyond agent-browser

- **playwright-stealth** — Fingerprint evasion, removes `navigator.webdriver`
- **playwright-recaptcha** — reCAPTCHA v2/v3 audio solving (~85-90%)
- **hcaptcha-challenger** — hCaptcha solving via Gemini vision
- **Human simulation** — Mouse curves, typing delays (80-250ms/char), typo correction
- **Dynamic field detection** — Site-agnostic form discovery

### Usage

```bash
# Basic registration
python3 {{CATALYST_ROOT}}/tools/registration_automation.py \
  https://site.com/signup \
  --email user@example.com \
  --password SecurePass123! \
  --username myusername

# With named session (NEW)
python3 {{CATALYST_ROOT}}/tools/registration_automation.py \
  https://site.com/signup \
  --email user@example.com \
  --password SecurePass123! \
  --session github-dev

# With persistent profile (NEW)
python3 {{CATALYST_ROOT}}/tools/registration_automation.py \
  https://site.com/signup \
  --email user@example.com \
  --password SecurePass123! \
  --profile ~/.browser_profiles/github

# Debug mode (visible browser)
python3 {{CATALYST_ROOT}}/tools/registration_automation.py \
  https://site.com/signup \
  --email user@example.com \
  --password SecurePass123!
  # (headless=False is default for debugging)
```

### Session Storage

Named sessions are stored in:
```
{{CATALYST_ROOT}}/.cache/browser_sessions/<session-name>/
```

Custom profiles use the specified path directly.

---

## Playwright MCP (Last Resort)

**Use only when CLI tools aren't available or for other agents.**

Available tools:
- `mcp__playwright__browser_navigate`
- `mcp__playwright__browser_snapshot`
- `mcp__playwright__browser_click`
- `mcp__playwright__browser_fill_form`
- `mcp__playwright__browser_take_screenshot`

**Drawbacks:**
- Protocol overhead (JSON-RPC, SSE)
- Opaque failure modes
- No anti-detection
- No CAPTCHA solving
- Harder to debug

---

## Agent Routing

| Agent | Primary Tool | Reason |
|-------|-------------|--------|
| **Bowser** | Direct Playwright Library | Needs anti-detection, CAPTCHA |
| **Validator** | agent-browser CLI or Playwright MCP | Simple verification |
| **Frontend Dev** | agent-browser CLI | Quick inspection |
| **{{ORCHESTRATOR_NAME}}** | agent-browser CLI | Quick checks |

---

## Troubleshooting

### agent-browser "Executable doesn't exist"

Browser version mismatch. Fix:
```bash
npx playwright install chromium
```

### Session not persisting

Ensure you're using the same `--session` or `--profile` flag on subsequent runs:
```bash
# First run
agent-browser --session myapp open https://app.com
# ... login ...

# Second run (MUST use same session name)
agent-browser --session myapp snapshot -i  # Still logged in
```

### CAPTCHA not solving

agent-browser doesn't solve CAPTCHAs. Use Direct Playwright Library:
```bash
python3 tools/registration_automation.py https://site.com/signup \
  --email x@y.com --password pass
```

---

## References

- [agent-browser GitHub](https://github.com/vercel-labs/agent-browser)
- [Playwright Python Docs](https://playwright.dev/python/docs/intro)
- [playwright-stealth](https://github.com/AtuboDad/playwright_stealth)
- [playwright-recaptcha](https://github.com/Xewdy444/Playwright-reCAPTCHA)
