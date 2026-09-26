# DaVinci Resolve CLI — Reference

## Overview

CLI tool at `tools/davinci_resolve.py` wrapping DaVinci Resolve's native Python Scripting API. Single-file, stdlib-only, 2,893 lines. Follows the `apple_provision.py` 4-layer architecture.

## Prerequisites

- **DaVinci Resolve Studio** (paid, $295 one-time) — free version blocks external scripting
- Resolve must be running (or use `--mock` for testing)
- macOS: Auto-detects paths at `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/`

## Architecture

```
CLI Parser (argparse) → Command Handlers (cmd_*) → ResolveClient → ResolveConnection
```

- **ResolveConnection**: Auto-detects macOS paths, imports `DaVinciResolveScript`, connects via `fusionscript.so`
- **ResolveClient**: Wraps every API call with error handling, dry-run, returns dataclasses
- **Command Handlers**: 26 functions, each returns 0 (success) / 1 (failure)
- **CLI Parser**: Nested subparsers, global flags before subcommand

## API Coverage

| Domain | Commands | Key Resolve API Methods |
|--------|----------|------------------------|
| System | `status`, `page` | `GetVersion()`, `GetCurrentPage()`, `OpenPage()` |
| Projects | `project list/info/create/load/save/settings/set` | `CreateProject()`, `LoadProject()`, `GetSetting()`, `SetSetting()` |
| Media | `media import/list/info/folders` | `ImportMedia()`, `GetClipList()`, `GetClipProperty()` |
| Timeline | `timeline list/create/info/add-clips/tracks/items` | `CreateEmptyTimeline()`, `AppendToTimeline()`, `GetItemListInTrack()` |
| Markers | `marker list/add/delete` | `AddMarker()`, `GetMarkers()`, `DeleteMarkerAtFrame()` |
| Color | `color apply-lut/apply-grade/export-lut` | `SetLUT()`, `ApplyGradeFromDRX()`, `ExportLUT()` |
| Render | `render presets/add/list/start/status/stop/clear` | `AddRenderJob()`, `StartRendering()`, `GetRenderJobList()` |

## Key API Notes

- **1-based indexing** for timelines and tracks (matches Resolve UI)
- **Valid marker colors**: Blue, Cyan, Green, Yellow, Red, Pink, Purple, Fuchsia, Rose, Lavender, Sky, Mint, Lemon, Sand, Cocoa, Cream
- **Valid pages**: media, cut, edit, fusion, color, fairlight, deliver
- `StartRendering()` blocks — use `--wait` flag with progress polling
- Connection is lazy — only established on first property access

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `ResolveNotRunningError` | Resolve not launched | Launch DaVinci Resolve |
| `ResolveScriptingDisabledError` | `scriptapp()` returns None | Enable in Preferences > System > General > External scripting |
| `ResolveProjectNotFoundError` | `LoadProject()` fails | Lists available projects in error message |
| `ResolveTimelineNotFoundError` | Timeline doesn't exist | Lists available timelines in error message |

## Environment Variables (Optional)

Auto-detected on macOS. Override with:
```bash
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
```

## Dataclasses

`ResolveStatus`, `ProjectInfo`, `ProjectSettings`, `ClipInfo`, `FolderInfo`, `TimelineInfo`, `TrackInfo`, `TimelineItemInfo`, `MarkerInfo`, `RenderJobInfo`, `ImportResult`

All serializable to JSON via `--json` flag.

## Complementary Tools

The Resolve CLI is the professional finishing tool. Other tools cover gaps it doesn't address:

| Gap | Tool | Status |
|-----|------|--------|
| Text animation, motion graphics, title cards | **Remotion** (`.claude/skills/community/remotion/`) | Installed, skill: `remotion-video` |
| Batch transcoding, format conversion | **PyAV** (FFmpeg Python bindings) | Not yet integrated |
| Editorial timeline interchange | **OTIO** (OpenTimelineIO) | Not yet integrated |
| Headless batch rendering (no GUI) | **FFmpeg** / **PyAV** | Available via system install |

**Pipeline:** Remotion renders text/motion graphics → MP4 → Resolve CLI `media import` → `timeline add-clips` → `color apply-lut` → `render start`

**What Resolve does that nothing else matches:** Color grading, Fairlight audio, Fusion VFX, professional codec rendering. These are NOT being replaced.
