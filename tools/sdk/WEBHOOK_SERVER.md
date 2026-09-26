# SDK Webhook Server

Flask-based webhook server for receiving SDK workflow events from external sources. Provides authenticated endpoints for logging observations, triggering workflows, and querying workflow status.

## Features

- **API Key Authentication** - Secure endpoints with X-API-Key header
- **Event Ingestion** - Log workflow observations from external systems
- **Pattern Learning** - Learn from workflow outcomes
- **Workflow Triggers** - Request workflow execution via webhook
- **Status Queries** - Check workflow health and metrics
- **Integration Ready** - Works with GitHub webhooks, n8n, Zapier, etc.

## Quick Start

### 1. Install Dependencies

```bash
cd {{CATALYST_ROOT}}/tools/sdk
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set API Key

```bash
# Generate a secure API key
export SDK_WEBHOOK_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Or set a custom key
export SDK_WEBHOOK_API_KEY="your-secret-key-here"
```

### 3. Start Server

**Development mode:**
```bash
./webhook_server.py
# Server runs on http://127.0.0.1:5000
```

**Production mode with gunicorn:**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app
```

**Custom host/port:**
```bash
./webhook_server.py --host 0.0.0.0 --port 8080
```

## API Endpoints

### Health Check (No Auth)

```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-08T20:00:00.000000",
  "version": "1.0.0"
}
```

### Log Observation

**Endpoint:** `POST /webhook/observe`
**Auth:** Required

```bash
curl -X POST http://localhost:5000/webhook/observe \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "daily_audit",
    "observation": "Triggered by GitHub webhook",
    "metadata": {
      "source": "github",
      "commit": "abc123"
    }
  }'
```

Response:
```json
{
  "status": "success",
  "observation_id": "a1b2c3d4e5f6",
  "workflow": "daily_audit",
  "timestamp": "2025-10-08T20:00:00.000000"
}
```

### Learn from Workflow

**Endpoint:** `POST /webhook/learn`
**Auth:** Required

```bash
curl -X POST http://localhost:5000/webhook/learn \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "daily_audit",
    "success": true,
    "metrics": {
      "duration_ms": 1234,
      "smoke_exit": 0
    },
    "notes": "All tests passed"
  }'
```

Response:
```json
{
  "status": "success",
  "pattern_id": "pattern_xyz",
  "workflow": "daily_audit",
  "timestamp": "2025-10-08T20:00:00.000000"
}
```

### Trigger Workflow

**Endpoint:** `POST /webhook/trigger`
**Auth:** Required

```bash
curl -X POST http://localhost:5000/webhook/trigger \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "daily_audit",
    "parameters": {
      "dry_run": false,
      "verbose": true
    }
  }'
```

Response:
```json
{
  "status": "triggered",
  "observation_id": "x1y2z3",
  "workflow": "daily_audit",
  "parameters": {"dry_run": false, "verbose": true},
  "timestamp": "2025-10-08T20:00:00.000000",
  "note": "Trigger logged. Actual execution handled by external orchestration."
}
```

### Get Workflow Status

**Endpoint:** `GET /workflow/<name>/status`
**Auth:** Required

```bash
curl http://localhost:5000/workflow/daily_audit/status \
  -H "X-API-Key: your-api-key"
```

Response:
```json
{
  "workflow": "daily_audit",
  "metrics": {
    "run_count": 42,
    "success_rate": 95.2,
    "avg_duration_ms": 1234.5,
    "last_run": "2025-10-08T09:10:00.000000"
  },
  "recent_history": [...],
  "timestamp": "2025-10-08T20:00:00.000000"
}
```

### List All Workflows

**Endpoint:** `GET /workflows`
**Auth:** Required

```bash
curl http://localhost:5000/workflows \
  -H "X-API-Key: your-api-key"
```

Response:
```json
{
  "workflows": ["daily_audit", "test_workflow", "build_workflow"],
  "count": 3,
  "timestamp": "2025-10-08T20:00:00.000000"
}
```

## Integration Examples

### GitHub Webhook

Configure a GitHub webhook to send events to your server:

**Webhook URL:** `https://your-server.com/webhook/observe`
**Content Type:** `application/json`
**Secret:** Your API key (set as X-API-Key header)

**Payload mapping:**
```json
{
  "workflow": "github_event",
  "observation": "{{event.type}} on {{repository.name}}",
  "metadata": {
    "commit": "{{head_commit.id}}",
    "author": "{{head_commit.author.name}}",
    "branch": "{{ref}}"
  }
}
```

### n8n Integration

1. Create HTTP Request node
2. Set Method: POST
3. Set URL: `http://localhost:5000/webhook/observe`
4. Add Header: `X-API-Key` with your API key
5. Set Body to JSON:
   ```json
   {
     "workflow": "{{$node.webhook.workflow_name}}",
     "observation": "{{$node.webhook.message}}",
     "metadata": {{$json}}
   }
   ```

### cron Integration

Create a cron job that sends status updates:

```bash
#!/bin/bash
# {{CATALYST_ROOT}}/tools/cron/webhook_status.sh

API_KEY="your-api-key"
WORKFLOW="daily_audit"

curl -X POST http://localhost:5000/webhook/observe \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"workflow\": \"$WORKFLOW\",
    \"observation\": \"Cron execution completed\",
    \"metadata\": {
      \"source\": \"cron\",
      \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)\"
    }
  }"
```

Add to crontab:
```
# Send status update after daily audit
15 9 * * * {{CATALYST_ROOT}}/tools/cron/webhook_status.sh
```

## Testing

Use the included test client to verify server functionality:

```bash
# Terminal 1: Start server
export SDK_WEBHOOK_API_KEY="test-key-12345"
./webhook_server.py

# Terminal 2: Run test client
./test_webhook_client.py
```

Expected output:
```
✓ PASS - Health Check
✓ PASS - Webhook Observe
✓ PASS - Webhook Learn
✓ PASS - Webhook Trigger
✓ PASS - Workflow Status
✓ PASS - List Workflows
✓ PASS - Authentication

Total: 7/7 tests passed
```

## Security

- **API Key Storage:** Store API keys in environment variables, never in code
- **HTTPS:** Use HTTPS in production (configure reverse proxy like nginx)
- **Rate Limiting:** Consider adding rate limiting for production use
- **IP Allowlist:** Consider restricting webhook sources by IP
- **Log Sensitive Data:** Webhook metadata may contain sensitive info - review before logging

## Production Deployment

### Using gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Start with 4 workers
export SDK_WEBHOOK_API_KEY="your-production-key"
gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app

# With systemd service
sudo cp webhook_server.service /etc/systemd/system/
sudo systemctl enable webhook_server
sudo systemctl start webhook_server
```

### Using systemd

Create `/etc/systemd/system/webhook_server.service`:

```ini
[Unit]
Description=SDK Webhook Server
After=network.target

[Service]
Type=simple
User={{USER_LOGIN}}
WorkingDirectory={{CATALYST_ROOT}}/tools/sdk
Environment="SDK_WEBHOOK_API_KEY=your-production-key"
ExecStart={{CATALYST_ROOT}}/tools/sdk/.venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name webhooks.your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring

View webhook server logs and metrics:

```bash
# View recent observations
./view_sdk_events.py --workflow webhook_server

# View metrics
./view_sdk_events.py --metrics webhook_server

# Generate monitoring dashboard
./generate_dashboard.py
open {{CATALYST_ROOT}}/registry/dashboard/sdk_monitor.html
```

## Troubleshooting

**Server won't start:**
- Check if port is already in use: `lsof -i :5000`
- Verify Flask is installed: `pip list | grep -i flask`
- Check API key is set: `echo $SDK_WEBHOOK_API_KEY`

**401 Unauthorized:**
- Verify X-API-Key header is set
- Check API key matches server key

**403 Forbidden:**
- API key provided but incorrect
- Verify key matches: `echo $SDK_WEBHOOK_API_KEY`

**500 Internal Server Error:**
- Check server logs for stack trace
- Verify MCP memory path exists: `~/.claude/mcp-data/builder-memory.json`
- Check disk space and permissions

## Architecture

```
External System (GitHub, n8n, cron)
    ↓
Flask Webhook Server (webhook_server.py)
    ↓
SDKMemoryBridge (sdk_memory_bridge.py)
    ↓
MCP Memory (~/.claude/mcp-data/builder-memory.json)
    ↓
Pattern Learning Database (registry/pattern_learning.db)
```

## Next Steps

- **Week 4:** Integrate with n8n workflows
- **Week 4:** Add cron wrappers for automated triggers
- **Week 4:** Deploy to production with monitoring
- **Week 4:** Set up governance validation workflows
