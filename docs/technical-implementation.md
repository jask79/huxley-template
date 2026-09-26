# Technical Implementation Guide

Complete technical reference for iOS development automation in Huxley.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     iOS Development Loop                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│  │              │   │              │   │              │     │
│  │ UI Designer  │──▶│ Mobile Dev   │──▶│ Backend Dev  │     │
│  │              │   │              │   │              │     │
│  └──────────────┘   └──────────────┘   └──────────────┘     │
│         │                   │                   │            │
│         │                   │                   │            │
│    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐      │
│    │Manifest │         │Manifest │         │Manifest │      │
│    │  .json  │         │  .json  │         │  .json  │      │
│    └─────────┘         └─────────┘         └─────────┘      │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │            Autonomous Validation Loop                  │   │
│  │                                                         │   │
│  │  BUILD → RUN → VALIDATE → DETECT → FIX → (repeat)     │   │
│  │                                                         │   │
│  │  Validation Tools: grid, ruler, color, bezel, recorder│   │
│  │  Testing Tools: simulator_control, screenshot_diff,   │   │
│  │                 test_matrix, pulse_logs                │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. iOS Testing Loop (`tools/ios_testing_loop.rb`)

**Purpose:** Autonomous build-test-fix loop for Mobile Dev agent

**Architecture:**
```
IOSTestingLoop
├── StateManager       # Persistent session state
├── MetricsTracker     # Performance and success metrics
├── CircuitBreaker     # Prevents infinite error loops
├── IssueDetector      # Analyzes build logs and runtime
├── MobileDevDelegator # Formats Task tool delegation
└── DesignValidator    # Auto-runs 5 validation tools
```

**Flow:**
```
1. BUILD (xcodebuild)
2. RUN (simctl launch)
3. MONITOR (screenshot, UI tree)
4. VALIDATE (5 tools automatically)
5. DETECT (issues from logs/tree)
6. FIX (delegate to Mobile Dev agent)
7. REPEAT (until success or max iterations)
```

**Exit Codes:**
- `0` - Success (all tests pass)
- `1` - Failure (unrecoverable error)
- `42` - Delegation needed (Task tool handoff)

**Usage:**
```bash
ruby tools/ios_testing_loop.rb \
  --simulator "iPhone 16" \
  --max-iterations 10 \
  --mode debug \
  /path/to/Project.xcodeproj \
  MyScheme
```

**Modes:**
- `quick` - Single build + run verification
- `debug` - Full autonomous loop with fix iterations
- `test` - Run test suite then switch to debug if failures

---

### 2. Task Delegation System

**Purpose:** Enable Mobile Dev agent to receive diagnostic bundles and fix issues autonomously

**Components:**

#### MobileDevDelegator (`tools/ios_testing/mobile_dev_delegator.rb`)

**Methods:**
- `create_delegation_prompt(issues, diagnostic_bundle, iteration)` → Markdown prompt for agent
- `save_delegation_context(issues, diagnostic_bundle, iteration)` → JSON context file
- `parse_agent_response(response_text)` → Extract success/files/changes

**Delegation Flow:**
```
1. ios_testing_loop.rb detects issues
2. Creates diagnostic bundle:
   ├── build_log.txt
   ├── screenshot.png
   ├── ui_tree.json
   ├── git_diff.patch
   └── issue_summary.json

3. MobileDevDelegator formats prompt
4. Saves delegation context JSON
5. Writes DELEGATION_NEEDED.json signal file
6. Exit with code 42

7. Task delegator (Python) detects exit 42
8. Reads DELEGATION_NEEDED.json
9. Writes TASK_INVOCATION_NEEDED.json
10. Returns to caller (Mobile Dev agent)

11. Mobile Dev agent reads diagnostic bundle
12. Analyzes issues
13. Applies fixes
14. Re-runs ios_testing_loop.rb to verify
```

#### Task Delegator (`.claude/skills/ios-testing/task_delegator.py`)

**Purpose:** Python wrapper that handles exit code 42 and prepares Task tool invocation

**Usage:**
```bash
python .claude/skills/ios-testing/task_delegator.py \
  /path/to/Project.xcodeproj \
  MyScheme \
  --simulator "iPhone 16" \
  --max-iterations 10 \
  --mode debug
```

**Environment Variables:**
- `CLAUDE_CODE_SESSION=1` - Indicates running in agent session
- `AUTOMATED_MODE=1` - Enables delegation signal files

---

### 3. Design Validation System

**Purpose:** Automatically run all 5 validation tools after every simulator run

**Component:** `tools/ios_testing/design_validator.rb`

**Auto-Run Tools:**

1. **Grid Overlay** (`tools/grid_overlay.rb`)
   - Applies 8px grid overlay to screenshot
   - Visual verification of spacing alignment
   - Output: `validation/grid_{timestamp}.png`

2. **Ruler Measurements** (`tools/ruler_tool.rb`)
   - Reads `docs/measurements.json` spec
   - Measures all specified elements
   - Checks 4px/8px grid compliance
   - Output: JSON with measurement results

3. **Color Verification** (`tools/color_picker.rb`)
   - Reads `docs/color_checks.json` spec
   - Verifies colors match design system
   - Delta E color matching (ΔE < 1.0 = exact)
   - WCAG contrast ratio checks
   - Output: JSON with color verification results

4. **Device Bezel** (`tools/device_bezel.rb`)
   - Creates professional screenshot with iPhone 16 Pro bezel
   - Dynamic Island rendering
   - White background + drop shadow
   - Output: `validation/handoff_{timestamp}.png`

5. **Screen Recorder** (`tools/screen_recorder.rb`)
   - Manual tool (not auto-run)
   - Records animations for demos
   - Output: MOV + GIF files

**Validation Specs:**

#### Measurements Spec (`docs/measurements.json`)
```json
{
  "measurements": [
    {
      "label": "Logo top margin",
      "from": "150,50",
      "to": "150,94"
    },
    {
      "label": "Button height",
      "from": "100,300",
      "to": "100,344"
    }
  ]
}
```

#### Color Checks Spec (`docs/color_checks.json`)
```json
{
  "check_points": [
    {
      "label": "Primary button",
      "at": "180,320",
      "expected": "primaryBlue"
    },
    {
      "label": "Background",
      "at": "50,50",
      "expected": "backgroundWhite"
    }
  ]
}
```

**Validation Output:**

```
validation_manifest.json:
{
  "project": "MyApp",
  "validations": [
    {
      "timestamp": "2025-10-27T20:00:00Z",
      "iteration": 1,
      "screenshot": "path/to/screenshot.png",
      "grid_overlay": "validation/grid_20251027_200000.png",
      "device_bezel": "validation/handoff_20251027_200000.png",
      "measurements": [...],
      "colors": [...],
      "status": "success"
    }
  ]
}
```

---

### 4. Handoff Manifest System

**Purpose:** Structured data format for agent-to-agent handoffs

**Specification:** See `/docs/HANDOFF_MANIFEST_SPEC.md`

**Directory Structure:**
```
docs/handoffs/
├── ui-designer/
│   ├── manifest.json          # UI Designer deliverables
│   ├── wireframes/            # Text-based wireframes
│   ├── screenshots/           # SwiftUI Previews
│   └── validation/            # Validation proof-of-work
├── mobile-dev/
│   ├── manifest.json          # Mobile Dev deliverables
│   ├── screenshots/           # Simulator screenshots
│   ├── validation/            # Validation proof-of-work
│   ├── test-reports/          # Test results
│   └── api-contract.json      # Backend API specification
└── backend-dev/
    ├── manifest.json          # Backend Dev deliverables
    └── api-docs/              # API documentation
```

**Manifest Keys:**
- `version` - Manifest format version (1.0.0)
- `agent` - Which agent created this
- `timestamp` - Creation time (ISO 8601)
- `project` - Project context
- `status` - completed | in_progress | blocked
- `deliverables` - What was delivered
- `validation` - Proof-of-work
- `next_agent` - Who receives this
- `handoff_notes` - Human-readable notes

**Example: Mobile Dev reads UI Designer manifest**
```python
import json

# Read UI Designer's deliverables
with open('docs/handoffs/ui-designer/manifest.json') as f:
    ui_manifest = json.load(f)

# Auto-discover SwiftUI Views
for view in ui_manifest['deliverables']['swiftui_views']:
    print(f"Implementing ViewModel for {view['view']}")
    print(f"View file: {view['file']}")
    print(f"Preview: {view['preview_screenshot']}")
```

---

### 5. File Locations (Predictable Paths)

**Source Code:**
```
src/
├── Views/                  # UI Designer creates
│   ├── LoginView.swift
│   └── DashboardView.swift
├── ViewModels/             # Mobile Dev creates
│   ├── LoginViewModel.swift
│   └── DashboardViewModel.swift
├── Services/               # Mobile Dev creates
│   ├── AuthServiceProtocol.swift
│   ├── MockAuthService.swift
│   └── RealAuthService.swift
└── DesignSystem/           # UI Designer creates
    ├── Colors.swift
    ├── Typography.swift
    └── Spacing.swift
```

**Documentation:**
```
docs/
├── handoffs/               # Agent manifests
│   ├── ui-designer/
│   ├── mobile-dev/
│   └── backend-dev/
├── measurements.json       # Ruler tool spec
├── color_checks.json       # Color picker spec
└── HANDOFF_MANIFEST_SPEC.md
```

**Validation Output:**
```
.ios-testing-state/
├── current_session.json    # Current session state
├── iteration_history.json  # All iterations
├── metrics.jsonl           # Performance metrics
├── screenshots/            # Simulator screenshots
├── validation/             # Validation results
│   ├── validation_manifest.json
│   ├── grid_*.png
│   └── handoff_*.png
└── diagnostics/            # Issue bundles
    └── {timestamp}_{issue}/
        ├── build_log.txt
        ├── screenshot.png
        ├── ui_tree.json
        ├── delegation_context.json
        └── DELEGATION_NEEDED.json
```

---

## Integration Examples

### Example 1: Complete Design-First Workflow

**Step 1: UI Designer**
```bash
# 1. Create wireframes (manual)
# 2. Implement SwiftUI Views
# 3. Run Xcode Previews
# 4. Auto-validate with tools

# Validation happens automatically:
ruby tools/grid_overlay.rb capture --simulator "iPhone 16" --grid 8
ruby tools/ruler_tool.rb interactive --file screenshot.png
ruby tools/color_picker.rb verify --at 180,320 --design-system src/Colors.swift
ruby tools/device_bezel.rb frame --file screenshot.png --device "iPhone 16 Pro"

# 5. Generate manifest (create_manifest.rb is not implemented — write the manifest JSON by hand per docs/HANDOFF_MANIFEST_SPEC.md)
ruby tools/create_manifest.rb ui-designer --project .  # (not implemented in this template)

# Result: docs/handoffs/ui-designer/manifest.json
```

**Step 2: Mobile Dev**
```bash
# 1. Read UI Designer manifest
ui_manifest=$(cat docs/handoffs/ui-designer/manifest.json)

# 2. Implement ViewModels + Mock Services
# 3. Define API Contract
# 4. Run autonomous testing loop

python .claude/skills/ios-testing/task_delegator.py \
  MyApp.xcodeproj \
  MyApp \
  --simulator "iPhone 16" \
  --max-iterations 10 \
  --mode debug

# Loop auto-runs:
# - Build
# - Run in simulator
# - Design validation (5 tools)
# - Issue detection
# - Fix delegation (if needed)

# 5. Generate manifest (create_manifest.rb is not implemented — write the manifest JSON by hand per docs/HANDOFF_MANIFEST_SPEC.md)
ruby tools/create_manifest.rb mobile-dev \
  --project . \
  --input-manifest docs/handoffs/ui-designer/manifest.json

# Result: docs/handoffs/mobile-dev/manifest.json
```

**Step 3: Backend Dev**
```bash
# 1. Read Mobile Dev manifest
mobile_manifest=$(cat docs/handoffs/mobile-dev/manifest.json)

# 2. Read API Contract
api_contract=$(cat docs/handoffs/mobile-dev/api-contract.json)

# 3. Implement endpoints matching contract EXACTLY
# 4. Deploy to staging
# 5. Generate manifest (create_manifest.rb is not implemented — write the manifest JSON by hand per docs/HANDOFF_MANIFEST_SPEC.md)

ruby tools/create_manifest.rb backend-dev \
  --project . \
  --input-manifest docs/handoffs/mobile-dev/manifest.json

# Result: docs/handoffs/backend-dev/manifest.json
```

**Step 4: Mobile Dev (Final Integration)**
```bash
# 1. Read Backend Dev manifest
backend_manifest=$(cat docs/handoffs/backend-dev/manifest.json)

# 2. Swap MockAuthService → RealAuthService (1-line change)
# 3. Update Config.swift with staging URL
# 4. Re-run testing loop to verify integration

python .claude/skills/ios-testing/task_delegator.py \
  MyApp.xcodeproj \
  MyApp \
  --simulator "iPhone 16" \
  --max-iterations 10 \
  --mode test

# All tests pass → Ready for TestFlight
```

---

### Example 2: Autonomous Fix Loop

**Scenario:** Build fails with missing import

```
Iteration 1:
  BUILD → ❌ Error: No such module 'Alamofire'
  CREATE diagnostic bundle
  DELEGATE to Mobile Dev agent
  EXIT code 42

Task Delegator detects exit 42:
  READ DELEGATION_NEEDED.json
  CREATE TASK_INVOCATION_NEEDED.json
  RETURN to Mobile Dev agent

Mobile Dev agent:
  READ diagnostic bundle
  ANALYZE: Missing Alamofire dependency
  FIX: Add Alamofire to Package.swift
  RE-RUN ios_testing_loop.rb

Iteration 2:
  BUILD → ✅ Success
  RUN → ✅ App launches
  VALIDATE → ✅ Design checks pass
  COMPLETE → Success!
```

---

### Example 3: Design Validation Auto-Integration

**Every simulator run automatically:**

```
1. Capture screenshot
   → .ios-testing-state/screenshots/screenshot_20251027_200000.png

2. Run grid overlay
   → .ios-testing-state/validation/grid_20251027_200000.png
   → Visual check: spacing aligned to 8px grid

3. Run ruler measurements (if spec exists)
   → Read docs/measurements.json
   → Measure all specified elements
   → Check grid compliance

4. Run color verification (if spec exists)
   → Read docs/color_checks.json
   → Verify all colors match design system
   → Check WCAG contrast ratios

5. Run device bezel
   → .ios-testing-state/validation/handoff_20251027_200000.png
   → Professional screenshot for client handoff

6. Update validation manifest
   → .ios-testing-state/validation/validation_manifest.json
   → Append latest validation results

Result: Complete validation proof-of-work with zero manual effort
```

---

## Command Reference

### iOS Testing Loop

```bash
# Quick verification (1 iteration)
ruby tools/ios_testing_loop.rb --mode quick Project.xcodeproj Scheme

# Debug loop (autonomous fix iterations)
ruby tools/ios_testing_loop.rb --mode debug --max-iterations 10 Project.xcodeproj Scheme

# Test suite + debug on failures
ruby tools/ios_testing_loop.rb --mode test Project.xcodeproj Scheme

# With custom simulator
ruby tools/ios_testing_loop.rb --simulator "iPhone 16 Pro Max" Project.xcodeproj Scheme
```

### Design Validation Tools

```bash
# Grid overlay
ruby tools/grid_overlay.rb capture --simulator "iPhone 16" --grid 8 --output grid.png

# Measurements
ruby tools/ruler_tool.rb measure --file screenshot.png --from 100,200 --to 100,244

# Interactive measurements
ruby tools/ruler_tool.rb interactive --file screenshot.png

# Color verification
ruby tools/color_picker.rb verify --file screenshot.png --at 180,320 --design-system src/Colors.swift

# Contrast check
ruby tools/color_picker.rb pick --at 180,320 --background "#FFFFFF"

# Device bezel
ruby tools/device_bezel.rb frame --file screenshot.png --device "iPhone 16 Pro" --shadow

# Screen recording
ruby tools/screen_recorder.rb record --duration 10 --gif --output demo.mov
```

### Manifest Tools

```bash
# Create manifest
ruby tools/create_manifest.rb ui-designer --project /path/to/project  # (not implemented in this template)
ruby tools/create_manifest.rb mobile-dev --project /path/to/project --input-manifest docs/handoffs/ui-designer/manifest.json  # (not implemented in this template)

# Validate manifest
ruby tools/validate_manifest.rb docs/handoffs/ui-designer/manifest.json  # (not implemented in this template)
```

---

## Troubleshooting

### Issue: Loop exits with code 42 but no Task invocation

**Cause:** Not running in CLAUDE_CODE_SESSION environment

**Solution:**
```bash
# Set environment variable
export CLAUDE_CODE_SESSION=1
export AUTOMATED_MODE=1

# Or use Python wrapper
python .claude/skills/ios-testing/task_delegator.py Project.xcodeproj Scheme
```

### Issue: Design validation tools not finding spec files

**Cause:** Missing `docs/measurements.json` or `docs/color_checks.json`

**Solution:**
```bash
# Create measurement spec
cat > docs/measurements.json <<EOF
{
  "measurements": [
    {
      "label": "Button height",
      "from": "100,300",
      "to": "100,344"
    }
  ]
}
EOF

# Create color check spec
cat > docs/color_checks.json <<EOF
{
  "check_points": [
    {
      "label": "Primary button",
      "at": "180,320",
      "expected": "primaryBlue"
    }
  ]
}
EOF
```

### Issue: Circuit breaker triggered (same error 3 times)

**Cause:** Fix not working, error repeating

**Solution:**
1. Review diagnostic bundles in `.ios-testing-state/diagnostics/`
2. Manual intervention required
3. Fix issue manually
4. Clear session: `rm .ios-testing-state/current_session.json`
5. Re-run loop

---

## Performance

### Typical Iteration Times

- **Build:** 30-90s (clean), 5-15s (incremental)
- **Launch:** 2-5s (simulator boot + app launch)
- **Validation:** 5-10s (all 5 tools)
- **Total per iteration:** ~45-120s

### Optimization Tips

1. **Use incremental builds** - Don't clean unless necessary
2. **Keep simulator booted** - Saves 10-15s per iteration
3. **Limit validation tools** - Comment out unused tools in design_validator.rb
4. **Reduce max iterations** - Start with 5 iterations

---

## Related Documentation

- [Design Validation Tools](/docs/DESIGN_VALIDATION_TOOLS.md)
- [Handoff Manifest Spec](/docs/HANDOFF_MANIFEST_SPEC.md)
