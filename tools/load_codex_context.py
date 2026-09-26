#!/usr/bin/env python3
"""
CODEX Context Loader - Lazy-loading stratified context system

Mirrors the CLAUDE context loader but targets CODEX.md + .codex-context files.
Keeps Codex sessions in sync with the same stratified context strategy used
for Claude Code.

Usage:
    python3 tools/load_codex_context.py --core
    python3 tools/load_codex_context.py --triggers "agent routing"
    python3 tools/load_codex_context.py --all
    python3 tools/load_codex_context.py --validate
"""

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set


class CodexContextLoader:
    def __init__(self, base_dir: Optional[str] = None):
        root = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
        self.base_dir = root
        self.index_path = self.base_dir / ".codex-context" / "index.json"
        self.fallback_path = self.base_dir / "CODEX.md.full-backup"
        self.index_data: Optional[Dict] = None
        self.loaded_sections: Set[str] = set()

    def load_index(self) -> Dict:
        if not self.index_path.exists():
            raise FileNotFoundError(f"Index file not found: {self.index_path}")

        with open(self.index_path, "r") as f:
            self.index_data = json.load(f)
        return self.index_data

    def compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def validate_section(self, section_name: str, content: str) -> bool:
        if not self.index_data:
            self.load_index()

        section_info = self.index_data["sections"].get(section_name)
        if not section_info:
            return False

        expected_headings = self.index_data["guards"]["expected_headings"].get(section_name, [])
        if not expected_headings:
            return True

        for heading in expected_headings:
            if heading not in content:
                print(
                    f"WARNING: Expected heading '{heading}' not found in section '{section_name}'",
                    file=sys.stderr,
                )
                return False

        return True

    def load_section(self, section_name: str, validate: bool = True) -> Optional[str]:
        if not self.index_data:
            self.load_index()

        section_info = self.index_data["sections"].get(section_name)
        if not section_info:
            print(f"ERROR: Section '{section_name}' not found in index", file=sys.stderr)
            return None

        file_path = self.base_dir / section_info["file"]

        try:
            with open(file_path, "r") as f:
                content = f.read()

            if validate and not self.validate_section(section_name, content):
                print(
                    f"ERROR: Section validation failed for '{section_name}', falling back to full file",
                    file=sys.stderr,
                )
                return self.load_fallback()

            self.loaded_sections.add(section_name)
            return content
        except Exception as exc:  # pragma: no cover - defensive path
            print(f"ERROR loading section '{section_name}': {exc}", file=sys.stderr)
            print("Falling back to full CODEX.md", file=sys.stderr)
            return self.load_fallback()

    def load_fallback(self) -> str:
        try:
            with open(self.fallback_path, "r") as f:
                content = f.read()
            print(f"Loaded fallback file: {self.fallback_path}", file=sys.stderr)
            return content
        except Exception as exc:
            print(f"CRITICAL ERROR: Cannot load fallback file: {exc}", file=sys.stderr)
            sys.exit(1)

    def match_triggers(self, message: str) -> Set[str]:
        if not self.index_data:
            self.load_index()

        message_lower = message.lower()
        matched_sections: Set[str] = set()

        for section_name, section_info in self.index_data["sections"].items():
            triggers = section_info.get("load_trigger")
            if not triggers:
                continue
            if isinstance(triggers, str):
                triggers = [triggers]
            for trigger in triggers:
                if trigger in message_lower:
                    matched_sections.add(section_name)
                    break

        return matched_sections

    def load_core(self) -> str:
        return self.load_section("core", validate=True) or ""

    def load_by_triggers(self, message: str) -> str:
        matched = self.match_triggers(message)
        if not matched:
            return ""

        sections: List[str] = []
        for section_name in sorted(matched):
            content = self.load_section(section_name, validate=True)
            if content:
                sections.append(f"<!-- Loaded: {section_name} -->\n{content}\n")
        return "\n".join(sections)

    def load_all(self) -> str:
        if not self.index_data:
            self.load_index()

        sections: List[str] = []
        for section_name in self.index_data["sections"]:
            content = self.load_section(section_name, validate=True)
            if content:
                sections.append(content)
        return "\n".join(sections)

    def validate_index_integrity(self) -> bool:
        if not self.index_data:
            self.load_index()

        guards = self.index_data.get("guards", {})
        if not guards.get("heading_validation"):
            return True

        expected_headings = guards.get("expected_headings", {})
        for section_name, headings in expected_headings.items():
            content = self.load_section(section_name, validate=False)
            if not content:
                print(f"Validation failed: Cannot load section '{section_name}'", file=sys.stderr)
                return False
            for heading in headings:
                if heading not in content:
                    print(
                        f"Validation failed: Heading '{heading}' missing in section '{section_name}'",
                        file=sys.stderr,
                    )
                    return False
        return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Load stratified CODEX context sections")
    parser.add_argument("--core", action="store_true", help="Load core CODEX context")
    parser.add_argument("--triggers", help="Load sections based on keyword triggers")
    parser.add_argument("--all", action="store_true", help="Load all sections")
    parser.add_argument("--validate", action="store_true", help="Validate index integrity")
    parser.add_argument("--base-dir", help="Override base directory (defaults to repo root)")

    args = parser.parse_args()
    loader = CodexContextLoader(base_dir=args.base_dir)

    if args.validate:
        ok = loader.validate_index_integrity()
        print("✅ Index validation passed" if ok else "❌ Index validation failed")
        sys.exit(0 if ok else 1)

    output_parts: List[str] = []

    if args.core:
        output_parts.append(loader.load_core())

    if args.triggers:
        output_parts.append(loader.load_by_triggers(args.triggers))

    if args.all:
        output_parts.append(loader.load_all())

    if not output_parts:
        # Default to core if no flags provided
        output_parts.append(loader.load_core())

    print("\n\n".join(part for part in output_parts if part))


if __name__ == "__main__":
    main()
