"""
YAML Schema and Validation for Media Workflow Configs.

Defines the structure for workflow YAML files using dataclasses and provides
validation without external dependencies (no Pydantic).

The engine is media-type agnostic. Each media_type value activates its own
validation rules and generation backend. New types (3d-render, video-edit)
register here and implement their own engine modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Dataclass schema
# ---------------------------------------------------------------------------

@dataclass
class GenerationConfig:
    """Parameters controlling media generation."""
    resolution: str = "2K"
    aspect_ratios: list[str] = field(default_factory=lambda: ["1:1"])
    # Video-specific fields (None when media_type == "image")
    duration: str | None = None
    fps: int | None = None
    camera_motion: str | None = None
    audio: str | None = None


@dataclass
class RefinementConfig:
    """Parameters controlling the evaluation/refinement loop."""
    mode: str = "autonomous"
    max_iterations: int = 3
    quality_threshold: float = 0.75
    regression_cutoff: bool = True
    evaluate_criteria: list[str] = field(default_factory=lambda: ["overall_quality"])
    hard_checks: list[str] = field(
        default_factory=lambda: ["file_exists", "file_not_empty", "resolution_match"]
    )


@dataclass
class ConsistencyConfig:
    """Parameters for style/character consistency across generations."""
    reference_images: int = 0
    style_weight: float = 0.5
    character_lock: bool = False


@dataclass
class VariantConfig:
    """Parameters for generating multiple variants."""
    count: int = 1
    variation_strength: float = 0.3


@dataclass
class OutputConfig:
    """Controls where and how generated assets are saved."""
    directory: str = "generated-media/{date}/"
    naming: str = "{workflow}-{sequence}"
    formats: list[str] = field(default_factory=lambda: ["png"])


@dataclass
class ProvenanceConfig:
    """Controls provenance/audit tracking."""
    enabled: bool = True
    log_eval_scores: bool = True
    snapshot_config: bool = True


@dataclass
class WorkflowConfig:
    """
    Top-level workflow configuration.

    This is the fully resolved schema that the engine operates on.
    """
    name: str = ""
    media_type: str = "image"
    model: str = "google/gemini-3-pro-image-preview"
    auth: str = "openrouter"
    auth_provider: str = "openrouter"
    profile: str = ""

    generation: GenerationConfig = field(default_factory=GenerationConfig)
    refinement: RefinementConfig = field(default_factory=RefinementConfig)
    consistency: ConsistencyConfig = field(default_factory=ConsistencyConfig)
    variants: VariantConfig = field(default_factory=VariantConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    provenance: ProvenanceConfig = field(default_factory=ProvenanceConfig)


# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------

VALID_MEDIA_TYPES = {
    "image",       # AI image generation (DALL-E, Gemini, Flux)
    "video",       # AI video generation (Sora 2, Veo 3)
    "vector",      # Programmatic SVG generation (local)
    "3d-render",   # Blender headless rendering (planned — 3D Developer agent)
    "video-edit",  # DaVinci Resolve automation (planned — Studio Engineer agent)
}
VALID_AUTH_TYPES = {"subscription", "api_key", "openrouter", "local", "gemini_direct", "gemini_oauth", "google_ai_studio"}
VALID_AUTH_PROVIDERS = {
    "gemini", "openai", "replicate", "openrouter",
    "stability", "midjourney", "runway", "pika",
    "local",    # Vector generation runs locally, no external API
    "blender",  # 3D rendering via local Blender installation
    "resolve",  # Video editing via local DaVinci Resolve
}
VALID_RESOLUTIONS = {"1K", "2K", "4K", "720p", "1080p", "1440p", "2160p"}
VALID_REFINEMENT_MODES = {"autonomous", "agent_in_loop"}
VALID_HARD_CHECKS = {
    "file_exists", "file_not_empty", "resolution_match", "not_corrupted",
    "duration_match",  # Video: verify duration matches config
    "no_artifacts",  # Domain-specific: visual artifact detection (future)
    # Vector-specific hard checks
    "svg_valid_structure",  # Valid XML with <svg> root
    "svg_has_viewbox",  # viewBox attribute present
    "svg_has_layers",  # At least one <g> group with id
    "svg_text_editable",  # No text baked as paths
    "svg_file_size",  # Under target file size
    # Transcode hard checks (PyAV)
    "codec_match",  # Output codec matches config target
    "bitrate_minimum",  # Bitrate meets minimum threshold
    "audio_present",  # Audio track exists when expected
    # Timeline hard checks (OTIO/MLT)
    "timeline_valid",  # OTIO file parses without errors
    "render_complete",  # Rendered file duration matches timeline
}
VALID_OUTPUT_FORMATS = {
    "png", "jpg", "jpeg", "webp", "gif",   # Image
    "mp4", "mov", "webm", "mkv", "avi",    # Video
    "svg", "pdf", "eps",                    # Vector
    "blend", "fbx", "glb", "gltf", "usd",  # 3D
    "exr",                                  # HDR/Render
    "otio", "edl", "fcpxml",               # Timeline
    "mlt",                                  # MLT XML
}
VALID_ASPECT_RATIOS = {
    "1:1", "4:3", "3:4", "4:5", "5:4",
    "16:9", "9:16", "3:2", "2:3", "21:9",
}
VALID_CAMERA_MOTIONS = {
    "static", "pan", "slow_dolly", "orbit", "zoom_in", "zoom_out", "handheld",
}
VALID_AUDIO_MODES = {"none", "ambient", "music"}
VALID_FPS_VALUES = {24, 30, 60}

# Transcode/render allowed values (PyAV + MLT)
VALID_CODECS = {"h264", "h265", "hevc", "vp9", "av1", "prores", "copy"}
VALID_AUDIO_CODECS = {"aac", "mp3", "flac", "opus", "copy", "none"}
VALID_PRESETS = {
    "ultrafast", "superfast", "veryfast", "faster", "fast",
    "medium", "slow", "slower", "veryslow",
}
VALID_PIXEL_FORMATS = {"yuv420p", "yuv422p", "yuv444p", "rgb24", "rgba"}
VALID_RENDER_CODECS = {"h264", "h265", "prores", "vp9", "copy"}

# Timeline allowed values (OTIO)
VALID_TIMELINE_TRANSITIONS = {"cut", "dissolve", "wipe", "fade_in", "fade_out"}
VALID_TIMELINE_EXPORT_FORMATS = {"otio", "edl", "fcpxml"}

# Vector-specific allowed values
VALID_ICON_STYLES = {"line", "filled", "duotone"}
VALID_VECTOR_TYPES = {
    "icon", "logo", "diagram", "badge",
    "wordmark", "monogram", "combination",
    "palette", "typography",
    "flowchart", "architecture", "wireframe",
    "traced",  # Phase 4: AI-to-vector traced output via VTracer
}
VALID_VECTOR_EXPORT_FORMATS = {"svg", "pdf", "png", "eps"}

# Phase 4: Trace-specific allowed values
VALID_TRACE_MODES = {"polygon", "spline"}
VALID_TRACE_QUALITY_PRESETS = {"fast", "balanced", "detailed", "geometric"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(config: dict[str, Any]) -> list[str]:
    """
    Validate a raw config dict against the workflow schema.

    Returns a list of validation error strings. An empty list means valid.
    """
    errors: list[str] = []

    # -- Top-level required fields --
    if not config.get("name"):
        errors.append("'name' is required and must be non-empty")

    media_type = config.get("media_type", "image")
    if media_type not in VALID_MEDIA_TYPES:
        errors.append(
            f"'media_type' must be one of {sorted(VALID_MEDIA_TYPES)}, got '{media_type}'"
        )

    auth = config.get("auth", "openrouter")
    if auth not in VALID_AUTH_TYPES:
        errors.append(
            f"'auth' must be one of {sorted(VALID_AUTH_TYPES)}, got '{auth}'"
        )

    auth_provider = config.get("auth_provider", "openrouter")
    if auth_provider not in VALID_AUTH_PROVIDERS:
        errors.append(
            f"'auth_provider' must be one of {sorted(VALID_AUTH_PROVIDERS)}, got '{auth_provider}'"
        )

    # -- YouTube source (optional) --
    youtube_source = config.get("youtube_source")
    if youtube_source is not None:
        if not isinstance(youtube_source, str) or not youtube_source.strip():
            errors.append(
                "'youtube_source' must be a non-empty string (YouTube URL or video ID)"
            )

    # -- Generation section --
    gen = config.get("generation", {})
    if isinstance(gen, dict):
        resolution = gen.get("resolution", "2K")
        if resolution not in VALID_RESOLUTIONS:
            errors.append(
                f"generation.resolution must be one of {sorted(VALID_RESOLUTIONS)}, "
                f"got '{resolution}'"
            )

        aspect_ratios = gen.get("aspect_ratios", ["1:1"])
        if not isinstance(aspect_ratios, list):
            errors.append("generation.aspect_ratios must be a list")
        else:
            import re
            for ar in aspect_ratios:
                if not isinstance(ar, str) or not re.match(r"^\d+:\d+$", ar):
                    errors.append(
                        f"generation.aspect_ratios: '{ar}' must be in N:M format "
                        f"(e.g., '16:9', '4:3')"
                    )

        if media_type == "video":
            fps = gen.get("fps")
            if fps is not None and (not isinstance(fps, int) or fps not in VALID_FPS_VALUES):
                errors.append(
                    f"generation.fps must be one of {sorted(VALID_FPS_VALUES)}, got {fps!r}"
                )

            duration = gen.get("duration")
            if duration is not None:
                # Normalize: accept "15s" or 15 or "15"
                dur_str = str(duration)
                if dur_str.endswith("s"):
                    dur_str = dur_str[:-1]
                try:
                    dur_int = int(dur_str)
                    if dur_int < 1 or dur_int > 120:
                        errors.append(
                            "generation.duration must be between 1 and 120 seconds, "
                            f"got {dur_int}"
                        )
                except (ValueError, TypeError):
                    errors.append(
                        f"generation.duration must be a string like '15s' or an integer, "
                        f"got {duration!r}"
                    )

            camera_motion = gen.get("camera_motion")
            if camera_motion is not None and camera_motion not in VALID_CAMERA_MOTIONS:
                errors.append(
                    f"generation.camera_motion must be one of "
                    f"{sorted(VALID_CAMERA_MOTIONS)}, got '{camera_motion}'"
                )

            audio = gen.get("audio")
            if audio is not None and audio not in VALID_AUDIO_MODES:
                errors.append(
                    f"generation.audio must be one of "
                    f"{sorted(VALID_AUDIO_MODES)}, got '{audio}'"
                )
    else:
        errors.append("'generation' must be a mapping")

    # -- Refinement section --
    ref = config.get("refinement", {})
    if isinstance(ref, dict):
        mode = ref.get("mode", "autonomous")
        if mode not in VALID_REFINEMENT_MODES:
            errors.append(
                f"refinement.mode must be one of {sorted(VALID_REFINEMENT_MODES)}, "
                f"got '{mode}'"
            )

        max_iter = ref.get("max_iterations", 3)
        if not isinstance(max_iter, int) or max_iter < 1 or max_iter > 10:
            errors.append("refinement.max_iterations must be an integer between 1 and 10")

        threshold = ref.get("quality_threshold", 0.75)
        if not isinstance(threshold, (int, float)) or threshold < 0.0 or threshold > 1.0:
            errors.append("refinement.quality_threshold must be a float between 0.0 and 1.0")

        hard_checks = ref.get("hard_checks", [])
        if isinstance(hard_checks, list):
            import re
            for hc in hard_checks:
                if not isinstance(hc, str) or not re.match(r"^[a-z][a-z0-9_]*$", hc):
                    errors.append(
                        f"refinement.hard_checks: '{hc}' must be a snake_case string "
                        f"(e.g., 'file_exists', 'no_artifacts')"
                    )
        else:
            errors.append("refinement.hard_checks must be a list")
    else:
        errors.append("'refinement' must be a mapping")

    # -- Consistency section --
    con = config.get("consistency", {})
    if isinstance(con, dict):
        ref_images = con.get("reference_images", 0)
        if not isinstance(ref_images, int) or ref_images < 0 or ref_images > 14:
            errors.append("consistency.reference_images must be an integer between 0 and 14")

        style_weight = con.get("style_weight", 0.5)
        if not isinstance(style_weight, (int, float)) or style_weight < 0.0 or style_weight > 1.0:
            errors.append("consistency.style_weight must be a float between 0.0 and 1.0")
    else:
        errors.append("'consistency' must be a mapping")

    # -- Variants section --
    var = config.get("variants", {})
    if isinstance(var, dict):
        count = var.get("count", 1)
        if not isinstance(count, int) or count < 1:
            errors.append("variants.count must be a positive integer")

        var_strength = var.get("variation_strength", 0.3)
        if not isinstance(var_strength, (int, float)) or var_strength < 0.0 or var_strength > 1.0:
            errors.append("variants.variation_strength must be a float between 0.0 and 1.0")
    else:
        errors.append("'variants' must be a mapping")

    # -- Output section --
    out = config.get("output", {})
    if isinstance(out, dict):
        formats = out.get("formats", ["png"])
        if isinstance(formats, list):
            for fmt in formats:
                if fmt not in VALID_OUTPUT_FORMATS:
                    errors.append(
                        f"output.formats: '{fmt}' is not valid "
                        f"(valid: {sorted(VALID_OUTPUT_FORMATS)})"
                    )
        else:
            errors.append("output.formats must be a list")
    else:
        errors.append("'output' must be a mapping")

    # -- Vector section (only validated when media_type == "vector") --
    if media_type == "vector":
        vec = config.get("vector", {})
        if isinstance(vec, dict):
            # grid_size format
            grid_size = vec.get("grid_size", "24x24")
            if grid_size:
                import re as _re
                if not _re.match(r"^\d+x\d+$", str(grid_size)):
                    errors.append(
                        f"vector.grid_size must be in NxM format (e.g., '24x24'), "
                        f"got '{grid_size}'"
                    )

            # stroke_weight
            stroke_weight = vec.get("stroke_weight", 2)
            if not isinstance(stroke_weight, (int, float)) or stroke_weight < 0.5 or stroke_weight > 10:
                errors.append("vector.stroke_weight must be a number between 0.5 and 10")

            # corner_radius
            corner_radius = vec.get("corner_radius", 0)
            if not isinstance(corner_radius, (int, float)) or corner_radius < 0:
                errors.append("vector.corner_radius must be a non-negative number")

            # icon_style
            icon_style = vec.get("icon_style", "line")
            if icon_style not in VALID_ICON_STYLES:
                errors.append(
                    f"vector.icon_style must be one of {sorted(VALID_ICON_STYLES)}, "
                    f"got '{icon_style}'"
                )

            # export_formats
            export_formats = vec.get("export_formats", ["svg", "pdf", "png"])
            if isinstance(export_formats, list):
                for ef in export_formats:
                    if ef not in VALID_VECTOR_EXPORT_FORMATS:
                        errors.append(
                            f"vector.export_formats: '{ef}' is not valid "
                            f"(valid: {sorted(VALID_VECTOR_EXPORT_FORMATS)})"
                        )
            else:
                errors.append("vector.export_formats must be a list")

            # file_size_limit_kb
            size_limit = vec.get("file_size_limit_kb", 100)
            if not isinstance(size_limit, (int, float)) or size_limit < 1:
                errors.append("vector.file_size_limit_kb must be a positive number")

            # palette (optional dict)
            palette = vec.get("palette")
            if palette is not None and not isinstance(palette, dict):
                errors.append("vector.palette must be a mapping of color_name: hex_value")

            # Phase 3: print-ready fields
            print_cfg = vec.get("print", {})
            if print_cfg and isinstance(print_cfg, dict):
                # bleed_mm
                bleed = print_cfg.get("bleed_mm")
                if bleed is not None:
                    if not isinstance(bleed, (int, float)) or bleed < 0 or bleed > 25:
                        errors.append(
                            "vector.print.bleed_mm must be a number between 0 and 25"
                        )

                # cmyk
                cmyk_val = print_cfg.get("cmyk")
                if cmyk_val is not None and not isinstance(cmyk_val, bool):
                    errors.append("vector.print.cmyk must be a boolean")

                # text_to_path
                ttp_val = print_cfg.get("text_to_path")
                if ttp_val is not None and not isinstance(ttp_val, bool):
                    errors.append("vector.print.text_to_path must be a boolean")

                # color_profile
                cp_val = print_cfg.get("color_profile")
                if cp_val is not None and not isinstance(cp_val, str):
                    errors.append("vector.print.color_profile must be a string path")

                # print_ready (convenience flag)
                pr_val = print_cfg.get("print_ready")
                if pr_val is not None and not isinstance(pr_val, bool):
                    errors.append("vector.print.print_ready must be a boolean")
            elif print_cfg:
                errors.append("vector.print must be a mapping")

            # Top-level vector convenience flags (Phase 3)
            for flag in ("print_ready", "cmyk", "text_to_path"):
                flag_val = vec.get(flag)
                if flag_val is not None and not isinstance(flag_val, bool):
                    errors.append(f"vector.{flag} must be a boolean")

            bleed_top = vec.get("bleed_mm")
            if bleed_top is not None:
                if not isinstance(bleed_top, (int, float)) or bleed_top < 0 or bleed_top > 25:
                    errors.append(
                        "vector.bleed_mm must be a number between 0 and 25"
                    )

            cp_top = vec.get("color_profile")
            if cp_top is not None and not isinstance(cp_top, str):
                errors.append("vector.color_profile must be a string path")
        elif vec:
            errors.append("'vector' must be a mapping")

    # -- Trace section (Phase 4: validated when present) --
    trace = config.get("trace", {})
    if trace and isinstance(trace, dict):
        trace_mode = trace.get("mode", "polygon")
        if trace_mode not in VALID_TRACE_MODES:
            errors.append(
                f"trace.mode must be one of {sorted(VALID_TRACE_MODES)}, "
                f"got '{trace_mode}'"
            )

        trace_quality = trace.get("quality")
        if trace_quality is not None and trace_quality not in VALID_TRACE_QUALITY_PRESETS:
            errors.append(
                f"trace.quality must be one of {sorted(VALID_TRACE_QUALITY_PRESETS)}, "
                f"got '{trace_quality}'"
            )

        color_precision = trace.get("color_precision")
        if color_precision is not None:
            if not isinstance(color_precision, int) or color_precision < 1 or color_precision > 12:
                errors.append("trace.color_precision must be an integer between 1 and 12")

        filter_speckle = trace.get("filter_speckle")
        if filter_speckle is not None:
            if not isinstance(filter_speckle, int) or filter_speckle < 0:
                errors.append("trace.filter_speckle must be a non-negative integer")

        corner_threshold = trace.get("corner_threshold")
        if corner_threshold is not None:
            if not isinstance(corner_threshold, (int, float)) or corner_threshold < 0 or corner_threshold > 180:
                errors.append("trace.corner_threshold must be a number between 0 and 180")

        length_threshold = trace.get("length_threshold")
        if length_threshold is not None:
            if not isinstance(length_threshold, (int, float)) or length_threshold < 0:
                errors.append("trace.length_threshold must be a non-negative number")

        trace_max_iter = trace.get("max_iterations")
        if trace_max_iter is not None:
            if not isinstance(trace_max_iter, int) or trace_max_iter < 1 or trace_max_iter > 50:
                errors.append("trace.max_iterations must be an integer between 1 and 50")

        splice_threshold = trace.get("splice_threshold")
        if splice_threshold is not None:
            if not isinstance(splice_threshold, (int, float)) or splice_threshold < 0 or splice_threshold > 180:
                errors.append("trace.splice_threshold must be a number between 0 and 180")

        path_precision = trace.get("path_precision")
        if path_precision is not None:
            if not isinstance(path_precision, int) or path_precision < 1 or path_precision > 8:
                errors.append("trace.path_precision must be an integer between 1 and 8")

    elif trace:
        errors.append("'trace' must be a mapping")

    # -- Quality gate section (Phase 4: validated when present) --
    qg = config.get("quality_gate", {})
    if qg and isinstance(qg, dict):
        qg_max_paths = qg.get("max_paths")
        if qg_max_paths is not None:
            if not isinstance(qg_max_paths, int) or qg_max_paths < 1:
                errors.append("quality_gate.max_paths must be a positive integer")

        qg_max_size = qg.get("max_file_size_kb")
        if qg_max_size is not None:
            if not isinstance(qg_max_size, (int, float)) or qg_max_size < 1:
                errors.append("quality_gate.max_file_size_kb must be a positive number")

        qg_max_colors = qg.get("max_colors")
        if qg_max_colors is not None:
            if not isinstance(qg_max_colors, int) or qg_max_colors < 1:
                errors.append("quality_gate.max_colors must be a positive integer")

        qg_max_retries = qg.get("max_retries")
        if qg_max_retries is not None:
            if not isinstance(qg_max_retries, int) or qg_max_retries < 1 or qg_max_retries > 10:
                errors.append("quality_gate.max_retries must be an integer between 1 and 10")

        qg_retry = qg.get("retry_on_fail")
        if qg_retry is not None and not isinstance(qg_retry, bool):
            errors.append("quality_gate.retry_on_fail must be a boolean")

    elif qg:
        errors.append("'quality_gate' must be a mapping")

    # -- Transcode section (validated when present) --
    tc = config.get("transcode", {})
    if tc and isinstance(tc, dict):
        tc_codec = tc.get("codec", "h264")
        if tc_codec not in VALID_CODECS:
            errors.append(
                f"transcode.codec must be one of {sorted(VALID_CODECS)}, got '{tc_codec}'"
            )
        tc_audio = tc.get("audio_codec", "aac")
        if tc_audio not in VALID_AUDIO_CODECS:
            errors.append(
                f"transcode.audio_codec must be one of {sorted(VALID_AUDIO_CODECS)}, "
                f"got '{tc_audio}'"
            )
        tc_preset = tc.get("preset", "medium")
        if tc_preset not in VALID_PRESETS:
            errors.append(
                f"transcode.preset must be one of {sorted(VALID_PRESETS)}, got '{tc_preset}'"
            )
        tc_crf = tc.get("crf")
        if tc_crf is not None:
            if not isinstance(tc_crf, int) or tc_crf < 0 or tc_crf > 63:
                errors.append("transcode.crf must be an integer between 0 and 63")
        tc_pix = tc.get("pixel_format")
        if tc_pix is not None and tc_pix not in VALID_PIXEL_FORMATS:
            errors.append(
                f"transcode.pixel_format must be one of {sorted(VALID_PIXEL_FORMATS)}, "
                f"got '{tc_pix}'"
            )
    elif tc:
        errors.append("'transcode' must be a mapping")

    # -- Timeline section (validated when present) --
    tl = config.get("timeline", {})
    if tl and isinstance(tl, dict):
        tl_fps = tl.get("fps")
        if tl_fps is not None:
            if not isinstance(tl_fps, (int, float)) or tl_fps <= 0:
                errors.append("timeline.fps must be a positive number")
        tl_trans = tl.get("transition_type", "dissolve")
        if tl_trans not in VALID_TIMELINE_TRANSITIONS:
            errors.append(
                f"timeline.transition_type must be one of "
                f"{sorted(VALID_TIMELINE_TRANSITIONS)}, got '{tl_trans}'"
            )
        tl_dur = tl.get("transition_duration")
        if tl_dur is not None:
            if not isinstance(tl_dur, (int, float)) or tl_dur < 0:
                errors.append("timeline.transition_duration must be a non-negative number")
        tl_fmts = tl.get("export_formats", [])
        if isinstance(tl_fmts, list):
            for fmt in tl_fmts:
                if fmt not in VALID_TIMELINE_EXPORT_FORMATS:
                    errors.append(
                        f"timeline.export_formats: '{fmt}' is not valid "
                        f"(valid: {sorted(VALID_TIMELINE_EXPORT_FORMATS)})"
                    )
        elif tl_fmts:
            errors.append("timeline.export_formats must be a list")
    elif tl:
        errors.append("'timeline' must be a mapping")

    # -- Render section (validated when present) --
    rn = config.get("render", {})
    if rn and isinstance(rn, dict):
        rn_codec = rn.get("codec", "h264")
        if rn_codec not in VALID_RENDER_CODECS:
            errors.append(
                f"render.codec must be one of {sorted(VALID_RENDER_CODECS)}, got '{rn_codec}'"
            )
        rn_quality = rn.get("quality")
        if rn_quality is not None:
            if not isinstance(rn_quality, int) or rn_quality < 0 or rn_quality > 63:
                errors.append("render.quality must be an integer between 0 and 63")
        rn_fps = rn.get("fps")
        if rn_fps is not None:
            if not isinstance(rn_fps, (int, float)) or rn_fps <= 0:
                errors.append("render.fps must be a positive number")
        rn_audio = rn.get("audio_codec")
        if rn_audio is not None and rn_audio not in VALID_AUDIO_CODECS:
            errors.append(
                f"render.audio_codec must be one of {sorted(VALID_AUDIO_CODECS)}, "
                f"got '{rn_audio}'"
            )
    elif rn:
        errors.append("'render' must be a mapping")

    return errors


def dict_to_workflow(config: dict[str, Any]) -> WorkflowConfig:
    """
    Convert a validated config dict into a WorkflowConfig dataclass tree.

    Assumes the config has already been validated (or you accept defaults
    for missing fields).
    """
    gen_raw = config.get("generation", {}) or {}
    ref_raw = config.get("refinement", {}) or {}
    con_raw = config.get("consistency", {}) or {}
    var_raw = config.get("variants", {}) or {}
    out_raw = config.get("output", {}) or {}
    pro_raw = config.get("provenance", {}) or {}

    return WorkflowConfig(
        name=config.get("name", ""),
        media_type=config.get("media_type", "image"),
        model=config.get("model", "google/gemini-3-pro-image-preview"),
        auth=config.get("auth", "openrouter"),
        auth_provider=config.get("auth_provider", "openrouter"),
        profile=config.get("profile", ""),
        generation=GenerationConfig(
            resolution=gen_raw.get("resolution", "2K"),
            aspect_ratios=gen_raw.get("aspect_ratios", ["1:1"]),
            duration=gen_raw.get("duration"),
            fps=gen_raw.get("fps"),
            camera_motion=gen_raw.get("camera_motion"),
            audio=gen_raw.get("audio"),
        ),
        refinement=RefinementConfig(
            mode=ref_raw.get("mode", "autonomous"),
            max_iterations=ref_raw.get("max_iterations", 3),
            quality_threshold=ref_raw.get("quality_threshold", 0.75),
            regression_cutoff=ref_raw.get("regression_cutoff", True),
            evaluate_criteria=ref_raw.get("evaluate_criteria", ["overall_quality"]),
            hard_checks=ref_raw.get("hard_checks", ["file_exists", "file_not_empty", "resolution_match"]),
        ),
        consistency=ConsistencyConfig(
            reference_images=con_raw.get("reference_images", 0),
            style_weight=con_raw.get("style_weight", 0.5),
            character_lock=con_raw.get("character_lock", False),
        ),
        variants=VariantConfig(
            count=var_raw.get("count", 1),
            variation_strength=var_raw.get("variation_strength", 0.3),
        ),
        output=OutputConfig(
            directory=out_raw.get("directory", "generated-media/{date}/"),
            naming=out_raw.get("naming", "{workflow}-{sequence}"),
            formats=out_raw.get("formats", ["png"]),
        ),
        provenance=ProvenanceConfig(
            enabled=pro_raw.get("enabled", True),
            log_eval_scores=pro_raw.get("log_eval_scores", True),
            snapshot_config=pro_raw.get("snapshot_config", True),
        ),
    )
