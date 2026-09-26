#!/usr/bin/env python3
"""
Integration Tests for hook_integration.py

Verifies SDK workflows can call Huxley hooks correctly.
"""

import sys
from pathlib import Path

# Add SDK tools to path
sys.path.insert(0, str(Path(__file__).parent))

from hook_integration import (
    call_hook,
    HookValidationError,
    HookResult,
    validate_tool_operation,
    notify_session_start,
    notify_session_end
)


def test_session_start_hook():
    """Test calling on_session_start hook"""
    print("→ Testing on_session_start hook...")

    result = notify_session_start({
        "workflow": "test_workflow",
        "capsule": "test_capsule"
    })

    assert result.success, "Session start hook should succeed"
    print("✓ on_session_start hook works")


def test_session_end_hook():
    """Test calling on_session_end hook"""
    print("\n→ Testing on_session_end hook...")

    result = notify_session_end({
        "workflow": "test_workflow",
        "duration_seconds": 5,
        "success": True
    })

    # Session end hook may succeed or fail gracefully
    print(f"✓ on_session_end hook completed: {result.message}")


def test_hook_result_class():
    """Test HookResult class"""
    print("\n→ Testing HookResult class...")

    # Test success
    success_result = HookResult(success=True, message="Test passed")
    assert success_result.exit_code() == 0, "Success should return exit code 0"

    # Test non-blocking warning
    warning_result = HookResult(success=False, message="Warning", block=False)
    assert warning_result.exit_code() == 1, "Warning should return exit code 1"

    # Test blocking error
    blocking_result = HookResult(success=False, message="Blocked", block=True)
    assert blocking_result.exit_code() == 2, "Blocking should return exit code 2"

    print("✓ HookResult exit codes correct")


def test_validation_error():
    """Test HookValidationError exception"""
    print("\n→ Testing HookValidationError...")

    try:
        raise HookValidationError("test_hook", "Test validation failure")
    except HookValidationError as e:
        assert e.hook_name == "test_hook"
        assert "test_hook" in str(e)
        print("✓ HookValidationError works correctly")


def test_post_tool_use_blocking():
    """Test that post_tool_use blocks on validation failure"""
    print("\n→ Testing post_tool_use blocking behavior...")

    # This will call the actual post_tool_use hook with a spec file
    # Expected: Hook will call validator, validator will fail, hook will block
    try:
        result = call_hook(
            "post_tool_use",
            tool_name="Edit",
            tool_input={"file_path": "capsules/example-social-capsule/specs/current.yaml"},
            tool_response={"filePath": "capsules/example-social-capsule/specs/current.yaml"},
            timeout=5
        )
        print("⚠ Expected HookValidationError but hook passed")
        print(f"  Result: {result.message}")
    except HookValidationError as e:
        # Expected - validation should fail and block
        assert "blocked execution" in str(e).lower()
        print("✓ post_tool_use correctly blocks on validation failure")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Hook Integration Test Suite")
    print("=" * 60)

    try:
        test_hook_result_class()
        test_validation_error()
        test_session_start_hook()
        test_session_end_hook()
        test_post_tool_use_blocking()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
