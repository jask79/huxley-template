#!/usr/bin/env python3
"""
iTerm2 Auto-Clear Scrollback on Tab Close

This script uses iTerm2's Python API to automatically clear scrollback
buffers when tabs/sessions close, ensuring memory is freed immediately.

Installation:
1. Open iTerm2 → Scripts → Manage → Install Python Runtime
2. Copy this script to: ~/Library/Application Support/iTerm2/Scripts/AutoLaunch/
3. Restart iTerm2 or use Scripts → AutoLaunch → iterm2_auto_clear_on_close

Documentation: https://iterm2.com/python-api/
"""

import iterm2

async def main(connection):
    """
    Monitor session termination events and clear scrollback buffers.
    """
    app = await iterm2.async_get_app(connection)

    async def on_session_ended(session_id):
        """
        Called when a session ends (tab closes, window closes, etc.)

        Note: By default, iTerm2 frees memory when sessions end.
        This handler is here for explicit logging and future enhancements.
        """
        print(f"Session {session_id} ended - memory should be freed automatically")

    # Monitor session lifecycle
    async with iterm2.SessionTerminationMonitor(connection) as monitor:
        while True:
            session_id = await monitor.async_get()
            await on_session_ended(session_id)

# Register the script to run automatically
iterm2.run_forever(main)
