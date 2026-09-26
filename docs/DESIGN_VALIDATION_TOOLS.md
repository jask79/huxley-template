# Design Validation Tools

**Five CLI tools for autonomous design verification in UI Designer and Mobile Dev agent loops.**

## Overview

These tools enable pixel-perfect design validation during autonomous agentic loops. They complement existing testing tools (simulator_control.rb, screenshot_diff.py, ios_test_matrix.rb) and provide design-specific verification capabilities.

**Purpose:** Enable UI Designer and Mobile Dev agents to autonomously verify designs match specifications without manual inspection.


**Tool Locations:** `{{CATALYST_ROOT}}/tools/`

---

## Tool Suite

### 1. Grid Overlay Tool
**File:** `grid_overlay.rb`
**Purpose:** Verify 4px/8px grid compliance visually

#### Features
- Apply 4px, 8px, 16px, or 32px grid overlays to screenshots
- Major grid lines (thicker, darker) for section boundaries
- Multiple grid colors (red, blue, green, pink, cyan)
- Metadata annotations
- Works with live simulator or existing screenshots

#### Usage

**Capture from simulator with grid:**
```bash
ruby tools/grid_overlay.rb capture --simulator "iPhone 16" --grid 8 --output ~/Desktop/grid_check.png
```

**Apply grid to existing screenshot:**
```bash
ruby tools/grid_overlay.rb capture --file ~/Desktop/screenshot.png --grid 4 --annotate
```

**With major grid lines:**
```bash
ruby tools/grid_overlay.rb capture --grid 8 --major 32 --color blue
```

**List presets:**
```bash
ruby tools/grid_overlay.rb presets
```

#### Options
- `--simulator NAME` - Simulator name (e.g., "iPhone 16")
- `--file PATH` - Use existing screenshot
- `--grid SIZE` - Grid size: 4, 8, 16, 32 pixels
- `--color COLOR` - Grid color: red, blue, green, pink, cyan
- `--major SIZE` - Major grid lines every N pixels (thicker, darker)
- `--output PATH` - Output file path
- `--annotate` - Add metadata annotation to image

#### When to Use
- After creating any UI layout
- Before claiming "spacing correct"
- When elements look misaligned
- During handoff QA

#### Dependencies
- ImageMagick: `brew install imagemagick`
- Xcode Command Line Tools

---

### 2. Ruler Tool
**File:** `ruler_tool.rb`
**Purpose:** Measure precise spacing between elements

#### Features
- Horizontal, vertical, and diagonal measurements in points
- Automatic 4px/8px grid compliance checking
- Common iOS spacing detection (4, 8, 16, 24, 32, 44pt)
- Interactive mode for multiple measurements
- Batch mode from JSON file
- Annotated screenshots with measurement overlays

#### Usage

**Measure distance between two points:**
```bash
ruby tools/ruler_tool.rb measure --file screenshot.png --from 100,200 --to 300,400 --annotate
```

**Interactive measurement mode:**
```bash
ruby tools/ruler_tool.rb interactive --file screenshot.png
```

**Batch measure from JSON:**
```bash
ruby tools/ruler_tool.rb batch --file screenshot.png --measurements measurements.json --output results.json
```

#### Options
- `--simulator NAME` - Simulator name
- `--file PATH` - Use existing screenshot
- `--from X,Y` - Starting coordinates (e.g., 100,200)
- `--to X,Y` - Ending coordinates (e.g., 300,400)
- `--measurements PATH` - JSON file for batch measurements
- `--output PATH` - Output file path (JSON results)
- `--annotate` - Save annotated image with measurement overlay

#### When to Use
- Verify margin/padding matches design system
- Check button heights (44pt minimum iOS)
- Measure spacing between sections
- Validate touch target sizes

#### Example measurements.json
```json
[
  {
    "label": "Top margin",
    "from": {"x": 0, "y": 0},
    "to": {"x": 0, "y": 24}
  },
  {
    "label": "Button height",
    "from": {"x": 100, "y": 200},
    "to": {"x": 100, "y": 244}
  },
  {
    "label": "Card spacing",
    "from": {"x": 20, "y": 300},
    "to": {"x": 20, "y": 316}
  }
]
```

#### Grid Compliance Output
```
✅ Grid Compliance:
   4px grid: ✅ (H: ✅, V: ✅)
   8px grid: ✅ (H: ✅, V: ✅)
   ✨ Uses standard iOS spacing
```

#### Dependencies
- ImageMagick: `brew install imagemagick`
- Xcode Command Line Tools

---

### 3. Color Picker Tool
**File:** `color_picker.rb`
**Purpose:** Extract and verify colors match design system

#### Features
- Extract colors at specific coordinates
- Verify against design system files (Colors.swift)
- Check WCAG accessibility contrast ratios
- Batch color extraction from JSON
- Extract dominant color palettes
- Multiple output formats (hex, rgb, swift, uicolor, css)
- Delta E (ΔE) color matching for design system verification

#### Usage

**Pick color at specific coordinates:**
```bash
ruby tools/color_picker.rb pick --file screenshot.png --at 150,300 --format swift
```

**Verify against design system:**
```bash
ruby tools/color_picker.rb verify --file screenshot.png --at 150,300 --design-system src/Colors.swift
```

**Check accessibility contrast:**
```bash
ruby tools/color_picker.rb pick --file screenshot.png --at 150,300 --background "#FFFFFF"
```

**Batch extract colors:**
```bash
ruby tools/color_picker.rb batch --file screenshot.png --points colors.json --design-system src/Colors.swift
```

**Extract dominant color palette:**
```bash
ruby tools/color_picker.rb palette --file screenshot.png --colors 10 --output palette.json
```

#### Options
- `--simulator NAME` - Simulator name
- `--file PATH` - Use existing screenshot
- `--at X,Y` - Coordinates to pick color from (e.g., 100,200)
- `--points PATH` - JSON file for batch picking
- `--design-system PATH` - Design system file (Colors.swift) for verification
- `--background HEX` - Background color for contrast check (e.g., #FFFFFF)
- `--format FORMAT` - Output format: hex, rgb, rgba, swift, uicolor, nscolor, css
- `--colors N` - Number of dominant colors (palette mode)
- `--output PATH` - Output file path (JSON)

#### Output Formats
- `hex` - #3366CC
- `rgb` - rgb(51, 102, 204)
- `rgba` - rgba(51, 102, 204, 1.0)
- `swift` - Color(red: 0.2, green: 0.4, blue: 0.8)
- `uicolor` - UIColor(red: 0.2, green: 0.4, blue: 0.8, alpha: 1.0)
- `nscolor` - NSColor(red: 0.2, green: 0.4, blue: 0.8, alpha: 1.0)
- `css` - rgb(51, 102, 204)

#### Design System Verification (Delta E)
- **Exact match** (ΔE < 1.0) - Color matches design system ✅
- **Close match** (ΔE < 3.0) - Visually similar, acceptable ⚠️
- **No match** (ΔE ≥ 3.0) - Color not in design system, add or fix ❌

#### Accessibility Contrast (WCAG)
- WCAG AA Normal Text: ≥4.5:1
- WCAG AA Large Text (18pt+): ≥3:1
- WCAG AAA Normal Text: ≥7:1
- WCAG AAA Large Text (18pt+): ≥4.5:1

#### When to Use
- After applying colors to any UI element
- Before claiming "colors match design system"
- When colors look slightly off
- To verify hard-coded colors aren't used
- Check accessibility compliance

#### Example colors.json
```json
[
  {"label": "Primary button background", "x": 180, "y": 400},
  {"label": "Primary button text", "x": 180, "y": 405},
  {"label": "Background", "x": 50, "y": 50},
  {"label": "Title text", "x": 100, "y": 150}
]
```

#### Design System File Format (Colors.swift)
```swift
import SwiftUI

extension Color {
    // Primary colors
    static let primaryBlue = Color(red: 0.2, green: 0.4, blue: 0.8)
    static let primaryRed = Color(hex: "#E63946")

    // Background colors
    static let backgroundPrimary = Color(hex: "#FFFFFF")
    static let backgroundSecondary = Color(hex: "#F5F5F5")

    // Text colors
    static let textPrimary = Color(red: 0.1, green: 0.1, blue: 0.1)
    static let textSecondary = Color(red: 0.4, green: 0.4, blue: 0.4)
}
```

#### Dependencies
- ImageMagick: `brew install imagemagick`
- Xcode Command Line Tools

---

### 4. Device Bezel Tool
**File:** `device_bezel.rb`
**Purpose:** Add professional device frames to screenshots

#### Features
- Add bezels for iPhone 16 Pro Max, iPhone 16 Pro, iPhone 16, iPhone SE, iPad Pro
- Dynamic Island rendering for modern iPhones
- Home button rendering for iPhone SE
- Multiple background presets (white, black, gradients)
- Custom hex color backgrounds
- Transparent backgrounds for compositing
- Drop shadow effects
- Adjustable padding

#### Usage

**Add iPhone bezel:**
```bash
ruby tools/device_bezel.rb frame --file screenshot.png --device "iPhone 16 Pro" --background white
```

**With shadow and gradient background:**
```bash
ruby tools/device_bezel.rb frame --file screenshot.png --device "iPhone 16" --background gradient-blue --shadow
```

**List available devices:**
```bash
ruby tools/device_bezel.rb list-devices
```

#### Options
- `--simulator NAME` - Simulator name
- `--file PATH` - Use existing screenshot
- `--device DEVICE` - Device type (required)
- `--background BG` - Background preset or hex color
- `--padding PX` - Padding around device (default: 50px)
- `--shadow` - Add drop shadow to device
- `--output PATH` - Output file path

#### Available Devices
- **iPhone 16 Pro Max** (1320×2868, Dynamic Island)
- **iPhone 16 Pro** (1206×2622, Dynamic Island)
- **iPhone 16** (1179×2556, Dynamic Island)
- **iPhone SE** (750×1334, Home Button)
- **iPad Pro 13** (2064×2752)
- **iPad Pro 11** (1668×2388)

#### Background Presets
- `white` - #FFFFFF
- `black` - #000000
- `light-gray` - #F5F5F5
- `dark-gray` - #1C1C1E
- `gradient-blue` - Blue gradient
- `gradient-purple` - Purple gradient
- `transparent` - Transparent (for overlaying)
- Custom hex color: `#F5F5F5`

#### When to Use
- Final handoff screenshots to client
- Marketing material screenshots
- Presentation decks
- Portfolio case studies
- App Store screenshots

#### Dependencies
- ImageMagick: `brew install imagemagick`
- Xcode Command Line Tools

---

### 5. Screen Recorder Tool
**File:** `screen_recorder.rb`
**Purpose:** Record animations and interactions for demo

#### Features
- Record video from iOS Simulator (MOV format)
- Convert to MP4 or GIF
- Automatic GIF conversion during recording
- Video trimming to specific time ranges
- Video optimization for smaller file sizes
- Adjustable frame rate (default 60fps video, 15fps GIF)
- Adjustable quality settings
- List available simulators

#### Usage

**Record 10-second video:**
```bash
ruby tools/screen_recorder.rb record --duration 10 --output ~/Desktop/animation_demo.mov
```

**Record with automatic GIF conversion:**
```bash
ruby tools/screen_recorder.rb record --duration 15 --gif --gif-fps 15 --output demo.mov
```

**Convert existing video to GIF:**
```bash
ruby tools/screen_recorder.rb convert --input demo.mov --output demo.gif --fps 15 --width 600
```

**Trim video:**
```bash
ruby tools/screen_recorder.rb trim --input demo.mov --start 00:00:05 --duration 10 --output trimmed.mov
```

**List available simulators:**
```bash
ruby tools/screen_recorder.rb list
```

#### Options
- `--simulator NAME` - Simulator name (default: first booted)
- `--duration SECONDS` - Recording duration (default: 10s)
- `--output PATH` - Output file path
- `--input PATH` - Input file for conversion/trimming
- `--start TIME` - Start time for trimming (e.g., 00:00:05)
- `--format FORMAT` - Output format: mov, mp4, gif
- `--fps FPS` - Frames per second (default: 60 video, 15 GIF)
- `--gif` - Also create GIF version after recording
- `--gif-fps FPS` - GIF frame rate (default: 15)
- `--width PX` - Width for GIF conversion (default: 600)
- `--quality N` - Quality (GIF: 1-100, MP4: 0-51 CRF)
- `--optimize` - Optimize video file size after recording

#### When to Use
- After implementing animations to demo timing
- Show gesture interactions (swipe, drag, pinch)
- Demo navigation transitions
- Illustrate loading states and error flows
- Create documentation GIFs

#### Tips
- Press Ctrl+C during recording to stop early
- Use `--gif` flag to auto-generate GIF alongside video
- Use `--optimize` for smaller file sizes (slower encoding)
- Trim videos to focus on specific interactions

#### Dependencies
- Xcode Command Line Tools (for recording)
- FFmpeg: `brew install ffmpeg` (for conversion, trimming, optimization)

---

## Integration with Agent Workflows

### UI Designer Agent Integration

**Design Verification Loop (Step 4 - VALIDATE DESIGN):**

```
1. CREATE DESIGN (SwiftUI components)
   ↓
2. RENDER IN TARGET ENVIRONMENT (iOS Simulator)
   ↓
3. CAPTURE VISUAL OUTPUT (Screenshot)
   ↓
4. VALIDATE DESIGN ← USE DESIGN VALIDATION TOOLS HERE

   ✅ Grid Overlay Tool
      - Verify spacing alignment
      - Check 4px/8px grid compliance

   ✅ Ruler Tool
      - Measure all margins and padding
      - Validate touch targets (44pt minimum)
      - Verify spacing matches specifications

   ✅ Color Picker Tool
      - Extract all UI colors
      - Verify against design system
      - Check WCAG contrast ratios
      - Confirm no hard-coded colors

   Results:
   - All measurements match? → Proceed
   - All colors from design system? → Proceed
   - Grid compliance confirmed? → Proceed
   - Accessibility met? → Proceed
   - Issues found? → Fix and loop back to step 1
   ↓
5. ITERATE IF NEEDED (Max 3 attempts)
   ↓
6. PROOF-OF-WORK ← USE TOOLS HERE

   ✅ Device Bezel Tool
      - Professional handoff screenshots
      - Light + Dark mode

   ✅ Screen Recorder Tool
      - Animation demos
      - Interaction recordings

   ✅ Validation checklist completed
```

### Mobile Dev Agent Integration

**BUILD-TEST LOOP (Step 4 - DESIGN VALIDATION):**

```
1. Build app with xcodebuildmcp
   ↓
2. Run tests (unit, UI, integration)
   ↓
3. Run in simulator - MANUALLY VERIFY
   ↓
4. DESIGN VALIDATION ← USE DESIGN VALIDATION TOOLS HERE

   ✅ Grid Overlay Tool → Verify spacing alignment

   ✅ Ruler Tool → Measure margins/padding/touch targets

   ✅ Color Picker Tool
      - Verify design system colors
      - Check accessibility contrast

   ✅ Device Bezel Tool
      - Professional handoff screenshots

   ✅ Screen Recorder Tool
      - Demo animations to UI Designer
   ↓
5. If validation fails → Fix implementation → Loop to step 1
   If validation passes → Deployment ready
```

---

## Example Validation Workflow

### Scenario: Product Card Component

**Task:** Implement product card component with image, title, price, and "Add to Cart" button

#### Step 1: Implementation (Mobile Dev)
- Implement SwiftUI component
- Build and run in simulator

#### Step 2: Design Validation

**Grid Overlay:**
```bash
ruby tools/grid_overlay.rb capture --simulator "iPhone 16" --grid 8 --output product_card_grid.png
```

**Result:** ✅ All elements align to 8px grid

**Ruler Measurements:**
```bash
ruby tools/ruler_tool.rb interactive --file product_card_screenshot.png

# Measurements taken:
> 16,16 200,16     # Card padding left: 16pt ✅
> 16,16 16,240     # Card padding top: 16pt ✅
> 16,260 16,304    # Button height: 44pt ✅
> 16,244 16,252    # Title-to-price spacing: 8pt ✅
```

**Result:** ✅ All measurements match design specifications

**Color Verification:**
```bash
ruby tools/color_picker.rb verify --file product_card_screenshot.png \
  --at 100,100 --design-system src/Colors.swift

# Check background color
Extracted Color: #FFFFFF
✅ EXACT MATCH: backgroundPrimary

ruby tools/color_picker.rb pick --file product_card_screenshot.png \
  --at 100,270 --background "#FFFFFF"

# Check button text contrast
Contrast Ratio: 4.8:1
✅ WCAG AA (Normal Text ≥4.5:1): Pass
```

**Result:** ✅ All colors from design system, contrast compliant

#### Step 3: Professional Handoff

**Device Bezel:**
```bash
ruby tools/device_bezel.rb frame --file product_card_screenshot.png \
  --device "iPhone 16 Pro" --background white --shadow \
  --output product_card_final.png
```

**Result:** Professional screenshot for client handoff

**Animation Demo:**
```bash
ruby tools/screen_recorder.rb record --duration 5 \
  --output product_card_tap_animation.mov --gif --gif-fps 15
```

**Result:** Video + GIF showing card tap animation

#### Step 4: Validation Summary

```markdown
## Implementation Verification ✅

**Component:** Product Card
**Iterations:** 1 (no fixes needed)

### Design Validation Results

**Grid Overlay Tool:**
- ✅ 8px grid compliance confirmed
- Screenshot: `product_card_grid.png`

**Ruler Tool:**
- ✅ Card padding: 16pt (2× grid)
- ✅ Image height: 180pt
- ✅ Button height: 44pt (iOS minimum)
- ✅ Title-to-price spacing: 8pt

**Color Picker Tool:**
- ✅ Background: `backgroundPrimary` (exact match, ΔE=0.0)
- ✅ Title text: `textPrimary` (exact match, ΔE=0.0)
- ✅ Price text: `accentGreen` (exact match, ΔE=0.0)
- ✅ Button: `primaryBlue` (exact match, ΔE=0.0)
- ✅ Contrast title/background: 12.1:1 (WCAG AAA)
- ✅ Contrast button text/background: 4.8:1 (WCAG AA)

**Device Bezel Tool:**
- Professional screenshot: `product_card_final.png`

**Screen Recorder Tool:**
- Animation demo: `product_card_tap_animation.mov`
- GIF: `product_card_tap_animation.gif`

### Handoff Package Ready
- ✅ All measurements verified
- ✅ All colors from design system
- ✅ Accessibility requirements met
- ✅ Professional screenshots created
- ✅ Animation demonstrated
- ✅ Implementation complete
```

---

## Troubleshooting

### Common Issues

**Issue: "ImageMagick not found"**
```bash
brew install imagemagick
```

**Issue: "Xcode Command Line Tools not found"**
```bash
xcode-select --install
```

**Issue: "FFmpeg not found" (screen_recorder.rb)**
```bash
brew install ffmpeg
```

**Issue: "No booted simulator found"**
```bash
# Boot simulator first
open -a Simulator
# Or use xcodebuildmcp to boot specific simulator
```

**Issue: Grid overlay colors hard to see**
- Try different colors: `--color blue`, `--color cyan`, `--color pink`
- Use `--major` for thicker grid lines: `--major 32`

**Issue: Color picker can't find design system colors**
- Verify Colors.swift file exists at specified path
- Check color definitions format matches examples
- Use `hex` format if Swift Color format not detected

**Issue: Device bezel screenshot looks wrong**
- Verify device name exactly matches available devices
- Run `ruby tools/device_bezel.rb list-devices` for valid names
- Screenshot dimensions must match device screen size

**Issue: Screen recording file not created**
- Check simulator is actually booted and running
- Verify output path directory exists
- Try shorter duration first (5-10 seconds)
- Check disk space available

---

## Tool Performance

### Execution Times (Approximate)

- **Grid Overlay:** ~2-5 seconds
- **Ruler Tool:** ~1-3 seconds per measurement
- **Color Picker:** ~1-2 seconds per color
- **Device Bezel:** ~5-10 seconds (complex renders)
- **Screen Recorder:** Duration + 2-5 seconds processing

### File Sizes (Approximate)

- **Grid Overlay Output:** 2-5 MB PNG
- **Ruler Tool Output:** 2-5 MB PNG (annotated)
- **Device Bezel Output:** 3-8 MB PNG
- **Screen Recording:** 1-5 MB per second (MOV), 500KB-2MB per second (GIF)

---

## Future Enhancements

### Planned Features

1. **Grid Overlay Tool:**
   - Auto-detect grid size from screenshot
   - Save/load custom grid presets
   - Highlight grid violations in red

2. **Ruler Tool:**
   - Auto-detect common measurements (44pt buttons, status bar height)
   - Compare measurements across multiple screenshots
   - Export measurements to design system documentation

3. **Color Picker Tool:**
   - Auto-generate missing design system colors
   - Suggest accessible color alternatives
   - Batch verify entire screenshot against design system

4. **Device Bezel Tool:**
   - Support for more devices (Apple Watch, Mac)
   - Custom device frames from templates
   - Multi-device composition (show iPhone + iPad together)

5. **Screen Recorder Tool:**
   - Picture-in-picture recording (simulator + code)
   - Auto-detect and trim to animations only
   - Add overlays (tap indicators, gesture paths)

---

## Credits

**Created:** October 27, 2025
**Location:** `{{CATALYST_ROOT}}/tools/`
**Documentation:** `{{CATALYST_ROOT}}/docs/DESIGN_VALIDATION_TOOLS.md`

**Related Documentation:**
- `{{CATALYST_ROOT}}/docs/SIMULATOR_TESTING_GUIDE.md` - Comprehensive simulator testing
- `{{CATALYST_ROOT}}/.claude/agents/ui-designer.md` - UI Designer agent
- `{{CATALYST_ROOT}}/.claude/agents/mobile-dev.md` - Mobile Dev agent
- `{{CATALYST_ROOT}}/.claude/skills/ios-testing/SKILL.md` - iOS testing skill

---

**End of Documentation**
