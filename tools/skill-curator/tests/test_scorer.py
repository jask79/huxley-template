"""Unit tests for scorer.py (S, Q, R formulas).

Run with:
    python3 tools/skill-curator/tests/test_scorer.py -v
"""

from __future__ import annotations

import math
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from lib.scorer import (  # noqa: E402
    ARCHIVE_S_THRESHOLD,
    HALF_LIFE_BASE,
    HALF_LIFE_MAX,
    HALF_LIFE_MIN,
    IMPROVE_Q_THRESHOLD,
    MERGE_R_THRESHOLD,
    SkillRecord,
    clamp,
    compute_idf,
    confidence_archive,
    confidence_improve,
    confidence_keep_active,
    confidence_merge,
    cosine_similarity,
    extract_top_tools,
    jaccard,
    quality,
    redundancy,
    staleness,
    tfidf_vector,
    tokenize_body,
    tokenize_description,
)


def _make_record(
    name: str = "test",
    body: str = "---\nname: test\ndescription: test desc\n---\n# Test\nbody",
    use_count: int = 0,
    last_used_at: str | None = None,
    first_used_at: str | None = None,
    feedback: list | None = None,
    file_mtime_days_ago: float = 100.0,  # default: 100d old file
    tmpdir: Path | None = None,
) -> SkillRecord:
    """Build a SkillRecord with controlled timestamps. Writes a temp file."""
    if tmpdir is None:
        tmpdir = Path(tempfile.mkdtemp())
    skill_dir = tmpdir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(body, encoding="utf-8")
    # Backdate mtime to simulate age
    age_seconds = file_mtime_days_ago * 86400
    target_mtime = datetime.now(timezone.utc).timestamp() - age_seconds
    import os
    os.utime(skill_path, (target_mtime, target_mtime))

    fm = {"name": name, "description": "test desc", "metadata": {"curated": True}}
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
    rec.desc_tokens = tokenize_description("test desc")
    return rec


# ---------------------------------------------------------------------------
# Staleness tests
# ---------------------------------------------------------------------------


class StalenessTests(unittest.TestCase):
    def test_newborn_returns_zero(self) -> None:
        now = datetime.now(timezone.utc)
        rec = _make_record(file_mtime_days_ago=3)  # < 7 days
        self.assertEqual(staleness(rec, now), 0.0)

    def test_old_unused_high_staleness(self) -> None:
        now = datetime.now(timezone.utc)
        # 100-day-old file, never used → S should be very high
        rec = _make_record(file_mtime_days_ago=100, use_count=0)
        s = staleness(rec, now)
        self.assertGreater(s, 0.7)
        self.assertLessEqual(s, 1.0)

    def test_recent_use_lowers_staleness(self) -> None:
        now = datetime.now(timezone.utc)
        rec = _make_record(
            file_mtime_days_ago=100,
            use_count=10,
            last_used_at=(now - timedelta(days=2)).isoformat(),
        )
        s = staleness(rec, now)
        # last_used 2 days ago → S should be small
        self.assertLess(s, 0.2)

    def test_active_skill_has_shorter_half_life(self) -> None:
        """A heavily-used skill that goes 30 days idle should be MORE stale than
        a never-hot skill at the same 30-day mark (tanh boost)."""
        now = datetime.now(timezone.utc)
        # Both: file mtime 100d ago, last_used 30d ago. Active has 50 invocations.
        last_used = (now - timedelta(days=30)).isoformat()
        active = _make_record(
            file_mtime_days_ago=100, use_count=50, last_used_at=last_used,
            first_used_at=(now - timedelta(days=100)).isoformat(),
        )
        passive = _make_record(
            file_mtime_days_ago=100, use_count=1, last_used_at=last_used,
            first_used_at=(now - timedelta(days=100)).isoformat(),
        )
        s_active = staleness(active, now)
        s_passive = staleness(passive, now)
        self.assertGreater(s_active, s_passive)

    def test_clamped_to_zero_one_range(self) -> None:
        now = datetime.now(timezone.utc)
        # 1000 days old, never used → S clamped at 1.0
        rec = _make_record(file_mtime_days_ago=1000, use_count=0)
        s = staleness(rec, now)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)

    def test_archive_threshold_at_about_52_days(self) -> None:
        """Per ADR rationale: ~52 days unused → S=0.7 with the standard 30d half-life."""
        now = datetime.now(timezone.utc)
        rec = _make_record(
            file_mtime_days_ago=100,
            use_count=0,
            last_used_at=(now - timedelta(days=52)).isoformat(),
        )
        s = staleness(rec, now)
        # Should be very close to 0.7 ± 0.05
        self.assertAlmostEqual(s, 0.7, delta=0.1)


# ---------------------------------------------------------------------------
# Quality tests
# ---------------------------------------------------------------------------


class QualityTests(unittest.TestCase):
    def test_cold_start_returns_neutral(self) -> None:
        now = datetime.now(timezone.utc)
        rec = _make_record(feedback=[])
        q, n_pos, n_neg = quality(rec, now)
        self.assertEqual(q, 0.5)
        self.assertEqual(n_pos, 0)
        self.assertEqual(n_neg, 0)

    def test_one_positive_signal_still_cold_start(self) -> None:
        now = datetime.now(timezone.utc)
        fb = [{"signal": "positive", "ts": now.isoformat()}]
        rec = _make_record(feedback=fb)
        q, _, _ = quality(rec, now)
        self.assertEqual(q, 0.5)

    def test_three_signals_exits_cold_start(self) -> None:
        now = datetime.now(timezone.utc)
        fb = [
            {"signal": "positive", "ts": now.isoformat()},
            {"signal": "positive", "ts": now.isoformat()},
            {"signal": "positive", "ts": now.isoformat()},
        ]
        rec = _make_record(feedback=fb)
        q, n_pos, n_neg = quality(rec, now)
        # Laplace: (3+1)/(3+0+2) = 4/5 = 0.8
        self.assertAlmostEqual(q, 0.8, places=2)

    def test_all_negative_below_improve_threshold(self) -> None:
        now = datetime.now(timezone.utc)
        fb = [{"signal": "negative", "ts": now.isoformat()} for _ in range(5)]
        rec = _make_record(feedback=fb)
        q, _, n_neg = quality(rec, now)
        # (0+1)/(0+5+2) ≈ 0.143 → below 0.3 threshold
        self.assertLess(q, IMPROVE_Q_THRESHOLD)
        self.assertEqual(n_neg, 5)

    def test_old_feedback_excluded_by_180_day_window(self) -> None:
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=200)).isoformat()
        fb = [{"signal": "negative", "ts": old_ts} for _ in range(10)]
        rec = _make_record(feedback=fb)
        q, n_pos, n_neg = quality(rec, now)
        # All filtered out → cold start
        self.assertEqual(q, 0.5)
        self.assertEqual(n_neg, 0)

    def test_neutral_counts_toward_total_only(self) -> None:
        now = datetime.now(timezone.utc)
        fb = [
            {"signal": "neutral", "ts": now.isoformat()},
            {"signal": "neutral", "ts": now.isoformat()},
            {"signal": "neutral", "ts": now.isoformat()},
        ]
        rec = _make_record(feedback=fb)
        q, n_pos, n_neg = quality(rec, now)
        # 3 neutrals exit cold-start, but n_pos=n_neg=0 → Laplace = 1/2 = 0.5
        self.assertEqual(q, 0.5)
        self.assertEqual(n_pos, 0)
        self.assertEqual(n_neg, 0)


# ---------------------------------------------------------------------------
# Redundancy tests
# ---------------------------------------------------------------------------


class RedundancyTests(unittest.TestCase):
    def test_jaccard_identical_sets_returns_one(self) -> None:
        self.assertEqual(jaccard(["a", "b", "c"], ["a", "b", "c"]), 1.0)

    def test_jaccard_disjoint_sets_returns_zero(self) -> None:
        self.assertEqual(jaccard(["a", "b"], ["c", "d"]), 0.0)

    def test_jaccard_empty_returns_zero(self) -> None:
        self.assertEqual(jaccard([], ["a", "b"]), 0.0)
        self.assertEqual(jaccard(["a"], []), 0.0)

    def test_cosine_identical_vectors_returns_one(self) -> None:
        v = {"a": 1.0, "b": 2.0}
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0)

    def test_cosine_disjoint_vectors_returns_zero(self) -> None:
        va = {"a": 1.0}
        vb = {"b": 1.0}
        self.assertAlmostEqual(cosine_similarity(va, vb), 0.0)

    def test_tokenize_strips_frontmatter_and_code(self) -> None:
        body = (
            "---\nname: test\n---\n"
            "# Title\n"
            "Some real text here that should be tokenized.\n"
            "```bash\necho not_real_content_in_code\n```\n"
            "More body text after fence."
        )
        tokens = tokenize_body(body)
        self.assertNotIn("not_real_content_in_code", tokens)
        self.assertNotIn("name", tokens)  # frontmatter stripped
        # "real" might be a stopword? It's not in our list.
        self.assertIn("real", tokens)
        self.assertIn("text", tokens)

    def test_tokenize_drops_stopwords_and_short_tokens(self) -> None:
        tokens = tokenize_body("---\n---\nThe quick brown fox is")
        self.assertNotIn("the", tokens)  # stopword
        self.assertNotIn("is", tokens)  # too short
        self.assertIn("quick", tokens)

    def test_redundancy_identical_skills_high(self) -> None:
        body = (
            "---\nname: a\ndescription: a thing\nallowed-tools:\n  - Bash\n  - Read\n---\n"
            "# Workflow\nDo the thing with bash and read."
        )
        tmp = Path(tempfile.mkdtemp())
        rec_a = _make_record(name="a", body=body, tmpdir=tmp)
        rec_b = _make_record(name="b", body=body.replace("name: a", "name: b"), tmpdir=tmp)
        idf = compute_idf([rec_a.body_tokens, rec_b.body_tokens])
        r, j, c, d = redundancy(rec_a, rec_b, idf)
        self.assertGreater(r, 0.8)

    def test_redundancy_disjoint_skills_low(self) -> None:
        body_a = (
            "---\nname: a\ndescription: refactor python imports\nallowed-tools:\n  - Read\n  - Edit\n---\n"
            "Do refactoring of python module imports systematically."
        )
        body_b = (
            "---\nname: b\ndescription: deploy frontend\nallowed-tools:\n  - Bash\n  - WebFetch\n---\n"
            "Deploy the frontend to vercel using cli commands."
        )
        tmp = Path(tempfile.mkdtemp())
        rec_a = _make_record(name="a", body=body_a, tmpdir=tmp)
        rec_b = _make_record(name="b", body=body_b, tmpdir=tmp)
        idf = compute_idf([rec_a.body_tokens, rec_b.body_tokens])
        r, j, c, d = redundancy(rec_a, rec_b, idf)
        self.assertLess(r, 0.5)

    def test_redundancy_clamped_to_unit_interval(self) -> None:
        body = (
            "---\nname: x\ndescription: test\nallowed-tools:\n  - Bash\n---\nbody"
        )
        tmp = Path(tempfile.mkdtemp())
        rec = _make_record(name="x", body=body, tmpdir=tmp)
        idf = compute_idf([rec.body_tokens])
        r, _, _, _ = redundancy(rec, rec, idf)
        self.assertGreaterEqual(r, 0.0)
        self.assertLessEqual(r, 1.0)


# ---------------------------------------------------------------------------
# Confidence tests
# ---------------------------------------------------------------------------


class ConfidenceTests(unittest.TestCase):
    def test_archive_confidence_at_threshold_is_zero(self) -> None:
        self.assertEqual(confidence_archive(ARCHIVE_S_THRESHOLD), 0.0)

    def test_archive_confidence_at_one_is_one(self) -> None:
        self.assertEqual(confidence_archive(1.0), 1.0)

    def test_improve_confidence_at_threshold_is_zero(self) -> None:
        # At Q exactly = threshold, qf = 0 → conf = 0
        self.assertEqual(confidence_improve(IMPROVE_Q_THRESHOLD, 10), 0.0)

    def test_improve_confidence_zero_when_no_negatives(self) -> None:
        self.assertEqual(confidence_improve(0.0, 0), 0.0)

    def test_merge_confidence_at_threshold_is_zero(self) -> None:
        self.assertEqual(confidence_merge(MERGE_R_THRESHOLD), 0.0)

    def test_merge_confidence_at_one_is_one(self) -> None:
        self.assertEqual(confidence_merge(1.0), 1.0)


# ---------------------------------------------------------------------------
# IDF / TF-IDF tests
# ---------------------------------------------------------------------------


class IdfTests(unittest.TestCase):
    def test_idf_decreases_with_frequency(self) -> None:
        # "everywhere" appears in all docs, "rare" in only one
        corpus = [
            ["everywhere", "rare"],
            ["everywhere", "common"],
            ["everywhere", "common"],
        ]
        idf = compute_idf(corpus)
        self.assertGreater(idf["rare"], idf["everywhere"])

    def test_tfidf_zero_for_empty_tokens(self) -> None:
        idf = compute_idf([["a", "b"]])
        v = tfidf_vector([], idf)
        self.assertEqual(v, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
