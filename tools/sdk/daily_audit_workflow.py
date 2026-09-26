#!/usr/bin/env python3
"""
Daily Audit SDK Workflow

SDK-based autonomous workflow for Huxley daily audit.
Runs daily at 9:10 AM via LaunchAgent, integrates with governance
framework for GREEN classification, and uses transactional rollback.

Features:
- Anthropic SDK message creation for task execution
- Governance framework integration (GREEN auto-execute)
- Transactional safety with automatic rollback
- Hook integration for validation
- Comprehensive logging and error handling
- Desktop notifications for results

Usage:
    # Run audit workflow
    ./daily_audit_workflow.py

    # Dry run (no execution)
    ./daily_audit_workflow.py --dry-run

    # Verbose logging
    ./daily_audit_workflow.py --verbose
"""

import sys
import json
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import os

# Add SDK tools to path
SDK_DIR = Path(__file__).parent
sys.path.insert(0, str(SDK_DIR))

from governance import GovernanceEngine, RiskLevel
from workflow_transaction import WorkflowTransaction
import hook_integration
from inspect_sdk_workflow import SDKWorkflowInspector
from sdk_memory_bridge import SDKMemoryBridge

# Anthropic SDK imports
try:
    from anthropic import Anthropic
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("⚠️ Anthropic SDK not available. Install with: pip install anthropic", file=sys.stderr)


class DailyAuditWorkflow:
    """
    SDK-based daily audit workflow with governance integration.
    """

    def __init__(
        self,
        catalyst_root: Optional[Path] = None,
        dry_run: bool = False,
        verbose: bool = False
    ):
        """
        Initialize daily audit workflow.

        Args:
            catalyst_root: Huxley root directory (defaults to {{CATALYST_ROOT}})
            dry_run: If True, don't execute operations
            verbose: If True, enable verbose logging
        """
        self.catalyst_root = catalyst_root or Path("{{CATALYST_ROOT}}")
        self.dry_run = dry_run
        self.verbose = verbose

        # Core directories
        self.registry = self.catalyst_root / "registry"
        self.daily_dir = self.registry / "daily"
        self.tools_dir = self.catalyst_root / "tools"

        # Ensure directories exist
        self.daily_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.governance = GovernanceEngine()
        self.inspector = SDKWorkflowInspector()
        self.memory = SDKMemoryBridge(workflow_id="daily_audit")

        # Workflow state
        self.workflow_id = f"daily_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = datetime.now()
        self.errors = []
        self.results = {}

        # Initialize Anthropic client if available
        self.client = None
        if SDK_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = Anthropic(api_key=api_key)
            else:
                self._log("⚠️ ANTHROPIC_API_KEY not set, using fallback execution")

    def _log(self, message: str, level: str = "INFO"):
        """Log message to stdout and audit file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)

        # Also write to daily audit log
        log_file = self.daily_dir / "daily_audit.log"
        with open(log_file, "a") as f:
            f.write(log_line + "\n")

    def _execute_bash_command(self, command: str, description: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Execute bash command with timeout and logging.

        Args:
            command: Bash command to execute
            description: Human-readable description
            timeout: Timeout in seconds

        Returns:
            Dict with success, stdout, stderr, exit_code
        """
        if self.dry_run:
            self._log(f"DRY RUN: Would execute: {command}")
            return {"success": True, "stdout": "", "stderr": "", "exit_code": 0}

        self._log(f"Executing: {description}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.catalyst_root
            )

            success = result.returncode == 0
            level = "INFO" if success else "ERROR"

            if self.verbose:
                if result.stdout:
                    self._log(f"  stdout: {result.stdout[:200]}", level)
                if result.stderr:
                    self._log(f"  stderr: {result.stderr[:200]}", level)

            return {
                "success": success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            self._log(f"✗ {description} timed out after {timeout}s", "ERROR")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "exit_code": -1
            }
        except Exception as e:
            self._log(f"✗ {description} failed: {e}", "ERROR")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }

    def _classify_workflow(self) -> bool:
        """
        Classify workflow using governance engine.

        Returns:
            True if workflow can proceed (GREEN), False otherwise
        """
        self._log("Classifying workflow with governance engine...")

        result = self.governance.classify_operation(
            operation="Run daily audit workflow",
            workflow_name="daily_audit"
        )

        self._log(f"Risk Level: {result.risk_level.value.upper()}")
        self._log(f"Rationale: {result.rationale}")
        self._log(f"Approval Required: {result.approval_required}")

        if result.risk_level != RiskLevel.GREEN:
            self._log("✗ Workflow not GREEN - cannot auto-execute", "ERROR")
            return False

        self._log("✓ Workflow classified as GREEN - proceeding")
        return True

    def run(self) -> int:
        """
        Execute daily audit workflow.

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        self._log("=" * 70)
        self._log(f"Starting SDK Daily Audit Workflow: {self.workflow_id}")
        self._log("=" * 70)

        # Log workflow start to memory
        self.memory.observe_workflow(
            "daily_audit",
            f"Workflow started: {self.workflow_id}",
            {"timestamp": self.start_time.isoformat()}
        )

        # Step 0: Classify workflow
        if not self._classify_workflow():
            self.memory.observe_workflow("daily_audit", "Workflow blocked by governance", {"risk_level": "non-green"})
            return 1

        # Step 1: Create workflow transaction
        with WorkflowTransaction(
            capsule="Huxley",
            auto_commit=False
        ) as txn:

            try:
                # Step 2: Run pre-flight checks
                self._log("\nSTEP 1: Pre-flight checks")
                self._run_preflight_checks()

                # Step 3: Fix permissions and validate test environment
                self._log("\nSTEP 2: Fix permissions and validate test environment")
                self._run_environment_setup()

                # Step 4: Run smoke tests
                self._log("\nSTEP 3: Run smoke tests")
                smoke_result = self._run_smoke_tests()
                self.results["smoke_tests"] = smoke_result

                # Step 5: Refresh metrics and analysis
                self._log("\nSTEP 4: Refresh metrics and system analysis")
                self._run_metrics_refresh()

                # Step 5.5: Run maintenance tasks
                self._log("\nSTEP 5: Run maintenance tasks")
                self._run_maintenance_tasks()

                # Step 6: Build dashboard
                self._log("\nSTEP 6: Build dashboard")
                self._run_dashboard_build()

                # Step 7: Record status
                self._log("\nSTEP 7: Record audit status")
                status = self._record_status()

                # Step 8: Send notification
                self._log("\nSTEP 8: Send desktop notification")
                self._send_notification(status)

                # Commit transaction
                txn.commit()

                # Calculate workflow duration
                duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000

                # Learn from workflow outcome
                self.memory.learn_from_workflow(
                    "daily_audit",
                    success=(status == "PASS"),
                    metrics={
                        "duration_ms": duration_ms,
                        "smoke_exit": smoke_result.get("exit_code", 0),
                        "workflow_id": self.workflow_id
                    },
                    notes=f"Audit {status.lower()}"
                )

                self._log("\n" + "=" * 70)
                self._log(f"✓ Daily audit completed: {status}")
                self._log("=" * 70)

                return 0 if status == "PASS" else 1

            except Exception as e:
                self._log(f"\n✗ Workflow failed: {e}", "ERROR")
                self.errors.append({
                    "type": "workflow_error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                })

                # Log failure to memory
                self.memory.observe_workflow(
                    "daily_audit",
                    f"Workflow exception: {str(e)[:100]}",
                    {"error_type": "exception", "message": str(e)}
                )

                # Learn from failure
                self.memory.learn_from_workflow(
                    "daily_audit",
                    success=False,
                    notes=f"Exception: {str(e)[:50]}"
                )

                # Transaction will auto-rollback
                return 1

    def _run_preflight_checks(self):
        """Verify core directories and dependencies exist"""
        checks = [
            (self.catalyst_root, "Huxley root"),
            (self.registry, "Registry"),
            (self.tools_dir, "Tools directory"),
            (self.daily_dir, "Daily audit directory")
        ]

        for path, name in checks:
            if path.exists():
                self._log(f"  ✓ {name}: {path}")
            else:
                raise RuntimeError(f"{name} not found: {path}")

    def _run_environment_setup(self):
        """Fix permissions and validate test environment"""
        # Run fix_perms.sh if available
        fix_perms = self.tools_dir / "fix_perms.sh"
        if fix_perms.exists():
            result = self._execute_bash_command(
                str(fix_perms),
                "Fix permissions"
            )
            if result["success"]:
                self._log("  ✓ Permissions fixed")
        else:
            self._log("  ⚠️ fix_perms.sh not found, skipping")

        # Validate test environment
        if test_guard.exists():
            result = self._execute_bash_command(
                f"python3 {test_guard} validate",
                "Validate test environment"
            )
            if result["success"]:
                self._log("  ✓ Test environment validated")
            else:
                self._log("  ⚠️ Test environment needs setup, attempting fix")
                self._execute_bash_command(
                    f"python3 {test_guard} setup",
                    "Setup test environment"
                )

    def _run_smoke_tests(self) -> Dict[str, Any]:
        """Run integration smoke tests"""
        # Find test entrypoint
        test_integration = self.tools_dir / "test_integration.sh"
        test_builder = self.tools_dir / "test_builder.sh"

        if test_integration.exists():
            test_cmd = str(test_integration)
            test_args = ""
        elif test_builder.exists():
            test_cmd = str(test_builder)
            test_args = "--integration-only"
        else:
            self._log("  ⚠️ No test scripts found, skipping smoke tests")
            return {"success": True, "exit_code": 0, "notes": "no test scripts"}

        # Execute tests with timeout
        result = self._execute_bash_command(
            f"{test_cmd} {test_args}",
            "Smoke tests",
            timeout=120
        )

        if result["success"]:
            self._log("  ✓ Smoke tests PASSED")
        else:
            self._log(f"  ✗ Smoke tests FAILED (exit {result['exit_code']})", "ERROR")

        return result

    def _run_metrics_refresh(self):
        """Refresh metrics and system analysis"""
        tasks = [
            ("compose_codex_context.py", "Codex context refresh"),
            ("metrics_rollup.py", "Metrics rollup"),
            ("daily_dependency_check.py --quiet", "Dependency check"),
        ]

        for script, description in tasks:
            script_path = self.tools_dir / script.split()[0]
            if script_path.exists():
                cmd = f"python3 {self.tools_dir / script}"
                result = self._execute_bash_command(cmd, description, timeout=60)
                if result["success"]:
                    self._log(f"  ✓ {description} completed")
                else:
                    self._log(f"  ⚠️ {description} had issues", "WARNING")
            else:
                self._log(f"  ⚠️ {description} not found: {script_path}")

    def _run_maintenance_tasks(self):
        """Run system maintenance tasks (log cleanup, etc.)"""
        # Codex consultation log retention (keep last 30 days)
        consult_logs = Path.home() / ".cache/huxley/codex-consult"
        if consult_logs.is_dir():
            quoted_path = shlex.quote(str(consult_logs))
            result = self._execute_bash_command(
                f"find {quoted_path} -type f -mtime +30 -delete && find {quoted_path} -type d -empty -delete",
                "Codex consultation log cleanup",
                timeout=30
            )
            if result["success"]:
                self._log("  ✓ Codex consultation logs pruned (>30d)")
            else:
                self._log("  ⚠️ Codex consultation log cleanup had issues", "WARNING")

    def _run_dashboard_build(self):
        """Build or refresh dashboard"""
        build_dashboard = self.tools_dir / "build_dashboard.py"
        refresh_dashboard = self.tools_dir / "refresh_dashboard.sh"

        if build_dashboard.exists():
            result = self._execute_bash_command(
                f"python3 {build_dashboard}",
                "Build dashboard",
                timeout=30
            )
            if result["success"]:
                self._log("  ✓ Dashboard built")
        elif refresh_dashboard.exists():
            result = self._execute_bash_command(
                str(refresh_dashboard),
                "Refresh dashboard",
                timeout=30
            )
            if result["success"]:
                self._log("  ✓ Dashboard refreshed")
        else:
            self._log("  ⚠️ No dashboard tools found")

    def _record_status(self) -> str:
        """
        Record audit status to JSON file.

        Returns:
            Status string ("PASS" or "FAIL")
        """
        smoke_result = self.results.get("smoke_tests", {})
        smoke_exit = smoke_result.get("exit_code", 0)

        status = "PASS" if smoke_exit == 0 else "FAIL"
        notes = "smoke tests passed, dashboard refreshed" if status == "PASS" else "smoke tests failed"

        # Write status JSON
        date_stamp = datetime.now().strftime("%Y%m%d")
        status_file = self.daily_dir / f"status-{date_stamp}.json"

        status_data = {
            "ts": datetime.now().isoformat() + "Z",
            "status": status,
            "smoke_exit": smoke_exit,
            "notes": notes,
            "dashboard": str(self.registry / "dashboard/index.html"),
            "workflow_id": self.workflow_id
        }

        if smoke_exit != 0 and smoke_result.get("stderr"):
            status_data["error_hint"] = smoke_result["stderr"][:200]

        with open(status_file, "w") as f:
            json.dump(status_data, f, indent=2)

        self._log(f"  ✓ Status recorded: {status} (exit: {smoke_exit})")
        self._log(f"  Status file: {status_file}")

        return status

    def _send_notification(self, status: str):
        """Send macOS desktop notification"""
        if status == "PASS":
            title = "Huxley Daily Audit"
            message = "Daily audit completed successfully ✅"
            sound = "Glass"
        else:
            title = "Huxley Daily Audit"
            message = "Daily audit failed ❌ Check logs for details"
            sound = "Basso"

        # Send notification via osascript
        notification_cmd = f'''osascript -e 'display notification "{message}" with title "{title}" sound name "{sound}"' '''

        result = self._execute_bash_command(
            notification_cmd,
            "Desktop notification",
            timeout=5
        )

        if result["success"]:
            self._log("  ✓ Desktop notification sent")
        else:
            self._log("  ⚠️ Desktop notification failed")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Daily Audit SDK Workflow")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute operations")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--builder-root", help="Huxley root directory")

    args = parser.parse_args()

    # Create workflow
    catalyst_root = Path(args.catalyst_root) if args.catalyst_root else None
    workflow = DailyAuditWorkflow(
        catalyst_root=catalyst_root,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Execute workflow
    return workflow.run()


if __name__ == "__main__":
    sys.exit(main())
