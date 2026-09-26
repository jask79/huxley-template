"""
ESLint output normalizer.

Converts ESLint linting output into structured NormalizedFeedback.
"""

import json
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


class ESLintNormalizer(FeedbackNormalizer):
    """Normalize ESLint output to structured feedback."""

    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Parse ESLint output.

        Expected raw_output format:
        {
            'exit_code': int,
            'stdout': str,
            'stderr': str,
            'tool': 'eslint' (optional),
            'json_output': dict (optional, if --format json was used)
        }
        """
        exit_code = raw_output["exit_code"]
        stdout = raw_output.get("stdout", "")
        stderr = raw_output.get("stderr", "")
        json_output = raw_output.get("json_output")

        # Try to parse JSON output first (more reliable)
        if json_output:
            issues = self._parse_json_output(json_output)
        else:
            issues = self._parse_text_output(stdout)

        salient_fragments = self._extract_salient_fragments(issues)

        # Determine category
        category = self._determine_category(issues, stderr, exit_code)

        # Check for deterministic blockers
        is_blocker, blocker_type = self._check_deterministic_blockers(stderr, stdout)

        # Compute quality score
        has_file_info = any(f.file_path is not None for f in salient_fragments)
        signal_quality = self._compute_base_quality(salient_fragments, stdout, has_file_info)

        # Generate summary if needed
        auto_summary = self._generate_summary(issues) if len(stdout) > 2000 else ""

        return NormalizedFeedback(
            success=exit_code == 0,
            exit_code=exit_code,
            category=category,
            is_deterministic_blocker=is_blocker,
            blocker_type=blocker_type,
            salient_fragments=salient_fragments,
            suggested_scope=self._suggest_scope(issues),
            signal_quality_score=signal_quality,
            feedback_source="eslint",
            stdout=stdout,
            stderr=stderr,
            timestamp=time.time(),
            tool_version=self._get_eslint_version(stdout, stderr),
            auto_summary=auto_summary,
        )

    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score for ESLint feedback."""
        has_file_info = any(f.file_path is not None for f in feedback.salient_fragments)
        return self._compute_base_quality(
            feedback.salient_fragments, feedback.stdout, has_file_info
        )

    def _parse_json_output(self, json_output: Any) -> list[dict[str, Any]]:
        """
        Parse ESLint JSON format output.

        JSON format:
        [
          {
            "filePath": "path/to/file.js",
            "messages": [
              {
                "ruleId": "no-unused-vars",
                "severity": 2,
                "message": "'foo' is assigned a value but never used",
                "line": 10,
                "column": 7
              }
            ]
          }
        ]
        """
        issues = []

        if isinstance(json_output, str):
            try:
                json_output = json.loads(json_output)
            except json.JSONDecodeError:
                return []

        if not isinstance(json_output, list):
            return []

        for file_result in json_output:
            file_path = file_result.get("filePath", "")
            messages = file_result.get("messages", [])

            for msg in messages:
                issues.append(
                    {
                        "file": file_path,
                        "line": msg.get("line"),
                        "column": msg.get("column"),
                        "severity": "error" if msg.get("severity") == 2 else "warning",
                        "message": msg.get("message", ""),
                        "rule": msg.get("ruleId", "unknown"),
                    }
                )

        return issues

    def _parse_text_output(self, stdout: str) -> list[dict[str, Any]]:
        """
        Parse ESLint text format output.

        Example format:
          /path/to/file.js
            10:7  error  'foo' is assigned a value but never used  no-unused-vars
            15:3  warning  Unexpected console statement  no-console
        """
        issues = []

        # Pattern for file paths
        file_pattern = r"^([^\s].+?\.(?:js|jsx|ts|tsx))$"

        # Pattern for lint messages
        message_pattern = r"^\s+(\d+):(\d+)\s+(error|warning)\s+(.+?)\s+([\w-]+)$"

        current_file = None
        lines = stdout.split("\n")

        for line in lines:
            # Check if this is a file path line
            file_match = re.match(file_pattern, line.strip())
            if file_match:
                current_file = file_match.group(1)
                continue

            # Check if this is a message line
            message_match = re.match(message_pattern, line)
            if message_match and current_file:
                line_num = int(message_match.group(1))
                col_num = int(message_match.group(2))
                severity = message_match.group(3)
                message = message_match.group(4)
                rule = message_match.group(5)

                issues.append(
                    {
                        "file": current_file,
                        "line": line_num,
                        "column": col_num,
                        "severity": severity,
                        "message": message,
                        "rule": rule,
                    }
                )

        return issues

    def _extract_salient_fragments(self, issues: list[dict]) -> list[SalientFragment]:
        """Convert issues to salient fragments."""
        fragments = []

        # Limit to most important issues (errors first, then warnings)
        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]

        # Take up to 10 errors and 5 warnings
        important_issues = errors[:10] + warnings[:5]

        for issue in important_issues:
            context = f"{issue.get('rule', 'unknown')} at {issue.get('file', 'unknown')}"
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

        # Permission errors
        if "EACCES" in stderr or "permission denied" in stderr.lower():
            return True, DeterministicBlocker.PERMISSION_DENIED

        # Missing dependencies
        if "Cannot find module" in stderr or "MODULE_NOT_FOUND" in stderr:
            return True, DeterministicBlocker.MISSING_EXTERNAL_DEP

        return False, None

    def _determine_category(
        self, issues: list[dict], stderr: str, exit_code: int
    ) -> FeedbackCategory:
        """Determine failure category from issues."""

        if exit_code == 0:
            return FeedbackCategory.UNKNOWN

        # Check for missing dependencies
        if "Cannot find module" in stderr:
            return FeedbackCategory.MISSING_DEPENDENCY

        # Check for permission errors
        if "permission denied" in stderr.lower():
            return FeedbackCategory.PERMISSION_DENIED

        # Check for type errors (TypeScript)
        if any("type" in i["message"].lower() for i in issues):
            return FeedbackCategory.TYPE_ERROR

        # Default to lint warning if we have issues
        if len(issues) > 0:
            # If any errors, categorize as validation error
            if any(i["severity"] == "error" for i in issues):
                return FeedbackCategory.VALIDATION_ERROR
            return FeedbackCategory.LINT_WARNING

        return FeedbackCategory.UNKNOWN

    def _suggest_scope(self, issues: list[dict]) -> str | None:
        """Suggest which file/function to focus on."""
        if len(issues) == 0:
            return None

        # Count issues per file
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
            return "No linting issues detected"

        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")

        summary_parts = []
        if error_count > 0:
            summary_parts.append(f"{error_count} error(s)")
        if warning_count > 0:
            summary_parts.append(f"{warning_count} warning(s)")

        summary = " and ".join(summary_parts)

        # Add file count
        unique_files = len(set(i.get("file") for i in issues if i.get("file")))
        if unique_files > 0:
            summary += f" across {unique_files} file(s)"

        return summary

    def _get_eslint_version(self, stdout: str, stderr: str) -> str | None:
        """Extract ESLint version from output."""
        # Try to find version in output
        for text in [stdout, stderr]:
            match = re.search(r"eslint[^\d]*(\d+\.\d+\.\d+)", text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None
