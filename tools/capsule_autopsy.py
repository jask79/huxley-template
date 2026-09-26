#!/usr/bin/env python3
"""
Capsule Autopsy Agent - Post-run analysis that extracts lessons and stores in RAG
Lane-aware analysis depth with failure pattern recognition and success amplification
"""

import os
import sys
import json
import pathlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

# Add Huxley tools to path
CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")
sys.path.append(str(CATALYST_ROOT / "tools"))
sys.path.append(str(CATALYST_ROOT / "capsules" / "example-ops-capsule" / "src"))

try:
    from run_manifest_schema import RunManifest, RunStage
    from events_logger import log_event
    from rag_client import RAGClient
except ImportError as e:
    print(f"Warning: Could not import Huxley tools: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class AutopsyAnalysis:
    """Results of capsule run autopsy"""
    run_id: str
    capsule_name: str
    lane: str
    analysis_depth: str  # 'basic', 'standard', 'comprehensive'
    
    # Core findings
    what_worked: List[str]
    what_failed: List[str] 
    what_to_tweak: List[str]
    
    # Patterns
    failure_patterns: List[Dict[str, Any]]
    success_patterns: List[Dict[str, Any]]
    
    # Insights
    root_causes: List[str]
    recommendations: List[str]
    lessons_learned: List[str]
    
    # Metrics
    duration_analysis: Dict[str, Any]
    error_categorization: Dict[str, Any]
    
    # Context
    related_runs: List[str]
    similar_failures: List[str]
    timestamp: str

class CapsuleAutopsyAgent:
    """Performs post-run analysis and extracts actionable lessons"""
    
    def __init__(self):
        self.catalyst_root = CATALYST_ROOT
        self.rag_client = RAGClient()
        self.registry_dir = self.catalyst_root / "registry"
        
        # Lane-specific analysis depths
        self.analysis_depths = {
            "fast": "basic",
            "deep": "comprehensive",
            "both": "standard"
        }
    
    def perform_autopsy(self, capsule_name: str, run_id: str = None) -> AutopsyAnalysis:
        """Perform complete autopsy analysis of a capsule run"""
        logger.info(f"Starting autopsy for capsule: {capsule_name}")
        
        # Find the run to analyze
        run_manifest = self._load_run_manifest(capsule_name, run_id)
        if not run_manifest:
            raise ValueError(f"Could not find run manifest for {capsule_name}:{run_id}")
        
        # Determine analysis depth based on lane
        analysis_depth = self.analysis_depths.get(run_manifest.lane.lower(), "standard")
        
        # Gather run artifacts
        run_data = self._gather_run_artifacts(capsule_name, run_manifest)
        
        # Perform analysis based on depth
        if analysis_depth == "basic":
            analysis = self._basic_analysis(run_manifest, run_data)
        elif analysis_depth == "comprehensive":
            analysis = self._comprehensive_analysis(run_manifest, run_data)
        else:
            analysis = self._standard_analysis(run_manifest, run_data)
        
        # Store results in RAG
        self._store_autopsy_results(analysis)
        
        # Log to events
        self._log_autopsy_event(analysis)
        
        logger.info(f"Autopsy completed for {capsule_name}:{run_manifest.run_id}")
        return analysis
    
    def _load_run_manifest(self, capsule_name: str, run_id: str = None) -> Optional[RunManifest]:
        """Load run manifest, using latest if run_id not specified"""
        capsule_dir = self.catalyst_root / "capsules" / capsule_name
        runs_dir = capsule_dir / "runs"
        
        if not runs_dir.exists():
            logger.warning(f"No runs directory found for {capsule_name}")
            return None
        
        if run_id:
            # Load specific run
            manifest_file = runs_dir / run_id / "manifest.json"
            if manifest_file.exists():
                return RunManifest.load(manifest_file)
        else:
            # Find latest run
            run_dirs = [d for d in runs_dir.iterdir() if d.is_dir()]
            if not run_dirs:
                return None
            
            latest_run = max(run_dirs, key=lambda x: x.stat().st_mtime)
            manifest_file = latest_run / "manifest.json"
            if manifest_file.exists():
                return RunManifest.load(manifest_file)
        
        return None
    
    def _gather_run_artifacts(self, capsule_name: str, run_manifest: RunManifest) -> Dict[str, Any]:
        """Gather all available run artifacts for analysis"""
        capsule_dir = self.catalyst_root / "capsules" / capsule_name
        run_dir = capsule_dir / "runs" / run_manifest.run_id
        
        artifacts = {
            "logs": [],
            "outputs": [],
            "errors": [],
            "performance_data": {},
            "dependencies": run_manifest.dependencies,
            "stages": run_manifest.stages
        }
        
        # Collect log files
        if run_dir.exists():
            for log_file in run_dir.glob("*.log"):
                try:
                    with open(log_file, 'r') as f:
                        artifacts["logs"].append({
                            "file": str(log_file.name),
                            "content": f.read(),
                            "size": log_file.stat().st_size
                        })
                except Exception as e:
                    logger.warning(f"Could not read log file {log_file}: {e}")
        
        # Collect outputs
        for output in run_manifest.outputs:
            if pathlib.Path(output.path).exists():
                artifacts["outputs"].append(output)
        
        # Extract error information from stages
        for stage in run_manifest.stages:
            if stage.status == "failed" and stage.error_message:
                artifacts["errors"].append({
                    "stage": stage.name,
                    "error": stage.error_message,
                    "exit_code": stage.exit_code,
                    "duration_ms": stage.duration_ms
                })
        
        return artifacts
    
    def _basic_analysis(self, run_manifest: RunManifest, run_data: Dict[str, Any]) -> AutopsyAnalysis:
        """Basic analysis for standard runs"""
        what_worked = []
        what_failed = []
        what_to_tweak = []
        
        # Simple pass/fail analysis
        if run_manifest.success:
            what_worked.append("Run completed successfully")
            if run_manifest.total_duration_ms:
                what_worked.append(f"Completed in {run_manifest.total_duration_ms}ms")
        else:
            what_failed.append(f"Run failed with exit code {run_manifest.exit_code}")
            if run_manifest.error_summary:
                what_failed.append(run_manifest.error_summary)
        
        # Quick stage analysis
        for stage in run_manifest.stages:
            if stage.status == "failed":
                what_failed.append(f"Stage '{stage.name}' failed")
            elif stage.status == "success":
                what_worked.append(f"Stage '{stage.name}' succeeded")
        
        # Simple recommendations
        recommendations = []
        if what_failed:
            recommendations.append("Review failed stages for quick fixes")
        
        return AutopsyAnalysis(
            run_id=run_manifest.run_id,
            capsule_name=run_manifest.capsule_name,
            lane=run_manifest.lane,
            analysis_depth="basic",
            what_worked=what_worked,
            what_failed=what_failed,
            what_to_tweak=what_to_tweak,
            failure_patterns=[],
            success_patterns=[],
            root_causes=[],
            recommendations=recommendations,
            lessons_learned=[],
            duration_analysis={},
            error_categorization={},
            related_runs=[],
            similar_failures=[],
            timestamp=datetime.now().isoformat()
        )
    
    def _standard_analysis(self, run_manifest: RunManifest, run_data: Dict[str, Any]) -> AutopsyAnalysis:
        """Standard analysis for mixed lane runs"""
        # Start with basic analysis
        basic = self._basic_analysis(run_manifest, run_data)
        
        # Add pattern recognition
        failure_patterns = self._identify_failure_patterns(run_data)
        success_patterns = self._identify_success_patterns(run_manifest, run_data)
        
        # Duration analysis
        duration_analysis = self._analyze_durations(run_manifest)
        
        # Enhanced recommendations
        recommendations = basic.recommendations.copy()
        if failure_patterns:
            recommendations.append("Similar failure patterns detected - check related runs")
        if duration_analysis.get("slow_stages"):
            recommendations.append("Optimize slow stages for better performance")
        
        basic.failure_patterns = failure_patterns
        basic.success_patterns = success_patterns
        basic.duration_analysis = duration_analysis
        basic.recommendations = recommendations
        basic.analysis_depth = "standard"
        
        return basic
    
    def _comprehensive_analysis(self, run_manifest: RunManifest, run_data: Dict[str, Any]) -> AutopsyAnalysis:
        """Comprehensive analysis for standard runs"""
        # Start with standard analysis
        standard = self._standard_analysis(run_manifest, run_data)
        
        # Add deep insights
        root_causes = self._identify_root_causes(run_data)
        lessons_learned = self._extract_lessons_learned(run_manifest, run_data)
        error_categorization = self._categorize_errors(run_data)
        related_runs = self._find_related_runs(run_manifest)
        similar_failures = self._find_similar_failures(run_manifest, run_data)
        
        # Enhanced what_to_tweak based on deep analysis
        what_to_tweak = standard.what_to_tweak.copy()
        for root_cause in root_causes:
            if "configuration" in root_cause.lower():
                what_to_tweak.append("Review configuration settings")
            elif "dependency" in root_cause.lower():
                what_to_tweak.append("Check dependency versions and availability")
            elif "resource" in root_cause.lower():
                what_to_tweak.append("Monitor resource usage and limits")
        
        standard.root_causes = root_causes
        standard.lessons_learned = lessons_learned
        standard.error_categorization = error_categorization
        standard.related_runs = related_runs
        standard.similar_failures = similar_failures
        standard.what_to_tweak = what_to_tweak
        standard.analysis_depth = "comprehensive"
        
        return standard
    
    def _identify_failure_patterns(self, run_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify common failure patterns"""
        patterns = []
        errors = run_data.get("errors", [])
        
        # Group errors by type
        error_types = {}
        for error in errors:
            error_msg = error.get("error", "").lower()
            
            # Classify error types
            if "timeout" in error_msg:
                error_types.setdefault("timeout", []).append(error)
            elif "permission" in error_msg or "access denied" in error_msg:
                error_types.setdefault("permissions", []).append(error)
            elif "not found" in error_msg or "missing" in error_msg:
                error_types.setdefault("missing_resource", []).append(error)
            elif "connection" in error_msg or "network" in error_msg:
                error_types.setdefault("network", []).append(error)
            else:
                error_types.setdefault("other", []).append(error)
        
        # Create patterns
        for error_type, occurrences in error_types.items():
            if len(occurrences) > 0:
                patterns.append({
                    "type": error_type,
                    "count": len(occurrences),
                    "stages": [e.get("stage") for e in occurrences],
                    "description": f"{len(occurrences)} {error_type} errors detected"
                })
        
        return patterns
    
    def _identify_success_patterns(self, run_manifest: RunManifest, run_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify what works well for amplification"""
        patterns = []
        
        # Fast completion pattern
        if run_manifest.total_duration_ms and run_manifest.total_duration_ms < 30000:  # Under 30s
            patterns.append({
                "type": "fast_execution",
                "value": run_manifest.total_duration_ms,
                "description": f"Fast execution in {run_manifest.total_duration_ms}ms"
            })
        
        # All stages successful pattern
        successful_stages = [s for s in run_manifest.stages if s.status == "success"]
        if len(successful_stages) == len(run_manifest.stages) and len(successful_stages) > 1:
            patterns.append({
                "type": "clean_execution",
                "value": len(successful_stages),
                "description": f"All {len(successful_stages)} stages completed successfully"
            })
        
        # Dependency reliability
        available_deps = [d for d in run_manifest.dependencies if d.status == "available"]
        if len(available_deps) > 0:
            patterns.append({
                "type": "dependency_reliability",
                "value": len(available_deps),
                "description": f"{len(available_deps)} dependencies available and working"
            })
        
        return patterns
    
    def _analyze_durations(self, run_manifest: RunManifest) -> Dict[str, Any]:
        """Analyze stage and total durations"""
        analysis = {
            "total_duration_ms": run_manifest.total_duration_ms,
            "stage_count": len(run_manifest.stages),
            "slow_stages": [],
            "fast_stages": [],
            "avg_stage_duration": 0
        }
        
        stage_durations = [s.duration_ms for s in run_manifest.stages if s.duration_ms]
        if stage_durations:
            avg_duration = sum(stage_durations) / len(stage_durations)
            analysis["avg_stage_duration"] = avg_duration
            
            # Identify outliers
            for stage in run_manifest.stages:
                if stage.duration_ms:
                    if stage.duration_ms > avg_duration * 2:  # 2x slower than average
                        analysis["slow_stages"].append({
                            "name": stage.name,
                            "duration_ms": stage.duration_ms
                        })
                    elif stage.duration_ms < avg_duration * 0.5:  # 2x faster than average
                        analysis["fast_stages"].append({
                            "name": stage.name,
                            "duration_ms": stage.duration_ms
                        })
        
        return analysis
    
    def _identify_root_causes(self, run_data: Dict[str, Any]) -> List[str]:
        """Identify root causes of failures"""
        root_causes = []
        errors = run_data.get("errors", [])
        logs = run_data.get("logs", [])
        
        # Analyze error messages for root causes
        for error in errors:
            error_msg = error.get("error", "").lower()
            
            if "configuration" in error_msg or "config" in error_msg:
                root_causes.append("Configuration issue detected")
            elif "dependency" in error_msg or "import" in error_msg:
                root_causes.append("Dependency resolution failure")
            elif "memory" in error_msg or "resource" in error_msg:
                root_causes.append("Resource exhaustion")
            elif "version" in error_msg or "compatibility" in error_msg:
                root_causes.append("Version compatibility issue")
        
        # Analyze logs for additional context
        for log in logs:
            content = log.get("content", "").lower()
            if "out of memory" in content:
                root_causes.append("Memory exhaustion")
            elif "disk full" in content or "no space" in content:
                root_causes.append("Disk space exhaustion")
        
        return list(set(root_causes))  # Remove duplicates
    
    def _extract_lessons_learned(self, run_manifest: RunManifest, run_data: Dict[str, Any]) -> List[str]:
        """Extract actionable lessons learned"""
        lessons = []
        
        # Success lessons
        if run_manifest.success:
            if run_manifest.total_duration_ms and run_manifest.total_duration_ms < 60000:
                lessons.append("Efficient execution pattern - preserve stage ordering and dependencies")
            
            successful_deps = [d for d in run_manifest.dependencies if d.status == "available"]
            if successful_deps:
                lessons.append(f"Reliable dependencies: {', '.join(d.name for d in successful_deps)}")
        
        # Failure lessons
        else:
            failure_stages = [s for s in run_manifest.stages if s.status == "failed"]
            if failure_stages:
                lessons.append(f"Critical failure points: {', '.join(s.name for s in failure_stages)}")
            
            if run_manifest.error_summary:
                lessons.append(f"Error pattern to avoid: {run_manifest.error_summary}")
        
        # Performance lessons
        slow_stages = [s for s in run_manifest.stages if s.duration_ms and s.duration_ms > 30000]
        if slow_stages:
            lessons.append(f"Performance bottlenecks in: {', '.join(s.name for s in slow_stages)}")
        
        return lessons
    
    def _categorize_errors(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        """Categorize errors for pattern analysis"""
        categorization = {
            "infrastructure": 0,
            "application": 0,
            "configuration": 0,
            "dependency": 0,
            "user": 0
        }
        
        errors = run_data.get("errors", [])
        for error in errors:
            error_msg = error.get("error", "").lower()
            
            if any(word in error_msg for word in ["network", "connection", "timeout", "dns"]):
                categorization["infrastructure"] += 1
            elif any(word in error_msg for word in ["import", "module", "package", "dependency"]):
                categorization["dependency"] += 1
            elif any(word in error_msg for word in ["config", "setting", "parameter"]):
                categorization["configuration"] += 1
            elif any(word in error_msg for word in ["permission", "access", "auth"]):
                categorization["user"] += 1
            else:
                categorization["application"] += 1
        
        return categorization
    
    def _find_related_runs(self, run_manifest: RunManifest) -> List[str]:
        """Find related runs from the same capsule"""
        capsule_dir = self.catalyst_root / "capsules" / run_manifest.capsule_name / "runs"
        related_runs = []
        
        if capsule_dir.exists():
            for run_dir in capsule_dir.iterdir():
                if run_dir.is_dir() and run_dir.name != run_manifest.run_id:
                    related_runs.append(run_dir.name)
        
        # Return most recent 5
        return related_runs[-5:] if len(related_runs) > 5 else related_runs
    
    def _find_similar_failures(self, run_manifest: RunManifest, run_data: Dict[str, Any]) -> List[str]:
        """Find similar failures across the system"""
        # This would query RAG for similar error patterns
        # For now, return placeholder
        return []
    
    def _store_autopsy_results(self, analysis: AutopsyAnalysis):
        """Store autopsy results in RAG system"""
        if not self.rag_client.is_available():
            logger.warning("RAG client not available, skipping storage")
            return
        
        # Create lesson from autopsy
        lesson_id = f"autopsy-{analysis.run_id}"
        lesson_body = self._format_lesson_body(analysis)
        
        lesson_data = {
            "id": lesson_id,
            "body": lesson_body,
            "meta": {
                "version": "1.0",
                "tags": ["autopsy", "post-run", analysis.capsule_name],
                "capsule_compatibility": [analysis.capsule_name],
                "builder_context": {
                    "source": "capsule_autopsy",
                    "run_id": analysis.run_id,
                    "analysis_depth": analysis.analysis_depth
                },
                "capsule_id": analysis.capsule_name,
                "step": "post_run_analysis",
                "failure_type": "comprehensive" if analysis.what_failed else "none",
                "fix_applied": "; ".join(analysis.recommendations[:3]),
                "outcome": "success" if not analysis.what_failed else "failure_analysis",
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        }
        
        try:
            success = self.rag_client._request("POST", "/builder/lessons/upsert", json=[lesson_data])
            if success.status_code == 200:
                logger.info(f"Stored autopsy lesson: {lesson_id}")
            else:
                logger.warning(f"Failed to store autopsy lesson: HTTP {success.status_code}")
        except Exception as e:
            logger.error(f"Error storing autopsy in RAG: {e}")
    
    def _format_lesson_body(self, analysis: AutopsyAnalysis) -> str:
        """Format autopsy analysis as lesson body"""
        body = f"# Autopsy: {analysis.capsule_name} - {analysis.run_id}\n\n"
        body += f"**Lane:** {analysis.lane} | **Analysis Depth:** {analysis.analysis_depth}\n\n"
        
        if analysis.what_worked:
            body += "## What Worked ✅\n"
            for item in analysis.what_worked:
                body += f"- {item}\n"
            body += "\n"
        
        if analysis.what_failed:
            body += "## What Failed ❌\n"
            for item in analysis.what_failed:
                body += f"- {item}\n"
            body += "\n"
        
        if analysis.what_to_tweak:
            body += "## What to Tweak 🔧\n"
            for item in analysis.what_to_tweak:
                body += f"- {item}\n"
            body += "\n"
        
        if analysis.lessons_learned:
            body += "## Lessons Learned 📚\n"
            for lesson in analysis.lessons_learned:
                body += f"- {lesson}\n"
            body += "\n"
        
        if analysis.recommendations:
            body += "## Recommendations 💡\n"
            for rec in analysis.recommendations:
                body += f"- {rec}\n"
            body += "\n"
        
        if analysis.failure_patterns:
            body += "## Failure Patterns 📊\n"
            for pattern in analysis.failure_patterns:
                body += f"- {pattern['description']}\n"
            body += "\n"
        
        if analysis.success_patterns:
            body += "## Success Patterns 🎯\n"
            for pattern in analysis.success_patterns:
                body += f"- {pattern['description']}\n"
            body += "\n"
        
        return body
    
    def _log_autopsy_event(self, analysis: AutopsyAnalysis):
        """Log autopsy completion to events system"""
        try:
            log_event(
                stage="post_run_autopsy",
                level="INFO",
                message=f"Autopsy completed for {analysis.capsule_name}:{analysis.run_id}",
                capsule=analysis.capsule_name,
                data={
                    "run_id": analysis.run_id,
                    "analysis_depth": analysis.analysis_depth,
                    "success_count": len(analysis.what_worked),
                    "failure_count": len(analysis.what_failed),
                    "lessons_count": len(analysis.lessons_learned)
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log autopsy event: {e}")

def main():
    """CLI interface for capsule autopsy"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Capsule Autopsy Agent")
    parser.add_argument("capsule_name", help="Name of capsule to analyze")
    parser.add_argument("--run-id", "-r", help="Specific run ID to analyze (default: latest)")
    parser.add_argument("--output", "-o", help="Output file for autopsy results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    try:
        agent = CapsuleAutopsyAgent()
        analysis = agent.perform_autopsy(args.capsule_name, args.run_id)
        
        if args.json:
            result = asdict(analysis)
            output = json.dumps(result, indent=2, default=str)
        else:
            output = f"Autopsy Results for {analysis.capsule_name}:{analysis.run_id}\n"
            output += "=" * 50 + "\n\n"
            output += f"Lane: {analysis.lane} | Depth: {analysis.analysis_depth}\n\n"
            
            if analysis.what_worked:
                output += "What Worked:\n"
                for item in analysis.what_worked:
                    output += f"  ✅ {item}\n"
                output += "\n"
            
            if analysis.what_failed:
                output += "What Failed:\n"
                for item in analysis.what_failed:
                    output += f"  ❌ {item}\n"
                output += "\n"
            
            if analysis.recommendations:
                output += "Recommendations:\n"
                for rec in analysis.recommendations:
                    output += f"  💡 {rec}\n"
                output += "\n"
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Autopsy results saved to {args.output}")
        else:
            print(output)
            
    except Exception as e:
        print(f"Autopsy failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()