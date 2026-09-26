#!/usr/bin/env python3
"""
Claude Code Agent Audit System
Comprehensive audit of all Claude Code agents in Huxley
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import re
import subprocess

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


class ClaudeAgentAuditor:
    """Audits Claude Code agents across the Huxley system"""
    
    def __init__(self):
        self.agents_found = []
        self.agent_configs = {}
        self.issues = []
        self.recommendations = []
        self.native_agents = [
            "Code Reviewer", "Debugger", "System Architect", "Security Analyst",
            "Performance Optimizer", "Frontend Specialist", "Backend Architect",
            "Test Automator", "Deployment Engineer", "Security Auditor"
        ]
    
    def audit_system(self) -> Dict[str, Any]:
        """Perform comprehensive agent audit"""
        print("🔍 Auditing Claude Code agents in Huxley...")
        
        # Scan for agent configurations
        self._scan_global_agent_configs()
        self._scan_capsule_agent_configs()
        self._scan_template_agent_configs()
        self._scan_mcp_agent_integrations()
        
        # Analyze agent usage patterns
        self._analyze_agent_usage()
        self._check_agent_consistency()
        self._validate_agent_specifications()
        
        # Security and compliance checks
        self._security_audit()
        self._compliance_check()
        
        # Generate recommendations
        self._generate_recommendations()
        
        return self._compile_audit_report()
    
    def _scan_global_agent_configs(self):
        """Scan global Claude agent configurations"""
        print("  📂 Scanning global agent configs...")
        
        # Check ~/.claude/agents/ directory
        global_agents_dir = Path.home() / ".claude" / "agents"
        if global_agents_dir.exists():
            for item in global_agents_dir.iterdir():
                if item.is_dir():
                    self._process_agent_directory(item, "global")
                elif item.suffix == '.md' and item.name != 'README.md':
                    self._process_agent_file(item, "global")
        
        # Check Huxley global agents
        builder_agents_dir = paths.base / ".claude" / "agents"
        if builder_agents_dir.exists():
            for item in builder_agents_dir.iterdir():
                if item.is_dir():
                    self._process_agent_directory(item, "builder_global")
                elif item.suffix == '.md' and item.name != 'README.md':
                    self._process_agent_file(item, "builder_global")
    
    def _scan_capsule_agent_configs(self):
        """Scan capsule-specific agent configurations"""
        print("  🏗️ Scanning capsule agent configs...")
        
        for capsule_dir in paths.capsules.iterdir():
            if not capsule_dir.is_dir() or capsule_dir.name.startswith('.'):
                continue
            
            agents_dir = capsule_dir / ".claude" / "agents"
            if agents_dir.exists():
                for agent_dir in agents_dir.iterdir():
                    if agent_dir.is_dir():
                        self._process_agent_directory(agent_dir, "capsule", capsule_dir.name)
    
    def _scan_template_agent_configs(self):
        """Scan template agent configurations"""
        print("  📋 Scanning template agent configs...")
        
        templates_dir = paths.base / "templates"
        if templates_dir.exists():
            for template_dir in templates_dir.iterdir():
                if not template_dir.is_dir():
                    continue
                
                agents_dir = template_dir / ".claude" / "agents"
                if agents_dir.exists():
                    for agent_dir in agents_dir.iterdir():
                        if agent_dir.is_dir():
                            self._process_agent_directory(agent_dir, "template", template_dir.name)
    
    def _process_agent_directory(self, agent_dir: Path, scope: str, context: str = None):
        """Process individual agent directory"""
        agent_name = agent_dir.name
        agent_info = {
            "name": agent_name,
            "scope": scope,
            "context": context,
            "path": str(agent_dir),
            "files": {},
            "valid": True,
            "issues": []
        }
        
        # Check for required files
        prompt_file = agent_dir / "prompt.md"
        config_file = agent_dir / "config.json"
        
        if prompt_file.exists():
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    agent_info["files"]["prompt"] = {
                        "content": f.read(),
                        "size": prompt_file.stat().st_size,
                        "modified": datetime.fromtimestamp(prompt_file.stat().st_mtime).isoformat()
                    }
            except Exception as e:
                agent_info["issues"].append(f"Cannot read prompt.md: {e}")
                agent_info["valid"] = False
        else:
            agent_info["issues"].append("Missing prompt.md file")
            agent_info["valid"] = False
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    agent_info["files"]["config"] = config_data
            except Exception as e:
                agent_info["issues"].append(f"Invalid config.json: {e}")
                agent_info["valid"] = False
        
        # Check for additional files
        for file_path in agent_dir.rglob("*"):
            if file_path.is_file() and file_path.name not in ["prompt.md", "config.json"]:
                rel_path = file_path.relative_to(agent_dir)
                agent_info["files"][str(rel_path)] = {
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                }
        
        self.agents_found.append(agent_info)
    
    def _process_agent_file(self, agent_file: Path, scope: str, context: str = None):
        """Process individual agent markdown file (Huxley format)"""
        agent_name = agent_file.stem
        agent_info = {
            "name": agent_name,
            "scope": scope,
            "context": context,
            "path": str(agent_file),
            "format": "markdown_file",
            "files": {},
            "valid": True,
            "issues": []
        }
        
        try:
            with open(agent_file, 'r', encoding='utf-8') as f:
                content = f.read()
                agent_info["files"]["agent_spec"] = {
                    "content": content,
                    "size": agent_file.stat().st_size,
                    "modified": datetime.fromtimestamp(agent_file.stat().st_mtime).isoformat()
                }
            
            # Parse agent specialization from filename
            if '.' in agent_name:
                parts = agent_name.split('.')
                agent_info["specialization"] = parts[1] if len(parts) > 1 else None
            
            # Basic content validation
            if len(content) < 100:
                agent_info["issues"].append("Agent specification very short")
                agent_info["valid"] = False
            
        except Exception as e:
            agent_info["issues"].append(f"Cannot read agent file: {e}")
            agent_info["valid"] = False
        
        self.agents_found.append(agent_info)
    
    def _scan_mcp_agent_integrations(self):
        """Scan MCP server integrations that might affect agents"""
        print("  🔌 Scanning MCP agent integrations...")
        
        mcp_config_file = paths.base / "global" / "claude-config" / "mcp_servers.json"
        if mcp_config_file.exists():
            try:
                with open(mcp_config_file) as f:
                    mcp_data = json.load(f)
                
                for server_name, config in mcp_data.get("mcpServers", {}).items():
                    if "agent" in server_name.lower() or "claude" in server_name.lower():
                        self.agent_configs["mcp_" + server_name] = {
                            "type": "mcp_integration",
                            "config": config,
                            "scope": "global"
                        }
            except Exception as e:
                self.issues.append(f"Error reading MCP config: {e}")
    
    def _analyze_agent_usage(self):
        """Analyze agent usage patterns"""
        print("  📊 Analyzing agent usage patterns...")
        
        # Count agents by scope
        scope_counts = {}
        for agent in self.agents_found:
            scope = agent["scope"]
            scope_counts[scope] = scope_counts.get(scope, 0) + 1
        
        # Check for duplicate agent names
        name_counts = {}
        for agent in self.agents_found:
            name = agent["name"]
            if name in name_counts:
                name_counts[name].append(agent)
            else:
                name_counts[name] = [agent]
        
        # Flag duplicates
        for name, agents in name_counts.items():
            if len(agents) > 1:
                self.issues.append({
                    "type": "duplicate_agents",
                    "severity": "medium",
                    "message": f"Duplicate agent name '{name}' found in {len(agents)} locations",
                    "details": [
                        f"{agent['scope']}" + (f":{agent['context']}" if agent['context'] else "")
                        for agent in agents
                    ]
                })
    
    def _check_agent_consistency(self):
        """Check consistency across agent configurations"""
        print("  ⚖️ Checking agent consistency...")
        
        # Check for consistent naming patterns
        for agent in self.agents_found:
            name = agent["name"]
            
            # Check naming convention (allow dots for specialization)
            if not re.match(r'^[a-z0-9-_.]+$', name):
                self.issues.append({
                    "type": "naming_convention",
                    "severity": "low",
                    "message": f"Agent name '{name}' doesn't follow naming convention",
                    "location": f"{agent['scope']}:{agent.get('context', '')}"
                })
            
            # Check for consistent file structure - handle both formats
            has_specification = (
                agent["files"].get("prompt") or 
                agent["files"].get("agent_spec") or 
                agent.get("format") == "markdown_file"
            )
            
            if not has_specification:
                self.issues.append({
                    "type": "missing_specification",
                    "severity": "high", 
                    "message": f"Agent '{name}' missing specification file",
                    "location": f"{agent['scope']}:{agent.get('context', '')}"
                })
    
    def _validate_agent_specifications(self):
        """Validate agent prompt specifications"""
        print("  📋 Validating agent specifications...")
        
        for agent in self.agents_found:
            # Handle both directory format (prompt.md) and file format (agent_spec)
            content = None
            if agent["files"].get("prompt"):
                content = agent["files"]["prompt"]["content"]
            elif agent["files"].get("agent_spec"):
                content = agent["files"]["agent_spec"]["content"]
            
            if not content:
                continue
            
            # Parse YAML frontmatter if present
            yaml_frontmatter = {}
            if content.startswith('---'):
                try:
                    import yaml
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        yaml_frontmatter = yaml.safe_load(parts[1])
                except:
                    pass
            
            # Check for required sections - adapt for Huxley format
            builder_sections = ["Mission", "Responsibilities", "Process", "Standards"]
            traditional_sections = ["Purpose", "Capabilities", "Instructions"]
            
            # Check for either Huxley format or traditional format
            has_builder_format = any(section.lower() in content.lower() for section in builder_sections)
            has_traditional_format = any(section.lower() in content.lower() for section in traditional_sections)
            has_yaml_metadata = bool(yaml_frontmatter.get('name') or yaml_frontmatter.get('description'))
            
            missing_sections = []
            if not (has_builder_format or has_traditional_format or has_yaml_metadata):
                missing_sections = ["structured sections or YAML metadata"]
            
            if missing_sections:
                self.issues.append({
                    "type": "incomplete_specification",
                    "severity": "medium",
                    "message": f"Agent '{agent['name']}' missing sections: {', '.join(missing_sections)}",
                    "location": f"{agent['scope']}:{agent.get('context', '')}"
                })
            
            # Check prompt length (too short or too long)
            content_length = len(content)
            if content_length < 100:
                self.issues.append({
                    "type": "prompt_too_short",
                    "severity": "medium",
                    "message": f"Agent '{agent['name']}' specification very short ({content_length} chars)",
                    "location": f"{agent['scope']}:{agent.get('context', '')}"
                })
            elif content_length > 8000:
                self.issues.append({
                    "type": "prompt_too_long",
                    "severity": "low",
                    "message": f"Agent '{agent['name']}' specification very long ({content_length} chars)",
                    "location": f"{agent['scope']}:{agent.get('context', '')}"
                })
    
    def _security_audit(self):
        """Perform security audit on agent configurations"""
        print("  🔒 Performing security audit...")
        
        for agent in self.agents_found:
            # Check for potential security issues in prompts/specs
            content = None
            if agent["files"].get("prompt", {}).get("content"):
                content = agent["files"]["prompt"]["content"]
            elif agent["files"].get("agent_spec", {}).get("content"):
                content = agent["files"]["agent_spec"]["content"]
            
            if content:
                
                # Check for hardcoded credentials or paths
                security_patterns = [
                    (r'password\s*[:=]\s*["\']?[\w\-\.]+["\']?', "potential_password"),
                    (r'api[_-]?key\s*[:=]\s*["\']?[\w\-\.]+["\']?', "potential_api_key"),
                    (r'token\s*[:=]\s*["\']?[\w\-\.]+["\']?', "potential_token"),
                    (r'/Users/\w+', "hardcoded_user_path"),
                    (r'[A-Za-z]:\\\\[\\w\\]+', "hardcoded_windows_path")
                ]
                
                for pattern, issue_type in security_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        self.issues.append({
                            "type": "security_risk",
                            "severity": "high",
                            "message": f"Agent '{agent['name']}' may contain {issue_type.replace('_', ' ')}",
                            "location": f"{agent['scope']}:{agent.get('context', '')}"
                        })
            
            # Check file permissions on agent directories
            try:
                agent_path = Path(agent["path"])
                stat = agent_path.stat()
                # Check if directory is world-readable
                if stat.st_mode & 0o004:
                    self.issues.append({
                        "type": "permission_security",
                        "severity": "medium",
                        "message": f"Agent '{agent['name']}' directory is world-readable",
                        "location": agent["path"]
                    })
            except Exception:
                pass
    
    def _compliance_check(self):
        """Check compliance with Huxley standards"""
        print("  ✅ Checking Huxley compliance...")
        
        # Check if native agents are being overridden appropriately
        for agent in self.agents_found:
            if agent["name"] in [name.lower().replace(" ", "-") for name in self.native_agents]:
                if agent["scope"] == "global":
                    self.issues.append({
                        "type": "native_override",
                        "severity": "medium",
                        "message": f"Agent '{agent['name']}' overrides native Claude Code agent globally",
                        "location": f"{agent['scope']}:{agent.get('context', '')}"
                    })
        
        # Check for agents without clear scope definition
        capsule_agents = [a for a in self.agents_found if a["scope"] == "capsule"]
        global_agents = [a for a in self.agents_found if a["scope"] in ["global", "builder_global"]]
        
        if len(capsule_agents) == 0 and len(global_agents) > 5:
            self.recommendations.append({
                "type": "architecture",
                "priority": "medium",
                "message": "Consider creating capsule-specific agents for specialized workflows",
                "details": "Many global agents may indicate need for more targeted capsule agents"
            })
    
    def _generate_recommendations(self):
        """Generate improvement recommendations"""
        print("  💡 Generating recommendations...")
        
        # Analyze agent distribution
        scope_counts = {}
        for agent in self.agents_found:
            scope = agent["scope"]
            scope_counts[scope] = scope_counts.get(scope, 0) + 1
        
        # Recommend agent standardization
        if len(set(a["name"] for a in self.agents_found)) != len(self.agents_found):
            self.recommendations.append({
                "type": "standardization",
                "priority": "high",
                "message": "Implement agent naming and versioning standards",
                "details": "Multiple agents with same names found across scopes"
            })
        
        # Check for missing common agents
        common_agents = ["security-auditor", "performance-optimizer", "code-reviewer"]
        found_names = set(a["name"] for a in self.agents_found)
        
        missing_common = [name for name in common_agents if name not in found_names]
        if missing_common:
            self.recommendations.append({
                "type": "coverage",
                "priority": "medium",
                "message": f"Consider adding common agents: {', '.join(missing_common)}",
                "details": "These agents are commonly useful across Huxley workflows"
            })
        
        # Performance recommendations
        large_prompts = [a for a in self.agents_found 
                        if a["files"].get("prompt", {}).get("content") and 
                        len(a["files"]["prompt"]["content"]) > 5000]
        
        if large_prompts:
            self.recommendations.append({
                "type": "performance",
                "priority": "low",
                "message": f"{len(large_prompts)} agents have very large prompts",
                "details": "Consider breaking down large prompts for better performance"
            })
    
    def _compile_audit_report(self) -> Dict[str, Any]:
        """Compile comprehensive audit report"""
        return {
            "audit_timestamp": datetime.now().isoformat(),
            "summary": {
                "total_agents": len(self.agents_found),
                "valid_agents": len([a for a in self.agents_found if a["valid"]]),
                "total_issues": len(self.issues),
                "high_severity_issues": len([i for i in self.issues if i.get("severity") == "high"]),
                "scope_distribution": self._get_scope_distribution(),
                "agent_health_score": self._calculate_health_score()
            },
            "agents": self.agents_found,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "compliance": {
                "naming_compliance": self._check_naming_compliance(),
                "security_compliance": self._check_security_compliance(),
                "structure_compliance": self._check_structure_compliance()
            },
            "next_actions": self._generate_next_actions()
        }
    
    def _get_scope_distribution(self) -> Dict[str, int]:
        """Get agent distribution by scope"""
        distribution = {}
        for agent in self.agents_found:
            scope = agent["scope"]
            distribution[scope] = distribution.get(scope, 0) + 1
        return distribution
    
    def _calculate_health_score(self) -> float:
        """Calculate overall agent health score (0-100)"""
        if not self.agents_found:
            return 0.0
        
        total_agents = len(self.agents_found)
        valid_agents = len([a for a in self.agents_found if a["valid"]])
        
        # Base score from validity
        validity_score = (valid_agents / total_agents) * 50
        
        # Score from having specifications
        agents_with_specs = len([a for a in self.agents_found 
                               if a["files"].get("prompt") or a["files"].get("agent_spec")])
        spec_score = (agents_with_specs / total_agents) * 30
        
        # Score from naming consistency
        properly_named = len([a for a in self.agents_found 
                            if re.match(r'^[a-z0-9-_.]+$', a["name"])])
        naming_score = (properly_named / total_agents) * 10
        
        # Score from YAML metadata (Huxley format bonus)
        agents_with_metadata = 0
        for agent in self.agents_found:
            content = (agent["files"].get("agent_spec", {}).get("content", "") or 
                      agent["files"].get("prompt", {}).get("content", ""))
            if content.startswith('---'):
                agents_with_metadata += 1
        
        metadata_score = (agents_with_metadata / total_agents) * 10
        
        # Deduct for genuine high severity issues (not format differences)
        real_high_issues = len([i for i in self.issues 
                               if i.get("severity") == "high" 
                               and i.get("type") not in ["missing_prompt", "missing_specification"]])
        severity_penalty = min(real_high_issues * 5, 20)
        
        total_score = validity_score + spec_score + naming_score + metadata_score - severity_penalty
        return max(0, min(100, total_score))
    
    def _check_naming_compliance(self) -> Dict[str, Any]:
        """Check naming convention compliance"""
        compliant = 0
        total = len(self.agents_found)
        
        for agent in self.agents_found:
            if re.match(r'^[a-z0-9-_]+$', agent["name"]):
                compliant += 1
        
        return {
            "compliant_agents": compliant,
            "total_agents": total,
            "compliance_percentage": (compliant / total * 100) if total > 0 else 0
        }
    
    def _check_security_compliance(self) -> Dict[str, Any]:
        """Check security compliance"""
        security_issues = [i for i in self.issues if i.get("type") == "security_risk"]
        return {
            "agents_with_security_issues": len(set(i.get("location", "") for i in security_issues)),
            "total_security_issues": len(security_issues),
            "security_score": max(0, 100 - len(security_issues) * 10)
        }
    
    def _check_structure_compliance(self) -> Dict[str, Any]:
        """Check structural compliance"""
        agents_with_prompts = len([a for a in self.agents_found if a["files"].get("prompt")])
        total_agents = len(self.agents_found)
        
        return {
            "agents_with_prompts": agents_with_prompts,
            "total_agents": total_agents,
            "structure_compliance_percentage": (agents_with_prompts / total_agents * 100) if total_agents > 0 else 0
        }
    
    def _generate_next_actions(self) -> List[str]:
        """Generate prioritized next actions"""
        actions = []
        
        high_severity_issues = [i for i in self.issues if i.get("severity") == "high"]
        if high_severity_issues:
            actions.append(f"🚨 Address {len(high_severity_issues)} high-severity issues immediately")
        
        security_issues = [i for i in self.issues if i.get("type") == "security_risk"]
        if security_issues:
            actions.append(f"🔒 Review and fix {len(security_issues)} security concerns")
        
        invalid_agents = [a for a in self.agents_found if not a["valid"]]
        if invalid_agents:
            actions.append(f"🔧 Fix {len(invalid_agents)} invalid agent configurations")
        
        if len(self.recommendations) > 0:
            high_priority_recs = [r for r in self.recommendations if r.get("priority") == "high"]
            if high_priority_recs:
                actions.append(f"💡 Implement {len(high_priority_recs)} high-priority recommendations")
        
        return actions[:5]  # Limit to top 5 actions


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Agent Audit System")
    parser.add_argument("--output", "-o", help="Output file path for audit report")
    parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    auditor = ClaudeAgentAuditor()
    report = auditor.audit_system()
    
    # Display summary
    print(f"\n📊 Agent Audit Summary:")
    print(f"   Total Agents: {report['summary']['total_agents']}")
    print(f"   Valid Agents: {report['summary']['valid_agents']}")
    print(f"   Health Score: {report['summary']['agent_health_score']:.1f}/100")
    print(f"   Issues Found: {report['summary']['total_issues']} ({report['summary']['high_severity_issues']} high severity)")
    
    # Show scope distribution
    print(f"\n🎯 Agent Distribution:")
    for scope, count in report['summary']['scope_distribution'].items():
        print(f"   {scope}: {count}")
    
    # Show top issues
    if report['issues']:
        print(f"\n⚠️  Top Issues:")
        for issue in sorted(report['issues'], key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x.get("severity", "low"), 1), reverse=True)[:5]:
            severity_icon = {"high": "🚨", "medium": "⚠️", "low": "ℹ️"}.get(issue.get("severity", "low"), "ℹ️")
            print(f"   {severity_icon} {issue.get('message', 'Unknown issue')}")
    
    # Show next actions
    if report['next_actions']:
        print(f"\n📋 Next Actions:")
        for action in report['next_actions']:
            print(f"   • {action}")
    
    # Save report
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = paths.registry / f"claude_agent_audit_{timestamp}.json"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if args.format == "json":
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
    else:
        # Generate markdown report
        with open(output_path.with_suffix('.md'), 'w') as f:
            f.write("# Claude Code Agent Audit Report\n\n")
            f.write(f"Generated: {report['audit_timestamp']}\n\n")
            f.write(f"## Summary\n")
            f.write(f"- **Total Agents:** {report['summary']['total_agents']}\n")
            f.write(f"- **Valid Agents:** {report['summary']['valid_agents']}\n")
            f.write(f"- **Health Score:** {report['summary']['agent_health_score']:.1f}/100\n")
            f.write(f"- **Issues:** {report['summary']['total_issues']} ({report['summary']['high_severity_issues']} high severity)\n\n")
            
            # Add more markdown sections as needed
    
    print(f"\n📄 Audit report saved: {output_path}")


if __name__ == "__main__":
    main()