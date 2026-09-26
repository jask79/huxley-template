# Cross-Bridge Debugging Playbook

## Overview

Debugging hybrid React Native + Swift apps requires coordinating two runtimes (JavaScript + Native), two build systems (Metro + Xcode), and understanding where errors originate across the bridge. This playbook covers systematic approaches for each failure category.

## Architecture Context

```
JavaScript (Metro Bundler)
    ↕ JSI Bridge
Native Runtime (Xcode / iOS Simulator)
    ↕ Expo Modules API
Swift Module Code
```

Errors can occur at any layer. The key skill is identifying WHICH layer failed.

## Debugging Setup

### Terminal Layout (Recommended)

Run these simultaneously:
```bash
# Terminal 1: Metro bundler (JS errors surface here)
npx expo start

# Terminal 2: Native build (Swift compile errors surface here)
npx expo run:ios

# Terminal 3: Xcode console (native runtime crashes)
# Open via: open ios/*.xcworkspace
```

### Xcode Breakpoints for Native Code

1. Open `ios/*.xcworkspace` in Xcode
2. Navigate to your Swift module file
3. Set breakpoints on native functions
4. Run from Xcode (not Metro) to hit native breakpoints
5. Use Xcode's LLDB console for Swift debugging

### Metro Console for JS Errors

Metro surfaces JavaScript errors with stack traces. Look for:
- `TypeError: X.Y is not a function` — Module not linked
- `Error: requireNativeModule: "X" not found` — Missing autolinking config
- Bridge errors with `[native]` in stack — Error in native code

## Error Categories & Solutions

### Category 1: Module Not Found

**Symptom:** `requireNativeModule: "ModuleName" could not be found`

**Diagnosis checklist:**
1. Does `expo-module.config.json` exist at module root?
2. Does it list the correct module class name?
3. Did you run `npx expo prebuild --clean`?
4. Did you run `pod install` (bare RN) or `npx expo run:ios` (Expo)?
5. Does the `Name("X")` in Swift match the JS `requireNativeModule("X")`?

**Fix sequence:**
```bash
# Clean and rebuild
rm -rf ios/build ios/Pods
npx expo prebuild -p ios --clean
npx expo run:ios
```

### Category 2: Swift Compile Errors

**Symptom:** Build fails with Swift errors in Xcode

**Common causes:**
- Missing `import ExpoModulesCore`
- Module class not `public`
- Definition function not returning `ModuleDefinition`
- Type mismatch in Function closures

**Diagnosis:**
```bash
# Build with verbose output
npx expo run:ios 2>&1 | grep -i error
```

Or open Xcode and check the Issue Navigator (Cmd+5).

**Common Swift fixes:**
```swift
// WRONG: Missing public
class MyModule: Module {                    // Build error
  func definition() -> ModuleDefinition {   // Build error

// RIGHT: Must be public
public class MyModule: Module {
  public func definition() -> ModuleDefinition {
```

### Category 3: Runtime Type Mismatch

**Symptom:** Function call crashes or returns unexpected value

**Diagnosis:** Add logging on both sides:

**JavaScript side:**
```typescript
console.log('[JS] Calling native function with:', JSON.stringify(args));
try {
  const result = await MyModule.myFunction(...args);
  console.log('[JS] Native returned:', JSON.stringify(result));
} catch (e) {
  console.error('[JS] Native threw:', e.message);
}
```

**Swift side:**
```swift
Function("myFunction") { (input: String) -> String in
  print("[Native] Received: \(input)")
  let result = processInput(input)
  print("[Native] Returning: \(result)")
  return result
}
```

**Type conversion gotchas:**

| JS sends | Swift expects | Result |
|----------|---------------|--------|
| `42` | `Int` | Works |
| `42.0` | `Int` | May fail — use `Double` |
| `null` | `String` | Crash — use `String?` |
| `undefined` | Any non-optional | Crash — use Optional |
| `[1,"a"]` | `[Int]` | Crash — mixed array |
| `{a: 1}` | `[String: Any]` | Works |

### Category 4: View Not Rendering

**Symptom:** Native view component shows blank/zero-size

**Diagnosis checklist:**
1. Does the view have explicit dimensions in React Native style?
2. Is `requireNativeViewManager("X")` matching `Name("X")` in Swift?
3. On iOS, does the view class extend `ExpoView`?
4. Are constraints set up in the view's `init` or `layoutSubviews`?

**Common fix — explicit sizing:**
```typescript
// WRONG: No size
<MyNativeView />

// RIGHT: Explicit size
<MyNativeView style={{ width: 300, height: 200 }} />
```

### Category 5: Events Not Firing

**Symptom:** JS event listener never triggers

**Diagnosis checklist:**
1. Event name in `Events("onX")` matches JS listener name?
2. `EventDispatcher` property name matches the event name?
3. `sendEvent` called from correct thread?
4. JS listener registered before event fires?

**Pattern for reliable events:**
```swift
// Module definition
Events("onDataReceived")

// In your logic
sendEvent("onDataReceived", [
  "data": someValue
])
```

```typescript
// JS — register listener BEFORE triggering native action
const subscription = MyModule.addListener('onDataReceived', (event) => {
  console.log('Got:', event.data);
});

// Later: cleanup
subscription.remove();
```

### Category 6: Async Function Hangs

**Symptom:** Promise never resolves

**Diagnosis:**
- Is the native function actually returning?
- Is there a deadlock (dispatching to main thread from main thread)?
- Is an exception being swallowed?

**Fix — add timeout wrapper in JS:**
```typescript
function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  const timeout = new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error(`Native call timed out after ${ms}ms`)), ms)
  );
  return Promise.race([promise, timeout]);
}

// Usage
const result = await withTimeout(MyModule.heavyWork(input), 10000);
```

**Fix — ensure native function completes:**
```swift
AsyncFunction("heavyWork") { (input: String) -> String in
  // This runs on a background thread automatically
  // Make sure it actually returns and doesn't deadlock
  return performWork(input)
}
```

## Expo-Specific Debugging

### Prebuild Inspection

After `npx expo prebuild`, inspect generated native files:

```bash
# Check Info.plist for config plugin results
cat ios/MyApp/Info.plist | grep MY_CUSTOM

# Check Podfile for module linking
cat ios/Podfile | grep my-module

# Check autolinking
cat ios/Pods/Local\ Podspecs/*.podspec.json
```

### Module Autolinking Verification

```bash
# List all autolinked modules
npx expo-modules-autolinking resolve -p ios

# Verify specific module is linked
npx expo-modules-autolinking resolve -p ios | grep MyModule
```

### Clean Rebuild (Nuclear Option)

When nothing else works:
```bash
# Remove ALL generated native code
rm -rf ios android node_modules
npm install
npx expo prebuild --clean
npx expo run:ios
```

## Xcode + Metro Coordination

### Running Both Simultaneously

**Approach 1: Metro + Xcode (for native debugging)**
1. Start Metro: `npx expo start`
2. Open Xcode: `open ios/*.xcworkspace`
3. In Xcode, Run (Cmd+R) targeting simulator
4. Xcode builds native code, Metro serves JS bundle
5. Native breakpoints work in Xcode

**Approach 2: Expo CLI only (for JS debugging)**
1. Run: `npx expo run:ios`
2. Shake device / Cmd+D for dev menu
3. "Debug JS Remotely" for Chrome DevTools
4. JS breakpoints work in Chrome

### When to Use Which

| Need | Tool |
|------|------|
| Swift breakpoints | Xcode |
| JS breakpoints | Chrome DevTools via dev menu |
| Swift compile errors | Xcode Issue Navigator |
| JS runtime errors | Metro console |
| Native crash logs | Xcode console or `Console.app` |
| Module linking issues | `expo-modules-autolinking resolve` |
| Config plugin issues | Inspect `ios/` after prebuild |

## Logging Strategy

### Unified Log Pattern

Use consistent prefixes to correlate across layers:

```typescript
// JavaScript
console.log('[JS:MyFeature] Starting operation');
console.log('[JS:MyFeature] Calling native with:', data);
```

```swift
// Swift
print("[Native:MyFeature] Received call")
print("[Native:MyFeature] Processing: \(input)")
print("[Native:MyFeature] Returning: \(result)")
```

Then filter in terminal:
```bash
# In Metro output
# [JS:MyFeature] logs appear automatically

# In Xcode console, filter by:
# [Native:MyFeature]
```

### iOS System Logging (for production debugging)

```swift
import os.log

let logger = Logger(subsystem: "com.app.mymodule", category: "MyFeature")

AsyncFunction("process") { (input: String) -> String in
  logger.info("Processing input: \(input)")
  let result = doWork(input)
  logger.debug("Result: \(result)")
  return result
}
```

View with: `Console.app` → filter by subsystem

## Performance Debugging

### Identifying Bridge Bottlenecks

```typescript
// Measure native call round-trip time
const start = performance.now();
const result = await MyModule.heavyFunction(data);
const duration = performance.now() - start;
console.log(`[Perf] Native call took ${duration.toFixed(1)}ms`);
```

**Guidelines:**
- < 1ms: Sync function is fine
- 1-16ms: Consider async but acceptable
- > 16ms: Must be async (blocks frame at 60fps)
- > 100ms: Consider moving to background with progress events

### Avoiding Bridge Chatter

```typescript
// BAD: Many small bridge calls
for (const item of items) {
  await MyModule.processItem(item);  // N bridge crossings
}

// GOOD: Single batch call
await MyModule.processItems(items);  // 1 bridge crossing
```

## Common Pitfalls Quick Reference

| Symptom | Likely Cause | Quick Fix |
|---------|-------------|-----------|
| "Module not found" | Missing autolinking | `prebuild --clean` |
| Build fails in Xcode | Swift syntax / missing import | Check Xcode Issue Navigator |
| Function returns undefined | Type mismatch | Check type conversion table |
| View shows zero size | Missing style dimensions | Add explicit width/height |
| Event never fires | Name mismatch | Match `Events("X")` with JS listener |
| Promise never resolves | Deadlock or exception | Add timeout, check threading |
| Stale native code | Cached build | Delete ios/build, rebuild |
| Config plugin not applying | Not in plugins array | Check app.json |

## References

- [Expo: Debugging Guide](https://docs.expo.dev/debugging/runtime-issues/)
- [React Native: Debugging](https://reactnative.dev/docs/debugging)
- [Expo: Module API](https://docs.expo.dev/modules/module-api/)
- Companion doc: `Expo_Module_Authoring.md`
- Companion doc: `RN_Swift_Hybrid_Patterns.md`
