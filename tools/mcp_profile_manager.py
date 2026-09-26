#!/usr/bin/env python3
"""
MCP Profile Manager
Manages and optimizes MCP profiles for Huxley agents
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

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
    spec = importlib.util.spec_from_file_location("agent_registry", parent_dir / "tools" / "agents" / "agent_registry.py")
    registry_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry_module)
    AgentRegistry = registry_module.AgentRegistry
    
except Exception as e:
    print(f"Error importing Huxley modules: {e}")
    sys.exit(1)


class MCPProfileManager:
    """Manages MCP profiles and optimizes agent configurations"""
    
    def __init__(self):
        self.registry = AgentRegistry()
        self.profile_configs = self._load_profile_configs()
        self.current_mcp_config = self._load_current_mcp_config()
        
    def _load_profile_configs(self) -> Dict[str, Any]:
        """Load MCP profile configurations"""
        profile_file = paths.base / "global" / "mcp" / "profile-configs.json"
        if profile_file.exists():
            with open(profile_file) as f:
                return json.load(f)
        return {}
    
    def _load_current_mcp_config(self) -> Dict[str, Any]:
        """Load current MCP server configuration"""
        mcp_config_file = paths.base / "global" / "claude-config" / "mcp_servers.json"
        if mcp_config_file.exists():
            with open(mcp_config_file) as f:
                return json.load(f)
        return {"mcpServers": {}}
    
    def analyze_profile_optimization(self) -> Dict[str, Any]:
        """Analyze current agent configurations and suggest profile optimizations"""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "current_profiles": {},
            "optimization_opportunities": [],
            "profile_recommendations": {},
            "mcp_utilization": {},
            "lane_compliance": {}
        }
        
        # Analyze each agent's current configuration
        for agent_id, agent_info in self.registry.agents.items():
            agent_name = agent_info["name"]
            current_tools = agent_info.get("metadata", {}).get("tools", [])
            
            # Determine current profile fit
            profile_fit = self._analyze_agent_profile_fit(agent_name, current_tools)
            analysis["current_profiles"][agent_id] = profile_fit
            
            # Check for optimization opportunities
            optimization = self._check_optimization_opportunities(agent_name, current_tools)
            if optimization["has_opportunities"]:
                analysis["optimization_opportunities"].append({
                    "agent": agent_name,
                    "agent_id": agent_id,
                    "opportunities": optimization["opportunities"]
                })
            
            # Generate profile recommendation
            recommendation = self._recommend_profile_for_agent(agent_name, current_tools)
            analysis["profile_recommendations"][agent_id] = recommendation
        
        # Analyze MCP utilization
        analysis["mcp_utilization"] = self._analyze_mcp_utilization()
        
        # Check lane compliance
        analysis["lane_compliance"] = self._check_lane_compliance()
        
        return analysis
    
    def _analyze_agent_profile_fit(self, agent_name: str, current_tools: List[str]) -> Dict[str, Any]:
        """Analyze how well an agent fits current MCP profiles"""
        profile_scores = {}
        
        for profile_name, profile_config in self.profile_configs.get("mcp_profiles", {}).items():
            score = self._calculate_profile_fit_score(agent_name, current_tools, profile_config)
            profile_scores[profile_name] = score
        
        best_profile = max(profile_scores.items(), key=lambda x: x[1]) if profile_scores else ("none", 0)
        
        return {
            "best_profile": best_profile[0],
            "fit_score": best_profile[1],
            "all_scores": profile_scores,
            "current_tools": current_tools
        }
    
    def _calculate_profile_fit_score(self, agent_name: str, current_tools: List[str], 
                                   profile_config: Dict[str, Any]) -> float:
        """Calculate how well an agent fits a specific profile"""
        score = 0
        
        # Check if agent is explicitly listed for this profile
        if agent_name in profile_config.get("agents", []):
            score += 50
        
        # Check tool alignment
        profile_mcps = profile_config.get("mcps", [])
        if profile_config.get("extends"):
            # Add parent profile MCPs
            parent_profile = self.profile_configs.get("mcp_profiles", {}).get(profile_config["extends"], {})
            profile_mcps.extend(parent_profile.get("mcps", []))
        
        profile_mcps.extend(profile_config.get("additional_mcps", []))
        
        # Score based on tool overlap
        tool_overlap = len(set(current_tools) & set(profile_mcps))
        total_profile_tools = len(profile_mcps)
        if total_profile_tools > 0:
            score += (tool_overlap / total_profile_tools) * 30
        
        # Check for missing core tools
        missing_core = len(set(profile_mcps) - set(current_tools))
        score -= missing_core * 5
        
        # Check for unnecessary tools
        unnecessary = len(set(current_tools) - set(profile_mcps) - set(profile_config.get("optional_mcps", [])))
        score -= unnecessary * 3
        
        return max(0, score)
    
    def _check_optimization_opportunities(self, agent_name: str, current_tools: List[str]) -> Dict[str, Any]:
        """Check for optimization opportunities for an agent"""
        opportunities = []
        
        # Check against agent MCP matrix
        agent_matrix = self.profile_configs.get("agent_mcp_matrix", {}).get(agent_name)
        if agent_matrix:
            core_mcps = agent_matrix.get("core_mcps", [])
            missing_core = [mcp for mcp in core_mcps if mcp not in current_tools]
            if missing_core:
                opportunities.append({
                    "type": "missing_core_mcps",
                    "description": f"Missing core MCPs: {', '.join(missing_core)}",
                    "priority": "high",
                    "action": f"Add {', '.join(missing_core)} to agent tools"
                })
            
            integration_mcps = agent_matrix.get("integration_mcps", [])
            missing_integration = [mcp for mcp in integration_mcps if mcp not in current_tools]
            if missing_integration:
                opportunities.append({
                    "type": "missing_integration_mcps", 
                    "description": f"Missing integration MCPs: {', '.join(missing_integration)}",
                    "priority": "medium",
                    "action": f"Consider adding {', '.join(missing_integration)} for enhanced functionality"
                })
        
        # Check for profile alignment
        recommended_profile = self._recommend_profile_for_agent(agent_name, current_tools)
        if recommended_profile["confidence"] > 0.7 and recommended_profile["profile"] != "current":
            opportunities.append({
                "type": "profile_optimization",
                "description": f"Agent would benefit from {recommended_profile['profile']} profile",
                "priority": "medium", 
                "action": f"Apply {recommended_profile['profile']} profile for optimized MCP access"
            })
        
        return {
            "has_opportunities": len(opportunities) > 0,
            "opportunities": opportunities
        }
    
    def _recommend_profile_for_agent(self, agent_name: str, current_tools: List[str]) -> Dict[str, Any]:
        """Recommend optimal profile for an agent"""
        # Check explicit agent mappings first
        for profile_name, profile_config in self.profile_configs.get("mcp_profiles", {}).items():
            if agent_name in profile_config.get("agents", []):
                return {
                    "profile": profile_name,
                    "confidence": 1.0,
                    "reason": "Explicitly mapped to profile"
                }
        
        # Analyze based on agent name patterns
        if "automation" in agent_name or "n8n" in agent_name:
            return {
                "profile": "automation",
                "confidence": 0.9,
                "reason": "Agent name indicates automation focus"
            }
        elif any(web_term in agent_name for web_term in ["frontend", "shopify", "web", "javascript"]):
            return {
                "profile": "webdev", 
                "confidence": 0.8,
                "reason": "Agent name indicates web development focus"
            }
        elif any(apple_term in agent_name for apple_term in ["ios", "macos", "xcode", "apple"]):
            return {
                "profile": "apple",
                "confidence": 0.9,
                "reason": "Agent name indicates Apple platform focus"
            }
        elif any(sec_term in agent_name for sec_term in ["security", "audit"]):
            return {
                "profile": "security",
                "confidence": 0.8,
                "reason": "Agent name indicates security focus"
            }
        else:
            return {
                "profile": "default",
                "confidence": 0.6,
                "reason": "No specific specialization detected"
            }
    
    def _analyze_mcp_utilization(self) -> Dict[str, Any]:
        """Analyze MCP server utilization across agents"""
        utilization = {}
        
        # Count MCP usage across all agents
        mcp_usage = {}
        for agent_info in self.registry.agents.values():
            tools = agent_info.get("metadata", {}).get("tools", [])
            for tool in tools:
                mcp_usage[tool] = mcp_usage.get(tool, 0) + 1
        
        # Analyze configured vs used MCPs
        configured_mcps = set(self.current_mcp_config.get("mcpServers", {}).keys())
        used_mcps = set(mcp_usage.keys())
        
        utilization = {
            "total_configured": len(configured_mcps),
            "total_used": len(used_mcps),
            "unused_mcps": list(configured_mcps - used_mcps),
            "missing_mcps": list(used_mcps - configured_mcps),
            "usage_distribution": dict(sorted(mcp_usage.items(), key=lambda x: x[1], reverse=True)),
            "utilization_rate": len(used_mcps) / len(configured_mcps) if configured_mcps else 0
        }
        
        return utilization
    
    def _check_lane_compliance(self) -> Dict[str, Any]:
        """Check compliance with lane-specific MCP requirements"""
        compliance = {
            "standard_agents": [],
            "standard_agents": [],
            "non_compliant": []
        }
        
        
        for agent_info in self.registry.agents.values():
            agent_tools = agent_info.get("metadata", {}).get("tools", [])
            
            # Handle lane as string or list
            if isinstance(agent_lane, list):
                agent_lanes = agent_lane
            elif isinstance(agent_lane, str):
                agent_lanes = [agent_lane]
            else:
                agent_lanes = []
            
            for lane in agent_lanes:
                    
                    missing_required = [mcp for mcp in required_mcps if mcp not in agent_tools]
                    
                    if missing_required:
                        compliance["non_compliant"].append({
                            "agent": agent_info["name"],
                            "missing_mcps": missing_required
                        })
                    else:
                        compliance[f"{lane}_agents"].append(agent_info["name"])
        
        return compliance
    
    def apply_profile_optimizations(self, optimization_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Apply recommended profile optimizations"""
        results = {
            "applied_optimizations": [],
            "failed_optimizations": [],
            "summary": {}
        }
        
        for opportunity in optimization_analysis.get("optimization_opportunities", []):
            agent_name = opportunity["agent"]
            agent_id = opportunity["agent_id"]
            
            try:
                # Apply each optimization opportunity
                for opt in opportunity["opportunities"]:
                    if opt["type"] == "missing_core_mcps":
                        result = self._add_mcps_to_agent(agent_id, opt["action"])
                        results["applied_optimizations"].append({
                            "agent": agent_name,
                            "optimization": opt["type"],
                            "result": result
                        })
                    elif opt["type"] == "profile_optimization":
                        result = self._apply_profile_to_agent(agent_id, opt["action"])
                        results["applied_optimizations"].append({
                            "agent": agent_name,
                            "optimization": opt["type"], 
                            "result": result
                        })
            except Exception as e:
                results["failed_optimizations"].append({
                    "agent": agent_name,
                    "error": str(e)
                })
        
        results["summary"] = {
            "total_optimizations": len(optimization_analysis.get("optimization_opportunities", [])),
            "successful": len(results["applied_optimizations"]),
            "failed": len(results["failed_optimizations"])
        }
        
        return results
    
    def _add_mcps_to_agent(self, agent_id: str, action_description: str) -> Dict[str, Any]:
        """Add MCPs to agent configuration"""
        # This would update the agent's YAML frontmatter
        # For now, return a placeholder result
        return {
            "action": "add_mcps",
            "description": action_description,
            "status": "simulated",
            "note": "MCP addition would be applied to agent YAML frontmatter"
        }
    
    def _apply_profile_to_agent(self, agent_id: str, action_description: str) -> Dict[str, Any]:
        """Apply profile configuration to agent"""
        # This would update the agent's configuration to match profile
        # For now, return a placeholder result
        return {
            "action": "apply_profile",
            "description": action_description,
            "status": "simulated",
            "note": "Profile would be applied to agent configuration"
        }
    
    def generate_profile_report(self, analysis: Dict[str, Any]) -> str:
        """Generate human-readable profile optimization report"""
        report = f"""
🔧 MCP Profile Optimization Report

## Summary
- **Total Agents Analyzed**: {len(analysis.get('current_profiles', {}))}
- **Optimization Opportunities**: {len(analysis.get('optimization_opportunities', []))}
- **MCP Utilization Rate**: {analysis.get('mcp_utilization', {}).get('utilization_rate', 0):.1%}

## Profile Recommendations
"""
        
        for agent_id, recommendation in analysis.get("profile_recommendations", {}).items():
            agent_name = self.registry.agents.get(agent_id, {}).get("name", agent_id)
            report += f"- **{agent_name}**: {recommendation['profile']} (confidence: {recommendation['confidence']:.1%})\n"
            report += f"  - Reason: {recommendation['reason']}\n"
        
        report += "\n## Optimization Opportunities\n"
        
        for opportunity in analysis.get("optimization_opportunities", []):
            report += f"### {opportunity['agent']}\n"
            for opt in opportunity["opportunities"]:
                priority_icon = {"high": "🚨", "medium": "⚠️", "low": "💡"}.get(opt["priority"], "•")
                report += f"- {priority_icon} **{opt['type']}**: {opt['description']}\n"
                report += f"  - Action: {opt['action']}\n"
        
        report += "\n## MCP Utilization\n"
        util = analysis.get("mcp_utilization", {})
        report += f"- **Configured MCPs**: {util.get('total_configured', 0)}\n"
        report += f"- **Used MCPs**: {util.get('total_used', 0)}\n"
        
        if util.get("unused_mcps"):
            report += f"- **Unused MCPs**: {', '.join(util['unused_mcps'])}\n"
        
        if util.get("missing_mcps"):
            report += f"- **Missing MCPs**: {', '.join(util['missing_mcps'])}\n"
        
        return report


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Profile Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze profile optimization opportunities")
    analyze_parser.add_argument("--output", help="Output file path")
    analyze_parser.add_argument("--format", choices=["json", "report"], default="report", help="Output format")
    
    # Apply command
    apply_parser = subparsers.add_parser("apply", help="Apply profile optimizations")
    apply_parser.add_argument("--analysis", help="Analysis file to apply optimizations from")
    apply_parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    
    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Show profile information")
    profile_parser.add_argument("--agent", help="Show profile for specific agent")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = MCPProfileManager()
    
    if args.command == "analyze":
        analysis = manager.analyze_profile_optimization()
        
        if args.format == "json":
            output = json.dumps(analysis, indent=2, default=str)
        else:
            output = manager.generate_profile_report(analysis)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"📊 Analysis saved: {args.output}")
        else:
            print(output)
    
    elif args.command == "apply":
        if args.analysis:
            with open(args.analysis) as f:
                analysis = json.load(f)
        else:
            analysis = manager.analyze_profile_optimization()
        
        if args.dry_run:
            print("🔍 Dry run - would apply the following optimizations:")
            for opportunity in analysis.get("optimization_opportunities", []):
                print(f"  • {opportunity['agent']}: {len(opportunity['opportunities'])} optimizations")
        else:
            results = manager.apply_profile_optimizations(analysis)
            print(f"✅ Applied {results['summary']['successful']} optimizations")
            if results['summary']['failed'] > 0:
                print(f"❌ Failed {results['summary']['failed']} optimizations")
    
    elif args.command == "profile":
        if args.agent:
            # Show specific agent profile
            agent_found = False
            for agent_id, agent_info in manager.registry.agents.items():
                if args.agent in agent_info["name"]:
                    analysis = manager.analyze_profile_optimization()
                    profile_info = analysis["profile_recommendations"].get(agent_id, {})
                    print(f"🤖 Agent: {agent_info['name']}")
                    print(f"   Recommended Profile: {profile_info.get('profile', 'unknown')}")
                    print(f"   Confidence: {profile_info.get('confidence', 0):.1%}")
                    print(f"   Reason: {profile_info.get('reason', 'unknown')}")
                    agent_found = True
                    break
            
            if not agent_found:
                print(f"Agent '{args.agent}' not found")
        else:
            # Show all profiles
            profiles = manager.profile_configs.get("mcp_profiles", {})
            print("📋 Available MCP Profiles:")
            for profile_name, profile_config in profiles.items():
                print(f"   • **{profile_name}**: {profile_config.get('description', 'No description')}")
                agents = profile_config.get('agents', [])
                if agents:
                    print(f"     Agents: {', '.join(agents)}")


if __name__ == "__main__":
    main()