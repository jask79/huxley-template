#!/usr/bin/env python3
"""
Agent Usage Analytics Tracker
Tracks Claude Code agent usage patterns and performance
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
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
    
    # Import agent registry
    spec = importlib.util.spec_from_file_location("agent_registry", parent_dir / "tools" / "agent_registry.py")
    registry_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry_module)
    AgentRegistry = registry_module.AgentRegistry
except Exception as e:
    print(f"Error importing Huxley modules: {e}")
    sys.exit(1)


class AgentUsageTracker:
    """Tracks and analyzes Claude Code agent usage patterns"""
    
    def __init__(self):
        self.registry = AgentRegistry()
        self.usage_log_file = paths.registry / "agent_usage.jsonl"
        self.analytics_file = paths.registry / "agent_analytics.json"
    
    def log_agent_usage(self, agent_name: str, task_type: str, success: bool = True, 
                       duration_seconds: float = None, context: Dict[str, Any] = None):
        """Log agent usage event"""
        usage_event = {
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent_name,
            "task_type": task_type,
            "success": success,
            "duration_seconds": duration_seconds,
            "context": context or {},
            "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown")
        }
        
        # Append to usage log
        self.usage_log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.usage_log_file, 'a') as f:
            f.write(json.dumps(usage_event, default=str) + '\n')
        
        # Update registry with usage stats
        agent_id = self._find_agent_id(agent_name)
        if agent_id:
            self.registry.update_agent_usage(agent_id, success)
    
    def _find_agent_id(self, agent_name: str) -> Optional[str]:
        """Find agent ID from name"""
        for agent_id, agent in self.registry.agents.items():
            if agent["name"] == agent_name or agent_name in agent["name"]:
                return agent_id
        return None
    
    def analyze_usage_patterns(self, days: int = 30) -> Dict[str, Any]:
        """Analyze agent usage patterns over specified period"""
        if not self.usage_log_file.exists():
            return {"error": "No usage data available"}
        
        cutoff_date = datetime.now() - timedelta(days=days)
        events = []
        
        # Load usage events
        with open(self.usage_log_file, 'r') as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    event_time = datetime.fromisoformat(event["timestamp"])
                    if event_time >= cutoff_date:
                        events.append(event)
                except:
                    continue
        
        if not events:
            return {"error": "No recent usage data"}
        
        # Analyze patterns
        analysis = {
            "analysis_period": f"{days} days",
            "total_events": len(events),
            "unique_agents": len(set(e["agent_name"] for e in events)),
            "success_rate": sum(1 for e in events if e["success"]) / len(events),
            "agent_usage": self._analyze_agent_usage(events),
            "task_distribution": self._analyze_task_distribution(events),
            "temporal_patterns": self._analyze_temporal_patterns(events),
            "performance_metrics": self._analyze_performance(events),
            "recommendations": self._generate_usage_recommendations(events)
        }
        
        # Save analytics
        self.analytics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.analytics_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        return analysis
    
    def _analyze_agent_usage(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze which agents are used most"""
        agent_stats = {}
        
        for event in events:
            agent = event["agent_name"]
            if agent not in agent_stats:
                agent_stats[agent] = {
                    "total_uses": 0,
                    "successes": 0,
                    "failures": 0,
                    "avg_duration": 0,
                    "durations": []
                }
            
            stats = agent_stats[agent]
            stats["total_uses"] += 1
            
            if event["success"]:
                stats["successes"] += 1
            else:
                stats["failures"] += 1
            
            if event.get("duration_seconds"):
                stats["durations"].append(event["duration_seconds"])
        
        # Calculate averages
        for agent, stats in agent_stats.items():
            if stats["durations"]:
                stats["avg_duration"] = sum(stats["durations"]) / len(stats["durations"])
            stats["success_rate"] = stats["successes"] / stats["total_uses"]
            del stats["durations"]  # Remove raw data
        
        # Sort by usage
        sorted_agents = sorted(agent_stats.items(), key=lambda x: x[1]["total_uses"], reverse=True)
        
        return {
            "most_used": sorted_agents[:10],
            "highest_success_rate": sorted(
                [(k, v["success_rate"]) for k, v in agent_stats.items() if v["total_uses"] >= 3],
                key=lambda x: x[1], reverse=True
            )[:10],
            "fastest_agents": sorted(
                [(k, v["avg_duration"]) for k, v in agent_stats.items() 
                 if v["avg_duration"] > 0],
                key=lambda x: x[1]
            )[:10]
        }
    
    def _analyze_task_distribution(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze distribution of task types"""
        task_counts = {}
        task_success = {}
        
        for event in events:
            task_type = event["task_type"]
            task_counts[task_type] = task_counts.get(task_type, 0) + 1
            
            if task_type not in task_success:
                task_success[task_type] = {"success": 0, "total": 0}
            
            task_success[task_type]["total"] += 1
            if event["success"]:
                task_success[task_type]["success"] += 1
        
        # Calculate success rates
        task_success_rates = {
            task: stats["success"] / stats["total"]
            for task, stats in task_success.items()
        }
        
        return {
            "task_frequency": sorted(task_counts.items(), key=lambda x: x[1], reverse=True),
            "task_success_rates": sorted(task_success_rates.items(), key=lambda x: x[1], reverse=True)
        }
    
    def _analyze_temporal_patterns(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze when agents are used"""
        hourly_usage = {}
        daily_usage = {}
        
        for event in events:
            dt = datetime.fromisoformat(event["timestamp"])
            hour = dt.hour
            day = dt.strftime("%A")
            
            hourly_usage[hour] = hourly_usage.get(hour, 0) + 1
            daily_usage[day] = daily_usage.get(day, 0) + 1
        
        return {
            "peak_hours": sorted(hourly_usage.items(), key=lambda x: x[1], reverse=True)[:5],
            "daily_distribution": daily_usage,
            "busiest_day": max(daily_usage.items(), key=lambda x: x[1]) if daily_usage else None
        }
    
    def _analyze_performance(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze performance metrics"""
        durations = [e["duration_seconds"] for e in events if e.get("duration_seconds")]
        
        if not durations:
            return {"error": "No duration data available"}
        
        durations.sort()
        n = len(durations)
        
        return {
            "avg_duration": sum(durations) / n,
            "median_duration": durations[n // 2],
            "p95_duration": durations[int(n * 0.95)],
            "fastest_completion": min(durations),
            "slowest_completion": max(durations),
            "performance_trend": self._calculate_performance_trend(events)
        }
    
    def _calculate_performance_trend(self, events: List[Dict]) -> str:
        """Calculate if performance is improving or declining"""
        timed_events = [e for e in events if e.get("duration_seconds")]
        if len(timed_events) < 10:
            return "insufficient_data"
        
        # Split into first and second half
        mid = len(timed_events) // 2
        first_half_avg = sum(e["duration_seconds"] for e in timed_events[:mid]) / mid
        second_half_avg = sum(e["duration_seconds"] for e in timed_events[mid:]) / (len(timed_events) - mid)
        
        if second_half_avg < first_half_avg * 0.9:
            return "improving"
        elif second_half_avg > first_half_avg * 1.1:
            return "declining"
        else:
            return "stable"
    
    def _generate_usage_recommendations(self, events: List[Dict]) -> List[Dict[str, str]]:
        """Generate recommendations based on usage patterns"""
        recommendations = []
        
        # Check for underutilized agents
        all_agents = set(self.registry.agents.keys())
        used_agents = set(e["agent_name"] for e in events)
        unused_agents = all_agents - used_agents
        
        if len(unused_agents) > 5:
            recommendations.append({
                "type": "utilization",
                "priority": "medium",
                "message": f"{len(unused_agents)} agents haven't been used recently",
                "action": "Review agent capabilities and consider consolidation"
            })
        
        # Check for high failure rates
        agent_failures = {}
        for event in events:
            agent = event["agent_name"]
            if agent not in agent_failures:
                agent_failures[agent] = {"success": 0, "total": 0}
            
            agent_failures[agent]["total"] += 1
            if event["success"]:
                agent_failures[agent]["success"] += 1
        
        high_failure_agents = [
            agent for agent, stats in agent_failures.items()
            if stats["total"] >= 3 and stats["success"] / stats["total"] < 0.7
        ]
        
        if high_failure_agents:
            recommendations.append({
                "type": "quality",
                "priority": "high",
                "message": f"Agents with high failure rates: {', '.join(high_failure_agents)}",
                "action": "Review and improve agent specifications"
            })
        
        # Check for performance issues
        slow_agents = []
        for event in events:
            if event.get("duration_seconds", 0) > 300:  # 5 minutes
                slow_agents.append(event["agent_name"])
        
        if slow_agents:
            recommendations.append({
                "type": "performance",
                "priority": "medium",
                "message": f"Slow performing agents detected: {set(slow_agents)}",
                "action": "Optimize agent prompts and tool usage"
            })
        
        return recommendations
    
    def generate_usage_report(self, days: int = 7) -> str:
        """Generate human-readable usage report"""
        analysis = self.analyze_usage_patterns(days)
        
        if "error" in analysis:
            return f"❌ Usage Report Error: {analysis['error']}"
        
        report = f"""
📊 Agent Usage Report ({days} days)

## Summary
- **Total Events**: {analysis['total_events']}
- **Unique Agents Used**: {analysis['unique_agents']}
- **Overall Success Rate**: {analysis['success_rate']:.1%}

## Most Active Agents
"""
        
        for agent, stats in analysis['agent_usage']['most_used'][:5]:
            report += f"- **{agent}**: {stats['total_uses']} uses, {stats['success_rate']:.1%} success\n"
        
        report += "\n## Task Distribution\n"
        for task, count in analysis['task_distribution']['task_frequency'][:5]:
            report += f"- **{task}**: {count} times\n"
        
        report += "\n## Performance\n"
        perf = analysis['performance_metrics']
        if 'error' not in perf:
            report += f"- **Average Duration**: {perf['avg_duration']:.1f}s\n"
            report += f"- **Performance Trend**: {perf['performance_trend']}\n"
        
        if analysis['recommendations']:
            report += "\n## Recommendations\n"
            for rec in analysis['recommendations']:
                priority_icon = {"high": "🚨", "medium": "⚠️", "low": "💡"}.get(rec['priority'], "•")
                report += f"- {priority_icon} {rec['message']}\n"
        
        return report


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Usage Analytics Tracker")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Log command
    log_parser = subparsers.add_parser("log", help="Log agent usage")
    log_parser.add_argument("agent", help="Agent name")
    log_parser.add_argument("task", help="Task type")
    log_parser.add_argument("--success", action="store_true", default=True, help="Task succeeded")
    log_parser.add_argument("--duration", type=float, help="Duration in seconds")
    log_parser.add_argument("--context", help="Additional context (JSON string)")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze usage patterns")
    analyze_parser.add_argument("--days", type=int, default=30, help="Analysis period in days")
    analyze_parser.add_argument("--output", help="Output file path")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate usage report")
    report_parser.add_argument("--days", type=int, default=7, help="Report period in days")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tracker = AgentUsageTracker()
    
    if args.command == "log":
        context = None
        if args.context:
            try:
                context = json.loads(args.context)
            except:
                print("Warning: Invalid JSON context, ignoring")
        
        tracker.log_agent_usage(
            agent_name=args.agent,
            task_type=args.task,
            success=args.success,
            duration_seconds=args.duration,
            context=context
        )
        print(f"✅ Logged usage for {args.agent} on {args.task}")
    
    elif args.command == "analyze":
        analysis = tracker.analyze_usage_patterns(args.days)
        
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(analysis, f, indent=2, default=str)
            print(f"📊 Analysis saved to {output_path}")
        else:
            print(json.dumps(analysis, indent=2, default=str))
    
    elif args.command == "report":
        report = tracker.generate_usage_report(args.days)
        print(report)


if __name__ == "__main__":
    main()