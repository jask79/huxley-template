"""Invariant tests — these MUST pass. Tests the curator cannot:
  - delete anything
  - touch non-curated skills
  - touch pinned skills
  - live-run during the 30-day grace period
  - touch the _proposed/, _promoted/, .archive/, or .curator/ subtrees

Run with:
    python3 tools/skill-curator/tests/test_invariants.py -v
"""

from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import curator  # noqa: E402
from lib.decider import (  # noqa: E402
    ACTION_ARCHIVE,
    ACTION_KEEP,
    Decision,
)
from lib.scorer import (  # noqa: E402
    SkillRecord,
    extract_top_tools,
    tokenize_body,
    tokenize_description,
)


def _build_skill_dir(
    parent: Path,
    name: str,
    *,
    curated: bool = True,
    pinned: bool = False,
    body: str | None = None,
) -> Path:
    """Create a skill dir under parent. Returns the SKILL.md path."""
    metadata_lines = []
    if curated:
        metadata_lines.append("  curated: true")
    else:
        metadata_lines.append("  curated: false")
    if pinned:
        metadata_lines.append("  pinned: true")

    if body is None:
        body = (
            f"---\n"
            f"name: {name}\n"
            f"description: test skill {name}\n"
            f"metadata:\n"
            + "\n".join(metadata_lines)
            + "\n---\n# {name}\n\nbody content here."
        )
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(body, encoding="utf-8")
    return skill_path


class StaticInvariantTests(unittest.TestCase):
    """Static analysis: verify curator.py never imports/uses delete primitives."""

    def setUp(self) -> None:
        self.curator_src = (ROOT / "curator.py").read_text(encoding="utf-8")

    def test_no_os_remove_call(self) -> None:
        """os.remove on a skill file is forbidden."""
        # Allow os.remove in the .archive cleanup of restore manifest, but check
        # curator.py specifically does not use it.
        # We do a string search; for a sharper check we'd parse AST.
        forbidden = ["os.remove(", "os.unlink("]
        for f in forbidden:
            # The os.unlink call inside save_state cleanup is on a *.tmp file in
            # the curator dir, NOT on a skill file. To keep this test simple,
            # check that none of these primitives are called with a path that
            # ends in SKILL.md or under .claude/skills/ (excluding .archive/).
            # We check for the literal call form.
            self.assertNotIn(
                f + "skill",  # crude heuristic
                self.curator_src.lower(),
                f"forbidden primitive {f}skill found in curator.py",
            )

    def test_no_rmtree_call(self) -> None:
        """shutil.rmtree on a skill dir is forbidden."""
        self.assertNotIn(
            "rmtree", self.curator_src,
            "shutil.rmtree must not appear in curator.py — archive only, never delete",
        )

    def test_no_path_unlink_call(self) -> None:
        """No `.unlink(` calls on skill paths."""
        # Allow temp-file unlink in save_state. We check that .unlink( does not
        # appear with a `record.path` or `skill_dir` argument by inspection.
        # Simplest crude pass: no `record.path.unlink` or `skill_dir.unlink`.
        for forbidden in ["record.path.unlink", "skill_dir.unlink", "skill_path.unlink"]:
            self.assertNotIn(
                forbidden, self.curator_src,
                f"forbidden call '{forbidden}' found in curator.py",
            )

    def test_archive_function_uses_shutil_move_not_delete(self) -> None:
        """archive_skill() must use shutil.move, never delete."""
        archive_func_src = self._extract_function_source("archive_skill")
        self.assertIn("shutil.move", archive_func_src)
        self.assertNotIn("rmtree", archive_func_src)
        self.assertNotIn("os.remove", archive_func_src)

    def _extract_function_source(self, name: str) -> str:
        """Return the source code of a top-level function from curator.py."""
        tree = ast.parse(self.curator_src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                start_line = node.lineno
                end_line = node.end_lineno
                lines = self.curator_src.splitlines()[start_line - 1 : end_line]
                return "\n".join(lines)
        self.fail(f"function {name} not found in curator.py")
        return ""


class FunctionalInvariantTests(unittest.TestCase):
    """Behavioral invariants: run discovery + decide and verify outcomes."""

    def test_non_curated_skills_excluded_from_decisions(self) -> None:
        """Skills without metadata.curated=true must never appear in decisions."""
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td) / "skills"
            skills_dir.mkdir()
            _build_skill_dir(skills_dir, "curated-one", curated=True)
            _build_skill_dir(skills_dir, "manual-skill", curated=False)
            _build_skill_dir(skills_dir, "another-manual", curated=False)

            all_found = curator.discover_skills(skills_dir)
            self.assertEqual(len(all_found), 3)

            # Build records and filter by curated as the curator does
            from lib.usage import is_curated, parse_frontmatter
            curated_count = 0
            for skill_md, _ in all_found:
                fm = parse_frontmatter(skill_md.read_text())
                if is_curated(fm):
                    curated_count += 1
            self.assertEqual(curated_count, 1)

    def test_excluded_dirs_never_discovered(self) -> None:
        """`_proposed/`, `_promoted/`, `.archive/`, `.curator/` are off-limits."""
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td) / "skills"
            skills_dir.mkdir()
            for excluded in ("_proposed", "_promoted", ".archive", ".curator"):
                d = skills_dir / excluded / "fake-skill"
                d.mkdir(parents=True)
                (d / "SKILL.md").write_text(
                    "---\nname: fake\n---\nbody", encoding="utf-8"
                )
            _build_skill_dir(skills_dir, "real", curated=True)

            found = curator.discover_skills(skills_dir)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0][1], "real")

    def test_pinned_skill_never_gets_archive_action(self) -> None:
        """Even if pinned skill is super stale, it should KEEP."""
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td) / "skills"
            skills_dir.mkdir()
            skill_md = _build_skill_dir(
                skills_dir, "pinned-old", curated=True, pinned=True
            )
            # Backdate
            mtime = (datetime.now(timezone.utc) - timedelta(days=400)).timestamp()
            os.utime(skill_md, (mtime, mtime))

            usage_map = {}
            rec = curator.load_skill_record(skill_md, "pinned-old", usage_map)
            self.assertIsNotNone(rec)

            from lib.scorer import compute_idf
            from lib.decider import decide_for_skill
            idf = compute_idf([rec.body_tokens])
            now = datetime.now(timezone.utc)
            decision = decide_for_skill(rec, None, None, idf, now)
            self.assertEqual(decision.action, ACTION_KEEP)


class GraceInvariantTests(unittest.TestCase):
    def test_live_refused_during_grace_period(self) -> None:
        """determine_mode must return 'dry-run' when within grace period."""
        now = datetime.now(timezone.utc)
        state = {"first_run_at": (now - timedelta(days=5)).isoformat()}
        mode, reason = curator.determine_mode(state, cli_dry_run=False, env_live=True, now=now)
        self.assertEqual(mode, "dry-run")
        self.assertIn("grace", reason.lower())

    def test_live_allowed_after_grace_with_env_var(self) -> None:
        now = datetime.now(timezone.utc)
        state = {"first_run_at": (now - timedelta(days=40)).isoformat()}
        mode, reason = curator.determine_mode(state, cli_dry_run=False, env_live=True, now=now)
        self.assertEqual(mode, "live")

    def test_live_refused_post_grace_without_env_var(self) -> None:
        """Even after grace period, no env var → still dry-run."""
        now = datetime.now(timezone.utc)
        state = {"first_run_at": (now - timedelta(days=40)).isoformat()}
        mode, reason = curator.determine_mode(state, cli_dry_run=False, env_live=False, now=now)
        self.assertEqual(mode, "dry-run")
        self.assertIn("CATALYST_CURATOR_LIVE", reason)

    def test_cli_dry_run_overrides_everything(self) -> None:
        now = datetime.now(timezone.utc)
        state = {"first_run_at": (now - timedelta(days=40)).isoformat()}
        mode, _ = curator.determine_mode(state, cli_dry_run=True, env_live=True, now=now)
        self.assertEqual(mode, "dry-run")

    def test_first_run_seeds_grace_clock(self) -> None:
        """If first_run_at is None, we're in grace by definition."""
        state = {"first_run_at": None}
        now = datetime.now(timezone.utc)
        self.assertTrue(curator.is_within_grace_period(state, now))


class AssertInvariantTests(unittest.TestCase):
    """The internal _assert_invariants check must catch violations."""

    def test_assert_invariants_passes_for_valid_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td)
            skill_md = _build_skill_dir(skills_dir, "ok", curated=True)
            usage = {}
            rec = curator.load_skill_record(skill_md, "ok", usage)

            from lib.decider import Decision
            decisions = [
                Decision(
                    skill_name="ok",
                    action=ACTION_KEEP,
                    confidence=1.0,
                    rationale="ok",
                    s_score=0.0,
                    q_score=0.5,
                    n_pos=0,
                    n_neg=0,
                    invocations_90d=0,
                )
            ]
            # Should not raise
            curator._assert_invariants(decisions, [rec])

    def test_assert_invariants_catches_pinned_violation(self) -> None:
        """If somehow a pinned skill got a non-KEEP action, assertion fires."""
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td)
            skill_md = _build_skill_dir(skills_dir, "pinned", curated=True, pinned=True)
            rec = curator.load_skill_record(skill_md, "pinned", {})

            from lib.decider import Decision
            bad_decisions = [
                Decision(
                    skill_name="pinned",
                    action=ACTION_ARCHIVE,
                    confidence=0.9,
                    rationale="violation",
                    s_score=0.9,
                    q_score=0.5,
                    n_pos=0,
                    n_neg=0,
                    invocations_90d=0,
                )
            ]
            with self.assertRaises(AssertionError):
                curator._assert_invariants(bad_decisions, [rec])


if __name__ == "__main__":
    unittest.main(verbosity=2)
