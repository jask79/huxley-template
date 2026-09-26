# Design Validation Tools

CLI tools for autonomous design verification. Tool locations: `{{CATALYST_ROOT}}/tools/`

## 1. Grid Overlay Tool

**Purpose:** Verify 4px/8px grid compliance

```bash
# Capture with grid overlay
ruby tools/grid_overlay.rb capture --simulator "iPhone 16" --grid 8 --output ~/Desktop/grid_check.png

# Apply to existing screenshot
ruby tools/grid_overlay.rb capture --file screenshot.png --grid 4 --annotate

# Options: --grid SIZE (4,8,16,32), --color (red,blue,green,pink,cyan), --major SIZE, --annotate
```

## 2. Ruler Tool

**Purpose:** Measure precise spacing between elements

```bash
# Measure between points
ruby tools/ruler_tool.rb measure --file screenshot.png --from 100,200 --to 300,400 --annotate

# Interactive mode
ruby tools/ruler_tool.rb interactive --file screenshot.png

# Batch from JSON
ruby tools/ruler_tool.rb batch --file screenshot.png --measurements measurements.json --output results.json
```

**measurements.json example:**
```json
[
  {"label": "Top margin", "from": {"x": 0, "y": 0}, "to": {"x": 0, "y": 24}},
  {"label": "Button height", "from": {"x": 100, "y": 200}, "to": {"x": 100, "y": 244}}
]
```

## 3. Color Picker Tool

**Purpose:** Extract and verify colors match design system

```bash
# Pick color at coordinates
ruby tools/color_picker.rb pick --file screenshot.png --at 150,300 --format swift

# Verify against design system
ruby tools/color_picker.rb verify --file screenshot.png --at 150,300 --design-system src/Colors.swift

# Check contrast
ruby tools/color_picker.rb pick --file screenshot.png --at 150,300 --background "#FFFFFF"

# Extract palette
ruby tools/color_picker.rb palette --file screenshot.png --colors 10 --output palette.json
```

**Output formats:** hex, rgb, swift, uicolor, css

**Contrast requirements:**
- WCAG AA Normal: >=4.5:1
- WCAG AA Large: >=3:1
- WCAG AAA Normal: >=7:1

## 4. Device Bezel Tool

**Purpose:** Add professional device frames

```bash
ruby tools/device_bezel.rb frame --file screenshot.png --device "iPhone 16 Pro" --background white --shadow
ruby tools/device_bezel.rb list-devices
```

**Devices:** iPhone 16 Pro Max/Pro/SE, iPad Pro 13/11
**Backgrounds:** white, black, light-gray, gradient-blue, gradient-purple, transparent, #HEX

## 5. Screen Recorder Tool

**Purpose:** Record animations for demos

```bash
# Record video
ruby tools/screen_recorder.rb record --duration 10 --output ~/Desktop/demo.mov

# Record with GIF
ruby tools/screen_recorder.rb record --duration 15 --gif --gif-fps 15 --output demo.mov

# Convert to GIF
ruby tools/screen_recorder.rb convert --input demo.mov --output demo.gif --fps 15 --width 600
```

---

## Verification Workflow

```
1. CREATE DESIGN → SwiftUI/HTML components
2. RENDER → Run in simulator
3. CAPTURE → Screenshot via xcodebuildmcp
4. VALIDATE (Tools):
   - Grid Overlay → Spacing alignment
   - Ruler → Margins, padding, touch targets
   - Color Picker → Design system compliance + contrast
5. ITERATE → Fix issues, loop back
6. PROOF-OF-WORK:
   - Device Bezel → Professional screenshots
   - Screen Recorder → Animation demos
```

## Proof-of-Work Example

```markdown
## Design Verification Complete

**Design:** Product Card Component
**Iterations:** 2

### Validation Results
- Grid Overlay: 8px compliance confirmed
- Ruler: Card 16pt padding, button 44pt height
- Color Picker: All colors from design system, contrast 7.2:1
- Device Bezel: iPhone 16 Pro screenshots (light/dark)
- Screen Recorder: Animation demo at 0.4s spring
```
