#!/bin/bash
# TodoWrite Helper - Easy integration with persistent tasks

set -e

CAPSULE_DIR=$(pwd)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function show_usage() {
    cat <<EOF
${BLUE}TodoWrite Helper - Sync ephemeral todos with persistent tasks${NC}

Usage:
  ./todowrite_helper.sh [command]

Commands:
  load              Load tasks from tasks.json (shows for TodoWrite)
  load-json         Load tasks as JSON (for copying into TodoWrite tool)
  status            Show current capsule task status
  complete <id>     Mark a task as completed
  add <desc>        Quick add a task

Examples:
  # Show tasks for this capsule
  ./todowrite_helper.sh load

  # Mark task as complete
  ./todowrite_helper.sh complete 358560fe

  # Quick add a task
  ./todowrite_helper.sh add "Fix authentication bug"

Note: Run this from within a capsule directory.
EOF
}

function check_capsule() {
    if [[ ! -d "specs" && ! -d "spec" ]]; then
        echo "❌ Not in a capsule directory. Run from capsules/<name>/"
        exit 1
    fi
}

case "${1:-}" in
    load)
        check_capsule
        python3 "$SCRIPT_DIR/sync_todowrite.py" load
        ;;

    load-json)
        check_capsule
        echo -e "${YELLOW}Copy this JSON into TodoWrite tool:${NC}\n"
        python3 "$SCRIPT_DIR/sync_todowrite.py" load --format json
        ;;

    status)
        check_capsule
        python3 "$SCRIPT_DIR/sync_todowrite.py" status
        ;;

    complete)
        if [[ -z "$2" ]]; then
            echo "❌ Usage: ./todowrite_helper.sh complete <task-id>"
            exit 1
        fi
        check_capsule
        CAPSULE_NAME=$(basename "$CAPSULE_DIR")
        python3 "$SCRIPT_DIR/task_manager.py" complete "$CAPSULE_NAME" "$2"
        ;;

    add)
        if [[ -z "$2" ]]; then
            echo "❌ Usage: ./todowrite_helper.sh add \"<description>\""
            exit 1
        fi
        check_capsule
        CAPSULE_NAME=$(basename "$CAPSULE_DIR")
        python3 "$SCRIPT_DIR/task_manager.py" add "$CAPSULE_NAME" "$2"
        ;;

    help|--help|-h)
        show_usage
        ;;

    *)
        show_usage
        exit 1
        ;;
esac
