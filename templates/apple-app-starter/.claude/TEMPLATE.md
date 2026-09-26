# Apple App Template Instructions

## Automatic Xcode Project Pipeline

This template is designed for iOS and macOS application development. When agents work with this template, they MUST follow the automatic Xcode project creation pipeline.

## Required Agent Actions

### 1. Platform Detection
When a user requests an iOS or macOS application, agents MUST:
- Detect Apple platform keywords (iOS, iPhone, iPad, macOS, Mac app)
- Automatically route to iOS Dev or macos-specialist agents
- Set up Apple-specific development environment

### 2. Automatic Xcode Project Creation
**CRITICAL**: Xcode projects are MANDATORY and AUTOMATIC for all Apple apps.

Agents MUST execute these steps WITHOUT prompting:
```bash
# 1. Create capsule structure
# 2. Generate Swift source files in src/ios/ or src/macos/
# 3. AUTOMATICALLY create Xcode project (NO PROMPT)
python3 {{CATALYST_ROOT}}/tools/create_linked_xcode_project.py /path/to/capsule ProjectName
# 4. Configure platform-specific settings
# 5. Verify project opens in Xcode
```

### 3. Never Prompt for Xcode Creation
**FORBIDDEN**:
- "Would you like me to create an Xcode project?"
- "Should I set up Xcode for this?"
- "Do you need an Xcode project?"

**REQUIRED**:
- Silently create Xcode project as part of standard pipeline
- Report completion: "✅ Xcode project created and linked"

## Template-Specific Configuration

### Source Organization
- `src/ios/` - iOS Swift source files
- `src/macos/` - macOS Swift source files  
- `src/shared/` - Shared business logic
- `src/resources/` - Assets, localizations

### MCP Servers
This template automatically configures:
- `xcodebuild` - Xcode build automation
- `apple-doc` - Apple Developer Documentation
- `applescript` - macOS system integration (for macOS apps)

### Agent Routing
- Keywords like "iOS", "iPhone", "iPad" → iOS Dev
- Keywords like "macOS", "Mac app", "desktop" → macos-specialist
- Both agents enforce automatic Xcode project creation

### Build Pipeline
1. **Detect** Apple platform request
2. **Create** capsule with apple-app-starter template
3. **Generate** Swift source files
4. **AUTO-CREATE** Xcode project (linked files)
5. **Configure** platform-specific settings
6. **Verify** development environment ready

## Validation Checklist

After using this template, verify:
- [ ] Capsule created with apple-app-starter structure
- [ ] Swift source files in appropriate src/ directories
- [ ] Xcode project created WITHOUT user prompt
- [ ] Project files are LINKED (not copied)
- [ ] Project opens successfully in Xcode
- [ ] All editors work on same source files

## Error Handling

If Xcode project creation fails:
1. Report specific error
2. Attempt automatic fixes
3. Retry creation once
4. Only then request user guidance

Remember: Xcode projects are not optional for Apple apps - they're mandatory infrastructure that must be created automatically as part of the standard development pipeline.