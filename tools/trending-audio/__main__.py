"""Allow `python3 -m trending_audio` invocation."""

import sys

from .cli import main

sys.exit(main())
