"""
MLT Framework CLI Wrapper for the Media Workflow Engine.

Provides a Python interface to the MLT framework's ``melt`` CLI for
timeline-based video rendering:
  - Render OTIO timelines via MLT XML intermediate
  - Render existing MLT XML files directly
  - Build MLT XML programmatically from clip specifications
  - Compose multi-track timelines with transitions

All operations are OPTIONAL. If ``melt`` is not installed, the engine still
works -- every method returns a clear error when melt is unavailable rather
than crashing.

Minimum supported version: MLT 7.0
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

class MLTError(Exception):
    """Raised when an MLT/melt operation fails."""


class MLTNotAvailableError(MLTError):
    """Raised when the melt binary cannot be located or does not meet version requirements."""


class MLTRenderError(MLTError):
    """Raised when a melt render operation fails."""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MLTRenderer:
    """Wrapper for the MLT framework ``melt`` CLI with version pinning."""

    MINIMUM_VERSION = "7.0"

    # Search paths for the melt binary, in order of preference
    _SEARCH_PATHS = [
        "/opt/homebrew/bin/melt",
        "/usr/local/bin/melt",
        "/usr/bin/melt",
    ]

    # Default timeout for melt render operations (seconds) -- 10 minutes
    DEFAULT_TIMEOUT = 600

    # Supported output codecs
    SUPPORTED_VIDEO_CODECS = {
        "libx264", "libx265", "libvpx-vp9", "prores_ks", "dnxhd",
        "mpeg4", "h264_videotoolbox", "hevc_videotoolbox",
    }

    SUPPORTED_AUDIO_CODECS = {
        "aac", "pcm_s16le", "pcm_s24le", "libvorbis", "libopus", "mp3",
    }

    # Common resolutions
    RESOLUTIONS = {
        "720p": (1280, 720),
        "1080p": (1920, 1080),
        "2k": (2560, 1440),
        "4k": (3840, 2160),
    }

    def __init__(self, melt_path: str | None = None) -> None:
        """
        Discover melt binary and verify version.

        Args:
            melt_path: Explicit path to melt binary. If None,
                searches standard locations then PATH.
        """
        self._binary_path: str | None = None
        self._version: str | None = None
        self._available: bool = False

        if melt_path:
            self._binary_path = melt_path
        else:
            self._binary_path = self._discover_binary()

        if self._binary_path:
            try:
                self._version = self._check_version()
                self._available = True
            except MLTError:
                self._available = False

    # ------------------------------------------------------------------
    # Public interface -- status
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if melt is installed and meets version requirements."""
        return self._available

    def get_version(self) -> str:
        """Return melt version string, or empty string if unavailable."""
        return self._version or ""

    def get_binary_path(self) -> str:
        """Return the resolved binary path, or empty string if unavailable."""
        return self._binary_path or ""

    # ------------------------------------------------------------------
    # Public interface -- rendering
    # ------------------------------------------------------------------

    def render_timeline(
        self,
        otio_timeline: Any,
        config: dict[str, Any],
        output_name: str,
    ) -> str:
        """
        Render an OpenTimelineIO timeline object via MLT.

        Converts the OTIO timeline to MLT XML, then renders to the final
        output format specified in *config*.

        Args:
            otio_timeline: An ``opentimelineio.schema.Timeline`` object.
            config: Render configuration dict with keys:
                - output_dir (str): Directory for output files.
                - codec (str): Video codec (default: libx264).
                - resolution (str|tuple): e.g. "1080p" or (1920, 1080).
                - bitrate (str): e.g. "8000k" (default: "8000k").
                - fps (int): Frame rate (default: 24).
                - audio_codec (str): Audio codec (default: aac).
                - format (str): Container format (default: mp4).
            output_name: Base name for the output file (without extension).

        Returns:
            Absolute path to the rendered output file.

        Raises:
            MLTNotAvailableError: If melt is not available.
            MLTRenderError: If the render fails.
        """
        self._require_available()

        output_dir = config.get("output_dir", "/tmp")
        os.makedirs(output_dir, exist_ok=True)

        fmt = config.get("format", "mp4")
        output_path = os.path.join(output_dir, f"{output_name}.{fmt}")
        self._sanitize_path(output_path)

        # Convert OTIO to MLT XML
        mlt_xml_path = os.path.join(output_dir, f"{output_name}_timeline.mlt")
        self._sanitize_path(mlt_xml_path)

        mlt_xml_path = self.otio_to_mlt_xml(otio_timeline, mlt_xml_path)

        # Render the MLT XML
        codec = config.get("codec", "libx264")
        resolution = config.get("resolution", "1080p")
        bitrate = config.get("bitrate", "8000k")
        fps = config.get("fps", 24)
        audio_codec = config.get("audio_codec", "aac")

        return self.render_mlt_xml(
            mlt_xml_path=mlt_xml_path,
            output_path=output_path,
            codec=codec,
            resolution=resolution,
            bitrate=bitrate,
            fps=fps,
            audio_codec=audio_codec,
        )

    def render_mlt_xml(
        self,
        mlt_xml_path: str,
        output_path: str,
        codec: str = "libx264",
        resolution: str | tuple[int, int] = "1080p",
        bitrate: str = "8000k",
        fps: int = 24,
        audio_codec: str = "aac",
        timeout: int | None = None,
    ) -> str:
        """
        Render an existing MLT XML file to a video output.

        Args:
            mlt_xml_path: Path to the MLT XML file.
            output_path: Path for the rendered output.
            codec: Video codec name (default: libx264).
            resolution: Resolution as string key or (width, height) tuple.
            bitrate: Video bitrate string (default: "8000k").
            fps: Frame rate (default: 24).
            audio_codec: Audio codec name (default: "aac").
            timeout: Render timeout in seconds (default: DEFAULT_TIMEOUT).

        Returns:
            Absolute path to the rendered output.

        Raises:
            MLTNotAvailableError: If melt is not available.
            MLTRenderError: If the render fails.
        """
        self._require_available()

        mlt_xml_path = os.path.abspath(mlt_xml_path)
        self._require_file(mlt_xml_path)
        self._sanitize_path(mlt_xml_path)

        output_path = os.path.abspath(output_path)
        self._sanitize_path(output_path)

        os.makedirs(Path(output_path).parent, exist_ok=True)

        # Resolve resolution
        width, height = self._resolve_resolution(resolution)

        # Build melt command
        args = [
            mlt_xml_path,
            "-consumer",
            f"avformat:{output_path}",
            f"width={width}",
            f"height={height}",
            f"vcodec={codec}",
            f"vb={bitrate}",
            f"acodec={audio_codec}",
            f"frame_rate_num={fps}",
            "frame_rate_den=1",
            "progressive=1",
        ]

        self._run_melt(args, timeout=timeout)

        if not Path(output_path).exists():
            raise MLTRenderError(
                f"Render failed: output not created at {output_path}"
            )

        return output_path

    def otio_to_mlt_xml(
        self,
        timeline: Any,
        output_path: str,
    ) -> str:
        """
        Convert an OpenTimelineIO timeline to MLT XML.

        Attempts to use ``otio-mlt-adapter`` if available, then falls
        back to direct XML generation by walking the OTIO data model.

        Args:
            timeline: An ``opentimelineio.schema.Timeline`` object.
            output_path: Path for the generated MLT XML file.

        Returns:
            Absolute path to the MLT XML file.

        Raises:
            MLTError: If conversion fails.
        """
        output_path = os.path.abspath(output_path)
        self._sanitize_path(output_path)

        # Try the dedicated adapter first
        try:
            import opentimelineio as otio  # noqa: F811

            otio.adapters.write_to_file(timeline, output_path, adapter_name="mlt")
            if Path(output_path).exists():
                return output_path
        except (ImportError, AttributeError, Exception):
            pass

        # Fallback: walk the OTIO structure and build MLT XML manually
        clips = self._otio_timeline_to_clips(timeline)
        if not clips:
            raise MLTError(
                "Cannot convert OTIO timeline: no clips found in timeline"
            )

        fps = 24
        try:
            rate = timeline.tracks[0][0].source_range.start_time.rate
            if rate > 0:
                fps = int(rate)
        except (IndexError, AttributeError):
            pass

        return self.generate_mlt_xml(
            clips=clips,
            output_path=output_path,
            fps=fps,
        )

    def generate_mlt_xml(
        self,
        clips: list[dict[str, Any]],
        output_path: str,
        fps: int = 24,
        resolution: str | tuple[int, int] = "1080p",
        transitions: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Build MLT XML directly from clip specifications.

        Each clip dict may contain:
            - resource (str): Path to the media file (REQUIRED).
            - in_frame (int): Start frame (default: 0).
            - out_frame (int): End frame (default: -1 for full clip).
            - filters (list[dict]): Optional filters to apply.

        Each transition dict may contain:
            - type (str): Transition type, e.g. "luma" (default: "luma").
            - a_track (int): First track index (default: 0).
            - b_track (int): Second track index (default: 1).
            - in_frame (int): Transition start frame.
            - out_frame (int): Transition end frame.
            - properties (dict): Additional MLT properties.

        Args:
            clips: List of clip specification dicts.
            output_path: Path for the generated MLT XML file.
            fps: Frame rate (default: 24).
            resolution: Resolution as string key or (width, height) tuple.
            transitions: Optional list of transition specifications.

        Returns:
            Absolute path to the generated MLT XML file.

        Raises:
            MLTError: If generation fails.
        """
        output_path = os.path.abspath(output_path)
        self._sanitize_path(output_path)

        if not clips:
            raise MLTError("Cannot generate MLT XML: no clips provided")

        width, height = self._resolve_resolution(resolution)

        # Build the XML tree
        mlt_root = ET.Element("mlt")
        mlt_root.set("version", "7.0")

        # Profile
        profile = ET.SubElement(mlt_root, "profile")
        profile.set("description", "custom")
        profile.set("width", str(width))
        profile.set("height", str(height))
        profile.set("progressive", "1")
        profile.set("frame_rate_num", str(fps))
        profile.set("frame_rate_den", "1")
        profile.set("sample_aspect_num", "1")
        profile.set("sample_aspect_den", "1")
        profile.set("display_aspect_num", str(width))
        profile.set("display_aspect_den", str(height))

        # Create producers for each clip
        producer_ids = []
        for i, clip in enumerate(clips):
            resource = clip.get("resource")
            if not resource:
                raise MLTError(f"Clip {i} missing required 'resource' key")

            resource = os.path.abspath(resource)
            self._sanitize_path(resource)

            prod_id = f"producer{i}"
            producer_ids.append(prod_id)

            producer = ET.SubElement(mlt_root, "producer")
            producer.set("id", prod_id)

            prop_resource = ET.SubElement(producer, "property")
            prop_resource.set("name", "resource")
            prop_resource.text = resource

            # Optional in/out
            in_frame = clip.get("in_frame", 0)
            out_frame = clip.get("out_frame", -1)
            if in_frame > 0:
                prop_in = ET.SubElement(producer, "property")
                prop_in.set("name", "in")
                prop_in.text = str(in_frame)
            if out_frame >= 0:
                prop_out = ET.SubElement(producer, "property")
                prop_out.set("name", "out")
                prop_out.text = str(out_frame)

            # Optional filters
            for f_spec in clip.get("filters", []):
                filt = ET.SubElement(producer, "filter")
                filt_name = f_spec.get("name", "")
                filt.set("id", f"filter_{prod_id}_{filt_name}")
                filt.set("mlt_service", filt_name)
                for pk, pv in f_spec.get("properties", {}).items():
                    fp = ET.SubElement(filt, "property")
                    fp.set("name", str(pk))
                    fp.text = str(pv)

        # Create playlist
        playlist = ET.SubElement(mlt_root, "playlist")
        playlist.set("id", "playlist0")
        for i, prod_id in enumerate(producer_ids):
            entry = ET.SubElement(playlist, "entry")
            entry.set("producer", prod_id)
            clip = clips[i]
            in_frame = clip.get("in_frame", 0)
            out_frame = clip.get("out_frame", -1)
            if in_frame > 0:
                entry.set("in", str(in_frame))
            if out_frame >= 0:
                entry.set("out", str(out_frame))

        # Create tractor
        tractor = ET.SubElement(mlt_root, "tractor")
        tractor.set("id", "tractor0")

        multitrack = ET.SubElement(tractor, "multitrack")
        track = ET.SubElement(multitrack, "track")
        track.set("producer", "playlist0")

        # If there are additional tracks for multi-track composition,
        # add them alongside transitions
        if transitions:
            for t_spec in transitions:
                trans = ET.SubElement(tractor, "transition")
                trans.set("mlt_service", t_spec.get("type", "luma"))
                a_track = t_spec.get("a_track", 0)
                b_track = t_spec.get("b_track", 1)

                prop_a = ET.SubElement(trans, "property")
                prop_a.set("name", "a_track")
                prop_a.text = str(a_track)

                prop_b = ET.SubElement(trans, "property")
                prop_b.set("name", "b_track")
                prop_b.text = str(b_track)

                if "in_frame" in t_spec:
                    prop_in = ET.SubElement(trans, "property")
                    prop_in.set("name", "in")
                    prop_in.text = str(t_spec["in_frame"])
                if "out_frame" in t_spec:
                    prop_out = ET.SubElement(trans, "property")
                    prop_out.set("name", "out")
                    prop_out.text = str(t_spec["out_frame"])

                for pk, pv in t_spec.get("properties", {}).items():
                    fp = ET.SubElement(trans, "property")
                    fp.set("name", str(pk))
                    fp.text = str(pv)

        # Write the XML
        tree = ET.ElementTree(mlt_root)
        ET.indent(tree, space="  ")

        os.makedirs(Path(output_path).parent, exist_ok=True)
        tree.write(output_path, encoding="unicode", xml_declaration=True)

        return output_path

    # ------------------------------------------------------------------
    # Public interface -- inspection
    # ------------------------------------------------------------------

    def validate_mlt_xml(self, mlt_xml_path: str) -> dict[str, Any]:
        """
        Validate an MLT XML file for structural correctness.

        Checks:
        - Well-formed XML
        - Root element is <mlt>
        - At least one producer with a resource
        - At least one playlist or tractor

        Args:
            mlt_xml_path: Path to the MLT XML file.

        Returns:
            Dict with keys:
                - valid (bool): Whether the file is valid.
                - errors (list[str]): Any structural problems found.
                - producers (int): Number of producers found.
                - playlists (int): Number of playlists found.
                - tractors (int): Number of tractors found.

        Raises:
            MLTError: If the file cannot be read.
        """
        mlt_xml_path = os.path.abspath(mlt_xml_path)
        self._require_file(mlt_xml_path)

        errors: list[str] = []
        producers = 0
        playlists = 0
        tractors = 0

        try:
            tree = ET.parse(mlt_xml_path)
            root = tree.getroot()
        except ET.ParseError as exc:
            return {
                "valid": False,
                "errors": [f"XML parse error: {exc}"],
                "producers": 0,
                "playlists": 0,
                "tractors": 0,
            }

        if root.tag != "mlt":
            errors.append(f"Root element is <{root.tag}>, expected <mlt>")

        for prod in root.iter("producer"):
            producers += 1
            res_prop = prod.find("property[@name='resource']")
            if res_prop is None or not res_prop.text:
                prod_id = prod.get("id", "unknown")
                errors.append(f"Producer '{prod_id}' has no resource property")

        for _ in root.iter("playlist"):
            playlists += 1

        for _ in root.iter("tractor"):
            tractors += 1

        if producers == 0:
            errors.append("No producers found in MLT XML")
        if playlists == 0 and tractors == 0:
            errors.append("No playlists or tractors found in MLT XML")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "producers": producers,
            "playlists": playlists,
            "tractors": tractors,
        }

    def get_clip_info(self, media_path: str) -> dict[str, Any]:
        """
        Use melt to get basic information about a media file.

        Args:
            media_path: Path to the media file.

        Returns:
            Dict with keys: duration_frames, fps, width, height, has_audio.

        Raises:
            MLTNotAvailableError: If melt is not available.
            MLTError: If the query fails.
        """
        self._require_available()

        media_path = os.path.abspath(media_path)
        self._require_file(media_path)
        self._sanitize_path(media_path)

        output = self._run_melt(
            [media_path, "-consumer", "xml"],
            timeout=30,
        )

        info: dict[str, Any] = {
            "duration_frames": 0,
            "fps": 0.0,
            "width": 0,
            "height": 0,
            "has_audio": False,
        }

        try:
            root = ET.fromstring(output)
            for prop in root.iter("property"):
                name = prop.get("name", "")
                text = prop.text or ""
                if name == "length":
                    info["duration_frames"] = int(text)
                elif name == "meta.media.frame_rate_num":
                    info["fps"] = float(text)
                elif name == "meta.media.width":
                    info["width"] = int(text)
                elif name == "meta.media.height":
                    info["height"] = int(text)
                elif name == "meta.media.has_audio" and text == "1":
                    info["has_audio"] = True
        except ET.ParseError:
            pass

        return info

    # ------------------------------------------------------------------
    # Private helpers -- binary management
    # ------------------------------------------------------------------

    def _discover_binary(self) -> str | None:
        """Search for the melt binary in standard locations."""
        for path in self._SEARCH_PATHS:
            if Path(path).exists() and os.access(path, os.X_OK):
                return path

        # Fall back to PATH lookup
        found = shutil.which("melt")
        return found

    def _check_version(self) -> str:
        """
        Verify that the discovered melt meets the minimum version.

        Returns:
            Version string (e.g., "7.24.0").

        Raises:
            MLTNotAvailableError: If version check fails or version is too old.
        """
        if not self._binary_path:
            raise MLTNotAvailableError(
                "melt binary not found. Install via: brew install mlt"
            )

        try:
            result = subprocess.run(
                [self._binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            raise MLTNotAvailableError(
                f"Cannot run melt version check: {exc}. "
                "Install via: brew install mlt"
            ) from exc

        # Parse version from output like "melt 7.24.0" or
        # "melt version 7.24.0" or just a line containing digits
        combined = f"{result.stdout} {result.stderr}"
        version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", combined)
        if not version_match:
            raise MLTNotAvailableError(
                f"Cannot parse melt version from: {combined.strip()[:200]}"
            )

        version = version_match.group(1)

        if not self._version_gte(version, self.MINIMUM_VERSION):
            raise MLTNotAvailableError(
                f"melt version {version} is below minimum {self.MINIMUM_VERSION}. "
                "Update via: brew upgrade mlt"
            )

        return version

    # ------------------------------------------------------------------
    # Private helpers -- subprocess execution
    # ------------------------------------------------------------------

    def _run_melt(
        self,
        args: list[str],
        timeout: int | None = None,
    ) -> str:
        """
        Execute melt with the given arguments.

        Args:
            args: Arguments to pass to melt (after the binary path).
            timeout: Timeout in seconds (default: DEFAULT_TIMEOUT).

        Returns:
            Combined stdout from the melt process.

        Raises:
            MLTNotAvailableError: If melt is not available.
            MLTRenderError: If the command fails or times out.
        """
        self._require_available()

        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

        cmd = [self._binary_path] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise MLTRenderError(
                f"melt timed out after {timeout}s. The timeline may be too "
                f"long or complex. Command: {' '.join(cmd[:5])}..."
            ) from exc
        except FileNotFoundError as exc:
            raise MLTNotAvailableError(
                f"melt binary not found at {self._binary_path}. "
                "Install via: brew install mlt"
            ) from exc
        except OSError as exc:
            raise MLTRenderError(
                f"Failed to execute melt: {exc}"
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                raise MLTRenderError(
                    f"melt returned error (exit {result.returncode}): "
                    f"{stderr[:500]}"
                )

        return result.stdout

    # ------------------------------------------------------------------
    # Private helpers -- validation and utilities
    # ------------------------------------------------------------------

    def _require_available(self) -> None:
        """Raise MLTNotAvailableError if melt is not available."""
        if not self._available:
            raise MLTNotAvailableError(
                "melt is not available. This operation requires MLT >= "
                f"{self.MINIMUM_VERSION}. Install via: brew install mlt"
            )

    @staticmethod
    def _require_file(path: str) -> None:
        """Raise MLTError if the file does not exist."""
        if not Path(path).exists():
            raise MLTError(f"Input file not found: {path}")

    @staticmethod
    def _sanitize_path(path: str) -> str:
        """
        Sanitize a file path for safe use in subprocess arguments.

        Rejects paths containing characters that could be interpreted
        as shell metacharacters or command injections.

        Raises:
            MLTError: If the path contains unsafe characters.
        """
        dangerous_chars = {";", "|", "`", "$", "\n", "\r", "&", "(", ")", "\x00"}
        for ch in dangerous_chars:
            if ch in path:
                raise MLTError(
                    f"File path contains unsafe character {ch!r} which could "
                    f"be used for command injection. "
                    f"Rename the file to remove special characters: {path}"
                )
        return path

    @staticmethod
    def _version_gte(version: str, minimum: str) -> bool:
        """Check if version >= minimum using tuple comparison."""
        def to_tuple(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split("."))
        return to_tuple(version) >= to_tuple(minimum)

    def _resolve_resolution(
        self, resolution: str | tuple[int, int]
    ) -> tuple[int, int]:
        """
        Resolve a resolution specification to (width, height).

        Args:
            resolution: Either a string key like "1080p" or a
                (width, height) tuple.

        Returns:
            (width, height) tuple.

        Raises:
            MLTError: If the resolution cannot be resolved.
        """
        if isinstance(resolution, tuple):
            if len(resolution) == 2:
                return resolution
            raise MLTError(f"Resolution tuple must have 2 elements: {resolution}")

        if isinstance(resolution, str):
            key = resolution.lower().strip()
            if key in self.RESOLUTIONS:
                return self.RESOLUTIONS[key]
            # Try parsing "WIDTHxHEIGHT"
            match = re.match(r"(\d+)\s*x\s*(\d+)", key)
            if match:
                return int(match.group(1)), int(match.group(2))
            raise MLTError(
                f"Unknown resolution '{resolution}'. Use one of "
                f"{list(self.RESOLUTIONS.keys())} or 'WIDTHxHEIGHT' format."
            )

        raise MLTError(f"Invalid resolution type: {type(resolution)}")

    @staticmethod
    def _otio_timeline_to_clips(timeline: Any) -> list[dict[str, Any]]:
        """
        Walk an OTIO timeline and extract clip specifications.

        Returns a list of clip dicts suitable for ``generate_mlt_xml``.
        """
        clips: list[dict[str, Any]] = []

        try:
            for track in timeline.tracks:
                for item in track:
                    # Only process actual clips (skip gaps, transitions)
                    type_name = type(item).__name__
                    if type_name not in ("Clip",):
                        continue

                    resource = ""
                    if hasattr(item, "media_reference") and item.media_reference:
                        ref = item.media_reference
                        if hasattr(ref, "target_url"):
                            resource = ref.target_url
                            # Strip file:// prefix for local paths
                            if resource.startswith("file://"):
                                resource = resource[7:]
                        elif hasattr(ref, "name"):
                            resource = ref.name

                    if not resource:
                        continue

                    clip_spec: dict[str, Any] = {"resource": resource}

                    if item.source_range:
                        sr = item.source_range
                        rate = sr.start_time.rate or 24
                        in_frame = int(sr.start_time.value)
                        duration_frames = int(sr.duration.value)
                        clip_spec["in_frame"] = in_frame
                        clip_spec["out_frame"] = in_frame + duration_frames - 1

                    clips.append(clip_spec)
        except (AttributeError, TypeError):
            pass

        return clips


# ---------------------------------------------------------------------------
# Module-level convenience: singleton instance
# ---------------------------------------------------------------------------

_default_instance: MLTRenderer | None = None


def get_mlt_renderer() -> MLTRenderer:
    """
    Get or create the module-level MLTRenderer singleton.

    Returns:
        An MLTRenderer instance (may or may not be available depending
        on whether melt is installed).
    """
    global _default_instance
    if _default_instance is None:
        _default_instance = MLTRenderer()
    return _default_instance
