---
name: ios-testing
description: Comprehensive iOS app testing and debugging using Xcode simulator with agentic fix loop and advanced simulator controls
when: Building or debugging iOS apps, running simulator tests, validating mobile UI/UX, testing network conditions, simulating locations, or testing accessibility features
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Task
  - mcp__xcodebuildmcp__build_sim
  - mcp__xcodebuildmcp__build_run_sim
  - mcp__xcodebuildmcp__boot_sim
  - mcp__xcodebuildmcp__list_sims
  - mcp__xcodebuildmcp__open_sim
  - mcp__xcodebuildmcp__install_app_sim
  - mcp__xcodebuildmcp__launch_app_sim
  - mcp__xcodebuildmcp__launch_app_logs_sim
  - mcp__xcodebuildmcp__stop_app_sim
  - mcp__xcodebuildmcp__start_sim_log_cap
  - mcp__xcodebuildmcp__stop_sim_log_cap
  - mcp__xcodebuildmcp__test_sim
  - mcp__xcodebuildmcp__screenshot
  - mcp__xcodebuildmcp__describe_ui
  - mcp__xcodebuildmcp__get_sim_app_path
metadata:
  version: "2.1.0"
  architecture: "Uses xcodebuildmcp + Huxley Simulator Control + Advanced Testing Framework"
  platform: "iOS (simulator)"
  last_updated: "2025-10-27"
  enhancements:
    - "Network monitoring and throttling"
    - "Location simulation and GPS routes"
    - "Environment controls (Dark Mode, Dynamic Type, accessibility)"
    - "Push notifications and deep links"
    - "UserDefaults manipulation"
    - "Status bar overrides"
    - "Visual regression testing (screenshot_diff.py)"
    - "Test matrix automation (ios_test_matrix.rb)"
    - "Network log analysis (pulse_log_export.rb)"
    - "One-command setup for testing infrastructure"
---

# iOS Testing & Debug Loop Skill

## Purpose
Comprehensive iOS application testing with automated debugging loop:
1. **Quick Verification** - Fast smoke tests during development (dev loop)
2. **Debug Loop** - Automatic issue detection and fix coordination with Mobile Dev agent
3. **Test Suite** - Comprehensive unit and UI test execution

## Key Features

- ✅ **Agentic Fix Loop** - Automatically detects issues and coordinates fixes with Mobile Dev agent
- ✅ **Real-time Feedback** - Live simulator, logs, and screenshots
- ✅ **UI Validation** - Accessibility tree analysis via describe_ui
- ✅ **Log Monitoring** - Automatic crash and error detection
- ✅ **Visual Verification** - Screenshot-based proof-of-work
- ✅ **Test Execution** - Unit and UI test suite support

## 🚀 NEW: Simulator Enhancement Capabilities (v2.0)

### Huxley Simulator Control Tool
**Location:** `{{CATALYST_ROOT}}/tools/simulator_control.rb`

Comprehensive simulator control tool providing:

#### **Network Capabilities**
- **Network Throttling** - Simulate 3G, Edge, LTE, 5G, WiFi, or offline conditions
- **Network Monitoring** - Real-time request inspection via Pulse (SPM package)
- **Status Bar Network Indicators** - Visual feedback for network state

#### **Location & GPS**
- **Set GPS Coordinates** - Test location-based features at any coordinates
- **GPX Route Simulation** - Play back walking/driving routes from GPX files
- **Named Locations** - Quick shortcuts to common test locations (SF, NYC, Tokyo, etc.)
- **Location Reset** - Clear location overrides

#### **Environment Controls**
- **Dark/Light Mode** - Toggle appearance instantly
- **Dynamic Type** - Test all 11 text size categories (XS → AccessibilityXXXL)
- **Accessibility Features** - Enable bold text, reduce motion, increase contrast, button shapes, etc.
- **Environment Reset** - Reset all overrides to defaults

#### **Quick Actions**
- **Push Notifications** - Send test push notifications with custom payloads
- **Deep Links** - Open URL schemes and universal links
- **Status Bar Overrides** - Perfect time (9:41), full battery, signal bars for screenshots

#### **App Preferences**
- **Read UserDefaults** - Inspect app preferences and feature flags
- **Write UserDefaults** - Test feature toggles and configuration changes
- **Delete Keys** - Remove specific preference keys

#### **Simulator Management**
- **List Simulators** - View all available simulators with states
- **Boot/Shutdown** - Control simulator lifecycle
- **Erase** - Reset simulator to factory state
- **Get UDID** - Convert simulator names to UDIDs

### Usage Examples

**Network Testing:**
```bash
# Simulate 3G network
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb network-throttle \
  --simulator "iPhone 16" \
  --profile 3g

# Reset to normal network
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb network-reset \
  --simulator "iPhone 16"
```

**Location Testing:**
```bash
# Set location to San Francisco
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb set-location \
  --simulator "iPhone 16" \
  --latitude 37.7749 \
  --longitude -122.4194

# Simulate walking route from GPX
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb simulate-route \
  --simulator "iPhone 16" \
  --gpx-file route.gpx
```

**Environment Testing:**
```bash
# Enable Dark Mode
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb set-appearance \
  --simulator "iPhone 16" \
  --mode dark

# Test largest accessibility text size
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb set-text-size \
  --simulator "iPhone 16" \
  --size AccessibilityXXXL

# Enable reduce motion
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb toggle-accessibility \
  --simulator "iPhone 16" \
  --feature reduce_motion \
  --enabled true
```

**Quick Actions:**
```bash
# Send push notification
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb send-push \
  --simulator "iPhone 16" \
  --bundle-id com.example.MyApp \
  --payload notification.json

# Open deep link
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb open-url \
  --simulator "iPhone 16" \
  --url "myapp://settings/account"
```

**UserDefaults Testing:**
```bash
# Enable feature flag
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb write-defaults \
  --simulator "iPhone 16" \
  --bundle-id com.example.MyApp \
  --key enableNewFeature \
  --value true \
  --type bool

# Read all preferences
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb read-defaults \
  --simulator "iPhone 16" \
  --bundle-id com.example.MyApp
```

**Status Bar (Perfect Screenshots):**
```bash
# Override for clean screenshots
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb override-status-bar \
  --simulator "iPhone 16" \
  --time "9:41" \
  --battery 100 \
  --wifi 3 \
  --cellular 4
```

### Pulse Network Monitoring Integration

**Setup (One-time per project):**
```bash
# Add Pulse to Xcode project
ruby {{CATALYST_ROOT}}/tools/xcode_project_tool.rb add-framework \
  --project MyApp.xcodeproj \
  --target MyApp \
  --framework Pulse \
  --package-url https://github.com/kean/Pulse \
  --version 5.0.0
```

**Usage in Code (AppDelegate.swift):**
```swift
import Pulse

func application(_ application: UIApplication,
                 didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    #if DEBUG
    // Enable Pulse network logging
    URLSessionProxyDelegate.enableAutomaticRegistration()

    // Optional: Show Pulse console with 3-finger tap
    LoggerStore.shared.makeCurrentConsoleGesture()
    #endif

    return true
}
```

**View Network Logs:**
- 3-finger tap on simulator → Pulse console opens
- Inspect all URLSession requests
- View JSON responses, headers, timing
- Copy cURL commands
- Export logs for analysis

### 🧪 Advanced iOS Testing Framework

**NEW:** Huxley provides three powerful testing tools that integrate with the ios-testing skill:

#### **1. screenshot_diff.py** - Visual Regression Testing

Automated visual regression testing via pixel-level screenshot comparison.

**Capabilities:**
- Pixel-level difference detection with antialiasing tolerance
- Multiple output formats (red highlights, side-by-side, overlay)
- Batch processing for entire screenshot directories
- HTML reports with visual comparisons
- Configurable thresholds (default: 1% difference tolerance)

**Usage:**
```bash
# Single comparison
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py \
  baseline.png current.png -o diff-output/

# Batch mode - compare directories
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py --batch \
  baseline-screenshots/ \
  current-screenshots/ \
  -o results/

# Custom threshold (2% tolerance)
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py \
  baseline.png current.png -t 0.02
```

#### **2. ios_test_matrix.rb** - Test Matrix Automation

Comprehensive test automation across device configuration matrices.

**Capabilities:**
- Automatic test combination generation (appearance × text_size × network × location × accessibility)
- Environment setup/teardown via simulator_control.rb
- Screenshot capture for each configuration
- HTML/JSON reports with pass/fail results
- 4 predefined presets: minimal, accessibility, network, comprehensive

**Usage:**
```bash
# Run minimal tests (6 configurations, ~5 min)
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb run \
  --preset minimal \
  --project MyApp.xcodeproj \
  --scheme MyApp

# Run comprehensive tests (54+ configurations, ~45 min)
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb run \
  --preset comprehensive \
  --project MyApp.xcodeproj \
  --scheme MyApp

# Generate custom config template
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb generate-config \
  --output custom-config.json
```

**Test Matrix Presets:**
- **minimal** - 6 configs (light/dark × 3 text sizes) - Fast validation
- **accessibility** - 40 configs (all accessibility features) - WCAG compliance
- **network** - 8 configs (WiFi/3G/Edge/Offline) - Network resilience
- **comprehensive** - 54 configs (full matrix) - Pre-release validation

#### **3. pulse_log_export.rb** - Network Log Analysis

Extract and analyze network logs from Pulse LoggerStore.

**Capabilities:**
- Export logs in multiple formats (JSON, CSV, text, HTML)
- Advanced filtering (status code, URL pattern, HTTP method, time range)
- Analysis reports (request counts, error rates, performance stats)
- Identify slow requests (>1s) and failures
- Request/response metrics (size, duration, status)

**Usage:**
```bash
# Export all logs
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb export \
  --app-id com.example.MyApp \
  --format json

# Generate analysis report
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb analyze \
  --app-id com.example.MyApp \
  --output network-report.html

# Filter errors only (4xx/5xx)
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb filter \
  --app-id com.example.MyApp \
  --status 400-599 \
  --output errors.json

# List installed apps
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb list-apps
```

#### **One-Command Setup for Any iOS Project**

Use the automated setup script to configure complete testing infrastructure:

```bash
# Setup testing framework
{{CATALYST_ROOT}}/tools/setup_ios_testing.sh \
  MyApp.xcodeproj \
  MyApp \
  com.example.MyApp
```

This creates:
- `testing/` directory with all scripts and configs
- Test matrix presets (minimal, accessibility, network, comprehensive)
- Baseline screenshot capture scripts
- Network analysis tools
- CI/CD workflow templates (GitHub Actions, GitLab, CircleCI, etc.)
- Complete documentation

#### **Integration Workflows**

**Visual Regression Testing:**
1. Capture baseline screenshots
2. Make UI changes
3. Capture current screenshots
4. Run screenshot diff → Visual regression report

**Matrix Testing:**
1. Configure test matrix (or use preset)
2. Run ios_test_matrix.rb
3. Automated environment setup for each configuration
4. Screenshots and reports generated

**Network Analysis:**
1. Integrate Pulse (one-time setup)
2. Run app and make network requests
3. Export logs with pulse_log_export.rb
4. Analyze performance, errors, slow requests

**Complete Pipeline:**
```bash
cd testing
./scripts/run-comprehensive-pipeline.sh
# Runs: matrix tests + visual regression + network analysis
# Generates: unified report with all results
```

**Documentation:** the test-loop runner and helpers live in `tools/ios_testing/`.

## Prerequisites

### Required Setup
```bash
# 1. Xcode must be installed
xcode-select -p

# 2. iOS Simulators must be available
xcrun simctl list devices available

# 3. Xcode project or workspace must exist
# Project: MyApp.xcodeproj
# Workspace: MyApp.xcworkspace (for CocoaPods/SPM)
```

### Project Requirements
- Valid `.xcodeproj` or `.xcworkspace` file
- Configured scheme (usually matches project name)
- iOS deployment target compatible with available simulators

---

## Workflow Modes

### Mode 1: Quick Verification (Dev Loop)

**Use when:** Iterating on iOS code, need immediate visual feedback

**Workflow:**
1. Build app for simulator
2. Launch in simulator with log capture
3. Visual verification (screenshot + UI tree)
4. Check for crashes/errors
5. Clean teardown

**Speed:** ~15-30 seconds per check

### Mode 2: Debug Loop (Agentic Fixing)

**Use when:** App has bugs/crashes that need systematic fixing

**Workflow:**
1. Build and run in simulator
2. Monitor for issues (crashes, UI errors, console errors)
3. If issues detected:
   - Capture diagnostics (logs, screenshots, UI state)
   - Delegate to Mobile Dev agent with full context
   - Agent fixes code
4. Rebuild and retest
5. Repeat until app works correctly

**Speed:** Variable (depends on complexity of fixes)

### Mode 3: Test Suite Execution

**Use when:** Running comprehensive unit/UI tests, pre-deployment validation

**Workflow:**
1. Build app for testing
2. Run test_sim with full test suite
3. Parse test results
4. Handle failures via Debug Loop if needed
5. Generate test report

**Speed:** Variable (based on test suite size)

---

## Quick Verification (Mode 1)

### Step 1: Identify Simulator

```bash
# List available simulators
mcp__xcodebuildmcp__list_sims()
# Returns: List of simulators with UUIDs and states

# Common simulator names:
# - "iPhone 16"
# - "iPhone 16 Pro"
# - "iPad Pro (12.9-inch)"
```

### Step 2: Build and Launch

**Option A: Combined build + run (faster):**
```markdown
mcp__xcodebuildmcp__build_run_sim({
  projectPath: "/path/to/MyApp.xcodeproj",  # or workspacePath for .xcworkspace
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})
```

**Option B: Separate steps (more control):**
```markdown
# 1. Build
mcp__xcodebuildmcp__build_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# 2. Boot simulator (if needed)
mcp__xcodebuildmcp__boot_sim({
  simulatorName: "iPhone 16"
})

# 3. Open Simulator app (make visible)
mcp__xcodebuildmcp__open_sim()

# 4. Install app
mcp__xcodebuildmcp__install_app_sim({
  simulatorName: "iPhone 16",
  appPath: "/path/to/DerivedData/.../MyApp.app"
})

# 5. Launch with logs
mcp__xcodebuildmcp__launch_app_logs_sim({
  simulatorName: "iPhone 16",
  bundleId: "com.example.MyApp"
})
```

### Step 3: Visual Verification

```markdown
# 1. Take screenshot
mcp__xcodebuildmcp__screenshot()
# Saves to: /tmp/simulator-screenshot.png

# 2. Get UI hierarchy
mcp__xcodebuildmcp__describe_ui()
# Returns: Accessibility tree with coordinates for all elements
```

### Step 4: Verify App State

**Quick checks:**
- ✅ Screenshot shows expected UI
- ✅ No crash messages in logs
- ✅ describe_ui shows expected elements
- ✅ App is responsive (not frozen)

### When Quick Verification Fails

If issues detected → Switch to **Mode 2: Debug Loop**

---

## Debug Loop (Mode 2)

### The Agentic Fix Pattern

**Problem Detection:**
```markdown
Issues can be detected from:
1. **Build Failures** - Compilation errors, missing dependencies
2. **Crashes** - App terminates unexpectedly
3. **UI Errors** - Missing elements, wrong layout
4. **Console Errors** - Runtime exceptions, warnings
5. **Test Failures** - Unit or UI tests fail
```

**Automated Fix Flow:**

```
┌─────────────────────────────────────────┐
│  1. BUILD PHASE                         │
│     • build_sim or build_run_sim        │
│     • Capture build logs                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  2. RUN PHASE                           │
│     • boot_sim (if needed)              │
│     • install_app_sim                   │
│     • launch_app_logs_sim               │
│     • open_sim (make visible)           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  3. MONITOR PHASE                       │
│     • screenshot (visual check)         │
│     • describe_ui (UI validation)       │
│     • Analyze logs from launch          │
│     • Detect issues:                    │
│       - Crashes (app terminated)        │
│       - UI errors (missing elements)    │
│       - Console errors (exceptions)     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
            ┌─────────┐
            │ Issues? │
            └────┬────┘
                 │
        ┌────────┴────────┐
        │                 │
       YES                NO
        │                 │
        ▼                 ▼
┌────────────────┐  ┌──────────────┐
│  4. FIX PHASE  │  │  5. VERIFY   │
│  • stop_app    │  │  • test_sim  │
│  • Delegate to │  │  • Final     │
│    Mobile Dev  │  │    checks    │
│    agent with: │  │  • Success!  │
│    - Errors    │  └──────────────┘
│    - Logs      │
│    - Screenshots
│    - UI tree  │
│  • Agent fixes │
│    code        │
└────────┬───────┘
         │
         └─────► Return to BUILD PHASE
```

### Implementation: Debug Loop Execution

**1. Start Debugging Session:**
```bash
# Helper script to track iteration count
echo "0" > /tmp/ios-debug-iteration.txt
```

**2. Build and Run:**
```markdown
# Build for simulator
result = mcp__xcodebuildmcp__build_run_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# Check for build errors
if "BUILD FAILED" in result:
  → Capture build errors
  → Delegate to Mobile Dev with build logs
  → Return to step 2 after fix
```

**3. Monitor for Issues:**
```markdown
# Wait for app to launch (give it time to initialize)
sleep 3

# Capture current state
screenshot_result = mcp__xcodebuildmcp__screenshot()
ui_tree = mcp__xcodebuildmcp__describe_ui()

# Analyze for issues:
# - App crashed? (check if process exists)
# - UI errors? (missing expected elements in ui_tree)
# - Console errors? (check logs from launch_app_logs_sim)
```

**4. Issue Detection Logic:**
```markdown
Issues = []

# Check 1: Build failures
if build_failed:
  Issues.append({
    type: "build_error",
    details: build_logs,
    severity: "critical"
  })

# Check 2: Crashes
if app_not_running:
  Issues.append({
    type: "crash",
    details: crash_logs,
    severity: "critical"
  })

# Check 3: UI errors
expected_elements = ["Login Button", "Username Field", "Password Field"]
for element in expected_elements:
  if element not in ui_tree:
    Issues.append({
      type: "ui_error",
      details: f"Missing {element}",
      severity: "high"
    })

# Check 4: Console errors
if "error" in logs.lower() or "exception" in logs.lower():
  Issues.append({
    type: "console_error",
    details: error_lines,
    severity: "medium"
  })
```

**5. Delegate to Mobile Dev Agent:**
```markdown
if len(Issues) > 0:
  # Increment iteration counter
  iteration = read("/tmp/ios-debug-iteration.txt")
  iteration = int(iteration) + 1
  write("/tmp/ios-debug-iteration.txt", str(iteration))

  # Maximum iterations safety check
  if iteration > 10:
    → Report: "Unable to fix after 10 iterations, manual intervention needed"
    → Exit loop

  # Stop app for clean fix
  mcp__xcodebuildmcp__stop_app_sim({
    simulatorName: "iPhone 16",
    bundleId: "com.example.MyApp"
  })

  # Delegate to Mobile Dev agent using Task tool
  Task({
    subagent_type: "📱 Mobile Dev",
    description: "Fix iOS app issues (iteration {iteration})",
    prompt: f"""
    The iOS app has {len(Issues)} issue(s) that need fixing:

    {format_issues(Issues)}

    **Diagnostics:**
    - Screenshot: {screenshot_path}
    - UI Tree: {ui_tree}
    - Logs: {logs}

    **Project:**
    - Path: /path/to/MyApp.xcodeproj
    - Scheme: MyApp

    Please analyze these issues and fix the code. Focus on:
    1. Root cause of each issue
    2. Minimal changes to resolve
    3. Verification that fix doesn't introduce new issues

    After fixing, I will rebuild and retest automatically.
    """
  })

  # Wait for Mobile Dev to complete
  → Agent makes fixes

  # Return to BUILD PHASE (step 2)
  → Rebuild and retest
```

**6. Success Verification:**
```markdown
if len(Issues) == 0:
  # App is working! Run comprehensive tests if available

  test_result = mcp__xcodebuildmcp__test_sim({
    projectPath: "/path/to/MyApp.xcodeproj",
    scheme: "MyApp",
    simulatorName: "iPhone 16"
  })

  # Final proof-of-work
  final_screenshot = mcp__xcodebuildmcp__screenshot()

  → Report: "✅ iOS app verified working!"
  → Report: f"Fixed in {iteration} iteration(s)"
  → Show final screenshot
```

---

## Test Suite Execution (Mode 3)

### Running Xcode Tests

**Unit Tests + UI Tests:**
```markdown
mcp__xcodebuildmcp__test_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# Returns:
# - Test results (passed/failed)
# - Failure details
# - Test duration
# - xcresult bundle path
```

### Test Result Analysis

**Parse test output for:**
1. **Total tests** - How many ran
2. **Passed tests** - Success count
3. **Failed tests** - Failure count and details
4. **Skipped tests** - Tests not executed

**If tests fail:**
→ Extract failure details
→ Delegate to Mobile Dev agent with:
  - Test name
  - Failure reason
  - Stack trace
  - Expected vs actual
→ Return to Debug Loop

---

## Integration with Xcode Previews

### Swift Previews Support

When available, Xcode Previews provide fastest feedback:

```swift
// In your SwiftUI view file
#Preview {
  ContentView()
}
```

**Preview workflow (when applicable):**
1. Mobile Dev agent makes changes
2. Xcode automatically refreshes preview
3. Visual verification without full rebuild
4. Only run full simulator build for integration testing

**When to use simulator instead of previews:**
- Testing navigation flows
- Testing data persistence
- Testing network calls
- Testing app lifecycle
- Integration testing across multiple screens

---

## Helper Scripts

### build-and-test.sh

```bash
#!/bin/bash
# Quick build and test script for iOS projects

PROJECT_PATH="${1:-MyApp.xcodeproj}"
SCHEME="${2:-MyApp}"
SIMULATOR="${3:-iPhone 16}"

echo "🔨 Building $SCHEME for $SIMULATOR..."

# Build and run
mcp__xcodebuildmcp__build_run_sim "{
  \"projectPath\": \"$PROJECT_PATH\",
  \"scheme\": \"$SCHEME\",
  \"simulatorName\": \"$SIMULATOR\"
}"

# Wait for launch
sleep 3

# Capture state
echo "📸 Capturing screenshot..."
mcp__xcodebuildmcp__screenshot "{}"

echo "🌳 Getting UI tree..."
mcp__xcodebuildmcp__describe_ui "{}"

echo "✅ Verification complete!"
```

### debug-loop.sh

```bash
#!/bin/bash
# Automated debug loop for iOS apps

PROJECT_PATH="${1:-MyApp.xcodeproj}"
SCHEME="${2:-MyApp}"
SIMULATOR="${3:-iPhone 16}"
MAX_ITERATIONS="${4:-10}"

ITERATION=0

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  ITERATION=$((ITERATION + 1))
  echo "🔄 Debug iteration $ITERATION/$MAX_ITERATIONS"

  # Build and run
  # Monitor for issues
  # If issues: delegate to Mobile Dev
  # If no issues: success!

  # (Full implementation would use xcodebuildmcp tools)
done
```

---

## Best Practices

### Issue Detection

**Build Issues:**
```markdown
# Check build output for:
- "error:" lines (compilation errors)
- "BUILD FAILED" (build failure)
- Missing dependencies
- Code signing issues
```

**Runtime Issues:**
```markdown
# Check logs for:
- "Fatal error:" (crashes)
- "Exception:" (runtime exceptions)
- "Warning:" (potential issues)
- "Failed to" (operation failures)
```

**UI Issues:**
```markdown
# Check describe_ui output for:
- Missing expected elements
- Incorrect element hierarchy
- Elements in wrong positions
- Accessibility violations
```

### Mobile Dev Agent Delegation

**Effective delegation includes:**
1. **Clear Issue Description** - What's wrong
2. **Full Context** - Logs, screenshots, UI tree
3. **Reproduction Steps** - How to trigger issue
4. **Expected Behavior** - What should happen
5. **Project Info** - Path, scheme, configuration

**What to avoid:**
- Vague descriptions ("it's broken")
- Missing diagnostics
- No reproduction steps
- Multiple unrelated issues in one delegation

### Iteration Management

**Safety limits:**
```markdown
MAX_ITERATIONS = 10  # Prevent infinite loops

if iteration > MAX_ITERATIONS:
  → Report failure
  → Suggest manual intervention
  → Provide full diagnostic bundle
```

**Optimization:**
```markdown
# Track which types of issues are being fixed
# to detect patterns:

if same_issue_3_times:
  → Different fix approach needed
  → Escalate to senior review
```

---

## Tool Reference

### Build & Run Tools

- `build_sim` - Build app for simulator (by ID or name)
- `build_run_sim` - Build and run in one step
- `boot_sim` - Boot a simulator
- `open_sim` - Open Simulator.app (make visible)
- `install_app_sim` - Install app to simulator
- `launch_app_sim` - Launch app in simulator
- `launch_app_logs_sim` - Launch app with automatic log capture
- `stop_app_sim` - Stop running app

### Monitoring Tools

- `screenshot` - Capture simulator screenshot
- `describe_ui` - Get accessibility tree with element coordinates
- `start_sim_log_cap` - Start log capture session
- `stop_sim_log_cap` - Stop log capture and get logs

### Testing Tools

- `test_sim` - Run unit and UI tests
- `list_sims` - List available simulators
- `get_sim_app_path` - Get path to built .app bundle

---

## Integration with Huxley

### Capsule Quality Gates

```yaml
# capsules/my-ios-app/ops/dod.yaml
testing:
  ios:
    mode: "ios-testing skill with agentic debug loop"
    quick_verify:
      - name: "App launches"
        method: "build_run_sim + screenshot + describe_ui"
        simulator: "iPhone 16"
      - name: "Main screen renders"
        method: "Visual verification via screenshot"

    comprehensive:
      - name: "Debug loop until working"
        method: "Delegate to ios-testing skill in Debug Loop mode"
        max_iterations: 10

      - name: "Test suite execution"
        method: "test_sim with full unit and UI tests"
        tests:
          - "All unit tests pass"
          - "All UI tests pass"
          - "No console errors"
```

### Mobile Dev Agent Integration

**Automatic delegation pattern:**
```markdown
When ios-testing skill detects issues:
1. Skill captures diagnostics
2. Skill delegates to Mobile Dev agent via Task tool
3. Mobile Dev fixes code
4. Skill automatically rebuilds and retests
5. Loop continues until working
```

**Manual intervention triggers:**
```markdown
User can request manual review if:
- Too many iterations (>10)
- Same issue repeatedly
- Complex debugging needed
- Performance optimization required
```

---

## Quick Reference

### Quick Verification
```bash
# 1. List simulators
mcp__xcodebuildmcp__list_sims

# 2. Build and run
mcp__xcodebuildmcp__build_run_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# 3. Visual check
mcp__xcodebuildmcp__screenshot
mcp__xcodebuildmcp__describe_ui

# 4. Done!
```

### Debug Loop
```markdown
1. Build and run
2. Monitor for issues
3. If issues detected:
   - Capture diagnostics
   - Delegate to Mobile Dev
   - Rebuild and retest
4. Repeat until working
```

### Test Suite
```bash
# Run all tests
mcp__xcodebuildmcp__test_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# Analyze results
# If failures → Debug Loop
```

---

## Troubleshooting

### Common Issues

**Simulator not booting:**
```bash
# Check simulator state
mcp__xcodebuildmcp__list_sims

# Boot manually
mcp__xcodebuildmcp__boot_sim({ simulatorName: "iPhone 16" })

# Wait for boot
sleep 10
```

**App not installing:**
```bash
# Verify app path exists
ls -la /path/to/DerivedData/.../MyApp.app

# Get correct path
app_path = mcp__xcodebuildmcp__get_sim_app_path({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})
```

**Build failures:**
```markdown
1. Check build logs for specific errors
2. Verify scheme configuration
3. Check code signing settings
4. Verify deployment target matches simulator
5. Delegate to Mobile Dev with build logs
```

**App crashes immediately:**
```markdown
1. Capture crash logs via launch_app_logs_sim
2. Check for missing dependencies
3. Verify bundle identifier
4. Check Info.plist configuration
5. Delegate to Mobile Dev with crash logs
```

---

## Performance Tips

1. **Use build_run_sim** instead of separate build + run for speed
2. **Keep simulator running** between iterations (don't reboot)
3. **Reuse log capture sessions** instead of starting/stopping
4. **Cache UI tree** if checking multiple elements
5. **Batch screenshot captures** at specific checkpoints

---

## Safety & Limits

- **Max iterations**: 10 (prevents infinite loops)
- **Timeout**: 300s per build (prevents hanging)
- **Log size limit**: 10MB (prevents memory issues)
- **Screenshot limit**: 50 per session (disk space)

---

*This skill provides comprehensive iOS testing with intelligent debugging capabilities, designed for rapid development iteration and systematic issue resolution.*
