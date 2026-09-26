# React Native + Swift Hybrid Development Patterns

## Overview

This document defines the standard patterns for building iOS apps that combine React Native (TypeScript) for rapid UI development with Swift for native iOS features. This is a production-proven practice used by Shopify, Meta, Discord, and Microsoft.

**The developer writes two languages: TypeScript and Swift. The frameworks handle everything in between.**

## Decision Framework

### When to Use Each Approach

| Project Type | Recommended Stack | Rationale |
|---|---|---|
| iOS app needing rapid prototyping + native features | **Expo + Expo Modules API** | Best of both worlds, minimal bridging complexity |
| iOS-only app needing maximum native polish | **Pure SwiftUI** | No bridging overhead, full platform access |
| Cross-platform app (iOS + Android) | **Expo + React Native** | Shared codebase with native escape hatches |
| Performance-critical native bridging | **Expo + Nitro Modules** | Direct C++↔Swift, no ObjC middleman |

### Default: Expo Modules API

**Expo Modules API is the default choice for native bridging.** It provides:
- Write Swift directly via `ModuleDefinition` — no manual Obj-C++ bridging headers
- SwiftUI views exposed via `@expo/ui/swift-ui` `<Host>` component
- Expo handles the adapter layer internally
- Works in both managed and bare workflows

**Use Nitro Modules only when:**
- Measured benchmarks show bridging overhead is the bottleneck
- Complex interop requires direct C++↔Swift (skip ObjC)
- Hot-path calls (animations, real-time processing) need maximum throughput


## Architecture: Three Patterns

### Pattern 1: Expo Modules API (Default — Recommended)

**When to use:** Most native module needs within an Expo project.

```
TypeScript (app code)
    ↕
Expo Modules API (auto-generated bridge)
    ↕
Swift Module (native logic)
```

**Swift module example:**
```swift
import ExpoModulesCore

public class LiquidGlassModule: Module {
  public func definition() -> ModuleDefinition {
    Name("LiquidGlass")

    Function("isSupported") {
      if #available(iOS 26, *) { return true }
      return false
    }

    View(LiquidGlassView.self) {
      Prop("effect") { (view, effect: String) in
        view.setEffect(effect)
      }
    }
  }
}
```

**No Obj-C++ bridging header needed.** Expo handles it.

### Pattern 2: Turbo Native Modules (Bare RN)

**When to use:** Bare React Native projects without Expo, or when Expo Modules API doesn't cover your use case.

```
TypeScript Codegen Spec
    ↕
Objective-C++ Adapter (thin glue)
    ↕
Swift Module (@objcMembers, NSObject)
```

**File structure:**
```
ios/
  AppName-Bridging-Header.h        # Exposes RN headers to Swift
  NativeMyModule.swift              # Pure Swift logic
  RCTNativeMyModule.mm              # Obj-C++ adapter (forwards calls)
```

**Critical requirements:**
- Swift class MUST inherit from `NSObject`
- Methods MUST have `@objc` or class must have `@objcMembers`
- Bridging header name MUST exactly match: `ExactAppName-Bridging-Header.h`
- Auto-generated Swift header import: `ExactAppName-Swift.h`
- After adding Swift files: run `pod install`
- After changing spec: re-run codegen

**Turbo Module Spec (TypeScript):**
```typescript
// specs/NativeMyModule.ts
import type { TurboModule } from 'react-native';
import { TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  doWork(input: string): Promise<string>;  // Async (recommended)
  getCount(): number;                       // Sync (use sparingly)
}

export default TurboModuleRegistry.getEnforcing<Spec>('MyModule');
```

**Swift Implementation:**
```swift
@objcMembers
class NativeMyModule: NSObject {
  static func requiresMainQueueSetup() -> Bool { false }

  func doWork(_ input: String,
              resolve: @escaping RCTPromiseResolveBlock,
              reject: @escaping RCTPromiseRejectBlock) {
    DispatchQueue.global(qos: .userInitiated).async {
      let result = self.processInput(input)
      resolve(result)
    }
  }

  func getCount() -> NSNumber {
    return NSNumber(value: 42)
  }
}
```

**Obj-C++ Adapter:**
```objc
// RCTNativeMyModule.mm
#import "AppName-Swift.h"
#import <AppNameSpec/AppNameSpec.h>

@interface RCTNativeMyModule : NSObject <NativeMyModuleSpec>
@end

@implementation RCTNativeMyModule {
  NativeMyModule *_swiftModule;
}

- (instancetype)init {
  self = [super init];
  _swiftModule = [[NativeMyModule alloc] init];
  return self;
}

- (void)doWork:(NSString *)input
       resolve:(RCTPromiseResolveBlock)resolve
        reject:(RCTPromiseRejectBlock)reject {
  [_swiftModule doWork:input resolve:resolve reject:reject];
}

- (NSNumber *)getCount {
  return [_swiftModule getCount];
}

@end
```

### Pattern 3: Embedding SwiftUI Views (Fabric Native Components)

**When to use:** Rendering SwiftUI views (like Liquid Glass) inside React Native's view hierarchy.

```
React Component (JSX)
    ↕
Codegen Component Spec
    ↕
ViewManager / ComponentView (.mm)
    ↕
SwiftUI Provider (UIHostingController wrapper)
    ↕
Pure SwiftUI View
```

**The key mechanism:** `UIHostingController` wraps SwiftUI views inside UIKit, which React Native can render.

**SwiftUI Provider:**
```swift
import SwiftUI

class LiquidGlassProvider: UIView {
  private var hostingController: UIHostingController<LiquidGlassContent>?

  @objc var effect: String = "regular" {
    didSet { updateView() }
  }

  override init(frame: CGRect) {
    super.init(frame: frame)
    setupHostingController()
  }

  private func setupHostingController() {
    let content = LiquidGlassContent(effect: effect)
    let host = UIHostingController(rootView: content)
    host.view.translatesAutoresizingMaskIntoConstraints = false
    addSubview(host.view)
    NSLayoutConstraint.activate([
      host.view.topAnchor.constraint(equalTo: topAnchor),
      host.view.bottomAnchor.constraint(equalTo: bottomAnchor),
      host.view.leadingAnchor.constraint(equalTo: leadingAnchor),
      host.view.trailingAnchor.constraint(equalTo: trailingAnchor),
    ])
    hostingController = host
  }

  private func updateView() {
    hostingController?.rootView = LiquidGlassContent(effect: effect)
  }
}

struct LiquidGlassContent: View {
  let effect: String

  var body: some View {
    if #available(iOS 26, *) {
      RoundedRectangle(cornerRadius: 20)
        .glassEffect(.regular)
    } else {
      RoundedRectangle(cornerRadius: 20)
        .fill(.ultraThinMaterial)
    }
  }
}
```

## Liquid Glass Integration

### Option A: `@callstack/liquid-glass` (Bare RN)
```bash
npm install @callstack/liquid-glass
```
- `LiquidGlassView` — individual glass surface
- `LiquidGlassContainerView` — groups elements for morphing
- Requires New Architecture (Fabric)

### Option B: `expo-glass-effect` (Expo — Recommended)
```bash
npx expo install expo-glass-effect
```
- Uses `UIVisualEffectView` under the hood
- `isGlassEffectAPIAvailable` for runtime detection
- Zero bridging code needed

### Option C: Custom SwiftUI `.glassEffect()` via Expo UI
```tsx
import { Host } from '@expo/ui/swift-ui';
// SwiftUI's native .glassEffect() modifier available through Expo UI
```

## Pattern 4: Custom SwiftUI View via Expo Modules API (MOST COMMON HYBRID PATTERN)

**When to use:** You need a custom SwiftUI view (not covered by `@expo/ui/swift-ui` pre-built components) exposed as a React Native component inside an Expo project. This combines ExpoView + UIHostingController + SwiftUI.

**This is the pattern the Mobile Dev agent should use for requests like "build a custom liquid glass menu bar" in an Expo RN project.**

### Step 1: Scaffold the Local Module

```bash
npx create-expo-module@latest --local
# Name it: liquid-glass-menu
# This creates modules/liquid-glass-menu/ with scaffold files
```

File structure after scaffold:
```
modules/
  liquid-glass-menu/
    expo-module.config.json      # Autolinking config
    index.ts                     # Re-exports
    src/
      LiquidGlassMenuModule.ts   # requireNativeModule wrapper
      LiquidGlassMenuView.tsx    # React component wrapper
    ios/
      LiquidGlassMenuModule.swift  # Module definition
      LiquidGlassMenuView.swift    # ExpoView + UIHostingController
```

### Step 2: Write the Expo Module Definition (Swift)

```swift
// modules/liquid-glass-menu/ios/LiquidGlassMenuModule.swift
import ExpoModulesCore

public class LiquidGlassMenuModule: Module {
  public func definition() -> ModuleDefinition {
    Name("LiquidGlassMenu")

    View(LiquidGlassMenuView.self) {
      Prop("items") { (view, items: [[String: String]]) in
        view.updateItems(items)
      }

      Prop("selectedIndex") { (view, index: Int) in
        view.updateSelectedIndex(index)
      }

      Events("onItemSelected")
    }
  }
}
```

### Step 3: Write the ExpoView + UIHostingController Bridge (Swift)

**This is the key file — it bridges ExpoView (UIKit) to SwiftUI via UIHostingController.**

```swift
// modules/liquid-glass-menu/ios/LiquidGlassMenuView.swift
import ExpoModulesCore
import SwiftUI

class LiquidGlassMenuView: ExpoView {
  let onItemSelected = EventDispatcher()

  private var hostingController: UIHostingController<LiquidGlassMenuContent>?
  private var menuItems: [MenuItem] = []
  private var currentSelectedIndex: Int = 0

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    setupHostingController()
  }

  // Clean up hosting controller to prevent retain cycles
  override func removeFromSuperview() {
    hostingController?.view.removeFromSuperview()
    hostingController = nil
    super.removeFromSuperview()
  }

  private func setupHostingController() {
    let content = LiquidGlassMenuContent(
      items: menuItems,
      selectedIndex: currentSelectedIndex,
      onSelect: { [weak self] index in
        self?.onItemSelected(["index": index])
      }
    )
    let host = UIHostingController(rootView: content)
    host.view.backgroundColor = .clear
    host.view.translatesAutoresizingMaskIntoConstraints = false
    addSubview(host.view)
    NSLayoutConstraint.activate([
      host.view.topAnchor.constraint(equalTo: topAnchor),
      host.view.bottomAnchor.constraint(equalTo: bottomAnchor),
      host.view.leadingAnchor.constraint(equalTo: leadingAnchor),
      host.view.trailingAnchor.constraint(equalTo: trailingAnchor),
    ])
    hostingController = host
  }

  func updateItems(_ items: [[String: String]]) {
    menuItems = items.compactMap { dict in
      guard let label = dict["label"], let icon = dict["icon"] else { return nil }
      return MenuItem(label: label, icon: icon)
    }
    refreshHostedView()
  }

  func updateSelectedIndex(_ index: Int) {
    currentSelectedIndex = index
    refreshHostedView()
  }

  private func refreshHostedView() {
    hostingController?.rootView = LiquidGlassMenuContent(
      items: menuItems,
      selectedIndex: currentSelectedIndex,
      onSelect: { [weak self] index in
        self?.onItemSelected(["index": index])
      }
    )
  }
}

// MARK: - Data Model

struct MenuItem {
  let label: String
  let icon: String
}

// MARK: - Pure SwiftUI View (this is where you write real SwiftUI)

struct LiquidGlassMenuContent: View {
  let items: [MenuItem]
  let selectedIndex: Int
  let onSelect: (Int) -> Void

  var body: some View {
    HStack(spacing: 0) {
      ForEach(Array(items.enumerated()), id: \.offset) { index, item in
        Button {
          onSelect(index)
        } label: {
          VStack(spacing: 4) {
            Image(systemName: item.icon)
              .font(.system(size: 20))
              .symbolEffect(.bounce, value: selectedIndex == index)
            Text(item.label)
              .font(.caption2)
          }
          .frame(maxWidth: .infinity)
          .padding(.vertical, 8)
          .foregroundStyle(selectedIndex == index ? .primary : .secondary)
        }
      }
    }
    .padding(.horizontal, 8)
    .padding(.vertical, 4)
    .applyGlassEffect()
  }
}

extension View {
  @ViewBuilder
  func applyGlassEffect() -> some View {
    if #available(iOS 26, *) {
      self.glassEffect(.regular.interactive, in: .capsule)
    } else {
      self
        .background(.ultraThinMaterial, in: Capsule())
    }
  }
}
```

### Step 4: Write the TypeScript Wrapper

```typescript
// modules/liquid-glass-menu/src/LiquidGlassMenuView.tsx
import { ViewProps } from 'react-native';
import { requireNativeViewManager } from 'expo-modules-core';
import * as React from 'react';

export type MenuItem = {
  label: string;
  icon: string; // SF Symbol name
};

export type LiquidGlassMenuProps = {
  items: MenuItem[];
  selectedIndex: number;
  onItemSelected?: (event: { nativeEvent: { index: number } }) => void;
} & ViewProps;

const NativeView: React.ComponentType<LiquidGlassMenuProps> =
  requireNativeViewManager('LiquidGlassMenu');

export default function LiquidGlassMenu(props: LiquidGlassMenuProps) {
  return <NativeView {...props} />;
}
```

### Step 5: Configure Autolinking

```json
// modules/liquid-glass-menu/expo-module.config.json
{
  "ios": {
    "modules": ["LiquidGlassMenuModule"]
  }
}
```

Ensure `package.json` has the modules directory configured:
```json
{
  "expo": {
    "autolinking": {
      "nativeModulesDir": "./modules"
    }
  }
}
```

### Step 6: Use in React Native

```tsx
// app/index.tsx (or any screen)
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import LiquidGlassMenu from '../modules/liquid-glass-menu';

const MENU_ITEMS = [
  { label: 'Home', icon: 'house.fill' },
  { label: 'Search', icon: 'magnifyingglass' },
  { label: 'Profile', icon: 'person.fill' },
  { label: 'Settings', icon: 'gearshape.fill' },
];

export default function HomeScreen() {
  const [selectedTab, setSelectedTab] = useState(0);

  return (
    <View style={styles.container}>
      {/* Screen content */}

      <LiquidGlassMenu
        style={styles.menuBar}
        items={MENU_ITEMS}
        selectedIndex={selectedTab}
        onItemSelected={({ nativeEvent: { index } }) => setSelectedTab(index)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  menuBar: { position: 'absolute', bottom: 34, left: 16, right: 16, height: 64 },
});
```

### Step 7: Build and Run

```bash
# Regenerate native project (picks up new module)
npx expo prebuild -p ios --clean

# Run in simulator
npx expo run:ios
```

### Key Points for This Pattern

- **ExpoView** is the bridge class — it's a UIView subclass that Expo knows how to manage
- **UIHostingController** is the adapter — it wraps SwiftUI into UIKit so ExpoView can host it
- **EventDispatcher** is how you send events back to React Native (maps to `onItemSelected` prop)
- **Prop()** closures are how React Native props flow INTO the Swift view
- **The SwiftUI view is pure SwiftUI** — write it exactly as you would in a native app
- **No Obj-C++ needed** — Expo Modules API handles the bridge layer internally
- After adding or changing native modules, run `npx expo prebuild -p ios --clean`

### Critical Gotchas (Codex-reviewed)

**1. Sizing — the #1 runtime bug:**
The SwiftUI view will collapse to zero size if React Native doesn't provide explicit dimensions. ALWAYS set `width` and `height` (or `flex`) on the RN side:
```tsx
// ✅ Explicit size — SwiftUI view renders correctly
<LiquidGlassMenu style={{ position: 'absolute', bottom: 34, left: 16, right: 16, height: 64 }} />

// ❌ No size — SwiftUI view collapses to 0×0
<LiquidGlassMenu />
```
If you need the SwiftUI view to size itself (intrinsic content size), override `intrinsicContentSize` in your ExpoView subclass:
```swift
override var intrinsicContentSize: CGSize {
  return hostingController?.view.intrinsicContentSize ?? .zero
}
```

**2. Lifecycle — clean up the hosting controller:**
Remove the hosting controller's view in `removeFromSuperview()` to prevent retain cycles:
```swift
override func removeFromSuperview() {
  hostingController?.view.removeFromSuperview()
  hostingController = nil
  super.removeFromSuperview()
}
```

**3. Dark Mode and Dynamic Type:**
UIHostingController inherits the trait collection from its parent, but you must ensure it propagates. Set `overrideUserInterfaceStyle = .unspecified` (the default) on the hosting controller — never hardcode `.light` or `.dark`. SwiftUI's `@Environment(\.colorScheme)` and `@Environment(\.dynamicTypeSize)` will then work automatically.

**4. iOS availability guards:**
`.glassEffect()` requires iOS 26+. ALWAYS use `#available` guards with a sensible fallback:
```swift
if #available(iOS 26, *) {
  self.glassEffect(.regular)
} else {
  self.background(.ultraThinMaterial, in: Capsule())
}
```

**5. Expo Go is NOT compatible with custom native modules:**
Custom Expo Modules require a **development build**, not Expo Go:
```bash
# Create a dev build (replaces Expo Go)
npx expo run:ios          # Local build (recommended)
# OR
eas build --profile development --platform ios  # Cloud build
```
The app will crash in Expo Go with "Module not found" if you try to load a custom native module.

**6. State management across the bridge — one-way data flow:**
Props flow from React → Swift. Events flow from Swift → React. Never try to sync state bidirectionally.
```
React state (useState/Zustand) ──props──> ExpoView ──UIHostingController──> SwiftUI View
                                                                              │
React callback (onItemSelected) <──EventDispatcher── ExpoView <───onSelect────┘
```
If you need complex state, keep it in React and pass it down as props. The SwiftUI view should be a **pure rendering layer** — it receives data and emits events, nothing else.

**7. Thread safety:**
Expo Module `Prop()` closures run on the main thread by default, which is correct for UIKit/SwiftUI updates. If you need background work, use `AsyncFunction()` and dispatch to main for UI updates:
```swift
AsyncFunction("loadData") { [weak self] in
  let data = try await fetchFromNetwork()
  await MainActor.run {
    self?.updateItems(data)
  }
}
```

### Build Workflow for Custom Modules

```bash
# First time (or after changing native module structure)
npx expo prebuild -p ios --clean

# Run in simulator
npx expo run:ios

# After changing ONLY Swift code (no structural changes)
# The app will hot-reload if Metro is running, but native changes need rebuild:
npx expo run:ios

# After changing expo-module.config.json or adding new modules
npx expo prebuild -p ios --clean && npx expo run:ios

# Reset everything if confused
rm -rf ios/ && npx expo prebuild -p ios --clean && npx expo run:ios
```

## Type Conversion Reference

When using Turbo Modules (Pattern 2), types convert through layers:

| TypeScript | C++ (Codegen) | Objective-C | Swift |
|---|---|---|---|
| `string` | `std::string` | `NSString *` | `String` |
| `number` | `double` | `NSNumber *` / `double` | `Double` / `NSNumber` |
| `boolean` | `bool` | `BOOL` | `Bool` |
| `Array<T>` | `std::vector<T>` | `NSArray *` | `[T]` |
| `Object` | `folly::dynamic` | `NSDictionary *` | `[String: Any]` |
| `Promise<T>` | callback pair | `RCTPromiseResolveBlock` + `RCTPromiseRejectBlock` | closures |

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Missing `@objc` on method | Method not found at runtime | Add `@objc` or `@objcMembers` to class |
| Pure Swift class (no NSObject) | Crash: unrecognized selector | Inherit from `NSObject` |
| Wrong bridging header name | Silent build failure | Must be exactly `AppName-Bridging-Header.h` |
| Forgot `pod install` after adding Swift | Build errors | Run `pod install` |
| Stale codegen | Cryptic type errors | Re-run codegen after spec changes |
| Blocking main thread in native | UI freezes | Use `DispatchQueue.global().async {}` |
| Strong reference cycle in timers | Memory leak | Use `[weak self]` in closures |
| Missing `@available` guard | Crash on older iOS | Wrap iOS 26+ APIs in `if #available` |

## Build Workflow

### Expo Project (Recommended)
```bash
# Create new project
npx create-expo-app MyApp --template tabs
cd MyApp

# Generate native project
npx expo prebuild -p ios --clean

# Run locally (dev)
npx expo run:ios

# Build for release (local, no EAS needed)
open ios/*.xcworkspace
# Xcode → Archive → Distribute
```

### Bare React Native
```bash
npx @react-native-community/cli init MyApp
cd MyApp

# After adding native modules
cd ios && pod install && cd ..

# Run
npx react-native run-ios

# Build for release
open ios/*.xcworkspace
# Xcode → Archive → Distribute
```

## References

- [React Native: Turbo Modules with Swift](https://reactnative.dev/docs/the-new-architecture/turbo-modules-with-swift)
- [Expo: Modules API Overview](https://docs.expo.dev/modules/overview/)
- [Expo: SwiftUI Guide](https://docs.expo.dev/guides/expo-ui-swift-ui/)
- [Expo: Glass Effect](https://docs.expo.dev/versions/latest/sdk/glass-effect/)
- [Callstack: Exposing SwiftUI Views to RN](https://www.callstack.com/blog/exposing-swiftui-views-to-react-native-an-integration-guide)
- [Callstack: Liquid Glass in RN](https://www.callstack.com/blog/how-to-use-liquid-glass-in-react-native)
- [Nitro Modules](https://nitro.margelo.com/docs/comparison)
