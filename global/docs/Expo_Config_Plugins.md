# Expo Config Plugins — Authoring Guide

## Overview

Config plugins modify native project files (Info.plist, AndroidManifest.xml, Podfile, build.gradle) at **prebuild time**. They run during `npx expo prebuild` to inject native configuration without manually editing Xcode/Android Studio projects.

**When to use:** Whenever your module needs native permissions, entitlements, build settings, or manifest entries.

## Plugin Anatomy

A config plugin is a function that receives an `ExpoConfig` and returns a modified `ExpoConfig`:

```typescript
import { ConfigPlugin } from 'expo/config-plugins';

const withMyPlugin: ConfigPlugin = (config) => {
  // Modify config
  return config;
};

export default withMyPlugin;
```

### With Parameters

```typescript
import { ConfigPlugin } from 'expo/config-plugins';

const withMyPlugin: ConfigPlugin<{ apiKey: string }> = (config, { apiKey }) => {
  // Use apiKey to modify config
  return config;
};

export default withMyPlugin;
```

## Available Mod Hooks

| Hook | Modifies | Platform |
|------|----------|----------|
| `withInfoPlist` | Info.plist entries | iOS |
| `withEntitlementsPlist` | Entitlements | iOS |
| `withXcodeProject` | Xcode project file | iOS |
| `withAppDelegate` | AppDelegate | iOS |
| `withPodfile` | Podfile | iOS |
| `withAndroidManifest` | AndroidManifest.xml | Android |
| `withMainActivity` | MainActivity | Android |
| `withMainApplication` | MainApplication | Android |
| `withProjectBuildGradle` | Project build.gradle | Android |
| `withAppBuildGradle` | App build.gradle | Android |
| `withStringsXml` | strings.xml | Android |
| `withAndroidColors` | colors.xml | Android |
| `withAndroidStyles` | styles.xml | Android |

## Pattern: iOS Info.plist Modification

```typescript
import { withInfoPlist, ConfigPlugin } from 'expo/config-plugins';

const withMyApiKey: ConfigPlugin<{ apiKey: string }> = (config, { apiKey }) => {
  config = withInfoPlist(config, (config) => {
    config.modResults['MY_CUSTOM_API_KEY'] = apiKey;
    return config;
  });
  return config;
};

export default withMyApiKey;
```

**Usage in app.json:**
```json
{
  "expo": {
    "plugins": [
      ["./plugins/withMyApiKey", { "apiKey": "abc123" }]
    ]
  }
}
```

## Pattern: Android Manifest Modification

```typescript
import {
  withAndroidManifest,
  AndroidConfig,
  ConfigPlugin
} from 'expo/config-plugins';

const withMyApiKey: ConfigPlugin<{ apiKey: string }> = (config, { apiKey }) => {
  config = withAndroidManifest(config, (config) => {
    const mainApplication = AndroidConfig.Manifest.getMainApplicationOrThrow(
      config.modResults
    );

    AndroidConfig.Manifest.addMetaDataItemToMainApplication(
      mainApplication,
      'MY_CUSTOM_API_KEY',
      apiKey
    );
    return config;
  });
  return config;
};

export default withMyApiKey;
```

## Pattern: Combined iOS + Android Plugin

```typescript
import {
  withInfoPlist,
  withAndroidManifest,
  AndroidConfig,
  ConfigPlugin
} from 'expo/config-plugins';

const withMyApiKey: ConfigPlugin<{ apiKey: string }> = (config, { apiKey }) => {
  // iOS: Add to Info.plist
  config = withInfoPlist(config, (config) => {
    config.modResults['MY_CUSTOM_API_KEY'] = apiKey;
    return config;
  });

  // Android: Add to AndroidManifest.xml
  config = withAndroidManifest(config, (config) => {
    const mainApplication = AndroidConfig.Manifest.getMainApplicationOrThrow(
      config.modResults
    );

    AndroidConfig.Manifest.addMetaDataItemToMainApplication(
      mainApplication,
      'MY_CUSTOM_API_KEY',
      apiKey
    );
    return config;
  });

  return config;
};

export default withMyApiKey;
```

## Pattern: iOS Permission Strings

```typescript
import { withInfoPlist, ConfigPlugin } from 'expo/config-plugins';

const withCameraPermission: ConfigPlugin<{ message?: string }> = (
  config,
  { message = 'Allow $(PRODUCT_NAME) to access your camera' } = {}
) => {
  return withInfoPlist(config, (config) => {
    config.modResults['NSCameraUsageDescription'] = message;
    return config;
  });
};

export default withCameraPermission;
```

## Pattern: Local Plugin File

Create a plugin file in your project:

**plugins/withMyPlugin.js:**
```javascript
const { withInfoPlist } = require('expo/config-plugins');

const withMyPlugin = (config) => {
  return withInfoPlist(config, (config) => {
    config.modResults.NSLocationWhenInUseUsageDescription =
      'Allow $(PRODUCT_NAME) to use your location';
    return config;
  });
};

module.exports = withMyPlugin;
```

**app.json:**
```json
{
  "expo": {
    "plugins": ["./plugins/withMyPlugin"]
  }
}
```

## Using Built-in Config Plugins

Many Expo packages include config plugins. Use them in `app.json`:

```json
{
  "expo": {
    "plugins": [
      "expo-router",
      "expo-apple-authentication",
      ["expo-camera", {
        "cameraPermission": "Allow $(PRODUCT_NAME) to access your camera",
        "microphonePermission": "Allow $(PRODUCT_NAME) to access your microphone"
      }],
      ["expo-location", {
        "locationAlwaysAndWhenInUsePermission": "Allow $(PRODUCT_NAME) to use your location."
      }],
      ["expo-notifications", {
        "icon": "./assets/notification_icon.png",
        "color": "#ffffff"
      }],
      ["expo-build-properties", {
        "android": {
          "compileSdkVersion": 35,
          "targetSdkVersion": 35
        },
        "ios": {
          "deploymentTarget": "15.1"
        }
      }]
    ]
  }
}
```

## expo-build-properties Reference

Controls native build settings:

### iOS Properties

| Property | Type | Purpose |
|----------|------|---------|
| `deploymentTarget` | string | iOS minimum version |
| `useFrameworks` | "static" \| "dynamic" | CocoaPods linking |
| `extraPods` | array | Additional CocoaPods |
| `ccacheEnabled` | boolean | C++ compiler cache |
| `buildReactNativeFromSource` | boolean | Build RN from source |
| `forceStaticLinking` | string[] | Force static link for pods |

### Android Properties

| Property | Type | Purpose |
|----------|------|---------|
| `compileSdkVersion` | number | Compile SDK version |
| `targetSdkVersion` | number | Target SDK version |
| `minSdkVersion` | number | Minimum SDK version |
| `buildToolsVersion` | string | Build tools version |
| `kotlinVersion` | string | Kotlin version |
| `enableMinifyInReleaseBuilds` | boolean | R8 obfuscation |
| `extraMavenRepos` | array | Additional Maven repos |

### Extra iOS Pod Example

```json
{
  "ios": {
    "extraPods": [
      {
        "name": "Protobuf",
        "version": "~> 3.14.0"
      },
      {
        "name": "MyPrivatePod",
        "git": "https://github.com/org/pod.git",
        "tag": "1.0.0"
      }
    ]
  }
}
```

## Pairing Config Plugin with Native Module

When your custom module needs native config, create both together:

### 1. Create the module
```bash
npx create-expo-module@latest expo-native-configuration
```

### 2. Write the plugin (`app.plugin.js` / `app.plugin.ts`)
```typescript
import {
  withInfoPlist,
  withAndroidManifest,
  AndroidConfig,
  ConfigPlugin
} from 'expo/config-plugins';

const withMyApiKey: ConfigPlugin<{ apiKey: string }> = (config, { apiKey }) => {
  config = withInfoPlist(config, (config) => {
    config.modResults['MY_CUSTOM_API_KEY'] = apiKey;
    return config;
  });

  config = withAndroidManifest(config, (config) => {
    const mainApplication = AndroidConfig.Manifest.getMainApplicationOrThrow(
      config.modResults
    );
    AndroidConfig.Manifest.addMetaDataItemToMainApplication(
      mainApplication, 'MY_CUSTOM_API_KEY', apiKey
    );
    return config;
  });

  return config;
};

export default withMyApiKey;
```

### 3. Native module reads the injected value

**Swift:**
```swift
Function("getApiKey") {
  return Bundle.main.object(forInfoDictionaryKey: "MY_CUSTOM_API_KEY") as? String
}
```

**Kotlin:**
```kotlin
Function("getApiKey") {
  val applicationInfo = appContext?.reactContext?.packageManager
    ?.getApplicationInfo(
      appContext?.reactContext?.packageName.toString(),
      PackageManager.GET_META_DATA
    )
  return@Function applicationInfo?.metaData?.getString("MY_CUSTOM_API_KEY")
}
```

### 4. Register in app.json
```json
{
  "expo": {
    "plugins": [
      ["expo-native-configuration/app.plugin.js", { "apiKey": "my-secret-key" }]
    ]
  }
}
```

## Workflow

```
1. Write config plugin (TypeScript/JavaScript)
2. Register in app.json plugins array
3. Run `npx expo prebuild -p ios --clean`
4. Verify native files were modified correctly
5. Run `npx expo run:ios`
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Plugin not running | Check `plugins` array in app.json |
| Changes not visible | Run `npx expo prebuild --clean` |
| Wrong file modified | Use correct mod hook (withInfoPlist vs withAndroidManifest) |
| Plugin crashes | Return config from every mod callback |
| Missing import | Import from `expo/config-plugins`, not `@expo/config-plugins` |

## References

- [Expo: Config Plugins Introduction](https://docs.expo.dev/config-plugins/introduction/)
- [Expo: Config Plugin + Native Module Tutorial](https://docs.expo.dev/modules/config-plugin-and-native-module-tutorial/)
- [Expo: Build Properties](https://docs.expo.dev/versions/latest/sdk/build-properties/)
