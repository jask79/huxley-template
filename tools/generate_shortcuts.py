#!/usr/bin/env python3
"""
Huxley - iOS Shortcuts Generation
Generates iOS Shortcuts from capsule specifications using Cherri language
"""

import os
import sys
import yaml
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Huxley paths
CATALYST_ROOT = Path(os.environ.get("CATALYST_ROOT", Path(__file__).resolve().parent.parent))

# Find Cherri CLI - multiple possible locations
CHERRI_PATHS = [
    "/Applications/Cherri.app/Contents/MacOS/Cherri",
    "/Applications/Cherri.app/Contents/MacOS/cherri", 
    "/usr/local/bin/cherri",
    "/opt/homebrew/bin/cherri",
    Path.home() / ".local/bin/cherri"
]

def find_cherri_cli():
    """Find the Cherri CLI binary"""
    for path in CHERRI_PATHS:
        if Path(path).exists():
            return str(path)
    return None

CHERRI_CLI = find_cherri_cli() or "{{CATALYST_ROOT}}/testing/cherri-cli/cherri"

class CherriShortcutGenerator:
    def __init__(self, capsule_path: Path, ide_preference: str = "cursor", agent_mode: bool = False):
        self.capsule_path = Path(capsule_path)
        self.ide_preference = ide_preference
        self.agent_mode = agent_mode
        self.spec_path = self.capsule_path / "spec" / "requirements.yaml"
        self.shortcuts_src = self.capsule_path / "src" / "shortcuts" 
        self.shortcuts_generated = self.shortcuts_src / "generated"
        self.shortcuts_ops = self.capsule_path / "ops" / "shortcuts"
        
        # Create directories
        self.shortcuts_generated.mkdir(parents=True, exist_ok=True)
        self.shortcuts_ops.mkdir(parents=True, exist_ok=True)
        
    def load_spec(self) -> Dict[str, Any]:
        """Load capsule specification"""
        if not self.spec_path.exists():
            raise FileNotFoundError(f"Specification not found: {self.spec_path}")
            
        with open(self.spec_path, 'r') as f:
            return yaml.safe_load(f)
    
    def generate_cherri_source(self, shortcut_spec: Dict[str, Any]) -> str:
        """Generate Cherri source code from shortcut specification"""
        name = shortcut_spec.get('name', 'UnnamedShortcut')
        icon = shortcut_spec.get('icon', 'gear')
        color = shortcut_spec.get('color', 'blue')
        actions = shortcut_spec.get('actions', [])
        
        # Clean name for Cherri (no spaces, special chars)
        clean_name = ''.join(c for c in name if c.isalnum())
        
        # Start building Cherri source with correct syntax
        cherri_lines = [
            f'/* Generated shortcut: {name} */',
            f'/* Generated on: {datetime.now().isoformat()} */',
            '',
            f'#define color {color}',
            f'#define glyph {icon}',
            f'#define name {clean_name}',
            '',
            '// Huxley variables',
            '@builderSystem = "Huxley automation"',
            ''
        ]
        
        # Convert actions to Cherri
        for action in actions:
            cherri_lines.extend(self._convert_action_to_cherri(action))
        
        # Add Huxley completion message
        cherri_lines.extend([
            '',
            '// Huxley completion',
            f'@completionMessage = "Shortcut executed from {self.capsule_path.name} capsule"',
            'alert(completionMessage)'
        ])
        
        return '\n'.join(cherri_lines)
    
    def _convert_action_to_cherri(self, action: Dict[str, Any]) -> List[str]:
        """Convert individual action specification to Cherri code"""
        action_type = action.get('type', '')
        params = action.get('parameters', {})
        
        cherri_lines = [f'// Action: {action_type}']
        
        # Map common action types to Cherri actions with correct syntax
        if action_type == 'get_text':
            text = params.get('text', 'Hello World')
            cherri_lines.append(f'@actionText = "{text}"')
            
        elif action_type == 'show_result':
            cherri_lines.append('// Show result action - handled by alert')
            
        elif action_type == 'get_url':
            url = params.get('url', 'https://example.com')
            cherri_lines.append(f'@url = "{url}"')
            cherri_lines.append('// URL content would be fetched here')
            
        elif action_type == 'show_alert':
            title = params.get('title', 'Alert')
            message = params.get('message', 'Message')
            cherri_lines.append(f'@alertTitle = "{title}"')
            cherri_lines.append(f'@alertMessage = "{message}"')
            cherri_lines.append('alert(alertMessage, alertTitle)')
            
        elif action_type == 'ssh_connect':
            target = params.get('target', 'builder_server')
            cherri_lines.append(f'@sshTarget = "{target}"')
            cherri_lines.append('// SSH connection would be established here')
            
        elif action_type == 'run_command':
            command = params.get('command', 'echo "Hello"')
            cherri_lines.append(f'@command = "{command}"')
            cherri_lines.append('// Command would be executed here')
            
        elif action_type == 'take_photo':
            cherri_lines.append('// Take photo action')
            cherri_lines.append('alert("Photo taken via Huxley")')
            
        elif action_type == 'get_location':
            cherri_lines.append('// Get location action')
            cherri_lines.append('alert("Location retrieved via Huxley")')
            
        elif action_type == 'send_notification':
            title = params.get('title', 'Notification')
            body = params.get('body', 'Body')
            cherri_lines.append(f'@notifTitle = "{title}"')
            cherri_lines.append(f'@notifBody = "{body}"')
            cherri_lines.append('alert(notifBody, notifTitle)')
            
        elif action_type == 'custom':
            # Raw Cherri code
            code = params.get('code', '// Custom action')
            cherri_lines.append(code)
            
        else:
            # Unknown action - add alert
            cherri_lines.append(f'@errorMsg = "Unknown action type: {action_type}"')
            cherri_lines.append('alert(errorMsg, "Huxley Error")')
        
        cherri_lines.append('')
        return cherri_lines
    
    def generate_common_actions(self) -> str:
        """Generate common Huxley actions file"""
        return '''// Common Huxley Actions for Cherri
// Generated by Huxley automation

// Debug mode check
copy debugMode {
    const debug = GetEnvironmentVariable("BUILDER_DEBUG")
    if debug == "true" {
        ShowAlert("Debug", "Debug mode enabled")
    }
}

// Connect to Huxley server via SSH
copy connectToBuilder {
    GetText("ssh user@builder-server.com")
    RunSSHScript()
}

// Log events to Huxley
copy logBuilderEvent(text eventType, text capsule) {
    GetCurrentDate()
    GetText("{eventType} in {capsule} at {currentDate}")
    AppendToFile("{CATALYST_ROOT}/global/events.log")
}

// Error handling pattern
copy handleErrors {
    // Add error handling logic here
    // For now, just show completion
    ShowAlert("Complete", "Shortcut executed successfully")
}

// Validate SSH connection
copy validateSSHConnection {
    // Test connection before executing commands
    GetText("echo 'Connection test'")
    RunSSHScript()
}

// Huxley health check
copy checkBuilderHealth {
    GetText("{CATALYST_ROOT}/catalyst-doctor.sh")
    RunSSHScript()
    ShowResult()
}

// Trigger capsule build
action triggerCapsuleBuild(text capsuleName, text lane) {
    GetText("{CATALYST_ROOT}/tools/trigger_planner.sh")
    GetText("--lane {lane}")
    GetText("{CATALYST_ROOT}/capsules/{capsuleName}")
    CombineText()
    RunSSHScript()
}
'''
    
    def compile_shortcut(self, cherri_file: Path, output_file: Path) -> bool:
        """Compile Cherri source to iOS Shortcut"""
        try:
            # Check if Cherri CLI exists
            if not CHERRI_CLI or not Path(CHERRI_CLI).exists():
                print(f"❌ Cherri CLI not found!")
                print("Searched locations:")
                for path in CHERRI_PATHS:
                    exists = "✅" if Path(path).exists() else "❌"
                    print(f"  {exists} {path}")
                print("Please ensure Cherri is installed or add CLI to PATH")
                return False
            
            # Compile command
            cmd = [str(CHERRI_CLI), str(cherri_file)]
            
            print(f"🔨 Compiling: {cherri_file.name}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cherri_file.parent)
            
            if result.returncode == 0:
                print(f"✅ Successfully compiled: {output_file.name}")
                
                # Move compiled shortcut to ops directory
                compiled_file = cherri_file.with_suffix('.shortcut')
                if compiled_file.exists():
                    compiled_file.rename(output_file)
                    print(f"📦 Deployed to: {output_file}")
                
                return True
            else:
                print(f"❌ Compilation failed:")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error compiling shortcut: {e}")
            return False
    
    def open_in_ide(self, cherri_file: Path, ide_preference: str = "cursor") -> bool:
        """Open generated Cherri file in IDE for validation and editing"""
        try:
            if ide_preference == "cursor":
                # Try Cursor IDE first (default)
                cursor_paths = [
                    "/Applications/Cursor.app",
                    "/usr/local/bin/cursor",
                    "/opt/homebrew/bin/cursor"
                ]
                
                for cursor_path in cursor_paths:
                    if Path(cursor_path).exists():
                        print(f"🖥️  Opening in Cursor IDE: {cherri_file.name}")
                        if cursor_path.endswith(".app"):
                            result = subprocess.run(["open", "-a", cursor_path, str(cherri_file)], 
                                                  capture_output=True, text=True)
                        else:
                            result = subprocess.run([cursor_path, str(cherri_file)], 
                                                  capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            print("✅ Cursor IDE opened with syntax highlighting")
                            return True
                        break
                
                # Fallback to Cherri IDE if available
                cherri_app = "/Applications/Cherri.app"
                if Path(cherri_app).exists():
                    print(f"🔄 Falling back to Cherri IDE: {cherri_file.name}")
                    result = subprocess.run(["open", "-a", cherri_app, str(cherri_file)], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        print("✅ Cherri IDE opened")
                        return True
            
            # Default system editor as last resort
            print(f"📝 Opening with system default editor: {cherri_file.name}")
            result = subprocess.run(["open", str(cherri_file)], capture_output=True, text=True)
            return result.returncode == 0
                
        except Exception as e:
            print(f"⚠️  Could not open IDE: {e}")
            return False

    def import_to_shortcuts_app(self, shortcut_file: Path) -> bool:
        """Import generated shortcut to macOS Shortcuts app"""
        try:
            print(f"📥 Importing to Shortcuts app: {shortcut_file.name}")
            
            # Use macOS 'open' command to import shortcut
            result = subprocess.run(["open", str(shortcut_file)], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Import initiated for: {shortcut_file.name}")
                print("💡 Check Shortcuts app to confirm import")
                return True
            else:
                print(f"❌ Import failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error importing shortcut: {e}")
            return False
    
    def generate_all_shortcuts(self):
        """Generate all shortcuts defined in capsule spec"""
        try:
            spec = self.load_spec()
            shortcuts = spec.get('shortcuts', [])
            
            if not shortcuts:
                print(f"ℹ️  No shortcuts defined in {self.spec_path}")
                return
            
            # Generate common actions file
            common_file = self.shortcuts_src / "common.cherri"
            with open(common_file, 'w') as f:
                f.write(self.generate_common_actions())
            print(f"📝 Generated common actions: {common_file}")
            
            # Generate individual shortcuts
            compiled_count = 0
            for shortcut_spec in shortcuts:
                name = shortcut_spec.get('name', 'UnnamedShortcut')
                clean_name = ''.join(c for c in name if c.isalnum())
                
                # Generate Cherri source
                cherri_source = self.generate_cherri_source(shortcut_spec)
                
                # Include common actions
                cherri_source = f'#include "../common.cherri"\n\n{cherri_source}'
                
                # Write source file
                cherri_file = self.shortcuts_generated / f"{clean_name}.cherri"
                with open(cherri_file, 'w') as f:
                    f.write(cherri_source)
                
                if not self.agent_mode:
                    print(f"📝 Generated: {cherri_file}")
                
                # Open in IDE for validation and editing (skip for agents or if preference is 'none')
                if not self.agent_mode and self.ide_preference != "none":
                    self.open_in_ide(cherri_file, ide_preference=self.ide_preference)
                elif self.agent_mode:
                    # Agents get minimal output
                    print(f"Generated .cherri: {clean_name}")
                
                # Compile to shortcut
                output_file = self.shortcuts_ops / f"{clean_name}.shortcut"
                if self.compile_shortcut(cherri_file, output_file):
                    compiled_count += 1
                    # Auto-import to macOS Shortcuts app
                    self.import_to_shortcuts_app(output_file)
            
            if self.agent_mode:
                print(f"✅ Generated {compiled_count}/{len(shortcuts)} shortcuts")
            else:
                print(f"\n🎉 Generated {len(shortcuts)} shortcuts, compiled {compiled_count} successfully")
                print(f"📁 Shortcuts available in: {self.shortcuts_ops}")
            
        except Exception as e:
            print(f"❌ Error generating shortcuts: {e}")
            sys.exit(1)

def main():
    """Main entry point"""
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print("Usage: generate_shortcuts.py <capsule_path> [ide_preference] [--agent]")
        print("Example: generate_shortcuts.py {{CATALYST_ROOT}}/capsules/my-capsule")
        print("Example: generate_shortcuts.py {{CATALYST_ROOT}}/capsules/my-capsule cursor")
        print("Example: generate_shortcuts.py {{CATALYST_ROOT}}/capsules/my-capsule none --agent")
        print()
        print("IDE options:")
        print("  cursor   - Open in Cursor IDE (default for manual)")
        print("  cherri   - Open in Cherri IDE") 
        print("  none     - No IDE (default for agent mode)")
        print()
        print("Modes:")
        print("  --agent  - Agent automation mode (no IDE, silent)")
        sys.exit(1)
    
    capsule_path = Path(sys.argv[1]).expanduser()
    
    # Check for agent mode
    agent_mode = "--agent" in sys.argv
    
    # Set IDE preference based on mode
    if agent_mode:
        ide_preference = "none"  # Agents don't need IDEs
        print("🤖 Agent Mode: Automated shortcut generation")
    else:
        ide_preference = sys.argv[2] if len(sys.argv) >= 3 and not sys.argv[2].startswith("--") else "cursor"
        print("👤 Manual Mode: Interactive development")
    
    if not capsule_path.exists():
        print(f"❌ Capsule path does not exist: {capsule_path}")
        sys.exit(1)
    
    if not agent_mode:
        print(f"🚀 Huxley - iOS Shortcuts Generation")
        print(f"📁 Capsule: {capsule_path.name}")
        print(f"📍 Path: {capsule_path}")
        print(f"🖥️  IDE: {ide_preference}")
        print()
    
    generator = CherriShortcutGenerator(capsule_path, ide_preference, agent_mode)
    generator.generate_all_shortcuts()

if __name__ == "__main__":
    main()