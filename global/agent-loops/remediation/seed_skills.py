"""
Seed initial remediation skills into the library.

Provides 15 foundational skills for common error patterns.
"""

import time

from .skill import RemediationSkill, SkillMetadata, SkillType
from .skill_library import SkillLibrary


def seed_initial_skills(library: SkillLibrary) -> None:
    """Seed 15 initial remediation skills."""

    skills = [
        # 1. Missing Import
        RemediationSkill(
            skill_id="fix_missing_import",
            name="Fix Missing Import",
            description="Add missing import statement when module/function not found",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"ModuleNotFoundError",
                r"ImportError",
                r"cannot import name",
                r"No module named",
            ],
            applicable_categories=["build_error", "runtime_error"],
            fix_template="""
Add the missing import at the top of {file_path}:

import {missing_module}

Or if it's a specific function/class:
from {missing_module} import {missing_name}

Check if the package is installed. If not, install with:
pip install {missing_module}
            """,
            required_context=["file_path", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "imports", "dependencies"],
        ),
        # 2. Null Check
        RemediationSkill(
            skill_id="fix_null_check",
            name="Fix Null/None Check",
            description="Add null/none checking before accessing attributes or methods",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"NoneType.*has no attribute",
                r"null is not an object",
                r"Cannot read property.*of null",
                r"Optional.*unwrap",
            ],
            applicable_categories=["runtime_error", "type_error"],
            fix_template="""
At line {line_number} in {file_path}, add null check:

if variable is not None:
    variable.method()

Or use optional chaining (if supported):
variable?.method()

Or provide a default value:
result = variable or default_value
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "javascript", "null-safety"],
        ),
        # 3. Install Dependency
        RemediationSkill(
            skill_id="install_dependency",
            name="Install Missing Dependency",
            description="Install missing package or dependency",
            skill_type=SkillType.DEPENDENCY_FIX,
            error_patterns=[r"No module named", r"Cannot find module", r"Package .* not found"],
            applicable_categories=["missing_dependency", "build_error"],
            fix_template="""
Install the missing dependency:

Python: pip install {package_name}
Node.js: npm install {package_name}
Ruby: gem install {package_name}

Then re-run your build/tests.
            """,
            required_context=["error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["dependencies", "installation"],
        ),
        # 4. Type Error
        RemediationSkill(
            skill_id="fix_type_error",
            name="Fix Type Mismatch",
            description="Correct type mismatches and add type conversions",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[r"TypeError", r"type .* is not assignable", r"expected .* but got"],
            applicable_categories=["type_error", "build_error"],
            fix_template="""
At line {line_number} in {file_path}, fix type mismatch:

Add type conversion:
int(value)  # Convert to integer
str(value)  # Convert to string
float(value)  # Convert to float

Or add type annotation:
variable: ExpectedType = value

Or update type hint:
def function(param: CorrectType) -> ReturnType:
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["types", "python", "typescript"],
        ),
        # 5. Test Assertion
        RemediationSkill(
            skill_id="fix_test_assertion",
            name="Fix Failing Test Assertion",
            description="Correct test assertions to match actual behavior",
            skill_type=SkillType.TEST_FIX,
            error_patterns=[r"AssertionError", r"Expected .* to equal", r"assert .* failed"],
            applicable_categories=["test_failure"],
            fix_template="""
In test at line {line_number} of {file_path}:

Review the assertion:
- Is the expected value correct?
- Has the implementation changed?
- Is the test testing the right thing?

Update assertion:
assert actual == expected  # Python
expect(actual).toBe(expected)  # JavaScript
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["testing", "assertions"],
        ),
        # 6. Error Handling
        RemediationSkill(
            skill_id="add_error_handling",
            name="Add Error Handling",
            description="Add try-catch or error handling for operations that can fail",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[r"Unhandled exception", r"Uncaught error", r"Fatal error"],
            applicable_categories=["runtime_error"],
            fix_template="""
At line {line_number} in {file_path}, add error handling:

Python:
try:
    risky_operation()
except SpecificError as e:
    handle_error(e)

JavaScript:
try {{
    riskyOperation();
}} catch (error) {{
    handleError(error);
}}
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["error-handling", "exceptions"],
        ),
        # 7. Syntax Error
        RemediationSkill(
            skill_id="fix_syntax_error",
            name="Fix Syntax Error",
            description="Correct syntax errors like missing brackets, quotes, colons",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[r"SyntaxError", r"unexpected token", r"invalid syntax"],
            applicable_categories=["build_error"],
            fix_template="""
At line {line_number} in {file_path}, fix syntax:

Common issues:
- Missing closing bracket/parenthesis/quote
- Missing colon at end of if/for/def statements
- Incorrect indentation
- Missing comma in list/dict

Review the line and surrounding context for syntax issues.
            """,
            required_context=["file_path", "line_number", "error_message", "context_lines"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["syntax", "parsing"],
        ),
        # 8. Circular Import
        RemediationSkill(
            skill_id="resolve_circular_import",
            name="Resolve Circular Import",
            description="Fix circular import dependencies between modules",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[r"circular import", r"ImportError.*circular"],
            applicable_categories=["build_error"],
            fix_template="""
In {file_path}, resolve circular import:

Options:
1. Move import inside function where it's used
2. Merge related functionality into one module
3. Create interface/protocol for dependency injection
4. Use TYPE_CHECKING guard:

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from module import Class  # Only for type hints
            """,
            required_context=["file_path", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["imports", "architecture", "python"],
        ),
        # 9. Async/Await
        RemediationSkill(
            skill_id="fix_async_await",
            name="Fix Async/Await Usage",
            description="Correct async function calls and await usage",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"coroutine .* was never awaited",
                r"await.*outside async function",
                r"Cannot use await",
            ],
            applicable_categories=["runtime_error", "build_error"],
            fix_template="""
At line {line_number} in {file_path}:

If calling async function, add await:
result = await async_function()

If function needs to be async:
async def function_name():
    result = await async_operation()

If running async code from sync context:
import asyncio
asyncio.run(async_function())
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["async", "python", "javascript"],
        ),
        # 10. Type Annotation
        RemediationSkill(
            skill_id="add_type_annotation",
            name="Add Type Annotation",
            description="Add missing type hints or annotations",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Missing type annotation",
                r"Missing return type",
                r"Argument .* missing type",
            ],
            applicable_categories=["type_error", "lint_warning"],
            fix_template="""
At line {line_number} in {file_path}, add type annotation:

For variables:
variable: str = "value"

For function parameters:
def function(param: int) -> str:
    return str(param)

For class attributes:
class MyClass:
    attribute: List[str]
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["types", "annotations", "python"],
        ),
        # 11. Lint Rule
        RemediationSkill(
            skill_id="fix_lint_rule",
            name="Fix Linting Rule Violation",
            description="Address code style and linting issues",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"line too long",
                r"unused import",
                r"unused variable",
                r"missing whitespace",
            ],
            applicable_categories=["lint_warning"],
            fix_template="""
At line {line_number} in {file_path}, fix lint issue:

For line length: Break into multiple lines
For unused import: Remove the import
For unused variable: Remove or prefix with _
For whitespace: Add/remove spaces per style guide

Or suppress if intentional:
# noqa  (Python)
// eslint-disable-next-line  (JavaScript)
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["linting", "style"],
        ),
        # 12. Build Configuration
        RemediationSkill(
            skill_id="fix_build_configuration",
            name="Fix Build Configuration",
            description="Correct build config files (package.json, setup.py, etc.)",
            skill_type=SkillType.CONFIG_FIX,
            error_patterns=[
                r"invalid.*configuration",
                r"malformed.*config",
                r"Invalid.*package.json",
            ],
            applicable_categories=["build_error"],
            fix_template="""
Review and fix build configuration:

Check syntax (JSON/YAML formatting)
Validate required fields
Update version constraints
Ensure file paths are correct

Common files: package.json, setup.py, tsconfig.json, Cargo.toml
            """,
            required_context=["error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["config", "build"],
        ),
        # 13. Package Conflict
        RemediationSkill(
            skill_id="resolve_package_conflict",
            name="Resolve Package Version Conflict",
            description="Fix dependency version conflicts and incompatibilities",
            skill_type=SkillType.DEPENDENCY_FIX,
            error_patterns=[
                r"version conflict",
                r"incompatible.*version",
                r"Could not find.*satisfies",
            ],
            applicable_categories=["missing_dependency", "build_error"],
            fix_template="""
Resolve package conflict:

1. Check dependency versions in requirements.txt / package.json
2. Update conflicting package versions
3. Use version constraints (>=, <, ~, ^)
4. Consider using lock files (package-lock.json, poetry.lock)
5. If needed, upgrade/downgrade major package

pip: pip install --upgrade package_name
npm: npm update package_name
            """,
            required_context=["error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["dependencies", "versions"],
        ),
        # 14. Indentation
        RemediationSkill(
            skill_id="fix_indentation",
            name="Fix Indentation Error",
            description="Correct indentation issues in code",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"IndentationError",
                r"unexpected indent",
                r"expected an indented block",
            ],
            applicable_categories=["build_error"],
            fix_template="""
At line {line_number} in {file_path}, fix indentation:

Python uses consistent indentation (4 spaces recommended):
- All code in a block must be at same level
- Don't mix tabs and spaces
- After colon (:), indent next line

Check editor settings for tabs vs spaces.
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["indentation", "python", "syntax"],
        ),
        # 15. Missing Return
        RemediationSkill(
            skill_id="add_missing_return",
            name="Add Missing Return Statement",
            description="Add return statement when function should return a value",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"missing return statement",
                r"not all code paths return",
                r"function must return",
            ],
            applicable_categories=["type_error", "build_error"],
            fix_template="""
At line {line_number} in {file_path}, add return:

Ensure all code paths return a value:
def function() -> int:
    if condition:
        return 1
    else:
        return 0  # Add this return

Or return None if optional:
def function() -> Optional[int]:
    if condition:
        return 1
    return None
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["return", "functions", "types"],
        ),
    ]

    # Add all skills to library
    for skill in skills:
        library.add_skill(skill)

    # Save to disk
    library.save()

    print(f"✓ Seeded {len(skills)} initial remediation skills")


if __name__ == "__main__":
    library = SkillLibrary()
    seed_initial_skills(library)
    print("\nLibrary Stats:")
    print(library.get_stats())
