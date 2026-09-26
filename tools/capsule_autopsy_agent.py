#!/usr/bin/env python3
"""
Capsule Autopsy Agent
Post-run parser + model summary that writes to lessons and events
Feeds weekly Ops brief automatically with schema validation
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import re

# Import Huxley modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("paths_config", parent_dir / "global" / "config" / "paths.py")
    paths_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paths_module)
    paths = paths_module.paths
    
    # Import run manifest module
    spec = importlib.util.spec_from_file_location("run_manifest", parent_dir / "global" / "config" / "run_manifest.py")
    manifest_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest_module)
    RunManifest = manifest_module.RunManifest
    
except Exception as e:
    print(f"Error importing Huxley modules: {e}")
    sys.exit(1)


class AutopsyAnalyzer:
    """Analyzes run manifests and creates lessons/events"""
    
    def __init__(self):
        self.schema_validator = EventSchemaValidator()
    
    def analyze_run(self, manifest_path: Path) -> Dict[str, Any]:
        """Analyze a completed run and generate insights"""
        try:
            manifest = RunManifest.load_manifest(manifest_path)
            data = manifest.to_dict()
            
            analysis = {
                "run_id": data["run_id"],
                "capsule": data["capsule"]["name"],
                "analysis_time": datetime.now().isoformat(),
                "status": data["execution"]["status"],
                "insights": [],
                "lessons": [],
                "events": [],
                "recommendations": []
            }
            
            # Analyze execution
            self._analyze_execution_performance(data, analysis)
            self._analyze_failures_and_errors(data, analysis)
            self._analyze_dod_compliance(data, analysis)
            self._extract_lessons_learned(data, analysis)
            self._generate_events(data, analysis)
            
            return analysis
            
        except Exception as e:
            return {
                "error": f"Failed to analyze {manifest_path}: {e}",
                "run_id": "unknown",
                "capsule": "unknown"
            }
    
    def _analyze_execution_performance(self, data: Dict[str, Any], analysis: Dict[str, Any]):
        """Analyze execution performance metrics"""
        execution = data.get("execution", {})
        duration_ms = execution.get("duration_ms", 0)
        
        # Performance thresholds by lane
        if lane == "standard":
            slow_threshold = 30000  # 30 seconds
            very_slow_threshold = 120000  # 2 minutes
        else:  # standard
            slow_threshold = 300000  # 5 minutes  
            very_slow_threshold = 1800000  # 30 minutes
        
        if duration_ms > very_slow_threshold:
            analysis["insights"].append({
                "type": "performance",
                "severity": "high", 
                "message": f"Execution very slow: {duration_ms/1000:.1f}s (expected < {very_slow_threshold/1000}s for {lane})",
            })
        elif duration_ms > slow_threshold:
            analysis["insights"].append({
                "type": "performance",
                "severity": "medium",
                "message": f"Execution slower than expected: {duration_ms/1000:.1f}s (expected < {slow_threshold/1000}s for {lane})",
            })
        
        # Resource usage analysis
        metrics = data.get("outputs", {}).get("metrics", {})
        memory_peak = metrics.get("memory_peak_mb", 0)
        
        if memory_peak > 1000:  # > 1GB
            analysis["insights"].append({
                "type": "resource",
                "severity": "medium",
                "message": f"High memory usage: {memory_peak:.1f}MB",
                "data": {"memory_peak_mb": memory_peak}
            })
    
    def _analyze_failures_and_errors(self, data: Dict[str, Any], analysis: Dict[str, Any]):
        """Analyze failures and extract error patterns"""
        execution = data.get("execution", {})
        status = execution.get("status", "unknown")
        exit_code = execution.get("exit_code", 0)
        
        if status == "failed" or exit_code != 0:
            analysis["insights"].append({
                "type": "failure",
                "severity": "high",
                "message": f"Run failed with exit code {exit_code}",
                "data": {"exit_code": exit_code, "status": status}
            })
            
            # Analyze logs for error patterns
            logs = data.get("outputs", {}).get("logs", {})
            structured_logs = logs.get("structured_logs", [])
            
            error_patterns = []
            for log_entry in structured_logs:
                if log_entry.get("level") in ["ERROR", "CRITICAL"]:
                    error_patterns.append(log_entry.get("message", ""))
            
            if error_patterns:
                # Extract common error types
                common_errors = self._categorize_errors(error_patterns)
                for error_type, count in common_errors.items():
                    analysis["lessons"].append({
                        "type": "error_pattern",
                        "pattern": error_type,
                        "occurrences": count,
                        "recommendation": self._get_error_recommendation(error_type)
                    })
    
    def _analyze_dod_compliance(self, data: Dict[str, Any], analysis: Dict[str, Any]):
        """Analyze Definition of Done compliance"""
        validation = data.get("validation", {})
        dod_checks = validation.get("dod_checks", [])
        
        if not dod_checks:
            analysis["insights"].append({
                "type": "process",
                "severity": "medium",
                "message": "No DoD checks recorded",
                "data": {}
            })
            return
        
        failed_checks = [check for check in dod_checks if check.get("status") != "passed"]
        
        if failed_checks:
            analysis["insights"].append({
                "type": "dod_compliance",
                "severity": "high",
                "message": f"{len(failed_checks)} DoD checks failed",
                "data": {"failed_checks": [check["name"] for check in failed_checks]}
            })
            
            # Create lessons for failed DoD checks
            for check in failed_checks:
                analysis["lessons"].append({
                    "type": "dod_failure",
                    "check_name": check["name"],
                    "failure_reason": check.get("message", ""),
                    "recommendation": f"Review and fix {check['name']} before next run"
                })
        
        # Test results analysis
        test_results = validation.get("test_results", {})
        if test_results:
            total = test_results.get("total", 0)
            failed = test_results.get("failed", 0)
            
            if failed > 0:
                analysis["insights"].append({
                    "type": "testing",
                    "severity": "high",
                    "message": f"{failed}/{total} tests failed",
                    "data": test_results
                })
    
    def _extract_lessons_learned(self, data: Dict[str, Any], analysis: Dict[str, Any]):
        """Extract actionable lessons from the run"""
        capsule_name = data.get("capsule", {}).get("name", "unknown")
        
        # Duration-based lessons
        duration_ms = data.get("execution", {}).get("duration_ms", 0)
        if duration_ms > 0:
            if duration_ms > 600000:  # > 10 minutes
                analysis["lessons"].append({
                    "type": "optimization",
                    "capsule": capsule_name,
                    "lesson": f"Long-running capsule ({duration_ms/60000:.1f} minutes) - consider optimization",
                    "recommendation": "Profile execution, check for inefficient operations, consider parallelization"
                })
        
        # Artifact analysis
        artifacts = data.get("outputs", {}).get("artifacts", [])
        if len(artifacts) == 0:
            analysis["lessons"].append({
                "type": "output",
                "capsule": capsule_name,
                "lesson": "No artifacts produced - verify expected outputs",
                "recommendation": "Ensure all expected outputs are captured as artifacts"
            })
        
        # Resource efficiency lessons
        metrics = data.get("outputs", {}).get("metrics", {})
        memory_peak = metrics.get("memory_peak_mb", 0)
        if memory_peak > 500:
            analysis["lessons"].append({
                "type": "resource_optimization", 
                "capsule": capsule_name,
                "lesson": f"High memory usage: {memory_peak:.1f}MB",
                "recommendation": "Review memory-intensive operations, consider streaming or batching"
            })
    
    def _generate_events(self, data: Dict[str, Any], analysis: Dict[str, Any]):
        """Generate structured events for logging"""
        run_id = data["run_id"]
        capsule_name = data.get("capsule", {}).get("name", "unknown")
        status = data.get("execution", {}).get("status", "unknown")
        
        # Main execution event
        analysis["events"].append({
            "timestamp": datetime.now().isoformat(),
            "capsule": capsule_name,
            "run_id": run_id,
            "stage": "autopsy",
            "level": "info",
            "message": f"Autopsy completed for {capsule_name}/{run_id}",
            "data": {
                "status": status,
                "insights_count": len(analysis["insights"]),
                "lessons_count": len(analysis["lessons"])
            },
            "tags": ["autopsy", "analysis", capsule_name]
        })
        
        # High-severity insights as events
        for insight in analysis["insights"]:
            if insight.get("severity") == "high":
                analysis["events"].append({
                    "timestamp": datetime.now().isoformat(),
                    "capsule": capsule_name,
                    "run_id": run_id,
                    "stage": "autopsy",
                    "level": "warning",
                    "message": insight["message"],
                    "data": insight.get("data", {}),
                    "tags": ["autopsy", insight["type"], capsule_name]
                })
    
    def _categorize_errors(self, error_messages: List[str]) -> Dict[str, int]:
        """Categorize error messages into common patterns"""
        categories = {}
        
        patterns = {
            "connection_error": [r"connection", r"timeout", r"network", r"unreachable"],
            "file_not_found": [r"no such file", r"file not found", r"does not exist"],
            "permission_error": [r"permission denied", r"access denied", r"forbidden"],
            "import_error": [r"import error", r"module not found", r"no module named"],
            "syntax_error": [r"syntax error", r"invalid syntax"],
            "type_error": [r"type error", r"unexpected type"],
            "value_error": [r"value error", r"invalid value"],
            "json_error": [r"json", r"invalid json", r"decode error"],
            "api_error": [r"api", r"http", r"status code", r"bad request"]
        }
        
        for error_msg in error_messages:
            error_lower = error_msg.lower()
            categorized = False
            
            for category, patterns_list in patterns.items():
                if any(re.search(pattern, error_lower) for pattern in patterns_list):
                    categories[category] = categories.get(category, 0) + 1
                    categorized = True
                    break
            
            if not categorized:
                categories["other"] = categories.get("other", 0) + 1
        
        return categories
    
    def _get_error_recommendation(self, error_type: str) -> str:
        """Get recommendation based on error type"""
        recommendations = {
            "connection_error": "Check network connectivity, verify endpoints, implement retries",
            "file_not_found": "Verify file paths, ensure inputs exist, add path validation", 
            "permission_error": "Check file permissions, verify access rights",
            "import_error": "Install missing dependencies, verify import paths",
            "syntax_error": "Review code syntax, run linter",
            "type_error": "Add type checking, validate input types",
            "value_error": "Add input validation, handle edge cases",
            "json_error": "Validate JSON format, add error handling for malformed data",
            "api_error": "Check API status, verify request format, handle rate limits",
            "other": "Review error details and add appropriate error handling"
        }
        
        return recommendations.get(error_type, "Review error and implement appropriate fixes")


class EventSchemaValidator:
    """Validates events against Huxley schema"""
    
    def __init__(self):
        self.required_fields = ["timestamp", "capsule", "run_id", "stage", "level", "message", "data", "tags"]
        self.valid_levels = ["debug", "info", "warning", "error", "critical"]
    
    def validate_event(self, event: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate event against schema"""
        errors = []
        
        # Check required fields
        for field in self.required_fields:
            if field not in event:
                errors.append(f"Missing required field: {field}")
        
        # Validate level
        if "level" in event and event["level"] not in self.valid_levels:
            errors.append(f"Invalid level: {event['level']}. Must be one of {self.valid_levels}")
        
        # Validate timestamp format
        if "timestamp" in event:
            try:
                datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
            except ValueError:
                errors.append("Invalid timestamp format. Must be ISO 8601")
        
        # Validate data is dict
        if "data" in event and not isinstance(event["data"], dict):
            errors.append("Data field must be an object/dict")
        
        # Validate tags is array
        if "tags" in event and not isinstance(event["tags"], list):
            errors.append("Tags field must be an array")
        
        return len(errors) == 0, errors


class AutopsyProcessor:
    """Processes autopsy results and integrates with Huxleys"""
    
    def __init__(self):
        self.analyzer = AutopsyAnalyzer()
        self.processed_runs = set()
        self._load_processed_runs()
    
    def _load_processed_runs(self):
        """Load list of already processed runs"""
        processed_file = paths.registry / "autopsy_processed.json"
        if processed_file.exists():
            try:
                with open(processed_file) as f:
                    data = json.load(f)
                    self.processed_runs = set(data.get("processed_runs", []))
            except Exception:
                pass
    
    def _save_processed_runs(self):
        """Save list of processed runs"""
        processed_file = paths.registry / "autopsy_processed.json"
        processed_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(processed_file, 'w') as f:
            json.dump({
                "last_update": datetime.now().isoformat(),
                "processed_runs": list(self.processed_runs)
            }, f, indent=2)
    
    def find_unprocessed_runs(self, max_age_days: int = 7) -> List[Path]:
        """Find run manifests that haven't been processed"""
        unprocessed = []
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        
        # Scan all capsules for run manifests
        for capsule_dir in paths.capsules.iterdir():
            if not capsule_dir.is_dir():
                continue
            
            runs_dir = capsule_dir / "runs"
            if not runs_dir.exists():
                continue
            
            for run_dir in runs_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                
                manifest_path = run_dir / "manifest.json"
                if not manifest_path.exists():
                    continue
                
                # Check if already processed
                run_key = f"{capsule_dir.name}:{run_dir.name}"
                if run_key in self.processed_runs:
                    continue
                
                # Check age
                try:
                    mod_time = datetime.fromtimestamp(manifest_path.stat().st_mtime)
                    if mod_time < cutoff_time:
                        continue
                except Exception:
                    continue
                
                unprocessed.append(manifest_path)
        
        return unprocessed
    
    def process_run(self, manifest_path: Path) -> Dict[str, Any]:
        """Process a single run manifest"""
        analysis = self.analyzer.analyze_run(manifest_path)
        
        if "error" in analysis:
            return analysis
        
        # Write lessons to RAG system
        self._write_lessons_to_rag(analysis)
        
        # Write events to events log
        self._write_events_to_log(analysis)
        
        # Mark as processed
        capsule_name = analysis["capsule"]
        run_id = analysis["run_id"]
        self.processed_runs.add(f"{capsule_name}:{run_id}")
        
        return analysis
    
    def _write_lessons_to_rag(self, analysis: Dict[str, Any]):
        """Write lessons to RAG system"""
        lessons = analysis.get("lessons", [])
        if not lessons:
            return
        
        rag_lessons = []
        for lesson in lessons:
            rag_lesson = {
                "id": f"lesson_{analysis['run_id']}_{hashlib.md5(lesson['lesson'].encode()).hexdigest()[:8]}",
                "body": f"**Lesson from {analysis['capsule']}:** {lesson['lesson']}\n\n**Recommendation:** {lesson['recommendation']}",
                "meta": {
                    "capsule_id": analysis["capsule"],
                    "run_id": analysis["run_id"],
                    "lesson_type": lesson["type"],
                    "date": datetime.now().isoformat(),
                    "tags": ["autopsy", "lesson", lesson["type"]],
                    "version": "1.0",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            }
            rag_lessons.append(rag_lesson)
        
        # Save lessons for manual ingestion (could automate with RAG API)
        lessons_file = paths.rag / "assets" / "lessons" / f"autopsy_{analysis['run_id']}.json"
        lessons_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(lessons_file, 'w') as f:
            json.dump(rag_lessons, f, indent=2)
    
    def _write_events_to_log(self, analysis: Dict[str, Any]):
        """Write events to Huxley events log"""
        events = analysis.get("events", [])
        if not events:
            return
        
        events_log = paths.events_log
        events_log.parent.mkdir(parents=True, exist_ok=True)
        
        with open(events_log, 'a') as f:
            for event in events:
                # Validate event before writing
                validator = EventSchemaValidator()
                is_valid, errors = validator.validate_event(event)
                
                if is_valid:
                    f.write(json.dumps(event) + '\n')
                else:
                    # Write error event instead
                    error_event = {
                        "timestamp": datetime.now().isoformat(),
                        "capsule": analysis["capsule"],
                        "run_id": analysis["run_id"],
                        "stage": "autopsy",
                        "level": "error",
                        "message": f"Invalid event schema: {', '.join(errors)}",
                        "data": {"original_event": event, "validation_errors": errors},
                        "tags": ["autopsy", "schema_error"]
                    }
                    f.write(json.dumps(error_event) + '\n')
    
    def run_autopsy_batch(self, max_age_days: int = 7) -> Dict[str, Any]:
        """Run autopsy on all unprocessed runs"""
        unprocessed = self.find_unprocessed_runs(max_age_days)
        
        results = {
            "processed_count": 0,
            "error_count": 0,
            "lessons_generated": 0,
            "events_generated": 0,
            "errors": []
        }
        
        print(f"Found {len(unprocessed)} unprocessed runs")
        
        for manifest_path in unprocessed:
            try:
                print(f"Processing: {manifest_path}")
                analysis = self.process_run(manifest_path)
                
                if "error" in analysis:
                    results["error_count"] += 1
                    results["errors"].append(analysis["error"])
                else:
                    results["processed_count"] += 1
                    results["lessons_generated"] += len(analysis.get("lessons", []))
                    results["events_generated"] += len(analysis.get("events", []))
                
            except Exception as e:
                results["error_count"] += 1
                results["errors"].append(f"Failed to process {manifest_path}: {e}")
        
        # Save processed runs
        self._save_processed_runs()
        
        return results


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Huxley Capsule Autopsy Agent")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Batch processing
    batch_parser = subparsers.add_parser("batch", help="Process all unprocessed runs")
    batch_parser.add_argument("--max-age", type=int, default=7, help="Max age in days for runs to process")
    
    # Process specific run
    run_parser = subparsers.add_parser("run", help="Process specific run")
    run_parser.add_argument("manifest_path", help="Path to run manifest")
    
    # List unprocessed
    list_parser = subparsers.add_parser("list", help="List unprocessed runs")
    list_parser.add_argument("--max-age", type=int, default=7, help="Max age in days")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    processor = AutopsyProcessor()
    
    if args.command == "batch":
        results = processor.run_autopsy_batch(args.max_age)
        
        print(f"\nBatch Autopsy Results:")
        print(f"Processed: {results['processed_count']}")
        print(f"Errors: {results['error_count']}")
        print(f"Lessons generated: {results['lessons_generated']}")
        print(f"Events generated: {results['events_generated']}")
        
        if results["errors"]:
            print(f"\nErrors:")
            for error in results["errors"][:5]:
                print(f"  - {error}")
    
    elif args.command == "run":
        manifest_path = Path(args.manifest_path)
        if not manifest_path.exists():
            print(f"Manifest not found: {manifest_path}")
            return
        
        analysis = processor.process_run(manifest_path)
        
        if "error" in analysis:
            print(f"Error: {analysis['error']}")
        else:
            print(f"Autopsy completed for {analysis['capsule']}/{analysis['run_id']}")
            print(f"Insights: {len(analysis['insights'])}")
            print(f"Lessons: {len(analysis['lessons'])}")
            print(f"Events: {len(analysis['events'])}")
    
    elif args.command == "list":
        unprocessed = processor.find_unprocessed_runs(args.max_age)
        
        print(f"Found {len(unprocessed)} unprocessed runs:")
        for manifest_path in unprocessed[:10]:
            rel_path = manifest_path.relative_to(paths.base)
            print(f"  {rel_path}")
        
        if len(unprocessed) > 10:
            print(f"  ... and {len(unprocessed) - 10} more")


if __name__ == "__main__":
    main()