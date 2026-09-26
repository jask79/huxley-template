# Xcode Project Standards - Huxley

## Core Principle: Always Link, Never Copy

The Huxley system enforces a strict policy for Xcode project creation:

**All Xcode projects MUST reference actual source files, never copy them.**

This ensures all editors (Xcode, Cursor, terminal, Claude Code) work on the same files.

## Implementation

### Use the Official Tool

```bash
# Create linked Xcode project (CORRECT)
python3 {{CATALYST_ROOT}}/tools/create_linked_xcode_project.py /path/to/capsule ProjectName

# Example
python3 {{CATALYST_ROOT}}/tools/create_linked_xcode_project.py {{CATALYST_ROOT}}/capsules/acme-app AcmeApp
```

### How It Works

1. **File References**: Uses `PBXFileReference` with relative paths
2. **Source Tree**: Sets `sourceTree = "<group>"` for proper linking  
3. **No Copying**: Source files remain in their original capsule locations
4. **Directory Structure**: Preserves original organization in Xcode navigator

### What You Get

```
capsule/
├── src/
│   ├── AppFile.swift          ← Original files (edit here)
│   ├── Views/
│   │   └── ContentView.swift  ← Original files (edit here)
│   └── Assets.xcassets        ← Original assets (edit here)
└── ios/
    └── MyApp.xcodeproj        ← Xcode project (references above files)
```

## Technical Details

### PBXFileReference Structure
```
{file_uuid} /* AppFile.swift */ = {
    isa = PBXFileReference; 
    lastKnownFileType = sourcecode.swift; 
    name = AppFile.swift; 
    path = ../src/AppFile.swift;      ← Relative path to actual file
    sourceTree = "<group>"; 
};
```

### Benefits

✅ **Single Source of Truth**: All editors modify the same files  
✅ **No Sync Issues**: Changes appear everywhere instantly  
✅ **Simplified Structure**: No duplicate files  
✅ **Storage Efficient**: No file copying  
✅ **Git Friendly**: Clean repository structure  

## Enforcement

### Agent Responsibilities

- **iOS Dev**: Must use linked project creation
- **macos-specialist**: Must use linked project creation  
- **System Architect**: Validates project structure
- **Code Reviewer**: Flags any file copying violations

### Validation Rules

**REQUIRED** ✅
- Use `tools/create_linked_xcode_project.py`
- Reference files with relative paths
- Preserve original directory structure
- Set `sourceTree = "<group>"`

**FORBIDDEN** ❌  
- Copying Swift source files
- Moving files into `.xcodeproj` directory
- Creating duplicate source files
- Using absolute file paths in references

## Migration

### Converting Existing Projects

If you have an existing project that copies files:

1. **Backup current project**
2. **Delete the .xcodeproj directory** 
3. **Recreate using linked approach**:
   ```bash
   python3 {{CATALYST_ROOT}}/tools/create_linked_xcode_project.py /path/to/capsule ProjectName
   ```

### Template Updates

All Huxley templates now use the linked approach by default:

- `templates/apple-app-starter/` 
- Agent-generated projects
- Automated capsule setups

## Examples

### Basic iOS App
```bash
# Navigate to capsule
cd {{CATALYST_ROOT}}/capsules/my-ios-app

# Create linked Xcode project  
python3 {{CATALYST_ROOT}}/tools/create_linked_xcode_project.py . MyiOSApp

# Open in Xcode
open MyiOSApp.xcodeproj
```

### Complex Project Structure
```bash
# For capsules with nested source structure
python3 {{CATALYST_ROOT}}/tools/create_linked_xcode_project.py \
  {{CATALYST_ROOT}}/capsules/complex-app \
  ComplexApp \
  --xcode-dir {{CATALYST_ROOT}}/capsules/complex-app/xcode
```

## Troubleshooting

### "File not found" in Xcode
- Check that source files exist at referenced paths
- Verify relative path calculations are correct
- Ensure no files were moved after project creation

### Build errors
- Confirm all Swift files are included in target
- Check that asset catalogs are properly referenced  
- Verify Info.plist path is correct

### Agent not following policy
- Check agent configuration includes xcode_project_policy.json
- Update agent prompts to reference this standard
- Report policy violations for correction

---

**Remember**: The goal is ONE codebase, multiple editors. Link, don't copy.