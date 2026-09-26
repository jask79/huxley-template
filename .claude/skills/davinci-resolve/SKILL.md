# DaVinci Resolve CLI — Programmatic Video Editing

## Description
CLI tool wrapping DaVinci Resolve's Python Scripting API for programmatic video editing, color grading, and rendering. Connects to a running Resolve instance and provides 30 subcommands covering projects, media pool, timelines, markers, color, and rendering.

**Requires:** DaVinci Resolve Studio (paid, $295 one-time) for external scripting
**Binary:** `python3 {{CATALYST_ROOT}}/tools/davinci_resolve.py`
**Dependencies:** None (stdlib only)
**Auth:** Connects to running Resolve instance via local IPC (no API keys needed)

---

## Global Flags

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Debug logging |
| `--json` | Machine-readable JSON output |
| `--dry-run` | Preview write/delete operations without executing |
| `--mock` | Use fake data (test CLI without Resolve running) |

**Note:** Global flags go BEFORE the subcommand: `davinci_resolve.py --json project list`

---

## System Commands

```bash
# Check connection, version, current state
python3 tools/davinci_resolve.py status

# Get or set current page (media, cut, edit, fusion, color, fairlight, deliver)
python3 tools/davinci_resolve.py page
python3 tools/davinci_resolve.py page color
```

---

## Project Management

```bash
# List all projects in current database
python3 tools/davinci_resolve.py project list

# Get current project details (or specify by name)
python3 tools/davinci_resolve.py project info
python3 tools/davinci_resolve.py project info "Brand Launch 2026"

# Create new project with optional settings
python3 tools/davinci_resolve.py project create "New Project" --fps 24 --width 3840 --height 2160

# Load/switch to a project
python3 tools/davinci_resolve.py project load "My Project"

# Save current project
python3 tools/davinci_resolve.py project save

# View all project settings
python3 tools/davinci_resolve.py project settings

# Set a specific project setting
python3 tools/davinci_resolve.py project set timelineFrameRate 30
```

---

## Media Pool

```bash
# Import files into media pool
python3 tools/davinci_resolve.py media import /path/to/video.mov /path/to/audio.wav

# Import into a specific folder
python3 tools/davinci_resolve.py media import /path/to/clip.mp4 --folder "B-Roll"

# List clips in media pool (optionally in a folder)
python3 tools/davinci_resolve.py media list
python3 tools/davinci_resolve.py media list --folder "Interviews"

# Get clip details
python3 tools/davinci_resolve.py media info "Interview_A_001.mov"

# List media pool folder structure
python3 tools/davinci_resolve.py media folders
```

---

## Timeline & Editing

```bash
# List all timelines
python3 tools/davinci_resolve.py timeline list

# Create empty timeline
python3 tools/davinci_resolve.py timeline create "Assembly Edit"

# Get timeline details (current or by name)
python3 tools/davinci_resolve.py timeline info
python3 tools/davinci_resolve.py timeline info "Main Edit v2"

# Append clips to current timeline
python3 tools/davinci_resolve.py timeline add-clips "Interview_A_001.mov" "B-Roll_City.mp4"

# List tracks on current timeline
python3 tools/davinci_resolve.py timeline tracks

# List items on a specific track
python3 tools/davinci_resolve.py timeline items --track-type video --track-index 1
```

---

## Markers

```bash
# List markers on current timeline
python3 tools/davinci_resolve.py marker list

# List markers on a specific timeline
python3 tools/davinci_resolve.py marker list --timeline "Main Edit v2"

# Add marker (valid colors: Blue, Cyan, Green, Yellow, Red, Pink, Purple, Fuchsia, Rose, Lavender, Sky, Mint, Lemon, Sand, Cocoa, Cream)
python3 tools/davinci_resolve.py marker add 86400 Green "In Point" --note "Start here" --duration 1

# Delete marker at frame
python3 tools/davinci_resolve.py marker delete 86400
```

---

## Color Grading

```bash
# Apply LUT to current clip (optionally specify node index)
python3 tools/davinci_resolve.py color apply-lut /path/to/look.cube
python3 tools/davinci_resolve.py color apply-lut /path/to/look.cube --node 2

# Apply DaVinci grade from DRX file (modes: 0=add, 1=replace)
python3 tools/davinci_resolve.py color apply-grade /path/to/grade.drx --mode 0

# Export LUT from current clip
python3 tools/davinci_resolve.py color export-lut /path/to/output.cube --type cube
```

---

## Rendering

```bash
# List available render presets
python3 tools/davinci_resolve.py render presets

# Add render job with preset
python3 tools/davinci_resolve.py render add --preset "YouTube 4K" --output /path/to/exports --name "final_export"

# Add render job with format/codec
python3 tools/davinci_resolve.py render add --format mp4 --codec H265 --output /path/to/exports

# List render queue
python3 tools/davinci_resolve.py render list

# Start rendering (optionally wait for completion with progress)
python3 tools/davinci_resolve.py render start
python3 tools/davinci_resolve.py render start --wait

# Check render status
python3 tools/davinci_resolve.py render status

# Stop rendering
python3 tools/davinci_resolve.py render stop

# Clear render queue (use --dry-run to preview)
python3 tools/davinci_resolve.py render clear
```

---

## Common Workflows

### Import-Edit-Export Pipeline
```bash
# 1. Create project
python3 tools/davinci_resolve.py project create "Client Project" --fps 24 --width 3840 --height 2160

# 2. Import media
python3 tools/davinci_resolve.py media import /Volumes/Media/interview.mov /Volumes/Media/broll/*.mp4

# 3. Create timeline and add clips
python3 tools/davinci_resolve.py timeline create "Assembly"
python3 tools/davinci_resolve.py timeline add-clips "interview.mov" "broll_01.mp4" "broll_02.mp4"

# 4. Add markers for review
python3 tools/davinci_resolve.py marker add 1440 Yellow "Review" --note "Check audio sync"

# 5. Apply color grade
python3 tools/davinci_resolve.py color apply-lut /path/to/look.cube

# 6. Render
python3 tools/davinci_resolve.py render add --preset "ProRes Master" --output /Volumes/Exports
python3 tools/davinci_resolve.py render start --wait
```

### Batch Render Multiple Timelines
```bash
# Get all timelines as JSON, iterate
python3 tools/davinci_resolve.py --json timeline list | python3 -c "
import json, sys, subprocess
for tl in json.load(sys.stdin):
    subprocess.run(['python3', 'tools/davinci_resolve.py', 'timeline', 'info', tl['name']])
"
```

---

## Testing Without Resolve

```bash
# All commands work with --mock flag (realistic fake data, no Resolve needed)
python3 tools/davinci_resolve.py --mock status
python3 tools/davinci_resolve.py --mock --json project list
python3 tools/davinci_resolve.py --mock timeline list
```
