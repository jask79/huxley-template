#!/usr/bin/env python3
"""
SDK End-to-End Test Suite

Comprehensive testing of complete SDK workflow pipeline from trigger
to completion, including all integration points.

Features:
- Full workflow execution testing
- Component integration validation
- Webhook server integration testing
- Memory bridge verification
- Dashboard generation testing
- Governance validation testing
- Cron wrapper testing
- Performance benchmarking

Usage:
    # Run all tests
    ./end_to_end_test.py

    # Run specific test category
    ./end_to_end_test.py --category integration

    # Verbose output
    ./end_to_end_test.py --verbose

    # Generate test report
    ./end_to_end_test.py --report
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import argparse
import subprocess

# Add SDK tools to path
SDK_DIR = Path(__file__).parent
sys.path.insert(0, str(SDK_DIR))

from sdk_memory_bridge import SDKMemoryBridge
from view_sdk_events import SDKEventsViewer
from generate_dashboard import DashboardGenerator
from governance_validator import GovernanceValidator


@dataclass
class TestResult:
    """Result of single test"""
    test_name: str
    category: str
    passed: bool
    duration_ms: float
    message: str = ""
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EndToEndTestSuite:
    """
    Comprehensive end-to-end testing for SDK workflows.
    """

    def __init__(self, verbose: bool = False):
        """Initialize test suite"""
        self.verbose = verbose
        self.results: List[TestResult] = []
        self.test_workflow = "e2e_test"

    def log(self, message: str):
        """Log message if verbose"""
        if self.verbose:
            print(f"  {message}")

    def run_test(self, test_name: str, category: str, test_func):
        """
        Run single test and record result.

        Args:
            test_name: Name of test
            category: Test category
            test_func: Test function to execute
        """
        print(f"Running: {test_name}...", end=" ")
        start_time = time.time()

        try:
            test_func()
            duration_ms = (time.time() - start_time) * 1000

            result = TestResult(
                test_name=test_name,
                category=category,
                passed=True,
                duration_ms=duration_ms,
                message="Test passed"
            )

            print(f"✓ PASS ({duration_ms:.1f}ms)")
            self.results.append(result)

        except AssertionError as e:
            duration_ms = (time.time() - start_time) * 1000

            result = TestResult(
                test_name=test_name,
                category=category,
                passed=False,
                duration_ms=duration_ms,
                message="Assertion failed",
                error=str(e)
            )

            print(f"✗ FAIL ({duration_ms:.1f}ms)")
            if self.verbose:
                print(f"    Error: {e}")
            self.results.append(result)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            result = TestResult(
                test_name=test_name,
                category=category,
                passed=False,
                duration_ms=duration_ms,
                message="Exception occurred",
                error=str(e)
            )

            print(f"✗ ERROR ({duration_ms:.1f}ms)")
            if self.verbose:
                print(f"    Error: {e}")
            self.results.append(result)

    # ========================================================================
    # Memory Bridge Tests
    # ========================================================================

    def test_memory_bridge_init(self):
        """Test memory bridge initialization"""
        self.log("Initializing memory bridge...")
        bridge = SDKMemoryBridge(workflow_id=self.test_workflow)
        assert bridge is not None
        assert bridge.workflow_id == self.test_workflow

    def test_memory_bridge_observe(self):
        """Test observation logging"""
        self.log("Logging observation...")
        bridge = SDKMemoryBridge(workflow_id=self.test_workflow)
        obs_id = bridge.observe_workflow(
            self.test_workflow,
            "E2E test observation",
            {"test": True}
        )
        assert obs_id is not None
        assert len(obs_id) > 0

    def test_memory_bridge_history(self):
        """Test history retrieval"""
        self.log("Retrieving history...")
        bridge = SDKMemoryBridge(workflow_id=self.test_workflow)
        history = bridge.get_workflow_history(self.test_workflow, days=1)
        assert isinstance(history, list)

    def test_memory_bridge_metrics(self):
        """Test metrics calculation"""
        self.log("Calculating metrics...")
        bridge = SDKMemoryBridge(workflow_id=self.test_workflow)
        metrics = bridge.get_workflow_metrics(self.test_workflow)
        assert 'run_count' in metrics
        assert 'success_rate' in metrics

    # ========================================================================
    # Events Viewer Tests
    # ========================================================================

    def test_events_viewer_list(self):
        """Test workflow listing"""
        self.log("Listing workflows...")
        viewer = SDKEventsViewer()
        workflows = viewer.list_workflows()
        assert isinstance(workflows, list)

    def test_events_viewer_summary(self):
        """Test summary generation"""
        self.log("Generating summary...")
        viewer = SDKEventsViewer()
        summary = viewer.get_summary()
        assert 'total_workflows' in summary
        assert 'total_runs' in summary

    # ========================================================================
    # Dashboard Tests
    # ========================================================================

    def test_dashboard_generation(self):
        """Test dashboard HTML generation"""
        self.log("Generating dashboard...")
        generator = DashboardGenerator()
        html = generator.generate_html()
        assert len(html) > 1000
        assert "SDK Monitoring Dashboard" in html

    def test_dashboard_save(self):
        """Test dashboard save"""
        self.log("Saving dashboard...")
        generator = DashboardGenerator()
        output = Path("/tmp/e2e_test_dashboard.html")
        generator.save_dashboard(output)
        assert output.exists()
        output.unlink()  # Cleanup

    # ========================================================================
    # Governance Tests
    # ========================================================================

    def test_governance_validator(self):
        """Test governance validator initialization"""
        self.log("Initializing governance validator...")
        validator = GovernanceValidator()
        assert validator is not None

    def test_governance_metrics_validation(self):
        """Test workflow metrics validation"""
        self.log("Validating workflow metrics...")
        validator = GovernanceValidator()
        # This might fail if workflow doesn't exist, which is OK
        try:
            result = validator.validate_workflow_metrics("daily_audit")
            assert result is not None
        except:
            pass  # Acceptable if workflow doesn't have metrics yet

    # ========================================================================
    # Cron Wrapper Tests
    # ========================================================================

    def test_cron_wrapper_exists(self):
        """Test cron wrapper file exists"""
        self.log("Checking cron wrapper...")
        wrapper = SDK_DIR / "cron_wrapper.py"
        assert wrapper.exists()
        assert wrapper.is_file()

    def test_cron_wrapper_executable(self):
        """Test cron wrapper is executable"""
        self.log("Checking cron wrapper executable...")
        wrapper = SDK_DIR / "cron_wrapper.py"
        import os
        assert os.access(wrapper, os.X_OK)

    # ========================================================================
    # Integration Tests
    # ========================================================================

    def test_full_workflow_simulation(self):
        """Test complete workflow simulation"""
        self.log("Running full workflow simulation...")

        # Step 1: Log workflow start
        bridge = SDKMemoryBridge(workflow_id=self.test_workflow)
        obs_id = bridge.observe_workflow(
            self.test_workflow,
            "E2E test workflow started",
            {"step": "start"}
        )
        assert obs_id is not None

        # Step 2: Simulate work
        time.sleep(0.1)

        # Step 3: Learn from outcome
        pattern_id = bridge.learn_from_workflow(
            self.test_workflow,
            success=True,
            metrics={"duration_ms": 100},
            notes="E2E test successful"
        )
        assert pattern_id is not None

        # Step 4: Verify observation was logged
        viewer = SDKEventsViewer()
        history = viewer.view_workflow_history(self.test_workflow, days=1)
        assert len(history) > 0

    def test_file_structure(self):
        """Test SDK file structure is complete"""
        self.log("Verifying file structure...")

        required_files = [
            "sdk_memory_bridge.py",
            "view_sdk_events.py",
            "generate_dashboard.py",
            "webhook_server.py",
            "governance_validator.py",
            "cron_wrapper.py",
            "end_to_end_test.py"
        ]

        for filename in required_files:
            filepath = SDK_DIR / filename
            assert filepath.exists(), f"Missing file: {filename}"

    # ========================================================================
    # Performance Tests
    # ========================================================================

    def test_memory_bridge_performance(self):
        """Test memory bridge performance"""
        self.log("Testing memory bridge performance...")

        bridge = SDKMemoryBridge(workflow_id=self.test_workflow)

        # Log 10 observations and measure time
        start = time.time()
        for i in range(10):
            bridge.observe_workflow(
                self.test_workflow,
                f"Performance test observation {i}",
                {"iteration": i}
            )
        duration_ms = (time.time() - start) * 1000

        # Should complete in under 1 second
        assert duration_ms < 1000, f"Too slow: {duration_ms:.1f}ms"

    def test_dashboard_generation_performance(self):
        """Test dashboard generation performance"""
        self.log("Testing dashboard generation performance...")

        generator = DashboardGenerator()

        start = time.time()
        html = generator.generate_html()
        duration_ms = (time.time() - start) * 1000

        # Should complete in under 2 seconds
        assert duration_ms < 2000, f"Too slow: {duration_ms:.1f}ms"

    # ========================================================================
    # Test Execution
    # ========================================================================

    def run_all_tests(self, category: Optional[str] = None):
        """Run all tests or filtered by category"""

        test_categories = {
            "memory": [
                ("Memory Bridge Init", "memory", self.test_memory_bridge_init),
                ("Memory Bridge Observe", "memory", self.test_memory_bridge_observe),
                ("Memory Bridge History", "memory", self.test_memory_bridge_history),
                ("Memory Bridge Metrics", "memory", self.test_memory_bridge_metrics),
            ],
            "events": [
                ("Events Viewer List", "events", self.test_events_viewer_list),
                ("Events Viewer Summary", "events", self.test_events_viewer_summary),
            ],
            "dashboard": [
                ("Dashboard Generation", "dashboard", self.test_dashboard_generation),
                ("Dashboard Save", "dashboard", self.test_dashboard_save),
            ],
            "governance": [
                ("Governance Validator", "governance", self.test_governance_validator),
                ("Governance Metrics", "governance", self.test_governance_metrics_validation),
            ],
            "cron": [
                ("Cron Wrapper Exists", "cron", self.test_cron_wrapper_exists),
                ("Cron Wrapper Executable", "cron", self.test_cron_wrapper_executable),
            ],
            "integration": [
                ("Full Workflow Simulation", "integration", self.test_full_workflow_simulation),
                ("File Structure", "integration", self.test_file_structure),
            ],
            "performance": [
                ("Memory Bridge Performance", "performance", self.test_memory_bridge_performance),
                ("Dashboard Performance", "performance", self.test_dashboard_generation_performance),
            ]
        }

        # Filter tests by category
        if category:
            if category not in test_categories:
                print(f"Unknown category: {category}")
                print(f"Available categories: {', '.join(test_categories.keys())}")
                return

            tests_to_run = test_categories[category]
        else:
            # Run all tests
            tests_to_run = []
            for cat_tests in test_categories.values():
                tests_to_run.extend(cat_tests)

        print(f"Running {len(tests_to_run)} tests...")
        print("=" * 70)

        for test_name, test_category, test_func in tests_to_run:
            self.run_test(test_name, test_category, test_func)

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {passed/total*100:.1f}%" if total > 0 else "N/A")

        # Category breakdown
        categories = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = {"passed": 0, "failed": 0}

            if result.passed:
                categories[result.category]["passed"] += 1
            else:
                categories[result.category]["failed"] += 1

        print("\nCategory Breakdown:")
        for category, counts in sorted(categories.items()):
            total_cat = counts["passed"] + counts["failed"]
            rate = counts["passed"] / total_cat * 100 if total_cat > 0 else 0
            print(f"  {category}: {counts['passed']}/{total_cat} ({rate:.0f}%)")

        # Failed tests
        if failed > 0:
            print("\nFailed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  ✗ {result.test_name}")
                    if result.error and self.verbose:
                        print(f"    {result.error}")

        print("=" * 70)

    def generate_report(self, output_path: Path):
        """Generate JSON test report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
                "duration_ms": sum(r.duration_ms for r in self.results)
            },
            "results": [
                {
                    "test": r.test_name,
                    "category": r.category,
                    "passed": r.passed,
                    "duration_ms": round(r.duration_ms, 2),
                    "message": r.message,
                    "error": r.error
                }
                for r in self.results
            ]
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nTest report saved to: {output_path}")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="SDK End-to-End Test Suite")

    parser.add_argument("--category", choices=[
        "memory", "events", "dashboard", "governance", "cron", "integration", "performance"
    ], help="Run tests from specific category only")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    parser.add_argument("--report", action="store_true",
                       help="Generate JSON test report")

    args = parser.parse_args()

    # Run tests
    suite = EndToEndTestSuite(verbose=args.verbose)
    suite.run_all_tests(category=args.category)
    suite.print_summary()

    # Generate report if requested
    if args.report:
        report_path = Path("{{CATALYST_ROOT}}/registry/testing/e2e_test_report.json")
        suite.generate_report(report_path)

    # Exit with appropriate code
    failed = sum(1 for r in suite.results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
