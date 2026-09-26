# SDK Production Deployment Guide

Complete guide for deploying SDK workflows, webhook server, and monitoring dashboard to production.

## Prerequisites

### System Requirements
- macOS 10.15+ (for daily audit workflow)
- Python 3.9+
- Virtual environment with dependencies installed
- 100MB+ free disk space

### Required Environment Variables

```bash
# Webhook Server
export SDK_WEBHOOK_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SDK_WEBHOOK_URL="http://localhost:5000"

# Optional: Enable notifications
export SDK_CRON_NOTIFY="true"

# Store in ~/.zshrc or ~/.bashrc for persistence
echo "export SDK_WEBHOOK_API_KEY=\"your-key-here\"" >> ~/.zshrc
```

## Quick Start

```bash
# 1. Generate API key
export SDK_WEBHOOK_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# 2. Start webhook server (background)
cd {{CATALYST_ROOT}}/tools/sdk
source .venv/bin/activate
gunicorn -w 4 -b 127.0.0.1:5000 webhook_server:app --daemon

# 3. Install cron jobs
crontab {{CATALYST_ROOT}}/tools/sdk/crontab.example

# 4. Generate dashboard
./generate_dashboard.py --refresh 30

# 5. Verify
./end_to_end_test.py
```

## Deployment Options

### Option 1: LaunchAgent (macOS - Recommended)

```bash
# Create LaunchAgent
cat > ~/Library/LaunchAgents/com.huxley.sdk-webhook.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.huxley.sdk-webhook</string>
    <key>ProgramArguments</key>
    <array>
        <string>{{CATALYST_ROOT}}/tools/sdk/.venv/bin/gunicorn</string>
        <string>-w</string>
        <string>4</string>
        <string>-b</string>
        <string>127.0.0.1:5000</string>
        <string>webhook_server:app</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{{CATALYST_ROOT}}/tools/sdk</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>SDK_WEBHOOK_API_KEY</key>
        <string>YOUR_API_KEY_HERE</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{{CATALYST_ROOT}}/registry/logs/webhook-server.log</string>
    <key>StandardErrorPath</key>
    <string>{{CATALYST_ROOT}}/registry/logs/webhook-server.err</string>
</dict>
</plist>
EOF

# Replace YOUR_API_KEY_HERE with actual key
sed -i '' "s/YOUR_API_KEY_HERE/$SDK_WEBHOOK_API_KEY/" ~/Library/LaunchAgents/com.huxley.sdk-webhook.plist

# Load service
launchctl load ~/Library/LaunchAgents/com.huxley.sdk-webhook.plist
launchctl start com.huxley.sdk-webhook

# Verify
curl http://localhost:5000/health
```

### Option 2: Manual Start (Development)

```bash
cd {{CATALYST_ROOT}}/tools/sdk
source .venv/bin/activate
export SDK_WEBHOOK_API_KEY="your-key-here"
./webhook_server.py
```

## Cron Installation

```bash
# Edit crontab
crontab -e

# Add daily audit (9:10 AM)
10 9 * * * export SDK_WEBHOOK_API_KEY="your-key" && {{CATALYST_ROOT}}/tools/sdk/cron_wrapper.py {{CATALYST_ROOT}}/tools/sdk/daily_audit_workflow.py >> {{CATALYST_ROOT}}/registry/cron/daily_audit.log 2>&1

# Add dashboard refresh (every 15 min, 9 AM - 6 PM)
*/15 9-18 * * * export SDK_WEBHOOK_API_KEY="your-key" && {{CATALYST_ROOT}}/tools/sdk/cron_wrapper.py {{CATALYST_ROOT}}/tools/sdk/generate_dashboard.py --timeout 60 >> {{CATALYST_ROOT}}/registry/cron/dashboard.log 2>&1
```

## Monitoring

### Dashboard Access

```bash
# Generate dashboard
./generate_dashboard.py --refresh 30

# Open in browser
open {{CATALYST_ROOT}}/registry/dashboard/sdk_monitor.html

# Serve with HTTP server
cd {{CATALYST_ROOT}}/registry/dashboard
python3 -m http.server 8080
# Access at http://localhost:8080/sdk_monitor.html
```

### View Logs

```bash
# Webhook server
tail -f {{CATALYST_ROOT}}/registry/logs/webhook-server.log

# Cron jobs
tail -f {{CATALYST_ROOT}}/registry/cron/*.log

# Daily audit
tail -f {{CATALYST_ROOT}}/registry/daily/daily_audit.log
```

### Check Status

```bash
# Workflow metrics
./view_sdk_events.py --summary

# Specific workflow
./view_sdk_events.py --metrics daily_audit

# Governance compliance
./governance_validator.py report

# Full test suite
./end_to_end_test.py --verbose
```

## Verification Checklist

- [ ] Webhook server running (`curl http://localhost:5000/health`)
- [ ] API key set (`echo $SDK_WEBHOOK_API_KEY`)
- [ ] Cron jobs installed (`crontab -l`)
- [ ] Dashboard generates (`./generate_dashboard.py`)
- [ ] Tests pass (`./end_to_end_test.py`)
- [ ] Governance validates (`./governance_validator.py report`)

## Troubleshooting

**Webhook server not starting:**
```bash
lsof -i :5000  # Check port
cat {{CATALYST_ROOT}}/registry/logs/webhook-server.err  # Check errors
launchctl list | grep webhook  # Check LaunchAgent
```

**Cron jobs not running:**
```bash
crontab -l  # Verify installed
tail -f /var/log/system.log | grep cron  # macOS logs
./cron_wrapper.py --dry-run workflow.py  # Test manually
```

**Dashboard not updating:**
```bash
./generate_dashboard.py  # Manual regeneration
ls -la {{CATALYST_ROOT}}/registry/dashboard/  # Check permissions
```

## Security

- Store API keys in environment variables only
- Use HTTPS for external access (nginx reverse proxy)
- Regular backups of `~/.claude/mcp-data/` and `registry/`
- Log rotation enabled
- Audit all webhook events

## Maintenance

**Daily:** Check dashboard metrics
**Weekly:** Review logs, compliance report
**Monthly:** Update dependencies, run full tests
**Quarterly:** Security audit, performance review

## Support

- Logs: `{{CATALYST_ROOT}}/registry/logs/`
- Tests: `./end_to_end_test.py --verbose`
- Docs: `{{CATALYST_ROOT}}/tools/sdk/*.md`
