"""
Unit tests for ESLint normalizer.

Tests ESLint output parsing with real output samples.
"""

import json
import os
import sys

import pytest

# Add parent directory to path for imports
_test_dir = os.path.dirname(os.path.abspath(__file__))
_agent_loops_dir = os.path.dirname(_test_dir)
sys.path.insert(0, _agent_loops_dir)

from core.feedback_schema import DeterministicBlocker, FeedbackCategory
from feedback.normalizers.eslint_normalizer import ESLintNormalizer

# Real ESLint output samples
ESLINT_SUCCESS_OUTPUT = """

✨  Done in 0.42s.
"""

ESLINT_TEXT_FORMAT_ERRORS = """
/Users/test/project/src/components/Button.tsx
  10:7   error    'foo' is assigned a value but never used  no-unused-vars
  15:3   warning  Unexpected console statement              no-console
  22:15  error    Missing semicolon                         semi

/Users/test/project/src/utils/helpers.ts
  8:1    error    'helper' is defined but never used        no-unused-vars
  42:20  warning  Use === instead of ==                     eqeqeq

✖ 5 problems (3 errors, 2 warnings)
  1 error and 0 warnings potentially fixable with the `--fix` option.
"""

ESLINT_JSON_FORMAT = [
    {
        "filePath": "/Users/test/project/src/App.tsx",
        "messages": [
            {
                "ruleId": "no-unused-vars",
                "severity": 2,
                "message": "'React' is defined but never used.",
                "line": 1,
                "column": 8,
                "nodeType": "Identifier",
                "messageId": "unusedVar",
                "endLine": 1,
                "endColumn": 13,
            },
            {
                "ruleId": "@typescript-eslint/no-explicit-any",
                "severity": 1,
                "message": "Unexpected any. Specify a different type.",
                "line": 25,
                "column": 15,
                "nodeType": "TSAnyKeyword",
                "messageId": "unexpectedAny",
                "endLine": 25,
                "endColumn": 18,
            },
        ],
        "errorCount": 1,
        "warningCount": 1,
        "fixableErrorCount": 0,
        "fixableWarningCount": 0,
        "source": "...",
    },
    {
        "filePath": "/Users/test/project/src/utils/api.ts",
        "messages": [
            {
                "ruleId": "no-console",
                "severity": 2,
                "message": "Unexpected console statement.",
                "line": 42,
                "column": 5,
                "nodeType": "MemberExpression",
                "messageId": "unexpected",
                "endLine": 42,
                "endColumn": 16,
            }
        ],
        "errorCount": 1,
        "warningCount": 0,
        "fixableErrorCount": 0,
        "fixableWarningCount": 0,
        "source": "...",
    },
]

ESLINT_MODULE_NOT_FOUND = """
Error: Cannot find module 'eslint-plugin-react'
Require stack:
- /Users/test/project/node_modules/eslint/lib/cli-engine/config-array-factory.js
    at Function.Module._resolveFilename (internal/modules/cjs/loader.js:880:15)
    at Function.Module._load (internal/modules/cjs/loader.js:725:27)
"""

ESLINT_PERMISSION_ERROR = """
EACCES: permission denied, open '/protected/.eslintrc.js'
"""


class TestESLintNormalizer:
    """Test ESLintNormalizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.normalizer = ESLintNormalizer()

    def test_parse_success(self):
        """Test parsing successful ESLint run."""
        raw_output = {"exit_code": 0, "stdout": ESLINT_SUCCESS_OUTPUT, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is True
        assert feedback.exit_code == 0
        assert len(feedback.salient_fragments) == 0
        assert feedback.feedback_source == "eslint"

    def test_parse_text_format(self):
        """Test parsing text format output."""
        raw_output = {"exit_code": 1, "stdout": ESLINT_TEXT_FORMAT_ERRORS, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        assert feedback.exit_code == 1
        assert feedback.category == FeedbackCategory.VALIDATION_ERROR

        # Should have 5 fragments (3 errors + 2 warnings, limited to top issues)
        assert len(feedback.salient_fragments) <= 15

        # Check first error
        fragments = feedback.salient_fragments
        assert any("no-unused-vars" in f.context for f in fragments)
        assert any(
            f.file_path == "/Users/test/project/src/components/Button.tsx" for f in fragments
        )

        # Check severity classification
        errors = [f for f in fragments if f.severity == "error"]
        warnings = [f for f in fragments if f.severity == "warning"]
        assert len(errors) > 0
        assert len(warnings) > 0

    def test_parse_json_format(self):
        """Test parsing JSON format output."""
        raw_output = {"exit_code": 1, "stdout": "", "stderr": "", "json_output": ESLINT_JSON_FORMAT}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        assert len(feedback.salient_fragments) == 3

        # Check that all messages were parsed
        messages = [f.message for f in feedback.salient_fragments]
        assert any("'React' is defined but never used" in m for m in messages)
        assert any("Unexpected any" in m for m in messages)
        assert any("Unexpected console statement" in m for m in messages)

        # Check file paths
        files = feedback.get_file_list()
        assert "/Users/test/project/src/App.tsx" in files
        assert "/Users/test/project/src/utils/api.ts" in files

        # Check line numbers
        assert any(f.line_number == 1 for f in feedback.salient_fragments)
        assert any(f.line_number == 25 for f in feedback.salient_fragments)
        assert any(f.line_number == 42 for f in feedback.salient_fragments)

    def test_parse_json_format_from_string(self):
        """Test parsing JSON format passed as string."""
        raw_output = {
            "exit_code": 1,
            "stdout": "",
            "stderr": "",
            "json_output": json.dumps(ESLINT_JSON_FORMAT),
        }

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        assert len(feedback.salient_fragments) > 0

    def test_detect_missing_dependency(self):
        """Test detection of missing module blocker."""
        raw_output = {"exit_code": 1, "stdout": "", "stderr": ESLINT_MODULE_NOT_FOUND}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.is_deterministic_blocker is True
        assert feedback.blocker_type == DeterministicBlocker.MISSING_EXTERNAL_DEP
        assert feedback.category == FeedbackCategory.MISSING_DEPENDENCY

    def test_detect_permission_blocker(self):
        """Test detection of permission denied blocker."""
        raw_output = {"exit_code": 1, "stdout": "", "stderr": ESLINT_PERMISSION_ERROR}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.is_deterministic_blocker is True
        assert feedback.blocker_type == DeterministicBlocker.PERMISSION_DENIED
        assert feedback.category == FeedbackCategory.PERMISSION_DENIED

    def test_suggested_scope_single_file(self):
        """Test suggested scope for single file."""
        json_output = [
            {
                "filePath": "/Users/test/project/src/App.tsx",
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "message": "Error 1",
                        "line": 1,
                        "column": 1,
                    },
                    {
                        "ruleId": "no-console",
                        "severity": 2,
                        "message": "Error 2",
                        "line": 2,
                        "column": 1,
                    },
                ],
            }
        ]

        raw_output = {"exit_code": 1, "stdout": "", "stderr": "", "json_output": json_output}

        feedback = self.normalizer.normalize(raw_output)

        # Should suggest the file with issues
        assert feedback.suggested_scope == "/Users/test/project/src/App.tsx"

    def test_suggested_scope_multiple_files(self):
        """Test suggested scope for multiple files."""
        raw_output = {"exit_code": 1, "stdout": ESLINT_TEXT_FORMAT_ERRORS, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should suggest Button.tsx (has 3 issues vs helpers.ts with 2)
        assert feedback.suggested_scope == "/Users/test/project/src/components/Button.tsx"

    def test_auto_summary_generation(self):
        """Test auto-summary generation for long output."""
        # Create long output > 2000 chars
        long_output = ESLINT_TEXT_FORMAT_ERRORS + "\n" + "=" * 3000

        raw_output = {"exit_code": 1, "stdout": long_output, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should have auto-summary
        assert feedback.auto_summary != ""
        assert (
            "error" in feedback.auto_summary.lower() or "warning" in feedback.auto_summary.lower()
        )

    def test_signal_quality_with_file_info(self):
        """Test signal quality with file/line information."""
        raw_output = {"exit_code": 1, "stdout": "", "stderr": "", "json_output": ESLINT_JSON_FORMAT}

        feedback = self.normalizer.normalize(raw_output)

        # Should have high quality (specific errors with file/line)
        assert feedback.signal_quality_score > 0.5
        assert feedback.is_actionable()

    def test_categorize_type_errors(self):
        """Test categorization of TypeScript type errors."""
        json_output = [
            {
                "filePath": "/Users/test/project/src/App.tsx",
                "messages": [
                    {
                        "ruleId": "@typescript-eslint/no-explicit-any",
                        "severity": 2,
                        "message": "Type 'string' is not assignable to type 'number'.",
                        "line": 10,
                        "column": 5,
                    }
                ],
            }
        ]

        raw_output = {"exit_code": 1, "stdout": "", "stderr": "", "json_output": json_output}

        feedback = self.normalizer.normalize(raw_output)

        # Should categorize as type error
        assert feedback.category == FeedbackCategory.TYPE_ERROR

    def test_limit_fragments(self):
        """Test that we limit number of fragments."""
        # Create many errors
        many_errors = [
            {
                "filePath": f"/Users/test/project/src/file{i}.tsx",
                "messages": [
                    {
                        "ruleId": "rule",
                        "severity": 2,
                        "message": f"Error {i}",
                        "line": 1,
                        "column": 1,
                    }
                ],
            }
            for i in range(50)  # 50 errors
        ]

        raw_output = {"exit_code": 1, "stdout": "", "stderr": "", "json_output": many_errors}

        feedback = self.normalizer.normalize(raw_output)

        # Should limit to 10 errors + 5 warnings = 15 max
        assert len(feedback.salient_fragments) <= 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
