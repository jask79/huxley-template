#!/usr/bin/env python3
"""
UI Pack Resolver - Determines which UI libraries are available for a capsule
and configures the Frontend Specialist agent accordingly.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

class UIPackResolver:
    def __init__(self, capsule_root: str):
        self.capsule_root = Path(capsule_root)
        self.ui_pack_path = self.capsule_root / "ops" / "ui-pack.json"
        self.mcp_config_path = self.capsule_root / "ops" / "mcp.json"
        
    def resolve_ui_pack(self) -> Dict[str, Any]:
        """Resolve UI pack configuration for this capsule."""
        if not self.ui_pack_path.exists():
            return self._get_default_pack()
            
        try:
            with open(self.ui_pack_path) as f:
                pack_config = json.load(f)
                
            # Validate and enrich configuration
            return self._validate_pack_config(pack_config)
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Invalid ui-pack.json: {e}, using defaults")
            return self._get_default_pack()
    
    def _get_default_pack(self) -> Dict[str, Any]:
        """Default UI pack (modern-web)."""
        return {
            "pack": "modern-web",
            "description": "Default modern web stack",
            "libraries": {
                "shadcn-ui": {"enabled": True, "priority": 1},
                "radix-ui": {"enabled": True, "priority": 2},
                "tailwindcss": {"enabled": True, "priority": 1}
            },
            "constraints": {
                "bundle_size": "< 500kb",
                "accessibility": "WCAG 2.1 AA"
            }
        }
    
    def _validate_pack_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize pack configuration."""
        required_keys = ["pack", "libraries"]
        for key in required_keys:
            if key not in config:
                raise KeyError(f"Missing required key: {key}")
        
        # Sort libraries by priority
        libraries = config["libraries"]
        for lib_name, lib_config in libraries.items():
            if "priority" not in lib_config:
                lib_config["priority"] = 99
        
        return config
    
    def get_enabled_libraries(self) -> List[str]:
        """Get list of enabled UI libraries in priority order."""
        config = self.resolve_ui_pack()
        libraries = config.get("libraries", {})
        
        enabled = [
            (name, lib.get("priority", 99))
            for name, lib in libraries.items()
            if lib.get("enabled", False)
        ]
        
        # Sort by priority (lower number = higher priority)
        enabled.sort(key=lambda x: x[1])
        return [name for name, _ in enabled]
    
    def get_agent_instructions(self) -> Dict[str, str]:
        """Get agent-specific instructions for this UI pack."""
        config = self.resolve_ui_pack()
        return config.get("agent_instructions", {})
    
    def get_constraints(self) -> Dict[str, Any]:
        """Get UI pack constraints."""
        config = self.resolve_ui_pack()
        return config.get("constraints", {})

def main():
    """CLI interface for UI pack resolution."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: ui_pack_resolver.py <capsule_path>")
        sys.exit(1)
    
    capsule_path = sys.argv[1]
    resolver = UIPackResolver(capsule_path)
    
    print("UI Pack Configuration:")
    print("=====================")
    
    config = resolver.resolve_ui_pack()
    print(f"Pack: {config['pack']}")
    print(f"Description: {config.get('description', 'N/A')}")
    
    print("\nEnabled Libraries (priority order):")
    for lib in resolver.get_enabled_libraries():
        print(f"  - {lib}")
    
    print("\nConstraints:")
    for key, value in resolver.get_constraints().items():
        print(f"  {key}: {value}")
    
    print("\nAgent Instructions:")
    for key, value in resolver.get_agent_instructions().items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()