# SwiftUI Design Patterns

Quick reference for UI designers working in SwiftUI. For detailed patterns, use Context7 MCP with SwiftUI library.

## SwiftUI ↔ React Mapping

| React Concept | SwiftUI Equivalent |
|---------------|-------------------|
| Component | `View` struct |
| Props | `let` properties |
| State | `@State` (Mobile Dev handles) |
| Children | `@ViewBuilder content` |
| CSS-in-JS | View modifiers |

---

## Layout Components

```swift
VStack { }           // flex-direction: column
HStack { }           // flex-direction: row
ZStack { }           // position: absolute (layered)
ScrollView { }       // Scrollable content
List { }             // UITableView equivalent
```

---

## Common Elements

**Text & Images:**
```swift
Text("Hello")
    .font(.title)
    .foregroundColor(.blue)

Image(systemName: "heart.fill")  // SF Symbols
    .font(.largeTitle)
    .foregroundColor(.red)
```

**Inputs (use .constant for visual design):**
```swift
TextField("Placeholder", text: .constant(""))
SecureField("Password", text: .constant(""))
Toggle("Enabled", isOn: .constant(false))
```

**Buttons:**
```swift
Button("Tap Me") { }
    .buttonStyle(.borderedProminent)
```

**Navigation:**
```swift
NavigationStack {
    List { }
        .navigationTitle("Title")
}

TabView {
    ContentView()
        .tabItem { Label("Home", systemImage: "house") }
}
```

---

## Common Modifiers

```swift
.padding()                           // Add padding
.frame(width: 200, height: 50)      // Set size
.background(Color.blue)              // Background color
.cornerRadius(12)                    // Rounded corners
.opacity(0.8)                        // Transparency
.shadow(radius: 5)                   // Drop shadow
.foregroundColor(.white)             // Text/icon color
.font(.headline)                     // Typography
```

**Materials (glassmorphism):**
```swift
.background(.ultraThinMaterial)
.background(.thinMaterial)
.background(.regularMaterial)
.background(.thickMaterial)
```

---

## Design System Template

```swift
// Colors
extension Color {
    static let brandPrimary = Color(hex: "#007AFF")
    static let brandSecondary = Color(hex: "#5856D6")
}

// Typography
extension Font {
    static let displayLarge = Font.system(size: 34, weight: .bold)
    static let bodyRegular = Font.system(size: 16, weight: .regular)
}

// Spacing
extension CGFloat {
    static let spacingXS: CGFloat = 4
    static let spacingSM: CGFloat = 8
    static let spacingMD: CGFloat = 16
    static let spacingLG: CGFloat = 24
}

// Reusable Button
struct PrimaryButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.headline)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity, minHeight: 50)
        }
        .background(Color.brandPrimary)
        .cornerRadius(12)
    }
}
```

---

## Preview Setup

```swift
#Preview("Light Mode") {
    MyView()
}

#Preview("Dark Mode") {
    MyView()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    MyView()
        .environment(\.sizeCategory, .accessibilityExtraLarge)
}
```

---

## UI Designer Boundaries

**You create (visual only):**
- ✅ `.constant("")` for TextField/SecureField
- ✅ Empty closures `{ }` for Button actions
- ✅ Static mock data for previews

**Mobile Dev adds:**
- ❌ State management (@State, @StateObject)
- ❌ Data binding ($variable)
- ❌ API calls and networking
- ❌ Navigation logic
- ❌ Error handling
