#!/usr/bin/env python3
"""
Agent Context & MCP Configuration Audit
Analyzes which agents need proper Huxley context and MCP configurations
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
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
    spec = importlib.util.spec_from_file_location("agent_registry", parent_dir / "tools" / "agent_registry.py")
    registry_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry_module)
    AgentRegistry = registry_module.AgentRegistry
    
except Exception as e:
    print(f"Error importing Huxley modules: {e}")
    sys.exit(1)


class AgentContextAuditor:
    """Audits agent Huxley context and MCP configuration needs"""
    
    def __init__(self):
        self.registry = AgentRegistry()
        self.mcp_matrix = self._load_mcp_matrix()
        self.builder_mcps = self._discover_builder_mcps()
        self.mcp_config = self._load_current_mcp_config()
        
    def _load_mcp_matrix(self) -> Dict[str, Any]:
        """Load Agent-MCP matrix data"""
        matrix_file = paths.base / "global" / "mcp" / "AGENT_MCP_MATRIX.md"
        if not matrix_file.exists():
            return {}
        
        # Parse MCP matrix (simplified - would need full markdown parser for production)
        matrix = {
            "agent_mcps": {
                "automation-specialist": {"core": ["filesystem", "n8n", "applescript"], "optional": ["git"]},
                "shopify-specialist": {"core": ["filesystem", "shopify"], "optional": ["git", "http"]},
                "frontend-specialist": {"core": ["filesystem"], "optional": ["git", "http", "shadcn-ui"]},
                "javascript-pro": {"core": ["filesystem"], "optional": ["git", "http", "shadcn-ui"]},
                "backend-architect": {"core": ["filesystem", "git"], "optional": ["http"]},
                "devops-troubleshooter": {"core": ["filesystem", "git"], "optional": ["http", "ccmem"]},
                "deployment-engineer": {"core": ["filesystem", "git"], "optional": ["http"]},
                "security-auditor": {"core": ["filesystem"], "optional": ["git", "http"]},
                "test-automator": {"core": ["filesystem"], "optional": ["git", "http"]},
                "python-pro": {"core": ["filesystem"], "optional": ["git", "http"]},
                "code-reviewer": {"core": ["filesystem", "git"], "optional": ["http"]},
                "ios-specialist": {"core": ["filesystem"], "optional": ["git", "xcodebuild", "ios-sim"]},
                "macos-specialist": {"core": ["filesystem"], "optional": ["git", "xcodebuild"]},
                "data-analyst": {"core": ["filesystem"], "optional": ["git", "http"]}
            },
            "profiles": {
                "default": ["filesystem", "git", "http", "keychain-presence", "ccmem"],
                "automation": ["filesystem", "git", "http", "keychain-presence", "ccmem", "n8n"],
                "webdev": ["filesystem", "git", "http", "keychain-presence", "ccmem", "shopify", "cms"],
                "apple": ["filesystem", "git", "http", "keychain-presence", "ccmem", "xcodebuild", "ios-sim"]
            }
        }
        return matrix
    
    def _discover_builder_mcps(self) -> List[str]:
        """Discover available Huxley-specific MCPs"""
        builder_mcps = []
        
        # Check for Huxley MCP capsules
        mcp_dirs = [
            "apple-doc-mcp",
            "n8n-mcp", 
            "git-mcp",
            "mcp-server-qdrant",
            "xcodebuildmcp"
        ]
        
        for mcp_dir in mcp_dirs:
            mcp_path = paths.base / "global" / mcp_dir
            if mcp_path.exists():
                builder_mcps.append(mcp_dir.replace("-mcp", "").replace("mcp-server-", ""))
        
        # Check for bridge MCPs
        bridge_mcps = [
            "bridge-mcp",
            "builder-memory",
            "siri-shortcuts",
            "applescript",
            "apple-doc",
            "iterm"
        ]
        
        for bridge_mcp in bridge_mcps:
            bridge_path = paths.base / "tools" / "bridge-mcp"
            if bridge_path.exists():
                builder_mcps.append(bridge_mcp)
        
        return builder_mcps
    
    def _load_current_mcp_config(self) -> Dict[str, Any]:
        """Load current MCP server configuration"""
        mcp_config_file = paths.base / "global" / "claude-config" / "mcp_servers.json"
        if mcp_config_file.exists():
            try:
                with open(mcp_config_file) as f:
                    return json.load(f)
            except:
                pass
        return {"mcpServers": {}}
    
    def audit_agent_configurations(self) -> Dict[str, Any]:
        """Audit all agents for Huxley context and MCP configuration needs"""
        print("🔍 Auditing agent Huxley context and MCP configurations...")
        
        audit_results = {
            "audit_timestamp": datetime.now().isoformat(),
            "total_agents": len(self.registry.agents),
            "configuration_issues": [],
            "missing_builder_context": [],
            "missing_mcp_configs": [],
            "mcp_gaps": {},
            "recommendations": [],
            "summary": {
                "agents_needing_context": 0,
                "agents_needing_mcps": 0,
                "critical_gaps": 0,
                "builder_awareness_score": 0
            }
        }
        
        for agent_id, agent_info in self.registry.agents.items():
            agent_audit = self._audit_single_agent(agent_info)
            
            # Categorize issues
            if agent_audit["needs_builder_context"]:
                audit_results["missing_builder_context"].append(agent_audit)
                audit_results["summary"]["agents_needing_context"] += 1
            
            if agent_audit["needs_mcp_config"]:
                audit_results["missing_mcp_configs"].append(agent_audit)
                audit_results["summary"]["agents_needing_mcps"] += 1
            
            if agent_audit["mcp_gaps"]:
                audit_results["mcp_gaps"][agent_id] = agent_audit["mcp_gaps"]
            
            if agent_audit["critical_issues"]:
                audit_results["configuration_issues"].extend(agent_audit["critical_issues"])
                audit_results["summary"]["critical_gaps"] += len(agent_audit["critical_issues"])
        
        # Calculate Huxley awareness score
        total_agents = len(self.registry.agents)
        if total_agents > 0:
            context_aware_agents = total_agents - audit_results["summary"]["agents_needing_context"]
            audit_results["summary"]["builder_awareness_score"] = (context_aware_agents / total_agents) * 100
        
        # Generate recommendations
        audit_results["recommendations"] = self._generate_configuration_recommendations(audit_results)
        
        return audit_results
    
    def _audit_single_agent(self, agent_info: Dict[str, Any]) -> Dict[str, Any]:
        """Audit single agent for Huxley context and MCP needs"""
        agent_name = agent_info["name"]
        agent_spec = self._load_agent_specification(agent_info)
        
        audit_result = {
            "agent_id": agent_info["id"],
            "agent_name": agent_name,
            "scope": agent_info["scope"],
            "needs_builder_context": False,
            "needs_mcp_config": False,
            "builder_context_score": 0,
            "mcp_gaps": [],
            "critical_issues": [],
            "recommendations": []
        }
        
        # Check Huxley context awareness
        if agent_spec:
            context_indicators = [
                "builder",
                "capsule",
                "dod",
                "definition of done",
                "standard",
                "standard",
                "requirements.yaml"
            ]
            
            found_indicators = sum(1 for indicator in context_indicators 
                                 if indicator.lower() in agent_spec.lower())
            
            audit_result["builder_context_score"] = (found_indicators / len(context_indicators)) * 100
            audit_result["needs_builder_context"] = audit_result["builder_context_score"] < 30
        else:
            audit_result["needs_builder_context"] = True
            audit_result["critical_issues"].append({
                "type": "missing_specification",
                "message": f"Agent {agent_name} has no readable specification"
            })
        
        # Check MCP configuration needs
        expected_mcps = self._get_expected_mcps_for_agent(agent_name)
        configured_mcps = self._get_configured_mcps_for_agent(agent_info)
        
        missing_core_mcps = []
        missing_optional_mcps = []
        
        if expected_mcps:
            for mcp in expected_mcps.get("core", []):
                if mcp not in configured_mcps:
                    missing_core_mcps.append(mcp)
            
            for mcp in expected_mcps.get("optional", []):
                if mcp not in configured_mcps and mcp in self.builder_mcps:
                    missing_optional_mcps.append(mcp)
            
            if missing_core_mcps:
                audit_result["needs_mcp_config"] = True
                audit_result["mcp_gaps"].extend(missing_core_mcps)
                audit_result["critical_issues"].append({
                    "type": "missing_core_mcps",
                    "message": f"Agent {agent_name} missing core MCPs: {', '.join(missing_core_mcps)}"
                })
            
            if missing_optional_mcps:
                audit_result["mcp_gaps"].extend(missing_optional_mcps)
        
        # Check for Huxley-specific requirements
        if agent_info["scope"] == "builder_global" or "builder" in agent_name:
            # Huxley agents should have stronger context requirements
            if audit_result["builder_context_score"] < 50:
                audit_result["critical_issues"].append({
                    "type": "insufficient_builder_context",
                    "message": f"Huxley agent {agent_name} has insufficient Huxley context awareness"
                })
        
        return audit_result
    
    def _load_agent_specification(self, agent_info: Dict[str, Any]) -> Optional[str]:
        """Load agent specification content"""
        try:
            agent_path = Path(agent_info["path"])
            if agent_path.is_file():
                with open(agent_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif agent_path.is_dir():
                prompt_file = agent_path / "prompt.md"
                if prompt_file.exists():
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        return f.read()
        except:
            pass
        return None
    
    def _get_expected_mcps_for_agent(self, agent_name: str) -> Optional[Dict[str, List[str]]]:
        """Get expected MCPs for agent based on matrix"""
        # Normalize agent name for lookup
        normalized_name = agent_name.replace(".", "").replace("-", "-")
        
        # Check direct match first
        if normalized_name in self.mcp_matrix.get("agent_mcps", {}):
            return self.mcp_matrix["agent_mcps"][normalized_name]
        
        # Check partial matches for specialized agents
        for matrix_agent, mcps in self.mcp_matrix.get("agent_mcps", {}).items():
            if matrix_agent.replace("-", "") in normalized_name.replace("-", ""):
                return mcps
        
        return None
    
    def _get_configured_mcps_for_agent(self, agent_info: Dict[str, Any]) -> List[str]:
        """Get currently configured MCPs for agent"""
        configured_mcps = []
        
        # Check agent metadata for tool declarations
        tools = agent_info.get("metadata", {}).get("tools", [])
        
        # Map tools to MCPs
        tool_to_mcp_mapping = {
            "filesystem": "filesystem",
            "git": "git", 
            "webfetch": "http",
            "applescript": "applescript",
            "siri-shortcuts": "siri-shortcuts",
            "apple-doc": "apple-doc",
            "shadcn-ui": "shadcn-ui",
            "xcodebuild": "xcodebuild",
            "n8n": "n8n",
            "shopify": "shopify"
        }
        
        for tool in tools:
            if tool.lower() in tool_to_mcp_mapping:
                configured_mcps.append(tool_to_mcp_mapping[tool.lower()])
        
        # Add MCPs from current configuration
        for server_name in self.mcp_config.get("mcpServers", {}):
            configured_mcps.append(server_name)
        
        return list(set(configured_mcps))
    
    def _generate_configuration_recommendations(self, audit_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate configuration improvement recommendations"""
        recommendations = []
        
        # Huxley context recommendations
        if audit_results["summary"]["agents_needing_context"] > 0:
            recommendations.append({
                "priority": "high",
                "category": "builder_context",
                "title": "Improve Huxley Context Awareness",
                "description": f"{audit_results['summary']['agents_needing_context']} agents lack adequate Huxley context",
                "action": "Update agent specifications to include Huxley-specific terminology and workflows",
                "affected_agents": [agent["agent_name"] for agent in audit_results["missing_builder_context"]]
            })
        
        # MCP configuration recommendations
        if audit_results["summary"]["agents_needing_mcps"] > 0:
            recommendations.append({
                "priority": "high", 
                "category": "mcp_configuration",
                "title": "Configure Missing MCP Access",
                "description": f"{audit_results['summary']['agents_needing_mcps']} agents missing required MCP configurations",
                "action": "Add missing MCPs to agent tool declarations and system configuration",
                "affected_agents": [agent["agent_name"] for agent in audit_results["missing_mcp_configs"]]
            })
        
        # Critical gap recommendations
        if audit_results["summary"]["critical_gaps"] > 0:
            recommendations.append({
                "priority": "critical",
                "category": "critical_gaps",
                "title": "Address Critical Configuration Gaps",
                "description": f"{audit_results['summary']['critical_gaps']} critical configuration issues found",
                "action": "Immediately address missing specifications and core MCP requirements",
                "details": audit_results["configuration_issues"]
            })
        
        # Huxley-specific MCP recommendations
        builder_specific_mcps = ["builder-memory", "apple-doc", "siri-shortcuts", "applescript"]
        missing_builder_mcps = [mcp for mcp in builder_specific_mcps if mcp not in self.mcp_config.get("mcpServers", {})]
        
        if missing_builder_mcps:
            recommendations.append({
                "priority": "medium",
                "category": "builder_mcps",
                "title": "Enable Huxley-Specific MCPs",
                "description": f"Huxley MCPs not configured: {', '.join(missing_builder_mcps)}",
                "action": "Configure Huxley-specific MCP servers for enhanced capabilities",
                "missing_mcps": missing_builder_mcps
            })
        
        # Profile optimization recommendations
        agent_profiles = self._analyze_agent_profile_needs()
        if agent_profiles["optimization_opportunities"]:
            recommendations.append({
                "priority": "medium",
                "category": "profile_optimization",
                "title": "Optimize MCP Profile Usage",
                "description": "Agents could benefit from specialized MCP profiles",
                "action": "Consider using specialized profiles (automation, webdev, apple) for better MCP alignment",
                "opportunities": agent_profiles["optimization_opportunities"]
            })
        
        return recommendations
    
    def _analyze_agent_profile_needs(self) -> Dict[str, Any]:
        """Analyze agent profile optimization opportunities"""
        profile_analysis = {
            "current_distribution": {},
            "optimization_opportunities": []
        }
        
        # Count agents by suggested profile
        profile_suggestions = {}
        for agent_id, agent_info in self.registry.agents.items():
            agent_name = agent_info["name"]
            suggested_profile = self._suggest_profile_for_agent(agent_name)
            
            if suggested_profile not in profile_suggestions:
                profile_suggestions[suggested_profile] = []
            profile_suggestions[suggested_profile].append(agent_name)
        
        # Identify optimization opportunities
        for profile, agents in profile_suggestions.items():
            if profile != "default" and len(agents) >= 2:
                profile_analysis["optimization_opportunities"].append({
                    "profile": profile,
                    "agents": agents,
                    "benefit": f"Specialized {profile} profile would provide optimized MCP access for {len(agents)} agents"
                })
        
        profile_analysis["current_distribution"] = profile_suggestions
        return profile_analysis
    
    def _suggest_profile_for_agent(self, agent_name: str) -> str:
        """Suggest optimal MCP profile for agent"""
        if "automation" in agent_name or "n8n" in agent_name:
            return "automation"
        elif any(web_term in agent_name for web_term in ["frontend", "shopify", "web", "javascript"]):
            return "webdev"
        elif any(apple_term in agent_name for apple_term in ["ios", "macos", "xcode"]):
            return "apple"
        else:
            return "default"
    
    def generate_configuration_fixes(self, audit_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate specific configuration fixes"""
        fixes = {
            "agent_updates": [],
            "mcp_additions": [],
            "context_improvements": []
        }
        
        # Generate agent specification updates
        for agent_audit in audit_results["missing_builder_context"]:
            fixes["context_improvements"].append({
                "agent": agent_audit["agent_name"],
                "current_score": agent_audit["builder_context_score"],
                "required_additions": [
                    "Add Huxley capsule workflow understanding",
                    "Include DoD integration capabilities",
                    "Reference lane-specific processes (standard/standard)",
                    "Mention requirements.yaml integration"
                ]
            })
        
        # Generate MCP configuration additions
        for agent_audit in audit_results["missing_mcp_configs"]:
            if agent_audit["mcp_gaps"]:
                fixes["mcp_additions"].append({
                    "agent": agent_audit["agent_name"],
                    "missing_mcps": agent_audit["mcp_gaps"],
                    "configuration_update": {
                        "tools": agent_audit["mcp_gaps"]
                    }
                })
        
        return fixes


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Context & MCP Configuration Audit")
    parser.add_argument("--output", help="Output file path for audit results")
    parser.add_argument("--format", choices=["json", "report"], default="report", help="Output format")
    parser.add_argument("--fixes", action="store_true", help="Generate configuration fixes")
    
    args = parser.parse_args()
    
    auditor = AgentContextAuditor()
    audit_results = auditor.audit_agent_configurations()
    
    if args.format == "json":
        output = json.dumps(audit_results, indent=2, default=str)
    else:
        output = generate_report(audit_results)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(output)
        print(f"📄 Audit results saved: {output_path}")
    else:
        print(output)
    
    if args.fixes:
        fixes = auditor.generate_configuration_fixes(audit_results)
        fixes_file = Path(args.output).with_name("configuration_fixes.json") if args.output else Path("configuration_fixes.json")
        with open(fixes_file, 'w') as f:
            json.dump(fixes, f, indent=2)
        print(f"🔧 Configuration fixes saved: {fixes_file}")


def generate_report(audit_results: Dict[str, Any]) -> str:
    """Generate human-readable audit report"""
    report = f"""
🔍 Agent Context & MCP Configuration Audit Report

## Summary
- **Total Agents**: {audit_results['total_agents']}
- **Agents Needing Context**: {audit_results['summary']['agents_needing_context']}
- **Agents Needing MCPs**: {audit_results['summary']['agents_needing_mcps']}
- **Critical Gaps**: {audit_results['summary']['critical_gaps']}
- **Huxley Awareness Score**: {audit_results['summary']['builder_awareness_score']:.1f}/100

## ⚠️ Missing Huxley Context
"""
    
    for agent in audit_results["missing_builder_context"]:
        report += f"- **{agent['agent_name']}** (Score: {agent['builder_context_score']:.1f}/100)\n"
        report += f"  - Scope: {agent['scope']}\n"
        if agent.get("recommendations"):
            report += f"  - Needs: {', '.join(agent['recommendations'])}\n"
        report += "\n"
    
    report += "## 🔌 Missing MCP Configurations\n"
    
    for agent in audit_results["missing_mcp_configs"]:
        report += f"- **{agent['agent_name']}**\n"
        if agent["mcp_gaps"]:
            report += f"  - Missing MCPs: {', '.join(agent['mcp_gaps'])}\n"
        report += "\n"
    
    if audit_results["recommendations"]:
        report += "## 💡 Recommendations\n"
        for rec in audit_results["recommendations"]:
            priority_icon = {"critical": "🚨", "high": "⚠️", "medium": "💡"}.get(rec["priority"], "•")
            report += f"- {priority_icon} **{rec['title']}** ({rec['priority']})\n"
            report += f"  - {rec['description']}\n"
            report += f"  - Action: {rec['action']}\n"
            report += "\n"
    
    return report


if __name__ == "__main__":
    main()