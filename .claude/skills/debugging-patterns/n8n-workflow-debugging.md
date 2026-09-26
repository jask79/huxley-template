# N8N Workflow Debugging

Patterns for debugging n8n workflows via REST API and MCP integration.

## Overview

N8N workflows are debugged via REST API (not database access). This ensures compatibility across self-hosted and cloud deployments.

**When to use:**
- Workflow execution failures
- Node configuration issues
- Credential problems
- Expression syntax errors

## N8N API Client

```python
import requests
import os

class N8nAPIClient:
    """Client for n8n REST API debugging operations"""

    def __init__(self):
        self.base_url = os.getenv('N8N_BASE_URL', 'https://n8n.localhost')
        self.api_key = os.getenv('N8N_API_KEY')
        self.headers = {
            'X-N8N-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

    def get_workflow(self, workflow_id):
        """Get workflow definition"""
        response = requests.get(
            f"{self.base_url}/api/v1/workflows/{workflow_id}",
            headers=self.headers
        )
        return response.json()

    def get_executions(self, workflow_id=None, limit=10, status=None):
        """Get workflow executions with optional filtering"""
        params = {'limit': limit}
        if workflow_id:
            params['workflowId'] = workflow_id
        if status:
            params['status'] = status

        response = requests.get(
            f"{self.base_url}/api/v1/executions",
            headers=self.headers,
            params=params
        )
        return response.json().get('data', [])

    def get_execution(self, execution_id):
        """Get specific execution details"""
        response = requests.get(
            f"{self.base_url}/api/v1/executions/{execution_id}",
            headers=self.headers
        )
        return response.json()

    def list_workflows(self, active=None):
        """List all workflows"""
        params = {}
        if active is not None:
            params['active'] = active

        response = requests.get(
            f"{self.base_url}/api/v1/workflows",
            headers=self.headers,
            params=params
        )
        return response.json().get('data', [])
```

## Debugging Functions

### Analyze Execution Errors

```python
def analyze_execution_error(execution_id):
    """
    Deep analysis of a failed execution
    """
    client = N8nAPIClient()
    execution = client.get_execution(execution_id)

    if execution.get('status') != 'error':
        return {'status': 'not_error', 'execution': execution}

    error_info = execution.get('error', {})
    exec_data = execution.get('data', {})

    analysis = {
        'execution_id': execution_id,
        'workflow_id': execution.get('workflowId'),
        'status': execution.get('status'),
        'started_at': execution.get('startedAt'),
        'finished_at': execution.get('stoppedAt'),
        'failing_node': exec_data.get('lastNodeExecuted'),
        'error_message': error_info.get('message'),
        'error_stack': error_info.get('stack'),
        'node_data': exec_data.get('resultData', {}).get('runData', {})
    }

    # Categorize error
    analysis['error_category'] = categorize_n8n_error(error_info)

    return analysis
```

### Validate Node Configuration

```python
def validate_node_configuration(workflow_id, node_name=None):
    """
    Validate node configurations in a workflow
    """
    client = N8nAPIClient()
    workflow = client.get_workflow(workflow_id)

    nodes = workflow.get('nodes', [])
    validation_results = []

    for node in nodes:
        if node_name and node.get('name') != node_name:
            continue

        result = {
            'node_name': node.get('name'),
            'node_type': node.get('type'),
            'issues': [],
            'warnings': []
        }

        # Check required parameters
        params = node.get('parameters', {})
        node_type = node.get('type', '')

        # HTTP Request node validation
        if 'httpRequest' in node_type:
            if not params.get('url'):
                result['issues'].append('Missing URL parameter')
            if params.get('authentication') == 'genericCredentialType':
                if not node.get('credentials'):
                    result['issues'].append('Authentication selected but no credentials configured')

        # Code node validation
        if 'code' in node_type.lower():
            code = params.get('jsCode', '') or params.get('pythonCode', '')
            if not code.strip():
                result['issues'].append('Code node has empty code')

        # Check for credential configuration
        credentials = node.get('credentials')
        if not credentials and 'http' not in node_type.lower():
            result['warnings'].append('Node may require credentials')

        validation_results.append(result)

    return validation_results
```

### Identify Failing Nodes

```python
def identify_failing_nodes(workflow_id, limit=50):
    """
    Aggregate node failures across executions
    """
    from collections import defaultdict

    client = N8nAPIClient()
    executions = client.get_executions(workflow_id=workflow_id, limit=limit)

    error_executions = [e for e in executions if e.get('status') == 'error']

    node_failures = defaultdict(int)
    error_patterns = defaultdict(list)

    for exec in error_executions:
        exec_data = exec.get('data', {})
        failing_node = exec_data.get('lastNodeExecuted', 'Unknown')
        error_info = exec.get('error', {})
        error_msg = error_info.get('message', 'No error message')

        if failing_node != 'Unknown':
            node_failures[failing_node] += 1
            error_patterns[failing_node].append(error_msg)

    hotspots = sorted(node_failures.items(), key=lambda x: x[1], reverse=True)

    return {
        'hotspots': hotspots,
        'error_patterns': error_patterns,
        'total_errors': len(error_executions)
    }
```

### Track Execution Failures (SQL)

```sql
-- Prerequisites:
-- 1. n8n_execution_logs table must exist in quality.db
-- 2. See monitoring/schema/quality_db_schema.sql for table definition
-- 3. N8N execution logging must be enabled

-- Pattern: Track execution failures over time
SELECT
    workflow_id,
    COUNT(*) as failure_count,
    MIN(started_at) as first_failure,
    MAX(started_at) as last_failure,
    AVG(duration_ms) as avg_duration
FROM n8n_execution_logs
WHERE status = 'error'
    AND started_at > datetime('now', '-7 days')
GROUP BY workflow_id
HAVING failure_count > 3
ORDER BY failure_count DESC;
```

## Debugging Checklist

**1. Gather Context:**
- [ ] Query Context7 for n8n debugging documentation
- [ ] Get workflow structure: `client.get_workflow(workflow_id)`
- [ ] List recent executions: `client.get_executions(workflow_id, limit=10)`
- [ ] Check n8n availability: `curl https://n8n.localhost/health`

**2. Execution Analysis:**
- [ ] Get failed execution data: `client.get_execution(execution_id)`
- [ ] Identify failing node from execution data
- [ ] Check node output data for clues
- [ ] Review execution error message and stack trace

**3. Node Validation:**
- [ ] Extract node configuration from workflow
- [ ] Check for missing required parameters
- [ ] Verify credential configuration
- [ ] Query Context7 for node-specific debugging

**4. Workflow Validation:**
- [ ] Check workflow structure (nodes and connections)
- [ ] Validate node connections
- [ ] Check for expression syntax errors
- [ ] Query Context7 for workflow validation patterns

**5. Pattern Analysis:**
- [ ] Query quality.db for similar n8n issues
- [ ] Aggregate failures: `identify_failing_nodes()`
- [ ] Identify node hotspots

**6. Resolution:**
- [ ] Apply fix (update workflow via API or n8n UI)
- [ ] Test fix (trigger workflow manually or via webhook)
- [ ] Verify success: check execution status
- [ ] Log pattern to quality.db for future reference

## Error Categories

| Category | Symptoms | Debug Approach |
|----------|----------|----------------|
| Configuration | Missing fields, invalid params | `validate_node_configuration()` + Context7 |
| Execution | HTTP timeouts, rate limits | Check execution logs + Context7 |
| Expression | Invalid JS syntax, undefined vars | MCP `validate_workflow_expressions` |
| Connection | Loops, missing connections | MCP `validate_workflow_connections` |
| Credential | Expired tokens, invalid keys | Context7 for auth patterns + check credentials |

## Output Format

```
🔄 N8N Workflow Debug Report

📋 Workflow: [Workflow Name] (ID: [workflow_id])
🔴 Status: Failed
⏱️ Execution: [execution_id]
📍 Failing Node: [Node Name] ([node_type])

🔬 Error Analysis:
├─ Error Message: [error.message]
├─ Error Category: [Configuration/Execution/Expression/Connection/Auth]
└─ Stack Trace: [error.stack]

🎯 Root Cause:
[Detailed explanation based on Context7 + MCP analysis]

🛠️ Resolution:
[Step-by-step fix based on validation + Context7 guidance]

📊 Pattern Match:
[If similar pattern exists in quality.db]

✅ Verification:
[How to test the fix]
```

## Integration with Quality DB

```python
def create_n8n_debug_pattern(workflow_id, error, resolution):
    """Store n8n-specific debug patterns"""
    import hashlib
    import json
    import sqlite3

    client = N8nAPIClient()
    workflow = client.get_workflow(workflow_id)
    workflow_name = workflow.get('name', 'Unknown')

    pattern_id = hashlib.sha256(
        f"n8n:{workflow_id}:{error.node}:{error.signature}".encode()
    ).hexdigest()[:16]

    context_fingerprint = json.dumps({
        'platform': 'n8n',
        'workflow_id': workflow_id,
        'workflow_name': workflow_name,
        'node_type': error.node_type,
        'error_category': categorize_n8n_error(error)
    })

    db = sqlite3.connect('{{CATALYST_ROOT}}/monitoring/quality.db')
    db.execute("""
        INSERT INTO debug_patterns (
            pattern_id, error_signature, context_fingerprint,
            root_cause, resolution, mode
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        pattern_id,
        f"n8n:{error.node_type}:{error.message}",
        context_fingerprint,
        error.root_cause,
        resolution,
        'n8n'
    ))
    db.commit()
```
