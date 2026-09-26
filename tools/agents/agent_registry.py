#!/usr/bin/env python3
"""
Claude Code Agent Registry System
Central registry for managing and discovering Huxley agents
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
import hashlib

# Import Huxley modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("paths_config", parent_dir / "global" / "config" / "paths.py")
    paths_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paths_module)
    paths = paths_module.paths
except Exception as e:
    print(f"Error importing Huxley modules: {e}")
    sys.exit(1)


class AgentRegistry:
    """Manages the central registry of Claude Code agents"""
    
    def __init__(self):
        self.registry_file = paths.registry / "claude_agents.json"
        self.agents = {}
        self.load_registry()
    
    def scan_and_update_registry(self) -> Dict[str, Any]:
        """Scan system for agents and update registry"""
        print("🔍 Scanning for Claude Code agents...")
        
        # Clear existing agents
        self.agents = {}
        
        # Scan global agents
        self._scan_agent_directory(Path.home() / ".claude" / "agents", "global")
        
        # Scan Huxley global agents
        self._scan_agent_directory(paths.base / ".claude" / "agents", "builder_global")
        
        # Scan capsule agents
        for capsule_dir in paths.capsules.iterdir():
            if capsule_dir.is_dir() and not capsule_dir.name.startswith('.'):
                agents_dir = capsule_dir / ".claude" / "agents"
                if agents_dir.exists():
                    self._scan_agent_directory(agents_dir, "capsule", capsule_dir.name)
        
        # Scan template agents
        templates_dir = paths.base / "templates"
        if templates_dir.exists():
            for template_dir in templates_dir.iterdir():
                if template_dir.is_dir():
                    agents_dir = template_dir / ".claude" / "agents"
                    if agents_dir.exists():
                        self._scan_agent_directory(agents_dir, "template", template_dir.name)
        
        # Save updated registry
        self.save_registry()
        
        return {
            "agents_found": len(self.agents),
            "scopes": list(set(a["scope"] for a in self.agents.values())),
            "last_updated": datetime.now().isoformat()
        }
    
    def _scan_agent_directory(self, agents_dir: Path, scope: str, context: str = None):
        """Scan directory for agents"""
        if not agents_dir.exists():
            return
        
        for item in agents_dir.iterdir():
            if item.is_file() and item.suffix == '.md' and item.name != 'README.md':
                self._process_agent_file(item, scope, context)
            elif item.is_dir():
                # Traditional Claude Code format
                prompt_file = item / "prompt.md"
                if prompt_file.exists():
                    self._process_traditional_agent(item, scope, context)
    
    def _process_agent_file(self, agent_file: Path, scope: str, context: str = None):
        """Process Huxley-format agent file"""
        agent_name = agent_file.stem
        agent_id = f"{scope}:{context or 'default'}:{agent_name}"
        
        try:
            with open(agent_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse YAML frontmatter
            frontmatter = {}
            if content.startswith('---'):
                try:
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                except:
                    pass
            
            # Extract specialization from filename
            specialization = None
            if '.' in agent_name:
                parts = agent_name.split('.')
                specialization = '.'.join(parts[1:]) if len(parts) > 1 else None
            
            # Calculate content hash for change detection
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Build agent record
            agent_record = {
                "id": agent_id,
                "name": agent_name,
                "display_name": frontmatter.get("name", agent_name.replace('-', ' ').title()),
                "description": frontmatter.get("description", ""),
                "scope": scope,
                "context": context,
                "specialization": specialization,
                "path": str(agent_file),
                "format": "builder_markdown",
                "metadata": {
                    "tools": frontmatter.get("tools", []),
                    "lane": frontmatter.get("lane"),
                    "branch": frontmatter.get("branch"),
                    "triggers": frontmatter.get("triggers", []),
                    "dependencies": frontmatter.get("dependencies", [])
                },
                "file_info": {
                    "size": agent_file.stat().st_size,
                    "modified": datetime.fromtimestamp(agent_file.stat().st_mtime).isoformat(),
                    "content_hash": content_hash
                },
                "usage_stats": {
                    "invocations": 0,
                    "last_used": None,
                    "success_rate": None
                },
                "health": {
                    "status": "healthy" if len(content) > 100 else "incomplete",
                    "issues": [],
                    "last_validated": datetime.now().isoformat()
                }
            }
            
            # Basic validation
            if len(content) < 100:
                agent_record["health"]["issues"].append("Specification too short")
                agent_record["health"]["status"] = "incomplete"
            
            if not frontmatter.get("description"):
                agent_record["health"]["issues"].append("Missing description in YAML frontmatter")
                agent_record["health"]["status"] = "needs_improvement"
            
            self.agents[agent_id] = agent_record
            
        except Exception as e:
            print(f"Error processing agent {agent_file}: {e}")
    
    def _process_traditional_agent(self, agent_dir: Path, scope: str, context: str = None):
        """Process traditional Claude Code agent directory"""
        agent_name = agent_dir.name
        agent_id = f"{scope}:{context or 'default'}:{agent_name}"
        
        try:
            prompt_file = agent_dir / "prompt.md"
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            config_file = agent_dir / "config.json"
            config = {}
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
            
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            agent_record = {
                "id": agent_id,
                "name": agent_name,
                "display_name": config.get("name", agent_name.replace('-', ' ').title()),
                "description": config.get("description", ""),
                "scope": scope,
                "context": context,
                "specialization": None,
                "path": str(agent_dir),
                "format": "traditional_directory",
                "metadata": {
                    "tools": config.get("tools", []),
                    "triggers": config.get("triggers", []),
                    "dependencies": config.get("dependencies", [])
                },
                "file_info": {
                    "size": prompt_file.stat().st_size,
                    "modified": datetime.fromtimestamp(prompt_file.stat().st_mtime).isoformat(),
                    "content_hash": content_hash
                },
                "usage_stats": {
                    "invocations": 0,
                    "last_used": None,
                    "success_rate": None
                },
                "health": {
                    "status": "healthy" if len(content) > 100 else "incomplete",
                    "issues": [],
                    "last_validated": datetime.now().isoformat()
                }
            }
            
            self.agents[agent_id] = agent_record
            
        except Exception as e:
            print(f"Error processing traditional agent {agent_dir}: {e}")
    
    def get_agents_by_criteria(self, **criteria) -> List[Dict[str, Any]]:
        """Get agents matching specific criteria"""
        results = []
        
        for agent in self.agents.values():
            match = True
            
            # Check each criterion
            for key, value in criteria.items():
                if key == "scope" and agent.get("scope") != value:
                    match = False
                    break
                elif key == "lane" and agent["metadata"].get("lane") != value:
                    match = False
                    break
                elif key == "context" and agent.get("context") != value:
                    match = False
                    break
                elif key == "specialization" and agent.get("specialization") != value:
                    match = False
                    break
                elif key == "tools" and not any(tool in agent["metadata"].get("tools", []) for tool in value):
                    match = False
                    break
                elif key == "health_status" and agent["health"]["status"] != value:
                    match = False
                    break
            
            if match:
                results.append(agent)
        
        return results
    
    def get_recommendations_for_context(self, lane: str = None, branch: str = None, 
                                      task_type: str = None) -> List[Dict[str, Any]]:
        """Get agent recommendations for specific context"""
        recommendations = []
        
        # Lane-specific agents
        if lane:
            lane_agents = self.get_agents_by_criteria(lane=lane)
            if lane_agents:
                recommendations.extend([
                    {"agent": agent, "reason": f"Specialized for {lane}", "priority": "high"}
                    for agent in lane_agents
                ])
        
        # Branch-specific agents
        if branch:
            branch_agents = [a for a in self.agents.values() 
                           if a["metadata"].get("branch") == branch]
            if branch_agents:
                recommendations.extend([
                    {"agent": agent, "reason": f"Specialized for {branch}", "priority": "high"}
                    for agent in branch_agents
                ])
        
        # Task-type specific recommendations
        task_mappings = {
            "security": ["security-analyst", "security-auditor"],
            "frontend": ["frontend-dev", "javascript-pro"],
            "backend": ["backend-dev", "python-pro"],
            "deployment": ["deployment-engineer", "devops-troubleshooter"],
            "testing": ["test-automator"],
            "review": ["code-reviewer"]
        }
        
        if task_type and task_type in task_mappings:
            for agent_name in task_mappings[task_type]:
                matching_agents = [a for a in self.agents.values() 
                                 if agent_name in a["name"]]
                recommendations.extend([
                    {"agent": agent, "reason": f"Specialized for {task_type}", "priority": "medium"}
                    for agent in matching_agents
                ])
        
        # Remove duplicates and sort by priority
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            agent_id = rec["agent"]["id"]
            if agent_id not in seen:
                seen.add(agent_id)
                unique_recommendations.append(rec)
        
        # Sort by priority
        priority_order = {"high": 3, "medium": 2, "low": 1}
        unique_recommendations.sort(key=lambda x: priority_order.get(x["priority"], 0), reverse=True)
        
        return unique_recommendations[:10]  # Top 10 recommendations
    
    def update_agent_usage(self, agent_id: str, success: bool = True):
        """Update agent usage statistics"""
        if agent_id in self.agents:
            stats = self.agents[agent_id]["usage_stats"]
            stats["invocations"] += 1
            stats["last_used"] = datetime.now().isoformat()
            
            # Update success rate
            if stats["success_rate"] is None:
                stats["success_rate"] = 1.0 if success else 0.0
            else:
                # Exponential moving average
                alpha = 0.1
                stats["success_rate"] = (alpha * (1.0 if success else 0.0) + 
                                       (1 - alpha) * stats["success_rate"])
            
            self.save_registry()
    
    def get_usage_analytics(self) -> Dict[str, Any]:
        """Get usage analytics for all agents"""
        total_invocations = sum(a["usage_stats"]["invocations"] for a in self.agents.values())
        
        # Most used agents
        most_used = sorted(
            [(a["name"], a["usage_stats"]["invocations"]) for a in self.agents.values()],
            key=lambda x: x[1], reverse=True
        )[:10]
        
        # Agents by success rate
        agents_with_success_rate = [
            (a["name"], a["usage_stats"]["success_rate"])
            for a in self.agents.values()
            if a["usage_stats"]["success_rate"] is not None
        ]
        agents_with_success_rate.sort(key=lambda x: x[1], reverse=True)
        
        # Unused agents
        unused_agents = [
            a["name"] for a in self.agents.values()
            if a["usage_stats"]["invocations"] == 0
        ]
        
        return {
            "total_agents": len(self.agents),
            "total_invocations": total_invocations,
            "most_used_agents": most_used,
            "highest_success_rate": agents_with_success_rate[:10],
            "unused_agents": unused_agents,
            "agent_health": {
                "healthy": len([a for a in self.agents.values() if a["health"]["status"] == "healthy"]),
                "needs_improvement": len([a for a in self.agents.values() if a["health"]["status"] == "needs_improvement"]),
                "incomplete": len([a for a in self.agents.values() if a["health"]["status"] == "incomplete"])
            }
        }
    
    def load_registry(self):
        """Load agent registry from file"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file) as f:
                    data = json.load(f)
                    self.agents = data.get("agents", {})
            except Exception as e:
                print(f"Warning: Could not load agent registry: {e}")
                self.agents = {}
        else:
            self.agents = {}
    
    def save_registry(self):
        """Save agent registry to file"""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        
        registry_data = {
            "version": "1.0.0",
            "last_updated": datetime.now().isoformat(),
            "agents": self.agents,
            "metadata": {
                "total_agents": len(self.agents),
                "scopes": list(set(a["scope"] for a in self.agents.values())),
                "health_summary": {
                    status: len([a for a in self.agents.values() if a["health"]["status"] == status])
                    for status in ["healthy", "needs_improvement", "incomplete"]
                }
            }
        }
        
        with open(self.registry_file, 'w') as f:
            json.dump(registry_data, f, indent=2, default=str)


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Agent Registry")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Scan command
    subparsers.add_parser("scan", help="Scan and update agent registry")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List agents")
    list_parser.add_argument("--scope", help="Filter by scope")
    list_parser.add_argument("--lane", help="Filter by lane")
    list_parser.add_argument("--context", help="Filter by context")
    list_parser.add_argument("--health", help="Filter by health status")
    list_parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
    
    # Recommend command
    rec_parser = subparsers.add_parser("recommend", help="Get agent recommendations")
    rec_parser.add_argument("--lane", help="Target lane (standard, standard)")
    rec_parser.add_argument("--branch", help="Target branch (web, mobile, etc)")
    rec_parser.add_argument("--task", help="Task type (security, frontend, backend, etc)")
    
    # Analytics command
    subparsers.add_parser("analytics", help="Show usage analytics")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show agent details")
    info_parser.add_argument("agent_name", help="Agent name to show info for")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    registry = AgentRegistry()
    
    if args.command == "scan":
        result = registry.scan_and_update_registry()
        print(f"✅ Registry updated:")
        print(f"   Agents found: {result['agents_found']}")
        print(f"   Scopes: {', '.join(result['scopes'])}")
        print(f"   Registry saved: {registry.registry_file}")
    
    elif args.command == "list":
        criteria = {}
        if args.scope:
            criteria["scope"] = args.scope
        if args.lane:
            criteria["lane"] = args.lane
        if args.context:
            criteria["context"] = args.context
        if args.health:
            criteria["health_status"] = args.health
        
        agents = registry.get_agents_by_criteria(**criteria)
        
        if args.format == "json":
            print(json.dumps(agents, indent=2, default=str))
        else:
            print(f"{'Name':<25} {'Scope':<15} {'Context':<15} {'Lane':<10} {'Health':<12} {'Last Used'}")
            print("-" * 95)
            for agent in agents:
                context = str(agent.get("context") or "N/A")
                lane = str(agent["metadata"].get("lane") or "N/A")
                health = str(agent["health"]["status"])
                last_used = str(agent["usage_stats"].get("last_used") or "Never")
                if last_used != "Never":
                    last_used = last_used[:10]  # Just the date
                
                print(f"{agent['name']:<25} {agent['scope']:<15} {context:<15} {lane:<10} {health:<12} {last_used}")
    
    elif args.command == "recommend":
        recommendations = registry.get_recommendations_for_context(
            lane=args.lane,
            branch=args.branch,
            task_type=args.task
        )
        
        if recommendations:
            print(f"🎯 Agent Recommendations:")
            for i, rec in enumerate(recommendations, 1):
                agent = rec["agent"]
                priority_icon = {"high": "🔥", "medium": "⭐", "low": "💡"}.get(rec["priority"], "•")
                print(f"  {i}. {priority_icon} {agent['display_name']}")
                print(f"     Reason: {rec['reason']}")
                print(f"     Scope: {agent['scope']}, Health: {agent['health']['status']}")
                if agent.get("specialization"):
                    print(f"     Specialization: {agent['specialization']}")
                print()
        else:
            print("No agent recommendations found for the specified criteria")
    
    elif args.command == "analytics":
        analytics = registry.get_usage_analytics()
        
        print(f"📊 Agent Usage Analytics:")
        print(f"   Total Agents: {analytics['total_agents']}")
        print(f"   Total Invocations: {analytics['total_invocations']}")
        
        print(f"\n🏆 Most Used Agents:")
        for name, count in analytics['most_used_agents']:
            print(f"   {name}: {count} invocations")
        
        if analytics['highest_success_rate']:
            print(f"\n⭐ Highest Success Rate:")
            for name, rate in analytics['highest_success_rate']:
                print(f"   {name}: {rate:.1%}")
        
        if analytics['unused_agents']:
            print(f"\n💤 Unused Agents ({len(analytics['unused_agents'])}):")
            for name in analytics['unused_agents'][:5]:
                print(f"   {name}")
            if len(analytics['unused_agents']) > 5:
                print(f"   ... and {len(analytics['unused_agents']) - 5} more")
        
        print(f"\n🏥 Agent Health:")
        health = analytics['agent_health']
        print(f"   Healthy: {health['healthy']}")
        print(f"   Needs Improvement: {health['needs_improvement']}")
        print(f"   Incomplete: {health['incomplete']}")
    
    elif args.command == "info":
        # Find agent by name
        matching_agents = [a for a in registry.agents.values() 
                          if args.agent_name in a["name"]]
        
        if not matching_agents:
            print(f"Agent '{args.agent_name}' not found")
            return
        
        if len(matching_agents) > 1:
            print(f"Multiple agents match '{args.agent_name}':")
            for agent in matching_agents:
                print(f"  - {agent['name']} ({agent['scope']}:{agent.get('context', 'default')})")
            return
        
        agent = matching_agents[0]
        print(f"🤖 Agent: {agent['display_name']}")
        print(f"   Name: {agent['name']}")
        print(f"   Description: {agent['description'] or 'No description'}")
        print(f"   Scope: {agent['scope']}")
        if agent.get('context'):
            print(f"   Context: {agent['context']}")
        if agent.get('specialization'):
            print(f"   Specialization: {agent['specialization']}")
        print(f"   Format: {agent['format']}")
        print(f"   Path: {agent['path']}")
        
        print(f"\n📊 Usage Statistics:")
        stats = agent['usage_stats']
        print(f"   Invocations: {stats['invocations']}")
        print(f"   Last Used: {stats['last_used'] or 'Never'}")
        if stats['success_rate'] is not None:
            print(f"   Success Rate: {stats['success_rate']:.1%}")
        
        print(f"\n🏥 Health:")
        health = agent['health']
        print(f"   Status: {health['status']}")
        if health['issues']:
            print(f"   Issues: {', '.join(health['issues'])}")
        
        if agent['metadata']:
            print(f"\n🔧 Metadata:")
            meta = agent['metadata']
            if meta.get('tools'):
                print(f"   Tools: {', '.join(meta['tools'])}")
            if meta.get('lane'):
                print(f"   Lane: {meta['lane']}")
            if meta.get('branch'):
                print(f"   Branch: {meta['branch']}")


if __name__ == "__main__":
    main()
