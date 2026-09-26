# Huxley Mobile App Development Workflow

> **Note:** the design-system steps below reference a `capsules/design-system` capsule that the template does not include — create one first or skip those steps.

**Purpose:** Complete workflow for developing mobile applications in Huxley (any capsule)

**Supports:** Native iOS (Swift/SwiftUI) AND React Native (iOS + Android)

**Last Updated:** October 2025

---

## Overview

Huxley supports **two mobile development approaches**, each with optimized workflows:

### Native iOS (Swift/SwiftUI)
- **Best for:** iOS-only apps, maximum performance, platform-specific features
- **Tools:** Xcode, SwiftUI, InjectionIII, Xcode Previews
- **Example:** `example-mobile-capsule` capsule

### React Native (Cross-Platform)
- **Best for:** iOS + Android from one codebase, web sharing, rapid iteration
- **Tools:** React Native, Storybook, Expo (optional)
- **Example:** Future mobile capsules

---

## Technology Stack Matrix

| Feature | Native iOS (Swift) | React Native |
|---------|-------------------|--------------|
| **Languages** | Swift 5.9+ | JavaScript/TypeScript |
| **UI Framework** | SwiftUI | React Native |
| **Platforms** | iOS only | iOS + Android (+ Web*) |
| **Component Library** | Built-in SwiftUI | NativeBase, React Native Paper, Tamagui |
| **Component Isolation** | Xcode Previews | Storybook (native + web) |
| **Hot Reloading** | InjectionIII (30x faster) | Built-in Fast Refresh |
| **Design Tool** | Huxley Design Studio | Huxley Design Studio |
| **Design Extraction** | SwiftUI export adapter | React export adapter |
| **IDE** | Xcode 15+ | VS Code, Cursor |
| **Documentation** | Apple DocC | Storybook Docs |
| **Performance** | Native (best) | Near-native (95%+) |
| **App Size** | Smaller | Larger (includes JS runtime) |

---

## Common Tools (Both Approaches)

### ✅ Design & Mockups

**Huxley Design Studio** (`https://design-studio.localhost`)
- **Why:** Complete visual design-to-code workflow
- **Components:**
  - Plasmic Studio → Visual component builder
  - App Flow Canvas → Screen flows (tldraw)
  - Mood Board → Inspiration (tldraw)
  - Design Tokens → `tokens/design-language.json`
- **Export:** React components, SwiftUI views, or static assets
- **Cost:** $0 (self-hosted, open-source)

### ✅ Design Resources

**Reference Libraries:**
- **Apple HIG:** iOS 18+ design patterns
- **Material Design 3:** Android design system
- **Mobbin:** Real app screenshots (mobbin.com)
- **Figma Community:** View iOS/Material kits for reference

**Component Sources:**
- **Native iOS:** Built-in SwiftUI components
- **React Native:** NativeBase, React Native Paper, Tamagui, gluestack-ui

---

## Workflow 1: Native iOS (Swift/SwiftUI)

**When to use:** iOS-only app, cutting-edge iOS features (widgets, Live Activities), maximum performance, platform-specific integrations

### Technology Stack

```
Development:
├─ Swift 5.9+ (Language)
├─ SwiftUI (UI Framework)
├─ Xcode 15+ (IDE)
└─ iOS 17+ (Target)

Visual Design Tools:
├─ Xcode Previews (PRIMARY: Instant visual iteration)
├─ InjectionIII (Hot reload: 60s → 2s for full app)
└─ Huxley Design Studio (Design-to-code: Plasmic Studio + tldraw canvases)

Documentation:
└─ Apple DocC (API documentation)
```

### Development Process

#### Phase 1: Visual Design in SwiftUI (UI Designer in Xcode)

**Who:** 📐 UI Designer

**IMPORTANT:** For iOS projects, UI Designer designs directly in SwiftUI using Xcode Previews. This eliminates translation layers and provides instant visual feedback.

**Why SwiftUI for UI Designer:**
- Declarative syntax similar to React (components, composition, state)
- Xcode Previews = instant visual feedback (no compilation needed)
- Designs in the target language (no HTML → Swift translation)
- Access to native iOS features (SF Symbols, materials, effects)
- Frontend/backend separation (UI structure separate from logic)

1. **Set up Xcode project:**
   - Use linked Xcode project in capsule (auto-created by Mobile Dev)
   - Or create new project: File → New → Project → iOS App
   - Set deployment target: iOS 17+ (for latest features)

2. **Design components in SwiftUI with Xcode Previews:**

   **Example: Button Component**
   ```swift
   import SwiftUI

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
           .background(Color.blue)
           .cornerRadius(12)
       }
   }

   // Xcode Previews for instant visual feedback
   #Preview("Default") {
       PrimaryButton(title: "Sign In", action: {})
           .padding()
   }

   #Preview("Light Mode") {
       PrimaryButton(title: "Sign In", action: {})
           .padding()
           .preferredColorScheme(.light)
   }

   #Preview("Dark Mode") {
       PrimaryButton(title: "Sign In", action: {})
           .padding()
           .preferredColorScheme(.dark)
   }
   ```

   **The Preview pane in Xcode shows all variants side-by-side instantly.**

3. **Design screens and layouts:**

   **Example: Dashboard Screen**
   ```swift
   import SwiftUI

   struct DashboardView: View {
       var body: some View {
           NavigationStack {
               ScrollView {
                   VStack(spacing: 20) {
                       // Header
                       HStack {
                           VStack(alignment: .leading) {
                               Text("Welcome back")
                                   .font(.subheadline)
                                   .foregroundColor(.secondary)
                               Text("Tyler")
                                   .font(.title)
                                   .bold()
                           }
                           Spacer()
                           Image(systemName: "bell.fill")
                               .font(.title2)
                               .foregroundColor(.blue)
                       }
                       .padding()

                       // Stats Card
                       StatsCard(
                           title: "Steps Today",
                           value: "8,432",
                           icon: "figure.walk"
                       )

                       // Action Button
                       PrimaryButton(title: "Start Workout", action: {})
                   }
               }
               .navigationTitle("Dashboard")
           }
       }
   }

   #Preview {
       DashboardView()
   }
   ```

4. **Use mock data for visual design:**
   ```swift
   // Create mock data structures
   struct Workout: Identifiable {
       let id = UUID()
       let name: String
       let duration: Int

       static let example = Workout(name: "Morning Run", duration: 30)
       static let examples = [
           Workout(name: "Morning Run", duration: 30),
           Workout(name: "Yoga Session", duration: 45),
           Workout(name: "Weight Training", duration: 60)
       ]
   }

   // Use in previews
   #Preview {
       WorkoutList(workouts: Workout.examples)
   }
   ```

5. **Iterate visually with Xcode Previews:**
   - Change code → Preview updates instantly
   - Test Light/Dark mode side-by-side
   - Preview on different devices (iPhone, iPad)
   - Interactive previews (tap buttons, scroll lists)
   - No compilation needed for preview updates

6. **Design all component states:**
   ```swift
   #Preview("Button States") {
       VStack(spacing: 20) {
           PrimaryButton(title: "Default", action: {})
           PrimaryButton(title: "Pressed", action: {})
               .opacity(0.8)
           PrimaryButton(title: "Disabled", action: {})
               .disabled(true)
               .opacity(0.5)
       }
       .padding()
   }
   ```

7. **Optional: Document in Design Studio (after visual approval):**
   - Export SwiftUI components via Plasmic Studio
   - Document in Docusaurus (`/design-system`)
   - Create design tokens (`tokens/design-language.json`)
   - Share Design Studio URL with stakeholders

#### Phase 2: Add Functionality (Mobile Dev)

**Who:** 📱 Mobile Dev

**Receives from UI Designer:**
- SwiftUI components (visual structure, no logic)
- Mock data structures
- Component previews showing all states
- Design system implementation (colors, fonts, spacing)

**Mobile Dev adds the logic layer:**

1. **Receive UI Designer's SwiftUI code:**
   - Review SwiftUI components in Xcode
   - Test all Previews to understand visual design
   - Identify where logic needs to be added

2. **Add state management and logic:**

   **Before (UI Designer's visual component):**
   ```swift
   struct WorkoutList: View {
       let workouts: [Workout]  // Static mock data

       var body: some View {
           List(workouts) { workout in
               WorkoutCard(workout: workout)
           }
       }
   }
   ```

   **After (Mobile Dev adds logic):**
   ```swift
   struct WorkoutList: View {
       @StateObject private var viewModel = WorkoutViewModel()  // Logic layer

       var body: some View {
           List(viewModel.workouts) { workout in  // Dynamic data
               WorkoutCard(workout: workout)
                   .onTapGesture {
                       viewModel.selectWorkout(workout)  // Business logic
                   }
           }
           .onAppear {
               viewModel.loadWorkouts()  // Data fetching
           }
           .alert("Error", isPresented: $viewModel.showError) {
               Button("OK", role: .cancel) {}
           } message: {
               Text(viewModel.errorMessage)  // Error handling
           }
       }
   }
   ```

3. **Create ViewModel layer (MVVM pattern):**
   ```swift
   @MainActor
   class WorkoutViewModel: ObservableObject {
       @Published var workouts: [Workout] = []
       @Published var showError = false
       @Published var errorMessage = ""

       private let apiService = APIService()

       func loadWorkouts() async {
           do {
               workouts = try await apiService.fetchWorkouts()
           } catch {
               errorMessage = error.localizedDescription
               showError = true
           }
       }

       func selectWorkout(_ workout: Workout) {
           // Navigation or detail logic
       }
   }
   ```

4. **Setup InjectionIII for fast iteration (one-time):**
   - Add package: `https://github.com/krzysztofzablocki/Inject`
   - Update Views: `import Inject`, `@ObserveInjection var inject`, `.enableInjection()`

**Understanding Your Iteration Tools:**

Huxley iOS workflow uses **both** Xcode Previews AND InjectionIII - they complement each other:

| Tool | Purpose | Best For | Speed |
|------|---------|----------|-------|
| **Xcode Previews** | Component isolation & design | Designing new components, testing variants, accessibility checks | Instant (in canvas) |
| **InjectionIII** | Full app hot reloading | Testing in app context, navigation flows, real state/data | 2s (vs 60s rebuild) |

**When to use each:**

- **Xcode Previews** → Designing `Button` component with 5 variants side-by-side
- **InjectionIII** → Testing how `Button` looks/behaves in actual login screen with navigation

**They work together:**
```swift
import SwiftUI
import Inject  // For InjectionIII

struct ContentView: View {
    @ObserveInjection var inject  // InjectionIII hook

    var body: some View {
        VStack {
            Text("Hello, world!")
        }
        .enableInjection()  // InjectionIII hook
    }
}

// Xcode Previews (component isolation)
#Preview("Light Mode") {
    ContentView()
}

#Preview("Dark Mode") {
    ContentView()
        .preferredColorScheme(.dark)
}
```

**Recommended workflow pattern:**
```
Component Design (Xcode Previews)
├─ Design Button in isolation
├─ Test variants (primary, secondary, disabled)
├─ Check with different text lengths
└─ Verify accessibility

↓ (once design is solid)

Integration Testing (InjectionIII)
├─ Add Button to login screen
├─ Test in actual navigation flow
├─ Tweak spacing in real context
└─ Edit → Save → See in 2s (no rebuild)
```

2. **Fast iteration loop (InjectionIII):**
   ```
   Run app ONCE (Cmd+R)
   ↓
   Navigate to screen
   ↓
   Edit Swift code
   ↓
   Save (Cmd+S) → See changes in 2s
   ↓
   Repeat (no rebuilding!)
   ```

3. **Component design patterns (Xcode Previews):**

   Use Previews to design components in isolation before integration:

   ```swift
   #Preview("Default") {
       MyComponent()
   }

   #Preview("Dark Mode") {
       MyComponent()
           .preferredColorScheme(.dark)
   }

   #Preview("With Long Text") {
       MyComponent(title: "Very Long Title That Might Wrap")
   }

   #Preview("Disabled State") {
       MyComponent(isEnabled: false)
   }
   ```

   **Tip:** Design component variants side-by-side in Previews, then use InjectionIII to test integration.

5. **Add networking and data persistence:**
   ```swift
   // API Service
   actor APIService {
       func fetchWorkouts() async throws -> [Workout] {
           let url = URL(string: "https://api.example.com/workouts")!
           let (data, _) = try await URLSession.shared.data(from: url)
           return try JSONDecoder().decode([Workout].self, from: data)
       }
   }

   // Core Data persistence (if needed)
   @MainActor
   class PersistenceController {
       static let shared = PersistenceController()
       let container: NSPersistentContainer
       // ... Core Data setup
   }
   ```

6. **Add navigation and routing:**
   ```swift
   enum Route: Hashable {
       case dashboard
       case workoutDetail(Workout)
       case settings
   }

   struct AppCoordinator: View {
       @State private var path = NavigationPath()

       var body: some View {
           NavigationStack(path: $path) {
               DashboardView()  // UI Designer's visual component
                   .navigationDestination(for: Route.self) { route in
                       switch route {
                       case .dashboard:
                           DashboardView()
                       case .workoutDetail(let workout):
                           WorkoutDetailView(workout: workout)
                       case .settings:
                           SettingsView()
                       }
                   }
           }
       }
   }
   ```

### Frontend/Backend Separation in SwiftUI

**UI Designer is responsible for:**
- ✅ Visual structure (VStack, HStack, Lists, etc.)
- ✅ Component layout and spacing
- ✅ Colors, fonts, styling
- ✅ Component states (default, pressed, disabled)
- ✅ Mock data structures
- ✅ Xcode Previews for all variants
- ❌ NOT: Business logic, API calls, state management, navigation

**Mobile Dev is responsible for:**
- ✅ ViewModels (MVVM pattern)
- ✅ State management (@State, @StateObject, @Published)
- ✅ API integration and networking
- ✅ Data persistence (Core Data, UserDefaults)
- ✅ Navigation and routing
- ✅ Error handling and edge cases
- ❌ NOT: Visual design changes (delegate back to UI Designer)

**Handoff protocol:**
1. UI Designer commits SwiftUI components with Previews
2. UI Designer shows visual design in Xcode to stakeholder
3. After visual approval, Mobile Dev adds logic layer
4. Mobile Dev does NOT change visual design without UI Designer approval
5. If design changes needed, Mobile Dev creates ticket for UI Designer

**Example handoff:**

```swift
// UI Designer creates this (visual only):
struct LoginView: View {
    var body: some View {
        VStack(spacing: 20) {
            TextField("Email", text: .constant(""))
                .textFieldStyle(.roundedBorder)
            SecureField("Password", text: .constant(""))
                .textFieldStyle(.roundedBorder)
            PrimaryButton(title: "Sign In", action: {})
        }
        .padding()
    }
}

// Mobile Dev adds logic (keeps visual intact):
struct LoginView: View {
    @StateObject private var viewModel = LoginViewModel()

    var body: some View {
        VStack(spacing: 20) {
            TextField("Email", text: $viewModel.email)  // Add binding
                .textFieldStyle(.roundedBorder)
                .autocapitalization(.none)  // Add behavior
                .keyboardType(.emailAddress)  // Add behavior

            SecureField("Password", text: $viewModel.password)  // Add binding
                .textFieldStyle(.roundedBorder)

            PrimaryButton(title: "Sign In") {  // Add action
                Task { await viewModel.signIn() }
            }

            if viewModel.isLoading {  // Add loading state
                ProgressView()
            }
        }
        .padding()
        .alert("Error", isPresented: $viewModel.showError) {  // Add error handling
            Button("OK", role: .cancel) {}
        } message: {
            Text(viewModel.errorMessage)
        }
    }
}
```

#### Phase 3: Validation

1. **Visual validation:**
   - Compare running app to UI Designer's Xcode Previews
   - Verify colors, spacing, typography match design system
   - Test Light/Dark mode
   - Test Dynamic Type scaling (all 11 sizes)
   - Verify on different iPhone/iPad sizes

2. **Functional testing:**
   - Test on real iPhone/iPad
   - Verify all interactions work (taps, swipes, gestures)
   - Test navigation flows
   - Test error states and edge cases
   - Verify loading states and empty states

3. **Accessibility testing:**
   - VoiceOver navigation works correctly
   - All interactive elements have labels
   - Dynamic Type scaling doesn't break layout
   - Touch targets meet 44pt minimum
   - Color contrast meets WCAG AA standards

### Performance: 30x Faster Iteration

- **Traditional:** Edit → Build → Run = 30-60s
- **With InjectionIII:** Edit → Save = 1-2s
- **Time saved:** 45-55 min/day

---

## Workflow 2: React Native (Cross-Platform)

**When to use:** iOS + Android from one codebase, team familiar with React, web sharing

### Technology Stack

```
Development:
├─ React Native 0.73+ (Framework)
├─ TypeScript 5+ (Language)
├─ VS Code / Cursor (IDE)
└─ iOS 17+ & Android 13+ (Targets)

Component Tools:
├─ Storybook 9+ (Component isolation)
│   ├─ Native mode (runs on device/simulator)
│   └─ Web mode (browser preview with 500+ addons)
├─ React Native Fast Refresh (Built-in hot reload)
└─ Huxley Design Studio (Design-to-code with React export adapter)

Component Libraries:
├─ NativeBase (Recommended default)
├─ React Native Paper (Material Design)
├─ Tamagui (Universal: mobile + web)
└─ gluestack-ui (shadcn-like for mobile)
```

### Development Process

#### Phase 1: Design (Huxley Design Studio)

**Who:** 📐 UI Designer

1. **Start Huxley Design Studio:**
   ```bash
   cd {{CATALYST_ROOT}}/capsules/design-system
   npm run dev:all
   # Access at https://design-studio.localhost
   ```

2. **Create mood board and app flows:**
   - Open Mood Board (`/moodboard`) to collect inspiration
   - Open App Flow Canvas (`/canvas`) to design screen flows
   - Add device frames: iOS (iPhone 15 Pro) & Android (Pixel 7)
   - Map navigation and user flows

3. **Define design tokens:**
   - Edit `capsules/design-system/tokens/design-language.json`
   - Specify colors, typography, spacing for both iOS and Android
   - Follow platform conventions (iOS HIG vs Material Design)
   - Define Light + Dark mode variants

4. **Design components in Plasmic Studio:**
   - Open Plasmic Studio (`/studio`)
   - Build components with drag-and-drop
   - Create variants (primary, secondary, disabled)
   - Design all states (default, hover, active, loading)

5. **Export to React Native:**
   ```bash
   # Export all components to React
   curl -X POST https://design-studio.localhost/api/export/project \
     -H "Content-Type: application/json" \
     -d '{"adapter": "react", "capsule": "my-rn-app"}'

   # Output: capsules/design-system/generated/react/
   ```

#### Phase 2: Setup Storybook (one-time)

**Who:** 📱 Mobile Dev

1. **Initialize Storybook:**
   ```bash
   npx storybook@latest init
   # Select: "Both" (native + web)
   ```

2. **Project structure:**
   ```
   my-app/
   ├── src/
   │   ├── components/
   │   │   ├── Button.tsx
   │   │   ├── Button.stories.tsx      # Storybook stories
   │   │   └── Card.tsx
   │   ├── screens/
   │   └── App.tsx
   ├── .storybook/
   │   └── main.ts
   └── package.json
   ```

3. **Create component story:**
   ```tsx
   // components/Button.stories.tsx
   import type { Meta, StoryObj } from '@storybook/react';
   import { Button } from './Button';

   const meta: Meta<typeof Button> = {
     component: Button,
     title: 'Components/Button',
   };

   export default meta;
   type Story = StoryObj<typeof Button>;

   export const Primary: Story = {
     args: {
       variant: 'primary',
       children: 'Press Me',
     },
   };

   export const Secondary: Story = {
     args: {
       variant: 'secondary',
       children: 'Cancel',
     },
   };
   ```

#### Phase 3: Implementation (React Native + Storybook)

**Who:** 📐 UI Designer + 📱 Mobile Dev (Same codebase!)

**Component-First Development:**

1. **Build component in Storybook:**
   ```bash
   # Run Storybook (native mode)
   npm run storybook
   # Opens on device/simulator

   # OR run Storybook (web mode)
   npm run storybook-web
   # Opens in browser at localhost:6006
   ```

2. **Develop component in isolation:**
   ```tsx
   // components/Button.tsx
   import { Pressable, Text } from 'react-native';

   export const Button = ({ variant, children, onPress }) => (
     <Pressable
       onPress={onPress}
       style={styles[variant]}
     >
       <Text>{children}</Text>
     </Pressable>
   );
   ```

3. **Test all states in Storybook:**
   - Default
   - Pressed
   - Disabled
   - Loading
   - Light/Dark mode

4. **Use component in app:**
   ```tsx
   // screens/HomeScreen.tsx
   import { Button } from '../components/Button';

   export const HomeScreen = () => (
     <View>
       <Button variant="primary" onPress={handlePress}>
         Get Started
       </Button>
     </View>
   );
   ```

**Fast Iteration with Fast Refresh:**

```
Edit component
↓
Save file
↓
See changes in ~1s (built-in)
↓
No manual refresh needed!
```

#### Phase 4: Integration & Testing

1. **Run app with components:**
   ```bash
   # iOS
   npx react-native run-ios

   # Android
   npx react-native run-android
   ```

2. **Test on devices:**
   - iOS Simulator + real iPhone
   - Android Emulator + real Android device
   - Verify both platforms look correct

3. **Visual comparison:**
   - Screenshot app on both platforms
   - Compare to Figma designs (iOS vs Android)

---

## Storybook Benefits for React Native

### ✅ Component Isolation

Build and test components without running full app:
- Faster iteration
- Focus on one component at a time
- Test all states easily

### ✅ Dual Preview Modes

**Native Mode:**
- Runs on iOS Simulator / Android Emulator
- Full native fidelity
- Test device-specific features

**Web Mode:**
- Browser preview
- 500+ Storybook addons
- Accessibility testing
- Responsive design tools
- Faster than launching simulator

### ✅ Living Documentation

Storybook becomes your component library docs:
- Visual catalog of all components
- Code examples for each variant
- Interactive playground
- Share with team

### ✅ Design System Enforcement

- Theme components with design tokens from design system documentation
- Ensure consistency across screens
- Catch design deviations early

---

## Figma Design Handoff

### Design Export Workflow

**UI Designer:**
1. Create designs in Figma (use one of 3 free files)
2. Export screens and components as PNG/SVG
3. Document design system in markdown:
   - Colors (hex values, semantic naming, Light/Dark mode)
   - Typography (fonts, sizes, weights)
   - Spacing (8pt grid system)
   - Component specifications (states, variants)
4. Share Figma file link with Mobile Dev

**Mobile Dev:**
- Review Figma file for design reference
- Use exported PNG/SVG screens for implementation
- Follow design system documentation
- Build components matching the visual design
- Validate implementation against Figma designs

---

## Decision Matrix: Native iOS vs React Native

### Choose Native iOS (Swift/SwiftUI) when:

✅ **iOS-only app** (no Android needed)
✅ **Maximum performance** required
✅ **Platform-specific features** (e.g., WidgetKit, Live Activities, Apple Watch)
✅ **Smallest app size** matters
✅ **Latest iOS features** immediately (SwiftUI gets new APIs first)
✅ **100% native look and feel** required

**Trade-offs:**
- ❌ Android requires separate codebase
- ❌ Designers can't code directly (translation step)
- ❌ No Storybook (use Xcode Previews instead)

### Choose React Native when:

✅ **iOS + Android** from one codebase
✅ **Team knows React** (JavaScript/TypeScript)
✅ **Shared web version** (React Native Web)
✅ **Storybook component library** desired
✅ **Designers can code** (React components)
✅ **Rapid prototyping** across platforms

**Trade-offs:**
- ❌ Slightly larger app size
- ❌ 5% performance overhead (still fast!)
- ❌ Platform-specific features need native modules
- ❌ Debugging can be more complex

---

## Common Patterns

### Design System Documentation

**Both approaches:**

1. **Create design tokens:**
   ```
   Colors: #007AFF (Primary), #FF3B30 (Error), etc.
   Typography: SF Pro (iOS), Roboto (Android)
   Spacing: 8pt grid
   ```

2. **Document in markdown:**
   ```markdown
   # Design System

   ## Colors
   - Primary: #007AFF
   - Secondary: #5856D6

   ## Typography
   - Display: SF Pro Display, 34pt Bold
   - Body: SF Pro Text, 16pt Regular
   ```

3. **Implement in code:**

   **Swift:**
   ```swift
   // Utilities/Colors.swift
   extension Color {
       static let primary = Color(hex: "#007AFF")
       static let secondary = Color(hex: "#5856D6")
   }
   ```

   **React Native:**
   ```typescript
   // theme/colors.ts
   export const colors = {
     primary: '#007AFF',
     secondary: '#5856D6',
   };
   ```

### Component Documentation

**Swift (DocC):**
```swift
/// Primary action button
///
/// ## Example
/// ```swift
/// Button("Submit") { handleSubmit() }
/// ```
struct Button: View { }
```

**React Native (Storybook):**
```tsx
// Button.stories.tsx - Auto-generates docs
export const Primary: Story = {
  args: { children: 'Submit' },
};
```

---

## Capsule Setup Checklist

### Native iOS Capsule

```
my-ios-app/
├── CLAUDE.md                        # Capsule context
├── QUICKSTART.md                    # Fast setup guide
├── docs/
│   ├── MOBILE_WORKFLOW.md           # iOS-specific workflow
│   ├── INJECTION_SETUP.md           # InjectionIII guide
│   └── DOCC_SETUP.md                # Documentation setup
├── design/
│   └── [Figma exports]
└── src/
    └── MyApp.xcodeproj
```

**Setup:**
1. Add InjectionIII package
2. Update Views with hot reload hooks
3. Create Figma file
4. Document design system

### React Native Capsule

```
my-rn-app/
├── CLAUDE.md                        # Capsule context
├── QUICKSTART.md                    # Fast setup guide
├── docs/
│   ├── MOBILE_WORKFLOW.md           # React Native workflow
│   └── STORYBOOK_SETUP.md           # Storybook guide
├── design/
│   └── [Figma exports]
├── .storybook/
│   └── main.ts
├── src/
│   ├── components/
│   │   └── *.stories.tsx
│   └── App.tsx
└── package.json
```

**Setup:**
1. Initialize Storybook (native + web)
2. Create component stories
3. Create Figma file (iOS + Android)
4. Document design system

---

## Resources

### Tools & CLIs

- **Figma:** https://figma.com (design tool)
- **InjectionIII:** https://github.com/krzysztofzablocki/Inject
- **Storybook:** https://storybook.js.org/docs/react-native

### Design Resources

- **Apple HIG:** https://developer.apple.com/design/human-interface-guidelines
- **Material Design 3:** https://m3.material.io
- **Mobbin:** https://mobbin.com (real app screenshots)
- **Figma Community:** https://figma.com/community (reference only)

### Component Libraries

**Native iOS:**
- Built-in SwiftUI components

**React Native:**
- NativeBase: https://nativebase.io
- React Native Paper: https://reactnativepaper.com
- Tamagui: https://tamagui.dev
- gluestack-ui: https://gluestack.io

---

## FAQs

**Q: Can I use Storybook with Swift/SwiftUI?**
A: No. Storybook is for web/React Native only. Use Xcode Previews instead (same concept, native integration).

**Q: Should I use Expo with React Native?**
A: Optional. Expo simplifies setup and provides great DX. Use if you don't need custom native modules.

**Q: How do I share components between web and mobile?**
A: Use React Native Web + Tamagui. Write once, run on iOS, Android, and web.

**Q: Can UI Designer code React Native components?**
A: Yes! React Native uses JavaScript/TypeScript. UI Designer can build components directly in Storybook, Mobile Dev integrates them.

**Q: What about Flutter?**
A: Not currently supported in Huxley. Stick to Native iOS or React Native.

---

*Mobile App Development Workflow - Huxley Global Documentation*
*Last Updated: October 2025*
