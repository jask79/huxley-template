"""
Image-to-Video Pipeline for the Media Workflow Engine.

Orchestrates the two-step workflow of generating a hero image and then
using it as the starting frame for video generation. Chains existing
generator methods and tracks provenance for both outputs.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

from engine.generator import MediaGenerator, GenerationError
from engine.evaluator import Evaluator
from engine.provenance import ProvenanceLogger


class PipelineError(Exception):
    """Raised when a pipeline step fails."""


class ImageToVideoPipeline:
    """
    Orchestrates the image-to-video workflow:

      1. Generate a hero image using an image workflow config
      2. Use that image as the starting frame for video generation
      3. Evaluate the video output
      4. Return both paths with provenance

    This is a simple two-step orchestrator that chains existing
    MediaGenerator methods. It does not implement its own generation
    logic -- it delegates entirely to the generator and evaluator.
    """

    def __init__(self, dry_run: bool = False) -> None:
        """
        Args:
            dry_run: If True, log steps without executing them.
        """
        self.dry_run = dry_run
        self.generator = MediaGenerator(dry_run=dry_run)
        self.evaluator = Evaluator()
        self.provenance = ProvenanceLogger()

    def run(
        self,
        image_prompt: str,
        video_prompt: str,
        image_config: dict[str, Any],
        video_config: dict[str, Any],
        image_output_name: str | None = None,
        video_output_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Run the full image-to-video pipeline.

        Args:
            image_prompt: Prompt for the hero image generation.
            video_prompt: Prompt for the video generation.
            image_config: Resolved workflow config for image generation.
            video_config: Resolved workflow config for video generation.
            image_output_name: Optional filename for the image output.
            video_output_name: Optional filename for the video output.

        Returns:
            Dict with keys:
              - image_path: str, path to the generated hero image
              - video_path: str, path to the generated video
              - image_eval: dict, evaluation results for the image
              - video_eval: dict, evaluation results for the video

        Raises:
            PipelineError: If either step fails.
        """
        result: dict[str, Any] = {
            "image_path": "",
            "video_path": "",
            "image_eval": {},
            "video_eval": {},
        }

        # ------------------------------------------------------------------
        # Step 1: Generate the hero image
        # ------------------------------------------------------------------
        print("Pipeline Step 1/2: Generating hero image...")

        if not image_output_name:
            image_output_name = f"hero_{date.today().strftime('%Y%m%d')}"

        try:
            image_path = self.generator.generate_image(
                prompt=image_prompt,
                config=image_config,
                output_name=image_output_name,
            )
        except GenerationError as exc:
            raise PipelineError(f"Image generation failed: {exc}") from exc

        result["image_path"] = image_path
        print(f"  Hero image: {image_path}")

        # Evaluate the image if not in dry-run mode
        if not self.dry_run:
            image_criteria = image_config.get("refinement", {}).get(
                "evaluate_criteria", ["overall_quality"]
            )
            passed, failures = self.evaluator.hard_check(image_path, image_config)
            if not passed:
                print(f"  Image hard check failures: {failures}")

            score, reasoning = self.evaluator.soft_evaluate(
                image_path, image_criteria, image_config
            )
            result["image_eval"] = {
                "hard_check_passed": passed,
                "failures": failures,
                "score": score,
                "reasoning": reasoning,
            }
            print(f"  Image score: {score:.2f}")

            # Record image provenance
            self.provenance.record_provenance(
                image_path, image_config, image_prompt,
                {"output_path": image_path, "final_score": score,
                 "iterations": 1, "eval_log": []},
            )

        # ------------------------------------------------------------------
        # Step 2: Use the hero image as the starting frame for video
        # ------------------------------------------------------------------
        print("Pipeline Step 2/2: Generating video from hero image...")

        if not video_output_name:
            video_output_name = f"video_{date.today().strftime('%Y%m%d')}"

        try:
            video_path = self.generator.generate_video(
                prompt=video_prompt,
                config=video_config,
                output_name=video_output_name,
                source_image=image_path,
            )
        except GenerationError as exc:
            raise PipelineError(
                f"Video generation failed (image was saved at {image_path}): {exc}"
            ) from exc

        result["video_path"] = video_path
        print(f"  Video: {video_path}")

        # Evaluate the video if not in dry-run mode
        if not self.dry_run:
            video_criteria = video_config.get("refinement", {}).get(
                "evaluate_criteria", ["overall_quality"]
            )
            v_passed, v_failures = self.evaluator.hard_check(video_path, video_config)
            if not v_passed:
                print(f"  Video hard check failures: {v_failures}")

            v_score, v_reasoning = self.evaluator.soft_evaluate(
                video_path, video_criteria, video_config
            )
            result["video_eval"] = {
                "hard_check_passed": v_passed,
                "failures": v_failures,
                "score": v_score,
                "reasoning": v_reasoning,
            }
            print(f"  Video score: {v_score:.2f}")

            # Record video provenance (include source image reference)
            video_config_with_source = dict(video_config)
            video_config_with_source["_source_image"] = image_path
            self.provenance.record_provenance(
                video_path, video_config_with_source, video_prompt,
                {"output_path": video_path, "final_score": v_score,
                 "iterations": 1, "eval_log": []},
            )

        print("Pipeline complete.")
        return result
