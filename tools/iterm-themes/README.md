# Huxley iTerm Themes

Terminal themes matching the Huxley system aesthetic.

## Available Themes

| Theme | File | Description |
|-------|------|-------------|
| **Huxley** | `Huxley.itermcolors` | Dark mode - deep dark background |
| **Huxley-Light** | `Huxley-Light.itermcolors` | Light mode - warm off-white background |

## Installation

1. **Double-click** the `.itermcolors` file to import into iTerm2
2. Open **iTerm2 > Settings > Profiles > Colors**
3. Select theme from the "Color Presets..." dropdown

## Color Mapping

| iTerm Element | Huxley Token | Hex | Purpose |
|---------------|---------------|-----|---------|
| Background | `terminalDark` | `#0A0E1A` | Deep dark primary |
| Foreground | `terminalText` | `#F0F0FA` | Near-white text |
| Cursor | `terminalCyan` | `#00D9FF` | Claude/AI accent |
| Selection | `terminalCard` | `#191E30` | Card backgrounds |
| Tab Color | `terminalInputBackground` | `#141928` | Input fields |

### ANSI Colors

| Color | Normal | Bright |
|-------|--------|--------|
| Black | `#0A0E1A` (terminalDark) | `#323B4B` (terminalBorder) |
| Red | `#F87171` (terminalRed) | `#FF9696` |
| Green | `#4ADE80` (terminalGreen) | `#70EBA0` |
| Yellow | `#FACC15` (terminalYellow) | `#FFDD55` |
| Blue | `#00D9FF` (terminalCyan) | `#66E6FF` |
| Magenta | `#FF6B9D` (terminalPink) | `#A78BFA` (terminalPurple) |
| Cyan | `#00D9FF` (terminalCyan) | `#80EBFF` |
| White | `#F0F0FA` (terminalText) | `#FFFFFF` |

## Design Philosophy

- **Deep dark background** (`#0A0E1A`) - matches the iOS app's terminal aesthetic
- **Cyan accent** (`#00D9FF`) - the signature Huxley/Claude color for cursor and links
- **Pink for user interaction** (`#FF6B9D`) - mirrors the mobile app's user bubble color
- **Muted borders** (`#323B4B`) - subtle separation without harsh contrast

## Source

Extracted from:
- `capsules/example-mobile-capsule/src/Extensions/Color+Terminal.swift`
- `capsules/example-mobile-capsule/Packages/ExampleKit/Sources/ExampleChatUI/ChatTheme.swift`
