#!/usr/bin/env python3
"""Debug version of PostToolUse hook to diagnose why it's not firing"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Log EVERYTHING to a debug file
debug_log = Path(os.environ.get("CATALYST_ROOT", str(Path(__file__).resolve().parent.parent))) / "registry" / "post_tool_use_debug.log"

try:
    # Log that we started
    with open(debug_log, 'a') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"HOOK STARTED: {datetime.now().isoformat()}\n")
        f.write(f"{'='*80}\n")

    # Try to read stdin
    try:
        stdin_data = sys.stdin.read()
        with open(debug_log, 'a') as f:
            f.write(f"STDIN RECEIVED ({len(stdin_data)} bytes):\n{stdin_data}\n\n")

        hook_input = json.loads(stdin_data)
        tool_name = hook_input.get("tool_name", "UNKNOWN")

        with open(debug_log, 'a') as f:
            f.write(f"PARSED: tool_name = {tool_name}\n")
            f.write(f"Full input:\n{json.dumps(hook_input, indent=2)}\n\n")

    except Exception as e:
        with open(debug_log, 'a') as f:
            f.write(f"ERROR parsing stdin: {e}\n")

    # Output valid PostToolUse response (empty object = allow normal processing)
    print(json.dumps({}))

    with open(debug_log, 'a') as f:
        f.write(f"HOOK COMPLETED SUCCESSFULLY\n")

    sys.exit(0)

except Exception as e:
    with open(debug_log, 'a') as f:
        f.write(f"FATAL ERROR: {e}\n")
        import traceback
        f.write(traceback.format_exc())
    sys.exit(0)
