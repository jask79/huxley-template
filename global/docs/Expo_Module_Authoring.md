# Expo Modules API — Authoring Custom Native Modules

## Overview

This document covers how to **write** custom Expo native modules in Swift (iOS) and Kotlin (Android) using the Expo Modules API `ModuleDefinition` DSL. This is the default bridging approach for Huxley hybrid RN+Swift projects.

**Key principle:** You write TypeScript + Swift. Expo handles the bridge layer. No Obj-C++ needed.

## Quick Start

### Scaffold a Local Module

```bash
# Create a local module inside your Expo project
npx create-expo-module@latest --local

# Run the app
npx expo run:ios
```

This creates a `modules/` directory with the module scaffolding. Local modules are auto-linked.

### Scaffold a Standalone Module (for reuse/npm)

```bash
npx create-expo-module@latest my-module
cd my-module/example
npx expo run:ios
```

## Module Definition DSL (Swift)

Every Expo module is a Swift class that extends `Module` and implements `definition()`:

```swift
import ExpoModulesCore

public class MyModule: Module {
  public func definition() -> ModuleDefinition {
    // All module components go here
  }
}
```

### Available Definition Components

| Component | Purpose | Thread |
|-----------|---------|--------|
| `Name("X")` | Module name for JS access | — |
| `Function("x") { }` | Synchronous function | JS thread |
| `AsyncFunction("x") { }` | Async function (returns Promise) | Background |
| `Property("x") { }` | Read-only property | JS thread |
| `Property("x").get {}.set {}` | Read/write property | JS thread |
| `Constant("x") { }` | Computed once, cached | JS thread |
| `Events("a", "b")` | Declare sendable events | — |
| `View(MyView.self) { }` | Register native view | — |
| `Class("X", MyClass.self) { }` | Expose shared object | — |
| `OnStartObserving { }` | First JS listener attached | — |
| `OnStopObserving { }` | Last JS listener removed | — |

## Pattern: Simple Function Module

**Swift (iOS):**
```swift
import ExpoModulesCore

public class ExpoSettingsModule: Module {
  public func definition() -> ModuleDefinition {
    Name("ExpoSettings")

    Function("getTheme") { () -> String in
      UserDefaults.standard.string(forKey: "theme") ?? "system"
    }

    Function("setTheme") { (theme: String) -> Void in
      UserDefaults.standard.set(theme, forKey: "theme")
    }
  }
}
```

**TypeScript wrapper:**
```typescript
import { NativeModule, requireNativeModule } from 'expo';

declare class ExpoSettingsModule extends NativeModule {
  getTheme: () => string;
  setTheme: (theme: string) => void;
}

export default requireNativeModule<ExpoSettingsModule>('ExpoSettings');
```

**Usage in React:**
```typescript
import ExpoSettings from './ExpoSettingsModule';

export function getTheme(): string {
  return ExpoSettings.getTheme();
}

export function setTheme(theme: string): void {
  ExpoSettings.setTheme(theme);
}
```

## Pattern: Module with Events

**Swift:**
```swift
import ExpoModulesCore

public class ExpoSettingsModule: Module {
  public func definition() -> ModuleDefinition {
    Name("ExpoSettings")

    Events("onChangeTheme")

    Function("setTheme") { (theme: String) -> Void in
      UserDefaults.standard.set(theme, forKey: "theme")
      sendEvent("onChangeTheme", [
        "theme": theme
      ])
    }

    Function("getTheme") { () -> String in
      UserDefaults.standard.string(forKey: "theme") ?? "system"
    }
  }
}
```

**TypeScript types:**
```typescript
export type Theme = 'light' | 'dark' | 'system';

export type ThemeChangeEvent = {
  theme: Theme;
};

export type ExpoSettingsModuleEvents = {
  onChangeTheme: (params: ThemeChangeEvent) => void;
};
```

**TypeScript module:**
```typescript
import { NativeModule, requireNativeModule } from 'expo';
import { ExpoSettingsModuleEvents, Theme } from './ExpoSettings.types';

declare class ExpoSettingsModule extends NativeModule<ExpoSettingsModuleEvents> {
  setTheme: (theme: Theme) => void;
  getTheme: () => Theme;
}

export default requireNativeModule<ExpoSettingsModule>('ExpoSettings');
```

**React usage with event listener:**
```typescript
import { EventSubscription } from 'expo-modules-core';
import ExpoSettingsModule from './ExpoSettingsModule';
import { ThemeChangeEvent } from './ExpoSettings.types';

export function addThemeListener(
  listener: (event: ThemeChangeEvent) => void
): EventSubscription {
  return ExpoSettingsModule.addListener('onChangeTheme', listener);
}
```

## Pattern: Enums with Enumerable

Use Swift enums conforming to `Enumerable` for type-safe values:

```swift
import ExpoModulesCore

public class ExpoSettingsModule: Module {
  public func definition() -> ModuleDefinition {
    Name("ExpoSettings")

    Events("onChangeTheme")

    Function("setTheme") { (theme: Theme) -> Void in
      UserDefaults.standard.set(theme.rawValue, forKey: "theme")
      sendEvent("onChangeTheme", [
        "theme": theme.rawValue
      ])
    }

    Function("getTheme") { () -> String in
      UserDefaults.standard.string(forKey: "theme") ?? Theme.system.rawValue
    }
  }

  enum Theme: String, Enumerable {
    case light
    case dark
    case system
  }
}
```

## Pattern: Native View Module

Expose a native UIKit/SwiftUI view to React Native:

**Swift module:**
```swift
import ExpoModulesCore

public class ExpoWebViewModule: Module {
  public func definition() -> ModuleDefinition {
    Name("ExpoWebView")

    View(ExpoWebView.self) {
      Events("onLoad")

      Prop("url") { (view, url: URL) in
        if view.webView.url != url {
          let urlRequest = URLRequest(url: url)
          view.webView.load(urlRequest)
        }
      }
    }
  }
}
```

**Swift view (extending ExpoView):**
```swift
import ExpoModulesCore
import WebKit

class ExpoWebView: ExpoView {
  let onLoad = EventDispatcher()
  lazy var webView = WKWebView()

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    addSubview(webView)
    // ... setup constraints
  }
}
```

**TypeScript wrapper:**
```typescript
import { ViewProps } from 'react-native';
import { requireNativeViewManager } from 'expo-modules-core';
import * as React from 'react';

export type Props = {
  url: string;
  onLoad?: (event: { url: string }) => void;
} & ViewProps;

const NativeView: React.ComponentType<Props> =
  requireNativeViewManager('ExpoWebView');

export default function ExpoWebView(props: Props) {
  return <NativeView {...props} />;
}
```

### View Definition Components

| Component | Purpose |
|-----------|---------|
| `Prop("name") { (view, value) in }` | Reactive property on the view |
| `Events("onX", "onY")` | View-bound callback events |
| `AsyncFunction("x") { (view) in }` | Method callable via React ref |
| `GroupView { }` | Groups child native views |

### View Events with EventDispatcher

```swift
class CameraView: ExpoView {
  let onCameraReady = EventDispatcher()

  func callOnCameraReady() {
    onCameraReady([
      "message": "Camera was mounted"
    ])
  }
}

class CameraViewModule: Module {
  public func definition() -> ModuleDefinition {
    View(CameraView.self) {
      Events("onCameraReady")
    }
  }
}
```

## Pattern: Shared Objects (Classes)

Expose Swift classes to JS with methods:

```swift
public final class SimpleImageModule: Module {
  public func definition() -> ModuleDefinition {
    Name("SimpleImageModule")

    AsyncFunction("createContextAsync") { (path: String) -> SimpleImageContext in
      return try SimpleImageContext(path: path)
    }

    Class("Context", SimpleImageContext.self) {
      Function("rotate") { (ctx, degrees: Double) -> SimpleImageContext in
        ctx.rotate(by: degrees)
        return ctx
      }

      Function("flipX") { (ctx: SimpleImageContext) -> SimpleImageContext in
        ctx.flipX()
        return ctx
      }

      AsyncFunction("renderAsync") { (ctx: SimpleImageContext) -> ImageRef in
        return ctx.render()
      }
    }
  }
}
```

## Pattern: System Event Observation

```swift
let CLIPBOARD_CHANGED_EVENT_NAME = "onClipboardChanged"

public class ClipboardModule: Module {
  public func definition() -> ModuleDefinition {
    Events(CLIPBOARD_CHANGED_EVENT_NAME)

    OnStartObserving {
      NotificationCenter.default.addObserver(
        self,
        selector: #selector(self.clipboardChangedListener),
        name: UIPasteboard.changedNotification,
        object: nil
      )
    }

    OnStopObserving {
      NotificationCenter.default.removeObserver(
        self,
        name: UIPasteboard.changedNotification,
        object: nil
      )
    }
  }

  @objc
  private func clipboardChangedListener() {
    sendEvent(CLIPBOARD_CHANGED_EVENT_NAME, [
      "contentTypes": availableContentTypes()
    ])
  }
}
```

## Pattern: Custom Type Conversion

Extend native types to conform to `Convertible`:

```swift
import ExpoModulesCore

extension CMTime: @retroactive Convertible {
  public static func convert(from value: Any?, appContext: AppContext) throws -> CMTime {
    if let seconds = value as? Double {
      return CMTime(seconds: seconds, preferredTimescale: .max)
    }
    throw Conversions.ConvertingException<CMTime>(value)
  }
}
```

## Pattern: Reading Native Config (Info.plist / AndroidManifest)

**Swift — Read from Info.plist:**
```swift
import ExpoModulesCore

public class ExpoNativeConfigurationModule: Module {
  public func definition() -> ModuleDefinition {
    Name("ExpoNativeConfiguration")

    Function("getApiKey") {
      return Bundle.main.object(forInfoDictionaryKey: "MY_CUSTOM_API_KEY") as? String
    }
  }
}
```

## Autolinking Configuration

Create `expo-module.config.json` at module root:

```json
{
  "ios": {
    "modules": ["MyModule"]
  },
  "android": {
    "modules": ["my.module.package.MyModule"]
  }
}
```

For local modules, set `nativeModulesDir` in package.json:

```json
{
  "expo": {
    "autolinking": {
      "nativeModulesDir": "./modules"
    }
  }
}
```

## Type Conversion: JS to Swift

| JavaScript | Swift |
|-----------|-------|
| `string` | `String` |
| `number` | `Int`, `Double`, `Float`, `CGFloat` |
| `boolean` | `Bool` |
| `null` | `nil` (Optional types) |
| `Array<T>` | `[T]` |
| `Record<string, T>` | `[String: T]` |
| `Promise<T>` | Return value from `AsyncFunction` |
| `URL` | `URL` |
| Custom enum | Conform to `Enumerable` |
| Custom type | Conform to `Convertible` |

## Function Limits

- Functions can accept up to **8 arguments** (generic limitation)
- `Function` runs synchronously on JS thread — keep fast
- `AsyncFunction` runs on background thread — use for I/O, computation
- View `AsyncFunction`s run on **UI thread** and receive the view as first arg

## Testing

### Generate Mocks

```bash
brew install sourcekitten
npx expo-modules-test-core generate-ts-mocks
```

### Jest Test

```javascript
import * as MyModule from '../MyModule';
import ExpoMyModule from '../ExpoMyModule';

describe('MyModule', () => {
  it('calls native module with correct parameters', async () => {
    await MyModule.doSomething('test-param');
    expect(ExpoMyModule.doSomething).toHaveBeenCalledWith('test-param');
  });
});
```

## File Structure

### Local Module (inside project)
```
modules/
  my-module/
    expo-module.config.json
    index.ts
    src/
      MyModule.ts          # TypeScript API
      MyModuleModule.ts    # requireNativeModule wrapper
      MyModule.types.ts    # Type definitions
    ios/
      MyModule.swift       # Swift implementation
    android/
      src/main/java/.../
        MyModule.kt        # Kotlin implementation
```

### Standalone Module (separate package)
```
my-module/
  package.json
  expo-module.config.json
  src/
    index.ts
    MyModule.ts
    MyModuleModule.ts
  ios/
    MyModule.swift
    MyModule.podspec
  android/
    build.gradle
    src/main/java/.../
      MyModule.kt
  example/                 # Test app
    app.json
    App.tsx
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Forgot `Name("X")` | Always set module name — JS uses it |
| Heavy work in `Function` | Use `AsyncFunction` for I/O |
| Missing `Convertible` conformance | Custom types need explicit conversion |
| Missing `expo-module.config.json` | Required for autolinking |
| Forgot `pod install` | Run after adding/changing iOS modules |
| Type mismatch JS↔Swift | Check type conversion table above |

## References

- [Expo: Module API Reference](https://docs.expo.dev/modules/module-api/)
- [Expo: Native Module Tutorial](https://docs.expo.dev/modules/native-module-tutorial/)
- [Expo: Native View Tutorial](https://docs.expo.dev/modules/native-view-tutorial/)
- [Expo: Existing Library Integration](https://docs.expo.dev/modules/existing-library/)
- [Expo: Config Plugin + Native Module Tutorial](https://docs.expo.dev/modules/config-plugin-and-native-module-tutorial/)
- [Expo: Shared Objects](https://docs.expo.dev/modules/shared-objects/)
