#!/bin/bash

# iTerm2 Configuration Optimizer for Huxley
# This script helps configure iTerm2 for optimal development experience

echo "🚀 iTerm2 Configuration Optimizer for Huxley"
echo "===================================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_section() {
    echo -e "${BLUE}$1${NC}"
}

print_recommendation() {
    echo -e "  ${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "  ${YELLOW}⚠${NC} $1"
}

print_section "📋 Configuration Checklist"
echo ""

print_section "1. Profile Configuration:"
print_recommendation "Set working directory to {{CATALYST_ROOT}}"
print_recommendation "Configure 'Send text at start' to 'claude' for auto-launch"
print_recommendation "Set up color scheme (Solarized Dark or Dracula recommended)"
print_recommendation "Configure font (JetBrains Mono 13-14pt recommended)"

echo ""
print_section "2. Performance Settings:"
print_recommendation "Enable GPU rendering in Advanced settings"
print_recommendation "Set scrollback buffer to 10,000+ lines"
print_recommendation "Enable shell integration for better navigation"

echo ""
print_section "3. Huxley-Specific Setup:"
print_recommendation "Create separate profiles for standard and standard"
print_recommendation "Set up triggers for error/warning highlighting"
print_recommendation "Configure status bar with git branch and directory"

echo ""
print_section "4. Hotkeys & Navigation:"
print_recommendation "Set up hotkey window (Cmd+\` or Option+Space)"
print_recommendation "Configure split pane shortcuts"
print_recommendation "Enable semantic history for code navigation"

echo ""
print_section "5. Recommended Color Schemes:"
print_recommendation "Solarized Dark - Easy on eyes for long sessions"
print_recommendation "Dracula - Good contrast for code"
print_recommendation "Material Design - Modern and clean"

echo ""
print_section "6. Essential Hotkeys to Configure:"
echo "  • Cmd+D: Split pane vertically"
echo "  • Cmd+Shift+D: Split pane horizontally"
echo "  • Cmd+[/]: Navigate between panes"
echo "  • Cmd+T: New tab"
echo "  • Cmd+Shift+Enter: Maximize current pane"

echo ""
print_warning "Full configuration guide being created..."

# Create comprehensive documentation
cat > {{CATALYST_ROOT}}/docs/iterm_best_practices.md << 'ENDOFDOC'
# iTerm2 Best Configuration for Huxley

## Quick Setup Guide

### 1. Essential Profile Settings

Open iTerm2 → Preferences (Cmd+,) → Profiles

#### General Tab
- **Profile Name**: "Huxley"
- **Command**: Login Shell
- **Working Directory**: Directory → `{{CATALYST_ROOT}}`
- **Send text at start**: `claude`

#### Colors Tab
- **Color Presets**: Choose Solarized Dark, Dracula, or Material
- **Minimum Contrast**: 30-40%
- **Cursor**: Box, Blinking enabled

#### Text Tab
- **Font**: JetBrains Mono, 13-14pt
- **Use ligatures**: ✓ (if font supports)
- **Vertical spacing**: 110-120%

#### Terminal Tab
- **Scrollback lines**: 20,000
- **Character Encoding**: UTF-8
- **Report Terminal Type**: xterm-256color

#### Keys Tab
Add these key mappings:
- Cmd+D → Split Vertically
- Cmd+Shift+D → Split Horizontally
- Cmd+[ / Cmd+] → Navigate Panes
- Cmd+Shift+Enter → Zoom Pane

### 2. Advanced Features

#### Status Bar
Preferences → Profiles → Session → Configure Status Bar
- Add: Current Directory, Git Branch, CPU, Memory
- Position: Bottom

#### Triggers
Preferences → Profiles → Advanced → Triggers
- Add regex patterns for error/warning highlighting
- `\[ERROR\]|error` → Highlight Red
- `\[WARNING\]|warning` → Highlight Yellow
- `\[SUCCESS\]|success` → Highlight Green
- `\[PRIVATE\]` → Highlight Purple

#### Shell Integration
Install for better navigation:
Run: curl -L https://iterm2.com/shell_integration/install_shell_integration.sh | bash

### 3. Huxley-Specific Profiles

Create two additional profiles:

#### standard Profile
- Name: "standard"
- Badge: "⚡ Fast"
- Working Directory: `{{CATALYST_ROOT}}/capsules/standard`
- Background: Slight blue tint (#001122)

#### standard Profile  
- Name: "standard"
- Badge: "🏗️ Deep"
- Working Directory: `{{CATALYST_ROOT}}/capsules/standard`
- Background: Slight green tint (#002211)

### 4. Performance Optimizations

- Enable GPU rendering (Advanced settings)
- Disable background images
- Limit transparency to 5-10%
- Use native fullscreen windows

### 5. Backup Configuration

Export settings:
defaults export com.googlecode.iterm2 ~/iterm-backup.plist

Import settings:
defaults import com.googlecode.iterm2 ~/iterm-backup.plist
ENDOFDOC

echo ""
print_section "✅ Setup Complete!"
echo ""
echo "Documentation created at: docs/iterm_best_practices.md"
echo ""
print_section "🎯 Next Steps:"
echo "1. Open iTerm Preferences: Cmd+,"
echo "2. Follow the guide in docs/iterm_best_practices.md"
echo "3. Install shell integration for enhanced features"
echo ""
echo "To install shell integration now, run:"
echo "curl -L https://iterm2.com/shell_integration/install_shell_integration.sh | bash"

