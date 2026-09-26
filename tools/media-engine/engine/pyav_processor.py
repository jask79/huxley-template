"""
PyAV Processor for the Media Workflow Engine.

Provides a Python interface for video/audio processing using the PyAV library
(FFmpeg bindings). Handles transcoding, frame extraction, media inspection,
resizing, audio extraction, and thumbnail generation.

PyAV is an optional dependency. If not installed, is_available() returns False
and all operations raise PyAVNotAvailableError with install instructions. The
rest of the engine works without it.

Install: pip3 install av
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class PyAVError(Exception):
    """Base error for all PyAV processor failures."""


class PyAVNotAvailableError(PyAVError):
    """Raised when the `av` package cannot be imported."""


class TranscodeError(PyAVError):
    """Raised when a transcode operation fails."""


# ---------------------------------------------------------------------------
# Codec and preset mappings
# ---------------------------------------------------------------------------

# Map friendly codec names to libav codec IDs
VIDEO_CODEC_MAP: dict[str, str] = {
    "h264": "libx264",
    "h.264": "libx264",
    "x264": "libx264",
    "h265": "libx265",
    "h.265": "libx265",
    "x265": "libx265",
    "hevc": "libx265",
    "vp9": "libvpx-vp9",
    "vp8": "libvpx",
    "av1": "libaom-av1",
    "prores": "prores_ks",
    "copy": "copy",
}

AUDIO_CODEC_MAP: dict[str, str] = {
    "aac": "aac",
    "mp3": "libmp3lame",
    "opus": "libopus",
    "flac": "flac",
    "pcm": "pcm_s16le",
    "vorbis": "libvorbis",
    "copy": "copy",
    "none": "none",
}

# Resolution shorthand → (width, height)
RESOLUTION_MAP: dict[str, tuple[int, int]] = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "2k": (2560, 1440),
    "4k": (3840, 2160),
    "2160p": (3840, 2160),
}

# CRF presets for quality-based encoding
CRF_PRESETS: dict[str, dict[str, int]] = {
    "libx264": {"high": 18, "medium": 23, "low": 28},
    "libx265": {"high": 18, "medium": 24, "low": 30},
    "libaom-av1": {"high": 20, "medium": 30, "low": 40},
}

# Encoding speed presets (fastest → slowest, better compression)
SPEED_PRESETS = [
    "ultrafast", "superfast", "veryfast", "faster", "fast",
    "medium", "slow", "slower", "veryslow",
]

# Default timeout for operations (seconds)
DEFAULT_TIMEOUT = 300


# ---------------------------------------------------------------------------
# PyAV Processor
# ---------------------------------------------------------------------------


class PyAVProcessor:
    """
    Video/audio processor wrapping the PyAV library (FFmpeg Python bindings).

    PyAV is an optional dependency. If not installed, is_available() returns
    False and operations raise PyAVNotAvailableError with install instructions.
    """

    def __init__(self) -> None:
        """Initialize and check if PyAV is available."""
        self._available: bool | None = None

    # ------------------------------------------------------------------
    # Availability check (pattern from vtracer_cli.py)
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """
        Check if the av (PyAV) Python package is installed.

        Returns:
            True if av can be imported, False otherwise.
        """
        if self._available is None:
            try:
                import av  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def _require_available(self) -> None:
        """Raise PyAVNotAvailableError if av is not installed."""
        if not self.is_available():
            raise PyAVNotAvailableError(
                "PyAV (av) is not installed. Install via: pip3 install av\n"
                "PyAV is an optional dependency for video/audio processing."
            )

    # ------------------------------------------------------------------
    # Input validation helpers (pattern from inkscape_cli.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _require_file(path: str) -> None:
        """Raise PyAVError if the file does not exist."""
        if not Path(path).exists():
            raise PyAVError(f"Input file not found: {path}")

    @staticmethod
    def _ensure_dir(path: str) -> None:
        """Ensure the parent directory of path exists."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_video_codec(codec: str) -> str:
        """Resolve a friendly codec name to a libav codec ID."""
        key = codec.lower().strip()
        if key in VIDEO_CODEC_MAP:
            return VIDEO_CODEC_MAP[key]
        # Allow raw libav codec names to pass through
        return key

    @staticmethod
    def _resolve_audio_codec(codec: str) -> str:
        """Resolve a friendly audio codec name to a libav codec ID."""
        key = codec.lower().strip()
        if key in AUDIO_CODEC_MAP:
            return AUDIO_CODEC_MAP[key]
        return key

    @staticmethod
    def _resolve_resolution(resolution: str | tuple[int, int] | None) -> tuple[int, int] | None:
        """Resolve a resolution string like '1080p' to (width, height)."""
        if resolution is None:
            return None
        if isinstance(resolution, tuple):
            return resolution
        key = str(resolution).lower().strip()
        if key in RESOLUTION_MAP:
            return RESOLUTION_MAP[key]
        # Try parsing WxH format
        if "x" in key:
            parts = key.split("x")
            if len(parts) == 2:
                try:
                    return (int(parts[0]), int(parts[1]))
                except ValueError:
                    pass
        raise PyAVError(
            f"Unknown resolution: {resolution}. "
            f"Supported: {', '.join(sorted(RESOLUTION_MAP.keys()))} or WxH format."
        )

    # ------------------------------------------------------------------
    # Media inspection
    # ------------------------------------------------------------------

    def get_media_info(self, input_path: str) -> dict[str, Any]:
        """
        Get detailed media information for a file.

        Returns a dict structured for provenance logging with keys:
          - duration: float (seconds)
          - video_codec: str or None
          - audio_codec: str or None
          - width: int or None
          - height: int or None
          - fps: float or None
          - video_bitrate: int or None (bits/sec)
          - audio_bitrate: int or None (bits/sec)
          - audio_sample_rate: int or None
          - audio_channels: int or None
          - format: str (container format name)
          - file_size: int (bytes)
          - streams: list of stream info dicts

        Args:
            input_path: Path to the media file.

        Returns:
            Dict with media metadata.

        Raises:
            PyAVNotAvailableError: If av is not installed.
            PyAVError: If the file cannot be opened or inspected.
        """
        self._require_available()
        import av

        input_path = os.path.abspath(input_path)
        self._require_file(input_path)

        try:
            container = av.open(input_path)
        except av.error.FileNotFoundError as exc:
            raise PyAVError(f"File not found: {input_path}") from exc
        except av.error.InvalidDataError as exc:
            raise PyAVError(f"Invalid media file: {input_path}: {exc}") from exc
        except Exception as exc:
            raise PyAVError(f"Cannot open media file: {input_path}: {exc}") from exc

        try:
            info: dict[str, Any] = {
                "duration": float(container.duration / av.time_base) if container.duration else 0.0,
                "video_codec": None,
                "audio_codec": None,
                "width": None,
                "height": None,
                "fps": None,
                "video_bitrate": None,
                "audio_bitrate": None,
                "audio_sample_rate": None,
                "audio_channels": None,
                "format": container.format.name if container.format else "unknown",
                "file_size": Path(input_path).stat().st_size,
                "streams": [],
            }

            for stream in container.streams:
                stream_info: dict[str, Any] = {
                    "type": stream.type,
                    "codec": stream.codec_context.name if stream.codec_context else "unknown",
                    "index": stream.index,
                }

                if stream.type == "video":
                    info["video_codec"] = stream.codec_context.name
                    info["width"] = stream.codec_context.width
                    info["height"] = stream.codec_context.height
                    if stream.average_rate:
                        info["fps"] = float(stream.average_rate)
                    if stream.codec_context.bit_rate:
                        info["video_bitrate"] = stream.codec_context.bit_rate
                    stream_info["width"] = stream.codec_context.width
                    stream_info["height"] = stream.codec_context.height
                    stream_info["fps"] = info["fps"]
                    stream_info["bitrate"] = info["video_bitrate"]

                elif stream.type == "audio":
                    info["audio_codec"] = stream.codec_context.name
                    if stream.codec_context.sample_rate:
                        info["audio_sample_rate"] = stream.codec_context.sample_rate
                    if stream.codec_context.channels:
                        info["audio_channels"] = stream.codec_context.channels
                    if stream.codec_context.bit_rate:
                        info["audio_bitrate"] = stream.codec_context.bit_rate
                    stream_info["sample_rate"] = info["audio_sample_rate"]
                    stream_info["channels"] = info["audio_channels"]
                    stream_info["bitrate"] = info["audio_bitrate"]

                info["streams"].append(stream_info)

        finally:
            container.close()

        return info

    def get_duration(self, input_path: str) -> float:
        """
        Get the duration of a media file in seconds.

        Args:
            input_path: Path to the media file.

        Returns:
            Duration in seconds as a float.

        Raises:
            PyAVNotAvailableError: If av is not installed.
            PyAVError: If the file cannot be opened.
        """
        info = self.get_media_info(input_path)
        return info["duration"]

    # ------------------------------------------------------------------
    # Transcoding
    # ------------------------------------------------------------------

    def transcode(
        self,
        input_path: str,
        output_path: str,
        codec: str = "h264",
        resolution: str | tuple[int, int] | None = None,
        bitrate: str | int | None = None,
        fps: int | None = None,
        audio_codec: str = "aac",
        crf: int | None = None,
        preset: str = "medium",
    ) -> dict[str, Any]:
        """
        Transcode a video file to a different format/codec/resolution.

        Args:
            input_path: Path to the source video.
            output_path: Path for the output file.
            codec: Video codec name (h264, h265, vp9, av1, prores, copy).
            resolution: Target resolution ('1080p', '4k', or (width, height)).
                None preserves original resolution.
            bitrate: Target video bitrate (e.g., '5M', 5000000, or None for CRF).
            fps: Target frame rate. None preserves original.
            audio_codec: Audio codec (aac, mp3, opus, flac, copy, none).
            crf: Constant Rate Factor for quality-based encoding. Overrides bitrate.
            preset: Encoding speed preset (ultrafast → veryslow).

        Returns:
            Dict with keys:
              - output_path: str, absolute path to transcoded file
              - duration: float, output duration in seconds
              - video_codec: str, codec used
              - audio_codec: str, audio codec used
              - width: int, output width
              - height: int, output height
              - file_size: int, output file size in bytes
              - transcode_time_ms: int, wall-clock time in milliseconds

        Raises:
            PyAVNotAvailableError: If av is not installed.
            TranscodeError: If transcoding fails.
        """
        self._require_available()
        import av

        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        self._require_file(input_path)
        self._ensure_dir(output_path)

        resolved_codec = self._resolve_video_codec(codec)
        resolved_audio = self._resolve_audio_codec(audio_codec)
        target_res = self._resolve_resolution(resolution)

        if preset not in SPEED_PRESETS:
            raise TranscodeError(
                f"Unknown preset: {preset}. "
                f"Valid: {', '.join(SPEED_PRESETS)}"
            )

        start_time = time.monotonic()

        try:
            in_container = av.open(input_path)
        except Exception as exc:
            raise TranscodeError(f"Cannot open input: {input_path}: {exc}") from exc

        try:
            out_container = av.open(output_path, mode="w")
        except Exception as exc:
            in_container.close()
            raise TranscodeError(f"Cannot create output: {output_path}: {exc}") from exc

        try:
            # Find input streams
            in_video = None
            in_audio = None
            for stream in in_container.streams:
                if stream.type == "video" and in_video is None:
                    in_video = stream
                elif stream.type == "audio" and in_audio is None:
                    in_audio = stream

            if in_video is None:
                raise TranscodeError(f"No video stream found in: {input_path}")

            # Determine output dimensions
            out_width = in_video.codec_context.width
            out_height = in_video.codec_context.height
            if target_res:
                out_width, out_height = target_res

            # Create output video stream
            if resolved_codec == "copy":
                out_video_stream = out_container.add_stream(template=in_video)
            else:
                out_video_stream = out_container.add_stream(resolved_codec)
                out_video_stream.width = out_width
                out_video_stream.height = out_height
                out_video_stream.pix_fmt = "yuv420p"

                # Frame rate
                if fps:
                    out_video_stream.rate = fps
                elif in_video.average_rate:
                    out_video_stream.rate = in_video.average_rate
                else:
                    out_video_stream.rate = 24

                # Quality settings
                if crf is not None:
                    out_video_stream.options = {"crf": str(crf), "preset": preset}
                elif bitrate:
                    parsed_bitrate = self._parse_bitrate(bitrate)
                    out_video_stream.bit_rate = parsed_bitrate
                    out_video_stream.options = {"preset": preset}
                else:
                    # Use default CRF for codec
                    default_crf = CRF_PRESETS.get(resolved_codec, {}).get("medium", 23)
                    out_video_stream.options = {"crf": str(default_crf), "preset": preset}

            # Create output audio stream
            out_audio_stream = None
            if in_audio and resolved_audio != "none":
                if resolved_audio == "copy":
                    out_audio_stream = out_container.add_stream(template=in_audio)
                else:
                    out_audio_stream = out_container.add_stream(resolved_audio)
                    out_audio_stream.rate = in_audio.codec_context.sample_rate or 44100
                    if hasattr(in_audio.codec_context, 'layout') and in_audio.codec_context.layout:
                        out_audio_stream.layout = in_audio.codec_context.layout
                    else:
                        out_audio_stream.layout = "stereo"

            # Transcode frames
            for packet in in_container.demux():
                if packet.stream.type == "video":
                    if resolved_codec == "copy":
                        packet.stream = out_video_stream
                        out_container.mux(packet)
                    else:
                        for frame in packet.decode():
                            # Resize if needed
                            if (frame.width != out_width or frame.height != out_height):
                                frame = frame.reformat(
                                    width=out_width,
                                    height=out_height,
                                    format="yuv420p",
                                )
                            elif frame.format.name != "yuv420p":
                                frame = frame.reformat(format="yuv420p")

                            for out_packet in out_video_stream.encode(frame):
                                out_container.mux(out_packet)

                elif packet.stream.type == "audio" and out_audio_stream:
                    if resolved_audio == "copy":
                        packet.stream = out_audio_stream
                        out_container.mux(packet)
                    else:
                        for frame in packet.decode():
                            for out_packet in out_audio_stream.encode(frame):
                                out_container.mux(out_packet)

            # Flush encoders
            if resolved_codec != "copy":
                for out_packet in out_video_stream.encode():
                    out_container.mux(out_packet)
            if out_audio_stream and resolved_audio != "copy":
                for out_packet in out_audio_stream.encode():
                    out_container.mux(out_packet)

        except TranscodeError:
            raise
        except Exception as exc:
            raise TranscodeError(f"Transcode failed: {exc}") from exc
        finally:
            out_container.close()
            in_container.close()

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if not Path(output_path).exists():
            raise TranscodeError(f"Transcode produced no output at: {output_path}")

        # Gather output info
        out_info = self.get_media_info(output_path)

        return {
            "output_path": os.path.abspath(output_path),
            "duration": out_info["duration"],
            "video_codec": out_info["video_codec"],
            "audio_codec": out_info["audio_codec"],
            "width": out_info["width"],
            "height": out_info["height"],
            "file_size": out_info["file_size"],
            "transcode_time_ms": elapsed_ms,
        }

    # ------------------------------------------------------------------
    # Frame extraction
    # ------------------------------------------------------------------

    def extract_frames(
        self,
        input_path: str,
        timestamps: list[float],
        output_dir: str,
        format: str = "png",
    ) -> list[dict[str, Any]]:
        """
        Extract frames at specific timestamps.

        Args:
            input_path: Path to the video file.
            timestamps: List of timestamps in seconds to extract.
            output_dir: Directory to write extracted frames.
            format: Image format for output (png, jpg).

        Returns:
            List of dicts, one per extracted frame:
              - path: str, absolute path to the frame image
              - timestamp: float, the requested timestamp
              - actual_timestamp: float, the actual decoded timestamp
              - width: int
              - height: int

        Raises:
            PyAVNotAvailableError: If av is not installed.
            PyAVError: If extraction fails.
        """
        self._require_available()
        import av

        input_path = os.path.abspath(input_path)
        output_dir = os.path.abspath(output_dir)
        self._require_file(input_path)
        os.makedirs(output_dir, exist_ok=True)

        if not timestamps:
            raise PyAVError("timestamps list cannot be empty")

        fmt = format.lower().strip()
        if fmt not in ("png", "jpg", "jpeg"):
            raise PyAVError(f"Unsupported frame format: {fmt}. Use png or jpg.")

        results: list[dict[str, Any]] = []
        sorted_ts = sorted(timestamps)

        try:
            container = av.open(input_path)
        except Exception as exc:
            raise PyAVError(f"Cannot open video: {input_path}: {exc}") from exc

        try:
            video_stream = None
            for stream in container.streams:
                if stream.type == "video":
                    video_stream = stream
                    break

            if video_stream is None:
                raise PyAVError(f"No video stream in: {input_path}")

            # Extract each requested timestamp
            for idx, ts in enumerate(sorted_ts):
                # Seek to just before the requested timestamp
                target_pts = int(ts / video_stream.time_base) if video_stream.time_base else int(ts * 1000000)
                container.seek(target_pts, stream=video_stream)

                # Decode the first frame after seek
                for frame in container.decode(video=0):
                    actual_ts = float(frame.pts * video_stream.time_base) if frame.pts is not None else ts

                    # Build output filename
                    ext = "jpg" if fmt in ("jpg", "jpeg") else "png"
                    frame_name = f"frame_{idx:04d}_{ts:.3f}s.{ext}"
                    frame_path = os.path.join(output_dir, frame_name)

                    # Save frame as image
                    img = frame.to_image()
                    img.save(frame_path)

                    results.append({
                        "path": os.path.abspath(frame_path),
                        "timestamp": ts,
                        "actual_timestamp": actual_ts,
                        "width": frame.width,
                        "height": frame.height,
                    })
                    break  # Only need first frame after seek

        except PyAVError:
            raise
        except Exception as exc:
            raise PyAVError(f"Frame extraction failed: {exc}") from exc
        finally:
            container.close()

        return results

    def extract_frame_at(
        self,
        input_path: str,
        timestamp: float,
        output_path: str,
    ) -> str:
        """
        Extract a single frame at a specific timestamp.

        Convenience wrapper around extract_frames for single-frame extraction.

        Args:
            input_path: Path to the video file.
            timestamp: Timestamp in seconds.
            output_path: Path for the output image.

        Returns:
            Absolute path to the extracted frame.

        Raises:
            PyAVNotAvailableError: If av is not installed.
            PyAVError: If extraction fails.
        """
        output_path = os.path.abspath(output_path)
        self._ensure_dir(output_path)

        ext = Path(output_path).suffix.lstrip(".").lower()
        if ext in ("jpg", "jpeg"):
            fmt = "jpg"
        else:
            fmt = "png"

        # Use a temp dir, then move the file to the target path
        output_dir = str(Path(output_path).parent)
        results = self.extract_frames(input_path, [timestamp], output_dir, fmt)

        if not results:
            raise PyAVError(f"No frame extracted at timestamp {timestamp}s")

        # Rename the extracted frame to the requested output path
        extracted = results[0]["path"]
        if extracted != output_path:
            os.replace(extracted, output_path)

        return os.path.abspath(output_path)

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize(
        self,
        input_path: str,
        output_path: str,
        width: int | None = None,
        height: int | None = None,
        maintain_aspect: bool = True,
    ) -> dict[str, Any]:
        """
        Resize a video to target dimensions.

        If maintain_aspect is True and only one dimension is specified,
        the other is calculated to preserve the aspect ratio.

        Args:
            input_path: Path to the source video.
            output_path: Path for the resized output.
            width: Target width in pixels. None to auto-calculate.
            height: Target height in pixels. None to auto-calculate.
            maintain_aspect: If True, preserve aspect ratio.

        Returns:
            Dict with output_path, width, height, duration, file_size.

        Raises:
            PyAVNotAvailableError: If av is not installed.
            PyAVError: If resize fails.
        """
        self._require_available()

        if width is None and height is None:
            raise PyAVError("At least one of width or height must be specified")

        # Get source dimensions to calculate aspect ratio
        info = self.get_media_info(input_path)
        src_width = info["width"]
        src_height = info["height"]

        if src_width is None or src_height is None:
            raise PyAVError(f"Cannot determine dimensions of: {input_path}")

        if maintain_aspect:
            aspect = src_width / src_height
            if width is not None and height is None:
                height = int(width / aspect)
                # Ensure even dimensions for video encoding
                height = height + (height % 2)
            elif height is not None and width is None:
                width = int(height * aspect)
                width = width + (width % 2)
        else:
            if width is None:
                width = src_width
            if height is None:
                height = src_height

        # Ensure even dimensions
        width = width + (width % 2)
        height = height + (height % 2)

        result = self.transcode(
            input_path=input_path,
            output_path=output_path,
            resolution=(width, height),
        )

        return {
            "output_path": result["output_path"],
            "width": result["width"],
            "height": result["height"],
            "duration": result["duration"],
            "file_size": result["file_size"],
        }

    # ------------------------------------------------------------------
    # Audio extraction
    # ------------------------------------------------------------------

    def extract_audio(
        self,
        input_path: str,
        output_path: str,
        codec: str = "aac",
    ) -> dict[str, Any]:
        """
        Extract the audio track from a video file.

        Args:
            input_path: Path to the source video.
            output_path: Path for the audio output.
            codec: Audio codec (aac, mp3, opus, flac, copy).

        Returns:
            Dict with keys:
              - output_path: str, absolute path to audio file
              - codec: str, audio codec used
              - duration: float, duration in seconds
              - sample_rate: int or None
              - channels: int or None
              - file_size: int

        Raises:
            PyAVNotAvailableError: If av is not installed.
            PyAVError: If extraction fails.
        """
        self._require_available()
        import av

        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        self._require_file(input_path)
        self._ensure_dir(output_path)

        resolved_codec = self._resolve_audio_codec(codec)

        try:
            in_container = av.open(input_path)
        except Exception as exc:
            raise PyAVError(f"Cannot open input: {input_path}: {exc}") from exc

        try:
            # Find audio stream
            in_audio = None
            for stream in in_container.streams:
                if stream.type == "audio":
                    in_audio = stream
                    break

            if in_audio is None:
                raise PyAVError(f"No audio stream found in: {input_path}")

            out_container = av.open(output_path, mode="w")

            try:
                if resolved_codec == "copy":
                    out_audio = out_container.add_stream(template=in_audio)
                else:
                    out_audio = out_container.add_stream(resolved_codec)
                    out_audio.rate = in_audio.codec_context.sample_rate or 44100
                    if hasattr(in_audio.codec_context, 'layout') and in_audio.codec_context.layout:
                        out_audio.layout = in_audio.codec_context.layout
                    else:
                        out_audio.layout = "stereo"

                for packet in in_container.demux(in_audio):
                    if resolved_codec == "copy":
                        packet.stream = out_audio
                        out_container.mux(packet)
                    else:
                        for frame in packet.decode():
                            for out_packet in out_audio.encode(frame):
                                out_container.mux(out_packet)

                # Flush encoder
                if resolved_codec != "copy":
                    for out_packet in out_audio.encode():
                        out_container.mux(out_packet)

            finally:
                out_container.close()

        except PyAVError:
            raise
        except Exception as exc:
            raise PyAVError(f"Audio extraction failed: {exc}") from exc
        finally:
            in_container.close()

        if not Path(output_path).exists():
            raise PyAVError(f"Audio extraction produced no output at: {output_path}")

        out_info = self.get_media_info(output_path)

        return {
            "output_path": os.path.abspath(output_path),
            "codec": out_info.get("audio_codec", resolved_codec),
            "duration": out_info["duration"],
            "sample_rate": out_info.get("audio_sample_rate"),
            "channels": out_info.get("audio_channels"),
            "file_size": out_info["file_size"],
        }

    # ------------------------------------------------------------------
    # Thumbnail generation
    # ------------------------------------------------------------------

    def generate_thumbnail(
        self,
        input_path: str,
        output_path: str,
        timestamp: float | None = None,
        size: tuple[int, int] | str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a poster/thumbnail frame from a video.

        If timestamp is None, extracts a frame at 10% of the video duration
        (avoids black intro frames).

        Args:
            input_path: Path to the source video.
            output_path: Path for the thumbnail image.
            timestamp: Timestamp in seconds. None for auto-selection.
            size: Thumbnail size as (width, height) or resolution string.
                None preserves original video dimensions.

        Returns:
            Dict with keys:
              - output_path: str, absolute path to thumbnail
              - timestamp: float, the timestamp used
              - width: int
              - height: int
              - file_size: int

        Raises:
            PyAVNotAvailableError: If av is not installed.
            PyAVError: If generation fails.
        """
        self._require_available()

        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        self._require_file(input_path)
        self._ensure_dir(output_path)

        # Auto-select timestamp if not provided
        if timestamp is None:
            duration = self.get_duration(input_path)
            timestamp = duration * 0.1 if duration > 0 else 0.0

        # Extract the frame
        self.extract_frame_at(input_path, timestamp, output_path)

        # Resize if requested
        if size is not None:
            target_res = self._resolve_resolution(size)
            if target_res:
                from PIL import Image
                img = Image.open(output_path)
                img = img.resize(target_res, Image.LANCZOS)
                img.save(output_path)

        stat = Path(output_path).stat()
        # Read dimensions from the saved image
        from PIL import Image
        img = Image.open(output_path)
        w, h = img.size
        img.close()

        return {
            "output_path": os.path.abspath(output_path),
            "timestamp": timestamp,
            "width": w,
            "height": h,
            "file_size": stat.st_size,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_bitrate(bitrate: str | int) -> int:
        """
        Parse a bitrate value to bits/sec.

        Supports formats: '5M', '5000k', '5000000', 5000000
        """
        if isinstance(bitrate, int):
            return bitrate

        raw = str(bitrate).strip().lower()
        if raw.endswith("m"):
            return int(float(raw[:-1]) * 1_000_000)
        elif raw.endswith("k"):
            return int(float(raw[:-1]) * 1_000)
        else:
            try:
                return int(raw)
            except ValueError:
                raise TranscodeError(
                    f"Cannot parse bitrate: {bitrate}. "
                    "Use formats like '5M', '5000k', or 5000000."
                )


# ---------------------------------------------------------------------------
# Module-level convenience: singleton instance
# ---------------------------------------------------------------------------

_default_instance: PyAVProcessor | None = None


def get_pyav_processor() -> PyAVProcessor:
    """
    Get or create the module-level PyAVProcessor singleton.

    Returns:
        A PyAVProcessor instance (may or may not be available depending
        on whether PyAV is installed).
    """
    global _default_instance
    if _default_instance is None:
        _default_instance = PyAVProcessor()
    return _default_instance
