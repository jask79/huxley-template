"""
Unit tests for adaptive limits.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from safety.adaptive_limits import AdaptiveLimits


def test_adaptive_limits_initialization():
    """Test adaptive limits initialization."""
    limits = AdaptiveLimits(default_max_iterations=5)

    assert limits.iterations_completed == 0
    assert limits.current_max_iterations == 5
    assert len(limits.history) == 0


def test_should_continue():
    """Test iteration continuation logic."""
    limits = AdaptiveLimits(default_max_iterations=5, min_iterations=2)

    # Should continue for minimum iterations
    assert limits.should_continue()

    limits.iterations_completed = 1
    assert limits.should_continue()

    # Should stop at max iterations
    limits.iterations_completed = 5
    assert not limits.should_continue()


def test_adaptive_adjustment_good_progress():
    """Test limit adjustment with good progress."""
    limits = AdaptiveLimits(default_max_iterations=5)

    # Record good progress
    for i in range(3):
        limits.record_iteration(
            success=False, progress_made=True, validation_results={"test": True}
        )

    # Limits should increase with good progress
    assert limits.current_max_iterations > 5


def test_adaptive_adjustment_poor_progress():
    """Test limit adjustment with poor progress."""
    limits = AdaptiveLimits(default_max_iterations=5, min_iterations=2)

    # Record poor progress
    for i in range(3):
        limits.record_iteration(
            success=False, progress_made=False, validation_results={"test": False}
        )

    # Limits should decrease with poor progress
    # But not below min_iterations
    assert limits.current_max_iterations >= limits.min_iterations


def test_progress_summary():
    """Test progress summary generation."""
    limits = AdaptiveLimits(default_max_iterations=5)

    limits.record_iteration(True, True, {"test": True})
    limits.record_iteration(False, True, {"test": False})
    limits.record_iteration(True, True, {"test": True})

    summary = limits.get_progress_summary()

    assert summary["iterations"] == 3
    assert summary["success_rate"] == 2 / 3
    assert summary["progress_rate"] == 1.0  # All had progress


def test_reset():
    """Test limits reset."""
    limits = AdaptiveLimits(default_max_iterations=5)

    limits.record_iteration(True, True, {"test": True})
    limits.record_iteration(True, True, {"test": True})

    limits.reset()

    assert limits.iterations_completed == 0
    assert len(limits.history) == 0
    assert limits.current_max_iterations == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
