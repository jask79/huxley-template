"""
Skill composer for LLM-based skill selection and composition.

Uses LLM to intelligently combine and apply skills.
"""

from typing import Any

from .skill import RemediationSkill


class SkillComposer:
    """
    Composes and applies remediation skills using LLM reasoning.

    Handles multi-skill scenarios, conflict detection, and fallback strategies.
    """

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize skill composer.

        Args:
            model: OpenAI model to use for composition
        """
        self.model = model
        self._openai_client = None

    @property
    def openai_client(self):
        """Lazy load OpenAI client."""
        if self._openai_client is None:
            try:
                from openai import OpenAI

                self._openai_client = OpenAI()
            except ImportError:
                raise ImportError("OpenAI package required. Install with: pip install openai")
        return self._openai_client

    def select_best_skill(
        self, candidate_skills: list[RemediationSkill], error_context: dict[str, Any], feedback: Any
    ) -> RemediationSkill | None:
        """
        Select the best skill from candidates.

        When Huxley is running in Claude Code, the LLM ({{ORCHESTRATOR_NAME}}) makes
        these decisions externally, so we don't need OpenAI API calls.
        Just returns the first (highest similarity) skill.

        Args:
            candidate_skills: List of potentially applicable skills (pre-sorted by similarity)
            error_context: Context about the error
            feedback: NormalizedFeedback object

        Returns:
            Best skill (first in list) or None if no candidates
        """
        if not candidate_skills:
            return None

        # Return first skill (highest similarity from semantic search)
        # In Huxley, Claude Code ({{ORCHESTRATOR_NAME}}) makes these decisions externally
        return candidate_skills[0]

    def compose_skills(
        self, skills: list[RemediationSkill], error_context: dict[str, Any]
    ) -> list[RemediationSkill]:
        """
        Compose multiple skills into an ordered sequence.

        Handles prerequisites, conflicts, and optimal ordering.

        Args:
            skills: List of skills to compose
            error_context: Error context

        Returns:
            Ordered list of skills to apply
        """
        if len(skills) <= 1:
            return skills

        # Check for conflicts
        conflicts = self._detect_conflicts(skills)
        if conflicts:
            # Use LLM to resolve conflicts
            skills = self._resolve_conflicts(skills, conflicts, error_context)

        # Order by prerequisites
        ordered_skills = self._order_by_prerequisites(skills)

        return ordered_skills

    def _detect_conflicts(self, skills: list[RemediationSkill]) -> list[tuple]:
        """
        Detect conflicts between skills.

        Args:
            skills: List of skills to check

        Returns:
            List of (skill1, skill2) conflict pairs
        """
        conflicts = []

        for i, skill1 in enumerate(skills):
            for skill2 in skills[i + 1 :]:
                if skill2.skill_id in skill1.conflicts_with:
                    conflicts.append((skill1, skill2))

        return conflicts

    def _resolve_conflicts(
        self, skills: list[RemediationSkill], conflicts: list[tuple], error_context: dict[str, Any]
    ) -> list[RemediationSkill]:
        """
        Resolve skill conflicts using LLM.

        Args:
            skills: Original skill list
            conflicts: List of conflict pairs
            error_context: Error context

        Returns:
            Filtered skill list with conflicts resolved
        """
        # Build prompt
        prompt = f"""
Given these conflicting remediation skills, select which ones to keep:

Error Context:
{error_context}

Conflicts:
"""
        for skill1, skill2 in conflicts:
            prompt += f"\n- {skill1.name} conflicts with {skill2.name}"

        prompt += "\n\nSkills:\n"
        for skill in skills:
            prompt += f"\n{skill.skill_id}: {skill.name}"
            prompt += f"\n  Description: {skill.description}"
            prompt += f"\n  Success Rate: {skill.metadata.success_rate:.1%}"

        prompt += "\n\nReturn comma-separated skill_ids to keep:"

        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at resolving conflicts between remediation skills.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=200,
        )

        # Parse selected skill IDs
        selected_ids = [sid.strip() for sid in response.choices[0].message.content.split(",")]

        # Filter skills
        return [skill for skill in skills if skill.skill_id in selected_ids]

    def _order_by_prerequisites(self, skills: list[RemediationSkill]) -> list[RemediationSkill]:
        """
        Order skills by prerequisite dependencies.

        Args:
            skills: List of skills to order

        Returns:
            Topologically sorted skill list
        """
        # Build dependency graph
        skill_map = {skill.skill_id: skill for skill in skills}
        ordered = []
        visited = set()

        def visit(skill: RemediationSkill):
            if skill.skill_id in visited:
                return

            # Visit prerequisites first
            for prereq_id in skill.prerequisites:
                if prereq_id in skill_map:
                    visit(skill_map[prereq_id])

            visited.add(skill.skill_id)
            ordered.append(skill)

        for skill in skills:
            visit(skill)

        return ordered

    def generate_fix_with_context(
        self, skill: RemediationSkill, error_context: dict[str, Any], feedback: Any
    ) -> str:
        """
        Generate contextualized fix instructions using skill template.

        In Huxley, Claude Code ({{ORCHESTRATOR_NAME}}) reads these templates directly,
        so we don't need external LLM calls.

        Args:
            skill: Skill to apply
            error_context: Error context
            feedback: NormalizedFeedback

        Returns:
            Detailed fix instructions from skill template
        """
        # Extract context from feedback
        skill_context = skill.extract_context(feedback)

        # Build fix prompt from skill template
        fix_prompt = skill.generate_fix_prompt(skill_context)

        # Return the skill's fix template - Claude Code ({{ORCHESTRATOR_NAME}}) reads this directly
        return fix_prompt

    def fallback_to_reasoning(self, error_context: dict[str, Any], feedback: Any) -> str:
        """
        Fall back to pure LLM reasoning when no skills match.

        Args:
            error_context: Error context
            feedback: NormalizedFeedback

        Returns:
            Fix instructions
        """
        primary_error = feedback.get_primary_error()

        prompt = f"""
Analyze this error and provide a fix:

Error Category: {feedback.category.value}
Error Message: {primary_error.message if primary_error else "Unknown"}
File: {primary_error.file_path if primary_error else "Unknown"}
Line: {primary_error.line_number if primary_error else "Unknown"}

Full Context:
{error_context}

Provide step-by-step fix instructions:
"""

        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert debugging assistant. Provide clear, actionable fixes.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )

        return response.choices[0].message.content

    def _build_selection_prompt(
        self, skills: list[RemediationSkill], error_context: dict[str, Any], feedback: Any
    ) -> str:
        """Build prompt for skill selection."""
        primary_error = feedback.get_primary_error()

        prompt = f"""
Select the best remediation skill for this error:

Error: {primary_error.message if primary_error else "Unknown"}
Category: {feedback.category.value}
File: {primary_error.file_path if primary_error else "Unknown"}

Context:
{error_context}

Available Skills:
"""

        for skill in skills:
            prompt += f"\n{skill.skill_id}: {skill.name}"
            prompt += f"\n  Description: {skill.description}"
            prompt += f"\n  Success Rate: {skill.metadata.success_rate:.1%}"
            prompt += f"\n  Avg Fix Time: {skill.metadata.avg_fix_time_seconds:.1f}s"

        prompt += "\n\nReturn the skill_id of the best match, or 'NONE' if no skill fits:"

        return prompt
