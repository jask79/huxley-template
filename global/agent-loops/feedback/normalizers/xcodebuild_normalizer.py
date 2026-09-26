"""
Xcode build output normalizer.

Converts xcodebuild compilation output into structured NormalizedFeedback.
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


class XcodeBuildNormalizer(FeedbackNormalizer):
    """Normalize Xcode build output to structured feedback."""

    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Parse xcodebuild output.

        Expected raw_output format:
        {
            'exit_code': int,
            'stdout': str,
            'stderr': str,
            'tool': 'xcodebuild' (optional)
        }
        """
        exit_code = raw_output["exit_code"]
        stdout = raw_output.get("stdout", "")
        stderr = raw_output.get("stderr", "")

        # Parse build errors and warnings
        issues = self._parse_build_output(stdout, stderr)
        salient_fragments = self._extract_salient_fragments(issues)

        # Determine category
        category = self._determine_category(issues, stderr, exit_code)

        # Check for deterministic blockers
        is_blocker, blocker_type = self._check_deterministic_blockers(stderr, stdout)

        # Compute quality score
        has_file_info = any(f.file_path is not None for f in salient_fragments)
        signal_quality = self._compute_base_quality(salient_fragments, stdout, has_file_info)

        # Generate summary if needed
        auto_summary = self._generate_summary(issues) if len(stdout) > 5000 else ""

        return NormalizedFeedback(
            success=exit_code == 0,
            exit_code=exit_code,
            category=category,
            is_deterministic_blocker=is_blocker,
            blocker_type=blocker_type,
            salient_fragments=salient_fragments,
            suggested_scope=self._suggest_scope(issues),
            signal_quality_score=signal_quality,
            feedback_source="xcodebuild",
            stdout=stdout,
            stderr=stderr,
            timestamp=time.time(),
            tool_version=self._get_xcode_version(stdout),
            auto_summary=auto_summary,
        )

    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score for Xcode feedback."""
        has_file_info = any(f.file_path is not None for f in feedback.salient_fragments)
        return self._compute_base_quality(
            feedback.salient_fragments, feedback.stdout, has_file_info
        )

    def _parse_build_output(self, stdout: str, stderr: str) -> list[dict[str, Any]]:
        """
        Parse Xcode build output for errors and warnings.

        Example formats:
          /path/to/File.swift:42:10: error: use of unresolved identifier 'foo'
          /path/to/File.swift:15:5: warning: variable 'bar' was never used
        """
        issues = []

        # Combine stdout and stderr
        full_output = stdout + "\n" + stderr

        # Pattern for Swift/Obj-C compiler errors
        # Format: /path/to/file.swift:line:column: error/warning: message
        error_pattern = r"^(.+?):(\d+):(\d+):\s+(error|warning):\s+(.+?)$"

        for match in re.finditer(error_pattern, full_output, re.MULTILINE):
            file_path = match.group(1).strip()
            line_num = int(match.group(2))
            col_num = int(match.group(3))
            severity = match.group(4)  # error or warning
            message = match.group(5).strip()

            issues.append(
                {
                    "file": file_path,
                    "line": line_num,
                    "column": col_num,
                    "severity": severity,
                    "message": message,
                }
            )

        # Pattern for linker errors (ld)
        # Format: ld: framework not found SomeFramework
        linker_pattern = r"ld:\s+(.+?)$"

        for match in re.finditer(linker_pattern, full_output, re.MULTILINE):
            message = match.group(1).strip()

            issues.append(
                {
                    "file": None,
                    "line": None,
                    "column": None,
                    "severity": "error",
                    "message": f"Linker error: {message}",
                }
            )

        # Pattern for missing dependency errors
        # Format: error: unable to load standard library for target
        missing_dep_pattern = r"error:\s+(?:unable to load|missing|could not find)\s+(.+?)$"

        for match in re.finditer(missing_dep_pattern, full_output, re.MULTILINE):
            message = match.group(0).strip()

            if not any(issue["message"] == message for issue in issues):
                issues.append(
                    {
                        "file": None,
                        "line": None,
                        "column": None,
                        "severity": "error",
                        "message": message,
                    }
                )

        # Pattern for provisioning profile errors
        provision_pattern = r"error:\s+.*?(?:provisioning profile|signing|certificate).*?$"

        for match in re.finditer(provision_pattern, full_output, re.MULTILINE | re.IGNORECASE):
            message = match.group(0).strip()

            if not any(issue["message"] == message for issue in issues):
                issues.append(
                    {
                        "file": None,
                        "line": None,
                        "column": None,
                        "severity": "error",
                        "message": message,
                    }
                )

        return issues

    def _extract_salient_fragments(self, issues: list[dict]) -> list[SalientFragment]:
        """Convert issues to salient fragments."""
        fragments = []

        # Prioritize errors over warnings
        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]

        # Take up to 15 errors and 5 warnings
        important_issues = errors[:15] + warnings[:5]

        for issue in important_issues:
            context = ""
            if issue.get("file"):
                context = f"{issue['file']}"
                if issue.get("line"):
                    context += f":{issue['line']}"

            fragments.append(
                SalientFragment(
                    message=issue["message"],
                    severity=issue["severity"],
                    line_number=issue.get("line"),
                    file_path=issue.get("file"),
                    context=context,
                )
            )

        return fragments

    def _check_deterministic_blockers(
        self, stderr: str, stdout: str
    ) -> tuple[bool, DeterministicBlocker | None]:
        """Check for blockers that require immediate escalation."""

        full_output = stdout + "\n" + stderr

        # Permission/signing errors
        if any(
            term in full_output
            for term in [
                "No signing certificate",
                "valid signing identity",
                "codesign failed",
                "Permission denied",
            ]
        ):
            return True, DeterministicBlocker.PERMISSION_DENIED

        # Missing SDK/toolchain
        if any(
            term in full_output
            for term in ["unable to load standard library", "SDK not found", "toolchain not found"]
        ):
            return True, DeterministicBlocker.MISSING_EXTERNAL_DEP

        # Service/connection errors
        if any(
            term in full_output
            for term in ["Unable to connect to", "connection refused", "service unavailable"]
        ):
            return True, DeterministicBlocker.SERVICE_DOWN

        return False, None

    def _determine_category(
        self, issues: list[dict], stderr: str, exit_code: int
    ) -> FeedbackCategory:
        """Determine failure category from issues."""

        if exit_code == 0:
            return FeedbackCategory.UNKNOWN

        full_output = stderr

        # Check for missing dependencies
        if any(
            term in full_output
            for term in [
                "unable to load standard library",
                "framework not found",
                "module not found",
            ]
        ):
            return FeedbackCategory.MISSING_DEPENDENCY

        # Check for permission/signing errors
        if any(term in full_output for term in ["signing", "certificate", "provisioning profile"]):
            return FeedbackCategory.PERMISSION_DENIED

        # Check for build errors
        if any(i["severity"] == "error" for i in issues):
            # Check if it's type errors
            if any("type" in i["message"].lower() for i in issues):
                return FeedbackCategory.TYPE_ERROR
            return FeedbackCategory.BUILD_ERROR

        # Default to validation error if we have warnings
        if len(issues) > 0:
            return FeedbackCategory.LINT_WARNING

        return FeedbackCategory.BUILD_ERROR

    def _suggest_scope(self, issues: list[dict]) -> str | None:
        """Suggest which file/function to focus on."""
        if len(issues) == 0:
            return None

        # Count issues per file (only for issues with file info)
        file_counts = {}
        for issue in issues:
            file_path = issue.get("file")
            if file_path:
                file_counts[file_path] = file_counts.get(file_path, 0) + 1

        if not file_counts:
            return None

        # Return file with most issues
        most_common = max(file_counts.items(), key=lambda x: x[1])
        return most_common[0]

    def _generate_summary(self, issues: list[dict]) -> str:
        """Generate summary for sprawling output."""
        if len(issues) == 0:
            return "Build completed successfully"

        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")

        summary_parts = []
        if error_count > 0:
            summary_parts.append(f"{error_count} error(s)")
        if warning_count > 0:
            summary_parts.append(f"{warning_count} warning(s)")

        summary = "Build failed with " + " and ".join(summary_parts)

        # Add file count if available
        unique_files = len(set(i.get("file") for i in issues if i.get("file")))
        if unique_files > 0:
            summary += f" across {unique_files} file(s)"

        return summary

    def _get_xcode_version(self, stdout: str) -> str | None:
        """Extract Xcode version from output."""
        # Look for Xcode version in build settings output
        match = re.search(r"Xcode\s+(\d+\.\d+(?:\.\d+)?)", stdout)
        if match:
            return match.group(1)

        # Look for build version
        match = re.search(r"Build version\s+(\d+\w+)", stdout)
        if match:
            return match.group(1)

        return None
