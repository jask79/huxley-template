"""
Vitest output normalizer.

Converts Vitest test output into structured NormalizedFeedback.
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


class VitestNormalizer(FeedbackNormalizer):
    """Normalize Vitest output to structured feedback."""

    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Parse Vitest output.

        Expected raw_output format:
        {
            'exit_code': int,
            'stdout': str,
            'stderr': str,
            'tool': 'vitest' (optional)
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
            feedback_source="vitest",
            stdout=stdout,
            stderr=stderr,
            timestamp=time.time(),
            tool_version=self._get_vitest_version(stdout),
            auto_summary=auto_summary,
        )

    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score for Vitest feedback."""
        has_file_info = any(f.file_path is not None for f in feedback.salient_fragments)
        return self._compute_base_quality(
            feedback.salient_fragments, feedback.stdout, has_file_info
        )

    def _parse_failures(self, stdout: str, stderr: str) -> list[dict[str, Any]]:
        """
        Extract failure information from Vitest output.

        Returns list of dicts with keys: test, error, file, line
        """
        failures = []

        # Pattern 1: ❌ test_name > nested_test
        #            Error: Expected ...
        #            at file.test.ts:123:45
        test_pattern = r"❌\s+([^\n]+)\n\s+([^\n]+)\n\s+at\s+([^:]+):(\d+):(\d+)"

        for match in re.finditer(test_pattern, stdout, re.MULTILINE):
            test_name = match.group(1).strip()
            error_msg = match.group(2).strip()
            file_path = match.group(3).strip()
            line_num = int(match.group(4))

            failures.append(
                {"test": test_name, "error": error_msg, "file": file_path, "line": line_num}
            )

        # Pattern 2: FAIL tests/Button.test.tsx > Button > renders correctly
        fail_pattern = r"FAIL\s+([^\s>]+)\s+>\s+([^\n]+)\n([^\n]+)"

        for match in re.finditer(fail_pattern, stdout, re.MULTILINE):
            file_path = match.group(1).strip()
            test_name = match.group(2).strip()
            error_msg = match.group(3).strip()

            failures.append(
                {
                    "test": f"{file_path} > {test_name}",
                    "error": error_msg,
                    "file": file_path,
                    "line": None,
                }
            )

        # Pattern 3: AssertionError with expect statements
        assertion_pattern = r"AssertionError:\s*expected\s+([^\n]+)\s+to\s+([^\n]+)"

        for match in re.finditer(assertion_pattern, stdout + stderr, re.MULTILINE):
            expected = match.group(1).strip()
            condition = match.group(2).strip()

            failures.append(
                {
                    "test": "assertion",
                    "error": f"AssertionError: expected {expected} to {condition}",
                    "file": None,
                    "line": None,
                }
            )

        # Pattern 4: Timeout errors
        timeout_pattern = r"Test\s+timed\s+out\s+in\s+(\d+)ms"

        for match in re.finditer(timeout_pattern, stdout + stderr, re.MULTILINE):
            timeout_ms = match.group(1)

            failures.append(
                {
                    "test": "timeout",
                    "error": f"Test timed out in {timeout_ms}ms",
                    "file": None,
                    "line": None,
                }
            )

        # Pattern 5: Import/module errors
        if "Cannot find module" in stderr or "Module not found" in stdout:
            import_error_match = re.search(
                r'Cannot find module\s+[\'"]([^\'"]+)[\'"]', stderr + stdout
            )
            if import_error_match:
                module = import_error_match.group(1)
                failures.append(
                    {
                        "test": "import",
                        "error": f"Cannot find module '{module}'",
                        "file": None,
                        "line": None,
                    }
                )

        # Pattern 6: ReferenceError (undefined variables/functions)
        ref_error_pattern = r"ReferenceError:\s+([^\s]+)\s+is\s+not\s+defined"

        for match in re.finditer(ref_error_pattern, stdout + stderr, re.MULTILINE):
            variable = match.group(1).strip()

            failures.append(
                {
                    "test": "reference",
                    "error": f"ReferenceError: {variable} is not defined",
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

        # Missing external dependencies
        if "Cannot find module" in stderr or "Module not found" in stdout:
            # Check if it's an external module (not relative import)
            if not any(pattern in stderr + stdout for pattern in ["./", "../", "@/"]):
                return True, DeterministicBlocker.MISSING_EXTERNAL_DEP

        # Service connection errors
        if any(
            err in stderr or err in stdout
            for err in [
                "ECONNREFUSED",
                "Connection refused",
                "Unable to connect",
                "Service unavailable",
                "Network error",
            ]
        ):
            return True, DeterministicBlocker.SERVICE_DOWN

        # Browser/Playwright errors (if using browser testing)
        if any(
            err in stderr or err in stdout
            for err in [
                "Browser executable not found",
                "Failed to launch browser",
                "browserType.launch",
            ]
        ):
            return True, DeterministicBlocker.MISSING_EXTERNAL_DEP

        return False, None

    def _determine_category(
        self, failures: list[dict], stderr: str, exit_code: int
    ) -> FeedbackCategory:
        """Determine failure category from failures."""

        if exit_code == 0:
            return FeedbackCategory.UNKNOWN

        # Check for import/module errors
        if any(
            "import" in f["test"].lower() or "Cannot find module" in f["error"] for f in failures
        ):
            return FeedbackCategory.MISSING_DEPENDENCY

        # Check for permission errors
        if "Permission denied" in stderr:
            return FeedbackCategory.PERMISSION_DENIED

        # Check for timeout
        if any(
            "timeout" in f["test"].lower() or "timed out" in f["error"].lower() for f in failures
        ):
            return FeedbackCategory.TIMEOUT

        # Check for runtime errors
        if any(err in stderr for err in ["ReferenceError", "TypeError", "SyntaxError"]):
            return FeedbackCategory.RUNTIME_ERROR

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

    def _get_vitest_version(self, stdout: str) -> str | None:
        """Extract Vitest version from output."""
        # Pattern: Vitest v1.2.3
        match = re.search(r"[Vv]itest\s+v?(\d+\.\d+\.\d+)", stdout)
        return match.group(1) if match else None
