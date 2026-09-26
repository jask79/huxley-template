#!/usr/bin/env python3
"""
Transactional Workflow Pattern for SDK

Provides atomic transaction semantics for SDK workflows with automatic
rollback on validation failures or errors. Ensures Huxley state remains
consistent even if SDK workflows fail mid-execution.

Usage:
    from workflow_transaction import workflow_transaction

    # Automatic rollback on error
    with workflow_transaction("example-social-capsule") as txn:
        # SDK workflow execution
        result = agent.execute_task("Update specs")

        # Validation checkpoint
        txn.validate_state()

        # Commit changes (automatic if no exception)
        txn.commit()

    # If exception raised, all changes rolled back automatically

    # Manual rollback control
    with workflow_transaction("example-social-capsule", auto_commit=False) as txn:
        result = agent.execute_task("Risky operation")

        if not meets_quality_standard(result):
            txn.rollback()  # Explicit rollback
            raise ValidationError("Quality gate failed")

        txn.commit()  # Explicit commit
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime
import sys

# Import MCP sync utilities for state management
sys.path.insert(0, str(Path(__file__).parent))
from mcp_sync import MCPLock, safe_mcp_read


class TransactionRollbackError(Exception):
    """Raised when transaction rollback fails"""
    pass


class WorkflowTransaction:
    """
    Manages transactional workflow execution with rollback support.

    Captures snapshots of:
    - MCP builder-memory state
    - Capsule files (specs, context, etc.)
    - Registry state

    Supports automatic or manual commit/rollback.
    """

    def __init__(
        self,
        capsule: str,
        auto_commit: bool = True,
        snapshot_files: bool = True
    ):
        """
        Initialize workflow transaction.

        Args:
            capsule: Capsule name for transaction scope
            auto_commit: Auto-commit on successful exit (default True)
            snapshot_files: Snapshot capsule files for rollback (default True)
        """
        self.capsule = capsule
        self.auto_commit = auto_commit
        self.snapshot_files = snapshot_files

        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.capsule_path = self.catalyst_root / "capsules" / capsule

        # Transaction state
        self.transaction_id = f"txn_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.snapshot_dir: Optional[Path] = None
        self.mcp_snapshot: Optional[Dict[str, Any]] = None
        self.committed = False
        self.rolled_back = False

        # Verify capsule exists
        if not self.capsule_path.exists():
            raise FileNotFoundError(f"Capsule not found: {capsule}")

    def __enter__(self):
        """Begin transaction - create snapshots"""
        self._begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        End transaction - commit or rollback.

        If exception occurred and auto_commit=True, rollback.
        If no exception and auto_commit=True, commit.
        If auto_commit=False, user must explicitly commit/rollback.
        """
        if exc_type is not None:
            # Exception occurred - rollback
            if not self.rolled_back:
                try:
                    self.rollback()
                except Exception as e:
                    print(f"⚠ Rollback failed: {e}", file=sys.stderr)
            return False  # Propagate exception

        # No exception
        if self.auto_commit and not self.committed:
            self.commit()
        elif not self.committed and not self.rolled_back:
            # Manual commit mode but user didn't commit
            print("⚠ Transaction not committed (auto_commit=False)", file=sys.stderr)
            self.rollback()

        return True

    def _begin(self):
        """Create transaction snapshots"""
        print(f"→ BEGIN transaction: {self.transaction_id}")

        # Snapshot MCP state
        try:
            self.mcp_snapshot = safe_mcp_read()
            print(f"  ✓ MCP state snapshot captured")
        except Exception as e:
            print(f"  ⚠ MCP snapshot failed: {e}", file=sys.stderr)
            self.mcp_snapshot = None

        # Snapshot capsule files
        if self.snapshot_files:
            try:
                # Ensure .cache directory exists
                cache_dir = self.catalyst_root / ".cache"
                cache_dir.mkdir(parents=True, exist_ok=True)

                self.snapshot_dir = Path(tempfile.mkdtemp(
                    prefix=f".txn_{self.capsule}_",
                    dir=cache_dir
                ))

                # Copy critical files
                critical_dirs = ["specs", "context", "product.yaml", "standards.yaml"]
                for item in critical_dirs:
                    src = self.capsule_path / item
                    if src.exists():
                        dst = self.snapshot_dir / item
                        if src.is_dir():
                            shutil.copytree(src, dst)
                        else:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dst)

                print(f"  ✓ Capsule files snapshot captured")
            except Exception as e:
                print(f"  ⚠ File snapshot failed: {e}", file=sys.stderr)
                self.snapshot_dir = None

    def commit(self):
        """
        Commit transaction - make changes permanent.

        Cleans up snapshots after successful commit.
        """
        if self.committed:
            print("⚠ Transaction already committed", file=sys.stderr)
            return

        if self.rolled_back:
            raise TransactionRollbackError("Cannot commit - already rolled back")

        print(f"→ COMMIT transaction: {self.transaction_id}")

        # Clean up snapshots
        self._cleanup_snapshots()

        self.committed = True
        print("  ✓ Transaction committed")

    def rollback(self):
        """
        Rollback transaction - restore snapshots.

        Reverts:
        - MCP builder-memory to snapshot state
        - Capsule files to snapshot state
        """
        if self.rolled_back:
            print("⚠ Transaction already rolled back", file=sys.stderr)
            return

        if self.committed:
            raise TransactionRollbackError("Cannot rollback - already committed")

        print(f"→ ROLLBACK transaction: {self.transaction_id}")

        errors = []

        # Restore MCP state
        if self.mcp_snapshot:
            try:
                with MCPLock() as lock:
                    lock.write(self.mcp_snapshot)
                print("  ✓ MCP state restored")
            except Exception as e:
                errors.append(f"MCP restore failed: {e}")
                print(f"  ✗ MCP restore failed: {e}", file=sys.stderr)

        # Restore capsule files
        if self.snapshot_dir and self.snapshot_dir.exists():
            try:
                # Remove modified files
                for item in ["specs", "context", "product.yaml", "standards.yaml"]:
                    target = self.capsule_path / item
                    if target.exists():
                        if target.is_dir():
                            shutil.rmtree(target)
                        else:
                            target.unlink()

                # Restore from snapshot
                for item in self.snapshot_dir.iterdir():
                    dst = self.capsule_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dst)
                    else:
                        shutil.copy2(item, dst)

                print("  ✓ Capsule files restored")
            except Exception as e:
                errors.append(f"File restore failed: {e}")
                print(f"  ✗ File restore failed: {e}", file=sys.stderr)

        # Clean up snapshots
        self._cleanup_snapshots()

        self.rolled_back = True

        if errors:
            raise TransactionRollbackError(
                f"Rollback completed with errors: {'; '.join(errors)}"
            )

        print("  ✓ Transaction rolled back")

    def validate_state(self):
        """
        Validation checkpoint - verify state is consistent.

        Raises exception if validation fails, triggering rollback.
        """
        print("→ VALIDATE transaction state")

        # Verify capsule still exists
        if not self.capsule_path.exists():
            raise TransactionRollbackError(
                f"Capsule directory deleted: {self.capsule}"
            )

        # Verify MCP accessible
        try:
            safe_mcp_read()
        except Exception as e:
            raise TransactionRollbackError(
                f"MCP state inaccessible: {e}"
            )

        print("  ✓ State validation passed")

    def _cleanup_snapshots(self):
        """Clean up transaction snapshots"""
        if self.snapshot_dir and self.snapshot_dir.exists():
            try:
                shutil.rmtree(self.snapshot_dir)
            except Exception as e:
                print(f"  ⚠ Snapshot cleanup failed: {e}", file=sys.stderr)


@contextmanager
def workflow_transaction(
    capsule: str,
    auto_commit: bool = True,
    snapshot_files: bool = True
):
    """
    Context manager for transactional SDK workflow execution.

    Args:
        capsule: Capsule name for transaction scope
        auto_commit: Auto-commit on success (default True)
        snapshot_files: Snapshot capsule files (default True)

    Yields:
        WorkflowTransaction instance

    Example:
        with workflow_transaction("example-social-capsule") as txn:
            # SDK workflow operations
            result = agent.execute_task("Update specs")

            # Validation
            txn.validate_state()

            # Auto-commit on success, auto-rollback on error

        # Manual commit control
        with workflow_transaction("example-social-capsule", auto_commit=False) as txn:
            result = agent.execute_task("Risky operation")

            if quality_check(result):
                txn.commit()
            else:
                txn.rollback()
    """
    txn = WorkflowTransaction(
        capsule=capsule,
        auto_commit=auto_commit,
        snapshot_files=snapshot_files
    )

    # Begin transaction
    txn._begin()

    try:
        yield txn

        # Auto-commit if enabled and no exception
        if txn.auto_commit and not txn.committed and not txn.rolled_back:
            txn.commit()

    except Exception:
        # Rollback on exception
        if not txn.rolled_back:
            txn.rollback()
        raise

    finally:
        # Cleanup snapshots if not already done
        if not txn.committed and not txn.rolled_back:
            # User didn't commit or rollback - force rollback
            txn.rollback()


def main():
    """CLI for testing workflow transactions"""
    import argparse

    parser = argparse.ArgumentParser(description="Workflow Transaction Testing")
    parser.add_argument("capsule", help="Capsule name")
    parser.add_argument("--test-rollback", action="store_true",
                       help="Test rollback by raising exception")
    parser.add_argument("--no-auto-commit", action="store_true",
                       help="Disable auto-commit (manual commit required)")

    args = parser.parse_args()

    try:
        print(f"Testing workflow transaction for: {args.capsule}\n")

        with workflow_transaction(
            args.capsule,
            auto_commit=not args.no_auto_commit
        ) as txn:

            print("\n→ Simulating workflow operations...")

            # Simulate work
            import time
            time.sleep(1)

            # Validation checkpoint
            txn.validate_state()

            if args.test_rollback:
                print("\n→ Triggering rollback test...")
                raise Exception("Test rollback triggered")

            if args.no_auto_commit:
                print("\n→ Manual commit...")
                txn.commit()

        print("\n✓ Transaction test completed successfully")
        return 0

    except Exception as e:
        print(f"\n✗ Transaction test failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
