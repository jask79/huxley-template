"""
Workflow Orchestrator for the Media Workflow Engine.

Chains multiple generation steps into a pipeline. Steps are defined
in a pipeline YAML config with step ordering, dependencies, and
output-to-input routing.

Example pipeline: "Generate hero image -> generate 5 social variants ->
create 15s product video -> apply brand overlay"

Pipeline YAML format:
    name: Product Launch Pipeline
    steps:
      - name: hero_image
        workflow: product-photography
        prompt: "{base_prompt}"

      - name: social_variants
        workflow: social-content
        prompt: "Social media variant of the product"
        input_from: hero_image
        count: 5

      - name: promo_video
        workflow: video-promo
        prompt: "15 second product promo video"
        source_image_from: hero_image
"""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from engine.loader import ConfigLoader, ConfigLoadError
from engine.resolver import ConfigResolver
from engine.generator import MediaGenerator, GenerationError
from engine.evaluator import Evaluator
from engine.provenance import ProvenanceLogger
from engine.queue import RateLimiter
from engine.cache import PromptCache
from engine.references import ReferenceManager


# Engine root for pipeline config resolution
ENGINE_ROOT = Path("{{CATALYST_ROOT}}/tools/media-engine")
PIPELINES_DIR = ENGINE_ROOT / "pipelines"


class PipelineError(Exception):
    """Raised when a pipeline step fails."""


class WorkflowOrchestrator:
    """
    Chains multiple generation steps into a pipeline.

    Steps are executed in order. Each step resolves its own workflow
    config, generates media, and passes outputs to dependent steps
    via the pipeline context.

    Supports:
      - Step chaining via input_from (output of one step feeds the next)
      - Source image routing via source_image_from (image-to-video)
      - Count-based iteration (generate N variants from a single step)
      - Prompt templating with {base_prompt} substitution
      - Cache integration to skip duplicate generations
    """

    def __init__(self, dry_run: bool = False) -> None:
        """
        Args:
            dry_run: If True, log steps without executing generation.
        """
        self.dry_run = dry_run
        self.loader = ConfigLoader()
        self.resolver = ConfigResolver(self.loader)
        self.generator = MediaGenerator(dry_run=dry_run)
        self.evaluator = Evaluator()
        self.provenance = ProvenanceLogger()
        self.rate_limiter = RateLimiter()
        self.cache = PromptCache()
        self.ref_manager = ReferenceManager()

    # ------------------------------------------------------------------
    # Pipeline loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_pipeline(config_path: str | Path) -> dict[str, Any]:
        """
        Load a pipeline configuration from a YAML file.

        Args:
            config_path: Path to the pipeline YAML file.

        Returns:
            Parsed pipeline config dict.

        Raises:
            PipelineError: If the file cannot be loaded or is invalid.
        """
        path = Path(config_path)

        # Try resolving from the pipelines directory if not absolute
        if not path.is_absolute() and not path.exists():
            candidate = PIPELINES_DIR / path
            if candidate.exists():
                path = candidate
            # Also try adding .yaml extension
            elif (PIPELINES_DIR / f"{path}.yaml").exists():
                path = PIPELINES_DIR / f"{path}.yaml"
            elif (PIPELINES_DIR / f"{path}.yml").exists():
                path = PIPELINES_DIR / f"{path}.yml"

        if not path.exists():
            raise PipelineError(f"Pipeline config not found: {config_path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise PipelineError(f"Invalid YAML in pipeline config: {exc}") from exc

        if not isinstance(data, dict):
            raise PipelineError(
                f"Pipeline config must be a mapping, got {type(data).__name__}"
            )

        if "steps" not in data or not isinstance(data["steps"], list):
            raise PipelineError("Pipeline config must have a 'steps' list")

        if not data["steps"]:
            raise PipelineError("Pipeline 'steps' list cannot be empty")

        # Validate each step has required fields
        for i, step in enumerate(data["steps"]):
            if not isinstance(step, dict):
                raise PipelineError(f"Step {i} must be a mapping")
            if "name" not in step:
                raise PipelineError(f"Step {i} missing required field 'name'")
            if "workflow" not in step:
                raise PipelineError(f"Step {i} ({step.get('name', '?')}) missing required field 'workflow'")
            if "prompt" not in step:
                raise PipelineError(f"Step {i} ({step['name']}) missing required field 'prompt'")

        return data

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    def run_pipeline(
        self,
        pipeline_config: dict[str, Any],
        base_prompt: str,
    ) -> dict[str, Any]:
        """
        Execute all steps in a pipeline, passing outputs between steps.

        Args:
            pipeline_config: Parsed pipeline config dict (from load_pipeline).
            base_prompt: The base prompt that can be referenced in step
                         prompts via {base_prompt}.

        Returns:
            Dict with keys:
              - name: pipeline name
              - steps: list of per-step result dicts
              - total_outputs: total number of generated files
              - duration_seconds: total execution time
        """
        pipeline_name = pipeline_config.get("name", "Unnamed Pipeline")
        steps = pipeline_config["steps"]

        print(f"Pipeline: {pipeline_name}")
        print(f"Steps: {len(steps)}")
        print(f"Base prompt: {base_prompt}")
        print()

        start_time = time.time()
        context: dict[str, Any] = {}  # Maps step_name -> step result
        step_results: list[dict[str, Any]] = []
        total_outputs = 0

        for i, step in enumerate(steps):
            step_name = step["name"]
            print(f"--- Step {i + 1}/{len(steps)}: {step_name} ---")

            try:
                result = self.run_step(step, context, base_prompt)
                context[step_name] = result
                step_results.append(result)
                total_outputs += len(result.get("outputs", []))
                print(f"  Completed: {len(result.get('outputs', []))} output(s)")
            except (PipelineError, GenerationError, ConfigLoadError) as exc:
                error_result = {
                    "name": step_name,
                    "status": "failed",
                    "error": str(exc),
                    "outputs": [],
                }
                context[step_name] = error_result
                step_results.append(error_result)
                print(f"  FAILED: {exc}")
                # Continue to next step -- allow partial pipeline completion

            print()

        duration = time.time() - start_time

        print(f"Pipeline '{pipeline_name}' complete.")
        print(f"Total outputs: {total_outputs}")
        print(f"Duration: {duration:.1f}s")

        return {
            "name": pipeline_name,
            "steps": step_results,
            "total_outputs": total_outputs,
            "duration_seconds": round(duration, 2),
        }

    def run_step(
        self,
        step: dict[str, Any],
        context: dict[str, Any],
        base_prompt: str,
    ) -> dict[str, Any]:
        """
        Execute a single pipeline step.

        Resolves the workflow config, substitutes prompt templates,
        routes inputs from previous steps, and generates media.

        Args:
            step: Step definition dict from the pipeline config.
            context: Dict mapping previous step names to their results.
            base_prompt: The base prompt for template substitution.

        Returns:
            Dict with keys:
              - name: step name
              - status: "completed" or "failed"
              - outputs: list of generated file paths
              - workflow: workflow name used
              - eval_results: list of evaluation result dicts

        Raises:
            PipelineError: If the step cannot be executed.
            GenerationError: If generation fails.
            ConfigLoadError: If the workflow config is invalid.
        """
        step_name = step["name"]
        workflow_name = step["workflow"]
        prompt_template = step["prompt"]
        count = step.get("count", 1)

        # Resolve prompt template
        prompt = prompt_template.replace("{base_prompt}", base_prompt)

        # Resolve workflow config
        runtime_overrides = step.get("overrides", {})
        config = self.resolver.resolve_config(
            workflow=workflow_name,
            runtime_overrides=runtime_overrides or None,
        )

        media_type = config.get("media_type", "image")

        # Resolve input dependencies
        source_image = None
        input_refs: list[str] = []

        # source_image_from: use a previous step's output as video source frame
        if "source_image_from" in step:
            source_step_name = step["source_image_from"]
            source_result = context.get(source_step_name)
            if source_result and source_result.get("outputs"):
                source_image = source_result["outputs"][0]
                print(f"  Source image from '{source_step_name}': {source_image}")
            else:
                raise PipelineError(
                    f"Step '{step_name}' references source_image_from "
                    f"'{source_step_name}', but that step has no outputs."
                )

        # input_from: use a previous step's output as reference input
        if "input_from" in step:
            input_step_name = step["input_from"]
            input_result = context.get(input_step_name)
            if input_result and input_result.get("outputs"):
                input_refs = input_result["outputs"]
                print(f"  Input from '{input_step_name}': {len(input_refs)} file(s)")
            else:
                raise PipelineError(
                    f"Step '{step_name}' references input_from "
                    f"'{input_step_name}', but that step has no outputs."
                )

        # Load additional references from config
        references = self.ref_manager.load_references(config)
        if input_refs:
            references = input_refs + references

        # Rate limit check
        provider = config.get("auth_provider", "openrouter")
        auth_type = config.get("auth", "openrouter")

        outputs: list[str] = []
        eval_results: list[dict[str, Any]] = []

        for iteration in range(1, count + 1):
            if count > 1:
                print(f"  Iteration {iteration}/{count}...")

            can_go, effective_auth = self.rate_limiter.can_proceed_with_fallback(
                provider, auth_type
            )
            if not can_go:
                print(f"  Rate limit reached after {iteration - 1} iterations.")
                break

            # Check cache
            iter_prompt = prompt if count == 1 else f"{prompt} (variant {iteration})"
            cached = self.cache.get(
                iter_prompt, config,
                references=references if references else None,
                source_image=source_image,
            )
            if cached:
                print(f"  Cache hit: {cached}")
                outputs.append(cached)
                continue

            # Generate
            output_name = f"{step_name}_{date.today().strftime('%Y%m%d')}_{iteration:03d}"

            try:
                if media_type == "video":
                    output_path = self.generator.generate_video(
                        prompt=iter_prompt,
                        config=config,
                        output_name=output_name,
                        references=references if references else None,
                        source_image=source_image,
                    )
                else:
                    output_path = self.generator.generate_image(
                        prompt=iter_prompt,
                        config=config,
                        output_name=output_name,
                        references=references if references else None,
                    )

                outputs.append(output_path)
                self.rate_limiter.record_request(provider, effective_auth)

                # Cache the result
                self.cache.put(
                    iter_prompt, config, output_path,
                    references=references if references else None,
                    source_image=source_image,
                )

                # Evaluate if not dry-run
                if not self.dry_run:
                    criteria = config.get("refinement", {}).get(
                        "evaluate_criteria", ["overall_quality"]
                    )
                    passed, failures = self.evaluator.hard_check(output_path, config)
                    score, reasoning = self.evaluator.soft_evaluate(
                        output_path, criteria, config
                    )

                    eval_result = {
                        "output_path": output_path,
                        "hard_check_passed": passed,
                        "failures": failures,
                        "score": score,
                        "reasoning": reasoning,
                    }
                    eval_results.append(eval_result)

                    # Record provenance
                    self.provenance.record_provenance(
                        output_path, config, iter_prompt,
                        {
                            "output_path": output_path,
                            "final_score": score,
                            "iterations": 1,
                            "eval_log": [],
                        },
                    )

            except GenerationError as exc:
                print(f"  Generation failed: {exc}")
                if count == 1:
                    raise

        return {
            "name": step_name,
            "status": "completed" if outputs else "failed",
            "outputs": outputs,
            "workflow": workflow_name,
            "eval_results": eval_results,
        }
