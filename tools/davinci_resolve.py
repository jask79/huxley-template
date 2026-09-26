#!/usr/bin/env python3
"""
DaVinci Resolve Scripting CLI for Huxley

Wraps the DaVinci Resolve Python Scripting API for programmatic control of:
- Project management (create, load, save, settings)
- Media pool operations (import, list, organize)
- Timeline manipulation (create, add clips, tracks, items)
- Marker management (add, list, delete)
- Color grading (apply LUTs, grades, export LUTs)
- Render queue management (add jobs, start/stop rendering)

DaVinci Resolve must be running for live commands. Use --mock for testing
without Resolve. Use --dry-run to preview write operations.

Requirements:
    - DaVinci Resolve Studio (scripting requires Studio license)
    - Python >= 3.6
    - Resolve scripting enabled in Preferences > System > General
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid marker colors in DaVinci Resolve
# ---------------------------------------------------------------------------
VALID_MARKER_COLORS = [
    "Blue", "Cyan", "Green", "Yellow", "Red", "Pink",
    "Purple", "Fuchsia", "Rose", "Lavender", "Sky", "Mint",
    "Lemon", "Sand", "Cocoa", "Cream",
]

# ---------------------------------------------------------------------------
# Valid page names
# ---------------------------------------------------------------------------
VALID_PAGES = ["media", "cut", "edit", "fusion", "color", "fairlight", "deliver"]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ResolveError(Exception):
    """Base exception for all Resolve errors."""
    pass

class ResolveConnectionError(ResolveError):
    """Failed to connect to Resolve."""
    pass

class ResolveNotRunningError(ResolveConnectionError):
    """DaVinci Resolve is not running."""
    pass

class ResolveScriptingDisabledError(ResolveConnectionError):
    """Scripting is disabled in Resolve preferences."""
    pass

class ResolveOperationError(ResolveError):
    """A Resolve operation failed."""
    pass

class ResolveProjectNotFoundError(ResolveError):
    """Requested project was not found."""
    pass

class ResolveTimelineNotFoundError(ResolveError):
    """Requested timeline was not found."""
    pass


# ---------------------------------------------------------------------------
# Structured result types
# ---------------------------------------------------------------------------

@dataclass
class ResolveStatus:
    connected: bool
    version: str
    product_name: str
    current_page: str
    current_project: str
    current_timeline: str

@dataclass
class ProjectInfo:
    name: str
    frame_rate: str
    resolution_width: str
    resolution_height: str
    timeline_count: int
    is_current: bool

@dataclass
class ProjectSettings:
    frame_rate: str
    resolution_width: str
    resolution_height: str
    all_settings: dict

@dataclass
class ClipInfo:
    name: str
    file_path: str
    duration: str
    resolution: str
    fps: str
    codec: str
    properties: dict

@dataclass
class FolderInfo:
    name: str
    clip_count: int
    subfolder_count: int

@dataclass
class TimelineInfo:
    name: str
    start_frame: int
    end_frame: int
    start_timecode: str
    video_track_count: int
    audio_track_count: int
    subtitle_track_count: int
    current_timecode: str

@dataclass
class TrackInfo:
    track_type: str
    track_index: int
    name: str
    item_count: int

@dataclass
class TimelineItemInfo:
    name: str
    start: int
    end: int
    duration: int
    track_type: str
    track_index: int

@dataclass
class MarkerInfo:
    frame_id: float
    color: str
    name: str
    note: str
    duration: float
    custom_data: str

@dataclass
class RenderJobInfo:
    job_id: str
    timeline_name: str
    status: str
    completion: str
    render_settings: dict

@dataclass
class ImportResult:
    success: bool
    imported_count: int
    clip_names: list
    errors: list


# ---------------------------------------------------------------------------
# ResolveConnection - handles finding and loading the scripting API
# ---------------------------------------------------------------------------

class ResolveConnection:
    """
    Manages the connection to DaVinci Resolve's scripting API.

    Auto-detects macOS paths, imports DaVinciResolveScript, and connects
    to the running Resolve instance.
    """

    MACOS_MODULES = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/"
    MACOS_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"

    LINUX_MODULES = "/opt/resolve/Developer/Scripting/Modules/"
    LINUX_SCRIPT_LIB = "/opt/resolve/libs/Fusion/fusionscript.so"

    def __init__(self):
        self._resolve = None
        self._project_manager = None

    def connect(self) -> Any:
        """
        Connect to DaVinci Resolve.

        Discovery order:
        1. RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB env vars
        2. Default macOS paths
        3. Default Linux paths

        Returns the Resolve scripting object.

        Raises:
            ResolveNotRunningError: If Resolve is not running
            ResolveScriptingDisabledError: If scripting is disabled
            ResolveConnectionError: If connection fails for other reasons
        """
        if self._resolve is not None:
            return self._resolve

        # Determine modules path and script lib path
        modules_path = os.environ.get("RESOLVE_SCRIPT_API")
        if modules_path:
            modules_path = os.path.join(modules_path, "Modules")
        script_lib = os.environ.get("RESOLVE_SCRIPT_LIB")

        if not modules_path or not os.path.isdir(modules_path):
            # Try default macOS paths
            if sys.platform.startswith("darwin"):
                if os.path.isdir(self.MACOS_MODULES):
                    modules_path = self.MACOS_MODULES
                if not script_lib and os.path.isfile(self.MACOS_SCRIPT_LIB):
                    script_lib = self.MACOS_SCRIPT_LIB
            elif sys.platform.startswith("linux"):
                if os.path.isdir(self.LINUX_MODULES):
                    modules_path = self.LINUX_MODULES
                if not script_lib and os.path.isfile(self.LINUX_SCRIPT_LIB):
                    script_lib = self.LINUX_SCRIPT_LIB

        if not modules_path or not os.path.isdir(modules_path):
            raise ResolveConnectionError(
                "Could not find DaVinci Resolve scripting modules.\n"
                "Ensure DaVinci Resolve is installed, or set RESOLVE_SCRIPT_API:\n"
                "  export RESOLVE_SCRIPT_API=\"/Library/Application Support/"
                "Blackmagic Design/DaVinci Resolve/Developer/Scripting\"\n"
                "  export RESOLVE_SCRIPT_LIB=\"/Applications/DaVinci Resolve/"
                "DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so\""
            )

        # Set environment for the module loader
        if script_lib:
            os.environ["RESOLVE_SCRIPT_LIB"] = script_lib

        # Add modules to sys.path
        if modules_path not in sys.path:
            sys.path.insert(0, modules_path)

        # Import the scripting module
        try:
            import DaVinciResolveScript as bmd
        except ImportError as e:
            raise ResolveConnectionError(
                f"Failed to import DaVinciResolveScript: {e}\n"
                f"Modules path: {modules_path}\n"
                f"Script lib: {script_lib}"
            )

        # Connect to running Resolve
        resolve = bmd.scriptapp("Resolve")
        if resolve is None:
            raise ResolveScriptingDisabledError(
                "DaVinci Resolve is not responding to scripting requests.\n"
                "Possible causes:\n"
                "  1. DaVinci Resolve is not running - launch it first\n"
                "  2. Scripting is disabled - enable in:\n"
                "     Preferences > System > General > External scripting using: Local\n"
                "  3. You need DaVinci Resolve Studio (not Free) for external scripting"
            )

        # Verify connection by getting version
        try:
            version = resolve.GetVersionString()
            if not version:
                raise ResolveNotRunningError(
                    "Connected to Resolve but GetVersion() returned empty.\n"
                    "DaVinci Resolve may not be fully started yet."
                )
            logger.info("Connected to DaVinci Resolve %s", version)
        except Exception as e:
            raise ResolveConnectionError(f"Failed to verify Resolve connection: {e}")

        self._resolve = resolve
        return resolve

    @property
    def resolve(self) -> Any:
        """Get the cached Resolve object, connecting if needed."""
        if self._resolve is None:
            self.connect()
        return self._resolve

    @property
    def project_manager(self) -> Any:
        """Get the ProjectManager object."""
        if self._project_manager is None:
            self._project_manager = self.resolve.GetProjectManager()
        return self._project_manager


# ---------------------------------------------------------------------------
# MockResolveConnection - realistic fake data for testing
# ---------------------------------------------------------------------------

class _MockFolder:
    """Mock media pool folder."""
    def __init__(self, name, clips=None, subfolders=None):
        self._name = name
        self._clips = clips or []
        self._subfolders = subfolders or []

    def GetName(self):
        return self._name

    def GetClipList(self):
        return self._clips

    def GetSubFolderList(self):
        return self._subfolders

    def GetUniqueId(self):
        return f"folder-{self._name.lower().replace(' ', '-')}"


class _MockClip:
    """Mock media pool item."""
    def __init__(self, name, props=None, markers=None):
        self._name = name
        self._props = props or {}
        self._markers = markers or {}

    def GetName(self):
        return self._name

    def GetClipProperty(self, key=None):
        if key is None:
            return dict(self._props)
        return self._props.get(key, "")

    def GetMarkers(self):
        return dict(self._markers)

    def GetMediaId(self):
        return f"clip-{self._name.lower().replace(' ', '-')}"

    def GetMetadata(self, key=None):
        if key is None:
            return {"Description": "", "Comments": ""}
        return ""

    def SetMetadata(self, *args):
        return True

    def AddMarker(self, frameId, color, name, note, duration, customData=""):
        self._markers[float(frameId)] = {
            "color": color, "name": name, "note": note,
            "duration": float(duration), "customData": customData,
        }
        return True

    def DeleteMarkerAtFrame(self, frameNum):
        fid = float(frameNum)
        if fid in self._markers:
            del self._markers[fid]
            return True
        return False


class _MockTimelineItem:
    """Mock timeline item."""
    def __init__(self, name, start, end, track_type="video", track_index=1):
        self._name = name
        self._start = start
        self._end = end
        self._track_type = track_type
        self._track_index = track_index

    def GetName(self):
        return self._name

    def GetStart(self, *args):
        return self._start

    def GetEnd(self, *args):
        return self._end

    def GetDuration(self, *args):
        return self._end - self._start

    def GetTrackTypeAndIndex(self):
        return [self._track_type, self._track_index]

    def GetNodeGraph(self):
        return _MockNodeGraph()

    def ExportLUT(self, export_type, output_path):
        return True

    def SetLUT(self, lut_path):
        return True


class _MockTimeline:
    """Mock timeline."""
    def __init__(self, name, start_frame=0, end_frame=7200, video_tracks=2,
                 audio_tracks=4, markers=None, items=None):
        self._name = name
        self._start_frame = start_frame
        self._end_frame = end_frame
        self._video_tracks = video_tracks
        self._audio_tracks = audio_tracks
        self._subtitle_tracks = 1
        self._markers = markers or {}
        self._items = items or {}
        self._track_names = {}

    def GetName(self):
        return self._name

    def SetName(self, name):
        self._name = name
        return True

    def GetStartFrame(self):
        return self._start_frame

    def GetEndFrame(self):
        return self._end_frame

    def GetStartTimecode(self):
        return "01:00:00:00"

    def GetTrackCount(self, track_type):
        if track_type == "video":
            return self._video_tracks
        elif track_type == "audio":
            return self._audio_tracks
        elif track_type == "subtitle":
            return self._subtitle_tracks
        return 0

    def GetCurrentTimecode(self):
        return "01:00:05:12"

    def GetTrackName(self, track_type, track_index):
        key = f"{track_type}_{track_index}"
        return self._track_names.get(key, f"{track_type.capitalize()} {track_index}")

    def SetTrackName(self, track_type, track_index, name):
        key = f"{track_type}_{track_index}"
        self._track_names[key] = name
        return True

    def GetItemListInTrack(self, track_type, index):
        key = f"{track_type}_{index}"
        return self._items.get(key, [])

    def AddMarker(self, frameId, color, name, note, duration, customData=""):
        self._markers[float(frameId)] = {
            "color": color, "name": name, "note": note,
            "duration": float(duration), "customData": customData,
        }
        return True

    def GetMarkers(self):
        return dict(self._markers)

    def DeleteMarkerAtFrame(self, frameNum):
        fid = float(frameNum)
        if fid in self._markers:
            del self._markers[fid]
            return True
        return False

    def GetUniqueId(self):
        return f"timeline-{self._name.lower().replace(' ', '-')}"

    def GetSetting(self, key=None):
        settings = {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineOutputResolutionWidth": "1920",
            "timelineOutputResolutionHeight": "1080",
        }
        if key is None:
            return settings
        return settings.get(key, "")

    def SetSetting(self, key, value):
        return True

    def GetCurrentVideoItem(self):
        items = self.GetItemListInTrack("video", 1)
        return items[0] if items else _MockTimelineItem("Mock Clip", 86400, 87120)

    def GetNodeGraph(self):
        return _MockNodeGraph()


class _MockNodeGraph:
    """Mock node graph for color operations."""
    def __init__(self, num_nodes=3):
        self._num_nodes = num_nodes
        self._luts = {}

    def GetNumNodes(self):
        return self._num_nodes

    def SetLUT(self, nodeIndex, lutPath):
        if 1 <= nodeIndex <= self._num_nodes:
            self._luts[nodeIndex] = lutPath
            return True
        return False

    def GetLUT(self, nodeIndex):
        return self._luts.get(nodeIndex, "")

    def ApplyGradeFromDRX(self, path, gradeMode):
        return True

    def GetNodeLabel(self, nodeIndex):
        return f"Node {nodeIndex}"


class _MockProject:
    """Mock project."""
    def __init__(self, name, settings=None, timelines=None, media_pool=None):
        self._name = name
        self._settings = settings or {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "videoCaptureNumChannels": "2",
            "audioCaptureNumChannels": "2",
            "colorScienceMode": "davinciYRGBColorManagedv2",
            "colorSpaceTimeline": "DaVinci WG",
            "colorSpaceOutput": "Rec.709 Gamma 2.4",
        }
        self._timelines = timelines or []
        self._media_pool = media_pool
        self._current_timeline_idx = 0
        self._render_jobs = []
        self._render_presets = ["H.264 Master", "ProRes Master", "YouTube 1080p",
                                "DNxHR HQX", "Custom Export"]
        self._render_formats = {
            "mp4": ".mp4", "mov": ".mov", "mxf": ".mxf",
            "avi": ".avi", "dpx": ".dpx", "exr": ".exr",
        }

    def GetName(self):
        return self._name

    def SetName(self, name):
        self._name = name
        return True

    def GetTimelineCount(self):
        return len(self._timelines)

    def GetTimelineByIndex(self, idx):
        if 1 <= idx <= len(self._timelines):
            return self._timelines[idx - 1]
        return None

    def GetCurrentTimeline(self):
        if self._timelines and self._current_timeline_idx < len(self._timelines):
            return self._timelines[self._current_timeline_idx]
        return None

    def SetCurrentTimeline(self, timeline):
        for i, t in enumerate(self._timelines):
            if t.GetName() == timeline.GetName():
                self._current_timeline_idx = i
                return True
        return False

    def GetMediaPool(self):
        return self._media_pool

    def GetSetting(self, key=None):
        if key is None:
            return dict(self._settings)
        return self._settings.get(key, "")

    def SetSetting(self, key, value):
        self._settings[key] = value
        return True

    def GetRenderJobList(self):
        return list(self._render_jobs)

    def GetRenderPresetList(self):
        return list(self._render_presets)

    def GetRenderFormats(self):
        return dict(self._render_formats)

    def GetRenderCodecs(self, fmt):
        codecs = {
            "mp4": {"H.264": "H264", "H.265": "H265"},
            "mov": {"ProRes 422": "ProRes422", "ProRes 422 HQ": "ProRes422HQ",
                     "ProRes 4444": "ProRes4444", "DNxHR HQX": "DNxHRHQX"},
        }
        return codecs.get(fmt, {})

    def GetCurrentRenderFormatAndCodec(self):
        return {"format": "mp4", "codec": "H264"}

    def SetCurrentRenderFormatAndCodec(self, fmt, codec):
        return True

    def SetRenderSettings(self, settings):
        return True

    def LoadRenderPreset(self, name):
        return name in self._render_presets

    def AddRenderJob(self):
        job_id = f"job-{len(self._render_jobs) + 1:03d}"
        self._render_jobs.append({
            "JobId": job_id,
            "TimelineName": self.GetCurrentTimeline().GetName() if self.GetCurrentTimeline() else "Unknown",
            "TargetDir": "{{HOME_DIR}}/Movies/Exports/",
            "RenderJobName": f"Render {len(self._render_jobs) + 1}",
            "FormatWidth": "1920",
            "FormatHeight": "1080",
            "IsExportVideo": True,
            "IsExportAudio": True,
        })
        return job_id

    def DeleteRenderJob(self, jobId):
        self._render_jobs = [j for j in self._render_jobs if j.get("JobId") != jobId]
        return True

    def DeleteAllRenderJobs(self):
        self._render_jobs = []
        return True

    def GetRenderJobStatus(self, jobId):
        for j in self._render_jobs:
            if j.get("JobId") == jobId:
                return {"JobStatus": "Ready", "CompletionPercentage": "0"}
        return {"JobStatus": "Unknown", "CompletionPercentage": "0"}

    def StartRendering(self, *args, **kwargs):
        return True

    def StopRendering(self):
        return None

    def IsRenderingInProgress(self):
        return False

    def GetGallery(self):
        return None

    def GetUniqueId(self):
        return f"project-{self._name.lower().replace(' ', '-')}"

    def SaveAsNewRenderPreset(self, name):
        self._render_presets.append(name)
        return True

    def ExportCurrentFrameAsStill(self, path):
        return True


class _MockMediaPool:
    """Mock media pool."""
    def __init__(self, root_folder=None):
        self._root = root_folder
        self._current = root_folder

    def GetRootFolder(self):
        return self._root

    def GetCurrentFolder(self):
        return self._current or self._root

    def SetCurrentFolder(self, folder):
        self._current = folder
        return True

    def AddSubFolder(self, parent, name):
        new_folder = _MockFolder(name)
        parent._subfolders.append(new_folder)
        return new_folder

    def ImportMedia(self, paths):
        clips = []
        for p in paths:
            name = os.path.basename(p)
            clip = _MockClip(name, {
                "File Path": p,
                "Duration": "00:00:30:00",
                "Resolution": "1920x1080",
                "FPS": "24.000",
                "Video Codec": "H.264",
                "Type": "Video",
            })
            clips.append(clip)
        return clips if clips else None

    def CreateEmptyTimeline(self, name):
        return _MockTimeline(name, video_tracks=1, audio_tracks=1)

    def AppendToTimeline(self, clips):
        items = []
        offset = 0
        for clip in clips:
            item = _MockTimelineItem(clip.GetName(), offset, offset + 720)
            items.append(item)
            offset += 720
        return items

    def GetUniqueId(self):
        return "mediapool-mock-001"


class _MockProjectManager:
    """Mock project manager."""
    def __init__(self, projects=None, current_idx=0):
        self._projects = projects or []
        self._current_idx = current_idx

    def GetCurrentProject(self):
        if self._projects and self._current_idx < len(self._projects):
            return self._projects[self._current_idx]
        return None

    def GetProjectListInCurrentFolder(self):
        return [p.GetName() for p in self._projects]

    def LoadProject(self, name):
        for i, p in enumerate(self._projects):
            if p.GetName() == name:
                self._current_idx = i
                return p
        return None

    def CreateProject(self, name, *args):
        proj = _MockProject(name)
        self._projects.append(proj)
        self._current_idx = len(self._projects) - 1
        return proj

    def SaveProject(self):
        return True

    def GetCurrentFolder(self):
        return "Root"

    def GetCurrentDatabase(self):
        return {"DbType": "Disk", "DbName": "Local Database"}


class _MockResolve:
    """Mock Resolve object."""
    def __init__(self, project_manager):
        self._pm = project_manager
        self._page = "edit"

    def GetProjectManager(self):
        return self._pm

    def GetVersionString(self):
        return "19.1.2.0009"

    def GetVersion(self):
        return [19, 1, 2, 9, ""]

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetCurrentPage(self):
        return self._page

    def OpenPage(self, page):
        if page in VALID_PAGES:
            self._page = page
            return True
        return False

    def GetMediaStorage(self):
        return None

    def Fusion(self):
        return None


def _build_mock_data():
    """Build realistic mock data for testing."""
    # Create mock clips
    clips = [
        _MockClip("Interview_A_001.mov", {
            "File Path": "{{HOME_DIR}}/Footage/Interview_A_001.mov",
            "Duration": "00:05:30:00",
            "Resolution": "3840x2160",
            "FPS": "24.000",
            "Video Codec": "ProRes 422 HQ",
            "Audio Codec": "Linear PCM",
            "Type": "Video + Audio",
            "Frames": "7920",
            "Start TC": "01:00:00:00",
            "End TC": "01:05:30:00",
        }),
        _MockClip("B-Roll_City_001.mp4", {
            "File Path": "{{HOME_DIR}}/Footage/B-Roll_City_001.mp4",
            "Duration": "00:02:15:00",
            "Resolution": "3840x2160",
            "FPS": "30.000",
            "Video Codec": "H.265",
            "Type": "Video",
            "Frames": "4050",
            "Start TC": "00:00:00:00",
            "End TC": "00:02:15:00",
        }),
        _MockClip("Drone_Sunset_001.mov", {
            "File Path": "{{HOME_DIR}}/Footage/Drone_Sunset_001.mov",
            "Duration": "00:01:45:00",
            "Resolution": "4096x2160",
            "FPS": "24.000",
            "Video Codec": "ProRes 4444",
            "Type": "Video",
            "Frames": "2520",
            "Start TC": "00:00:00:00",
            "End TC": "00:01:45:00",
        }),
        _MockClip("VO_Take3.wav", {
            "File Path": "{{HOME_DIR}}/Footage/Audio/VO_Take3.wav",
            "Duration": "00:04:10:00",
            "Resolution": "",
            "FPS": "",
            "Audio Codec": "Linear PCM",
            "Audio Bit Depth": "24",
            "Audio SR": "48000",
            "Type": "Audio",
            "Frames": "5940",
        }),
        _MockClip("Music_BG_01.mp3", {
            "File Path": "{{HOME_DIR}}/Footage/Audio/Music_BG_01.mp3",
            "Duration": "00:03:30:00",
            "Resolution": "",
            "FPS": "",
            "Audio Codec": "MP3",
            "Type": "Audio",
            "Frames": "5040",
        }),
        _MockClip("Lower_Third.png", {
            "File Path": "{{HOME_DIR}}/Footage/Graphics/Lower_Third.png",
            "Duration": "00:00:01:00",
            "Resolution": "1920x1080",
            "FPS": "",
            "Video Codec": "PNG",
            "Type": "Still",
            "Frames": "1",
        }),
        _MockClip("Logo_Overlay.exr", {
            "File Path": "{{HOME_DIR}}/Footage/Graphics/Logo_Overlay.exr",
            "Duration": "00:00:01:00",
            "Resolution": "2048x2048",
            "FPS": "",
            "Video Codec": "OpenEXR",
            "Type": "Still",
            "Frames": "1",
        }),
    ]

    # Build folders
    audio_folder = _MockFolder("Audio", clips=[clips[3], clips[4]])
    graphics_folder = _MockFolder("Graphics", clips=[clips[5], clips[6]])
    root_folder = _MockFolder("Master",
                              clips=[clips[0], clips[1], clips[2]],
                              subfolders=[audio_folder, graphics_folder])

    media_pool = _MockMediaPool(root_folder)

    # Timeline items
    tl_items_v1 = [
        _MockTimelineItem("Interview_A_001.mov", 86400, 94320, "video", 1),
        _MockTimelineItem("B-Roll_City_001.mp4", 94320, 96360, "video", 1),
    ]
    tl_items_v2 = [
        _MockTimelineItem("Drone_Sunset_001.mov", 86400, 88920, "video", 2),
        _MockTimelineItem("Lower_Third.png", 87120, 87264, "video", 2),
    ]
    tl_items_a1 = [
        _MockTimelineItem("VO_Take3.wav", 86400, 92340, "audio", 1),
    ]
    tl_items_a2 = [
        _MockTimelineItem("Music_BG_01.mp3", 86400, 91440, "audio", 2),
    ]

    # Timelines
    timeline1 = _MockTimeline(
        "Main Edit v2", start_frame=86400, end_frame=98280,
        video_tracks=3, audio_tracks=4,
        markers={
            86400.0: {"color": "Green", "name": "In Point", "note": "Start here",
                      "duration": 1.0, "customData": ""},
            90720.0: {"color": "Red", "name": "Review", "note": "Check audio sync",
                      "duration": 1.0, "customData": "review-001"},
            94320.0: {"color": "Blue", "name": "B-Roll Start", "note": "",
                      "duration": 1.0, "customData": ""},
            96840.0: {"color": "Yellow", "name": "End Card", "note": "Add end card here",
                      "duration": 48.0, "customData": ""},
        },
        items={
            "video_1": tl_items_v1,
            "video_2": tl_items_v2,
            "audio_1": tl_items_a1,
            "audio_2": tl_items_a2,
        },
    )

    timeline2 = _MockTimeline(
        "Selects Timeline", start_frame=86400, end_frame=100800,
        video_tracks=1, audio_tracks=2,
        markers={
            87600.0: {"color": "Green", "name": "Good Take", "note": "Use this",
                      "duration": 1.0, "customData": ""},
        },
    )

    # Projects
    project1 = _MockProject(
        "Brand Launch 2026",
        settings={
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "3840",
            "timelineResolutionHeight": "2160",
            "videoCaptureNumChannels": "2",
            "audioCaptureNumChannels": "2",
            "colorScienceMode": "davinciYRGBColorManagedv2",
            "colorSpaceTimeline": "DaVinci WG/Intermediate",
            "colorSpaceOutput": "Rec.709 Gamma 2.4",
            "superScale": "0",
            "timelineWorkingLuminance": "100",
        },
        timelines=[timeline1, timeline2],
        media_pool=media_pool,
    )

    project2 = _MockProject(
        "Product Demo Short",
        settings={
            "timelineFrameRate": "30",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "colorScienceMode": "davinciYRGB",
            "colorSpaceTimeline": "Rec.709",
            "colorSpaceOutput": "Rec.709 Gamma 2.4",
        },
        timelines=[_MockTimeline("Product Demo v1", video_tracks=2, audio_tracks=2)],
    )

    project3 = _MockProject(
        "Social Media Cuts",
        settings={
            "timelineFrameRate": "30",
            "timelineResolutionWidth": "1080",
            "timelineResolutionHeight": "1920",
            "colorScienceMode": "davinciYRGB",
        },
        timelines=[
            _MockTimeline("Instagram Reel", video_tracks=1, audio_tracks=1),
            _MockTimeline("TikTok Cut", video_tracks=1, audio_tracks=1),
        ],
    )

    # Add render jobs to project1
    project1._render_jobs = [
        {
            "JobId": "job-001",
            "TimelineName": "Main Edit v2",
            "TargetDir": "{{HOME_DIR}}/Movies/Exports/",
            "RenderJobName": "Main Edit Final",
            "FormatWidth": "3840",
            "FormatHeight": "2160",
            "IsExportVideo": True,
            "IsExportAudio": True,
            "OutputFilename": "Brand_Launch_2026_Final.mp4",
        },
        {
            "JobId": "job-002",
            "TimelineName": "Selects Timeline",
            "TargetDir": "{{HOME_DIR}}/Movies/Exports/Selects/",
            "RenderJobName": "Selects Export",
            "FormatWidth": "1920",
            "FormatHeight": "1080",
            "IsExportVideo": True,
            "IsExportAudio": True,
            "OutputFilename": "Selects_Preview.mov",
        },
    ]

    pm = _MockProjectManager([project1, project2, project3], current_idx=0)
    return _MockResolve(pm)


class MockResolveConnection:
    """
    Mock connection that provides realistic fake data.
    Used for testing the CLI without DaVinci Resolve running.
    """

    def __init__(self):
        self._resolve = _build_mock_data()
        self._project_manager = self._resolve.GetProjectManager()

    def connect(self) -> Any:
        return self._resolve

    @property
    def resolve(self) -> Any:
        return self._resolve

    @property
    def project_manager(self) -> Any:
        return self._project_manager


# ---------------------------------------------------------------------------
# ResolveClient - high-level API wrapper with error handling
# ---------------------------------------------------------------------------

class ResolveClient:
    """
    High-level wrapper around the Resolve scripting API.

    Provides error handling, dry-run support, and returns structured
    dataclass results instead of raw API objects.
    """

    def __init__(self, connection, dry_run: bool = False):
        self.conn = connection
        self.dry_run = dry_run

    @property
    def resolve(self):
        return self.conn.resolve

    @property
    def pm(self):
        return self.conn.project_manager

    # --- System ---

    def get_status(self) -> ResolveStatus:
        """Get current Resolve status."""
        resolve = self.resolve
        pm = self.pm

        project = pm.GetCurrentProject()
        project_name = project.GetName() if project else "(none)"

        timeline = project.GetCurrentTimeline() if project else None
        timeline_name = timeline.GetName() if timeline else "(none)"

        return ResolveStatus(
            connected=True,
            version=resolve.GetVersionString(),
            product_name=resolve.GetProductName(),
            current_page=resolve.GetCurrentPage() or "(none)",
            current_project=project_name,
            current_timeline=timeline_name,
        )

    def get_page(self) -> str:
        """Get current page name."""
        return self.resolve.GetCurrentPage() or "(none)"

    def set_page(self, page_name: str) -> bool:
        """Set current page."""
        page = page_name.lower().strip()
        if page not in VALID_PAGES:
            raise ResolveOperationError(
                f"Invalid page: '{page_name}'. Valid pages: {', '.join(VALID_PAGES)}"
            )
        if self.dry_run:
            logger.info("[DRY RUN] Would switch to page: %s", page)
            return True
        result = self.resolve.OpenPage(page)
        if not result:
            raise ResolveOperationError(f"Failed to switch to page: {page}")
        return True

    # --- Projects ---

    def list_projects(self) -> List[ProjectInfo]:
        """List all projects in the current database folder."""
        pm = self.pm
        project_names = pm.GetProjectListInCurrentFolder()
        current = pm.GetCurrentProject()
        current_name = current.GetName() if current else ""

        results = []
        for name in project_names:
            is_current = (name == current_name)

            if is_current and current:
                results.append(ProjectInfo(
                    name=name,
                    frame_rate=current.GetSetting("timelineFrameRate") or "",
                    resolution_width=current.GetSetting("timelineResolutionWidth") or "",
                    resolution_height=current.GetSetting("timelineResolutionHeight") or "",
                    timeline_count=current.GetTimelineCount(),
                    is_current=True,
                ))
            else:
                results.append(ProjectInfo(
                    name=name,
                    frame_rate="",
                    resolution_width="",
                    resolution_height="",
                    timeline_count=0,
                    is_current=False,
                ))

        return results

    def get_project_info(self, name: Optional[str] = None) -> ProjectInfo:
        """Get info for a project (current if name is None)."""
        pm = self.pm
        project = pm.GetCurrentProject()

        if name and project and project.GetName() != name:
            # Need to load the requested project to get its info
            raise ResolveOperationError(
                f"Cannot get info for '{name}' without loading it. "
                f"Current project is '{project.GetName()}'. "
                f"Use 'project load {name}' first."
            )

        if not project:
            raise ResolveOperationError("No project is currently loaded.")

        return ProjectInfo(
            name=project.GetName(),
            frame_rate=project.GetSetting("timelineFrameRate") or "",
            resolution_width=project.GetSetting("timelineResolutionWidth") or "",
            resolution_height=project.GetSetting("timelineResolutionHeight") or "",
            timeline_count=project.GetTimelineCount(),
            is_current=True,
        )

    def create_project(self, name: str, fps: Optional[str] = None,
                       width: Optional[str] = None,
                       height: Optional[str] = None) -> ProjectInfo:
        """Create a new project."""
        if self.dry_run:
            logger.info("[DRY RUN] Would create project: %s", name)
            return ProjectInfo(
                name=name,
                frame_rate=fps or "24",
                resolution_width=width or "1920",
                resolution_height=height or "1080",
                timeline_count=0,
                is_current=True,
            )

        pm = self.pm

        # Attempt to save the current project first — CreateProject can fail
        # if the current project is in an unsaved/blocking state (e.g. fresh
        # "Untitled Project" on Resolve startup).
        try:
            pm.SaveProject()
        except Exception:
            pass

        project = pm.CreateProject(name)
        if not project:
            raise ResolveOperationError(
                f"Failed to create project '{name}'. "
                "A project with this name may already exist."
            )

        if fps:
            project.SetSetting("timelineFrameRate", fps)
        if width:
            project.SetSetting("timelineResolutionWidth", width)
        if height:
            project.SetSetting("timelineResolutionHeight", height)

        return ProjectInfo(
            name=project.GetName(),
            frame_rate=project.GetSetting("timelineFrameRate") or "",
            resolution_width=project.GetSetting("timelineResolutionWidth") or "",
            resolution_height=project.GetSetting("timelineResolutionHeight") or "",
            timeline_count=project.GetTimelineCount(),
            is_current=True,
        )

    def load_project(self, name: str) -> ProjectInfo:
        """Load a project by name."""
        if self.dry_run:
            logger.info("[DRY RUN] Would load project: %s", name)
            return ProjectInfo(name=name, frame_rate="", resolution_width="",
                               resolution_height="", timeline_count=0, is_current=True)

        pm = self.pm
        project = pm.LoadProject(name)
        if not project:
            available = pm.GetProjectListInCurrentFolder()
            raise ResolveProjectNotFoundError(
                f"Project '{name}' not found.\n"
                f"Available projects: {', '.join(available) if available else '(none)'}"
            )

        return ProjectInfo(
            name=project.GetName(),
            frame_rate=project.GetSetting("timelineFrameRate") or "",
            resolution_width=project.GetSetting("timelineResolutionWidth") or "",
            resolution_height=project.GetSetting("timelineResolutionHeight") or "",
            timeline_count=project.GetTimelineCount(),
            is_current=True,
        )

    def save_project(self) -> bool:
        """Save the current project."""
        if self.dry_run:
            logger.info("[DRY RUN] Would save current project")
            return True
        return self.pm.SaveProject()

    def get_project_settings(self) -> ProjectSettings:
        """Get all settings for the current project."""
        project = self.pm.GetCurrentProject()
        if not project:
            raise ResolveOperationError("No project is currently loaded.")

        all_settings = project.GetSetting("") or project.GetSetting(None) or {}
        # GetSetting("") or GetSetting() returns all settings as dict
        if not isinstance(all_settings, dict):
            all_settings = {}

        # Also try without args
        if not all_settings:
            try:
                all_settings = project.GetSetting() or {}
            except TypeError:
                all_settings = {}

        return ProjectSettings(
            frame_rate=project.GetSetting("timelineFrameRate") or "",
            resolution_width=project.GetSetting("timelineResolutionWidth") or "",
            resolution_height=project.GetSetting("timelineResolutionHeight") or "",
            all_settings=all_settings,
        )

    def set_project_setting(self, key: str, value: str) -> bool:
        """Set a project setting."""
        project = self.pm.GetCurrentProject()
        if not project:
            raise ResolveOperationError("No project is currently loaded.")

        if self.dry_run:
            logger.info("[DRY RUN] Would set project setting %s = %s", key, value)
            return True

        result = project.SetSetting(key, value)
        if not result:
            raise ResolveOperationError(
                f"Failed to set project setting '{key}' to '{value}'. "
                "The key may be invalid or the value may not be accepted."
            )
        return True

    # --- Media Pool ---

    def _get_current_project(self):
        """Get the current project, raising an error if none loaded."""
        project = self.pm.GetCurrentProject()
        if not project:
            raise ResolveOperationError("No project is currently loaded.")
        return project

    def _get_media_pool(self):
        """Get the media pool for the current project."""
        project = self._get_current_project()
        pool = project.GetMediaPool()
        if not pool:
            raise ResolveOperationError("Could not access the media pool.")
        return pool

    def _find_folder(self, folder_name: Optional[str] = None):
        """Find a folder in the media pool by name. Returns root if None."""
        pool = self._get_media_pool()
        if not folder_name:
            return pool.GetRootFolder()

        root = pool.GetRootFolder()
        # Search recursively
        found = self._search_folder(root, folder_name)
        if not found:
            raise ResolveOperationError(
                f"Folder '{folder_name}' not found in media pool."
            )
        return found

    def _search_folder(self, folder, target_name: str):
        """Recursively search for a folder by name."""
        if folder.GetName() == target_name:
            return folder
        for sub in (folder.GetSubFolderList() or []):
            result = self._search_folder(sub, target_name)
            if result:
                return result
        return None

    def import_media(self, file_paths: List[str],
                     folder_name: Optional[str] = None) -> ImportResult:
        """Import media files into the media pool."""
        errors = []
        valid_paths = []

        for fp in file_paths:
            abs_path = os.path.abspath(fp)
            if not os.path.exists(abs_path):
                errors.append(f"File not found: {abs_path}")
            else:
                valid_paths.append(abs_path)

        if not valid_paths:
            return ImportResult(
                success=False, imported_count=0, clip_names=[], errors=errors
            )

        if self.dry_run:
            logger.info("[DRY RUN] Would import %d files", len(valid_paths))
            return ImportResult(
                success=True,
                imported_count=len(valid_paths),
                clip_names=[os.path.basename(p) for p in valid_paths],
                errors=errors,
            )

        pool = self._get_media_pool()

        if folder_name:
            folder = self._find_folder(folder_name)
            pool.SetCurrentFolder(folder)

        clips = pool.ImportMedia(valid_paths)
        if not clips:
            errors.append("ImportMedia returned no clips")
            return ImportResult(
                success=False, imported_count=0, clip_names=[], errors=errors
            )

        clip_names = []
        for clip in clips:
            try:
                clip_names.append(clip.GetName())
            except Exception:
                clip_names.append("(unknown)")

        return ImportResult(
            success=True,
            imported_count=len(clips),
            clip_names=clip_names,
            errors=errors,
        )

    def list_clips(self, folder_name: Optional[str] = None) -> List[ClipInfo]:
        """List clips in a media pool folder."""
        folder = self._find_folder(folder_name)
        clips = folder.GetClipList() or []

        results = []
        for clip in clips:
            props = clip.GetClipProperty() or {}
            results.append(ClipInfo(
                name=clip.GetName(),
                file_path=props.get("File Path", ""),
                duration=props.get("Duration", ""),
                resolution=props.get("Resolution", ""),
                fps=props.get("FPS", ""),
                codec=props.get("Video Codec", props.get("Audio Codec", "")),
                properties=props,
            ))

        return results

    def get_clip_info(self, clip_name: str,
                      folder_name: Optional[str] = None) -> ClipInfo:
        """Get detailed info for a specific clip."""
        folder = self._find_folder(folder_name)
        clips = folder.GetClipList() or []

        for clip in clips:
            if clip.GetName() == clip_name:
                props = clip.GetClipProperty() or {}
                return ClipInfo(
                    name=clip.GetName(),
                    file_path=props.get("File Path", ""),
                    duration=props.get("Duration", ""),
                    resolution=props.get("Resolution", ""),
                    fps=props.get("FPS", ""),
                    codec=props.get("Video Codec", props.get("Audio Codec", "")),
                    properties=props,
                )

        raise ResolveOperationError(
            f"Clip '{clip_name}' not found"
            + (f" in folder '{folder_name}'" if folder_name else " in root folder")
        )

    def list_folders(self, parent_name: Optional[str] = None) -> List[FolderInfo]:
        """List folders in the media pool."""
        parent = self._find_folder(parent_name)

        results = []
        # Include the parent itself
        clips = parent.GetClipList() or []
        subs = parent.GetSubFolderList() or []
        results.append(FolderInfo(
            name=parent.GetName(),
            clip_count=len(clips),
            subfolder_count=len(subs),
        ))

        # Include subfolders
        for sub in subs:
            sub_clips = sub.GetClipList() or []
            sub_subs = sub.GetSubFolderList() or []
            results.append(FolderInfo(
                name=sub.GetName(),
                clip_count=len(sub_clips),
                subfolder_count=len(sub_subs),
            ))

        return results

    # --- Timeline ---

    def list_timelines(self) -> List[TimelineInfo]:
        """List all timelines in the current project."""
        project = self._get_current_project()
        count = project.GetTimelineCount()
        current_tl = project.GetCurrentTimeline()
        current_name = current_tl.GetName() if current_tl else ""

        results = []
        for i in range(1, count + 1):
            tl = project.GetTimelineByIndex(i)
            if not tl:
                continue

            results.append(TimelineInfo(
                name=tl.GetName(),
                start_frame=tl.GetStartFrame(),
                end_frame=tl.GetEndFrame(),
                start_timecode=tl.GetStartTimecode() or "",
                video_track_count=tl.GetTrackCount("video"),
                audio_track_count=tl.GetTrackCount("audio"),
                subtitle_track_count=tl.GetTrackCount("subtitle"),
                current_timecode=tl.GetCurrentTimecode() if tl.GetName() == current_name else "",
            ))

        return results

    def create_timeline(self, name: str) -> TimelineInfo:
        """Create a new empty timeline."""
        if self.dry_run:
            logger.info("[DRY RUN] Would create timeline: %s", name)
            return TimelineInfo(name=name, start_frame=0, end_frame=0,
                                start_timecode="01:00:00:00",
                                video_track_count=1, audio_track_count=1,
                                subtitle_track_count=0, current_timecode="")

        pool = self._get_media_pool()
        tl = pool.CreateEmptyTimeline(name)
        if not tl:
            raise ResolveOperationError(
                f"Failed to create timeline '{name}'. Name may already exist."
            )

        return TimelineInfo(
            name=tl.GetName(),
            start_frame=tl.GetStartFrame(),
            end_frame=tl.GetEndFrame(),
            start_timecode=tl.GetStartTimecode() or "",
            video_track_count=tl.GetTrackCount("video"),
            audio_track_count=tl.GetTrackCount("audio"),
            subtitle_track_count=tl.GetTrackCount("subtitle"),
            current_timecode="",
        )

    def get_timeline_info(self, name: Optional[str] = None) -> TimelineInfo:
        """Get info for a timeline (current if name is None)."""
        project = self._get_current_project()

        if name:
            tl = self._find_timeline(project, name)
        else:
            tl = project.GetCurrentTimeline()
            if not tl:
                raise ResolveOperationError("No timeline is currently active.")

        return TimelineInfo(
            name=tl.GetName(),
            start_frame=tl.GetStartFrame(),
            end_frame=tl.GetEndFrame(),
            start_timecode=tl.GetStartTimecode() or "",
            video_track_count=tl.GetTrackCount("video"),
            audio_track_count=tl.GetTrackCount("audio"),
            subtitle_track_count=tl.GetTrackCount("subtitle"),
            current_timecode=tl.GetCurrentTimecode() or "",
        )

    def _find_timeline(self, project, name: str):
        """Find a timeline by name."""
        count = project.GetTimelineCount()
        names = []
        for i in range(1, count + 1):
            tl = project.GetTimelineByIndex(i)
            if tl:
                tl_name = tl.GetName()
                names.append(tl_name)
                if tl_name == name:
                    return tl

        raise ResolveTimelineNotFoundError(
            f"Timeline '{name}' not found.\n"
            f"Available timelines: {', '.join(names) if names else '(none)'}"
        )

    def add_clips_to_timeline(self, clip_names: List[str]) -> int:
        """Add clips from media pool to current timeline by name."""
        project = self._get_current_project()
        tl = project.GetCurrentTimeline()
        if not tl:
            raise ResolveOperationError("No timeline is currently active.")

        pool = project.GetMediaPool()
        if not pool:
            raise ResolveOperationError("Could not access the media pool.")

        if self.dry_run:
            logger.info("[DRY RUN] Would add %d clips to timeline", len(clip_names))
            return len(clip_names)

        # Find clips by name in media pool
        root = pool.GetRootFolder()
        found_clips = []
        for name in clip_names:
            clip = self._find_clip_in_folder(root, name)
            if clip:
                found_clips.append(clip)
            else:
                logger.warning("Clip not found in media pool: %s", name)

        if not found_clips:
            raise ResolveOperationError(
                "None of the specified clips were found in the media pool."
            )

        result = pool.AppendToTimeline(found_clips)
        return len(result) if result else 0

    def _find_clip_in_folder(self, folder, clip_name: str):
        """Recursively find a clip by name."""
        for clip in (folder.GetClipList() or []):
            if clip.GetName() == clip_name:
                return clip
        for sub in (folder.GetSubFolderList() or []):
            result = self._find_clip_in_folder(sub, clip_name)
            if result:
                return result
        return None

    def list_tracks(self, timeline_name: Optional[str] = None) -> List[TrackInfo]:
        """List all tracks in a timeline."""
        project = self._get_current_project()
        if timeline_name:
            tl = self._find_timeline(project, timeline_name)
        else:
            tl = project.GetCurrentTimeline()
            if not tl:
                raise ResolveOperationError("No timeline is currently active.")

        results = []
        for track_type in ["video", "audio", "subtitle"]:
            count = tl.GetTrackCount(track_type)
            for idx in range(1, count + 1):
                name = tl.GetTrackName(track_type, idx) or f"{track_type.capitalize()} {idx}"
                items = tl.GetItemListInTrack(track_type, idx) or []
                results.append(TrackInfo(
                    track_type=track_type,
                    track_index=idx,
                    name=name,
                    item_count=len(items),
                ))

        return results

    def list_timeline_items(self, track_type: Optional[str] = None,
                            track_index: Optional[int] = None,
                            timeline_name: Optional[str] = None) -> List[TimelineItemInfo]:
        """List items in timeline tracks."""
        project = self._get_current_project()
        if timeline_name:
            tl = self._find_timeline(project, timeline_name)
        else:
            tl = project.GetCurrentTimeline()
            if not tl:
                raise ResolveOperationError("No timeline is currently active.")

        results = []
        track_types = [track_type] if track_type else ["video", "audio", "subtitle"]

        for tt in track_types:
            count = tl.GetTrackCount(tt)
            indices = [track_index] if track_index else range(1, count + 1)

            for idx in indices:
                if idx < 1 or idx > count:
                    continue
                items = tl.GetItemListInTrack(tt, idx) or []
                for item in items:
                    try:
                        results.append(TimelineItemInfo(
                            name=item.GetName(),
                            start=int(item.GetStart()),
                            end=int(item.GetEnd()),
                            duration=int(item.GetDuration()),
                            track_type=tt,
                            track_index=idx,
                        ))
                    except Exception as e:
                        logger.warning("Error reading timeline item: %s", e)

        return results

    # --- Markers ---

    def list_markers(self, timeline_name: Optional[str] = None) -> List[MarkerInfo]:
        """List markers on a timeline."""
        project = self._get_current_project()
        if timeline_name:
            tl = self._find_timeline(project, timeline_name)
        else:
            tl = project.GetCurrentTimeline()
            if not tl:
                raise ResolveOperationError("No timeline is currently active.")

        markers = tl.GetMarkers() or {}
        results = []
        for frame_id, info in sorted(markers.items()):
            results.append(MarkerInfo(
                frame_id=float(frame_id),
                color=info.get("color", ""),
                name=info.get("name", ""),
                note=info.get("note", ""),
                duration=float(info.get("duration", 1.0)),
                custom_data=info.get("customData", ""),
            ))

        return results

    def add_marker(self, frame: int, color: str, name: str,
                   note: str = "", duration: int = 1,
                   timeline_name: Optional[str] = None) -> bool:
        """Add a marker to the current timeline."""
        # Validate color
        color_title = color.title()
        if color_title not in VALID_MARKER_COLORS:
            raise ResolveOperationError(
                f"Invalid marker color: '{color}'. "
                f"Valid colors: {', '.join(VALID_MARKER_COLORS)}"
            )

        project = self._get_current_project()
        if timeline_name:
            tl = self._find_timeline(project, timeline_name)
        else:
            tl = project.GetCurrentTimeline()
            if not tl:
                raise ResolveOperationError("No timeline is currently active.")

        if self.dry_run:
            logger.info("[DRY RUN] Would add %s marker '%s' at frame %d",
                        color_title, name, frame)
            return True

        result = tl.AddMarker(frame, color_title, name, note, duration)
        if not result:
            raise ResolveOperationError(
                f"Failed to add marker at frame {frame}. "
                "A marker may already exist at this position."
            )
        return True

    def delete_marker(self, frame: int,
                      timeline_name: Optional[str] = None) -> bool:
        """Delete a marker at a specific frame."""
        project = self._get_current_project()
        if timeline_name:
            tl = self._find_timeline(project, timeline_name)
        else:
            tl = project.GetCurrentTimeline()
            if not tl:
                raise ResolveOperationError("No timeline is currently active.")

        if self.dry_run:
            logger.info("[DRY RUN] Would delete marker at frame %d", frame)
            return True

        result = tl.DeleteMarkerAtFrame(frame)
        if not result:
            raise ResolveOperationError(
                f"Failed to delete marker at frame {frame}. "
                "No marker may exist at this position."
            )
        return True

    # --- Color ---

    def apply_lut(self, lut_path: str, node_index: int = 1,
                  timeline_name: Optional[str] = None) -> bool:
        """Apply a LUT to a node on the current clip."""
        if not os.path.exists(lut_path) and not lut_path.startswith("/"):
            # Allow relative LUT paths (Resolve searches its LUT directories)
            logger.info("LUT path '%s' treated as relative to Resolve LUT directories", lut_path)

        project = self._get_current_project()
        if timeline_name:
            tl = self._find_timeline(project, timeline_name)
        else:
            tl = project.GetCurrentTimeline()
            if not tl:
                raise ResolveOperationError("No timeline is currently active.")

        if self.dry_run:
            logger.info("[DRY RUN] Would apply LUT '%s' to node %d", lut_path, node_index)
            return True

        current_item = tl.GetCurrentVideoItem()
        if not current_item:
            raise ResolveOperationError(
                "No video item is currently selected on the timeline."
            )

        graph = current_item.GetNodeGraph()
        if not graph:
            raise ResolveOperationError("Could not access the node graph. Are you on the Color page?")

        num_nodes = graph.GetNumNodes()
        if node_index < 1 or node_index > num_nodes:
            raise ResolveOperationError(
                f"Node index {node_index} out of range. "
                f"Timeline has {num_nodes} nodes (1-based)."
            )

        result = graph.SetLUT(node_index, lut_path)
        if not result:
            raise ResolveOperationError(
                f"Failed to apply LUT. Ensure the LUT file is valid and "
                f"has been discovered by Resolve (Project > Refresh LUT List)."
            )
        return True

    def apply_grade(self, drx_path: str, grade_mode: int = 0) -> bool:
        """Apply a grade from a DRX file."""
        if not os.path.exists(drx_path):
            raise ResolveOperationError(f"DRX file not found: {drx_path}")

        project = self._get_current_project()
        tl = project.GetCurrentTimeline()
        if not tl:
            raise ResolveOperationError("No timeline is currently active.")

        if self.dry_run:
            logger.info("[DRY RUN] Would apply grade from '%s' (mode %d)", drx_path, grade_mode)
            return True

        current_item = tl.GetCurrentVideoItem()
        if not current_item:
            raise ResolveOperationError(
                "No video item is currently selected on the timeline."
            )

        graph = current_item.GetNodeGraph()
        if not graph:
            raise ResolveOperationError("Could not access the node graph.")

        result = graph.ApplyGradeFromDRX(drx_path, grade_mode)
        if not result:
            raise ResolveOperationError(f"Failed to apply grade from '{drx_path}'.")
        return True

    def export_lut(self, output_path: str, export_type: int = 0) -> bool:
        """Export a LUT from the current clip."""
        project = self._get_current_project()
        tl = project.GetCurrentTimeline()
        if not tl:
            raise ResolveOperationError("No timeline is currently active.")

        if self.dry_run:
            logger.info("[DRY RUN] Would export LUT to '%s'", output_path)
            return True

        current_item = tl.GetCurrentVideoItem()
        if not current_item:
            raise ResolveOperationError(
                "No video item is currently selected on the timeline."
            )

        result = current_item.ExportLUT(export_type, output_path)
        if not result:
            raise ResolveOperationError(f"Failed to export LUT to '{output_path}'.")
        return True

    # --- Render ---

    def list_render_presets(self) -> List[str]:
        """List available render presets."""
        project = self._get_current_project()
        return project.GetRenderPresetList() or []

    def add_render_job(self, preset: Optional[str] = None,
                       output_dir: Optional[str] = None,
                       custom_name: Optional[str] = None,
                       fmt: Optional[str] = None,
                       codec: Optional[str] = None) -> str:
        """Add a render job to the queue."""
        project = self._get_current_project()

        if self.dry_run:
            logger.info("[DRY RUN] Would add render job (preset=%s, output=%s)",
                        preset, output_dir)
            return "dry-run-job-id"

        if preset:
            loaded = project.LoadRenderPreset(preset)
            if not loaded:
                raise ResolveOperationError(
                    f"Render preset '{preset}' not found. "
                    f"Available presets: {', '.join(project.GetRenderPresetList() or [])}"
                )

        settings = {}
        if output_dir:
            settings["TargetDir"] = output_dir
        if custom_name:
            settings["CustomName"] = custom_name

        if settings:
            project.SetRenderSettings(settings)

        if fmt and codec:
            project.SetCurrentRenderFormatAndCodec(fmt, codec)

        job_id = project.AddRenderJob()
        if not job_id:
            raise ResolveOperationError("Failed to add render job.")
        return job_id

    def list_render_jobs(self) -> List[RenderJobInfo]:
        """List all render jobs in the queue."""
        project = self._get_current_project()
        jobs = project.GetRenderJobList() or []

        results = []
        for job in jobs:
            job_id = job.get("JobId", "")
            status_info = project.GetRenderJobStatus(job_id) if job_id else {}
            results.append(RenderJobInfo(
                job_id=job_id,
                timeline_name=job.get("TimelineName", ""),
                status=status_info.get("JobStatus", "Unknown"),
                completion=status_info.get("CompletionPercentage", "0"),
                render_settings=job,
            ))

        return results

    def start_rendering(self, wait: bool = False) -> bool:
        """Start rendering all queued jobs."""
        project = self._get_current_project()

        if self.dry_run:
            logger.info("[DRY RUN] Would start rendering")
            return True

        result = project.StartRendering()
        if not result:
            raise ResolveOperationError("Failed to start rendering.")

        if wait:
            print(f"  {DIM}Rendering in progress...{RESET}")
            while project.IsRenderingInProgress():
                # Print progress for each job
                jobs = project.GetRenderJobList() or []
                for job in jobs:
                    jid = job.get("JobId", "")
                    status = project.GetRenderJobStatus(jid) or {}
                    pct = status.get("CompletionPercentage", "0")
                    jstatus = status.get("JobStatus", "")
                    if jstatus == "Rendering":
                        print(f"\r  {CYAN}Rendering: {pct}%{RESET}  ", end="", flush=True)
                time.sleep(2)
            print(f"\r  {GREEN}Rendering complete!{RESET}      ")

        return True

    def get_render_status(self, job_id: Optional[str] = None) -> List[RenderJobInfo]:
        """Get render status for specific job or all jobs."""
        project = self._get_current_project()

        if job_id:
            status = project.GetRenderJobStatus(job_id) or {}
            return [RenderJobInfo(
                job_id=job_id,
                timeline_name="",
                status=status.get("JobStatus", "Unknown"),
                completion=status.get("CompletionPercentage", "0"),
                render_settings=status,
            )]

        return self.list_render_jobs()

    def stop_rendering(self) -> bool:
        """Stop any active render."""
        project = self._get_current_project()
        if self.dry_run:
            logger.info("[DRY RUN] Would stop rendering")
            return True
        project.StopRendering()
        return True

    def clear_render_queue(self) -> bool:
        """Clear all render jobs from the queue."""
        project = self._get_current_project()
        if self.dry_run:
            logger.info("[DRY RUN] Would clear render queue")
            return True
        return project.DeleteAllRenderJobs()


# ---------------------------------------------------------------------------
# CLI output helpers
# ---------------------------------------------------------------------------

def _visible_len(s: str) -> int:
    """Return the visible length of a string, stripping ANSI escape codes."""
    import re
    return len(re.sub(r'\033\[[0-9;]*m', '', str(s)))


def _format_table(headers: List[str], rows: List[List[str]]) -> str:
    """Format a simple text table."""
    if not rows:
        return "  (no results)"

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], _visible_len(cell))

    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    separator = "  ".join("-" * w for w in col_widths)

    lines = [f"  {header_line}", f"  {separator}"]
    for row in rows:
        parts = []
        for i in range(len(headers)):
            cell = str(row[i] if i < len(row) else "")
            # Pad accounting for invisible ANSI escape codes
            pad = col_widths[i] - _visible_len(cell)
            parts.append(cell + " " * max(0, pad))
        lines.append(f"  {'  '.join(parts)}")

    return "\n".join(lines)


def _json_output(data: Any) -> None:
    """Print JSON-formatted output."""
    print(json.dumps(data, indent=2, default=str))


def _dc_to_dict(obj) -> dict:
    """Convert a dataclass to a dict for JSON output."""
    return asdict(obj)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_status(client: ResolveClient, args: argparse.Namespace) -> int:
    """Show Resolve connection status."""
    status = client.get_status()

    if args.json:
        _json_output(_dc_to_dict(status))
        return 0

    print(f"\n{BOLD}DaVinci Resolve Status{RESET}\n")
    print(f"  {BOLD}Connected:{RESET}   {GREEN}Yes{RESET}" if status.connected
          else f"  {BOLD}Connected:{RESET}   {RED}No{RESET}")
    print(f"  {BOLD}Product:{RESET}     {status.product_name}")
    print(f"  {BOLD}Version:{RESET}     {status.version}")
    print(f"  {BOLD}Page:{RESET}        {status.current_page}")
    print(f"  {BOLD}Project:{RESET}     {status.current_project}")
    print(f"  {BOLD}Timeline:{RESET}    {status.current_timeline}")
    return 0


def cmd_page(client: ResolveClient, args: argparse.Namespace) -> int:
    """Get or set current page."""
    page_name = getattr(args, "page_name", None)

    if page_name:
        client.set_page(page_name)
        if args.json:
            _json_output({"page": page_name, "success": True})
        else:
            print(f"{GREEN}Switched to page: {page_name}{RESET}")
    else:
        page = client.get_page()
        if args.json:
            _json_output({"page": page})
        else:
            print(f"Current page: {BOLD}{page}{RESET}")
            print(f"{DIM}Valid pages: {', '.join(VALID_PAGES)}{RESET}")

    return 0


def cmd_project_list(client: ResolveClient, args: argparse.Namespace) -> int:
    """List projects."""
    projects = client.list_projects()

    if args.json:
        _json_output([_dc_to_dict(p) for p in projects])
        return 0

    print(f"\n{BOLD}Projects ({len(projects)}){RESET}\n")
    rows = []
    for p in projects:
        current_marker = f"{GREEN}*{RESET}" if p.is_current else " "
        res = f"{p.resolution_width}x{p.resolution_height}" if p.resolution_width else ""
        rows.append([
            current_marker,
            p.name,
            p.frame_rate or "",
            res,
            str(p.timeline_count) if p.is_current else "",
        ])
    print(_format_table(["", "Name", "FPS", "Resolution", "Timelines"], rows))
    return 0


def cmd_project_info(client: ResolveClient, args: argparse.Namespace) -> int:
    """Show project info."""
    name = getattr(args, "project_name", None)
    info = client.get_project_info(name)

    if args.json:
        _json_output(_dc_to_dict(info))
        return 0

    print(f"\n{BOLD}Project: {info.name}{RESET}\n")
    print(f"  {BOLD}Frame Rate:{RESET}    {info.frame_rate}")
    print(f"  {BOLD}Resolution:{RESET}    {info.resolution_width}x{info.resolution_height}")
    print(f"  {BOLD}Timelines:{RESET}     {info.timeline_count}")
    return 0


def cmd_project_create(client: ResolveClient, args: argparse.Namespace) -> int:
    """Create a new project."""
    info = client.create_project(
        args.name,
        fps=getattr(args, "fps", None),
        width=getattr(args, "width", None),
        height=getattr(args, "height", None),
    )

    if args.json:
        _json_output(_dc_to_dict(info))
    else:
        print(f"{GREEN}Created project: {info.name}{RESET}")
        print(f"  Frame Rate:  {info.frame_rate}")
        print(f"  Resolution:  {info.resolution_width}x{info.resolution_height}")

    return 0


def cmd_project_load(client: ResolveClient, args: argparse.Namespace) -> int:
    """Load a project."""
    info = client.load_project(args.name)

    if args.json:
        _json_output(_dc_to_dict(info))
    else:
        print(f"{GREEN}Loaded project: {info.name}{RESET}")
        print(f"  Frame Rate:  {info.frame_rate}")
        print(f"  Resolution:  {info.resolution_width}x{info.resolution_height}")
        print(f"  Timelines:   {info.timeline_count}")

    return 0


def cmd_project_save(client: ResolveClient, args: argparse.Namespace) -> int:
    """Save the current project."""
    result = client.save_project()

    if args.json:
        _json_output({"success": result})
    else:
        if result:
            print(f"{GREEN}Project saved successfully{RESET}")
        else:
            print(f"{RED}Failed to save project{RESET}")

    return 0 if result else 1


def cmd_project_settings(client: ResolveClient, args: argparse.Namespace) -> int:
    """Show project settings."""
    settings = client.get_project_settings()

    if args.json:
        _json_output(_dc_to_dict(settings))
        return 0

    print(f"\n{BOLD}Project Settings{RESET}\n")
    print(f"  {BOLD}Frame Rate:{RESET}    {settings.frame_rate}")
    print(f"  {BOLD}Resolution:{RESET}    {settings.resolution_width}x{settings.resolution_height}")

    if settings.all_settings:
        print(f"\n  {BOLD}All Settings:{RESET}")
        for key in sorted(settings.all_settings.keys()):
            val = settings.all_settings[key]
            print(f"    {DIM}{key}:{RESET} {val}")

    return 0


def cmd_project_set(client: ResolveClient, args: argparse.Namespace) -> int:
    """Set a project setting."""
    client.set_project_setting(args.key, args.value)

    if args.json:
        _json_output({"key": args.key, "value": args.value, "success": True})
    else:
        print(f"{GREEN}Set {args.key} = {args.value}{RESET}")

    return 0


def cmd_media_import(client: ResolveClient, args: argparse.Namespace) -> int:
    """Import media files."""
    result = client.import_media(
        args.files,
        folder_name=getattr(args, "folder", None),
    )

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0 if result.success else 1

    if result.success:
        print(f"{GREEN}Imported {result.imported_count} clip(s){RESET}")
        for name in result.clip_names:
            print(f"  - {name}")
    else:
        print(f"{RED}Import failed{RESET}")

    if result.errors:
        print(f"\n{YELLOW}Errors:{RESET}")
        for e in result.errors:
            print(f"  - {e}")

    return 0 if result.success else 1


def cmd_media_list(client: ResolveClient, args: argparse.Namespace) -> int:
    """List clips in media pool."""
    folder_name = getattr(args, "folder", None)
    clips = client.list_clips(folder_name)

    if args.json:
        _json_output([_dc_to_dict(c) for c in clips])
        return 0

    title = f"Media Pool" + (f" - {folder_name}" if folder_name else " - Root")
    print(f"\n{BOLD}{title} ({len(clips)} clips){RESET}\n")

    rows = []
    for c in clips:
        rows.append([c.name, c.duration, c.resolution, c.fps, c.codec])
    print(_format_table(["Name", "Duration", "Resolution", "FPS", "Codec"], rows))
    return 0


def cmd_media_info(client: ResolveClient, args: argparse.Namespace) -> int:
    """Show clip info."""
    clip = client.get_clip_info(args.clip_name)

    if args.json:
        _json_output(_dc_to_dict(clip))
        return 0

    print(f"\n{BOLD}Clip: {clip.name}{RESET}\n")
    print(f"  {BOLD}File:{RESET}       {clip.file_path}")
    print(f"  {BOLD}Duration:{RESET}   {clip.duration}")
    print(f"  {BOLD}Resolution:{RESET} {clip.resolution}")
    print(f"  {BOLD}FPS:{RESET}        {clip.fps}")
    print(f"  {BOLD}Codec:{RESET}      {clip.codec}")

    if clip.properties:
        print(f"\n  {BOLD}All Properties:{RESET}")
        for key in sorted(clip.properties.keys()):
            val = clip.properties[key]
            if val:
                print(f"    {DIM}{key}:{RESET} {val}")

    return 0


def cmd_media_folders(client: ResolveClient, args: argparse.Namespace) -> int:
    """List media pool folders."""
    folders = client.list_folders()

    if args.json:
        _json_output([_dc_to_dict(f) for f in folders])
        return 0

    print(f"\n{BOLD}Media Pool Folders{RESET}\n")
    rows = []
    for i, f in enumerate(folders):
        prefix = "" if i == 0 else "  "
        rows.append([prefix + f.name, str(f.clip_count), str(f.subfolder_count)])
    print(_format_table(["Folder", "Clips", "Subfolders"], rows))
    return 0


def cmd_timeline_list(client: ResolveClient, args: argparse.Namespace) -> int:
    """List timelines."""
    timelines = client.list_timelines()

    if args.json:
        _json_output([_dc_to_dict(t) for t in timelines])
        return 0

    print(f"\n{BOLD}Timelines ({len(timelines)}){RESET}\n")
    rows = []
    for t in timelines:
        duration_frames = t.end_frame - t.start_frame
        tracks = f"{t.video_track_count}V/{t.audio_track_count}A/{t.subtitle_track_count}S"
        rows.append([t.name, t.start_timecode, str(duration_frames), tracks])
    print(_format_table(["Name", "Start TC", "Frames", "Tracks"], rows))
    return 0


def cmd_timeline_create(client: ResolveClient, args: argparse.Namespace) -> int:
    """Create a new timeline."""
    info = client.create_timeline(args.name)

    if args.json:
        _json_output(_dc_to_dict(info))
    else:
        print(f"{GREEN}Created timeline: {info.name}{RESET}")
        print(f"  Tracks: {info.video_track_count}V / {info.audio_track_count}A")

    return 0


def cmd_timeline_info(client: ResolveClient, args: argparse.Namespace) -> int:
    """Show timeline info."""
    name = getattr(args, "timeline_name", None)
    info = client.get_timeline_info(name)

    if args.json:
        _json_output(_dc_to_dict(info))
        return 0

    print(f"\n{BOLD}Timeline: {info.name}{RESET}\n")
    print(f"  {BOLD}Start Frame:{RESET}    {info.start_frame}")
    print(f"  {BOLD}End Frame:{RESET}      {info.end_frame}")
    print(f"  {BOLD}Duration:{RESET}       {info.end_frame - info.start_frame} frames")
    print(f"  {BOLD}Start TC:{RESET}       {info.start_timecode}")
    print(f"  {BOLD}Current TC:{RESET}     {info.current_timecode or '(not active)'}")
    print(f"  {BOLD}Video Tracks:{RESET}   {info.video_track_count}")
    print(f"  {BOLD}Audio Tracks:{RESET}   {info.audio_track_count}")
    print(f"  {BOLD}Subtitle Tracks:{RESET} {info.subtitle_track_count}")
    return 0


def cmd_timeline_add_clips(client: ResolveClient, args: argparse.Namespace) -> int:
    """Add clips to the current timeline."""
    count = client.add_clips_to_timeline(args.clips)

    if args.json:
        _json_output({"added_count": count, "clips": args.clips})
    else:
        print(f"{GREEN}Added {count} clip(s) to timeline{RESET}")

    return 0


def cmd_timeline_tracks(client: ResolveClient, args: argparse.Namespace) -> int:
    """List timeline tracks."""
    tracks = client.list_tracks()

    if args.json:
        _json_output([_dc_to_dict(t) for t in tracks])
        return 0

    print(f"\n{BOLD}Timeline Tracks ({len(tracks)}){RESET}\n")
    rows = []
    for t in tracks:
        rows.append([
            t.track_type.capitalize(),
            str(t.track_index),
            t.name,
            str(t.item_count),
        ])
    print(_format_table(["Type", "Index", "Name", "Items"], rows))
    return 0


def cmd_timeline_items(client: ResolveClient, args: argparse.Namespace) -> int:
    """List timeline items."""
    track_type = getattr(args, "track_type", None)
    track_index = getattr(args, "track_index", None)
    if track_index is not None:
        track_index = int(track_index)

    items = client.list_timeline_items(track_type=track_type, track_index=track_index)

    if args.json:
        _json_output([_dc_to_dict(item) for item in items])
        return 0

    print(f"\n{BOLD}Timeline Items ({len(items)}){RESET}\n")
    rows = []
    for item in items:
        rows.append([
            item.name,
            item.track_type.capitalize(),
            str(item.track_index),
            str(item.start),
            str(item.end),
            str(item.duration),
        ])
    print(_format_table(["Name", "Type", "Track", "Start", "End", "Duration"], rows))
    return 0


def cmd_marker_list(client: ResolveClient, args: argparse.Namespace) -> int:
    """List markers."""
    timeline_name = getattr(args, "timeline", None)
    markers = client.list_markers(timeline_name=timeline_name)

    if args.json:
        _json_output([_dc_to_dict(m) for m in markers])
        return 0

    print(f"\n{BOLD}Markers ({len(markers)}){RESET}\n")
    rows = []
    for m in markers:
        rows.append([
            str(int(m.frame_id)),
            m.color,
            m.name,
            m.note,
            str(int(m.duration)),
        ])
    print(_format_table(["Frame", "Color", "Name", "Note", "Duration"], rows))
    return 0


def cmd_marker_add(client: ResolveClient, args: argparse.Namespace) -> int:
    """Add a marker."""
    note = getattr(args, "note", "") or ""
    duration = getattr(args, "duration", 1) or 1

    client.add_marker(
        frame=int(args.frame),
        color=args.color,
        name=args.marker_name,
        note=note,
        duration=int(duration),
    )

    if args.json:
        _json_output({
            "frame": int(args.frame),
            "color": args.color,
            "name": args.marker_name,
            "note": note,
            "duration": int(duration),
            "success": True,
        })
    else:
        print(f"{GREEN}Added {args.color} marker '{args.marker_name}' at frame {args.frame}{RESET}")

    return 0


def cmd_marker_delete(client: ResolveClient, args: argparse.Namespace) -> int:
    """Delete a marker."""
    client.delete_marker(int(args.frame))

    if args.json:
        _json_output({"frame": int(args.frame), "success": True})
    else:
        print(f"{GREEN}Deleted marker at frame {args.frame}{RESET}")

    return 0


def cmd_color_apply_lut(client: ResolveClient, args: argparse.Namespace) -> int:
    """Apply a LUT."""
    node = getattr(args, "node", 1) or 1
    client.apply_lut(args.lut_path, node_index=int(node))

    if args.json:
        _json_output({"lut_path": args.lut_path, "node": int(node), "success": True})
    else:
        print(f"{GREEN}Applied LUT '{args.lut_path}' to node {node}{RESET}")

    return 0


def cmd_color_apply_grade(client: ResolveClient, args: argparse.Namespace) -> int:
    """Apply a grade from DRX file."""
    mode = getattr(args, "mode", 0) or 0
    client.apply_grade(args.drx_path, grade_mode=int(mode))

    if args.json:
        _json_output({"drx_path": args.drx_path, "mode": int(mode), "success": True})
    else:
        modes = {0: "No keyframes", 1: "Source Timecode aligned", 2: "Start Frames aligned"}
        mode_name = modes.get(int(mode), str(mode))
        print(f"{GREEN}Applied grade from '{args.drx_path}' (mode: {mode_name}){RESET}")

    return 0


def cmd_color_export_lut(client: ResolveClient, args: argparse.Namespace) -> int:
    """Export a LUT."""
    export_type = getattr(args, "type", 0) or 0
    client.export_lut(args.output, export_type=int(export_type))

    if args.json:
        _json_output({"output": args.output, "type": int(export_type), "success": True})
    else:
        print(f"{GREEN}Exported LUT to '{args.output}'{RESET}")

    return 0


def cmd_render_presets(client: ResolveClient, args: argparse.Namespace) -> int:
    """List render presets."""
    presets = client.list_render_presets()

    if args.json:
        _json_output(presets)
        return 0

    print(f"\n{BOLD}Render Presets ({len(presets)}){RESET}\n")
    for i, p in enumerate(presets, 1):
        print(f"  {i}. {p}")
    return 0


def cmd_render_add(client: ResolveClient, args: argparse.Namespace) -> int:
    """Add a render job."""
    job_id = client.add_render_job(
        preset=getattr(args, "preset", None),
        output_dir=getattr(args, "output", None),
        custom_name=getattr(args, "name", None),
        fmt=getattr(args, "format", None),
        codec=getattr(args, "codec", None),
    )

    if args.json:
        _json_output({"job_id": job_id, "success": True})
    else:
        print(f"{GREEN}Added render job: {job_id}{RESET}")

    return 0


def cmd_render_list(client: ResolveClient, args: argparse.Namespace) -> int:
    """List render jobs."""
    jobs = client.list_render_jobs()

    if args.json:
        _json_output([_dc_to_dict(j) for j in jobs])
        return 0

    print(f"\n{BOLD}Render Queue ({len(jobs)} jobs){RESET}\n")
    rows = []
    for j in jobs:
        status_color = GREEN if j.status == "Complete" else CYAN if j.status == "Rendering" else ""
        status_reset = RESET if status_color else ""
        rows.append([
            j.job_id,
            j.timeline_name,
            f"{status_color}{j.status}{status_reset}",
            f"{j.completion}%",
        ])
    print(_format_table(["Job ID", "Timeline", "Status", "Progress"], rows))
    return 0


def cmd_render_start(client: ResolveClient, args: argparse.Namespace) -> int:
    """Start rendering."""
    wait = getattr(args, "wait", False)
    client.start_rendering(wait=wait)

    if args.json:
        _json_output({"success": True, "waited": wait})
    else:
        if not wait:
            print(f"{GREEN}Rendering started{RESET}")

    return 0


def cmd_render_status(client: ResolveClient, args: argparse.Namespace) -> int:
    """Get render status."""
    job_id = getattr(args, "job_id", None)
    jobs = client.get_render_status(job_id)

    if args.json:
        _json_output([_dc_to_dict(j) for j in jobs])
        return 0

    for j in jobs:
        print(f"  Job {j.job_id}: {j.status} ({j.completion}%)")
    return 0


def cmd_render_stop(client: ResolveClient, args: argparse.Namespace) -> int:
    """Stop rendering."""
    client.stop_rendering()

    if args.json:
        _json_output({"success": True})
    else:
        print(f"{GREEN}Rendering stopped{RESET}")

    return 0


def cmd_render_clear(client: ResolveClient, args: argparse.Namespace) -> int:
    """Clear render queue."""
    result = client.clear_render_queue()

    if args.json:
        _json_output({"success": result})
    else:
        if result:
            print(f"{GREEN}Render queue cleared{RESET}")
        else:
            print(f"{RED}Failed to clear render queue{RESET}")

    return 0 if result else 1


# ---------------------------------------------------------------------------
# CLI Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="davinci_resolve",
        description=(
            "DaVinci Resolve Scripting CLI\n"
            "Control DaVinci Resolve programmatically for project management,\n"
            "media pool operations, timeline editing, color grading, and rendering."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --mock status\n"
            "  %(prog)s --mock --json project list\n"
            "  %(prog)s project create 'New Project' --fps 24 --width 3840 --height 2160\n"
            "  %(prog)s media import ~/Footage/clip1.mov ~/Footage/clip2.mp4\n"
            "  %(prog)s timeline create 'Main Edit'\n"
            "  %(prog)s marker add 86400 Green 'In Point' --note 'Start here'\n"
            "  %(prog)s render add --preset 'H.264 Master' --output ~/Movies/\n"
            "  %(prog)s render start --wait\n"
            "\n"
            "DaVinci Resolve must be running for live commands.\n"
            "Use --mock for testing without Resolve running.\n"
        ),
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview write operations without making changes",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Use mock data (no Resolve connection required)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command group")

    # --- status ---
    subparsers.add_parser("status", help="Show Resolve connection status and current state")

    # --- page ---
    p_page = subparsers.add_parser("page", help="Get or set the current page")
    p_page.add_argument("page_name", nargs="?", default=None,
                        help=f"Page to switch to ({', '.join(VALID_PAGES)})")

    # --- project ---
    p_project = subparsers.add_parser("project", help="Project management")
    project_sub = p_project.add_subparsers(dest="project_command")

    project_sub.add_parser("list", help="List all projects")

    p_pi = project_sub.add_parser("info", help="Show project info")
    p_pi.add_argument("project_name", nargs="?", default=None, help="Project name (default: current)")

    p_pc = project_sub.add_parser("create", help="Create a new project")
    p_pc.add_argument("name", help="Project name")
    p_pc.add_argument("--fps", help="Timeline frame rate (e.g. 24, 30, 60)")
    p_pc.add_argument("--width", help="Timeline resolution width")
    p_pc.add_argument("--height", help="Timeline resolution height")

    p_pl = project_sub.add_parser("load", help="Load a project")
    p_pl.add_argument("name", help="Project name to load")

    project_sub.add_parser("save", help="Save the current project")

    project_sub.add_parser("settings", help="Show all project settings")

    p_ps = project_sub.add_parser("set", help="Set a project setting")
    p_ps.add_argument("key", help="Setting key (e.g. timelineFrameRate)")
    p_ps.add_argument("value", help="Setting value")

    # --- media ---
    p_media = subparsers.add_parser("media", help="Media pool operations")
    media_sub = p_media.add_subparsers(dest="media_command")

    p_mi = media_sub.add_parser("import", help="Import media files")
    p_mi.add_argument("files", nargs="+", help="File paths to import")
    p_mi.add_argument("--folder", "-f", help="Target folder in media pool")

    p_ml = media_sub.add_parser("list", help="List clips in media pool")
    p_ml.add_argument("--folder", "-f", help="Folder to list (default: root)")

    p_mc = media_sub.add_parser("info", help="Show clip details")
    p_mc.add_argument("clip_name", help="Clip name")

    media_sub.add_parser("folders", help="List media pool folder structure")

    # --- timeline ---
    p_timeline = subparsers.add_parser("timeline", help="Timeline operations")
    timeline_sub = p_timeline.add_subparsers(dest="timeline_command")

    timeline_sub.add_parser("list", help="List all timelines")

    p_tc = timeline_sub.add_parser("create", help="Create a new timeline")
    p_tc.add_argument("name", help="Timeline name")

    p_ti = timeline_sub.add_parser("info", help="Show timeline info")
    p_ti.add_argument("timeline_name", nargs="?", default=None,
                      help="Timeline name (default: current)")

    p_tac = timeline_sub.add_parser("add-clips", help="Add clips to current timeline")
    p_tac.add_argument("clips", nargs="+", help="Clip names from media pool")

    timeline_sub.add_parser("tracks", help="List timeline tracks")

    p_tit = timeline_sub.add_parser("items", help="List timeline items")
    p_tit.add_argument("--track-type", "-t", choices=["video", "audio", "subtitle"],
                       help="Filter by track type")
    p_tit.add_argument("--track-index", "-i", type=int, help="Filter by track index (1-based)")

    # --- marker ---
    p_marker = subparsers.add_parser("marker", help="Marker management")
    marker_sub = p_marker.add_subparsers(dest="marker_command")

    p_mkl = marker_sub.add_parser("list", help="List markers")
    p_mkl.add_argument("--timeline", "-t", help="Timeline name (default: current)")

    p_mka = marker_sub.add_parser("add", help="Add a marker")
    p_mka.add_argument("frame", type=int, help="Frame position")
    p_mka.add_argument("color", help=f"Marker color ({', '.join(VALID_MARKER_COLORS[:6])}...)")
    p_mka.add_argument("marker_name", help="Marker name")
    p_mka.add_argument("--note", "-n", default="", help="Marker note")
    p_mka.add_argument("--duration", "-d", type=int, default=1, help="Marker duration in frames")

    p_mkd = marker_sub.add_parser("delete", help="Delete a marker")
    p_mkd.add_argument("frame", type=int, help="Frame position of marker to delete")

    # --- color ---
    p_color = subparsers.add_parser("color", help="Color grading operations")
    color_sub = p_color.add_subparsers(dest="color_command")

    p_cal = color_sub.add_parser("apply-lut", help="Apply a LUT to a node")
    p_cal.add_argument("lut_path", help="Path to LUT file (.cube, .3dl, etc.)")
    p_cal.add_argument("--node", "-n", type=int, default=1, help="Node index (1-based, default: 1)")

    p_cag = color_sub.add_parser("apply-grade", help="Apply a grade from DRX file")
    p_cag.add_argument("drx_path", help="Path to DRX file")
    p_cag.add_argument("--mode", "-m", type=int, default=0,
                       help="Grade mode: 0=No keyframes, 1=Source TC aligned, 2=Start Frames aligned")

    p_cel = color_sub.add_parser("export-lut", help="Export a LUT from current clip")
    p_cel.add_argument("output", help="Output file path")
    p_cel.add_argument("--type", "-t", type=int, default=0,
                       help="Export type (LUT size enum)")

    # --- render ---
    p_render = subparsers.add_parser("render", help="Render queue management")
    render_sub = p_render.add_subparsers(dest="render_command")

    render_sub.add_parser("presets", help="List available render presets")

    p_ra = render_sub.add_parser("add", help="Add a render job to the queue")
    p_ra.add_argument("--preset", "-p", help="Render preset name")
    p_ra.add_argument("--output", "-o", help="Output directory")
    p_ra.add_argument("--name", "-n", help="Custom output filename")
    p_ra.add_argument("--format", "-f", help="Render format (e.g. mp4, mov)")
    p_ra.add_argument("--codec", "-c", help="Render codec (e.g. H264, ProRes422HQ)")

    render_sub.add_parser("list", help="List render jobs in queue")

    p_rs = render_sub.add_parser("start", help="Start rendering")
    p_rs.add_argument("--wait", "-w", action="store_true",
                      help="Wait for rendering to complete (blocking)")

    p_rst = render_sub.add_parser("status", help="Get render job status")
    p_rst.add_argument("job_id", nargs="?", default=None, help="Job ID (default: all)")

    render_sub.add_parser("stop", help="Stop active render")
    render_sub.add_parser("clear", help="Clear all render jobs from queue")

    return parser


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

# Top-level commands
TOP_COMMANDS = {
    "status": cmd_status,
    "page": cmd_page,
}

# Nested command dispatch tables
PROJECT_COMMANDS = {
    "list": cmd_project_list,
    "info": cmd_project_info,
    "create": cmd_project_create,
    "load": cmd_project_load,
    "save": cmd_project_save,
    "settings": cmd_project_settings,
    "set": cmd_project_set,
}

MEDIA_COMMANDS = {
    "import": cmd_media_import,
    "list": cmd_media_list,
    "info": cmd_media_info,
    "folders": cmd_media_folders,
}

TIMELINE_COMMANDS = {
    "list": cmd_timeline_list,
    "create": cmd_timeline_create,
    "info": cmd_timeline_info,
    "add-clips": cmd_timeline_add_clips,
    "tracks": cmd_timeline_tracks,
    "items": cmd_timeline_items,
}

MARKER_COMMANDS = {
    "list": cmd_marker_list,
    "add": cmd_marker_add,
    "delete": cmd_marker_delete,
}

COLOR_COMMANDS = {
    "apply-lut": cmd_color_apply_lut,
    "apply-grade": cmd_color_apply_grade,
    "export-lut": cmd_color_export_lut,
}

RENDER_COMMANDS = {
    "presets": cmd_render_presets,
    "add": cmd_render_add,
    "list": cmd_render_list,
    "start": cmd_render_start,
    "status": cmd_render_status,
    "stop": cmd_render_stop,
    "clear": cmd_render_clear,
}

NESTED_DISPATCH = {
    "project": ("project_command", PROJECT_COMMANDS),
    "media": ("media_command", MEDIA_COMMANDS),
    "timeline": ("timeline_command", TIMELINE_COMMANDS),
    "marker": ("marker_command", MARKER_COMMANDS),
    "color": ("color_command", COLOR_COMMANDS),
    "render": ("render_command", RENDER_COMMANDS),
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Create connection
    if args.mock:
        connection = MockResolveConnection()
    else:
        connection = ResolveConnection()

    client = ResolveClient(connection, dry_run=args.dry_run)

    # Resolve the command handler
    handler = None

    # Check top-level commands
    if args.command in TOP_COMMANDS:
        handler = TOP_COMMANDS[args.command]

    # Check nested commands
    elif args.command in NESTED_DISPATCH:
        sub_attr, cmd_table = NESTED_DISPATCH[args.command]
        sub_cmd = getattr(args, sub_attr, None)
        if not sub_cmd:
            # Print help for the command group
            # Re-parse to get the subparser
            parser.parse_args([args.command, "--help"])
            return 1
        handler = cmd_table.get(sub_cmd)

    if not handler:
        parser.print_help()
        return 1

    try:
        return handler(client, args)
    except ResolveNotRunningError as e:
        print(f"\n{RED}DaVinci Resolve is not running.{RESET}\n")
        print(f"{e}")
        print(f"\n{YELLOW}Launch DaVinci Resolve and try again, "
              f"or use --mock for testing.{RESET}")
        return 1
    except ResolveScriptingDisabledError as e:
        print(f"\n{RED}Scripting is disabled in DaVinci Resolve.{RESET}\n")
        print(f"{e}")
        return 1
    except ResolveProjectNotFoundError as e:
        print(f"\n{RED}Project not found.{RESET}\n")
        print(f"{e}")
        return 1
    except ResolveTimelineNotFoundError as e:
        print(f"\n{RED}Timeline not found.{RESET}\n")
        print(f"{e}")
        return 1
    except ResolveOperationError as e:
        print(f"\n{RED}Operation failed: {e}{RESET}")
        return 1
    except ResolveConnectionError as e:
        print(f"\n{RED}Connection error: {e}{RESET}")
        return 1
    except ResolveError as e:
        print(f"\n{RED}Resolve error: {e}{RESET}")
        return 1
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted{RESET}")
        return 130
    except Exception as e:
        logger.debug("Unhandled exception", exc_info=True)
        print(f"\n{RED}Error: {e}{RESET}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
