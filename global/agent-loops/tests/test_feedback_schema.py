"""
Unit tests for feedback schema.

Tests all enums, dataclasses, and quality scoring methods.
"""

import os
import sys

import pytest

# Add parent directory to path for imports
_test_dir = os.path.dirname(os.path.abspath(__file__))
_agent_loops_dir = os.path.dirname(_test_dir)
sys.path.insert(0, _agent_loops_dir)

from core.feedback_schema import (
    DeterministicBlocker,
    FeedbackCategory,
    NormalizedFeedback,
    SalientFragment,
)


class TestFeedbackCategory:
    """Test FeedbackCategory enum."""

    def test_all_categories_exist(self):
        """Verify all expected categories exist."""
        expected = {
            "BUILD_ERROR",
            "TEST_FAILURE",
            "LINT_WARNING",
            "TYPE_ERROR",
            "RUNTIME_ERROR",
            "TIMEOUT",
            "PERMISSION_DENIED",
            "MISSING_DEPENDENCY",
            "NETWORK_ERROR",
            "CAPTCHA_FAILURE",
            "VALIDATION_ERROR",
            "UNKNOWN",
        }
        actual = {cat.name for cat in FeedbackCategory}
        assert actual == expected

    def test_category_values(self):
        """Verify category values are snake_case."""
        for category in FeedbackCategory:
            assert category.value.replace("_", "").islower()


class TestDeterministicBlocker:
    """Test DeterministicBlocker enum."""

    def test_all_blockers_exist(self):
        """Verify all expected blockers exist."""
        expected = {
            "PERMISSION_DENIED",
            "MISSING_EXTERNAL_DEP",
            "QUOTA_EXCEEDED",
            "SERVICE_DOWN",
            "SECURITY_VIOLATION",
        }
        actual = {blocker.name for blocker in DeterministicBlocker}
        assert actual == expected


class TestSalientFragment:
    """Test SalientFragment dataclass."""

    def test_create_minimal_fragment(self):
        """Test creating fragment with required fields only."""
        fragment = SalientFragment(message="Test error message", severity="error")
        assert fragment.message == "Test error message"
        assert fragment.severity == "error"
        assert fragment.line_number is None
        assert fragment.file_path is None
        assert fragment.context == ""

    def test_create_full_fragment(self):
        """Test creating fragment with all fields."""
        fragment = SalientFragment(
            message="Undefined variable 'foo'",
            severity="error",
            line_number=42,
            file_path="src/test.py",
            context="def test_function():",
        )
        assert fragment.message == "Undefined variable 'foo'"
        assert fragment.severity == "error"
        assert fragment.line_number == 42
        assert fragment.file_path == "src/test.py"
        assert fragment.context == "def test_function():"

    def test_invalid_severity_raises(self):
        """Test that invalid severity raises ValueError."""
        with pytest.raises(ValueError, match="Invalid severity"):
            SalientFragment(
                message="Test",
                severity="critical",  # Not valid
            )

    def test_valid_severities(self):
        """Test all valid severity values."""
        for severity in ["error", "warning", "info"]:
            fragment = SalientFragment(message="Test", severity=severity)
            assert fragment.severity == severity


class TestNormalizedFeedback:
    """Test NormalizedFeedback dataclass."""

    def test_create_minimal_feedback(self):
        """Test creating feedback with required fields only."""
        feedback = NormalizedFeedback(
            success=False,
            exit_code=1,
            category=FeedbackCategory.TEST_FAILURE,
            is_deterministic_blocker=False,
            blocker_type=None,
            salient_fragments=[],
            suggested_scope=None,
            signal_quality_score=0.5,
            feedback_source="pytest",
            stdout="test output",
            stderr="",
        )
        assert feedback.success is False
        assert feedback.exit_code == 1
        assert feedback.category == FeedbackCategory.TEST_FAILURE
        assert feedback.feedback_source == "pytest"

    def test_quality_score_validation(self):
        """Test that quality score must be 0.0-1.0."""
        # Valid scores
        for score in [0.0, 0.5, 1.0]:
            feedback = NormalizedFeedback(
                success=True,
                exit_code=0,
                category=FeedbackCategory.UNKNOWN,
                is_deterministic_blocker=False,
                blocker_type=None,
                salient_fragments=[],
                suggested_scope=None,
                signal_quality_score=score,
                feedback_source="test",
                stdout="",
                stderr="",
            )
            assert feedback.signal_quality_score == score

        # Invalid scores
        for invalid_score in [-0.1, 1.1, 2.0]:
            with pytest.raises(ValueError, match="signal_quality_score must be between"):
                NormalizedFeedback(
                    success=True,
                    exit_code=0,
                    category=FeedbackCategory.UNKNOWN,
                    is_deterministic_blocker=False,
                    blocker_type=None,
                    salient_fragments=[],
                    suggested_scope=None,
                    signal_quality_score=invalid_score,
                    feedback_source="test",
                    stdout="",
                    stderr="",
                )

    def test_is_actionable(self):
        """Test is_actionable method."""
        # High quality = actionable
        feedback = NormalizedFeedback(
            success=False,
            exit_code=1,
            category=FeedbackCategory.TEST_FAILURE,
            is_deterministic_blocker=False,
            blocker_type=None,
            salient_fragments=[],
            suggested_scope=None,
            signal_quality_score=0.8,
            feedback_source="test",
            stdout="",
            stderr="",
        )
        assert feedback.is_actionable() is True

        # Low quality = not actionable
        feedback.signal_quality_score = 0.3
        assert feedback.is_actionable() is False

    def test_is_noisy(self):
        """Test is_noisy method."""
        # Very low quality = noisy
        feedback = NormalizedFeedback(
            success=False,
            exit_code=1,
            category=FeedbackCategory.TEST_FAILURE,
            is_deterministic_blocker=False,
            blocker_type=None,
            salient_fragments=[],
            suggested_scope=None,
            signal_quality_score=0.2,
            feedback_source="test",
            stdout="",
            stderr="",
        )
        assert feedback.is_noisy() is True

        # Higher quality = not noisy
        feedback.signal_quality_score = 0.5
        assert feedback.is_noisy() is False

    def test_get_primary_error(self):
        """Test get_primary_error method."""
        # No fragments
        feedback = NormalizedFeedback(
            success=False,
            exit_code=1,
            category=FeedbackCategory.TEST_FAILURE,
            is_deterministic_blocker=False,
            blocker_type=None,
            salient_fragments=[],
            suggested_scope=None,
            signal_quality_score=0.5,
            feedback_source="test",
            stdout="",
            stderr="",
        )
        assert feedback.get_primary_error() is None

        # Errors and warnings - should return first error
        error = SalientFragment(message="Error 1", severity="error")
        warning = SalientFragment(message="Warning 1", severity="warning")
        error2 = SalientFragment(message="Error 2", severity="error")

        feedback.salient_fragments = [warning, error, error2]
        primary = feedback.get_primary_error()
        assert primary == error

        # Only warnings - should return first fragment
        feedback.salient_fragments = [warning]
        primary = feedback.get_primary_error()
        assert primary == warning

    def test_get_file_list(self):
        """Test get_file_list method."""
        fragment1 = SalientFragment(message="Error 1", severity="error", file_path="src/file1.py")
        fragment2 = SalientFragment(message="Error 2", severity="error", file_path="src/file2.py")
        fragment3 = SalientFragment(
            message="Error 3",
            severity="error",
            file_path="src/file1.py",  # Duplicate
        )

        feedback = NormalizedFeedback(
            success=False,
            exit_code=1,
            category=FeedbackCategory.TEST_FAILURE,
            is_deterministic_blocker=False,
            blocker_type=None,
            salient_fragments=[fragment1, fragment2, fragment3],
            suggested_scope=None,
            signal_quality_score=0.5,
            feedback_source="test",
            stdout="",
            stderr="",
        )

        files = feedback.get_file_list()
        assert files == ["src/file1.py", "src/file2.py"]  # Sorted and unique

    def test_to_dict(self):
        """Test to_dict serialization."""
        fragment = SalientFragment(
            message="Test error", severity="error", line_number=10, file_path="test.py"
        )

        feedback = NormalizedFeedback(
            success=False,
            exit_code=1,
            category=FeedbackCategory.TEST_FAILURE,
            is_deterministic_blocker=True,
            blocker_type=DeterministicBlocker.PERMISSION_DENIED,
            salient_fragments=[fragment],
            suggested_scope="test.py",
            signal_quality_score=0.8,
            feedback_source="pytest",
            stdout="output",
            stderr="error",
            tool_version="7.4.0",
            auto_summary="1 test failed",
        )

        result = feedback.to_dict()

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert result["category"] == "test_failure"
        assert result["is_deterministic_blocker"] is True
        assert result["blocker_type"] == "permission_denied"
        assert len(result["salient_fragments"]) == 1
        assert result["salient_fragments"][0]["message"] == "Test error"
        assert result["suggested_scope"] == "test.py"
        assert result["signal_quality_score"] == 0.8
        assert result["feedback_source"] == "pytest"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
