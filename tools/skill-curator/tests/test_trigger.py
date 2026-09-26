"""Unit tests for the trigger heuristic.

Run with:
    python3 -m unittest tools.skill-curator.tests.test_trigger
or:
    python3 tools/skill-curator/tests/test_trigger.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make `lib` importable regardless of how the test is invoked.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from lib.extractor import parse_session_jsonl  # noqa: E402
from lib.trigger import evaluate  # noqa: E402

FIXTURES = HERE / "fixtures"


class TriggerHeuristicTests(unittest.TestCase):
    def test_should_propose_session_passes(self) -> None:
        summary = parse_session_jsonl(FIXTURES / "should_propose.jsonl")
        decision = evaluate(summary)
        self.assertTrue(
            decision.propose,
            f"Expected propose=True, got reasons={decision.reasons}",
        )
        # Session has 9 calls of 4 distinct tool types and 'Perfect, ship it!' as
        # the final user message — explicit positive must trigger.
        self.assertGreaterEqual(summary.tool_call_count, 8)
        self.assertGreaterEqual(len(summary.distinct_tool_types), 3)

    def test_low_volume_session_blocked(self) -> None:
        summary = parse_session_jsonl(FIXTURES / "should_skip_low_volume.jsonl")
        decision = evaluate(summary)
        self.assertFalse(decision.propose)
        self.assertTrue(any("volume" in r for r in decision.reasons))

    def test_low_diversity_session_blocked(self) -> None:
        summary = parse_session_jsonl(FIXTURES / "should_skip_low_diversity.jsonl")
        decision = evaluate(summary)
        self.assertFalse(decision.propose)
        self.assertTrue(any("diversity" in r for r in decision.reasons))

    def test_error_exit_session_blocked(self) -> None:
        """≥8 calls, ≥3 tool types, no positive keyword, AND error markers in
        the last 3 assistant turns — must NOT propose."""
        summary = parse_session_jsonl(FIXTURES / "should_skip_error_exit.jsonl")
        decision = evaluate(summary)
        self.assertFalse(
            decision.propose,
            f"Expected skip, got reasons={decision.reasons}",
        )
        self.assertTrue(any("success" in r for r in decision.reasons))

    def test_explicit_positive_keyword_match_is_word_bounded(self) -> None:
        """Make sure 'yes' inside 'eyes' doesn't false-trigger."""
        from lib.trigger import _has_positive_signal

        self.assertTrue(_has_positive_signal("Yes!"))
        self.assertTrue(_has_positive_signal("ship it"))
        self.assertTrue(_has_positive_signal("looks good"))
        self.assertFalse(_has_positive_signal("the eyes have it"))
        self.assertFalse(_has_positive_signal(""))
        self.assertFalse(_has_positive_signal("can you redo this?"))

    def test_clean_exit_alone_is_sufficient(self) -> None:
        """Without a positive keyword, a clean-exit session still proposes."""
        from dataclasses import replace

        summary = parse_session_jsonl(FIXTURES / "should_propose.jsonl")
        # Strip the explicit positive — only clean exit should remain.
        summary_no_pos = replace(summary, last_user_message="ok")
        decision = evaluate(summary_no_pos)
        self.assertTrue(
            decision.propose,
            f"Clean-exit-only session should still propose, got {decision.reasons}",
        )


if __name__ == "__main__":
    unittest.main()
