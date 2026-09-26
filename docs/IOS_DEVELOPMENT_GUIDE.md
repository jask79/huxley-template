# iOS Development Guide

Complete reference for building, testing, and automating iOS apps in Huxley.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Testing](#testing)
4. [Advanced Testing Patterns](#advanced-testing-patterns)
5. [CI/CD Integration](#cicd-integration)
6. [Quick Reference](#quick-reference)
7. [Shortcuts Pipeline](#shortcuts-pipeline)

---

## Getting Started

### Prerequisites

```bash
# Python packages (for screenshot diffing)
pip3 install Pillow numpy

# Ruby gems (for test matrix and network tools)
gem install json

# Verify
python3 -c "import PIL; import numpy"
ruby -e "require 'json'"
```

### One-Command Setup

Run the setup script to scaffold complete testing infrastructure for any iOS project:

```bash
{{CATALYST_ROOT}}/tools/setup_ios_testing.sh MyApp.xcodeproj MyApp com.example.MyApp
```

This creates:

```
MyApp/
├── MyApp.xcodeproj
└── testing/
    ├── README.md
    ├── PULSE_SETUP.md
    ├── baseline-screenshots/
    ├── current-screenshots/
    ├── test-results/
    ├── configs/
    │   ├── minimal.json          # 6 combinations
    │   ├── accessibility.json    # 40 combinations
    │   ├── network.json          # 8 combinations
    │   └── comprehensive.json    # 54 combinations
    └── scripts/
        ├── capture-baseline.sh
        ├── capture-current.sh
        ├── run-visual-diff.sh
        ├── run-matrix-tests.sh
        ├── analyze-network.sh
        └── run-comprehensive-pipeline.sh
```

### Add Network Monitoring (Optional)

Automatically integrates Pulse network monitoring into your app:

```bash
{{CATALYST_ROOT}}/tools/add_pulse_to_app.sh MyApp/MyApp.swift
```

Adds: URLSession monitoring, 3-finger tap gesture for logs, DEBUG-only (zero production overhead).

Or follow the manual guide: `cat testing/PULSE_SETUP.md`

### Capture Baseline Screenshots

```bash
cd testing
./scripts/capture-baseline.sh

# Commit baselines to git
git add baseline-screenshots/
git commit -m "Add baseline screenshots for visual regression testing"
```

### Run Your First Test

```bash
cd testing

# Quick validation (6 configurations, ~5 minutes)
./scripts/run-matrix-tests.sh minimal

# View results
open test-results/minimal/report.html
```

---

## Development Workflow

Huxley uses a **Design-First** approach with 3 agents working in sequence:

```
UI Designer → Mobile Dev → Backend Dev → Complete App
```

**Why Design-First?**
- UX drives requirements
- Mobile Dev defines the backend API contract
- Complete app works with mocks before backend exists
- Simple 1-line swap from mock to real APIs

### Phase 1: UI Designer

#### Wireframing

Tools: Mermaid diagrams, text-based wireframes, markdown.

```
┌─────────────────────────────┐
│         [App Logo]          │
│                             │
│  ┌───────────────────────┐  │
│  │ Email                 │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │ Password              │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │      Log In           │  │
│  └───────────────────────┘  │
│      Forgot Password?       │
└─────────────────────────────┘
```

#### SwiftUI Implementation

UI Designer creates visual structure only — no business logic:

```swift
// src/Views/LoginView.swift
struct LoginView: View {
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        VStack(spacing: 24) {
            Image("logo")
                .resizable()
                .frame(width: 120, height: 120)

            TextField("Email", text: $email)
                .textFieldStyle(.roundedBorder)
                .autocapitalization(.none)

            SecureField("Password", text: $password)
                .textFieldStyle(.roundedBorder)

            Button("Log In") {
                // Mobile Dev adds logic here
            }
            .buttonStyle(.borderedProminent)
            .frame(height: 44) // iOS minimum touch target
        }
        .padding(24)
    }
}

#Preview {
    LoginView()
}
```

**Design system files:** `src/DesignSystem/Colors.swift`, `Typography.swift`, `Spacing.swift`

#### Design Validation (5 CLI Tools)

```bash
# 1. Grid compliance (4px/8px grid)
ruby tools/grid_overlay.rb capture --simulator "iPhone 16" --grid 8

# 2. Measure spacing precisely
ruby tools/ruler_tool.rb measure --file screenshot.png --from 0,100 --to 0,144 --annotate

# 3. Verify colors match design system + check contrast
ruby tools/color_picker.rb verify --file screenshot.png --at 180,320 --design-system src/Colors.swift
ruby tools/color_picker.rb pick --at 180,320 --background "#FFFFFF"

# 4. Professional device frame screenshots
ruby tools/device_bezel.rb frame --file screenshot.png --device "iPhone 16 Pro" --shadow

# 5. Animation demos
ruby tools/screen_recorder.rb record --duration 5 --gif --output animation.mov
```

**Deliverables:** SwiftUI Views (structure only), design system files, professional screenshots, animation demos, validation proof-of-work.

---

### Phase 2: Mobile Dev

Mobile Dev builds the complete app with mock APIs first, then swaps to real APIs after the backend is ready.

#### Step 1: Mock API Layer (First!)

```swift
// src/Services/AuthServiceProtocol.swift
protocol AuthServiceProtocol {
    func login(email: String, password: String) async throws -> LoginResponse
}

// src/Services/MockAuthService.swift
class MockAuthService: AuthServiceProtocol {
    func login(email: String, password: String) async throws -> LoginResponse {
        try await Task.sleep(nanoseconds: 1_000_000_000)  // Simulate network delay

        if email == "test@example.com" && password == "password" {
            return LoginResponse(
                accessToken: "mock-token-123",
                refreshToken: "mock-refresh-456",
                user: User(id: "1", name: "Test User", email: email)
            )
        } else {
            throw AuthError.invalidCredentials
        }
    }
}

// src/Services/RealAuthService.swift (implemented after backend is ready)
class RealAuthService: AuthServiceProtocol {
    func login(email: String, password: String) async throws -> LoginResponse {
        let response: LoginResponse = try await APIClient.shared.request(
            "/auth/login",
            method: .post,
            body: LoginRequest(email: email, password: password)
        )
        try KeychainManager.save(token: response.accessToken, key: "accessToken")
        return response
    }
}
```

#### Step 2: ViewModels & Business Logic

```swift
// src/ViewModels/LoginViewModel.swift
@MainActor
class LoginViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var isLoading = false
    @Published var errorMessage: String?

    func login() async {
        isLoading = true
        defer { isLoading = false }

        do {
            _ = try await AuthService.login(email: email, password: password)
            // Navigate to dashboard
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
```

#### Step 3: Wire Views to ViewModels

```swift
// src/Views/LoginView.swift (Mobile Dev updates)
struct LoginView: View {
    @StateObject private var viewModel = LoginViewModel()

    var body: some View {
        VStack(spacing: 24) {
            TextField("Email", text: $viewModel.email)
                .textFieldStyle(.roundedBorder)
                .disabled(viewModel.isLoading)

            SecureField("Password", text: $viewModel.password)
                .textFieldStyle(.roundedBorder)
                .disabled(viewModel.isLoading)

            Button("Log In") {
                Task { await viewModel.login() }
            }
            .buttonStyle(.borderedProminent)
            .frame(height: 44)
            .disabled(viewModel.isLoading)

            if viewModel.isLoading { ProgressView() }

            if let error = viewModel.errorMessage {
                Text(error).foregroundStyle(.red)
            }
        }
        .padding(24)
    }
}
```

#### Step 4: Configuration

```swift
// src/Config/Config.swift
enum Config {
    static let apiBaseURL: String = {
        #if DEBUG
        return "https://api-dev.myapp.com"
        #else
        return "https://api.myapp.com"
        #endif
    }()
}
```

#### Step 5: Build-Test Loop (Mandatory)

1. Build: `xcodebuildmcp build and run`
2. Tests: Unit, integration, UI tests
3. Run in simulator
4. Design validation: grid_overlay, ruler_tool, color_picker, device_bezel, screen_recorder
5. Comprehensive testing: simulator_control, screenshot_diff, ios_test_matrix, pulse_log_export

**Deliverables:** Complete working app (with mocks), backend API contract defined, all tests passing, design validation complete, professional screenshots.

---

### Phase 3: Backend Dev

Backend Dev implements real APIs matching Mobile Dev's contract exactly:

```python
# FastAPI example — must match Mobile Dev's protocol exactly
@app.post("/auth/login")
async def login(request: LoginRequest) -> LoginResponse:
    user = await authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user
    )
```

**Deliverables:** Real API endpoints, database schema, authentication system, API documentation.

---

### Phase 4: Mock → Real Swap

One line change in Mobile Dev's dependency injection:

```swift
// Before (mock)
let authService: AuthServiceProtocol = MockAuthService()

// After (real)
let authService: AuthServiceProtocol = RealAuthService()
```

**Final tests:** Integration tests with real backend, end-to-end tests, performance tests, security audit.

---

### Project File Structure

```
MyApp/
├── src/
│   ├── Views/               # UI Designer creates
│   │   ├── LoginView.swift
│   │   └── DashboardView.swift
│   ├── ViewModels/          # Mobile Dev creates
│   │   ├── LoginViewModel.swift
│   │   └── DashboardViewModel.swift
│   ├── Services/            # Mobile Dev creates
│   │   ├── AuthServiceProtocol.swift
│   │   ├── MockAuthService.swift      # Built first
│   │   └── RealAuthService.swift      # Added later
│   ├── DesignSystem/        # UI Designer creates
│   │   ├── Colors.swift
│   │   ├── Typography.swift
│   │   └── Spacing.swift
│   └── Config/
│       └── Config.swift
├── docs/
│   ├── wireframes/
│   ├── screenshots/
│   └── animations/
└── tests/
    ├── ViewModelTests/
    ├── ServiceTests/
    └── UITests/
```

---

### Common Design Issues

**Grid alignment:** Elements not on 8px grid → use `grid_overlay.rb` to visually verify, adjust padding/margins to multiples of 8.

**Color mismatch:** Hard-coded colors instead of design system → use `color_picker.rb verify` mode.

**Touch targets:** Buttons smaller than 44pt iOS minimum → use `ruler_tool.rb` to measure, set `.frame(height: 44)`.

**Contrast ratios:** Text fails WCAG AA (4.5:1) → use `color_picker.rb --background` flag, adjust colors.

---

## Testing

### Test Matrix Presets

| Preset | Configs | Time | Use Case |
|--------|---------|------|----------|
| **minimal** | 6 | 5-10 min | Daily dev, PRs |
| **accessibility** | 40 | 15-25 min | WCAG compliance |
| **network** | 8 | 10-15 min | Network resilience |
| **comprehensive** | 54 | 30-60 min | Pre-release |

**Minimal** — Light/Dark × 3 text sizes (L, XL, XXL)

**Accessibility** — 2 appearance × 5 text sizes × 4 accessibility features (Reduce Motion, Increase Contrast, Bold Text, normal)

**Network** — Light/Dark × WiFi / 3G (1.6 Mbps) / Edge (240 Kbps) / Offline

**Comprehensive** — 2 appearance × 3 text sizes × 3 network conditions × 3 accessibility states

### Running Tests

```bash
cd testing

# By preset
./scripts/run-matrix-tests.sh minimal
./scripts/run-matrix-tests.sh accessibility
./scripts/run-matrix-tests.sh network
./scripts/run-matrix-tests.sh comprehensive

# Full pipeline (matrix + visual regression + network analysis)
./scripts/run-comprehensive-pipeline.sh
```

### Visual Regression

```bash
cd testing

# Capture current state
./scripts/capture-current.sh

# Compare with baseline
./scripts/run-visual-diff.sh

# View results
open test-results/visual-diff-*/report.html
```

**Updating baselines** (after approved UI changes):

```bash
cd testing
./scripts/capture-baseline.sh
./scripts/run-visual-diff.sh          # Review diffs
open test-results/visual-diff-*/report.html
git add baseline-screenshots/
git commit -m "Update baselines for [reason]"
```

### Network Analysis

```bash
cd testing
./scripts/analyze-network.sh
open test-results/network-analysis-*.html
```

### Performance Reference

| Operation | Time | Output Size |
|-----------|------|-------------|
| Screenshot diff (single) | 1-2s | ~500KB |
| Screenshot diff (batch 50) | 30-60s | ~25MB |
| Minimal matrix | 5-10min | ~50MB |
| Accessibility matrix | 15-25min | ~200MB |
| Network matrix | 10-15min | ~80MB |
| Comprehensive matrix | 30-60min | ~300MB |
| Network analysis | 2-3s | ~500KB |
| Full pipeline | 30-60min | ~350MB |

---

## Advanced Testing Patterns

### Tool 1: Screenshot Diffing (`screenshot_diff.py`)

Pixel-level visual regression testing with antialiasing tolerance, batch processing, and HTML reports.

```bash
# Single comparison
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py baseline.png current.png -o diff/

# Batch mode (compare directories)
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py --batch \
  baseline-screenshots/ current-screenshots/ -o visual-diff-results/

# Custom threshold (2% tolerance, default is 1%)
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py baseline.png current.png -t 0.02

# JSON output for CI automation
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py baseline.png current.png -f json > diff.json
```

**Output:** `diff.png` (red highlights), `side-by-side.png`, `overlay.png`, `report.html`

**Dependencies:** `pip3 install Pillow numpy`

---

### Tool 2: Test Matrix (`ios_test_matrix.rb`)

Runs tests across all combinations of device configurations, generates HTML/JSON reports.

```bash
# Use a preset
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb run \
  --preset minimal \
  --project MyApp.xcodeproj \
  --scheme MyApp

# Use a custom config file
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb run --config test-config.json

# Generate a config template
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb generate-config --output test-config.json

# List available presets
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb list-configs
```

**Custom config format:**

```json
{
  "name": "My Test Matrix",
  "project_path": "/path/to/MyApp.xcodeproj",
  "scheme": "MyApp",
  "simulator": "iPhone 16",
  "matrix": {
    "appearance": ["light", "dark"],
    "text_size": ["L", "XL", "XXL", "AccessibilityXL"],
    "network": ["wifi", "3g", "off"],
    "location": [
      {"name": "SF", "lat": 37.7749, "lon": -122.4194},
      {"name": "NYC", "lat": 40.7128, "lon": -74.0060}
    ],
    "accessibility": [
      {"reduce_motion": true},
      {"increase_contrast": true}
    ]
  },
  "screenshot_screens": ["HomeView", "SettingsView"],
  "output_dir": "./test-results"
}
```

---

### Tool 3: Network Log Export (`pulse_log_export.rb`)

Extracts and analyzes network logs from Pulse LoggerStore.

```bash
# Export all logs
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb export \
  --app-id com.example.MyApp --format json

# Generate analysis report
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb analyze \
  --app-id com.example.MyApp --output network-report.html

# Filter errors only (4xx/5xx)
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb filter \
  --app-id com.example.MyApp --status 400-599 --output errors.json

# Filter by URL pattern
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb filter \
  --app-id com.example.MyApp --url-pattern "api.example.com" --format csv

# Filter by HTTP method and time range
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb filter \
  --app-id com.example.MyApp --method POST --since "2024-01-01T00:00:00Z"

# List installed apps
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb list-apps
```

**Analysis report includes:** Total requests, success/error rates, average response time, data sent/received, HTTP method distribution, status code breakdown, slow requests (>1s), error details.

**Requires Pulse in your Xcode project.** Add it:

```bash
ruby {{CATALYST_ROOT}}/tools/xcode_project_tool.rb add-package \
  --url "https://github.com/kean/Pulse" --product "Pulse"
```

---

### Integration Workflows

#### Workflow: Visual Regression Testing

```bash
# 1. Capture baselines (first time only)
ruby {{CATALYST_ROOT}}/tools/xcode_project_tool.rb build-run
ruby {{CATALYST_ROOT}}/tools/xcode_project_tool.rb take-screenshots --output baseline-screenshots/

# 2. After making changes, capture current state
ruby {{CATALYST_ROOT}}/tools/xcode_project_tool.rb build-run
ruby {{CATALYST_ROOT}}/tools/xcode_project_tool.rb take-screenshots --output current-screenshots/

# 3. Run diff analysis
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py --batch \
  baseline-screenshots/ current-screenshots/ -o screenshot-diff-results/

# 4. Review report
open screenshot-diff-results/report.html
```

#### Workflow: Network Performance Testing

```bash
# 1. Throttle to 3G speeds
ruby {{CATALYST_ROOT}}/tools/simulator_control.rb network-throttle \
  --simulator "iPhone 16" --profile 3g

# 2. Run app
ruby {{CATALYST_ROOT}}/tools/xcode_project_tool.rb build-run

# 3. Export network logs
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb analyze \
  --app-id com.example.MyApp --output network-analysis.html

open network-analysis.html
```

#### Workflow: Complete Testing Pipeline

```bash
#!/bin/bash
# comprehensive-test-pipeline.sh

APP_ID="com.example.MyApp"
PROJECT_PATH="{{CATALYST_ROOT}}/my-app/MyApp.xcodeproj"
SCHEME="MyApp"
SIMULATOR="iPhone 16"
OUTPUT_DIR="./test-results-$(date +%Y%m%d-%H%M%S)"

# Step 1: Run test matrix
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb run \
  --preset comprehensive \
  --project "$PROJECT_PATH" --scheme "$SCHEME" \
  --simulator "$SIMULATOR" \
  --output "$OUTPUT_DIR/matrix-results"

# Step 2: Visual regression testing
if [ -d "baseline-screenshots" ]; then
  python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py --batch \
    baseline-screenshots/ \
    "$OUTPUT_DIR/matrix-results/screenshots" \
    -o "$OUTPUT_DIR/visual-diff"
else
  echo "No baseline screenshots found — creating baseline"
  cp -r "$OUTPUT_DIR/matrix-results/screenshots" baseline-screenshots
fi

# Step 3: Network analysis
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb analyze \
  --app-id "$APP_ID" --output "$OUTPUT_DIR/network-analysis.html"

echo "Pipeline complete. Results: $OUTPUT_DIR"
```

#### Workflow: Matrix + Screenshot Diff (Per Configuration)

```bash
# Run matrix with screenshots
ruby ios_test_matrix.rb run --config test-config.json

# For each configuration's screenshots, run diff
for config_dir in matrix-results/screenshots/*; do
  config_name=$(basename "$config_dir")
  python3 screenshot_diff.py --batch \
    "baseline-screenshots/$config_name" \
    "$config_dir" \
    -o "diff-results/$config_name"
done
```

---

### Best Practices

**Screenshot Diffing:**
- Create baseline screenshots in production-ready state
- Use consistent simulator and status bar settings (`simulator_control.rb override-status-bar`)
- Review diffs before accepting — some changes are intentional
- Update baselines after approved UI changes
- Default 1% threshold is appropriate; increase to 2% (`-t 0.02`) only if too many false positives

**Test Matrix:**
- Start with minimal preset, expand to comprehensive for release
- Screenshot key screens only (not every view)
- Run minimal daily, accessibility weekly, comprehensive before releases
- Boot simulator before starting: `xcrun simctl boot "iPhone 16"`

**Network Analysis:**
- Export logs after test runs (not before — the database will be empty)
- Filter by status 400-599 to find client errors
- Compare performance across network conditions (3G vs WiFi)
- Run analysis after each test matrix run to correlate failures

---

### Troubleshooting

**"No booted simulators found"**
```bash
xcrun simctl boot "iPhone 16"
sleep 10
xcrun simctl list devices | grep Booted
```

**"Dependencies not installed"**
```bash
pip3 install Pillow numpy
gem install json
python3 -c "import PIL; import numpy"
ruby -e "require 'json'"
```

**"Image dimensions don't match"** — Different simulators used for baseline vs. current. Use the same simulator for both.

**"Too many false positives"** — Increase threshold: `python3 screenshot_diff.py baseline.png current.png -t 0.02`

**"Baseline screenshots not found"**
```bash
cd testing
./scripts/capture-baseline.sh
git add baseline-screenshots/ && git commit -m "Add baseline screenshots"
```

**"Pulse database not found"** — Pulse not integrated or no network requests made. Run the app and trigger network activity first. Use `ruby pulse_log_export.rb list-apps` to verify app bundle ID.

**"Could not find app container"** — Wrong bundle ID. Verify with `ruby pulse_log_export.rb list-apps`.

**Tests timing out on CI** — Use `minimal` preset for PRs, `comprehensive` for main branch only.

---

## CI/CD Integration

### Platform Templates

| Platform | Template Path |
|----------|---------------|
| GitHub Actions | `templates/ci-cd/ios-testing-github-actions.yml` |
| GitLab CI | `templates/ci-cd/ios-testing-gitlab-ci.yml` |
| Bitbucket | `templates/ci-cd/ios-testing-bitbucket-pipelines.yml` |
| CircleCI | `templates/ci-cd/ios-testing-circleci-config.yml` |
| Jenkins | `templates/ci-cd/ios-testing-Jenkinsfile` |

Copy the appropriate template and customize `SCHEME`, `BUNDLE_ID`, and `SIMULATOR`.

### GitHub Actions Setup

```bash
mkdir -p .github/workflows
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-github-actions.yml \
   .github/workflows/ios-testing.yml
```

Customize:
```yaml
env:
  SCHEME: "YourScheme"
  BUNDLE_ID: "com.your.app"
  SIMULATOR: "iPhone 16"
```

Example workflow:
```yaml
name: iOS Testing Pipeline
on: [push, pull_request]

jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Dependencies
        run: |
          pip3 install Pillow numpy
          gem install json

      - name: Boot Simulator
        run: |
          xcrun simctl boot "iPhone 16" || true
          sleep 10

      - name: Run Test Matrix
        run: |
          ruby tools/ios_test_matrix.rb run \
            --preset accessibility \
            --project MyApp.xcodeproj \
            --scheme MyApp \
            --output test-results/

      - name: Visual Regression Tests
        run: |
          python3 tools/screenshot_diff.py --batch \
            baseline-screenshots/ test-results/screenshots/ \
            -o visual-diff/ -f json > diff-results.json

      - name: Check for Regressions
        run: |
          if [ $(jq '.different' diff-results.json) -gt 0 ]; then
            echo "Visual regressions detected"
            exit 1
          fi

      - name: Upload Results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: test-results-${{ github.sha }}
          path: |
            test-results/
            visual-diff/
          retention-days: 30
          if-no-files-found: warn
```

### GitLab CI Setup

```bash
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-gitlab-ci.yml .gitlab-ci.yml
```

Stages: setup → build → test → analyze → report. Ensure you have a macOS runner tagged `macos`.

Artifacts stored 1 week for MRs, 1 month for main branch.

### Bitbucket Pipelines Setup

```bash
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-bitbucket-pipelines.yml bitbucket-pipelines.yml
```

Enable Pipelines in Repository Settings. Select macOS runner.

### CircleCI Setup

```bash
mkdir -p .circleci
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-circleci-config.yml .circleci/config.yml
```

Includes `nightly` workflow (cron at midnight) running comprehensive tests on main branch.

### Jenkins Setup

```bash
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-Jenkinsfile Jenkinsfile
```

Install plugins: HTML Publisher, Git, Pipeline. Create Pipeline job pointing to SCM. Configure macOS node with label `macos`.

Parameters: `TEST_PRESET`, `RUN_VISUAL_REGRESSION`, `RUN_NETWORK_ANALYSIS`.

---

### Common CI/CD Patterns

**Branch-specific testing:**
```yaml
# GitHub Actions
- name: Select Test Preset
  id: preset
  run: |
    if [[ "${{ github.ref }}" == "refs/heads/main" ]]; then
      echo "preset=comprehensive" >> $GITHUB_OUTPUT
    else
      echo "preset=minimal" >> $GITHUB_OUTPUT
    fi
```

**Scheduled nightly tests:**
```yaml
# GitHub Actions
on:
  schedule:
    - cron: '0 0 * * *'  # Midnight UTC

# GitLab CI
test:comprehensive:scheduled:
  only:
    - schedules
  script:
    - cd testing && ./scripts/run-comprehensive-pipeline.sh
```

**Parallel test execution:**
```yaml
# GitHub Actions — run all three presets simultaneously
strategy:
  matrix:
    preset: [minimal, accessibility, network]
steps:
  - run: ./scripts/run-matrix-tests.sh ${{ matrix.preset }}
```

**Dependency caching:**
```yaml
# GitHub Actions
- uses: actions/cache@v3
  with:
    path: |
      ~/.cache/pip
      ~/.gem
    key: ${{ runner.os }}-deps-${{ hashFiles('**/Pipfile.lock', '**/Gemfile.lock') }}
```

**Simulator boot optimization:**
```bash
# Start simulator boot in background while building
xcrun simctl boot "iPhone 16" &
BOOT_PID=$!
xcodebuild build -scheme MyApp ...
wait $BOOT_PID  # Simulator ready by the time build finishes
```

**Baseline management in CI:**
```yaml
- name: Setup Baselines
  run: |
    cd testing
    if [ ! -d baseline-screenshots ] || [ -z "$(ls -A baseline-screenshots)" ]; then
      ./scripts/capture-baseline.sh
      git config user.email "ci@example.com"
      git config user.name "CI Bot"
      git add baseline-screenshots/
      git commit -m "Create baseline screenshots [skip ci]"
      git push
    fi
```

**Branch strategy:**

| Branch type | Preset | Visual regression | Network analysis |
|-------------|--------|-------------------|------------------|
| Feature branches | minimal | yes | no |
| Main/develop | comprehensive | yes | yes |
| Release branches | comprehensive + accessibility | yes | yes |

---

## Quick Reference

### Initial Setup (One-Time)

```bash
# Setup testing framework
{{CATALYST_ROOT}}/tools/setup_ios_testing.sh MyApp.xcodeproj MyApp com.example.MyApp

# Add Pulse network monitoring (optional)
{{CATALYST_ROOT}}/tools/add_pulse_to_app.sh MyApp/MyApp.swift

# Capture and commit baselines
cd testing
./scripts/capture-baseline.sh
git add baseline-screenshots/ && git commit -m "Add baseline screenshots"
```

### Running Tests

```bash
cd testing

./scripts/run-matrix-tests.sh minimal          # 6 configs, ~5 min
./scripts/run-matrix-tests.sh accessibility    # 40 configs, ~20 min
./scripts/run-matrix-tests.sh network          # 8 configs, ~12 min
./scripts/run-matrix-tests.sh comprehensive    # 54 configs, ~45 min
./scripts/run-comprehensive-pipeline.sh        # Full pipeline
```

### Visual Regression

```bash
cd testing
./scripts/capture-current.sh
./scripts/run-visual-diff.sh
open test-results/visual-diff-*/report.html
```

### Network Analysis

```bash
cd testing
./scripts/analyze-network.sh
open test-results/network-analysis-*.html
```

### Direct Tool Usage

```bash
# Screenshot diff
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py baseline.png current.png -o diff/
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py --batch baseline/ current/ -o results/
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py baseline.png current.png -t 0.02  # 2% threshold

# Test matrix
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb run --preset minimal --project MyApp.xcodeproj --scheme MyApp
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb generate-config -o custom.json
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb list-configs

# Network export
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb export --app-id com.example.MyApp
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb analyze --app-id com.example.MyApp
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb filter --app-id com.example.MyApp --status 400-599
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb list-apps
```

### CI/CD Templates

```bash
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-github-actions.yml .github/workflows/ios-testing.yml
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-gitlab-ci.yml .gitlab-ci.yml
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-bitbucket-pipelines.yml bitbucket-pipelines.yml
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-circleci-config.yml .circleci/config.yml
cp {{CATALYST_ROOT}}/templates/ci-cd/ios-testing-Jenkinsfile Jenkinsfile
```

### Common Workflows

```bash
# Daily development
cd testing && ./scripts/run-matrix-tests.sh minimal && ./scripts/run-visual-diff.sh

# Before PR
cd testing && ./scripts/run-matrix-tests.sh accessibility && ./scripts/run-visual-diff.sh

# Network debugging
cd testing && ./scripts/run-matrix-tests.sh network && ./scripts/analyze-network.sh

# Pre-release
cd testing && ./scripts/run-comprehensive-pipeline.sh
```

### Tool Help

```bash
{{CATALYST_ROOT}}/tools/setup_ios_testing.sh --help
python3 {{CATALYST_ROOT}}/tools/screenshot_diff.py --help
ruby {{CATALYST_ROOT}}/tools/ios_test_matrix.rb --help
ruby {{CATALYST_ROOT}}/tools/pulse_log_export.rb --help
{{CATALYST_ROOT}}/tools/add_pulse_to_app.sh --help
```

### New Project Checklist

- [ ] Run `setup_ios_testing.sh` with project details
- [ ] Add Pulse (optional)
- [ ] Capture baseline screenshots
- [ ] Commit baselines to git
- [ ] Run minimal test matrix
- [ ] Verify all tests pass and review report
- [ ] Choose CI/CD platform and copy template
- [ ] Test pipeline on feature branch, then enable for main

---

## Shortcuts Pipeline

Complete automation pipeline from Huxley specifications to deployable iOS Shortcuts using Cherri language.

### Architecture

```
Capsule Spec (requirements.yaml)
    → Generate .cherri source
    → Cursor IDE validation
    → Cherri CLI compilation
    → .shortcut file
    → macOS Shortcuts.app import
```

### IDE Integration

**Primary: Cursor IDE** (`/Applications/Cursor.app`)
- Cherri language extension with syntax highlighting, IntelliSense, real-time error checking
- Automatically opens generated .cherri files

**Fallback: Cherri IDE** (`/Applications/Cherri.app`)
- Native Cherri support, built-in compilation, shortcut preview

### Usage

```bash
# Default: opens Cursor IDE for interactive development
python3 tools/generate_shortcuts.py /path/to/capsule

# Force Cherri IDE
python3 tools/generate_shortcuts.py /path/to/capsule cherri

# Terminal only (no IDE)
python3 tools/generate_shortcuts.py /path/to/capsule none

# Agent automation mode (no IDE, minimal output)
python3 tools/generate_shortcuts.py /path/to/capsule --agent
```

### Generated File Structure

```
capsule/
├── spec/requirements.yaml          # Source specification
├── src/shortcuts/
│   ├── common.cherri               # Common Huxley actions
│   └── generated/
│       └── ShortcutName.cherri     # Generated source
└── ops/shortcuts/
    └── ShortcutName.shortcut       # Compiled, signed shortcut
```

### Pipeline Steps

1. **Spec Parsing** — Read `spec/requirements.yaml` shortcut definitions
2. **Source Generation** — Create `.cherri` files with Huxley patterns
3. **IDE Opening** — Launch Cursor IDE for validation and editing
4. **Compilation** — Cherri CLI compiles to signed `.shortcut` files
5. **Auto-Import** — Open shortcuts in macOS Shortcuts app for installation

### Quality Assurance

- Cursor IDE Cherri extension catches syntax errors before compilation
- Generated code follows Huxley conventions
- All shortcuts are properly signed for iOS installation
- Complete test suite with sample shortcuts
