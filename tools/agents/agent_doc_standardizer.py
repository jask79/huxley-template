#!/usr/bin/env python3
"""
Agent Documentation Standardizer
Standardizes Claude Code agent documentation format across Huxley
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
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
except Exception as e:
    print(f"Error importing Huxley modules: {e}")
    sys.exit(1)


class AgentDocStandardizer:
    """Standardizes agent documentation format"""
    
    STANDARD_TEMPLATE = '''---
name: {name}
description: {description}
tools: {tools}
lane: {lane}
branch: {branch}
targets: {targets}
---

# {display_name}

## Mission
{mission}

## Responsibilities
{responsibilities}

## Process
{process}

## Standards
{standards}

## Tools & Capabilities
{tools_section}

## Lane/Branch Specialization
{specialization}

## Definition of Done Contributions
{dod_contributions}
'''

    def __init__(self):
        self.standards_file = paths.registry / "agent_documentation_standards.json"
        self.template_dir = paths.base / "templates" / "agent_templates"
        self.validation_rules = self._load_validation_rules()
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load documentation validation rules"""
        return {
            "required_sections": [
                "Mission", "Responsibilities", "Process", "Standards"
            ],
            "required_yaml_fields": [
                "name", "description", "tools"
            ],
            "optional_yaml_fields": [
            ],
            "min_section_length": 50,
            "max_section_length": 2000,
            "required_dod_contributions": True,
            "tools_format": "array",
            "naming_pattern": r"^[a-z0-9-]+(\.[a-z0-9-]+)*$"
        }
    
    def create_standard_template(self, agent_name: str, **kwargs) -> str:
        """Create standardized agent documentation"""
        
        # Set defaults
        defaults = {
            "name": agent_name,
            "display_name": kwargs.get("display_name", agent_name.replace("-", " ").title()),
            "description": kwargs.get("description", f"Specialized agent for {agent_name.replace('-', ' ')} tasks"),
            "tools": json.dumps(kwargs.get("tools", ["filesystem", "write", "edit"])),
            "branch": kwargs.get("branch", ""),
            "targets": json.dumps(kwargs.get("targets", [])),
            "mission": kwargs.get("mission", f"Primary responsibility for {agent_name.replace('-', ' ')} operations in Huxley capsules."),
            "responsibilities": kwargs.get("responsibilities", self._generate_default_responsibilities(agent_name)),
            "process": kwargs.get("process", self._generate_default_process(agent_name)),
            "standards": kwargs.get("standards", self._generate_default_standards(agent_name)),
            "tools_section": kwargs.get("tools_section", self._generate_tools_section(kwargs.get("tools", []))),
            "dod_contributions": kwargs.get("dod_contributions", self._generate_dod_contributions(agent_name))
        }
        
        return self.STANDARD_TEMPLATE.format(**defaults)
    
    def _generate_default_responsibilities(self, agent_name: str) -> str:
        """Generate default responsibilities based on agent name"""
        base_responsibilities = {
            "security": "- Threat assessment and vulnerability analysis\n- Security architecture review\n- Compliance validation",
            "frontend": "- UI/UX implementation and optimization\n- Frontend performance monitoring\n- Accessibility compliance",
            "backend": "- API design and architecture\n- Database optimization\n- Scalability planning",
            "devops": "- Deployment pipeline management\n- Infrastructure monitoring\n- Incident response",
            "test": "- Test strategy development\n- Test automation\n- Quality assurance"
        }
        
        for key, responsibilities in base_responsibilities.items():
            if key in agent_name:
                return responsibilities
        
        return f"- {agent_name.replace('-', ' ').title()} operations\n- Quality assurance\n- Best practices compliance"
    
    def _generate_default_process(self, agent_name: str) -> str:
        """Generate default process section"""
        return f"""1. **Analysis**: Review {agent_name.replace('-', ' ')} requirements
2. **Planning**: Develop implementation strategy
3. **Execution**: Implement solutions following Huxley standards
4. **Validation**: Verify compliance with DoD requirements
5. **Documentation**: Update relevant documentation"""
    
    def _generate_default_standards(self, agent_name: str) -> str:
        """Generate default standards section"""
        return f"""- Follow Huxley capsule-centric architecture
- Maintain compatibility with standard and standard workflows
- Ensure all outputs are production-ready
- Document decisions and rationale
- Integrate with existing Huxley tooling"""
    
    def _generate_tools_section(self, tools: List[str]) -> str:
        """Generate tools section based on available tools"""
        if not tools:
            return "- Standard Huxley tools (filesystem, write, edit)"
        
        tool_descriptions = {
            "filesystem": "File system operations and navigation",
            "write": "File creation and modification",
            "edit": "Precise file editing capabilities",
            "bash": "Command line operations and script execution", 
            "webfetch": "External API and web resource access",
            "git": "Version control operations",
            "grep": "Code search and pattern matching"
        }
        
        tool_list = []
        for tool in tools:
            desc = tool_descriptions.get(tool, f"{tool.title()} operations")
            tool_list.append(f"- **{tool}**: {desc}")
        
        return "\n".join(tool_list)
    
    def _generate_specialization_section(self, lane: Optional[str], branch: Optional[str]) -> str:
        """Generate lane/branch specialization section"""
        sections = []
        
        if lane:
            lane_desc = {
                "standard": "Optimized for rapid iteration and quick delivery",
                "standard": "Enhanced quality assurance and production readiness"
            }
            sections.append(f"**Lane Specialization ({lane})**: {lane_desc.get(lane, f'Specialized for {lane} workflows')}")
        
        if branch:
            branch_desc = {
                "web": "Web application development and optimization",
                "mobile": "Mobile application development",
                "desktop": "Desktop application development",
                "analytics": "Data analysis and business intelligence"
            }
            sections.append(f"**Branch Specialization ({branch})**: {branch_desc.get(branch, f'Specialized for {branch} development')}")
        
        return "\n\n".join(sections) if sections else "General purpose agent suitable for all Huxley workflows"
    
    def _generate_dod_contributions(self, agent_name: str) -> str:
        """Generate DoD contributions section"""
        dod_templates = {
            "security": """- [ ] Security threat model completed
- [ ] Vulnerability assessment passed  
- [ ] Security controls implemented
- [ ] Compliance requirements validated""",
            "frontend": """- [ ] UI/UX requirements satisfied
- [ ] Performance benchmarks met
- [ ] Accessibility standards compliance
- [ ] Cross-browser compatibility verified""",
            "backend": """- [ ] API design reviewed and approved
- [ ] Database schema optimized
- [ ] Performance requirements met
- [ ] Scalability considerations addressed""",
            "test": """- [ ] Test coverage targets achieved
- [ ] All tests passing
- [ ] Performance tests completed
- [ ] Integration tests validated"""
        }
        
        for key, dod in dod_templates.items():
            if key in agent_name:
                return dod
        
        return f"""- [ ] {agent_name.replace('-', ' ').title()} requirements completed
- [ ] Quality standards met
- [ ] Documentation updated
- [ ] Integration validated"""
    
    def validate_agent_documentation(self, file_path: Path) -> Dict[str, Any]:
        """Validate agent documentation against standards"""
        validation_result = {
            "file": str(file_path),
            "valid": True,
            "issues": [],
            "score": 100,
            "recommendations": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Cannot read file: {e}")
            validation_result["score"] = 0
            return validation_result
        
        # Validate YAML frontmatter
        frontmatter = {}
        if content.startswith('---'):
            try:
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    content_body = parts[2]
                else:
                    validation_result["issues"].append("Malformed YAML frontmatter")
                    validation_result["score"] -= 20
            except Exception as e:
                validation_result["issues"].append(f"Invalid YAML frontmatter: {e}")
                validation_result["score"] -= 30
        else:
            validation_result["issues"].append("Missing YAML frontmatter")
            validation_result["score"] -= 40
            content_body = content
        
        # Check required YAML fields
        for field in self.validation_rules["required_yaml_fields"]:
            if field not in frontmatter:
                validation_result["issues"].append(f"Missing required YAML field: {field}")
                validation_result["score"] -= 10
        
        # Validate agent name format
        agent_name = frontmatter.get("name", file_path.stem)
        if not re.match(self.validation_rules["naming_pattern"], agent_name):
            validation_result["issues"].append(f"Agent name '{agent_name}' doesn't match naming convention")
            validation_result["score"] -= 5
        
        # Check required sections
        for section in self.validation_rules["required_sections"]:
            pattern = rf"#{1,2}\s+{section}"
            if not re.search(pattern, content_body, re.IGNORECASE):
                validation_result["issues"].append(f"Missing required section: {section}")
                validation_result["score"] -= 15
        
        # Check section length
        sections = re.findall(r'#{1,2}\s+([^\n]+)\n(.*?)(?=#{1,2}|$)', content_body, re.DOTALL)
        for section_name, section_content in sections:
            content_length = len(section_content.strip())
            if content_length < self.validation_rules["min_section_length"]:
                validation_result["issues"].append(f"Section '{section_name}' too short ({content_length} chars)")
                validation_result["score"] -= 5
            elif content_length > self.validation_rules["max_section_length"]:
                validation_result["issues"].append(f"Section '{section_name}' too long ({content_length} chars)")
                validation_result["score"] -= 3
        
        # Check for DoD contributions
        if self.validation_rules["required_dod_contributions"]:
            if "definition of done" not in content.lower() and "dod" not in content.lower():
                validation_result["issues"].append("Missing Definition of Done contributions")
                validation_result["score"] -= 10
        
        # Generate recommendations
        if validation_result["score"] < 80:
            validation_result["recommendations"].append("Consider using standardization tool to fix format issues")
        
        if "tools" in frontmatter and not isinstance(frontmatter["tools"], list):
            validation_result["recommendations"].append("Tools should be specified as YAML array")
        
        validation_result["valid"] = len(validation_result["issues"]) == 0
        validation_result["score"] = max(0, validation_result["score"])
        
        return validation_result
    
    def standardize_agent_file(self, file_path: Path, preserve_content: bool = True) -> Dict[str, Any]:
        """Standardize an existing agent file"""
        result = {
            "file": str(file_path),
            "success": False,
            "changes_made": [],
            "backup_created": False
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
        except Exception as e:
            result["error"] = f"Cannot read file: {e}"
            return result
        
        # Create backup
        backup_path = file_path.with_suffix(f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            result["backup_created"] = True
            result["backup_path"] = str(backup_path)
        except Exception as e:
            result["error"] = f"Cannot create backup: {e}"
            return result
        
        # Parse existing content
        frontmatter = {}
        content_body = original_content
        
        if original_content.startswith('---'):
            try:
                parts = original_content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    content_body = parts[2]
            except:
                pass
        
        # Extract or generate metadata
        agent_name = frontmatter.get("name", file_path.stem)
        
        # Extract existing sections if preserving content
        existing_sections = {}
        if preserve_content:
            section_pattern = r'#{1,2}\s+([^\n]+)\n(.*?)(?=#{1,2}|$)'
            sections = re.findall(section_pattern, content_body, re.DOTALL)
            for section_name, section_content in sections:
                existing_sections[section_name.strip().lower()] = section_content.strip()
        
        # Generate standardized content
        standardized_content = self.create_standard_template(
            agent_name=agent_name,
            display_name=frontmatter.get("display_name", existing_sections.get("name", agent_name.replace("-", " ").title())),
            description=frontmatter.get("description", ""),
            tools=frontmatter.get("tools", ["filesystem", "write", "edit"]),
            branch=frontmatter.get("branch"),
            targets=frontmatter.get("targets", []),
            mission=existing_sections.get("mission", ""),
            responsibilities=existing_sections.get("responsibilities", ""),
            process=existing_sections.get("process", ""),
            standards=existing_sections.get("standards", ""),
            specialization=existing_sections.get("lane/branch specialization", ""),
            dod_contributions=existing_sections.get("definition of done contributions", "")
        )
        
        # Write standardized file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(standardized_content)
            result["success"] = True
            result["changes_made"].append("Applied standard format template")
            
            if preserve_content:
                result["changes_made"].append("Preserved existing content where possible")
            else:
                result["changes_made"].append("Generated new content based on template")
                
        except Exception as e:
            result["error"] = f"Cannot write standardized file: {e}"
            return result
        
        return result
    
    def scan_and_standardize_all(self, directory: Path, dry_run: bool = False) -> Dict[str, Any]:
        """Scan directory and standardize all agent files"""
        results = {
            "scanned_files": 0,
            "standardized_files": 0,
            "errors": 0,
            "results": [],
            "summary": {}
        }
        
        # Find all agent files
        agent_files = []
        if directory.exists():
            for item in directory.rglob("*.md"):
                if item.name != "README.md" and ".claude" in str(item):
                    agent_files.append(item)
        
        results["scanned_files"] = len(agent_files)
        
        for agent_file in agent_files:
            # Validate first
            validation = self.validate_agent_documentation(agent_file)
            
            file_result = {
                "file": str(agent_file),
                "validation": validation,
                "standardization": None
            }
            
            # Standardize if needed
            if not validation["valid"] or validation["score"] < 90:
                if not dry_run:
                    standardization = self.standardize_agent_file(agent_file, preserve_content=True)
                    file_result["standardization"] = standardization
                    
                    if standardization["success"]:
                        results["standardized_files"] += 1
                    else:
                        results["errors"] += 1
                else:
                    file_result["standardization"] = {"dry_run": True, "would_standardize": True}
                    results["standardized_files"] += 1
            
            results["results"].append(file_result)
        
        # Generate summary
        avg_score = sum(r["validation"]["score"] for r in results["results"]) / len(results["results"]) if results["results"] else 0
        results["summary"] = {
            "average_score": avg_score,
            "files_needing_standardization": results["standardized_files"],
            "compliance_rate": (results["scanned_files"] - results["standardized_files"]) / results["scanned_files"] * 100 if results["scanned_files"] > 0 else 0
        }
        
        return results


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Documentation Standardizer")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create template command
    create_parser = subparsers.add_parser("create", help="Create standardized agent template")
    create_parser.add_argument("name", help="Agent name")
    create_parser.add_argument("--output", help="Output file path")
    create_parser.add_argument("--description", help="Agent description")
    create_parser.add_argument("--tools", nargs="+", default=["filesystem", "write", "edit"], help="Tools list")
    create_parser.add_argument("--lane", help="Lane specialization")
    create_parser.add_argument("--branch", help="Branch specialization")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate agent documentation")
    validate_parser.add_argument("file", help="Agent file to validate")
    validate_parser.add_argument("--json", action="store_true", help="Output JSON format")
    
    # Standardize command
    standardize_parser = subparsers.add_parser("standardize", help="Standardize agent documentation")
    standardize_parser.add_argument("file", help="Agent file to standardize")
    standardize_parser.add_argument("--preserve", action="store_true", default=True, help="Preserve existing content")
    
    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan and standardize directory")
    scan_parser.add_argument("directory", help="Directory to scan")
    scan_parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    scan_parser.add_argument("--report", help="Save report to file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    standardizer = AgentDocStandardizer()
    
    if args.command == "create":
        template = standardizer.create_standard_template(
            agent_name=args.name,
            description=args.description,
            tools=args.tools,
            lane=args.lane,
            branch=args.branch
        )
        
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(template)
            print(f"✅ Template created: {output_path}")
        else:
            print(template)
    
    elif args.command == "validate":
        file_path = Path(args.file)
        validation = standardizer.validate_agent_documentation(file_path)
        
        if args.json:
            print(json.dumps(validation, indent=2))
        else:
            print(f"📋 Validation Report: {file_path.name}")
            print(f"   Valid: {'✅' if validation['valid'] else '❌'}")
            print(f"   Score: {validation['score']}/100")
            
            if validation["issues"]:
                print(f"   Issues ({len(validation['issues'])}):")
                for issue in validation["issues"]:
                    print(f"     • {issue}")
            
            if validation["recommendations"]:
                print(f"   Recommendations:")
                for rec in validation["recommendations"]:
                    print(f"     💡 {rec}")
    
    elif args.command == "standardize":
        file_path = Path(args.file)
        result = standardizer.standardize_agent_file(file_path, preserve_content=args.preserve)
        
        if result["success"]:
            print(f"✅ Standardized: {file_path}")
            if result["backup_created"]:
                print(f"   Backup: {result['backup_path']}")
            for change in result["changes_made"]:
                print(f"   • {change}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
    
    elif args.command == "scan":
        directory = Path(args.directory)
        results = standardizer.scan_and_standardize_all(directory, dry_run=args.dry_run)
        
        print(f"📊 Standardization Scan Results")
        print(f"   Files Scanned: {results['scanned_files']}")
        print(f"   Files Standardized: {results['standardized_files']}")
        print(f"   Errors: {results['errors']}")
        print(f"   Average Score: {results['summary']['average_score']:.1f}/100")
        print(f"   Compliance Rate: {results['summary']['compliance_rate']:.1f}%")
        
        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"   Report saved: {report_path}")


if __name__ == "__main__":
    main()