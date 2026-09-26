# [Your App Name] - React Native Application

## Purpose
[Brief description of your React Native app - what it does and who it's for]

## Current Status
- **Phase:** Initial Setup
- **Last Updated:** [Date]
- **Platforms:** iOS 17+ & Android 13+
- **Technology:** React Native + TypeScript + Storybook

## Technical Overview
- **Primary Technologies:** React Native 0.73+, TypeScript 5+
- **UI Framework:** React Native with component library (NativeBase/Paper/Tamagui)
- **Development Tools:** Storybook (native + web), Fast Refresh
- **Design:** your design tool of choice (Figma, Penpot, ...)
- **Dependencies:** iOS 17+, Android 13+

## Key Features
[List your app's main features]

1. Feature 1
2. Feature 2
3. Feature 3

## Development Workflow

**Complete workflow:** See `{{CATALYST_ROOT}}/global/docs/Mobile_App_Workflow.md`

### Quick Reference

**Tools:**
- **React Native** - Cross-platform framework
- **Storybook** - Component library (native + web preview)
- **Fast Refresh** - Built-in hot reload (~1s)

**Workflow:**
```
📐 UI Designer (design tool)
    ↓
📐 UI Designer + 📱 Mobile Dev (Storybook Components)
    ↓
📱 Mobile Dev (Integration)
    ↓
Validation (Test iOS + Android)
```

### Storybook Component Development

**Run Storybook:**
```bash
# Native mode (device/simulator)
npm run storybook

# Web mode (browser - faster)
npm run storybook-web
```

**Create component story:**
```tsx
// components/Button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
  component: Button,
  title: 'Components/Button',
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: {
    variant: 'primary',
    children: 'Press Me',
  },
};

export const Secondary: Story = {
  args: {
    variant: 'secondary',
    children: 'Cancel',
  },
};
```

**Fast iteration:**
```
1. Run Storybook (once)
2. Edit component code
3. Save → See changes in ~1s
4. Test all states in isolation
5. Use in app
```

## Design Resources

## Design System

**Theme Configuration:**

```typescript
// theme/colors.ts
export const colors = {
  // Brand
  primary: '#007AFF',
  secondary: '#5856D6',

  // Status
  success: '#34C759',
  warning: '#FF9500',
  error: '#FF3B30',
  info: '#5AC8FA',

  // Neutral
  background: '#FFFFFF',
  surface: '#F2F2F7',
  text: '#000000',
  textSecondary: '#8E8E93',
  border: '#C6C6C8',
};

// theme/typography.ts
export const typography = {
  // Display
  displayLarge: {
    fontSize: 57,
    fontWeight: '700' as const,
    lineHeight: 64,
  },
  displayMedium: {
    fontSize: 45,
    fontWeight: '700' as const,
    lineHeight: 52,
  },

  // Body
  bodyLarge: {
    fontSize: 16,
    fontWeight: '400' as const,
    lineHeight: 24,
  },
  bodyMedium: {
    fontSize: 14,
    fontWeight: '400' as const,
    lineHeight: 20,
  },
};

// theme/spacing.ts
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
  xxxl: 64,
};
```

## Component Libraries

**Choose one:**

### NativeBase (Recommended)
```bash
npm install native-base react-native-svg react-native-safe-area-context
```
- 100+ components
- Great theming system
- Good documentation

### React Native Paper (Material Design)
```bash
npm install react-native-paper react-native-vector-icons
```
- Material Design 3
- Excellent components
- Android-first aesthetic

### Tamagui (Universal)
```bash
npm install tamagui @tamagui/core
```
- Works on mobile + web
- Optimized compiler
- Modern DX

## Directory Structure

```
your-app/
├── CLAUDE.md                    # This file
├── QUICKSTART.md                # Quick setup guide
├── README.md                    # Project overview
├── package.json
├── tsconfig.json
├── .storybook/
│   └── main.ts                  # Storybook config
├── docs/
│   ├── MOBILE_WORKFLOW.md       # React Native workflow
│   └── STORYBOOK_SETUP.md       # Storybook details
├── design/
│   └── [design exports]
└── src/
    ├── App.tsx                  # Main app entry
    ├── components/
    │   ├── Button.tsx
    │   ├── Button.stories.tsx   # Storybook story
    │   ├── Card.tsx
    │   └── Card.stories.tsx
    ├── screens/
    │   ├── HomeScreen.tsx
    │   └── SettingsScreen.tsx
    ├── services/
    └── theme/
        ├── colors.ts
        ├── typography.ts
        └── spacing.ts
```

## Setup Checklist

- [ ] Initialize React Native project with TypeScript
- [ ] Add Storybook (native + web)
- [ ] Choose component library (NativeBase/Paper/Tamagui)
- [ ] Create your screen designs
- [ ] Export design system values
- [ ] Implement theme (colors, typography, spacing)
- [ ] Create component stories
- [ ] Test on iOS + Android
- [ ] Reference this workflow doc in code comments

## Documentation

- **Global Mobile Workflow:** `{{CATALYST_ROOT}}/global/docs/Mobile_App_Workflow.md`
- **Design Workflow:** `{{CATALYST_ROOT}}/global/docs/Design_to_Code_Workflow.md`

## Platform Guidelines

- **Apple HIG:** https://developer.apple.com/design/human-interface-guidelines
- **Material Design 3:** https://m3.material.io
- **React Native:** https://reactnative.dev
- **Storybook:** https://storybook.js.org/docs/react-native

## Performance Expectations

**With Fast Refresh:**
- Edit → Save: ~1s (built-in)
- Storybook web preview: <1s
- Component isolation: Faster than full app
- Cross-platform: Single codebase for iOS + Android

---

*React Native App Template - Huxley*
