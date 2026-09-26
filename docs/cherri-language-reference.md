# Cherri Language Reference for Huxley

## Overview
Cherri is a programming language designed specifically for creating iOS Shortcuts that compile directly to signed, runnable Shortcut files. This reference is for Huxley automation agents to generate iOS shortcuts from capsule specifications.

## IDE Integration

### Default IDE: Cursor IDE (Primary)
**Cursor IDE with Cherri extension** provides:
- ✅ Syntax highlighting for .cherri files
- ✅ IntelliSense and autocompletion  
- ✅ Error checking and validation
- ✅ Code formatting and linting
- ✅ Direct compilation support
- ✅ Huxley integration

### Fallback IDE: Cherri IDE (Secondary)
**Cherri IDE** provides:
- ✅ Native Cherri language support
- ✅ Built-in compilation
- ✅ Shortcut preview

### IDE Priority Order
1. **Cursor IDE** (Default - best development experience)
2. **Cherri IDE** (Fallback - native support)
3. **System Default** (Last resort)

## Core Workflow
```bash
spec/requirements.yaml → .cherri source → [Cursor IDE] → cherri compile → .shortcut → macOS import
```

The Huxley system automatically opens generated .cherri files in Cursor IDE for validation and editing before compilation.

## Language Syntax

### Basic Structure
```cherri
// Shortcut definition with metadata
@Icon("globe")
@Color("blue")
Shortcut MyShortcut {
    // Actions go here
    GetText("Hello World")
    ShowResult()
}
```

### Variables and Constants
```cherri
// Constants
const message = "Hello"
const count = 42

// Variables with type annotations
@string: userInput
@number: result
@boolean: isEnabled
```

### Actions (iOS Shortcuts Actions)

#### Common Actions
```cherri
// Text Operations
GetText("Static text")
GetTextFromInput()
GetTextFromClipboard()
ShowResult()

// Web Operations
GetURL("https://api.example.com")
GetContentsOfURL()
GetValueForKey("data")

// Device Operations
GetCurrentLocation()
TakePhoto()
GetPhotosFromCamera()

// Logic Operations
If(condition) {
    // True actions
} Else {
    // False actions
}

// Alerts and Notifications
ShowAlert("Title", "Message")
ShowNotification("Title", "Body")
```

#### Raw Action Definition
```cherri
// For actions not directly supported
rawAction("is.workflow.actions.gettext", {
    "WFTextActionText": "Custom text"
})
```

### Custom Actions
```cherri
action fetchAPIData(text endpoint) {
    GetURL("https://api.example.com/{endpoint}")
    GetContentsOfURL()
    GetValueForKey("result")
}

// Usage
fetchAPIData("users")
```

### Copy-Paste Actions (Reusable Code Blocks)
```cherri
copy validateConnection {
    const online = IsOnline()
    if !online {
        ShowAlert("Error", "No internet connection!")
        Exit()
    }
}

// Usage
paste validateConnection
```

### File Operations
```cherri
// Include other Cherri files
#include 'common-actions.cherri'
#include 'api-helpers.cherri'

// Embed files as base64
@file: icon = 'assets/icon.png'
```

### Metadata Decorators
```cherri
@Icon("globe")          // System icon name
@Color("blue")          // Color theme
@Import("Shortcuts")    // Required imports
@Summary("Description") // Shortcut description
```

### Data Types and Type System
```cherri
// Supported types
@string: text
@number: count  
@boolean: flag
@date: timestamp
@location: coords
@photo: image
@file: document
```

## Huxley Integration

### Spec-to-Cherri Mapping

#### From `spec/requirements.yaml`:
```yaml
shortcuts:
  - name: "Weather Alert"
    icon: "cloud.rain"
    color: "blue"
    actions:
      - type: "get_location"
      - type: "get_weather"
        parameters:
          location: "current"
      - type: "show_alert"
        parameters:
          title: "Weather Update"
          message: "Current conditions"
```

#### Generated `.cherri`:
```cherri
@Icon("cloud.rain")
@Color("blue")
Shortcut WeatherAlert {
    GetCurrentLocation()
    GetWeatherForecast()
    ShowAlert("Weather Update", "Current conditions")
}
```

### Automation Actions for Huxley

#### Common Huxley Patterns
```cherri
// SSH Connection Pattern
copy connectToBuilder {
    GetText("ssh user@builder-server.com")
    RunSSHScript()
}

// File Upload Pattern  
copy uploadToCapsule {
    SelectPhoto()
    GetText("{{CATALYST_ROOT}}/capsules/{capsule}/runs/input/")
    SaveFileToPath()
}

// Notification Pattern
copy notifyCompletion(text capsule, text status) {
    ShowNotification("Huxley Alert", "{capsule} is {status}")
}
```

## Compilation and Signing

### CLI Usage
```bash
# Compile to shortcut
cherri source.cherri

# Debug mode
cherri --debug source.cherri

# Output to specific location
cherri --output /path/to/shortcut.shortcut source.cherri
```

### Signing Methods (Automatic)
1. **macOS Signing** (preferred) - Uses system keychain
2. **HubSign** (fallback) - Cloud signing service
3. **shortcut-signing-server** (fallback) - Alternative signing

### File Structure
```
capsule/
├── spec/
│   └── requirements.yaml    # Shortcut definitions
├── src/
│   └── shortcuts/
│       ├── generated/       # Auto-generated .cherri files
│       ├── common.cherri    # Shared actions
│       └── custom.cherri    # Manual customizations
└── ops/
    └── shortcuts/           # Compiled .shortcut files
```

## Huxley Automation Agent Instructions

### Agent Capabilities Required
1. **Parse YAML** shortcut definitions from `spec/requirements.yaml`
2. **Generate Cherri** source code following Huxley patterns
3. **Compile shortcuts** using Cherri CLI
4. **Handle signing** automatically via Cherri's built-in methods
5. **Deploy shortcuts** to appropriate capsule directories

### Error Handling
```cherri
copy handleErrors {
    const result = TryAction()
    if result.hasError {
        ShowAlert("Error", result.errorMessage)
        LogEvent("shortcut_error", result.details)
        Exit()
    }
}
```

### Testing Pattern
```cherri
copy testShortcut {
    const testMode = GetEnvironmentVariable("BUILDER_TEST_MODE")
    if testMode == "true" {
        ShowAlert("Test Mode", "This is a test run")
        // Mock actions
    } else {
        // Real actions
    }
}
```

## Advanced Features

### Conditional Logic
```cherri
If(GetEnvironmentVariable("DEBUG") == "true") {
    ShowAlert("Debug", "Debug mode enabled")
}

Switch(GetDeviceType()) {
    case "iPhone":
        // iPhone-specific actions
    case "iPad": 
        // iPad-specific actions
    default:
        // Default actions
}
```

### Loops and Iteration
```cherri
// Repeat actions
Repeat(5) {
    TakePhoto()
    Wait(2)
}

// For each item
ForEach(GetPhotosFromAlbum("Screenshots")) {
    ResizeImage(1024)
    SaveToPhotoAlbum()
}
```

### Integration with Huxley Events
```cherri
copy logBuilderEvent(text eventType, text capsule) {
    GetCurrentDate()
    GetText("{eventType} in {capsule} at {currentDate}")
    AppendToFile("{{CATALYST_ROOT}}/global/events.log")
}
```

This reference enables Huxley automation agents to fully understand and generate Cherri code for iOS Shortcuts creation, covering the complete A-Z workflow from specification to signed shortcut deployment.