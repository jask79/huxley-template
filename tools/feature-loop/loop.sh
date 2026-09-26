#!/bin/bash
# Feature Loop Runner for Huxley
# Runs autonomous iterations until PRD complete or max reached
#
# Usage: ./loop.sh <prd-file-path>

set -euo pipefail

# Configuration
MAX_ITERATIONS=${MAX_ITERATIONS:-10}
SLEEP_BETWEEN=${SLEEP_BETWEEN:-5}
CATALYST_ROOT="{{CATALYST_ROOT}}"
LOOP_DIR="$CATALYST_ROOT/tools/feature-loop"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging helper
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Send notification (macOS)
notify() {
    local title="$1"
    local message="$2"
    osascript -e "display notification \"$message\" with title \"$title\""
}

# Validate arguments
if [ $# -eq 0 ]; then
    error "No PRD file specified"
    echo "Usage: $0 <prd-file-path>"
    exit 1
fi

PRD_FILE="$1"

# Resolve relative paths
if [[ ! "$PRD_FILE" = /* ]]; then
    PRD_FILE="$CATALYST_ROOT/$PRD_FILE"
fi

# Validate PRD exists
if [ ! -f "$PRD_FILE" ]; then
    error "PRD file not found: $PRD_FILE"
    exit 1
fi

# Validate JSON format
if ! jq empty "$PRD_FILE" 2>/dev/null; then
    error "Invalid JSON in PRD file"
    exit 1
fi

# Extract PRD metadata
FEATURE_NAME=$(jq -r '.feature // "unknown"' "$PRD_FILE")
BRANCH_NAME=$(jq -r '.branch // "unknown"' "$PRD_FILE")
MAX_FROM_PRD=$(jq -r '.maxIterations // 10' "$PRD_FILE")
REQUIRE_VALIDATION=$(jq -r '.governance.requireValidation // true' "$PRD_FILE")
NOTIFY_ON_COMPLETE=$(jq -r '.governance.notifyOnComplete // true' "$PRD_FILE")
COST_ALERT_THRESHOLD=$(jq -r '.governance.costAlertThreshold // 5' "$PRD_FILE")

# Use PRD max iterations if specified
if [ "$MAX_FROM_PRD" != "null" ]; then
    MAX_ITERATIONS=$MAX_FROM_PRD
fi

# Create run directory
SAFE_BRANCH=$(echo "$BRANCH_NAME" | sed 's/[^a-zA-Z0-9_-]/-/g')
RUN_DIR="$LOOP_DIR/runs/$SAFE_BRANCH"
mkdir -p "$RUN_DIR"

PROGRESS_LOG="$RUN_DIR/progress.log"
PRD_SNAPSHOT="$RUN_DIR/prd-snapshot.json"

# Copy PRD snapshot
cp "$PRD_FILE" "$PRD_SNAPSHOT"

log "Starting Feature Loop"
log "Feature: $FEATURE_NAME"
log "Branch: $BRANCH_NAME"
log "Max Iterations: $MAX_ITERATIONS"
log "Run Directory: $RUN_DIR"
log "Progress Log: $PROGRESS_LOG"

# Initialize progress log
{
    echo "========================================="
    echo "Feature Loop Run - $(date)"
    echo "========================================="
    echo "Feature: $FEATURE_NAME"
    echo "Branch: $BRANCH_NAME"
    echo "PRD: $PRD_FILE"
    echo "Max Iterations: $MAX_ITERATIONS"
    echo "Require Validation: $REQUIRE_VALIDATION"
    echo "========================================="
    echo ""
} >> "$PROGRESS_LOG"

# Main loop
ITERATION=0
while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    ITERATION=$((ITERATION + 1))

    log "Starting iteration $ITERATION/$MAX_ITERATIONS"

    # Log iteration start
    {
        echo "--- Iteration $ITERATION ($(date)) ---"
    } >> "$PROGRESS_LOG"

    # Cost alert check
    if [ $ITERATION -ge $COST_ALERT_THRESHOLD ]; then
        warn "Cost alert: Iteration $ITERATION >= threshold $COST_ALERT_THRESHOLD"
    fi

    # Prepare iteration prompt by injecting PRD content
    ITERATION_PROMPT=$(cat "$LOOP_DIR/iteration-prompt.md")
    PRD_CONTENT=$(cat "$PRD_FILE")

    # Create temporary prompt file with PRD embedded
    TEMP_PROMPT=$(mktemp)
    echo "$ITERATION_PROMPT" > "$TEMP_PROMPT"
    echo "" >> "$TEMP_PROMPT"
    echo "## Current PRD State" >> "$TEMP_PROMPT"
    echo '```json' >> "$TEMP_PROMPT"
    echo "$PRD_CONTENT" >> "$TEMP_PROMPT"
    echo '```' >> "$TEMP_PROMPT"

    # Run Claude Code iteration
    log "Executing Claude Code session..."

    OUTPUT_FILE="$RUN_DIR/iteration-$ITERATION-output.txt"

    if claude --dangerously-skip-permissions --prompt-file "$TEMP_PROMPT" > "$OUTPUT_FILE" 2>&1; then
        success "Iteration $ITERATION completed"

        # Check for completion signal
        if grep -q "<loop-signal>COMPLETE</loop-signal>" "$OUTPUT_FILE"; then
            success "Feature loop complete! All tasks passing."
            {
                echo "Loop completed successfully at iteration $ITERATION"
                echo "All tasks passing."
                echo "========================================="
            } >> "$PROGRESS_LOG"

            # Notification
            if [ "$NOTIFY_ON_COMPLETE" = "true" ]; then
                notify "Feature Loop Complete" "Feature '$FEATURE_NAME' completed in $ITERATION iterations"
            fi

            # Cleanup temp file
            rm -f "$TEMP_PROMPT"

            exit 0
        fi

        # Log iteration results
        {
            echo "Status: Success"
            echo "Output logged to: iteration-$ITERATION-output.txt"
            echo ""
        } >> "$PROGRESS_LOG"

    else
        error "Iteration $ITERATION failed"
        {
            echo "Status: FAILED"
            echo "Output logged to: iteration-$ITERATION-output.txt"
            echo ""
        } >> "$PROGRESS_LOG"
    fi

    # Cleanup temp file
    rm -f "$TEMP_PROMPT"

    # Check if we're at max iterations
    if [ $ITERATION -ge $MAX_ITERATIONS ]; then
        warn "Maximum iterations ($MAX_ITERATIONS) reached"
        {
            echo "========================================="
            echo "Maximum iterations reached without completion"
            echo "Feature may require manual intervention"
            echo "========================================="
        } >> "$PROGRESS_LOG"

        if [ "$NOTIFY_ON_COMPLETE" = "true" ]; then
            notify "Feature Loop Incomplete" "Feature '$FEATURE_NAME' reached max iterations ($MAX_ITERATIONS)"
        fi

        exit 1
    fi

    # Sleep between iterations
    log "Sleeping ${SLEEP_BETWEEN}s before next iteration..."
    sleep $SLEEP_BETWEEN
done

# Should never reach here, but just in case
error "Loop exited unexpectedly"
exit 1
