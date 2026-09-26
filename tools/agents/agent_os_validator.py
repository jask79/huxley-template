#!/usr/bin/env python3
"""
Agent OS Validation and Enforcement Tool

This tool validates Agent OS implementation across the Huxley system,
ensuring standards compliance and proper integration.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING" 
    INFO = "INFO"


@dataclass
class ValidationResult:
    severity: ValidationSeverity
    component: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class AgentOSValidator:
    def __init__(self, catalyst_root: Path):
        self.catalyst_root = Path(catalyst_root)
        self.global_agent_os = self.catalyst_root / "global" / "agent-os"
        self.capsules_dir = self.catalyst_root / "capsules"
        self.results: List[ValidationResult] = []
    
    def add_result(self, severity: ValidationSeverity, component: str, 
                   message: str, file_path: Optional[str] = None, 
                   line_number: Optional[int] = None):
        """Add a validation result"""
        self.results.append(ValidationResult(
            severity=severity,
            component=component,
            message=message,
            file_path=file_path,
            line_number=line_number
        ))
    
    def validate_global_structure(self) -> bool:
        """Validate global Agent OS structure"""
        component = "Global Agent OS Structure"
        success = True
        
        # Check main directories exist
        required_dirs = [
            "commands",
            "standards", 
            "standards/base",
            "standards/lanes",
            "standards/branches",
            "instructions",
            "instructions/base",
            "instructions/workflows"
        ]
        
        for dir_path in required_dirs:
            full_path = self.global_agent_os / dir_path
            if not full_path.exists():
                self.add_result(ValidationSeverity.ERROR, component,
                              f"Missing required directory: {dir_path}")
                success = False
        
        # Check required files exist
        required_files = [
            "commands/README.md",
            "standards/README.md",
            "standards/base/coding-standards.md",
            "instructions/README.md",
            "instructions/base/agent-context-template.md"
        ]
        
        for file_path in required_files:
            full_path = self.global_agent_os / file_path
            if not full_path.exists():
                self.add_result(ValidationSeverity.ERROR, component,
                              f"Missing required file: {file_path}")
                success = False
        
        if success:
            self.add_result(ValidationSeverity.INFO, component,
                          "Global Agent OS structure is valid")
        
        return success
    
    def validate_capsule_structure(self, capsule_path: Path) -> bool:
        """Validate Agent OS structure for a single capsule"""
        capsule_name = capsule_path.name
        component = f"Capsule: {capsule_name}"
        success = True
        
        agent_os_dir = capsule_path / ".agent-os"
        
        # Check if .agent-os directory exists
        if not agent_os_dir.exists():
            self.add_result(ValidationSeverity.WARNING, component,
                          "Missing .agent-os directory - capsule not enhanced")
            return False
        
        # Check required subdirectories
        required_dirs = ["product", "specs", "standards", "instructions"]
        for dir_name in required_dirs:
            dir_path = agent_os_dir / dir_name
            if not dir_path.exists():
                self.add_result(ValidationSeverity.ERROR, component,
                              f"Missing required directory: .agent-os/{dir_name}")
                success = False
        
        # Check required files
        required_files = {
            "product/vision.md": ValidationSeverity.ERROR,
            "product/architecture.md": ValidationSeverity.WARNING,
            "standards/coding-standards.md": ValidationSeverity.ERROR,
            "instructions/agent-context.md": ValidationSeverity.ERROR
        }
        
        for file_path, severity in required_files.items():
            full_path = agent_os_dir / file_path
            if not full_path.exists():
                self.add_result(severity, component,
                              f"Missing file: .agent-os/{file_path}")
                if severity == ValidationSeverity.ERROR:
                    success = False
        
        return success
    
    def validate_capsule_metadata_consistency(self, capsule_path: Path) -> bool:
        """Validate consistency between capsule metadata and Agent OS context"""
        capsule_name = capsule_path.name
        component = f"Capsule Metadata: {capsule_name}"
        success = True
        
        # Read capsule.json
        capsule_json_path = capsule_path / "capsule.json"
        capsule_data = {}
        if capsule_json_path.exists():
            try:
                with open(capsule_json_path, 'r') as f:
                    capsule_data = json.load(f)
            except json.JSONDecodeError as e:
                self.add_result(ValidationSeverity.ERROR, component,
                              f"Invalid JSON in capsule.json: {e}")
                success = False
        
        # Read requirements.yaml
        requirements_path = capsule_path / "spec" / "requirements.yaml" 
        requirements_data = {}
        if requirements_path.exists():
            try:
                with open(requirements_path, 'r') as f:
                    requirements_data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                self.add_result(ValidationSeverity.ERROR, component,
                              f"Invalid YAML in requirements.yaml: {e}")
                success = False
        
        # Check consistency between metadata sources
        if capsule_data and requirements_data:
                if capsule_lane and req_lane and capsule_lane != req_lane:
                    self.add_result(ValidationSeverity.WARNING, component,
                                  f"Lane mismatch: capsule.json='{capsule_lane}', requirements.yaml='{req_lane}'")
        
        return success
    
    def validate_standards_hierarchy(self) -> bool:
        """Validate standards hierarchy and inheritance"""
        component = "Standards Hierarchy"
        success = True
        
        # Check lane standards
        lanes_dir = self.global_agent_os / "standards" / "lanes"
        if lanes_dir.exists():
            for lane_dir in lanes_dir.iterdir():
                if lane_dir.is_dir():
                    standards_file = lane_dir / "standards.md"
                    if not standards_file.exists():
                        self.add_result(ValidationSeverity.WARNING, component,
                                      f"Missing standards file for lane: {lane_dir.name}")
        
        # Check branch standards 
        branches_dir = self.global_agent_os / "standards" / "branches"
        if branches_dir.exists():
            for branch_dir in branches_dir.iterdir():
                if branch_dir.is_dir():
                    standards_file = branch_dir / "standards.md"
                    if not standards_file.exists():
                        self.add_result(ValidationSeverity.INFO, component,
                                      f"No standards file for branch: {branch_dir.name}")
        
        return success
    
    def validate_command_integration(self) -> bool:
        """Validate Agent OS command integration"""
        component = "Command Integration"
        success = True
        
        commands_dir = self.global_agent_os / "commands"
        if not commands_dir.exists():
            self.add_result(ValidationSeverity.ERROR, component,
                          "Commands directory missing")
            return False
        
        # Check for command files
        command_files = list(commands_dir.glob("*.md"))
        if not command_files:
            self.add_result(ValidationSeverity.WARNING, component,
                          "No command files found")
        
        # Validate command file format
        for cmd_file in command_files:
            if cmd_file.name != "README.md":
                try:
                    with open(cmd_file, 'r') as f:
                        content = f.read()
                        if not content.startswith('---'):
                            self.add_result(ValidationSeverity.WARNING, component,
                                          f"Command file missing YAML frontmatter: {cmd_file.name}")
                except Exception as e:
                    self.add_result(ValidationSeverity.ERROR, component,
                                  f"Error reading command file {cmd_file.name}: {e}")
                    success = False
        
        return success
    
    def validate_agent_instructions(self) -> bool:
        """Validate agent instruction structure and content"""
        component = "Agent Instructions"
        success = True
        
        instructions_dir = self.global_agent_os / "instructions"
        if not instructions_dir.exists():
            self.add_result(ValidationSeverity.ERROR, component,
                          "Instructions directory missing")
            return False
        
        # Check base instructions exist
        base_dir = instructions_dir / "base"
        if base_dir.exists():
            context_template = base_dir / "agent-context-template.md"
            if not context_template.exists():
                self.add_result(ValidationSeverity.ERROR, component,
                              "Missing base agent context template")
                success = False
        
        return success
    
    def run_comprehensive_validation(self) -> Dict[str, int]:
        """Run comprehensive validation of Agent OS implementation"""
        self.results = []  # Reset results
        
        print("Running Agent OS comprehensive validation...")
        
        # Validate global structure
        self.validate_global_structure()
        
        # Validate standards hierarchy
        self.validate_standards_hierarchy()
        
        # Validate command integration 
        self.validate_command_integration()
        
        # Validate agent instructions
        self.validate_agent_instructions()
        
        # Validate each capsule
        if self.capsules_dir.exists():
            for item in self.capsules_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.') and item.name != 'ops':
                    self.validate_capsule_structure(item)
                    self.validate_capsule_metadata_consistency(item)
        
        # Summarize results
        summary = {
            "total": len(self.results),
            "errors": len([r for r in self.results if r.severity == ValidationSeverity.ERROR]),
            "warnings": len([r for r in self.results if r.severity == ValidationSeverity.WARNING]),
            "info": len([r for r in self.results if r.severity == ValidationSeverity.INFO])
        }
        
        return summary
    
    def generate_report(self, output_file: Optional[Path] = None) -> str:
        """Generate validation report"""
        report_lines = []
        report_lines.append("# Agent OS Validation Report")
        report_lines.append("")
        
        # Summary
        summary = {
            "total": len(self.results),
            "errors": len([r for r in self.results if r.severity == ValidationSeverity.ERROR]),
            "warnings": len([r for r in self.results if r.severity == ValidationSeverity.WARNING]),
            "info": len([r for r in self.results if r.severity == ValidationSeverity.INFO])
        }
        
        report_lines.append("## Summary")
        report_lines.append(f"- Total Issues: {summary['total']}")
        report_lines.append(f"- Errors: {summary['errors']}")
        report_lines.append(f"- Warnings: {summary['warnings']}")
        report_lines.append(f"- Info: {summary['info']}")
        report_lines.append("")
        
        # Group results by severity
        for severity in [ValidationSeverity.ERROR, ValidationSeverity.WARNING, ValidationSeverity.INFO]:
            severity_results = [r for r in self.results if r.severity == severity]
            if severity_results:
                report_lines.append(f"## {severity.value}S")
                report_lines.append("")
                
                for result in severity_results:
                    line = f"- **{result.component}**: {result.message}"
                    if result.file_path:
                        line += f" (File: {result.file_path}"
                        if result.line_number:
                            line += f", Line: {result.line_number}"
                        line += ")"
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
    parser = argparse.ArgumentParser(description='Validate Agent OS implementation')
    parser.add_argument('--builder-root', default='{{CATALYST_ROOT}}',
                       help='Huxley root directory')
    parser.add_argument('--output', help='Output file for validation report')
    parser.add_argument('--capsule', help='Validate specific capsule only')
    parser.add_argument('--summary-only', action='store_true', 
                       help='Show only summary results')
    
    args = parser.parse_args()
    
    validator = AgentOSValidator(args.catalyst_root)
    
    if args.capsule:
        # Validate specific capsule
        capsule_path = validator.capsules_dir / args.capsule
        if not capsule_path.exists():
            print(f"Capsule not found: {args.capsule}")
            return 1
        
        validator.validate_capsule_structure(capsule_path)
        validator.validate_capsule_metadata_consistency(capsule_path)
    else:
        # Run comprehensive validation
        summary = validator.run_comprehensive_validation()
    
    if args.summary_only:
        print(f"Validation complete:")
        print(f"  Total: {len(validator.results)}")
        print(f"  Errors: {len([r for r in validator.results if r.severity == ValidationSeverity.ERROR])}")
        print(f"  Warnings: {len([r for r in validator.results if r.severity == ValidationSeverity.WARNING])}")
        print(f"  Info: {len([r for r in validator.results if r.severity == ValidationSeverity.INFO])}")
    else:
        # Generate and display full report
        output_path = Path(args.output) if args.output else None
        report = validator.generate_report(output_path)
        
        if not args.output:
            print(report)
    
    # Return appropriate exit code
    error_count = len([r for r in validator.results if r.severity == ValidationSeverity.ERROR])
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    exit(main())