#!/bin/bash
set -euo pipefail

# trigger_planner.sh - Enhanced configurable planner trigger for Huxley capsules
# Usage: trigger_planner.sh [--print-merged-config] [--dry-run] <absolute_capsule_path>

CATALYST_ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
GLOBAL_CONFIG_FILE="$CATALYST_ROOT/tools/planner_config.json"
LOG_FILE="$CATALYST_ROOT/registry/planner-hooks.log"

# Huxley Context Banner
STATE_FILE="$CATALYST_ROOT/global/system_state.md"
SESSION_FILE="$CATALYST_ROOT/global/session_context.md"

show_context_banner() {
    if [ -f "$STATE_FILE" ] || [ -f "$SESSION_FILE" ]; then
        echo "=== Huxley Context ==="
        if [ -f "$STATE_FILE" ]; then
            STATE_HEADER=$(head -n 1 "$STATE_FILE" 2>/dev/null || echo "System State: Available")
            echo "State: $STATE_HEADER"
        fi
        if [ -f "$SESSION_FILE" ]; then
            SESSION_HEADER=$(head -n 1 "$SESSION_FILE" 2>/dev/null || echo "Session Context: Available")
            echo "Session: $SESSION_HEADER"
        fi
        echo "======================="
        echo ""
    fi
}

# Debug flags
PRINT_MERGED_CONFIG=false
DRY_RUN=false

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

error_exit() {
    log_msg "ERROR slug=$(basename "$CAPSULE_PATH") msg=$*"
    exit 1
}

send_notification() {
    local title="$1"
    local message="$2"
    
    # Try osascript first
    if osascript -e "display notification \"$message\" with title \"Huxley\" subtitle \"$title\"" 2>/dev/null; then
        return 0
    fi
    
    # Fallback to terminal-notifier if available
    if command -v terminal-notifier >/dev/null 2>&1; then
        terminal-notifier -title "Huxley" -subtitle "$title" -message "$message" 2>/dev/null || true
    fi
}

find_prompt() {
    local role="$1"
    local branch="${2:-}"
        local capsule="$4"
    
    local search_paths=()
    
    # Priority 1: Claude Code project agents with lane/branch specialization
    if [ -n "$lane" ]; then
        search_paths+=(".claude/agents/${role}.${lane}.md")
    fi
    if [ -n "$branch" ]; then
        search_paths+=(".claude/agents/${role}.${branch}.md")
    fi
    search_paths+=(".claude/agents/${role}.md")
    
    # Priority 2: Claude Code user-level agents (fallback)
    if [ -n "$lane" ]; then
        search_paths+=("$HOME/.claude/agents/${role}.${lane}.md")
    fi
    if [ -n "$branch" ]; then
        search_paths+=("$HOME/.claude/agents/${role}.${branch}.md")
    fi
    search_paths+=("$HOME/.claude/agents/${role}.md")
    
    # Priority 3: Legacy Huxley agent paths (backward compatibility)
    if [ -n "$lane" ]; then
        search_paths+=("ops/agent-${role}-${lane}.md")
        search_paths+=("spec/agent-${role}-${lane}.md")
    fi
    if [ -n "$branch" ]; then
        search_paths+=("ops/agent-${role}-${branch}.md")
        search_paths+=("spec/agent-${role}-${branch}.md")
    fi
    search_paths+=("ops/agent-${role}.md")
    search_paths+=("spec/agent-${role}.md")
    
    for path in "${search_paths[@]}"; do
        # Handle absolute paths (user-level agents)
        if [[ "$path" =~ ^/ ]]; then
            local full_path="$path"
        else
            local full_path="$capsule/$path"
        fi
        
        if [ -f "$full_path" ]; then
            echo "$full_path"
            return 0
        fi
    done
    
    return 1
}

merge_configs() {
    local global_config="$1"
    local capsule_config="$2"
    
    python3 - <<PY
import json
import sys

try:
    # Read global config
    with open('$global_config', 'r') as f:
        global_cfg = json.load(f)
    
    # Read capsule config if it exists
    capsule_cfg = {}
    try:
        with open('$capsule_config', 'r') as f:
            capsule_cfg = json.load(f)
    except FileNotFoundError:
        pass
    
    # Merge: capsule overrides global
    merged = global_cfg.copy()
    for key, value in capsule_cfg.items():
        if key == 'env' and isinstance(value, dict) and key in merged:
            # For env, merge dictionaries
            merged_env = merged[key].copy()
            merged_env.update(value)
            merged[key] = merged_env
        else:
            merged[key] = value
    
    # Output merged config
    print(json.dumps(merged))
    
except Exception as e:
    print(f'{{"error": "Config merge failed: {e}"}}')
    sys.exit(1)
PY
}

generate_env_example() {
    local capsule="$1"
    local requirements_file="$capsule/spec/requirements.yaml"
    local env_example="$capsule/.env.example"
    
    if [ ! -f "$requirements_file" ]; then
        return 0
    fi
    
    if [ -f "$env_example" ]; then
        return 0
    fi
    
    # Extract secrets from requirements.yaml and generate .env.example
    python3 - <<PY
import yaml
import os

try:
    with open('$requirements_file', 'r') as f:
        data = yaml.safe_load(f)
    
    secrets = []
    if isinstance(data, dict):
        constraints = data.get('constraints', {})
        if isinstance(constraints, dict):
            secrets = constraints.get('secrets', [])
    
    if secrets:
        with open('$env_example', 'w') as f:
            f.write("# Environment variables for $(basename '$capsule')\n")
            f.write("# Copy to .env and fill in real values\n\n")
            for secret in secrets:
                f.write(f"{secret.upper()}=your_value_here\n")
        
        print(f"Generated .env.example with {len(secrets)} secrets")
    
except Exception as e:
    print(f"Failed to generate .env.example: {e}")
PY
}

cleanup_lock() {
    if [ -n "${LOCK_FILE:-}" ] && [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
        log_msg "INFO slug=$(basename "$CAPSULE_PATH") msg=Lock removed"
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --print-merged-config)
            PRINT_MERGED_CONFIG=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            cat << 'EOF'
trigger_planner.sh - Enhanced Planner Trigger

Usage: trigger_planner.sh [options] <capsule_path>

Options:
  --print-merged-config  Print final merged configuration and exit
  --dry-run             Show what would be executed without running planner
  --help, -h            Show this help message

Arguments:
  capsule_path          Absolute path to capsule directory

Examples:
  trigger_planner.sh /path/to/capsule
  trigger_planner.sh --dry-run /path/to/capsule
  trigger_planner.sh --print-merged-config /path/to/capsule
EOF
            exit 0
            ;;
        -*)
            error_exit "Unknown option: $1"
            ;;
        *)
            CAPSULE_PATH="$1"
            shift
            ;;
    esac
done

# Validate arguments
if [ -z "${CAPSULE_PATH:-}" ]; then
    error_exit "Usage: trigger_planner.sh [options] <absolute_capsule_path>"
fi

# Validate capsule path
if [ ! -d "$CAPSULE_PATH" ]; then
    error_exit "Capsule directory does not exist: $CAPSULE_PATH"
fi

# Resolve to absolute path
CAPSULE_PATH=$(python3 -c "import os; print(os.path.realpath('$CAPSULE_PATH'))")

# Show Huxley context banner
show_context_banner

# Validate spec/requirements.yaml exists
REQUIREMENTS_FILE="$CAPSULE_PATH/spec/requirements.yaml"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    error_exit "Missing spec/requirements.yaml in capsule: $CAPSULE_PATH"
fi

CAPSULE_NAME=$(basename "$CAPSULE_PATH")
LOCK_FILE="$CAPSULE_PATH/.planner.lock"

# Set up cleanup trap
trap cleanup_lock EXIT INT TERM

# Check for existing lock
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        log_msg "INFO slug=$CAPSULE_NAME msg=SKIP due to lock (PID: $LOCK_PID)"
        exit 0
    else
        log_msg "INFO slug=$CAPSULE_NAME msg=Removing stale lock"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
echo $$ > "$LOCK_FILE"

log_msg "INFO slug=$CAPSULE_NAME msg=Triggering planner ($CAPSULE_PATH)"

# Load and merge configurations
if [ ! -f "$GLOBAL_CONFIG_FILE" ]; then
    error_exit "Global configuration file not found: $GLOBAL_CONFIG_FILE"
fi

CAPSULE_CONFIG_FILE="$CAPSULE_PATH/ops/planner.json"
MERGED_CONFIG=$(merge_configs "$GLOBAL_CONFIG_FILE" "$CAPSULE_CONFIG_FILE")

if echo "$MERGED_CONFIG" | grep -q '"error"'; then
    error_exit "Configuration merge failed: $MERGED_CONFIG"
fi

# Parse merged configuration
PLANNER_CMD=$(echo "$MERGED_CONFIG" | python3 -c "import json,sys; config=json.load(sys.stdin); print(config.get('cmd', ''))")
PLANNER_ARGS=$(echo "$MERGED_CONFIG" | python3 -c "import json,sys; config=json.load(sys.stdin); print(' '.join(config.get('args', [])))")
PLANNER_ENV=$(echo "$MERGED_CONFIG" | python3 -c "import json,sys; config=json.load(sys.stdin); env=config.get('env',{}); [print(f'{k}={v}') for k,v in env.items()]")
TIMEOUT_SEC=$(echo "$MERGED_CONFIG" | python3 -c "import json,sys; config=json.load(sys.stdin); print(config.get('timeout_sec', 900))")
FALLBACK_TO_MARKER=$(echo "$MERGED_CONFIG" | python3 -c "import json,sys; config=json.load(sys.stdin); print('true' if config.get('fallback_to_marker', True) else 'false')")

if [ -z "$PLANNER_CMD" ]; then
    error_exit "Invalid configuration: missing 'cmd' field"
fi

# Handle debug flags
if [ "$PRINT_MERGED_CONFIG" = true ]; then
    echo "$MERGED_CONFIG"
    exit 0
fi

# Override command from environment if set
if [ -n "${CLAUDE_PLANNER_CMD:-}" ]; then
    PLANNER_CMD="$CLAUDE_PLANNER_CMD"
    log_msg "INFO slug=$CAPSULE_NAME msg=Using command from CLAUDE_PLANNER_CMD: $PLANNER_CMD"
fi

# Generate .env.example if needed
generate_env_example "$CAPSULE_PATH"

# Check for secrets reminder
if [ ! -f "$CAPSULE_PATH/.env" ] && [ -f "$CAPSULE_PATH/.env.example" ]; then
    log_msg "INFO slug=$CAPSULE_NAME msg=Reminder: .env.example exists but .env is missing - consider copying and filling real values"
fi

# --- MCP Grants Begin ---
PROFILES_DIR="$CATALYST_ROOT/global/mcp/profiles"
REQUESTED_MCP="$("$CATALYST_ROOT/tools/mcp_resolver.py" "$CAPSULE_PATH" "$PROFILES_DIR" 2>/dev/null || echo "")"
if [ -z "$REQUESTED_MCP" ]; then
  REQUESTED_MCP="$("$CATALYST_ROOT/tools/mcp_resolver.py" "$CAPSULE_PATH" "$PROFILES_DIR")"
fi
export CLAUDE_MCP_SERVERS="$REQUESTED_MCP"
log_msg "INFO slug=$CAPSULE_NAME msg=MCP servers granted: $CLAUDE_MCP_SERVERS"

# Log structured event
"$CATALYST_ROOT/tools/events_logger.py" mcp_grants "MCP servers granted" --slug="$CAPSULE_NAME" --level=INFO servers="$REQUESTED_MCP"

# Agent tools cross-check
CHECK_JSON="$("$CATALYST_ROOT/tools/agents/agent_tools_check.py" "$CAPSULE_PATH" "$CLAUDE_MCP_SERVERS")"
if [ "$CHECK_JSON" != "[]" ]; then
  log_msg "WARN slug=$CAPSULE_NAME msg=unmet_agent_tools=$CHECK_JSON"
fi

# MCP grants excessive check (least privilege)
GRANTS_JSON="$("$CATALYST_ROOT/tools/mcp_grants_check.py" "$CAPSULE_PATH" "$CLAUDE_MCP_SERVERS")"
if echo "$GRANTS_JSON" | python3 -c "import json,sys; data=json.load(sys.stdin); sys.exit(0 if not data.get('has_issues', False) else 1)" 2>/dev/null; then
  : # No excessive grants
else
  EXCESSIVE=$(echo "$GRANTS_JSON" | python3 -c "import json,sys; data=json.load(sys.stdin); print(' '.join(data.get('excessive_grants', [])))")
  if [ -n "$EXCESSIVE" ]; then
    log_msg "WARN slug=$CAPSULE_NAME msg=excessive_mcp_grants=[$EXCESSIVE] consider_removing_unused_mcps"
  fi
fi
# --- MCP Grants End ---

# Extract branch from requirements.yaml
BRANCH=$(python3 -c "
import yaml
try:
    with open('$REQUIREMENTS_FILE', 'r') as f:
        data = yaml.safe_load(f)
    project = data.get('project', {})
    print(project.get('branch', ''))
except:
    print('')
" 2>/dev/null || echo "")

# Using unified quality standards approach - no lane differentiation
LANE="standard"

# Determine DoD file path using unified quality standards
DOD_FILE="$CATALYST_ROOT/global/dod/quality_standards.md"
DOD_ARGS=()
if [ -f "$DOD_FILE" ]; then
    DOD_ARGS+=("--dod-path" "$DOD_FILE")
    log_msg "INFO slug=$CAPSULE_NAME msg=Using DoD checklist for $LANE: $DOD_FILE"
else
    log_msg "WARN slug=$CAPSULE_NAME msg=DoD file not found: $DOD_FILE (proceeding without DoD validation)"
fi

# Discover prompt files
PROMPT_ARGS=()
for role in planner executor tester; do
    if prompt_file=$(find_prompt "$role" "$BRANCH" "$LANE" "$CAPSULE_PATH"); then
        PROMPT_ARGS+=("--prompt-$role" "$prompt_file")
        log_msg "INFO slug=$CAPSULE_NAME msg=Found prompt for $role: $(basename "$prompt_file")"
    fi
done

# Check if command is executable
if ! command -v "$PLANNER_CMD" >/dev/null 2>&1; then
    if [ "$FALLBACK_TO_MARKER" = "true" ]; then
        MARKER_FILE="$CAPSULE_PATH/.plan_me"
        touch "$MARKER_FILE"
        log_msg "INFO slug=$CAPSULE_NAME msg=FALLBACK: Command not found ($PLANNER_CMD), created marker: $MARKER_FILE"
        exit 0
    else
        error_exit "Planner command not found and fallback disabled: $PLANNER_CMD"
    fi
fi

# Build full command with prompt and DoD arguments
FULL_ARGS=()
if [ -n "$PLANNER_ARGS" ]; then
    IFS=' ' read -ra ARGS_ARRAY <<< "$PLANNER_ARGS"
    FULL_ARGS+=("${ARGS_ARRAY[@]}")
fi
if [ ${#PROMPT_ARGS[@]} -gt 0 ]; then
    FULL_ARGS+=("${PROMPT_ARGS[@]}")
fi
if [ ${#DOD_ARGS[@]} -gt 0 ]; then
    FULL_ARGS+=("${DOD_ARGS[@]}")
fi
FULL_ARGS+=("$CAPSULE_PATH")

FULL_CMD="$PLANNER_CMD ${FULL_ARGS[*]}"

# Handle dry-run mode
if [ "$DRY_RUN" = true ]; then
    echo "DRY RUN MODE - Would execute:"
    echo "  Command: $PLANNER_CMD"
    echo "  Args: ${FULL_ARGS[*]}"
    echo "  Timeout: ${TIMEOUT_SEC}s"
    echo "  Lock file: $LOCK_FILE"
    echo "  Lane: $LANE"
    echo "  DoD file: $DOD_FILE"
    if [ -n "$PLANNER_ENV" ]; then
        echo "  Environment:"
        echo "$PLANNER_ENV" | sed 's/^/    /'
    fi
    log_msg "INFO slug=$CAPSULE_NAME msg=DRY RUN: Would execute: $FULL_CMD (lane: $LANE, timeout: ${TIMEOUT_SEC}s)"
    exit 0
fi

log_msg "INFO slug=$CAPSULE_NAME msg=Executing: $FULL_CMD (timeout: ${TIMEOUT_SEC}s)"

# Execute with timeout using Python subprocess
python3 - <<PY
import subprocess
import sys
import os
from datetime import datetime

# Set up environment
env = os.environ.copy()
env_vars = """$PLANNER_ENV""".strip()
for line in env_vars.split('\n'):
    if line and '=' in line:
        key, value = line.split('=', 1)
        env[key] = value

# Build command array
cmd_parts = ["$PLANNER_CMD"] + [$(printf '"%s",' "${FULL_ARGS[@]}" | sed 's/,$//')] 

log_file = "$LOG_FILE"
capsule_name = "$CAPSULE_NAME"

def log_output(msg):
    with open(log_file, 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] PLANNER slug={capsule_name} msg={msg}\n")

try:
    # Execute with timeout
    result = subprocess.run(
        cmd_parts,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=int("$TIMEOUT_SEC")
    )
    
    # Log output
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                log_output(f"OUTPUT: {line}")
    
    if result.returncode == 0:
        log_output("SUCCESS: Planner completed")
        sys.exit(0)
    else:
        log_output(f"ERROR: Planner failed with exit code {result.returncode}")
        sys.exit(result.returncode)

except subprocess.TimeoutExpired:
    log_output(f"TIMEOUT: Planner timed out after $TIMEOUT_SEC seconds")
    sys.exit(124)  # Standard timeout exit code

except Exception as e:
    log_output(f"ERROR: Failed to execute planner: {e}")
    sys.exit(1)
PY

# Check exit status and send notification on failure
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    if [ $EXIT_CODE -eq 124 ]; then
        FAILURE_MSG="Planner timed out for $CAPSULE_NAME"
        log_msg "ERROR slug=$CAPSULE_NAME msg=Planner timed out after ${TIMEOUT_SEC}s"
    else
        FAILURE_MSG="Planner failed for $CAPSULE_NAME (exit code: $EXIT_CODE)"
        log_msg "ERROR slug=$CAPSULE_NAME msg=Planner failed with exit code $EXIT_CODE"
    fi
    
    send_notification "Planner Failed" "$FAILURE_MSG"
    exit $EXIT_CODE
fi

log_msg "INFO slug=$CAPSULE_NAME msg=Planner completed successfully"

# Auto-executor chain (unified approach)
if true; then  # Using unified quality standards
    EXECUTOR_ENABLED=$(echo "$MERGED_CONFIG" | python3 -c "import json,sys; config=json.load(sys.stdin); print('true' if config.get('auto_executor', {}).get('enabled', False) else 'false')")
    EXECUTOR_CMD=$(echo "$MERGED_CONFIG" | python3 -c "import json,sys; config=json.load(sys.stdin); print(config.get('auto_executor', {}).get('cmd', ''))")
    EXECUTOR_ARGS=$(echo "$MERGED_CONFIG" | python3 -c "import json,sys; config=json.load(sys.stdin); print(' '.join(config.get('auto_executor', {}).get('args', [])))")
    
    if [ "$EXECUTOR_ENABLED" = "true" ] && [ -n "$EXECUTOR_CMD" ]; then
        log_msg "INFO slug=$CAPSULE_NAME msg=auto-executor triggered"
        
        # Build executor command with same prompt and DoD arguments
        EXECUTOR_FULL_ARGS=()
        if [ -n "$EXECUTOR_ARGS" ]; then
            IFS=' ' read -ra EXEC_ARGS_ARRAY <<< "$EXECUTOR_ARGS"
            EXECUTOR_FULL_ARGS+=("${EXEC_ARGS_ARRAY[@]}")
        fi
        if [ ${#PROMPT_ARGS[@]} -gt 0 ]; then
            EXECUTOR_FULL_ARGS+=("${PROMPT_ARGS[@]}")
        fi
        if [ ${#DOD_ARGS[@]} -gt 0 ]; then
            EXECUTOR_FULL_ARGS+=("${DOD_ARGS[@]}")
        fi
        EXECUTOR_FULL_ARGS+=("$CAPSULE_PATH")
        
        EXECUTOR_FULL_CMD="$EXECUTOR_CMD ${EXECUTOR_FULL_ARGS[*]}"
        
        if command -v "$EXECUTOR_CMD" >/dev/null 2>&1; then
            log_msg "INFO slug=$CAPSULE_NAME msg=Executing auto-executor: $EXECUTOR_FULL_CMD"
            
            # Execute executor with same timeout logic
            python3 - <<PY
import subprocess
import sys
import os
from datetime import datetime

# Set up environment (reuse planner env)
env = os.environ.copy()
env_vars = """$PLANNER_ENV""".strip()
for line in env_vars.split('\\n'):
    if line and '=' in line:
        key, value = line.split('=', 1)
        env[key] = value

# Build command array
cmd_parts = ["$EXECUTOR_CMD"] + [$(printf '\"%s\",' "${EXECUTOR_FULL_ARGS[@]}" | sed 's/,$//')] 

log_file = "$LOG_FILE"
capsule_name = "$CAPSULE_NAME"

def log_output(msg):
    with open(log_file, 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] EXECUTOR slug={capsule_name} msg={msg}\\n")

try:
    # Execute with same timeout as planner
    result = subprocess.run(
        cmd_parts,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=int("$TIMEOUT_SEC")
    )
    
    # Log output
    if result.stdout:
        for line in result.stdout.strip().split('\\n'):
            if line.strip():
                log_output(f"OUTPUT: {line}")
    
    if result.returncode == 0:
        log_output("SUCCESS: Auto-executor completed")
        sys.exit(0)
    else:
        log_output(f"WARNING: Auto-executor failed with exit code {result.returncode}")
        sys.exit(0)  # Don't fail overall pipeline on executor failure

except subprocess.TimeoutExpired:
    log_output(f"WARNING: Auto-executor timed out after $TIMEOUT_SEC seconds")
    sys.exit(0)  # Don't fail overall pipeline on executor timeout

except Exception as e:
    log_output(f"WARNING: Failed to execute auto-executor: {e}")
    sys.exit(0)  # Don't fail overall pipeline on executor error
PY
            
            EXECUTOR_EXIT_CODE=$?
            if [ $EXECUTOR_EXIT_CODE -eq 0 ]; then
                log_msg "INFO slug=$CAPSULE_NAME msg=Auto-executor completed successfully"
                send_notification "Execution Complete" "$CAPSULE_NAME auto-execution completed"
            else
                log_msg "WARN slug=$CAPSULE_NAME msg=Auto-executor completed with warnings (see logs)"
                send_notification "Execution Warning" "$CAPSULE_NAME auto-execution completed with warnings"
            fi
        else
            log_msg "WARN slug=$CAPSULE_NAME msg=Auto-executor command not found: $EXECUTOR_CMD"
        fi
    else
        log_msg "INFO slug=$CAPSULE_NAME msg=auto-executor disabled or not configured"
    fi
fi

exit 0

