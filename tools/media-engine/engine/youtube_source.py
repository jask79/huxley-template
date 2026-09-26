"""
YouTube Source Integration for the Media Workflow Engine.

Extracts metadata and transcripts from YouTube videos using the yt-transcript
CLI tool (tools/yt-transcript). The extracted context is formatted for prompt
injection so AI media generators can use video content as creative source
material.

Usage:
    from engine.youtube_source import YouTubeSource, YouTubeSourceError

    yt = YouTubeSource()
    metadata = yt.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    enriched_prompt = yt.build_prompt_context(metadata, user_prompt)
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Absolute path to the yt-transcript CLI tool
YT_TRANSCRIPT_TOOL = "{{CATALYST_ROOT}}/tools/yt-transcript"

# Maximum transcript length to inject into prompts (characters)
DEFAULT_TRANSCRIPT_LIMIT = 2000


class YouTubeSourceError(Exception):
    """Raised when YouTube source extraction fails."""


@dataclass
class YouTubeMetadata:
    """Structured metadata from a YouTube video."""
    video_id: str = ""
    url: str = ""
    title: str = ""
    channel: str = ""
    duration: str = ""
    description: str = ""
    upload_date: str = ""
    view_count: int | None = None
    chapters: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    transcript: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for serialization."""
        return {
            "video_id": self.video_id,
            "url": self.url,
            "title": self.title,
            "channel": self.channel,
            "duration": self.duration,
            "description": self.description,
            "upload_date": self.upload_date,
            "view_count": self.view_count,
            "chapters": self.chapters,
            "tags": self.tags,
            "transcript_length": len(self.transcript),
        }


class YouTubeSource:
    """
    Wraps the yt-transcript CLI tool for YouTube video metadata and
    transcript extraction.

    All operations are non-fatal by design: extraction failures produce
    warnings rather than blocking media generation.
    """

    def __init__(
        self,
        tool_path: str | None = None,
        transcript_limit: int = DEFAULT_TRANSCRIPT_LIMIT,
    ) -> None:
        """
        Args:
            tool_path: Override path to the yt-transcript tool.
            transcript_limit: Max chars of transcript to include in prompts.
        """
        self.tool_path = tool_path or YT_TRANSCRIPT_TOOL
        self.transcript_limit = transcript_limit

    def is_available(self) -> bool:
        """Check if the yt-transcript tool exists and is executable."""
        tool = Path(self.tool_path)
        return tool.exists() and tool.stat().st_mode & 0o111 != 0

    def extract(self, url: str) -> YouTubeMetadata:
        """
        Extract metadata and transcript from a YouTube URL.

        Calls the yt-transcript tool with --json flag and parses the
        structured output.

        Args:
            url: YouTube video URL or video ID.

        Returns:
            YouTubeMetadata with all available fields populated.

        Raises:
            YouTubeSourceError: If the tool is not available or extraction
                fails completely.
        """
        if not self.is_available():
            raise YouTubeSourceError(
                f"yt-transcript tool not found at {self.tool_path}. "
                "Ensure tools/yt-transcript exists and is executable."
            )

        video_id = self._extract_video_id(url)

        try:
            result = subprocess.run(
                [self.tool_path, url, "--json"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise YouTubeSourceError(
                f"yt-transcript timed out after 120s for {url}"
            )
        except FileNotFoundError:
            raise YouTubeSourceError(
                f"yt-transcript tool not found at {self.tool_path}"
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise YouTubeSourceError(
                f"yt-transcript failed (exit {result.returncode}): {stderr}"
            )

        # Parse JSON output
        raw_output = result.stdout.strip()
        if not raw_output:
            raise YouTubeSourceError(
                f"yt-transcript returned empty output for {url}"
            )

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise YouTubeSourceError(
                f"yt-transcript returned invalid JSON: {exc}"
            ) from exc

        return self._parse_metadata(data, url, video_id)

    def build_prompt_context(
        self,
        metadata: YouTubeMetadata,
        user_prompt: str,
        include_transcript: bool = True,
        include_chapters: bool = True,
    ) -> str:
        """
        Build an enriched prompt by injecting YouTube context.

        Prepends structured YouTube metadata to the user's prompt with
        clear section markers. Long transcripts are truncated to
        self.transcript_limit characters.

        Args:
            metadata: Extracted YouTube metadata.
            user_prompt: The original user prompt.
            include_transcript: Whether to include transcript text.
            include_chapters: Whether to include chapter markers.

        Returns:
            Enriched prompt string with YouTube context prepended.
        """
        sections: list[str] = []

        # Header with video info
        header_parts = [f"[YouTube Source: {metadata.title}]"]
        if metadata.channel:
            header_parts.append(f"Channel: {metadata.channel}")
        if metadata.duration:
            header_parts.append(f"Duration: {metadata.duration}")
        sections.append("\n".join(header_parts))

        # Description excerpt (first 500 chars)
        if metadata.description:
            desc = metadata.description[:500]
            if len(metadata.description) > 500:
                desc += "..."
            sections.append(f"[Description]\n{desc}")

        # Chapters
        if include_chapters and metadata.chapters:
            chapter_lines = ["[Chapters]"]
            for ch in metadata.chapters[:20]:  # Cap at 20 chapters
                start = ch.get("start_time", 0)
                mins = int(start // 60)
                secs = int(start % 60)
                chapter_lines.append(f"  [{mins:02d}:{secs:02d}] {ch.get('title', '')}")
            sections.append("\n".join(chapter_lines))

        # Transcript excerpt
        if include_transcript and metadata.transcript:
            transcript = metadata.transcript
            if len(transcript) > self.transcript_limit:
                transcript = transcript[:self.transcript_limit] + "... [truncated]"
            sections.append(f"[Transcript excerpt]\n{transcript}")

        # Combine with separator
        youtube_context = "\n\n".join(sections)

        return f"{youtube_context}\n\n---\n\n{user_prompt}"

    def build_provenance_data(self, metadata: YouTubeMetadata) -> dict[str, Any]:
        """
        Build provenance-ready metadata dict for a YouTube source.

        Args:
            metadata: Extracted YouTube metadata.

        Returns:
            Dict suitable for inclusion in provenance records.
        """
        return {
            "video_id": metadata.video_id,
            "url": metadata.url,
            "title": metadata.title,
            "channel": metadata.channel,
            "duration": metadata.duration,
            "upload_date": metadata.upload_date,
            "transcript_length": len(metadata.transcript),
            "chapter_count": len(metadata.chapters),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_video_id(url: str) -> str:
        """Extract YouTube video ID from various URL formats."""
        # Already a plain video ID (11 chars)
        if re.match(r"^[a-zA-Z0-9_-]{11}$", url):
            return url

        # Standard watch URL
        match = re.search(r"v=([a-zA-Z0-9_-]{11})", url)
        if match:
            return match.group(1)

        # Short URL
        match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
        if match:
            return match.group(1)

        # Shorts URL
        match = re.search(r"shorts/([a-zA-Z0-9_-]{11})", url)
        if match:
            return match.group(1)

        # Return the input as-is if no pattern matches
        return url

    def _parse_metadata(
        self,
        data: dict[str, Any],
        url: str,
        video_id: str,
    ) -> YouTubeMetadata:
        """Parse raw JSON output from yt-transcript into YouTubeMetadata."""
        # The yt-transcript --json output has metadata fields at top level
        # and a "transcript" key with the full transcript text
        transcript_raw = data.get("transcript", "")

        # If transcript is a list of segments (timestamped mode), join them
        if isinstance(transcript_raw, list):
            transcript_raw = " ".join(
                seg.get("text", "") if isinstance(seg, dict) else str(seg)
                for seg in transcript_raw
            )

        # Clean transcript: collapse whitespace, strip
        transcript = " ".join(transcript_raw.split()).strip()

        # Parse upload date
        upload_date = data.get("upload_date", "")
        if upload_date and len(upload_date) == 8 and upload_date.isdigit():
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

        return YouTubeMetadata(
            video_id=video_id,
            url=url,
            title=data.get("title", ""),
            channel=data.get("uploader", data.get("channel", "")),
            duration=data.get("duration_string", ""),
            description=data.get("description", ""),
            upload_date=upload_date,
            view_count=data.get("view_count"),
            chapters=data.get("chapters") or [],
            tags=data.get("tags") or [],
            transcript=transcript,
        )
