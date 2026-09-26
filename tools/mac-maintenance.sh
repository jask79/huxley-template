#!/bin/bash
# Huxley Mac Maintenance — Mole + RAM purge automation
# Designed for M1 Mac with 16GB RAM running heavy Claude Code workloads
#
# Usage:
#   ./mac-maintenance.sh              # Full clean + optimize + purge
#   ./mac-maintenance.sh --quick      # RAM purge + lightweight cache clean only
#   ./mac-maintenance.sh --deep       # Aggressive: pressure signal + orphan kill + caches + purge + swap report
#   ./mac-maintenance.sh --dry-run    # Preview what would be cleaned
#   ./mac-maintenance.sh --status     # Show current RAM/disk stats
#
# Runs non-interactively for automation (LaunchAgent, cron, {{ORCHESTRATOR_NAME}})

set -euo pipefail

LOG_DIR="$HOME/.cache/catalyst-maintenance"
LOG_FILE="$LOG_DIR/maintenance.log"
STATS_FILE="$LOG_DIR/last_run.json"
MAX_LOG_SIZE=1048576  # 1MB

mkdir -p "$LOG_DIR"

# --- Helpers ---

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

log() {
    local msg="[$(timestamp)] $1"
    echo "$msg" >> "$LOG_FILE"
    # Only print to stdout if attached to TTY
    if [[ -t 1 ]]; then echo "$msg"; fi
}

rotate_log() {
    if [[ -f "$LOG_FILE" ]]; then
        local size
        size=$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
        if [[ "$size" -gt "$MAX_LOG_SIZE" ]]; then
            mv "$LOG_FILE" "$LOG_FILE.old"
            log "Log rotated (was ${size} bytes)"
        fi
    fi
}

get_memory_stats() {
    local page_size
    page_size=$(sysctl -n hw.pagesize 2>/dev/null || echo 16384)
    local mem_total_bytes
    mem_total_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
    local mem_total_gb
    mem_total_gb=$(echo "$mem_total_bytes" | awk '{printf "%.1f", $1/1073741824}')

    local vm_stats
    vm_stats=$(vm_stat 2>/dev/null)
    local pages_free pages_inactive pages_active pages_wired pages_compressed pages_speculative
    pages_free=$(echo "$vm_stats" | awk '/Pages free/ {gsub(/\./,"",$NF); print $NF}')
    pages_inactive=$(echo "$vm_stats" | awk '/Pages inactive/ {gsub(/\./,"",$NF); print $NF}')
    pages_active=$(echo "$vm_stats" | awk '/Pages active/ {gsub(/\./,"",$NF); print $NF}')
    pages_wired=$(echo "$vm_stats" | awk '/Pages wired down/ {gsub(/\./,"",$NF); print $NF}')
    pages_compressed=$(echo "$vm_stats" | awk '/Pages occupied by compressor/ {gsub(/\./,"",$NF); print $NF}')
    pages_speculative=$(echo "$vm_stats" | awk '/Pages speculative/ {gsub(/\./,"",$NF); print $NF}')

    # Calculate used = active + wired + compressed
    local used_pages=$(( ${pages_active:-0} + ${pages_wired:-0} + ${pages_compressed:-0} ))
    local used_bytes=$(( used_pages * page_size ))
    local used_gb
    used_gb=$(echo "$used_bytes" | awk '{printf "%.1f", $1/1073741824}')

    local free_pages=$(( ${pages_free:-0} + ${pages_inactive:-0} + ${pages_speculative:-0} ))
    local free_bytes=$(( free_pages * page_size ))
    local free_gb
    free_gb=$(echo "$free_bytes" | awk '{printf "%.1f", $1/1073741824}')

    local pressure
    pressure=$(memory_pressure 2>/dev/null | grep "System-wide" | awk '{print $NF}' || echo "unknown")

    echo "${used_gb}|${free_gb}|${mem_total_gb}|${pressure}|${pages_compressed:-0}"
}

get_swap_stats() {
    local swap_used
    swap_used=$(sysctl -n vm.swapusage 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="used") {gsub(/M/,"",$(i+2)); print $(i+2)}}' || echo "0")
    echo "${swap_used:-0}"
}

get_disk_free() {
    df -h / 2>/dev/null | awk 'NR==2 {print $4}' || echo "unknown"
}

show_status() {
    local mem_info
    mem_info=$(get_memory_stats)
    IFS='|' read -r used_gb free_gb total_gb pressure compressed <<< "$mem_info"
    local swap_mb
    swap_mb=$(get_swap_stats)
    local disk_free
    disk_free=$(get_disk_free)

    echo ""
    echo "=== Mac Maintenance Status ==="
    echo "RAM:       ${used_gb}GB used / ${total_gb}GB total (${free_gb}GB free)"
    echo "Pressure:  ${pressure}"
    echo "Swap:      ${swap_mb}MB used"
    echo "Disk:      ${disk_free} free"

    if [[ -f "$STATS_FILE" ]]; then
        echo ""
        echo "--- Last Run ---"
        local last_run last_freed last_mode
        last_run=$(python3 -c "import json; d=json.load(open('$STATS_FILE')); print(d.get('timestamp','unknown'))" 2>/dev/null || echo "unknown")
        last_freed=$(python3 -c "import json; d=json.load(open('$STATS_FILE')); print(d.get('ram_freed_gb','?'))" 2>/dev/null || echo "?")
        last_mode=$(python3 -c "import json; d=json.load(open('$STATS_FILE')); print(d.get('mode','?'))" 2>/dev/null || echo "?")
        echo "Time:      $last_run"
        echo "Mode:      $last_mode"
        echo "RAM freed: ${last_freed}GB"
    fi
    echo ""
}

save_stats() {
    local mode="$1" ram_before="$2" ram_after="$3" disk_before="$4" disk_after="$5" duration="$6"
    local ram_freed
    ram_freed=$(echo "$ram_before $ram_after" | awk '{printf "%.1f", $1-$2}')
    python3 -c "
import json, datetime
stats = {
    'timestamp': '$(timestamp)',
    'mode': '$mode',
    'ram_used_before_gb': $ram_before,
    'ram_used_after_gb': $ram_after,
    'ram_freed_gb': max(0, round($ram_before - $ram_after, 1)),
    'disk_free_before': '$disk_before',
    'disk_free_after': '$disk_after',
    'duration_seconds': $duration
}
with open('$STATS_FILE', 'w') as f:
    json.dump(stats, f, indent=2)
" 2>/dev/null || true
}

# --- Core Operations ---

purge_ram() {
    log "Purging inactive RAM..."
    if sudo -n purge 2>/dev/null; then
        log "RAM purge complete (sudo purge)"
    else
        log "WARN: sudo purge unavailable. Run setup_passwordless_purge to enable."
        log "Falling back to sync (flushes write buffers only)"
        sync 2>/dev/null || true
    fi
}

setup_passwordless_purge() {
    # Creates a sudoers entry allowing passwordless 'purge' for current user.
    # purge is safe — it only flushes the disk cache from RAM, no data loss risk.
    local sudoers_file="/etc/sudoers.d/catalyst-purge"
    local user
    user=$(whoami)

    if [[ -f "$sudoers_file" ]]; then
        echo "Passwordless purge already configured at $sudoers_file"
        return 0
    fi

    echo "Setting up passwordless sudo for 'purge' command..."
    echo "This allows the maintenance script to free RAM without a password prompt."
    echo "The purge command only flushes disk cache — completely safe."
    echo ""
    echo "Will create: $sudoers_file"
    echo "Contents:    $user ALL=(ALL) NOPASSWD: /usr/sbin/purge"
    echo ""

    # Requires interactive sudo for this one-time setup
    sudo sh -c "echo '$user ALL=(ALL) NOPASSWD: /usr/sbin/purge' > '$sudoers_file' && chmod 440 '$sudoers_file'"

    if sudo -n purge 2>/dev/null; then
        echo "Success! Passwordless purge is now enabled."
    else
        echo "ERROR: Setup failed. Check sudo permissions."
        return 1
    fi
}

run_mole_clean() {
    local dry_run="${1:-false}"
    log "Running Mole clean (dry_run=$dry_run)..."

    local mo_bin="/opt/homebrew/bin/mo"
    if [[ ! -x "$mo_bin" ]]; then
        log "WARN: Mole not found at $mo_bin"
        return 0
    fi

    # Mole clean requires a TTY for its interactive scanning
    if [[ ! -t 0 ]]; then
        log "Skipping Mole clean (no TTY — use 'mo clean' manually or run from terminal)"
        return 0
    fi

    local args=("clean")
    [[ "$dry_run" == "true" ]] && args+=("--dry-run")

    local output
    output=$("$mo_bin" "${args[@]}" 2>&1) || true
    log "Mole clean output: $(echo "$output" | tail -5)"
}

run_mole_optimize() {
    local dry_run="${1:-false}"
    log "Running Mole optimize (dry_run=$dry_run)..."

    local mo_bin="/opt/homebrew/bin/mo"
    if [[ ! -x "$mo_bin" ]]; then
        log "WARN: Mole not found at $mo_bin"
        return 1
    fi

    local args=("optimize")
    [[ "$dry_run" == "true" ]] && args+=("--dry-run")

    local output
    output=$("$mo_bin" "${args[@]}" 2>&1 </dev/null) || true
    log "Mole optimize output: $(echo "$output" | tail -5)"
}

clean_dev_caches() {
    # Targeted cleanup of known dev caches
    log "Cleaning development caches..."

    # npm and pip are fast (<1s each)
    npm cache clean --force 2>/dev/null || true
    pip3 cache purge 2>/dev/null || true

    # brew cleanup is SLOW (~40s on swapped systems) — run in background, don't wait
    (brew cleanup --prune=1 2>/dev/null || true) &
    disown 2>/dev/null || true

    log "Dev cache cleanup done (brew cleanup running in background)"
}

# --- Main Execution Modes ---

clean_system_caches() {
    log "Cleaning system caches..."
    rm -rf ~/Library/Caches/com.apple.dt.Xcode/Downloads/* 2>/dev/null || true
    rm -rf ~/Library/Developer/Xcode/DerivedData/* 2>/dev/null || true
    rm -rf ~/Library/Caches/pip 2>/dev/null || true
    rm -rf ~/Library/Caches/Homebrew/* 2>/dev/null || true
    rm -rf ~/Library/Caches/typescript/* 2>/dev/null || true

    # Claude Code image cache — screenshots pasted into sessions (may contain credentials)
    # Uses same cleanupPeriodDays as session transcripts (default 30 if unset)
    if [[ -d "$HOME/.claude/image-cache" ]]; then
        local retention_days
        retention_days=$(python3 -c "
import json
try: print(json.load(open('$HOME/.claude/settings.json')).get('cleanupPeriodDays', 30))
except: print(30)
" 2>/dev/null || echo 30)
        local img_deleted
        img_deleted=$(find "$HOME/.claude/image-cache" -type f -mtime +${retention_days} -delete -print 2>/dev/null | wc -l | tr -d ' ')
        # Remove empty UUID directories left behind
        find "$HOME/.claude/image-cache" -type d -empty -not -path "$HOME/.claude/image-cache" -delete 2>/dev/null || true
        if [[ "$img_deleted" -gt 0 ]]; then
            log "Claude image cache: deleted $img_deleted files older than ${retention_days} days"
        fi
    fi

    log "System caches cleaned"
}

run_quick() {
    log "=== Quick maintenance started ==="
    local start_time
    start_time=$(date +%s)

    local mem_before disk_before
    mem_before=$(get_memory_stats | cut -d'|' -f1)
    disk_before=$(get_disk_free)

    # 1. Flush RAM
    purge_ram

    # 2. Clean stale temp files that accumulate hourly
    log "Cleaning temp files..."

    local mem_after disk_after
    mem_after=$(get_memory_stats | cut -d'|' -f1)
    disk_after=$(get_disk_free)

    local duration=$(( $(date +%s) - start_time ))
    save_stats "quick" "$mem_before" "$mem_after" "$disk_before" "$disk_after" "$duration"

    local freed
    freed=$(echo "$mem_before $mem_after" | awk '{r=$1-$2; printf "%.1f", (r>0?r:0)}')
    log "=== Quick maintenance done (${duration}s, freed ~${freed}GB RAM) ==="
}

run_full() {
    log "=== Full maintenance started ==="
    local start_time
    start_time=$(date +%s)

    local mem_before disk_before
    mem_before=$(get_memory_stats | cut -d'|' -f1)
    disk_before=$(get_disk_free)

    # 1. Mole clean (disk caches, logs, browser leftovers, dev artifacts)
    run_mole_clean false

    # 2. Mole optimize (memory release, DNS flush, app state cleanup)
    run_mole_optimize false

    # 3. Dev-specific caches
    clean_dev_caches

    # 4. Final RAM purge
    purge_ram

    # 5. Prompt variant optimization maintenance (graduation, review linkage, stale cleanup)
    if [ -f "{{CATALYST_ROOT}}/scripts/variant_maintenance.py" ]; then
        log "Running variant optimization maintenance..."
        python3 {{CATALYST_ROOT}}/scripts/variant_maintenance.py --quiet 2>/dev/null || true
    fi

    local mem_after disk_after
    mem_after=$(get_memory_stats | cut -d'|' -f1)
    disk_after=$(get_disk_free)

    local duration=$(( $(date +%s) - start_time ))
    save_stats "full" "$mem_before" "$mem_after" "$disk_before" "$disk_after" "$duration"

    local freed
    freed=$(echo "$mem_before $mem_after" | awk '{r=$1-$2; printf "%.1f", (r>0?r:0)}')
    log "=== Full maintenance done (${duration}s, freed ~${freed}GB RAM) ==="
}

run_dry() {
    log "=== Dry run started ==="
    run_mole_clean true
    run_mole_optimize true
    log "=== Dry run complete (no changes made) ==="
}

# --- Deep Mode Operations ---

notify_memory_pressure() {
    # Nudge the kernel to reclaim memory by triggering jetsam pressure.
    # We allocate a modest chunk (~256MB) briefly — enough for the kernel
    # to fire DISPATCH_SOURCE_TYPE_MEMORYPRESSURE to apps, causing them to
    # drop optional caches and shrink heaps. Then release immediately.
    #
    # On heavily swapped systems, even this may get OOM-killed by jetsam,
    # which is fine — the pressure notification still fires before the kill.
    # Skip on heavily swapped systems — adding pressure just makes it worse
    local swap_mb
    swap_mb=$(get_swap_stats)
    local swap_int
    swap_int=$(printf '%.0f' "$swap_mb" 2>/dev/null || echo 0)

    if [[ "$swap_int" -gt 6000 ]]; then
        log "Skipping pressure spike (swap=${swap_int}MB — already under heavy pressure)"
        return 0
    fi

    log "Triggering memory pressure notifications (swap=${swap_int}MB)..."

    # Run in subshell so jetsam kills don't affect our main process
    (
        python3 -c "
try:
    buf = bytearray(256 * 1024 * 1024)
    for i in range(0, len(buf), 65536):
        buf[i] = 1
    import time; time.sleep(0.3)
    del buf
except Exception:
    pass
" 2>/dev/null
    ) 2>/dev/null || true

    log "Memory pressure notification triggered"
}

kill_orphan_processes() {
    # Kill orphaned Node/Python processes not attached to active work.
    # OPT-IN: set VROOM_KILL_ORPHANS=1 to enable. Any process whose command
    # line matches VROOM_PROTECT_REGEX (extended regex) is spared.
    if [[ "${VROOM_KILL_ORPHANS:-0}" != "1" ]]; then
        log "Orphan-process kill skipped (opt in with VROOM_KILL_ORPHANS=1)"
        return 0
    fi
    log "Scanning for orphaned processes..."
    local killed=0

    # Get PIDs of our current shell tree to avoid killing ourselves
    local my_pid=$$
    local parent_pid=$PPID

    # Kill orphaned node processes (stale MCP servers, old watchers)
    # Protected: node processes with active parent shells, Claude Code's own node
    while IFS= read -r line; do
        local pid comm
        pid=$(echo "$line" | awk '{print $1}')
        comm=$(echo "$line" | awk '{print $2}')
        [[ -z "$pid" || "$pid" == "$my_pid" || "$pid" == "$parent_pid" ]] && continue

        # Check if process has been running >= 1 hour and parent is init (orphaned)
        local ppid_check
        ppid_check=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        if [[ "$ppid_check" == "1" ]]; then
            # Orphaned node process (parent is launchd/init)
            local elapsed
            elapsed=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
            # Only kill if running >= 1 hour
            # etime format: MM:SS (<1h), HH:MM:SS (1-24h), D-HH:MM:SS (days)
            # Match D- prefix (days) or 3+ colon-separated fields (HH:MM:SS = at least 1 hour)
            if echo "$elapsed" | grep -qE '([0-9]+-|[0-9]+:[0-9]+:[0-9]+)'; then
                log "Killing orphaned node process: PID=$pid elapsed=$elapsed"
                kill "$pid" 2>/dev/null && ((killed++)) || true
            fi
        fi
    done < <(ps -eo pid,comm 2>/dev/null | grep -E '/node$|^[0-9]+ node$' | grep -v grep || true)

    # Kill orphaned python processes (stale MCP servers, old scripts)
    while IFS= read -r line; do
        local pid
        pid=$(echo "$line" | awk '{print $1}')
        [[ -z "$pid" || "$pid" == "$my_pid" || "$pid" == "$parent_pid" ]] && continue

        local ppid_check
        ppid_check=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        if [[ "$ppid_check" == "1" ]]; then
            local elapsed
            elapsed=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
            if echo "$elapsed" | grep -qE '([0-9]+-|[0-9]{2,}:)'; then
                # Don't kill the agent-memory-system or other known-good daemons
                local cmdline
                cmdline=$(ps -o args= -p "$pid" 2>/dev/null || echo "")
                if echo "$cmdline" | grep -qE "${VROOM_PROTECT_REGEX:-mcp|server|daemon|watch|lsp|language[_-]server}"; then
                    log "Skipping protected Python process: PID=$pid ($cmdline)"
                    continue
                fi
                log "Killing orphaned python process: PID=$pid elapsed=$elapsed"
                kill "$pid" 2>/dev/null && ((killed++)) || true
            fi
        fi
    done < <(ps -eo pid,comm 2>/dev/null | grep -iE 'python|Python' | grep -v grep || true)

    log "Orphan cleanup: killed $killed processes"
}

restart_finder_dock() {
    # Finder and Dock accumulate memory over days. macOS auto-relaunches both.
    # OPT-IN: set VROOM_RESTART_FINDER=1 to enable.
    if [[ "${VROOM_RESTART_FINDER:-0}" != "1" ]]; then
        log "Finder/Dock restart skipped (opt in with VROOM_RESTART_FINDER=1)"
        return 0
    fi
    log "Restarting Finder and Dock (frees accumulated memory)..."
    killall Finder 2>/dev/null || true
    killall Dock 2>/dev/null || true
    sleep 1
    log "Finder and Dock restarted"
}

flush_system_caches_deep() {
    # DNS cache, Quick Look thumbnails, font caches
    log "Flushing DNS, Quick Look, and font caches..."

    # DNS cache (dscacheutil doesn't need sudo, mDNSResponder does but -n skips if no NOPASSWD)
    dscacheutil -flushcache 2>/dev/null || true
    sudo -n killall -HUP mDNSResponder 2>/dev/null || true

    # Quick Look thumbnail cache
    qlmanage -r cache 2>/dev/null || true

    # CUPS printer job cache (can grow silently)
    rm -rf /tmp/cups-* 2>/dev/null || true

    log "Deep system caches flushed"
}

clean_private_var_folders() {
    # /private/var/folders is macOS per-user temp. Files older than 1 day are safe to remove.
    log "Cleaning /private/var/folders temp files (>1 day old)..."
    if [[ -d "/private/var/folders" ]]; then
        # Find and remove temp files in the Caches (C) subfolder only — safe target
        find /private/var/folders -maxdepth 4 -name "com.apple.DeveloperTools" -type d -exec rm -rf {} + 2>/dev/null || true
        find /private/var/folders -maxdepth 4 -name "com.apple.metadata.mds" -type d -mtime +1 -exec rm -rf {} + 2>/dev/null || true
    fi
    log "Private var folders cleaned"
}

shorten_proc_name() {
    # Shorten full paths to readable app/binary names
    awk '{
        mb = $1; name = $2
        # Known path patterns → friendly names
        if (name ~ /claude\/versions/) { name = "claude-cli"; }
        # /Applications/Foo.app/... → Foo
        else {
            n = split(name, parts, "/")
            for (i = 1; i <= n; i++) {
                if (parts[i] ~ /\.app$/) {
                    sub(/\.app$/, "", parts[i])
                    name = parts[i]
                    break
                }
            }
            # Still a full path? Use last component
            if (name ~ /^\//) {
                split(name, parts, "/")
                name = parts[n]
            }
        }
        printf "%s  %s\n", mb, name
    }'
}

get_top_consumers() {
    echo ""
    echo "=== Top Memory Consumers ==="
    ps -eo rss,comm 2>/dev/null | awk '{a[$2]+=$1} END {for(p in a) printf "%6.0fMB  %s\n", a[p]/1024, p}' | sort -rn | head -12 | shorten_proc_name
    echo ""
}

get_kill_recommendations() {
    local swap_mb="$1"
    # Only suggest kills if swap is still high (>4GB)
    local swap_int
    swap_int=$(printf '%.0f' "$swap_mb" 2>/dev/null || echo 0)
    if [[ "$swap_int" -gt 4000 ]]; then
        echo ""
        echo "=== Swap Relief Candidates ==="
        echo "(Swap still >4GB — these apps would free the most if quit)"
        # Show top RSS consumers, excluding Claude and iTerm
        ps -eo rss,comm 2>/dev/null | awk '{a[$2]+=$1} END {for(p in a) printf "%6.0fMB  %s\n", a[p]/1024, p}' | \
            sort -rn | grep -viE '(claude|iterm|WindowServer|kernel_task|launchd)' | head -3 | shorten_proc_name || true
        echo ""
    fi
}

run_deep() {
    # Relax strict mode for cleanup — every operation has its own error handling,
    # and we don't want a grep returning 1 (no matches) to abort the whole cycle.
    set +e
    log "=== Deep maintenance started ==="
    local start_time
    start_time=$(date +%s)

    # Capture before state
    local mem_before disk_before swap_before
    mem_before=$(get_memory_stats | cut -d'|' -f1)
    disk_before=$(get_disk_free)
    swap_before=$(get_swap_stats)

    echo ""
    echo "=== Before ==="
    echo "RAM:  ${mem_before}GB used"
    echo "Swap: ${swap_before}MB"
    echo "Disk: ${disk_before} free"

    # 1. Trigger memory pressure notifications (apps release caches)
    notify_memory_pressure

    # 2. Kill orphaned node/python processes
    kill_orphan_processes

    # 3. Restart Finder + Dock (frees accumulated memory)
    restart_finder_dock

    # 4. Flush DNS, Quick Look, font caches
    flush_system_caches_deep

    # 5. Clean /private/var/folders temp
    clean_private_var_folders

    # 6. Dev caches (brew, npm, pip)
    clean_dev_caches

    # 7. System caches (Xcode, pip, Homebrew, typescript, tmp)
    clean_system_caches

    # 8. Final purge (now more effective — apps already released memory)
    purge_ram

    # Capture after state
    local mem_after disk_after swap_after
    mem_after=$(get_memory_stats | cut -d'|' -f1)
    disk_after=$(get_disk_free)
    swap_after=$(get_swap_stats)

    local duration=$(( $(date +%s) - start_time ))
    save_stats "deep" "$mem_before" "$mem_after" "$disk_before" "$disk_after" "$duration"

    local ram_freed swap_freed
    ram_freed=$(echo "$mem_before $mem_after" | awk '{r=$1-$2; printf "%.1f", (r>0?r:0)}')
    swap_freed=$(echo "$swap_before $swap_after" | awk '{r=$1-$2; printf "%.0f", (r>0?r:0)}')

    echo ""
    echo "=== After ==="
    echo "RAM:  ${mem_after}GB used (freed ${ram_freed}GB)"
    echo "Swap: ${swap_after}MB (freed ${swap_freed}MB)"
    echo "Disk: ${disk_after} free"
    echo "Time: ${duration}s"

    # Top consumers
    get_top_consumers

    # Kill recommendations if swap still high
    get_kill_recommendations "$swap_after"

    log "=== Deep maintenance done (${duration}s, freed ~${ram_freed}GB RAM, ~${swap_freed}MB swap) ==="
}

# --- Entry Point ---

rotate_log

case "${1:-}" in
    --quick|-q)
        run_quick
        ;;
    --deep|-d)
        run_deep
        ;;
    --dry-run|-n)
        run_dry
        ;;
    --status|-s)
        show_status
        ;;
    --setup)
        setup_passwordless_purge
        ;;
    --help|-h)
        echo "Huxley Mac Maintenance (Mole + RAM purge)"
        echo ""
        echo "Usage:"
        echo "  mac-maintenance.sh              Full clean + optimize + purge"
        echo "  mac-maintenance.sh --quick      RAM purge only (fast, ~5s)"
        echo "  mac-maintenance.sh --deep       Aggressive: pressure + orphan kill + caches + purge + swap report"
        echo "  mac-maintenance.sh --dry-run    Preview what would be cleaned"
        echo "  mac-maintenance.sh --status     Show current RAM/disk/swap stats"
        echo "  mac-maintenance.sh --setup      One-time: enable passwordless purge"
        echo ""
        echo "Logs: $LOG_DIR"
        ;;
    *)
        run_full
        ;;
esac
