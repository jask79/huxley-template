#!/bin/bash
set -euo pipefail

# on_capsule_created.sh - Capsule creation hook wrapper
# Called by inbox_sync.py when a new capsule is imported
# Usage: on_capsule_created.sh <absolute_capsule_path>

CATALYST_ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_FILE="$CATALYST_ROOT/registry/planner-hooks.log"
TRIGGER_SCRIPT="$CATALYST_ROOT/tools/trigger_planner.sh"

# Validate arguments
if [ $# -ne 1 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: on_capsule_created.sh requires capsule path argument" >> "$LOG_FILE"
    exit 1
fi

CAPSULE_PATH="$1"
CAPSULE_NAME=$(basename "$CAPSULE_PATH")

# Log hook activation
echo "[$(date '+%Y-%m-%d %H:%M:%S')] planner hook triggered: $CAPSULE_PATH" >> "$LOG_FILE"

# Call planner trigger, but never crash the importer
if [ -x "$TRIGGER_SCRIPT" ]; then
    if "$TRIGGER_SCRIPT" "$CAPSULE_PATH"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] planner hook completed successfully for: $CAPSULE_NAME" >> "$LOG_FILE"
    else
        TRIGGER_EXIT_CODE=$?
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] planner hook failed with exit code $TRIGGER_EXIT_CODE for: $CAPSULE_NAME" >> "$LOG_FILE"
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] planner trigger script not found or not executable: $TRIGGER_SCRIPT" >> "$LOG_FILE"
fi

# Always exit successfully to prevent disrupting the import process
exit 0




