"""Extract tool sequence + outcomes from a Claude Code session JSONL file.

Phase 2 of the Hermes cherry-pick: this is the read-only side of the proposer.
It speaks Claude Code's session JSONL schema and produces a normalized summary
the trigger heuristic and Gemini synthesizer both consume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolCall:
    """A single tool invocation pulled from an assistant turn."""

    name: str
    input_summary: str  # Truncated stringified input for prompt synthesis
    error: bool = False
    error_text: str = ""


@dataclass
class SessionSummary:
    """Everything the proposer needs to know about a session."""

    session_id: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    user_messages: list[str] = field(default_factory=list)
    assistant_text_blocks: list[str] = field(default_factory=list)
    last_user_message: str = ""
    last_assistant_blocks: list[str] = field(default_factory=list)
    schema_version: str = "unknown"

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)

    @property
    def distinct_tool_types(self) -> set[str]:
        return {t.name for t in self.tool_calls}

    @property
    def top_tools(self, n: int = 5) -> list[str]:
        # Used for dedupe hash. Sorted alphabetically so order doesn't matter.
        from collections import Counter

        counter = Counter(t.name for t in self.tool_calls)
        most_common = [name for name, _ in counter.most_common(n)]
        return sorted(most_common)


def _truncate(s: str, n: int = 280) -> str:
    if len(s) <= n:
        return s
    return s[: n - 3] + "..."


def _extract_text_from_content(content: Any) -> str:
    """Pull the human-readable text out of an assistant or user content block.

    Claude Code stores `message.content` as either a plain string or a list of
    `{type, text}` / `{type, tool_use, ...}` items.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type", "")
        if item_type == "text":
            parts.append(item.get("text", ""))
        elif item_type == "tool_result":
            result = item.get("content", "")
            if isinstance(result, list):
                for sub in result:
                    if isinstance(sub, dict) and sub.get("type") == "text":
                        parts.append(sub.get("text", ""))
            elif isinstance(result, str):
                parts.append(result)
    return "\n".join(p for p in parts if p)


def parse_session_jsonl(jsonl_path: Path) -> SessionSummary:
    """Read a session JSONL and return a SessionSummary.

    Best-effort: malformed lines are skipped, never raised.
    """
    summary = SessionSummary(session_id=jsonl_path.stem)

    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue

            rec_type = rec.get("type", "")
            if rec_type == "system" and rec.get("subtype") == "bridge_status":
                summary.schema_version = rec.get("version", summary.schema_version)
                continue

            if rec_type == "user":
                msg = rec.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else ""
                text = _extract_text_from_content(content)
                if text.strip():
                    summary.user_messages.append(text.strip())

            elif rec_type == "assistant":
                msg = rec.get("message", {})
                content = msg.get("content", []) if isinstance(msg, dict) else []
                if not isinstance(content, list):
                    continue
                # Capture text blocks
                text = _extract_text_from_content(content)
                if text.strip():
                    summary.assistant_text_blocks.append(text.strip())
                # Capture tool calls
                for item in content:
                    if not isinstance(item, dict) or item.get("type") != "tool_use":
                        continue
                    name = item.get("name", "unknown")
                    raw_input = item.get("input", {})
                    try:
                        input_summary = _truncate(json.dumps(raw_input, ensure_ascii=False))
                    except (TypeError, ValueError):
                        input_summary = _truncate(str(raw_input))
                    summary.tool_calls.append(
                        ToolCall(name=name, input_summary=input_summary)
                    )

    if summary.user_messages:
        summary.last_user_message = summary.user_messages[-1]
    if summary.assistant_text_blocks:
        summary.last_assistant_blocks = summary.assistant_text_blocks[-3:]

    return summary


def format_tool_sequence_for_prompt(summary: SessionSummary, max_calls: int = 40) -> str:
    """Render the tool sequence as a numbered list for the synthesizer prompt."""
    calls = summary.tool_calls[:max_calls]
    lines = []
    for i, call in enumerate(calls, start=1):
        lines.append(f"{i}. {call.name}: {call.input_summary}")
    if len(summary.tool_calls) > max_calls:
        lines.append(f"... ({len(summary.tool_calls) - max_calls} more calls truncated)")
    return "\n".join(lines)
