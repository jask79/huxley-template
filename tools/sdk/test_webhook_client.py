#!/usr/bin/env python3
"""
Webhook Server Test Client

Demonstrates how to interact with the SDK webhook server.
Can be used for testing and as integration examples.

Usage:
    # Start webhook server first in another terminal:
    ./webhook_server.py

    # Then run this test client:
    ./test_webhook_client.py
"""

import sys
import requests
import json
from typing import Dict, Any

# Server configuration
SERVER_URL = "http://127.0.0.1:5000"
API_KEY = "test-key-12345"  # Match the key set in webhook_server.py

def test_health_check():
    """Test health endpoint (no auth required)"""
    print("=== Testing Health Check ===")
    try:
        response = requests.get(f"{SERVER_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_observe_webhook():
    """Test webhook observation logging"""
    print("\n=== Testing Webhook Observe ===")
    try:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "workflow": "test_workflow",
            "observation": "Webhook server integration test",
            "metadata": {
                "test": True,
                "source": "test_client"
            }
        }

        response = requests.post(
            f"{SERVER_URL}/webhook/observe",
            headers=headers,
            json=data
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 201
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_learn_webhook():
    """Test workflow learning endpoint"""
    print("\n=== Testing Webhook Learn ===")
    try:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "workflow": "test_workflow",
            "success": True,
            "metrics": {
                "duration_ms": 1234,
                "test": True
            },
            "notes": "Integration test successful"
        }

        response = requests.post(
            f"{SERVER_URL}/webhook/learn",
            headers=headers,
            json=data
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 201
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_trigger_webhook():
    """Test workflow trigger endpoint"""
    print("\n=== Testing Webhook Trigger ===")
    try:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "workflow": "test_workflow",
            "parameters": {
                "dry_run": True,
                "verbose": True
            }
        }

        response = requests.post(
            f"{SERVER_URL}/webhook/trigger",
            headers=headers,
            json=data
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 202
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_workflow_status():
    """Test workflow status query"""
    print("\n=== Testing Workflow Status ===")
    try:
        headers = {"X-API-Key": API_KEY}

        response = requests.get(
            f"{SERVER_URL}/workflow/test_workflow/status",
            headers=headers
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Workflow: {data['workflow']}")
            print(f"Metrics: {json.dumps(data['metrics'], indent=2)}")
            print(f"Recent History: {len(data['recent_history'])} observations")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_list_workflows():
    """Test workflow list endpoint"""
    print("\n=== Testing Workflow List ===")
    try:
        headers = {"X-API-Key": API_KEY}

        response = requests.get(
            f"{SERVER_URL}/workflows",
            headers=headers
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Total Workflows: {data['count']}")
            print(f"Workflows: {data['workflows']}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_authentication():
    """Test API key authentication"""
    print("\n=== Testing Authentication ===")

    # Test missing API key
    print("Testing missing API key...")
    try:
        response = requests.post(
            f"{SERVER_URL}/webhook/observe",
            json={"workflow": "test", "observation": "test"}
        )
        print(f"Status (expected 401): {response.status_code}")
        missing_key_pass = response.status_code == 401
    except Exception as e:
        print(f"Error: {e}")
        missing_key_pass = False

    # Test invalid API key
    print("\nTesting invalid API key...")
    try:
        response = requests.post(
            f"{SERVER_URL}/webhook/observe",
            headers={"X-API-Key": "invalid-key"},
            json={"workflow": "test", "observation": "test"}
        )
        print(f"Status (expected 403): {response.status_code}")
        invalid_key_pass = response.status_code == 403
    except Exception as e:
        print(f"Error: {e}")
        invalid_key_pass = False

    return missing_key_pass and invalid_key_pass


def main():
    """Run all tests"""
    print("=" * 70)
    print("SDK Webhook Server Test Client")
    print("=" * 70)
    print(f"Server URL: {SERVER_URL}")
    print(f"API Key: {API_KEY}")
    print()
    print("Make sure webhook_server.py is running!")
    print("Start with: export SDK_WEBHOOK_API_KEY=test-key-12345 && ./webhook_server.py")
    print("=" * 70)

    # Run tests
    results = {
        "Health Check": test_health_check(),
        "Webhook Observe": test_observe_webhook(),
        "Webhook Learn": test_learn_webhook(),
        "Webhook Trigger": test_trigger_webhook(),
        "Workflow Status": test_workflow_status(),
        "List Workflows": test_list_workflows(),
        "Authentication": test_authentication()
    }

    # Summary
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    for test, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test}")

    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
