# iOS Testing Skill - Quick Reference

Comprehensive iOS app testing and debugging with agentic fix loops.

## Quick Start

### 1. List Available Simulators
```bash
# Via skill invocation ({{ORCHESTRATOR_NAME}} coordinates)
"List iOS simulators"

# Returns simulator names and UUIDs for targeting
```

### 2. Quick Verification (Fast Dev Loop)
```bash
# Build, run, and verify in ~15-30 seconds
"Quick verify MyApp.xcodeproj on iPhone 16"

# Skill will:
# ✅ Build for simulator
# ✅ Launch app with logs
# ✅ Screenshot + UI tree
# ✅ Report any issues
```

### 3. Debug Loop (Automatic Fixing)
```bash
# Automatically fix issues until app works
"Debug MyApp.xcodeproj on iPhone 16 until working"

# Skill will:
# 🔄 Build and run
# 🔍 Detect issues (crashes, UI errors, console errors)
# 🤖 Delegate fixes to Mobile Dev agent
# 🔁 Rebuild and retest automatically
# ✅ Report success when working
```

### 4. Run Test Suite
```bash
# Execute all unit and UI tests
"Run tests for MyApp.xcodeproj on iPhone 16"

# If tests fail → automatic debug loop
```

## Three Modes

| Mode | Use Case | Speed | Agent Involvement |
|------|----------|-------|-------------------|
| **Quick Verification** | Fast smoke test during development | 15-30s | None ({{ORCHESTRATOR_NAME}} only) |
| **Debug Loop** | Fix bugs/crashes automatically | Variable | Mobile Dev (fixes) |
| **Test Suite** | Comprehensive pre-deployment testing | Variable | Mobile Dev (if failures) |

## Common Commands

### Building & Running
```bash
# Combined (fastest)
"Build and run MyApp on iPhone 16"

# Separate steps (more control)
"Build MyApp for iPhone 16"
"Install MyApp on iPhone 16"
"Launch MyApp on iPhone 16"
```

### Monitoring
```bash
# Visual verification
"Take screenshot of iPhone 16"
"Show UI tree for MyApp"

# Log analysis
"Check logs for MyApp on iPhone 16"
```

### Testing
```bash
# Quick check
"Verify MyApp is working on iPhone 16"

# Full test suite
"Run all tests for MyApp"

# Specific test
"Run LoginTests for MyApp"
```

## Project Types

### Xcode Projects (.xcodeproj)
```bash
# Standard single-target projects
"Test /path/to/MyApp.xcodeproj on iPhone 16"
```

### Xcode Workspaces (.xcworkspace)
```bash
# Projects with CocoaPods or SPM dependencies
"Test /path/to/MyApp.xcworkspace on iPhone 16"
```

## Debug Loop Example

```
User: "Debug MyApp.xcodeproj until it works on iPhone 16"

{{ORCHESTRATOR_NAME}} (via ios-testing skill):
🔨 Building MyApp...
✅ Build succeeded

🚀 Launching on iPhone 16...
📸 Screenshot captured
🌳 UI tree analyzed

❌ Issues detected:
  1. Missing "Login Button" in UI
  2. Console error: "Failed to load UserDefaults"

🤖 Delegating to Mobile Dev agent...

Mobile Dev Agent:
📝 Analyzing issues...
🔧 Fixed: Added Login Button to ContentView
🔧 Fixed: Initialized UserDefaults in AppDelegate
✅ Changes complete

{{ORCHESTRATOR_NAME}}:
🔄 Rebuilding and retesting...
🔨 Build succeeded
🚀 Launched successfully
📸 Screenshot verified
🌳 UI tree verified

✅ MyApp is working! Fixed in 1 iteration.
```

## Integration Patterns

### With Mobile Dev Agent
```bash
# Automatic coordination
"Test and fix MyApp until working"
# Skill handles:
# - Issue detection
# - Diagnostic gathering
# - Agent delegation
# - Rebuild/retest loop
```

### With Xcode Previews
```bash
# Use previews for rapid SwiftUI iteration
# Use simulator for integration testing

"Preview changes to LoginView"  # Fast SwiftUI preview
"Test full login flow in simulator"  # Integration test
```

### With CI/CD
```yaml
# In capsule ops/dod.yaml
testing:
  ios:
    quick_verify:
      - "Verify app launches"
    comprehensive:
      - "Run full test suite"
      - "Debug loop if failures"
```

## What Gets Detected

### Build Issues
- Compilation errors
- Missing dependencies
- Code signing problems
- Configuration errors

### Runtime Issues
- App crashes
- Fatal errors
- Exceptions
- Memory warnings

### UI Issues
- Missing UI elements
- Incorrect layouts
- Accessibility violations
- Navigation problems

### Console Issues
- Error messages
- Warning patterns
- Failed operations
- Resource loading failures

## Safety Features

- **Max iterations**: 10 (prevents infinite loops)
- **Build timeout**: 300s (prevents hanging)
- **Log size limit**: 10MB (prevents memory issues)
- **Automatic cleanup**: Stops apps, closes sessions

## Troubleshooting

### Simulator Issues
```bash
# List simulators to verify availability
"List iOS simulators"

# Boot simulator manually if needed
"Boot iPhone 16 simulator"

# Reset simulator if corrupted
xcrun simctl erase "iPhone 16"
```

### Build Issues
```bash
# Clean build folder
"Clean build for MyApp"

# Check scheme configuration
"List schemes for MyApp.xcodeproj"

# Verify build settings
"Show build settings for MyApp"
```

### App Issues
```bash
# Get detailed logs
"Show full logs for MyApp"

# Check app installation
"Get app path for MyApp on iPhone 16"

# Reinstall app
"Reinstall MyApp on iPhone 16"
```

## Performance Tips

1. Keep simulator running between tests
2. Use `build_run_sim` instead of separate steps
3. Cache screenshots/logs when checking multiple times
4. Use Xcode Previews for UI-only changes
5. Run test suite only when needed

## Files Created

```
.claude/skills/ios-testing/
├── SKILL.md           # Complete documentation
├── README.md          # This file - quick reference
└── (scripts coming soon)
```

## Next Steps

1. **Invoke the skill**: "Test MyApp.xcodeproj"
2. **Let it run**: Skill handles build → run → monitor → fix loop
3. **Review results**: Screenshot + logs + fix summary
4. **Iterate**: Skill continues until app works correctly

---

**Key Benefit**: Combines xcodebuildmcp's 59 Xcode tools with Mobile Dev agent's expertise to create a fully automated iOS testing and debugging workflow.

No manual intervention needed - from broken code to working app automatically.
