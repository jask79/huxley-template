#!/usr/bin/env python3
"""
OBS Studio CLI for Huxley

Controls OBS Studio via WebSocket v5 protocol for programmatic control of:
- Scene management (list, switch, create, remove)
- Scene items (add, remove, show/hide, transform)
- Input/source management (create, remove, settings, audio)
- Streaming (start, stop, toggle, captions)
- Recording (start, stop, pause, resume, split, chapters)
- Virtual camera and replay buffer
- Transitions, filters, and configuration
- Studio mode and UI controls

OBS Studio must be running with WebSocket server enabled for live commands.
Use --mock for testing without OBS. Use --dry-run to preview write operations.

Requirements:
    - OBS Studio with WebSocket server enabled (Tools > WebSocket Server Settings)
    - Python >= 3.8
    - websockets >= 12.0
"""

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, InvalidURI
except ImportError:
    print("Error: websockets package required. Install with: pip install websockets", file=sys.stderr)
    sys.exit(1)

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
# OBS WebSocket v5 OpCodes
# ---------------------------------------------------------------------------
OP_HELLO = 0
OP_IDENTIFY = 1
OP_IDENTIFIED = 2
OP_REQUEST = 6
OP_REQUEST_RESPONSE = 7

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OBSError(Exception):
    """Base exception for all OBS CLI errors."""

class OBSConnectionError(OBSError):
    """Failed to connect to OBS WebSocket."""

class OBSAuthError(OBSConnectionError):
    """Authentication failed."""

class OBSNotRunningError(OBSConnectionError):
    """OBS is not running or WebSocket is not enabled."""

class OBSRequestError(OBSError):
    """An OBS request failed."""
    def __init__(self, message: str, code: int = 0, comment: str = ""):
        super().__init__(message)
        self.code = code
        self.comment = comment

class OBSTimeoutError(OBSError):
    """Request timed out."""


# ---------------------------------------------------------------------------
# Structured result types
# ---------------------------------------------------------------------------

@dataclass
class VersionInfo:
    obs_version: str
    websocket_version: str
    rpc_version: int
    platform: str
    platform_description: str
    available_requests: List[str]
    supported_image_formats: List[str]

@dataclass
class StreamStatus:
    active: bool
    reconnecting: bool
    timecode: str
    duration: int
    congestion: float
    bytes: int
    skipped_frames: int
    total_frames: int

@dataclass
class RecordStatus:
    active: bool
    paused: bool
    timecode: str
    duration: int
    bytes: int


# ---------------------------------------------------------------------------
# OBSConnection – WebSocket v5 transport layer
# ---------------------------------------------------------------------------

class OBSConnection:
    """Manages WebSocket connection to OBS, including v5 authentication."""

    def __init__(self, url: str = "ws://localhost:4455",
                 password: Optional[str] = None, timeout: float = 10.0):
        self._url = url
        self._password = password
        self._timeout = timeout
        self._ws = None
        self._identified = False
        self._request_counter = 0

    async def connect(self) -> None:
        """Connect and authenticate with OBS WebSocket v5."""
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(self._url, max_size=2**24),
                timeout=self._timeout
            )
        except asyncio.TimeoutError:
            raise OBSNotRunningError(
                f"Connection timed out to {self._url}. "
                "Is OBS running with WebSocket server enabled?"
            )
        except OSError as e:
            if "Connection refused" in str(e) or "ECONNREFUSED" in str(e):
                raise OBSNotRunningError(
                    f"Connection refused at {self._url}. "
                    "OBS is not running or WebSocket server is disabled."
                )
            raise OBSConnectionError(f"Failed to connect: {e}")
        except InvalidURI:
            raise OBSConnectionError(f"Invalid WebSocket URL: {self._url}")

        # Handshake — close WebSocket on any failure
        try:
            # Receive Hello (op=0)
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=self._timeout)
            except asyncio.TimeoutError:
                raise OBSConnectionError("Timed out waiting for Hello from OBS")

            hello = json.loads(raw)
            if hello.get("op") != OP_HELLO:
                raise OBSConnectionError(f"Expected Hello (op=0), got op={hello.get('op')}")

            hello_data = hello["d"]
            logger.debug(
                "OBS v%s, WebSocket v%s, RPC v%d",
                hello_data.get("obsStudioVersion"),
                hello_data.get("obsWebSocketVersion"),
                hello_data.get("rpcVersion", 1),
            )

            # Build Identify message (op=1)
            identify_data: Dict[str, Any] = {
                "rpcVersion": hello_data.get("rpcVersion", 1),
                "eventSubscriptions": 0,  # CLI doesn't need events
            }

            # Handle authentication if required
            auth_info = hello_data.get("authentication")
            if auth_info:
                if not self._password:
                    raise OBSAuthError(
                        "OBS requires a password but none was provided. "
                        "Set OBS_WEBSOCKET_PASSWORD or use --password."
                    )
                identify_data["authentication"] = self._generate_auth(
                    self._password, auth_info["salt"], auth_info["challenge"]
                )

            await self._ws.send(json.dumps({"op": OP_IDENTIFY, "d": identify_data}))

            # Receive Identified (op=2)
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=self._timeout)
            except asyncio.TimeoutError:
                raise OBSAuthError("Timed out waiting for Identified – authentication may have failed")

            identified = json.loads(raw)
            if identified.get("op") != OP_IDENTIFIED:
                raise OBSAuthError(
                    f"Expected Identified (op=2), got op={identified.get('op')}. "
                    "Authentication may have failed."
                )

            self._identified = True
            logger.debug("Successfully identified with OBS WebSocket")
        except Exception:
            await self._ws.close()
            self._ws = None
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None
            self._identified = False

    async def send_request(self, request_type: str,
                           request_data: Optional[Dict] = None,
                           timeout: float = 10.0) -> Dict:
        """Send a request and return the response data."""
        if not self._ws or not self._identified:
            raise OBSConnectionError("Not connected to OBS")

        self._request_counter += 1
        request_id = str(self._request_counter)

        msg: Dict[str, Any] = {
            "op": OP_REQUEST,
            "d": {
                "requestType": request_type,
                "requestId": request_id,
            }
        }
        if request_data:
            msg["d"]["requestData"] = request_data

        await self._ws.send(json.dumps(msg))

        # Wait for matching response
        try:
            while True:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
                resp = json.loads(raw)
                if resp.get("op") != OP_REQUEST_RESPONSE:
                    continue  # skip events
                if resp["d"].get("requestId") != request_id:
                    continue  # skip non-matching responses
                break
        except asyncio.TimeoutError:
            raise OBSTimeoutError(f"Request {request_type} timed out after {timeout}s")
        except ConnectionClosed:
            raise OBSConnectionError("WebSocket connection closed during request")

        status = resp["d"].get("requestStatus", {})
        if not status.get("result", False):
            raise OBSRequestError(
                f"{request_type} failed: {status.get('comment', 'Unknown error')}",
                code=status.get("code", 0),
                comment=status.get("comment", ""),
            )

        return resp["d"].get("responseData") or {}

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._identified

    @staticmethod
    def _generate_auth(password: str, salt: str, challenge: str) -> str:
        """OBS WebSocket v5 SHA-256 authentication."""
        secret_hash = hashlib.sha256((password + salt).encode("utf-8")).digest()
        secret = base64.b64encode(secret_hash).decode("utf-8")
        auth_hash = hashlib.sha256((secret + challenge).encode("utf-8")).digest()
        return base64.b64encode(auth_hash).decode("utf-8")


# ---------------------------------------------------------------------------
# MockOBSConnection – for testing without OBS
# ---------------------------------------------------------------------------

class MockOBSConnection:
    """Returns realistic fake data for all request types."""

    def __init__(self):
        self._identified = True
        self.is_connected = True

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def send_request(self, request_type: str,
                           request_data: Optional[Dict] = None,
                           timeout: float = 10.0) -> Dict:
        """Return mock data for known request types."""
        mock_data = {
            "GetVersion": {
                "obsVersion": "31.0.0",
                "obsWebSocketVersion": "5.5.4",
                "rpcVersion": 1,
                "platform": "macos",
                "platformDescription": "macOS 15.3",
                "availableRequests": ["GetVersion", "GetStats", "GetSceneList"],
                "supportedImageFormats": ["png", "jpg", "bmp"],
            },
            "GetStats": {
                "cpuUsage": 4.2, "memoryUsage": 512.8,
                "availableDiskSpace": 150000.0,
                "activeFps": 60.0, "averageFrameRenderTime": 2.1,
                "renderSkippedFrames": 0, "renderTotalFrames": 108000,
                "outputSkippedFrames": 0, "outputTotalFrames": 108000,
                "webSocketSessionIncomingMessages": 42,
                "webSocketSessionOutgoingMessages": 42,
            },
            "GetSceneList": {
                "currentProgramSceneName": "Main Scene",
                "currentPreviewSceneName": "",
                "scenes": [
                    {"sceneIndex": 0, "sceneName": "Main Scene"},
                    {"sceneIndex": 1, "sceneName": "BRB Screen"},
                    {"sceneIndex": 2, "sceneName": "Starting Soon"},
                ],
            },
            "GetCurrentProgramScene": {"currentProgramSceneName": "Main Scene"},
            "GetCurrentPreviewScene": {"currentPreviewSceneName": "BRB Screen"},
            "GetSceneItemList": {
                "sceneItems": [
                    {"sceneItemId": 1, "sourceName": "Webcam", "sceneItemEnabled": True,
                     "sceneItemIndex": 0, "inputKind": "av_capture_input_v2"},
                    {"sceneItemId": 2, "sourceName": "Display Capture", "sceneItemEnabled": True,
                     "sceneItemIndex": 1, "inputKind": "screen_capture"},
                    {"sceneItemId": 3, "sourceName": "Mic/Aux", "sceneItemEnabled": True,
                     "sceneItemIndex": 2, "inputKind": "coreaudio_input_capture"},
                ],
            },
            "GetSceneItemId": {"sceneItemId": 1},
            "GetSceneItemTransform": {
                "sceneItemTransform": {
                    "positionX": 0.0, "positionY": 0.0,
                    "rotation": 0.0, "scaleX": 1.0, "scaleY": 1.0,
                    "cropTop": 0, "cropBottom": 0, "cropLeft": 0, "cropRight": 0,
                    "sourceWidth": 1920, "sourceHeight": 1080,
                    "width": 1920.0, "height": 1080.0,
                }
            },
            "GetInputList": {
                "inputs": [
                    {"inputName": "Webcam", "inputKind": "av_capture_input_v2", "inputUuid": "a1b2"},
                    {"inputName": "Display Capture", "inputKind": "screen_capture", "inputUuid": "c3d4"},
                    {"inputName": "Mic/Aux", "inputKind": "coreaudio_input_capture", "inputUuid": "e5f6"},
                    {"inputName": "Desktop Audio", "inputKind": "coreaudio_output_capture", "inputUuid": "g7h8"},
                    {"inputName": "Browser Source", "inputKind": "browser_source", "inputUuid": "i9j0"},
                ],
            },
            "GetInputKindList": {
                "inputKinds": [
                    "av_capture_input_v2", "screen_capture", "browser_source",
                    "coreaudio_input_capture", "coreaudio_output_capture",
                    "image_source", "color_source_v3", "text_ft2_source_v2",
                ],
            },
            "GetSpecialInputs": {
                "desktop1": "Desktop Audio", "desktop2": None,
                "mic1": "Mic/Aux", "mic2": None, "mic3": None, "mic4": None,
            },
            "GetInputSettings": {"inputSettings": {"device_id": "default"}, "inputKind": "av_capture_input_v2"},
            "GetInputDefaultSettings": {"defaultInputSettings": {}},
            "GetInputMute": {"inputMuted": False},
            "ToggleInputMute": {"inputMuted": True},
            "GetInputVolume": {"inputVolumeDb": 0.0, "inputVolumeMul": 1.0},
            "GetInputAudioBalance": {"inputAudioBalance": 0.5},
            "GetInputAudioSyncOffset": {"inputAudioSyncOffset": 0},
            "GetInputAudioMonitorType": {"monitorType": "OBS_MONITORING_TYPE_NONE"},
            "GetSourceActive": {"videoActive": True, "videoShowing": True},
            "GetStreamStatus": {
                "outputActive": False, "outputReconnecting": False,
                "outputTimecode": "00:00:00.000", "outputDuration": 0,
                "outputCongestion": 0.0, "outputBytes": 0,
                "outputSkippedFrames": 0, "outputTotalFrames": 0,
            },
            "ToggleStream": {"outputActive": True},
            "GetRecordStatus": {
                "outputActive": False, "outputPaused": False,
                "outputTimecode": "00:00:00.000", "outputDuration": 0,
                "outputBytes": 0,
            },
            "ToggleRecord": {"outputActive": True},
            "StopRecord": {"outputPath": "{{HOME_DIR}}/Movies/recording.mkv"},
            "GetVirtualCamStatus": {"outputActive": False},
            "ToggleVirtualCam": {"outputActive": True},
            "GetReplayBufferStatus": {"outputActive": False},
            "ToggleReplayBuffer": {"outputActive": True},
            "GetLastReplayBufferReplay": {"savedReplayPath": "{{HOME_DIR}}/Movies/replay.mkv"},
            "GetOutputList": {
                "outputs": [
                    {"outputName": "adv_stream", "outputKind": "rtmp_output", "outputActive": False},
                    {"outputName": "adv_file_output", "outputKind": "ffmpeg_muxer", "outputActive": False},
                ],
            },
            "GetOutputStatus": {"outputActive": False, "outputReconnecting": False, "outputTimecode": "00:00:00.000", "outputDuration": 0, "outputBytes": 0},
            "GetOutputSettings": {"outputSettings": {}},
            "ToggleOutput": {"outputActive": True},
            "GetTransitionList": {
                "currentSceneTransitionName": "Fade",
                "currentSceneTransitionKind": "fade_transition",
                "transitions": [
                    {"transitionName": "Cut", "transitionKind": "cut_transition"},
                    {"transitionName": "Fade", "transitionKind": "fade_transition"},
                    {"transitionName": "Swipe", "transitionKind": "swipe_transition"},
                ],
            },
            "GetCurrentSceneTransition": {
                "transitionName": "Fade", "transitionKind": "fade_transition",
                "transitionFixed": False, "transitionDuration": 300,
                "transitionConfigurable": True, "transitionSettings": {},
            },
            "GetCurrentSceneTransitionDuration": {"transitionDuration": 300},
            "GetCurrentSceneTransitionSettings": {"transitionSettings": {}},
            "GetSourceFilterKindList": {
                "sourceFilterKinds": [
                    "color_filter_v2", "chroma_key_filter_v2", "noise_suppress_filter_v2",
                    "compressor_filter", "limiter_filter", "gain_filter",
                ],
            },
            "GetSourceFilterList": {
                "filters": [
                    {"filterEnabled": True, "filterIndex": 0, "filterKind": "noise_suppress_filter_v2",
                     "filterName": "Noise Suppression", "filterSettings": {"suppress_level": -30}},
                ],
            },
            "GetSourceFilterDefaultSettings": {"defaultFilterSettings": {}},
            "GetSourceFilter": {
                "filterEnabled": True, "filterIndex": 0, "filterKind": "noise_suppress_filter_v2",
                "filterSettings": {"suppress_level": -30},
            },
            "GetSceneCollectionList": {
                "currentSceneCollectionName": "Default",
                "sceneCollections": ["Default", "Streaming", "Recording"],
            },
            "GetProfileList": {
                "currentProfileName": "Default",
                "profiles": ["Default", "High Quality", "Low Bandwidth"],
            },
            "GetVideoSettings": {
                "fpsNumerator": 60, "fpsDenominator": 1,
                "baseWidth": 1920, "baseHeight": 1080,
                "outputWidth": 1920, "outputHeight": 1080,
            },
            "GetStreamServiceSettings": {
                "streamServiceType": "rtmp_common",
                "streamServiceSettings": {"server": "auto", "key": "****"},
            },
            "GetRecordDirectory": {"recordDirectory": "{{HOME_DIR}}/Movies"},
            "GetStudioModeEnabled": {"studioModeEnabled": False},
            "GetHotkeyList": {"hotkeys": ["OBSBasic.StartStreaming", "OBSBasic.StopStreaming", "OBSBasic.StartRecording", "OBSBasic.StopRecording"]},
            "GetMonitorList": {
                "monitors": [
                    {"monitorIndex": 0, "monitorName": "Built-in Display", "monitorWidth": 3024, "monitorHeight": 1964},
                ],
            },
            "GetPersistentData": {"slotValue": None},
            "GetMediaInputStatus": {"mediaState": "OBS_MEDIA_STATE_NONE", "mediaDuration": 0, "mediaCursor": 0},
            "CreateSceneItem": {"sceneItemId": 99},
            "CreateInput": {"sceneItemId": 99},
        }
        return mock_data.get(request_type, {})


# ---------------------------------------------------------------------------
# OBSClient – high-level typed operations
# ---------------------------------------------------------------------------

class OBSClient:
    """High-level OBS operations wrapping the connection layer."""

    def __init__(self, connection, dry_run: bool = False):
        self._conn = connection
        self._dry_run = dry_run

    async def connect(self) -> None:
        await self._conn.connect()

    async def disconnect(self) -> None:
        await self._conn.disconnect()

    # -- General --

    async def get_version(self) -> Dict:
        return await self._conn.send_request("GetVersion")

    async def get_stats(self) -> Dict:
        return await self._conn.send_request("GetStats")

    async def get_hotkey_list(self) -> List[str]:
        data = await self._conn.send_request("GetHotkeyList")
        return data.get("hotkeys", [])

    async def trigger_hotkey(self, name: str, context: Optional[str] = None) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would trigger hotkey: %s", name)
            return
        params: Dict[str, Any] = {"hotkeyName": name}
        if context:
            params["contextName"] = context
        await self._conn.send_request("TriggerHotkeyByName", params)

    # -- Scenes --

    async def get_scene_list(self) -> Dict:
        return await self._conn.send_request("GetSceneList")

    async def get_current_scene(self) -> str:
        data = await self._conn.send_request("GetCurrentProgramScene")
        return data.get("currentProgramSceneName", "")

    async def set_current_scene(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would switch to scene: %s", name)
            return
        await self._conn.send_request("SetCurrentProgramScene", {"sceneName": name})

    async def create_scene(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would create scene: %s", name)
            return
        await self._conn.send_request("CreateScene", {"sceneName": name})

    async def remove_scene(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would remove scene: %s", name)
            return
        await self._conn.send_request("RemoveScene", {"sceneName": name})

    async def get_preview_scene(self) -> str:
        data = await self._conn.send_request("GetCurrentPreviewScene")
        return data.get("currentPreviewSceneName", "")

    async def set_preview_scene(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set preview scene: %s", name)
            return
        await self._conn.send_request("SetCurrentPreviewScene", {"sceneName": name})

    async def trigger_studio_transition(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would trigger studio mode transition")
            return
        await self._conn.send_request("TriggerStudioModeTransition")

    # -- Scene Items --

    async def get_scene_items(self, scene: str) -> List[Dict]:
        data = await self._conn.send_request("GetSceneItemList", {"sceneName": scene})
        return data.get("sceneItems", [])

    async def create_scene_item(self, scene: str, source: str, enabled: bool = True) -> int:
        if self._dry_run:
            logger.info("[DRY RUN] Would add %s to %s", source, scene)
            return -1
        data = await self._conn.send_request("CreateSceneItem", {
            "sceneName": scene, "sourceName": source, "sceneItemEnabled": enabled,
        })
        return data.get("sceneItemId", -1)

    async def remove_scene_item(self, scene: str, item_id: int) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would remove item %d from %s", item_id, scene)
            return
        await self._conn.send_request("RemoveSceneItem", {"sceneName": scene, "sceneItemId": item_id})

    async def set_scene_item_enabled(self, scene: str, item_id: int, enabled: bool) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would %s item %d in %s", "show" if enabled else "hide", item_id, scene)
            return
        await self._conn.send_request("SetSceneItemEnabled", {
            "sceneName": scene, "sceneItemId": item_id, "sceneItemEnabled": enabled,
        })

    async def get_scene_item_transform(self, scene: str, item_id: int) -> Dict:
        data = await self._conn.send_request("GetSceneItemTransform", {"sceneName": scene, "sceneItemId": item_id})
        return data.get("sceneItemTransform", {})

    async def set_scene_item_transform(self, scene: str, item_id: int, transform: Dict) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set transform on item %d in %s", item_id, scene)
            return
        await self._conn.send_request("SetSceneItemTransform", {
            "sceneName": scene, "sceneItemId": item_id, "sceneItemTransform": transform,
        })

    async def get_scene_item_id(self, scene: str, source: str) -> int:
        data = await self._conn.send_request("GetSceneItemId", {"sceneName": scene, "sourceName": source})
        return data.get("sceneItemId", -1)

    # -- Inputs --

    async def get_input_list(self, kind: Optional[str] = None) -> List[Dict]:
        params = {"inputKind": kind} if kind else {}
        data = await self._conn.send_request("GetInputList", params or None)
        return data.get("inputs", [])

    async def get_input_kind_list(self) -> List[str]:
        data = await self._conn.send_request("GetInputKindList")
        return data.get("inputKinds", [])

    async def get_special_inputs(self) -> Dict:
        return await self._conn.send_request("GetSpecialInputs")

    async def create_input(self, scene: str, name: str, kind: str,
                           settings: Optional[Dict] = None, enabled: bool = True) -> int:
        if self._dry_run:
            logger.info("[DRY RUN] Would create input %s (%s) in %s", name, kind, scene)
            return -1
        params: Dict[str, Any] = {"sceneName": scene, "inputName": name, "inputKind": kind, "sceneItemEnabled": enabled}
        if settings:
            params["inputSettings"] = settings
        data = await self._conn.send_request("CreateInput", params)
        return data.get("sceneItemId", -1)

    async def remove_input(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would remove input: %s", name)
            return
        await self._conn.send_request("RemoveInput", {"inputName": name})

    async def rename_input(self, name: str, new_name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would rename %s to %s", name, new_name)
            return
        await self._conn.send_request("SetInputName", {"inputName": name, "newInputName": new_name})

    async def get_input_settings(self, name: str) -> Dict:
        return await self._conn.send_request("GetInputSettings", {"inputName": name})

    async def set_input_settings(self, name: str, settings: Dict, overlay: bool = True) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set settings on %s", name)
            return
        await self._conn.send_request("SetInputSettings", {"inputName": name, "inputSettings": settings, "overlay": overlay})

    async def get_input_defaults(self, kind: str) -> Dict:
        data = await self._conn.send_request("GetInputDefaultSettings", {"inputKind": kind})
        return data.get("defaultInputSettings", {})

    # -- Audio --

    async def get_input_mute(self, name: str) -> bool:
        data = await self._conn.send_request("GetInputMute", {"inputName": name})
        return data.get("inputMuted", False)

    async def set_input_mute(self, name: str, muted: bool) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would %s %s", "mute" if muted else "unmute", name)
            return
        await self._conn.send_request("SetInputMute", {"inputName": name, "inputMuted": muted})

    async def toggle_input_mute(self, name: str) -> bool:
        if self._dry_run:
            logger.info("[DRY RUN] Would toggle mute on %s", name)
            return False
        data = await self._conn.send_request("ToggleInputMute", {"inputName": name})
        return data.get("inputMuted", False)

    async def get_input_volume(self, name: str) -> Dict:
        return await self._conn.send_request("GetInputVolume", {"inputName": name})

    async def set_input_volume(self, name: str, db: Optional[float] = None, mul: Optional[float] = None) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set volume on %s", name)
            return
        params: Dict[str, Any] = {"inputName": name}
        if db is not None:
            params["inputVolumeDb"] = db
        if mul is not None:
            params["inputVolumeMul"] = mul
        await self._conn.send_request("SetInputVolume", params)

    async def get_audio_balance(self, name: str) -> float:
        data = await self._conn.send_request("GetInputAudioBalance", {"inputName": name})
        return data.get("inputAudioBalance", 0.5)

    async def set_audio_balance(self, name: str, balance: float) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set audio balance on %s to %f", name, balance)
            return
        await self._conn.send_request("SetInputAudioBalance", {"inputName": name, "inputAudioBalance": balance})

    async def get_sync_offset(self, name: str) -> int:
        data = await self._conn.send_request("GetInputAudioSyncOffset", {"inputName": name})
        return data.get("inputAudioSyncOffset", 0)

    async def set_sync_offset(self, name: str, offset_ms: int) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set sync offset on %s to %d ms", name, offset_ms)
            return
        await self._conn.send_request("SetInputAudioSyncOffset", {"inputName": name, "inputAudioSyncOffset": offset_ms})

    async def get_monitor_type(self, name: str) -> str:
        data = await self._conn.send_request("GetInputAudioMonitorType", {"inputName": name})
        return data.get("monitorType", "")

    async def set_monitor_type(self, name: str, monitor_type: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set monitor type on %s to %s", name, monitor_type)
            return
        await self._conn.send_request("SetInputAudioMonitorType", {"inputName": name, "monitorType": monitor_type})

    # -- Sources --

    async def get_source_active(self, name: str) -> Dict:
        return await self._conn.send_request("GetSourceActive", {"sourceName": name})

    async def save_screenshot(self, source: str, path: str, fmt: str = "png",
                              width: Optional[int] = None, height: Optional[int] = None) -> str:
        if self._dry_run:
            logger.info("[DRY RUN] Would save screenshot of %s to %s", source, path)
            return path
        params: Dict[str, Any] = {"sourceName": source, "imageFormat": fmt, "imageFilePath": path}
        if width:
            params["imageWidth"] = width
        if height:
            params["imageHeight"] = height
        await self._conn.send_request("SaveSourceScreenshot", params)
        return path

    # -- Streaming --

    async def get_stream_status(self) -> Dict:
        return await self._conn.send_request("GetStreamStatus")

    async def start_stream(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would start streaming")
            return
        await self._conn.send_request("StartStream")

    async def stop_stream(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would stop streaming")
            return
        await self._conn.send_request("StopStream")

    async def toggle_stream(self) -> bool:
        if self._dry_run:
            logger.info("[DRY RUN] Would toggle streaming")
            return False
        data = await self._conn.send_request("ToggleStream")
        return data.get("outputActive", False)

    async def send_caption(self, text: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would send caption: %s", text)
            return
        await self._conn.send_request("SendStreamCaption", {"captionText": text})

    # -- Recording --

    async def get_record_status(self) -> Dict:
        return await self._conn.send_request("GetRecordStatus")

    async def start_record(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would start recording")
            return
        await self._conn.send_request("StartRecord")

    async def stop_record(self) -> str:
        if self._dry_run:
            logger.info("[DRY RUN] Would stop recording")
            return ""
        data = await self._conn.send_request("StopRecord")
        return data.get("outputPath", "")

    async def toggle_record(self) -> bool:
        if self._dry_run:
            logger.info("[DRY RUN] Would toggle recording")
            return False
        data = await self._conn.send_request("ToggleRecord")
        return data.get("outputActive", False)

    async def pause_record(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would pause recording")
            return
        await self._conn.send_request("PauseRecord")

    async def resume_record(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would resume recording")
            return
        await self._conn.send_request("ResumeRecord")

    async def split_record(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would split recording file")
            return
        await self._conn.send_request("SplitRecordFile")

    async def create_chapter(self, name: Optional[str] = None) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would create chapter: %s", name or "(unnamed)")
            return
        params = {"chapterName": name} if name else {}
        await self._conn.send_request("CreateRecordChapter", params or None)

    # -- Virtual Camera --

    async def get_virtualcam_status(self) -> bool:
        data = await self._conn.send_request("GetVirtualCamStatus")
        return data.get("outputActive", False)

    async def start_virtualcam(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would start virtual camera")
            return
        await self._conn.send_request("StartVirtualCam")

    async def stop_virtualcam(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would stop virtual camera")
            return
        await self._conn.send_request("StopVirtualCam")

    async def toggle_virtualcam(self) -> bool:
        if self._dry_run:
            logger.info("[DRY RUN] Would toggle virtual camera")
            return False
        data = await self._conn.send_request("ToggleVirtualCam")
        return data.get("outputActive", False)

    # -- Replay Buffer --

    async def get_replay_status(self) -> bool:
        data = await self._conn.send_request("GetReplayBufferStatus")
        return data.get("outputActive", False)

    async def start_replay(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would start replay buffer")
            return
        await self._conn.send_request("StartReplayBuffer")

    async def stop_replay(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would stop replay buffer")
            return
        await self._conn.send_request("StopReplayBuffer")

    async def save_replay(self) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would save replay buffer")
            return
        await self._conn.send_request("SaveReplayBuffer")

    async def get_last_replay(self) -> str:
        data = await self._conn.send_request("GetLastReplayBufferReplay")
        return data.get("savedReplayPath", "")

    # -- Outputs --

    async def get_output_list(self) -> List[Dict]:
        data = await self._conn.send_request("GetOutputList")
        return data.get("outputs", [])

    async def get_output_status(self, name: str) -> Dict:
        return await self._conn.send_request("GetOutputStatus", {"outputName": name})

    async def start_output(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would start output: %s", name)
            return
        await self._conn.send_request("StartOutput", {"outputName": name})

    async def stop_output(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would stop output: %s", name)
            return
        await self._conn.send_request("StopOutput", {"outputName": name})

    async def get_output_settings(self, name: str) -> Dict:
        return await self._conn.send_request("GetOutputSettings", {"outputName": name})

    async def set_output_settings(self, name: str, settings: Dict) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set output settings on %s", name)
            return
        await self._conn.send_request("SetOutputSettings", {"outputName": name, "outputSettings": settings})

    # -- Transitions --

    async def get_transition_list(self) -> Dict:
        return await self._conn.send_request("GetTransitionList")

    async def get_current_transition(self) -> Dict:
        return await self._conn.send_request("GetCurrentSceneTransition")

    async def set_current_transition(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set transition to: %s", name)
            return
        await self._conn.send_request("SetCurrentSceneTransition", {"transitionName": name})

    async def get_transition_duration(self) -> int:
        data = await self._conn.send_request("GetCurrentSceneTransitionDuration")
        return data.get("transitionDuration", 0)

    async def set_transition_duration(self, ms: int) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set transition duration to %d ms", ms)
            return
        await self._conn.send_request("SetCurrentSceneTransitionDuration", {"transitionDuration": ms})

    async def get_transition_settings(self) -> Dict:
        data = await self._conn.send_request("GetCurrentSceneTransition")
        return data.get("transitionSettings", {})

    async def set_transition_settings(self, settings: Dict) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set transition settings")
            return
        await self._conn.send_request("SetCurrentSceneTransitionSettings", {"transitionSettings": settings})

    # -- Filters --

    async def get_filter_kinds(self) -> List[str]:
        data = await self._conn.send_request("GetSourceFilterKindList")
        return data.get("sourceFilterKinds", [])

    async def get_filter_list(self, source: str) -> List[Dict]:
        data = await self._conn.send_request("GetSourceFilterList", {"sourceName": source})
        return data.get("filters", [])

    async def get_filter_defaults(self, kind: str) -> Dict:
        data = await self._conn.send_request("GetSourceFilterDefaultSettings", {"filterKind": kind})
        return data.get("defaultFilterSettings", {})

    async def create_filter(self, source: str, name: str, kind: str, settings: Optional[Dict] = None) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would create filter %s on %s", name, source)
            return
        params: Dict[str, Any] = {"sourceName": source, "filterName": name, "filterKind": kind}
        if settings:
            params["filterSettings"] = settings
        await self._conn.send_request("CreateSourceFilter", params)

    async def remove_filter(self, source: str, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would remove filter %s from %s", name, source)
            return
        await self._conn.send_request("RemoveSourceFilter", {"sourceName": source, "filterName": name})

    async def get_filter_info(self, source: str, name: str) -> Dict:
        return await self._conn.send_request("GetSourceFilter", {"sourceName": source, "filterName": name})

    async def set_filter_enabled(self, source: str, name: str, enabled: bool) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would %s filter %s on %s", "enable" if enabled else "disable", name, source)
            return
        await self._conn.send_request("SetSourceFilterEnabled", {"sourceName": source, "filterName": name, "filterEnabled": enabled})

    async def set_filter_settings(self, source: str, name: str, settings: Dict, overlay: bool = True) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set filter settings on %s/%s", source, name)
            return
        await self._conn.send_request("SetSourceFilterSettings", {"sourceName": source, "filterName": name, "filterSettings": settings, "overlay": overlay})

    async def set_filter_index(self, source: str, name: str, index: int) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would reorder filter %s on %s to index %d", name, source, index)
            return
        await self._conn.send_request("SetSourceFilterIndex", {"sourceName": source, "filterName": name, "filterIndex": index})

    # -- Config --

    async def get_scene_collections(self) -> Dict:
        return await self._conn.send_request("GetSceneCollectionList")

    async def set_scene_collection(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would switch to collection: %s", name)
            return
        await self._conn.send_request("SetCurrentSceneCollection", {"sceneCollectionName": name})

    async def create_scene_collection(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would create collection: %s", name)
            return
        await self._conn.send_request("CreateSceneCollection", {"sceneCollectionName": name})

    async def get_profiles(self) -> Dict:
        return await self._conn.send_request("GetProfileList")

    async def set_profile(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would switch to profile: %s", name)
            return
        await self._conn.send_request("SetCurrentProfile", {"profileName": name})

    async def create_profile(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would create profile: %s", name)
            return
        await self._conn.send_request("CreateProfile", {"profileName": name})

    async def remove_profile(self, name: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would remove profile: %s", name)
            return
        await self._conn.send_request("RemoveProfile", {"profileName": name})

    async def get_video_settings(self) -> Dict:
        return await self._conn.send_request("GetVideoSettings")

    async def set_video_settings(self, **kwargs) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set video settings: %s", kwargs)
            return
        await self._conn.send_request("SetVideoSettings", kwargs)

    async def get_stream_service(self) -> Dict:
        return await self._conn.send_request("GetStreamServiceSettings")

    async def get_record_directory(self) -> str:
        data = await self._conn.send_request("GetRecordDirectory")
        return data.get("recordDirectory", "")

    async def set_record_directory(self, path: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set record directory to: %s", path)
            return
        await self._conn.send_request("SetRecordDirectory", {"recordDirectory": path})

    # -- Studio Mode --

    async def get_studio_mode(self) -> bool:
        data = await self._conn.send_request("GetStudioModeEnabled")
        return data.get("studioModeEnabled", False)

    async def set_studio_mode(self, enabled: bool) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would %s studio mode", "enable" if enabled else "disable")
            return
        await self._conn.send_request("SetStudioModeEnabled", {"studioModeEnabled": enabled})

    # -- Media Inputs --

    async def get_media_status(self, name: str) -> Dict:
        return await self._conn.send_request("GetMediaInputStatus", {"inputName": name})

    async def set_media_cursor(self, name: str, cursor_ms: int) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would set media cursor on %s to %d ms", name, cursor_ms)
            return
        await self._conn.send_request("SetMediaInputCursor", {"inputName": name, "mediaCursor": cursor_ms})

    async def trigger_media_action(self, name: str, action: str) -> None:
        if self._dry_run:
            logger.info("[DRY RUN] Would trigger %s on %s", action, name)
            return
        await self._conn.send_request("TriggerMediaInputAction", {"inputName": name, "mediaAction": action})

    # -- UI --

    async def get_monitor_list(self) -> List[Dict]:
        data = await self._conn.send_request("GetMonitorList")
        return data.get("monitors", [])


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _json_out(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))

def _parse_json_arg(value: str, label: str = "settings") -> Dict:
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise OBSError(f"Invalid JSON for --{label}: {e}")

def _ok(msg: str) -> None:
    print(f"{GREEN}{msg}{RESET}")

def _err(msg: str) -> None:
    print(f"{RED}{msg}{RESET}", file=sys.stderr)

def _info(label: str, value: Any) -> None:
    print(f"  {CYAN}{label}:{RESET} {value}")


# ---------------------------------------------------------------------------
# Handler functions  (async def cmd_*(client, args) -> int)
# ---------------------------------------------------------------------------

# --- Top-level ---

async def cmd_status(client: OBSClient, args) -> int:
    version = await client.get_version()
    scene = await client.get_current_scene()
    stream = await client.get_stream_status()
    record = await client.get_record_status()
    if args.json:
        _json_out({"version": version, "currentScene": scene, "stream": stream, "record": record})
    else:
        _ok(f"Connected to OBS v{version.get('obsVersion', '?')}")
        _info("WebSocket", f"v{version.get('obsWebSocketVersion', '?')}")
        _info("Platform", version.get("platformDescription", "?"))
        _info("Current scene", scene)
        _info("Streaming", "Active" if stream.get("outputActive") else "Inactive")
        _info("Recording", "Active" if record.get("outputActive") else "Inactive")
    return 0

async def cmd_version(client: OBSClient, args) -> int:
    data = await client.get_version()
    if args.json:
        _json_out(data)
    else:
        _info("OBS Version", data.get("obsVersion"))
        _info("WebSocket", data.get("obsWebSocketVersion"))
        _info("RPC Version", data.get("rpcVersion"))
        _info("Platform", data.get("platformDescription"))
        _info("Image Formats", ", ".join(data.get("supportedImageFormats", [])))
    return 0

async def cmd_stats(client: OBSClient, args) -> int:
    data = await client.get_stats()
    if args.json:
        _json_out(data)
    else:
        _info("CPU Usage", f"{data.get('cpuUsage', 0):.1f}%")
        _info("Memory", f"{data.get('memoryUsage', 0):.1f} MB")
        _info("FPS", f"{data.get('activeFps', 0):.1f}")
        _info("Frame Time", f"{data.get('averageFrameRenderTime', 0):.2f} ms")
        _info("Render Skipped", f"{data.get('renderSkippedFrames', 0)}/{data.get('renderTotalFrames', 0)}")
        _info("Output Skipped", f"{data.get('outputSkippedFrames', 0)}/{data.get('outputTotalFrames', 0)}")
        _info("Disk Space", f"{data.get('availableDiskSpace', 0):.0f} MB")
    return 0

# --- Scene ---

async def cmd_scene_list(client: OBSClient, args) -> int:
    data = await client.get_scene_list()
    if args.json:
        _json_out(data)
    else:
        current = data.get("currentProgramSceneName", "")
        for s in data.get("scenes", []):
            name = s.get("sceneName", "")
            marker = f" {GREEN}(active){RESET}" if name == current else ""
            print(f"  {name}{marker}")
    return 0

async def cmd_scene_current(client: OBSClient, args) -> int:
    name = await client.get_current_scene()
    if args.json:
        _json_out({"currentScene": name})
    else:
        print(name)
    return 0

async def cmd_scene_switch(client: OBSClient, args) -> int:
    await client.set_current_scene(args.name)
    _ok(f"Switched to scene: {args.name}")
    return 0

async def cmd_scene_create(client: OBSClient, args) -> int:
    await client.create_scene(args.name)
    _ok(f"Created scene: {args.name}")
    return 0

async def cmd_scene_remove(client: OBSClient, args) -> int:
    await client.remove_scene(args.name)
    _ok(f"Removed scene: {args.name}")
    return 0

async def cmd_scene_preview(client: OBSClient, args) -> int:
    if hasattr(args, 'name') and args.name:
        await client.set_preview_scene(args.name)
        _ok(f"Set preview scene: {args.name}")
    else:
        name = await client.get_preview_scene()
        if args.json:
            _json_out({"previewScene": name})
        else:
            print(name or "(none)")
    return 0

async def cmd_scene_transition(client: OBSClient, args) -> int:
    await client.trigger_studio_transition()
    _ok("Studio mode transition triggered")
    return 0

# --- Item ---

async def cmd_item_list(client: OBSClient, args) -> int:
    items = await client.get_scene_items(args.scene)
    if args.json:
        _json_out(items)
    else:
        for item in items:
            enabled = f"{GREEN}ON{RESET}" if item.get("sceneItemEnabled") else f"{RED}OFF{RESET}"
            print(f"  [{item.get('sceneItemId', '?')}] {item.get('sourceName', '?')} ({item.get('inputKind', '?')}) {enabled}")
    return 0

async def cmd_item_add(client: OBSClient, args) -> int:
    item_id = await client.create_scene_item(args.scene, args.source, not getattr(args, 'disabled', False))
    _ok(f"Added {args.source} to {args.scene} (ID: {item_id})")
    return 0

async def cmd_item_remove(client: OBSClient, args) -> int:
    await client.remove_scene_item(args.scene, args.item_id)
    _ok(f"Removed item {args.item_id} from {args.scene}")
    return 0

async def cmd_item_show(client: OBSClient, args) -> int:
    await client.set_scene_item_enabled(args.scene, args.item_id, True)
    _ok(f"Showed item {args.item_id} in {args.scene}")
    return 0

async def cmd_item_hide(client: OBSClient, args) -> int:
    await client.set_scene_item_enabled(args.scene, args.item_id, False)
    _ok(f"Hid item {args.item_id} in {args.scene}")
    return 0

async def cmd_item_transform(client: OBSClient, args) -> int:
    transform = await client.get_scene_item_transform(args.scene, args.item_id)
    if args.json:
        _json_out(transform)
    else:
        for k, v in transform.items():
            _info(k, v)
    return 0

async def cmd_item_id(client: OBSClient, args) -> int:
    item_id = await client.get_scene_item_id(args.scene, args.source)
    if args.json:
        _json_out({"sceneItemId": item_id})
    else:
        print(item_id)
    return 0

# --- Input ---

async def cmd_input_list(client: OBSClient, args) -> int:
    inputs = await client.get_input_list(getattr(args, 'kind', None))
    if args.json:
        _json_out(inputs)
    else:
        for inp in inputs:
            print(f"  {inp.get('inputName', '?')} ({inp.get('inputKind', '?')})")
    return 0

async def cmd_input_kinds(client: OBSClient, args) -> int:
    kinds = await client.get_input_kind_list()
    if args.json:
        _json_out(kinds)
    else:
        for k in kinds:
            print(f"  {k}")
    return 0

async def cmd_input_create(client: OBSClient, args) -> int:
    settings = _parse_json_arg(args.settings) if getattr(args, 'settings', None) else None
    item_id = await client.create_input(args.scene, args.name, args.kind, settings)
    _ok(f"Created input {args.name} ({args.kind}) in {args.scene} (ID: {item_id})")
    return 0

async def cmd_input_remove(client: OBSClient, args) -> int:
    await client.remove_input(args.name)
    _ok(f"Removed input: {args.name}")
    return 0

async def cmd_input_rename(client: OBSClient, args) -> int:
    await client.rename_input(args.name, args.new_name)
    _ok(f"Renamed {args.name} to {args.new_name}")
    return 0

async def cmd_input_settings(client: OBSClient, args) -> int:
    data = await client.get_input_settings(args.name)
    if args.json:
        _json_out(data)
    else:
        _info("Kind", data.get("inputKind"))
        for k, v in data.get("inputSettings", {}).items():
            _info(k, v)
    return 0

async def cmd_input_set(client: OBSClient, args) -> int:
    settings = _parse_json_arg(args.settings)
    await client.set_input_settings(args.name, settings)
    _ok(f"Updated settings for {args.name}")
    return 0

async def cmd_input_defaults(client: OBSClient, args) -> int:
    data = await client.get_input_defaults(args.kind)
    _json_out(data)
    return 0

# --- Audio ---

async def cmd_audio_mute(client: OBSClient, args) -> int:
    muted = await client.get_input_mute(args.input)
    if args.json:
        _json_out({"inputMuted": muted})
    else:
        print(f"{args.input}: {'muted' if muted else 'unmuted'}")
    return 0

async def cmd_audio_set_mute(client: OBSClient, args) -> int:
    muted = args.state.lower() in ("on", "true", "1", "yes")
    await client.set_input_mute(args.input, muted)
    _ok(f"{'Muted' if muted else 'Unmuted'} {args.input}")
    return 0

async def cmd_audio_toggle_mute(client: OBSClient, args) -> int:
    new_state = await client.toggle_input_mute(args.input)
    _ok(f"{args.input} is now {'muted' if new_state else 'unmuted'}")
    return 0

async def cmd_audio_volume(client: OBSClient, args) -> int:
    data = await client.get_input_volume(args.input)
    if args.json:
        _json_out(data)
    else:
        _info("Volume (dB)", f"{data.get('inputVolumeDb', 0):.1f}")
        _info("Volume (mul)", f"{data.get('inputVolumeMul', 0):.3f}")
    return 0

async def cmd_audio_set_volume(client: OBSClient, args) -> int:
    await client.set_input_volume(args.input, db=getattr(args, 'db', None), mul=getattr(args, 'mul', None))
    _ok(f"Set volume for {args.input}")
    return 0

async def cmd_audio_balance(client: OBSClient, args) -> int:
    bal = await client.get_audio_balance(args.input)
    if args.json:
        _json_out({"inputAudioBalance": bal})
    else:
        print(f"{args.input}: {bal:.2f}")
    return 0

async def cmd_audio_set_balance(client: OBSClient, args) -> int:
    await client.set_audio_balance(args.input, args.value)
    _ok(f"Set audio balance to {args.value} for {args.input}")
    return 0

async def cmd_audio_sync_offset(client: OBSClient, args) -> int:
    offset = await client.get_sync_offset(args.input)
    if args.json:
        _json_out({"inputAudioSyncOffset": offset})
    else:
        print(f"{args.input}: {offset} ms")
    return 0

async def cmd_audio_set_sync_offset(client: OBSClient, args) -> int:
    await client.set_sync_offset(args.input, args.value)
    _ok(f"Set sync offset to {args.value} ms for {args.input}")
    return 0

async def cmd_audio_monitor_type(client: OBSClient, args) -> int:
    mtype = await client.get_monitor_type(args.input)
    if args.json:
        _json_out({"monitorType": mtype})
    else:
        print(f"{args.input}: {mtype}")
    return 0

async def cmd_audio_set_monitor_type(client: OBSClient, args) -> int:
    await client.set_monitor_type(args.input, args.type)
    _ok(f"Set monitor type to {args.type} for {args.input}")
    return 0

# --- Source ---

async def cmd_source_active(client: OBSClient, args) -> int:
    data = await client.get_source_active(args.name)
    if args.json:
        _json_out(data)
    else:
        _info("Video Active", data.get("videoActive"))
        _info("Video Showing", data.get("videoShowing"))
    return 0

async def cmd_source_screenshot(client: OBSClient, args) -> int:
    path = await client.save_screenshot(
        args.name, args.path, getattr(args, 'format', 'png'),
        width=getattr(args, 'width', None), height=getattr(args, 'height', None),
    )
    _ok(f"Screenshot saved: {path}")
    return 0

# --- Stream ---

async def cmd_stream_status(client: OBSClient, args) -> int:
    data = await client.get_stream_status()
    if args.json:
        _json_out(data)
    else:
        active = data.get("outputActive", False)
        print(f"  Stream: {GREEN}Active{RESET}" if active else f"  Stream: {DIM}Inactive{RESET}")
        if active:
            _info("Timecode", data.get("outputTimecode"))
            _info("Bytes", data.get("outputBytes"))
            _info("Skipped", f"{data.get('outputSkippedFrames', 0)}/{data.get('outputTotalFrames', 0)}")
    return 0

async def cmd_stream_start(client: OBSClient, args) -> int:
    await client.start_stream()
    _ok("Streaming started")
    return 0

async def cmd_stream_stop(client: OBSClient, args) -> int:
    await client.stop_stream()
    _ok("Streaming stopped")
    return 0

async def cmd_stream_toggle(client: OBSClient, args) -> int:
    active = await client.toggle_stream()
    _ok(f"Streaming {'started' if active else 'stopped'}")
    return 0

async def cmd_stream_caption(client: OBSClient, args) -> int:
    await client.send_caption(args.text)
    _ok("Caption sent")
    return 0

# --- Record ---

async def cmd_record_status(client: OBSClient, args) -> int:
    data = await client.get_record_status()
    if args.json:
        _json_out(data)
    else:
        active = data.get("outputActive", False)
        paused = data.get("outputPaused", False)
        if active:
            state = f"{YELLOW}Paused{RESET}" if paused else f"{GREEN}Recording{RESET}"
        else:
            state = f"{DIM}Inactive{RESET}"
        print(f"  Recording: {state}")
        if active:
            _info("Timecode", data.get("outputTimecode"))
            _info("Bytes", data.get("outputBytes"))
    return 0

async def cmd_record_start(client: OBSClient, args) -> int:
    await client.start_record()
    _ok("Recording started")
    return 0

async def cmd_record_stop(client: OBSClient, args) -> int:
    path = await client.stop_record()
    _ok(f"Recording stopped → {path}")
    return 0

async def cmd_record_toggle(client: OBSClient, args) -> int:
    active = await client.toggle_record()
    _ok(f"Recording {'started' if active else 'stopped'}")
    return 0

async def cmd_record_pause(client: OBSClient, args) -> int:
    await client.pause_record()
    _ok("Recording paused")
    return 0

async def cmd_record_resume(client: OBSClient, args) -> int:
    await client.resume_record()
    _ok("Recording resumed")
    return 0

async def cmd_record_split(client: OBSClient, args) -> int:
    await client.split_record()
    _ok("Recording file split")
    return 0

async def cmd_record_chapter(client: OBSClient, args) -> int:
    name = getattr(args, 'name', None)
    await client.create_chapter(name)
    _ok(f"Chapter created{f': {name}' if name else ''}")
    return 0

# --- VirtualCam ---

async def cmd_vcam_status(client: OBSClient, args) -> int:
    active = await client.get_virtualcam_status()
    if args.json:
        _json_out({"active": active})
    else:
        print(f"  Virtual Camera: {GREEN}Active{RESET}" if active else f"  Virtual Camera: {DIM}Inactive{RESET}")
    return 0

async def cmd_vcam_start(client: OBSClient, args) -> int:
    await client.start_virtualcam()
    _ok("Virtual camera started")
    return 0

async def cmd_vcam_stop(client: OBSClient, args) -> int:
    await client.stop_virtualcam()
    _ok("Virtual camera stopped")
    return 0

async def cmd_vcam_toggle(client: OBSClient, args) -> int:
    active = await client.toggle_virtualcam()
    _ok(f"Virtual camera {'started' if active else 'stopped'}")
    return 0

# --- Replay ---

async def cmd_replay_status(client: OBSClient, args) -> int:
    active = await client.get_replay_status()
    if args.json:
        _json_out({"active": active})
    else:
        print(f"  Replay Buffer: {GREEN}Active{RESET}" if active else f"  Replay Buffer: {DIM}Inactive{RESET}")
    return 0

async def cmd_replay_start(client: OBSClient, args) -> int:
    await client.start_replay()
    _ok("Replay buffer started")
    return 0

async def cmd_replay_stop(client: OBSClient, args) -> int:
    await client.stop_replay()
    _ok("Replay buffer stopped")
    return 0

async def cmd_replay_save(client: OBSClient, args) -> int:
    await client.save_replay()
    _ok("Replay buffer saved")
    return 0

async def cmd_replay_last(client: OBSClient, args) -> int:
    path = await client.get_last_replay()
    if args.json:
        _json_out({"path": path})
    else:
        print(path)
    return 0

# --- Output ---

async def cmd_output_list(client: OBSClient, args) -> int:
    outputs = await client.get_output_list()
    if args.json:
        _json_out(outputs)
    else:
        for o in outputs:
            active = f"{GREEN}ON{RESET}" if o.get("outputActive") else f"{DIM}OFF{RESET}"
            print(f"  {o.get('outputName', '?')} ({o.get('outputKind', '?')}) {active}")
    return 0

async def cmd_output_status(client: OBSClient, args) -> int:
    data = await client.get_output_status(args.name)
    if args.json:
        _json_out(data)
    else:
        _info("Active", data.get("outputActive"))
        _info("Timecode", data.get("outputTimecode"))
        _info("Bytes", data.get("outputBytes"))
    return 0

async def cmd_output_start(client: OBSClient, args) -> int:
    await client.start_output(args.name)
    _ok(f"Output {args.name} started")
    return 0

async def cmd_output_stop(client: OBSClient, args) -> int:
    await client.stop_output(args.name)
    _ok(f"Output {args.name} stopped")
    return 0

async def cmd_output_settings(client: OBSClient, args) -> int:
    data = await client.get_output_settings(args.name)
    _json_out(data)
    return 0

async def cmd_output_set(client: OBSClient, args) -> int:
    settings = _parse_json_arg(args.settings)
    await client.set_output_settings(args.name, settings)
    _ok(f"Updated settings for output {args.name}")
    return 0

# --- Transition ---

async def cmd_transition_list(client: OBSClient, args) -> int:
    data = await client.get_transition_list()
    if args.json:
        _json_out(data)
    else:
        current = data.get("currentSceneTransitionName", "")
        for t in data.get("transitions", []):
            name = t.get("transitionName", "?")
            marker = f" {GREEN}(active){RESET}" if name == current else ""
            print(f"  {name} ({t.get('transitionKind', '?')}){marker}")
    return 0

async def cmd_transition_current(client: OBSClient, args) -> int:
    data = await client.get_current_transition()
    if args.json:
        _json_out(data)
    else:
        _info("Name", data.get("transitionName"))
        _info("Kind", data.get("transitionKind"))
        _info("Duration", f"{data.get('transitionDuration', 0)} ms")
    return 0

async def cmd_transition_set(client: OBSClient, args) -> int:
    await client.set_current_transition(args.name)
    _ok(f"Set transition: {args.name}")
    return 0

async def cmd_transition_duration(client: OBSClient, args) -> int:
    if hasattr(args, 'ms') and args.ms is not None:
        await client.set_transition_duration(args.ms)
        _ok(f"Set transition duration: {args.ms} ms")
    else:
        ms = await client.get_transition_duration()
        if args.json:
            _json_out({"transitionDuration": ms})
        else:
            print(f"{ms} ms")
    return 0

async def cmd_transition_settings(client: OBSClient, args) -> int:
    data = await client.get_transition_settings()
    _json_out(data)
    return 0

async def cmd_transition_set_settings(client: OBSClient, args) -> int:
    settings = _parse_json_arg(args.settings)
    await client.set_transition_settings(settings)
    _ok("Updated transition settings")
    return 0

async def cmd_transition_trigger(client: OBSClient, args) -> int:
    await client.trigger_studio_transition()
    _ok("Transition triggered")
    return 0

# --- Filter ---

async def cmd_filter_kinds(client: OBSClient, args) -> int:
    kinds = await client.get_filter_kinds()
    if args.json:
        _json_out(kinds)
    else:
        for k in kinds:
            print(f"  {k}")
    return 0

async def cmd_filter_list(client: OBSClient, args) -> int:
    filters = await client.get_filter_list(args.source)
    if args.json:
        _json_out(filters)
    else:
        for f in filters:
            enabled = f"{GREEN}ON{RESET}" if f.get("filterEnabled") else f"{RED}OFF{RESET}"
            print(f"  [{f.get('filterIndex', '?')}] {f.get('filterName', '?')} ({f.get('filterKind', '?')}) {enabled}")
    return 0

async def cmd_filter_defaults(client: OBSClient, args) -> int:
    data = await client.get_filter_defaults(args.kind)
    _json_out(data)
    return 0

async def cmd_filter_add(client: OBSClient, args) -> int:
    settings = _parse_json_arg(args.settings) if getattr(args, 'settings', None) else None
    await client.create_filter(args.source, args.name, args.kind, settings)
    _ok(f"Created filter {args.name} on {args.source}")
    return 0

async def cmd_filter_remove(client: OBSClient, args) -> int:
    await client.remove_filter(args.source, args.name)
    _ok(f"Removed filter {args.name} from {args.source}")
    return 0

async def cmd_filter_info(client: OBSClient, args) -> int:
    data = await client.get_filter_info(args.source, args.name)
    _json_out(data)
    return 0

async def cmd_filter_enable(client: OBSClient, args) -> int:
    await client.set_filter_enabled(args.source, args.name, True)
    _ok(f"Enabled filter {args.name} on {args.source}")
    return 0

async def cmd_filter_disable(client: OBSClient, args) -> int:
    await client.set_filter_enabled(args.source, args.name, False)
    _ok(f"Disabled filter {args.name} on {args.source}")
    return 0

async def cmd_filter_set(client: OBSClient, args) -> int:
    settings = _parse_json_arg(args.settings)
    await client.set_filter_settings(args.source, args.name, settings)
    _ok(f"Updated settings for filter {args.name} on {args.source}")
    return 0

async def cmd_filter_reorder(client: OBSClient, args) -> int:
    await client.set_filter_index(args.source, args.name, args.index)
    _ok(f"Moved filter {args.name} to index {args.index} on {args.source}")
    return 0

# --- Config ---

async def cmd_config_collections(client: OBSClient, args) -> int:
    data = await client.get_scene_collections()
    if args.json:
        _json_out(data)
    else:
        current = data.get("currentSceneCollectionName", "")
        for c in data.get("sceneCollections", []):
            marker = f" {GREEN}(active){RESET}" if c == current else ""
            print(f"  {c}{marker}")
    return 0

async def cmd_config_set_collection(client: OBSClient, args) -> int:
    await client.set_scene_collection(args.name)
    _ok(f"Switched to collection: {args.name}")
    return 0

async def cmd_config_profiles(client: OBSClient, args) -> int:
    data = await client.get_profiles()
    if args.json:
        _json_out(data)
    else:
        current = data.get("currentProfileName", "")
        for p in data.get("profiles", []):
            marker = f" {GREEN}(active){RESET}" if p == current else ""
            print(f"  {p}{marker}")
    return 0

async def cmd_config_set_profile(client: OBSClient, args) -> int:
    await client.set_profile(args.name)
    _ok(f"Switched to profile: {args.name}")
    return 0

async def cmd_config_video(client: OBSClient, args) -> int:
    data = await client.get_video_settings()
    if args.json:
        _json_out(data)
    else:
        fps_n = data.get("fpsNumerator", 0)
        fps_d = data.get("fpsDenominator", 1)
        _info("Base Resolution", f"{data.get('baseWidth')}x{data.get('baseHeight')}")
        _info("Output Resolution", f"{data.get('outputWidth')}x{data.get('outputHeight')}")
        _info("FPS", f"{fps_n/fps_d:.0f}" if fps_d == 1 else f"{fps_n}/{fps_d}")
    return 0

async def cmd_config_record_dir(client: OBSClient, args) -> int:
    path = await client.get_record_directory()
    if args.json:
        _json_out({"recordDirectory": path})
    else:
        print(path)
    return 0

async def cmd_config_set_record_dir(client: OBSClient, args) -> int:
    await client.set_record_directory(args.path)
    _ok(f"Set record directory: {args.path}")
    return 0

async def cmd_config_create_collection(client: OBSClient, args) -> int:
    await client.create_scene_collection(args.name)
    _ok(f"Created scene collection: {args.name}")
    return 0

async def cmd_config_create_profile(client: OBSClient, args) -> int:
    await client.create_profile(args.name)
    _ok(f"Created profile: {args.name}")
    return 0

async def cmd_config_remove_profile(client: OBSClient, args) -> int:
    await client.remove_profile(args.name)
    _ok(f"Removed profile: {args.name}")
    return 0

async def cmd_config_stream_service(client: OBSClient, args) -> int:
    data = await client.get_stream_service()
    if args.json:
        _json_out(data)
    else:
        _info("Type", data.get("streamServiceType"))
        settings = data.get("streamServiceSettings", {})
        for k, v in settings.items():
            _info(k, v)
    return 0

# --- Studio Mode ---

async def cmd_studio_status(client: OBSClient, args) -> int:
    enabled = await client.get_studio_mode()
    if args.json:
        _json_out({"studioModeEnabled": enabled})
    else:
        print(f"  Studio Mode: {GREEN}Enabled{RESET}" if enabled else f"  Studio Mode: {DIM}Disabled{RESET}")
    return 0

async def cmd_studio_enable(client: OBSClient, args) -> int:
    await client.set_studio_mode(True)
    _ok("Studio Mode enabled")
    return 0

async def cmd_studio_disable(client: OBSClient, args) -> int:
    await client.set_studio_mode(False)
    _ok("Studio Mode disabled")
    return 0

# --- Hotkey ---

async def cmd_hotkey_list(client: OBSClient, args) -> int:
    hotkeys = await client.get_hotkey_list()
    if args.json:
        _json_out(hotkeys)
    else:
        for h in hotkeys:
            print(f"  {h}")
    return 0

async def cmd_hotkey_trigger(client: OBSClient, args) -> int:
    await client.trigger_hotkey(args.name)
    _ok(f"Triggered hotkey: {args.name}")
    return 0

# --- Monitor ---

async def cmd_monitor_list(client: OBSClient, args) -> int:
    monitors = await client.get_monitor_list()
    if args.json:
        _json_out(monitors)
    else:
        for m in monitors:
            print(f"  [{m.get('monitorIndex')}] {m.get('monitorName')} ({m.get('monitorWidth')}x{m.get('monitorHeight')})")
    return 0


# ---------------------------------------------------------------------------
# CLI Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="obs_cli",
        description="OBS Studio CLI for Huxley — controls OBS via WebSocket v5",
    )
    p.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.add_argument("--dry-run", action="store_true", help="Preview write operations")
    p.add_argument("--mock", action="store_true", help="Use mock data (no OBS needed)")
    p.add_argument("--url", default=None, help="WebSocket URL (default: ws://localhost:4455)")
    p.add_argument("--password", default=None, help="WebSocket password")

    sub = p.add_subparsers(dest="command", help="Command group")

    # Top-level commands
    sub.add_parser("status", help="Connection status and overview")
    sub.add_parser("version", help="OBS version info")
    sub.add_parser("stats", help="Session statistics")

    # --- scene ---
    scene = sub.add_parser("scene", help="Scene management")
    ss = scene.add_subparsers(dest="subcmd")
    ss.add_parser("list", help="List scenes")
    ss.add_parser("current", help="Get current scene")
    s = ss.add_parser("switch", help="Switch scene"); s.add_argument("name")
    s = ss.add_parser("create", help="Create scene"); s.add_argument("name")
    s = ss.add_parser("remove", help="Remove scene"); s.add_argument("name")
    s = ss.add_parser("preview", help="Get/set preview scene"); s.add_argument("name", nargs="?")
    ss.add_parser("transition", help="Trigger studio transition")

    # --- item ---
    item = sub.add_parser("item", help="Scene item management")
    si = item.add_subparsers(dest="subcmd")
    s = si.add_parser("list", help="List items"); s.add_argument("scene")
    s = si.add_parser("add", help="Add source to scene"); s.add_argument("scene"); s.add_argument("source"); s.add_argument("--disabled", action="store_true")
    s = si.add_parser("remove", help="Remove item"); s.add_argument("scene"); s.add_argument("item_id", type=int)
    s = si.add_parser("show", help="Show item"); s.add_argument("scene"); s.add_argument("item_id", type=int)
    s = si.add_parser("hide", help="Hide item"); s.add_argument("scene"); s.add_argument("item_id", type=int)
    s = si.add_parser("transform", help="Get transform"); s.add_argument("scene"); s.add_argument("item_id", type=int)
    s = si.add_parser("id", help="Get item ID"); s.add_argument("scene"); s.add_argument("source")

    # --- input ---
    inp = sub.add_parser("input", help="Input management")
    si = inp.add_subparsers(dest="subcmd")
    s = si.add_parser("list", help="List inputs"); s.add_argument("--kind", default=None)
    si.add_parser("kinds", help="List input kinds")
    s = si.add_parser("create", help="Create input"); s.add_argument("scene"); s.add_argument("name"); s.add_argument("kind"); s.add_argument("--settings", default=None)
    s = si.add_parser("remove", help="Remove input"); s.add_argument("name")
    s = si.add_parser("rename", help="Rename input"); s.add_argument("name"); s.add_argument("new_name")
    s = si.add_parser("settings", help="Get settings"); s.add_argument("name")
    s = si.add_parser("set", help="Set settings"); s.add_argument("name"); s.add_argument("--settings", required=True)
    s = si.add_parser("defaults", help="Get defaults"); s.add_argument("kind")

    # --- audio ---
    aud = sub.add_parser("audio", help="Audio controls")
    sa = aud.add_subparsers(dest="subcmd")
    s = sa.add_parser("mute", help="Get mute state"); s.add_argument("input")
    s = sa.add_parser("set-mute", help="Set mute"); s.add_argument("input"); s.add_argument("state", help="on/off")
    s = sa.add_parser("toggle-mute", help="Toggle mute"); s.add_argument("input")
    s = sa.add_parser("volume", help="Get volume"); s.add_argument("input")
    s = sa.add_parser("set-volume", help="Set volume"); s.add_argument("input"); s.add_argument("--db", type=float, default=None); s.add_argument("--mul", type=float, default=None)
    s = sa.add_parser("balance", help="Get balance"); s.add_argument("input")
    s = sa.add_parser("set-balance", help="Set balance"); s.add_argument("input"); s.add_argument("value", type=float)
    s = sa.add_parser("sync-offset", help="Get sync offset"); s.add_argument("input")
    s = sa.add_parser("set-sync-offset", help="Set sync offset"); s.add_argument("input"); s.add_argument("value", type=int)
    s = sa.add_parser("monitor-type", help="Get monitor type"); s.add_argument("input")
    s = sa.add_parser("set-monitor-type", help="Set monitor type"); s.add_argument("input"); s.add_argument("type")

    # --- source ---
    src = sub.add_parser("source", help="Source operations")
    ss = src.add_subparsers(dest="subcmd")
    s = ss.add_parser("active", help="Get active state"); s.add_argument("name")
    s = ss.add_parser("screenshot", help="Save screenshot"); s.add_argument("name"); s.add_argument("path"); s.add_argument("--format", default="png"); s.add_argument("--width", type=int, default=None); s.add_argument("--height", type=int, default=None)

    # --- stream ---
    strm = sub.add_parser("stream", help="Streaming controls")
    ss = strm.add_subparsers(dest="subcmd")
    ss.add_parser("status", help="Get stream status")
    ss.add_parser("start", help="Start streaming")
    ss.add_parser("stop", help="Stop streaming")
    ss.add_parser("toggle", help="Toggle streaming")
    s = ss.add_parser("caption", help="Send caption"); s.add_argument("text")

    # --- record ---
    rec = sub.add_parser("record", help="Recording controls")
    sr = rec.add_subparsers(dest="subcmd")
    sr.add_parser("status", help="Get record status")
    sr.add_parser("start", help="Start recording")
    sr.add_parser("stop", help="Stop recording")
    sr.add_parser("toggle", help="Toggle recording")
    sr.add_parser("pause", help="Pause recording")
    sr.add_parser("resume", help="Resume recording")
    sr.add_parser("split", help="Split recording file")
    s = sr.add_parser("chapter", help="Add chapter"); s.add_argument("name", nargs="?")

    # --- virtualcam ---
    vcam = sub.add_parser("virtualcam", help="Virtual camera")
    sv = vcam.add_subparsers(dest="subcmd")
    sv.add_parser("status", help="Get status")
    sv.add_parser("start", help="Start")
    sv.add_parser("stop", help="Stop")
    sv.add_parser("toggle", help="Toggle")

    # --- replay ---
    rep = sub.add_parser("replay", help="Replay buffer")
    sr = rep.add_subparsers(dest="subcmd")
    sr.add_parser("status", help="Get status")
    sr.add_parser("start", help="Start")
    sr.add_parser("stop", help="Stop")
    sr.add_parser("save", help="Save replay")
    sr.add_parser("last", help="Get last replay path")

    # --- output ---
    out = sub.add_parser("output", help="Output management")
    so = out.add_subparsers(dest="subcmd")
    so.add_parser("list", help="List outputs")
    s = so.add_parser("status", help="Get status"); s.add_argument("name")
    s = so.add_parser("start", help="Start output"); s.add_argument("name")
    s = so.add_parser("stop", help="Stop output"); s.add_argument("name")
    s = so.add_parser("settings", help="Get settings"); s.add_argument("name")
    s = so.add_parser("set", help="Set settings"); s.add_argument("name"); s.add_argument("--settings", required=True)

    # --- transition ---
    trn = sub.add_parser("transition", help="Transition controls")
    st = trn.add_subparsers(dest="subcmd")
    st.add_parser("list", help="List transitions")
    st.add_parser("current", help="Get current")
    s = st.add_parser("set", help="Set transition"); s.add_argument("name")
    s = st.add_parser("duration", help="Get/set duration"); s.add_argument("ms", type=int, nargs="?")
    st.add_parser("settings", help="Get settings")
    s = st.add_parser("set-settings", help="Set settings"); s.add_argument("--settings", required=True)
    st.add_parser("trigger", help="Trigger transition")

    # --- filter ---
    flt = sub.add_parser("filter", help="Filter management")
    sf = flt.add_subparsers(dest="subcmd")
    sf.add_parser("kinds", help="List filter kinds")
    s = sf.add_parser("list", help="List filters"); s.add_argument("source")
    s = sf.add_parser("defaults", help="Get defaults"); s.add_argument("kind")
    s = sf.add_parser("add", help="Add filter"); s.add_argument("source"); s.add_argument("name"); s.add_argument("kind"); s.add_argument("--settings", default=None)
    s = sf.add_parser("remove", help="Remove filter"); s.add_argument("source"); s.add_argument("name")
    s = sf.add_parser("info", help="Get filter info"); s.add_argument("source"); s.add_argument("name")
    s = sf.add_parser("enable", help="Enable filter"); s.add_argument("source"); s.add_argument("name")
    s = sf.add_parser("disable", help="Disable filter"); s.add_argument("source"); s.add_argument("name")
    s = sf.add_parser("set", help="Set settings"); s.add_argument("source"); s.add_argument("name"); s.add_argument("--settings", required=True)
    s = sf.add_parser("reorder", help="Set index"); s.add_argument("source"); s.add_argument("name"); s.add_argument("index", type=int)

    # --- config ---
    cfg = sub.add_parser("config", help="OBS configuration")
    sc = cfg.add_subparsers(dest="subcmd")
    sc.add_parser("collections", help="List scene collections")
    s = sc.add_parser("set-collection", help="Switch collection"); s.add_argument("name")
    s = sc.add_parser("create-collection", help="Create collection"); s.add_argument("name")
    sc.add_parser("profiles", help="List profiles")
    s = sc.add_parser("set-profile", help="Switch profile"); s.add_argument("name")
    s = sc.add_parser("create-profile", help="Create profile"); s.add_argument("name")
    s = sc.add_parser("remove-profile", help="Remove profile"); s.add_argument("name")
    sc.add_parser("video", help="Get video settings")
    sc.add_parser("stream-service", help="Get stream service settings")
    sc.add_parser("record-dir", help="Get record directory")
    s = sc.add_parser("set-record-dir", help="Set record directory"); s.add_argument("path")

    # --- studio ---
    stu = sub.add_parser("studio", help="Studio mode")
    ss = stu.add_subparsers(dest="subcmd")
    ss.add_parser("status", help="Get studio mode status")
    ss.add_parser("enable", help="Enable studio mode")
    ss.add_parser("disable", help="Disable studio mode")

    # --- hotkey ---
    hk = sub.add_parser("hotkey", help="Hotkey controls")
    sh = hk.add_subparsers(dest="subcmd")
    sh.add_parser("list", help="List hotkeys")
    s = sh.add_parser("trigger", help="Trigger hotkey"); s.add_argument("name")

    # --- monitor ---
    mon = sub.add_parser("monitor", help="Monitor info")
    sm = mon.add_subparsers(dest="subcmd")
    sm.add_parser("list", help="List monitors")

    return p


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

DISPATCH = {
    ("status", None): cmd_status,
    ("version", None): cmd_version,
    ("stats", None): cmd_stats,
    ("scene", "list"): cmd_scene_list,
    ("scene", "current"): cmd_scene_current,
    ("scene", "switch"): cmd_scene_switch,
    ("scene", "create"): cmd_scene_create,
    ("scene", "remove"): cmd_scene_remove,
    ("scene", "preview"): cmd_scene_preview,
    ("scene", "transition"): cmd_scene_transition,
    ("item", "list"): cmd_item_list,
    ("item", "add"): cmd_item_add,
    ("item", "remove"): cmd_item_remove,
    ("item", "show"): cmd_item_show,
    ("item", "hide"): cmd_item_hide,
    ("item", "transform"): cmd_item_transform,
    ("item", "id"): cmd_item_id,
    ("input", "list"): cmd_input_list,
    ("input", "kinds"): cmd_input_kinds,
    ("input", "create"): cmd_input_create,
    ("input", "remove"): cmd_input_remove,
    ("input", "rename"): cmd_input_rename,
    ("input", "settings"): cmd_input_settings,
    ("input", "set"): cmd_input_set,
    ("input", "defaults"): cmd_input_defaults,
    ("audio", "mute"): cmd_audio_mute,
    ("audio", "set-mute"): cmd_audio_set_mute,
    ("audio", "toggle-mute"): cmd_audio_toggle_mute,
    ("audio", "volume"): cmd_audio_volume,
    ("audio", "set-volume"): cmd_audio_set_volume,
    ("audio", "balance"): cmd_audio_balance,
    ("audio", "set-balance"): cmd_audio_set_balance,
    ("audio", "sync-offset"): cmd_audio_sync_offset,
    ("audio", "set-sync-offset"): cmd_audio_set_sync_offset,
    ("audio", "monitor-type"): cmd_audio_monitor_type,
    ("audio", "set-monitor-type"): cmd_audio_set_monitor_type,
    ("source", "active"): cmd_source_active,
    ("source", "screenshot"): cmd_source_screenshot,
    ("stream", "status"): cmd_stream_status,
    ("stream", "start"): cmd_stream_start,
    ("stream", "stop"): cmd_stream_stop,
    ("stream", "toggle"): cmd_stream_toggle,
    ("stream", "caption"): cmd_stream_caption,
    ("record", "status"): cmd_record_status,
    ("record", "start"): cmd_record_start,
    ("record", "stop"): cmd_record_stop,
    ("record", "toggle"): cmd_record_toggle,
    ("record", "pause"): cmd_record_pause,
    ("record", "resume"): cmd_record_resume,
    ("record", "split"): cmd_record_split,
    ("record", "chapter"): cmd_record_chapter,
    ("virtualcam", "status"): cmd_vcam_status,
    ("virtualcam", "start"): cmd_vcam_start,
    ("virtualcam", "stop"): cmd_vcam_stop,
    ("virtualcam", "toggle"): cmd_vcam_toggle,
    ("replay", "status"): cmd_replay_status,
    ("replay", "start"): cmd_replay_start,
    ("replay", "stop"): cmd_replay_stop,
    ("replay", "save"): cmd_replay_save,
    ("replay", "last"): cmd_replay_last,
    ("output", "list"): cmd_output_list,
    ("output", "status"): cmd_output_status,
    ("output", "start"): cmd_output_start,
    ("output", "stop"): cmd_output_stop,
    ("output", "settings"): cmd_output_settings,
    ("output", "set"): cmd_output_set,
    ("transition", "list"): cmd_transition_list,
    ("transition", "current"): cmd_transition_current,
    ("transition", "set"): cmd_transition_set,
    ("transition", "duration"): cmd_transition_duration,
    ("transition", "settings"): cmd_transition_settings,
    ("transition", "set-settings"): cmd_transition_set_settings,
    ("transition", "trigger"): cmd_transition_trigger,
    ("filter", "kinds"): cmd_filter_kinds,
    ("filter", "list"): cmd_filter_list,
    ("filter", "defaults"): cmd_filter_defaults,
    ("filter", "add"): cmd_filter_add,
    ("filter", "remove"): cmd_filter_remove,
    ("filter", "info"): cmd_filter_info,
    ("filter", "enable"): cmd_filter_enable,
    ("filter", "disable"): cmd_filter_disable,
    ("filter", "set"): cmd_filter_set,
    ("filter", "reorder"): cmd_filter_reorder,
    ("config", "collections"): cmd_config_collections,
    ("config", "set-collection"): cmd_config_set_collection,
    ("config", "create-collection"): cmd_config_create_collection,
    ("config", "profiles"): cmd_config_profiles,
    ("config", "set-profile"): cmd_config_set_profile,
    ("config", "create-profile"): cmd_config_create_profile,
    ("config", "remove-profile"): cmd_config_remove_profile,
    ("config", "video"): cmd_config_video,
    ("config", "stream-service"): cmd_config_stream_service,
    ("config", "record-dir"): cmd_config_record_dir,
    ("config", "set-record-dir"): cmd_config_set_record_dir,
    ("studio", "status"): cmd_studio_status,
    ("studio", "enable"): cmd_studio_enable,
    ("studio", "disable"): cmd_studio_disable,
    ("hotkey", "list"): cmd_hotkey_list,
    ("hotkey", "trigger"): cmd_hotkey_trigger,
    ("monitor", "list"): cmd_monitor_list,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _async_main(args) -> int:
    # Build connection
    if args.mock:
        conn = MockOBSConnection()
    else:
        url = args.url or os.environ.get("OBS_WEBSOCKET_URL", "ws://localhost:4455")
        password = args.password or os.environ.get("OBS_WEBSOCKET_PASSWORD")
        conn = OBSConnection(url=url, password=password)

    client = OBSClient(conn, dry_run=args.dry_run)

    try:
        await client.connect()
        # Resolve handler
        cmd = args.command
        subcmd = getattr(args, "subcmd", None)
        handler = DISPATCH.get((cmd, subcmd))
        if not handler:
            _err(f"Unknown command: {cmd} {subcmd or ''}")
            return 1
        return await handler(client, args)
    except OBSNotRunningError as e:
        _err(f"OBS not reachable: {e}")
        return 1
    except OBSAuthError as e:
        _err(f"Authentication failed: {e}")
        return 1
    except OBSRequestError as e:
        _err(f"Request failed: {e}")
        return 1
    except OBSTimeoutError as e:
        _err(f"Timeout: {e}")
        return 1
    except OBSError as e:
        _err(f"OBS error: {e}")
        return 1
    finally:
        await client.disconnect()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    if not args.command:
        parser.print_help()
        return 0

    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    sys.exit(main())
