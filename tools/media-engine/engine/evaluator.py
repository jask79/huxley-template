"""
Quality Evaluator for the Media Workflow Engine.

Provides hard checks (pass/fail) and soft evaluation (scored 0.0-1.0) for
generated media assets. Implements the generate-evaluate-iterate refinement
loop used in autonomous mode.

Soft evaluation uses the OpenRouterClient to send the generated image to
Gemini for vision-based quality scoring against configured criteria. Falls
back to a conservative stub score (0.5) if the API call fails, ensuring
the failure is visible (below most quality thresholds) rather than silently
passing. In agent_in_loop mode, evaluation is deferred to the calling
agent (unchanged from Phase 1).
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Any, Callable


class EvaluationError(Exception):
    """Raised when evaluation encounters an unrecoverable error."""


class Evaluator:
    """
    Evaluates generated media assets against config-defined criteria.

    Two evaluation types:
      1. Hard checks (pass/fail): file exists, not empty, resolution match, etc.
      2. Soft eval (scored 0.0-1.0): quality assessment against criteria.

    The evaluator also implements the refinement loop, repeatedly calling
    the generator and evaluating until quality thresholds are met or
    iteration limits are reached.
    """

    # ------------------------------------------------------------------
    # Hard checks
    # ------------------------------------------------------------------

    def hard_check(
        self,
        output_path: str,
        config: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Run pass/fail hard checks on a generated asset.

        Args:
            output_path: Path to the generated file.
            config: Resolved workflow config dict.

        Returns:
            Tuple of (all_passed, list_of_failure_descriptions).
        """
        failures: list[str] = []
        checks = config.get("refinement", {}).get(
            "hard_checks", ["file_exists", "file_not_empty"]
        )

        path = Path(output_path)

        if "file_exists" in checks:
            if not path.exists():
                failures.append(f"File does not exist: {output_path}")
                # If file doesn't exist, skip remaining checks
                return False, failures

        if "file_not_empty" in checks:
            if path.exists() and path.stat().st_size == 0:
                failures.append(f"File is empty (0 bytes): {output_path}")

        if "resolution_match" in checks:
            if path.exists() and path.stat().st_size > 0:
                res_error = self._check_resolution(path, config)
                if res_error:
                    failures.append(res_error)

        if "not_corrupted" in checks:
            if path.exists() and path.stat().st_size > 0:
                corruption_error = self._check_corruption(path)
                if corruption_error:
                    failures.append(corruption_error)

        if "duration_match" in checks:
            media_type = config.get("media_type", "image")
            if media_type == "video" and path.exists() and path.stat().st_size > 0:
                duration_error = self._check_video_duration(path, config)
                if duration_error:
                    failures.append(duration_error)

        # Transcode hard checks (PyAV)
        if "codec_match" in checks:
            if path.exists() and path.stat().st_size > 0:
                codec_error = self._check_codec(path, config)
                if codec_error:
                    failures.append(codec_error)

        if "bitrate_minimum" in checks:
            if path.exists() and path.stat().st_size > 0:
                bitrate_error = self._check_bitrate(path, config)
                if bitrate_error:
                    failures.append(bitrate_error)

        if "audio_present" in checks:
            if path.exists() and path.stat().st_size > 0:
                audio_error = self._check_audio_present(path)
                if audio_error:
                    failures.append(audio_error)

        # Timeline hard checks (OTIO)
        if "timeline_valid" in checks:
            if path.exists() and path.stat().st_size > 0:
                tl_error = self._check_timeline_valid(path)
                if tl_error:
                    failures.append(tl_error)

        if "render_complete" in checks:
            if path.exists() and path.stat().st_size > 0:
                render_error = self._check_render_complete(path, config)
                if render_error:
                    failures.append(render_error)

        # SVG-specific hard checks (for media_type == "vector")
        media_type = config.get("media_type", "image")
        if media_type == "vector" and path.exists() and path.stat().st_size > 0:
            svg_checks = {
                "svg_valid_structure", "svg_has_viewbox", "svg_has_layers",
                "svg_text_editable", "svg_file_size",
            }
            active_svg_checks = svg_checks.intersection(set(checks))
            if active_svg_checks:
                svg_failures = self._check_svg(path, config, active_svg_checks)
                failures.extend(svg_failures)

        return len(failures) == 0, failures

    # ------------------------------------------------------------------
    # Soft evaluation (AI-powered via OpenRouter)
    # ------------------------------------------------------------------

    def soft_evaluate(
        self,
        output_path: str,
        criteria: list[str],
        config: dict[str, Any],
    ) -> tuple[float, str]:
        """
        Evaluate an asset against quality criteria and return a score.

        Uses the OpenRouterClient to send the generated image to Gemini
        for vision-based scoring. Falls back to a conservative stub score
        of 0.5 if the API call fails (below most quality thresholds, so
        a broken evaluator does not silently pass assets).

        In agent_in_loop mode, the calling agent provides the actual score
        rather than relying on this method.

        Args:
            output_path: Path to the generated file.
            criteria: List of evaluation criteria from config.
            config: Resolved workflow config dict.

        Returns:
            Tuple of (score: 0.0-1.0, reasoning: str).
        """
        mode = config.get("refinement", {}).get("mode", "autonomous")

        if mode == "agent_in_loop":
            return 0.0, (
                "Agent-in-loop mode: score must be provided by the calling agent. "
                "Use the agent's visual assessment to set the score."
            )

        # Verify the file exists before attempting evaluation
        if not Path(output_path).exists():
            return 0.0, f"Cannot evaluate: file does not exist at {output_path}"

        media_type = config.get("media_type", "image")

        # Try AI-powered evaluation via OpenRouter
        try:
            from engine.api_client import OpenRouterClient

            client = OpenRouterClient()
            eval_criteria = criteria if criteria else ["overall_quality"]
            model = config.get("model", "google/gemini-3-pro-image-preview")

            if media_type == "video":
                # For video evaluation, the AI evaluates based on the prompt
                # and metadata rather than visual inspection (no keyframe
                # extraction without ffmpeg). Provide context about what
                # was generated so the evaluation is informed.
                gen_config = config.get("generation", {})
                duration = gen_config.get("duration", "unknown")
                camera = gen_config.get("camera_motion", "none")

                criteria_str = ", ".join(eval_criteria)
                video_eval_note = (
                    f"This is a video asset evaluation. Duration: {duration}, "
                    f"Camera motion: {camera}. "
                    f"Evaluate these criteria for a video: {criteria_str}. "
                    f"Score each criterion from 0 to 10 based on typical "
                    f"quality expectations for the described parameters."
                )

                # Use text-based evaluation (no vision for video files)
                scores_example = ", ".join(
                    '"{0}": 0'.format(c) for c in eval_criteria
                )
                json_example = '{{"scores": {{{0}}}, "overall": 0.0, "reasoning": "..."}}'.format(
                    scores_example
                )

                payload = {
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": (
                            f"{video_eval_note}\n\n"
                            f"Respond ONLY with valid JSON in this exact format, "
                            f"no other text: {json_example}"
                        ),
                    }],
                }

                response = client._send_request(payload)
                result = client._parse_eval_response(response)
            else:
                result = client.evaluate_image(
                    image_path=output_path,
                    criteria=eval_criteria,
                    model=model,
                )

            overall = result.get("overall", 0.5)
            scores = result.get("scores", {})
            reasoning = result.get("reasoning", "")

            # Build a detailed reasoning string
            score_details = ", ".join(
                f"{k}: {v}/10" for k, v in scores.items()
            ) if scores else "no per-criterion scores"

            media_label = "Video" if media_type == "video" else "Image"
            full_reasoning = (
                f"AI evaluation ({model}, {media_label}). "
                f"Criteria scores: [{score_details}]. "
                f"Reasoning: {reasoning}. "
                f"File: {output_path}"
            )

            return overall, full_reasoning

        except Exception as exc:
            # Graceful degradation: fall back to conservative stub score.
            # Score 0.5 is deliberately below most quality thresholds so
            # that a broken evaluator does not silently pass assets.
            criteria_str = ", ".join(criteria) if criteria else "overall_quality"
            return 0.5, (
                f"[STUB] Evaluation (AI eval failed: {exc}). "
                f"is_stub: True. "
                f"Criteria: [{criteria_str}]. "
                f"Manual evaluation recommended for production assets. "
                f"File: {output_path}"
            )

    # ------------------------------------------------------------------
    # Regression cutoff
    # ------------------------------------------------------------------

    def should_continue(
        self,
        current_score: float,
        previous_score: float | None,
        config: dict[str, Any],
    ) -> bool:
        """
        Determine whether the refinement loop should continue.

        Returns False (stop) if:
          - current_score >= quality_threshold (good enough)
          - regression_cutoff is enabled and current_score < previous_score

        Returns True (continue) otherwise.

        Args:
            current_score: Score from the most recent evaluation.
            previous_score: Score from the previous iteration (None if first).
            config: Resolved workflow config dict.
        """
        refinement = config.get("refinement", {})
        threshold = refinement.get("quality_threshold", 0.75)
        regression_cutoff = refinement.get("regression_cutoff", True)

        # Met the quality bar -- stop iterating
        if current_score >= threshold:
            return False

        # Score regressed -- stop if cutoff is enabled
        if regression_cutoff and previous_score is not None:
            if current_score < previous_score:
                return False

        return True

    # ------------------------------------------------------------------
    # Full evaluation loop
    # ------------------------------------------------------------------

    def run_evaluation_loop(
        self,
        generator_fn: Callable[[str], str],
        prompt: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Run the full generate -> evaluate -> iterate loop for autonomous mode.

        Args:
            generator_fn: A callable that takes a prompt string and returns
                          the path to the generated file. This is typically
                          a bound method like generator.generate_image.
            prompt: The generation prompt.
            config: Resolved workflow config dict.

        Returns:
            Dict with keys:
              - output_path: str, path to the best output
              - final_score: float, best quality score achieved
              - iterations: int, number of iterations performed
              - eval_log: list[dict], per-iteration evaluation records
        """
        refinement = config.get("refinement", {})
        max_iterations = refinement.get("max_iterations", 3)
        criteria = refinement.get("evaluate_criteria", ["overall_quality"])

        eval_log: list[dict[str, Any]] = []
        best_path: str | None = None
        best_score: float = 0.0
        previous_score: float | None = None

        for iteration in range(1, max_iterations + 1):
            # Generate
            try:
                output_path = generator_fn(prompt)
            except Exception as exc:
                eval_log.append({
                    "iteration": iteration,
                    "status": "generation_failed",
                    "error": str(exc),
                })
                continue

            # Hard checks
            passed, failures = self.hard_check(output_path, config)
            if not passed:
                eval_log.append({
                    "iteration": iteration,
                    "output_path": output_path,
                    "status": "hard_check_failed",
                    "failures": failures,
                })
                continue

            # Soft evaluation
            score, reasoning = self.soft_evaluate(output_path, criteria, config)

            eval_log.append({
                "iteration": iteration,
                "output_path": output_path,
                "status": "evaluated",
                "score": score,
                "reasoning": reasoning,
            })

            # Track best result
            if score > best_score:
                best_score = score
                best_path = output_path

            # Check whether to continue
            if not self.should_continue(score, previous_score, config):
                break

            previous_score = score

        return {
            "output_path": best_path or "",
            "final_score": best_score,
            "iterations": len(eval_log),
            "eval_log": eval_log,
        }

    # ------------------------------------------------------------------
    # Internal check helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_resolution(path: Path, config: dict[str, Any]) -> str | None:
        """
        Check if an image file's resolution matches the config target.

        Returns an error string if mismatched, or None if OK.
        Only checks PNG and JPEG files; skips others silently.
        """
        target_resolution = config.get("generation", {}).get("resolution", "2K")

        # Map resolution names to minimum pixel dimensions (shorter side)
        resolution_mins: dict[str, int] = {
            "1K": 720,
            "720p": 720,
            "1080p": 1080,
            "1440p": 1440,
            "2K": 1080,
            "2160p": 2160,
            "4K": 2160,
        }
        min_dim = resolution_mins.get(target_resolution, 0)
        if min_dim == 0:
            return None  # Unknown resolution target, skip check

        try:
            width, height = _read_image_dimensions(path)
        except ValueError:
            return None  # Can't read dimensions, skip check

        shorter_side = min(width, height)
        if shorter_side < min_dim:
            return (
                f"Resolution too low: {width}x{height} "
                f"(need at least {min_dim}px on shorter side for {target_resolution})"
            )

        return None

    @staticmethod
    def _check_corruption(path: Path) -> str | None:
        """
        Basic corruption check: verify file has valid image/video headers.

        Returns an error string if corrupted, or None if OK.
        """
        suffix = path.suffix.lower()

        try:
            with open(path, "rb") as f:
                header = f.read(16)
        except OSError as exc:
            return f"Cannot read file: {exc}"

        if len(header) < 8:
            return f"File too small to be valid media ({len(header)} bytes)"

        # PNG: 89 50 4E 47 0D 0A 1A 0A
        if suffix == ".png":
            if header[:8] != b"\x89PNG\r\n\x1a\n":
                return "PNG file has invalid header (possibly corrupted)"

        # JPEG: FF D8 FF
        elif suffix in (".jpg", ".jpeg"):
            if header[:3] != b"\xff\xd8\xff":
                return "JPEG file has invalid header (possibly corrupted)"

        # WebP: RIFF....WEBP
        elif suffix == ".webp":
            if header[:4] != b"RIFF" or header[8:12] != b"WEBP":
                return "WebP file has invalid header (possibly corrupted)"

        # MP4: ftyp at offset 4
        elif suffix == ".mp4":
            if header[4:8] != b"ftyp":
                return "MP4 file has invalid header (possibly corrupted)"

        return None

    @staticmethod
    def _check_video_duration(path: Path, config: dict[str, Any]) -> str | None:
        """
        Check if a video file's duration matches the config target.

        Reads the MP4 moov/mvhd atom to extract duration without requiring
        ffprobe. Returns an error string if mismatched, or None if OK.

        Tolerance: +/- 20% of target duration (video gen models are approximate).
        """
        target_raw = config.get("generation", {}).get("duration")
        if target_raw is None:
            return None  # No target duration specified, skip check

        # Normalize target duration
        dur_str = str(target_raw)
        if dur_str.endswith("s"):
            dur_str = dur_str[:-1]
        try:
            target_seconds = int(dur_str)
        except (ValueError, TypeError):
            return None  # Can't parse target, skip check

        # Try PyAV first (more accurate), fall back to MP4 atom parsing
        actual_seconds = None
        try:
            from engine.pyav_processor import PyAVProcessor
            proc = PyAVProcessor()
            if proc.is_available():
                actual_seconds = proc.get_duration(str(path))
        except Exception:
            pass
        if actual_seconds is None:
            actual_seconds = _read_mp4_duration(path)
        if actual_seconds is None:
            return None  # Can't read duration, skip check

        # Allow +/- 20% tolerance
        tolerance = target_seconds * 0.20
        lower = target_seconds - tolerance
        upper = target_seconds + tolerance

        if actual_seconds < lower or actual_seconds > upper:
            return (
                f"Video duration mismatch: {actual_seconds:.1f}s actual vs "
                f"{target_seconds}s target (tolerance: +/-20%)"
            )

        return None

    @staticmethod
    def _check_svg(path: Path, config: dict[str, Any], checks: set[str]) -> list[str]:
        """
        Run SVG-specific validation checks using the vector validator.

        Delegates to vector_validator.validate_svg for the actual checks,
        then filters results to only include the requested check names.

        Returns a list of failure description strings.
        """
        try:
            from engine.vector_validator import validate_svg
        except ImportError:
            return ["SVG validation unavailable: vector_validator module not found"]

        _, results = validate_svg(str(path), config)

        # Map validator check names to evaluator check names
        check_name_map = {
            "xml_valid": "svg_valid_structure",
            "svg_root": "svg_valid_structure",
            "svg_has_viewbox": "svg_has_viewbox",
            "svg_has_layers": "svg_has_layers",
            "svg_text_editable": "svg_text_editable",
            "svg_file_size": "svg_file_size",
        }

        failures: list[str] = []
        for result in results:
            mapped_name = check_name_map.get(result.check_name, result.check_name)
            if mapped_name in checks and not result.passed:
                failures.append(result.message)

        return failures

    @staticmethod
    def _check_codec(path: Path, config: dict[str, Any]) -> str | None:
        """Check if output file codec matches transcode config target."""
        target_codec = config.get("transcode", {}).get("codec")
        if not target_codec or target_codec == "copy":
            return None
        try:
            from engine.pyav_processor import PyAVProcessor
            proc = PyAVProcessor()
            if not proc.is_available():
                return None
            info = proc.get_media_info(str(path))
            actual = info.get("video_codec", "")
            # Normalize: h265 and hevc are the same
            norm = {"h265": "hevc", "h264": "h264", "vp9": "vp9", "av1": "av1", "prores": "prores"}
            t_norm = norm.get(target_codec, target_codec)
            a_norm = norm.get(actual, actual)
            if t_norm != a_norm:
                return f"Codec mismatch: expected {target_codec}, got {actual}"
        except Exception:
            return None
        return None

    @staticmethod
    def _check_bitrate(path: Path, config: dict[str, Any]) -> str | None:
        """Check if output bitrate meets minimum threshold."""
        min_bitrate = config.get("transcode", {}).get("bitrate")
        if not min_bitrate:
            return None
        try:
            from engine.pyav_processor import PyAVProcessor
            proc = PyAVProcessor()
            if not proc.is_available():
                return None
            info = proc.get_media_info(str(path))
            actual_bps = info.get("video_bitrate", 0)
            # Parse target: "5M" -> 5_000_000, "2000k" -> 2_000_000
            target_str = str(min_bitrate).strip().upper()
            if target_str.endswith("M"):
                target_bps = float(target_str[:-1]) * 1_000_000
            elif target_str.endswith("K"):
                target_bps = float(target_str[:-1]) * 1_000
            else:
                target_bps = float(target_str)
            # Allow 20% under target
            if actual_bps < target_bps * 0.8:
                return (
                    f"Bitrate too low: {actual_bps / 1_000_000:.1f}Mbps actual vs "
                    f"{target_bps / 1_000_000:.1f}Mbps target"
                )
        except Exception:
            return None
        return None

    @staticmethod
    def _check_audio_present(path: Path) -> str | None:
        """Check if the file has an audio track."""
        try:
            from engine.pyav_processor import PyAVProcessor
            proc = PyAVProcessor()
            if not proc.is_available():
                return None
            info = proc.get_media_info(str(path))
            if not info.get("audio_codec"):
                return "Expected audio track but none found"
        except Exception:
            return None
        return None

    @staticmethod
    def _check_timeline_valid(path: Path) -> str | None:
        """Check if an OTIO file parses without errors."""
        if path.suffix not in (".otio", ".edl", ".fcpxml"):
            return None
        try:
            from engine.otio_timeline import OTIOTimeline
            tl = OTIOTimeline()
            if not tl.is_available():
                return None
            timeline = tl.import_timeline(str(path))
            if timeline is None:
                return f"Timeline file failed to parse: {path.name}"
        except Exception as exc:
            return f"Timeline validation error: {exc}"
        return None

    @staticmethod
    def _check_render_complete(path: Path, config: dict[str, Any]) -> str | None:
        """Check rendered file duration matches expected timeline duration."""
        expected_dur = config.get("_expected_duration")
        if expected_dur is None:
            return None
        try:
            from engine.pyav_processor import PyAVProcessor
            proc = PyAVProcessor()
            if not proc.is_available():
                return None
            actual = proc.get_duration(str(path))
            if actual is None:
                return None
            tolerance = expected_dur * 0.10  # 10% tolerance for render
            if abs(actual - expected_dur) > tolerance:
                return (
                    f"Render duration mismatch: {actual:.1f}s actual vs "
                    f"{expected_dur:.1f}s expected"
                )
        except Exception:
            return None
        return None


# ---------------------------------------------------------------------------
# MP4 duration reader (stdlib only, no ffprobe)
# ---------------------------------------------------------------------------

def _read_mp4_duration(path: Path) -> float | None:
    """
    Read the duration of an MP4 file from its moov/mvhd atom.

    Scans the file for the 'moov' box, then finds the 'mvhd' box within it
    to extract the timescale and duration fields. Returns duration in seconds,
    or None if the atoms cannot be found/parsed.

    MP4 box structure:
      [4 bytes: size][4 bytes: type][payload...]
      mvhd payload (version 0): [1 byte version][3 bytes flags]
        [4 bytes creation_time][4 bytes modification_time]
        [4 bytes timescale][4 bytes duration]
      mvhd payload (version 1): [1 byte version][3 bytes flags]
        [8 bytes creation_time][8 bytes modification_time]
        [4 bytes timescale][8 bytes duration]
    """
    try:
        with open(path, "rb") as f:
            file_size = path.stat().st_size

            # Scan top-level boxes for 'moov'
            moov_data = _find_box(f, file_size, b"moov")
            if moov_data is None:
                return None

            # Scan within moov for 'mvhd'
            # We need to search the moov data as a stream
            import io
            moov_stream = io.BytesIO(moov_data)
            mvhd_data = _find_box(moov_stream, len(moov_data), b"mvhd")
            if mvhd_data is None or len(mvhd_data) < 4:
                return None

            # Parse mvhd
            version = mvhd_data[0]

            if version == 0:
                # Version 0: 4-byte fields
                if len(mvhd_data) < 20:
                    return None
                timescale = struct.unpack(">I", mvhd_data[12:16])[0]
                duration = struct.unpack(">I", mvhd_data[16:20])[0]
            elif version == 1:
                # Version 1: 8-byte time fields, 4-byte timescale, 8-byte duration
                if len(mvhd_data) < 28:
                    return None
                timescale = struct.unpack(">I", mvhd_data[20:24])[0]
                duration = struct.unpack(">Q", mvhd_data[24:32])[0]
            else:
                return None

            if timescale == 0:
                return None

            return duration / timescale

    except (OSError, struct.error):
        return None


def _find_box(stream, max_size: int, box_type: bytes) -> bytes | None:
    """
    Find a box of the given type in an MP4 stream.

    Reads sequential boxes and returns the payload of the first match.
    Returns None if the box is not found within max_size bytes.
    """
    pos = 0
    while pos < max_size:
        stream.seek(pos) if hasattr(stream, 'seek') else None
        header = stream.read(8)
        if len(header) < 8:
            return None

        box_size = struct.unpack(">I", header[:4])[0]
        btype = header[4:8]

        if box_size == 0:
            # Box extends to end of file
            remaining = max_size - pos - 8
            if btype == box_type:
                return stream.read(remaining)
            return None

        if box_size == 1:
            # Extended size (64-bit)
            ext = stream.read(8)
            if len(ext) < 8:
                return None
            box_size = struct.unpack(">Q", ext)[0]
            header_size = 16
        else:
            header_size = 8

        if box_size < header_size:
            return None  # Invalid box

        payload_size = box_size - header_size

        if btype == box_type:
            data = stream.read(payload_size)
            return data if len(data) == payload_size else None

        pos += box_size

    return None


# ---------------------------------------------------------------------------
# Image dimension reader (stdlib only, no Pillow)
# ---------------------------------------------------------------------------

def _read_image_dimensions(path: Path) -> tuple[int, int]:
    """
    Read width and height from a PNG or JPEG file header.

    Returns (width, height). Raises ValueError if format is unsupported
    or header cannot be parsed.
    """
    suffix = path.suffix.lower()

    with open(path, "rb") as f:
        if suffix == ".png":
            # PNG IHDR chunk: width at offset 16, height at offset 20 (4 bytes each, big-endian)
            header = f.read(24)
            if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Not a valid PNG file")
            width = struct.unpack(">I", header[16:20])[0]
            height = struct.unpack(">I", header[20:24])[0]
            return width, height

        elif suffix in (".jpg", ".jpeg"):
            # JPEG: scan for SOF0/SOF2 markers (0xFF 0xC0 or 0xFF 0xC2)
            data = f.read(65536)  # Read enough to find the marker
            i = 0
            while i < len(data) - 9:
                if data[i] == 0xFF:
                    marker = data[i + 1]
                    if marker in (0xC0, 0xC2):
                        # SOF: height at i+5, width at i+7 (2 bytes each, big-endian)
                        height = struct.unpack(">H", data[i + 5 : i + 7])[0]
                        width = struct.unpack(">H", data[i + 7 : i + 9])[0]
                        return width, height
                    elif marker == 0xD8:
                        i += 2  # SOI marker, skip
                    elif marker == 0xFF:
                        i += 1  # Padding byte
                    else:
                        # Other marker: read segment length and skip
                        if i + 3 < len(data):
                            seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
                            i += 2 + seg_len
                        else:
                            break
                else:
                    i += 1

            raise ValueError("Could not find SOF marker in JPEG")

    raise ValueError(f"Unsupported image format: {suffix}")
