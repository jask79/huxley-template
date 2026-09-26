"""
Remediation skill dataclass and metadata.

Represents a reusable fix pattern with versioning and tracking.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillType(Enum):
    """Type of remediation skill."""

    CODE_FIX = "code_fix"
    DEPENDENCY_FIX = "dependency_fix"
    CONFIG_FIX = "config_fix"
    BUILD_FIX = "build_fix"
    TEST_FIX = "test_fix"


@dataclass
class SkillMetadata:
    """Metadata for skill tracking and versioning."""

    version: str
    created_at: float
    last_used: float | None = None
    success_count: int = 0
    failure_count: int = 0
    avg_fix_time_seconds: float = 0.0

    def record_success(self, fix_time: float) -> None:
        """Record successful skill application."""
        self.success_count += 1
        self.last_used = time.time()

        # Update running average
        total_time = self.avg_fix_time_seconds * (self.success_count - 1)
        self.avg_fix_time_seconds = (total_time + fix_time) / self.success_count

    def record_failure(self) -> None:
        """Record failed skill application."""
        self.failure_count += 1
        self.last_used = time.time()

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def is_reliable(self) -> bool:
        """Check if skill has proven reliability."""
        return self.success_count >= 3 and self.success_rate >= 0.7


@dataclass
class RemediationSkill:
    """
    Reusable remediation skill for fixing specific error patterns.

    A skill encapsulates:
    - Pattern matching for when to apply
    - Fix template or instructions
    - Success criteria
    - Historical performance data
    """

    # Core identification
    skill_id: str
    name: str
    description: str
    skill_type: SkillType

    # Pattern matching
    error_patterns: list[str]  # Regex patterns or keywords
    applicable_categories: list[str]  # FeedbackCategory values

    # Fix instructions
    fix_template: str  # LLM instructions or code template
    required_context: list[str]  # What info needed (e.g., "file_path", "line_number")

    # Metadata
    metadata: SkillMetadata

    # Optional constraints
    prerequisites: list[str] = field(default_factory=list)  # Other skill IDs needed first
    conflicts_with: list[str] = field(default_factory=list)  # Incompatible skills
    tags: list[str] = field(default_factory=list)  # For categorization

    def matches_error(self, error_message: str, category: str) -> bool:
        """
        Check if this skill applies to an error.

        Args:
            error_message: Error text to match against
            category: FeedbackCategory value

        Returns:
            True if skill is applicable
        """
        import re

        # Check category match
        if category not in self.applicable_categories:
            return False

        # Check pattern match
        for pattern in self.error_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True

        return False

    def extract_context(self, feedback: Any) -> dict[str, Any]:
        """
        Extract required context from feedback.

        Args:
            feedback: NormalizedFeedback object

        Returns:
            Dictionary of context values
        """
        context = {}

        primary_error = feedback.get_primary_error()
        if not primary_error:
            return context

        # Map required context to feedback fields
        if "file_path" in self.required_context:
            context["file_path"] = primary_error.file_path

        if "line_number" in self.required_context:
            context["line_number"] = primary_error.line_number

        if "error_message" in self.required_context:
            context["error_message"] = primary_error.message

        if "context_lines" in self.required_context:
            context["context_lines"] = primary_error.context

        return context

    def generate_fix_prompt(self, context: dict[str, Any]) -> str:
        """
        Generate LLM prompt for applying this skill.

        Args:
            context: Context dictionary from extract_context()

        Returns:
            Formatted prompt string
        """
        # Replace template variables
        prompt = self.fix_template
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            prompt = prompt.replace(placeholder, str(value))

        return prompt

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "skill_type": self.skill_type.value,
            "error_patterns": self.error_patterns,
            "applicable_categories": self.applicable_categories,
            "fix_template": self.fix_template,
            "required_context": self.required_context,
            "metadata": {
                "version": self.metadata.version,
                "created_at": self.metadata.created_at,
                "last_used": self.metadata.last_used,
                "success_count": self.metadata.success_count,
                "failure_count": self.metadata.failure_count,
                "avg_fix_time_seconds": self.metadata.avg_fix_time_seconds,
            },
            "prerequisites": self.prerequisites,
            "conflicts_with": self.conflicts_with,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemediationSkill":
        """Create skill from dictionary."""
        metadata = SkillMetadata(
            version=data["metadata"]["version"],
            created_at=data["metadata"]["created_at"],
            last_used=data["metadata"].get("last_used"),
            success_count=data["metadata"].get("success_count", 0),
            failure_count=data["metadata"].get("failure_count", 0),
            avg_fix_time_seconds=data["metadata"].get("avg_fix_time_seconds", 0.0),
        )

        return cls(
            skill_id=data["skill_id"],
            name=data["name"],
            description=data["description"],
            skill_type=SkillType(data["skill_type"]),
            error_patterns=data["error_patterns"],
            applicable_categories=data["applicable_categories"],
            fix_template=data["fix_template"],
            required_context=data["required_context"],
            metadata=metadata,
            prerequisites=data.get("prerequisites", []),
            conflicts_with=data.get("conflicts_with", []),
            tags=data.get("tags", []),
        )
