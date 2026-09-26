#!/usr/bin/env python3
"""
Agent OS Standards Enforcement Tool

This tool enforces Agent OS standards across the Huxley system,
automatically fixing common issues and ensuring compliance.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import shutil
from dataclasses import dataclass


@dataclass
class EnforcementAction:
    action: str
    component: str
    description: str
    success: bool
    details: Optional[str] = None


class AgentOSEnforcer:
    def __init__(self, catalyst_root: Path, dry_run: bool = False):
        self.catalyst_root = Path(catalyst_root)
        self.global_agent_os = self.catalyst_root / "global" / "agent-os"
        self.capsules_dir = self.catalyst_root / "capsules"
        self.dry_run = dry_run
        self.actions: List[EnforcementAction] = []
    
    def add_action(self, action: str, component: str, description: str, 
                   success: bool, details: Optional[str] = None):
        """Record an enforcement action"""
        self.actions.append(EnforcementAction(
            action=action,
            component=component,
            description=description,
            success=success,
            details=details
        ))
    
    def ensure_global_structure(self) -> bool:
        """Ensure global Agent OS structure exists"""
        component = "Global Structure"
        success = True
        
        # Required directories
        required_dirs = [
            "commands",
            "standards",
            "standards/base", 
            "standards/lanes",
            "standards/lanes/standard",
            "standards/lanes/standard",
            "standards/branches",
            "instructions",
            "instructions/base",
            "instructions/workflows",
            "instructions/roles"
        ]
        
        for dir_path in required_dirs:
            full_path = self.global_agent_os / dir_path
            if not full_path.exists():
                if not self.dry_run:
                    try:
                        full_path.mkdir(parents=True, exist_ok=True)
                        self.add_action("CREATE", component, 
                                      f"Created directory: {dir_path}", True)
                    except Exception as e:
                        self.add_action("CREATE", component,
                                      f"Failed to create directory: {dir_path}", False, str(e))
                        success = False
                else:
                    self.add_action("CREATE", component,
                                  f"Would create directory: {dir_path}", True)
        
        return success
    
    def enforce_capsule_structure(self, capsule_path: Path) -> bool:
        """Enforce proper Agent OS structure in capsule"""
        capsule_name = capsule_path.name
        component = f"Capsule: {capsule_name}"
        success = True
        
        # Skip ops directory and hidden directories
        if capsule_name == 'ops' or capsule_name.startswith('.'):
            return True
        
        agent_os_dir = capsule_path / ".agent-os"
        
        # Create .agent-os directory if missing
        if not agent_os_dir.exists():
            if not self.dry_run:
                try:
                    agent_os_dir.mkdir(exist_ok=True)
                    self.add_action("CREATE", component,
                                  "Created .agent-os directory", True)
                except Exception as e:
                    self.add_action("CREATE", component,
                                  "Failed to create .agent-os directory", False, str(e))
                    return False
            else:
                self.add_action("CREATE", component,
                              "Would create .agent-os directory", True)
        
        # Create required subdirectories
        required_dirs = ["product", "specs", "standards", "instructions"]
        for dir_name in required_dirs:
            dir_path = agent_os_dir / dir_name
            if not dir_path.exists():
                if not self.dry_run:
                    try:
                        dir_path.mkdir(exist_ok=True)
                        self.add_action("CREATE", component,
                                      f"Created .agent-os/{dir_name}", True)
                    except Exception as e:
                        self.add_action("CREATE", component,
                                      f"Failed to create .agent-os/{dir_name}", False, str(e))
                        success = False
                else:
                    self.add_action("CREATE", component,
                                  f"Would create .agent-os/{dir_name}", True)
        
        return success
    
    def enforce_standards_inheritance(self, capsule_path: Path) -> bool:
        """Enforce proper standards inheritance in capsule"""
        capsule_name = capsule_path.name
        component = f"Standards: {capsule_name}"
        success = True
        
        if capsule_name == 'ops' or capsule_name.startswith('.'):
            return True
        
        # Get capsule metadata to determine lane and branch
        capsule_json_path = capsule_path / "capsule.json"
        requirements_path = capsule_path / "spec" / "requirements.yaml"
        
        lane = "standard"  # default
        branch = "automation"  # default
        
        # Extract lane from capsule.json
        if capsule_json_path.exists():
            try:
                with open(capsule_json_path, 'r') as f:
                    capsule_data = json.load(f)
            except:
                pass
        
        # Extract branch from requirements.yaml
        if requirements_path.exists():
            try:
                with open(requirements_path, 'r') as f:
                    req_data = yaml.safe_load(f)
                    if 'project' in req_data:
                        branch = req_data['project'].get('branch', branch)
            except:
                pass
        
        # Ensure standards file references inheritance hierarchy
        standards_file = capsule_path / ".agent-os" / "standards" / "coding-standards.md"
        if standards_file.exists():
            try:
                with open(standards_file, 'r') as f:
                    content = f.read()
                
                # Check if inheritance is properly documented
                if "Inheritance Hierarchy" not in content:
                    inheritance_text = f"""# Coding Standards

## Inheritance Hierarchy
This capsule inherits standards from:
1. Global Agent OS base standards
2. Lane-specific standards ({lane})
3. Branch-specific standards ({branch})
4. Capsule-specific customizations (this file)

## Capsule-Specific Standards
{content.replace('# Coding Standards', '').strip()}
"""
                    if not self.dry_run:
                        with open(standards_file, 'w') as f:
                            f.write(inheritance_text)
                        self.add_action("UPDATE", component,
                                      "Added standards inheritance hierarchy", True)
                    else:
                        self.add_action("UPDATE", component,
                                      "Would add standards inheritance hierarchy", True)
            
            except Exception as e:
                self.add_action("UPDATE", component,
                              "Failed to update standards inheritance", False, str(e))
                success = False
        
        return success
    
    def enforce_file_permissions(self) -> bool:
        """Enforce proper file permissions for Agent OS components"""
        component = "File Permissions"
        success = True
        
        # Make enhancement and validation tools executable
        tools = [
            self.catalyst_root / "tools" / "agent_os_enhancer.py",
            self.catalyst_root / "tools" / "agent_os_validator.py",
            self.catalyst_root / "tools" / "agent_os_enforcer.py"
        ]
        
        for tool in tools:
            if tool.exists():
                current_mode = tool.stat().st_mode
                if not (current_mode & 0o111):  # Not executable
                    if not self.dry_run:
                        try:
                            tool.chmod(0o755)
                            self.add_action("CHMOD", component,
                                          f"Made {tool.name} executable", True)
                        except Exception as e:
                            self.add_action("CHMOD", component,
                                          f"Failed to make {tool.name} executable", False, str(e))
                            success = False
                    else:
                        self.add_action("CHMOD", component,
                                      f"Would make {tool.name} executable", True)
        
        return success
    
    def validate_and_fix_yaml(self, file_path: Path) -> bool:
        """Validate and attempt to fix YAML files"""
        component = f"YAML: {file_path.name}"
        success = True
        
        if not file_path.exists():
            return True
        
        try:
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            # YAML is valid
            return True
        except yaml.YAMLError as e:
            self.add_action("VALIDATE", component,
                          f"YAML syntax error: {e}", False)
            # Could implement basic YAML fixes here
            success = False
        except Exception as e:
            self.add_action("VALIDATE", component,
                          f"Error reading file: {e}", False)
            success = False
        
        return success
    
    def validate_and_fix_json(self, file_path: Path) -> bool:
        """Validate and attempt to fix JSON files"""
        component = f"JSON: {file_path.name}"
        success = True
        
        if not file_path.exists():
            return True
        
        try:
            with open(file_path, 'r') as f:
                json.load(f)
            # JSON is valid
            return True
        except json.JSONDecodeError as e:
            self.add_action("VALIDATE", component,
                          f"JSON syntax error: {e}", False)
            # Could implement basic JSON fixes here
            success = False
        except Exception as e:
            self.add_action("VALIDATE", component,
                          f"Error reading file: {e}", False)
            success = False
        
        return success
    
    def run_enforcement(self) -> Dict[str, int]:
        """Run comprehensive Agent OS enforcement"""
        self.actions = []  # Reset actions
        
        print(f"Running Agent OS enforcement {'(DRY RUN)' if self.dry_run else ''}...")
        
        # Ensure global structure
        self.ensure_global_structure()
        
        # Enforce file permissions
        self.enforce_file_permissions()
        
        # Enforce capsule structures
        if self.capsules_dir.exists():
            for item in self.capsules_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    self.enforce_capsule_structure(item)
                    self.enforce_standards_inheritance(item)
                    
                    # Validate important files
                    self.validate_and_fix_json(item / "capsule.json")
                    self.validate_and_fix_yaml(item / "spec" / "requirements.yaml")
        
        # Summarize actions
        summary = {
            "total": len(self.actions),
            "successful": len([a for a in self.actions if a.success]),
            "failed": len([a for a in self.actions if not a.success])
        }
        
        return summary
    
    def generate_report(self, output_file: Optional[Path] = None) -> str:
        """Generate enforcement report"""
        report_lines = []
        report_lines.append("# Agent OS Enforcement Report")
        report_lines.append("")
        
        # Summary
        summary = {
            "total": len(self.actions),
            "successful": len([a for a in self.actions if a.success]),
            "failed": len([a for a in self.actions if not a.success])
        }
        
        report_lines.append("## Summary")
        report_lines.append(f"- Total Actions: {summary['total']}")
        report_lines.append(f"- Successful: {summary['successful']}")
        report_lines.append(f"- Failed: {summary['failed']}")
        if self.dry_run:
            report_lines.append("- Mode: DRY RUN (no changes made)")
        report_lines.append("")
        
        # Group actions by type
        action_types = list(set(a.action for a in self.actions))
        for action_type in sorted(action_types):
            type_actions = [a for a in self.actions if a.action == action_type]
            if type_actions:
                report_lines.append(f"## {action_type} Actions")
                report_lines.append("")
                
                for action in type_actions:
                    status = "✓" if action.success else "✗"
                    line = f"- {status} **{action.component}**: {action.description}"
                    if action.details:
                        line += f" ({action.details})"
                    report_lines.append(line)
                report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        # Write to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            print(f"Report written to: {output_file}")
        
        return report_text


def main():
    parser = argparse.ArgumentParser(description='Enforce Agent OS standards')
    parser.add_argument('--builder-root', default='{{CATALYST_ROOT}}',
                       help='Huxley root directory')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--output', help='Output file for enforcement report')
    parser.add_argument('--capsule', help='Enforce standards for specific capsule only')
    
    args = parser.parse_args()
    
    enforcer = AgentOSEnforcer(args.catalyst_root, dry_run=args.dry_run)
    
    if args.capsule:
        # Enforce for specific capsule
        capsule_path = enforcer.capsules_dir / args.capsule
        if not capsule_path.exists():
            print(f"Capsule not found: {args.capsule}")
            return 1
        
        enforcer.enforce_capsule_structure(capsule_path)
        enforcer.enforce_standards_inheritance(capsule_path)
    else:
        # Run comprehensive enforcement
        summary = enforcer.run_enforcement()
    
    # Generate and display report
    output_path = Path(args.output) if args.output else None
    report = enforcer.generate_report(output_path)
    
    if not args.output:
        print(report)
    
    # Return appropriate exit code
    failed_count = len([a for a in enforcer.actions if not a.success])
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    exit(main())