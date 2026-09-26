#!/usr/bin/env python3
"""
Specification Validation Tool for Huxley
Validates capsule specifications against schema patterns extracted from GitHub Spec Kit

Usage:
    ./tools/validate_specs.py <capsule_path>
    ./tools/validate_specs.py --all
    ./tools/validate_specs.py capsules/example-media-capsule
"""

import yaml
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime


class ValidationLevel(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    level: ValidationLevel
    field: str
    message: str
    suggestion: Optional[str] = None


class SpecValidator:
    """Validates Huxley capsule specifications"""
    
    def __init__(self):
        self.required_fields = {
            'current.yaml': [
                'name',
                'description',
                'version',
                'status',
                'architecture',
                'dependencies'
            ],
            'next.yaml': [
                'planned_version',
                'planned_features',
                'migration_strategy'
            ],
            'standards.yaml': [
                'version',
                'capsule',
                'quality_standards'
            ],
            'product.yaml': [
                'version',
                'capsule',
                'vision',
                'mission',
                'current_capabilities'
            ]
        }
        
        self.field_schemas = {
            'version': {'type': str, 'pattern': r'^\d+\.\d+\.\d+$'},
            'status': {'type': str, 'values': ['development', 'testing', 'production', 'deprecated']},
            'architecture': {
                'type': dict,
                'required_keys': ['pattern', 'components'],
                'optional_keys': ['data_flow', 'integrations']
            },
            'dependencies': {
                'type': dict,
                'required_keys': [],
                'optional_keys': ['capsules', 'external', 'runtime']
            },
            'quality_gates': {
                'type': list,
                'min_items': 1,
                'item_schema': {'type': dict, 'required_keys': ['name', 'threshold']}
            }
        }
        
        self.results: List[ValidationResult] = []
    
    def validate_capsule(self, capsule_path: Path) -> Tuple[bool, List[ValidationResult]]:
        """Validate a single capsule's specifications"""
        self.results = []
        
        if not capsule_path.exists():
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                'path',
                f"Capsule path does not exist: {capsule_path}"
            ))
            return False, self.results
        
        # Check Huxley capsule structure
        # 1. Validate specs/ directory
        specs_dir = capsule_path / 'specs'
        if not specs_dir.exists():
            # Fallback to spec/ directory pattern
            specs_dir = capsule_path / 'spec'
            if not specs_dir.exists():
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    'specs',
                    "Missing 'specs/' directory",
                    "Create specs/ directory with current.yaml and next.yaml"
                ))
                return False, self.results
        
        # Validate spec files
        spec_files = ['current.yaml', 'next.yaml']
        for spec_file in spec_files:
            self._validate_spec_file(specs_dir / spec_file, spec_file)
        
        # 2. Validate root-level framework files (Huxley structure)
        framework_files = ['standards.yaml', 'product.yaml']
        for framework_file in framework_files:
            self._validate_spec_file(capsule_path / framework_file, framework_file)
        
        # 3. Check context/ directory (Huxley structure)
        context_dir = capsule_path / 'context'
        if context_dir.exists():
            context_files = ['decisions.md', 'patterns.md', 'evolution.md']
            for context_file in context_files:
                context_path = context_dir / context_file
                if not context_path.exists():
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        f'context/{context_file}',
                        f"Missing context file: {context_file}",
                        f"Consider adding {context_file} to document capsule evolution"
                    ))
        else:
            self.results.append(ValidationResult(
                ValidationLevel.WARNING,
                'context',
                "Missing 'context/' directory", 
                "Create context/ with decisions.md, patterns.md, evolution.md"
            ))
        
        # 4. Check specs/versions/ directory
        versions_dir = specs_dir / 'versions'
        if not versions_dir.exists():
            self.results.append(ValidationResult(
                ValidationLevel.INFO,
                'specs/versions',
                "Missing 'specs/versions/' directory",
                "Create specs/versions/ to track specification evolution history"
            ))
        
        # Validate cross-file consistency
        self._validate_consistency(capsule_path)
        
        # Check for errors
        has_errors = any(r.level == ValidationLevel.ERROR for r in self.results)
        return not has_errors, self.results
    
    def _validate_spec_file(self, file_path: Path, file_name: str):
        """Validate a single specification file"""
        if not file_path.exists():
            self.results.append(ValidationResult(
                ValidationLevel.WARNING,
                file_name,
                f"Missing {file_name}",
                f"Create {file_name} with required fields"
            ))
            return
        
        try:
            with open(file_path, 'r') as f:
                spec = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                file_name,
                f"Invalid YAML syntax: {e}"
            ))
            return
        
        if not spec:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                file_name,
                f"{file_name} is empty"
            ))
            return
        
        # Check required fields
        if file_name in self.required_fields:
            for field in self.required_fields[file_name]:
                if field not in spec:
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        f"{file_name}.{field}",
                        f"Missing required field '{field}'",
                        f"Add '{field}' to {file_name}"
                    ))
                else:
                    # Validate field schema if defined
                    self._validate_field_schema(spec[field], field, f"{file_name}.{field}")
    
    def _validate_field_schema(self, value: Any, field_name: str, full_path: str):
        """Validate a field against its schema"""
        if field_name not in self.field_schemas:
            return
        
        schema = self.field_schemas[field_name]
        
        # Type validation
        if 'type' in schema:
            expected_type = schema['type']
            if not isinstance(value, expected_type):
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    full_path,
                    f"Expected type {expected_type.__name__}, got {type(value).__name__}"
                ))
                return
        
        # Pattern validation for strings
        if 'pattern' in schema and isinstance(value, str):
            import re
            if not re.match(schema['pattern'], value):
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    full_path,
                    f"Value '{value}' doesn't match pattern {schema['pattern']}"
                ))
        
        # Enum validation
        if 'values' in schema and value not in schema['values']:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                full_path,
                f"Invalid value '{value}'. Must be one of: {schema['values']}"
            ))
        
        # Dict validation
        if isinstance(value, dict) and 'required_keys' in schema:
            for key in schema['required_keys']:
                if key not in value:
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        f"{full_path}.{key}",
                        f"Missing required key '{key}'"
                    ))
        
        # List validation
        if isinstance(value, list):
            if 'min_items' in schema and len(value) < schema['min_items']:
                self.results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    full_path,
                    f"List should have at least {schema['min_items']} items"
                ))
            
            if 'item_schema' in schema:
                for i, item in enumerate(value):
                    if 'type' in schema['item_schema'] and not isinstance(item, schema['item_schema']['type']):
                        self.results.append(ValidationResult(
                            ValidationLevel.ERROR,
                            f"{full_path}[{i}]",
                            f"Invalid item type"
                        ))
                    
                    if 'required_keys' in schema['item_schema'] and isinstance(item, dict):
                        for key in schema['item_schema']['required_keys']:
                            if key not in item:
                                self.results.append(ValidationResult(
                                    ValidationLevel.ERROR,
                                    f"{full_path}[{i}].{key}",
                                    f"Missing required key '{key}' in list item"
                                ))
    
    def _validate_consistency(self, capsule_path: Path):
        """Validate consistency between specification files"""
        current_path = capsule_path / 'specs' / 'current.yaml'
        next_path = capsule_path / 'specs' / 'next.yaml'
        
        if not current_path.exists() or not next_path.exists():
            return
        
        try:
            with open(current_path, 'r') as f:
                current = yaml.safe_load(f)
            with open(next_path, 'r') as f:
                next_spec = yaml.safe_load(f)
        except:
            return
        
        # Check version progression
        if 'version' in current and 'planned_version' in next_spec:
            current_version = current['version']
            planned_version = next_spec['planned_version']
            
            # Simple version comparison
            try:
                current_parts = [int(x) for x in current_version.split('.')]
                planned_parts = [int(x) for x in planned_version.split('.')]
                
                if planned_parts <= current_parts:
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        'version_progression',
                        f"Planned version {planned_version} should be greater than current {current_version}"
                    ))
            except:
                pass
        
        # Check that next.yaml references current capabilities
        if 'name' in current and 'planned_features' in next_spec:
            if not next_spec.get('builds_on_current', True):
                self.results.append(ValidationResult(
                    ValidationLevel.INFO,
                    'evolution',
                    "next.yaml appears to be a complete rewrite rather than evolution",
                    "Consider if this should be a new capsule instead"
                ))
    
    def format_results(self, capsule_name: str) -> str:
        """Format validation results for display"""
        if not self.results:
            return f"✅ {capsule_name}: All validations passed!"
        
        output = [f"\n📋 Validation Report for {capsule_name}"]
        output.append("=" * 50)
        
        # Group by level
        errors = [r for r in self.results if r.level == ValidationLevel.ERROR]
        warnings = [r for r in self.results if r.level == ValidationLevel.WARNING]
        infos = [r for r in self.results if r.level == ValidationLevel.INFO]
        
        if errors:
            output.append(f"\n❌ Errors ({len(errors)}):")
            for r in errors:
                output.append(f"  - {r.field}: {r.message}")
                if r.suggestion:
                    output.append(f"    💡 {r.suggestion}")
        
        if warnings:
            output.append(f"\n⚠️  Warnings ({len(warnings)}):")
            for r in warnings:
                output.append(f"  - {r.field}: {r.message}")
                if r.suggestion:
                    output.append(f"    💡 {r.suggestion}")
        
        if infos:
            output.append(f"\nℹ️  Info ({len(infos)}):")
            for r in infos:
                output.append(f"  - {r.field}: {r.message}")
                if r.suggestion:
                    output.append(f"    💡 {r.suggestion}")
        
        output.append("\n" + "=" * 50)
        summary = "✅ PASSED" if not errors else "❌ FAILED"
        output.append(f"Summary: {summary} ({len(errors)} errors, {len(warnings)} warnings, {len(infos)} info)")
        
        return "\n".join(output)


def validate_all_capsules():
    """Validate all capsules in the Huxley system"""
    validator = SpecValidator()
    base_path = Path.cwd()
    capsules_dir = base_path / 'capsules'
    
    if not capsules_dir.exists():
        print("❌ No capsules directory found")
        return 1
    
    all_passed = True
    results_summary = []
    
    # Find all capsules (directories with specs/)
    capsules = [d for d in capsules_dir.iterdir() 
                if d.is_dir() and (d / 'specs').exists()]
    
    print(f"\n🔍 Validating {len(capsules)} capsules...\n")
    
    for capsule in sorted(capsules):
        passed, results = validator.validate_capsule(capsule)
        
        if not passed:
            all_passed = False
        
        # Show brief status
        status = "✅" if passed else "❌"
        error_count = len([r for r in results if r.level == ValidationLevel.ERROR])
        warning_count = len([r for r in results if r.level == ValidationLevel.WARNING])
        
        print(f"{status} {capsule.name:30} - {error_count} errors, {warning_count} warnings")
        results_summary.append((capsule.name, passed, results))
    
    # Show detailed results for failed capsules
    print("\n" + "=" * 60)
    failed_capsules = [r for r in results_summary if not r[1]]
    
    if failed_capsules:
        print("\n📝 Detailed Results for Failed Capsules:")
        for name, passed, results in failed_capsules:
            validator.results = results
            print(validator.format_results(name))
    
    # Summary
    passed_count = len([r for r in results_summary if r[1]])
    print(f"\n📊 Overall Summary: {passed_count}/{len(capsules)} capsules passed validation")
    
    return 0 if all_passed else 1


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: validate_specs.py <capsule_path> or --all")
        return 1
    
    if sys.argv[1] == '--all':
        return validate_all_capsules()
    
    capsule_path = Path(sys.argv[1]).resolve()
    validator = SpecValidator()
    
    passed, results = validator.validate_capsule(capsule_path)
    print(validator.format_results(capsule_path.name))
    
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())