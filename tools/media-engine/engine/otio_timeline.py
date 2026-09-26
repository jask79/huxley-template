"""
OTIO Timeline Builder for the Media Workflow Engine.

Provides a Python interface for building, exporting, and importing timelines
using OpenTimelineIO (OTIO). Supports lossless OTIO JSON, CMX 3600 EDL, and
FCPXML export for interchange with DaVinci Resolve, Final Cut Pro, Premiere,
and other NLEs.

OpenTimelineIO is an optional dependency -- the rest of the engine works
without it. When available, this module bridges Media Engine generated assets
(images, video clips) into structured timelines that NLEs can import.

Install: pip3 install opentimelineio

Duration Detection:
  When building timelines from generated assets, clip durations are auto-detected
  using PyAV (if available). If PyAV is not installed, sensible defaults are used
  (5s for images, 10s for video). This graceful fallback ensures the module works
  in minimal environments.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class OTIOError(Exception):
    """Base error for OTIO timeline operations."""


class OTIONotAvailableError(OTIOError):
    """Raised when opentimelineio is not installed."""


class TimelineBuildError(OTIOError):
    """Raised when timeline construction fails."""


class TimelineExportError(OTIOError):
    """Raised when timeline export fails."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ClipSpec:
    """Specification for a single clip in the timeline.

    Attributes:
        path: Absolute or relative path to the media file.
        name: Display name for the clip. Defaults to the filename stem.
        in_point: Start time in seconds within the source media.
        out_point: End time in seconds within the source media.
            None means use full duration.
        track: Track index (0-based). Multiple tracks allow compositing.
        transition_in: Transition type before this clip.
            Supported: "dissolve", "wipe", "fade_in", "fade_out", None.
        transition_duration: Duration of the transition in seconds.
        effects: List of effect names (metadata only -- NLE applies them).
    """

    path: str
    name: str = ""
    in_point: float = 0.0
    out_point: float | None = None
    track: int = 0
    transition_in: str | None = None
    transition_duration: float = 1.0
    effects: list[str] | None = None

    def __post_init__(self) -> None:
        if not self.name:
            self.name = Path(self.path).stem
        if self.effects is None:
            self.effects = []


@dataclass
class MarkerSpec:
    """Specification for a timeline marker.

    Attributes:
        time: Position in seconds from timeline start.
        name: Marker label.
        color: Marker color. Supported: RED, GREEN, BLUE, YELLOW,
            CYAN, MAGENTA, ORANGE, PINK, PURPLE, WHITE, BLACK.
        comment: Optional annotation text.
    """

    time: float
    name: str
    color: str = "GREEN"
    comment: str = ""


# ---------------------------------------------------------------------------
# Default durations for media types without PyAV detection
# ---------------------------------------------------------------------------

_DEFAULT_IMAGE_DURATION_S = 5.0
_DEFAULT_VIDEO_DURATION_S = 10.0

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif", ".bmp", ".gif"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mxf"}

# Transition type mapping
_TRANSITION_TYPES = {
    "dissolve": "SMPTE_Dissolve",
    "wipe": "Custom",
    "fade_in": "SMPTE_Dissolve",
    "fade_out": "SMPTE_Dissolve",
    "cut": None,
}

# Marker color mapping to OTIO MarkerColor enum names
_MARKER_COLORS = {
    "RED", "GREEN", "BLUE", "YELLOW", "CYAN", "MAGENTA",
    "ORANGE", "PINK", "PURPLE", "WHITE", "BLACK",
}


# ---------------------------------------------------------------------------
# Duration detection helpers
# ---------------------------------------------------------------------------


def _detect_duration_pyav(path: str) -> float | None:
    """
    Detect media duration in seconds using PyAV.

    Returns None if PyAV is not installed or detection fails.
    """
    try:
        import av
    except ImportError:
        return None

    try:
        container = av.open(path)
        try:
            if container.duration and container.duration > 0:
                return float(container.duration * av.time_base)
            # Fallback: check individual streams
            for stream in container.streams:
                if stream.duration and stream.time_base:
                    return float(stream.duration * stream.time_base)
        finally:
            container.close()
    except Exception:
        pass

    return None


def _detect_duration(path: str) -> float:
    """
    Detect media duration with PyAV fallback to defaults.

    For images, always returns the default still-image duration.
    For video, tries PyAV first, then falls back to default.
    """
    ext = Path(path).suffix.lower()

    if ext in _IMAGE_EXTENSIONS:
        return _DEFAULT_IMAGE_DURATION_S

    if ext in _VIDEO_EXTENSIONS:
        detected = _detect_duration_pyav(path)
        if detected is not None and detected > 0:
            return detected
        return _DEFAULT_VIDEO_DURATION_S

    # Unknown extension -- try PyAV, then default to video duration
    detected = _detect_duration_pyav(path)
    if detected is not None and detected > 0:
        return detected
    return _DEFAULT_VIDEO_DURATION_S


# ---------------------------------------------------------------------------
# OTIOTimeline class
# ---------------------------------------------------------------------------


class OTIOTimeline:
    """
    Builder for OpenTimelineIO timelines.

    Wraps the opentimelineio library with a high-level interface designed for
    the Media Engine's asset pipeline. Supports multi-track video timelines
    with transitions, markers, and export to OTIO JSON, CMX 3600 EDL, and
    FCPXML.

    OTIO is an optional dependency. Use ``is_available()`` to check before
    calling any build/export methods.
    """

    def __init__(self) -> None:
        """Initialize the timeline builder."""
        self._otio = None
        self._available: bool | None = None

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """
        Check if opentimelineio is importable.

        Returns:
            True if the ``opentimelineio`` package is installed.
        """
        if self._available is None:
            try:
                import opentimelineio  # noqa: F401
                self._otio = opentimelineio
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def _require_available(self) -> None:
        """Raise OTIONotAvailableError if OTIO is not installed."""
        if not self.is_available():
            raise OTIONotAvailableError(
                "opentimelineio is not installed. "
                "Install via: pip3 install opentimelineio\n"
                "OTIO is an optional dependency for timeline building."
            )

    def _otio_module(self):
        """Return the cached opentimelineio module."""
        self._require_available()
        return self._otio

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------

    def _rational_time(self, seconds: float, fps: float):
        """Create a RationalTime from seconds and fps."""
        otio = self._otio_module()
        frame_count = round(seconds * fps)
        return otio.opentime.RationalTime(frame_count, fps)

    def _time_range(self, start_seconds: float, duration_seconds: float, fps: float):
        """Create a TimeRange from start/duration in seconds."""
        otio = self._otio_module()
        return otio.opentime.TimeRange(
            start_time=self._rational_time(start_seconds, fps),
            duration=self._rational_time(duration_seconds, fps),
        )

    # ------------------------------------------------------------------
    # Timeline creation
    # ------------------------------------------------------------------

    def create_timeline(
        self,
        name: str,
        fps: float = 24.0,
        clips: list[ClipSpec] | None = None,
        markers: list[MarkerSpec] | None = None,
    ):
        """
        Create a new OTIO timeline with optional clips and markers.

        Args:
            name: Timeline name.
            fps: Frame rate (default 24.0).
            clips: List of ClipSpec objects to add sequentially.
            markers: List of MarkerSpec objects to add.

        Returns:
            An opentimelineio.schema.Timeline object.

        Raises:
            OTIONotAvailableError: If OTIO is not installed.
            TimelineBuildError: If timeline construction fails.
        """
        otio = self._otio_module()

        try:
            timeline = otio.schema.Timeline(name=name)
            timeline.metadata["fps"] = fps
            timeline.metadata["created_by"] = "Huxley Media Engine"
            timeline.metadata["created_at"] = datetime.now().isoformat()

            # Determine how many video tracks we need
            max_track = 0
            if clips:
                max_track = max(c.track for c in clips)

            # Create video tracks
            for i in range(max_track + 1):
                track = otio.schema.Track(
                    name=f"V{i + 1}",
                    kind=otio.schema.TrackKind.Video,
                )
                timeline.tracks.append(track)

            # Add clips
            if clips:
                for clip_spec in clips:
                    self.add_clip(timeline, clip_spec, fps=fps)

            # Add markers
            if markers:
                for marker_spec in markers:
                    self.add_marker(timeline, marker_spec, fps=fps)

            return timeline

        except OTIOError:
            raise
        except Exception as exc:
            raise TimelineBuildError(
                f"Failed to create timeline '{name}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Clip management
    # ------------------------------------------------------------------

    def add_clip(self, timeline, clip_spec: ClipSpec, fps: float = 24.0) -> None:
        """
        Add a clip to an existing timeline.

        Args:
            timeline: OTIO Timeline object.
            clip_spec: ClipSpec with path, timing, and track info.
            fps: Frame rate for time calculations.

        Raises:
            TimelineBuildError: If the clip cannot be added.
        """
        otio = self._otio_module()

        try:
            # Resolve the media file path to absolute
            media_path = os.path.abspath(clip_spec.path)
            file_url = f"file://{media_path}"

            # Determine clip duration
            if clip_spec.out_point is not None:
                clip_duration = clip_spec.out_point - clip_spec.in_point
            elif os.path.exists(media_path):
                full_duration = _detect_duration(media_path)
                clip_duration = full_duration - clip_spec.in_point
            else:
                # File doesn't exist yet (dry-run or planned)
                clip_duration = _DEFAULT_VIDEO_DURATION_S - clip_spec.in_point

            if clip_duration <= 0:
                raise TimelineBuildError(
                    f"Clip '{clip_spec.name}' has non-positive duration: "
                    f"{clip_duration}s (in={clip_spec.in_point}, out={clip_spec.out_point})"
                )

            # Build the OTIO clip
            source_range = self._time_range(clip_spec.in_point, clip_duration, fps)

            media_ref = otio.schema.ExternalReference(
                target_url=file_url,
                available_range=self._time_range(0, clip_duration + clip_spec.in_point, fps),
            )

            clip = otio.schema.Clip(
                name=clip_spec.name,
                source_range=source_range,
                media_reference=media_ref,
            )

            # Store effect metadata on the clip
            if clip_spec.effects:
                clip.metadata["effects"] = clip_spec.effects

            # Ensure track exists
            while len(timeline.tracks) <= clip_spec.track:
                new_track = otio.schema.Track(
                    name=f"V{len(timeline.tracks) + 1}",
                    kind=otio.schema.TrackKind.Video,
                )
                timeline.tracks.append(new_track)

            target_track = timeline.tracks[clip_spec.track]

            # Add transition before clip if specified
            if clip_spec.transition_in and clip_spec.transition_in != "cut":
                self.add_transition(
                    timeline,
                    track_index=clip_spec.track,
                    position=len(target_track),
                    transition_type=clip_spec.transition_in,
                    duration=clip_spec.transition_duration,
                    fps=fps,
                )

            target_track.append(clip)

        except OTIOError:
            raise
        except Exception as exc:
            raise TimelineBuildError(
                f"Failed to add clip '{clip_spec.name}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def add_transition(
        self,
        timeline,
        track_index: int,
        position: int,
        transition_type: str,
        duration: float,
        fps: float = 24.0,
    ) -> None:
        """
        Insert a transition at the given position in a track.

        Args:
            timeline: OTIO Timeline object.
            track_index: Index of the video track.
            position: Position index in the track to insert.
            transition_type: One of "dissolve", "wipe", "fade_in", "fade_out".
            duration: Transition duration in seconds.
            fps: Frame rate.

        Raises:
            TimelineBuildError: If the transition cannot be inserted.
        """
        otio = self._otio_module()

        try:
            if transition_type not in _TRANSITION_TYPES:
                raise TimelineBuildError(
                    f"Unknown transition type: '{transition_type}'. "
                    f"Supported: {', '.join(sorted(_TRANSITION_TYPES.keys()))}"
                )

            otio_type = _TRANSITION_TYPES[transition_type]
            if otio_type is None:
                return  # "cut" = no transition

            half_duration = duration / 2.0
            in_offset = self._rational_time(half_duration, fps)
            out_offset = self._rational_time(half_duration, fps)

            transition = otio.schema.Transition(
                name=transition_type,
                transition_type=otio_type,
                in_offset=in_offset,
                out_offset=out_offset,
            )

            while len(timeline.tracks) <= track_index:
                new_track = otio.schema.Track(
                    name=f"V{len(timeline.tracks) + 1}",
                    kind=otio.schema.TrackKind.Video,
                )
                timeline.tracks.append(new_track)

            track = timeline.tracks[track_index]

            # Clamp position to valid range
            insert_pos = min(position, len(track))
            track.insert(insert_pos, transition)

        except OTIOError:
            raise
        except Exception as exc:
            raise TimelineBuildError(
                f"Failed to add transition '{transition_type}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Markers
    # ------------------------------------------------------------------

    def add_marker(
        self,
        timeline,
        marker_spec: MarkerSpec,
        fps: float = 24.0,
    ) -> None:
        """
        Add a marker to the timeline.

        Markers are added to the first video track (V1). If no tracks exist,
        one is created.

        Args:
            timeline: OTIO Timeline object.
            marker_spec: MarkerSpec with time, name, color, comment.
            fps: Frame rate.

        Raises:
            TimelineBuildError: If the marker cannot be added.
        """
        otio = self._otio_module()

        try:
            # Resolve color
            color_upper = marker_spec.color.upper()
            if color_upper not in _MARKER_COLORS:
                color_upper = "GREEN"

            otio_color = getattr(otio.schema.MarkerColor, color_upper, otio.schema.MarkerColor.GREEN)

            marker = otio.schema.Marker(
                name=marker_spec.name,
                marked_range=otio.opentime.TimeRange(
                    start_time=self._rational_time(marker_spec.time, fps),
                    duration=self._rational_time(0, fps),
                ),
                color=otio_color,
                comment=marker_spec.comment,
            )

            # Add to first track or timeline-level
            if timeline.tracks:
                timeline.tracks[0].markers.append(marker)
            else:
                # Create a track to hold the marker
                track = otio.schema.Track(
                    name="V1",
                    kind=otio.schema.TrackKind.Video,
                )
                track.markers.append(marker)
                timeline.tracks.append(track)

        except OTIOError:
            raise
        except Exception as exc:
            raise TimelineBuildError(
                f"Failed to add marker '{marker_spec.name}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Export methods
    # ------------------------------------------------------------------

    def export_otio(self, timeline, output_path: str) -> str:
        """
        Export timeline as lossless OTIO JSON.

        Args:
            timeline: OTIO Timeline object.
            output_path: Output file path (should end in .otio).

        Returns:
            Absolute path to the exported file.

        Raises:
            TimelineExportError: If export fails.
        """
        otio = self._otio_module()

        try:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)

            otio.adapters.write_to_file(timeline, str(out))
            return os.path.abspath(str(out))

        except Exception as exc:
            raise TimelineExportError(
                f"Failed to export OTIO JSON to '{output_path}': {exc}"
            ) from exc

    def export_edl(self, timeline, output_path: str, fps: float = 24.0) -> str:
        """
        Export timeline as CMX 3600 EDL.

        The built-in OTIO adapters for EDL are not included in the minimal
        opentimelineio package (0.18+). This method generates CMX 3600 EDL
        directly from the OTIO timeline structure.

        Args:
            timeline: OTIO Timeline object.
            output_path: Output file path (should end in .edl).
            fps: Frame rate for timecode conversion.

        Returns:
            Absolute path to the exported file.

        Raises:
            TimelineExportError: If export fails.
        """
        self._require_available()

        try:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)

            lines = [
                f"TITLE: {timeline.name}",
                f"FCM: {'DROP FRAME' if fps in (29.97, 59.94) else 'NON-DROP FRAME'}",
                "",
            ]

            event_num = 1
            record_tc = 0.0  # Running record timecode in seconds

            for track in timeline.tracks:
                for item in track:
                    otio_mod = self._otio_module()
                    if isinstance(item, otio_mod.schema.Transition):
                        # Skip transitions in EDL for simplicity
                        continue
                    if not isinstance(item, otio_mod.schema.Clip):
                        continue

                    clip = item
                    sr = clip.source_range
                    if sr is None:
                        continue

                    src_in = sr.start_time.to_seconds() if sr.start_time else 0.0
                    src_duration = sr.duration.to_seconds() if sr.duration else 0.0
                    src_out = src_in + src_duration

                    rec_in = record_tc
                    rec_out = record_tc + src_duration
                    record_tc = rec_out

                    # Get reel name from media reference
                    reel = "AX"
                    if hasattr(clip, "media_reference") and clip.media_reference:
                        ref = clip.media_reference
                        if hasattr(ref, "target_url") and ref.target_url:
                            reel_name = Path(ref.target_url.replace("file://", "")).stem
                            reel = reel_name[:8].upper() if reel_name else "AX"

                    # Format: EVENT REEL TRACK TRANSITION SRC_IN SRC_OUT REC_IN REC_OUT
                    line = (
                        f"{event_num:03d}  {reel:<8s} V     C        "
                        f"{_seconds_to_timecode(src_in, fps)} "
                        f"{_seconds_to_timecode(src_out, fps)} "
                        f"{_seconds_to_timecode(rec_in, fps)} "
                        f"{_seconds_to_timecode(rec_out, fps)}"
                    )
                    lines.append(line)

                    # Add clip name as comment
                    if clip.name:
                        lines.append(f"* FROM CLIP NAME: {clip.name}")
                    lines.append("")

                    event_num += 1

            out.write_text("\n".join(lines), encoding="utf-8")
            return os.path.abspath(str(out))

        except OTIOError:
            raise
        except Exception as exc:
            raise TimelineExportError(
                f"Failed to export EDL to '{output_path}': {exc}"
            ) from exc

    def export_fcpxml(self, timeline, output_path: str, fps: float = 24.0) -> str:
        """
        Export timeline as FCPXML (version 1.11) for DaVinci Resolve / FCP.

        Generates FCPXML directly since the OTIO FCPXML adapter is not
        included in the minimal opentimelineio package.

        Args:
            timeline: OTIO Timeline object.
            output_path: Output file path (should end in .fcpxml).
            fps: Frame rate.

        Returns:
            Absolute path to the exported file.

        Raises:
            TimelineExportError: If export fails.
        """
        self._require_available()

        try:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)

            # Determine frame duration string for FCPXML
            # FCPXML uses rational time: e.g., "100/2400s" for 24fps
            fps_int = int(round(fps))
            frame_dur_num = 100
            frame_dur_den = fps_int * 100

            # Calculate total timeline duration
            total_duration = 0.0
            for track in timeline.tracks:
                track_dur = 0.0
                for item in track:
                    otio_mod = self._otio_module()
                    if isinstance(item, otio_mod.schema.Clip) and item.source_range:
                        track_dur += item.source_range.duration.to_seconds()
                total_duration = max(total_duration, track_dur)

            total_frames = int(round(total_duration * fps))

            # Build XML tree
            fcpxml = ET.Element("fcpxml", version="1.11")

            # Resources
            resources = ET.SubElement(fcpxml, "resources")

            # Format resource
            fmt = ET.SubElement(resources, "format", {
                "id": "r1",
                "name": f"FFVideoFormat{fps_int}p",
                "frameDuration": f"{frame_dur_num}/{frame_dur_den}s",
                "width": "1920",
                "height": "1080",
            })

            # Asset resources for each clip
            asset_id = 1
            asset_map: dict[str, str] = {}  # media_url -> asset_id

            for track in timeline.tracks:
                for item in track:
                    otio_mod = self._otio_module()
                    if not isinstance(item, otio_mod.schema.Clip):
                        continue
                    ref = item.media_reference
                    if ref and hasattr(ref, "target_url") and ref.target_url:
                        url = ref.target_url
                        if url not in asset_map:
                            aid = f"r{asset_id + 1}"
                            asset_map[url] = aid
                            asset_el = ET.SubElement(resources, "asset", {
                                "id": aid,
                                "name": item.name or Path(url).stem,
                                "src": url,
                                "format": "r1",
                            })
                            if ref.available_range:
                                dur_s = ref.available_range.duration.to_seconds()
                                dur_frames = int(round(dur_s * fps))
                                asset_el.set(
                                    "duration",
                                    f"{dur_frames * frame_dur_num}/{frame_dur_den}s",
                                )
                            asset_id += 1

            # Library > Event > Project > Sequence
            library = ET.SubElement(fcpxml, "library")
            event = ET.SubElement(library, "event", name=timeline.name)
            project = ET.SubElement(event, "project", name=timeline.name)

            sequence = ET.SubElement(project, "sequence", {
                "format": "r1",
                "duration": f"{total_frames * frame_dur_num}/{frame_dur_den}s",
                "tcStart": "0s",
                "tcFormat": "NDF" if fps not in (29.97, 59.94) else "DF",
            })

            spine = ET.SubElement(sequence, "spine")

            # Add clips to spine
            for track in timeline.tracks:
                offset_s = 0.0
                for item in track:
                    otio_mod = self._otio_module()
                    if isinstance(item, otio_mod.schema.Transition):
                        continue
                    if not isinstance(item, otio_mod.schema.Clip):
                        continue

                    sr = item.source_range
                    if sr is None:
                        continue

                    dur_s = sr.duration.to_seconds()
                    dur_frames = int(round(dur_s * fps))
                    start_s = sr.start_time.to_seconds() if sr.start_time else 0.0
                    start_frames = int(round(start_s * fps))
                    offset_frames = int(round(offset_s * fps))

                    # Get asset ref
                    ref_id = "r1"
                    if item.media_reference and hasattr(item.media_reference, "target_url"):
                        url = item.media_reference.target_url
                        ref_id = asset_map.get(url, "r1")

                    clip_el = ET.SubElement(spine, "asset-clip", {
                        "name": item.name or "Untitled",
                        "ref": ref_id,
                        "duration": f"{dur_frames * frame_dur_num}/{frame_dur_den}s",
                        "start": f"{start_frames * frame_dur_num}/{frame_dur_den}s",
                        "offset": f"{offset_frames * frame_dur_num}/{frame_dur_den}s",
                        "format": "r1",
                    })

                    offset_s += dur_s

                # Only process first track for single-spine FCPXML
                break

            # Add markers
            for track in timeline.tracks:
                for marker in track.markers:
                    marker_time_s = marker.marked_range.start_time.to_seconds()
                    marker_frames = int(round(marker_time_s * fps))

                    # Find the clip that contains this marker time
                    # and add marker as child element
                    cumulative = 0.0
                    for clip_el in spine:
                        dur_attr = clip_el.get("duration", "0s")
                        dur_val = _parse_fcpxml_duration(dur_attr, fps)
                        if cumulative + dur_val >= marker_time_s:
                            local_time = marker_time_s - cumulative
                            local_frames = int(round(local_time * fps))
                            m_el = ET.SubElement(clip_el, "marker", {
                                "start": f"{local_frames * frame_dur_num}/{frame_dur_den}s",
                                "value": marker.name or "Marker",
                            })
                            if marker.comment:
                                note = ET.SubElement(m_el, "note")
                                note.text = marker.comment
                            break
                        cumulative += dur_val
                break  # markers only on first track

            # Write XML
            tree = ET.ElementTree(fcpxml)
            ET.indent(tree, space="  ")

            with open(str(out), "wb") as f:
                f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write(b'<!DOCTYPE fcpxml>\n')
                tree.write(f, encoding="utf-8", xml_declaration=False)

            return os.path.abspath(str(out))

        except OTIOError:
            raise
        except Exception as exc:
            raise TimelineExportError(
                f"Failed to export FCPXML to '{output_path}': {exc}"
            ) from exc

    def export_all(
        self,
        timeline,
        output_dir: str,
        formats: list[str] | None = None,
        fps: float = 24.0,
    ) -> dict[str, str]:
        """
        Export timeline in multiple formats.

        Args:
            timeline: OTIO Timeline object.
            output_dir: Directory for output files.
            formats: List of format names. Supported: "otio", "edl", "fcpxml".
                Default: all three.
            fps: Frame rate for EDL/FCPXML export.

        Returns:
            Dict mapping format name to absolute output path.

        Raises:
            TimelineExportError: If any export fails.
        """
        if formats is None:
            formats = ["otio", "edl", "fcpxml"]

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        base_name = re.sub(r'[^\w\-]', '_', timeline.name.lower())
        results: dict[str, str] = {}

        exporters = {
            "otio": (self.export_otio, f"{base_name}.otio", {}),
            "edl": (self.export_edl, f"{base_name}.edl", {"fps": fps}),
            "fcpxml": (self.export_fcpxml, f"{base_name}.fcpxml", {"fps": fps}),
        }

        for fmt in formats:
            fmt_lower = fmt.lower()
            if fmt_lower not in exporters:
                raise TimelineExportError(
                    f"Unknown export format: '{fmt}'. "
                    f"Supported: {', '.join(sorted(exporters.keys()))}"
                )

            export_fn, filename, kwargs = exporters[fmt_lower]
            output_path = str(out_dir / filename)
            results[fmt_lower] = export_fn(timeline, output_path, **kwargs)

        return results

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_timeline(self, input_path: str):
        """
        Import a timeline from an OTIO, EDL, or FCPXML file.

        Only OTIO JSON import is supported via the built-in adapter.
        EDL and FCPXML import require contrib adapters (not bundled
        with opentimelineio 0.18+). For those formats, use DaVinci
        Resolve or another NLE to convert to OTIO first.

        Args:
            input_path: Path to the timeline file (.otio, .otioz).

        Returns:
            An opentimelineio.schema.Timeline object.

        Raises:
            TimelineExportError: If import fails.
        """
        otio = self._otio_module()

        try:
            in_path = Path(input_path)
            if not in_path.exists():
                raise TimelineExportError(f"Input file not found: {input_path}")

            timeline = otio.adapters.read_from_file(str(in_path))
            return timeline

        except OTIOError:
            raise
        except Exception as exc:
            raise TimelineExportError(
                f"Failed to import timeline from '{input_path}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Timeline info
    # ------------------------------------------------------------------

    def get_timeline_info(self, timeline) -> dict[str, Any]:
        """
        Get summary information about a timeline.

        Args:
            timeline: OTIO Timeline object.

        Returns:
            Dict with keys:
              - name: str, timeline name
              - duration_seconds: float, total duration
              - track_count: int, number of tracks
              - clip_count: int, total clips across all tracks
              - marker_count: int, total markers
              - clips: list of dicts with clip details
              - markers: list of dicts with marker details
        """
        self._require_available()
        otio = self._otio_module()

        clips_info = []
        markers_info = []
        clip_count = 0
        marker_count = 0
        total_duration = 0.0

        for track_idx, track in enumerate(timeline.tracks):
            track_duration = 0.0
            for item in track:
                if isinstance(item, otio.schema.Clip):
                    clip_count += 1
                    sr = item.source_range
                    dur = sr.duration.to_seconds() if sr and sr.duration else 0.0
                    track_duration += dur
                    clips_info.append({
                        "name": item.name,
                        "track": track_idx,
                        "duration_seconds": dur,
                        "media_url": (
                            item.media_reference.target_url
                            if item.media_reference and hasattr(item.media_reference, "target_url")
                            else None
                        ),
                    })
                elif isinstance(item, otio.schema.Transition):
                    pass  # transitions don't add to clip count

            total_duration = max(total_duration, track_duration)

            for marker in track.markers:
                marker_count += 1
                markers_info.append({
                    "name": marker.name,
                    "time_seconds": marker.marked_range.start_time.to_seconds(),
                    "color": str(marker.color),
                    "comment": marker.comment,
                })

        return {
            "name": timeline.name,
            "duration_seconds": total_duration,
            "track_count": len(timeline.tracks),
            "clip_count": clip_count,
            "marker_count": marker_count,
            "clips": clips_info,
            "markers": markers_info,
        }

    # ------------------------------------------------------------------
    # Primary integration point
    # ------------------------------------------------------------------

    def timeline_from_media_engine_outputs(
        self,
        paths: list[str],
        fps: float = 24.0,
        transition_type: str | None = None,
        transition_duration: float = 1.0,
        timeline_name: str | None = None,
    ):
        """
        Build a sequential timeline from Media Engine generated assets.

        This is the PRIMARY integration point between the Media Engine
        pipeline and the timeline builder. Takes a list of generated asset
        paths (images, videos), auto-detects durations using PyAV (with
        graceful fallback to defaults), and builds a sequential timeline
        on a single video track.

        Args:
            paths: List of media file paths (images and/or videos).
            fps: Frame rate (default 24.0).
            transition_type: Transition between clips.
                "dissolve", "wipe", "fade_in", "fade_out", or None for cuts.
            transition_duration: Transition duration in seconds (default 1.0).
            timeline_name: Optional timeline name. Defaults to
                "Media Engine Timeline YYYY-MM-DD".

        Returns:
            An opentimelineio.schema.Timeline object.

        Raises:
            TimelineBuildError: If no valid paths are provided or build fails.
        """
        if not paths:
            raise TimelineBuildError("No media paths provided for timeline.")

        if timeline_name is None:
            timeline_name = f"Media Engine Timeline {datetime.now().strftime('%Y-%m-%d')}"

        clips: list[ClipSpec] = []
        markers: list[MarkerSpec] = []
        cumulative_time = 0.0

        for i, path in enumerate(paths):
            abs_path = os.path.abspath(path)
            name = Path(abs_path).stem

            # Detect duration
            if os.path.exists(abs_path):
                duration = _detect_duration(abs_path)
            else:
                # File planned but not yet generated
                ext = Path(abs_path).suffix.lower()
                if ext in _IMAGE_EXTENSIONS:
                    duration = _DEFAULT_IMAGE_DURATION_S
                else:
                    duration = _DEFAULT_VIDEO_DURATION_S

            clip = ClipSpec(
                path=abs_path,
                name=name,
                in_point=0.0,
                out_point=duration,
                track=0,
                transition_in=transition_type if i > 0 else None,
                transition_duration=transition_duration,
            )
            clips.append(clip)

            # Add a marker at each clip start for navigation
            markers.append(MarkerSpec(
                time=cumulative_time,
                name=f"Clip {i + 1}: {name}",
                color="GREEN",
                comment=f"Auto-generated clip boundary",
            ))

            cumulative_time += duration

        return self.create_timeline(
            name=timeline_name,
            fps=fps,
            clips=clips,
            markers=markers,
        )


# ---------------------------------------------------------------------------
# Utility functions (module-level)
# ---------------------------------------------------------------------------


def _seconds_to_timecode(seconds: float, fps: float) -> str:
    """
    Convert seconds to SMPTE timecode string (HH:MM:SS:FF).

    Args:
        seconds: Time in seconds.
        fps: Frame rate.

    Returns:
        Timecode string in HH:MM:SS:FF format.
    """
    if seconds < 0:
        seconds = 0.0

    total_frames = int(round(seconds * fps))
    fps_int = int(round(fps))

    ff = total_frames % fps_int
    total_seconds = total_frames // fps_int
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60

    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def _timecode_to_seconds(timecode: str, fps: float) -> float:
    """
    Convert SMPTE timecode (HH:MM:SS:FF) to seconds.

    Args:
        timecode: Timecode string.
        fps: Frame rate.

    Returns:
        Time in seconds.
    """
    parts = timecode.split(":")
    if len(parts) != 4:
        return 0.0

    hh, mm, ss, ff = [int(p) for p in parts]
    total_seconds = hh * 3600 + mm * 60 + ss + ff / fps
    return total_seconds


def _parse_fcpxml_duration(dur_str: str, fps: float) -> float:
    """
    Parse an FCPXML duration string (e.g., "4800/2400s") to seconds.

    Args:
        dur_str: Duration string from FCPXML attribute.
        fps: Frame rate (used as fallback).

    Returns:
        Duration in seconds.
    """
    dur_str = dur_str.strip()

    # Format: "NUM/DENs"
    match = re.match(r"(\d+)/(\d+)s", dur_str)
    if match:
        num = int(match.group(1))
        den = int(match.group(2))
        if den > 0:
            return num / den
        return 0.0

    # Format: "NUMs"
    match = re.match(r"([\d.]+)s", dur_str)
    if match:
        return float(match.group(1))

    return 0.0
