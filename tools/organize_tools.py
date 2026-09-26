#!/usr/bin/env python3
"""
Organize tools into categorized subdirectories
Creates symlinks to maintain backwards compatibility
"""

import os
import sys
import shutil
from pathlib import Path

# Add common utilities
sys.path.insert(0, os.path.dirname(__file__))
from common.builder_utils import CATALYST_ROOT, logger, PathValidator

class ToolOrganizer:
    """Organize tools into logical subdirectories"""
    
    def __init__(self):
        self.tools_dir = Path(CATALYST_ROOT) / 'tools'
        self.validator = PathValidator()
        
        # Define tool categories and their files
        self.categories = {
            'core': [
                'bs.py', 
                'run_manifest_cli.py', 
                'run_manifest_schema.py',
                'run_manifest_validator.py',
                'run_with_manifest.py',
                'load_config.sh',
                'gen-config.sh',
            ],
            'agents': [
                'agent_registry.py',
                'agent_os_enforcer.py',
                'agent_os_enhancer.py',
                'agent_os_validator.py',
                'agent_context_audit.py',
                'agent_doc_standardizer.py',
                'agent_test_framework.py',
                'agent_tools_check.py',
                'agent_usage_tracker.py',
                'claude_agent_audit.py',
            ],
            'capsules': [
                'capsule_autopsy.py',
                'capsule_autopsy_agent.py',
                'capsule_health_monitor.py',
                'capsule_maintenance_manager.py',
                'new-capsule.sh',
                'fork_capsule.py',
                'migrate_to_capsules.py',
                'migrate_test_capsules.sh',
                'validate_capsules.sh',
                'on_capsule_created.sh',
            ],
            'mcp': [
                'mcp_audit.sh',
                'mcp_audit_logger.py',
                'mcp_auto_configurator.py',
                'mcp_grants_check.py',
                'mcp_platform_loader.py',
                'mcp_profile_manager.py',
                'mcp_resolver.py',
                'consolidate_mcps.py',
                'merge_mcp.py',
            ],
            'maintenance': [
                'backup_memory.sh',
                'backup_registry.sh',
                'clear_memory.sh',
                'setup_memory.sh',
                'memory_status.sh',
                'daily_audit.sh',
                'weekly_system_audit.sh',
                'rotate_logs.sh',
                'rotate-logs.sh',
                'fix_perms.sh',
                'fix_hardcoded_paths.py',
                'fix_hardcoded_paths_v2.py',
            ],
            'testing': [
                'test_builder.sh',
                'test_integration.sh',
                'test_lane_features.sh',
                'test_agent_discovery.sh',
                'test_agent_routing.py',
                'test_agent_routing.sh',
                'test_context_persistence.py',
                'test_enhanced_debugger.py',
                'test_shortcut_generation.py',
                'test_system_integration.py',
                'test_results_debugger.json',
            ],
            'system': [
                'system_health_rollup.py',
                'system_ops_integration.py',
                'metrics_rollup.py',
                'performance_baseline.py',
                'circuit_breaker.py',
                'dependency_mapper.py',
                'daily_dependency_check.py',
                'events_logger.py',
            ],
            'utilities': [
                'secretctl.py',
                'setup_rag_security.sh',
                'scan_secrets.sh',
                'preflight_secrets.sh',
                'preflight.sh',
                'set_lane.sh',
                'validate_dod.sh',
                'snapshot.sh',
                'snapshot_builder.sh',
                'diagnose_builder.sh',
                'list-workflows.sh',
                'refresh_dashboard.sh',
                'trigger_planner.sh',
                'update_session.sh',
            ],
        }
        
        # Files to keep in root tools directory
        self.keep_in_root = [
            '__init__.py',
            'organize_tools.py',
            'setup_builder_env.sh',
            'setup_environment.sh',
        ]
    
    def create_directories(self):
        """Create category subdirectories"""
        for category in self.categories.keys():
            category_dir = self.tools_dir / category
            if not category_dir.exists():
                category_dir.mkdir(parents=True)
                logger.info(f"Created directory: {category_dir}")
    
    def categorize_uncategorized(self):
        """Find and report uncategorized files"""
        all_categorized = set()
        for files in self.categories.values():
            all_categorized.update(files)
        
        all_categorized.update(self.keep_in_root)
        
        uncategorized = []
        for file_path in self.tools_dir.glob('*'):
            if file_path.is_file() and file_path.name not in all_categorized:
                if not file_path.name.endswith('.backup') and not file_path.name.endswith('.bak'):
                    uncategorized.append(file_path.name)
        
        if uncategorized:
            logger.warning(f"Uncategorized files found: {uncategorized}")
            # Add to utilities by default
            self.categories['utilities'].extend(uncategorized)
    
    def move_files(self, create_symlinks=True):
        """Move files to their categories and optionally create symlinks"""
        moved_files = []
        errors = []
        
        for category, files in self.categories.items():
            category_dir = self.tools_dir / category
            
            for filename in files:
                src_path = self.tools_dir / filename
                dst_path = category_dir / filename
                
                if not src_path.exists():
                    continue
                
                if src_path.is_file():
                    try:
                        # Move the file
                        shutil.move(str(src_path), str(dst_path))
                        moved_files.append((filename, category))
                        logger.info(f"Moved {filename} to {category}/")
                        
                        # Create symlink for backwards compatibility
                        if create_symlinks:
                            os.symlink(str(dst_path), str(src_path))
                            logger.info(f"Created symlink for {filename}")
                    
                    except Exception as e:
                        errors.append((filename, str(e)))
                        logger.error(f"Error moving {filename}: {e}")
        
        return moved_files, errors
    
    def create_category_init_files(self):
        """Create __init__.py files in category directories"""
        for category in self.categories.keys():
            category_dir = self.tools_dir / category
            init_file = category_dir / '__init__.py'
            
            if not init_file.exists():
                content = f'''"""
Huxley {category.title()} Tools
{category.title()} utilities for the Huxley system
"""

__all__ = []
'''
                with open(init_file, 'w') as f:
                    f.write(content)
                logger.info(f"Created {category}/__init__.py")
    
    def create_index_file(self):
        """Create an index file listing all tools by category"""
        index_path = self.tools_dir / 'TOOLS_INDEX.md'
        
        content = """# Huxley Tools Index

## Directory Structure

```
tools/
├── common/        # Shared utilities and validation
├── core/          # Core Huxley utilities
├── agents/        # Agent management tools
├── capsules/      # Capsule operations
├── mcp/           # MCP integration tools
├── maintenance/   # System maintenance scripts
├── testing/       # Test utilities and scripts
├── system/        # System health and monitoring
└── utilities/     # General utilities
```

## Tools by Category

"""
        
        for category, files in sorted(self.categories.items()):
            content += f"### {category.title()}\n\n"
            for filename in sorted(files):
                file_path = self.tools_dir / category / filename
                if file_path.exists():
                    # Get first line of file for description
                    try:
                        with open(file_path, 'r') as f:
                            lines = f.readlines()
                            desc = ""
                            for line in lines[1:5]:
                                if line.strip().startswith('#'):
                                    desc = line.strip('# ').strip()
                                    break
                            content += f"- `{filename}` - {desc}\n"
                    except:
                        content += f"- `{filename}`\n"
            content += "\n"
        
        with open(index_path, 'w') as f:
            f.write(content)
        logger.info(f"Created tools index: {index_path}")
    
    def run(self, dry_run=False):
        """Run the organization process"""
        logger.info("Starting tool organization...")
        
        # Find uncategorized files
        self.categorize_uncategorized()
        
        if dry_run:
            print("\nDRY RUN - No files will be moved")
            print("\nPlanned organization:")
            for category, files in self.categories.items():
                print(f"\n{category}/")
                for filename in files[:5]:
                    if (self.tools_dir / filename).exists():
                        print(f"  - {filename}")
                if len(files) > 5:
                    print(f"  ... and {len(files) - 5} more")
            return
        
        # Create directories
        self.create_directories()
        
        # Move files
        moved, errors = self.move_files(create_symlinks=True)
        
        # Create init files
        self.create_category_init_files()
        
        # Create index
        self.create_index_file()
        
        # Print summary
        print("\n" + "="*60)
        print("TOOL ORGANIZATION COMPLETE")
        print("="*60)
        print(f"Files moved: {len(moved)}")
        print(f"Errors: {len(errors)}")
        print(f"Symlinks created for backwards compatibility")
        
        if errors:
            print("\nErrors encountered:")
            for filename, error in errors[:5]:
                print(f"  - {filename}: {error}")
        
        print("\nNext steps:")
        print("1. Test that existing scripts still work with symlinks")
        print("2. Update any hardcoded tool paths to use categories")
        print("3. Remove symlinks once all references are updated")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Organize Huxley tools')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without moving files')
    args = parser.parse_args()
    
    organizer = ToolOrganizer()
    try:
        organizer.run(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\nProcess interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()