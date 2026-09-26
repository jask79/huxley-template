#!/usr/bin/env python3
"""
SDK Cron Wrapper - Production Cron Job Framework

Wraps SDK workflows for cron execution with comprehensive error handling,
logging, notifications, and webhook integration.

Features:
- Pre-execution validation (environment, dependencies, locks)
- Workflow execution with timeout protection
- Automatic retry on transient failures
- Webhook integration for observation logging
- Desktop notifications for failures
- Lock file management (prevent concurrent runs)
- Comprehensive logging with rotation
- Exit code management for cron monitoring

Usage:
    # Execute workflow with default settings
    ./cron_wrapper.py daily_audit_workflow.py

    # With custom timeout and retries
    ./cron_wrapper.py daily_audit_workflow.py --timeout 300 --retries 2

    # Dry run (validation only)
    ./cron_wrapper.py daily_audit_workflow.py --dry-run

    # Disable notifications
    ./cron_wrapper.py daily_audit_workflow.py --no-notify

Crontab Example:
    # Daily audit at 9:10 AM
    10 9 * * * {{CATALYST_ROOT}}/tools/sdk/cron_wrapper.py {{CATALYST_ROOT}}/tools/sdk/daily_audit_workflow.py

Environment Variables:
    SDK_WEBHOOK_URL - Webhook server URL (default: http://localhost:5000)
    SDK_WEBHOOK_API_KEY - API key for webhook authentication
    SDK_CRON_NOTIFY - Enable/disable notifications (default: true)
"""

import sys
import os
import json
import subprocess
import time
import fcntl
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import argparse
import hashlib

# Add SDK tools to path
SDK_DIR = Path(__file__).parent
sys.path.insert(0, str(SDK_DIR))


class CronWrapper:
    """
    Production cron wrapper for SDK workflows.
    """

    def __init__(
        self,
        workflow_script: Path,
        timeout: int = 600,
        retries: int = 1,
        dry_run: bool = False,
        notify: bool = True,
        webhook_url: Optional[str] = None,
        webhook_api_key: Optional[str] = None
    ):
        """
        Initialize cron wrapper.

        Args:
            workflow_script: Path to workflow script to execute
            timeout: Execution timeout in seconds (default: 600)
            retries: Number of retries on failure (default: 1)
            dry_run: If True, validate but don't execute
            notify: If True, send desktop notifications on failure
            webhook_url: Webhook server URL
            webhook_api_key: Webhook API key
        """
        self.workflow_script = workflow_script
        self.timeout = timeout
        self.retries = retries
        self.dry_run = dry_run
        self.notify = notify

        # Get workflow name from script
        self.workflow_name = workflow_script.stem

        # Webhook configuration
        self.webhook_url = webhook_url or os.getenv("SDK_WEBHOOK_URL", "http://localhost:5000")
        self.webhook_api_key = webhook_api_key or os.getenv("SDK_WEBHOOK_API_KEY")

        # Directories
        self.log_dir = Path("{{CATALYST_ROOT}}/registry/cron")
        self.lock_dir = Path("{{CATALYST_ROOT}}/registry/locks")

        # Create directories
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{self.workflow_name}_{timestamp}.log"
        self.lock_file = self.lock_dir / f"{self.workflow_name}.lock"

        # Execution state
        self.start_time = datetime.now()
        self.execution_id = f"{self.workflow_name}_{timestamp}"
        self.errors: List[str] = []

    def log(self, message: str, level: str = "INFO"):
        """Log message to file and stdout"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"

        # Print to stdout
        print(log_line)

        # Write to log file
        with open(self.log_file, "a") as f:
            f.write(log_line + "\n")

    def send_webhook(self, observation: str, metadata: Optional[Dict[str, Any]] = None):
        """Send observation to webhook server"""
        if not self.webhook_api_key:
            self.log("Webhook API key not set, skipping webhook", "DEBUG")
            return

        try:
            import requests

            headers = {
                "X-API-Key": self.webhook_api_key,
                "Content-Type": "application/json"
            }

            data = {
                "workflow": self.workflow_name,
                "observation": observation,
                "metadata": metadata or {}
            }

            response = requests.post(
                f"{self.webhook_url}/webhook/observe",
                headers=headers,
                json=data,
                timeout=5
            )

            if response.status_code == 201:
                self.log(f"Webhook sent: {observation}", "DEBUG")
            else:
                self.log(f"Webhook failed: {response.status_code}", "WARNING")

        except Exception as e:
            self.log(f"Webhook error: {e}", "WARNING")

    def send_notification(self, title: str, message: str, sound: str = "Basso"):
        """Send macOS desktop notification"""
        if not self.notify:
            return

        try:
            escaped_message = message.replace("'", "'\"'\"'")
            escaped_title = title.replace("'", "'\"'\"'")
            escaped_sound = sound.replace("'", "'\"'\"'")
            subprocess.run(
                ["osascript", "-e", f"display notification \"{escaped_message}\" with title \"{escaped_title}\" sound name \"{escaped_sound}\""],
                shell=False, timeout=5, capture_output=True
            )
            self.log(f"Notification sent: {title}", "DEBUG")
        except Exception as e:
            self.log(f"Notification error: {e}", "WARNING")

    def acquire_lock(self) -> bool:
        """
        Acquire lock file to prevent concurrent execution.

        Returns:
            True if lock acquired, False if already locked
        """
        try:
            # Create lock file
            self.lock_fd = open(self.lock_file, 'w')

            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Write execution ID to lock file
            self.lock_fd.write(f"{self.execution_id}\n")
            self.lock_fd.write(f"{datetime.now().isoformat()}\n")
            self.lock_fd.flush()

            self.log(f"Lock acquired: {self.lock_file}", "DEBUG")
            return True

        except BlockingIOError:
            self.log(f"Lock already held: {self.lock_file}", "ERROR")
            self.errors.append("workflow_already_running")
            return False

        except Exception as e:
            self.log(f"Lock acquisition error: {e}", "ERROR")
            self.errors.append(f"lock_error: {e}")
            return False

    def release_lock(self):
        """Release lock file"""
        try:
            if hasattr(self, 'lock_fd'):
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
                self.lock_file.unlink(missing_ok=True)
                self.log(f"Lock released: {self.lock_file}", "DEBUG")
        except Exception as e:
            self.log(f"Lock release error: {e}", "WARNING")

    def validate_environment(self) -> bool:
        """
        Validate execution environment.

        Returns:
            True if environment is valid
        """
        self.log("Validating environment...")

        # Check workflow script exists
        if not self.workflow_script.exists():
            self.log(f"Workflow script not found: {self.workflow_script}", "ERROR")
            self.errors.append("workflow_script_not_found")
            return False

        # Check script is executable or python
        if not os.access(self.workflow_script, os.X_OK) and not self.workflow_script.suffix == '.py':
            self.log(f"Workflow script not executable: {self.workflow_script}", "ERROR")
            self.errors.append("workflow_script_not_executable")
            return False

        # Check Python availability
        try:
            result = subprocess.run(
                ["python3", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                self.log("Python3 not available", "ERROR")
                self.errors.append("python3_not_found")
                return False
        except Exception as e:
            self.log(f"Python3 check failed: {e}", "ERROR")
            self.errors.append(f"python3_error: {e}")
            return False

        # Check disk space
        try:
            stat = os.statvfs(str(self.log_dir))
            free_space_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)

            if free_space_mb < 100:  # Less than 100MB
                self.log(f"Low disk space: {free_space_mb:.1f}MB", "WARNING")
                self.errors.append(f"low_disk_space: {free_space_mb:.1f}MB")

        except Exception as e:
            self.log(f"Disk space check failed: {e}", "WARNING")

        self.log("✓ Environment validated")
        return True

    def execute_workflow(self) -> int:
        """
        Execute workflow with timeout and error handling.

        Returns:
            Exit code (0 = success, non-zero = failure)
        """
        self.log(f"Executing workflow: {self.workflow_script}")

        # Build command
        if self.workflow_script.suffix == '.py':
            cmd = ["python3", str(self.workflow_script)]
        else:
            cmd = [str(self.workflow_script)]

        # Execute with timeout
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.workflow_script.parent
            )

            # Log output
            if result.stdout:
                self.log("--- STDOUT ---", "DEBUG")
                for line in result.stdout.splitlines():
                    self.log(f"  {line}", "DEBUG")

            if result.stderr:
                self.log("--- STDERR ---", "DEBUG" if result.returncode == 0 else "ERROR")
                for line in result.stderr.splitlines():
                    self.log(f"  {line}", "DEBUG" if result.returncode == 0 else "ERROR")

            # Check exit code
            if result.returncode == 0:
                self.log(f"✓ Workflow completed successfully (exit {result.returncode})")
            else:
                self.log(f"✗ Workflow failed (exit {result.returncode})", "ERROR")
                self.errors.append(f"workflow_exit_{result.returncode}")

            return result.returncode

        except subprocess.TimeoutExpired:
            self.log(f"✗ Workflow timed out after {self.timeout}s", "ERROR")
            self.errors.append(f"timeout_{self.timeout}s")
            return 124  # Standard timeout exit code

        except Exception as e:
            self.log(f"✗ Workflow execution error: {e}", "ERROR")
            self.errors.append(f"execution_error: {e}")
            return 1

    def run(self) -> int:
        """
        Execute complete cron workflow.

        Returns:
            Exit code (0 = success, non-zero = failure)
        """
        self.log("=" * 70)
        self.log(f"SDK Cron Wrapper: {self.execution_id}")
        self.log("=" * 70)
        self.log(f"Workflow: {self.workflow_script}")
        self.log(f"Timeout: {self.timeout}s")
        self.log(f"Retries: {self.retries}")
        self.log(f"Dry Run: {self.dry_run}")
        self.log(f"Log File: {self.log_file}")
        self.log("=" * 70)

        # Send start webhook
        self.send_webhook(
            f"Cron execution started: {self.execution_id}",
            {"execution_id": self.execution_id, "dry_run": self.dry_run}
        )

        try:
            # Step 1: Validate environment
            if not self.validate_environment():
                self.log("✗ Environment validation failed", "ERROR")
                self.send_webhook(
                    "Cron execution failed: environment validation",
                    {"errors": self.errors}
                )
                self.send_notification(
                    "Cron Execution Failed",
                    f"{self.workflow_name}: Environment validation failed"
                )
                return 1

            # Step 2: Acquire lock
            if not self.acquire_lock():
                self.log("✗ Failed to acquire lock (workflow already running)", "ERROR")
                self.send_webhook(
                    "Cron execution blocked: workflow already running",
                    {"lock_file": str(self.lock_file)}
                )
                return 2

            # Step 3: Execute workflow (with retries)
            if self.dry_run:
                self.log("✓ Dry run - skipping execution")
                exit_code = 0
            else:
                exit_code = None
                for attempt in range(1, self.retries + 2):  # +1 for initial attempt
                    if attempt > 1:
                        self.log(f"Retry attempt {attempt - 1}/{self.retries}")
                        time.sleep(5)  # Wait before retry

                    exit_code = self.execute_workflow()

                    if exit_code == 0:
                        break  # Success, no need to retry

                    # Check if error is retryable
                    if exit_code == 124:  # Timeout
                        self.log("Timeout error - retrying", "WARNING")
                        continue
                    else:
                        self.log("Non-retryable error - stopping", "ERROR")
                        break

            # Step 4: Calculate duration
            duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000

            # Step 5: Send completion webhook
            if exit_code == 0:
                self.send_webhook(
                    f"Cron execution completed successfully",
                    {
                        "execution_id": self.execution_id,
                        "duration_ms": duration_ms,
                        "exit_code": exit_code
                    }
                )
            else:
                self.send_webhook(
                    f"Cron execution failed (exit {exit_code})",
                    {
                        "execution_id": self.execution_id,
                        "duration_ms": duration_ms,
                        "exit_code": exit_code,
                        "errors": self.errors
                    }
                )
                self.send_notification(
                    "Cron Execution Failed",
                    f"{self.workflow_name}: Exit code {exit_code}"
                )

            # Step 6: Log summary
            self.log("=" * 70)
            self.log(f"Execution completed: {exit_code}")
            self.log(f"Duration: {duration_ms:.1f}ms")
            if self.errors:
                self.log(f"Errors: {', '.join(self.errors)}")
            self.log("=" * 70)

            return exit_code

        except Exception as e:
            self.log(f"✗ Wrapper exception: {e}", "ERROR")
            self.send_webhook(
                "Cron execution exception",
                {"error": str(e), "execution_id": self.execution_id}
            )
            self.send_notification(
                "Cron Execution Exception",
                f"{self.workflow_name}: {str(e)[:100]}"
            )
            return 1

        finally:
            # Always release lock
            self.release_lock()


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="SDK Cron Wrapper")

    parser.add_argument("workflow_script",
                       help="Path to workflow script to execute")
    parser.add_argument("--timeout", type=int, default=600,
                       help="Execution timeout in seconds (default: 600)")
    parser.add_argument("--retries", type=int, default=1,
                       help="Number of retries on failure (default: 1)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Validate but don't execute")
    parser.add_argument("--no-notify", dest="notify", action="store_false",
                       help="Disable desktop notifications")
    parser.add_argument("--webhook-url",
                       help="Webhook server URL (default: $SDK_WEBHOOK_URL or http://localhost:5000)")
    parser.add_argument("--webhook-api-key",
                       help="Webhook API key (default: $SDK_WEBHOOK_API_KEY)")

    args = parser.parse_args()

    # Resolve workflow script path
    workflow_script = Path(args.workflow_script).resolve()

    # Create wrapper
    wrapper = CronWrapper(
        workflow_script=workflow_script,
        timeout=args.timeout,
        retries=args.retries,
        dry_run=args.dry_run,
        notify=args.notify,
        webhook_url=args.webhook_url,
        webhook_api_key=args.webhook_api_key
    )

    # Execute
    exit_code = wrapper.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
