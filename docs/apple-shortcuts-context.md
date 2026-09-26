# Apple Shortcuts Context for Huxley Agents

## Apple Shortcuts Fundamentals

### What Are iOS Shortcuts?
iOS Shortcuts are automated workflows that can:
- Run on iPhone, iPad, Apple Watch, Mac, HomePod
- Be triggered by Siri voice commands
- Execute from Home Screen widgets
- Run automatically based on location/time
- Chain multiple apps and system functions together

### Core Concepts for Agents

#### 1. Actions vs Shortcuts
- **Actions**: Individual building blocks (Get Text, Show Alert, etc.)
- **Shortcuts**: Complete workflows composed of multiple actions
- **Data Flow**: Actions pass data between each other in sequence

#### 2. Input/Output Types
```
Text → Number → Boolean → URL → Image → File → Contact → Location → Date
```
Actions must match compatible input/output types.

#### 3. System Integration Points
- **Siri**: Voice activation and responses
- **Widgets**: Home/Lock screen quick access  
- **Share Sheet**: Input from other apps
- **Automation**: Time/location/app-based triggers
- **Shortcuts App**: Management and organization

## iOS Shortcuts Action Categories

### Essential Categories for Huxley

#### Text & Data
- `GetText`, `GetTextFromInput`, `GetTextFromClipboard`
- `ReplaceText`, `SplitText`, `CombineText`
- `GetNumbers`, `Calculate`, `FormatNumber`

#### Web & APIs
- `GetURL`, `GetContentsOfURL` 
- `GetValueForKey`, `GetDictionaryValue`
- `MakeHTTPRequest` (GET, POST, PUT, DELETE)

#### Device Functions  
- `GetCurrentLocation`, `GetWeather`
- `TakePhoto`, `SelectPhotos`, `SaveToPhotos`
- `GetBatteryLevel`, `SetBrightness`, `SetVolume`

#### Notifications & Alerts
- `ShowAlert`, `ShowNotification`
- `AskForInput`, `ChooseFromMenu`
- `ShowResult`, `QuickLook`

#### Files & Storage
- `GetFile`, `SaveFile`, `AppendToFile`
- `GetFolderContents`, `CreateFolder`
- `GetMyShortcuts`, `RunShortcut`

#### Logic & Flow Control
- `If/Otherwise`, `RepeatWithEach`, `Repeat`
- `GetItemFromList`, `FilterFiles`, `SortList`
- `WaitToReturn`, `Exit`, `StopShortcut`

#### System & Apps
- `OpenApp`, `GetRunningApps`
- `RunShellScript`, `RunSSHScript` 
- `SendMessage`, `SendEmail`

## Apple Shortcuts Limitations for Agents

### Security Restrictions
- **No System File Access**: Can't access arbitrary system files
- **Sandboxed**: Limited to user-accessible directories  
- **Permission Prompts**: First-time actions require user approval
- **No Root Access**: Cannot perform administrative tasks

### iOS vs macOS Differences
- **SSH**: Only available on macOS shortcuts
- **Shell Scripts**: macOS only
- **File System**: More restricted on iOS
- **Apps**: Different available apps per platform

### Huxley Considerations
- **SSH Dependencies**: Huxley server connections require macOS
- **File Paths**: Use relative paths when possible
- **Error Handling**: Always include fallback actions
- **Testing**: Different behavior on device vs simulator

## Advanced Shortcuts Concepts

### Shortcut Parameters
```cherri
// Shortcuts can accept parameters from Siri/widgets
@input: text searchTerm
@input: number maxResults = 10

GetURL("https://api.example.com/search?q={searchTerm}&limit={maxResults}")
```

### Magic Variables
```cherri
// Previous action outputs become "magic variables"
GetCurrentLocation()
// → Creates "Current Location" magic variable
GetWeather(CurrentLocation)
```

### Content Types
```cherri
// Shortcuts understand rich content types
GetPhotosFromAlbum("Recent")
// → Photos with metadata (date, location, etc.)
ResizeImage(Photos, 800)
```

### Error Handling Patterns
```cherri
// Always handle network failures
GetContentsOfURL("https://api.example.com/data")
If (LastAction == "Failed")
    ShowAlert("Error", "Network unavailable")
    Exit()
Otherwise
    // Process successful response
    GetValueForKey("status")
End
```

## Huxley Integration Patterns

### Common Huxley Shortcuts
1. **Status Checks**: Monitor capsule health via SSH
2. **Notifications**: Alert on build completion/failures  
3. **Quick Actions**: Trigger builds, deployments
4. **Data Sync**: Upload logs, download reports
5. **System Info**: Check server resources, disk space

### Recommended Shortcut Architecture
```cherri
// 1. Input validation
If (Input == "")
    AskForInput("Enter capsule name")
    Set name to ProvidedInput
Otherwise
    Set name to Input
End

// 2. Main logic with error handling
GetURL("https://builder-api.com/status/{name}")
If (StatusCode == 200)
    // Success path
    GetValueForKey("status")
    ShowResult()
Otherwise
    // Error path  
    ShowAlert("Error", "Could not check {name} status")
End

// 3. Logging
GetCurrentDate()
AppendToFile("~/shortcuts.log", "{name} checked at {currentDate}")
```

## Testing & Debugging

### Testing Strategies
- **Simulator Testing**: Use iOS Simulator for development
- **Device Testing**: Real device for production validation
- **Mock Data**: Use static responses for API testing
- **Error Simulation**: Test network failures and edge cases

### Common Issues
- **Permission Errors**: First run requires user approval
- **Network Timeouts**: Add timeout handling
- **Type Mismatches**: Ensure action input/output compatibility
- **Path Issues**: Use proper file paths for each platform

## Best Practices for Agents

1. **Always Include Error Handling**: Network, permissions, invalid input
2. **Use Descriptive Names**: Clear shortcut and variable names
3. **Add User Feedback**: Show progress and results
4. **Keep It Simple**: Complex logic should be server-side
5. **Test Cross-Platform**: Ensure iOS/macOS compatibility
6. **Document Dependencies**: Note required permissions/apps
7. **Handle Edge Cases**: Empty inputs, network failures, etc.

This context ensures Huxley agents understand not just Cherri syntax, but the underlying Apple Shortcuts ecosystem they're generating code for.