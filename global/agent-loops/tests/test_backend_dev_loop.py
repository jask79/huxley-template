"""
Integration tests for Backend Dev agentic loop.

Tests the complete loop execution with backend-specific validations.
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.backend_dev_loop import BackendDevLoop, BackendTask
from core.loop_executor import LoopResult
from remediation.skill_library import SkillLibrary


class TestBackendDevLoop:
    """Test suite for BackendDevLoop."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def backend_loop(self, temp_project):
        """Create BackendDevLoop instance."""
        return BackendDevLoop(project_root=temp_project, max_iterations=3, verbose=False)

    @pytest.fixture
    def sample_task(self):
        """Create sample backend task."""
        return BackendTask(
            description="Create user API endpoint with CRUD operations",
            api_file="api/users.py",
            model_file="models/user.py",
            test_file="tests/test_users.py",
            validation_tools=["pytest", "mypy"],
        )

    def test_initialization(self, backend_loop, temp_project):
        """Test BackendDevLoop initialization."""
        assert backend_loop.project_root == Path(temp_project)
        assert backend_loop.executor.agent_name == "Backend Dev"
        assert backend_loop.executor.adaptive_limits.default_max_iterations == 3

    def test_backend_skills_loaded(self, backend_loop):
        """Test that backend skills are automatically loaded."""
        library = backend_loop.executor.skill_library

        # Check for backend-specific skills
        skill_ids = [s.skill_id for s in library.list_skills()]

        assert "fix_sqlalchemy_query" in skill_ids
        assert "fix_pydantic_validation" in skill_ids
        assert "fix_async_endpoint" in skill_ids
        assert "add_api_error_handling" in skill_ids
        assert "fix_database_migration" in skill_ids

    def test_task_creation(self, sample_task):
        """Test BackendTask creation and defaults."""
        assert sample_task.description == "Create user API endpoint with CRUD operations"
        assert sample_task.api_file == "api/users.py"
        assert "pytest" in sample_task.validation_tools
        assert "mypy" in sample_task.validation_tools

    def test_task_default_validation_tools(self):
        """Test BackendTask sets default validation tools."""
        task = BackendTask(description="Test task")

        assert task.validation_tools == ["pytest", "mypy", "ruff"]

    @patch("subprocess.run")
    def test_run_validation_tool_pytest(self, mock_run, backend_loop, sample_task):
        """Test pytest validation tool execution."""
        # Mock successful pytest run
        mock_run.return_value = Mock(
            returncode=0, stdout="test_users.py::test_create_user PASSED\n", stderr=""
        )

        result = backend_loop._run_validation_tool("pytest", sample_task)

        assert result["exit_code"] == 0
        assert "PASSED" in result["stdout"]
        assert mock_run.called

    @patch("subprocess.run")
    def test_run_validation_tool_mypy(self, mock_run, backend_loop, sample_task):
        """Test mypy validation tool execution."""
        # Mock mypy with type errors
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="api/users.py:10: error: Incompatible return value type\n",
        )

        result = backend_loop._run_validation_tool("mypy", sample_task)

        assert result["exit_code"] == 1
        assert "Incompatible return value type" in result["stderr"]

    @patch("subprocess.run")
    def test_run_validation_tool_ruff(self, mock_run, backend_loop, sample_task):
        """Test ruff validation tool execution."""
        # Mock ruff with lint violations
        mock_run.return_value = Mock(
            returncode=1, stdout="api/users.py:15:1: F401 'os' imported but unused\n", stderr=""
        )

        result = backend_loop._run_validation_tool("ruff", sample_task)

        assert result["exit_code"] == 1
        assert "F401" in result["stdout"]

    @patch("subprocess.run")
    def test_run_validation_tool_timeout(self, mock_run, backend_loop, sample_task):
        """Test validation tool timeout handling."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 60)

        result = backend_loop._run_validation_tool("pytest", sample_task)

        assert result["exit_code"] == -1
        assert "timed out" in result["stderr"]

    @patch("subprocess.run")
    def test_run_validation_tool_not_found(self, mock_run, backend_loop, sample_task):
        """Test handling of missing validation tool."""
        mock_run.side_effect = FileNotFoundError()

        result = backend_loop._run_validation_tool("pytest", sample_task)

        assert result["exit_code"] == -1
        assert "not found" in result["stderr"]
        assert "pip install" in result["stderr"]

    def test_unknown_validation_tool(self, backend_loop, sample_task):
        """Test error handling for unknown validation tool."""
        # ValueError is raised inside the try block and caught by the broad
        # `except Exception` handler, which returns a dict instead of re-raising.
        result = backend_loop._run_validation_tool("unknown_tool", sample_task)
        assert result["exit_code"] == -1
        assert "Unknown validation tool" in result["stderr"]

    def test_backend_task_with_custom_tools(self):
        """Test BackendTask with custom validation tools."""
        task = BackendTask(description="Test task", validation_tools=["pytest", "api_test"])

        assert task.validation_tools == ["pytest", "api_test"]
        assert "mypy" not in task.validation_tools

    def test_batch_build_multiple_tasks(self, backend_loop):
        """Test batch building multiple tasks."""
        tasks = [
            BackendTask(description="Task 1", api_file="api/users.py"),
            BackendTask(description="Task 2", api_file="api/posts.py"),
        ]

        # Mock the build_api method
        with patch.object(backend_loop, "build_api") as mock_build:
            # First task succeeds, second fails
            mock_build.side_effect = [
                LoopResult(
                    success=True,
                    iterations=1,
                    final_feedback=None,
                    escalation_triggered=False,
                    escalation_reason=None,
                    trace_id="test-1",
                    execution_time=1.0,
                ),
                LoopResult(
                    success=False,
                    iterations=3,
                    final_feedback=None,
                    escalation_triggered=True,
                    escalation_reason="Max iterations reached",
                    trace_id="test-2",
                    execution_time=3.0,
                ),
            ]

            results = backend_loop.batch_build(tasks)

            # Should stop after second task fails
            assert len(results) == 2
            assert results[0].success is True
            assert results[1].success is False
            assert mock_build.call_count == 2

    def test_batch_build_all_succeed(self, backend_loop):
        """Test batch build where all tasks succeed."""
        tasks = [
            BackendTask(description="Task 1"),
            BackendTask(description="Task 2"),
            BackendTask(description="Task 3"),
        ]

        with patch.object(backend_loop, "build_api") as mock_build:
            # All tasks succeed
            mock_build.return_value = LoopResult(
                success=True,
                iterations=1,
                final_feedback=None,
                escalation_triggered=False,
                escalation_reason=None,
                trace_id="test",
                execution_time=1.0,
            )

            results = backend_loop.batch_build(tasks)

            assert len(results) == 3
            assert all(r.success for r in results)
            assert mock_build.call_count == 3

    @pytest.mark.skip(reason="requires pytest-asyncio (not installed): pip install pytest-asyncio")
    @pytest.mark.asyncio
    async def test_async_build(self, backend_loop, sample_task):
        """Test async version of build_api."""
        with patch.object(backend_loop, "build_api") as mock_build:
            mock_build.return_value = LoopResult(
                success=True,
                iterations=1,
                final_feedback=None,
                escalation_triggered=False,
                escalation_reason=None,
                trace_id="test",
                execution_time=1.0,
            )

            result = await backend_loop.build_api_async(sample_task)

            assert result.success is True
            assert mock_build.called


class TestBackendSkillsIntegration:
    """Test integration of backend skills with the loop."""

    @pytest.fixture
    def skill_library(self):
        """Create skill library with backend skills."""
        library = SkillLibrary()
        from remediation.backend_skills import seed_backend_skills

        seed_backend_skills(library)
        return library

    def test_all_backend_skills_loaded(self, skill_library):
        """Test that all 10 backend skills are loaded."""
        backend_skill_ids = [
            "fix_sqlalchemy_query",
            "fix_pydantic_validation",
            "fix_async_endpoint",
            "add_api_error_handling",
            "fix_database_migration",
            "fix_cors_configuration",
            "add_request_validation",
            "fix_authentication",
            "optimize_database_query",
            "fix_serialization",
        ]

        loaded_ids = [s.skill_id for s in skill_library.list_skills()]

        for skill_id in backend_skill_ids:
            assert skill_id in loaded_ids, f"Skill {skill_id} not loaded"

    def test_sqlalchemy_skill_pattern_matching(self, skill_library):
        """Test SQLAlchemy skill matches appropriate errors."""
        skill = skill_library.get_skill("fix_sqlalchemy_query")

        assert skill.matches_error(
            "sqlalchemy.orm.exc.DetachedInstanceError: Instance is not bound", "runtime_error"
        )

        assert skill.matches_error("Multiple rows were found for one()", "runtime_error")

    def test_pydantic_skill_pattern_matching(self, skill_library):
        """Test Pydantic skill matches validation errors."""
        skill = skill_library.get_skill("fix_pydantic_validation")

        assert skill.matches_error(
            "pydantic.error_wrappers.ValidationError: field required", "validation_error"
        )

        assert skill.matches_error("value is not a valid email address", "validation_error")

    def test_async_skill_pattern_matching(self, skill_library):
        """Test async endpoint skill matches coroutine errors."""
        skill = skill_library.get_skill("fix_async_endpoint")

        assert skill.matches_error("coroutine 'get_users' was never awaited", "runtime_error")

    def test_backend_skills_have_proper_metadata(self, skill_library):
        """Test all backend skills have required metadata."""
        backend_skills = [
            s
            for s in skill_library.list_skills()
            if s.skill_id.startswith(("fix_", "add_", "optimize_")) and "backend" in s.tags
        ]

        for skill in backend_skills:
            assert skill.skill_id
            assert skill.name
            assert skill.description
            assert len(skill.error_patterns) > 0
            assert len(skill.applicable_categories) > 0
            assert skill.fix_template
            assert skill.metadata.version == "1.0"
            assert "backend" in skill.tags

    def test_skill_library_search_by_error(self, skill_library):
        """Test searching for skills by error message."""
        # Search for SQLAlchemy error
        skills = skill_library.search_by_error(
            "DetachedInstanceError: Instance is not bound to a Session", "runtime_error", top_k=3
        )

        assert len(skills) > 0
        assert any("sqlalchemy" in s.skill_id for s in skills)

        # Search for Pydantic validation error
        skills = skill_library.search_by_error(
            "validation error for User: field required", "validation_error", top_k=3
        )

        assert len(skills) > 0
        assert any("pydantic" in s.skill_id for s in skills)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
