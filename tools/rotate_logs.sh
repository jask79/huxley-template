#!/bin/bash
set -euo pipefail

# rotate_logs.sh - Log rotation for Huxley
# Rotates and compresses logs when they exceed size threshold

CATALYST_ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
REGISTRY="$CATALYST_ROOT/registry"
MAX_SIZE_MB=5
KEEP_ARCHIVES=5
VERBOSE=false

usage() {
    cat << 'EOF'
rotate_logs.sh - Huxley Log Rotation

Usage: rotate_logs.sh [options]

Options:
  --max-size SIZE     Maximum log size in MB before rotation (default: 5)
  --keep-archives N   Number of archived logs to keep (default: 5)
  --verbose, -v       Show detailed output
  --help, -h          Show this help message

Logs rotated:
  - inbox-sync.log
  - planner-hooks.log  
  - inbox-sync.launchd.log
  - test-builder.log

Archives are compressed with gzip and named: logfile.1.gz, logfile.2.gz, etc.
EOF
}

log_msg() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] LOG_ROTATION: $message" >> "$REGISTRY/log-rotation.log"
}

get_file_size_mb() {
    local file="$1"
    if [ -f "$file" ]; then
        local size_bytes
        size_bytes=$(stat -f%z "$file" 2>/dev/null || echo "0")
        echo $((size_bytes / 1024 / 1024))
    else
        echo "0"
    fi
}

rotate_log() {
    local logfile="$1"
    
    if [ ! -f "$logfile" ]; then
        [ "$VERBOSE" = true ] && log_msg "Log file not found: $logfile"
        return 0
    fi
    
    local size_mb
    size_mb=$(get_file_size_mb "$logfile")
    
    if [ "$size_mb" -lt "$MAX_SIZE_MB" ]; then
        [ "$VERBOSE" = true ] && log_msg "Log file $logfile is ${size_mb}MB (under ${MAX_SIZE_MB}MB threshold)"
        return 0
    fi
    
    log_msg "Rotating $logfile (${size_mb}MB > ${MAX_SIZE_MB}MB threshold)"
    
    local basename
    basename=$(basename "$logfile")
    local dir
    dir=$(dirname "$logfile")
    
    # Shift existing archives
    for i in $(seq $((KEEP_ARCHIVES - 1)) -1 2); do
        local old_archive="$dir/${basename}.$((i-1)).gz"
        local new_archive="$dir/${basename}.${i}.gz"
        
        if [ -f "$old_archive" ]; then
            mv "$old_archive" "$new_archive"
            [ "$VERBOSE" = true ] && log_msg "Moved $old_archive to $new_archive"
        fi
    done
    
    # Compress current log to .1.gz
    if [ -f "$logfile" ]; then
        gzip -c "$logfile" > "$dir/${basename}.1.gz"
        
        # Clear current log but keep file for ongoing writes
        > "$logfile"
        
        log_msg "Rotated and compressed $basename to ${basename}.1.gz"
    fi
    
    # Remove oldest archive if it exists
    local oldest_archive="$dir/${basename}.${KEEP_ARCHIVES}.gz"
    if [ -f "$oldest_archive" ]; then
        rm -f "$oldest_archive"
        log_msg "Removed oldest archive: ${basename}.${KEEP_ARCHIVES}.gz"
    fi
}

cleanup_old_archives() {
    local logfile="$1"
    local basename
    basename=$(basename "$logfile")
    local dir
    dir=$(dirname "$logfile")
    
    # Remove any archives beyond our keep limit
    for i in $(seq $((KEEP_ARCHIVES + 1)) 20); do
        local old_archive="$dir/${basename}.${i}.gz"
        if [ -f "$old_archive" ]; then
            rm -f "$old_archive"
            [ "$VERBOSE" = true ] && log_msg "Cleaned up excess archive: ${basename}.${i}.gz"
        fi
    done
}

show_log_status() {
    local logfile="$1"
    
    if [ ! -f "$logfile" ]; then
        echo "  $(basename "$logfile"): Not found"
        return
    fi
    
    local size_mb
    size_mb=$(get_file_size_mb "$logfile")
    local basename
    basename=$(basename "$logfile")
    local dir
    dir=$(dirname "$logfile")
    
    # Count archives
    local archive_count=0
    for i in $(seq 1 20); do
        if [ -f "$dir/${basename}.${i}.gz" ]; then
            ((archive_count++))
        else
            break
        fi
    done
    
    local status="OK"
    [ "$size_mb" -ge "$MAX_SIZE_MB" ] && status="NEEDS ROTATION"
    
    printf "  %-25s %3sMB  %s archives  %s\n" "$(basename "$logfile"):" "$size_mb" "$archive_count" "$status"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-size)
            MAX_SIZE_MB="$2"
            shift 2
            ;;
        --keep-archives)
            KEEP_ARCHIVES="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

# Ensure registry directory exists
mkdir -p "$REGISTRY"

echo "=== Huxley Log Rotation ==="
echo "$(date)"
echo "Max size: ${MAX_SIZE_MB}MB"
echo "Keep archives: $KEEP_ARCHIVES"
echo

# Show current status
echo "Log Status:"
for logfile in \
    "$REGISTRY/inbox-sync.log" \
    "$REGISTRY/planner-hooks.log" \
    "$REGISTRY/inbox-sync.launchd.log" \
    "$REGISTRY/test-builder.log" \
    "$REGISTRY/log-rotation.log"; do
    show_log_status "$logfile"
done
echo

# Rotate logs that need it
ROTATIONS_PERFORMED=0
for logfile in \
    "$REGISTRY/inbox-sync.log" \
    "$REGISTRY/planner-hooks.log" \
    "$REGISTRY/inbox-sync.launchd.log" \
    "$REGISTRY/test-builder.log"; do
    
    if [ -f "$logfile" ]; then
        size_mb=$(get_file_size_mb "$logfile")
        
        if [ "$size_mb" -ge "$MAX_SIZE_MB" ]; then
            rotate_log "$logfile"
            cleanup_old_archives "$logfile"
            ((ROTATIONS_PERFORMED++))
        fi
    fi
done

# Summary
if [ "$ROTATIONS_PERFORMED" -gt 0 ]; then
    echo "✅ Rotated $ROTATIONS_PERFORMED log file(s)"
    log_msg "Log rotation completed: $ROTATIONS_PERFORMED files rotated"
else
    echo "✅ No logs need rotation"
    [ "$VERBOSE" = true ] && log_msg "Log rotation check completed: no files needed rotation"
fi

# Show disk usage
if command -v du >/dev/null 2>&1; then
    total_size=$(du -sh "$REGISTRY" 2>/dev/null | cut -f1)
    echo "Registry disk usage: $total_size"
fi

echo
echo "To set up automatic rotation:"
echo "  # Add to crontab (monthly at 3 AM):"
echo "  0 3 1 * * $CATALYST_ROOT/tools/rotate_logs.sh"
echo "  # Or create a launch agent for automatic rotation"

exit 0




