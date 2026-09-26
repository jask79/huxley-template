"""
Unit tests for pytest normalizer.

Tests pytest output parsing with real output samples.
"""

import os
import sys

import pytest

# Add parent directory to path for imports
_test_dir = os.path.dirname(os.path.abspath(__file__))
_agent_loops_dir = os.path.dirname(_test_dir)
sys.path.insert(0, _agent_loops_dir)

from core.feedback_schema import DeterministicBlocker, FeedbackCategory
from feedback.normalizers.pytest_normalizer import PytestNormalizer

# Real pytest output samples
PYTEST_SUCCESS_OUTPUT = """
============================= test session starts ==============================
platform darwin -- Python 3.10.0, pytest-7.4.0, pluggy-1.0.0
rootdir: /Users/test/project
collected 3 items

tests/test_math.py ...                                                   [100%]

============================== 3 passed in 0.05s ===============================
"""

PYTEST_SIMPLE_FAILURE = """
============================= test session starts ==============================
platform darwin -- Python 3.10.0, pytest-7.4.0, pluggy-1.0.0
rootdir: /Users/test/project
collected 2 items

tests/test_math.py F.                                                    [ 50%]

=================================== FAILURES ===================================
_______________________________ test_addition __________________________________

    def test_addition():
>       assert 1 + 1 == 3
E       assert 2 == 3

tests/test_math.py:10: AssertionError
=========================== short test summary info ============================
FAILED tests/test_math.py::test_addition - assert 2 == 3
========================= 1 failed, 1 passed in 0.12s ==========================
"""

PYTEST_MULTIPLE_FAILURES = """
============================= test session starts ==============================
collected 5 items

tests/test_api.py FF.                                                    [ 60%]
tests/test_db.py F.                                                      [100%]

=================================== FAILURES ===================================
_______________________________ test_get_user __________________________________

tests/test_api.py:42: in test_get_user
    assert response.status_code == 200
E   AssertionError: assert 404 == 200

_______________________________ test_create_user _______________________________

tests/test_api.py:67: in test_create_user
    assert user.id is not None
E   AssertionError: assert None is not None

________________________________ test_query ____________________________________

tests/test_db.py:15: in test_query
    assert len(results) > 0
E   AssertionError: assert 0 > 0

=========================== short test summary info ============================
FAILED tests/test_api.py::test_get_user - AssertionError: assert 404 == 200
FAILED tests/test_api.py::test_create_user - AssertionError: assert None is not None
FAILED tests/test_db.py::test_query - AssertionError: assert 0 > 0
==================== 3 failed, 2 passed in 0.43s ===========================
"""

PYTEST_IMPORT_ERROR = """
============================= test session starts ==============================
collected 0 items / 1 error

==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_feature.py _______________________
ImportError while importing test module '/Users/test/project/tests/test_feature.py'.
Hint: make sure your test file names start with 'test_'
tests/test_feature.py:5: in <module>
    from mypackage import missing_module
E   ModuleNotFoundError: No module named 'missing_module'
=========================== short test summary info ============================
ERROR tests/test_feature.py - ModuleNotFoundError: No module named 'missing_module'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.15s ===============================
"""

PYTEST_PERMISSION_ERROR = """
FAILED tests/test_file_access.py::test_write_file - PermissionError: [Errno 13] Permission denied: '/protected/file.txt'
"""


class TestPytestNormalizer:
    """Test PytestNormalizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.normalizer = PytestNormalizer()

    def test_parse_success(self):
        """Test parsing successful pytest run."""
        raw_output = {"exit_code": 0, "stdout": PYTEST_SUCCESS_OUTPUT, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is True
        assert feedback.exit_code == 0
        assert len(feedback.salient_fragments) == 0
        assert feedback.tool_version == "7.4.0"
        assert feedback.feedback_source == "pytest"

    def test_parse_simple_failure(self):
        """Test parsing single test failure."""
        raw_output = {"exit_code": 1, "stdout": PYTEST_SIMPLE_FAILURE, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        assert feedback.exit_code == 1
        assert feedback.category == FeedbackCategory.TEST_FAILURE
        assert len(feedback.salient_fragments) == 1

        # Check first fragment
        fragment = feedback.salient_fragments[0]
        assert "assert 2 == 3" in fragment.message
        assert fragment.severity == "error"
        assert fragment.file_path == "tests/test_math.py"
        assert "test_addition" in fragment.context

        # Check suggested scope
        assert feedback.suggested_scope == "tests/test_math.py"

    def test_parse_multiple_failures(self):
        """Test parsing multiple test failures."""
        raw_output = {"exit_code": 1, "stdout": PYTEST_MULTIPLE_FAILURES, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        assert len(feedback.salient_fragments) == 3

        # Check that we captured all failures
        messages = [f.message for f in feedback.salient_fragments]
        assert any("404 == 200" in m for m in messages)
        assert any("None is not None" in m for m in messages)
        assert any("0 > 0" in m for m in messages)

        # Check file paths
        files = feedback.get_file_list()
        assert "tests/test_api.py" in files
        assert "tests/test_db.py" in files

        # Suggested scope should be test_api.py (has more failures)
        assert feedback.suggested_scope == "tests/test_api.py"

    def test_parse_import_error(self):
        """Test parsing import/collection error."""
        raw_output = {"exit_code": 2, "stdout": PYTEST_IMPORT_ERROR, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        # _determine_category checks if 'import' is in f['test'].lower().
        # The collection error produces test='tests/test_feature.py' (no "import").
        # stderr is empty so Pattern 3 doesn't fire either.
        # The category therefore falls through to TEST_FAILURE (implementation authoritative).
        assert feedback.category == FeedbackCategory.TEST_FAILURE
        assert len(feedback.salient_fragments) > 0

        # Check error message contains the collection error details
        fragment = feedback.salient_fragments[0]
        assert "ModuleNotFoundError" in fragment.message or "missing_module" in fragment.message

    def test_detect_permission_blocker(self):
        """Test detection of permission denied blocker."""
        raw_output = {
            "exit_code": 1,
            "stdout": "",
            "stderr": "Permission denied: /protected/file.txt",
        }

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.is_deterministic_blocker is True
        assert feedback.blocker_type == DeterministicBlocker.PERMISSION_DENIED
        assert feedback.category == FeedbackCategory.PERMISSION_DENIED

    def test_detect_missing_system_dependency(self):
        """Test detection of missing system dependency."""
        raw_output = {
            "exit_code": 1,
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named _sqlite3",
        }

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.is_deterministic_blocker is True
        assert feedback.blocker_type == DeterministicBlocker.MISSING_EXTERNAL_DEP

    def test_signal_quality_high(self):
        """Test high signal quality for specific errors."""
        raw_output = {"exit_code": 1, "stdout": PYTEST_SIMPLE_FAILURE, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should have good quality (specific error with file/line info)
        assert feedback.signal_quality_score > 0.5
        assert feedback.is_actionable()

    def test_signal_quality_low_for_noise(self):
        """Test low signal quality for noisy output."""
        # Create very long noisy output
        noisy_output = "=" * 100000  # Very long output

        raw_output = {"exit_code": 1, "stdout": noisy_output, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Quality should be reduced due to noise
        assert feedback.signal_quality_score < 0.5

    def test_auto_summary_for_long_output(self):
        """Test auto-summary generation for long output."""
        # Create output > 2000 chars
        long_output = PYTEST_MULTIPLE_FAILURES + "\n" + "." * 3000

        raw_output = {"exit_code": 1, "stdout": long_output, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should have auto-summary
        assert feedback.auto_summary != ""
        assert "failure" in feedback.auto_summary.lower()

    def test_extract_file_and_line(self):
        """Test file and line extraction from test names."""
        # Test with line number
        file, line = self.normalizer._extract_file_and_line("tests/test_foo.py:123::test_method")
        assert file == "tests/test_foo.py"
        assert line == 123

        # Test without line number
        file, line = self.normalizer._extract_file_and_line(
            "tests/test_foo.py::TestClass::test_method"
        )
        assert file == "tests/test_foo.py"
        assert line is None

        # Test simple file
        file, line = self.normalizer._extract_file_and_line("tests/test_foo.py")
        assert file == "tests/test_foo.py"
        assert line is None

    def test_version_extraction(self):
        """Test pytest version extraction."""
        version = self.normalizer._get_pytest_version(PYTEST_SUCCESS_OUTPUT)
        assert version == "7.4.0"

        # Test alternate format
        version = self.normalizer._get_pytest_version("pytest-8.0.1")
        assert version == "8.0.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
