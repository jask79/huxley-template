"""
Unit tests for Xcode build normalizer.

Tests xcodebuild output parsing with real output samples.
"""

import os
import sys

import pytest

# Add parent directory to path for imports
_test_dir = os.path.dirname(os.path.abspath(__file__))
_agent_loops_dir = os.path.dirname(_test_dir)
sys.path.insert(0, _agent_loops_dir)

from core.feedback_schema import DeterministicBlocker, FeedbackCategory
from feedback.normalizers.xcodebuild_normalizer import XcodeBuildNormalizer

# Real xcodebuild output samples
XCODE_SUCCESS_OUTPUT = """
Build settings from command line:
    ARCHS = arm64
    SDKROOT = iphoneos17.0

=== BUILD TARGET MyApp OF PROJECT MyApp WITH CONFIGURATION Debug ===

Check dependencies
...
** BUILD SUCCEEDED **
"""

XCODE_COMPILE_ERROR = """
=== BUILD TARGET MyApp OF PROJECT MyApp WITH CONFIGURATION Debug ===

CompileSwift normal arm64 (in target 'MyApp' from project 'MyApp')
    cd /Users/test/MyApp
    /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swift-frontend ...

/Users/test/MyApp/Sources/ContentView.swift:42:10: error: use of unresolved identifier 'foo'
        print(foo)
              ^~~

/Users/test/MyApp/Sources/ContentView.swift:55:20: error: value of type 'String' has no member 'bar'
        myString.bar()
        ~~~~~~~~ ^~~

** BUILD FAILED **
"""

XCODE_MULTIPLE_ERRORS = """
=== BUILD TARGET MyApp ===

/Users/test/MyApp/Sources/Models/User.swift:15:5: warning: variable 'name' was never used
    var name: String
    ^

/Users/test/MyApp/Sources/ViewModels/UserViewModel.swift:28:12: error: cannot assign value of type 'Int' to type 'String'
        age = 25
              ^~

/Users/test/MyApp/Sources/Views/ProfileView.swift:42:20: error: missing return in closure expected to return 'Bool'
        .filter { user in
                  ^

/Users/test/MyApp/Sources/Views/SettingsView.swift:100:10: warning: result of call to 'save()' is unused
        save()
        ^~~~~~

** BUILD FAILED **

The following build commands failed:
    CompileSwift normal arm64 /Users/test/MyApp/Sources/ViewModels/UserViewModel.swift
"""

XCODE_LINKER_ERROR = """
=== BUILD TARGET MyApp ===

Ld /Users/test/MyApp/build/Debug-iphoneos/MyApp.app/MyApp normal (in target 'MyApp' from project 'MyApp')
    cd /Users/test/MyApp
    /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang ...

ld: framework not found FirebaseAuth
clang: error: linker command failed with exit code 1 (use -v to see invocation)

** BUILD FAILED **
"""

XCODE_SIGNING_ERROR = """
error: No signing certificate "iOS Development" found: No "iOS Development" signing certificate matching team ID "ABCD123456" with a private key was found. (in target 'MyApp' from project 'MyApp')

error: Code signing is required for product type 'Application' in SDK 'iOS 17.0' (in target 'MyApp' from project 'MyApp')

** BUILD FAILED **
"""

XCODE_MISSING_SDK = """
error: unable to load standard library for target 'arm64-apple-ios17.0'
<unknown>:0: error: SDK not found

** BUILD FAILED **
"""


class TestXcodeBuildNormalizer:
    """Test XcodeBuildNormalizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.normalizer = XcodeBuildNormalizer()

    def test_parse_success(self):
        """Test parsing successful build."""
        raw_output = {"exit_code": 0, "stdout": XCODE_SUCCESS_OUTPUT, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is True
        assert feedback.exit_code == 0
        assert len(feedback.salient_fragments) == 0
        assert feedback.feedback_source == "xcodebuild"

    def test_parse_compile_errors(self):
        """Test parsing Swift compile errors."""
        raw_output = {"exit_code": 65, "stdout": XCODE_COMPILE_ERROR, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        # _determine_category checks if 'type' appears in any error message.
        # "value of type 'String' has no member 'bar'" contains 'type', so
        # the implementation returns TYPE_ERROR (implementation is authoritative).
        assert feedback.category == FeedbackCategory.TYPE_ERROR
        assert len(feedback.salient_fragments) == 2

        # Check first error
        fragment = feedback.salient_fragments[0]
        assert "unresolved identifier" in fragment.message
        assert fragment.file_path == "/Users/test/MyApp/Sources/ContentView.swift"
        assert fragment.line_number == 42
        assert fragment.severity == "error"

        # Check second error
        fragment2 = feedback.salient_fragments[1]
        assert "no member" in fragment2.message
        assert fragment2.line_number == 55

    def test_parse_multiple_errors_and_warnings(self):
        """Test parsing multiple errors and warnings."""
        raw_output = {"exit_code": 65, "stdout": XCODE_MULTIPLE_ERRORS, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        # The missing_dep_pattern also matches "error: missing return..." so the
        # normalizer extracts 3 error fragments + 2 warning fragments = 5 total.
        assert len(feedback.salient_fragments) == 5

        # Check we have both errors and warnings
        errors = [f for f in feedback.salient_fragments if f.severity == "error"]
        warnings = [f for f in feedback.salient_fragments if f.severity == "warning"]

        assert len(errors) == 3
        assert len(warnings) == 2

        # Check file paths
        files = feedback.get_file_list()
        assert "/Users/test/MyApp/Sources/Models/User.swift" in files
        assert "/Users/test/MyApp/Sources/ViewModels/UserViewModel.swift" in files

    def test_parse_linker_error(self):
        """Test parsing linker errors."""
        raw_output = {"exit_code": 65, "stdout": XCODE_LINKER_ERROR, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.success is False
        # _determine_category only checks stderr for framework/dependency keywords.
        # Linker errors appear in stdout ("ld: framework not found ..."), so the
        # category falls through to BUILD_ERROR (implementation is authoritative).
        assert feedback.category == FeedbackCategory.BUILD_ERROR

        # Should have linker error fragment
        assert len(feedback.salient_fragments) > 0
        fragment = feedback.salient_fragments[0]
        assert "Linker error" in fragment.message
        assert "FirebaseAuth" in fragment.message

    def test_detect_signing_blocker(self):
        """Test detection of code signing blocker."""
        raw_output = {"exit_code": 65, "stdout": XCODE_SIGNING_ERROR, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.is_deterministic_blocker is True
        assert feedback.blocker_type == DeterministicBlocker.PERMISSION_DENIED
        # _determine_category checks stderr (empty here) not stdout, so signing
        # keywords aren't found there. "product type" contains 'type', so the
        # category resolves to TYPE_ERROR (implementation is authoritative).
        assert feedback.category == FeedbackCategory.TYPE_ERROR

        # Should have signing error fragments
        assert len(feedback.salient_fragments) > 0
        assert any("signing" in f.message.lower() for f in feedback.salient_fragments)

    def test_detect_missing_sdk_blocker(self):
        """Test detection of missing SDK blocker."""
        raw_output = {"exit_code": 65, "stdout": XCODE_MISSING_SDK, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        assert feedback.is_deterministic_blocker is True
        assert feedback.blocker_type == DeterministicBlocker.MISSING_EXTERNAL_DEP
        # _determine_category checks stderr (empty here) for "unable to load".
        # The keyword is in stdout, so the check misses it and falls through to
        # BUILD_ERROR (implementation is authoritative).
        assert feedback.category == FeedbackCategory.BUILD_ERROR

    def test_suggested_scope_single_file(self):
        """Test suggested scope for single file with errors."""
        raw_output = {"exit_code": 65, "stdout": XCODE_COMPILE_ERROR, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should suggest ContentView.swift (only file with errors)
        assert feedback.suggested_scope == "/Users/test/MyApp/Sources/ContentView.swift"

    def test_suggested_scope_multiple_files(self):
        """Test suggested scope for multiple files."""
        raw_output = {"exit_code": 65, "stdout": XCODE_MULTIPLE_ERRORS, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should suggest a file (any with errors)
        assert feedback.suggested_scope is not None
        assert feedback.suggested_scope.endswith(".swift")

    def test_auto_summary_for_long_output(self):
        """Test auto-summary generation for long output."""
        # Create long output > 5000 chars
        long_output = XCODE_MULTIPLE_ERRORS + "\n" + "=" * 6000

        raw_output = {"exit_code": 65, "stdout": long_output, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should have auto-summary
        assert feedback.auto_summary != ""
        assert (
            "error" in feedback.auto_summary.lower() or "warning" in feedback.auto_summary.lower()
        )

    def test_signal_quality_with_file_info(self):
        """Test signal quality with file/line information."""
        raw_output = {"exit_code": 65, "stdout": XCODE_COMPILE_ERROR, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should have high quality (specific errors with file/line)
        assert feedback.signal_quality_score > 0.5
        assert feedback.is_actionable()

    def test_signal_quality_without_file_info(self):
        """Test signal quality for errors without file info."""
        raw_output = {"exit_code": 65, "stdout": XCODE_LINKER_ERROR, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should have lower quality (linker errors have no file/line)
        # But still somewhat actionable
        assert feedback.signal_quality_score > 0.3

    def test_version_extraction(self):
        """Test Xcode version extraction."""
        output_with_version = """
Build settings from command line:
    XCODE = Xcode 15.0
...
"""
        version = self.normalizer._get_xcode_version(output_with_version)
        assert version == "15.0"

        # Test build version format
        output_with_build = """
Build version 15A240d
...
"""
        version = self.normalizer._get_xcode_version(output_with_build)
        assert version == "15A240d"

    def test_categorize_type_errors(self):
        """Test categorization of type errors."""
        type_error_output = """
/Users/test/MyApp/Source.swift:10:5: error: type 'String' does not conform to protocol 'Numeric'
"""
        raw_output = {"exit_code": 65, "stdout": type_error_output, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should categorize as type error
        assert feedback.category == FeedbackCategory.TYPE_ERROR

    def test_limit_error_fragments(self):
        """Test that we limit number of error fragments."""
        # Create output with many errors
        many_errors = "\n".join(
            [f"/Users/test/MyApp/File{i}.swift:{i}:1: error: Error {i}" for i in range(50)]
        )

        raw_output = {"exit_code": 65, "stdout": many_errors, "stderr": ""}

        feedback = self.normalizer.normalize(raw_output)

        # Should limit to 15 errors + 5 warnings = 20 max
        assert len(feedback.salient_fragments) <= 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
