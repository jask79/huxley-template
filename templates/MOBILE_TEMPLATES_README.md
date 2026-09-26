# Huxley Mobile App Templates

**Complete starter templates for Native iOS and React Native apps**

---

## Available Templates

### 1. Native iOS App (`native-ios-app/`)

**Best for:** iOS-only apps, maximum performance, platform-specific features

**Includes:**
- ✅ CLAUDE.md with workflow reference
- ✅ QUICKSTART.md (15-minute setup)
- ✅ InjectionIII integration guide
- ✅ Design system starter (Colors, Typography, Spacing)
- ✅ Xcode Previews examples


### 2. React Native App (`react-native-app/`)

**Best for:** iOS + Android from one codebase, Storybook component library

**Includes:**
- ✅ CLAUDE.md with workflow reference
- ✅ QUICKSTART.md (20-minute setup)
- ✅ Storybook setup guide (native + web)
- ✅ Component library recommendations
- ✅ Theme system starter
- ✅ Example Button component with story


---

## How to Use Templates

### Option 1: Copy Template to New Capsule

```bash
# Create new capsule directory
mkdir -p {{CATALYST_ROOT}}/capsules/my-new-app

# Copy template files (Native iOS)
cp -r {{CATALYST_ROOT}}/templates/native-ios-app/* {{CATALYST_ROOT}}/capsules/my-new-app/

# OR copy React Native template
cp -r {{CATALYST_ROOT}}/templates/react-native-app/* {{CATALYST_ROOT}}/capsules/my-new-app/

# Update CLAUDE.md with your app details
# Follow QUICKSTART.md to complete setup
```

### Option 2: Reference Template Files

```bash
# Navigate to new capsule
cd {{CATALYST_ROOT}}/capsules/my-new-app

# Copy specific files as needed
cp {{CATALYST_ROOT}}/templates/native-ios-app/CLAUDE.md .
cp {{CATALYST_ROOT}}/templates/native-ios-app/QUICKSTART.md .
```

---

## Template Contents

### Native iOS App

```
templates/native-ios-app/
├── CLAUDE.md                    # Capsule context + workflow
├── QUICKSTART.md                # 15-minute setup guide
├── docs/
│   └── [Reference global docs]
├── design/
│   └── [design export directory]
└── src/
    └── [Xcode project goes here]
```

**Key Features:**
- InjectionIII integration documented
- Design system code templates (Colors.swift, etc.)
- Xcode Previews examples
- References global Mobile_App_Workflow.md

### React Native App

```
templates/react-native-app/
├── CLAUDE.md                    # Capsule context + workflow
├── QUICKSTART.md                # 20-minute setup guide
├── package.json.template        # Dependencies reference
├── docs/
│   └── [Reference global docs]
├── design/
│   └── [design export directory]
└── src/
    ├── components/              # Component examples
    │   └── Button example
    └── theme/                   # Theme system
        ├── colors.ts
        ├── typography.ts
        └── spacing.ts
```

**Key Features:**
- Storybook setup guide (native + web)
- Component library recommendations
- Theme system templates
- Example Button component with Storybook story
- References global Mobile_App_Workflow.md

---

## Workflow Comparison

### Native iOS

```
1. Copy template to new capsule
2. Create Xcode project
3. Add InjectionIII package
4. Copy design system files (Colors.swift, etc.)
5. Design your screens in your design tool
6. Export designs as PNG references
7. Implement in Swift with hot reload (2s updates)
```

**Speed:** 30x faster iteration (60s → 2s)

### React Native

```
1. Copy template to new capsule
2. Initialize React Native project
3. Add Storybook (npx storybook@latest init)
4. Copy theme system files
5. Design your screens in your design tool
6. Export designs as PNG references
7. Build components in Storybook (~1s updates)
8. Test on iOS + Android
```

**Speed:** Built-in Fast Refresh (~1s), Storybook web preview (<1s)

---

## Customization Checklist

After copying template to new capsule:

### Both Templates

- [ ] Update CLAUDE.md:
  - [ ] Replace "[Your App Name]" with actual name
  - [ ] Update "Purpose" section
  - [ ] List key features
  - [ ] Update current status
- [ ] Update QUICKSTART.md with app-specific steps
- [ ] Export design system values
- [ ] Update theme code with brand colors/fonts

### Native iOS Specific

- [ ] Create Xcode project
- [ ] Add InjectionIII package
- [ ] Implement Colors.swift, Typography.swift, Spacing.swift
- [ ] Add hot reload hooks to Views

### React Native Specific

- [ ] Initialize React Native project with TypeScript
- [ ] Add Storybook (select "Both")
- [ ] Choose component library (NativeBase/Paper/Tamagui)
- [ ] Implement theme files
- [ ] Create component stories

---

## Documentation References

**Global Docs:**
- `{{CATALYST_ROOT}}/global/docs/Mobile_App_Workflow.md` - Complete mobile workflow
- `{{CATALYST_ROOT}}/global/docs/Design_to_Code_Workflow.md` - Design workflow

**Template Files:**
- `templates/native-ios-app/CLAUDE.md` - iOS template context
- `templates/native-ios-app/QUICKSTART.md` - iOS quick start
- `templates/react-native-app/CLAUDE.md` - React Native template context
- `templates/react-native-app/QUICKSTART.md` - React Native quick start

---

## Template Maintenance

**When to update templates:**
- New iOS version with design changes
- New React Native version
- Storybook major version update
- Design system best practices evolve

**How to update:**
1. Update CLAUDE.md and QUICKSTART.md
2. Test updated workflow
4. Document changes in this README

---

## Quick Decision Guide

**Choose Native iOS when:**
- iOS-only app
- Maximum performance required
- Platform-specific features (WidgetKit, Live Activities)
- Smallest app size matters

**Choose React Native when:**
- iOS + Android from one codebase
- Team knows React/TypeScript
- Storybook component library desired
- Shared web version (React Native Web)
- Rapid cross-platform prototyping

---

## Support

**Questions about templates?**
- Reference global/docs/Mobile_App_Workflow.md
- Check template QUICKSTART.md files
- Review example capsule: capsules/example-mobile-capsule (Native iOS)

---

*Mobile App Templates - Huxley*
*Last Updated: October 2025*
