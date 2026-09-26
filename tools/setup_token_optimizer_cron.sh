#!/bin/bash
#
# Setup Token Optimizer Cron Job
# Configures automated cleanup to run daily
#

set -e

# Configuration
CATALYST_DIR="{{CATALYST_ROOT}}"
SCRIPT_PATH="$CATALYST_DIR/tools/token_optimizer.py"
LOG_DIR="$CATALYST_DIR/logs/token-optimizer"
RETENTION_DAYS=7

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "Token Optimizer - Cron Job Setup"
echo "=================================================="
echo

# Create log directory
mkdir -p "$LOG_DIR"

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Error: Token optimizer script not found at $SCRIPT_PATH"
    exit 1
fi

# Make script executable
chmod +x "$SCRIPT_PATH"

# Generate cron command
CRON_TIME="0 3 * * *"  # 3 AM daily
LOG_FILE="$LOG_DIR/cleanup_\$(date +\%Y\%m\%d).log"
CRON_CMD="$CRON_TIME cd $CATALYST_DIR && /usr/bin/python3 $SCRIPT_PATH --retention-days $RETENTION_DAYS >> $LOG_FILE 2>&1"

echo -e "${BLUE}Configuration:${NC}"
echo "  Script: $SCRIPT_PATH"
echo "  Schedule: Daily at 3:00 AM"
echo "  Retention: $RETENTION_DAYS days"
echo "  Logs: $LOG_DIR"
echo

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "token_optimizer.py"; then
    echo -e "${YELLOW}⚠️  Existing token optimizer cron job found${NC}"
    echo
    echo "Current cron job:"
    crontab -l | grep "token_optimizer.py"
    echo
    read -p "Replace existing cron job? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi

    # Remove existing job
    crontab -l | grep -v "token_optimizer.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo
echo -e "${GREEN}✅ Cron job installed successfully!${NC}"
echo
echo "Scheduled job:"
echo "  $CRON_CMD"
echo

# Verify installation
echo "Current crontab:"
echo "─────────────────────────────────────────────────"
crontab -l | grep "token_optimizer.py"
echo "─────────────────────────────────────────────────"
echo

# Test run
echo "Would you like to run a dry-run test now? (y/n): "
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo
    echo "Running dry-run test..."
    cd "$CATALYST_DIR"
    python3 "$SCRIPT_PATH" --dry-run
fi

echo
echo -e "${GREEN}Setup complete!${NC}"
echo
echo "The token optimizer will run daily at 3:00 AM."
echo "Logs will be saved to: $LOG_DIR"
echo
echo "Manual commands:"
echo "  # Run now (dry-run):  python3 $SCRIPT_PATH --dry-run"
echo "  # Run now (live):     python3 $SCRIPT_PATH"
echo "  # View logs:          ls -lh $LOG_DIR"
echo "  # Remove cron job:    crontab -l | grep -v token_optimizer.py | crontab -"
echo
