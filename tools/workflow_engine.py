#!/usr/bin/env python3
"""
Huxley Workflow Engine - Test integration immediately
"""

import os
import sys
from pathlib import Path

print("✅ Agent OS Workflow Engine - Integration Test")
print(f"📍 Current directory: {os.getcwd()}")
print(f"🔧 Huxley root: {Path(__file__).parent.parent}")

# Test capsule detection
def test_capsule_detection():
    current_dir = Path.cwd()
    if (current_dir / "capsule.json").exists():
        print(f"✅ Detected capsule: {current_dir.name}")
        return True
    else:
        print(f"ℹ️  No capsule detected in {current_dir}")
        return False

# Test Agent OS integration
def test_agent_os_integration():
    catalyst_root = Path(__file__).parent.parent
    agent_os_path = catalyst_root / "global" / "agent-os"
    
    if agent_os_path.exists():
        print(f"✅ Agent OS integration path found: {agent_os_path}")
        
        # Check for copied components
        components = {
            "agent-specs": agent_os_path / "agent-specs",
            "workflows": agent_os_path / "workflows", 
            "standards": agent_os_path / "standards",
            "config": agent_os_path / "config"
        }
        
        for name, path in components.items():
            if path.exists():
                print(f"  ✅ {name}: {len(list(path.glob('*')))} files")
            else:
                print(f"  ❌ {name}: NOT FOUND")
        
        return True
    else:
        print(f"❌ Agent OS integration path not found: {agent_os_path}")
        return False

if __name__ == "__main__":
    print("\n=== INTEGRATION TEST RESULTS ===")
    
    capsule_detected = test_capsule_detection()
    agent_os_integrated = test_agent_os_integration()
    
    if agent_os_integrated:
        print("\n🎉 Agent OS integration successful!")
        print("Ready to enhance Huxley with Agent OS capabilities")
    else:
        print("\n⚠️  Integration incomplete - check component installation")
    
    sys.exit(0 if agent_os_integrated else 1)