# Huxley Debug Overlays for SwiftUI
**Production-Ready Debug Tools for iOS Development**

## Overview

Huxley Debug Overlays are a collection of reusable SwiftUI components designed to accelerate iOS development and debugging. These tools only compile in DEBUG builds and provide powerful capabilities for:

- Layout alignment and spacing validation
- Pixel-perfect design comparison
- Precise measurements and distance calculations
- Color extraction and code generation
- Animation debugging and speed control

All overlays are **zero-impact on production** (automatically excluded from Release builds) and follow SwiftUI best practices.

---

## Quick Start

### Installation

Copy the entire `DebugOverlays/` folder into your Xcode project:

```
MyApp/
├── Sources/
│   ├── Views/
│   ├── Models/
│   └── DebugOverlays/          ← Add this folder
│       ├── GridOverlay.swift
│       ├── DesignOverlay.swift
│       ├── RulerOverlay.swift
│       ├── ColorPickerOverlay.swift
│       ├── AnimationControlOverlay.swift
│       └── README.md (this file)
```

### Basic Usage

```swift
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Text("Hello, World!")
        }
        .debugGrid()  // Add 8pt grid overlay
    }
}
```

---

## Components

### 1. Grid Overlay

**Purpose:** Validate layout alignment and spacing using a visual grid.

**Features:**
- Customizable grid spacing (default: 8pt)
- Major grid lines every 5th line
- Adjustable colors and line width
- Non-interactive overlay

**Usage:**

```swift
// Simple usage (8pt grid)
VStack {
    // Your content
}
.debugGrid()

// Custom spacing and color
VStack {
    // Your content
}
.debugGrid(spacing: 4, color: .blue.opacity(0.2))

// Conditional display
VStack {
    // Your content
}
.debugGrid(enabled: showDebugTools)
```

**Direct component usage:**

```swift
.overlay(
    GridOverlay(
        spacing: 8,
        color: .red.opacity(0.3),
        lineWidth: 0.5,
        showMajorLines: true
    )
)
```

---

### 2. Design Overlay

**Purpose:** Compare implemented UI against design mockups for pixel-perfect accuracy.

**Features:**
- Opacity adjustment slider
- Multiple blend modes (normal, difference, multiply, screen)
- Side-by-side comparison slider
- Collapsible controls

**Setup:**

1. Export design mockup from Figma/Sketch as PNG
2. Add image to Assets.xcassets (e.g., "figma-home-screen")
3. Add overlay to view

**Usage:**

```swift
// Overlay mockup on implementation
VStack {
    // Your implementation
}
.designOverlay("figma-home-screen")

// Side-by-side slider comparison
DesignComparisonView(
    designImageName: "figma-home-screen"
) {
    // Your implementation
    HomeScreenView()
}
```

**Controls:**
- **Opacity Slider:** Adjust transparency (0-100%)
- **Blend Mode:** Normal, Difference (highlights differences), Multiply, Screen
- **Eye Icon:** Show/hide controls

---

### 3. Ruler Overlay

**Purpose:** Precise measurements, coordinates, and distance calculations.

**Features:**
- Horizontal and vertical rulers (every 10pt)
- Real-time coordinate tracking
- Distance measurement tool
- Multiple measurements with automatic cleanup

**Usage:**

```swift
// Add rulers
VStack {
    // Your content
}
.debugRulers()

// Horizontal only
VStack {
    // Your content
}
.debugRulers(horizontal: true, vertical: false)

// Distance measurement tool
VStack {
    // Your content
}
.measurementTool()
```

**Interaction:**
- **Tap and drag:** Show coordinates at cursor
- **Measurement tool:** Tap to set start point, drag to measure distance, release to save
- **Clear measurements:** Tap trash icon

---

### 4. Color Picker Overlay

**Purpose:** Extract colors from UI and generate code in multiple formats.

**Features:**
- Magnifier loupe for precise color picking
- Copy code to clipboard in multiple formats:
  - SwiftUI `Color`
  - UIKit `UIColor`
  - Hex code
  - RGB values
- Visual color swatch display

**Usage:**

```swift
// Add color picker
VStack {
    // Your content with various colors
}
.colorPicker()

// Conditional
VStack {
    // Your content
}
.colorPicker(enabled: showColorPicker)
```

**Interaction:**
1. Tap and hold on any color
2. Magnifier loupe appears
3. Release to capture color
4. Color info panel slides up
5. Tap format to copy to clipboard
6. Close panel when done

**Generated Formats:**

```swift
// SwiftUI Color
Color(red: 0.251, green: 0.502, blue: 0.753, opacity: 1.000)

// UIColor
UIColor(red: 0.251, green: 0.502, blue: 0.753, alpha: 1.000)

// Hex
#4080BF

// RGB
rgb(64, 128, 191)
```

---

### 5. Animation Control Overlay

**Purpose:** Debug animations by slowing down or speeding up playback.

**Features:**
- Animation speed control (0.1x to 2x)
- Preset speed buttons
- Minimized/expanded panel
- Animation timeline visualizer
- Per-view animation multipliers

**Usage:**

```swift
// Add global animation controls
ZStack {
    // Your app content
}
.animationControls()

// Slow down specific animation
Text("Animating")
    .animation(.easeInOut(duration: 1.0).slow(by: 2.0), value: isAnimating)

// Multiply animation duration for debugging
Circle()
    .frame(width: isExpanded ? 200 : 100)
    .animationMultiplier(2.0)  // 2x slower

// Animation timeline (for complex sequences)
AnimationTimelineView(animations: [
    ("Fade In", duration: 0.3),
    ("Scale Up", duration: 0.5),
    ("Slide", duration: 0.4)
])
```

**Controls:**
- **Speed Slider:** Adjust from 0.1x (very slow) to 2x (fast)
- **Presets:** Quick access to common speeds
- **Expand/Collapse:** Toggle control panel

---

## Combining Overlays

You can stack multiple debug overlays:

```swift
struct ContentView: View {
    @State private var showDebugTools = true

    var body: some View {
        VStack {
            // Your content
        }
        .debugGrid(enabled: showDebugTools)
        .debugRulers(enabled: showDebugTools)
        .colorPicker(enabled: showDebugTools)
        .animationControls(enabled: showDebugTools)
    }
}
```

---

## Common Workflows

### Workflow 1: Layout Validation

```swift
VStack(spacing: 16) {
    // Your layout
}
.debugGrid(spacing: 8)
.debugRulers()
```

1. Enable grid to verify spacing consistency
2. Use rulers to measure exact distances
3. Disable when layout is correct

### Workflow 2: Design Implementation

```swift
VStack {
    // Your implementation
}
.designOverlay("figma-screen")
.colorPicker()
```

1. Overlay Figma mockup on implementation
2. Adjust opacity to see differences
3. Use color picker to extract exact colors
4. Use difference blend mode to highlight discrepancies

### Workflow 3: Animation Tuning

```swift
ZStack {
    // Your animated UI
}
.animationControls()
```

1. Enable animation controls
2. Slow down to 0.1x or 0.5x
3. Watch animations frame-by-frame
4. Fine-tune timing and easing
5. Return to 1x to verify

### Workflow 4: Pixel-Perfect Screenshots

```swift
VStack {
    // Your screen
}
.debugGrid(spacing: 8)
.debugRulers()
```

1. Use rulers to verify exact positioning
2. Use grid to validate spacing
3. Remove overlays before screenshot
4. Use simulator_control.rb for perfect status bar

---

## Integration with Huxley Testing Tools

These debug overlays work seamlessly with Huxley's comprehensive testing framework:

### With simulator_control.rb

```bash
# Set up perfect testing environment
ruby tools/simulator_control.rb set-appearance --simulator "iPhone 16" --mode dark
ruby tools/simulator_control.rb override-status-bar --simulator "iPhone 16" --time "9:41"

# Run app with debug overlays enabled
# Use overlays to validate UI
# Take screenshot with xcodebuildmcp
```

### With Mobile Dev Agent

The Mobile Dev agent can add these overlays to any iOS project automatically:

```
"Add grid overlay to help me validate spacing"
→ Mobile Dev adds .debugGrid() to view

"I need to compare my implementation against the Figma mockup"
→ Mobile Dev adds .designOverlay("figma-file")
  and helps import design image

"Slow down the animation so I can see what's wrong"
→ Mobile Dev adds .animationControls()
```

---

## Best Practices

### DO:

✅ Use debug overlays during development
✅ Remove overlays before production screenshots
✅ Commit overlay code (safe in DEBUG builds only)
✅ Combine multiple overlays for comprehensive debugging
✅ Use conditional `enabled` parameters for easy toggling

### DON'T:

❌ Wrap overlays in `#if DEBUG` (already done internally)
❌ Leave overlays enabled for App Store screenshots
❌ Use overlays for production builds (they won't compile)
❌ Modify overlay source files (copy and extend instead)

---

## Keyboard Shortcuts (Optional Enhancement)

Add keyboard shortcuts for quick overlay toggling:

```swift
struct ContentView: View {
    @State private var showGrid = false
    @State private var showRulers = false
    @State private var showColorPicker = false

    var body: some View {
        VStack {
            // Your content
        }
        .debugGrid(enabled: showGrid)
        .debugRulers(enabled: showRulers)
        .colorPicker(enabled: showColorPicker)
        .onAppear {
            setupKeyboardShortcuts()
        }
    }

    private func setupKeyboardShortcuts() {
        // Register keyboard shortcuts in AppDelegate or SceneDelegate
        // Cmd+G: Toggle Grid
        // Cmd+R: Toggle Rulers
        // Cmd+C: Toggle Color Picker
    }
}
```

---

## Customization

All overlays support customization through init parameters:

```swift
// Custom grid
GridOverlay(
    spacing: 4,               // 4pt grid
    color: .blue.opacity(0.2), // Blue grid lines
    lineWidth: 0.3,           // Thinner lines
    showMajorLines: false     // No major lines
)

// Custom ruler
RulerOverlay(
    showHorizontal: true,
    showVertical: true,
    color: .green.opacity(0.8),
    thickness: 25
)
```

---

## Troubleshooting

**Overlays not showing:**
- Check you're running in DEBUG configuration
- Verify `enabled` parameter is true
- Ensure overlay is added after view content (use `.overlay()`)

**Overlays blocking interactions:**
- All overlays have `.allowsHitTesting(false)` by default
- Exception: Color picker and measurement tool need interaction

**Performance issues:**
- Overlays are lightweight, but rendering many lines can impact FPS
- Disable overlays when not actively debugging
- Use conditional `enabled` parameters

**Color picker not capturing colors:**
- Current implementation uses placeholder colors
- Real implementation requires UIView snapshot API
- Alternative: Use Digital Color Meter app (macOS)

---

## Advanced: Custom Debug Overlays

Create your own debug overlays following the same pattern:

```swift
#if DEBUG
struct CustomDebugOverlay: View {
    var body: some View {
        // Your debug visualization
    }
}

extension View {
    func customDebug(enabled: Bool = true) -> some View {
        self.overlay(
            Group {
                if enabled {
                    CustomDebugOverlay()
                }
            }
        )
    }
}
#endif
```

---

## Version History

- **v1.0.0** - Initial release
  - Grid Overlay
  - Design Overlay
  - Ruler Overlay
  - Color Picker Overlay
  - Animation Control Overlay

---

## Summary

Huxley Debug Overlays provide a comprehensive suite of tools for iOS development:

1. **GridOverlay** - Validate alignment and spacing
2. **DesignOverlay** - Pixel-perfect design comparison
3. **RulerOverlay** - Precise measurements
4. **ColorPickerOverlay** - Color extraction
5. **AnimationControlOverlay** - Animation debugging

All tools are DEBUG-only, zero-impact on production, and designed for seamless integration with Huxley's Mobile Dev workflows.

**Next Steps:**
1. Copy debug overlay files to your project
2. Add `.debugGrid()` to a view
3. Build and run in simulator
4. Explore other overlays as needed

For questions or enhancements, see Huxley documentation.
