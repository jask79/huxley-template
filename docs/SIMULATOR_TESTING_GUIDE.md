# iOS Simulator Testing & Enhancement Guide
**Huxley Comprehensive Testing Framework**

## Overview

Huxley provides a powerful two-tier testing system for iOS mobile development:

1. **xcodebuildmcp** - MCP server for Xcode build, run, and test operations
2. **simulator_control.rb** - CLI tool for advanced simulator manipulation and testing scenarios

Together, these tools enable rapid iteration, comprehensive testing, and sophisticated debugging workflows for the Mobile Dev agent.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Mobile Dev Agent / ios-testing Skill                       │
│  (Orchestrates testing workflows)                           │
└──────────────┬─────────────────────────────┬────────────────┘
               │                             │
               │                             │
         ┌─────▼─────────┐           ┌──────▼────────────┐
         │ xcodebuildmcp │           │ simulator_control │
         │  (MCP Server) │           │  (Ruby CLI Tool)  │
         └─────┬─────────┘           └──────┬────────────┘
               │                             │
               │                             │
         ┌─────▼──────────────────────────────▼────────┐
         │           iOS Simulator (simctl)             │
         │  - Build and run apps                        │
         │  - Execute tests                             │
         │  - Capture logs and screenshots              │
         │  - Environment control (network, location)   │
         └──────────────────────────────────────────────┘
```

---

## Tool Comparison

| Capability                  | xcodebuildmcp              | simulator_control.rb         |
|-----------------------------|----------------------------|------------------------------|
| **Build apps**              | ✅ Primary tool             | ❌                            |
| **Run apps on simulator**   | ✅ Primary tool             | ❌                            |
| **Execute tests**           | ✅ Primary tool             | ❌                            |
| **Screenshot capture**      | ✅ Primary tool             | ❌                            |
| **UI tree inspection**      | ✅ Primary tool             | ❌                            |
| **Log streaming**           | ✅ Primary tool             | ❌                            |
| **Network throttling**      | ❌                          | ✅ Primary tool               |
| **Location simulation**     | ❌                          | ✅ Primary tool               |
| **Dark Mode toggle**        | ❌                          | ✅ Primary tool               |
| **Dynamic Type testing**    | ❌                          | ✅ Primary tool               |
| **Push notifications**      | ❌                          | ✅ Primary tool               |
| **Deep link testing**       | ❌                          | ✅ Primary tool               |
| **UserDefaults editing**    | ❌                          | ✅ Primary tool               |
| **Status bar overrides**    | ❌                          | ✅ Primary tool               |
| **Simulator management**    | ✅ Boot, list, basic ops    | ✅ Advanced ops + environment |

**Rule of Thumb:**
- **xcodebuildmcp** → Build, run, test, capture
- **simulator_control.rb** → Manipulate environment, test edge cases

---

## Integration Patterns

### Pattern 1: Build → Test Environment → Verify

**Use Case:** Test app behavior under specific conditions

```bash
# 1. Build and launch (xcodebuildmcp)
mcp__xcodebuildmcp__build_run_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# 2. Set test environment (simulator_control.rb)
ruby tools/simulator_control.rb set-appearance \
  --simulator "iPhone 16" --mode dark

ruby tools/simulator_control.rb network-throttle \
  --simulator "iPhone 16" --profile 3g

# 3. Verify behavior (xcodebuildmcp)
mcp__xcodebuildmcp__screenshot()
mcp__xcodebuildmcp__describe_ui()

# 4. Check logs for issues
mcp__xcodebuildmcp__stop_sim_log_cap({ simulatorName: "iPhone 16" })
```

### Pattern 2: Environment Matrix Testing

**Use Case:** Test app across multiple configurations

```bash
# Test matrix: [Light/Dark] × [S/L/XL] × [WiFi/3G/Offline]

appearances=("light" "dark")
text_sizes=("S" "L" "XL")
networks=("wifi" "3g" "off")

for appearance in "${appearances[@]}"; do
  for size in "${text_sizes[@]}"; do
    for network in "${networks[@]}"; do
      echo "Testing: $appearance, $size, $network"

      # Set environment
      ruby tools/simulator_control.rb set-appearance \
        --simulator "iPhone 16" --mode "$appearance"

      ruby tools/simulator_control.rb set-text-size \
        --simulator "iPhone 16" --size "$size"

      ruby tools/simulator_control.rb network-throttle \
        --simulator "iPhone 16" --profile "$network"

      # Run app and capture
      mcp__xcodebuildmcp__launch_app_logs_sim({
        simulatorName: "iPhone 16",
        bundleId: "com.example.MyApp"
      })

      sleep 3

      mcp__xcodebuildmcp__screenshot()

      # Reset for next iteration
      ruby tools/simulator_control.rb reset-environment \
        --simulator "iPhone 16"

      mcp__xcodebuildmcp__stop_app_sim({
        simulatorName: "iPhone 16",
        bundleId: "com.example.MyApp"
      })
    done
  done
done
```

### Pattern 3: Location-Based Feature Testing

**Use Case:** Test geofencing, maps, or location-dependent features

```bash
# 1. Build and launch
mcp__xcodebuildmcp__build_run_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# 2. Test different locations
locations=(
  "37.7749,-122.4194:San Francisco"
  "40.7128,-74.0060:New York"
  "51.5074,-0.1278:London"
)

for loc in "${locations[@]}"; do
  coords="${loc%%:*}"
  name="${loc##*:}"
  lat="${coords%,*}"
  lon="${coords#*,}"

  echo "Testing location: $name ($lat, $lon)"

  # Set location
  ruby tools/simulator_control.rb set-location \
    --simulator "iPhone 16" \
    --latitude "$lat" \
    --longitude "$lon"

  sleep 2

  # Capture screenshot
  mcp__xcodebuildmcp__screenshot()
  mv /tmp/simulator-screenshot.png "/tmp/location-$name.png"

  # Check UI state
  mcp__xcodebuildmcp__describe_ui()
done

# 3. Reset location
ruby tools/simulator_control.rb reset-location \
  --simulator "iPhone 16"
```

### Pattern 4: Push Notification Testing

**Use Case:** Verify push notification handling and UI

```bash
# 1. Build and launch
mcp__xcodebuildmcp__build_run_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# 2. Create test notification payload
cat > /tmp/test_notification.json << EOF
{
  "aps": {
    "alert": {
      "title": "Test Notification",
      "body": "Testing push notification handling"
    },
    "badge": 1,
    "sound": "default"
  },
  "customData": {
    "action": "openProfile",
    "userId": "12345"
  }
}
EOF

# 3. Send push notification
ruby tools/simulator_control.rb send-push \
  --simulator "iPhone 16" \
  --bundle-id "com.example.MyApp" \
  --payload /tmp/test_notification.json

# 4. Wait for notification to appear
sleep 2

# 5. Capture screenshot showing notification
mcp__xcodebuildmcp__screenshot()

# 6. Check if app handled notification correctly
mcp__xcodebuildmcp__describe_ui()
```

### Pattern 5: Accessibility Compliance Testing

**Use Case:** Ensure app meets accessibility standards

```bash
# 1. Build and launch
mcp__xcodebuildmcp__build_run_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# 2. Test with accessibility features enabled
accessibility_features=(
  "bold_text"
  "reduce_motion"
  "reduce_transparency"
  "increase_contrast"
  "button_shapes"
)

for feature in "${accessibility_features[@]}"; do
  echo "Testing with $feature enabled"

  # Enable feature
  ruby tools/simulator_control.rb toggle-accessibility \
    --simulator "iPhone 16" \
    --feature "$feature" \
    --enabled true

  sleep 1

  # Capture screenshot
  mcp__xcodebuildmcp__screenshot()
  mv /tmp/simulator-screenshot.png "/tmp/accessibility-$feature.png"

  # Check UI tree for accessibility issues
  mcp__xcodebuildmcp__describe_ui() > "/tmp/ui-tree-$feature.txt"

  # Disable feature for next test
  ruby tools/simulator_control.rb toggle-accessibility \
    --simulator "iPhone 16" \
    --feature "$feature" \
    --enabled false
done

# 3. Test all Dynamic Type sizes
text_sizes=("S" "M" "L" "XL" "XXL" "AccessibilityM" "AccessibilityL" "AccessibilityXL")

for size in "${text_sizes[@]}"; do
  echo "Testing with text size: $size"

  ruby tools/simulator_control.rb set-text-size \
    --simulator "iPhone 16" \
    --size "$size"

  sleep 1

  mcp__xcodebuildmcp__screenshot()
  mv /tmp/simulator-screenshot.png "/tmp/text-size-$size.png"
done
```

### Pattern 6: Network Resilience Testing

**Use Case:** Verify app handles network failures gracefully

```bash
# 1. Build and launch
mcp__xcodebuildmcp__build_run_sim({
  projectPath: "/path/to/MyApp.xcodeproj",
  scheme: "MyApp",
  simulatorName: "iPhone 16"
})

# 2. Test network scenarios
echo "=== Scenario 1: Fast WiFi ==="
ruby tools/simulator_control.rb network-throttle \
  --simulator "iPhone 16" --profile wifi
sleep 5
mcp__xcodebuildmcp__screenshot()

echo "=== Scenario 2: 3G Connection ==="
ruby tools/simulator_control.rb network-throttle \
  --simulator "iPhone 16" --profile 3g
sleep 10  # Longer wait for slower connection
mcp__xcodebuildmcp__screenshot()

echo "=== Scenario 3: Offline Mode ==="
ruby tools/simulator_control.rb network-throttle \
  --simulator "iPhone 16" --profile off
sleep 3
mcp__xcodebuildmcp__screenshot()

# 3. Check app UI shows appropriate error states
mcp__xcodebuildmcp__describe_ui()

# 4. Reset network
ruby tools/simulator_control.rb network-reset \
  --simulator "iPhone 16"
```

---

## Mobile Dev Agent Workflows

### Quick Development Iteration

```
1. Code changes in Swift files
2. xcodebuildmcp: build_run_sim → compile and launch
3. Visual check (2-3 seconds)
4. Repeat

No environment changes needed for rapid iteration.
```

### Feature Testing Workflow

```
1. Implement feature
2. xcodebuildmcp: build_run_sim
3. simulator_control: set test environment
4. xcodebuildmcp: screenshot + describe_ui
5. Verify feature works correctly
6. simulator_control: reset_environment
```

### Bug Reproduction Workflow

```
1. Set up specific conditions using simulator_control:
   - Network state
   - Location
   - Dark Mode
   - Text size
   - Accessibility features
2. xcodebuildmcp: build_run_sim
3. Reproduce bug
4. xcodebuildmcp: capture logs, screenshot, UI tree
5. Fix issue
6. Rebuild and verify fix
```

### Pre-Release Testing Workflow

```
1. Run comprehensive test matrix:
   - All appearance modes
   - All text sizes
   - Multiple network conditions
   - Accessibility features
   - Location scenarios
2. Capture screenshots for each scenario
3. Generate test report
4. Fix any issues found
```

---

## ios-testing Skill Integration

The **ios-testing** skill automatically coordinates both tools:

### Quick Verification Mode
```
- xcodebuildmcp: build + run
- xcodebuildmcp: screenshot + UI tree
- Automated pass/fail check
```

### Debug Loop Mode
```
1. xcodebuildmcp: build + run
2. Detect issues (crashes, UI errors, console errors)
3. If issues found:
   - xcodebuildmcp: capture diagnostics
   - Delegate to Mobile Dev agent
   - Mobile Dev fixes code
   - Loop back to step 1
4. Repeat until clean
```

### Enhanced Testing Mode (With Simulator Control)
```
1. Set test environment (simulator_control)
2. Build and run (xcodebuildmcp)
3. Execute test scenarios (simulator_control + xcodebuildmcp)
4. Capture results (xcodebuildmcp)
5. Reset environment (simulator_control)
```

---

## Best Practices

### When to Use Each Tool

**Always use xcodebuildmcp for:**
- Building projects
- Running apps
- Executing tests
- Capturing screenshots
- Inspecting UI elements
- Streaming logs

**Always use simulator_control.rb for:**
- Changing simulator environment
- Testing edge cases
- Simulating user scenarios
- Setting up test conditions
- Taking marketing screenshots

### Efficient Testing Strategy

1. **Develop with xcodebuildmcp only**
   - Fast build-run cycles
   - InjectionIII hot reload (2s)
   - No environment changes needed

2. **Test features with simulator_control**
   - Set up specific scenarios
   - Verify edge cases
   - Test accessibility compliance

3. **Comprehensive testing before release**
   - Automated test matrix
   - All combinations tested
   - Screenshots captured

### Performance Tips

1. **Keep simulator booted** between tests
2. **Reset environment** after scenario testing
3. **Batch environment changes** before launching app
4. **Use JSON output** from simulator_control for parsing
5. **Parallel testing** on multiple simulators (if needed)

---

## Troubleshooting

### xcodebuildmcp issues
- Check `.mcp.json` configuration
- Verify `enableAllProjectMcpServers: true` in settings
- Restart Claude Code session
- Run `claude mcp list` to verify connection

### simulator_control.rb issues
- Ensure simulator is booted first
- Check simulator name matches exactly (case-sensitive)
- Verify Ruby is available: `ruby --version`
- Check tool permissions: `chmod +x tools/simulator_control.rb`

### Integration issues
- Run tools sequentially (xcodebuildmcp first, then simulator_control)
- Allow time for simulator to respond (add `sleep` between commands)
- Reset simulator if behavior is inconsistent
- Check simctl availability: `xcrun simctl list`

---

## Quick Reference

### Common Command Sequences

**Basic test run:**
```bash
# Build and run
xcodebuildmcp: build_run_sim

# Capture state
xcodebuildmcp: screenshot
xcodebuildmcp: describe_ui
```

**Dark Mode test:**
```bash
xcodebuildmcp: build_run_sim
simulator_control: set-appearance --mode dark
xcodebuildmcp: screenshot
simulator_control: reset-environment
```

**Network test:**
```bash
xcodebuildmcp: build_run_sim
simulator_control: network-throttle --profile 3g
# Wait for API calls to complete
xcodebuildmcp: screenshot
simulator_control: network-reset
```

**Location test:**
```bash
xcodebuildmcp: build_run_sim
simulator_control: set-location --latitude 37.7749 --longitude -122.4194
xcodebuildmcp: screenshot
simulator_control: reset-location
```

**Perfect screenshot:**
```bash
simulator_control: override-status-bar --time "9:41" --battery 100
simulator_control: set-appearance --mode light
xcodebuildmcp: build_run_sim
xcodebuildmcp: screenshot
simulator_control: clear-status-bar
```

---

## Summary

**Huxley provides a comprehensive iOS testing framework through the synergy of xcodebuildmcp and simulator_control.rb:**

- **xcodebuildmcp** handles all build, run, and test operations
- **simulator_control.rb** provides environment manipulation and edge case testing
- **Mobile Dev agent** orchestrates both tools for efficient workflows
- **ios-testing skill** automates complex testing scenarios

This two-tier architecture enables rapid development iteration while maintaining comprehensive testing coverage for production-quality iOS applications.
