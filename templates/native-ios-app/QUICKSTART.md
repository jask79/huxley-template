# Native iOS App - Quick Start

**Get productive in 15 minutes**

---

## 1. Create Xcode Project (5 min)

```bash
# Open Xcode
open /Applications/Xcode.app

# File → New → Project
# Select: iOS → App
# Interface: SwiftUI
# Language: Swift
# Minimum iOS: 17.0
```

---

## 2. Add InjectionIII (3 min)

### Add Package

1. File → Add Package Dependencies
2. URL: `https://github.com/krzysztofzablocki/Inject`
3. Click "Add Package"
4. Select your app target
5. Click "Add Package"

### Update ContentView.swift

```swift
import SwiftUI
import Inject  // ← Add this

struct ContentView: View {
    @ObserveInjection var inject  // ← Add this

    var body: some View {
        VStack {
            Image(systemName: "globe")
                .imageScale(.large)
                .foregroundStyle(.tint)
            Text("Hello, world!")
        }
        .padding()
        .enableInjection()  // ← Add this
    }
}
```

---

## 3. Test Hot Reloading (2 min)

1. **Run app** (Cmd+R)
2. **Edit** ContentView.swift - change "Hello, world!" to "Hello, {{ORCHESTRATOR_NAME}}!"
3. **Save** (Cmd+S)
4. **Watch** - text updates in ~2 seconds! 🎉

---

## 3.5 Understanding Your Iteration Tools (1 min)

**You have TWO tools that work together:**

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **Xcode Previews** | Component isolation | Designing new components, testing variants side-by-side |
| **InjectionIII** | Full app hot reload | Testing in app context, navigation flows, real data |

**Workflow:**
```
Xcode Previews (Component Design)
├─ Design Button with 5 variants
├─ Test with different text lengths
└─ Verify Light/Dark mode

↓ (once design is solid)

InjectionIII (Integration)
├─ Add Button to login screen
├─ Test in navigation flow
└─ Edit → Save → See in 2s
```

**Example supporting both:**
```swift
import SwiftUI
import Inject

struct MyButton: View {
    @ObserveInjection var inject  // For InjectionIII

    var body: some View {
        Button("Press Me") { }
            .enableInjection()
    }
}

// For Xcode Previews
#Preview("Default") { MyButton() }
#Preview("Dark") { MyButton().preferredColorScheme(.dark) }
```

**Bottom line:** Use Previews to design, InjectionIII to integrate. Both are essential!

---

## 4. Design System Setup (5 min)

### Create Utilities Folder

```
YourApp/
└── Utilities/
    ├── Colors.swift
    ├── Typography.swift
    └── Spacing.swift
```

### Colors.swift

```swift
import SwiftUI

extension Color {
    // Brand Colors
    static let primary = Color(hex: "#007AFF")
    static let secondary = Color(hex: "#5856D6")

    // Status Colors
    static let success = Color(hex: "#34C759")
    static let warning = Color(hex: "#FF9500")
    static let error = Color(hex: "#FF3B30")

    // Neutral Colors
    static let background = Color(.systemBackground)
    static let secondaryBackground = Color(.secondarySystemBackground)
    static let text = Color(.label)
    static let secondaryText = Color(.secondaryLabel)
}

// Hex color initializer
extension Color {
    init(hex: String) {
        let scanner = Scanner(string: hex)
        scanner.scanLocation = hex.hasPrefix("#") ? 1 : 0

        var rgb: UInt64 = 0
        scanner.scanHexInt64(&rgb)

        let r = Double((rgb >> 16) & 0xFF) / 255.0
        let g = Double((rgb >> 8) & 0xFF) / 255.0
        let b = Double(rgb & 0xFF) / 255.0

        self.init(red: r, green: g, blue: b)
    }
}
```

### Typography.swift

```swift
import SwiftUI

extension Font {
    // Display
    static let displayLarge = Font.system(size: 57, weight: .bold, design: .rounded)
    static let displayMedium = Font.system(size: 45, weight: .bold, design: .rounded)
    static let displaySmall = Font.system(size: 36, weight: .bold, design: .rounded)

    // Headline
    static let headlineLarge = Font.system(size: 32, weight: .semibold, design: .rounded)
    static let headlineMedium = Font.system(size: 28, weight: .semibold, design: .rounded)
    static let headlineSmall = Font.system(size: 24, weight: .semibold, design: .rounded)

    // Title
    static let titleLarge = Font.system(size: 22, weight: .semibold)
    static let titleMedium = Font.system(size: 16, weight: .semibold)
    static let titleSmall = Font.system(size: 14, weight: .semibold)

    // Body
    static let bodyLarge = Font.system(size: 16, weight: .regular)
    static let bodyMedium = Font.system(size: 14, weight: .regular)
    static let bodySmall = Font.system(size: 12, weight: .regular)

    // Label
    static let labelLarge = Font.system(size: 14, weight: .medium)
    static let labelMedium = Font.system(size: 12, weight: .medium)
    static let labelSmall = Font.system(size: 11, weight: .medium)
}
```

### Spacing.swift

```swift
import SwiftUI

enum Spacing {
    // 8pt grid system
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let base: CGFloat = 16
    static let lg: CGFloat = 24
    static let xl: CGFloat = 32
    static let xxl: CGFloat = 48
    static let xxxl: CGFloat = 64

    // Corner radius
    static let radiusXS: CGFloat = 4
    static let radiusSM: CGFloat = 8
    static let radiusMD: CGFloat = 12
    static let radiusLG: CGFloat = 16
    static let radiusXL: CGFloat = 20

    // Touch targets
    static let touchMinimum: CGFloat = 44
    static let touchComfortable: CGFloat = 48
    static let touchLarge: CGFloat = 56
}
```

---

## 6. Development Loop

```
Run app ONCE (Cmd+R)
↓
Navigate to screen you're working on
↓
Edit Swift code
↓
Save (Cmd+S) → See changes in 2s
↓
Repeat (no rebuilding!)
```

---

## 7. Add Xcode Previews (Optional)

For complex components:

```swift
struct MyComplexView: View {
    @ObserveInjection var inject

    var body: some View {
        // Complex implementation
        .enableInjection()
    }
}

#Preview("Default") {
    MyComplexView()
}

#Preview("Dark Mode") {
    MyComplexView()
        .preferredColorScheme(.dark)
}

#Preview("With Data") {
    MyComplexView()
        .environmentObject(SampleData())
}
```

---

## Next Steps

**Read complete workflow:**
- `{{CATALYST_ROOT}}/global/docs/Mobile_App_Workflow.md`

**Reference docs:**
- `docs/MOBILE_WORKFLOW.md` - iOS-specific details
- `docs/INJECTION_SETUP.md` - InjectionIII deep dive
- `docs/DOCC_SETUP.md` - Documentation generation

---

## Troubleshooting

**InjectionIII not working?**
1. Check `import Inject` at top of file
2. Check `@ObserveInjection var inject` in View struct
3. Check `.enableInjection()` at end of body
4. Clean build folder (Cmd+Shift+K) and rebuild

**App won't build?**
1. Clean build folder (Cmd+Shift+K)
2. Close and reopen Xcode
3. Verify package was added correctly

---

*Native iOS Quick Start - Huxley Template*
