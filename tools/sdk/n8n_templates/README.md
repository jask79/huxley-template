# n8n Integration Templates for SDK Workflows

Pre-built n8n workflow templates for integrating with SDK webhook server and workflows.

## Templates

### 1. Webhook Trigger (`webhook_trigger.json`)

**Purpose:** Accept external webhook events and forward to SDK webhook server

**Use Cases:**
- Third-party service integrations
- Custom webhook endpoints
- Event aggregation

**Configuration:**
1. Import workflow into n8n
2. Set webhook path in Webhook Trigger node
3. Configure SDK_WEBHOOK_API_KEY credential
4. Update SDK webhook server URL if needed
5. Activate workflow

**Test:**
```bash
curl -X POST http://your-n8n-host/webhook/sdk-workflow-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "test_workflow",
    "message": "Hello from external system"
  }'
```

### 2. Scheduled Workflow (`scheduled_workflow.json`)

**Purpose:** Trigger SDK workflows on a schedule

**Use Cases:**
- Daily/hourly workflow execution
- Automated maintenance tasks
- Periodic health checks

**Configuration:**
1. Import workflow into n8n
2. Update cron expression in Cron Trigger node (default: 9 AM daily)
3. Set workflow name to trigger
4. Configure SDK_WEBHOOK_API_KEY credential
5. Activate workflow

**Cron Examples:**
- `0 9 * * *` - 9 AM daily
- `*/15 * * * *` - Every 15 minutes
- `0 */2 * * *` - Every 2 hours
- `0 0 * * 0` - Midnight every Sunday

### 3. GitHub Webhook (`github_webhook.json`)

**Purpose:** Integrate GitHub events with SDK workflows

**Use Cases:**
- CI/CD pipeline triggers
- Code push notifications
- Deployment automation

**Configuration:**
1. Import workflow into n8n
2. Get webhook URL from Webhook node
3. Add webhook to GitHub repository settings
4. Configure SDK_WEBHOOK_API_KEY credential
5. Update branch filter if needed (default: main)
6. Activate workflow

**GitHub Setup:**
1. Go to repository Settings → Webhooks
2. Add webhook URL: `http://your-n8n-host/webhook/github-webhook`
3. Content type: `application/json`
4. Events: Push events
5. Active: ✓

## Prerequisites

### 1. n8n Installation

Install n8n if not already running:

```bash
# npm
npm install -g n8n

# Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n

# Start n8n
n8n start
```

Access n8n at: http://localhost:5678

### 2. SDK Webhook Server

Ensure webhook server is running:

```bash
# Set API key
export SDK_WEBHOOK_API_KEY="your-secure-api-key"

# Start webhook server
cd {{CATALYST_ROOT}}/tools/sdk
source .venv/bin/activate
./webhook_server.py
```

Or with gunicorn for production:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app
```

### 3. Credentials Setup

Create HTTP Header Auth credential in n8n:

1. Go to n8n Settings → Credentials
2. Add new credential: "Header Auth"
3. Name: `SDK Webhook API Key`
4. Add header:
   - Name: `X-API-Key`
   - Value: Your SDK_WEBHOOK_API_KEY
5. Save

## Importing Templates

### Method 1: n8n UI

1. Open n8n at http://localhost:5678
2. Click "Workflows" → "Import from File"
3. Select template JSON file
4. Click "Import"
5. Configure credentials
6. Activate workflow

### Method 2: n8n CLI

```bash
# Import workflow
n8n import:workflow --input=webhook_trigger.json

# List workflows
n8n list:workflow

# Activate workflow
n8n update:workflow --id=WORKFLOW_ID --active=true
```

### Method 3: API

```bash
# Import via API
curl -X POST http://localhost:5678/rest/workflows \
  -H "Content-Type: application/json" \
  -d @webhook_trigger.json
```

## Customization

### Modifying Webhook Endpoints

Update the `url` parameter in HTTP Request nodes:

```json
{
  "parameters": {
    "url": "http://your-server:5000/webhook/observe"
  }
}
```

### Adding Authentication

Templates use Header Auth by default. For other methods:

**Basic Auth:**
```json
{
  "authentication": "basicAuth",
  "basicAuth": "={{ $credentials.basicAuth }}"
}
```

**OAuth2:**
```json
{
  "authentication": "oAuth2",
  "oAuth2": "={{ $credentials.oAuth2 }}"
}
```

### Adding Error Handling

Add error handling nodes after HTTP requests:

1. Add "Error Trigger" node
2. Connect to failed HTTP Request
3. Add notification or logging logic

Example error handler:
```json
{
  "name": "Error Handler",
  "type": "n8n-nodes-base.errorTrigger",
  "position": [850, 450]
}
```

## Testing Workflows

### Test Webhook Trigger

```bash
# Test webhook endpoint
curl -X POST http://localhost:5678/webhook/sdk-workflow-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "test_workflow",
    "message": "Test from curl",
    "metadata": {
      "source": "manual_test",
      "timestamp": "2025-10-08T22:00:00Z"
    }
  }'
```

### Test Scheduled Workflow

1. Open workflow in n8n
2. Click "Execute Workflow" button
3. Check execution results
4. Verify webhook server received trigger

### Test GitHub Webhook

1. Make a commit to main branch
2. Push to GitHub
3. Check n8n execution log
4. Verify SDK webhook server received observation

## Monitoring

### n8n Execution History

View execution history in n8n:
1. Go to "Executions" tab
2. Filter by workflow name
3. View detailed execution logs

### SDK Webhook Server Logs

```bash
# View webhook observations
./view_sdk_events.py --workflow n8n_scheduler

# View metrics
./view_sdk_events.py --metrics n8n_scheduler

# Search observations
./view_sdk_events.py --search "n8n"
```

### Dashboard Monitoring

```bash
# Generate dashboard
./generate_dashboard.py

# View dashboard
open {{CATALYST_ROOT}}/registry/dashboard/sdk_monitor.html
```

## Production Deployment

### 1. Secure n8n

```bash
# Set basic auth
export N8N_BASIC_AUTH_ACTIVE=true
export N8N_BASIC_AUTH_USER=admin
export N8N_BASIC_AUTH_PASSWORD=secure-password

# Enable HTTPS
export N8N_PROTOCOL=https
export N8N_SSL_KEY=/path/to/ssl/key.pem
export N8N_SSL_CERT=/path/to/ssl/cert.pem
```

### 2. Persist Data

Use external database for n8n:

```bash
# PostgreSQL
export DB_TYPE=postgresdb
export DB_POSTGRESDB_HOST=localhost
export DB_POSTGRESDB_PORT=5432
export DB_POSTGRESDB_DATABASE=n8n
export DB_POSTGRESDB_USER=n8n_user
export DB_POSTGRESDB_PASSWORD=password
```

### 3. Production Webhook Server

Use systemd or Docker for webhook server:

```bash
# systemd service
sudo systemctl enable webhook_server
sudo systemctl start webhook_server

# Docker
docker run -d \
  --name sdk-webhook-server \
  -p 5000:5000 \
  -e SDK_WEBHOOK_API_KEY=your-key \
  -v ~/.claude/mcp-data:/root/.claude/mcp-data \
  sdk-webhook-server:latest
```

## Troubleshooting

### Webhook Not Triggering

1. Check n8n workflow is active
2. Verify webhook URL is correct
3. Test webhook with curl
4. Check n8n execution logs

### Authentication Errors

1. Verify API key is set correctly
2. Check credential is selected in nodes
3. Test webhook server authentication:
   ```bash
   curl -H "X-API-Key: your-key" http://localhost:5000/health
   ```

### Workflow Execution Fails

1. Check n8n error logs
2. Verify webhook server is running
3. Test SDK workflows manually
4. Check network connectivity

## Advanced Patterns

### Workflow Chaining

Chain multiple workflows together:

1. Workflow A triggers
2. Workflow A calls SDK webhook
3. SDK webhook triggers Workflow B
4. Workflow B processes and responds

### Error Retry Logic

Add retry mechanism:

```json
{
  "name": "Retry on Failure",
  "type": "n8n-nodes-base.errorTrigger",
  "parameters": {
    "retryCount": 3,
    "retryDelay": 5000
  }
}
```

### Conditional Routing

Route based on workflow results:

```json
{
  "name": "Route Based on Status",
  "type": "n8n-nodes-base.switch",
  "parameters": {
    "rules": {
      "rules": [
        {
          "conditions": {
            "string": [
              {
                "value1": "={{ $json.status }}",
                "value2": "success"
              }
            ]
          }
        }
      ]
    }
  }
}
```

## Resources

- [n8n Documentation](https://docs.n8n.io/)
- [n8n Community](https://community.n8n.io/)
- [SDK Webhook Server Docs](../WEBHOOK_SERVER.md)
- [Huxley Automation Guide](../../docs/AUTOMATION.md)
