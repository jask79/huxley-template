"""Allow running as `python3 tools/tiktok-intel/` (directory execution)."""

import sys
from pathlib import Path

# When Python runs a directory, it executes __main__.py with __package__=None.
# Delegate to cli.py which handles the import bootstrapping.
_dir = Path(__file__).resolve().parent
exec((_dir / "cli.py").read_text(), {"__name__": "__main__", "__file__": str(_dir / "cli.py")})
