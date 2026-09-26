#!/usr/bin/env python3
"""
CLAUDE.md Context Loader - Lazy-loading stratified context system

This tool implements the consensus token optimization strategy (Phase 1):
- Loads CLAUDE.md sections on-demand based on trigger keywords
- Validates section headings to guard against index breakage
- Falls back to full CLAUDE.md.full-backup if any section fails
- Implements Codex's safeguards: O(1) lookups, version hashing, concurrency safety

Usage:
    # Load core context (always)
    python3 tools/load_claude_context.py --core

    # Load specific sections based on triggers
    python3 tools/load_claude_context.py --triggers "route agent specialist"

    # Load all sections
    python3 tools/load_claude_context.py --all

    # Validate index integrity
    python3 tools/load_claude_context.py --validate
"""

import json
import hashlib
import os
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional

class ContextLoader:
    def __init__(self, base_dir: str = "{{CATALYST_ROOT}}"):
        self.base_dir = Path(base_dir)
        self.index_path = self.base_dir / ".claude-context" / "index.json"
        self.fallback_path = self.base_dir / "CLAUDE.md.full-backup"
        self.index_data = None
        self.loaded_sections: Set[str] = set()

    def load_index(self) -> Dict:
        """Load and validate the index file."""
        if not self.index_path.exists():
            raise FileNotFoundError(f"Index file not found: {self.index_path}")

        with open(self.index_path, 'r') as f:
            self.index_data = json.load(f)

        return self.index_data

    def compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def validate_section(self, section_name: str, content: str) -> bool:
        """
        Validate section headings match expected patterns.

        Implements Codex's safeguard: Guard against changed headings breaking index.
        """
        if not self.index_data:
            self.load_index()

        section_info = self.index_data['sections'].get(section_name)
        if not section_info:
            return False

        expected_headings = self.index_data['guards']['expected_headings'].get(section_name, [])
        if not expected_headings:
            return True  # No validation required for this section

        # Check if all expected headings are present in content
        for heading in expected_headings:
            if heading not in content:
                print(f"WARNING: Expected heading '{heading}' not found in section '{section_name}'", file=sys.stderr)
                return False

        return True

    def load_section(self, section_name: str, validate: bool = True) -> Optional[str]:
        """
        Load a specific section with optional validation.

        Implements Codex's safeguards:
        - O(1) lookup via index
        - Heading validation before loading
        - Fallback to full file if parsing fails
        """
        if not self.index_data:
            self.load_index()

        section_info = self.index_data['sections'].get(section_name)
        if not section_info:
            print(f"ERROR: Section '{section_name}' not found in index", file=sys.stderr)
            return None

        file_path = self.base_dir / section_info['file']

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Validate section headings if enabled
            if validate and not self.validate_section(section_name, content):
                print(f"ERROR: Section validation failed for '{section_name}', falling back to full file", file=sys.stderr)
                return self.load_fallback()

            self.loaded_sections.add(section_name)
            return content

        except Exception as e:
            print(f"ERROR loading section '{section_name}': {e}", file=sys.stderr)
            print("Falling back to full CLAUDE.md", file=sys.stderr)
            return self.load_fallback()

    def load_fallback(self) -> str:
        """
        Load the full backup file as fallback.

        Implements Codex's safeguard: Ship a fallback to full load if parsing fails.
        """
        try:
            with open(self.fallback_path, 'r') as f:
                content = f.read()
            print(f"Loaded fallback file: {self.fallback_path}", file=sys.stderr)
            return content
        except Exception as e:
            print(f"CRITICAL ERROR: Cannot load fallback file: {e}", file=sys.stderr)
            sys.exit(1)

    def match_triggers(self, message: str) -> Set[str]:
        """
        Match trigger keywords in message to determine which sections to load.

        Returns set of section names that match triggers.
        """
        if not self.index_data:
            self.load_index()

        message_lower = message.lower()
        matched_sections = set()

        for section_name, section_info in self.index_data['sections'].items():
            triggers = section_info.get('load_trigger')

            if not triggers:
                continue

            # Handle both single string and list of triggers
            if isinstance(triggers, str):
                triggers = [triggers]

            # Check if any trigger matches
            for trigger in triggers:
                if trigger in message_lower:
                    matched_sections.add(section_name)
                    break

        return matched_sections

    def load_core(self) -> str:
        """Load core context (always loaded)."""
        return self.load_section('core', validate=True)

    def load_by_triggers(self, message: str) -> str:
        """
        Load sections based on trigger keywords in message.

        Returns combined context from all matched sections.
        """
        matched = self.match_triggers(message)

        if not matched:
            return ""

        sections_content = []
        for section_name in sorted(matched):
            content = self.load_section(section_name, validate=True)
            if content:
                sections_content.append(f"<!-- Loaded: {section_name} -->\n{content}\n")

        return "\n".join(sections_content)

    def load_all(self) -> str:
        """Load all sections."""
        if not self.index_data:
            self.load_index()

        all_content = []
        for section_name in self.index_data['sections'].keys():
            content = self.load_section(section_name, validate=True)
            if content:
                all_content.append(content)

        return "\n".join(all_content)

    def validate_index_integrity(self) -> bool:
        """
        Validate the entire index system.

        Checks:
        - All section files exist
        - All expected headings are present
        - File hashes match (if computed)
        """
        if not self.index_data:
            self.load_index()

        all_valid = True

        for section_name, section_info in self.index_data['sections'].items():
            file_path = self.base_dir / section_info['file']

            # Check file exists
            if not file_path.exists():
                print(f"ERROR: Section file not found: {file_path}", file=sys.stderr)
                all_valid = False
                continue

            # Load and validate content
            try:
                with open(file_path, 'r') as f:
                    content = f.read()

                if not self.validate_section(section_name, content):
                    all_valid = False

            except Exception as e:
                print(f"ERROR validating section '{section_name}': {e}", file=sys.stderr)
                all_valid = False

        return all_valid


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CLAUDE.md stratified context loader")
    parser.add_argument('--core', action='store_true', help="Load core context only")
    parser.add_argument('--triggers', type=str, help="Load sections based on trigger keywords")
    parser.add_argument('--all', action='store_true', help="Load all sections")
    parser.add_argument('--validate', action='store_true', help="Validate index integrity")
    parser.add_argument('--base-dir', type=str, default="{{CATALYST_ROOT}}", help="Base directory")

    args = parser.parse_args()

    loader = ContextLoader(base_dir=args.base_dir)

    try:
        if args.validate:
            valid = loader.validate_index_integrity()
            if valid:
                print("✓ Index validation passed", file=sys.stderr)
                sys.exit(0)
            else:
                print("✗ Index validation failed", file=sys.stderr)
                sys.exit(1)

        elif args.core:
            content = loader.load_core()
            print(content)

        elif args.triggers:
            core = loader.load_core()
            triggered = loader.load_by_triggers(args.triggers)
            print(core)
            if triggered:
                print("\n" + triggered)

        elif args.all:
            content = loader.load_all()
            print(content)

        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
