#!/usr/bin/env python3
import json
import sys
import os
from pathlib import Path

def main():
    with open('/tmp/claude_hook_debug_detailed.log', 'a') as f:
        f.write(f"=== Hook Debug Test ===\n")
        f.write(f"Working directory: {os.getcwd()}\n")
        f.write(f"Python path: {sys.executable}\n")
        f.write(f"Environment OPENAI_API_KEY: {'Yes' if os.environ.get('OPENAI_API_KEY') else 'No'}\n")
        
        # Test settings file access
        settings_files = [
            Path.home() / '.claude' / 'settings.local.json',
            Path.home() / '.claude' / '.claude' / 'settings.json',
        ]
        
        for settings_path in settings_files:
            f.write(f"Settings file {settings_path}: {'EXISTS' if settings_path.exists() else 'MISSING'}\n")
            if settings_path.exists():
                try:
                    with open(settings_path, 'r') as sf:
                        settings = json.load(sf)
                        api_key = settings.get('env', {}).get('OPENAI_API_KEY')
                        f.write(f"  API Key in {settings_path.name}: {'Found' if api_key else 'Missing'}\n")
                except Exception as e:
                    f.write(f"  Error reading {settings_path.name}: {e}\n")
        
        # Test stdin input
        input_data = sys.stdin.read()
        f.write(f"Input data: {input_data[:100]}...\n")
        f.write(f"Input length: {len(input_data)}\n")
        f.write("=== End Debug ===\n\n")

if __name__ == "__main__":
    main()
