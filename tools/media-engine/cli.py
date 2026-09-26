#!/usr/bin/env python3
"""
Huxley Media Workflow Engine CLI.

Media-type agnostic workflow orchestration for all media formats:
image, video, vector, 3D rendering, video editing, and future types.

Each media_type plugs into the same infrastructure — YAML configs,
4-layer inheritance, evaluation loops, provenance, caching, and pipelines.

Usage:
    python3 tools/media-engine/cli.py generate --workflow product-photography --prompt "..."
    python3 tools/media-engine/cli.py resolve --workflow product-photography
    python3 tools/media-engine/cli.py variant --input image.png --workflow social-content --count 5
    python3 tools/media-engine/cli.py refine --input image.png --prompt "..." --workflow product-photography
    python3 tools/media-engine/cli.py batch --workflow product-photography --prompts-file prompts.txt
    python3 tools/media-engine/cli.py pipeline --config pipelines/product-launch.yaml --prompt "..."
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure engine package is importable when running from any directory
ENGINE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_ROOT))

from engine.loader import ConfigLoader, ConfigLoadError
from engine.resolver import ConfigResolver
from engine.generator import MediaGenerator, GenerationError
from engine.evaluator import Evaluator
from engine.provenance import ProvenanceLogger
from engine.queue import RateLimiter
from engine.references import ReferenceManager
from engine.cache import PromptCache
from engine.orchestrator import WorkflowOrchestrator, PipelineError
from engine.youtube_source import YouTubeSource, YouTubeSourceError


def cmd_generate(args: argparse.Namespace) -> int:
    """Handle the 'generate' subcommand."""
    loader = ConfigLoader()
    resolver = ConfigResolver(loader)
    generator = MediaGenerator(dry_run=args.dry_run)
    evaluator = Evaluator()
    provenance = ProvenanceLogger()
    rate_limiter = RateLimiter()
    ref_manager = ReferenceManager()
    cache = PromptCache()

    # Build runtime overrides from CLI args
    runtime_overrides: dict = {}
    if args.output_name:
        runtime_overrides.setdefault("output", {})["naming"] = args.output_name

    # Apply ref-count override if specified
    ref_count_override = getattr(args, "ref_count", None)
    if ref_count_override is not None:
        runtime_overrides.setdefault("consistency", {})["reference_images"] = ref_count_override

    # Apply explicit refs directory as reference_paths override
    refs_dir = getattr(args, "refs", None)
    if refs_dir:
        runtime_overrides.setdefault("consistency", {})["reference_paths"] = [refs_dir]

    # Apply video-specific overrides
    duration_override = getattr(args, "duration", None)
    if duration_override is not None:
        runtime_overrides.setdefault("generation", {})["duration"] = duration_override

    size_override = getattr(args, "size", None)
    source_image = getattr(args, "source_image", None)
    print_ready = getattr(args, "print_ready", False)

    # Apply --print-ready flag as a config override
    if print_ready:
        vec_overrides = runtime_overrides.setdefault("vector", {})
        print_overrides = vec_overrides.setdefault("print", {})
        print_overrides["print_ready"] = True
        print_overrides.setdefault("bleed_mm", 3.0)
        print_overrides.setdefault("cmyk", True)
        print_overrides.setdefault("text_to_path", True)
        # Also set the top-level convenience flag for detection
        runtime_overrides["_print_ready"] = True

    # Apply --auth override if specified
    auth_override = getattr(args, "auth", None)
    if auth_override:
        runtime_overrides["auth"] = auth_override
        # Set matching auth_provider
        if auth_override == "openrouter":
            runtime_overrides["auth_provider"] = "openrouter"
        elif auth_override in ("gemini_direct", "gemini_oauth", "google_ai_studio"):
            runtime_overrides["auth_provider"] = "gemini"

    # Resolve config
    try:
        config = resolver.resolve_config(
            workflow=args.workflow,
            capsule_config=args.capsule,
            runtime_overrides=runtime_overrides or None,
        )
    except ConfigLoadError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    # Apply nano-banana CLI overrides post-resolution
    video_fast = getattr(args, "video_fast", False)
    if video_fast and config.get("auth") == "gemini_direct":
        config["model"] = "veo-3.1-fast-generate-preview"

    no_audio = getattr(args, "no_audio", False)
    if no_audio:
        config.setdefault("generation", {})["audio"] = "none"

    extend_from = getattr(args, "extend", None)
    if extend_from:
        config["_extend_from"] = extend_from

    # Check cache before generating (unless --no-cache)
    use_cache = not getattr(args, "no_cache", False)
    if use_cache:
        cached = cache.get(args.prompt, config)
        if cached:
            print(f"Cache hit: {cached}")
            return 0

    # Rate limit check
    provider = config.get("auth_provider", "openrouter")
    auth_type = config.get("auth", "openrouter")
    if not rate_limiter.can_proceed(provider, auth_type):
        print(f"Rate limit exceeded for {provider}. Try again later.", file=sys.stderr)
        return 1

    # Load references
    capsule_path = None
    if args.capsule:
        capsule_path = str(Path(args.capsule).parent)

    references = ref_manager.load_references(config, capsule_path)

    # YouTube source extraction (--yt-source or config youtube_source)
    yt_source_url = getattr(args, "yt_source", None) or config.get("youtube_source")
    yt_metadata = None
    yt_provenance = None

    if yt_source_url:
        yt = YouTubeSource()
        if not yt.is_available():
            print("Warning: yt-transcript tool not found, skipping YouTube source.", file=sys.stderr)
        else:
            try:
                yt_metadata = yt.extract(yt_source_url)
                # Enrich the prompt with YouTube context
                args.prompt = yt.build_prompt_context(yt_metadata, args.prompt)
                yt_provenance = yt.build_provenance_data(yt_metadata)
                print(f"YouTube source: {yt_metadata.title}")
                print(f"  Channel: {yt_metadata.channel}")
                if yt_metadata.duration:
                    print(f"  Duration: {yt_metadata.duration}")
                print(f"  Transcript: {len(yt_metadata.transcript)} chars "
                      f"(injecting first {yt.transcript_limit})")
            except YouTubeSourceError as exc:
                print(f"Warning: YouTube extraction failed: {exc}", file=sys.stderr)
                print("Continuing without YouTube context.", file=sys.stderr)

    # Store YouTube provenance in config for downstream tracking
    if yt_provenance:
        config["_youtube_source"] = yt_provenance

    # Determine media type and generate
    media_type = config.get("media_type", "image")
    refinement_mode = config.get("refinement", {}).get("mode", "autonomous")

    print(f"Workflow: {config.get('name', args.workflow)}")
    print(f"Media type: {media_type}")
    if media_type != "vector":
        print(f"Model: {config.get('model', 'unknown')}")
    if config.get("auth") == "gemini_direct":
        print(f"Provider: nano-banana (direct Gemini API)")
    elif config.get("auth") == "google_ai_studio":
        print(f"Provider: Google AI Studio (service account)")
    elif config.get("auth") == "gemini_oauth":
        print(f"Provider: Gemini OAuth (personal Google account)")
    print(f"Refinement: {refinement_mode}")
    if references:
        print(f"References: {len(references)} loaded")
    if media_type == "video":
        gen_cfg = config.get("generation", {})
        print(f"Duration: {gen_cfg.get('duration', 'default')}")
        if gen_cfg.get("camera_motion"):
            print(f"Camera: {gen_cfg['camera_motion']}")
        if source_image:
            print(f"Source image: {source_image}")
        if extend_from:
            print(f"Extending: {extend_from}")
        if config.get("auth") == "gemini_direct":
            audio = gen_cfg.get("audio", "ambient")
            print(f"Audio: {'off' if audio == 'none' else 'on'}")
    if media_type == "vector":
        vec_cfg = config.get("vector", {})
        vector_type = vec_cfg.get("type", "")
        pipeline_type = config.get("pipeline_type", "")

        if vector_type == "traced" or pipeline_type == "ai_to_vector":
            print(f"Vector type: traced (AI-to-vector pipeline)")
            trace_cfg = config.get("trace", {})
            print(f"Trace mode: {trace_cfg.get('mode', 'polygon')}")
            print(f"Trace quality: {trace_cfg.get('quality', 'balanced')}")
            gate_cfg = config.get("quality_gate", {})
            print(f"Quality gate: max_paths={gate_cfg.get('max_paths', 500)}, "
                  f"max_size={gate_cfg.get('max_file_size_kb', 500)}KB")
            # Check VTracer availability
            try:
                from engine.vtracer_cli import VTracerWrapper
                vt = VTracerWrapper()
                if vt.is_available():
                    print("VTracer: installed (available)")
                else:
                    print("VTracer: NOT installed (pip3 install vtracer)")
            except ImportError:
                print("VTracer: NOT installed (pip3 install vtracer)")
        else:
            print(f"Vector style: {vec_cfg.get('icon_style', 'line')}")
            print(f"Grid: {vec_cfg.get('grid_size', 'N/A')}")
        print(f"Export formats: {vec_cfg.get('export_formats', ['svg', 'pdf', 'png'])}")

        # Phase 3: Show Inkscape availability and print-ready status
        from engine.inkscape_cli import get_inkscape
        inkscape = get_inkscape()
        if inkscape.is_available():
            print(f"Inkscape: v{inkscape.get_version()} (available)")
        else:
            print("Inkscape: not installed (print features unavailable)")

        print_cfg = vec_cfg.get("print", {})
        is_print_ready = (
            print_cfg.get("print_ready", False)
            or vec_cfg.get("print_ready", False)
            or config.get("_print_ready", False)
        )
        if is_print_ready:
            bleed = print_cfg.get("bleed_mm", vec_cfg.get("bleed_mm", 3.0))
            do_cmyk = print_cfg.get("cmyk", vec_cfg.get("cmyk", False))
            do_ttp = print_cfg.get("text_to_path", vec_cfg.get("text_to_path", False))
            print(f"Print-ready: YES (bleed: {bleed}mm, CMYK: {do_cmyk}, outlined: {do_ttp})")
    print()

    # Vector generation has its own dedicated path with refinement loop
    if media_type == "vector":
        try:
            result = generator.generate_vector(args.prompt, config, args.output_name)

            svg_path = result["svg_path"]
            exports = result.get("exports", {})
            validation = result.get("validation", {})
            iterations = result.get("iterations", 1)
            needs_review = result.get("needs_review", False)

            print(f"SVG: {svg_path}")
            print(f"Iterations: {iterations}")

            for fmt, paths in exports.items():
                if fmt != "svg":
                    for p in paths:
                        print(f"  {fmt.upper()}: {p}")

            if validation.get("passed"):
                print("Validation: PASSED")
            else:
                print("Validation: WARNINGS")
                for r in validation.get("results", []):
                    if "FAIL" in str(r):
                        print(f"  - {r}")

            if needs_review:
                print("Mode: agent_in_loop (needs agent review)")

            # Show trace metrics if this was an AI-to-vector pipeline (Phase 4)
            trace_metrics = validation.get("trace_metrics", {})
            trace_params = validation.get("trace_params", {})
            quality_gate = validation.get("quality_gate", {})
            source_image = validation.get("source_image", "")

            if trace_metrics:
                print("Trace metrics:")
                print(f"  Paths: {trace_metrics.get('path_count', 'N/A')}")
                print(f"  File size: {trace_metrics.get('file_size', 0) / 1024:.1f}KB")
                print(f"  Colors: {trace_metrics.get('colors_used', 'N/A')}")
                print(f"  Trace time: {trace_metrics.get('trace_time_ms', 0)}ms")

            if trace_params:
                print(f"Trace params: mode={trace_params.get('mode', 'N/A')}, "
                      f"color_precision={trace_params.get('color_precision', 'N/A')}, "
                      f"filter_speckle={trace_params.get('filter_speckle', 'N/A')}")

            if quality_gate:
                gate_status = "PASSED" if quality_gate.get("passed") else "FAILED"
                rec = quality_gate.get("recommendation", "N/A")
                print(f"Quality gate: {gate_status} (recommendation: {rec})")
                for issue in quality_gate.get("issues", []):
                    print(f"  - {issue}")

            if source_image:
                print(f"Source image: {source_image}")

            # Show print-ready outputs if present (Phase 3)
            print_ready_result = result.get("print_ready")
            if print_ready_result:
                print("Print-ready outputs:")
                for out_type, out_path in print_ready_result.items():
                    print(f"  {out_type}: {out_path}")

            # Show dimension checks if present
            dim_checks = validation.get("dimension_checks", [])
            if dim_checks:
                print("Dimension checks:")
                for dc in dim_checks:
                    status = "OK" if dc.get("passed") else "MISMATCH"
                    print(f"  [{status}] {dc.get('message', dc.get('scale', ''))}")

            # Record provenance with iteration tracking
            provenance.record_provenance(
                svg_path, config, args.prompt,
                {
                    "output_path": svg_path,
                    "final_score": 1.0 if validation.get("passed") else 0.5,
                    "iterations": iterations,
                    "eval_log": [{
                        "iteration": iterations,
                        "validation": validation,
                        "exports": {k: v for k, v in exports.items()},
                        "dimension_checks": dim_checks,
                        "needs_review": needs_review,
                    }],
                },
            )

        except GenerationError as exc:
            print(f"Vector generation failed: {exc}", file=sys.stderr)
            return 1

        return 0

    try:
        if refinement_mode == "autonomous" and not args.dry_run:
            # Use the evaluation loop for autonomous mode
            if media_type == "video":
                gen_fn = lambda p: generator.generate_video(
                    p, config, args.output_name,
                    references=references, source_image=source_image,
                )
            else:
                gen_fn = lambda p: generator.generate_image(
                    p, config, args.output_name, references=references
                )

            result = evaluator.run_evaluation_loop(gen_fn, args.prompt, config)

            print(f"Iterations: {result['iterations']}")
            print(f"Final score: {result['final_score']:.2f}")
            print(f"Output: {result['output_path']}")

            # Record provenance
            if result["output_path"]:
                rate_limiter.record_request(provider, auth_type)
                provenance.record_provenance(
                    result["output_path"], config, args.prompt, result
                )
                # Cache the result
                if use_cache:
                    cache.put(args.prompt, config, result["output_path"])

        else:
            # Single-shot generation (agent_in_loop or dry_run)
            if media_type == "video":
                output_path = generator.generate_video(
                    args.prompt, config, args.output_name,
                    references=references, source_image=source_image,
                )
            else:
                output_path = generator.generate_image(
                    args.prompt, config, args.output_name, references=references
                )

            print(f"Output: {output_path}")

            # Record provenance for single-shot
            rate_limiter.record_request(provider, auth_type)
            eval_result = {
                "output_path": output_path,
                "final_score": 0.0,
                "iterations": 1,
                "eval_log": [],
            }
            provenance.record_provenance(output_path, config, args.prompt, eval_result)

            # Cache the result
            if use_cache:
                cache.put(args.prompt, config, output_path)

    except GenerationError as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """Handle the 'resolve' subcommand."""
    loader = ConfigLoader()
    resolver = ConfigResolver(loader)

    try:
        config = resolver.resolve_config(
            workflow=args.workflow,
            capsule_config=args.capsule,
        )
    except ConfigLoadError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(config, indent=2, default=str))
    else:
        print(resolver.show_resolved(config))

    return 0


def cmd_variant(args: argparse.Namespace) -> int:
    """Handle the 'variant' subcommand."""
    loader = ConfigLoader()
    resolver = ConfigResolver(loader)
    generator = MediaGenerator(dry_run=args.dry_run)
    provenance = ProvenanceLogger()
    rate_limiter = RateLimiter()

    # Override variant count from CLI
    runtime_overrides = {"variants": {"count": args.count}}

    try:
        config = resolver.resolve_config(
            workflow=args.workflow,
            capsule_config=args.capsule,
            runtime_overrides=runtime_overrides,
        )
    except ConfigLoadError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    input_path = args.input
    if not Path(input_path).exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    provider = config.get("auth_provider", "openrouter")
    auth_type = config.get("auth", "openrouter")

    print(f"Generating {args.count} variants from: {input_path}")
    print(f"Workflow: {config.get('name', args.workflow)}")
    print()

    # Generate each variant as an edit of the original
    variant_prompt = (
        f"Create a variation of this image. "
        f"Variation strength: {config.get('variants', {}).get('variation_strength', 0.3)}. "
        f"Keep the same general subject and composition but introduce subtle creative differences."
    )

    outputs: list[str] = []
    for i in range(1, args.count + 1):
        if not rate_limiter.can_proceed(provider, auth_type):
            print(f"Rate limit reached after {i - 1} variants.", file=sys.stderr)
            break

        output_name = f"{Path(input_path).stem}_variant_{i:03d}"
        print(f"  Variant {i}/{args.count}...", end=" ", flush=True)

        try:
            output_path = generator.edit_image(input_path, variant_prompt, config, output_name)
            outputs.append(output_path)
            rate_limiter.record_request(provider, auth_type)
            print(f"-> {output_path}")

            eval_result = {
                "output_path": output_path,
                "final_score": 0.0,
                "iterations": 1,
                "eval_log": [],
            }
            provenance.record_provenance(output_path, config, variant_prompt, eval_result)

        except GenerationError as exc:
            print(f"FAILED: {exc}")

    print(f"\nGenerated {len(outputs)}/{args.count} variants.")
    return 0


def cmd_refine(args: argparse.Namespace) -> int:
    """Handle the 'refine' subcommand."""
    loader = ConfigLoader()
    resolver = ConfigResolver(loader)
    generator = MediaGenerator(dry_run=args.dry_run)
    evaluator = Evaluator()
    provenance = ProvenanceLogger()
    rate_limiter = RateLimiter()

    try:
        config = resolver.resolve_config(
            workflow=args.workflow,
            capsule_config=args.capsule,
        )
    except ConfigLoadError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    input_path = args.input
    if not Path(input_path).exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    provider = config.get("auth_provider", "openrouter")
    auth_type = config.get("auth", "openrouter")

    if not rate_limiter.can_proceed(provider, auth_type):
        print(f"Rate limit exceeded for {provider}.", file=sys.stderr)
        return 1

    print(f"Refining: {input_path}")
    print(f"Edit: {args.prompt}")
    print(f"Workflow: {config.get('name', args.workflow)}")
    print()

    try:
        output_name = args.output_name or f"{Path(input_path).stem}_refined"
        output_path = generator.edit_image(input_path, args.prompt, config, output_name)
        rate_limiter.record_request(provider, auth_type)

        print(f"Output: {output_path}")

        # Hard check the result
        passed, failures = evaluator.hard_check(output_path, config)
        if not passed:
            print("Hard check failures:")
            for f in failures:
                print(f"  - {f}")
        else:
            print("Hard checks: PASSED")

        # Record provenance
        eval_result = {
            "output_path": output_path,
            "final_score": 0.85 if passed else 0.0,
            "iterations": 1,
            "eval_log": [{"status": "passed" if passed else "failed", "failures": failures}],
        }
        provenance.record_provenance(output_path, config, args.prompt, eval_result)

    except GenerationError as exc:
        print(f"Refinement failed: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_refs(args: argparse.Namespace) -> int:
    """Handle the 'refs' subcommand."""
    ref_manager = ReferenceManager()

    refs_action = args.refs_action

    if refs_action == "list":
        # Show what refs would be loaded for a workflow
        if not args.workflow:
            print("Error: --workflow is required for 'refs list'", file=sys.stderr)
            return 1

        loader = ConfigLoader()
        resolver = ConfigResolver(loader)

        try:
            config = resolver.resolve_config(
                workflow=args.workflow,
                capsule_config=args.capsule,
            )
        except ConfigLoadError as exc:
            print(f"Config error: {exc}", file=sys.stderr)
            return 1

        capsule_path = None
        if args.capsule:
            capsule_path = str(Path(args.capsule).parent)

        references = ref_manager.load_references(config, capsule_path)

        consistency = config.get("consistency", {})
        print(f"Workflow: {config.get('name', args.workflow)}")
        print(f"Max reference images: {consistency.get('reference_images', 0)}")
        print(f"Style weight: {consistency.get('style_weight', 0.5)}")
        print(f"Character lock: {consistency.get('character_lock', False)}")
        print()

        if references:
            print(f"References loaded: {len(references)}")
            for i, ref in enumerate(references, 1):
                size = Path(ref).stat().st_size if Path(ref).exists() else 0
                print(f"  {i}. {ref} ({size:,} bytes)")
        else:
            print("No reference images found.")
            print()
            print("Add references to:")
            print(f"  Shared: {ref_manager.shared_dir}/")
            if capsule_path:
                print(f"  Capsule: {capsule_path}/references/")
            print("  Or set consistency.reference_paths in your workflow config.")

        return 0

    elif refs_action == "add":
        # Add an image to a reference library directory
        if not args.image:
            print("Error: --image is required for 'refs add'", file=sys.stderr)
            return 1

        target_dir = args.dir or str(ref_manager.shared_dir)

        try:
            result = ref_manager.add_reference(target_dir, args.image)
            print(f"Added reference: {result}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        return 0

    elif refs_action == "index":
        # Index a reference directory
        target_dir = args.dir or str(ref_manager.shared_dir)
        index = ref_manager.index_references(target_dir)

        if not index:
            print(f"No images found in: {target_dir}")
            return 0

        print(f"Reference index for: {target_dir}")
        print(f"Total images: {len(index)}")
        print()

        for name, meta in index.items():
            dims = meta.get("dimensions")
            dims_str = f"{dims[0]}x{dims[1]}" if dims else "unknown"
            size_kb = meta["size"] / 1024
            print(f"  {name}: {dims_str}, {size_kb:.1f}KB, {meta['date']}")

        return 0

    else:
        print(f"Unknown refs action: {refs_action}", file=sys.stderr)
        return 1


def cmd_batch(args: argparse.Namespace) -> int:
    """Handle the 'batch' subcommand."""
    loader = ConfigLoader()
    resolver = ConfigResolver(loader)
    generator = MediaGenerator(dry_run=args.dry_run)
    evaluator = Evaluator()
    provenance = ProvenanceLogger()
    rate_limiter = RateLimiter()
    ref_manager = ReferenceManager()
    cache = PromptCache()

    # Read prompts file
    prompts_path = Path(args.prompts_file)
    if not prompts_path.exists():
        print(f"Prompts file not found: {args.prompts_file}", file=sys.stderr)
        return 1

    try:
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts = [line.strip() for line in f if line.strip()]
    except OSError as exc:
        print(f"Cannot read prompts file: {exc}", file=sys.stderr)
        return 1

    if not prompts:
        print("Prompts file is empty.", file=sys.stderr)
        return 1

    # Resolve config
    runtime_overrides: dict = {}
    if args.profile:
        runtime_overrides["profile"] = args.profile

    try:
        config = resolver.resolve_config(
            workflow=args.workflow,
            capsule_config=getattr(args, "capsule", None),
            runtime_overrides=runtime_overrides or None,
        )
    except ConfigLoadError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    # Load references once for all prompts
    references = ref_manager.load_references(config)

    provider = config.get("auth_provider", "openrouter")
    auth_type = config.get("auth", "openrouter")
    media_type = config.get("media_type", "image")

    print(f"Batch Production")
    print(f"Workflow: {config.get('name', args.workflow)}")
    print(f"Prompts: {len(prompts)}")
    print(f"Media type: {media_type}")
    print(f"Model: {config.get('model', 'unknown')}")
    if references:
        print(f"References: {len(references)} loaded")
    print()

    total = len(prompts)
    cached_count = 0
    generated_count = 0
    failed_count = 0
    outputs: list[str] = []

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{total}] {prompt[:60]}{'...' if len(prompt) > 60 else ''}")

        # Check cache first
        cached = cache.get(prompt, config)
        if cached:
            print(f"  CACHED: {cached}")
            cached_count += 1
            outputs.append(cached)
            continue

        # Rate limit check
        if not rate_limiter.can_proceed(provider, auth_type):
            print(f"  SKIPPED: Rate limit exceeded.", file=sys.stderr)
            failed_count += 1
            continue

        output_name = f"batch_{i:04d}"

        try:
            if media_type == "video":
                output_path = generator.generate_video(
                    prompt, config, output_name,
                    references=references if references else None,
                )
            else:
                output_path = generator.generate_image(
                    prompt, config, output_name,
                    references=references if references else None,
                )

            rate_limiter.record_request(provider, auth_type)

            # Cache the result
            cache.put(prompt, config, output_path)

            # Record provenance
            eval_result = {
                "output_path": output_path,
                "final_score": 0.0,
                "iterations": 1,
                "eval_log": [],
            }
            provenance.record_provenance(output_path, config, prompt, eval_result)

            outputs.append(output_path)
            generated_count += 1
            print(f"  OK: {output_path}")

        except GenerationError as exc:
            print(f"  FAILED: {exc}")
            failed_count += 1

    print()
    print(f"Batch Summary:")
    print(f"  Total prompts: {total}")
    print(f"  Cached: {cached_count}")
    print(f"  Generated: {generated_count}")
    print(f"  Failed: {failed_count}")

    return 0 if failed_count == 0 else 1


def cmd_pipeline(args: argparse.Namespace) -> int:
    """Handle the 'pipeline' subcommand."""
    import yaml

    # Check if this is an AI-to-vector pipeline (Phase 4)
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ENGINE_ROOT / config_path

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        print(f"Pipeline config error: {exc}", file=sys.stderr)
        return 1

    pipeline_type = raw_config.get("pipeline_type", "")

    if pipeline_type == "ai_to_vector":
        # Route to AI-to-vector pipeline (Phase 4)
        from engine.ai_to_vector_pipeline import (
            AIToVectorPipeline,
            AIToVectorPipelineError,
        )

        print(f"Pipeline: {raw_config.get('name', 'AI to Vector')}")
        print(f"Type: ai_to_vector")
        trace_cfg = raw_config.get("trace", {})
        print(f"Trace mode: {trace_cfg.get('mode', 'polygon')}")
        print(f"Trace quality: {trace_cfg.get('quality', 'balanced')}")
        gate_cfg = raw_config.get("quality_gate", {})
        print(f"Quality gate: max_paths={gate_cfg.get('max_paths', 500)}, "
              f"max_size={gate_cfg.get('max_file_size_kb', 500)}KB")
        print()

        try:
            pipeline = AIToVectorPipeline(dry_run=args.dry_run)
            result = pipeline.run(args.prompt, raw_config)

            # Display results
            print(f"\nSVG: {result.get('svg_path', 'N/A')}")
            if result.get("source_image_path"):
                print(f"Source image: {result['source_image_path']}")
            print(f"Iterations: {result.get('iterations', 0)}")

            # Exports
            for fmt, paths in result.get("exports", {}).items():
                for p in paths:
                    print(f"  {fmt.upper()}: {p}")

            # Trace metrics
            metrics = result.get("trace_metrics", {})
            if metrics:
                print("Trace metrics:")
                print(f"  Paths: {metrics.get('path_count', 'N/A')}")
                print(f"  File size: {metrics.get('file_size', 0) / 1024:.1f}KB")
                print(f"  Colors: {metrics.get('colors_used', 'N/A')}")
                print(f"  Trace time: {metrics.get('trace_time_ms', 0)}ms")

            # Quality gate
            gate = result.get("quality_gate_result", {})
            if gate:
                status = "PASSED" if gate.get("passed") else "FAILED"
                print(f"Quality gate: {status} (recommendation: {gate.get('recommendation', 'N/A')})")
                for issue in gate.get("issues", []):
                    print(f"  - {issue}")

            return 0

        except AIToVectorPipelineError as exc:
            print(f"AI-to-vector pipeline failed: {exc}", file=sys.stderr)
            return 1

    # Standard multi-step pipeline (existing orchestrator)
    orchestrator = WorkflowOrchestrator(dry_run=args.dry_run)

    # Load pipeline config
    try:
        pipeline_config = orchestrator.load_pipeline(args.config)
    except PipelineError as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1

    # Run the pipeline
    try:
        result = orchestrator.run_pipeline(pipeline_config, args.prompt)
    except PipelineError as exc:
        print(f"Pipeline execution failed: {exc}", file=sys.stderr)
        return 1

    # Check for any failed steps
    failed_steps = [s for s in result["steps"] if s["status"] == "failed"]
    if failed_steps:
        print(f"\nWarning: {len(failed_steps)} step(s) failed:")
        for step in failed_steps:
            print(f"  - {step['name']}: {step.get('error', 'unknown error')}")
        return 1

    return 0


def cmd_transcode(args: argparse.Namespace) -> int:
    """Handle the 'transcode' subcommand."""
    loader = ConfigLoader()
    resolver = ConfigResolver(loader)
    generator = MediaGenerator(dry_run=args.dry_run)
    provenance = ProvenanceLogger()

    input_path = args.input
    if not Path(input_path).exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Resolve config if workflow given, otherwise use defaults
    runtime_overrides: dict = {}
    tc_overrides = {}
    if args.codec:
        tc_overrides["codec"] = args.codec
    if args.resolution:
        tc_overrides["resolution"] = args.resolution
    if args.bitrate:
        tc_overrides["bitrate"] = args.bitrate
    if args.fps:
        tc_overrides["fps"] = args.fps
    if tc_overrides:
        runtime_overrides["transcode"] = tc_overrides

    try:
        config = resolver.resolve_config(
            workflow=args.workflow,
            runtime_overrides=runtime_overrides or None,
        )
    except ConfigLoadError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    tc = config.get("transcode", {})
    print(f"Transcode: {input_path}")
    print(f"  Codec: {tc.get('codec', 'h264')}")
    print(f"  Preset: {tc.get('preset', 'medium')}")
    print(f"  CRF: {tc.get('crf', 23)}")
    print(f"  Audio: {tc.get('audio_codec', 'aac')}")
    print()

    try:
        output_path = generator.transcode(input_path, config, args.output_name)
        print(f"Output: {output_path}")

        eval_result = {
            "output_path": output_path,
            "final_score": 1.0,
            "iterations": 1,
            "eval_log": [],
        }
        provenance.record_provenance(
            output_path, config, f"transcode:{input_path}", eval_result
        )

    except GenerationError as exc:
        print(f"Transcode failed: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Handle the 'inspect' subcommand."""
    input_path = args.input
    if not Path(input_path).exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    generator = MediaGenerator()
    try:
        info = generator.inspect(input_path)
    except GenerationError as exc:
        print(f"Inspect failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(info, indent=2, default=str))
    else:
        print(f"File: {input_path}")
        for key, val in info.items():
            print(f"  {key}: {val}")

    return 0


def cmd_timeline(args: argparse.Namespace) -> int:
    """Handle the 'timeline' subcommand."""
    loader = ConfigLoader()
    resolver = ConfigResolver(loader)
    generator = MediaGenerator(dry_run=args.dry_run)
    provenance = ProvenanceLogger()

    clips = args.clips
    for clip in clips:
        if not Path(clip).exists():
            print(f"Clip not found: {clip}", file=sys.stderr)
            return 1

    # Build runtime overrides
    runtime_overrides: dict = {}
    tl_overrides = {}
    if args.fps:
        tl_overrides["fps"] = args.fps
    if args.transition:
        tl_overrides["transition_type"] = args.transition
    if args.transition_duration is not None:
        tl_overrides["transition_duration"] = args.transition_duration
    if args.export_formats:
        tl_overrides["export_formats"] = args.export_formats
    if tl_overrides:
        runtime_overrides["timeline"] = tl_overrides

    if args.no_render:
        runtime_overrides.setdefault("render", {})["enabled"] = False

    workflow = getattr(args, "workflow", None) or "video-edit-basic"
    try:
        config = resolver.resolve_config(
            workflow=workflow,
            runtime_overrides=runtime_overrides or None,
        )
    except ConfigLoadError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    tl_cfg = config.get("timeline", {})
    print(f"Timeline: {args.name or 'untitled'}")
    print(f"  Clips: {len(clips)}")
    print(f"  FPS: {tl_cfg.get('fps', 24.0)}")
    print(f"  Transition: {tl_cfg.get('transition_type', 'dissolve')}")
    print(f"  Export: {tl_cfg.get('export_formats', ['otio', 'fcpxml'])}")
    render_enabled = config.get("render", {}).get("enabled", True)
    print(f"  Render: {'yes' if render_enabled else 'no'}")
    print()

    try:
        result = generator.generate_video_edit(clips, config, args.output_name)

        for fmt, path in result.get("timeline_exports", {}).items():
            print(f"  {fmt.upper()}: {path}")

        info = result.get("timeline_info", {})
        print(f"  Duration: {info.get('duration', 0):.1f}s")
        print(f"  Clips: {info.get('clips', 0)}")

        if result.get("render_path"):
            print(f"  Render: {result['render_path']}")
        elif render_enabled:
            print("  Render: skipped (melt not available)")

        # Record provenance
        primary_output = result.get("render_path") or next(
            iter(result.get("timeline_exports", {}).values()), ""
        )
        if primary_output:
            eval_result = {
                "output_path": primary_output,
                "final_score": 1.0,
                "iterations": 1,
                "eval_log": [],
            }
            provenance.record_provenance(
                primary_output, config,
                f"timeline:{','.join(Path(c).name for c in clips)}",
                eval_result,
            )

    except GenerationError as exc:
        print(f"Timeline composition failed: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    """Handle the 'compose' subcommand (convenience wrapper for timeline + render)."""
    loader = ConfigLoader()
    resolver = ConfigResolver(loader)
    generator = MediaGenerator(dry_run=args.dry_run)
    provenance = ProvenanceLogger()

    clips = args.clips
    for clip in clips:
        if not Path(clip).exists():
            print(f"Clip not found: {clip}", file=sys.stderr)
            return 1

    try:
        config = resolver.resolve_config(workflow=args.workflow)
    except ConfigLoadError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    print(f"Compose: {config.get('name', args.workflow)}")
    print(f"  Clips: {len(clips)}")
    print()

    try:
        result = generator.generate_video_edit(clips, config, args.output_name)

        for fmt, path in result.get("timeline_exports", {}).items():
            print(f"  {fmt.upper()}: {path}")

        if result.get("render_path"):
            print(f"  Render: {result['render_path']}")

    except GenerationError as exc:
        print(f"Compose failed: {exc}", file=sys.stderr)
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="media-engine",
        description="Huxley Media Workflow Engine - configurable media production pipeline",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be done without actually generating media",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- generate ----
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate an image or video from a prompt",
    )
    gen_parser.add_argument(
        "--workflow", "-w",
        required=True,
        help="Name of the workflow template to use",
    )
    gen_parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="The generation prompt",
    )
    gen_parser.add_argument(
        "--capsule", "-c",
        default=None,
        help="Path to capsule-level config YAML for overrides",
    )
    gen_parser.add_argument(
        "--output-name", "-o",
        default=None,
        help="Output filename (without extension)",
    )
    gen_parser.add_argument(
        "--refs",
        default=None,
        help="Explicit reference images directory",
    )
    gen_parser.add_argument(
        "--ref-count",
        type=int,
        default=None,
        help="Override how many reference images to include (overrides config)",
    )
    gen_parser.add_argument(
        "--duration",
        default=None,
        help="Override video duration (e.g., '15s', '30'). Video workflows only.",
    )
    gen_parser.add_argument(
        "--size",
        default=None,
        help="Override video size (e.g., '1280x720', '1792x1024'). Video workflows only.",
    )
    gen_parser.add_argument(
        "--source-image",
        default=None,
        help="Source image for image-to-video pipeline (starting frame)",
    )
    gen_parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Skip cache lookup and force regeneration",
    )
    gen_parser.add_argument(
        "--print-ready",
        action="store_true",
        default=False,
        help="Enable print-ready features (bleed, CMYK, text-to-path). "
             "Requires Inkscape for full functionality. Vector workflows only.",
    )
    gen_parser.add_argument(
        "--extend",
        default=None,
        help="Path to a previous video to extend (nano-banana Veo 3.1 only). "
             "Creates a continuation clip from the previous video.",
    )
    gen_parser.add_argument(
        "--video-fast",
        action="store_true",
        default=False,
        help="Use Veo 3.1 Fast mode ($0.10/s instead of $0.50/s). "
             "Only applies to gemini_direct auth workflows.",
    )
    gen_parser.add_argument(
        "--no-audio",
        action="store_true",
        default=False,
        help="Disable audio generation in video. Reduces cost.",
    )
    gen_parser.add_argument(
        "--yt-source",
        default=None,
        help="YouTube video URL to extract as source material. "
             "Injects title, metadata, and transcript excerpt into the prompt.",
    )
    gen_parser.add_argument(
        "--auth",
        choices=["openrouter", "gemini_direct", "gemini_oauth", "google_ai_studio"],
        default=None,
        help="Override auth method (default: from workflow YAML). "
             "openrouter=paid OpenRouter, gemini_direct=Google API key, "
             "gemini_oauth=personal Google account OAuth, "
             "google_ai_studio=GCP service account.",
    )

    # ---- resolve ----
    res_parser = subparsers.add_parser(
        "resolve",
        help="Show the fully resolved config for a workflow",
    )
    res_parser.add_argument(
        "--workflow", "-w",
        required=True,
        help="Name of the workflow template to resolve",
    )
    res_parser.add_argument(
        "--capsule", "-c",
        default=None,
        help="Path to capsule-level config YAML for overrides",
    )
    res_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON instead of formatted text",
    )

    # ---- variant ----
    var_parser = subparsers.add_parser(
        "variant",
        help="Generate variants of an existing image",
    )
    var_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the source image",
    )
    var_parser.add_argument(
        "--workflow", "-w",
        required=True,
        help="Name of the workflow template to use",
    )
    var_parser.add_argument(
        "--count", "-n",
        type=int,
        default=5,
        help="Number of variants to generate (default: 5)",
    )
    var_parser.add_argument(
        "--capsule", "-c",
        default=None,
        help="Path to capsule-level config YAML for overrides",
    )

    # ---- refine ----
    ref_parser = subparsers.add_parser(
        "refine",
        help="Edit/refine an existing image with a prompt",
    )
    ref_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the image to refine",
    )
    ref_parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="The edit/refinement instruction",
    )
    ref_parser.add_argument(
        "--workflow", "-w",
        required=True,
        help="Name of the workflow template to use",
    )
    ref_parser.add_argument(
        "--output-name", "-o",
        default=None,
        help="Output filename (without extension)",
    )
    ref_parser.add_argument(
        "--capsule", "-c",
        default=None,
        help="Path to capsule-level config YAML for overrides",
    )

    # ---- refs ----
    refs_parser = subparsers.add_parser(
        "refs",
        help="Manage reference image libraries",
    )
    refs_subparsers = refs_parser.add_subparsers(dest="refs_action", required=True)

    # refs list
    refs_list = refs_subparsers.add_parser(
        "list",
        help="Show what references would be loaded for a workflow",
    )
    refs_list.add_argument(
        "--workflow", "-w",
        default=None,
        help="Name of the workflow template",
    )
    refs_list.add_argument(
        "--capsule", "-c",
        default=None,
        help="Path to capsule-level config YAML for overrides",
    )

    # refs add
    refs_add = refs_subparsers.add_parser(
        "add",
        help="Add an image to a reference library",
    )
    refs_add.add_argument(
        "--dir", "-d",
        default=None,
        help="Target reference library directory (default: shared)",
    )
    refs_add.add_argument(
        "--image", "-i",
        default=None,
        help="Path to the image to add",
    )

    # refs index
    refs_index = refs_subparsers.add_parser(
        "index",
        help="Index images in a reference directory",
    )
    refs_index.add_argument(
        "--dir", "-d",
        default=None,
        help="Directory to index (default: shared references)",
    )

    # ---- batch ----
    batch_parser = subparsers.add_parser(
        "batch",
        help="Generate media from a batch of prompts",
    )
    batch_parser.add_argument(
        "--workflow", "-w",
        required=True,
        help="Name of the workflow template to use",
    )
    batch_parser.add_argument(
        "--prompts-file", "-f",
        required=True,
        help="Path to a text file with one prompt per line",
    )
    batch_parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Max parallel generations (reserved for future use, currently sequential)",
    )
    batch_parser.add_argument(
        "--profile",
        default=None,
        help="Override the workflow profile (e.g., 'fast-draft', 'batch-production')",
    )
    batch_parser.add_argument(
        "--capsule", "-c",
        default=None,
        help="Path to capsule-level config YAML for overrides",
    )

    # ---- pipeline ----
    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run a multi-step pipeline from a config file",
    )
    pipeline_parser.add_argument(
        "--config",
        required=True,
        help="Path to the pipeline YAML config file",
    )
    pipeline_parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="The base prompt (available as {base_prompt} in step prompts)",
    )

    # ---- transcode ----
    tc_parser = subparsers.add_parser(
        "transcode",
        help="Transcode a media file (format/codec conversion via PyAV)",
    )
    tc_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input media file",
    )
    tc_parser.add_argument(
        "--workflow", "-w",
        default="transcode-web",
        help="Workflow template for transcode settings (default: transcode-web)",
    )
    tc_parser.add_argument(
        "--codec",
        default=None,
        help="Override output codec (h264, h265, vp9, av1, prores)",
    )
    tc_parser.add_argument(
        "--resolution",
        default=None,
        help="Override output resolution (e.g., '1920x1080', '1280x720')",
    )
    tc_parser.add_argument(
        "--bitrate",
        default=None,
        help="Override output bitrate (e.g., '5M', '2000k')",
    )
    tc_parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Override output framerate",
    )
    tc_parser.add_argument(
        "--output-name", "-o",
        default=None,
        help="Output filename (without extension)",
    )

    # ---- inspect ----
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect a media file and show metadata (via PyAV)",
    )
    inspect_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the media file to inspect",
    )
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON",
    )

    # ---- timeline ----
    tl_parser = subparsers.add_parser(
        "timeline",
        help="Compose a timeline from media clips (OTIO, optional MLT render)",
    )
    tl_parser.add_argument(
        "--clips",
        nargs="+",
        required=True,
        help="Paths to media clips to assemble into a timeline",
    )
    tl_parser.add_argument(
        "--name",
        default=None,
        help="Timeline name",
    )
    tl_parser.add_argument(
        "--workflow", "-w",
        default="video-edit-basic",
        help="Workflow template for timeline settings (default: video-edit-basic)",
    )
    tl_parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Override timeline framerate (default: from workflow)",
    )
    tl_parser.add_argument(
        "--transition",
        default=None,
        help="Override transition type (cut, dissolve, wipe, fade_in, fade_out)",
    )
    tl_parser.add_argument(
        "--transition-duration",
        type=float,
        default=None,
        help="Override transition duration in seconds",
    )
    tl_parser.add_argument(
        "--export-formats",
        nargs="+",
        default=None,
        help="Override export formats (otio, edl, fcpxml)",
    )
    tl_parser.add_argument(
        "--output-name", "-o",
        default=None,
        help="Output filename prefix (without extension)",
    )
    tl_parser.add_argument(
        "--no-render",
        action="store_true",
        default=False,
        help="Skip MLT rendering (export timeline files only)",
    )

    # ---- compose ----
    comp_parser = subparsers.add_parser(
        "compose",
        help="Compose clips into a timeline and render (convenience shortcut)",
    )
    comp_parser.add_argument(
        "--clips",
        nargs="+",
        required=True,
        help="Paths to media clips to compose",
    )
    comp_parser.add_argument(
        "--workflow", "-w",
        default="video-edit-basic",
        help="Workflow template (default: video-edit-basic)",
    )
    comp_parser.add_argument(
        "--output-name", "-o",
        default=None,
        help="Output filename prefix (without extension)",
    )

    # ---- gemini-auth ----
    ga_parser = subparsers.add_parser(
        "gemini-auth",
        help="Manage Gemini OAuth authentication (login/status/logout)",
    )
    ga_sub = ga_parser.add_subparsers(dest="ga_action", required=True)
    ga_sub.add_parser("login", help="Authenticate with your Google account (opens browser)")
    ga_sub.add_parser("status", help="Check current OAuth token status")
    ga_sub.add_parser("logout", help="Delete stored OAuth token")

    # ---- google-ai-studio-auth ----
    gsa_parser = subparsers.add_parser(
        "google-ai-studio-auth",
        help="Check Google AI Studio service account status",
    )
    gsa_sub = gsa_parser.add_subparsers(dest="gsa_action", required=True)
    gsa_sub.add_parser("status", help="Check service account configuration")

    return parser


def cmd_gemini_auth(args: argparse.Namespace) -> int:
    """Handle the 'gemini-auth' subcommand."""
    from engine.gemini_oauth_client import login, status, logout, GeminiOAuthError

    action = args.ga_action

    if action == "login":
        print("Opening browser for Google OAuth consent...")
        try:
            result = login()
            print(f"Authenticated as: {result.get('email', 'unknown')}")
            print(f"Token expiry: {result.get('expiry', 'unknown')}")
            print(f"Token saved: {result.get('token_path')}")
            print("\nYou can now use --auth gemini_oauth with generate commands.")
            return 0
        except GeminiOAuthError as exc:
            print(f"Login failed: {exc}", file=sys.stderr)
            return 1

    elif action == "status":
        result = status()
        if result["valid"]:
            print(f"Status: authenticated")
            print(f"Email: {result.get('email', 'unknown')}")
            print(f"Expiry: {result.get('expiry', 'unknown')}")
            print(f"Token: {result.get('token_path')}")
        else:
            print("Status: not authenticated")
            print("Run: python3 tools/media-engine/cli.py gemini-auth login")
        return 0

    elif action == "logout":
        deleted = logout()
        if deleted:
            print("OAuth token deleted.")
        else:
            print("No token file found.")
        return 0

    return 1


def cmd_google_ai_studio_auth(args: argparse.Namespace) -> int:
    """Handle the 'google-ai-studio-auth' subcommand."""
    from engine.gemini_sa_client import status

    action = args.gsa_action

    if action == "status":
        result = status()
        if result["valid"]:
            print(f"Status: configured")
            print(f"Email: {result.get('email', 'unknown')}")
            print(f"Project: {result.get('project_id', 'unknown')}")
            print(f"Key file: {result.get('key_path')}")
            print(f"\nUse with: --auth google_ai_studio")
        else:
            print("Status: not configured")
            if result.get("key_path"):
                print(f"Key file found but invalid: {result['key_path']}")
            else:
                print("No service account key found.")
                print("\nSetup:")
                print("  1. Place key at: {{HOME_DIR}}/.catalyst/google-service-account.json")
                print("  2. Or set: GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
                print("  3. Or store path in Keychain:")
                print("     security add-generic-password -a huxley "
                      "-s google-service-account-json-path -w /path/to/key.json")
        return 0

    return 1


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Dispatch to subcommand handler
    handlers = {
        "generate": cmd_generate,
        "resolve": cmd_resolve,
        "variant": cmd_variant,
        "refine": cmd_refine,
        "refs": cmd_refs,
        "batch": cmd_batch,
        "pipeline": cmd_pipeline,
        "transcode": cmd_transcode,
        "inspect": cmd_inspect,
        "timeline": cmd_timeline,
        "compose": cmd_compose,
        "gemini-auth": cmd_gemini_auth,
        "google-ai-studio-auth": cmd_google_ai_studio_auth,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
