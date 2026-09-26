"""
Integration tests for Frontend Dev agentic loop.

Tests the complete workflow: normalize → remediate → iterate → success.
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.frontend_dev_loop import FrontendDevLoop
from remediation.frontend_skills import get_frontend_skill_count, seed_frontend_skills
from remediation.skill_library import SkillLibrary


class TestFrontendDevLoop:
    """Test suite for FrontendDevLoop."""

    def test_initialization(self):
        """Test loop initialization."""
        loop = FrontendDevLoop(project_dir="/tmp/test-project", max_iterations=5)

        assert loop.project_dir == Path("/tmp/test-project")
        assert loop.max_iterations == 5
        assert loop.executor.agent_name == "Frontend Dev"

        # Verify frontend skills were seeded
        skill_stats = loop.executor.skill_library.get_stats()
        assert skill_stats["total_skills"] >= get_frontend_skill_count()

    def test_frontend_skills_seeded(self):
        """Test that all frontend skills are loaded."""
        library = SkillLibrary()
        seed_frontend_skills(library)

        # Verify all 10 skills exist
        expected_skills = [
            "fix_react_hook_dependency",
            "fix_jsx_syntax",
            "fix_import_path",
            "fix_prop_types",
            "fix_state_mutation",
            "add_key_prop",
            "fix_event_handler",
            "fix_css_module_import",
            "fix_async_component",
            "fix_context_usage",
        ]

        for skill_id in expected_skills:
            skill = library.get_skill(skill_id)
            assert skill is not None, f"Skill {skill_id} not found"
            assert skill.name
            assert skill.description
            assert len(skill.error_patterns) > 0
            assert len(skill.applicable_categories) > 0

    def test_skill_pattern_matching(self):
        """Test that frontend skills match expected error patterns."""
        library = SkillLibrary()
        seed_frontend_skills(library)

        # Test React Hook dependency skill
        hook_skill = library.get_skill("fix_react_hook_dependency")
        assert hook_skill.matches_error(
            "React Hook useEffect has a missing dependency: 'userId'", "build_error"
        )

        # Test JSX syntax skill
        jsx_skill = library.get_skill("fix_jsx_syntax")
        assert jsx_skill.matches_error(
            "Expected corresponding JSX closing tag for <div>", "syntax_error"
        )

        # Test import path skill
        import_skill = library.get_skill("fix_import_path")
        assert import_skill.matches_error("Cannot find module '@/components/Button'", "build_error")

        # Test prop types skill
        props_skill = library.get_skill("fix_prop_types")
        assert props_skill.matches_error(
            "TS2322: Type 'string' is not assignable to type 'number'", "type_error"
        )

    def test_skill_fix_templates(self):
        """Test that skills have useful fix templates."""
        library = SkillLibrary()
        seed_frontend_skills(library)

        # Test each skill has a non-empty fix template
        for skill_id in [
            "fix_react_hook_dependency",
            "fix_jsx_syntax",
            "fix_import_path",
            "fix_prop_types",
            "fix_state_mutation",
            "add_key_prop",
            "fix_event_handler",
            "fix_css_module_import",
            "fix_async_component",
            "fix_context_usage",
        ]:
            skill = library.get_skill(skill_id)
            assert len(skill.fix_template) > 100, f"{skill_id} has short template"
            assert "{" in skill.fix_template, f"{skill_id} missing template variables"

    def test_skill_tags(self):
        """Test that skills have relevant tags."""
        library = SkillLibrary()
        seed_frontend_skills(library)

        # All frontend skills should have react tag
        for skill_id in [
            "fix_react_hook_dependency",
            "add_key_prop",
            "fix_state_mutation",
            "fix_context_usage",
        ]:
            skill = library.get_skill(skill_id)
            assert "react" in skill.tags

        # TypeScript-related skills should have typescript tag
        typescript_skills = ["fix_prop_types", "fix_event_handler", "fix_import_path"]
        for skill_id in typescript_skills:
            skill = library.get_skill(skill_id)
            assert "typescript" in skill.tags or "types" in skill.tags

    def test_tsc_normalizer_integration(self):
        """Test that TSC normalizer is registered."""
        loop = FrontendDevLoop(project_dir="/tmp/test-project", max_iterations=5)

        registry = loop.executor.feedback_registry
        assert registry.has_normalizer("tsc")

        # Test normalization with mock tsc output
        mock_output = {
            "exit_code": 1,
            "stdout": "src/Button.tsx(45,10): error TS2322: Type 'string' is not assignable to type 'number'.",
            "stderr": "",
            "tool": "tsc",
        }

        feedback = registry.normalize("tsc", mock_output)

        assert not feedback.success
        assert feedback.exit_code == 1
        assert feedback.category.value == "type_error"
        assert len(feedback.salient_fragments) > 0
        assert "TS2322" in feedback.salient_fragments[0].message

    def test_vitest_normalizer_integration(self):
        """Test that Vitest normalizer is registered."""
        loop = FrontendDevLoop(project_dir="/tmp/test-project", max_iterations=5)

        registry = loop.executor.feedback_registry
        assert registry.has_normalizer("vitest")

        # Test normalization with mock vitest output
        mock_output = {
            "exit_code": 1,
            "stdout": '❌ Button > renders correctly\n    AssertionError: expected "Submit" to equal "Click Me"\n    at Button.test.tsx:15:20',
            "stderr": "",
            "tool": "vitest",
        }

        feedback = registry.normalize("vitest", mock_output)

        assert not feedback.success
        assert feedback.exit_code == 1
        assert feedback.category.value == "test_failure"
        assert len(feedback.salient_fragments) > 0

    def test_validation_detection(self):
        """Test build command detection."""
        loop = FrontendDevLoop(project_dir="/tmp/test-project", max_iterations=5)

        # Default should be npm run build
        build_cmd = loop._detect_build_command()
        assert build_cmd == ["npm", "run", "build"]

    def test_loop_reset(self):
        """Test loop state reset."""
        loop = FrontendDevLoop(project_dir="/tmp/test-project", max_iterations=5)

        # Simulate some state
        loop.validation_history = [{"build": True, "test": False}]
        loop.executor.adaptive_limits.iterations_completed = 3

        # Reset
        loop.reset()

        assert len(loop.validation_history) == 0
        assert loop.executor.adaptive_limits.iterations_completed == 0
        assert loop.executor.current_trace is None

    def test_stats_retrieval(self):
        """Test stats retrieval."""
        loop = FrontendDevLoop(project_dir="/tmp/test-project", max_iterations=5)

        stats = loop.get_stats()

        assert "total_iterations" in stats
        assert "max_iterations" in stats
        assert "skill_library_stats" in stats
        assert "validation_history" in stats

        # Verify skill stats
        assert stats["skill_library_stats"]["total_skills"] >= 10

    def test_skill_context_extraction(self):
        """Test that skills can extract context from feedback."""
        library = SkillLibrary()
        seed_frontend_skills(library)

        skill = library.get_skill("fix_react_hook_dependency")

        # Mock feedback with primary error
        from core.feedback_schema import FeedbackCategory, NormalizedFeedback, SalientFragment

        feedback = NormalizedFeedback(
            success=False,
            exit_code=1,
            category=FeedbackCategory.BUILD_ERROR,
            is_deterministic_blocker=False,
            blocker_type=None,
            salient_fragments=[
                SalientFragment(
                    message="React Hook useEffect has a missing dependency: 'userId'",
                    severity="error",
                    line_number=45,
                    file_path="src/components/Profile.tsx",
                    context="useEffect hook",
                )
            ],
            suggested_scope="src/components/Profile.tsx",
            signal_quality_score=0.9,
            feedback_source="eslint",
            stdout="",
            stderr="",
            timestamp=0,
            tool_version="8.0.0",
            auto_summary="",
        )

        context = skill.extract_context(feedback)

        assert "file_path" in context
        assert context["file_path"] == "src/components/Profile.tsx"
        assert "line_number" in context
        assert context["line_number"] == 45


@pytest.mark.integration
class TestFrontendDevLoopIntegration:
    """Integration tests requiring actual project setup."""

    @pytest.mark.skip(reason="Requires real project setup")
    def test_full_component_build_loop(self):
        """
        Full integration test: build component with iteration.

        This test would require:
        - Real Next.js/React project
        - Component scaffold with intentional errors
        - Full validation toolchain (tsc, vitest, eslint)

        For Phase 1 pilot testing.
        """
        pass

    @pytest.mark.skip(reason="Requires real project setup")
    def test_remediation_application(self):
        """
        Test that remediation skills are actually applied and fix errors.

        For Phase 1 pilot testing.
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
