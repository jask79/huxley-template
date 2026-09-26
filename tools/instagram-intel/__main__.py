"""Allow running as `python3 tools/instagram-intel/` (directory execution)."""

import runpy
import sys
from pathlib import Path

# When Python runs a directory, it executes __main__.py.
# Delegate to cli.py via runpy (proper module execution, not exec).
_cli = str(Path(__file__).resolve().parent / "cli.py")
sys.exit(runpy.run_path(_cli, run_name="__main__"))
