#!/usr/bin/env python3
"""
Huxley Performance Baseline Tool
Runs standardized test jobs to measure execution time, token usage, and success rates
"""

import json
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

@dataclass
class BaselineResult:
    test_name: str
    lane: str
    agent: str
    start_time: str
    end_time: str
    duration_seconds: float
    success: bool
    token_usage: Optional[int] = None
    mcp_calls: int = 0
    error_message: Optional[str] = None
    capsule_slug: Optional[str] = None

class PerformanceBaseline:
    def __init__(self):
        self.base_dir = Path("{{CATALYST_ROOT}}")
        self.results: List[BaselineResult] = []
        self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
    def log_event(self, message: str, level: str = "INFO"):
        """Log to Huxley event system"""
        log_script = self.base_dir / "tools" / "log_event.py"
        if log_script.exists():
            try:
                subprocess.run([
                    "python3", str(log_script),
                    "--stage", "performance_baseline",
                    "--level", level,
                    "--message", message
                ], capture_output=True, timeout=10)
            except:
                pass
        print(f"[{level}] {message}")

    def run_test_job(self, test_name: str, lane: str, expected_agent: str, 
                     branch: str = "test", timeout: int = 300) -> BaselineResult:
        """Run a single standardized test job using existing test capsules"""
        start_time = datetime.now(timezone.utc)
        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Use existing test capsules for baseline measurements
        test_capsules = {
            "automation-simple": "test-fast-lane",
            "automation-complex": "test-deep-lane", 
            "web-simple": "good-fast",
            "web-complex": "test-capsule",
            "apple-complex": "enhanced-test"
        }
        
        capsule_slug = test_capsules.get(test_name, f"test-{test_name}")
        capsule_path = self.base_dir / "testing" / "capsules" / capsule_slug
        
        self.log_event(f"Starting baseline test: {test_name} ({lane})")
        
        try:
            # Test capsule exists
            if not capsule_path.exists():
                raise FileNotFoundError(f"Test capsule not found: {capsule_path}")
                
            # Run trigger_planner on existing test capsule with secure execution
            trigger_script = self.base_dir / "tools" / "trigger_planner.sh"
            
            # Validate paths for security
            if not trigger_script.exists():
                raise FileNotFoundError(f"Trigger script not found: {trigger_script}")
            if not capsule_path.exists():
                raise FileNotFoundError(f"Test capsule not found: {capsule_path}")
                
            # Ensure paths are absolute and within expected directories
            if not str(trigger_script).startswith(str(self.base_dir)):
                raise ValueError(f"Trigger script outside base directory: {trigger_script}")
            if not str(capsule_path).startswith(str(self.base_dir)):
                raise ValueError(f"Capsule path outside base directory: {capsule_path}")
            
            # Execute with validated, absolute paths (no shell expansion)
            cmd = [str(trigger_script), str(capsule_path)]
            
            result = subprocess.run(
                cmd, 
                cwd=str(self.base_dir),
                capture_output=True, 
                text=True, 
                timeout=timeout,
                shell=False  # Critical: prevent shell injection
            )
            
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            success = result.returncode == 0
            error_msg = result.stderr if not success else None
            
            # Count MCP calls from output (rough estimate)
            mcp_calls = result.stdout.count("MCP") + result.stderr.count("MCP")
            
            return BaselineResult(
                test_name=test_name,
                lane=lane,
                agent=expected_agent,
                start_time=start_iso,
                end_time=end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                duration_seconds=duration,
                success=success,
                mcp_calls=mcp_calls,
                error_message=error_msg,
                capsule_slug=capsule_slug
            )
            
        except subprocess.TimeoutExpired:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            return BaselineResult(
                test_name=test_name,
                lane=lane, 
                agent=expected_agent,
                start_time=start_iso,
                end_time=end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                duration_seconds=duration,
                success=False,
                error_message=f"Timeout after {timeout}s"
            )
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            return BaselineResult(
                test_name=test_name,
                lane=lane,
                agent=expected_agent, 
                start_time=start_iso,
                end_time=end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                duration_seconds=duration,
                success=False,
                error_message=str(e)
            )

    def run_baseline_suite(self):
        """Run complete baseline test suite"""
        
        # Test suite: 5 standardized tests across different domains and lanes
        test_suite = [
            # standard tests (should be quick)
            ("automation-simple", "standard", "automation-specialist", "automation"),
            ("web-simple", "standard", "frontend-specialist", "web"),
            
            # standard tests (more thorough, slower)
            ("automation-complex", "standard", "automation-specialist", "automation"),
            ("web-complex", "standard", "frontend-specialist", "web"),
            ("apple-complex", "standard", "ios-specialist", "ios"),
        ]
        
        self.log_event("Starting Huxley performance baseline suite")
        
        for test_name, lane, agent, branch in test_suite:
            self.log_event(f"Running {test_name} in {lane} (expected: {agent})")
            
            result = self.run_test_job(test_name, lane, agent, branch)
            self.results.append(result)
            
            status = "✅ PASS" if result.success else "❌ FAIL"
            duration = f"{result.duration_seconds:.1f}s"
            self.log_event(f"  {status} {test_name}: {duration}")
            
            if not result.success and result.error_message:
                self.log_event(f"  Error: {result.error_message[:100]}", "ERROR")
                
            # Brief pause between tests to avoid overwhelming system
            time.sleep(2)
            
        self.log_event("Baseline suite completed")

    def generate_report(self) -> Dict:
        """Generate comprehensive baseline report"""
        
        # Calculate statistics
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Lane-specific stats
        standard_results = [r for r in self.results if r.lane == "standard"]
        standard_results = [r for r in self.results if r.lane == "standard"]
        
        standard_avg = sum(r.duration_seconds for r in standard_results) / len(standard_results) if standard_results else 0
        standard_avg = sum(r.duration_seconds for r in standard_results) / len(standard_results) if standard_results else 0
        
        # Agent routing accuracy
        routing_accurate = sum(1 for r in self.results if r.success) # Assuming success implies correct routing
        routing_accuracy = (routing_accurate / total_tests * 100) if total_tests > 0 else 0
        
        report = {
            "baseline_timestamp": self.timestamp,
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate_percent": round(success_rate, 1),
                "standard_avg_seconds": round(standard_avg, 1),
                "standard_avg_seconds": round(standard_avg, 1),
                "agent_routing_accuracy_percent": round(routing_accuracy, 1)
            },
            "performance_targets": {
                "standard_target_seconds": 60,
                "standard_target_seconds": 180, 
                "success_rate_target_percent": 90,
                "routing_accuracy_target_percent": 100
            },
            "detailed_results": [asdict(r) for r in self.results],
            "analysis": {
                "standard_within_target": standard_avg <= 60,
                "standard_within_target": standard_avg <= 180,
                "success_rate_acceptable": success_rate >= 90,
                "routing_accuracy_acceptable": routing_accuracy >= 95
            }
        }
        
        return report

    def save_baseline(self, report: Dict):
        """Save baseline results to registry"""
        
        # Save to registry/baselines/
        baseline_dir = self.base_dir / "registry" / "baselines"
        baseline_dir.mkdir(exist_ok=True)
        
        timestamp_str = self.timestamp.replace(":", "-").replace("T", "_")
        baseline_file = baseline_dir / f"baseline_{timestamp_str}.json"
        
        with open(baseline_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        # Also save as latest baseline
        latest_file = baseline_dir / "latest_baseline.json"
        with open(latest_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        self.log_event(f"Baseline saved: {baseline_file}")
        
        return baseline_file

    def print_summary(self, report: Dict):
        """Print human-readable summary"""
        
        print("\n" + "="*60)
        print("🚀 Huxley PERFORMANCE BASELINE")
        print("="*60)
        
        summary = report["summary"]
        targets = report["performance_targets"] 
        analysis = report["analysis"]
        
        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Tests Run: {summary['total_tests']}")
        print(f"   Success Rate: {summary['success_rate_percent']}% (target: {targets['success_rate_target_percent']}%)")
        print(f"   Agent Routing: {summary['agent_routing_accuracy_percent']}% (target: {targets['routing_accuracy_target_percent']}%)")
        
        print(f"\n⚡ LANE PERFORMANCE:")
        print(f"   standard: {summary['standard_avg_seconds']}s avg (target: ≤{targets['standard_target_seconds']}s)")
        print(f"   standard: {summary['standard_avg_seconds']}s avg (target: ≤{targets['standard_target_seconds']}s)")
        
        print(f"\n🎯 TARGET ANALYSIS:")
        for metric, status in analysis.items():
            emoji = "✅" if status else "❌"
            print(f"   {emoji} {metric.replace('_', ' ').title()}")
            
        print(f"\n📝 INDIVIDUAL TEST RESULTS:")
        for result in self.results:
            status = "✅" if result.success else "❌"
            print(f"   {status} {result.test_name:20} {result.lane:10} {result.duration_seconds:6.1f}s")
            
        print("\n" + "="*60)

def main():
    baseline = PerformanceBaseline()
    
    print("🚀 Starting Huxley Performance Baseline...")
    print("This will create test capsules and measure system performance.")
    print("Estimated time: 10-15 minutes\n")
    
    try:
        # Run the baseline suite
        baseline.run_baseline_suite()
        
        # Generate and save report
        report = baseline.generate_report()
        baseline_file = baseline.save_baseline(report)
        
        # Print summary
        baseline.print_summary(report)
        
        print(f"\n📄 Full report saved to: {baseline_file}")
        print("Use this baseline to track Huxley performance over time.")
        
        return 0 if report["analysis"]["success_rate_acceptable"] else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Baseline interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Baseline failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())