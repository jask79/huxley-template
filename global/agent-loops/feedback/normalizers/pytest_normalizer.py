"""
Pytest output normalizer.

Converts pytest test output into structured NormalizedFeedback.
"""

import re
import time
from typing import Any

from core.feedback_schema import (
    DeterministicBlocker,
    FeedbackCategory,
    NormalizedFeedback,
    SalientFragment,
)
from feedback.normalizers.base import FeedbackNormalizer


class PytestNormalizer(FeedbackNormalizer):
    """Normalize pytest output to structured feedback."""

    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Parse pytest output.

        Expected raw_output format:
        {
            'exit_code': int,
            'stdout': str,
            'stderr': str,
            'tool': 'pytest' (optional)
        }
        """
        exit_code = raw_output["exit_code"]
        stdout = raw_output.get("stdout", "")
        stderr = raw_output.get("stderr", "")

        # Parse test results
        failures = self._parse_failures(stdout, stderr)
        salient_fragments = self._extract_salient_fragments(failures)

        # Determine category
        category = self._determine_category(failures, stderr, exit_code)

        # Check for deterministic blockers
        is_blocker, blocker_type = self._check_deterministic_blockers(stderr, stdout)

        # Compute quality score
        has_file_info = any(f.file_path is not None for f in salient_fragments)
        signal_quality = self._compute_base_quality(salient_fragments, stdout, has_file_info)

        # Generate summary if needed
        auto_summary = self._generate_summary(failures) if len(stdout) > 2000 else ""

        return NormalizedFeedback(
            success=exit_code == 0,
            exit_code=exit_code,
            category=category,
            is_deterministic_blocker=is_blocker,
            blocker_type=blocker_type,
            salient_fragments=salient_fragments,
            suggested_scope=self._suggest_scope(failures),
            signal_quality_score=signal_quality,
            feedback_source="pytest",
            stdout=stdout,
            stderr=stderr,
            timestamp=time.time(),
            tool_version=self._get_pytest_version(stdout),
            auto_summary=auto_summary,
        )

    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score for pytest feedback."""
        has_file_info = any(f.file_path is not None for f in feedback.salient_fragments)
        return self._compute_base_quality(
            feedback.salient_fragments, feedback.stdout, has_file_info
        )

    def _parse_failures(self, stdout: str, stderr: str) -> list[dict[str, Any]]:
        """
        Extract failure information from pytest output.

        Returns list of dicts with keys: test, error, file, line
        """
        failures = []

        # Pattern 1: FAILED test_file.py::TestClass::test_method - AssertionError
        failure_pattern = r"FAILED\s+([^\s]+)\s+-\s+(.+?)(?=\n|$)"

        for match in re.finditer(failure_pattern, stdout, re.MULTILINE):
            test_name = match.group(1).strip()
            error_msg = match.group(2).strip()

            file_path, line_num = self._extract_file_and_line(test_name)

            failures.append(
                {"test": test_name, "error": error_msg, "file": file_path, "line": line_num}
            )

        # Pattern 2: ERROR collecting - for collection errors
        error_pattern = r"ERROR\s+([^\s]+)\s+-\s+(.+?)(?=\n|$)"

        for match in re.finditer(error_pattern, stdout, re.MULTILINE):
            location = match.group(1).strip()
            error_msg = match.group(2).strip()

            file_path, line_num = self._extract_file_and_line(location)

            failures.append(
                {
                    "test": location,
                    "error": f"Collection error: {error_msg}",
                    "file": file_path,
                    "line": line_num,
                }
            )

        # Pattern 3: Check stderr for import errors
        if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
            import_error_match = re.search(r"(ModuleNotFoundError|ImportError):\s*(.+)", stderr)
            if import_error_match:
                failures.append(
                    {
                        "test": "import",
                        "error": import_error_match.group(0),
                        "file": None,
                        "line": None,
                    }
                )

        return failures

    def _extract_salient_fragments(self, failures: list[dict]) -> list[SalientFragment]:
        """Convert failures to salient fragments."""
        fragments = []

        for failure in failures:
            fragments.append(
                SalientFragment(
                    message=failure["error"],
                    severity="error",
                    line_number=failure.get("line"),
                    file_path=failure.get("file"),
                    context=failure["test"],
                )
            )

        return fragments

    def _check_deterministic_blockers(
        self, stderr: str, stdout: str
    ) -> tuple[bool, DeterministicBlocker | None]:
        """Check for blockers that require immediate escalation."""

        # Permission errors
        if "Permission denied" in stderr or "EACCES" in stderr:
            return True, DeterministicBlocker.PERMISSION_DENIED

        # Missing external dependencies (not pip installable)
        if "ModuleNotFoundError" in stderr:
            # Check if it's a system dependency
            if any(pkg in stderr for pkg in ["_sqlite3", "_ctypes", "_ssl"]):
                return True, DeterministicBlocker.MISSING_EXTERNAL_DEP

        # Service connection errors
        if any(
            err in stderr or err in stdout
            for err in [
                "Connection refused",
                "Unable to connect",
                "Service unavailable",
                "ECONNREFUSED",
            ]
        ):
            return True, DeterministicBlocker.SERVICE_DOWN

        return False, None

    def _determine_category(
        self, failures: list[dict], stderr: str, exit_code: int
    ) -> FeedbackCategory:
        """Determine failure category from failures."""

        if exit_code == 0:
            return FeedbackCategory.UNKNOWN

        # Check for import/collection errors
        if any("import" in f["test"].lower() for f in failures):
            return FeedbackCategory.MISSING_DEPENDENCY

        # Check for permission errors
        if "Permission denied" in stderr:
            return FeedbackCategory.PERMISSION_DENIED

        # Check for timeout
        if "timeout" in stderr.lower():
            return FeedbackCategory.TIMEOUT

        # Default to test failure
        if len(failures) > 0:
            return FeedbackCategory.TEST_FAILURE

        return FeedbackCategory.UNKNOWN

    def _suggest_scope(self, failures: list[dict]) -> str | None:
        """Suggest which file/function to focus on."""
        if len(failures) == 0:
            return None

        # If all failures in same file, suggest that file
        files = set(f.get("file") for f in failures if f.get("file"))
        if len(files) == 1:
            return list(files)[0]

        # If multiple files, suggest the one with most failures
        if len(files) > 1:
            file_counts = {}
            for f in failures:
                file_path = f.get("file")
                if file_path:
                    file_counts[file_path] = file_counts.get(file_path, 0) + 1

            most_common = max(file_counts.items(), key=lambda x: x[1])
            return most_common[0]

        return None

    def _generate_summary(self, failures: list[dict]) -> str:
        """Generate summary for sprawling output."""
        if len(failures) == 0:
            return "No test failures detected"

        summary = f"{len(failures)} test failure(s): "
        test_names = [f["test"] for f in failures[:3]]
        summary += ", ".join(test_names)

        if len(failures) > 3:
            summary += f" and {len(failures) - 3} more"

        return summary

    def _extract_file_and_line(self, test_name: str) -> tuple[str | None, int | None]:
        """
        Extract file path and line number from test name.

        Examples:
          tests/test_foo.py::TestClass::test_method -> (tests/test_foo.py, None)
          tests/test_foo.py:123::test_method -> (tests/test_foo.py, 123)
        """
        # Split by ::
        parts = test_name.split("::")
        if len(parts) == 0:
            return None, None

        file_part = parts[0]

        # Check for line number
        if ":" in file_part:
            file_path, line_str = file_part.rsplit(":", 1)
            try:
                line_num = int(line_str)
                return file_path, line_num
            except ValueError:
                return file_part, None

        return file_part, None

    def _get_pytest_version(self, stdout: str) -> str | None:
        """Extract pytest version from output."""
        match = re.search(r"pytest[- ](\d+\.\d+\.\d+)", stdout)
        return match.group(1) if match else None
