"""Unit tests for hash-based dedupe.

Run with:
    python3 tools/skill-curator/tests/test_deduper.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from lib.deduper import (  # noqa: E402
    _hash_skill_md,
    collect_existing_hashes,
    hash_top_tools,
    has_duplicate,
)
from lib.extractor import SessionSummary, ToolCall  # noqa: E402


def _build_summary(tools: list[str]) -> SessionSummary:
    s = SessionSummary(session_id="test")
    for t in tools:
        s.tool_calls.append(ToolCall(name=t, input_summary="(test)"))
    return s


class HashCollisionTests(unittest.TestCase):
    def test_same_tool_set_same_hash(self) -> None:
        a = _build_summary(["Bash", "Read", "Write", "Edit", "Bash"])
        b = _build_summary(["Read", "Bash", "Edit", "Write", "Bash"])
        # Both have top_tools = sorted top 5 = ["Bash","Edit","Read","Write"]
        self.assertEqual(hash_top_tools(a.top_tools), hash_top_tools(b.top_tools))

    def test_different_tool_set_different_hash(self) -> None:
        a = _build_summary(["Bash", "Read", "Write"])
        b = _build_summary(["Glob", "Grep", "Task"])
        self.assertNotEqual(hash_top_tools(a.top_tools), hash_top_tools(b.top_tools))

    def test_hash_is_stable_across_invocations(self) -> None:
        a = _build_summary(["Read", "Edit"])
        h1 = hash_top_tools(a.top_tools)
        h2 = hash_top_tools(a.top_tools)
        self.assertEqual(h1, h2)


class SkillMdHashTests(unittest.TestCase):
    def test_hashes_existing_skill_with_allowed_tools_block(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            skills = Path(td) / "skills"
            (skills / "my-skill").mkdir(parents=True)
            (skills / "my-skill" / "SKILL.md").write_text(
                "---\n"
                "name: my-skill\n"
                "description: test skill\n"
                "allowed-tools:\n"
                "  - Bash\n"
                "  - Read\n"
                "---\n\n# My Skill\n\nDoes things.\n",
                encoding="utf-8",
            )
            hashes = collect_existing_hashes(skills)
            self.assertEqual(len(hashes), 1)
            expected = hash_top_tools(["Bash", "Read"])
            self.assertIn(expected, hashes)

    def test_skips_excluded_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            skills = Path(td) / "skills"
            (skills / "_proposed" / "draft").mkdir(parents=True)
            (skills / "_proposed" / "draft" / "SKILL.md").write_text(
                "---\nname: draft\ndescription: x\nallowed-tools:\n  - Bash\n---\nbody",
                encoding="utf-8",
            )
            hashes = collect_existing_hashes(skills)
            self.assertEqual(len(hashes), 0)

    def test_dedupe_detects_session_collision_with_existing_skill(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            skills = Path(td) / "skills"
            proposed = skills / "_proposed"
            proposed.mkdir(parents=True)
            (skills / "git-helper").mkdir(parents=True)
            (skills / "git-helper" / "SKILL.md").write_text(
                "---\n"
                "name: git-helper\n"
                "description: git\n"
                "allowed-tools:\n"
                "  - Bash\n"
                "  - Read\n"
                "  - Edit\n"
                "---\n\n# Git Helper\n",
                encoding="utf-8",
            )
            session = _build_summary(["Bash", "Read", "Edit", "Bash", "Bash"])
            is_dup, h = has_duplicate(session, skills, proposed)
            self.assertTrue(is_dup, f"expected dedupe match, hash={h}")

    def test_dedupe_detects_collision_with_existing_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            skills = Path(td) / "skills"
            proposed = skills / "_proposed"
            (proposed / "draft-foo").mkdir(parents=True)
            (proposed / "draft-foo" / "SKILL.md").write_text(
                "---\n"
                "name: draft-foo\n"
                "description: x\n"
                "allowed-tools:\n"
                "  - Glob\n"
                "  - Grep\n"
                "---\nsome body content here that is at least somewhat substantial.",
                encoding="utf-8",
            )
            session = _build_summary(["Glob", "Grep", "Glob"])
            is_dup, _ = has_duplicate(session, skills, proposed)
            self.assertTrue(is_dup)

    def test_no_collision_for_distinct_tool_sets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            skills = Path(td) / "skills"
            proposed = skills / "_proposed"
            proposed.mkdir(parents=True)
            (skills / "thing").mkdir(parents=True)
            (skills / "thing" / "SKILL.md").write_text(
                "---\nname: thing\ndescription: x\nallowed-tools:\n  - Bash\n  - Write\n---\nbody",
                encoding="utf-8",
            )
            session = _build_summary(["Glob", "Grep", "Task"])
            is_dup, _ = has_duplicate(session, skills, proposed)
            self.assertFalse(is_dup)


if __name__ == "__main__":
    unittest.main()
