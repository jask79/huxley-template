#!/usr/bin/env python3
"""
MCP File Synchronization Utilities

Provides thread-safe, process-safe file locking and atomic writes for
Huxley MCP builder-memory.json access. Prevents race conditions when
multiple SDK workflows run concurrently.

Usage:
    # Safe read
    state = safe_mcp_read()

    # Safe update
    safe_mcp_update(lambda state: {**state, "new_key": "value"})

    # Context manager
    with MCPLock() as lock:
        state = lock.read()
        updated = process(state)
        lock.write(updated)
"""

import fcntl
import json
import tempfile
import os
import sys
from pathlib import Path
from typing import Callable, Any, Optional
from contextlib import contextmanager


class MCPLock:
    """Thread-safe, process-safe lock for MCP builder-memory.json"""

    def __init__(self, mcp_path: Optional[Path] = None):
        if mcp_path is None:
            self.mcp_path = Path.home() / ".claude/mcp-data/builder-memory.json"
        else:
            self.mcp_path = Path(mcp_path)

        self.lock_file: Optional[Any] = None
        self.is_locked = False

    def __enter__(self):
        """Acquire exclusive lock on MCP file"""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock"""
        self.release()
        return False

    def acquire(self, timeout: int = 30):
        """
        Acquire exclusive lock on MCP file.

        Args:
            timeout: Maximum seconds to wait for lock

        Raises:
            TimeoutError: If lock not acquired within timeout
            FileNotFoundError: If MCP file doesn't exist
        """
        if not self.mcp_path.exists():
            raise FileNotFoundError(f"MCP file not found: {self.mcp_path}")

        self.lock_file = open(self.mcp_path, 'r+')

        try:
            # Try to acquire exclusive lock
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.is_locked = True
        except BlockingIOError:
            # Lock held by another process, wait for it
            import time
            start = time.time()
            while time.time() - start < timeout:
                try:
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.is_locked = True
                    break
                except BlockingIOError:
                    time.sleep(0.1)
            else:
                self.lock_file.close()
                raise TimeoutError(
                    f"Could not acquire MCP lock after {timeout}s"
                )

    def release(self):
        """Release lock on MCP file"""
        if self.lock_file and self.is_locked:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
            self.is_locked = False

    def read(self) -> dict:
        """
        Read MCP state (must hold lock).

        Returns:
            MCP state dictionary

        Raises:
            RuntimeError: If lock not held
        """
        if not self.is_locked:
            raise RuntimeError("Must acquire lock before reading")

        self.lock_file.seek(0)
        return json.load(self.lock_file)

    def write(self, state: dict):
        """
        Write MCP state atomically (must hold lock).

        Args:
            state: MCP state dictionary to write

        Raises:
            RuntimeError: If lock not held
        """
        if not self.is_locked:
            raise RuntimeError("Must acquire lock before writing")

        # Write to temp file first
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.mcp_path.parent,
            prefix=".builder-memory-",
            suffix=".json.tmp"
        )

        try:
            with os.fdopen(temp_fd, 'w') as temp_file:
                json.dump(state, temp_file, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            # Atomic replace
            os.replace(temp_path, self.mcp_path)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise


def safe_mcp_read(mcp_path: Optional[Path] = None) -> dict:
    """
    Safely read MCP builder-memory with locking.

    Args:
        mcp_path: Optional custom MCP path

    Returns:
        MCP state dictionary

    Example:
        state = safe_mcp_read()
        patterns = state.get("patterns", [])
    """
    with MCPLock(mcp_path) as lock:
        return lock.read()


def safe_mcp_update(
    update_fn: Callable[[dict], dict],
    mcp_path: Optional[Path] = None
) -> dict:
    """
    Safely update MCP builder-memory with locking and atomic writes.

    Args:
        update_fn: Function that takes current state and returns updated state
        mcp_path: Optional custom MCP path

    Returns:
        Updated MCP state

    Example:
        def add_pattern(state):
            patterns = state.get("patterns", [])
            patterns.append({"name": "new-pattern", "data": "..."})
            return {**state, "patterns": patterns}

        updated = safe_mcp_update(add_pattern)
    """
    with MCPLock(mcp_path) as lock:
        current_state = lock.read()
        updated_state = update_fn(current_state)
        lock.write(updated_state)
        return updated_state


@contextmanager
def mcp_transaction(mcp_path: Optional[Path] = None):
    """
    Context manager for MCP transactions with automatic rollback on error.

    Yields:
        Tuple of (current_state, commit_fn)

    Example:
        with mcp_transaction() as (state, commit):
            # Modify state
            state["patterns"].append(new_pattern)
            # Commit changes
            commit(state)
            # If exception occurs, changes are not committed
    """
    lock = MCPLock(mcp_path)
    lock.acquire()

    try:
        current_state = lock.read()
        committed = False

        def commit(updated_state: dict):
            nonlocal committed
            lock.write(updated_state)
            committed = True

        yield current_state, commit

        if not committed:
            # Transaction not committed, no changes made
            pass

    finally:
        lock.release()


def filter_private_data(data: Any, private_prefix: str = "[PRIVATE]") -> Any:
    """
    Recursively filter out private data before MCP storage.

    Args:
        data: Data structure to filter (dict, list, str, etc.)
        private_prefix: Prefix marking private data

    Returns:
        Filtered data with private content removed

    Example:
        state = {
            "public": "visible",
            "secret": "[PRIVATE] API key: sk-1234"
        }
        filtered = filter_private_data(state)
        # {"public": "visible", "secret": "[REDACTED]"}
    """
    if isinstance(data, dict):
        return {
            key: filter_private_data(value, private_prefix)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [filter_private_data(item, private_prefix) for item in data]
    elif isinstance(data, str):
        if private_prefix in data:
            return "[REDACTED]"
        return data
    else:
        return data


def main():
    """CLI for testing MCP locking"""
    import argparse

    parser = argparse.ArgumentParser(description="MCP File Locking Utilities")
    parser.add_argument("--read", action="store_true", help="Read MCP state")
    parser.add_argument("--test-lock", action="store_true", help="Test lock acquisition")
    parser.add_argument("--filter-test", action="store_true", help="Test privacy filtering")

    args = parser.parse_args()

    if args.read:
        try:
            state = safe_mcp_read()
            print("✓ MCP state read successfully")
            print(f"  Entities: {len(state.get('entities', []))}")
            print(f"  Patterns: {len(state.get('patterns', []))}")
        except Exception as e:
            print(f"✗ Failed to read MCP: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.test_lock:
        try:
            with MCPLock() as lock:
                print("✓ Lock acquired successfully")
                state = lock.read()
                print(f"  State loaded: {len(state)} top-level keys")
            print("✓ Lock released successfully")
        except Exception as e:
            print(f"✗ Lock test failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.filter_test:
        test_data = {
            "public": "visible data",
            "secret": "[PRIVATE] API key: sk-1234",
            "nested": {
                "normal": "value",
                "sensitive": "[PRIVATE] password123"
            }
        }
        filtered = filter_private_data(test_data)
        print("✓ Privacy filter test:")
        print(f"  Original: {json.dumps(test_data, indent=2)}")
        print(f"  Filtered: {json.dumps(filtered, indent=2)}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
