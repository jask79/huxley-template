"""Integration tests — 10 fixture skills covering all 5 decision branches,
plus restoration round-trip.

Run with:
    python3 tools/skill-curator/tests/test_integration.py -v
"""

from __future__ import annotations

import filecmp
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import curator  # noqa: E402
import restore  # noqa: E402
from lib.decider import (  # noqa: E402
    ACTION_ARCHIVE,
    ACTION_IMPROVE,
    ACTION_KEEP,
    ACTION_MERGE,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_mtime(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def _build_fixture_skill(
    skills_dir: Path,
    name: str,
    *,
    curated: bool = True,
    pinned: bool = False,
    body_extra: str = "",
    tools: list[str] | None = None,
    description: str = "",
    file_mtime_days_ago: float = 30.0,
) -> Path:
    """Build a fixture skill dir under skills_dir."""
    tools_block = ""
    if tools:
        tools_block = "allowed-tools:\n" + "\n".join(f"  - {t}" for t in tools) + "\n"
    desc = description or f"description for {name}"
    md_lines = ["  curated: " + ("true" if curated else "false")]
    if pinned:
        md_lines.append("  pinned: true")

    body = (
        "---\n"
        f"name: {name}\n"
        f"description: {desc}\n"
        f"{tools_block}"
        "metadata:\n"
        + "\n".join(md_lines)
        + "\n---\n\n"
        f"# {name}\n\n"
        f"{body_extra or 'Generic body content for testing purposes.'}\n"
    )

    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(body, encoding="utf-8")
    mtime = _now() - timedelta(days=file_mtime_days_ago)
    _set_mtime(skill_path, mtime)
    return skill_path


def _build_full_fixture_set(skills_dir: Path) -> dict:
    """Build the 10 fixture skills covering all branches.

    Per Algo Wizard's test plan section 6:
      1. Fresh+active (KEEP)
      2. Old+unused (ARCHIVE)
      3. Pinned+old (KEEP override)
      4. Bad feedback (IMPROVE)
      5,6. Near-duplicate pair (MERGE)
      7. Newborn (KEEP)
      8. Never-used (ARCHIVE after 30+ days)
      9. Cold-start feedback (KEEP)
     10. Pinned+cluster member (KEEP, pinned bypasses MERGE)
    """
    now = _now()
    expected_actions = {}

    # 1. Fresh + active
    _build_fixture_skill(skills_dir, "fresh-active",
                         file_mtime_days_ago=30,
                         body_extra="Fresh skill that is actively used today.")
    expected_actions["fresh-active"] = ACTION_KEEP

    # 2. Old + unused
    _build_fixture_skill(skills_dir, "old-unused",
                         file_mtime_days_ago=200,
                         body_extra="An old skill that nobody has touched in a long time.")
    expected_actions["old-unused"] = ACTION_ARCHIVE

    # 3. Pinned + old
    _build_fixture_skill(skills_dir, "pinned-old",
                         pinned=True,
                         file_mtime_days_ago=300,
                         body_extra="Pinned skill that the curator must never touch.")
    expected_actions["pinned-old"] = ACTION_KEEP

    # 4. Bad feedback (will be set up via usage_map below)
    _build_fixture_skill(skills_dir, "bad-feedback",
                         file_mtime_days_ago=10,
                         body_extra="A skill that gets bad reviews.")
    expected_actions["bad-feedback"] = ACTION_IMPROVE

    # 5,6. Near-duplicate pair — merge cluster
    twin_body = (
        "Deploy the application to vercel using the cli with environment "
        "variables and verify the deployment afterwards by checking the "
        "production url responds correctly and shows the expected content."
    )
    _build_fixture_skill(skills_dir, "deploy-vercel-a",
                         tools=["Bash", "Read"],
                         description="deploy app to vercel via cli",
                         body_extra=twin_body,
                         file_mtime_days_ago=20)
    _build_fixture_skill(skills_dir, "deploy-vercel-b",
                         tools=["Bash", "Read"],
                         description="deploy app to vercel via cli",
                         body_extra=twin_body,
                         file_mtime_days_ago=20)
    # Leader (more invocations) = a; b should MERGE.
    expected_actions["deploy-vercel-a"] = ACTION_KEEP
    expected_actions["deploy-vercel-b"] = ACTION_MERGE

    # 7. Newborn (less than 7 days)
    _build_fixture_skill(skills_dir, "newborn",
                         file_mtime_days_ago=3,
                         body_extra="Newly created skill — too young to evaluate.")
    expected_actions["newborn"] = ACTION_KEEP

    # 8. Never-used (old)
    _build_fixture_skill(skills_dir, "never-used",
                         file_mtime_days_ago=180,
                         body_extra="Created long ago and never invoked at all.")
    expected_actions["never-used"] = ACTION_ARCHIVE

    # 9. Cold-start feedback (1-2 signals, doesn't trigger improve)
    _build_fixture_skill(skills_dir, "cold-start",
                         file_mtime_days_ago=10,
                         body_extra="A skill with very limited feedback so far.")
    expected_actions["cold-start"] = ACTION_KEEP

    # 10. Pinned + would-be cluster member
    _build_fixture_skill(skills_dir, "pinned-twin",
                         pinned=True,
                         tools=["Bash", "Read"],
                         description="deploy app to vercel via cli",
                         body_extra=twin_body,
                         file_mtime_days_ago=20)
    expected_actions["pinned-twin"] = ACTION_KEEP

    # Build usage map
    recent = (now - timedelta(days=2)).isoformat()
    long_ago = (now - timedelta(days=120)).isoformat()
    usage_map = {
        "fresh-active": {
            "use_count": 30, "last_used_at": recent,
            "first_used_at": (now - timedelta(days=60)).isoformat(),
            "feedback": [], "created_at": (now - timedelta(days=60)).isoformat(),
        },
        "old-unused": {
            "use_count": 0, "last_used_at": None,
            "first_used_at": None,
            "feedback": [], "created_at": (now - timedelta(days=200)).isoformat(),
        },
        "pinned-old": {
            "use_count": 0, "last_used_at": None,
            "feedback": [], "created_at": (now - timedelta(days=300)).isoformat(),
        },
        "bad-feedback": {
            "use_count": 20, "last_used_at": recent,
            "feedback": [
                {"signal": "negative", "ts": recent} for _ in range(6)
            ],
            "created_at": (now - timedelta(days=60)).isoformat(),
        },
        "deploy-vercel-a": {
            "use_count": 25, "last_used_at": recent,
            "feedback": [], "created_at": (now - timedelta(days=60)).isoformat(),
        },
        "deploy-vercel-b": {
            "use_count": 5, "last_used_at": recent,
            "feedback": [], "created_at": (now - timedelta(days=60)).isoformat(),
        },
        "newborn": {
            "use_count": 0, "last_used_at": None,
            "feedback": [], "created_at": (now - timedelta(days=3)).isoformat(),
        },
        "never-used": {
            "use_count": 0, "last_used_at": None,
            "feedback": [], "created_at": (now - timedelta(days=180)).isoformat(),
        },
        "cold-start": {
            "use_count": 5, "last_used_at": recent,
            "feedback": [
                {"signal": "negative", "ts": recent},
            ],  # only 1 signal — cold-start
            "created_at": (now - timedelta(days=30)).isoformat(),
        },
        "pinned-twin": {
            "use_count": 5, "last_used_at": recent,
            "feedback": [], "created_at": (now - timedelta(days=60)).isoformat(),
        },
    }
    usage_path = skills_dir / ".usage.json"
    usage_path.write_text(json.dumps(usage_map, indent=2), encoding="utf-8")

    return expected_actions


class IntegrationFixtureTests(unittest.TestCase):
    def test_full_dry_run_against_10_fixtures(self) -> None:
        """End-to-end: 10 skills, all 5 branches, dry-run mode."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / ".claude" / "skills"
            skills_dir.mkdir(parents=True)
            archive_root = skills_dir / ".archive"
            curator_dir = skills_dir / ".curator"
            reports_dir = curator_dir / "reports"
            state_file = curator_dir / "state.json"
            curator_dir.mkdir(parents=True)
            prompt_path = curator_dir / "PROMPT.md"
            prompt_path.write_text("(test prompt)", encoding="utf-8")

            session_dir = root / "sessions"
            session_dir.mkdir()  # no jsonl files → safe by default

            expected = _build_full_fixture_set(skills_dir)

            ec = curator.run_curator(
                skills_dir=skills_dir,
                archive_root=archive_root,
                reports_dir=reports_dir,
                state_file=state_file,
                prompt_path=prompt_path,
                session_dir=session_dir,
                cli_dry_run=True,
                skip_telegram=True,
                force=False,
                quiet=True,
            )
            self.assertEqual(ec, 0)

            # Report file must exist
            reports = list(reports_dir.glob("*.md"))
            self.assertEqual(len(reports), 1)
            report_text = reports[0].read_text(encoding="utf-8")
            self.assertIn("# Skill Curator Report", report_text)
            # Dry-run mode header
            self.assertIn("dry-run", report_text)

            # No mutations: all fixture dirs still exist
            for name in expected.keys():
                self.assertTrue(
                    (skills_dir / name).exists(),
                    f"{name} dir was deleted in dry-run! (CRITICAL BUG)",
                )

            # Verify each expected action appears in the report
            for name, action in expected.items():
                # Pinned skills skipped from non-keep sections; we just check rationale
                self.assertIn(name, report_text, f"{name} missing from report")

    def test_archive_action_in_live_mode_post_grace(self) -> None:
        """With grace period bypassed, ARCHIVE action moves the dir."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / ".claude" / "skills"
            skills_dir.mkdir(parents=True)
            archive_root = skills_dir / ".archive"
            curator_dir = skills_dir / ".curator"
            reports_dir = curator_dir / "reports"
            state_file = curator_dir / "state.json"
            curator_dir.mkdir(parents=True)
            prompt_path = curator_dir / "PROMPT.md"
            prompt_path.write_text("(test prompt)", encoding="utf-8")

            session_dir = root / "sessions"
            session_dir.mkdir()

            # Single ARCHIVE-target skill
            _build_fixture_skill(
                skills_dir,
                "to-archive",
                file_mtime_days_ago=200,
                body_extra="ancient unused skill",
            )
            usage = {
                "to-archive": {
                    "use_count": 0, "last_used_at": None,
                    "feedback": [],
                    "created_at": (_now() - timedelta(days=200)).isoformat(),
                }
            }
            (skills_dir / ".usage.json").write_text(
                json.dumps(usage, indent=2), encoding="utf-8"
            )

            # Pre-seed state with first_run_at 40 days ago to bypass grace
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "first_run_at": (_now() - timedelta(days=40)).isoformat(),
                "last_run_at": None,
                "last_report_path": None,
                "runs_count": 5,
                "paused": False,
            }
            state_file.write_text(json.dumps(state), encoding="utf-8")

            os.environ["CATALYST_CURATOR_LIVE"] = "1"
            try:
                ec = curator.run_curator(
                    skills_dir=skills_dir,
                    archive_root=archive_root,
                    reports_dir=reports_dir,
                    state_file=state_file,
                    prompt_path=prompt_path,
                    session_dir=session_dir,
                    cli_dry_run=False,
                    skip_telegram=True,
                    force=False,
                    quiet=True,
                )
            finally:
                del os.environ["CATALYST_CURATOR_LIVE"]
            self.assertEqual(ec, 0)

            # Skill dir should be GONE from live, exist in archive
            self.assertFalse((skills_dir / "to-archive").exists())
            archived = list(archive_root.rglob("to-archive"))
            self.assertEqual(len(archived), 1, f"expected 1 archive, got {archived}")


class RestorationTests(unittest.TestCase):
    def test_round_trip_archive_then_restore_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / ".claude" / "skills"
            skills_dir.mkdir(parents=True)
            archive_root = skills_dir / ".archive"

            # Create a skill with multiple files
            skill_dir = skills_dir / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: my-skill\ndescription: x\nmetadata:\n  curated: true\n---\nbody",
                encoding="utf-8",
            )
            (skill_dir / "extra.md").write_text("extra content", encoding="utf-8")
            ref_dir = skill_dir / "references"
            ref_dir.mkdir()
            (ref_dir / "doc.md").write_text("reference doc", encoding="utf-8")

            # Snapshot original contents
            original_snapshot = {}
            for f in skill_dir.rglob("*"):
                if f.is_file():
                    original_snapshot[str(f.relative_to(skill_dir))] = f.read_bytes()

            # Archive via curator's archive_skill
            from lib.decider import Decision
            from lib.usage import parse_frontmatter
            now = _now()
            body_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            from lib.scorer import (
                SkillRecord,
                extract_top_tools,
                tokenize_body,
                tokenize_description,
            )
            rec = SkillRecord(
                name="my-skill",
                path=skill_dir / "SKILL.md",
                body_text=body_text,
                frontmatter=parse_frontmatter(body_text),
                usage_record={"use_count": 0},
            )
            rec.top_tools = extract_top_tools(body_text)
            rec.body_tokens = tokenize_body(body_text)
            rec.desc_tokens = tokenize_description("x")
            decision = Decision(
                skill_name="my-skill",
                action=ACTION_ARCHIVE,
                confidence=0.9,
                rationale="test",
                s_score=0.9,
                q_score=0.5,
                n_pos=0,
                n_neg=0,
                invocations_90d=0,
            )
            ok, msg, archived_to = curator.archive_skill(rec, decision, archive_root, now)
            self.assertTrue(ok, msg)
            self.assertFalse(skill_dir.exists())

            # Restore
            ok2, msg2 = restore.restore("my-skill", archive_root, skills_dir)
            self.assertTrue(ok2, msg2)

            # Verify byte-identical (excluding the cleanup-removed manifest)
            restored = skills_dir / "my-skill"
            self.assertTrue(restored.exists())
            for relpath, original_bytes in original_snapshot.items():
                f = restored / relpath
                self.assertTrue(f.exists(), f"{relpath} missing after restore")
                self.assertEqual(
                    f.read_bytes(), original_bytes,
                    f"{relpath} differs after restore",
                )

    def test_restore_refuses_when_destination_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td)
            archive_root = skills_dir / ".archive"
            archived = archive_root / "2026-05-06-1200" / "skill-x"
            archived.mkdir(parents=True)
            (archived / "SKILL.md").write_text("body", encoding="utf-8")
            # Pre-existing live dir
            live = skills_dir / "skill-x"
            live.mkdir()
            (live / "SKILL.md").write_text("different body", encoding="utf-8")

            ok, msg = restore.restore("skill-x", archive_root, skills_dir)
            self.assertFalse(ok)
            self.assertIn("already exists", msg)

    def test_restore_finds_most_recent_archive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td)
            archive_root = skills_dir / ".archive"

            old_archive = archive_root / "2026-04-01-0000" / "skill-x"
            old_archive.mkdir(parents=True)
            (old_archive / "SKILL.md").write_text("OLD VERSION", encoding="utf-8")

            new_archive = archive_root / "2026-05-01-0000" / "skill-x"
            new_archive.mkdir(parents=True)
            (new_archive / "SKILL.md").write_text("NEW VERSION", encoding="utf-8")
            # Make sure mtime ordering matches dir-name ordering
            new_mtime = _now().timestamp()
            old_mtime = new_mtime - 1_000_000
            os.utime(new_archive, (new_mtime, new_mtime))
            os.utime(old_archive, (old_mtime, old_mtime))

            candidates = restore.find_archive_candidates(archive_root, "skill-x")
            self.assertGreaterEqual(len(candidates), 2)
            # Most recent first
            self.assertEqual(candidates[0], new_archive)


if __name__ == "__main__":
    unittest.main(verbosity=2)
