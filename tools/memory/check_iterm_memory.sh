#!/bin/bash
# iTerm2 Memory Monitor
# Checks iTerm2 memory usage and alerts if excessive
# Recommended: Run weekly via cron or LaunchAgent

set -euo pipefail

ITERM_PID=$(pgrep -x iTerm2 || echo "")

if [ -z "$ITERM_PID" ]; then
    echo "ℹ️  iTerm2 is not running"
    exit 0
fi

# Get memory usage in MB
MEMORY_KB=$(ps -o rss= -p "$ITERM_PID")
MEMORY_MB=$(echo "scale=2; $MEMORY_KB / 1024" | bc)
MEMORY_GB=$(echo "scale=2; $MEMORY_KB / 1024 / 1024" | bc)

# Get uptime
UPTIME_SECONDS=$(ps -o etime= -p "$ITERM_PID" | awk -F- '{if (NF==2) {print $1*86400 + $2} else {print $1}}' | awk -F: '{if (NF==3) {print $1*3600 + $2*60 + $3} else if (NF==2) {print $1*60 + $2} else {print $1}}')
UPTIME_HOURS=$(echo "scale=1; $UPTIME_SECONDS / 3600" | bc)

echo "📊 iTerm2 Memory Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Memory Usage: ${MEMORY_MB} MB (${MEMORY_GB} GB)"
echo "Process Uptime: ${UPTIME_HOURS} hours"
echo ""

# Alert thresholds
WARNING_THRESHOLD_MB=2048  # 2 GB
CRITICAL_THRESHOLD_MB=10240  # 10 GB

if (( $(echo "$MEMORY_MB > $CRITICAL_THRESHOLD_MB" | bc -l) )); then
    echo "🚨 CRITICAL: iTerm2 using ${MEMORY_GB} GB!"
    echo "   Action required: Restart iTerm2 immediately"
    echo "   1. Save your work"
    echo "   2. pkill -9 iTerm2"
    echo "   3. Verify configs: defaults read com.googlecode.iterm2 | grep -i scrollback"
    exit 2
elif (( $(echo "$MEMORY_MB > $WARNING_THRESHOLD_MB" | bc -l) )); then
    echo "⚠️  WARNING: iTerm2 using ${MEMORY_GB} GB"
    echo "   Consider restarting iTerm2 soon"
    echo "   Tip: Cmd+K to clear scrollback in active sessions"
    exit 1
else
    echo "✅ Memory usage is healthy"
    exit 0
fi
