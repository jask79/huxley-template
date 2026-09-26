#!/usr/bin/env python3
"""
SDK Webhook Server - Event Ingestion API

Flask-based webhook server for receiving SDK workflow events from external sources.
Provides authenticated endpoints for logging observations, triggering workflows,
and querying workflow status.

Features:
- API key authentication for security
- Webhook endpoints for event ingestion
- Integration with SDKMemoryBridge
- Workflow trigger capabilities
- Status query endpoints
- Request logging and error handling

Usage:
    # Start server (development)
    ./webhook_server.py

    # Start server (production with gunicorn)
    gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app

    # Set API key via environment
    export SDK_WEBHOOK_API_KEY="your-secret-key-here"

    # Send webhook event
    curl -X POST http://localhost:5000/webhook/observe \
      -H "X-API-Key: your-secret-key-here" \
      -H "Content-Type: application/json" \
      -d '{"workflow": "daily_audit", "observation": "triggered by external system", "metadata": {"source": "github"}}'
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps

# Flask imports
try:
    from flask import Flask, request, jsonify, abort
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("⚠️ Flask not available. Install with: pip install flask", file=sys.stderr)
    sys.exit(1)

# Add SDK tools to path
SDK_DIR = Path(__file__).parent
sys.path.insert(0, str(SDK_DIR))

from sdk_memory_bridge import SDKMemoryBridge

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Get API key from environment (generate random default if not set)
API_KEY = os.getenv("SDK_WEBHOOK_API_KEY")
if not API_KEY:
    import secrets
    API_KEY = secrets.token_urlsafe(32)
    print("⚠️ SDK_WEBHOOK_API_KEY not set. Generated a temporary in-memory key (not shown).", file=sys.stderr)
    print('   Set a permanent key with: export SDK_WEBHOOK_API_KEY="<your-key>"', file=sys.stderr)

# Initialize memory bridge
memory_bridge = SDKMemoryBridge(workflow_id="webhook_server")


def require_api_key(f):
    """
    Decorator for API key authentication.

    Expects X-API-Key header with valid API key.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from header
        provided_key = request.headers.get('X-API-Key')

        if not provided_key:
            abort(401, description="Missing X-API-Key header")

        if provided_key != API_KEY:
            abort(403, description="Invalid API key")

        return f(*args, **kwargs)

    return decorated_function


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint (no auth required).

    Returns:
        JSON with server status
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })


@app.route('/webhook/observe', methods=['POST'])
@require_api_key
def webhook_observe():
    """
    Webhook endpoint for logging observations.

    Request body:
        {
            "workflow": "workflow_name",
            "observation": "observation text",
            "metadata": {optional metadata dict}
        }

    Returns:
        JSON with observation ID
    """
    # Validate request
    if not request.is_json:
        abort(400, description="Content-Type must be application/json")

    data = request.get_json()

    # Validate required fields
    if 'workflow' not in data:
        abort(400, description="Missing required field: workflow")
    if 'observation' not in data:
        abort(400, description="Missing required field: observation")

    workflow = data['workflow']
    observation = data['observation']
    metadata = data.get('metadata', {})

    # Add webhook metadata
    metadata['source'] = 'webhook'
    metadata['ip'] = request.remote_addr
    metadata['user_agent'] = request.headers.get('User-Agent', 'unknown')

    # Log observation
    try:
        obs_id = memory_bridge.observe_workflow(workflow, observation, metadata)

        return jsonify({
            "status": "success",
            "observation_id": obs_id,
            "workflow": workflow,
            "timestamp": datetime.now().isoformat()
        }), 201

    except Exception as e:
        app.logger.error(f"Failed to log observation: {e}")
        abort(500, description=f"Failed to log observation: {str(e)}")


@app.route('/webhook/learn', methods=['POST'])
@require_api_key
def webhook_learn():
    """
    Webhook endpoint for learning from workflow outcomes.

    Request body:
        {
            "workflow": "workflow_name",
            "success": true/false,
            "metrics": {optional metrics dict},
            "notes": "optional notes"
        }

    Returns:
        JSON with pattern ID
    """
    # Validate request
    if not request.is_json:
        abort(400, description="Content-Type must be application/json")

    data = request.get_json()

    # Validate required fields
    if 'workflow' not in data:
        abort(400, description="Missing required field: workflow")
    if 'success' not in data:
        abort(400, description="Missing required field: success")

    workflow = data['workflow']
    success = bool(data['success'])
    metrics = data.get('metrics', {})
    notes = data.get('notes')

    # Learn from workflow
    try:
        pattern_id = memory_bridge.learn_from_workflow(
            workflow,
            success=success,
            metrics=metrics,
            notes=notes
        )

        return jsonify({
            "status": "success",
            "pattern_id": pattern_id,
            "workflow": workflow,
            "timestamp": datetime.now().isoformat()
        }), 201

    except Exception as e:
        app.logger.error(f"Failed to learn from workflow: {e}")
        abort(500, description=f"Failed to learn from workflow: {str(e)}")


@app.route('/webhook/trigger', methods=['POST'])
@require_api_key
def webhook_trigger():
    """
    Webhook endpoint for triggering workflows.

    Request body:
        {
            "workflow": "workflow_name",
            "parameters": {optional parameters dict}
        }

    Returns:
        JSON with trigger acknowledgment

    Note:
        This endpoint logs the trigger request but does not execute the workflow.
        Actual workflow execution should be handled by external orchestration (cron, n8n, etc.)
    """
    # Validate request
    if not request.is_json:
        abort(400, description="Content-Type must be application/json")

    data = request.get_json()

    # Validate required fields
    if 'workflow' not in data:
        abort(400, description="Missing required field: workflow")

    workflow = data['workflow']
    parameters = data.get('parameters', {})

    # Log trigger request
    try:
        obs_id = memory_bridge.observe_workflow(
            workflow,
            f"Workflow trigger requested via webhook",
            {
                "source": "webhook_trigger",
                "parameters": parameters,
                "ip": request.remote_addr
            }
        )

        return jsonify({
            "status": "triggered",
            "observation_id": obs_id,
            "workflow": workflow,
            "parameters": parameters,
            "timestamp": datetime.now().isoformat(),
            "note": "Trigger logged. Actual execution handled by external orchestration."
        }), 202

    except Exception as e:
        app.logger.error(f"Failed to log trigger: {e}")
        abort(500, description=f"Failed to log trigger: {str(e)}")


@app.route('/workflow/<workflow_name>/status', methods=['GET'])
@require_api_key
def workflow_status(workflow_name: str):
    """
    Get workflow status and metrics.

    Args:
        workflow_name: Name of workflow

    Returns:
        JSON with workflow metrics and recent history
    """
    try:
        metrics = memory_bridge.get_workflow_metrics(workflow_name)
        history = memory_bridge.get_workflow_history(workflow_name, days=1)

        return jsonify({
            "workflow": workflow_name,
            "metrics": metrics,
            "recent_history": history[-5:],  # Last 5 observations
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        app.logger.error(f"Failed to get workflow status: {e}")
        abort(500, description=f"Failed to get workflow status: {str(e)}")


@app.route('/workflows', methods=['GET'])
@require_api_key
def list_workflows():
    """
    List all workflows with observations.

    Returns:
        JSON with list of workflow names
    """
    try:
        workflows = memory_bridge.list_workflows()

        return jsonify({
            "workflows": workflows,
            "count": len(workflows),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        app.logger.error(f"Failed to list workflows: {e}")
        abort(500, description=f"Failed to list workflows: {str(e)}")


@app.errorhandler(400)
def bad_request(error):
    """Handle 400 errors"""
    return jsonify({
        "error": "bad_request",
        "message": str(error.description)
    }), 400


@app.errorhandler(401)
def unauthorized(error):
    """Handle 401 errors"""
    return jsonify({
        "error": "unauthorized",
        "message": str(error.description)
    }), 401


@app.errorhandler(403)
def forbidden(error):
    """Handle 403 errors"""
    return jsonify({
        "error": "forbidden",
        "message": str(error.description)
    }), 403


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "error": "not_found",
        "message": "Endpoint not found"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        "error": "internal_server_error",
        "message": str(error.description) if hasattr(error, 'description') else "Internal server error"
    }), 500


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="SDK Webhook Server")
    parser.add_argument("--host", default="127.0.0.1",
                       help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000,
                       help="Port to bind to (default: 5000)")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug mode")

    args = parser.parse_args()

    print("=" * 70)
    print("SDK Webhook Server Starting")
    print("=" * 70)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print("API Key: (set; not shown)")
    print()
    print("Available Endpoints:")
    print("  GET  /health                       - Health check (no auth)")
    print("  POST /webhook/observe              - Log observation")
    print("  POST /webhook/learn                - Learn from workflow outcome")
    print("  POST /webhook/trigger              - Trigger workflow")
    print("  GET  /workflow/<name>/status       - Get workflow status")
    print("  GET  /workflows                    - List all workflows")
    print()
    print("Authentication: Include header 'X-API-Key: <key>'")
    print("=" * 70)

    # Start server
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == "__main__":
    main()
