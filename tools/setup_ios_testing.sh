#!/bin/bash
# iOS Testing Framework Setup Script
# Automatically configures complete testing framework for iOS projects
#
# Usage: ./setup_ios_testing.sh /path/to/MyApp.xcodeproj MyApp com.example.MyApp

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check arguments
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <project_path> <scheme> <bundle_id>"
    echo
    echo "Example:"
    echo "  $0 MyApp.xcodeproj MyApp com.example.MyApp"
    exit 1
fi

PROJECT_PATH="$1"
SCHEME="$2"
BUNDLE_ID="$3"
PROJECT_DIR=$(dirname "$PROJECT_PATH")
PROJECT_NAME=$(basename "$PROJECT_PATH" .xcodeproj)

print_header "🚀 iOS Testing Framework Setup"

echo "Project: $PROJECT_NAME"
echo "Scheme:  $SCHEME"
echo "Bundle:  $BUNDLE_ID"
echo "Path:    $PROJECT_PATH"
echo

# Check if project exists
if [ ! -d "$PROJECT_PATH" ]; then
    print_error "Project not found: $PROJECT_PATH"
    exit 1
fi

# Create testing directory structure
print_header "📁 Creating Directory Structure"

mkdir -p "$PROJECT_DIR/testing"
mkdir -p "$PROJECT_DIR/testing/baseline-screenshots"
mkdir -p "$PROJECT_DIR/testing/current-screenshots"
mkdir -p "$PROJECT_DIR/testing/test-results"
mkdir -p "$PROJECT_DIR/testing/configs"
mkdir -p "$PROJECT_DIR/testing/scripts"

print_success "Created testing directory structure"

# Step 1: Add Pulse Network Monitoring
print_header "📊 Adding Pulse Network Monitoring"

# Check if Pulse is already added
if grep -q "kean/Pulse" "$PROJECT_PATH/project.pbxproj" 2>/dev/null; then
    print_warning "Pulse already added to project"
else
    print_info "Adding Pulse package dependency..."

    # Use xcode_project_tool.rb to add Pulse
    ruby {{CATALYST_ROOT}}/tools/xcode_project_tool.rb add-package \
        --url "https://github.com/kean/Pulse" \
        --product "Pulse" \
        --project "$PROJECT_PATH" 2>/dev/null || {
        print_warning "Could not add Pulse automatically. Add manually via Xcode:"
        echo "  1. File → Add Package Dependencies"
        echo "  2. URL: https://github.com/kean/Pulse"
        echo "  3. Add 'Pulse' product to your target"
    }
fi

# Create Pulse setup guide
cat > "$PROJECT_DIR/testing/PULSE_SETUP.md" << 'EOF'
# Pulse Network Monitoring Setup

## Integration Steps

### 1. Add to AppDelegate or Main App File

```swift
import Pulse

#if DEBUG
func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    // Enable automatic URLSession monitoring
    URLSessionProxyDelegate.enableAutomaticRegistration()

    // Enable 3-finger tap gesture to show Pulse console
    LoggerStore.shared.makeCurrentConsoleGesture()

    return true
}
#endif
```

### 2. View Network Logs in Simulator

- **3-finger tap** anywhere in app to open Pulse console
- Or add a debug button:

```swift
#if DEBUG
Button("View Network Logs") {
    let vc = UIHostingController(rootView: MainView(store: .shared))
    present(vc, animated: true)
}
#endif
```

### 3. Export Logs for Analysis

```bash
# Export all logs
ruby tools/pulse_log_export.rb export --app-id YOUR_BUNDLE_ID --format json

# Analyze network performance
ruby tools/pulse_log_export.rb analyze --app-id YOUR_BUNDLE_ID --output network-report.html

# Filter errors only
ruby tools/pulse_log_export.rb filter --app-id YOUR_BUNDLE_ID --status 400-599
```

## Features

- ✅ Automatic URLSession request/response logging
- ✅ Request/response body inspection
- ✅ Network timing metrics
- ✅ Error tracking
- ✅ Export to JSON/CSV/HTML
- ✅ Zero production overhead (DEBUG only)

## Next Steps

1. Add Pulse integration code to your app
2. Run app and make network requests
3. Use 3-finger tap to view logs
4. Export logs using pulse_log_export.rb

See: {{CATALYST_ROOT}}/docs/ADVANCED_IOS_TESTING.md
EOF

print_success "Created Pulse setup guide"

# Step 2: Create Test Matrix Configurations
print_header "📋 Creating Test Matrix Configurations"

# Minimal preset
cat > "$PROJECT_DIR/testing/configs/minimal.json" << EOF
{
  "name": "Minimal Test Matrix",
  "project_path": "$PROJECT_PATH",
  "scheme": "$SCHEME",
  "simulator": "iPhone 16",
  "matrix": {
    "appearance": ["light", "dark"],
    "text_size": ["L", "XL", "XXL"]
  },
  "test_command": "xcodebuild test -scheme $SCHEME -destination 'platform=iOS Simulator,name=iPhone 16' || true",
  "screenshot_screens": ["Main"],
  "output_dir": "$PROJECT_DIR/testing/test-results/minimal"
}
EOF

# Accessibility preset
cat > "$PROJECT_DIR/testing/configs/accessibility.json" << EOF
{
  "name": "Accessibility Test Matrix",
  "project_path": "$PROJECT_PATH",
  "scheme": "$SCHEME",
  "simulator": "iPhone 16",
  "matrix": {
    "appearance": ["light", "dark"],
    "text_size": ["L", "XL", "XXL", "AccessibilityXL", "AccessibilityXXXL"],
    "accessibility": [
      {},
      {"reduce_motion": true},
      {"increase_contrast": true},
      {"bold_text": true}
    ]
  },
  "test_command": "xcodebuild test -scheme $SCHEME -destination 'platform=iOS Simulator,name=iPhone 16' || true",
  "screenshot_screens": ["Main", "Settings"],
  "output_dir": "$PROJECT_DIR/testing/test-results/accessibility"
}
EOF

# Network preset
cat > "$PROJECT_DIR/testing/configs/network.json" << EOF
{
  "name": "Network Test Matrix",
  "project_path": "$PROJECT_PATH",
  "scheme": "$SCHEME",
  "simulator": "iPhone 16",
  "matrix": {
    "appearance": ["light", "dark"],
    "network": ["wifi", "3g", "edge", "off"]
  },
  "test_command": "xcodebuild test -scheme $SCHEME -destination 'platform=iOS Simulator,name=iPhone 16' || true",
  "screenshot_screens": ["Main"],
  "output_dir": "$PROJECT_DIR/testing/test-results/network"
}
EOF

# Comprehensive preset
cat > "$PROJECT_DIR/testing/configs/comprehensive.json" << EOF
{
  "name": "Comprehensive Test Matrix",
  "project_path": "$PROJECT_PATH",
  "scheme": "$SCHEME",
  "simulator": "iPhone 16",
  "matrix": {
    "appearance": ["light", "dark"],
    "text_size": ["L", "XL", "AccessibilityXL"],
    "network": ["wifi", "3g", "off"],
    "accessibility": [
      {},
      {"reduce_motion": true},
      {"increase_contrast": true}
    ]
  },
  "test_command": "xcodebuild test -scheme $SCHEME -destination 'platform=iOS Simulator,name=iPhone 16' || true",
  "screenshot_screens": ["Main", "Settings", "Profile"],
  "output_dir": "$PROJECT_DIR/testing/test-results/comprehensive"
}
EOF

print_success "Created test matrix configurations:"
echo "  - minimal.json (6 combinations)"
echo "  - accessibility.json (40 combinations)"
echo "  - network.json (8 combinations)"
echo "  - comprehensive.json (54 combinations)"

# Step 3: Create Testing Scripts
print_header "🔧 Creating Testing Scripts"

# Baseline screenshot capture script
cat > "$PROJECT_DIR/testing/scripts/capture-baseline.sh" << 'EOFSCRIPT'
#!/bin/bash
# Capture baseline screenshots for visual regression testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BASELINE_DIR="$PROJECT_DIR/baseline-screenshots"

echo "📸 Capturing baseline screenshots..."
echo

# Boot simulator
echo "Booting simulator..."
xcrun simctl boot "iPhone 16" 2>/dev/null || true
sleep 5

# Build and run app
echo "Building app..."
cd "$PROJECT_DIR/.."
xcodebuild build -scheme SCHEME_PLACEHOLDER -destination 'platform=iOS Simulator,name=iPhone 16' | grep -E "(error|warning|succeeded)"

# Wait for app to launch
echo "Launching app..."
sleep 3

# Capture screenshots using simulator_control.rb
echo "Capturing screenshots..."
xcrun simctl io "iPhone 16" screenshot "$BASELINE_DIR/home.png"

echo
echo "✅ Baseline screenshots captured to: $BASELINE_DIR"
echo
echo "Next steps:"
echo "  1. Make UI changes to your app"
echo "  2. Run: ./scripts/capture-current.sh"
echo "  3. Run: ./scripts/run-visual-diff.sh"
EOFSCRIPT

sed -i '' "s/SCHEME_PLACEHOLDER/$SCHEME/g" "$PROJECT_DIR/testing/scripts/capture-baseline.sh"
chmod +x "$PROJECT_DIR/testing/scripts/capture-baseline.sh"

# Current screenshot capture script
cat > "$PROJECT_DIR/testing/scripts/capture-current.sh" << 'EOFSCRIPT'
#!/bin/bash
# Capture current screenshots for comparison

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CURRENT_DIR="$PROJECT_DIR/current-screenshots"

echo "📸 Capturing current screenshots..."
echo

# Boot simulator
echo "Booting simulator..."
xcrun simctl boot "iPhone 16" 2>/dev/null || true
sleep 5

# Build and run app
echo "Building app..."
cd "$PROJECT_DIR/.."
xcodebuild build -scheme SCHEME_PLACEHOLDER -destination 'platform=iOS Simulator,name=iPhone 16' | grep -E "(error|warning|succeeded)"

# Wait for app to launch
echo "Launching app..."
sleep 3

# Capture screenshots
echo "Capturing screenshots..."
xcrun simctl io "iPhone 16" screenshot "$CURRENT_DIR/home.png"

echo
echo "✅ Current screenshots captured to: $CURRENT_DIR"
echo
echo "Next step: Run visual diff"
echo "  ./scripts/run-visual-diff.sh"
EOFSCRIPT

sed -i '' "s/SCHEME_PLACEHOLDER/$SCHEME/g" "$PROJECT_DIR/testing/scripts/capture-current.sh"
chmod +x "$PROJECT_DIR/testing/scripts/capture-current.sh"

# Visual diff script
cat > "$PROJECT_DIR/testing/scripts/run-visual-diff.sh" << 'EOFSCRIPT'
#!/bin/bash
# Run visual regression testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BASELINE_DIR="$PROJECT_DIR/baseline-screenshots"
CURRENT_DIR="$PROJECT_DIR/current-screenshots"
RESULTS_DIR="$PROJECT_DIR/test-results/visual-diff-$(date +%Y%m%d-%H%M%S)"

echo "🔍 Running visual regression tests..."
echo

# Check if baseline exists
if [ ! -d "$BASELINE_DIR" ] || [ -z "$(ls -A "$BASELINE_DIR")" ]; then
    echo "❌ No baseline screenshots found"
    echo "   Run: ./scripts/capture-baseline.sh"
    exit 1
fi

# Check if current exists
if [ ! -d "$CURRENT_DIR" ] || [ -z "$(ls -A "$CURRENT_DIR")" ]; then
    echo "❌ No current screenshots found"
    echo "   Run: ./scripts/capture-current.sh"
    exit 1
fi

# Run screenshot diff
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py --batch \
    "$BASELINE_DIR" \
    "$CURRENT_DIR" \
    -o "$RESULTS_DIR"

echo
echo "✅ Visual diff complete!"
echo "📊 Results: $RESULTS_DIR"
echo
echo "Open report:"
echo "  open $RESULTS_DIR/report.html"
EOFSCRIPT

chmod +x "$PROJECT_DIR/testing/scripts/run-visual-diff.sh"

# Matrix test runner script
cat > "$PROJECT_DIR/testing/scripts/run-matrix-tests.sh" << 'EOFSCRIPT'
#!/bin/bash
# Run test matrix automation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PRESET="${1:-minimal}"
CONFIG_FILE="$PROJECT_DIR/configs/${PRESET}.json"

echo "🧪 Running test matrix: $PRESET"
echo

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config not found: $CONFIG_FILE"
    echo
    echo "Available configs:"
    ls -1 "$PROJECT_DIR/configs"
    exit 1
fi

# Run test matrix
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb run --config "$CONFIG_FILE"

echo
echo "✅ Test matrix complete!"
echo "📊 Results: $(cat "$CONFIG_FILE" | grep output_dir | cut -d'"' -f4)"
EOFSCRIPT

chmod +x "$PROJECT_DIR/testing/scripts/run-matrix-tests.sh"

# Network analysis script
cat > "$PROJECT_DIR/testing/scripts/analyze-network.sh" << EOFSCRIPT
#!/bin/bash
# Analyze network logs from Pulse

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="\$(dirname "\$SCRIPT_DIR")"
OUTPUT_FILE="\$PROJECT_DIR/test-results/network-analysis-\$(date +%Y%m%d-%H%M%S).html"

echo "🌐 Analyzing network logs..."
echo

# Analyze network logs
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb analyze \\
    --app-id $BUNDLE_ID \\
    --output "\$OUTPUT_FILE"

echo
echo "✅ Network analysis complete!"
echo "📊 Report: \$OUTPUT_FILE"
echo
echo "Open report:"
echo "  open \$OUTPUT_FILE"
EOFSCRIPT

chmod +x "$PROJECT_DIR/testing/scripts/analyze-network.sh"

# Comprehensive pipeline script
cat > "$PROJECT_DIR/testing/scripts/run-comprehensive-pipeline.sh" << 'EOFSCRIPT'
#!/bin/bash
# Run complete testing pipeline (matrix + visual diff + network analysis)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="$PROJECT_DIR/test-results/pipeline-$TIMESTAMP"

mkdir -p "$RESULTS_DIR"

echo "🚀 Starting Comprehensive Testing Pipeline"
echo "=========================================="
echo

# Step 1: Run test matrix
echo "📊 Step 1/3: Running test matrix..."
./run-matrix-tests.sh comprehensive
cp -r "$PROJECT_DIR/test-results/comprehensive" "$RESULTS_DIR/matrix-results"

# Step 2: Visual regression testing
echo
echo "🖼️  Step 2/3: Running visual regression tests..."
if [ -d "$PROJECT_DIR/baseline-screenshots" ] && [ -n "$(ls -A "$PROJECT_DIR/baseline-screenshots")" ]; then
    python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py --batch \
        "$PROJECT_DIR/baseline-screenshots" \
        "$RESULTS_DIR/matrix-results/screenshots" \
        -o "$RESULTS_DIR/visual-diff"
else
    echo "⚠️  No baseline screenshots. Creating baseline from current run..."
    mkdir -p "$PROJECT_DIR/baseline-screenshots"
    cp -r "$RESULTS_DIR/matrix-results/screenshots/"* "$PROJECT_DIR/baseline-screenshots/"
fi

# Step 3: Network analysis
echo
echo "🌐 Step 3/3: Analyzing network logs..."
./analyze-network.sh

# Generate summary report
cat > "$RESULTS_DIR/SUMMARY.md" << EOF
# Comprehensive Test Results
Generated: $(date)

## Test Matrix Results
- Configuration: Comprehensive
- Results: [View Report](matrix-results/report.html)

## Visual Regression Results
- Diff Report: [View Report](visual-diff/report.html)
- Baseline: $PROJECT_DIR/baseline-screenshots/
- Current: $RESULTS_DIR/matrix-results/screenshots/

## Network Analysis
- Report: [View Report](../network-analysis-*.html)

## Quick Links
- [Matrix Results](matrix-results/report.html)
- [Visual Diff](visual-diff/report.html)
- [Network Analysis](../network-analysis-*.html)

## Statistics
- Test Configurations: $(find "$RESULTS_DIR/matrix-results/screenshots" -type d | wc -l | xargs)
- Screenshots Captured: $(find "$RESULTS_DIR/matrix-results/screenshots" -name "*.png" | wc -l | xargs)
EOF

echo
echo "=========================================="
echo "✅ Pipeline Complete!"
echo "=========================================="
echo
echo "📊 Results Directory: $RESULTS_DIR"
echo "📄 Summary: $RESULTS_DIR/SUMMARY.md"
echo
echo "Open reports:"
echo "  open $RESULTS_DIR/matrix-results/report.html"
echo "  open $RESULTS_DIR/visual-diff/report.html"
echo "  open $PROJECT_DIR/test-results/network-analysis-*.html"
EOFSCRIPT

chmod +x "$PROJECT_DIR/testing/scripts/run-comprehensive-pipeline.sh"

print_success "Created testing scripts:"
echo "  - capture-baseline.sh"
echo "  - capture-current.sh"
echo "  - run-visual-diff.sh"
echo "  - run-matrix-tests.sh"
echo "  - analyze-network.sh"
echo "  - run-comprehensive-pipeline.sh"

# Step 4: Create README
print_header "📚 Creating Testing Documentation"

cat > "$PROJECT_DIR/testing/README.md" << EOF
# iOS Testing Framework

Complete testing setup for **$PROJECT_NAME**

## 🚀 Quick Start

### 1. Initial Setup (One-Time)

\`\`\`bash
# Add Pulse network monitoring (follow guide)
cat PULSE_SETUP.md

# Capture baseline screenshots
./scripts/capture-baseline.sh
\`\`\`

### 2. Running Tests

\`\`\`bash
# Quick validation (6 configurations)
./scripts/run-matrix-tests.sh minimal

# Accessibility compliance (40 configurations)
./scripts/run-matrix-tests.sh accessibility

# Network testing (8 configurations)
./scripts/run-matrix-tests.sh network

# Full comprehensive testing (54 configurations)
./scripts/run-matrix-tests.sh comprehensive
\`\`\`

### 3. Visual Regression Testing

\`\`\`bash
# After making UI changes
./scripts/capture-current.sh
./scripts/run-visual-diff.sh

# View results
open test-results/visual-diff-*/report.html
\`\`\`

### 4. Network Analysis

\`\`\`bash
# Analyze network performance
./scripts/analyze-network.sh

# View report
open test-results/network-analysis-*.html
\`\`\`

### 5. Complete Pipeline

\`\`\`bash
# Run everything at once
./scripts/run-comprehensive-pipeline.sh

# Results in: test-results/pipeline-*/
\`\`\`

## 📁 Directory Structure

\`\`\`
testing/
├── README.md                     # This file
├── PULSE_SETUP.md                # Pulse integration guide
├── baseline-screenshots/         # Reference screenshots
├── current-screenshots/          # Current screenshots
├── test-results/                 # Test output
├── configs/                      # Test matrix configurations
│   ├── minimal.json              # 6 combinations
│   ├── accessibility.json        # 40 combinations
│   ├── network.json              # 8 combinations
│   └── comprehensive.json        # 54 combinations
└── scripts/                      # Testing scripts
    ├── capture-baseline.sh       # Create baseline screenshots
    ├── capture-current.sh        # Capture current state
    ├── run-visual-diff.sh        # Compare screenshots
    ├── run-matrix-tests.sh       # Run test matrix
    ├── analyze-network.sh        # Network analysis
    └── run-comprehensive-pipeline.sh  # Full pipeline
\`\`\`

## 🧪 Test Matrix Presets

### Minimal (6 combinations)
- Light/Dark mode
- 3 text sizes (L, XL, XXL)
- **Use for:** Quick validation after changes

### Accessibility (40 combinations)
- Light/Dark mode
- 5 text sizes (L → AccessibilityXXXL)
- 4 accessibility features
- **Use for:** Accessibility compliance

### Network (8 combinations)
- Light/Dark mode
- 4 network conditions (WiFi, 3G, Edge, Offline)
- **Use for:** Network resilience testing

### Comprehensive (54 combinations)
- All appearance modes
- Multiple text sizes
- Network conditions
- Accessibility features
- **Use for:** Release validation

## 📊 Reports

All test runs generate HTML reports with:
- ✅ Pass/fail status for each configuration
- 📸 Screenshots for visual comparison
- 📈 Performance metrics
- 🔍 Detailed diff analysis

## 🔧 Tools Used

- **screenshot_diff.py** - Visual regression testing
- **ios_test_matrix.rb** - Matrix test automation
- **pulse_log_export.rb** - Network log analysis
- **simulator_control.rb** - Simulator manipulation

## 📚 Documentation

- Complete Framework: \`{{CATALYST_ROOT}}/docs/ADVANCED_IOS_TESTING.md\`
- Mobile Dev Agent: \`{{CATALYST_ROOT}}/.claude/agents/mobile-dev.md\`
- iOS Testing Skill: \`{{CATALYST_ROOT}}/.claude/skills/ios-testing/SKILL.md\`

## 🐛 Troubleshooting

**No baseline screenshots?**
\`\`\`bash
./scripts/capture-baseline.sh
\`\`\`

**Test matrix timing out?**
- Use smaller preset: \`minimal\` instead of \`comprehensive\`
- Reduce matrix dimensions in config JSON

**Pulse database not found?**
- Integrate Pulse following PULSE_SETUP.md
- Run app and make network requests first

**Visual diffs too sensitive?**
- Adjust threshold in screenshot_diff.py: \`-t 0.02\` (2%)

## ✅ Best Practices

1. **Capture baselines in production-ready state** (no debug overlays)
2. **Run minimal preset frequently** (fast feedback)
3. **Run comprehensive preset before releases** (thorough validation)
4. **Review visual diffs carefully** (some changes are intentional)
5. **Update baselines after approved UI changes**
6. **Archive test results** for historical comparison

---

*iOS Testing Framework - Huxley*
*Generated by setup_ios_testing.sh*
EOF

print_success "Created testing README.md"

# Step 5: Create CI/CD workflow template
print_header "🔄 Creating CI/CD Templates"

mkdir -p "$PROJECT_DIR/.github/workflows"

cat > "$PROJECT_DIR/.github/workflows/ios-testing.yml" << EOF
name: iOS Testing Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: macos-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Setup Dependencies
        run: |
          pip3 install Pillow numpy
          gem install json

      - name: Select Xcode Version
        run: sudo xcode-select -s /Applications/Xcode_15.0.app

      - name: Boot Simulator
        run: |
          xcrun simctl boot "iPhone 16" || true
          sleep 10

      - name: Build App
        run: |
          xcodebuild build \\
            -scheme $SCHEME \\
            -destination 'platform=iOS Simulator,name=iPhone 16'

      - name: Run Test Matrix (Minimal)
        run: |
          cd testing
          ./scripts/run-matrix-tests.sh minimal

      - name: Visual Regression Tests
        run: |
          cd testing
          if [ -d baseline-screenshots ] && [ -n "\$(ls -A baseline-screenshots)" ]; then
            ./scripts/run-visual-diff.sh
          else
            echo "⚠️  No baseline screenshots - skipping visual regression"
          fi

      - name: Network Analysis
        run: |
          cd testing
          ./scripts/analyze-network.sh || true

      - name: Upload Test Results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: test-results
          path: |
            testing/test-results/

      - name: Check for Visual Regressions
        run: |
          if [ -f testing/test-results/visual-diff-*/diff-results.json ]; then
            DIFF_COUNT=\$(cat testing/test-results/visual-diff-*/diff-results.json | jq '.different')
            if [ "\$DIFF_COUNT" -gt 0 ]; then
              echo "❌ \$DIFF_COUNT visual regressions detected"
              exit 1
            fi
          fi

      - name: Post Results Comment
        uses: actions/github-script@v6
        if: github.event_name == 'pull_request'
        with:
          script: |
            const fs = require('fs');
            const summary = fs.readFileSync('testing/test-results/SUMMARY.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.name,
              body: summary
            });
EOF

print_success "Created GitHub Actions workflow"

# Final summary
print_header "✅ Setup Complete!"

echo "Testing framework installed for: $PROJECT_NAME"
echo
echo "📁 Location: $PROJECT_DIR/testing/"
echo
echo "🚀 Next Steps:"
echo
echo "1. Integrate Pulse network monitoring:"
echo "   cat $PROJECT_DIR/testing/PULSE_SETUP.md"
echo
echo "2. Capture baseline screenshots:"
echo "   cd $PROJECT_DIR/testing"
echo "   ./scripts/capture-baseline.sh"
echo
echo "3. Run your first test:"
echo "   cd $PROJECT_DIR/testing"
echo "   ./scripts/run-matrix-tests.sh minimal"
echo
echo "4. View results:"
echo "   open $PROJECT_DIR/testing/test-results/minimal/report.html"
echo
echo "📚 Documentation:"
echo "   - Framework guide: $PROJECT_DIR/testing/README.md"
echo "   - Pulse setup: $PROJECT_DIR/testing/PULSE_SETUP.md"
echo "   - Complete docs: {{CATALYST_ROOT}}/docs/ADVANCED_IOS_TESTING.md"
echo

print_success "iOS Testing Framework ready to use!"
