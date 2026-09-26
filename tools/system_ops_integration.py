#!/usr/bin/env python3
"""
System Ops Advisor Integration - Wire all Huxleys for weekly evidence collection
Orchestrates autopsy, dependency mapping, replay analysis, and opportunity feeding for comprehensive insights
"""

import os
import sys
import json
import pathlib
import subprocess
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import tempfile

# Add Huxley tools to path
CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")
sys.path.append(str(CATALYST_ROOT / "tools"))

try:
    from events_logger import log_event
    from capsule_autopsy import CapsuleAutopsyAgent
    from dependency_mapper import DependencyMapper
    from daily_dependency_check import DependencyMonitor
except ImportError as e:
    print(f"Warning: Could not import Huxley tools: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class WeeklyEvidence:
    """Weekly evidence collection from all Huxleys"""
    period_start: str
    period_end: str
    generated_at: str
    
    # System health
    total_capsules: int
    active_capsules: int
    successful_runs: int
    failed_runs: int
    
    # Autopsy insights
    key_lessons: List[str]
    recurring_issues: List[str]
    success_patterns: List[str]
    
    # Dependency insights
    dependency_risks: List[Dict[str, Any]]
    dependency_changes: List[str]
    critical_dependencies: List[str]
    
    # Performance insights
    performance_trends: List[Dict[str, Any]]
    optimization_opportunities: List[str]
    
    # Scout opportunities
    high_priority_opportunities: List[Dict[str, Any]]
    opportunity_categories: Dict[str, int]
    
    # Integration health
    system_integration_status: Dict[str, str]
    recommendation_confidence: float
    
    metadata: Dict[str, Any]

class SystemOpsIntegrator:
    """Integrates all Huxleys for comprehensive weekly evidence"""
    
    def __init__(self):
        self.catalyst_root = CATALYST_ROOT
        self.rag_service_url = "http://localhost:8000"
        
        # Initialize system components
        self.autopsy_agent = CapsuleAutopsyAgent() if 'CapsuleAutopsyAgent' in globals() else None
        self.dependency_mapper = DependencyMapper() if 'DependencyMapper' in globals() else None
        self.dependency_monitor = DependencyMonitor() if 'DependencyMonitor' in globals() else None
        
    def collect_weekly_evidence(self, days_back: int = 7) -> WeeklyEvidence:
        """Collect comprehensive weekly evidence from all systems"""
        logger.info(f"Collecting weekly evidence for last {days_back} days")
        
        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)
        
        evidence = WeeklyEvidence(
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            generated_at=datetime.now().isoformat(),
            total_capsules=0,
            active_capsules=0,
            successful_runs=0,
            failed_runs=0,
            key_lessons=[],
            recurring_issues=[],
            success_patterns=[],
            dependency_risks=[],
            dependency_changes=[],
            critical_dependencies=[],
            performance_trends=[],
            optimization_opportunities=[],
            high_priority_opportunities=[],
            opportunity_categories={},
            system_integration_status={},
            recommendation_confidence=0.0,
            metadata={}
        )
        
        # Collect evidence from each system
        try:
            # 1. Capsule and run statistics
            capsule_stats = self._collect_capsule_statistics(period_start)
            evidence.total_capsules = capsule_stats["total_capsules"]
            evidence.active_capsules = capsule_stats["active_capsules"]
            evidence.successful_runs = capsule_stats["successful_runs"]
            evidence.failed_runs = capsule_stats["failed_runs"]
            evidence.system_integration_status["capsule_stats"] = "healthy"
            
            # 2. Autopsy insights
            autopsy_insights = self._collect_autopsy_insights(period_start)
            evidence.key_lessons = autopsy_insights["key_lessons"]
            evidence.recurring_issues = autopsy_insights["recurring_issues"]
            evidence.success_patterns = autopsy_insights["success_patterns"]
            evidence.system_integration_status["autopsy"] = "healthy" if autopsy_insights else "degraded"
            
            # 3. Dependency analysis
            dependency_analysis = self._collect_dependency_analysis()
            evidence.dependency_risks = dependency_analysis["risks"]
            evidence.dependency_changes = dependency_analysis["changes"]
            evidence.critical_dependencies = dependency_analysis["critical"]
            evidence.system_integration_status["dependencies"] = "healthy"
            
            # 4. Performance insights
            performance_insights = self._collect_performance_insights(period_start)
            evidence.performance_trends = performance_insights["trends"]
            evidence.optimization_opportunities = performance_insights["opportunities"]
            evidence.system_integration_status["performance"] = "healthy"
            
            # 5. Scout opportunities
            scout_opportunities = self._collect_scout_opportunities()
            evidence.high_priority_opportunities = scout_opportunities["high_priority"]
            evidence.opportunity_categories = scout_opportunities["categories"]
            evidence.system_integration_status["scout_feed"] = "healthy" if scout_opportunities else "degraded"
            
            # Calculate overall confidence
            evidence.recommendation_confidence = self._calculate_confidence(evidence)
            
            # Store metadata
            evidence.metadata = {
                "collection_duration_seconds": (datetime.now() - datetime.fromisoformat(evidence.generated_at)).total_seconds(),
                "data_sources_available": sum(1 for status in evidence.system_integration_status.values() if status == "healthy"),
                "total_data_sources": len(evidence.system_integration_status)
            }
            
        except Exception as e:
            logger.error(f"Error collecting weekly evidence: {e}")
            evidence.metadata["collection_error"] = str(e)
        
        return evidence
    
    def _collect_capsule_statistics(self, period_start: datetime) -> Dict[str, int]:
        """Collect capsule and run statistics"""
        stats = {
            "total_capsules": 0,
            "active_capsules": 0,
            "successful_runs": 0,
            "failed_runs": 0
        }
        
        try:
            capsules_dir = self.catalyst_root / "capsules"
            if not capsules_dir.exists():
                return stats
            
            for capsule_dir in capsules_dir.iterdir():
                if capsule_dir.is_dir() and not capsule_dir.name.startswith('.'):
                    stats["total_capsules"] += 1
                    
                    # Check for recent activity
                    runs_dir = capsule_dir / "runs"
                    if runs_dir.exists():
                        recent_activity = False
                        for run_dir in runs_dir.iterdir():
                            if run_dir.is_dir():
                                manifest_file = run_dir / "manifest.json"
                                if manifest_file.exists():
                                    try:
                                        with open(manifest_file, 'r') as f:
                                            manifest = json.load(f)
                                        
                                        run_time = datetime.fromisoformat(manifest.get("start_time", ""))
                                        if run_time >= period_start:
                                            recent_activity = True
                                            if manifest.get("success", False):
                                                stats["successful_runs"] += 1
                                            else:
                                                stats["failed_runs"] += 1
                                    except:
                                        continue
                        
                        if recent_activity:
                            stats["active_capsules"] += 1
            
        except Exception as e:
            logger.warning(f"Error collecting capsule statistics: {e}")
        
        return stats
    
    def _collect_autopsy_insights(self, period_start: datetime) -> Dict[str, List[str]]:
        """Collect insights from autopsy analyses"""
        insights = {
            "key_lessons": [],
            "recurring_issues": [],
            "success_patterns": []
        }
        
        try:
            # Query RAG for recent autopsy analyses
            import requests
            response = requests.post(
                f"{self.rag_service_url}/query",
                json={
                    "collection": "autopsy_analyses",
                    "query": "lessons learned patterns issues",
                    "top_k": 20
                },
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                for result in results.get("results", []):
                    content = result.get("content", "")
                    metadata = result.get("metadata", {})
                    
                    # Extract key insights from autopsy content
                    if "lesson learned" in content.lower():
                        lessons = self._extract_lessons_from_content(content)
                        insights["key_lessons"].extend(lessons)
                    
                    if "recurring" in content.lower() or "repeated" in content.lower():
                        issues = self._extract_issues_from_content(content)
                        insights["recurring_issues"].extend(issues)
                    
                    if "success" in content.lower() and "pattern" in content.lower():
                        patterns = self._extract_patterns_from_content(content)
                        insights["success_patterns"].extend(patterns)
            
            # Deduplicate and limit results
            insights["key_lessons"] = list(set(insights["key_lessons"]))[:5]
            insights["recurring_issues"] = list(set(insights["recurring_issues"]))[:3]
            insights["success_patterns"] = list(set(insights["success_patterns"]))[:3]
            
        except Exception as e:
            logger.warning(f"Error collecting autopsy insights: {e}")
        
        return insights
    
    def _extract_lessons_from_content(self, content: str) -> List[str]:
        """Extract lesson statements from autopsy content"""
        lessons = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('-') and ("learn" in line.lower() or "should" in line.lower()):
                lesson = line.lstrip('- ').strip()
                if len(lesson) > 10:  # Filter out very short items
                    lessons.append(lesson)
        
        return lessons[:3]  # Top 3 lessons
    
    def _extract_issues_from_content(self, content: str) -> List[str]:
        """Extract issue statements from autopsy content"""
        issues = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if ("error" in line.lower() or "fail" in line.lower() or "problem" in line.lower()) and len(line) > 10:
                issue = line.lstrip('- ').strip()
                issues.append(issue)
        
        return issues[:2]  # Top 2 issues
    
    def _extract_patterns_from_content(self, content: str) -> List[str]:
        """Extract success patterns from autopsy content"""
        patterns = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if ("pattern" in line.lower() or "consistently" in line.lower()) and "success" in line.lower():
                pattern = line.lstrip('- ').strip()
                if len(pattern) > 10:
                    patterns.append(pattern)
        
        return patterns[:2]  # Top 2 patterns
    
    def _collect_dependency_analysis(self) -> Dict[str, Any]:
        """Collect dependency analysis insights"""
        analysis = {
            "risks": [],
            "changes": [],
            "critical": []
        }
        
        try:
            # Run dependency check
            if self.dependency_monitor:
                check_results = self.dependency_monitor.run_daily_check()
                
                # Extract risks
                for risk in check_results.get("risks", []):
                    if risk.get("level") in ["HIGH", "MEDIUM"]:
                        analysis["risks"].append({
                            "type": risk.get("type"),
                            "level": risk.get("level"),
                            "description": risk.get("description"),
                            "node_id": risk.get("node_id"),
                            "dependent_count": risk.get("dependent_count")
                        })
                
                # Extract warnings as changes
                for warning in check_results.get("warnings", []):
                    analysis["changes"].append(warning)
            
            # Load dependency graph for critical dependencies
            graph_file = self.catalyst_root / "global" / "dependency-graph.json"
            if graph_file.exists():
                with open(graph_file, 'r') as f:
                    graph_data = json.load(f)
                
                # Find critical dependencies (high dependent count)
                edge_counts = {}
                for edge in graph_data.get("edges", []):
                    to_node = edge.get("to_node", "")
                    edge_counts[to_node] = edge_counts.get(to_node, 0) + 1
                
                critical_nodes = [(node, count) for node, count in edge_counts.items() if count >= 3]
                critical_nodes.sort(key=lambda x: x[1], reverse=True)
                
                for node_id, count in critical_nodes[:5]:  # Top 5 critical
                    node_data = graph_data.get("nodes", {}).get(node_id, {})
                    node_name = node_data.get("name", node_id.split(":")[-1])
                    analysis["critical"].append(f"{node_name} ({count} dependents)")
        
        except Exception as e:
            logger.warning(f"Error collecting dependency analysis: {e}")
        
        return analysis
    
    def _collect_performance_insights(self, period_start: datetime) -> Dict[str, Any]:
        """Collect performance insights"""
        insights = {
            "trends": [],
            "opportunities": []
        }
        
        try:
            # Query RAG for performance-related content
            import requests
            response = requests.post(
                f"{self.rag_service_url}/query",
                json={
                    "collection": "scout_opportunities",
                    "query": "performance optimization slow duration",
                    "top_k": 10
                },
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                for result in results.get("results", []):
                    metadata = result.get("metadata", {})
                    if metadata.get("category") == "optimization":
                        content = result.get("content", "")
                        
                        # Extract performance trend
                        if "duration" in metadata:
                            insights["trends"].append({
                                "metric": "duration",
                                "value": metadata.get("avg_duration_ms"),
                                "stage": metadata.get("stage"),
                                "type": "performance"
                            })
                        
                        # Extract optimization opportunities
                        lines = content.split('\n')
                        for line in lines:
                            if line.strip().startswith('- ') and ("optim" in line.lower() or "improv" in line.lower()):
                                opportunity = line.strip().lstrip('- ')
                                insights["opportunities"].append(opportunity)
            
            # Limit results
            insights["opportunities"] = list(set(insights["opportunities"]))[:4]
            
        except Exception as e:
            logger.warning(f"Error collecting performance insights: {e}")
        
        return insights
    
    def _collect_scout_opportunities(self) -> Dict[str, Any]:
        """Collect Scout Agent opportunities"""
        opportunities_data = {
            "high_priority": [],
            "categories": {}
        }
        
        try:
            # Query RAG for high-priority opportunities
            import requests
            response = requests.post(
                f"{self.rag_service_url}/query",
                json={
                    "collection": "scout_opportunities",
                    "query": "high priority opportunity action",
                    "top_k": 15
                },
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                categories = {}
                
                for result in results.get("results", []):
                    metadata = result.get("metadata", {})
                    priority = metadata.get("priority", "medium")
                    category = metadata.get("category", "unknown")
                    confidence = metadata.get("confidence", 0.0)
                    
                    # Count categories
                    categories[category] = categories.get(category, 0) + 1
                    
                    # Collect high priority opportunities
                    if priority == "high" and confidence >= 0.7:
                        content = result.get("content", "")
                        title = content.split('\n')[0].lstrip('# ').strip()
                        
                        opportunities_data["high_priority"].append({
                            "title": title,
                            "category": category,
                            "confidence": confidence,
                            "priority": priority
                        })
                
                opportunities_data["categories"] = categories
                
                # Limit high priority items
                opportunities_data["high_priority"] = opportunities_data["high_priority"][:5]
        
        except Exception as e:
            logger.warning(f"Error collecting scout opportunities: {e}")
        
        return opportunities_data
    
    def _calculate_confidence(self, evidence: WeeklyEvidence) -> float:
        """Calculate overall recommendation confidence"""
        confidence_factors = []
        
        # Data availability factor
        healthy_systems = sum(1 for status in evidence.system_integration_status.values() if status == "healthy")
        total_systems = len(evidence.system_integration_status)
        data_availability = healthy_systems / max(total_systems, 1)
        confidence_factors.append(data_availability * 0.3)
        
        # Activity level factor
        total_runs = evidence.successful_runs + evidence.failed_runs
        activity_factor = min(1.0, total_runs / 10)  # Normalize to 10 runs as "high activity"
        confidence_factors.append(activity_factor * 0.2)
        
        # Evidence quality factor
        evidence_count = (
            len(evidence.key_lessons) +
            len(evidence.dependency_risks) +
            len(evidence.high_priority_opportunities)
        )
        evidence_quality = min(1.0, evidence_count / 15)  # Normalize to 15 pieces of evidence
        confidence_factors.append(evidence_quality * 0.3)
        
        # System health factor
        if evidence.failed_runs > 0:
            health_factor = evidence.successful_runs / max(total_runs, 1)
        else:
            health_factor = 1.0
        confidence_factors.append(health_factor * 0.2)
        
        return sum(confidence_factors)
    
    def generate_weekly_report(self, evidence: WeeklyEvidence) -> str:
        """Generate human-readable weekly report"""
        report = f"""# Huxley Weekly Report

**Period**: {evidence.period_start[:10]} to {evidence.period_end[:10]}
**Generated**: {evidence.generated_at[:19]}
**Confidence**: {evidence.recommendation_confidence:.2f}

## 📊 System Overview

- **Total Capsules**: {evidence.total_capsules}
- **Active Capsules**: {evidence.active_capsules}
- **Successful Runs**: {evidence.successful_runs}
- **Failed Runs**: {evidence.failed_runs}

## 🎯 Key Lessons Learned

"""
        
        if evidence.key_lessons:
            for lesson in evidence.key_lessons:
                report += f"- {lesson}\n"
        else:
            report += "No key lessons identified this period.\n"
        
        report += "\n## 🚨 Recurring Issues\n\n"
        if evidence.recurring_issues:
            for issue in evidence.recurring_issues:
                report += f"- {issue}\n"
        else:
            report += "No recurring issues identified.\n"
        
        report += "\n## ✅ Success Patterns\n\n"
        if evidence.success_patterns:
            for pattern in evidence.success_patterns:
                report += f"- {pattern}\n"
        else:
            report += "No specific success patterns identified.\n"
        
        report += "\n## ⚠️ Dependency Risks\n\n"
        if evidence.dependency_risks:
            for risk in evidence.dependency_risks[:3]:  # Top 3
                report += f"- **{risk['level']}**: {risk['description']}\n"
        else:
            report += "No significant dependency risks.\n"
        
        if evidence.critical_dependencies:
            report += "\n**Critical Dependencies**:\n"
            for dep in evidence.critical_dependencies:
                report += f"- {dep}\n"
        
        report += "\n## 🚀 Optimization Opportunities\n\n"
        if evidence.optimization_opportunities:
            for opp in evidence.optimization_opportunities:
                report += f"- {opp}\n"
        else:
            report += "No optimization opportunities identified.\n"
        
        report += "\n## 🎯 High-Priority Scout Opportunities\n\n"
        if evidence.high_priority_opportunities:
            for opp in evidence.high_priority_opportunities:
                report += f"- **{opp['title']}** ({opp['category']}, confidence: {opp['confidence']:.2f})\n"
        else:
            report += "No high-priority opportunities identified.\n"
        
        if evidence.opportunity_categories:
            report += "\n**Opportunity Categories**:\n"
            for category, count in evidence.opportunity_categories.items():
                report += f"- {category.title()}: {count}\n"
        
        report += "\n## 🏥 System Integration Health\n\n"
        for system, status in evidence.system_integration_status.items():
            status_emoji = "✅" if status == "healthy" else "⚠️"
            report += f"- {system.replace('_', ' ').title()}: {status_emoji} {status}\n"
        
        return report
    
    def save_weekly_evidence(self, evidence: WeeklyEvidence) -> pathlib.Path:
        """Save weekly evidence to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        evidence_file = self.catalyst_root / "global" / f"weekly_evidence_{timestamp}.json"
        
        with open(evidence_file, 'w') as f:
            json.dump(asdict(evidence), f, indent=2, default=str)
        
        return evidence_file
    
    def ingest_evidence_to_rag(self, evidence: WeeklyEvidence) -> bool:
        """Ingest weekly evidence into RAG system"""
        try:
            # Generate report content
            report_content = self.generate_weekly_report(evidence)
            
            # Prepare RAG document
            doc_id = f"weekly_evidence_{evidence.period_end[:10]}"
            document = {
                "id": doc_id,
                "content": report_content,
                "metadata": {
                    "type": "weekly_evidence",
                    "period_start": evidence.period_start,
                    "period_end": evidence.period_end,
                    "confidence": evidence.recommendation_confidence,
                    "total_capsules": evidence.total_capsules,
                    "successful_runs": evidence.successful_runs,
                    "failed_runs": evidence.failed_runs
                }
            }
            
            # Upsert to RAG
            import requests
            response = requests.post(
                f"{self.rag_service_url}/upsert",
                json={
                    "collection": "system_evidence",
                    "documents": [document]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully ingested weekly evidence to RAG")
                return True
            else:
                logger.error(f"Failed to ingest evidence: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Error ingesting evidence to RAG: {e}")
            return False
    
    def run_weekly_integration(self, days_back: int = 7) -> Dict[str, Any]:
        """Run complete weekly integration cycle"""
        logger.info("Starting weekly system integration cycle")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "evidence_collected": False,
            "evidence_saved": False,
            "evidence_ingested": False,
            "report_generated": False,
            "confidence": 0.0,
            "errors": []
        }
        
        try:
            # Collect evidence
            evidence = self.collect_weekly_evidence(days_back)
            results["evidence_collected"] = True
            results["confidence"] = evidence.recommendation_confidence
            
            # Save evidence
            evidence_file = self.save_weekly_evidence(evidence)
            results["evidence_saved"] = True
            results["evidence_file"] = str(evidence_file)
            
            # Generate report
            report_content = self.generate_weekly_report(evidence)
            report_file = evidence_file.with_suffix('.md')
            
            with open(report_file, 'w') as f:
                f.write(report_content)
            
            results["report_generated"] = True
            results["report_file"] = str(report_file)
            
            # Ingest to RAG
            if self.ingest_evidence_to_rag(evidence):
                results["evidence_ingested"] = True
            
            # Log integration event
            log_event(
                stage="weekly_integration",
                level="INFO",
                message=f"Weekly system integration completed (confidence: {evidence.recommendation_confidence:.2f})",
                capsule="system",
                data={
                    "total_capsules": evidence.total_capsules,
                    "active_capsules": evidence.active_capsules,
                    "successful_runs": evidence.successful_runs,
                    "failed_runs": evidence.failed_runs,
                    "confidence": evidence.recommendation_confidence
                }
            )
            
        except Exception as e:
            logger.error(f"Weekly integration failed: {e}")
            results["errors"].append(str(e))
        
        return results

def main():
    """CLI interface for system ops integration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="System Ops Advisor Integration")
    parser.add_argument("--days", "-d", type=int, default=7, help="Days of data to analyze")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--report-only", action="store_true", help="Only generate report, don't save or ingest")
    
    args = parser.parse_args()
    
    try:
        integrator = SystemOpsIntegrator()
        
        if args.report_only:
            evidence = integrator.collect_weekly_evidence(args.days)
            report = integrator.generate_weekly_report(evidence)
            print(report)
        else:
            results = integrator.run_weekly_integration(args.days)
            
            if args.json:
                print(json.dumps(results, indent=2, default=str))
            else:
                success_count = sum(1 for key in ["evidence_collected", "evidence_saved", "report_generated"] if results.get(key))
                print(f"🔄 Weekly System Integration - {success_count}/3 steps completed")
                print("=" * 60)
                print(f"Evidence Collected: {'✅' if results['evidence_collected'] else '❌'}")
                print(f"Evidence Saved: {'✅' if results['evidence_saved'] else '❌'}")
                print(f"Report Generated: {'✅' if results['report_generated'] else '❌'}")
                print(f"RAG Ingested: {'✅' if results['evidence_ingested'] else '❌'}")
                print(f"Confidence: {results['confidence']:.2f}")
                
                if results.get("report_file"):
                    print(f"\nReport: {results['report_file']}")
                
                if results["errors"]:
                    print(f"\nErrors:")
                    for error in results["errors"]:
                        print(f"  - {error}")
    
    except Exception as e:
        logger.error(f"Failed to run system ops integration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()