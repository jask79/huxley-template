# Frontend Testing Examples

Pre-built test examples demonstrating comprehensive testing patterns.

## Available Tests

### test_landing_page.py
**Purpose:** Tests landing page rendering, basic interactions, and console errors

**Usage:**
```bash
python test_landing_page.py [url]
python test_landing_page.py http://localhost:8080
```

**Checks:**
- Page loads successfully
- No console errors
- No network failures
- Page has content
- Interactive elements present (buttons, links, forms)

**Output:**
- `landing-page.png` - Full page screenshot
- Exit code: 0 (pass) or 1 (fail)

---

### test_form_submit.py
**Purpose:** Tests form filling, submission, and validation

**Usage:**
```bash
python test_form_submit.py [url]
python test_form_submit.py http://localhost:8080/signup
```

**Checks:**
- Form elements exist (email, password, submit button)
- Form can be filled
- Form submission works
- Success/error message appears

**Output:**
- `form-initial.png` - Form before filling
- `form-filled.png` - Form after filling
- `form-success.png` or `form-failed.png` - Result
- Exit code: 0 (pass) or 1 (fail)

---

## Creating Custom Tests

### Template

```python
#!/usr/bin/env python3
"""
Frontend Testing - [Test Name]

[Description of what this test does]

Usage: python test_[name].py [url]
"""

from playwright.async_api import async_playwright
import asyncio
import sys

async def test_[name](url="http://localhost:8080"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            print(f"🔍 Testing [feature]: {url}")

            # RECONNAISSANCE - Wait for stability
            await page.goto(url)
            await page.wait_for_load_state("networkidle")

            # CAPTURE - Take snapshot
            await page.screenshot(path="test-state.png")

            # IDENTIFY - Find selectors
            # ... your selector logic

            # ACTION - Interact with page
            # ... your interaction logic

            # VALIDATE - Check results
            # ... your validation logic

            print("\n✅ Test PASSED")
            return 0

        except Exception as e:
            print(f"\n❌ Test FAILED: {e}")
            return 1

        finally:
            await browser.close()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    exit_code = asyncio.run(test_[name](url))
    sys.exit(exit_code)
```

## Best Practices

1. **Always wait for networkidle** before inspecting DOM
2. **Use descriptive selectors** (role, text, label) over CSS classes
3. **Capture screenshots** at key stages
4. **Handle both success and failure** cases
5. **Return proper exit codes** (0 = pass, 1 = fail)
6. **Log progress** so users can follow along
7. **Close browser** even if test fails (use try/finally)

## Integration with Capsules

Add tests to capsule quality gates:

```yaml
# capsules/[your-capsule]/ops/dod.yaml
testing:
  frontend:
    - name: "Landing page renders"
      script: "python .claude/skills/frontend-testing/examples/test_landing_page.py http://localhost:3000"

    - name: "Signup form works"
      script: "python .claude/skills/frontend-testing/examples/test_form_submit.py http://localhost:3000/signup"
```

## Running All Tests

Create a test suite runner:

```bash
#!/bin/bash
# test_suite.sh

echo "Running frontend test suite..."

python examples/test_landing_page.py http://localhost:8080
TEST1=$?

python examples/test_form_submit.py http://localhost:8080/signup
TEST2=$?

if [ $TEST1 -eq 0 ] && [ $TEST2 -eq 0 ]; then
    echo "✅ All tests passed"
    exit 0
else
    echo "❌ Some tests failed"
    exit 1
fi
```
