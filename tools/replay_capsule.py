#!/usr/bin/env python3
"""
Build Replay Tool - Reproducible run replay for iterating on successful patterns
Uses recorded manifest, seed inputs, and environment to recreate exact conditions
"""

import os
import sys
import json
import shutil
import pathlib
import subprocess
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import tempfile

# Add Huxley tools to path
CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")
sys.path.append(str(CATALYST_ROOT / "tools"))

try:
    from run_manifest_schema import RunManifest, RunInput, RunOutput, RunStage
    from events_logger import log_event
    from capsule_autopsy import CapsuleAutopsyAgent
except ImportError as e:
    print(f"Warning: Could not import Huxley tools: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CapsuleReplayManager:
    """Manages capsule run replay for reproducible iterations"""
    
    def __init__(self):
        self.catalyst_root = CATALYST_ROOT
        self.temp_dir = None
        
    def replay_run(self, capsule_name: str, run_id: str, 
                   modifications: Dict[str, Any] = None,
                   dry_run: bool = False) -> Dict[str, Any]:
        """Replay a specific capsule run with optional modifications"""
        logger.info(f"Starting replay of {capsule_name}:{run_id}")
        
        replay_results = {
            "original_run_id": run_id,
            "replay_run_id": None,
            "capsule_name": capsule_name,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "modifications": modifications or {},
            "dry_run": dry_run,
            "stages_replayed": 0,
            "differences": [],
            "errors": []
        }
        
        try:
            # Load original run manifest
            original_manifest = self._load_run_manifest(capsule_name, run_id)
            if not original_manifest:
                raise ValueError(f"Could not load manifest for {capsule_name}:{run_id}")
            
            # Create replay environment
            replay_manifest = self._create_replay_manifest(original_manifest, modifications)
            replay_results["replay_run_id"] = replay_manifest.run_id
            
            if dry_run:
                replay_results["success"] = True
                replay_results["dry_run_plan"] = self._generate_dry_run_plan(original_manifest, modifications)
                return replay_results
            
            # Set up replay environment
            self._setup_replay_environment(capsule_name, original_manifest, replay_manifest)
            
            # Execute replay
            success = self._execute_replay(capsule_name, replay_manifest)
            replay_results["success"] = success
            replay_results["stages_replayed"] = len(replay_manifest.stages)
            
            # Compare results with original
            if success:
                differences = self._compare_with_original(original_manifest, replay_manifest)
                replay_results["differences"] = differences
            
            # Store replay results
            self._store_replay_results(capsule_name, replay_manifest, replay_results)
            
            # Trigger autopsy for replay
            self._trigger_replay_autopsy(capsule_name, replay_manifest.run_id, original_manifest.run_id)
            
            logger.info(f"Replay completed: {'SUCCESS' if success else 'FAILED'}")
            
        except Exception as e:
            logger.error(f"Replay failed: {e}")
            replay_results["errors"].append(str(e))
            
        finally:
            self._cleanup_temp_resources()
        
        return replay_results
    
    def list_replayable_runs(self, capsule_name: str, 
                           successful_only: bool = True) -> List[Dict[str, Any]]:
        """List runs that can be replayed"""
        capsule_dir = self.catalyst_root / "capsules" / capsule_name
        runs_dir = capsule_dir / "runs"
        
        replayable_runs = []
        
        if not runs_dir.exists():
            return replayable_runs
        
        for run_dir in runs_dir.iterdir():
            if run_dir.is_dir():
                manifest_file = run_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        manifest = RunManifest.load(manifest_file)
                        
                        # Filter by success if requested
                        if successful_only and not manifest.success:
                            continue
                        
                        replayable_runs.append({
                            "run_id": manifest.run_id,
                            "timestamp": manifest.start_time,
                            "success": manifest.success,
                            "duration_ms": manifest.total_duration_ms,
                            "stages": len(manifest.stages),
                            "trigger": manifest.trigger
                        })
                        
                    except Exception as e:
                        logger.warning(f"Could not load manifest from {manifest_file}: {e}")
        
        # Sort by timestamp (most recent first)
        replayable_runs.sort(key=lambda x: x["timestamp"], reverse=True)
        return replayable_runs
    
    def _load_run_manifest(self, capsule_name: str, run_id: str) -> Optional[RunManifest]:
        """Load run manifest for replay"""
        capsule_dir = self.catalyst_root / "capsules" / capsule_name
        manifest_file = capsule_dir / "runs" / run_id / "manifest.json"
        
        if not manifest_file.exists():
            logger.error(f"Manifest file not found: {manifest_file}")
            return None
        
        try:
            return RunManifest.load(manifest_file)
        except Exception as e:
            logger.error(f"Could not load manifest: {e}")
            return None
    
    def _create_replay_manifest(self, original: RunManifest, 
                              modifications: Dict[str, Any] = None) -> RunManifest:
        """Create replay manifest based on original with modifications"""
        replay_id = f"{original.capsule_name}-replay-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Deep copy original manifest
        replay_data = json.loads(original.to_json())
        
        # Update for replay
        replay_data["run_id"] = replay_id
        replay_data["start_time"] = datetime.now().isoformat()
        replay_data["end_time"] = None
        replay_data["total_duration_ms"] = None
        replay_data["status"] = "pending"
        replay_data["success"] = False
        replay_data["trigger"] = "replay"
        replay_data["metadata"] = replay_data.get("metadata", {})
        replay_data["metadata"]["original_run_id"] = original.run_id
        replay_data["metadata"]["replay"] = True
        
        # Reset stages
        for stage in replay_data.get("stages", []):
            stage["start_time"] = None
            stage["end_time"] = None
            stage["duration_ms"] = None
            stage["status"] = "pending"
            stage["exit_code"] = None
            stage["error_message"] = None
        
        # Apply modifications
        if modifications:
            self._apply_modifications(replay_data, modifications)
        
        return RunManifest.from_dict(replay_data)
    
    def _apply_modifications(self, manifest_data: Dict[str, Any], 
                           modifications: Dict[str, Any]):
        """Apply modifications to replay manifest"""
        
        # Modify inputs
        if "inputs" in modifications:
            input_mods = modifications["inputs"]
            for input_item in manifest_data.get("inputs", []):
                if input_item["name"] in input_mods:
                    input_item["value"] = input_mods[input_item["name"]]
        
        # Modify environment variables
        if "environment" in modifications:
            env_mods = modifications["environment"]
            env_vars = manifest_data.setdefault("environment", {}).setdefault("environment_variables", {})
            env_vars.update(env_mods)
        
        # Modify stages (skip, add, modify)
        if "stages" in modifications:
            stage_mods = modifications["stages"]
            
            # Handle stage skips
            if "skip" in stage_mods:
                stages_to_skip = stage_mods["skip"]
                manifest_data["stages"] = [
                    stage for stage in manifest_data.get("stages", [])
                    if stage["name"] not in stages_to_skip
                ]
            
            # Handle stage modifications
            if "modify" in stage_mods:
                for stage in manifest_data.get("stages", []):
                    if stage["name"] in stage_mods["modify"]:
                        stage_mod = stage_mods["modify"][stage["name"]]
                        stage.update(stage_mod)
        
        # Modify metadata
        if "metadata" in modifications:
            manifest_data.setdefault("metadata", {}).update(modifications["metadata"])
    
    def _generate_dry_run_plan(self, original: RunManifest, 
                             modifications: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate dry run plan showing what would be replayed"""
        plan = {
            "original_run_id": original.run_id,
            "original_success": original.success,
            "original_duration_ms": original.total_duration_ms,
            "stages_to_replay": [],
            "inputs_changed": [],
            "environment_changed": [],
            "estimated_duration_ms": original.total_duration_ms
        }
        
        # Analyze stages
        for stage in original.stages:
            stage_plan = {
                "name": stage.name,
                "original_status": stage.status,
                "original_duration_ms": stage.duration_ms,
                "will_replay": True
            }
            
            # Check if stage will be skipped
            if (modifications and 
                "stages" in modifications and 
                "skip" in modifications["stages"] and 
                stage.name in modifications["stages"]["skip"]):
                stage_plan["will_replay"] = False
                stage_plan["reason"] = "Explicitly skipped in modifications"
            
            plan["stages_to_replay"].append(stage_plan)
        
        # Analyze input changes
        if modifications and "inputs" in modifications:
            for input_name, new_value in modifications["inputs"].items():
                original_input = next(
                    (inp for inp in original.inputs if inp.name == input_name), 
                    None
                )
                if original_input:
                    plan["inputs_changed"].append({
                        "name": input_name,
                        "original_value": original_input.value,
                        "new_value": new_value
                    })
        
        # Analyze environment changes
        if modifications and "environment" in modifications:
            plan["environment_changed"] = list(modifications["environment"].keys())
        
        # Estimate duration (reduce if stages are skipped)
        skipped_duration = sum(
            stage.duration_ms or 0 
            for stage in original.stages 
            if (modifications and 
                "stages" in modifications and 
                "skip" in modifications["stages"] and 
                stage.name in modifications["stages"]["skip"])
        )
        plan["estimated_duration_ms"] = max(0, (original.total_duration_ms or 0) - skipped_duration)
        
        return plan
    
    def _setup_replay_environment(self, capsule_name: str, 
                                original: RunManifest, replay: RunManifest):
        """Set up environment for replay"""
        capsule_dir = self.catalyst_root / "capsules" / capsule_name
        
        # Create replay run directory
        replay_run_dir = capsule_dir / "runs" / replay.run_id
        replay_run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save replay manifest
        replay.save(replay_run_dir / "manifest.json")
        
        # Copy input files if they exist
        original_run_dir = capsule_dir / "runs" / original.run_id
        if original_run_dir.exists():
            # Copy any input files that were captured
            for input_item in original.inputs:
                if input_item.source == "file" and isinstance(input_item.value, str):
                    input_path = pathlib.Path(input_item.value)
                    if input_path.exists() and input_path.is_relative_to(original_run_dir):
                        # Copy to replay directory
                        relative_path = input_path.relative_to(original_run_dir)
                        dest_path = replay_run_dir / relative_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(input_path, dest_path)
                        
                        # Update input path in replay manifest
                        for replay_input in replay.inputs:
                            if replay_input.name == input_item.name:
                                replay_input.value = str(dest_path)
        
        logger.info(f"Replay environment set up in {replay_run_dir}")
    
    def _execute_replay(self, capsule_name: str, replay_manifest: RunManifest) -> bool:
        """Execute the replay"""
        capsule_dir = self.catalyst_root / "capsules" / capsule_name
        replay_run_dir = capsule_dir / "runs" / replay_manifest.run_id
        
        # Start replay timing
        replay_manifest.start_time = datetime.now().isoformat()
        overall_success = True
        
        try:
            # Set up environment variables
            replay_env = os.environ.copy()
            if replay_manifest.environment.environment_variables:
                replay_env.update(replay_manifest.environment.environment_variables)
            
            # Execute each stage
            for stage in replay_manifest.stages:
                if stage.status == "pending":  # Only run pending stages
                    success = self._execute_stage(capsule_dir, replay_run_dir, stage, replay_env)
                    if not success:
                        overall_success = False
                        break  # Stop on first failure
            
            # Complete the replay
            replay_manifest.complete_run(
                exit_code=0 if overall_success else 1,
                error_summary=None if overall_success else "One or more stages failed during replay"
            )
            
            # Save final manifest
            replay_manifest.save(replay_run_dir / "manifest.json")
            
            return overall_success
            
        except Exception as e:
            logger.error(f"Error during replay execution: {e}")
            replay_manifest.complete_run(exit_code=2, error_summary=str(e))
            replay_manifest.save(replay_run_dir / "manifest.json")
            return False
    
    def _execute_stage(self, capsule_dir: pathlib.Path, replay_run_dir: pathlib.Path,
                      stage: RunStage, env: Dict[str, str]) -> bool:
        """Execute a single stage during replay"""
        stage.start_time = datetime.now().isoformat()
        stage.status = "running"
        
        try:
            if not stage.command:
                # No command to execute, mark as success
                stage.status = "success"
                stage.exit_code = 0
                stage.end_time = datetime.now().isoformat()
                return True
            
            # Log stage execution
            stage_log = replay_run_dir / f"{stage.name}.log"
            
            with open(stage_log, 'w') as log_file:
                # Execute command
                result = subprocess.run(
                    stage.command,
                    shell=True,
                    cwd=capsule_dir,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    timeout=300  # 5 minute timeout per stage
                )
            
            # Update stage with results
            stage.exit_code = result.returncode
            stage.status = "success" if result.returncode == 0 else "failed"
            stage.log_path = str(stage_log)
            
            if result.returncode != 0:
                # Read error from log
                try:
                    with open(stage_log, 'r') as f:
                        log_content = f.read()
                        # Get last few lines as error message
                        error_lines = log_content.strip().split('\n')[-5:]
                        stage.error_message = '\n'.join(error_lines)
                except:
                    stage.error_message = f"Stage failed with exit code {result.returncode}"
            
            stage.end_time = datetime.now().isoformat()
            
            # Calculate duration
            if stage.start_time:
                start = datetime.fromisoformat(stage.start_time)
                end = datetime.fromisoformat(stage.end_time)
                stage.duration_ms = int((end - start).total_seconds() * 1000)
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            stage.status = "failed"
            stage.exit_code = 124  # Standard timeout exit code
            stage.error_message = "Stage timed out after 300 seconds"
            stage.end_time = datetime.now().isoformat()
            return False
            
        except Exception as e:
            stage.status = "failed"
            stage.exit_code = 1
            stage.error_message = str(e)
            stage.end_time = datetime.now().isoformat()
            return False
    
    def _compare_with_original(self, original: RunManifest, 
                             replay: RunManifest) -> List[Dict[str, Any]]:
        """Compare replay results with original run"""
        differences = []
        
        # Compare overall success
        if original.success != replay.success:
            differences.append({
                "type": "overall_result",
                "original": original.success,
                "replay": replay.success,
                "description": f"Overall result changed: {original.success} -> {replay.success}"
            })
        
        # Compare duration (allow 20% variance)
        if original.total_duration_ms and replay.total_duration_ms:
            duration_diff_pct = abs(replay.total_duration_ms - original.total_duration_ms) / original.total_duration_ms
            if duration_diff_pct > 0.2:  # More than 20% difference
                differences.append({
                    "type": "duration",
                    "original": original.total_duration_ms,
                    "replay": replay.total_duration_ms,
                    "difference_pct": round(duration_diff_pct * 100, 1),
                    "description": f"Duration difference: {round(duration_diff_pct * 100, 1)}%"
                })
        
        # Compare stage results
        original_stages = {s.name: s for s in original.stages}
        for replay_stage in replay.stages:
            original_stage = original_stages.get(replay_stage.name)
            if original_stage:
                if original_stage.status != replay_stage.status:
                    differences.append({
                        "type": "stage_status",
                        "stage": replay_stage.name,
                        "original": original_stage.status,
                        "replay": replay_stage.status,
                        "description": f"Stage '{replay_stage.name}' status: {original_stage.status} -> {replay_stage.status}"
                    })
        
        return differences
    
    def _store_replay_results(self, capsule_name: str, replay_manifest: RunManifest,
                            results: Dict[str, Any]):
        """Store replay results and log events"""
        try:
            # Log replay event
            log_event(
                stage="capsule_replay",
                level="INFO" if results["success"] else "WARNING",
                message=f"Capsule replay {'completed' if results['success'] else 'failed'}: {capsule_name}",
                capsule=capsule_name,
                data={
                    "original_run_id": results["original_run_id"],
                    "replay_run_id": results["replay_run_id"],
                    "stages_replayed": results["stages_replayed"],
                    "success": results["success"],
                    "modifications_applied": len(results["modifications"]) > 0
                }
            )
            
        except Exception as e:
            logger.warning(f"Failed to store replay results: {e}")
    
    def _trigger_replay_autopsy(self, capsule_name: str, replay_run_id: str, 
                              original_run_id: str):
        """Trigger autopsy for replay to compare with original"""
        try:
            autopsy_agent = CapsuleAutopsyAgent()
            analysis = autopsy_agent.perform_autopsy(capsule_name, replay_run_id)
            
            # Store comparison metadata
            analysis.metadata = analysis.metadata or {}
            analysis.metadata["replay_comparison"] = {
                "original_run_id": original_run_id,
                "is_replay": True
            }
            
        except Exception as e:
            logger.warning(f"Failed to trigger replay autopsy: {e}")
    
    def _cleanup_temp_resources(self):
        """Clean up temporary resources"""
        if self.temp_dir and pathlib.Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")

def main():
    """CLI interface for capsule replay"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Capsule Replay Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List replayable runs")
    list_parser.add_argument("capsule_name", help="Name of capsule")
    list_parser.add_argument("--all", action="store_true", help="Include failed runs")
    
    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay a run")
    replay_parser.add_argument("capsule_name", help="Name of capsule")
    replay_parser.add_argument("run_id", help="Run ID to replay")
    replay_parser.add_argument("--dry-run", action="store_true", help="Show what would be replayed")
    replay_parser.add_argument("--modify-input", action="append", nargs=2, 
                              metavar=("NAME", "VALUE"), help="Modify input value")
    replay_parser.add_argument("--modify-env", action="append", nargs=2,
                              metavar=("NAME", "VALUE"), help="Modify environment variable")
    replay_parser.add_argument("--skip-stage", action="append", 
                              metavar="STAGE", help="Skip specific stage")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    manager = CapsuleReplayManager()
    
    try:
        if args.command == "list":
            runs = manager.list_replayable_runs(
                args.capsule_name, 
                successful_only=not args.all
            )
            
            if not runs:
                print(f"No replayable runs found for {args.capsule_name}")
            else:
                print(f"Replayable runs for {args.capsule_name}:")
                print("=" * 60)
                for run in runs:
                    status = "✅" if run["success"] else "❌"
                    duration = f"{run['duration_ms']}ms" if run['duration_ms'] else "Unknown"
                    print(f"    {run['timestamp']} | {run['stages']} stages | {run['trigger']}")
                    print()
        
        elif args.command == "replay":
            # Prepare modifications
            modifications = {}
            
            if args.modify_input:
                modifications["inputs"] = {name: value for name, value in args.modify_input}
            
            if args.modify_env:
                modifications["environment"] = {name: value for name, value in args.modify_env}
            
            if args.skip_stage:
                modifications.setdefault("stages", {})["skip"] = args.skip_stage
            
            # Execute replay
            results = manager.replay_run(
                args.capsule_name,
                args.run_id,
                modifications=modifications if modifications else None,
                dry_run=args.dry_run
            )
            
            if args.dry_run:
                print(f"🔍 Dry Run Plan for {args.capsule_name}:{args.run_id}")
                print("=" * 50)
                plan = results["dry_run_plan"]
                print(f"Original: {'✅' if plan['original_success'] else '❌'} ({plan['original_duration_ms']}ms)")
                print(f"Estimated: ~{plan['estimated_duration_ms']}ms")
                
                if plan["inputs_changed"]:
                    print(f"\nInput Changes ({len(plan['inputs_changed'])}):")
                    for change in plan["inputs_changed"]:
                        print(f"  {change['name']}: {change['original_value']} -> {change['new_value']}")
                
                if plan["environment_changed"]:
                    print(f"\nEnvironment Changes: {', '.join(plan['environment_changed'])}")
                
                stages_to_replay = [s for s in plan["stages_to_replay"] if s["will_replay"]]
                stages_to_skip = [s for s in plan["stages_to_replay"] if not s["will_replay"]]
                
                print(f"\nStages to Replay ({len(stages_to_replay)}):")
                for stage in stages_to_replay:
                    print(f"  ✅ {stage['name']} ({stage['original_duration_ms']}ms)")
                
                if stages_to_skip:
                    print(f"\nStages to Skip ({len(stages_to_skip)}):")
                    for stage in stages_to_skip:
                        print(f"  ⏭️  {stage['name']} - {stage.get('reason', 'Unknown')}")
                        
            else:
                print(f"🔄 Replay Results for {args.capsule_name}:{args.run_id}")
                print("=" * 50)
                status = "✅ SUCCESS" if results["success"] else "❌ FAILED"
                print(f"Status: {status}")
                print(f"Replay ID: {results['replay_run_id']}")
                print(f"Stages Replayed: {results['stages_replayed']}")
                
                if results.get("differences"):
                    print(f"\nDifferences from Original ({len(results['differences'])}):")
                    for diff in results["differences"]:
                        print(f"  - {diff['description']}")
                
                if results.get("errors"):
                    print(f"\nErrors ({len(results['errors'])}):")
                    for error in results["errors"]:
                        print(f"  - {error}")
                
                if results["success"]:
                    print(f"\n✅ Replay completed successfully!")
                else:
                    print(f"\n❌ Replay failed - check logs for details")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()