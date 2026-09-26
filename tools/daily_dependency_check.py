#!/usr/bin/env python3
"""
Daily Dependency Check - Compare dependency graph changes and log warnings
Integrates with daily audit system to monitor dependency evolution
"""

import sys
import pathlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add Huxley tools to path
CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")
sys.path.append(str(CATALYST_ROOT / "tools"))

try:
    from dependency_mapper import DependencyMapper
    from events_logger import log_event
except ImportError as e:
    print(f"Warning: Could not import Huxley tools: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DependencyMonitor:
    """Monitors dependency changes and risks"""
    
    def __init__(self):
        self.catalyst_root = CATALYST_ROOT
        self.registry_dir = self.catalyst_root / "registry"
        
    def run_daily_check(self) -> Dict[str, Any]:
        """Run daily dependency check"""
        logger.info("Running daily dependency check...")
        
        check_results = {
            "timestamp": datetime.now().isoformat(),
            "graph_updated": False,
            "changes_detected": False,
            "warnings": [],
            "risks": [],
            "summary": ""
        }
        
        try:
            # Build current dependency graph
            mapper = DependencyMapper()
            current_graph = mapper.build_complete_graph()
            check_results["graph_updated"] = True
            
            # Load yesterday's graph for comparison
            yesterday_graph = self._load_historical_graph()
            
            if yesterday_graph:
                # Detect critical changes
                critical_changes = self._detect_critical_changes(yesterday_graph, current_graph)
                if critical_changes:
                    check_results["changes_detected"] = True
                    check_results["warnings"].extend(critical_changes)
            
            # Analyze current risks
            risks = self._analyze_risks(current_graph)
            check_results["risks"] = risks
            
            # Generate summary
            check_results["summary"] = self._generate_summary(check_results)
            
            # Log significant events
            self._log_check_events(check_results)
            
        except Exception as e:
            logger.error(f"Daily dependency check failed: {e}")
            check_results["error"] = str(e)
            check_results["summary"] = f"Dependency check failed: {e}"
        
        return check_results
    
    def _load_historical_graph(self) -> Dict[str, Any]:
        """Load historical dependency graph from yesterday"""
        graph_file = self.catalyst_root / "global" / "dependency-graph.json"
        
        if not graph_file.exists():
            return None
        
        try:
            # Check file age - should be from yesterday ideally
            file_age = datetime.now() - datetime.fromtimestamp(graph_file.stat().st_mtime)
            if file_age > timedelta(days=2):
                logger.warning(f"Dependency graph is {file_age.days} days old")
            
            with open(graph_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.warning(f"Could not load historical graph: {e}")
            return None
    
    def _detect_critical_changes(self, old_graph: Dict[str, Any], 
                                current_graph_obj) -> List[str]:
        """Detect critical dependency changes that warrant warnings"""
        warnings = []
        
        # Convert current graph to comparable format
        current_graph = {
            "nodes": {k: v.__dict__ if hasattr(v, '__dict__') else v 
                     for k, v in current_graph_obj.nodes.items()},
            "edges": [e.__dict__ if hasattr(e, '__dict__') else e 
                     for e in current_graph_obj.edges]
        }
        
        old_nodes = set(old_graph.get("nodes", {}).keys())
        current_nodes = set(current_graph.get("nodes", {}).keys())
        
        # Critical node removals
        removed_nodes = old_nodes - current_nodes
        for node_id in removed_nodes:
            node_info = old_graph["nodes"].get(node_id, {})
            node_name = node_info.get("name", node_id)
            node_type = node_info.get("type", "unknown")
            
            # Check if this node had dependents
            had_dependents = any(
                edge.get("to_node") == node_id 
                for edge in old_graph.get("edges", [])
            )
            
            if had_dependents:
                warnings.append(f"CRITICAL: {node_type} '{node_name}' removed but had dependents")
            else:
                warnings.append(f"INFO: {node_type} '{node_name}' removed (no dependents)")
        
        # New critical dependencies
        added_nodes = current_nodes - old_nodes
        for node_id in added_nodes:
            node_info = current_graph["nodes"].get(node_id, {})
            node_name = node_info.get("name", node_id)
            node_type = node_info.get("type", "unknown")
            
            if node_type in ["mcp", "api", "service"]:
                warnings.append(f"NEW: {node_type} '{node_name}' added as dependency")
        
        # Dependency relationship changes
        old_edges = {(e.get("from_node"), e.get("to_node"), e.get("relationship")) 
                    for e in old_graph.get("edges", [])}
        current_edges = {(e.get("from_node"), e.get("to_node"), e.get("relationship")) 
                        for e in current_graph.get("edges", [])}
        
        # Critical relationship removals
        removed_edges = old_edges - current_edges
        for edge in removed_edges:
            from_node, to_node, relationship = edge
            if relationship == "requires":  # Focus on hard requirements
                warnings.append(f"DEPENDENCY REMOVED: {from_node} no longer requires {to_node}")
        
        return warnings
    
    def _analyze_risks(self, graph) -> List[Dict[str, Any]]:
        """Analyze current dependency risks"""
        risks = []
        
        # Single points of failure (nodes with many dependents)
        dependency_counts = {}
        for edge in graph.edges:
            to_node = edge.to_node
            dependency_counts[to_node] = dependency_counts.get(to_node, 0) + 1
        
        # Identify high-risk dependencies
        for node_id, count in dependency_counts.items():
            if count >= 3:  # 3+ dependents = high risk
                node = graph.nodes.get(node_id)
                if node:
                    risk_level = "HIGH" if count >= 5 else "MEDIUM"
                    risks.append({
                        "type": "single_point_of_failure",
                        "level": risk_level,
                        "description": f"{node.name} ({node.type}) has {count} dependents",
                        "node_id": node_id,
                        "dependent_count": count
                    })
        
        # External dependency risks (APIs, services)
        external_types = ["api", "service", "mcp"]
        for node in graph.nodes.values():
            if node.type in external_types:
                dependent_count = dependency_counts.get(node.id, 0)
                if dependent_count > 0:
                    risks.append({
                        "type": "external_dependency",
                        "level": "MEDIUM",
                        "description": f"External {node.type} '{node.name}' used by {dependent_count} components",
                        "node_id": node.id,
                        "dependent_count": dependent_count
                    })
        
        # Circular dependency detection (simplified)
        # This could be enhanced with proper cycle detection algorithms
        
        return risks
    
    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """Generate human-readable summary"""
        summary_parts = []
        
        if results.get("graph_updated"):
            summary_parts.append("Dependency graph updated")
        
        warning_count = len(results.get("warnings", []))
        if warning_count > 0:
            summary_parts.append(f"{warning_count} warnings")
        
        risk_count = len(results.get("risks", []))
        if risk_count > 0:
            high_risks = sum(1 for r in results["risks"] if r.get("level") == "HIGH")
            if high_risks > 0:
                summary_parts.append(f"{high_risks} high risks")
            else:
                summary_parts.append(f"{risk_count} medium risks")
        
        if not summary_parts:
            return "No significant dependency changes"
        
        return "; ".join(summary_parts)
    
    def _log_check_events(self, results: Dict[str, Any]):
        """Log significant events to Huxley registry"""
        try:
            # Log overall check completion
            level = "WARNING" if results.get("warnings") or results.get("error") else "INFO"
            
            log_event(
                stage="dependency_check",
                level=level,
                message=f"Daily dependency check: {results['summary']}",
                capsule="system",
                data={
                    "warnings_count": len(results.get("warnings", [])),
                    "risks_count": len(results.get("risks", [])),
                    "changes_detected": results.get("changes_detected", False)
                }
            )
            
            # Log individual warnings as separate events
            for warning in results.get("warnings", []):
                log_event(
                    stage="dependency_warning",
                    level="WARNING",
                    message=warning,
                    capsule="system"
                )
                
            # Log high-risk dependencies
            for risk in results.get("risks", []):
                if risk.get("level") == "HIGH":
                    log_event(
                        stage="dependency_risk",
                        level="WARNING",
                        message=f"HIGH RISK: {risk['description']}",
                        capsule="system",
                        data=risk
                    )
                    
        except Exception as e:
            logger.warning(f"Failed to log dependency check events: {e}")

def main():
    """CLI interface for daily dependency check"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Daily Dependency Check")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        monitor = DependencyMonitor()
        results = monitor.run_daily_check()
        
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print(f"🔍 Daily Dependency Check - {datetime.now().strftime('%Y-%m-%d')}")
            print("=" * 50)
            print(f"Status: {results['summary']}")
            
            if results.get("warnings"):
                print(f"\n⚠️  Warnings ({len(results['warnings'])}):")
                for warning in results["warnings"]:
                    print(f"  - {warning}")
            
            if results.get("risks"):
                high_risks = [r for r in results["risks"] if r.get("level") == "HIGH"]
                medium_risks = [r for r in results["risks"] if r.get("level") == "MEDIUM"]
                
                if high_risks:
                    print(f"\n🚨 High Risks ({len(high_risks)}):")
                    for risk in high_risks:
                        print(f"  - {risk['description']}")
                
                if medium_risks and not args.quiet:
                    print(f"\n⚠️  Medium Risks ({len(medium_risks)}):")
                    for risk in medium_risks[:3]:  # Show top 3
                        print(f"  - {risk['description']}")
                    if len(medium_risks) > 3:
                        print(f"  ... and {len(medium_risks) - 3} more")
            
            if not results.get("warnings") and not results.get("risks"):
                print("\n✅ No significant risks or changes detected")
        
        # Exit with appropriate code
        exit_code = 0
        if results.get("error"):
            exit_code = 2
        elif results.get("warnings") or any(r.get("level") == "HIGH" for r in results.get("risks", [])):
            exit_code = 1
        
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f"Daily dependency check failed: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()