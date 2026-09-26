# iOS/macOS Application Pipeline - Huxley

## Core Principle: Xcode Projects Are Mandatory

**For ALL iOS and macOS applications, an Xcode project MUST be created automatically as part of the standard pipeline.**

This is not optional - it's a required step for Apple platform development.

## Pipeline Stages for Apple Applications

### 1. Initial Setup Phase
When creating any iOS or macOS application:

```
User Request: "Build an iOS app for tracking habits"
↓
Agent Detection: iOS application identified
↓
AUTOMATIC ACTIONS (no prompting needed):
1. Create capsule structure
2. Set up Swift source files
3. Create linked Xcode project ← AUTOMATIC
4. Configure build settings
5. Set up asset catalogs
```

### 2. Automatic Xcode Project Creation

**WHEN**: Immediately after Swift files are created
**HOW**: Using the linked project creator
**WHERE**: In the capsule's src directory

```bash
# This happens AUTOMATICALLY - no user prompt needed
python3 {{CATALYST_ROOT}}/tools/create_linked_xcode_project.py \
  /path/to/capsule \
  ProjectName
```

### 3. Standard iOS/macOS Build Pipeline

```mermaid
graph TD
    A[User: "Create iOS/macOS app"] --> B[Agent: Detect Apple Platform]
    B --> C[Create Capsule Structure]
    C --> D[Generate Swift Files]
    D --> E[AUTO: Create Xcode Project]
    E --> F[Configure Build Settings]
    F --> G[Set Up Assets]
    G --> H[Ready for Development]
    
    style E fill:#f9f,stroke:#333,stroke-width:4px
```

## Implementation Requirements

### For iOS Dev Agent

**MUST DO automatically when building iOS apps:**
1. Create Swift source files in capsule
2. **Immediately create linked Xcode project** (no prompt)
3. Configure Info.plist settings
4. Set up asset catalogs
5. Configure build schemes

### For macos-specialist Agent

**MUST DO automatically when building macOS apps:**
1. Create Swift source files in capsule
2. **Immediately create linked Xcode project** (no prompt)
3. Configure entitlements
4. Set up menu structure
5. Configure build schemes

## Pipeline Checklist

When an iOS/macOS app is requested, agents MUST complete ALL items:

- [ ] Capsule directory created
- [ ] Swift source files generated
- [ ] **Xcode project created (AUTOMATIC - no prompt)**
- [ ] Assets.xcassets configured
- [ ] Info.plist configured
- [ ] Build settings configured
- [ ] Project can be opened in Xcode
- [ ] All files are linked (not copied)

## Agent Instructions

### Automatic Triggers

Agents should create Xcode projects when they detect:
- Keywords: "iOS app", "iPhone app", "iPad app", "macOS app", "Mac app"
- File patterns: `*.swift` files in capsule
- Capsule type: apple-app-starter template
- Platform targets: ios, macos, tvos, watchos

### No User Prompting Required

**WRONG** ❌
```
Agent: "Would you like me to create an Xcode project?"
Agent: "Should I set up Xcode for this?"
Agent: "Do you need an Xcode project?"
```

**RIGHT** ✅
```
Agent: "Creating iOS application with habit tracking..."
Agent: [Creates Swift files]
Agent: [Automatically creates Xcode project]
Agent: "✅ Xcode project created and linked to source files"
```

## Error Handling

If Xcode project creation fails:
1. Report the specific error
2. Attempt to fix common issues (missing directories, permissions)
3. Retry creation
4. Only then ask user for guidance

## Validation

After creating an Apple platform app, verify:
```bash
# Check Xcode project exists
ls -la /path/to/capsule/**/*.xcodeproj

# Verify project references actual files
grep -r "sourceTree" /path/to/capsule/**/*.pbxproj | head -5

# Confirm no file copying occurred
# Source files should NOT exist inside .xcodeproj
find /path/to/capsule/**/*.xcodeproj -name "*.swift" | wc -l
# Should return 0
```

## Summary

**The Rule**: If it's an iOS or macOS app, it gets an Xcode project. Period.

No questions asked. No prompts needed. It's part of the standard pipeline.

---

*This pipeline ensures every Apple platform application is immediately ready for development in Xcode, while maintaining the single-source-of-truth principle through linked file references.*