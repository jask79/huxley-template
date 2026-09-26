"""Unit tests for decider.py — the 5-branch decision tree.

Run with:
    python3 tools/skill-curator/tests/test_decider.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from lib.decider import (  # noqa: E402
    ACTION_ARCHIVE,
    ACTION_IMPROVE,
    ACTION_KEEP,
    ACTION_MERGE,
    Decision,
    build_similarity_matrix,
    decide_all,
    decide_for_skill,
    find_clusters,
    pick_leader,
)
from lib.scorer import (  # noqa: E402
    SkillRecord,
    compute_idf,
    extract_top_tools,
    tokenize_body,
    tokenize_description,
)


def _build_record(
    name: str,
    body: str,
    tmpdir: Path,
    use_count: int = 0,
    last_used_at: str | None = None,
    first_used_at: str | None = None,
    feedback: list | None = None,
    file_mtime_days_ago: float = 100.0,
    pinned: bool = False,
    curated: bool = True,
) -> SkillRecord:
    skill_dir = tmpdir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(body, encoding="utf-8")
    age_seconds = file_mtime_days_ago * 86400
    target_mtime = datetime.now(timezone.utc).timestamp() - age_seconds
    os.utime(skill_path, (target_mtime, target_mtime))

    fm = {
        "name": name,
        "description": f"description for {name}",
        "metadata": {"curated": curated, "pinned": pinned},
    }
    usage_record = {
        "use_count": use_count,
        "last_used_at": last_used_at,
        "first_used_at": first_used_at,
        "feedback": feedback or [],
        "created_at": (
            datetime.now(timezone.utc) - timedelta(days=file_mtime_days_ago)
        ).isoformat(),
    }
    rec = SkillRecord(
        name=name,
        path=skill_path,
        body_text=body,
        frontmatter=fm,
        usage_record=usage_record,
    )
    rec.top_tools = extract_top_tools(body)
    rec.body_tokens = tokenize_body(body)
    rec.desc_tokens = tokenize_description(fm["description"])
    return rec


# ---------------------------------------------------------------------------
# Branch 1: pinned → KEEP
# ---------------------------------------------------------------------------


class PinnedBranchTests(unittest.TestCase):
    def test_pinned_skill_always_keeps(self) -> None:
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        rec = _build_record(
            "pinned-old",
            "---\nname: pinned-old\n---\nold body content",
            tmp,
            file_mtime_days_ago=300,
            pinned=True,
            use_count=0,
        )
        idf = compute_idf([rec.body_tokens])
        decision = decide_for_skill(rec, None, None, idf, now)
        self.assertEqual(decision.action, ACTION_KEEP)
        self.assertEqual(decision.confidence, 1.0)
        self.assertIn("pinned", decision.rationale.lower())


# ---------------------------------------------------------------------------
# Branch 2: not curated → KEEP (defensive)
# ---------------------------------------------------------------------------


class NonCuratedBranchTests(unittest.TestCase):
    def test_non_curated_skill_keeps_defensively(self) -> None:
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        rec = _build_record(
            "not-curated",
            "---\nname: not-curated\n---\nbody",
            tmp,
            curated=False,
        )
        idf = compute_idf([rec.body_tokens])
        decision = decide_for_skill(rec, None, None, idf, now)
        self.assertEqual(decision.action, ACTION_KEEP)
        self.assertIn("not curated", decision.rationale.lower())


# ---------------------------------------------------------------------------
# Branch 3: in cluster → MERGE
# ---------------------------------------------------------------------------


class MergeBranchTests(unittest.TestCase):
    def test_in_cluster_non_leader_gets_merge(self) -> None:
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        body_a = (
            "---\nname: a\ndescription: deploy to vercel\nallowed-tools:\n  - Bash\n  - Read\n---\n"
            "Deploy the frontend application to vercel using cli with environment variables."
        )
        body_b = (
            "---\nname: b\ndescription: deploy to vercel\nallowed-tools:\n  - Bash\n  - Read\n---\n"
            "Deploy the frontend application to vercel using cli with environment variables."
        )
        rec_a = _build_record("a", body_a, tmp, use_count=10,
                              last_used_at=(now - timedelta(days=1)).isoformat())
        rec_b = _build_record("b", body_b, tmp, use_count=2,
                              last_used_at=(now - timedelta(days=1)).isoformat())
        idf = compute_idf([rec_a.body_tokens, rec_b.body_tokens])

        decisions, pairs, clusters = decide_all([rec_a, rec_b], idf, now)
        actions = {d.skill_name: d.action for d in decisions}

        # Both should be in a cluster; one is leader (KEEP), one is loser (MERGE)
        self.assertEqual(len(clusters), 1)
        self.assertIn(ACTION_MERGE, actions.values())
        self.assertIn(ACTION_KEEP, actions.values())

    def test_invocations_pick_leader(self) -> None:
        """Per ADR rule 1: invocations_90d more wins."""
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        body = (
            "---\nname: x\ndescription: same\nallowed-tools:\n  - Bash\n---\n"
            "identical body identical body identical body identical body."
        )
        recent = (now - timedelta(days=5)).isoformat()
        a = _build_record("a", body.replace("name: x", "name: a"), tmp,
                          use_count=20, last_used_at=recent)
        b = _build_record("b", body.replace("name: x", "name: b"), tmp,
                          use_count=2, last_used_at=recent)
        leader = pick_leader([a, b], now)
        self.assertEqual(leader.name, "a")

    def test_alphabetic_tiebreak_when_all_equal(self) -> None:
        """Per ADR rule 5: lexicographic name as final fallback."""
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        body = "---\nname: x\ndescription: same\n---\nbody"
        # Use distinct files with same mtime AND same first_used_at to equalize
        # all 4 prior tiebreakers, forcing a fall-through to alphabetic.
        common_t0 = (now - timedelta(days=100)).isoformat()
        target_mtime = now.timestamp() - 100 * 86400
        recs = []
        for n in ["zebra", "alpha"]:
            body_n = body.replace("name: x", f"name: {n}")
            r = _build_record(
                n, body_n, tmp,
                use_count=0,
                first_used_at=common_t0,
            )
            # Same mtime so file-mtime equal
            os.utime(r.path, (target_mtime, target_mtime))
            # Pad bodies to identical length (also pre-set in body_text)
            r.body_text = body_n
            recs.append(r)
        leader = pick_leader(recs, now)
        self.assertEqual(leader.name, "alpha")


# ---------------------------------------------------------------------------
# Branch 4: stale + zero-90d → ARCHIVE
# ---------------------------------------------------------------------------


class ArchiveBranchTests(unittest.TestCase):
    def test_stale_unused_skill_archives(self) -> None:
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        # 200d old, never used → S high, inv90=0
        rec = _build_record(
            "stale",
            "---\nname: stale\n---\nold body that hasn't been touched",
            tmp,
            file_mtime_days_ago=200,
            use_count=0,
            last_used_at=None,
        )
        idf = compute_idf([rec.body_tokens])
        decision = decide_for_skill(rec, None, None, idf, now)
        self.assertEqual(decision.action, ACTION_ARCHIVE)

    def test_recently_used_skill_does_not_archive(self) -> None:
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        rec = _build_record(
            "fresh",
            "---\nname: fresh\n---\nbody",
            tmp,
            file_mtime_days_ago=200,
            use_count=5,
            last_used_at=(now - timedelta(days=10)).isoformat(),
        )
        idf = compute_idf([rec.body_tokens])
        decision = decide_for_skill(rec, None, None, idf, now)
        self.assertNotEqual(decision.action, ACTION_ARCHIVE)


# ---------------------------------------------------------------------------
# Branch 5: bad quality → IMPROVE
# ---------------------------------------------------------------------------


class ImproveBranchTests(unittest.TestCase):
    def test_low_quality_with_enough_negatives_improves(self) -> None:
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        # Recent use to avoid ARCHIVE branch; 5 negatives → Q low
        recent = (now - timedelta(days=5)).isoformat()
        feedback = [{"signal": "negative", "ts": recent} for _ in range(5)]
        rec = _build_record(
            "bad",
            "---\nname: bad\n---\nbody",
            tmp,
            file_mtime_days_ago=10,  # young, low S
            use_count=10,
            last_used_at=recent,
            feedback=feedback,
        )
        idf = compute_idf([rec.body_tokens])
        decision = decide_for_skill(rec, None, None, idf, now)
        self.assertEqual(decision.action, ACTION_IMPROVE)

    def test_low_quality_below_neg_floor_does_not_improve(self) -> None:
        """n_neg ≥ 5 floor — only 4 negatives should NOT trigger IMPROVE."""
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        recent = (now - timedelta(days=5)).isoformat()
        feedback = [{"signal": "negative", "ts": recent} for _ in range(4)]
        rec = _build_record(
            "barely-bad",
            "---\nname: barely-bad\n---\nbody",
            tmp,
            file_mtime_days_ago=10,
            use_count=10,
            last_used_at=recent,
            feedback=feedback,
        )
        idf = compute_idf([rec.body_tokens])
        decision = decide_for_skill(rec, None, None, idf, now)
        self.assertNotEqual(decision.action, ACTION_IMPROVE)


# ---------------------------------------------------------------------------
# Default: KEEP
# ---------------------------------------------------------------------------


class KeepBranchTests(unittest.TestCase):
    def test_active_healthy_skill_keeps(self) -> None:
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        recent = (now - timedelta(days=2)).isoformat()
        rec = _build_record(
            "good",
            "---\nname: good\n---\nbody",
            tmp,
            file_mtime_days_ago=20,
            use_count=15,
            last_used_at=recent,
        )
        idf = compute_idf([rec.body_tokens])
        decision = decide_for_skill(rec, None, None, idf, now)
        self.assertEqual(decision.action, ACTION_KEEP)


# ---------------------------------------------------------------------------
# Cluster wins over staleness (ADR section 4: branch 3 before branch 4)
# ---------------------------------------------------------------------------


class BranchOrderingTests(unittest.TestCase):
    def test_cluster_takes_precedence_over_staleness(self) -> None:
        """A stale skill that's also in a merge cluster should MERGE, not ARCHIVE."""
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        body = (
            "---\nname: x\ndescription: same workflow\nallowed-tools:\n  - Bash\n---\n"
            "identical body content " * 20
        )
        # Both stale (no recent use) — but in a cluster
        a = _build_record("a", body.replace("name: x", "name: a"), tmp,
                          file_mtime_days_ago=200, use_count=20,
                          last_used_at=(now - timedelta(days=2)).isoformat())
        b = _build_record("b", body.replace("name: x", "name: b"), tmp,
                          file_mtime_days_ago=200, use_count=0)
        idf = compute_idf([a.body_tokens, b.body_tokens])

        decisions, pairs, clusters = decide_all([a, b], idf, now)
        actions = {d.skill_name: d.action for d in decisions}
        # b is stale BUT in cluster — should be MERGE, not ARCHIVE
        if len(clusters) >= 1:
            self.assertNotEqual(actions["b"], ACTION_ARCHIVE)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class DeterminismTests(unittest.TestCase):
    def test_same_input_yields_same_output(self) -> None:
        now = datetime.now(timezone.utc)
        tmp = Path(tempfile.mkdtemp())
        recs = [
            _build_record(f"s{i}", f"---\nname: s{i}\n---\nbody {i}", tmp)
            for i in range(5)
        ]
        idf = compute_idf([r.body_tokens for r in recs])

        d1, p1, c1 = decide_all(recs, idf, now)
        d2, p2, c2 = decide_all(recs, idf, now)
        # Action lists identical
        self.assertEqual([d.action for d in d1], [d.action for d in d2])
        # Pair ordering identical
        self.assertEqual([(p.a, p.b, p.r) for p in p1], [(p.a, p.b, p.r) for p in p2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
