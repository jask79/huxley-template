"""
Normalizer for API test output.

Parses API test failures (pytest with requests library) and extracts
structured error information about endpoint failures.
"""

import re
from typing import Any

from core.feedback_schema import (
    DeterministicBlocker,
    FeedbackCategory,
    NormalizedFeedback,
    SalientFragment,
)
from feedback.normalizers.base import FeedbackNormalizer


class ApiTestNormalizer(FeedbackNormalizer):
    """Parse and normalize API test output (pytest + requests)."""

    # Pytest test failure patterns
    TEST_FAILURE_PATTERN = re.compile(r"^(?P<file>[^\s]+)::(?P<test>\S+)\s+FAILED")

    # HTTP error patterns
    STATUS_CODE_PATTERN = re.compile(
        r"(?:AssertionError|assert)\s+(?P<actual>\d+)\s*(?:!=|==)\s*(?P<expected>\d+)"
    )

    ENDPOINT_PATTERN = re.compile(r"(?:GET|POST|PUT|DELETE|PATCH)\s+(?P<endpoint>/[^\s]+)")

    # Critical HTTP status codes that block functionality
    CRITICAL_STATUSES = {500, 502, 503}
    CRITICAL_ERROR_TYPES = {"connection_error", "timeout", "internal_server_error"}

    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Normalize pytest API test output into structured feedback.

        Args:
            raw_output: Dict with 'stdout', 'stderr', 'exit_code'

        Returns:
            NormalizedFeedback with parsed API test failures
        """
        stdout = raw_output.get("stdout", "")
        stderr = raw_output.get("stderr", "")
        exit_code = raw_output.get("exit_code", 0)

        output = stdout + "\n" + stderr
        failures = self._extract_test_failures(output)
        fragments = self._failures_to_fragments(failures)

        # Connection/service errors are deterministic blockers
        is_blocker = any(
            f.get("error_type") in self.CRITICAL_ERROR_TYPES for f in failures
        )
        blocker_type = DeterministicBlocker.SERVICE_DOWN if is_blocker else None

        success = exit_code == 0 and len(fragments) == 0

        signal_quality = self.compute_signal_quality(
            NormalizedFeedback(
                success=success,
                exit_code=exit_code,
                category=FeedbackCategory.TEST_FAILURE,
                is_deterministic_blocker=is_blocker,
                blocker_type=blocker_type,
                salient_fragments=fragments,
                suggested_scope=self._suggest_scope(failures),
                signal_quality_score=0.5,  # placeholder
                feedback_source="pytest_api",
                stdout=stdout,
                stderr=stderr,
            )
        )

        return NormalizedFeedback(
            success=success,
            exit_code=exit_code,
            category=FeedbackCategory.TEST_FAILURE,
            is_deterministic_blocker=is_blocker,
            blocker_type=blocker_type,
            salient_fragments=fragments,
            suggested_scope=self._suggest_scope(failures),
            signal_quality_score=signal_quality,
            feedback_source="pytest_api",
            stdout=stdout,
            stderr=stderr,
        )

    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score based on fragment detail."""
        has_file_info = any(f.file_path for f in feedback.salient_fragments)
        full_output = feedback.stdout + feedback.stderr
        return self._compute_base_quality(
            feedback.salient_fragments, full_output, has_file_info=has_file_info
        )

    def _extract_test_failures(self, output: str) -> list[dict[str, Any]]:
        """Extract test failure details from pytest output."""
        failures = []
        lines = output.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i]
            match = self.TEST_FAILURE_PATTERN.search(line)
            if match:
                failure: dict[str, Any] = {
                    "file": match.group("file"),
                    "test": match.group("test"),
                    "message": line.strip(),
                }

                # Look ahead up to 30 lines for error context
                context_lines = lines[i + 1 : i + 31]
                context_str = "\n".join(context_lines)

                status_match = self.STATUS_CODE_PATTERN.search(context_str)
                if status_match:
                    failure["expected_status"] = int(status_match.group("expected"))
                    failure["actual_status"] = int(status_match.group("actual"))
                    failure["error_type"] = "status_code_mismatch"

                endpoint_match = self.ENDPOINT_PATTERN.search(context_str)
                if endpoint_match:
                    failure["endpoint"] = endpoint_match.group("endpoint")

                if "ConnectionError" in context_str:
                    failure["error_type"] = "connection_error"
                elif "Timeout" in context_str:
                    failure["error_type"] = "timeout"
                elif "JSONDecodeError" in context_str:
                    failure["error_type"] = "json_parse_error"
                elif "ValidationError" in context_str:
                    failure["error_type"] = "validation_error"

                failures.append(failure)

            i += 1

        return failures

    def _failures_to_fragments(self, failures: list[dict[str, Any]]) -> list[SalientFragment]:
        """Convert failure dicts into SalientFragment instances."""
        fragments = []
        for failure in failures:
            error_type = failure.get("error_type", "unknown")
            actual_status = failure.get("actual_status")

            is_critical = (
                error_type in self.CRITICAL_ERROR_TYPES
                or actual_status in self.CRITICAL_STATUSES
            )
            severity = "error" if is_critical else "warning"

            endpoint = failure.get("endpoint", "")
            expected = failure.get("expected_status")
            actual = failure.get("actual_status")

            if expected and actual:
                context = f"expected {expected}, got {actual}"
                if endpoint:
                    context = f"{endpoint}: {context}"
            else:
                context = endpoint or error_type or ""

            fragments.append(
                SalientFragment(
                    message=failure.get("message", "Test failure"),
                    severity=severity,
                    file_path=failure.get("file"),
                    context=context,
                )
            )
        return fragments

    def _suggest_scope(self, failures: list[dict[str, Any]]) -> str | None:
        """Suggest the endpoint or file that needs attention."""
        for failure in failures:
            if failure.get("endpoint"):
                return failure["endpoint"]
        for failure in failures:
            if failure.get("file"):
                return failure["file"]
        return None


# Register with feedback registry
def register(registry):
    """Register API test normalizer with the feedback registry."""
    registry.register_normalizer("pytest_api", ApiTestNormalizer())
