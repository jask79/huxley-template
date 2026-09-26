#!/usr/bin/env python3
"""
Quick Cross-Capsule Dependency Check
Fast optimization analysis for Huxley
"""

import os
import json
from pathlib import Path

def quick_scan():
    """Quick dependency scan of active capsules"""
    catalyst_root = Path('{{CATALYST_ROOT}}')
    capsules_dir = catalyst_root / 'capsules'
    
    results = {
        'active_capsules': [],
        'shared_usage': 0,
        'cross_refs': 0,
        'mcp_usage': 0
    }
    
    # Scan active capsules only
    for capsule_dir in capsules_dir.iterdir():
        if not capsule_dir.is_dir() or capsule_dir.name.startswith('.'):
            continue
            
        capsule_name = capsule_dir.name
        results['active_capsules'].append(capsule_name)
        
        # Quick checks
        if (capsule_dir / 'ops' / 'mcp.json').exists():
            results['mcp_usage'] += 1
            
        req_file = capsule_dir / 'spec' / 'requirements.yaml'
        if req_file.exists():
            try:
                with open(req_file, 'r') as f:
                    content = f.read(200)  # First 200 chars
                    if 'shared' in content.lower():
                        results['shared_usage'] += 1
                    if 'capsules' in content.lower():
                        results['cross_refs'] += 1
            except:
                pass
    
    return results

def generate_quick_report(results):
    """Generate optimization recommendations"""
    report = f"""# Quick Dependency Analysis

## Summary
- Active capsules: {len(results['active_capsules'])}
- Capsules using shared resources: {results['shared_usage']}
- Cross-capsule references: {results['cross_refs']}
- MCP-enabled capsules: {results['mcp_usage']}

## Active Capsules
{chr(10).join(f"- {name}" for name in results['active_capsules'])}

## Optimization Status
✅ Capsule isolation: {len(results['active_capsules'])} isolated units
✅ MCP integration: {results['mcp_usage']}/{len(results['active_capsules'])} capsules
⚠️ Shared resource usage: {results['shared_usage']} detected
⚠️ Cross-capsule coupling: {results['cross_refs']} references

## Recommendations
1. **Maintain isolation**: Current capsule boundaries are effective
2. **Expand MCP usage**: Consider MCP for remaining {len(results['active_capsules']) - results['mcp_usage']} capsules
3. **Monitor coupling**: Review cross-capsule references for optimization
4. **Standardize shared patterns**: Create shared utilities for common needs

## Health Score: {int((1 - results['cross_refs']/max(len(results['active_capsules']), 1)) * 100)}%
"""
    return report

if __name__ == "__main__":
    results = quick_scan()
    report = generate_quick_report(results)
    print(report)
    
    # Save report
    output_file = Path('{{CATALYST_ROOT}}/registry/quick_dependency_analysis.md')
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(f"\nReport saved to: {output_file}")