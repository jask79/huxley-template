#!/bin/bash
# Unified Alert Handler for Huxley

SEVERITY="$1"
MESSAGE="$2"
SOURCE="$3"

ALERT_LOG="{{CATALYST_ROOT}}/registry/alerts.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Log alert
echo "[$TIMESTAMP] [$SEVERITY] [$SOURCE] $MESSAGE" >> "$ALERT_LOG"

# Desktop notification for warnings and above
if [[ "$SEVERITY" != "info" ]]; then
    osascript -e "display notification \"$MESSAGE\" with title \"Huxley Alert\" subtitle \"$SOURCE ($SEVERITY)\""
fi

# Critical alerts get additional attention
if [[ "$SEVERITY" == "critical" ]]; then
    echo "🚨 CRITICAL ALERT: $MESSAGE" | tee -a "$ALERT_LOG"
    # Could add additional escalation here
fi
