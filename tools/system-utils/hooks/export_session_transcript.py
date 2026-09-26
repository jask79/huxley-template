#!/usr/bin/env python3
"""Stop hook: detect user corrections in session transcript and write memory files.

Scans the session JSONL for correction/preference signals in user messages,
extracts the correction context, and writes feedback_*.md files to the
Huxley memory directory. No LLM calls -- pure regex/keyword matching.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path("{{HOME_DIR}}/.claude/projects/{{CLAUDE_PROJECT_SLUG}}/memory")
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"
LOG_FILE = Path("{{CATALYST_ROOT}}/logs/feedback-capture.log")

# Patterns that signal a correction or strong preference in user messages.
# Intentionally narrow — false positives are worse than false negatives here.
CORRECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bno[,.]?\s+(don'?t|never|not that|stop|that'?s (wrong|not))",
        r"\bdon'?t do that\b",
        r"\bstop doing\b",
        r"\bnever\s+(do|use|call|run|say|add|create|put|write|make)\s+\w",
        r"\buse\s+\w[\w\s]{0,20}\s+not\s+\w",
        r"\bthat'?s not what i\b",
        r"\balways use\b",
        r"\bfrom now on\b",
        r"\bi already told you\b",
        r"\bhow many times\b",
        r"\bdo not\s+(do|use|call|run|say|add|create|put|write|make)\s+\w",
    ]
]

# Patterns indicating the message is mostly pasted content, not a direct correction
PASTE_MARKERS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"<task-notification>",
        r"<system-reminder>",
        r"SessionStart:startup hook",
        r"^```",
        r"^\s*❯\s",  # terminal prompt paste
        r"^\s*⏺\s",  # claude code output marker
        r"^\s*│\s",  # box-drawing from pasted terminal output
        r"Stop hook (blocking|feedback)",
        r"AUTOMATIC_TURN_REVIEW",
    ]
]

MIN_USER_MESSAGES = 4
MAX_USER_TEXT_FOR_CORRECTION = 600  # Corrections are usually short
MAX_SLUG_LEN = 40


def log(msg: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
    except Exception:  # noqa: S110
        pass


def _extract_text(message: object) -> str:
    """Extract plain text from a JSONL message field (same pattern as auto_rename_session.py)."""
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)
    return str(content) if content else ""


def _clean_text(text: str) -> str:
    """Strip system-reminder blocks and excess whitespace."""
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
    return text.strip()


def load_transcript(transcript_path: str) -> list[dict]:
    """Load transcript as list of {type, text} dicts."""
    entries = []
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg_type = obj.get("type")
                if msg_type not in ("user", "assistant"):
                    continue
                text = _clean_text(_extract_text(obj.get("message", "")))
                if text:
                    entries.append({"type": msg_type, "text": text})
    except Exception as e:
        log(f"Error reading transcript: {e}")
    return entries


def looks_like_paste(text: str) -> bool:
    """True if the message looks like pasted content (transcript, terminal output, system blocks)."""
    # Count paste markers — any single strong match rejects the message
    for p in PASTE_MARKERS:
        if p.search(text):
            return True
    # If more than 30% of lines start with quote-like prefixes, it's pasted
    lines = text.split("\n")
    if len(lines) > 10:
        pasted = sum(1 for ln in lines if ln.lstrip().startswith((">", "│", "⏺", "❯", "|")))
        if pasted / len(lines) > 0.30:
            return True
    return False


def is_correction(text: str) -> bool:
    if len(text) > MAX_USER_TEXT_FOR_CORRECTION:
        return False
    if looks_like_paste(text):
        return False
    return any(p.search(text) for p in CORRECTION_PATTERNS)


def make_slug(text: str) -> str:
    """Turn correction text into a filesystem-safe slug."""
    # Strip common filler at start
    filler_re = r"^(no[,.]?\s+|please\s+|don'?t\s+|never\s+|stop\s+)"
    text = re.sub(filler_re, "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    text = re.sub(r"\s+", "_", text.strip())
    return text[:MAX_SLUG_LEN].strip("_")


def slug_exists(slug: str) -> bool:
    """Check if a feedback file with this slug (or close variant) already exists."""
    target = MEMORY_DIR / f"feedback_{slug}.md"
    if target.exists():
        return True
    # Fuzzy: check if any existing feedback file shares >60% of slug tokens
    slug_tokens = set(slug.split("_"))
    for existing in MEMORY_DIR.glob("feedback_*.md"):
        ex_tokens = set(existing.stem.replace("feedback_", "").split("_"))
        if len(slug_tokens) >= 2 and len(ex_tokens) >= 2:
            overlap = len(slug_tokens & ex_tokens) / max(len(slug_tokens), len(ex_tokens))
            if overlap > 0.60:
                return True
    return False


def write_memory(slug: str, user_text: str, assistant_text: str) -> bool:
    """Write a feedback_*.md memory file."""
    path = MEMORY_DIR / f"feedback_{slug}.md"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # One-line description: first sentence of user correction, truncated
    first_sentence = re.split(r"[.!?\n]", user_text)[0].strip()[:100]

    # How-to-apply: include the assistant context if short enough
    context_note = ""
    if assistant_text:
        snip = assistant_text[:200].replace("\n", " ")
        ellipsis = "..." if len(assistant_text) > 200 else ""
        context_note = f'\n\n**Context:** In response to: "{snip}{ellipsis}"'

    # Sanitize for YAML frontmatter: strip newlines, escape colons
    safe_desc = first_sentence.replace("\n", " ").replace(":", " -")
    safe_desc = safe_desc.replace("---", "- -")

    content = f"""---
name: feedback_{slug}
description: "{safe_desc}"
type: feedback
---

{user_text[:500]}
{context_note}

**Why:** Detected from session correction on {today}
**How to apply:** Apply whenever the situation described above arises.
"""
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        # Guard against path traversal (slug is derived from user text)
        if path.resolve().parent != MEMORY_DIR.resolve():
            log(f"Path traversal blocked: {path}")
            return False
        path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        log(f"Failed to write {path}: {e}")
        return False


def append_memory_index(slug: str, description: str) -> None:
    """Append an index entry to MEMORY.md under the Feedback section."""
    if not MEMORY_INDEX.exists():
        return
    try:
        content = MEMORY_INDEX.read_text()
        entry = f"- **feedback_{slug}:** See `memory/feedback_{slug}.md`"
        # Don't add if already there
        if f"feedback_{slug}" in content:
            return
        # Find the Feedback section and append there
        feedback_marker = "## Feedback (not in CLAUDE.md)"
        if feedback_marker in content:
            insert_at = content.index(feedback_marker) + len(feedback_marker)
            # Find the next newline after the marker line
            next_nl = content.find("\n", insert_at)
            if next_nl != -1:
                content = content[:next_nl + 1] + entry + "\n" + content[next_nl + 1:]
            else:
                content += "\n" + entry + "\n"
        else:
            content += f"\n{entry}\n"
        MEMORY_INDEX.write_text(content)
    except Exception as e:
        log(f"Failed to update MEMORY.md: {e}")


def detect_corrections(entries: list[dict]) -> list[dict]:
    """Scan transcript entries and return list of correction events."""
    corrections = []
    for i, entry in enumerate(entries):
        if entry["type"] != "user":
            continue
        text = entry["text"]
        if not is_correction(text):
            continue
        # Find the preceding assistant message
        assistant_text = ""
        for j in range(i - 1, -1, -1):
            if entries[j]["type"] == "assistant":
                assistant_text = entries[j]["text"]
                break
        corrections.append({"user": text, "assistant": assistant_text})
    return corrections


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    transcript_path = data.get("transcript_path", "")
    session_id = data.get("session_id", "unknown")

    if not transcript_path or not os.path.exists(transcript_path):
        return 0

    entries = load_transcript(transcript_path)
    user_count = sum(1 for e in entries if e["type"] == "user")

    if user_count < MIN_USER_MESSAGES:
        return 0

    corrections = detect_corrections(entries)
    if not corrections:
        return 0

    log(f"session={session_id} found {len(corrections)} correction(s)")

    written = 0
    for correction in corrections:
        user_text = correction["user"]
        assistant_text = correction["assistant"]

        slug = make_slug(user_text)
        if not slug or len(slug) < 4:
            continue

        if slug_exists(slug):
            log(f"  skip (exists): feedback_{slug}")
            continue

        description = re.split(r"[.!?\n]", user_text)[0].strip()[:100]
        if write_memory(slug, user_text, assistant_text):
            append_memory_index(slug, description)
            log(f"  wrote: feedback_{slug}.md")
            written += 1

    if written:
        log(f"session={session_id} wrote {written} new feedback file(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
