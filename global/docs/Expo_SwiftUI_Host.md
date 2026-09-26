# Expo UI — SwiftUI Host Component Reference

## Overview

`@expo/ui/swift-ui` provides a `<Host>` component that embeds SwiftUI views directly inside React Native's view tree. This is the zero-bridging-code approach for using SwiftUI components like buttons, pickers, sliders, and gauges in your React Native app.

**Requirement:** Expo SDK 54+, iOS only.

```bash
npx expo install @expo/ui
```

## Host Component

The `<Host>` component wraps SwiftUI children and manages their layout within React Native:

```tsx
import { Host, Button } from '@expo/ui/swift-ui';

export function SaveButton() {
  return (
    <Host style={{ flex: 1 }}>
      <Button variant="default">Save changes</Button>
    </Host>
  );
}
```

### Sizing Options

**Flexbox sizing (standard):**
```tsx
<Host style={{ flex: 1 }}>
  {/* SwiftUI content fills available space */}
</Host>
```

**Match contents (intrinsic size):**
```tsx
<Host matchContents>
  {/* Host shrinks to fit SwiftUI content */}
</Host>
```

**Fixed size:**
```tsx
<Host style={{ width: 300, height: 200 }}>
  {/* Fixed dimensions */}
</Host>
```

## Available Components

### Button

```tsx
import { Button, Host } from '@expo/ui/swift-ui';

<Host style={{ flex: 1 }}>
  <Button
    variant="default"
    onPress={() => setEditingProfile(true)}>
    Edit profile
  </Button>
</Host>
```

### Text

```tsx
import { Text, Host, VStack } from '@expo/ui/swift-ui';

<Host style={{ flex: 1 }}>
  <VStack spacing={8}>
    <Text>Hello, world!</Text>
  </VStack>
</Host>
```

### Switch (Toggle)

```tsx
import { Host, Switch } from '@expo/ui/swift-ui';

<Host matchContents>
  <Switch
    checked={checked}
    onValueChange={(checked) => setChecked(checked)}
    color="#ff0000"
    label="Play music"
    variant="switch"
  />
</Host>
```

### Switch (Checkbox)

```tsx
import { Host, Switch } from '@expo/ui/swift-ui';

<Host matchContents>
  <Switch
    checked={checked}
    onValueChange={(checked) => setChecked(checked)}
    label="Play music"
    variant="checkbox"
  />
</Host>
```

### Picker (Segmented)

```tsx
import { Host, Picker } from '@expo/ui/swift-ui';

<Host matchContents>
  <Picker
    options={['$', '$$', '$$$', '$$$$']}
    selectedIndex={selectedIndex}
    onOptionSelected={({ nativeEvent: { index } }) => {
      setSelectedIndex(index);
    }}
    variant="segmented"
  />
</Host>
```

### Picker (Wheel)

```tsx
import { Host, Picker } from '@expo/ui/swift-ui';

<Host style={{ height: 100 }}>
  <Picker
    options={['$', '$$', '$$$', '$$$$']}
    selectedIndex={selectedIndex}
    onOptionSelected={({ nativeEvent: { index } }) => {
      setSelectedIndex(index);
    }}
    variant="wheel"
  />
</Host>
```

### Slider

```tsx
import { Host, Slider } from '@expo/ui/swift-ui';

<Host style={{ minHeight: 60 }}>
  <Slider
    value={value}
    onValueChange={(value) => setValue(value)}
  />
</Host>
```

### TextField

```tsx
import { Host, TextField } from '@expo/ui/swift-ui';

<Host matchContents>
  <TextField
    autocorrection={false}
    defaultValue="A single line text input"
    onChangeText={setValue}
  />
</Host>
```

### LinearProgress

```tsx
import { LinearProgress, Host } from '@expo/ui/swift-ui';

<Host style={{ width: 300 }}>
  <LinearProgress progress={0.5} color="red" />
</Host>
```

### CircularProgress

```tsx
import { CircularProgress, Host } from '@expo/ui/swift-ui';

<Host style={{ width: 300 }}>
  <CircularProgress progress={0.5} color="blue" />
</Host>
```

### Gauge (Circular Capacity)

```tsx
import { Gauge, Host } from '@expo/ui/swift-ui';
import { PlatformColor } from 'react-native';

<Host matchContents>
  <Gauge
    max={{ value: 1, label: '1' }}
    min={{ value: 0, label: '0' }}
    current={{ value: 0.5 }}
    color={[
      PlatformColor('systemRed'),
      PlatformColor('systemOrange'),
      PlatformColor('systemYellow'),
      PlatformColor('systemGreen'),
    ]}
    type="circularCapacity"
  />
</Host>
```

### ColorPicker

```tsx
import { ColorPicker, Host } from '@expo/ui/swift-ui';

<Host style={{ width: 400, height: 200 }}>
  <ColorPicker
    label="Select a color"
    selection={color}
    onValueChanged={setColor}
  />
</Host>
```

### List

```tsx
import { Host, List } from '@expo/ui/swift-ui';

<Host style={{ flex: 1 }}>
  <List
    scrollEnabled={false}
    editModeEnabled={editModeEnabled}
    onSelectionChange={(items) => alert(`Selected: ${items.join(', ')}`)}
    moveEnabled={moveEnabled}
    onMoveItem={(from, to) => alert(`Moved ${from} to ${to}`)}
    onDeleteItem={(item) => alert(`Deleted: ${item}`)}
    listStyle="automatic"
    deleteEnabled={deleteEnabled}
    selectEnabled={selectEnabled}>
    {data.map((item, index) => (
      <LabelPrimitive key={index} title={item.text} systemImage={item.systemImage} />
    ))}
  </List>
</Host>
```

### BottomSheet

```tsx
import { BottomSheet, Host, Text } from '@expo/ui/swift-ui';
import { useWindowDimensions } from 'react-native';

const { width } = useWindowDimensions();

<Host style={{ position: 'absolute', width }}>
  <BottomSheet isOpened={isOpened} onIsOpenedChange={(e) => setIsOpened(e)}>
    <Text>Hello, world!</Text>
  </BottomSheet>
</Host>
```

### Layout: VStack

```tsx
import { Button, Host, VStack, Text } from '@expo/ui/swift-ui';

<Host style={{ flex: 1 }}>
  <VStack spacing={8}>
    <Text>Hello, world!</Text>
    <Button onPress={() => console.log('Pressed')}>
      Click
    </Button>
  </VStack>
</Host>
```

## Glass Effect (Liquid Glass)

For Liquid Glass effects, use `expo-glass-effect` (NOT Host):

```bash
npx expo install expo-glass-effect
```

```tsx
import { GlassView } from 'expo-glass-effect';

<GlassView style={styles.glassView} />
<GlassView style={styles.glassView} glassEffectStyle="clear" />
```

**Note:** `GlassView` is only available on iOS 26+. It falls back to a regular `View` on unsupported platforms. Use `isGlassEffectAPIAvailable` for runtime detection.

## When to Use Host vs Custom Module

| Scenario | Approach |
|----------|----------|
| Standard SwiftUI controls (Button, Picker, etc.) | `<Host>` + `@expo/ui/swift-ui` |
| Custom SwiftUI view with complex logic | Custom Expo Module with `View()` definition |
| Glass/material effects | `expo-glass-effect` |
| Non-visual native functionality | Custom Expo Module with `Function()` |
| Platform-specific UI requiring UIKit | Custom Expo Module extending `ExpoView` |

## Platform Notes

- **iOS only** — `@expo/ui/swift-ui` components are not available on Android
- Some components are **not available on Apple TV** (Slider, ColorPicker, Gauge wheel variant)
- Use `Platform.OS === 'ios'` guards when sharing code cross-platform
- The `<Host>` component itself renders as a regular `View` on non-iOS platforms

## References

- [Expo: SwiftUI Guide](https://docs.expo.dev/guides/expo-ui-swift-ui/)
- [Expo: Glass Effect](https://docs.expo.dev/versions/latest/sdk/glass-effect/)
- Companion doc: `Expo_Module_Authoring.md` (for custom native modules)
- Companion doc: `RN_Swift_Hybrid_Patterns.md` (architecture overview)
