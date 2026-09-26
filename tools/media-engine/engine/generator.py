"""
Generation Interface for the Media Workflow Engine.

Wraps the existing shell scripts in tools/image-gen/ to provide a Python
interface for image generation, image editing, and video generation.
Translates config parameters into environment variables and CLI arguments
understood by the shell scripts.

When reference images are available (consistency.reference_images > 0),
routes through the OpenRouterClient for direct API calls with multi-image
support. Otherwise, falls back to the shell scripts for backward compatibility.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from datetime import date
from pathlib import Path
from typing import Any


# Absolute paths to the shell scripts
IMAGE_GEN_SCRIPT = "{{CATALYST_ROOT}}/tools/image-gen/generate.sh"
IMAGE_EDIT_SCRIPT = "{{CATALYST_ROOT}}/tools/image-gen/edit-image.sh"
VIDEO_GEN_SCRIPT = "{{CATALYST_ROOT}}/tools/image-gen/generate-video.sh"

# Default model (matches api_client.py)
DEFAULT_MODEL = "google/gemini-3-pro-image-preview"

# nano-banana CLI binary (direct Gemini API, bypasses OpenRouter)
NANO_BANANA_BIN = "/opt/homebrew/bin/nano-banana"

# Engine root for default output paths
ENGINE_ROOT = Path("{{CATALYST_ROOT}}/tools/media-engine")


class GenerationError(Exception):
    """Raised when a generation script fails."""


class VectorGenerationError(Exception):
    """Raised when vector generation fails."""


class MediaGenerator:
    """
    Wraps shell-based media generation scripts with config-driven parameters.

    Translates WorkflowConfig values into the environment variables and
    arguments expected by generate.sh, edit-image.sh, and generate-video.sh.
    """

    def __init__(self, dry_run: bool = False) -> None:
        """
        Args:
            dry_run: If True, log the command that would be run without
                     actually executing it. Useful for testing.
        """
        self.dry_run = dry_run

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def generate_image(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
        references: list[str] | None = None,
    ) -> str:
        """
        Generate an image using the configured model and parameters.

        If reference images are available (either passed explicitly or
        loaded via consistency config), routes through the OpenRouterClient
        for multi-image API calls. Otherwise falls back to shell scripts.

        Args:
            prompt: The image generation prompt.
            config: Resolved workflow config dict.
            output_name: Optional output filename (without extension).
            references: Optional list of reference image paths. If None,
                references are loaded from config/capsule automatically.

        Returns:
            Absolute path to the generated image file.

        Raises:
            GenerationError: If the script fails or produces no output.
        """
        # Route through nano-banana for gemini_direct auth
        if config.get("auth") == "gemini_direct":
            return self._generate_image_nano_banana(prompt, config, output_name)

        # Route through OAuth client for gemini_oauth auth
        if config.get("auth") == "gemini_oauth":
            return self._generate_image_gemini_oauth(prompt, config, output_name)

        # Route through service account for google_ai_studio auth
        if config.get("auth") == "google_ai_studio":
            return self._generate_image_google_ai_studio(prompt, config, output_name)

        # Check if we should use the API client path (references available)
        consistency = config.get("consistency", {})
        ref_count = consistency.get("reference_images", 0)

        if references is None and ref_count > 0:
            # Try to load references via the ReferenceManager
            try:
                from engine.references import ReferenceManager
                ref_mgr = ReferenceManager()
                capsule_path = config.get("_capsule_path")
                references = ref_mgr.load_references(config, capsule_path)
            except Exception:
                references = []

        if references:
            return self.generate_image_with_refs(
                prompt, config, references, output_name
            )

        # Fall back to shell script path
        if not Path(IMAGE_GEN_SCRIPT).exists():
            raise GenerationError(f"Image generation script not found: {IMAGE_GEN_SCRIPT}")

        env = self._build_env(config)
        output_dir = self._resolve_output_dir(config)
        env["IMAGE_OUTPUT_DIR"] = output_dir

        args = [IMAGE_GEN_SCRIPT, prompt]
        if output_name:
            args.append(output_name)

        output = self._run_script(args, env)
        return self._extract_output_path(output, output_dir)

    # ------------------------------------------------------------------
    # Vector generation
    # ------------------------------------------------------------------

    def generate_vector(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a vector SVG file with refinement loop and export.

        Supports two refinement modes:
          - autonomous: generate -> validate -> adjust config -> retry (up to max_iterations)
          - agent_in_loop: generate -> validate -> return results for agent review

        Routes to the appropriate vector generator function based on the
        workflow name or vector_type config field.

        Args:
            prompt: The generation prompt (parsed for icon names, brand names, etc.).
            config: Resolved workflow config dict with media_type == "vector".
            output_name: Optional output filename (without extension).

        Returns:
            Dict with keys:
              - svg_path: str, absolute path to the generated SVG
              - exports: dict mapping format -> list of file paths
              - validation: dict with passed (bool) and results (list)
              - iterations: int, number of generation attempts
              - needs_review: bool (True if agent_in_loop and validation failed)

        Raises:
            GenerationError: If vector generation fails.
        """
        from engine.vector_validator import validate_svg
        from engine.vector_exporter import export_all, ExportError

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"vector_{date.today().strftime('%Y%m%d_%H%M%S')}"

        # Determine vector type from config or workflow name
        vector_cfg = config.get("vector", {})
        vector_type = vector_cfg.get("type", "")
        workflow_name = config.get("name", "").lower()

        # Check for pipeline_type to detect traced (Phase 4)
        pipeline_type = config.get("pipeline_type", "")

        if not vector_type:
            if pipeline_type == "ai_to_vector":
                vector_type = "traced"
            elif "trace" in workflow_name:
                vector_type = "traced"
            elif "icon" in workflow_name:
                vector_type = "icon"
            elif "wordmark" in workflow_name:
                vector_type = "wordmark"
            elif "monogram" in workflow_name:
                vector_type = "monogram"
            elif "combination" in workflow_name:
                vector_type = "combination"
            elif "logo" in workflow_name:
                vector_type = "logo"
            elif "palette" in workflow_name:
                vector_type = "palette"
            elif "typography" in workflow_name:
                vector_type = "typography"
            elif "flowchart" in workflow_name:
                vector_type = "flowchart"
            elif "architecture" in workflow_name:
                vector_type = "architecture"
            elif "wireframe" in workflow_name:
                vector_type = "wireframe"
            elif "diagram" in workflow_name:
                vector_type = "diagram"
            elif "badge" in workflow_name:
                vector_type = "badge"
            else:
                vector_type = "icon"  # Default

        # Phase 4: Route traced vector type to AI-to-vector pipeline
        if vector_type == "traced":
            return self._generate_traced_vector(prompt, config, output_name)

        if self.dry_run:
            svg_path = os.path.join(output_dir, f"{output_name}.svg")
            print(f"[DRY RUN] Would generate vector ({vector_type})")
            print(f"  Prompt: {prompt}")
            print(f"  Output: {svg_path}")
            print(f"  Export formats: {vector_cfg.get('export_formats', ['svg', 'pdf', 'png'])}")
            return {
                "svg_path": svg_path,
                "exports": {"svg": [svg_path]},
                "validation": {"passed": True, "results": []},
                "iterations": 0,
                "needs_review": False,
            }

        # Refinement loop configuration
        refinement = config.get("refinement", {})
        max_iterations = refinement.get("max_iterations", 3)
        mode = refinement.get("mode", "autonomous")

        best_svg_path = None
        best_validation = None
        best_passed = False
        iteration_config = dict(config)  # Mutable copy for adjustments

        for iteration in range(1, max_iterations + 1):
            svg_path = os.path.join(output_dir, f"{output_name}.svg")

            # Generate SVG
            try:
                svg_path = self._generate_vector_svg(
                    prompt, iteration_config, svg_path, vector_type
                )
            except GenerationError:
                raise
            except Exception as exc:
                raise GenerationError(
                    f"Vector generation failed ({vector_type}): {exc}"
                ) from exc

            # Validate SVG
            passed, results = validate_svg(svg_path, iteration_config)
            validation_info = {
                "passed": passed,
                "results": [str(r) for r in results],
                "iteration": iteration,
            }

            # Track the best result
            if passed or best_svg_path is None:
                best_svg_path = svg_path
                best_validation = validation_info
                best_passed = passed

            if passed:
                # Validation passed -- export and return
                break

            if mode == "agent_in_loop":
                # Return with validation results for agent evaluation
                # Export a preview PNG for the agent to inspect
                try:
                    exports = export_all(svg_path, iteration_config)
                except ExportError:
                    exports = {"svg": [svg_path]}

                return {
                    "svg_path": svg_path,
                    "exports": exports,
                    "validation": validation_info,
                    "iterations": iteration,
                    "needs_review": True,
                }

            # Autonomous mode: adjust config and retry
            if iteration < max_iterations:
                failures = [r for r in results if not r.passed]
                failure_names = [r.check_name for r in failures]
                iteration_config = self._adjust_vector_config(
                    iteration_config, failure_names
                )
                print(
                    f"  Iteration {iteration}: validation failed "
                    f"({', '.join(failure_names)}), adjusting and retrying..."
                )

        # Use best result
        svg_path = best_svg_path
        validation_info = best_validation

        if not best_passed:
            failure_strs = [
                r for r in validation_info.get("results", []) if "FAIL" in r
            ]
            print(f"  SVG validation warnings after {max_iterations} iterations: "
                  f"{'; '.join(failure_strs)}")

        # Export to configured formats
        try:
            exports = export_all(svg_path, config)
        except ExportError as exc:
            print(f"  Export warning: {exc}")
            exports = {"svg": [svg_path]}

        # Verify PNG dimensions for icon workflows (multi-resolution)
        if vector_type == "icon" and "png" in exports:
            from engine.vector_validator import check_multi_resolution
            grid_size = vector_cfg.get("grid_size", "24x24")
            dim_results = check_multi_resolution(exports.get("png", []), grid_size)
            if dim_results:
                validation_info.setdefault("dimension_checks", dim_results)

        # Phase 3: Print-ready post-processing (Inkscape CLI integration)
        print_cfg = vector_cfg.get("print", {})
        is_print_ready = (
            print_cfg.get("print_ready", False)
            or vector_cfg.get("print_ready", False)
            or config.get("_print_ready", False)
        )
        print_results: dict[str, str] = {}

        if is_print_ready:
            print_results = self._run_print_ready_exports(
                svg_path, vector_cfg, print_cfg
            )
            if print_results:
                exports["print"] = list(print_results.values())
                validation_info["print_ready"] = {
                    "outputs": print_results,
                    "inkscape_used": bool(print_results),
                }

        return {
            "svg_path": svg_path,
            "exports": exports,
            "validation": validation_info,
            "iterations": iteration,
            "needs_review": False,
            "print_ready": print_results if is_print_ready else None,
        }

    def _generate_vector_svg(
        self,
        prompt: str,
        config: dict[str, Any],
        svg_path: str,
        vector_type: str,
    ) -> str:
        """
        Generate a single SVG file by dispatching to the appropriate generator.

        Args:
            prompt: The generation prompt.
            config: Resolved config dict.
            svg_path: Output SVG file path.
            vector_type: The type of vector to generate.

        Returns:
            Absolute path to the generated SVG.
        """
        from engine.vector_generator import (
            generate_icon,
            generate_geometric_logo,
            generate_diagram,
            generate_badge,
            generate_wordmark,
            generate_monogram,
            generate_combination_mark,
            generate_brand_palette,
            generate_brand_typography,
            generate_flowchart,
            generate_architecture,
            generate_wireframe,
            VectorGenerationError as VGError,
        )

        try:
            generator_map = {
                "icon": generate_icon,
                "logo": generate_geometric_logo,
                "wordmark": generate_wordmark,
                "monogram": generate_monogram,
                "combination": generate_combination_mark,
                "palette": generate_brand_palette,
                "typography": generate_brand_typography,
                "flowchart": generate_flowchart,
                "architecture": generate_architecture,
                "wireframe": generate_wireframe,
                "diagram": generate_diagram,
                "badge": generate_badge,
            }
            gen_fn = generator_map.get(vector_type, generate_icon)
            return gen_fn(config, prompt, svg_path)
        except (VGError, Exception) as exc:
            raise GenerationError(
                f"Vector generation failed ({vector_type}): {exc}"
            ) from exc

    @staticmethod
    def _adjust_vector_config(
        config: dict[str, Any],
        failure_names: list[str],
    ) -> dict[str, Any]:
        """
        Adjust vector config to fix common validation failures.

        Creates a modified copy of the config with parameters tuned to
        address the specific failures detected.

        Args:
            config: Current config dict.
            failure_names: List of failed check names from the validator.

        Returns:
            Adjusted config dict.
        """
        import copy
        adjusted = copy.deepcopy(config)
        vec = adjusted.setdefault("vector", {})

        for name in failure_names:
            if name == "svg_file_size":
                # Reduce complexity: increase size limit slightly, simplify
                current_limit = vec.get("file_size_limit_kb", 100)
                vec["file_size_limit_kb"] = int(current_limit * 1.5)

            elif name == "svg_has_layers":
                # Ensure groups are created (this is a generation issue, not config)
                pass

            elif name == "svg_text_editable":
                # Ensure text elements are not converted to paths
                pass

            elif name == "svg_path_count":
                # Reduce max path count expectation or simplify
                current_max = vec.get("max_path_count", 500)
                vec["max_path_count"] = int(current_max * 1.5)

            elif name == "svg_layer_naming":
                # This is a generation logic issue, not adjustable via config
                pass

        return adjusted

    # ------------------------------------------------------------------
    # Phase 4: AI-to-Vector traced generation
    # ------------------------------------------------------------------

    def _generate_traced_vector(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a traced vector via the AI-to-vector pipeline.

        Delegates to AIToVectorPipeline which handles:
          1. AI concept image generation
          2. VTracer raster-to-vector tracing
          3. Quality gate evaluation
          4. SVG post-processing
          5. Multi-format export

        Args:
            prompt: The generation prompt.
            config: Resolved workflow config dict.
            output_name: Optional output filename base.

        Returns:
            Dict matching the generate_vector return format:
              - svg_path, exports, validation, iterations, needs_review
              - Plus trace-specific: trace_params, trace_metrics,
                quality_gate_result, source_image_path

        Raises:
            GenerationError: If the pipeline fails.
        """
        from engine.ai_to_vector_pipeline import (
            AIToVectorPipeline,
            AIToVectorPipelineError,
        )

        try:
            pipeline = AIToVectorPipeline(dry_run=self.dry_run)
            result = pipeline.run(prompt, config, output_name)

            # Map pipeline result to generate_vector return format
            gate_passed = result.get("quality_gate_result", {}).get("passed", False)
            return {
                "svg_path": result.get("svg_path", ""),
                "exports": result.get("exports", {}),
                "validation": {
                    "passed": gate_passed,
                    "results": [
                        f"Quality gate: {'PASSED' if gate_passed else 'FAILED'}",
                    ] + [
                        f"  - {issue}"
                        for issue in result.get(
                            "quality_gate_result", {}
                        ).get("issues", [])
                    ],
                    "iteration": result.get("iterations", 1),
                    "trace_params": result.get("trace_params", {}),
                    "trace_metrics": result.get("trace_metrics", {}),
                    "quality_gate": result.get("quality_gate_result", {}),
                    "source_image": result.get("source_image_path", ""),
                },
                "iterations": result.get("iterations", 1),
                "needs_review": not gate_passed,
            }

        except AIToVectorPipelineError as exc:
            raise GenerationError(
                f"AI-to-vector pipeline failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Phase 3: Print-ready exports (Inkscape CLI)
    # ------------------------------------------------------------------

    @staticmethod
    def _run_print_ready_exports(
        svg_path: str,
        vector_cfg: dict[str, Any],
        print_cfg: dict[str, Any],
    ) -> dict[str, str]:
        """
        Run Inkscape-powered print-ready exports on a generated SVG.

        Handles graceful degradation when Inkscape is not installed.
        All operations are optional and non-fatal.

        Args:
            svg_path: Path to the source SVG.
            vector_cfg: The vector section of the resolved config.
            print_cfg: The vector.print section of the resolved config.

        Returns:
            Dict mapping output type to file path (empty if nothing produced).
        """
        from engine.inkscape_cli import get_inkscape, InkscapeError

        inkscape = get_inkscape()
        results: dict[str, str] = {}

        # Resolve print parameters (print section overrides top-level vector)
        bleed_mm = print_cfg.get("bleed_mm", vector_cfg.get("bleed_mm", 3.0))
        do_cmyk = print_cfg.get("cmyk", vector_cfg.get("cmyk", False))
        do_text_to_path = print_cfg.get(
            "text_to_path", vector_cfg.get("text_to_path", False)
        )
        color_profile = print_cfg.get(
            "color_profile", vector_cfg.get("color_profile")
        )
        do_eps = "eps" in vector_cfg.get("export_formats", [])

        try:
            print_outputs = inkscape.export_print_ready(
                input_svg=svg_path,
                bleed_mm=bleed_mm,
                text_to_path=do_text_to_path,
                cmyk=do_cmyk,
                export_eps=do_eps,
                color_profile=color_profile,
            )
            results.update(print_outputs)
        except InkscapeError as exc:
            print(f"  Print-ready export warning: {exc}")

        return results

    # ------------------------------------------------------------------
    # Image generation with references (API client path)
    # ------------------------------------------------------------------

    def generate_image_with_refs(
        self,
        prompt: str,
        config: dict[str, Any],
        references: list[str],
        output_name: str | None = None,
    ) -> str:
        """
        Generate an image using the API client with reference images.

        Uses the OpenRouterClient to send multi-image requests for
        style/character consistency.

        Args:
            prompt: The image generation prompt.
            config: Resolved workflow config dict.
            references: List of reference image file paths.
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the generated image file.

        Raises:
            GenerationError: If the API call fails.
        """
        from engine.api_client import OpenRouterClient, APIClientError

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"gen_{date.today().strftime('%Y%m%d_%H%M%S')}"

        output_path = os.path.join(output_dir, f"{output_name}.png")

        if self.dry_run:
            model = config.get("model", DEFAULT_MODEL)
            consistency = config.get("consistency", {})
            print(f"[DRY RUN] Would generate via API client with {len(references)} references")
            print(f"  Model: {model}")
            print(f"  Style weight: {consistency.get('style_weight', 0.5)}")
            print(f"  Character lock: {consistency.get('character_lock', False)}")
            print(f"  References: {references}")
            print(f"  Output dir: {output_dir}")
            return output_path

        try:
            client = OpenRouterClient()
            consistency = config.get("consistency", {})

            image_bytes = client.generate_with_references(
                prompt=prompt,
                model=config.get("model", DEFAULT_MODEL),
                reference_images=references,
                style_weight=consistency.get("style_weight", 0.7),
                character_lock=consistency.get("character_lock", False),
            )

            saved_path = client.save_image(image_bytes, output_path)

            # Track which references were used
            try:
                from engine.references import ReferenceManager
                ref_mgr = ReferenceManager()
                session_id = str(uuid.uuid4())[:8]
                ref_mgr.track_generation(session_id, saved_path, references)
            except Exception:
                pass  # Tracking is non-critical

            return saved_path

        except APIClientError as exc:
            raise GenerationError(f"API generation with references failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Image editing
    # ------------------------------------------------------------------

    def edit_image(
        self,
        input_path: str,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> str:
        """
        Edit an existing image using the configured model.

        Args:
            input_path: Path to the source image.
            prompt: The edit instruction.
            config: Resolved workflow config dict.
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the edited image file.

        Raises:
            GenerationError: If the script fails or input doesn't exist.
        """
        # Route through nano-banana for gemini_direct auth
        if config.get("auth") == "gemini_direct":
            return self._edit_image_nano_banana(input_path, prompt, config, output_name)

        # Route through OAuth client for gemini_oauth auth
        if config.get("auth") == "gemini_oauth":
            return self._edit_image_gemini_oauth(input_path, prompt, config, output_name)

        # Route through service account for google_ai_studio auth
        if config.get("auth") == "google_ai_studio":
            return self._edit_image_google_ai_studio(input_path, prompt, config, output_name)

        if not Path(IMAGE_EDIT_SCRIPT).exists():
            raise GenerationError(f"Image edit script not found: {IMAGE_EDIT_SCRIPT}")

        if not Path(input_path).exists():
            raise GenerationError(f"Input image not found: {input_path}")

        env = self._build_env(config)
        output_dir = self._resolve_output_dir(config)
        env["IMAGE_OUTPUT_DIR"] = output_dir

        args = [IMAGE_EDIT_SCRIPT, input_path, prompt]
        if output_name:
            args.append(output_name)

        output = self._run_script(args, env)
        return self._extract_output_path(output, output_dir)

    # ------------------------------------------------------------------
    # Nano Banana CLI (direct Gemini API)
    # ------------------------------------------------------------------

    def _generate_image_nano_banana(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> str:
        """
        Generate an image via nano-banana CLI (direct Gemini API).

        Uses the nano-banana Pro model by default, or Flash model when
        the config model contains 'flash'.

        Args:
            prompt: The image generation prompt.
            config: Resolved workflow config dict with auth == "gemini_direct".
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the generated image file.

        Raises:
            GenerationError: If nano-banana fails.
        """
        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"gen_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(output_dir, f"{output_name}.png")

        args = [NANO_BANANA_BIN, prompt, "--output", output_path]

        # Flash model selection
        model = config.get("model", "")
        if "flash" in model.lower():
            args.append("--flash")

        if self.dry_run:
            print(f"[DRY RUN] nano-banana image generation")
            print(f"  Model: {model or 'nano-banana-pro-preview'}")
            print(f"  Output: {output_path}")
            return output_path

        self._run_nano_banana(args)

        if not Path(output_path).exists():
            raise GenerationError(
                f"nano-banana produced no output at {output_path}"
            )

        return output_path

    def _edit_image_nano_banana(
        self,
        input_path: str,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> str:
        """
        Edit an image via nano-banana CLI (direct Gemini API).

        Args:
            input_path: Path to the source image.
            prompt: The edit instruction.
            config: Resolved workflow config dict.
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the edited image file.

        Raises:
            GenerationError: If nano-banana fails or input doesn't exist.
        """
        if not Path(input_path).exists():
            raise GenerationError(f"Input image not found: {input_path}")

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"edit_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(output_dir, f"{output_name}.png")

        args = [NANO_BANANA_BIN, prompt, "--file", input_path, "--output", output_path]

        if self.dry_run:
            print(f"[DRY RUN] nano-banana image edit")
            print(f"  Input: {input_path}")
            print(f"  Output: {output_path}")
            return output_path

        self._run_nano_banana(args)

        if not Path(output_path).exists():
            raise GenerationError(
                f"nano-banana produced no output at {output_path}"
            )

        return output_path

    # ------------------------------------------------------------------
    # Gemini OAuth methods (personal Google account, no API key)
    # ------------------------------------------------------------------

    def _generate_image_gemini_oauth(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> str:
        """
        Generate an image via Gemini OAuth (personal Google account).

        Args:
            prompt: The image generation prompt.
            config: Resolved workflow config dict with auth == "gemini_oauth".
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the generated image file.

        Raises:
            GenerationError: If OAuth client fails.
        """
        from engine.gemini_oauth_client import generate_image, GeminiOAuthError

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"gen_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(output_dir, f"{output_name}.png")

        model = config.get("model", DEFAULT_MODEL)
        generation = config.get("generation", {})
        aspect_ratios = generation.get("aspect_ratios", ["1:1"])
        aspect_ratio = aspect_ratios[0] if aspect_ratios else "1:1"

        if self.dry_run:
            print(f"[DRY RUN] gemini_oauth image generation")
            print(f"  Model: {model}")
            print(f"  Aspect ratio: {aspect_ratio}")
            print(f"  Output: {output_path}")
            return output_path

        try:
            return generate_image(
                prompt=prompt,
                model=model,
                output_path=output_path,
                aspect_ratio=aspect_ratio,
            )
        except GeminiOAuthError as exc:
            raise GenerationError(f"gemini_oauth failed: {exc}") from exc

    def _edit_image_gemini_oauth(
        self,
        input_path: str,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> str:
        """
        Edit an image via Gemini OAuth (personal Google account).

        Args:
            input_path: Path to the source image.
            prompt: The edit instruction.
            config: Resolved workflow config dict.
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the edited image file.

        Raises:
            GenerationError: If OAuth client fails or input doesn't exist.
        """
        from engine.gemini_oauth_client import edit_image, GeminiOAuthError

        if not Path(input_path).exists():
            raise GenerationError(f"Input image not found: {input_path}")

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"edit_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(output_dir, f"{output_name}.png")

        model = config.get("model", DEFAULT_MODEL)

        if self.dry_run:
            print(f"[DRY RUN] gemini_oauth image edit")
            print(f"  Model: {model}")
            print(f"  Input: {input_path}")
            print(f"  Output: {output_path}")
            return output_path

        try:
            return edit_image(
                input_path=input_path,
                prompt=prompt,
                model=model,
                output_path=output_path,
            )
        except GeminiOAuthError as exc:
            raise GenerationError(f"gemini_oauth edit failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Google AI Studio methods (GCP service account, no API key/OAuth)
    # ------------------------------------------------------------------

    def _generate_image_google_ai_studio(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> str:
        """
        Generate an image via Google AI Studio (GCP service account).

        Args:
            prompt: The image generation prompt.
            config: Resolved workflow config dict with auth == "google_ai_studio".
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the generated image file.

        Raises:
            GenerationError: If service account client fails.
        """
        from engine.gemini_sa_client import generate_image, GeminiServiceAccountError

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"gen_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(output_dir, f"{output_name}.png")

        model = config.get("model", DEFAULT_MODEL)
        generation = config.get("generation", {})
        aspect_ratios = generation.get("aspect_ratios", ["1:1"])
        aspect_ratio = aspect_ratios[0] if aspect_ratios else "1:1"

        if self.dry_run:
            print(f"[DRY RUN] google_ai_studio image generation")
            print(f"  Model: {model}")
            print(f"  Aspect ratio: {aspect_ratio}")
            print(f"  Output: {output_path}")
            return output_path

        try:
            return generate_image(
                prompt=prompt,
                model=model,
                output_path=output_path,
                aspect_ratio=aspect_ratio,
            )
        except GeminiServiceAccountError as exc:
            raise GenerationError(f"google_ai_studio failed: {exc}") from exc

    def _edit_image_google_ai_studio(
        self,
        input_path: str,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> str:
        """
        Edit an image via Google AI Studio (GCP service account).

        Args:
            input_path: Path to the source image.
            prompt: The edit instruction.
            config: Resolved workflow config dict.
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the edited image file.

        Raises:
            GenerationError: If service account client fails or input doesn't exist.
        """
        from engine.gemini_sa_client import edit_image, GeminiServiceAccountError

        if not Path(input_path).exists():
            raise GenerationError(f"Input image not found: {input_path}")

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"edit_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(output_dir, f"{output_name}.png")

        model = config.get("model", DEFAULT_MODEL)

        if self.dry_run:
            print(f"[DRY RUN] google_ai_studio image edit")
            print(f"  Model: {model}")
            print(f"  Input: {input_path}")
            print(f"  Output: {output_path}")
            return output_path

        try:
            return edit_image(
                input_path=input_path,
                prompt=prompt,
                model=model,
                output_path=output_path,
            )
        except GeminiServiceAccountError as exc:
            raise GenerationError(f"google_ai_studio edit failed: {exc}") from exc

    def _generate_video_nano_banana(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
        references: list[str] | None = None,
        source_image: str | None = None,
        extend_from: str | None = None,
    ) -> str:
        """
        Generate video via nano-banana CLI (Veo 3.1).

        Supports text-to-video, image-to-video (--file), video extension
        (--extend), and reference images for character consistency.

        Args:
            prompt: The video generation prompt.
            config: Resolved workflow config dict with auth == "gemini_direct".
            output_name: Optional output filename (without extension).
            references: Optional list of reference image paths (max 3).
            source_image: Optional image for image-to-video animation.
            extend_from: Optional path to previous video for extension.

        Returns:
            Absolute path to the generated video file.

        Raises:
            GenerationError: If nano-banana fails.
        """
        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"video_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(output_dir, f"{output_name}.mp4")

        # Build camera motion suffix for the prompt
        gen_config = config.get("generation", {})
        full_prompt = prompt
        camera_motion = gen_config.get("camera_motion")
        if camera_motion and camera_motion != "static":
            motion_map = {
                "pan": "Use a smooth panning camera movement.",
                "slow_dolly": "Use a slow, cinematic dolly camera movement.",
                "orbit": "Use an orbiting camera movement around the subject.",
                "zoom_in": "Use a gradual zoom-in camera movement.",
                "zoom_out": "Use a gradual zoom-out camera movement.",
                "handheld": "Use a handheld-style camera with natural shake.",
            }
            motion_text = motion_map.get(camera_motion, "")
            if motion_text:
                full_prompt = f"{prompt} {motion_text}"

        args = [NANO_BANANA_BIN, "--video", full_prompt, "--output", output_path]

        # Model/speed selection
        model = config.get("model", "")
        if "fast" in model.lower():
            args.append("--video-fast")

        # Duration
        duration = gen_config.get("duration")
        if duration:
            dur = self._normalize_duration(duration)
            args.extend(["--duration", str(dur)])

        # Aspect ratio
        aspect_ratios = gen_config.get("aspect_ratios", [])
        if aspect_ratios:
            args.extend(["--aspect", aspect_ratios[0]])

        # Resolution
        resolution = gen_config.get("resolution", "")
        if resolution in ("720p", "1080p"):
            args.extend(["--resolution", resolution])

        # Audio control
        audio = gen_config.get("audio")
        if audio == "none":
            args.append("--no-audio")

        # Source image (image-to-video)
        if source_image:
            if not Path(source_image).exists():
                raise GenerationError(f"Source image not found: {source_image}")
            args.extend(["--file", source_image])

        # Video extension
        if extend_from:
            if not Path(extend_from).exists():
                raise GenerationError(
                    f"Extension source video not found: {extend_from}"
                )
            args.extend(["--extend", extend_from])

        # Reference images for character consistency (up to 3)
        if references:
            for ref in references[:3]:
                if Path(ref).exists():
                    args.extend(["--reference", ref])

        if self.dry_run:
            print(f"[DRY RUN] nano-banana video generation")
            print(f"  Model: {model or 'veo-3.1-generate-preview'}")
            print(f"  Duration: {gen_config.get('duration', '8s')}")
            print(f"  Audio: {audio or 'on'}")
            if source_image:
                print(f"  Source image: {source_image}")
            if extend_from:
                print(f"  Extending: {extend_from}")
            if references:
                print(f"  References: {len(references[:3])} images")
            print(f"  Output: {output_path}")
            return output_path

        self._run_nano_banana(args)

        if not Path(output_path).exists():
            raise GenerationError(
                f"nano-banana produced no output at {output_path}"
            )

        return output_path

    def _run_nano_banana(self, args: list[str]) -> str:
        """
        Execute nano-banana CLI and return stdout.

        Args:
            args: Command arguments starting with the nano-banana binary path.

        Returns:
            stdout from the nano-banana process.

        Raises:
            GenerationError: If nano-banana is not installed or fails.
        """
        if not Path(NANO_BANANA_BIN).exists():
            raise GenerationError(
                f"nano-banana not found at {NANO_BANANA_BIN}. "
                "Install with: npm install -g @the-focus-ai/nano-banana"
            )

        # Ensure nano-banana can find node and GEMINI_API_KEY
        env = os.environ.copy()
        # Add Homebrew bin to PATH so node is discoverable
        homebrew_bin = "/opt/homebrew/bin"
        if homebrew_bin not in env.get("PATH", ""):
            env["PATH"] = f"{homebrew_bin}:{env.get('PATH', '')}"
        if "GEMINI_API_KEY" not in env:
            try:
                import sys as _sys
                _sys.path.insert(0, "{{CATALYST_ROOT}}/global/lib")
                from secret_provider import get_secret
                env["GEMINI_API_KEY"] = get_secret("gemini-api-key")
            except Exception:
                pass  # Fall through — nano-banana will report the missing key

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise GenerationError(
                "nano-banana timed out after 600s"
            ) from exc
        except FileNotFoundError as exc:
            raise GenerationError(
                f"nano-banana not found at {NANO_BANANA_BIN}. "
                "Install with: npm install -g @the-focus-ai/nano-banana"
            ) from exc

        if result.returncode != 0:
            raise GenerationError(
                f"nano-banana failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout.strip()}\n"
                f"stderr: {result.stderr.strip()}"
            )

        return result.stdout

    # ------------------------------------------------------------------
    # Video generation
    # ------------------------------------------------------------------

    def generate_video(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
        references: list[str] | None = None,
        source_image: str | None = None,
    ) -> str:
        """
        Generate a video using the configured model and parameters.

        If reference images are available or a source image is provided,
        routes through the OpenRouterClient for API-based generation.
        Otherwise falls back to the shell script.

        Args:
            prompt: The video generation prompt.
            config: Resolved workflow config dict.
            output_name: Optional output filename (without extension).
            references: Optional list of reference image paths for style
                consistency. If None, references are loaded from config.
            source_image: Optional path to an image to use as the starting
                frame for image-to-video generation.

        Returns:
            Absolute path to the generated video file.

        Raises:
            GenerationError: If the generation fails.
        """
        # Check if we should load references from config
        consistency = config.get("consistency", {})
        ref_count = consistency.get("reference_images", 0)

        if references is None and ref_count > 0:
            try:
                from engine.references import ReferenceManager
                ref_mgr = ReferenceManager()
                capsule_path = config.get("_capsule_path")
                references = ref_mgr.load_references(config, capsule_path)
            except Exception:
                references = []

        # Route through nano-banana for gemini_direct auth
        if config.get("auth") == "gemini_direct":
            return self._generate_video_nano_banana(
                prompt, config, output_name,
                references=references,
                source_image=source_image,
                extend_from=config.get("_extend_from"),
            )

        # Route to API client if we have a source image (image-to-video)
        if source_image:
            return self.generate_video_with_refs(
                prompt, config, source_image=source_image, output_name=output_name
            )

        # Route to API client if we have references
        if references:
            return self.generate_video_with_refs(
                prompt, config, references=references, output_name=output_name
            )

        # Fall back to shell script path
        if not Path(VIDEO_GEN_SCRIPT).exists():
            raise GenerationError(
                f"Video generation script not found: {VIDEO_GEN_SCRIPT}. "
                "Video generation may not be configured yet."
            )

        env = self._build_env(config)
        output_dir = self._resolve_output_dir(config)
        env["VIDEO_OUTPUT_DIR"] = output_dir

        # Extract video-specific parameters
        gen_config = config.get("generation", {})
        duration = self._normalize_duration(gen_config.get("duration", "4"))

        # Map resolution to Sora-compatible size string
        resolution = gen_config.get("resolution", "1080p")
        aspect_ratios = gen_config.get("aspect_ratios", ["16:9"])
        size = self._resolve_video_size(resolution, aspect_ratios[0] if aspect_ratios else "16:9")

        args = [VIDEO_GEN_SCRIPT, prompt]
        if output_name:
            args.append(output_name)
        else:
            args.append(f"video_{date.today().strftime('%Y%m%d')}")
        args.append(str(duration))
        args.append(size)

        output = self._run_script(args, env)
        return self._extract_output_path(output, output_dir)

    # ------------------------------------------------------------------
    # Video generation with references / source image (API client path)
    # ------------------------------------------------------------------

    def generate_video_with_refs(
        self,
        prompt: str,
        config: dict[str, Any],
        references: list[str] | None = None,
        source_image: str | None = None,
        output_name: str | None = None,
    ) -> str:
        """
        Generate a video using the API client with reference or source images.

        For image-to-video workflows, pass source_image to use as the
        starting frame. For style consistency, pass references.

        Args:
            prompt: The video generation prompt.
            config: Resolved workflow config dict.
            references: Optional list of reference image paths.
            source_image: Optional path to an image for image-to-video.
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the generated video file.

        Raises:
            GenerationError: If the API call fails.
        """
        from engine.api_client import OpenRouterClient, APIClientError

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"video_{date.today().strftime('%Y%m%d_%H%M%S')}"

        output_path = os.path.join(output_dir, f"{output_name}.mp4")

        gen_config = config.get("generation", {})
        model = config.get("model", "openai/sora-2")
        duration = self._normalize_duration(gen_config.get("duration", "4"))
        resolution = gen_config.get("resolution", "1080p")
        aspect_ratios = gen_config.get("aspect_ratios", ["16:9"])
        size = self._resolve_video_size(
            resolution, aspect_ratios[0] if aspect_ratios else "16:9"
        )

        # Build style-aware prompt if references provided
        full_prompt = prompt
        if references:
            consistency = config.get("consistency", {})
            style_weight = consistency.get("style_weight", 0.7)
            if style_weight > 0.6:
                full_prompt = (
                    f"Match the visual style of the reference images closely. {prompt}"
                )
            elif style_weight > 0.3:
                full_prompt = (
                    f"Take inspiration from the reference image style. {prompt}"
                )

        # Add camera motion to the prompt if specified
        camera_motion = gen_config.get("camera_motion")
        if camera_motion and camera_motion != "static":
            motion_map = {
                "pan": "Use a smooth panning camera movement.",
                "slow_dolly": "Use a slow, cinematic dolly camera movement.",
                "orbit": "Use an orbiting camera movement around the subject.",
                "zoom_in": "Use a gradual zoom-in camera movement.",
                "zoom_out": "Use a gradual zoom-out camera movement.",
                "handheld": "Use a handheld-style camera with natural shake.",
            }
            motion_text = motion_map.get(camera_motion, "")
            if motion_text:
                full_prompt = f"{full_prompt} {motion_text}"

        if self.dry_run:
            print(f"[DRY RUN] Would generate video via API client")
            print(f"  Model: {model}")
            print(f"  Duration: {duration}s | Size: {size}")
            if source_image:
                print(f"  Source image: {source_image}")
            if references:
                print(f"  References: {len(references)} images")
            print(f"  Camera motion: {camera_motion or 'none'}")
            print(f"  Output: {output_path}")
            return output_path

        try:
            client = OpenRouterClient()

            if source_image:
                # Image-to-video: use source image as starting frame
                result = client.generate_video_from_image(
                    image_path=source_image,
                    prompt=full_prompt,
                    model=model,
                    duration=str(duration),
                    size=size,
                )
            else:
                # Text-to-video (references inform style via prompt only)
                result = client.generate_video(
                    prompt=full_prompt,
                    model=model,
                    duration=str(duration),
                    size=size,
                )

            # Save the video to disk
            if result.get("data"):
                saved_path = client.save_video(result["data"], output_path)
            elif result.get("url"):
                # Download from URL
                video_data = self._download_url(result["url"])
                saved_path = client.save_video(video_data, output_path)
            else:
                raise GenerationError(
                    "Video API returned no video data or URL. "
                    f"Response content: {result.get('content', '')[:200]}"
                )

            # Track reference usage
            if references:
                try:
                    from engine.references import ReferenceManager
                    ref_mgr = ReferenceManager()
                    session_id = str(uuid.uuid4())[:8]
                    ref_mgr.track_generation(session_id, saved_path, references)
                except Exception:
                    pass  # Tracking is non-critical

            return saved_path

        except APIClientError as exc:
            raise GenerationError(f"API video generation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Transcode (PyAV)
    # ------------------------------------------------------------------

    def transcode(
        self,
        input_path: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> str:
        """
        Transcode a media file using PyAV.

        Args:
            input_path: Path to the input media file.
            config: Resolved workflow config dict with transcode section.
            output_name: Optional output filename (without extension).

        Returns:
            Absolute path to the transcoded output file.

        Raises:
            GenerationError: If transcoding fails or PyAV is unavailable.
        """
        try:
            from engine.pyav_processor import PyAVProcessor, PyAVNotAvailableError
        except ImportError as exc:
            raise GenerationError("PyAV module not available: pip install av") from exc

        proc = PyAVProcessor()
        if not proc.is_available():
            raise GenerationError("PyAV (av package) is not installed: pip install av")

        output_dir = self._resolve_output_dir(config)
        tc = config.get("transcode", {})
        codec = tc.get("codec", "h264")

        ext_map = {"h264": "mp4", "h265": "mp4", "hevc": "mp4", "vp9": "webm", "av1": "mp4", "prores": "mov", "copy": "mp4"}
        ext = ext_map.get(codec, "mp4")

        if not output_name:
            output_name = self._resolve_output_name(config)
        output_path = os.path.join(output_dir, f"{output_name}.{ext}")

        if self.dry_run:
            print(f"[DRY RUN] Would transcode: {input_path} -> {output_path}")
            print(f"  Codec: {codec}, Preset: {tc.get('preset', 'medium')}, CRF: {tc.get('crf', 23)}")
            return output_path

        # Parse resolution if provided
        resolution = None
        res_str = tc.get("resolution") or config.get("generation", {}).get("resolution")
        if res_str and "x" in str(res_str):
            parts = str(res_str).split("x")
            try:
                resolution = (int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass

        proc.transcode(
            input_path=input_path,
            output_path=output_path,
            codec=codec,
            resolution=resolution,
            bitrate=tc.get("bitrate"),
            fps=tc.get("fps") or config.get("generation", {}).get("fps"),
            crf=tc.get("crf", 23),
            preset=tc.get("preset", "medium"),
            audio_codec=tc.get("audio_codec", "aac"),
        )

        return output_path

    # ------------------------------------------------------------------
    # Timeline composition & render (OTIO + MLT)
    # ------------------------------------------------------------------

    def generate_video_edit(
        self,
        clips: list[str],
        config: dict[str, Any],
        output_name: str | None = None,
        markers: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Build a timeline from clips, export it, and optionally render via MLT.

        Args:
            clips: List of media file paths to compose.
            config: Resolved workflow config dict with timeline/render sections.
            output_name: Optional output name prefix.
            markers: Optional list of marker dicts with time, name, color.

        Returns:
            Dict with keys:
              - timeline_exports: dict mapping format -> file path
              - render_path: str or None (if MLT render was performed)
              - timeline_info: dict with duration, track count, clip count

        Raises:
            GenerationError: If OTIO is unavailable or composition fails.
        """
        try:
            from engine.otio_timeline import OTIOTimeline, ClipSpec, MarkerSpec
        except ImportError as exc:
            raise GenerationError("OTIO module not available: pip install opentimelineio") from exc

        tl_builder = OTIOTimeline()
        if not tl_builder.is_available():
            raise GenerationError("opentimelineio is not installed: pip install opentimelineio")

        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = self._resolve_output_name(config)

        tl_config = config.get("timeline", {})
        fps = tl_config.get("fps", 24.0)
        transition = tl_config.get("transition_type", "dissolve")
        trans_dur = tl_config.get("transition_duration", 0.5)
        export_formats = tl_config.get("export_formats", ["otio", "fcpxml"])

        if self.dry_run:
            print(f"[DRY RUN] Would compose timeline from {len(clips)} clips")
            print(f"  FPS: {fps}, Transition: {transition} ({trans_dur}s)")
            print(f"  Export: {export_formats}")
            return {
                "timeline_exports": {f: os.path.join(output_dir, f"{output_name}.{f}") for f in export_formats},
                "render_path": None,
                "timeline_info": {"duration": 0, "tracks": 1, "clips": len(clips)},
            }

        # Build marker specs
        marker_specs = []
        if markers:
            for m in markers:
                marker_specs.append(MarkerSpec(
                    time=m.get("time", 0.0),
                    name=m.get("name", ""),
                    color=m.get("color", "GREEN"),
                    comment=m.get("comment", ""),
                ))

        # Create timeline
        timeline = tl_builder.timeline_from_media_engine_outputs(
            paths=clips,
            fps=fps,
            transition_type=transition if transition != "cut" else None,
            transition_duration=trans_dur if transition != "cut" else 0,
        )

        # Add markers
        for ms in marker_specs:
            tl_builder.add_marker(timeline, ms)

        # Export
        exports = tl_builder.export_all(timeline, output_dir, export_formats)

        # Get timeline info
        info = tl_builder.get_timeline_info(timeline)

        # Optionally render via MLT
        render_path = None
        render_cfg = config.get("render", {})
        if render_cfg.get("enabled", True):
            try:
                from engine.mlt_renderer import MLTRenderer
                renderer = MLTRenderer()
                if renderer.is_available():
                    render_path = renderer.render_timeline(
                        timeline, config, output_name,
                    )
            except ImportError:
                pass  # MLT not available, skip render
            except Exception as exc:
                print(f"MLT render warning: {exc}")

        return {
            "timeline_exports": exports,
            "render_path": render_path,
            "timeline_info": info,
        }

    # ------------------------------------------------------------------
    # Media inspection (PyAV)
    # ------------------------------------------------------------------

    def inspect(self, input_path: str) -> dict[str, Any]:
        """
        Inspect a media file and return metadata.

        Args:
            input_path: Path to the media file.

        Returns:
            Dict with media metadata (duration, codecs, resolution, etc.)

        Raises:
            GenerationError: If PyAV is unavailable.
        """
        try:
            from engine.pyav_processor import PyAVProcessor
        except ImportError as exc:
            raise GenerationError("PyAV module not available: pip install av") from exc

        proc = PyAVProcessor()
        if not proc.is_available():
            raise GenerationError("PyAV (av package) is not installed: pip install av")

        return proc.get_media_info(input_path)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_env(self, config: dict[str, Any]) -> dict[str, str]:
        """
        Build the environment variables dict for a generation script.

        Inherits the current process environment and adds/overrides
        media-engine-specific variables.
        """
        env = dict(os.environ)

        # Set the model
        model = config.get("model", "google/gemini-3-pro-image-preview")
        media_type = config.get("media_type", "image")

        if media_type == "video":
            env["VIDEO_MODEL"] = model
        else:
            env["IMAGE_MODEL"] = model

        return env

    def _resolve_output_dir(self, config: dict[str, Any]) -> str:
        """
        Resolve the output directory from config, expanding placeholders.

        Supported placeholders:
          {date}    -> YYYY-MM-DD
          {capsule} -> capsule directory name (from config context)
        """
        output_config = config.get("output", {})
        directory = output_config.get("directory", "generated-media/{date}/")

        # Expand placeholders
        today = date.today().strftime("%Y-%m-%d")
        directory = directory.replace("{date}", today)
        directory = directory.replace("{capsule}", config.get("_capsule_name", "default"))

        # Make absolute if relative
        if not os.path.isabs(directory):
            directory = str(Path("{{CATALYST_ROOT}}") / directory)

        # Ensure the directory exists
        os.makedirs(directory, exist_ok=True)

        return directory

    def _resolve_output_name(
        self,
        config: dict[str, Any],
        sequence: int = 1,
    ) -> str:
        """
        Build an output filename from the naming template in config.

        Supported placeholders:
          {workflow}   -> workflow name (spaces replaced with hyphens, lowercased)
          {sequence}   -> zero-padded sequence number
          {resolution} -> resolution string
          {duration}   -> video duration in seconds (video workflows)
        """
        output_config = config.get("output", {})
        naming = output_config.get("naming", "{workflow}-{sequence}")

        workflow_name = config.get("name", "output").replace(" ", "-").lower()
        resolution = config.get("generation", {}).get("resolution", "2K")
        duration_raw = config.get("generation", {}).get("duration", "")
        duration_str = str(self._normalize_duration(duration_raw)) + "s" if duration_raw else ""

        naming = naming.replace("{workflow}", workflow_name)
        naming = naming.replace("{sequence}", f"{sequence:03d}")
        naming = naming.replace("{resolution}", resolution)
        naming = naming.replace("{duration}", duration_str)

        return naming

    def _run_script(
        self,
        args: list[str],
        env: dict[str, str],
    ) -> str:
        """
        Execute a shell script and return its stdout.

        Raises GenerationError on non-zero exit code.
        """
        if self.dry_run:
            cmd_str = " ".join(args)
            model = env.get("IMAGE_MODEL", env.get("VIDEO_MODEL", "unknown"))
            output_dir = env.get("IMAGE_OUTPUT_DIR", env.get("VIDEO_OUTPUT_DIR", "/tmp"))
            # Return a synthetic path so downstream consumers (evaluator, provenance) work
            synthetic_path = os.path.join(output_dir, "dry_run_output.png")
            print(f"[DRY RUN] Would execute: {cmd_str}")
            print(f"  Model: {model}")
            print(f"  Output dir: {output_dir}")
            return synthetic_path

        try:
            result = subprocess.run(
                args,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout (video gen can be slow)
            )
        except subprocess.TimeoutExpired as exc:
            raise GenerationError(
                f"Script timed out after 600s: {' '.join(args)}"
            ) from exc
        except FileNotFoundError as exc:
            raise GenerationError(f"Script not found: {args[0]}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            raise GenerationError(
                f"Script failed (exit {result.returncode}):\n"
                f"stdout: {stdout}\n"
                f"stderr: {stderr}"
            )

        return result.stdout

    @staticmethod
    def _extract_output_path(script_output: str, output_dir: str) -> str:
        """
        Extract the output file path from script stdout.

        The generate scripts print the output path as the last non-empty line.
        In dry-run mode, the output IS the synthetic path (returned directly
        from _run_script, not parsed from stdout).
        """
        # If the output is already an absolute file path (dry-run mode returns this),
        # return it directly.
        stripped = script_output.strip()
        if stripped.startswith("/") and "\n" not in stripped:
            return stripped

        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        if not lines:
            raise GenerationError("Script produced no output")

        # The last line should be the file path
        last_line = lines[-1]

        # Check if it looks like a file path
        if last_line.startswith("/") or last_line.startswith("./"):
            return last_line

        # Try to find a path in the output
        for line in reversed(lines):
            if line.startswith("/") and ("." in line.split("/")[-1]):
                return line

        raise GenerationError(
            f"Could not extract output path from script output:\n{stripped}"
        )

    @staticmethod
    def _normalize_duration(duration: str | int | None) -> int:
        """
        Normalize a duration value to an integer (seconds).

        Accepts "15s", "15", or 15. Returns the integer value.
        Defaults to 4 if the input cannot be parsed.
        """
        if duration is None:
            return 4

        dur_str = str(duration)
        if dur_str.endswith("s"):
            dur_str = dur_str[:-1]

        try:
            return int(dur_str)
        except (ValueError, TypeError):
            return 4

    @staticmethod
    def _download_url(url: str) -> bytes:
        """
        Download content from a URL and return raw bytes.

        Args:
            url: The URL to download.

        Returns:
            Raw bytes of the downloaded content.

        Raises:
            GenerationError: If the download fails.
        """
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            raise GenerationError(f"Failed to download video from {url}: {exc}") from exc

    @staticmethod
    def _resolve_video_size(resolution: str, aspect_ratio: str) -> str:
        """
        Map resolution + aspect ratio to a Sora-compatible size string.

        Sora accepts specific size combinations like 1280x720, 1792x1024, etc.
        """
        # Map common combinations to Sora sizes
        size_map: dict[tuple[str, str], str] = {
            # 16:9 landscape
            ("720p", "16:9"): "1280x720",
            ("1080p", "16:9"): "1792x1024",
            ("1440p", "16:9"): "1792x1024",
            ("1K", "16:9"): "1280x720",
            ("2K", "16:9"): "1792x1024",
            ("2160p", "16:9"): "1792x1024",  # Sora max
            ("4K", "16:9"): "1792x1024",  # Sora max
            # 9:16 portrait
            ("720p", "9:16"): "720x1280",
            ("1080p", "9:16"): "1024x1792",
            ("1440p", "9:16"): "1024x1792",
            ("1K", "9:16"): "720x1280",
            ("2K", "9:16"): "1024x1792",
            ("2160p", "9:16"): "1024x1792",
            ("4K", "9:16"): "1024x1792",
            # 1:1 square
            ("720p", "1:1"): "1280x720",
            ("1080p", "1:1"): "1280x720",
            ("1440p", "1:1"): "1280x720",
            ("2K", "1:1"): "1280x720",
            ("4K", "1:1"): "1280x720",
            # 4:3
            ("720p", "4:3"): "1280x720",
            ("1080p", "4:3"): "1280x720",
            ("2K", "4:3"): "1280x720",
            ("4K", "4:3"): "1280x720",
            # 3:2
            ("720p", "3:2"): "1280x720",
            ("1080p", "3:2"): "1280x720",
            ("2K", "3:2"): "1792x1024",
            ("4K", "3:2"): "1792x1024",
            # 3:4
            ("720p", "3:4"): "720x1280",
            ("1080p", "3:4"): "720x1280",
            ("2K", "3:4"): "1024x1792",
            ("4K", "3:4"): "1024x1792",
            # 2:3
            ("720p", "2:3"): "720x1280",
            ("1080p", "2:3"): "720x1280",
            ("2K", "2:3"): "1024x1792",
            ("4K", "2:3"): "1024x1792",
            # 21:9 ultrawide
            ("720p", "21:9"): "1280x720",
            ("1080p", "21:9"): "1792x1024",
            ("2K", "21:9"): "1792x1024",
            ("4K", "21:9"): "1792x1024",
        }

        return size_map.get((resolution, aspect_ratio), "1280x720")
