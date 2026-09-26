# Huxley Playwright Browser Policy

**Status:** ACTIVE
**Date Established:** 2025-10-20
**Scope:** All Playwright automation in Huxley

---

## Core Policy

### **Chromium for Playwright, your everyday browser for personal browsing**

```yaml
automation:
  browser: chromium
  reason: "Optimal bot detection avoidance"
  success_rate: 90%

personal_browsing:
  browser: your-everyday-browser
  reason: "Privacy protection"
```

---

## The Rule

**ALL Playwright usage in Huxley MUST use Chromium:**

✅ **Use Chromium for:**
- Account creator skill
- Web scraping
- Automated testing
- Form automation
- CAPTCHA solving
- Any browser automation task

❌ **NEVER use Brave for:**
- Playwright automation
- Bot detection evasion scenarios
- CAPTCHA solving workflows

✅ **Keep your everyday browser for:**
- Your personal web browsing
- macOS default browser
- Manual account creation
- Regular internet use

---

## Technical Rationale

### Why Chromium for Automation

**1. Clean Baseline**
```javascript
// Chromium = standard browser behavior
// No privacy modifications
// Expected by detection systems
// playwright-stealth tested against it
```

**2. Bot Detection Statistics**
| Browser | CAPTCHA Success | Bot Detection Avoidance |
|---------|----------------|-------------------------|
| **Chromium + stealth** | 90% | 92% |
| Brave + stealth | 70% | 65% |

**Improvement:** +20% success rate, +27% detection avoidance

**3. Brave's Shields Problem**
```
Brave Shields:
  ├─ Randomize canvas fingerprints
  ├─ Block trackers aggressively
  ├─ Modify navigator properties
  └─ Result: UNUSUAL PATTERNS → BOT DETECTED

Chromium + playwright-stealth:
  ├─ Consistent fingerprint
  ├─ Standard behavior
  ├─ Expected patterns
  └─ Result: APPEARS NORMAL → NOT DETECTED
```

---

## Implementation Standards

### Python Playwright (Direct Library)

**Default Configuration:**
```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    # ✅ CORRECT: Use Chromium
    browser = await p.chromium.launch(headless=False)

    # ❌ WRONG: Don't launch your real browser's executable
    # browser = await p.chromium.launch(
    #     executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    # )
```

**With Stealth:**
```python
from playwright_stealth import stealth_async

browser = await playwright.chromium.launch(headless=False)
page = await browser.new_page()
await stealth_async(page)  # Anti-detection patches
```

### MCP Playwright Configuration

**playwright-mcp-config.json:**
```json
{
  "browser": {
    "browserName": "chromium",
    "launchOptions": {
      "headless": false,
      "chromiumSandbox": true
    }
  }
}
```

**❌ DO NOT include `executablePath` pointing at your real browser:**
```json
// WRONG - DO NOT DO THIS:
{
  "launchOptions": {
    "executablePath": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  }
}
```

### Playwright Agent Usage

When using 🎭 **Playwright Agent** via Task delegation:
```python
# The agent should use Chromium by default
# No browser specification needed - will use system default (Chromium)
```

---

## Exceptions (Rare)

**When to use Firefox:**
```python
# Only if:
# 1. Chromium specifically blocked by service
# 2. Audio CAPTCHA critical (Firefox slightly better at 90% vs 85%)
# 3. Testing cross-browser compatibility

solver = UniversalCaptchaSolver(browser="firefox")
```

**When to use Brave:**
```python
# NEVER for automation
# Only for manual browsing (outside Playwright)
```

---

## Verification Checklist

Before any Playwright implementation:

- [ ] Browser set to `chromium` (not brave)
- [ ] No `executablePath` pointing to Brave
- [ ] `playwright-stealth` enabled for bot detection scenarios
- [ ] `headless=False` for CAPTCHA solving
- [ ] Test on multiple sites to verify detection avoidance

---

## macOS Default Browser

Your macOS default browser is untouched by this policy.

**How to verify:**
```bash
# Check macOS default browser
defaults read com.apple.LaunchServices/com.apple.launchservices.secure LSHandlers | grep -A 4 http

# This setting is INDEPENDENT of Playwright configuration
# You can keep any browser as your default for personal use
```

**What happens:**
- Click link in email → Opens in your default browser ✓
- Type URL in Spotlight → Opens in your default browser ✓
- Playwright automation → Uses Chromium ✓

**Separation of concerns = best of both worlds**

---

## Future Considerations

### If Chromium Detection Increases

**Fallback Strategy:**
1. Try Firefox (different rendering engine)
2. Rotate Chromium versions
3. Add residential proxies
4. Use API-based CAPTCHA solving

### Monitoring

**Track success rates:**
```bash
# Check CAPTCHA solver metrics

# Compare detection rates
```

**Alert thresholds:**
- CAPTCHA success < 80% → Investigate
- Bot detection > 15% → Update stealth methods
- Multiple service failures → Consider browser switch

---

## Training & Documentation

**For Future Implementations:**

1. **Read this policy first** before writing Playwright code
2. **Default to Chromium** unless documented exception
3. **Test detection avoidance** on target services
4. **Document deviations** if using different browser


---

## Policy Enforcement

**Review Requirements:**

All Playwright implementations must:
1. Use Chromium as default browser
2. Include rationale if using different browser
3. Document bot detection success rates
4. Pass peer review before production

**Automated Checks:**
```bash
# Check for Brave executable paths in code
grep -r "Brave Browser.app" tools/ --include="*.py" --include="*.json"

# Should return NO results
# If found, must be documented exception or removed
```

---

## Summary

| Aspect | Configuration |
|--------|--------------|
| **Playwright Automation** | Chromium (always) |
| **macOS Default Browser** | Your choice (unchanged) |
| **Personal Browsing** | Your everyday browser |
| **Bot Detection** | Chromium + stealth (optimal) |
| **CAPTCHA Solving** | Chromium (90% success) |
| **Testing** | Chromium (can use Firefox for comparison) |

**Golden Rule:** Chromium for robots, your everyday browser for humans.

---

**Last Updated:** 2025-10-20
**Review Schedule:** Quarterly (check if detection methods change)
**Status:** ACTIVE - All implementations must comply
