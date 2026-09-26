#!/bin/bash
# Schedule automated autopsy runs for Huxley
# Integrates with existing daily audit system

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CATALYST_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Log file for autopsy runs
AUTOPSY_LOG="$CATALYST_ROOT/registry/autopsy.log"

# Function to run autopsy and log results
run_autopsy() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) - Starting automated autopsy" >> "$AUTOPSY_LOG"
    
    cd "$CATALYST_ROOT"
    
    # Run the autopsy agent
    if python3 tools/capsule_autopsy_agent.py batch --max-age 1 >> "$AUTOPSY_LOG" 2>&1; then
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) - Autopsy completed successfully" >> "$AUTOPSY_LOG"
    else
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) - Autopsy failed with error code $?" >> "$AUTOPSY_LOG"
    fi
    
    # Log event to main events log using standardized logger
CATALYST_ROOT="$CATALYST_ROOT" python3 - <<'PY'
import os
from pathlib import Path
import sys

catalyst_root = Path(os.environ["CATALYST_ROOT"])
sys.path.insert(0, str(catalyst_root / "tools"))

from events_logger import EventLogger

EventLogger(capsule_slug="system").log_event(
    event_type="autopsy_scheduled",
    metadata={"source": "schedule_autopsy"},
    level="INFO",
    message="Scheduled autopsy run completed"
)
PY
}

# If called with "install", set up cron job
if [[ "$1" == "install" ]]; then
    echo "Installing autopsy cron job..."
    
    # Create cron entry to run autopsy every 4 hours
    CRON_ENTRY="0 */4 * * * $SCRIPT_DIR/schedule_autopsy.sh run"
    
    # Add to crontab if not already present
    (crontab -l 2>/dev/null | grep -v "schedule_autopsy.sh"; echo "$CRON_ENTRY") | crontab -
    
    echo "Autopsy scheduled to run every 4 hours"
    echo "View logs: tail -f $AUTOPSY_LOG"
    
elif [[ "$1" == "uninstall" ]]; then
    echo "Removing autopsy cron job..."
    crontab -l 2>/dev/null | grep -v "schedule_autopsy.sh" | crontab -
    echo "Autopsy cron job removed"
    
elif [[ "$1" == "run" ]]; then
    # Called by cron
    run_autopsy
    
else
    echo "Huxley Autopsy Scheduler"
    echo "Usage: $0 {install|uninstall|run}"
    echo ""
    echo "Commands:"
    echo "  install   - Set up automated autopsy to run every 4 hours"
    echo "  uninstall - Remove automated autopsy"
    echo "  run       - Run autopsy now (used by cron)"
    echo ""
    echo "Manual run: python3 tools/capsule_autopsy_agent.py batch"
fi
