# iOS Testing Skill - Example Usage

## Scenario: Testing a Simple iOS App

Let's walk through testing a basic iOS app with the skill.

### App Overview
- **Name**: SimpleCounter
- **Type**: SwiftUI app
- **Features**: Counter with increment/decrement buttons
- **Project**: SimpleCounter.xcodeproj

---

## Example 1: Quick Verification (Happy Path)

### User Request
```
"Quick verify SimpleCounter.xcodeproj on iPhone 16"
```

### Skill Execution

**Step 1: Build and Run**
```markdown
{{ORCHESTRATOR_NAME}}: 🔨 Building SimpleCounter for iPhone 16...

[Using mcp__xcodebuildmcp__build_run_sim]
Result:
  ✅ BUILD SUCCEEDED
  ✅ App installed to simulator
  ✅ App launched successfully
```

**Step 2: Visual Verification**
```markdown
{{ORCHESTRATOR_NAME}}: 📸 Capturing screenshot...

[Using mcp__xcodebuildmcp__screenshot]
Result:
  Screenshot saved to: /tmp/simulator-screenshot.png
  Shows: Counter app with "Count: 0" and +/- buttons
```

**Step 3: UI Validation**
```markdown
{{ORCHESTRATOR_NAME}}: 🌳 Analyzing UI tree...

[Using mcp__xcodebuildmcp__describe_ui]
Result:
  Found elements:
  ✅ Text("Count: 0")
  ✅ Button("+")
  ✅ Button("-")
  ✅ Navigation("Counter App")
```

**Step 4: Report**
```markdown
{{ORCHESTRATOR_NAME}}: ✅ Quick verification complete!

Summary:
  • Build: SUCCESS
  • Launch: SUCCESS
  • UI Elements: All present
  • Console: No errors
  • Duration: 18 seconds

SimpleCounter.xcodeproj is working correctly on iPhone 16.
```

---

## Example 2: Debug Loop (Bug Detection and Fix)

### User Request
```
"Debug SimpleCounter.xcodeproj until working on iPhone 16"
```

### Initial State
The app has a bug: increment button handler is commented out

```swift
// In ContentView.swift
Button("+") {
    // count += 1  // Commented out by mistake!
}
```

### Skill Execution

#### Iteration 1

**Build and Run**
```markdown
{{ORCHESTRATOR_NAME}}: 🔄 Debug iteration 1/10

🔨 Building SimpleCounter...
✅ Build succeeded

🚀 Launching on iPhone 16...
✅ App launched

📸 Capturing screenshot...
🌳 Getting UI tree...
```

**Issue Detection**
```markdown
{{ORCHESTRATOR_NAME}}: 🔍 Monitoring for issues...

[Analyzing logs, UI state, behavior]

❌ Issues detected:

1. UI Error:
   - Element: Button("+")
   - Expected: Tapping increments counter
   - Actual: No action occurs
   - Evidence: Console shows button tap but no state change

2. Behavioral Issue:
   - Counter remains at 0 after multiple taps
   - Expected behavior: Should increment

Severity: HIGH (feature not working)
```

**Delegate to Mobile Dev**
```markdown
{{ORCHESTRATOR_NAME}}: 🤖 Delegating to Mobile Dev agent...

[Using Task tool]
Task({
  subagent_type: "📱 Mobile Dev",
  description: "Fix SimpleCounter increment button (iteration 1)",
  prompt: """
  The iOS app has 1 issue that needs fixing:

  **Issue 1: Increment button not working**
  - Type: UI Error + Behavioral Issue
  - Severity: HIGH
  - Details: Button "+" does not increment counter when tapped

  **Diagnostics:**
  - Screenshot: Shows counter stuck at 0
  - UI Tree: Button exists and is tappable
  - Logs: Button tap registered but no state change
  - Project: {{HOME_DIR}}/SimpleCounter.xcodeproj

  **Expected Behavior:**
  Tapping "+" button should increment counter by 1

  Please analyze and fix the root cause.
  """
})
```

**Mobile Dev Agent Response**
```markdown
Mobile Dev: 📝 Analyzing SimpleCounter increment button issue...

Root Cause:
  File: ContentView.swift:23
  Issue: Button action is commented out
  Code:
    Button("+") {
        // count += 1  // <- This line is commented!
    }

🔧 Fixing...

[Edits ContentView.swift]
- Uncommented: count += 1

✅ Fix complete.

Changes made:
  • ContentView.swift: Enabled increment action
```

**Rebuild and Retest**
```markdown
{{ORCHESTRATOR_NAME}}: 🔄 Rebuilding SimpleCounter...

🔨 Building...
✅ Build succeeded

🚀 Launching...
✅ App launched

🔍 Testing increment button...
✅ Counter increments correctly (0 → 1 → 2 → 3)

📸 Final screenshot shows working counter

✅ No issues detected!
```

**Success Report**
```markdown
{{ORCHESTRATOR_NAME}}: 🎉 SimpleCounter verified working!

Summary:
  • Fixed in: 1 iteration
  • Issues resolved: 1
  • Fix: Uncommented increment button action
  • Total time: 3 minutes 12 seconds
  • Final state: All features working

The app is now ready for testing or deployment.
```

---

## Example 3: Complex Debug Loop (Multiple Issues)

### User Request
```
"Debug BrokenApp.xcodeproj until working on iPhone 16"
```

### Initial State
The app has multiple issues:
1. Missing import statement (build error)
2. Wrong button label (UI error)
3. Memory leak in view (console warning)

### Skill Execution Summary

#### Iteration 1
```
Issue: Build failure (missing import)
Fix: Mobile Dev adds "import SwiftUI"
Result: Build succeeds, but new issues found
```

#### Iteration 2
```
Issue: Button labeled "Sbmit" instead of "Submit"
Fix: Mobile Dev corrects typo
Result: UI correct, but console warning found
```

#### Iteration 3
```
Issue: Memory leak warning in console
Fix: Mobile Dev removes strong reference cycle
Result: All issues resolved ✅
```

**Final Report**
```markdown
{{ORCHESTRATOR_NAME}}: 🎉 BrokenApp verified working!

Summary:
  • Fixed in: 3 iterations
  • Issues resolved: 3
    1. Build error (missing import)
    2. UI error (button typo)
    3. Memory leak (reference cycle)
  • Total time: 8 minutes 45 seconds
  • Mobile Dev fixes: 3
  • Final state: App working perfectly

All issues systematically detected and fixed automatically.
```

---

## Example 4: Test Suite Execution

### User Request
```
"Run all tests for MyApp.xcodeproj on iPhone 16"
```

### Skill Execution

**Build for Testing**
```markdown
{{ORCHESTRATOR_NAME}}: 🔨 Building MyApp for testing...

✅ Build succeeded for testing
```

**Run Tests**
```markdown
{{ORCHESTRATOR_NAME}}: 🧪 Running test suite...

[Using mcp__xcodebuildmcp__test_sim]

Test Results:
  ✅ testCounterIncrement - PASSED (0.12s)
  ✅ testCounterDecrement - PASSED (0.08s)
  ❌ testCounterReset - FAILED (0.15s)
     Expected: 0, Got: 5
  ✅ testButtonLabels - PASSED (0.05s)
  ❌ testNavigationTitle - FAILED (0.03s)
     Expected: "Counter", Got: "Countr"

Summary:
  Total: 5 tests
  Passed: 3 (60%)
  Failed: 2 (40%)
  Duration: 0.43s
```

**Automatic Debug Loop for Failures**
```markdown
{{ORCHESTRATOR_NAME}}: ❌ Tests failed. Entering debug loop...

🤖 Delegating to Mobile Dev agent...

Issue 1: testCounterReset failure
Issue 2: testNavigationTitle failure

Mobile Dev: Fixing...
  1. Reset button not clearing counter → Fixed
  2. Navigation title typo → Fixed

{{ORCHESTRATOR_NAME}}: 🔄 Re-running tests...

Test Results (Retry):
  ✅ testCounterIncrement - PASSED (0.11s)
  ✅ testCounterDecrement - PASSED (0.09s)
  ✅ testCounterReset - PASSED (0.14s)
  ✅ testButtonLabels - PASSED (0.06s)
  ✅ testNavigationTitle - PASSED (0.04s)

✅ All tests passed! (5/5)
```

---

## Example 5: Safety Limit (Max Iterations)

### Scenario
App has a fundamental architectural issue that requires major refactoring

### Execution
```markdown
{{ORCHESTRATOR_NAME}}: 🔄 Debug iteration 1/10
  Issue: Data model thread safety violation
  Fix: Mobile Dev adds locks

{{ORCHESTRATOR_NAME}}: 🔄 Debug iteration 2/10
  Issue: Still crashing (different thread)
  Fix: Mobile Dev adds more locks

{{ORCHESTRATOR_NAME}}: 🔄 Debug iteration 3/10
  Issue: Deadlock now occurring
  Fix: Mobile Dev removes locks, tries dispatch queue

... [iterations 4-9 continue with different approaches]

{{ORCHESTRATOR_NAME}}: 🔄 Debug iteration 10/10
  Issue: Still unstable under load
  Fix: Mobile Dev attempts optimization

{{ORCHESTRATOR_NAME}}: ⚠️ Maximum iterations (10) reached

❌ Unable to fix BrokenApp automatically.

Manual intervention required.

Diagnostic bundle created:
  • Logs: /tmp/brokenapp-debug-logs.txt
  • Screenshots: /tmp/brokenapp-screenshots/
  • Issue history: /tmp/brokenapp-issues.json
  • All attempted fixes documented

Recommendation:
  The app requires architectural refactoring beyond
  automated fixes. Please review the diagnostic bundle
  and consider:

  1. Redesigning data layer for thread safety
  2. Adding comprehensive unit tests
  3. Code review with senior engineer

The skill has captured all context for manual debugging.
```

---

## Example 6: Integration with Xcode Previews

### Scenario
Using both Previews and Simulator for optimal workflow

### Workflow
```markdown
User: "I'm working on the profile screen UI"

{{ORCHESTRATOR_NAME}}: Using SwiftUI Previews for rapid iteration...

[Mobile Dev works in Xcode with live previews]

Mobile Dev: ✅ Profile screen layout complete

User: "Now test the full navigation flow to profile"

{{ORCHESTRATOR_NAME}}: Switching to simulator for integration testing...

[Using ios-testing skill]

Quick verify flow:
  1. Launch app in simulator
  2. Navigate: Home → Settings → Profile
  3. Verify: All navigation works
  4. Screenshot: Profile screen matches preview

✅ Navigation flow verified working
```

**Key Insight**: Previews for UI work, Simulator for integration testing

---

## Summary of Examples

| Example | Scenario | Iterations | Time | Outcome |
|---------|----------|-----------|------|---------|
| **1. Quick Verify** | Working app | 0 | 18s | ✅ Verified |
| **2. Simple Bug** | 1 button issue | 1 | 3m 12s | ✅ Fixed |
| **3. Multiple Issues** | 3 different bugs | 3 | 8m 45s | ✅ Fixed |
| **4. Test Suite** | 2 test failures | 1 | 5m 30s | ✅ Fixed |
| **5. Max Iterations** | Architectural issue | 10 | 35m | ⚠️ Manual needed |
| **6. Preview + Sim** | UI + integration | N/A | Variable | ✅ Hybrid approach |

---

## Key Takeaways

1. **Quick verification** for working apps: ~20 seconds
2. **Simple bugs** fixed automatically: 1-2 iterations
3. **Complex bugs** systematically resolved: 3-5 iterations
4. **Safety limit** prevents infinite loops: 10 iterations max
5. **Test failures** trigger automatic debug loop
6. **Complementary to Previews**: Previews for UI, Simulator for integration

**The skill works best when**:
- Issues are well-defined (crashes, UI errors, test failures)
- Project structure is standard (Xcode conventions)
- Mobile Dev agent has clear error messages to work from

**Manual intervention needed when**:
- Architectural changes required
- Multiple approaches fail repeatedly
- Issue is ambiguous or environmental

---

*These examples demonstrate the full range of the ios-testing skill's capabilities, from quick smoke tests to complex multi-issue debugging scenarios.*
