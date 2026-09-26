#!/usr/bin/env python3
"""
Specification Documentation Generator for Huxley
Automatically generates markdown documentation from capsule specifications

Usage:
    ./tools/generate_spec_docs.py <capsule_path>
    ./tools/generate_spec_docs.py --all
    ./tools/generate_spec_docs.py capsules/example-media-capsule
"""

import yaml
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class SpecDocGenerator:
    """Generates documentation from Huxley capsule specifications"""
    
    def __init__(self):
        self.spec_locations = ['specs', 'spec']  # Support both patterns
        self.config_locations = ['config', '.']
    
    def find_spec_files(self, capsule_path: Path) -> Dict[str, Path]:
        """Find all specification files in a Huxley capsule"""
        spec_files = {}
        
        # 1. Find specs directory (specs/ or spec/ fallback)
        for loc in self.spec_locations:
            spec_dir = capsule_path / loc
            if spec_dir.exists():
                for yaml_file in spec_dir.glob('*.yaml'):
                    spec_files[yaml_file.stem] = yaml_file
                break
        
        # 2. Find root-level framework files (Huxley structure)
        framework_files = ['standards.yaml', 'product.yaml']
        for name in framework_files:
            yaml_file = capsule_path / name
            if yaml_file.exists():
                spec_files[name.replace('.yaml', '')] = yaml_file
        
        # 3. Find context directory markdown files
        context_dir = capsule_path / 'context'
        if context_dir.exists():
            for md_file in context_dir.glob('*.md'):
                spec_files[f'context_{md_file.stem}'] = md_file
        
        # 4. Check for legacy files
        for loc in self.config_locations:
            config_dir = capsule_path / loc
            if config_dir.exists():
                for name in ['requirements', 'dependencies']:
                    yaml_file = config_dir / f'{name}.yaml'
                    if yaml_file.exists():
                        spec_files[name] = yaml_file
        
        # 5. Check for capsule.json
        capsule_json = capsule_path / 'capsule.json'
        if capsule_json.exists():
            spec_files['capsule'] = capsule_json
        
        return spec_files
    
    def load_spec(self, file_path: Path) -> Optional[Dict]:
        """Load a specification file (YAML or JSON)"""
        try:
            with open(file_path, 'r') as f:
                if file_path.suffix == '.json':
                    return json.load(f)
                elif file_path.suffix == '.md':
                    # Don't try to parse markdown as YAML
                    return None
                else:
                    return yaml.safe_load(f)
        except Exception as e:
            if file_path.suffix not in ['.md']:  # Don't warn for markdown files
                print(f"Warning: Could not load {file_path}: {e}")
            return None
    
    def generate_capsule_docs(self, capsule_path: Path) -> str:
        """Generate documentation for a single capsule"""
        capsule_name = capsule_path.name
        spec_files = self.find_spec_files(capsule_path)
        
        if not spec_files:
            return f"# {capsule_name}\n\nNo specification files found.\n"
        
        # Load all specs
        specs = {}
        for name, path in spec_files.items():
            spec = self.load_spec(path)
            if spec:
                specs[name] = spec
        
        # Generate documentation
        doc = []
        doc.append(f"# {capsule_name} Specification Documentation")
        doc.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        
        # Overview section
        doc.append("## Overview\n")
        if 'current' in specs:
            current = specs['current']
            if 'name' in current:
                doc.append(f"**Name:** {current['name']}\n")
            if 'description' in current:
                doc.append(f"**Description:** {current['description']}\n")
            if 'version' in current:
                doc.append(f"**Current Version:** {current['version']}\n")
            if 'status' in current:
                doc.append(f"**Status:** {current['status']}\n")
        elif 'capsule' in specs:
            capsule = specs['capsule']
            if 'name' in capsule:
                doc.append(f"**Name:** {capsule['name']}\n")
            if 'description' in capsule:
                doc.append(f"**Description:** {capsule['description']}\n")
        
        # Architecture section
        if 'current' in specs and 'architecture' in specs['current']:
            doc.append("\n## Architecture\n")
            arch = specs['current']['architecture']
            
            if isinstance(arch, dict):
                if 'pattern' in arch:
                    doc.append(f"**Pattern:** {arch['pattern']}\n")
                if 'components' in arch:
                    doc.append("\n### Components\n")
                    self._format_yaml_section(arch['components'], doc)
                if 'data_flow' in arch:
                    doc.append("\n### Data Flow\n")
                    self._format_yaml_section(arch['data_flow'], doc)
                if 'integrations' in arch:
                    doc.append("\n### Integrations\n")
                    self._format_yaml_section(arch['integrations'], doc)
            else:
                self._format_yaml_section(arch, doc)
        
        # Dependencies section
        if 'dependencies' in specs:
            doc.append("\n## Dependencies\n")
            self._format_yaml_section(specs['dependencies'], doc)
        elif 'current' in specs and 'dependencies' in specs['current']:
            doc.append("\n## Dependencies\n")
            self._format_yaml_section(specs['current']['dependencies'], doc)
        
        # Requirements section
        if 'requirements' in specs:
            doc.append("\n## Requirements\n")
            self._format_yaml_section(specs['requirements'], doc)
        
        # Standards section
        if 'standards' in specs:
            doc.append("\n## Quality Standards\n")
            standards = specs['standards']
            
            if 'quality_gates' in standards:
                doc.append("\n### Quality Gates\n")
                self._format_quality_gates(standards['quality_gates'], doc)
            
            if 'performance_requirements' in standards:
                doc.append("\n### Performance Requirements\n")
                self._format_yaml_section(standards['performance_requirements'], doc)
            
            if 'security_requirements' in standards:
                doc.append("\n### Security Requirements\n")
                self._format_yaml_section(standards['security_requirements'], doc)
        
        # Product/Roadmap section
        if 'product' in specs:
            doc.append("\n## Product Vision & Roadmap\n")
            product = specs['product']
            
            if 'vision' in product:
                doc.append(f"\n### Vision\n{product['vision']}\n")
            
            if 'capabilities' in product:
                doc.append("\n### Capabilities\n")
                self._format_list(product['capabilities'], doc)
            
            if 'roadmap' in product:
                doc.append("\n### Roadmap\n")
                self._format_yaml_section(product['roadmap'], doc)
        
        # Next version planning
        if 'next' in specs:
            doc.append("\n## Next Version Planning\n")
            next_spec = specs['next']
            
            if 'planned_version' in next_spec:
                doc.append(f"**Target Version:** {next_spec['planned_version']}\n")
            
            if 'planned_features' in next_spec:
                doc.append("\n### Planned Features\n")
                self._format_list(next_spec['planned_features'], doc)
            
            if 'migration_strategy' in next_spec:
                doc.append("\n### Migration Strategy\n")
                doc.append(f"{next_spec['migration_strategy']}\n")
        
        # Context documentation section
        context_files = {k: v for k, v in spec_files.items() if k.startswith('context_')}
        if context_files:
            doc.append("\n## Context Documentation\n")
            
            # Decisions
            if 'context_decisions' in context_files:
                doc.append("\n### Architectural Decisions\n")
                try:
                    with open(context_files['context_decisions'], 'r') as f:
                        decisions = f.read()
                        # Extract first 500 chars as preview
                        preview = decisions[:500] + "..." if len(decisions) > 500 else decisions
                        doc.append(f"```markdown\n{preview}\n```\n")
                        doc.append(f"*Full decisions documented in `context/decisions.md`*\n")
                except:
                    doc.append("*See `context/decisions.md` for architectural decisions*\n")
            
            # Patterns
            if 'context_patterns' in context_files:
                doc.append("\n### Learned Patterns\n")
                doc.append("*Documented patterns and best practices in `context/patterns.md`*\n")
            
            # Evolution
            if 'context_evolution' in context_files:
                doc.append("\n### Evolution Trajectory\n")
                doc.append("*Long-term roadmap and evolution path in `context/evolution.md`*\n")
        
        # File listing
        doc.append("\n## Specification Files\n")
        doc.append("| File | Location | Type |\n")
        doc.append("|------|----------|------|\n")
        for name, path in sorted(spec_files.items()):
            relative_path = path.relative_to(capsule_path)
            file_type = "YAML" if path.suffix == '.yaml' else "JSON" if path.suffix == '.json' else "Markdown"
            doc.append(f"| {name} | `{relative_path}` | {file_type} |\n")
        
        return "\n".join(doc)
    
    def _format_yaml_section(self, data: Any, doc: List[str], indent: int = 0):
        """Format a YAML section as markdown"""
        prefix = "  " * indent
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    doc.append(f"{prefix}- **{key}:**")
                    self._format_yaml_section(value, doc, indent + 1)
                else:
                    doc.append(f"{prefix}- **{key}:** {value}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    doc.append(f"{prefix}- ")
                    self._format_yaml_section(item, doc, indent + 1)
                else:
                    doc.append(f"{prefix}- {item}")
        else:
            doc.append(f"{prefix}{data}")
    
    def _format_list(self, items: List, doc: List[str]):
        """Format a list as markdown bullets"""
        if not items:
            doc.append("*No items defined*\n")
            return
        
        for item in items:
            if isinstance(item, dict):
                # Format dict as nested items
                for key, value in item.items():
                    doc.append(f"- **{key}:** {value}")
            else:
                doc.append(f"- {item}")
    
    def _format_quality_gates(self, gates: List, doc: List[str]):
        """Format quality gates as a table"""
        if not gates:
            doc.append("*No quality gates defined*\n")
            return
        
        doc.append("| Gate | Threshold | Description |")
        doc.append("|------|-----------|-------------|")
        
        for gate in gates:
            if isinstance(gate, dict):
                name = gate.get('name', 'Unknown')
                threshold = gate.get('threshold', 'N/A')
                description = gate.get('description', '')
                doc.append(f"| {name} | {threshold} | {description} |")
            else:
                doc.append(f"| {gate} | - | - |")
    
    def save_documentation(self, capsule_path: Path, content: str):
        """Save generated documentation to the capsule's docs directory"""
        docs_dir = capsule_path / 'docs'
        docs_dir.mkdir(exist_ok=True)
        
        doc_file = docs_dir / 'SPECIFICATIONS.md'
        with open(doc_file, 'w') as f:
            f.write(content)
        
        return doc_file


def generate_all_docs():
    """Generate documentation for all capsules"""
    generator = SpecDocGenerator()
    base_path = Path.cwd()
    capsules_dir = base_path / 'capsules'
    
    if not capsules_dir.exists():
        print("❌ No capsules directory found")
        return 1
    
    # Find all capsules
    capsules = [d for d in capsules_dir.iterdir() if d.is_dir()]
    
    print(f"\n📚 Generating documentation for {len(capsules)} capsules...\n")
    
    generated = []
    failed = []
    
    for capsule in sorted(capsules):
        try:
            # Check if capsule has any spec files
            spec_files = generator.find_spec_files(capsule)
            if not spec_files:
                print(f"⏭️  {capsule.name:30} - No specifications found")
                continue
            
            # Generate documentation
            content = generator.generate_capsule_docs(capsule)
            
            # Save to file
            doc_file = generator.save_documentation(capsule, content)
            
            print(f"✅ {capsule.name:30} - Generated {doc_file.name}")
            generated.append(capsule.name)
            
        except Exception as e:
            print(f"❌ {capsule.name:30} - Error: {e}")
            failed.append(capsule.name)
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"  - Generated: {len(generated)} capsules")
    print(f"  - Failed: {len(failed)} capsules")
    print(f"  - Skipped: {len(capsules) - len(generated) - len(failed)} capsules")
    
    return 0 if not failed else 1


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: generate_spec_docs.py <capsule_path> or --all")
        return 1
    
    generator = SpecDocGenerator()
    
    if sys.argv[1] == '--all':
        return generate_all_docs()
    
    capsule_path = Path(sys.argv[1]).resolve()
    
    if not capsule_path.exists():
        print(f"❌ Path does not exist: {capsule_path}")
        return 1
    
    # Generate documentation
    content = generator.generate_capsule_docs(capsule_path)
    
    # Save to file
    doc_file = generator.save_documentation(capsule_path, content)
    
    print(f"✅ Generated documentation: {doc_file}")
    print(f"\nPreview:\n{'-' * 60}")
    print(content[:500] + "..." if len(content) > 500 else content)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())