"""
A/B Evaluation Harness for the Media Workflow Engine.

Compares two sets of generation parameters systematically. Generates
the same prompt with config A and config B, evaluates both, and logs
the comparison for analysis.

Results are stored in eval/ab-results/ as JSONL for aggregation and
retrospective analysis of which configurations produce better outputs.
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.generator import MediaGenerator, GenerationError
from engine.evaluator import Evaluator
from engine.provenance import ProvenanceLogger


# Default results directory
ENGINE_ROOT = Path("{{CATALYST_ROOT}}/tools/media-engine")
AB_RESULTS_DIR = ENGINE_ROOT / "eval" / "ab-results"
AB_RESULTS_LOG = AB_RESULTS_DIR / "ab-results.jsonl"


class ABEvalHarness:
    """
    Compare two sets of generation parameters systematically.

    Generates the same prompt with config A and config B, evaluates
    both, and logs the comparison for analysis.

    The harness runs multiple trials to account for generation
    variability and provides aggregate statistics (mean, std)
    for reliable comparison.
    """

    def __init__(
        self,
        dry_run: bool = False,
        results_dir: str | Path | None = None,
    ) -> None:
        """
        Args:
            dry_run: If True, simulate generation without API calls.
            results_dir: Directory for A/B result logs. Defaults to
                         eval/ab-results/ under the engine root.
        """
        self.dry_run = dry_run
        self.generator = MediaGenerator(dry_run=dry_run)
        self.evaluator = Evaluator()
        self.provenance = ProvenanceLogger()
        self.results_dir = Path(results_dir) if results_dir else AB_RESULTS_DIR
        self.results_log = self.results_dir / "ab-results.jsonl"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def compare(
        self,
        prompt: str,
        config_a: dict[str, Any],
        config_b: dict[str, Any],
        trials: int = 3,
        label_a: str = "A",
        label_b: str = "B",
    ) -> dict[str, Any]:
        """
        Run A/B comparison.

        Generates the prompt with both configs for the specified number
        of trials. Each trial produces two outputs (one per config),
        both evaluated against the same criteria.

        Args:
            prompt: The generation prompt (same for both configs).
            config_a: First configuration dict.
            config_b: Second configuration dict.
            trials: Number of comparison trials to run (default: 3).
            label_a: Human-readable label for config A.
            label_b: Human-readable label for config B.

        Returns:
            Dict with keys:
              - prompt: the prompt used
              - trials: list of per-trial result dicts
              - summary_a: aggregate stats for config A
                  (mean, std, scores list)
              - summary_b: aggregate stats for config B
              - winner: "A", "B", or "tie"
              - winner_label: the label of the winning config
              - margin: difference in mean scores
              - duration_seconds: total execution time
        """
        print(f"A/B Comparison: {label_a} vs {label_b}")
        print(f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"Trials: {trials}")
        print()

        start_time = time.time()
        trial_results: list[dict[str, Any]] = []
        scores_a: list[float] = []
        scores_b: list[float] = []

        for trial_num in range(1, trials + 1):
            print(f"Trial {trial_num}/{trials}:")

            trial = self._run_trial(
                prompt, config_a, config_b, trial_num, label_a, label_b
            )
            trial_results.append(trial)

            if trial["score_a"] is not None:
                scores_a.append(trial["score_a"])
            if trial["score_b"] is not None:
                scores_b.append(trial["score_b"])

            print(f"  {label_a}: {trial['score_a']:.3f}  |  "
                  f"{label_b}: {trial['score_b']:.3f}")
            print()

        # Compute aggregate statistics
        summary_a = self._compute_summary(scores_a)
        summary_b = self._compute_summary(scores_b)

        # Determine winner
        mean_a = summary_a["mean"]
        mean_b = summary_b["mean"]
        margin = abs(mean_a - mean_b)

        # Tie threshold: within 0.02 of each other
        if margin < 0.02:
            winner = "tie"
            winner_label = "tie"
        elif mean_a > mean_b:
            winner = "A"
            winner_label = label_a
        else:
            winner = "B"
            winner_label = label_b

        duration = time.time() - start_time

        result = {
            "prompt": prompt,
            "label_a": label_a,
            "label_b": label_b,
            "trials": trial_results,
            "summary_a": summary_a,
            "summary_b": summary_b,
            "winner": winner,
            "winner_label": winner_label,
            "margin": round(margin, 4),
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_a": config_a.get("model", "unknown"),
            "model_b": config_b.get("model", "unknown"),
        }

        # Print summary
        print("=" * 50)
        print(f"  {label_a} mean: {mean_a:.3f} (std: {summary_a['std']:.3f})")
        print(f"  {label_b} mean: {mean_b:.3f} (std: {summary_b['std']:.3f})")
        print(f"  Winner: {winner_label} (margin: {margin:.3f})")
        print(f"  Duration: {duration:.1f}s")
        print("=" * 50)

        # Log the comparison
        self.log_comparison(result)

        return result

    def log_comparison(self, result: dict[str, Any]) -> None:
        """
        Append comparison result to eval/ab-results/ab-results.jsonl.

        Args:
            result: The comparison result dict from compare().
        """
        self.results_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.results_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, default=str) + "\n")
        except OSError as exc:
            print(f"Warning: Could not write A/B results log: {exc}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_trial(
        self,
        prompt: str,
        config_a: dict[str, Any],
        config_b: dict[str, Any],
        trial_num: int,
        label_a: str,
        label_b: str,
    ) -> dict[str, Any]:
        """
        Run a single A/B trial: generate with both configs and evaluate.

        Returns:
            Dict with score_a, score_b, output_a, output_b, and eval details.
        """
        media_type_a = config_a.get("media_type", "image")
        media_type_b = config_b.get("media_type", "image")
        criteria_a = config_a.get("refinement", {}).get(
            "evaluate_criteria", ["overall_quality"]
        )
        criteria_b = config_b.get("refinement", {}).get(
            "evaluate_criteria", ["overall_quality"]
        )

        # Generate with config A
        output_a = ""
        score_a = 0.0
        reasoning_a = ""

        output_name_a = f"ab_{label_a.lower()}_{trial_num:03d}"
        try:
            if media_type_a == "video":
                output_a = self.generator.generate_video(
                    prompt, config_a, output_name_a
                )
            else:
                output_a = self.generator.generate_image(
                    prompt, config_a, output_name_a
                )

            if not self.dry_run:
                score_a, reasoning_a = self.evaluator.soft_evaluate(
                    output_a, criteria_a, config_a
                )
            else:
                score_a = 0.85  # Stub score for dry-run
                reasoning_a = "Dry-run stub score"

        except GenerationError as exc:
            reasoning_a = f"Generation failed: {exc}"

        # Generate with config B
        output_b = ""
        score_b = 0.0
        reasoning_b = ""

        output_name_b = f"ab_{label_b.lower()}_{trial_num:03d}"
        try:
            if media_type_b == "video":
                output_b = self.generator.generate_video(
                    prompt, config_b, output_name_b
                )
            else:
                output_b = self.generator.generate_image(
                    prompt, config_b, output_name_b
                )

            if not self.dry_run:
                score_b, reasoning_b = self.evaluator.soft_evaluate(
                    output_b, criteria_b, config_b
                )
            else:
                score_b = 0.85  # Stub score for dry-run
                reasoning_b = "Dry-run stub score"

        except GenerationError as exc:
            reasoning_b = f"Generation failed: {exc}"

        return {
            "trial": trial_num,
            "output_a": output_a,
            "output_b": output_b,
            "score_a": score_a,
            "score_b": score_b,
            "reasoning_a": reasoning_a,
            "reasoning_b": reasoning_b,
        }

    @staticmethod
    def _compute_summary(scores: list[float]) -> dict[str, Any]:
        """
        Compute aggregate statistics for a list of scores.

        Returns:
            Dict with mean, std, min, max, and the raw scores list.
        """
        if not scores:
            return {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "scores": [],
            }

        mean = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0

        return {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(min(scores), 4),
            "max": round(max(scores), 4),
            "scores": [round(s, 4) for s in scores],
        }
