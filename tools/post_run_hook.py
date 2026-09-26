#!/usr/bin/env python3
"""
Post-Run Hook - Automatically trigger autopsy after capsule runs
Call this from capsule workflows to ensure every run gets analyzed
"""

import sys
import pathlib
import subprocess
import json
from datetime import datetime

CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")

def trigger_autopsy(capsule_name: str, run_id: str = None, background: bool = True):
    """Trigger autopsy for a capsule run"""
    autopsy_script = CATALYST_ROOT / "tools" / "capsule_autopsy.py"
    
    if not autopsy_script.exists():
        print(f"Warning: Autopsy script not found at {autopsy_script}")
        return False
    
    cmd = [sys.executable, str(autopsy_script), capsule_name]
    if run_id:
        cmd.extend(["--run-id", run_id])
    
    try:
        if background:
            # Run in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            print(f"🔍 Autopsy started in background (PID: {process.pid}) for {capsule_name}")
        else:
            # Run synchronously
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Autopsy completed for {capsule_name}")
            else:
                print(f"❌ Autopsy failed for {capsule_name}: {result.stderr}")
        
        return True
    except Exception as e:
        print(f"Failed to trigger autopsy: {e}")
        return False

def main():
    """CLI interface for post-run hook"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Post-Run Hook - Trigger Autopsy")
    parser.add_argument("capsule_name", help="Name of capsule that finished running")
    parser.add_argument("--run-id", "-r", help="Specific run ID")
    parser.add_argument("--sync", action="store_true", help="Run autopsy synchronously")
    
    args = parser.parse_args()
    
    success = trigger_autopsy(
        capsule_name=args.capsule_name,
        run_id=args.run_id,
        background=not args.sync
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()