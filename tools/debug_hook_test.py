#!/usr/bin/env python3
"""
Debug hook to test if hooks are firing at all.
This just logs that it ran and allows everything.
"""

import json
import sys
from datetime import datetime

# Log to a file so we can see if this ran
log_file = "{{CATALYST_ROOT}}/tools/hook_debug.log"

try:
    with open(log_file, 'a') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"DEBUG HOOK FIRED: {datetime.now().isoformat()}\n")
        f.write(f"{'='*60}\n")

        # Read stdin
        stdin_data = sys.stdin.read()
        f.write(f"STDIN: {stdin_data}\n")

    # Always allow
    print(json.dumps({
        "decision": "allow",
        "reason": "Debug hook - just logging"
    }))
    sys.exit(0)

except Exception as e:
    with open(log_file, 'a') as f:
        f.write(f"ERROR: {str(e)}\n")
    sys.exit(0)
