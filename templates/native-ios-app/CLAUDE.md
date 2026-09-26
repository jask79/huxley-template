# [Your App Name] - Native iOS Application

## Purpose
[Brief description of your iOS app - what it does and who it's for]

## Current Status
- **Phase:** Initial Setup
- **Last Updated:** [Date]
- **Platform:** iOS 17+
- **Technology:** Native Swift/SwiftUI

## Technical Overview
- **Primary Technologies:** Swift 5.9+, SwiftUI
- **Development Tools:** Xcode 15+, InjectionIII (hot reloading)
- **Design:** your design tool of choice (Figma, Penpot, ...)
- **Dependencies:** iOS 17+

## Key Features
[List your app's main features]

1. Feature 1
2. Feature 2
3. Feature 3

## Development Workflow

**Complete workflow:** See `{{CATALYST_ROOT}}/global/docs/Mobile_App_Workflow.md`

### Quick Reference

**Tools:**
- **Xcode 15+** - IDE and build system
- **InjectionIII** - Hot reloading (30x faster iteration: 60s → 2s)
- **Xcode Previews** - Component isolation

**Workflow:**
```
📐 UI Designer (design tool)
    ↓
📱 Mobile Dev (Swift + InjectionIII)
    ↓
Validation (Screenshots vs design)
```

### InjectionIII Setup

**Add package to Xcode:**
1. File → Add Package Dependencies
2. URL: `https://github.com/krzysztofzablocki/Inject`
3. Add to your target

**Update View files:**
```swift
import SwiftUI
import Inject

struct MyView: View {
    @ObserveInjection var inject

    var body: some View {
        // Your view code
        .enableInjection()
    }
}
```

**Fast iteration:**
```
1. Run app ONCE (Cmd+R)
2. Edit Swift code
3. Save (Cmd+S) → See changes in 2s
4. Repeat steps 2-3 (no rebuilding!)
```

## Design Resources

## Design System

**Colors:**
```swift
// Update with your brand colors
extension Color {
    static let primary = Color(hex: "#007AFF")
    static let secondary = Color(hex: "#5856D6")
    static let success = Color(hex: "#34C759")
    static let warning = Color(hex: "#FF9500")
    static let error = Color(hex: "#FF3B30")
}
```

**Typography:**
```swift
// SF Pro font system (iOS default)
// Display: 34pt Bold
// Title: 22pt Semibold
// Body: 16pt Regular
```

**Spacing:**
```swift
// 8pt grid system
enum Spacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let base: CGFloat = 16
    static let lg: CGFloat = 24
    static let xl: CGFloat = 32
    static let xxl: CGFloat = 48
}
```

## Directory Structure

```
your-app/
├── CLAUDE.md                    # This file
├── QUICKSTART.md                # Quick setup guide
├── README.md                    # Project overview
├── docs/
│   ├── MOBILE_WORKFLOW.md       # iOS-specific workflow
│   ├── INJECTION_SETUP.md       # Hot reload guide
│   └── DOCC_SETUP.md            # Documentation setup
├── design/
│   └── [design exports]
└── src/
    ├── YourApp.xcodeproj        # Xcode project
    ├── Models/
    ├── Views/
    ├── Services/
    └── Utilities/
        ├── Colors.swift
        ├── Typography.swift
        └── Spacing.swift
```

## Setup Checklist

- [ ] Create Xcode project
- [ ] Add InjectionIII package
- [ ] Update key Views with hot reload hooks
- [ ] Create your screen designs
- [ ] Export design system values
- [ ] Implement Colors.swift, Typography.swift, Spacing.swift
- [ ] Add Xcode Previews to complex components
- [ ] Reference this workflow doc in code comments

## Documentation

- **Global Mobile Workflow:** `{{CATALYST_ROOT}}/global/docs/Mobile_App_Workflow.md`
- **Design Workflow:** `{{CATALYST_ROOT}}/global/docs/Design_to_Code_Workflow.md`

## Apple Guidelines

- **Apple HIG:** https://developer.apple.com/design/human-interface-guidelines
- **SwiftUI:** https://developer.apple.com/xcode/swiftui/
- **InjectionIII:** https://github.com/krzysztofzablocki/Inject

## Performance Expectations

**With InjectionIII:**
- Edit → Save: 1-2s (vs 30-60s full rebuild)
- 30x faster iteration
- 45-55 min/day saved

---

*Native iOS App Template - Huxley*
