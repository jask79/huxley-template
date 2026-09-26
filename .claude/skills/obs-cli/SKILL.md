# OBS Studio CLI — Programmatic Production Control

## Description
CLI tool for controlling OBS Studio via WebSocket v5 protocol. Manages scenes, inputs, audio, streaming, recording, transitions, filters, and configuration. Connects to a running OBS instance on port 4455.

**Requires:** OBS Studio with WebSocket server enabled (Tools > WebSocket Server Settings)
**Binary:** `python3 {{CATALYST_ROOT}}/tools/obs_cli.py`
**Dependencies:** websockets (pip, v16.0)
**Auth:** Optional password via `OBS_WEBSOCKET_PASSWORD` env var

---

## Global Flags

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Debug logging |
| `--json` | Machine-readable JSON output |
| `--dry-run` | Preview mutations without executing |
| `--mock` | Use fake data (test CLI without OBS running) |
| `--url URL` | WebSocket URL (default: `ws://localhost:4455`) |
| `--password PW` | WebSocket password |

**Note:** Global flags go BEFORE the subcommand: `obs_cli.py --json scene list`

---

## Status & Info

```bash
python3 tools/obs_cli.py status            # Connection + version + current state
python3 tools/obs_cli.py version           # Detailed OBS version info
python3 tools/obs_cli.py stats             # CPU, memory, FPS, frame stats
```

---

## Scene Management

```bash
python3 tools/obs_cli.py scene list                    # List all scenes
python3 tools/obs_cli.py scene current                 # Get current program scene
python3 tools/obs_cli.py scene switch "Scene Name"     # Switch to scene
python3 tools/obs_cli.py scene create "New Scene"      # Create scene
python3 tools/obs_cli.py scene remove "Old Scene"      # Remove scene
python3 tools/obs_cli.py scene preview                 # Get preview scene (Studio Mode)
python3 tools/obs_cli.py scene preview "Scene Name"    # Set preview scene
python3 tools/obs_cli.py scene transition              # Trigger studio mode transition
```

---

## Scene Items

```bash
python3 tools/obs_cli.py item list "Scene Name"                # List items in scene
python3 tools/obs_cli.py item add "Scene" "Source" [--disabled] # Add source to scene
python3 tools/obs_cli.py item remove "Scene" 1                 # Remove item by ID
python3 tools/obs_cli.py item show "Scene" 1                   # Enable item
python3 tools/obs_cli.py item hide "Scene" 1                   # Disable item
python3 tools/obs_cli.py item transform "Scene" 1              # Get position/scale/crop
python3 tools/obs_cli.py item id "Scene" "Source Name"         # Get item ID by source name
```

---

## Input Management

```bash
python3 tools/obs_cli.py input list [--kind av_capture_input_v2]   # List inputs
python3 tools/obs_cli.py input kinds                                # List available input kinds
python3 tools/obs_cli.py input create "Scene" "Name" "kind"        # Create input
python3 tools/obs_cli.py input remove "Name"                       # Remove input
python3 tools/obs_cli.py input rename "Old" "New"                  # Rename input
python3 tools/obs_cli.py input settings "Name"                     # Get settings (JSON)
python3 tools/obs_cli.py input set "Name" --settings '{"key":"val"}'  # Set settings
python3 tools/obs_cli.py input defaults "input_kind"               # Get default settings
```

---

## Audio Control

```bash
python3 tools/obs_cli.py audio mute "Mic/Aux"              # Get mute state
python3 tools/obs_cli.py audio set-mute "Mic/Aux" on       # Mute
python3 tools/obs_cli.py audio set-mute "Mic/Aux" off      # Unmute
python3 tools/obs_cli.py audio toggle-mute "Mic/Aux"       # Toggle mute
python3 tools/obs_cli.py audio volume "Mic/Aux"            # Get volume (dB + multiplier)
python3 tools/obs_cli.py audio set-volume "Mic/Aux" --db -3.0    # Set volume in dB
python3 tools/obs_cli.py audio set-volume "Mic/Aux" --mul 0.5    # Set volume multiplier
python3 tools/obs_cli.py audio balance "Mic/Aux"           # Get stereo balance
python3 tools/obs_cli.py audio set-balance "Mic/Aux" 0.5   # Set balance (0.0-1.0)
python3 tools/obs_cli.py audio sync-offset "Mic/Aux"       # Get sync offset
python3 tools/obs_cli.py audio set-sync-offset "Mic/Aux" 50  # Set offset in ms
python3 tools/obs_cli.py audio monitor-type "Mic/Aux"      # Get monitor type
python3 tools/obs_cli.py audio set-monitor-type "Mic/Aux" OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT
```

---

## Sources

```bash
python3 tools/obs_cli.py source active "Webcam"              # Check if source is active
python3 tools/obs_cli.py source screenshot "Webcam" out.png   # Save screenshot
python3 tools/obs_cli.py source screenshot "Webcam" out.jpg --format jpg --width 1920
```

---

## Streaming

```bash
python3 tools/obs_cli.py stream status     # Get stream status
python3 tools/obs_cli.py stream start      # Start streaming
python3 tools/obs_cli.py stream stop       # Stop streaming
python3 tools/obs_cli.py stream toggle     # Toggle streaming
python3 tools/obs_cli.py stream caption "Hello viewers"  # Send CEA-608 caption
```

---

## Recording

```bash
python3 tools/obs_cli.py record status     # Get record status
python3 tools/obs_cli.py record start      # Start recording
python3 tools/obs_cli.py record stop       # Stop recording (prints output path)
python3 tools/obs_cli.py record toggle     # Toggle recording
python3 tools/obs_cli.py record pause      # Pause recording
python3 tools/obs_cli.py record resume     # Resume recording
python3 tools/obs_cli.py record split      # Split recording file
python3 tools/obs_cli.py record chapter    # Add chapter marker
python3 tools/obs_cli.py record chapter "Intro"  # Add named chapter
```

---

## Virtual Camera

```bash
python3 tools/obs_cli.py virtualcam status    # Get virtual camera status
python3 tools/obs_cli.py virtualcam start     # Start virtual camera
python3 tools/obs_cli.py virtualcam stop      # Stop virtual camera
python3 tools/obs_cli.py virtualcam toggle    # Toggle virtual camera
```

---

## Replay Buffer

```bash
python3 tools/obs_cli.py replay status     # Replay buffer status
python3 tools/obs_cli.py replay start      # Start replay buffer
python3 tools/obs_cli.py replay stop       # Stop replay buffer
python3 tools/obs_cli.py replay save       # Save replay
python3 tools/obs_cli.py replay last       # Get last replay file path
```

---

## Outputs

```bash
python3 tools/obs_cli.py output list                           # List all outputs
python3 tools/obs_cli.py output status "adv_stream"           # Get output status
python3 tools/obs_cli.py output start "adv_stream"            # Start output
python3 tools/obs_cli.py output stop "adv_stream"             # Stop output
python3 tools/obs_cli.py output settings "adv_stream"         # Get output settings
python3 tools/obs_cli.py output set "adv_stream" --settings '{"key":"val"}'
```

---

## Transitions

```bash
python3 tools/obs_cli.py transition list              # List available transitions
python3 tools/obs_cli.py transition current           # Current transition info
python3 tools/obs_cli.py transition set "Fade"        # Set current transition
python3 tools/obs_cli.py transition duration          # Get duration
python3 tools/obs_cli.py transition duration 500      # Set duration (ms)
python3 tools/obs_cli.py transition settings          # Get transition settings
python3 tools/obs_cli.py transition set-settings '{}' # Set transition settings
python3 tools/obs_cli.py transition trigger           # Trigger studio mode transition
```

---

## Filters

```bash
python3 tools/obs_cli.py filter kinds                          # List filter kinds
python3 tools/obs_cli.py filter list "Webcam"                 # List filters on source
python3 tools/obs_cli.py filter defaults "color_filter_v2"    # Default filter settings
python3 tools/obs_cli.py filter add "Webcam" "CC" "color_filter_v2"   # Add filter
python3 tools/obs_cli.py filter add "Webcam" "CC" "color_filter_v2" --settings '{"brightness":0.1}'
python3 tools/obs_cli.py filter remove "Webcam" "CC"          # Remove filter
python3 tools/obs_cli.py filter info "Webcam" "CC"            # Get filter info
python3 tools/obs_cli.py filter enable "Webcam" "CC"          # Enable filter
python3 tools/obs_cli.py filter disable "Webcam" "CC"         # Disable filter
python3 tools/obs_cli.py filter set "Webcam" "CC" --settings '{"brightness":0.2}'
python3 tools/obs_cli.py filter reorder "Webcam" "CC" 0       # Move to index
```

---

## Configuration

```bash
python3 tools/obs_cli.py config collections              # List scene collections
python3 tools/obs_cli.py config set-collection "Default" # Switch collection
python3 tools/obs_cli.py config create-collection "New"  # Create collection
python3 tools/obs_cli.py config profiles                 # List profiles
python3 tools/obs_cli.py config set-profile "Stream"     # Switch profile
python3 tools/obs_cli.py config create-profile "New"     # Create profile
python3 tools/obs_cli.py config remove-profile "Old"     # Remove profile
python3 tools/obs_cli.py config video                    # Get video settings
python3 tools/obs_cli.py config stream-service           # Get stream service settings
python3 tools/obs_cli.py config record-dir               # Get record directory
python3 tools/obs_cli.py config set-record-dir /path     # Set record directory
```

---

## Studio Mode

```bash
python3 tools/obs_cli.py studio status     # Studio mode status
python3 tools/obs_cli.py studio enable     # Enable studio mode
python3 tools/obs_cli.py studio disable    # Disable studio mode
```

---

## Hotkeys & Monitors

```bash
python3 tools/obs_cli.py hotkey list                           # List all hotkeys
python3 tools/obs_cli.py hotkey trigger "OBSBasic.StartRecording"  # Trigger hotkey
python3 tools/obs_cli.py monitor list                          # List connected monitors
```
