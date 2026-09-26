#!/usr/bin/env python3
"""
Week 3 Integration Validation

Validates all Week 3 deliverables are working together:
- In-process MCP integration (sdk_memory_bridge.py)
- Huxley-memory bridge with workflow observations
- Monitoring dashboard (generate_dashboard.py)
- Events viewer (view_sdk_events.py)
- Webhook server (webhook_server.py)

Usage:
    ./validate_week3.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add SDK tools to path
SDK_DIR = Path(__file__).parent
sys.path.insert(0, str(SDK_DIR))

from sdk_memory_bridge import SDKMemoryBridge
from view_sdk_events import SDKEventsViewer
from generate_dashboard import DashboardGenerator


class Week3Validator:
    """
    Validates Week 3 SDK implementation.
    """

    def __init__(self):
        """Initialize validator"""
        self.results = []
        self.test_workflow = "week3_validation"

    def log_result(self, test: str, passed: bool, message: str = ""):
        """Log test result"""
        self.results.append({
            "test": test,
            "passed": passed,
            "message": message
        })

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test}")
        if message:
            print(f"  {message}")

    def test_memory_bridge(self) -> bool:
        """Test SDK memory bridge functionality"""
        print("\n=== Testing SDK Memory Bridge ===")

        try:
            # Initialize bridge
            bridge = SDKMemoryBridge(workflow_id=self.test_workflow)

            # Test observation logging
            obs_id = bridge.observe_workflow(
                self.test_workflow,
                "Week 3 validation test observation",
                {"test": True, "timestamp": datetime.now().isoformat()}
            )

            self.log_result(
                "Memory Bridge - Observation Logging",
                bool(obs_id),
                f"Observation ID: {obs_id}"
            )

            # Test workflow entity creation
            bridge.create_workflow_entity(
                self.test_workflow,
                "validation",
                {"created": datetime.now().isoformat()}
            )

            self.log_result(
                "Memory Bridge - Entity Creation",
                True,
                f"Entity created for {self.test_workflow}"
            )

            # Test learning from workflow
            pattern_id = bridge.learn_from_workflow(
                self.test_workflow,
                success=True,
                metrics={"duration_ms": 123, "test": True},
                notes="Week 3 validation successful"
            )

            self.log_result(
                "Memory Bridge - Pattern Learning",
                bool(pattern_id),
                f"Pattern ID: {pattern_id}"
            )

            # Test history retrieval
            history = bridge.get_workflow_history(self.test_workflow, days=1)

            self.log_result(
                "Memory Bridge - History Retrieval",
                len(history) > 0,
                f"Found {len(history)} observations"
            )

            # Test metrics calculation
            metrics = bridge.get_workflow_metrics(self.test_workflow)

            self.log_result(
                "Memory Bridge - Metrics Calculation",
                metrics['run_count'] > 0,
                f"Run count: {metrics['run_count']}, Success rate: {metrics['success_rate']}%"
            )

            return all([r['passed'] for r in self.results[-5:]])

        except Exception as e:
            self.log_result("Memory Bridge - Integration", False, f"Error: {e}")
            return False

    def test_events_viewer(self) -> bool:
        """Test SDK events viewer"""
        print("\n=== Testing SDK Events Viewer ===")

        try:
            viewer = SDKEventsViewer()

            # Test workflow listing
            workflows = viewer.list_workflows()

            self.log_result(
                "Events Viewer - List Workflows",
                self.test_workflow in workflows,
                f"Found {len(workflows)} workflows including {self.test_workflow}"
            )

            # Test workflow history
            history = viewer.view_workflow_history(self.test_workflow, days=1)

            self.log_result(
                "Events Viewer - View History",
                len(history) > 0,
                f"Retrieved {len(history)} historical observations"
            )

            # Test workflow metrics
            metrics = viewer.view_workflow_metrics(self.test_workflow)

            self.log_result(
                "Events Viewer - View Metrics",
                'run_count' in metrics and 'success_rate' in metrics,
                f"Metrics: {metrics['run_count']} runs, {metrics['success_rate']}% success"
            )

            # Test search functionality
            search_results = viewer.search_observations("week3", days=1)

            self.log_result(
                "Events Viewer - Search Observations",
                len(search_results) > 0,
                f"Found {len(search_results)} matching observations"
            )

            # Test summary generation
            summary = viewer.get_summary()

            self.log_result(
                "Events Viewer - Generate Summary",
                summary['total_workflows'] > 0,
                f"Summary: {summary['total_workflows']} workflows, {summary['total_runs']} runs"
            )

            return all([r['passed'] for r in self.results[-5:]])

        except Exception as e:
            self.log_result("Events Viewer - Integration", False, f"Error: {e}")
            return False

    def test_dashboard_generator(self) -> bool:
        """Test dashboard generator"""
        print("\n=== Testing Dashboard Generator ===")

        try:
            generator = DashboardGenerator()

            # Test HTML generation
            html = generator.generate_html(refresh_seconds=0)

            self.log_result(
                "Dashboard Generator - HTML Generation",
                len(html) > 1000 and "SDK Monitoring Dashboard" in html,
                f"Generated {len(html)} bytes of HTML"
            )

            # Test dashboard save
            test_output = Path("/tmp/week3_validation_dashboard.html")
            generator.save_dashboard(test_output, refresh_seconds=0)

            self.log_result(
                "Dashboard Generator - Save Dashboard",
                test_output.exists(),
                f"Dashboard saved to {test_output}"
            )

            # Verify dashboard content
            with open(test_output, 'r') as f:
                content = f.read()
                has_workflows = self.test_workflow in content or "Total Workflows" in content
                has_styling = "background: #0a0a0a" in content

            self.log_result(
                "Dashboard Generator - Content Validation",
                has_workflows and has_styling,
                "Dashboard contains workflow data and dark theme styling"
            )

            return all([r['passed'] for r in self.results[-3:]])

        except Exception as e:
            self.log_result("Dashboard Generator - Integration", False, f"Error: {e}")
            return False

    def test_webhook_server(self) -> bool:
        """Test webhook server availability"""
        print("\n=== Testing Webhook Server ===")

        try:
            # Import Flask app
            from webhook_server import app, require_api_key

            self.log_result(
                "Webhook Server - Flask App Import",
                app is not None,
                "Flask app loaded successfully"
            )

            # Check authentication decorator
            self.log_result(
                "Webhook Server - Auth Decorator",
                require_api_key is not None,
                "API key authentication decorator available"
            )

            # Check endpoints are registered
            endpoints = [rule.rule for rule in app.url_map.iter_rules()]
            expected_endpoints = [
                '/health',
                '/webhook/observe',
                '/webhook/learn',
                '/webhook/trigger',
                '/workflow/<workflow_name>/status',
                '/workflows'
            ]

            all_endpoints_exist = all(
                any(expected in endpoint for endpoint in endpoints)
                for expected in ['/health', '/webhook/observe', '/workflow', '/workflows']
            )

            self.log_result(
                "Webhook Server - Endpoint Registration",
                all_endpoints_exist,
                f"Found {len(endpoints)} registered endpoints"
            )

            return all([r['passed'] for r in self.results[-3:]])

        except Exception as e:
            self.log_result("Webhook Server - Integration", False, f"Error: {e}")
            return False

    def test_file_existence(self) -> bool:
        """Test that all required files exist"""
        print("\n=== Testing File Existence ===")

        required_files = {
            "sdk_memory_bridge.py": "In-process MCP bridge",
            "view_sdk_events.py": "Events viewer CLI",
            "generate_dashboard.py": "Dashboard generator",
            "webhook_server.py": "Webhook server",
            "test_webhook_client.py": "Webhook test client",
            "WEBHOOK_SERVER.md": "Webhook server documentation",
            "requirements.txt": "Python dependencies"
        }

        for filename, description in required_files.items():
            file_path = SDK_DIR / filename
            exists = file_path.exists()

            self.log_result(
                f"File Existence - {filename}",
                exists,
                description
            )

        return all([r['passed'] for r in self.results[-len(required_files):]])

    def run_validation(self) -> int:
        """Run complete validation suite"""
        print("=" * 70)
        print("Week 3 Implementation Validation")
        print("=" * 70)
        print(f"SDK Directory: {SDK_DIR}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Run all tests
        file_check = self.test_file_existence()
        memory_bridge = self.test_memory_bridge()
        events_viewer = self.test_events_viewer()
        dashboard = self.test_dashboard_generator()
        webhook = self.test_webhook_server()

        # Summary
        print("\n" + "=" * 70)
        print("Validation Summary")
        print("=" * 70)

        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['passed'])

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {passed_tests / total_tests * 100:.1f}%")

        print("\nComponent Status:")
        print(f"  {'✓' if file_check else '✗'} File Structure")
        print(f"  {'✓' if memory_bridge else '✗'} SDK Memory Bridge")
        print(f"  {'✓' if events_viewer else '✗'} Events Viewer")
        print(f"  {'✓' if dashboard else '✗'} Dashboard Generator")
        print(f"  {'✓' if webhook else '✗'} Webhook Server")

        print("\n" + "=" * 70)

        if passed_tests == total_tests:
            print("✓ Week 3 Implementation: VALIDATED")
            print("  All components working correctly")
            print("\n  Ready for Week 4:")
            print("    - Cron wrappers")
            print("    - n8n integration")
            print("    - Governance validation")
            print("    - Production deployment")
        else:
            print("✗ Week 3 Implementation: VALIDATION FAILED")
            print(f"  {total_tests - passed_tests} tests failed")
            print("\n  Failed tests:")
            for r in self.results:
                if not r['passed']:
                    print(f"    - {r['test']}")
                    if r['message']:
                        print(f"      {r['message']}")

        print("=" * 70)

        return 0 if passed_tests == total_tests else 1


def main():
    """CLI entry point"""
    validator = Week3Validator()
    return validator.run_validation()


if __name__ == "__main__":
    sys.exit(main())
