#!/usr/bin/env python3
"""
Huxley Run Manifest CLI
Command-line tool for managing run manifests
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Import Huxley config
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("paths_config", parent_dir / "global" / "config" / "paths.py")
    paths_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paths_module)
    paths = paths_module.paths
    
    spec = importlib.util.spec_from_file_location("run_manifest", parent_dir / "global" / "config" / "run_manifest.py")
    manifest_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest_module)
    RunManifest = manifest_module.RunManifest
    validate_manifest = manifest_module.validate_manifest
    
except Exception as e:
    print(f"Error importing Huxley modules: {e}")
    sys.exit(1)


def list_capsules() -> List[str]:
    """List available capsules"""
    if not paths.capsules.exists():
        return []
    
    capsules = []
    for item in paths.capsules.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            capsules.append(item.name)
    
    return sorted(capsules)


def list_runs_command(args):
    """List runs for a capsule"""
    if args.capsule == "all":
        # List runs for all capsules
        all_runs = []
        for capsule in list_capsules():
            runs = RunManifest.list_runs(capsule)
            for run in runs:
                run["capsule"] = capsule
                all_runs.append(run)
        
        # Sort by start time
        all_runs.sort(key=lambda x: x["started_at"], reverse=True)
        runs = all_runs
    else:
        runs = RunManifest.list_runs(args.capsule)
    
    if not runs:
        print(f"No runs found for capsule: {args.capsule}")
        return
    
    # Display runs
    print(f"{'Capsule':<20} {'Run ID':<25} {'Started At':<20} {'Status':<12} {'Duration':<10}")
    print("-" * 95)
    
    for run in runs:
        capsule = run.get("capsule", args.capsule)
        duration = ""
        if run.get("duration_ms"):
            duration = f"{run['duration_ms']/1000:.1f}s"
        
        print(f"{capsule:<20} {run['run_id']:<25} {run['started_at'][:19]:<20} "
              f"{run['status']:<12} {duration:<10}")


def show_run_command(args):
    """Show details of a specific run"""
    # Find the run
    manifest_path = None
    
    if args.manifest_path:
        manifest_path = Path(args.manifest_path)
    else:
        # Search for run_id in capsule
        runs = RunManifest.list_runs(args.capsule)
        for run in runs:
            if run["run_id"] == args.run_id:
                manifest_path = Path(run["manifest_path"])
                break
        
        if not manifest_path:
            print(f"Run {args.run_id} not found in capsule {args.capsule}")
            return
    
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return
    
    # Load and display manifest
    try:
        manifest = RunManifest.load_manifest(manifest_path)
        data = manifest.to_dict()
        
        if args.json:
            print(json.dumps(data, indent=2, default=str))
        else:
            # Human-readable format
            print(f"Run: {data['run_id']}")
            print(f"Capsule: {data['capsule']['name']} v{data['capsule']['version']}")
            
            exec_info = data['execution']
            print(f"Started: {exec_info['started_at']}")
            if exec_info.get('ended_at'):
                print(f"Ended: {exec_info['ended_at']}")
                if exec_info.get('duration_ms'):
                    print(f"Duration: {exec_info['duration_ms']/1000:.2f}s")
            print(f"Status: {exec_info['status']}")
            if exec_info.get('exit_code') is not None:
                print(f"Exit Code: {exec_info['exit_code']}")
            
            # Environment
            env = data['environment']
            print(f"\\nEnvironment:")
            print(f"  Platform: {env['system']['platform']}")
            print(f"  Python: {env['system']['python_version']}")
            
            # Inputs
            if data['inputs'].get('files'):
                print(f"\\nInput Files: {len(data['inputs']['files'])}")
                
            # Outputs
            outputs = data['outputs']
            if outputs.get('artifacts'):
                print(f"\\nArtifacts: {len(outputs['artifacts'])}")
                for artifact in outputs['artifacts'][:5]:  # Show first 5
                    print(f"  - {artifact['path']} ({artifact['type']})")
                if len(outputs['artifacts']) > 5:
                    print(f"  ... and {len(outputs['artifacts']) - 5} more")
            
            # Validation
            validation = data['validation']
            if validation.get('dod_checks'):
                print(f"\\nDoD Checks: {len(validation['dod_checks'])}")
                for check in validation['dod_checks']:
                    status_icon = "✓" if check['status'] == 'passed' else "✗"
                    print(f"  {status_icon} {check['name']}: {check['status']}")
            
            if validation.get('test_results'):
                tests = validation['test_results']
                total = tests.get('total', 0)
                if total > 0:
                    print(f"\\nTest Results: {tests.get('passed', 0)}/{total} passed")
    
    except Exception as e:
        print(f"Error loading manifest: {e}")


def validate_command(args):
    """Validate a manifest file"""
    manifest_path = Path(args.manifest_path)
    
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return
    
    try:
        with open(manifest_path) as f:
            data = json.load(f)
        
        errors = validate_manifest(data)
        
        if errors:
            print("Validation failed:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("Manifest is valid")
    
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Validation error: {e}")
        sys.exit(1)


def replay_command(args):
    """Generate replay command for a run"""
    # Find the run
    runs = RunManifest.list_runs(args.capsule)
    manifest_path = None
    
    for run in runs:
        if run["run_id"] == args.run_id:
            manifest_path = Path(run["manifest_path"])
            break
    
    if not manifest_path:
        print(f"Run {args.run_id} not found in capsule {args.capsule}")
        return
    
    try:
        manifest = RunManifest.load_manifest(manifest_path)
        data = manifest.to_dict()
        
        # Generate replay information
        print(f"Replay information for run: {args.run_id}")
        print(f"Capsule: {data['capsule']['name']}")
        
        repro = data.get('reproducibility', {})
        if repro.get('git_commit'):
            print(f"\\nGit commit: {repro['git_commit']}")
            print(f"To restore: git checkout {repro['git_commit']}")
        
        if repro.get('random_seed'):
            print(f"\\nRandom seed: {repro['random_seed']}")
        
        # Environment variables
        env_vars = data['environment'].get('variables', {})
        if env_vars:
            print(f"\\nEnvironment variables:")
            for key, value in env_vars.items():
                if key.startswith('BUILDER_'):
                    print(f"  export {key}='{value}'")
        
        # Input parameters
        params = data['inputs'].get('parameters', {})
        if params:
            print(f"\\nInput parameters:")
            for key, value in params.items():
                print(f"  {key}: {value}")
        
        # Dependencies
        deps = data['inputs'].get('dependencies', {})
        if deps.get('python_packages'):
            print(f"\\nPython packages (sample):")
            # Show key packages
            for pkg, version in list(deps['python_packages'].items())[:10]:
                print(f"  {pkg}=={version}")
            if len(deps['python_packages']) > 10:
                print(f"  ... and {len(deps['python_packages']) - 10} more")
    
    except Exception as e:
        print(f"Error loading manifest: {e}")


def stats_command(args):
    """Show statistics about runs"""
    all_runs = []
    capsules = list_capsules()
    
    for capsule in capsules:
        runs = RunManifest.list_runs(capsule)
        for run in runs:
            run["capsule"] = capsule
            all_runs.append(run)
    
    if not all_runs:
        print("No runs found")
        return
    
    # Calculate statistics
    total_runs = len(all_runs)
    status_counts = {}
    capsule_counts = {}
    
    for run in all_runs:
        status = run.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        
        capsule = run["capsule"]
        capsule_counts[capsule] = capsule_counts.get(capsule, 0) + 1
    
    print(f"Run Statistics:")
    print(f"  Total runs: {total_runs}")
    print(f"  Total capsules: {len(capsules)}")
    
    print(f"\\nBy Status:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    
    print(f"\\nBy Capsule:")
    for capsule, count in sorted(capsule_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {capsule}: {count}")
    
    # Recent activity
    recent_runs = sorted(all_runs, key=lambda x: x["started_at"], reverse=True)[:5]
    print(f"\\nRecent runs:")
    for run in recent_runs:
        print(f"  {run['capsule']}/{run['run_id']} - {run['started_at'][:19]} ({run['status']})")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Huxley Run Manifest CLI")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List runs
    list_parser = subparsers.add_parser("list", help="List runs for a capsule")
    list_parser.add_argument("capsule", help="Capsule name (or 'all' for all capsules)")
    
    # Show run details
    show_parser = subparsers.add_parser("show", help="Show run details")
    show_parser.add_argument("capsule", help="Capsule name")
    show_parser.add_argument("run_id", help="Run ID")
    show_parser.add_argument("--json", action="store_true", help="Output as JSON")
    show_parser.add_argument("--manifest-path", help="Direct path to manifest file")
    
    # Validate manifest
    validate_parser = subparsers.add_parser("validate", help="Validate manifest file")
    validate_parser.add_argument("manifest_path", help="Path to manifest file")
    
    # Generate replay info
    replay_parser = subparsers.add_parser("replay", help="Generate replay information")
    replay_parser.add_argument("capsule", help="Capsule name")
    replay_parser.add_argument("run_id", help="Run ID")
    
    # Show statistics
    stats_parser = subparsers.add_parser("stats", help="Show run statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute command
    if args.command == "list":
        list_runs_command(args)
    elif args.command == "show":
        show_run_command(args)
    elif args.command == "validate":
        validate_command(args)
    elif args.command == "replay":
        replay_command(args)
    elif args.command == "stats":
        stats_command(args)


if __name__ == "__main__":
    main()