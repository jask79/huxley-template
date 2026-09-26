# YouTube Transcript Extraction

Extract video metadata and transcripts from YouTube URLs for LLM consumption.

## Tool

`tools/yt-transcript` — Bash wrapper combining `yt-dlp` (metadata) + `youtube_transcript_api` (transcript).

## Dependencies

- `yt-dlp` (install via `brew install yt-dlp`)
- `youtube_transcript_api` (pipx, installed at `{{HOME_DIR}}/.local/bin/youtube_transcript_api`)

## Usage

```bash
# Full output: metadata + transcript (default)
tools/yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"

# Transcript only (most common for LLM context)
tools/yt-transcript VIDEO_ID --transcript-only

# Metadata only (title, channel, duration, chapters, tags)
tools/yt-transcript URL --metadata-only

# With timestamps in transcript
tools/yt-transcript URL --timestamps

# Structured JSON output
tools/yt-transcript URL --json

# Different language
tools/yt-transcript URL --lang es
```

## URL Formats Supported

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- Bare video ID: `VIDEO_ID`

## Output Modes

| Flag | Output |
|------|--------|
| (default) | Metadata header + transcript text |
| `--json` | Single JSON object with all fields + transcript |
| `--metadata-only` | Title, channel, duration, views, chapters, tags, description |
| `--transcript-only` | Raw transcript text only |
| `--timestamps` | Transcript with timing data (JSON format) |

## When to Use

- User sends a YouTube link and asks about content
- Research tasks requiring video content analysis
- Content analysis, summarization, or extraction workflows
- Media Engine workflows that reference YouTube source material

## Limitations

- Cannot process video frames (audio/visual content beyond captions)
- Requires captions to exist (manual or auto-generated)
- Auto-generated captions may have transcription errors
- Some videos have captions disabled by the creator
