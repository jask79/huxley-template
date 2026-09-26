#!/usr/bin/env python3
"""
Cross-Capsule Dependency Resolver
Optimizes dependency handling between capsules
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

class DependencyResolver:
    def __init__(self, catalyst_root: str = None):
        self.catalyst_root = Path(catalyst_root or os.environ.get('CATALYST_ROOT', os.getcwd()))
        self.capsules_dir = self.catalyst_root / 'capsules'
        self.shared_dir = self.catalyst_root / 'shared'
        self.registry_dir = self.catalyst_root / 'registry'
        
    def scan_dependencies(self) -> Dict[str, Dict]:
        """Scan all capsules for dependencies"""
        dependencies = {}
        
        for capsule_dir in self.capsules_dir.iterdir():
            if not capsule_dir.is_dir() or capsule_dir.name.startswith('.'):
                continue
                
            capsule_name = capsule_dir.name
            deps = self._scan_capsule_dependencies(capsule_dir)
            dependencies[capsule_name] = deps
            
        return dependencies
    
    def _scan_capsule_dependencies(self, capsule_dir: Path) -> Dict:
        """Scan a single capsule for dependencies"""
        deps = {
            'external_tools': [],
            'shared_resources': [],
            'mcp_servers': [],
            'cross_capsule_refs': []
        }
        
        # Check requirements.yaml
        req_file = capsule_dir / 'spec' / 'requirements.yaml'
        if req_file.exists():
            deps.update(self._parse_requirements(req_file))
        
        # Check dependencies.yaml
        dep_file = capsule_dir / 'spec' / 'dependencies.yaml'
        if dep_file.exists():
            deps.update(self._parse_dependencies(dep_file))
            
        # Check for shared resource usage
        deps['shared_resources'] = self._find_shared_usage(capsule_dir)
        
        # Check for cross-capsule references
        deps['cross_capsule_refs'] = self._find_cross_refs(capsule_dir)
        
        return deps
    
    def _parse_requirements(self, file_path: Path) -> Dict:
        """Parse requirements.yaml for dependencies"""
        try:
            import yaml
            with open(file_path) as f:
                content = yaml.safe_load(f)
            
            deps = {}
            if 'dependencies' in content:
                deps['external_tools'] = content['dependencies'].get('tools', [])
                deps['mcp_servers'] = content['dependencies'].get('mcp_servers', [])
                
            return deps
        except Exception:
            return {}
    
    def _parse_dependencies(self, file_path: Path) -> Dict:
        """Parse dependencies.yaml for detailed deps"""
        try:
            import yaml
            with open(file_path) as f:
                content = yaml.safe_load(f)
            return content
        except Exception:
            return {}
    
    def _find_shared_usage(self, capsule_dir: Path) -> List[str]:
        """Find references to shared/ directory"""
        shared_refs = []
        
        # Check only Python files to avoid timeout
        for pattern in ['**/*.py']:
            try:
                for file_path in list(capsule_dir.glob(pattern))[:10]:  # Limit to 10 files
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(1000)  # Read only first 1000 chars
                            if 'shared/' in content:
                                shared_refs.append('shared_resource_found')
                    except Exception:
                        continue
            except Exception:
                continue
                    
        return shared_refs
    
    def _find_cross_refs(self, capsule_dir: Path) -> List[str]:
        """Find references to other capsules"""
        cross_refs = []
        capsule_name = capsule_dir.name
        
        # Quick check in main files only
        key_files = [
            capsule_dir / 'README.md',
            capsule_dir / 'spec' / 'requirements.yaml'
        ]
        
        for file_path in key_files:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(500)  # First 500 chars only
                        if 'capsules/' in content:
                            cross_refs.append('cross_ref_found')
                except Exception:
                    continue
                    
        return cross_refs
    
    def optimize_dependencies(self, dependencies: Dict[str, Dict]) -> Dict[str, List[str]]:
        """Generate optimization recommendations"""
        recommendations = {}
        
        # Find duplicate shared resources
        shared_usage = {}
        for capsule, deps in dependencies.items():
            for shared_ref in deps.get('shared_resources', []):
                if shared_ref not in shared_usage:
                    shared_usage[shared_ref] = []
                shared_usage[shared_ref].append(capsule)
        
        # Recommend consolidation for frequently used resources
        frequent_shared = {k: v for k, v in shared_usage.items() if len(v) > 2}
        if frequent_shared:
            recommendations['consolidate_shared'] = [
                f"Resource '{res}' used by {len(capsules)} capsules: {', '.join(capsules)}"
                for res, capsules in frequent_shared.items()
            ]
        
        # Find circular dependencies
        circular = self._find_circular_deps(dependencies)
        if circular:
            recommendations['circular_dependencies'] = circular
        
        # Recommend shared utilities
        common_patterns = self._find_common_patterns(dependencies)
        if common_patterns:
            recommendations['create_shared_utils'] = common_patterns
            
        return recommendations
    
    def _find_circular_deps(self, dependencies: Dict[str, Dict]) -> List[str]:
        """Detect circular dependencies between capsules"""
        circular = []
        
        for capsule_a, deps_a in dependencies.items():
            cross_refs_a = deps_a.get('cross_capsule_refs', [])
            for capsule_b in cross_refs_a:
                if capsule_b in dependencies:
                    cross_refs_b = dependencies[capsule_b].get('cross_capsule_refs', [])
                    if capsule_a in cross_refs_b:
                        circular.append(f"{capsule_a} ↔ {capsule_b}")
        
        return list(set(circular))
    
    def _find_common_patterns(self, dependencies: Dict[str, Dict]) -> List[str]:
        """Find common external tool usage patterns"""
        tool_usage = {}
        
        for capsule, deps in dependencies.items():
            for tool in deps.get('external_tools', []):
                if tool not in tool_usage:
                    tool_usage[tool] = []
                tool_usage[tool].append(capsule)
        
        # Tools used by 3+ capsules should be in shared/
        common_tools = [
            f"Tool '{tool}' used by {len(capsules)} capsules - consider shared utility"
            for tool, capsules in tool_usage.items() 
            if len(capsules) >= 3
        ]
        
        return common_tools
    
    def generate_report(self) -> str:
        """Generate dependency optimization report"""
        dependencies = self.scan_dependencies()
        optimizations = self.optimize_dependencies(dependencies)
        
        report = "# Cross-Capsule Dependency Analysis\n\n"
        
        # Summary
        report += f"## Summary\n"
        report += f"- Total capsules analyzed: {len(dependencies)}\n"
        report += f"- Optimization opportunities: {len(optimizations)}\n\n"
        
        # Current dependencies
        report += "## Current Dependencies\n\n"
        for capsule, deps in dependencies.items():
            report += f"### {capsule}\n"
            if deps.get('external_tools'):
                report += f"- External tools: {', '.join(deps['external_tools'])}\n"
            if deps.get('shared_resources'):
                report += f"- Shared resources: {len(deps['shared_resources'])} references\n"
            if deps.get('cross_capsule_refs'):
                report += f"- Cross-capsule refs: {', '.join(deps['cross_capsule_refs'])}\n"
            report += "\n"
        
        # Optimization recommendations
        report += "## Optimization Recommendations\n\n"
        for category, items in optimizations.items():
            report += f"### {category.replace('_', ' ').title()}\n"
            for item in items:
                report += f"- {item}\n"
            report += "\n"
        
        return report

def main():
    resolver = DependencyResolver()
    report = resolver.generate_report()
    print(report)
    
    # Save to file
    output_file = resolver.registry_dir / 'dependency_analysis.md'
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(f"Report saved to: {output_file}")

if __name__ == "__main__":
    main()