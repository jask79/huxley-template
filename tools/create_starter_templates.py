#!/usr/bin/env python3
"""
Create customized starter templates from the base template
"""

import os
import json
import shutil
import pathlib

CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")
TEMPLATES_DIR = CATALYST_ROOT / "templates"
BASE_TEMPLATE = TEMPLATES_DIR / "capsule-base"

def customize_template(template_dir, customizations):
    """Apply customizations to template files"""
    
    # Customize metadata.yaml
    metadata_file = template_dir / "spec" / "metadata.yaml"
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            content = f.read()
        
        for placeholder, value in customizations.get('metadata', {}).items():
            content = content.replace(f"{{{{{placeholder}}}}}", str(value))
            
        with open(metadata_file, 'w') as f:
            f.write(content)
    
    # Customize MCP config
    mcp_file = template_dir / "ops" / "mcp.json"
    if mcp_file.exists():
        with open(mcp_file, 'r') as f:
            config = json.load(f)
        
        mcp_config = customizations.get('mcp', {})
        config.update(mcp_config)
        
        with open(mcp_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    # Customize README
    readme_file = template_dir / "README.md"
    if readme_file.exists():
        with open(readme_file, 'r') as f:
            content = f.read()
        
        readme_customizations = customizations.get('readme', {})
        for placeholder, value in readme_customizations.items():
            content = content.replace(f"{{{{{placeholder}}}}}", str(value))
            
        with open(readme_file, 'w') as f:
            f.write(content)

def create_apple_app_starter():
    """Create Apple App starter template"""
    template_dir = TEMPLATES_DIR / "apple-app-starter"
    
    customizations = {
        'metadata': {
            'CAPSULE_NAME': '{{APP_NAME}}',
            'CAPSULE_SLUG': '{{APP_SLUG}}', 
            'BRANCH': 'apple',
            'LANE': 'standard',
            'TARGETS': '["ios", "macos", "swift", "swiftui"]',
            'PRIMARY_AGENTS': '["ios-specialist", "macos-specialist"]',
            'SECONDARY_AGENTS': '["security-auditor", "test-automator"]',
            'MCP_PROFILE': 'apple',
            'DOD_LEVEL': 'comprehensive',
            'TEST_COVERAGE': '80',
            'SECURITY_SCAN': 'true',
            'PERF_BENCH': 'true',
            'DOMAIN_TYPE': 'business',
            'CATEGORY': 'mobile-app',
            'COMPLEXITY': 'medium'
        },
        'mcp': {
            'profile': 'apple',
            'include': [],
            'exclude': []
        },
        'readme': {
            'TEMPLATE_TYPE': 'Apple App Development'
        }
    }
    
    customize_template(template_dir, customizations)
    print(f"✅ Created Apple App starter template: {template_dir}")

def create_web_dev_starter():
    """Create Web Dev starter template"""
    template_dir = TEMPLATES_DIR / "web-dev-starter"
    
    # Copy base template
    if template_dir.exists():
        shutil.rmtree(template_dir)
    shutil.copytree(BASE_TEMPLATE, template_dir)
    
    customizations = {
        'metadata': {
            'CAPSULE_NAME': '{{WEB_APP_NAME}}',
            'CAPSULE_SLUG': '{{WEB_APP_SLUG}}',
            'BRANCH': 'web', 
            'LANE': 'standard',
            'TARGETS': '["react", "nextjs", "typescript", "tailwind"]',
            'PRIMARY_AGENTS': '["frontend-specialist", "javascript-pro"]',
            'SECONDARY_AGENTS': '["backend-architect", "security-auditor"]',
            'MCP_PROFILE': 'webdev',
            'DOD_LEVEL': 'comprehensive', 
            'TEST_COVERAGE': '85',
            'SECURITY_SCAN': 'true',
            'PERF_BENCH': 'true',
            'DOMAIN_TYPE': 'business',
            'CATEGORY': 'web-app',
            'COMPLEXITY': 'medium'
        },
        'mcp': {
            'profile': 'webdev',
            'include': [],
            'exclude': []
        },
        'readme': {
            'TEMPLATE_TYPE': 'Web Development'
        }
    }
    
    customize_template(template_dir, customizations)
    print(f"✅ Created Web Dev starter template: {template_dir}")

def main():
    print("🏗️ Creating Enhanced Starter Templates")
    print("=" * 50)
    
    if not BASE_TEMPLATE.exists():
        print(f"❌ Base template not found: {BASE_TEMPLATE}")
        return
    
    # Create Apple App starter
    create_apple_app_starter()
    
    # Create Web Dev starter  
    create_web_dev_starter()
    
    print("\n📊 Template Summary:")
    for template_dir in TEMPLATES_DIR.glob("*-starter"):
        mcp_file = template_dir / "ops" / "mcp.json"
        if mcp_file.exists():
            with open(mcp_file) as f:
                config = json.load(f)
                profile = config.get('profile', 'unknown')
                print(f"  {template_dir.name}: MCP profile '{profile}'")
    
    print(f"\n🎉 All starter templates created in: {TEMPLATES_DIR}")

if __name__ == "__main__":
    main()