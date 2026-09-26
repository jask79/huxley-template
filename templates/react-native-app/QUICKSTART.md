# React Native App - Quick Start

**Get productive in 20 minutes**

---

## 1. Initialize React Native Project (5 min)

```bash
# Navigate to your capsule directory
cd {{CATALYST_ROOT}}/capsules/your-app-name

# Initialize with TypeScript template
npx react-native init YourApp --template react-native-template-typescript

# Move into project
cd YourApp
```

---

## 2. Add Storybook (5 min)

### Install Storybook

```bash
# Initialize Storybook
npx storybook@latest init

# Select: "Both" (native + web)
# This installs both preview modes
```

### Verify Installation

```bash
# Check package.json for scripts:
# "storybook": "storybook dev"
# "storybook-web": "storybook dev --web"

# Run Storybook (native mode)
npm run storybook

# OR run Storybook (web mode - faster)
npm run storybook-web
```

---

## 3. Install Component Library (3 min)

**Choose ONE:**

### Option A: NativeBase (Recommended)

```bash
npm install native-base react-native-svg react-native-safe-area-context
```

### Option B: React Native Paper

```bash
npm install react-native-paper react-native-vector-icons
```

### Option C: Tamagui (Mobile + Web)

```bash
npm install tamagui @tamagui/core
```

---

## 4. Create Theme (5 min)

### Create theme directory

```bash
mkdir -p src/theme
```

### src/theme/colors.ts

```typescript
export const colors = {
  // Brand
  primary: '#007AFF',
  secondary: '#5856D6',

  // Status
  success: '#34C759',
  warning: '#FF9500',
  error: '#FF3B30',

  // Neutral
  background: '#FFFFFF',
  text: '#000000',
  textSecondary: '#8E8E93',
};
```

### src/theme/spacing.ts

```typescript
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};
```

### src/theme/typography.ts

```typescript
export const typography = {
  displayLarge: {
    fontSize: 57,
    fontWeight: '700' as const,
    lineHeight: 64,
  },
  bodyLarge: {
    fontSize: 16,
    fontWeight: '400' as const,
    lineHeight: 24,
  },
};
```

---

## 5. Create First Component with Story (5 min)

### Create component

```bash
mkdir -p src/components
```

### src/components/Button.tsx

```tsx
import React from 'react';
import { Pressable, Text, StyleSheet } from 'react-native';
import { colors, spacing } from '../theme';

interface ButtonProps {
  variant?: 'primary' | 'secondary';
  children: string;
  onPress?: () => void;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  children,
  onPress,
}) => {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.button,
        variant === 'primary' ? styles.primary : styles.secondary,
      ]}
    >
      <Text style={styles.text}>{children}</Text>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  button: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: 12,
    alignItems: 'center',
  },
  primary: {
    backgroundColor: colors.primary,
  },
  secondary: {
    backgroundColor: colors.secondary,
  },
  text: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
```

### src/components/Button.stories.tsx

```tsx
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

---

## 6. Test Storybook (2 min)

### Run Storybook

```bash
# Web mode (faster, browser preview)
npm run storybook-web
# Opens at http://localhost:6006

# OR native mode (device/simulator)
npm run storybook
```

### View Your Component

1. Navigate to "Components/Button" in Storybook
2. See Primary and Secondary variants
3. Edit Button.tsx and save
4. See changes in ~1s (Fast Refresh) 🎉

---

## 7. Run Full App (2 min)

### iOS

```bash
# Run on iOS Simulator
npm run ios

# OR specific simulator
npx react-native run-ios --simulator="iPhone 15 Pro"
```

### Android

```bash
# Start Android emulator first, then:
npm run android
```

---

## 9. Development Loop

### Component Development (Storybook)

```
1. Run Storybook (npm run storybook-web)
2. Create component (e.g., Card.tsx)
3. Create story (Card.stories.tsx)
4. Edit → Save → See changes in 1s
5. Test all states (default, loading, error)
6. Use in app
```

### App Development

```
1. Run app (npm run ios / npm run android)
2. Import components from Storybook
3. Edit → Save → Fast Refresh (~1s)
4. Test on both platforms
```

---

## 10. Platform-Specific Code (If Needed)

```tsx
import { Platform } from 'react-native';

const styles = StyleSheet.create({
  container: {
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 4,
      },
      android: {
        elevation: 4,
      },
    }),
  },
});
```

---

## Next Steps

**Read complete workflow:**
- `{{CATALYST_ROOT}}/global/docs/Mobile_App_Workflow.md`

**Reference docs:**
- `docs/MOBILE_WORKFLOW.md` - React Native details
- `docs/STORYBOOK_SETUP.md` - Storybook deep dive

**Component libraries:**
- NativeBase: https://nativebase.io
- React Native Paper: https://reactnativepaper.com
- Tamagui: https://tamagui.dev

---

## Troubleshooting

**Storybook not showing components?**
1. Check story file ends with `.stories.tsx`
2. Verify `export default meta` and story exports
3. Restart Storybook

**Metro bundler errors?**
```bash
# Clear cache
npm start -- --reset-cache

# Clean install
rm -rf node_modules && npm install
```

**iOS build fails?**
```bash
cd ios && pod install && cd ..
npm run ios
```

**Android build fails?**
```bash
cd android && ./gradlew clean && cd ..
npm run android
```

---

## Project Structure

```
your-app/
├── src/
│   ├── components/
│   │   ├── Button.tsx
│   │   └── Button.stories.tsx
│   ├── screens/
│   ├── theme/
│   │   ├── colors.ts
│   │   ├── spacing.ts
│   │   └── typography.ts
│   └── App.tsx
├── .storybook/
│   └── main.ts
├── android/
├── ios/
└── package.json
```

---

*React Native Quick Start - Huxley Template*
