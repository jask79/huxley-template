#!/usr/bin/env python3
"""
Automatic Specification Synchronization for Huxley
Checkpoint-based spec updates via pre-commit hook

Analyzes codebase state and automatically updates spec files with high-confidence changes:
- Dependencies from package files
- File structure from directory analysis
- Tech stack from file extensions and imports
- Feature completion from code analysis

Usage:
    ./tools/sync_specs.py --auto                    # Run automatic sync (pre-commit)
    ./tools/sync_specs.py --capsule <path>          # Sync specific capsule
    ./tools/sync_specs.py --dry-run                 # Show what would change
"""

import yaml
import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re
import subprocess


@dataclass
class CodebaseState:
    """Represents current state of the codebase"""
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    file_structure: Dict[str, Any] = field(default_factory=dict)
    tech_stack: Set[str] = field(default_factory=set)
    entry_points: List[str] = field(default_factory=list)
    detected_features: Set[str] = field(default_factory=set)


@dataclass
class SpecUpdate:
    """Represents a proposed spec update"""
    file: str
    field: str
    old_value: Any
    new_value: Any
    confidence: float
    reason: str


class SpecSyncer:
    """Automatic spec synchronization engine"""

    # Confidence threshold for automatic updates
    CONFIDENCE_THRESHOLD = 0.85

    # File patterns to analyze
    DEPENDENCY_FILES = {
        'requirements.txt': 'python',
        'package.json': 'javascript',
        'Podfile': 'ios',
        'Gemfile': 'ruby',
        'go.mod': 'go',
        'Cargo.toml': 'rust'
    }

    # Tech stack detection patterns
    TECH_PATTERNS = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.swift': 'swift',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.java': 'java',
        '.kt': 'kotlin'
    }

    def __init__(self, capsule_path: Path, dry_run: bool = False, auto_mode: bool = False):
        self.capsule_path = capsule_path
        self.dry_run = dry_run
        self.auto_mode = auto_mode
        self.updates: List[SpecUpdate] = []
        self.log_file = capsule_path / "context" / "spec_updates.log"

    def analyze_codebase(self) -> CodebaseState:
        """Analyze current codebase state"""
        state = CodebaseState()

        # Analyze dependencies
        state.dependencies = self._analyze_dependencies()

        # Analyze file structure
        state.file_structure = self._analyze_file_structure()

        # Detect tech stack
        state.tech_stack = self._detect_tech_stack()

        # Find entry points
        state.entry_points = self._find_entry_points()

        return state

    def _analyze_dependencies(self) -> Dict[str, List[str]]:
        """Extract dependencies from package files"""
        dependencies = {}

        for dep_file, lang in self.DEPENDENCY_FILES.items():
            file_path = self.capsule_path / dep_file
            if not file_path.exists():
                continue

            try:
                if dep_file == 'requirements.txt':
                    deps = self._parse_requirements_txt(file_path)
                elif dep_file == 'package.json':
                    deps = self._parse_package_json(file_path)
                elif dep_file == 'Podfile':
                    deps = self._parse_podfile(file_path)
                else:
                    deps = []

                if deps:
                    dependencies[lang] = deps
            except Exception as e:
                print(f"Warning: Failed to parse {dep_file}: {e}", file=sys.stderr)

        return dependencies

    def _parse_requirements_txt(self, file_path: Path) -> List[str]:
        """Parse Python requirements.txt"""
        deps = []
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name (before ==, >=, etc.)
                    match = re.match(r'^([a-zA-Z0-9\-_]+)', line)
                    if match:
                        deps.append(match.group(1))
        return deps

    def _parse_package_json(self, file_path: Path) -> List[str]:
        """Parse Node.js package.json"""
        with open(file_path, 'r') as f:
            data = json.load(f)
            deps = []
            if 'dependencies' in data:
                deps.extend(data['dependencies'].keys())
            if 'devDependencies' in data:
                deps.extend(data['devDependencies'].keys())
            return deps

    def _parse_podfile(self, file_path: Path) -> List[str]:
        """Parse iOS Podfile"""
        deps = []
        with open(file_path, 'r') as f:
            for line in f:
                # Match: pod 'PodName'
                match = re.match(r"\s*pod\s+['\"]([^'\"]+)['\"]", line)
                if match:
                    deps.append(match.group(1))
        return deps

    def _analyze_file_structure(self) -> Dict[str, Any]:
        """Analyze directory structure"""
        structure = {
            'directories': [],
            'total_files': 0,
            'main_components': []
        }

        # Count directories and files
        for item in self.capsule_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                structure['directories'].append(item.name)
                # Count files in this directory
                file_count = len(list(item.rglob('*')))
                if file_count > 5:  # Significant component
                    structure['main_components'].append(item.name)

        # Count total files
        structure['total_files'] = len(list(self.capsule_path.rglob('*')))

        return structure

    def _detect_tech_stack(self) -> Set[str]:
        """Detect technologies from file extensions"""
        tech_stack = set()

        for pattern, tech in self.TECH_PATTERNS.items():
            if list(self.capsule_path.rglob(f'*{pattern}')):
                tech_stack.add(tech)

        # Check for specific frameworks
        if (self.capsule_path / 'package.json').exists():
            try:
                with open(self.capsule_path / 'package.json') as f:
                    pkg = json.load(f)
                    deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}

                    if 'react' in deps:
                        tech_stack.add('react')
                    if 'next' in deps:
                        tech_stack.add('nextjs')
                    if 'vue' in deps:
                        tech_stack.add('vue')
                    if 'express' in deps:
                        tech_stack.add('express')
            except:
                pass

        if (self.capsule_path / 'requirements.txt').exists():
            try:
                with open(self.capsule_path / 'requirements.txt') as f:
                    content = f.read().lower()
                    if 'fastapi' in content:
                        tech_stack.add('fastapi')
                    if 'django' in content:
                        tech_stack.add('django')
                    if 'flask' in content:
                        tech_stack.add('flask')
            except:
                pass

        return tech_stack

    def _find_entry_points(self) -> List[str]:
        """Find main entry point files"""
        entry_points = []

        # Common entry point patterns
        patterns = [
            'main.py', 'app.py', 'index.js', 'index.ts',
            'main.swift', 'main.go', 'main.rs', 'server.py'
        ]

        for pattern in patterns:
            matches = list(self.capsule_path.rglob(pattern))
            if matches:
                entry_points.extend([str(m.relative_to(self.capsule_path)) for m in matches])

        return entry_points

    def load_specs(self) -> Dict[str, Any]:
        """Load current specification files"""
        specs = {}

        spec_files = {
            'current': self.capsule_path / 'specs' / 'current.yaml',
            'standards': self.capsule_path / 'standards.yaml',
            'product': self.capsule_path / 'product.yaml'
        }

        for name, path in spec_files.items():
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        specs[name] = yaml.safe_load(f)
                except Exception as e:
                    print(f"Warning: Failed to load {path}: {e}", file=sys.stderr)
                    specs[name] = {}
            else:
                specs[name] = {}

        return specs

    def generate_updates(self, codebase: CodebaseState, specs: Dict[str, Any]) -> List[SpecUpdate]:
        """Generate high-confidence spec updates"""
        updates = []

        # Update dependencies in standards.yaml
        if codebase.dependencies:
            updates.extend(self._update_dependencies(codebase, specs))

        # Update tech stack in specs/current.yaml
        if codebase.tech_stack:
            updates.extend(self._update_tech_stack(codebase, specs))

        # Update file structure in specs/current.yaml
        if codebase.file_structure:
            updates.extend(self._update_file_structure(codebase, specs))

        # Filter by confidence threshold
        high_confidence_updates = [
            u for u in updates if u.confidence >= self.CONFIDENCE_THRESHOLD
        ]

        return high_confidence_updates

    def _update_dependencies(self, codebase: CodebaseState, specs: Dict[str, Any]) -> List[SpecUpdate]:
        """Update dependency specifications"""
        updates = []

        current_spec = specs.get('current', {})
        spec_deps = current_spec.get('dependencies', {})

        for lang, deps in codebase.dependencies.items():
            # Check if dependencies have changed
            spec_key = f'{lang}_packages'
            current_deps = set(spec_deps.get('external', {}).get(spec_key, []))
            new_deps = set(deps)

            if current_deps != new_deps:
                # Sort for consistent ordering
                updates.append(SpecUpdate(
                    file='specs/current.yaml',
                    field=f'dependencies.external.{spec_key}',
                    old_value=sorted(list(current_deps)),
                    new_value=sorted(list(new_deps)),
                    confidence=0.95,  # Very high confidence - mechanical extraction
                    reason=f'Updated {lang} dependencies from {self._get_dep_file(lang)}'
                ))

        return updates

    def _update_tech_stack(self, codebase: CodebaseState, specs: Dict[str, Any]) -> List[SpecUpdate]:
        """Update technology stack"""
        updates = []

        current_spec = specs.get('current', {})
        arch = current_spec.get('architecture', {})
        current_stack = set(arch.get('technology_stack', {}).get('languages', []))

        new_stack = codebase.tech_stack

        if current_stack != new_stack:
            # Sort for consistent ordering
            updates.append(SpecUpdate(
                file='specs/current.yaml',
                field='architecture.technology_stack.languages',
                old_value=sorted(list(current_stack)),
                new_value=sorted(list(new_stack)),
                confidence=0.90,  # High confidence - detected from files
                reason='Updated languages based on file extensions and frameworks'
            ))

        return updates

    def _update_file_structure(self, codebase: CodebaseState, specs: Dict[str, Any]) -> List[SpecUpdate]:
        """Update file structure components"""
        updates = []

        current_spec = specs.get('current', {})
        arch = current_spec.get('architecture', {})
        current_components = arch.get('components', [])

        # Extract component names from current spec
        if isinstance(current_components, list):
            current_comp_names = set(current_components)
        else:
            current_comp_names = set()

        # Get main components from analysis
        new_comp_names = set(codebase.file_structure.get('main_components', []))

        # Only update if there are new significant components
        added = new_comp_names - current_comp_names
        if added and len(added) <= 3:  # Avoid massive changes
            updated_components = sorted(list(current_comp_names | new_comp_names))
            updates.append(SpecUpdate(
                file='specs/current.yaml',
                field='architecture.components',
                old_value=sorted(list(current_comp_names)),
                new_value=updated_components,
                confidence=0.80,  # Good confidence - directory analysis
                reason=f'Added new components: {", ".join(sorted(added))}'
            ))

        return updates

    def _get_dep_file(self, lang: str) -> str:
        """Get dependency file name for language"""
        for file, l in self.DEPENDENCY_FILES.items():
            if l == lang:
                return file
        return f'{lang} packages'

    def apply_updates(self, updates: List[SpecUpdate]) -> bool:
        """Apply updates to spec files"""
        if not updates:
            return True

        # Group updates by file
        updates_by_file = {}
        for update in updates:
            if update.file not in updates_by_file:
                updates_by_file[update.file] = []
            updates_by_file[update.file].append(update)

        # Apply updates to each file
        for file_name, file_updates in updates_by_file.items():
            file_path = self.capsule_path / file_name

            if not file_path.exists():
                print(f"Warning: Spec file not found: {file_path}", file=sys.stderr)
                continue

            try:
                # Load YAML
                with open(file_path, 'r') as f:
                    spec_data = yaml.safe_load(f) or {}

                # Apply each update
                for update in file_updates:
                    self._apply_field_update(spec_data, update)

                # Write updated YAML
                if not self.dry_run:
                    with open(file_path, 'w') as f:
                        yaml.dump(spec_data, f, default_flow_style=False, sort_keys=False)
                    print(f"✓ Updated {file_name}")
                else:
                    print(f"[DRY RUN] Would update {file_name}")

            except Exception as e:
                print(f"Error updating {file_name}: {e}", file=sys.stderr)
                return False

        return True

    def _apply_field_update(self, data: Dict, update: SpecUpdate):
        """Apply a single field update to spec data"""
        # Parse field path (e.g., "architecture.technology_stack.languages")
        parts = update.field.split('.')

        # Navigate to parent
        current = data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set value
        current[parts[-1]] = update.new_value

    def log_updates(self, updates: List[SpecUpdate]):
        """Log updates to spec_updates.log"""
        if not updates:
            return

        # Ensure context directory exists
        context_dir = self.capsule_path / "context"
        context_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().isoformat()

        with open(self.log_file, 'a') as f:
            f.write(f"\n# Spec Update - {timestamp}\n")
            for update in updates:
                f.write(f"- [{update.file}] {update.field}\n")
                f.write(f"  Confidence: {update.confidence:.0%}\n")
                f.write(f"  Reason: {update.reason}\n")
                f.write(f"  Old: {update.old_value}\n")
                f.write(f"  New: {update.new_value}\n")

    def validate_specs(self) -> bool:
        """Validate updated specs using existing validator"""
        validator_path = Path(__file__).parent / "validate_specs.py"
        if not validator_path.exists():
            print("Warning: validate_specs.py not found, skipping validation", file=sys.stderr)
            return True

        try:
            result = subprocess.run(
                [sys.executable, str(validator_path), str(self.capsule_path)],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return True
            else:
                print(f"Validation failed:\n{result.stdout}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"Validation error: {e}", file=sys.stderr)
            return False

    def sync(self) -> bool:
        """Run complete sync process"""
        print(f"Analyzing codebase: {self.capsule_path.name}")

        # 1. Analyze codebase
        codebase_state = self.analyze_codebase()

        # 2. Load current specs
        specs = self.load_specs()

        # 3. Generate updates
        updates = self.generate_updates(codebase_state, specs)

        if not updates:
            print("✓ Specs are up to date")
            return True

        # 4. Show updates
        print(f"\nProposed updates ({len(updates)}):")
        for update in updates:
            print(f"  • [{update.file}] {update.field}")
            print(f"    {update.reason} (confidence: {update.confidence:.0%})")

        # 5. Apply updates
        if self.apply_updates(updates):
            # 6. Log updates
            self.log_updates(updates)

            # 7. Validate
            if not self.dry_run:
                if self.validate_specs():
                    print("\n✓ Specs updated and validated")
                    return True
                else:
                    if self.auto_mode:
                        # In auto mode (pre-commit), warn but don't fail
                        print("\n⚠️  Validation warnings present (not blocking commit)")
                        return True
                    else:
                        print("\n✗ Validation failed - review changes manually")
                        return False
            else:
                print("\n[DRY RUN] No changes written")
                return True
        else:
            print("\n✗ Failed to apply updates")
            return False


def find_capsule_root() -> Optional[Path]:
    """Find capsule root from current directory"""
    current = Path.cwd()

    # Check if we're in a capsule (has specs/ or spec/ directory)
    if (current / 'specs').exists() or (current / 'spec').exists():
        return current

    # Check if we're in Huxley root
    if (current / 'capsules').exists():
        return None  # User must specify capsule

    # Walk up to find capsule root
    for parent in current.parents:
        if (parent / 'specs').exists() or (parent / 'spec').exists():
            return parent

    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Automatic specification synchronization')
    parser.add_argument('--auto', action='store_true', help='Auto mode (for pre-commit hook)')
    parser.add_argument('--capsule', type=Path, help='Capsule path to sync')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without writing')

    args = parser.parse_args()

    # Determine capsule path
    if args.capsule:
        capsule_path = args.capsule
    else:
        capsule_path = find_capsule_root()

    if not capsule_path:
        print("Error: Could not find capsule root. Run from capsule directory or use --capsule", file=sys.stderr)
        sys.exit(1)

    if not capsule_path.exists():
        print(f"Error: Capsule path does not exist: {capsule_path}", file=sys.stderr)
        sys.exit(1)

    # Run sync
    syncer = SpecSyncer(capsule_path, dry_run=args.dry_run, auto_mode=args.auto)
    success = syncer.sync()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
