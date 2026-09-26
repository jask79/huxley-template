"""
Unit tests for remediation skills system.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import time

from remediation.skill import RemediationSkill, SkillMetadata, SkillType


def test_skill_creation():
    """Test creating a remediation skill."""
    metadata = SkillMetadata(version="1.0", created_at=time.time())

    skill = RemediationSkill(
        skill_id="test_skill",
        name="Test Skill",
        description="A test skill",
        skill_type=SkillType.CODE_FIX,
        error_patterns=[r"TestError"],
        applicable_categories=["test_failure"],
        fix_template="Fix: {error_message}",
        required_context=["error_message"],
        metadata=metadata,
    )

    assert skill.skill_id == "test_skill"
    assert skill.name == "Test Skill"
    assert skill.skill_type == SkillType.CODE_FIX


def test_skill_matches_error():
    """Test error pattern matching."""
    metadata = SkillMetadata(version="1.0", created_at=time.time())

    skill = RemediationSkill(
        skill_id="import_fixer",
        name="Fix Import",
        description="Fixes import errors",
        skill_type=SkillType.CODE_FIX,
        error_patterns=[r"ModuleNotFoundError", r"ImportError"],
        applicable_categories=["build_error", "runtime_error"],
        fix_template="Add import statement",
        required_context=[],
        metadata=metadata,
    )

    # Should match
    assert skill.matches_error("ModuleNotFoundError: No module named 'foo'", "build_error")
    assert skill.matches_error("ImportError: cannot import", "runtime_error")

    # Should not match
    assert not skill.matches_error("TypeError: invalid type", "type_error")
    assert not skill.matches_error("ModuleNotFoundError", "wrong_category")


def test_skill_metadata_tracking():
    """Test skill success/failure tracking."""
    metadata = SkillMetadata(version="1.0", created_at=time.time())

    # Record successes
    metadata.record_success(fix_time=5.0)
    metadata.record_success(fix_time=3.0)
    metadata.record_success(fix_time=4.0)

    assert metadata.success_count == 3
    assert metadata.avg_fix_time_seconds == 4.0  # (5 + 3 + 4) / 3

    # Record failure
    metadata.record_failure()

    assert metadata.failure_count == 1
    assert metadata.success_rate == 0.75  # 3 successes / 4 total

    # Check reliability
    assert metadata.is_reliable  # >=3 successes and >=70% success rate


def test_skill_serialization():
    """Test skill to/from dict conversion."""
    metadata = SkillMetadata(
        version="1.0", created_at=time.time(), success_count=5, failure_count=1
    )

    skill = RemediationSkill(
        skill_id="test_skill",
        name="Test Skill",
        description="Test",
        skill_type=SkillType.CODE_FIX,
        error_patterns=["error"],
        applicable_categories=["test"],
        fix_template="fix",
        required_context=["context"],
        metadata=metadata,
    )

    # Convert to dict
    skill_dict = skill.to_dict()

    # Convert back
    restored_skill = RemediationSkill.from_dict(skill_dict)

    assert restored_skill.skill_id == skill.skill_id
    assert restored_skill.metadata.success_count == 5
    assert restored_skill.metadata.failure_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
