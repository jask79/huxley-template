"""
AI-to-Vector Pipeline for the Media Workflow Engine.

Orchestrates the full workflow of generating a concept image via AI,
tracing it to SVG vectors using VTracer, running quality gate checks,
post-processing the traced SVG, and exporting to configured formats.

Pipeline steps:
  1. Generate concept image (existing Media Engine AI generation)
  2. Trace to SVG via VTracer
  3. Quality gate check
  4. If quality gate fails: retry with simpler params (up to N attempts)
  5. Post-process: add semantic groups, clean namespaces, normalize viewBox
  6. Export to configured formats (SVG, PDF, PNG)
  7. Record provenance

Follows the pattern established by engine/pipeline.py (ImageToVideoPipeline).
"""

from __future__ import annotations

import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from lxml import etree

from engine.generator import MediaGenerator, GenerationError
from engine.evaluator import Evaluator
from engine.provenance import ProvenanceLogger
from engine.vtracer_cli import VTracerWrapper, VTracerError, QUALITY_PRESETS
from engine.vector_quality_gate import VectorQualityGate
from engine.vector_exporter import export_all, ExportError


class AIToVectorPipelineError(Exception):
    """Raised when the AI-to-vector pipeline fails."""


class AIToVectorPipeline:
    """
    Pipeline: AI image generation -> VTracer -> quality gate -> SVG cleanup.

    This is the Phase 4 pipeline that bridges AI raster generation with
    vector output. It generates a concept image, traces it to SVG, and
    applies quality gates and post-processing.
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
        self.vtracer = VTracerWrapper()

    def run(
        self,
        prompt: str,
        config: dict[str, Any],
        output_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute the full AI-to-vector pipeline.

        Steps:
          1. Generate concept image via Media Engine (existing API client)
          2. Trace to SVG via VTracer
          3. Quality gate check
          4. If quality gate fails: retry with simpler params (up to 3 attempts)
          5. Post-process: add semantic groups, clean namespaces
          6. Export to configured formats (SVG, PDF, PNG)
          7. Record provenance

        Args:
            prompt: The generation prompt describing the desired vector.
            config: Resolved workflow config dict. Expected to have:
              - source.workflow: image workflow to use for concept generation
              - source.model: AI model for concept image
              - trace: VTracer parameters (mode, quality, color_precision, etc.)
              - quality_gate: thresholds (max_paths, max_file_size_kb, etc.)
              - output: directory, naming, formats
              - refinement: mode, max_iterations
            output_name: Optional filename base for outputs.

        Returns:
            Dict with keys:
              - svg_path: str, path to the final post-processed SVG
              - source_image_path: str, path to the AI-generated concept image
              - exports: dict, format -> list of file paths
              - quality_gate_result: dict, quality gate evaluation
              - trace_params: dict, VTracer parameters used
              - trace_metrics: dict, tracing performance metrics
              - iterations: int, number of trace attempts
              - provenance_path: str, path to the .provenance.json sidecar

        Raises:
            AIToVectorPipelineError: If the pipeline fails unrecoverably.
        """
        # Check VTracer availability first
        if not self.dry_run and not self.vtracer.is_available():
            raise AIToVectorPipelineError(
                "vtracer is not installed. Install via: pip3 install vtracer\n"
                "The AI-to-vector pipeline requires VTracer for raster-to-vector tracing."
            )

        pipeline_start = time.monotonic()

        # Resolve output paths
        output_dir = self._resolve_output_dir(config)
        if not output_name:
            output_name = f"ai-to-vector_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Extract pipeline-specific config sections
        source_config = config.get("source", {})
        trace_config = config.get("trace", {})
        gate_config = config.get("quality_gate", {})
        refinement = config.get("refinement", {})
        max_retries = gate_config.get("max_retries", 3)
        retry_on_fail = gate_config.get("retry_on_fail", True)

        result: dict[str, Any] = {
            "svg_path": "",
            "source_image_path": "",
            "exports": {},
            "quality_gate_result": {},
            "trace_params": {},
            "trace_metrics": {},
            "iterations": 0,
            "provenance_path": "",
        }

        # ------------------------------------------------------------------
        # Step 1: Generate concept image
        # ------------------------------------------------------------------
        print("AI-to-Vector Pipeline Step 1/4: Generating concept image...")

        concept_image_path = self._generate_concept_image(
            prompt, config, source_config, output_dir, output_name
        )
        result["source_image_path"] = concept_image_path
        print(f"  Concept image: {concept_image_path}")

        if self.dry_run:
            svg_path = os.path.join(output_dir, f"{output_name}.svg")
            print("[DRY RUN] Would trace, quality-gate, post-process, and export.")
            result["svg_path"] = svg_path
            result["exports"] = {"svg": [svg_path]}
            result["quality_gate_result"] = {"passed": True, "recommendation": "accept"}
            result["iterations"] = 0
            return result

        # ------------------------------------------------------------------
        # Step 2-3: Trace + Quality Gate (with retries)
        # ------------------------------------------------------------------
        print("AI-to-Vector Pipeline Step 2/4: Tracing to SVG...")

        # Initialize quality gate
        quality_gate = VectorQualityGate(
            max_paths=gate_config.get("max_paths", 500),
            max_file_size_kb=gate_config.get("max_file_size_kb", 500),
            max_colors=gate_config.get("max_colors", 64),
        )

        # Resolve initial trace parameters
        trace_params = self._resolve_trace_params(trace_config)
        best_trace_result: dict[str, Any] | None = None
        best_gate_result: dict[str, Any] | None = None
        best_svg_path: str | None = None
        final_iteration = 0

        for iteration in range(1, max_retries + 1):
            final_iteration = iteration
            traced_svg_path = os.path.join(
                output_dir,
                f"{output_name}_traced_v{iteration}.svg"
            )

            # Trace
            try:
                trace_result = self.vtracer.trace(
                    input_image=concept_image_path,
                    output_svg=traced_svg_path,
                    **trace_params,
                )
            except VTracerError as exc:
                print(f"  Trace attempt {iteration} failed: {exc}")
                if iteration == max_retries:
                    raise AIToVectorPipelineError(
                        f"VTracer tracing failed after {max_retries} attempts: {exc}"
                    ) from exc
                continue

            print(f"  Trace attempt {iteration}: "
                  f"{trace_result['path_count']} paths, "
                  f"{trace_result['file_size'] / 1024:.1f}KB, "
                  f"{trace_result['colors_used']} colors, "
                  f"{trace_result['trace_time_ms']}ms")

            # Quality gate
            gate_result = quality_gate.evaluate(
                traced_svg_path, concept_image_path
            )

            # Track best result
            if best_trace_result is None or gate_result.get("passed"):
                best_trace_result = trace_result
                best_gate_result = gate_result
                best_svg_path = traced_svg_path

            if gate_result["passed"]:
                print(f"  Quality gate: PASSED")
                break

            print(f"  Quality gate: FAILED ({gate_result['recommendation']})")
            for issue in gate_result.get("issues", []):
                print(f"    - {issue}")

            if not retry_on_fail:
                break

            if gate_result["recommendation"] == "reject":
                print("  Trace fundamentally unsuitable. Stopping retries.")
                break

            # Apply suggested adjustments for next iteration
            adjustments = gate_result.get("suggested_adjustments", {})
            if adjustments:
                trace_params.update(adjustments)
                print(f"  Adjusting params for retry: {adjustments}")
            else:
                # Generic simplification if no specific suggestions
                trace_params["color_precision"] = max(
                    2, trace_params.get("color_precision", 6) - 2
                )
                trace_params["filter_speckle"] = min(
                    12, trace_params.get("filter_speckle", 4) + 2
                )
                print(f"  Simplified params for retry")

        # Use best result
        if best_svg_path is None or best_trace_result is None:
            raise AIToVectorPipelineError(
                "No successful trace produced. Check the source image quality."
            )

        result["trace_params"] = best_trace_result.get("params", trace_params)
        result["trace_metrics"] = {
            "trace_time_ms": best_trace_result["trace_time_ms"],
            "path_count": best_trace_result["path_count"],
            "file_size": best_trace_result["file_size"],
            "colors_used": best_trace_result["colors_used"],
        }
        result["quality_gate_result"] = best_gate_result or {}
        result["iterations"] = final_iteration

        # ------------------------------------------------------------------
        # Step 4: Post-process the traced SVG
        # ------------------------------------------------------------------
        print("AI-to-Vector Pipeline Step 3/4: Post-processing SVG...")

        final_svg_path = os.path.join(output_dir, f"{output_name}.svg")
        try:
            self._post_process_traced_svg(best_svg_path, final_svg_path, output_name)
            print(f"  Post-processed SVG: {final_svg_path}")
        except Exception as exc:
            # If post-processing fails, use the raw trace
            print(f"  Post-processing warning: {exc}")
            print(f"  Using raw traced SVG instead.")
            final_svg_path = best_svg_path

        result["svg_path"] = os.path.abspath(final_svg_path)

        # ------------------------------------------------------------------
        # Step 5: Export to configured formats
        # ------------------------------------------------------------------
        print("AI-to-Vector Pipeline Step 4/4: Exporting...")

        # Build a config suitable for the vector exporter
        export_config = {
            "vector": {
                "export_formats": config.get("output", {}).get(
                    "formats", ["svg", "pdf", "png"]
                ),
            },
            "name": config.get("name", "ai-to-vector"),
        }

        try:
            exports = export_all(final_svg_path, export_config)
            result["exports"] = exports
            for fmt, paths in exports.items():
                for p in paths:
                    print(f"  {fmt.upper()}: {p}")
        except ExportError as exc:
            print(f"  Export warning: {exc}")
            result["exports"] = {"svg": [final_svg_path]}

        # ------------------------------------------------------------------
        # Record provenance
        # ------------------------------------------------------------------
        pipeline_time_ms = int((time.monotonic() - pipeline_start) * 1000)

        provenance_data = {
            "output_path": final_svg_path,
            "final_score": 1.0 if (best_gate_result or {}).get("passed") else 0.5,
            "iterations": final_iteration,
            "eval_log": [{
                "pipeline": "ai_to_vector",
                "source_image": concept_image_path,
                "trace_params": result["trace_params"],
                "trace_metrics": result["trace_metrics"],
                "quality_gate": result["quality_gate_result"],
                "pipeline_time_ms": pipeline_time_ms,
            }],
        }

        self.provenance.record_provenance(
            final_svg_path, config, prompt, provenance_data
        )
        result["provenance_path"] = f"{final_svg_path}.provenance.json"

        # Clean up intermediate trace files (keep only the final)
        self._cleanup_intermediates(output_dir, output_name, final_iteration)

        print(f"\nPipeline complete ({pipeline_time_ms}ms)")
        return result

    def _generate_concept_image(
        self,
        prompt: str,
        pipeline_config: dict[str, Any],
        source_config: dict[str, Any],
        output_dir: str,
        output_name: str,
    ) -> str:
        """
        Generate the AI concept image for tracing.

        Uses the source workflow/model from pipeline config, or falls
        back to generating with the default image model.

        Args:
            prompt: The generation prompt.
            pipeline_config: Full pipeline config.
            source_config: The "source" section of config.
            output_dir: Directory for output files.
            output_name: Base filename.

        Returns:
            Absolute path to the generated concept image.
        """
        # Build an image generation config from the source section
        image_config: dict[str, Any] = {
            "name": f"{output_name}_concept",
            "media_type": "image",
            "model": source_config.get(
                "model", "google/gemini-2.5-flash-image"
            ),
            "auth": pipeline_config.get("auth", "openrouter"),
            "auth_provider": pipeline_config.get("auth_provider", "openrouter"),
            "generation": {
                "resolution": source_config.get("resolution", "2K"),
                "aspect_ratios": source_config.get("aspect_ratios", ["1:1"]),
            },
            "refinement": {
                "mode": "autonomous",
                "max_iterations": source_config.get("max_iterations", 2),
            },
            "output": {
                "directory": output_dir,
                "formats": ["png"],
            },
        }

        concept_prompt = (
            f"{prompt} - clean composition, minimal background, "
            f"high contrast, suitable for vector tracing"
        )

        concept_name = f"{output_name}_concept"

        if self.dry_run:
            synthetic_path = os.path.join(output_dir, f"{concept_name}.png")
            print(f"[DRY RUN] Would generate concept image: {synthetic_path}")
            return synthetic_path

        try:
            image_path = self.generator.generate_image(
                prompt=concept_prompt,
                config=image_config,
                output_name=concept_name,
            )
            return image_path
        except GenerationError as exc:
            raise AIToVectorPipelineError(
                f"Concept image generation failed: {exc}"
            ) from exc

    def _post_process_traced_svg(
        self,
        input_svg: str,
        output_svg: str,
        name_prefix: str,
    ) -> str:
        """
        Clean up VTracer output SVG.

        VTracer outputs raw paths without semantic structure. Post-processing:
          - Adds a root group with meaningful ID
          - Normalizes viewBox
          - Removes redundant whitespace in path data
          - Adds XML namespace declarations
          - Cleans up any VTracer-specific attributes

        Args:
            input_svg: Path to the raw VTracer SVG.
            output_svg: Path for the post-processed SVG.
            name_prefix: Prefix for semantic group IDs.

        Returns:
            Absolute path to the post-processed SVG.
        """
        tree = etree.parse(input_svg)
        root = tree.getroot()

        # Ensure SVG namespace
        SVG_NS = "http://www.w3.org/2000/svg"
        nsmap = root.nsmap.copy()
        if None in nsmap:
            nsmap.pop(None)
        nsmap["svg"] = SVG_NS

        # Get or set viewBox
        viewbox = root.get("viewBox") or root.get("viewbox")
        width = root.get("width")
        height = root.get("height")

        if not viewbox and width and height:
            # Try to extract numeric values
            w = self._parse_dimension(width)
            h = self._parse_dimension(height)
            if w and h:
                root.set("viewBox", f"0 0 {w} {h}")

        # Create a semantic root group wrapping all content
        safe_id = re.sub(r"[^a-z0-9_-]", "-", name_prefix.lower())

        # Collect all direct children that are elements (not text/comments)
        children = list(root)

        # Only wrap if there are paths/groups to wrap (skip defs, style, etc.)
        wrap_elements = []
        keep_elements = []
        for child in children:
            tag = etree.QName(child.tag).localname if "}" in child.tag else child.tag
            if tag in ("defs", "style", "title", "desc", "metadata"):
                keep_elements.append(child)
            else:
                wrap_elements.append(child)

        if wrap_elements:
            # Create wrapper group
            wrapper = etree.SubElement(root, f"{{{SVG_NS}}}g")
            wrapper.set("id", f"traced-{safe_id}")

            # Move wrappable elements into the group
            for el in wrap_elements:
                root.remove(el)
                wrapper.append(el)

        # Simplify path data: normalize whitespace
        for path_el in root.iter(f"{{{SVG_NS}}}path"):
            d = path_el.get("d", "")
            if d:
                # Collapse multiple spaces, trim
                d = re.sub(r"\s+", " ", d).strip()
                path_el.set("d", d)
        # Also check for paths without namespace
        for path_el in root.iter("path"):
            d = path_el.get("d", "")
            if d:
                d = re.sub(r"\s+", " ", d).strip()
                path_el.set("d", d)

        # Write output
        output_path = Path(output_svg)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        tree.write(
            str(output_path),
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

        return os.path.abspath(str(output_path))

    def _resolve_output_dir(self, config: dict[str, Any]) -> str:
        """Resolve the output directory from config."""
        output_config = config.get("output", {})
        directory = output_config.get("directory", "generated-media/{date}/")

        today = date.today().strftime("%Y-%m-%d")
        directory = directory.replace("{date}", today)
        directory = directory.replace(
            "{capsule}", config.get("_capsule_name", "default")
        )

        if not os.path.isabs(directory):
            directory = str(Path("{{CATALYST_ROOT}}") / directory)

        os.makedirs(directory, exist_ok=True)
        return directory

    def _resolve_trace_params(self, trace_config: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve VTracer parameters from the trace config section.

        If a quality preset is specified, uses that as the base and
        overlays any explicit parameter overrides.
        """
        quality = trace_config.get("quality", "balanced")
        base_params = dict(QUALITY_PRESETS.get(quality, QUALITY_PRESETS["balanced"]))

        # Overlay explicit overrides
        for key in (
            "mode", "color_precision", "filter_speckle",
            "corner_threshold", "length_threshold", "max_iterations",
            "splice_threshold", "path_precision",
        ):
            if key in trace_config:
                base_params[key] = trace_config[key]

        return base_params

    @staticmethod
    def _parse_dimension(value: str) -> float | None:
        """Parse a dimension value like '300px', '300', or '300.5'."""
        if not value:
            return None
        # Strip units
        cleaned = re.sub(r"[a-zA-Z%]+$", "", value.strip())
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _cleanup_intermediates(
        output_dir: str,
        output_name: str,
        final_iteration: int,
    ) -> None:
        """Remove intermediate traced SVG files (keep only the final)."""
        for i in range(1, final_iteration + 1):
            intermediate = os.path.join(
                output_dir, f"{output_name}_traced_v{i}.svg"
            )
            if os.path.exists(intermediate):
                try:
                    os.remove(intermediate)
                except OSError:
                    pass  # Non-critical cleanup
