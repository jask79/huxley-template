# SwiftUI for UI Designers

**Quick Reference: React → SwiftUI Translation**

**Last Updated:** October 2025

---

## Overview

SwiftUI is Apple's declarative UI framework for iOS, iPadOS, macOS, watchOS, and tvOS. If you know React, **you already understand SwiftUI's mental model.**

**Key Similarities:**
- Declarative syntax (describe what, not how)
- Component-based architecture
- Props pattern (immutable properties)
- Composition over inheritance
- Live preview/hot reload

---

## Core Concepts

### 1. Components = Views

**React:**
```jsx
function Welcome({ name }) {
  return <Text>Hello, {name}</Text>;
}
```

**SwiftUI:**
```swift
struct Welcome: View {
    let name: String

    var body: some View {
        Text("Hello, \(name)")
    }
}
```

### 2. Props = Properties

**React:**
```jsx
function Button({ title, onPress, disabled }) {
  return (
    <TouchableOpacity onPress={onPress} disabled={disabled}>
      <Text>{title}</Text>
    </TouchableOpacity>
  );
}
```

**SwiftUI:**
```swift
struct PrimaryButton: View {
    let title: String
    let action: () -> Void
    let disabled: Bool = false

    var body: some View {
        Button(action: action) {
            Text(title)
        }
        .disabled(disabled)
    }
}
```

### 3. Styling = View Modifiers

**React (CSS-in-JS):**
```jsx
<View style={{
  padding: 20,
  backgroundColor: '#007AFF',
  borderRadius: 12
}}>
```

**SwiftUI (chained modifiers):**
```swift
SomeView()
    .padding(20)
    .background(Color.blue)
    .cornerRadius(12)
```

---

## Layout Components

### Flex Direction → Stack Views

**React Native:**
```jsx
// Vertical
<View style={{ flexDirection: 'column' }}>
  <Text>Item 1</Text>
  <Text>Item 2</Text>
</View>

// Horizontal
<View style={{ flexDirection: 'row' }}>
  <Text>Item 1</Text>
  <Text>Item 2</Text>
</View>
```

**SwiftUI:**
```swift
// Vertical
VStack {
    Text("Item 1")
    Text("Item 2")
}

// Horizontal
HStack {
    Text("Item 1")
    Text("Item 2")
}
```

### Spacing and Alignment

**React Native:**
```jsx
<View style={{
  flexDirection: 'column',
  gap: 20,
  alignItems: 'flex-start'
}}>
```

**SwiftUI:**
```swift
VStack(alignment: .leading, spacing: 20) {
    // Content
}

// Alignment options:
// .leading (left), .center, .trailing (right)
// .top, .bottom
```

### Z-Index → ZStack

**React Native:**
```jsx
<View>
  <View style={{ position: 'absolute', zIndex: 1 }}>Background</View>
  <View style={{ position: 'absolute', zIndex: 2 }}>Foreground</View>
</View>
```

**SwiftUI:**
```swift
ZStack {
    BackgroundView()  // Bottom layer
    ForegroundView()  // Top layer
}
```

---

## Common Components

### Text

**React Native:**
```jsx
<Text style={{
  fontSize: 24,
  fontWeight: 'bold',
  color: '#007AFF'
}}>
  Hello World
</Text>
```

**SwiftUI:**
```swift
Text("Hello World")
    .font(.title)
    .fontWeight(.bold)
    .foregroundColor(.blue)

// Or use system text styles:
Text("Headline")
    .font(.headline)

Text("Body")
    .font(.body)
```

### Images

**React Native:**
```jsx
<Image
  source={require('./icon.png')}
  style={{ width: 50, height: 50 }}
/>
```

**SwiftUI:**
```swift
// Asset catalog image
Image("icon")
    .resizable()
    .frame(width: 50, height: 50)

// SF Symbol (system icon)
Image(systemName: "heart.fill")
    .font(.largeTitle)
    .foregroundColor(.red)
```

### Buttons

**React Native:**
```jsx
<TouchableOpacity onPress={() => console.log('Pressed')}>
  <Text>Press Me</Text>
</TouchableOpacity>
```

**SwiftUI:**
```swift
Button("Press Me") {
    print("Pressed")
}

// With custom styling
Button(action: {}) {
    Text("Press Me")
        .padding()
        .background(Color.blue)
        .foregroundColor(.white)
        .cornerRadius(8)
}

// Built-in button styles
Button("Press Me") {}
    .buttonStyle(.borderedProminent)
```

### Text Input

**React Native:**
```jsx
<TextInput
  placeholder="Enter email"
  value={email}
  onChangeText={setEmail}
  keyboardType="email-address"
/>
```

**SwiftUI (visual design only):**
```swift
// UI Designer uses .constant() for visual design
TextField("Enter email", text: .constant(""))
    .textFieldStyle(.roundedBorder)
    .keyboardType(.emailAddress)

SecureField("Password", text: .constant(""))
    .textFieldStyle(.roundedBorder)

// Mobile Dev replaces with real binding:
// TextField("Enter email", text: $email)
```

### Lists

**React Native:**
```jsx
<FlatList
  data={items}
  renderItem={({ item }) => <Text>{item.name}</Text>}
/>
```

**SwiftUI:**
```swift
List(items) { item in
    Text(item.name)
}

// Or with ScrollView for custom layouts
ScrollView {
    ForEach(items) { item in
        Text(item.name)
    }
}
```

---

## Navigation

### Stack Navigation

**React Native:**
```jsx
<NavigationContainer>
  <Stack.Navigator>
    <Stack.Screen name="Home" component={HomeScreen} />
    <Stack.Screen name="Details" component={DetailsScreen} />
  </Stack.Navigator>
</NavigationContainer>
```

**SwiftUI:**
```swift
NavigationStack {
    HomeView()
        .navigationTitle("Home")
        .navigationDestination(for: Workout.self) { workout in
            WorkoutDetailView(workout: workout)
        }
}
```

### Tab Navigation

**React Native:**
```jsx
<Tab.Navigator>
  <Tab.Screen name="Home" component={HomeScreen} />
  <Tab.Screen name="Settings" component={SettingsScreen} />
</Tab.Navigator>
```

**SwiftUI:**
```swift
TabView {
    HomeView()
        .tabItem {
            Label("Home", systemImage: "house")
        }

    SettingsView()
        .tabItem {
            Label("Settings", systemImage: "gear")
        }
}
```

---

## Styling Reference

### Colors

**React Native:**
```jsx
style={{ backgroundColor: '#007AFF' }}
```

**SwiftUI:**
```swift
.background(Color.blue)
.foregroundColor(.red)

// Custom colors
.background(Color(hex: "#007AFF"))

// Semantic colors (adapt to Light/Dark mode)
.background(.primary)       // Text color
.background(.secondary)     // Secondary text
.background(.tertiary)      // Tertiary text
```

### Padding & Spacing

**React Native:**
```jsx
style={{ padding: 20, marginTop: 10 }}
```

**SwiftUI:**
```swift
.padding()              // All sides (default 16)
.padding(.horizontal)   // Left & right
.padding(.top, 20)      // Specific side
```

### Size

**React Native:**
```jsx
style={{ width: 200, height: 100 }}
```

**SwiftUI:**
```swift
.frame(width: 200, height: 100)
.frame(maxWidth: .infinity)  // Full width
```

### Border Radius

**React Native:**
```jsx
style={{ borderRadius: 12 }}
```

**SwiftUI:**
```swift
.cornerRadius(12)

// Or with specific corners
.clipShape(RoundedRectangle(cornerRadius: 12))
```

### Shadows

**React Native:**
```jsx
style={{
  shadowColor: '#000',
  shadowOffset: { width: 0, height: 2 },
  shadowOpacity: 0.25,
  shadowRadius: 3.84
}}
```

**SwiftUI:**
```swift
.shadow(radius: 5)
.shadow(color: .black.opacity(0.25), radius: 5, x: 0, y: 2)
```

### Opacity

**React Native:**
```jsx
style={{ opacity: 0.8 }}
```

**SwiftUI:**
```swift
.opacity(0.8)
```

---

## iOS-Specific Features

### SF Symbols (6,900+ icons)

```swift
Image(systemName: "heart.fill")
Image(systemName: "star.fill")
Image(systemName: "person.circle")
Image(systemName: "gear")
Image(systemName: "house")

// With styling
Image(systemName: "heart.fill")
    .font(.largeTitle)
    .foregroundColor(.red)
```

**Browse all icons:** Download SF Symbols app from Apple

### Materials (Glassmorphism)

```swift
.background(.ultraThinMaterial)  // Most translucent
.background(.thinMaterial)
.background(.regularMaterial)
.background(.thickMaterial)      // Least translucent

// Example: Card with glass effect
VStack {
    Text("Glassmorphic Card")
}
.padding()
.background(.ultraThinMaterial)
.cornerRadius(12)
```

### Dynamic Type (Accessibility)

```swift
Text("Scales with user preference")
    .font(.body)

// System text styles (adapt to user settings):
.font(.largeTitle)
.font(.title)
.font(.title2)
.font(.title3)
.font(.headline)
.font(.body)
.font(.callout)
.font(.subheadline)
.font(.footnote)
.font(.caption)
.font(.caption2)
```

---

## Design System Patterns

### Color Extension

```swift
extension Color {
    static let brandPrimary = Color(hex: "#007AFF")
    static let brandSecondary = Color(hex: "#5856D6")
    static let brandSuccess = Color(hex: "#34C759")
    static let brandError = Color(hex: "#FF3B30")

    // Semantic colors
    static let cardBackground = Color(.secondarySystemBackground)
    static let textPrimary = Color(.label)
    static let textSecondary = Color(.secondaryLabel)
}

// Usage:
Text("Hello")
    .foregroundColor(.brandPrimary)
```

### Typography Extension

```swift
extension Font {
    static let displayLarge = Font.system(size: 34, weight: .bold)
    static let displayMedium = Font.system(size: 24, weight: .semibold)
    static let bodyLarge = Font.system(size: 18, weight: .regular)
    static let bodyRegular = Font.system(size: 16, weight: .regular)
    static let caption = Font.system(size: 12, weight: .regular)
}

// Usage:
Text("Heading")
    .font(.displayLarge)
```

### Spacing Extension

```swift
extension CGFloat {
    static let spacingXS: CGFloat = 4
    static let spacingSM: CGFloat = 8
    static let spacingMD: CGFloat = 16
    static let spacingLG: CGFloat = 24
    static let spacingXL: CGFloat = 32
    static let spacing2XL: CGFloat = 48
}

// Usage:
VStack(spacing: .spacingLG) {
    // Content
}
```

### Reusable Components

```swift
struct PrimaryButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.headline)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 50)
        }
        .background(Color.brandPrimary)
        .cornerRadius(12)
    }
}

struct CardView<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .padding()
            .background(.ultraThinMaterial)
            .cornerRadius(12)
            .shadow(radius: 2)
    }
}

// Usage:
CardView {
    Text("Card content")
}
```

---

## Xcode Previews

### Basic Preview

```swift
struct ContentView: View {
    var body: some View {
        Text("Hello, World!")
    }
}

#Preview {
    ContentView()
}
```

### Multiple Previews

```swift
#Preview("Light Mode") {
    ContentView()
}

#Preview("Dark Mode") {
    ContentView()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    ContentView()
        .environment(\.sizeCategory, .accessibilityExtraLarge)
}

#Preview("iPhone SE") {
    ContentView()
        .previewDevice("iPhone SE (3rd generation)")
}

#Preview("iPad") {
    ContentView()
        .previewDevice("iPad Pro (12.9-inch) (6th generation)")
}
```

### Preview with Mock Data

```swift
struct Workout: Identifiable {
    let id = UUID()
    let name: String
    let duration: Int

    static let example = Workout(name: "Morning Run", duration: 30)
    static let examples = [
        Workout(name: "Morning Run", duration: 30),
        Workout(name: "Yoga Flow", duration: 45),
        Workout(name: "Weight Training", duration: 60)
    ]
}

#Preview {
    WorkoutList(workouts: Workout.examples)
}
```

---

## Frontend/Backend Separation

### What UI Designer Creates (Visual Only)

```swift
struct LoginView: View {
    var body: some View {
        VStack(spacing: 20) {
            Text("Welcome Back")
                .font(.largeTitle)
                .bold()

            TextField("Email", text: .constant(""))
                .textFieldStyle(.roundedBorder)

            SecureField("Password", text: .constant(""))
                .textFieldStyle(.roundedBorder)

            Button("Sign In") {
                // Empty - Mobile Dev adds logic
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
```

**Key patterns for UI Designer:**
- `.constant("")` for TextField/SecureField
- Empty closures `{}` for Button actions
- Static mock data for lists
- No `@State`, `@StateObject`, or `$` bindings

### What Mobile Dev Adds (Logic Layer)

```swift
struct LoginView: View {
    @StateObject private var viewModel = LoginViewModel()

    var body: some View {
        VStack(spacing: 20) {
            Text("Welcome Back")
                .font(.largeTitle)
                .bold()

            TextField("Email", text: $viewModel.email)  // Real binding
                .textFieldStyle(.roundedBorder)
                .autocapitalization(.none)
                .keyboardType(.emailAddress)

            SecureField("Password", text: $viewModel.password)  // Real binding
                .textFieldStyle(.roundedBorder)

            Button("Sign In") {
                Task { await viewModel.signIn() }  // Real logic
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.isLoading)

            if viewModel.isLoading {
                ProgressView()
            }
        }
        .padding()
        .alert("Error", isPresented: $viewModel.showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(viewModel.errorMessage)
        }
    }
}
```

---

## Common Patterns

### Cards

```swift
VStack(alignment: .leading, spacing: 12) {
    Text("Card Title")
        .font(.headline)

    Text("Card description goes here")
        .font(.subheadline)
        .foregroundColor(.secondary)
}
.padding()
.background(.ultraThinMaterial)
.cornerRadius(12)
.shadow(radius: 2)
```

### Forms

```swift
Form {
    Section("Profile") {
        TextField("Name", text: .constant(""))
        TextField("Email", text: .constant(""))
    }

    Section("Preferences") {
        Toggle("Notifications", isOn: .constant(false))
        Toggle("Dark Mode", isOn: .constant(false))
    }
}
```

### List with Custom Rows

```swift
List(workouts) { workout in
    HStack {
        Image(systemName: "figure.run")
            .font(.title2)
            .foregroundColor(.blue)

        VStack(alignment: .leading) {
            Text(workout.name)
                .font(.headline)
            Text("\(workout.duration) min")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }

        Spacer()

        Image(systemName: "chevron.right")
            .foregroundColor(.secondary)
    }
    .padding(.vertical, 4)
}
```

### Empty State

```swift
VStack(spacing: 16) {
    Image(systemName: "tray")
        .font(.system(size: 64))
        .foregroundColor(.secondary)

    Text("No Workouts Yet")
        .font(.title2)
        .bold()

    Text("Start your first workout to see it here")
        .font(.subheadline)
        .foregroundColor(.secondary)
        .multilineTextAlignment(.center)

    Button("Start Workout") {}
        .buttonStyle(.borderedProminent)
}
.padding()
```

---

## Quick Reference Cheat Sheet

| Concept | React Native | SwiftUI |
|---------|-------------|---------|
| **Container** | `<View>` | `VStack`, `HStack`, `ZStack` |
| **Text** | `<Text>` | `Text()` |
| **Image** | `<Image>` | `Image()` |
| **Button** | `<TouchableOpacity>` | `Button()` |
| **Input** | `<TextInput>` | `TextField()` |
| **List** | `<FlatList>` | `List()` |
| **Scroll** | `<ScrollView>` | `ScrollView` |
| **Padding** | `padding: 20` | `.padding(20)` |
| **Background** | `backgroundColor` | `.background()` |
| **Border Radius** | `borderRadius` | `.cornerRadius()` |
| **Font Size** | `fontSize` | `.font()` |
| **Color** | `color` | `.foregroundColor()` |
| **Flex** | `flexDirection: 'column'` | `VStack` |
| **Props** | `props.name` | `let name: String` |
| **Styling** | `style={}` | `.modifier()` |

---

## Learning Resources

**Official Apple Resources:**
- Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
- SwiftUI Tutorials: https://developer.apple.com/tutorials/swiftui
- SF Symbols App: Download from Apple Developer
- iOS Design Resources: https://developer.apple.com/design/resources/

**Huxley Resources:**
- Mobile App Workflow: `{{CATALYST_ROOT}}/global/docs/Mobile_App_Workflow.md`
- UI Designer Agent: `{{CATALYST_ROOT}}/.claude/agents/ui-designer.md`
- Mobile Dev Agent: `{{CATALYST_ROOT}}/.claude/agents/mobile-dev.md`

---

## 25-Minute Learning Path

**Basics (5 minutes):**
1. VStack, HStack, ZStack
2. Text, Image, Button
3. .padding(), .background(), .cornerRadius()

**Components (10 minutes):**
4. List, ScrollView
5. TextField, Toggle, Picker
6. NavigationStack, TabView

**Polish (10 minutes):**
7. SF Symbols
8. Materials (.ultraThinMaterial)
9. Previews (#Preview)

**You're now ready to design iOS apps in SwiftUI!**

---

*SwiftUI for UI Designers - Huxley Quick Reference*
*Last Updated: October 2025*
