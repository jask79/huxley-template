#!/usr/bin/env python3
"""
Documentation Bundle Generator

Creates bundled documentation files to reduce token consumption
when loading related agent specialty docs.

Phase 3 of token optimization.

Bundles are created as markdown files with clear section markers,
making them easy to search and reference.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Paths
BUILDEOROS_ROOT = Path(__file__).parent.parent
DOCS_DIR = BUILDEOROS_ROOT / "global" / "docs"
BUNDLES_DIR = BUILDEOROS_ROOT / "global" / "docs" / "bundles"

# Bundle definitions
BUNDLES = {
    "ios-development": {
        "description": "iOS Development Context Bundle - Navigation, Touch, Animation",
        "files": [
            "iOS_Navigation_Architecture.md",
            "iOS_Touch_Interaction_Patterns.md",
            "iOS_Animation_Patterns.md"
        ]
    },
    "agentic-loop": {
        "description": "Agentic Loop Architecture Bundle - Foundation, Architecture, Implementation",
        "files": [
            "Agentic_Loop_Phase_0_Foundation.md",
            "Agentic_Loop_Architecture.md",
            "Agentic_Loop_Implementation_Plan.md"
        ]
    },
    "mobile-workflow": {
        "description": "Mobile Development Workflow Bundle - SwiftUI and App Workflow",
        "files": [
            "Mobile_App_Workflow.md",
            "SwiftUI_For_UI_Designers.md"
        ]
    },
    "browser-automation": {
        "description": "Browser Automation Bundle - Playwright Architecture and Guide",
        "files": [
            "PLAYWRIGHT_ARCHITECTURE_EXPLAINED.md",
            "Browser_Automation_Guide.md"
        ]
    }
}


def generate_bundle_header(bundle_name: str, bundle_info: Dict, file_sizes: Dict[str, int]) -> str:
    """Generate the header for a bundle file."""
    total_size = sum(file_sizes.values())

    header = f"""# {bundle_info['description']}

**Bundle:** `{bundle_name}.bundle.md`
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Purpose
This bundle combines multiple related documentation files to reduce token consumption
when loading agent specialty context. Instead of loading files separately, this
single bundle can be loaded once and referenced throughout the session.

## Contents
"""

    for i, filename in enumerate(bundle_info['files'], 1):
        size_kb = file_sizes.get(filename, 0) / 1024
        header += f"{i}. `{filename}` ({size_kb:.1f} KB)\n"

    header += f"\n**Total Size:** {total_size / 1024:.1f} KB\n"
    header += "\n## Token Optimization\n"
    header += "- **Before:** Multiple file loads, cumulative token cost\n"
    header += "- **After:** Single bundle load, reduced overhead\n"
    header += f"- **Savings:** Eliminates file I/O overhead for {len(bundle_info['files'])} separate loads\n"
    header += "\n---\n\n"

    return header


def generate_bundle(bundle_name: str, bundle_info: Dict) -> tuple[str, Dict[str, int]]:
    """Generate a bundle file from multiple source files."""
    content_parts = []
    file_sizes = {}

    # Generate header
    # First, collect file sizes
    for filename in bundle_info['files']:
        file_path = DOCS_DIR / filename
        if file_path.exists():
            file_sizes[filename] = os.path.getsize(file_path)

    header = generate_bundle_header(bundle_name, bundle_info, file_sizes)
    content_parts.append(header)

    # Add each file's content with section markers
    for i, filename in enumerate(bundle_info['files'], 1):
        file_path = DOCS_DIR / filename

        if not file_path.exists():
            print(f"   ⚠️  Warning: {filename} not found, skipping")
            continue

        # Read file content
        with open(file_path, 'r') as f:
            file_content = f.read()

        # Add section marker and content
        section = f"\n{'=' * 80}\n"
        section += f"## SECTION {i}: {filename}\n"
        section += f"{'=' * 80}\n\n"
        section += file_content
        section += f"\n\n{'=' * 80}\n"
        section += f"## END SECTION {i}\n"
        section += f"{'=' * 80}\n\n"

        content_parts.append(section)

    return "\n".join(content_parts), file_sizes


def generate_bundle_index() -> str:
    """Generate an index of all bundles."""
    index = f"""# Documentation Bundle Index

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This directory contains bundled documentation files for token optimization.
Each bundle combines related documentation files to reduce loading overhead.

## Available Bundles

"""

    for bundle_name, bundle_info in BUNDLES.items():
        bundle_path = BUNDLES_DIR / f"{bundle_name}.bundle.md"
        if bundle_path.exists():
            bundle_size = os.path.getsize(bundle_path)
            index += f"### `{bundle_name}.bundle.md` ({bundle_size / 1024:.1f} KB)\n"
            index += f"{bundle_info['description']}\n\n"
            index += "**Contains:**\n"
            for filename in bundle_info['files']:
                index += f"- {filename}\n"
            index += "\n"

    index += """## Usage

Instead of loading multiple files:
```python
# OLD: Multiple loads
with open('iOS_Navigation_Architecture.md') as f1:
    nav = f1.read()
with open('iOS_Touch_Interaction_Patterns.md') as f2:
    touch = f2.read()
with open('iOS_Animation_Patterns.md') as f3:
    anim = f3.read()
```

Load a single bundle:
```python
# NEW: Single bundle load
with open('bundles/ios-development.bundle.md') as f:
    ios_context = f.read()
```

## Token Savings

- **Reduced file I/O:** Single load vs multiple loads
- **Better caching:** One file to cache instead of many
- **Lower overhead:** Eliminates per-file metadata and parsing

## Maintenance

To regenerate bundles after documentation updates:
```bash
python3 tools/doc_bundle_generator.py
```
"""

    return index


def main():
    """Generate all documentation bundles."""
    print("Documentation Bundle Generator")
    print("=" * 80)

    # Create bundles directory
    BUNDLES_DIR.mkdir(exist_ok=True)
    print(f"\n1. Bundles directory: {BUNDLES_DIR}")

    # Generate each bundle
    total_original_size = 0
    total_bundle_size = 0

    print(f"\n2. Generating {len(BUNDLES)} bundles...")

    for bundle_name, bundle_info in BUNDLES.items():
        print(f"\n   Bundle: {bundle_name}")
        print(f"   Description: {bundle_info['description']}")

        # Generate bundle
        bundle_content, file_sizes = generate_bundle(bundle_name, bundle_info)

        # Save bundle
        bundle_path = BUNDLES_DIR / f"{bundle_name}.bundle.md"
        with open(bundle_path, 'w') as f:
            f.write(bundle_content)

        # Calculate sizes
        original_size = sum(file_sizes.values())
        bundle_size = os.path.getsize(bundle_path)

        total_original_size += original_size
        total_bundle_size += bundle_size

        print(f"   Files: {len(file_sizes)}")
        print(f"   Original total: {original_size / 1024:.1f} KB")
        print(f"   Bundle size: {bundle_size / 1024:.1f} KB")
        print(f"   ✓ Saved to: {bundle_path.name}")

    # Generate index
    print(f"\n3. Generating bundle index...")
    index_content = generate_bundle_index()
    index_path = BUNDLES_DIR / "README.md"
    with open(index_path, 'w') as f:
        f.write(index_content)
    print(f"   ✓ Saved to: {index_path.name}")

    # Summary
    print(f"\n4. Summary:")
    print(f"   Total bundles: {len(BUNDLES)}")
    print(f"   Original size: {total_original_size / 1024:.1f} KB")
    print(f"   Bundle size: {total_bundle_size / 1024:.1f} KB")

    overhead = total_bundle_size - total_original_size
    if overhead > 0:
        print(f"   Bundle overhead: {overhead / 1024:.1f} KB ({overhead / total_original_size * 100:.1f}%)")
        print(f"      (Bundle headers and section markers)")
    else:
        print(f"   Bundle savings: {abs(overhead) / 1024:.1f} KB")

    print(f"\n✅ All bundles generated successfully!")
    print(f"\nToken Optimization Benefits:")
    print(f"   - Single file load vs {sum(len(b['files']) for b in BUNDLES.values())} separate loads")
    print(f"   - Reduced file I/O overhead")
    print(f"   - Better caching (one file to cache per bundle)")


if __name__ == "__main__":
    main()
