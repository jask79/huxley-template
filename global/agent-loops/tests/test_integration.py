"""
Integration tests for complete loop execution.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loop_executor import FoundationLoopExecutor


def test_simple_success_loop():
    """Test a simple successful loop execution."""
    executor = FoundationLoopExecutor(agent_name="Test Agent", max_iterations=3)

    # Mock functions
    iteration_count = [0]

    def mock_execute(task):
        iteration_count[0] += 1
        return iteration_count[0] >= 2  # Succeed on 2nd iteration

    def mock_validate():
        if iteration_count[0] < 2:
            # First iteration - failure
            return "pytest", {
                "exit_code": 1,
                "stdout": "FAILED test.py::test_example",
                "stderr": "AssertionError: Expected 2, got 1",
            }
        else:
            # Second iteration - success
            return "pytest", {
                "exit_code": 0,
                "stdout": "PASSED test.py::test_example",
                "stderr": "",
            }

    criteria = {"tests_pass": False}

    # Execute loop
    result = executor.execute_loop(
        task={"description": "Fix failing test"},
        execute_fn=mock_execute,
        validate_fn=mock_validate,
        criteria=criteria,
    )

    # Should succeed after iterations
    assert result.iterations >= 1


def test_deterministic_blocker_escalation():
    """Test that deterministic blockers trigger immediate escalation."""
    executor = FoundationLoopExecutor(agent_name="Test Agent", max_iterations=5)

    def mock_execute(task):
        return False

    def mock_validate():
        return "pytest", {
            "exit_code": 126,
            "stdout": "",
            "stderr": "PermissionError: Permission denied",
        }

    criteria = {"tests_pass": False}

    result = executor.execute_loop(
        task={"description": "Run tests"},
        execute_fn=mock_execute,
        validate_fn=mock_validate,
        criteria=criteria,
    )

    # Should escalate immediately
    assert result.escalation_triggered
    assert "permission" in result.escalation_reason.lower()


def test_stuck_detection_escalation():
    """Test that stuck detection triggers escalation."""
    executor = FoundationLoopExecutor(agent_name="Test Agent", max_iterations=10)

    def mock_execute(task):
        return False

    def mock_validate():
        # Return same error every time
        return "pytest", {
            "exit_code": 1,
            "stdout": "FAILED",
            "stderr": "ImportError: No module named 'foo'",
        }

    criteria = {"tests_pass": False}

    result = executor.execute_loop(
        task={"description": "Fix import error"},
        execute_fn=mock_execute,
        validate_fn=mock_validate,
        criteria=criteria,
    )

    # Should eventually escalate due to stuck detection
    assert result.escalation_triggered or result.iterations >= 5


def test_max_iterations_escalation():
    """Test escalation when max iterations reached."""
    executor = FoundationLoopExecutor(agent_name="Test Agent", max_iterations=2)

    def mock_execute(task):
        return False

    def mock_validate():
        return "pytest", {"exit_code": 1, "stdout": "FAILED", "stderr": "Different error each time"}

    criteria = {"tests_pass": False}

    result = executor.execute_loop(
        task={"description": "Fix tests"},
        execute_fn=mock_execute,
        validate_fn=mock_validate,
        criteria=criteria,
    )

    # Should escalate after max iterations
    assert result.escalation_triggered
    assert result.iterations >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
