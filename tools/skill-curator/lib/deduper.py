"""Hash-based dedupe.

A workflow's "shape" is the set of its top 5 most-used tools, sorted alphabetically.
We hash that set and compare against:
  1. Hashes computed on every existing skill in `.claude/skills/` (best-effort,
     based on tool names mentioned in the SKILL.md body or `allowed-tools`)
  2. Hashes from already-proposed drafts in `.claude/skills/_proposed/`

This is the "cheap dedupe" called out in the ADR. Full semantic dedupe is
deferred to Phase 4 (the curator).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .extractor import SessionSummary

# Regex that matches lines like "  - Bash" under an `allowed-tools:` block.
ALLOWED_TOOL_LINE = re.compile(r"^\s*-\s+([A-Za-z][A-Za-z0-9_]*)\s*$")

# Tools we expect to see (tightens the cross-reference; ignores arbitrary words).
KNOWN_TOOLS = {
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Task",
    "WebFetch",
    "WebSearch",
    "TodoWrite",
    "ToolSearch",
    "NotebookEdit",
    "Skill",
}


def hash_top_tools(top_tools: list[str]) -> str:
    """Stable hash of a sorted tool name list."""
    normalized = "|".join(sorted(t for t in top_tools if t))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def session_hash(summary: SessionSummary, n: int = 5) -> str:
    """Compute the dedupe hash for a session."""
    return hash_top_tools(summary.top_tools)


def _hash_skill_md(skill_path: Path) -> str | None:
    """Best-effort hash of an existing SKILL.md based on its tool footprint.

    Looks at:
      - the `allowed-tools:` YAML block, if present
      - fall back to which KNOWN_TOOLS appear in the body text
    Returns None if we can't extract any tools (the skill is probably navigation
    or content-only, not workflow-shaped — no collision risk).
    """
    try:
        text = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    tools: set[str] = set()

    # Pass 1: allowed-tools YAML block
    in_allowed_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("allowed-tools:"):
            in_allowed_block = True
            # inline form: allowed-tools: [Bash, Read]
            inline = stripped.split(":", 1)[1].strip()
            if inline.startswith("[") and inline.endswith("]"):
                for t in inline[1:-1].split(","):
                    t = t.strip().strip("'\"")
                    if t:
                        tools.add(t)
                in_allowed_block = False
            continue
        if in_allowed_block:
            m = ALLOWED_TOOL_LINE.match(line)
            if m:
                tools.add(m.group(1))
            elif stripped and not stripped.startswith("-") and not stripped.startswith("#"):
                in_allowed_block = False

    # Pass 2: fallback to body scan
    if not tools:
        for known in KNOWN_TOOLS:
            if known in text:
                tools.add(known)

    if not tools:
        return None

    # Cap at top-N alphabetically for parity with session_hash semantics.
    top = sorted(tools)[:5]
    return hash_top_tools(top)


def collect_existing_hashes(skills_dir: Path) -> set[str]:
    """Walk `.claude/skills/` and gather best-effort hashes of every skill.

    Skips the `_proposed/` and `_promoted/` subtrees (those are handled separately
    or aren't real skills yet). Skips the `.archive/` subtree.
    """
    hashes: set[str] = set()
    if not skills_dir.exists():
        return hashes

    excluded_dirs = {"_proposed", "_promoted", ".archive", "node_modules", "__pycache__"}

    for entry in skills_dir.iterdir():
        if not entry.is_dir() or entry.name in excluded_dirs:
            continue
        # SKILL.md or skill.md (Huxley is mixed-case — handle both).
        for candidate in ("SKILL.md", "skill.md"):
            skill_path = entry / candidate
            if skill_path.exists():
                h = _hash_skill_md(skill_path)
                if h:
                    hashes.add(h)
                break  # only one canonical skill file per dir

    return hashes


def collect_proposed_hashes(proposed_dir: Path) -> set[str]:
    """Hashes of drafts already sitting in `.claude/skills/_proposed/`."""
    hashes: set[str] = set()
    if not proposed_dir.exists():
        return hashes

    for entry in proposed_dir.iterdir():
        if not entry.is_dir():
            continue
        for candidate in ("SKILL.md", "skill.md"):
            skill_path = entry / candidate
            if skill_path.exists():
                h = _hash_skill_md(skill_path)
                if h:
                    hashes.add(h)
                break
    return hashes


def has_duplicate(summary: SessionSummary, skills_dir: Path, proposed_dir: Path) -> tuple[bool, str]:
    """Return (is_dup, hash). Caller logs the hash on dedupe-skip."""
    h = session_hash(summary)
    existing = collect_existing_hashes(skills_dir)
    proposed = collect_proposed_hashes(proposed_dir)
    if h in existing:
        return True, h
    if h in proposed:
        return True, h
    return False, h
