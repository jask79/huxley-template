"""
Unit tests for stuck detection.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from safety.stuck_detector import StuckDetector


def test_stuck_detector_initialization():
    """Test stuck detector initialization."""
    detector = StuckDetector()

    assert len(detector.error_history) == 0
    assert len(detector.file_change_history) == 0
    assert len(detector.validation_history) == 0


def test_error_repetition_detection():
    """Test error repetition detection."""
    detector = StuckDetector(error_repetition_threshold=3)

    # Record same error multiple times
    for i in range(4):
        detector.record_error("ImportError: No module named 'foo'", "build_error")

    # Should detect stuck due to repetition
    assert detector._detect_error_repetition()


def test_zero_progress_detection():
    """Test zero progress detection."""
    detector = StuckDetector(zero_progress_window=3)

    # Record multiple iterations with no improvement
    for i in range(4):
        detector.record_validation({"build": False, "test": False})

    # Should detect zero progress
    assert detector._detect_zero_progress()


def test_stuck_not_detected_with_progress():
    """Test that stuck is not detected when progress is made."""
    detector = StuckDetector()

    # Record errors but with different types
    detector.record_error("Error 1", "build_error")
    detector.record_error("Error 2", "test_failure")
    detector.record_error("Error 3", "type_error")

    # Record improving validations
    detector.record_validation({"build": False, "test": False})
    detector.record_validation({"build": True, "test": False})
    detector.record_validation({"build": True, "test": True})

    # Should not detect stuck
    assert not detector.check_stuck()


def test_code_churn_detection():
    """Test code churn detection."""
    detector = StuckDetector(code_churn_threshold=3)

    # Simulate oscillating changes to same file (small tweaks that keep reverting)
    version1 = "def foo():\n    return 1"
    version2 = "def foo():\n    return 2"  # Minor change
    version3 = "def foo():\n    return 1"  # Back to version1
    version4 = "def foo():\n    return 2"  # Back to version2

    # Change back and forth - this represents genuine churn
    detector.record_file_change("test.py", version1)
    detector.record_file_change("test.py", version2)
    detector.record_file_change("test.py", version3)
    detector.record_file_change("test.py", version4)

    # Should detect churn (versions are highly similar, oscillating)
    churning = detector._detect_code_churn()
    assert len(churning) > 0


def test_stuck_summary():
    """Test stuck summary generation."""
    detector = StuckDetector()

    detector.record_error("Error 1", "build_error")
    detector.record_validation({"test": False})

    summary = detector.get_stuck_summary()

    assert "is_stuck" in summary
    assert "error_repetition" in summary
    assert "signals" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
