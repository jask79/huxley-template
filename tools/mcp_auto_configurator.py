#!/usr/bin/env python3
"""
MCP Server Auto-Configurator for Huxley
Automatically configures MCP servers based on capsule language detection
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from language_detector import CapsuleLanguageDetector

class MCPAutoConfigurator:
    """Automatically configures MCP servers for capsules"""
    
    def __init__(self):
        self.detector = CapsuleLanguageDetector()
        self.claude_config_dir = Path.home() / '.claude'
        self.project_config_dir = Path.cwd() / '.claude'
        
        # MCP server registry with installation paths.
        # NOTE: none of these four servers ship with the template — install each
        # under global/<name>/ yourself before configuring a capsule with it.
        self.mcp_registry = {
            'apple-doc-mcp': {
                'path': '{{CATALYST_ROOT}}/global/apple-doc-mcp/dist/index.js',
                'command': 'node',
                'transport': 'stdio',
                'description': 'Apple Developer Documentation access',
                'languages': ['swift', 'objective-c']
            },
            'xcodebuild-mcp': {
                'path': '{{CATALYST_ROOT}}/global/xcodebuildmcp/dist/index.js',
                'command': 'node',
                'transport': 'stdio',
                'description': 'Xcode build tools integration',
                'languages': ['swift', 'objective-c']
            },
            'n8n-mcp': {
                'path': '{{CATALYST_ROOT}}/global/n8n-mcp/dist/index.js',
                'command': 'node',
                'transport': 'stdio',
                'description': 'n8n workflow automation',
                'languages': ['automation', 'javascript', 'python']
            },
            'git-mcp': {
                'path': '{{CATALYST_ROOT}}/global/git-mcp/dist/index.js',
                'command': 'node',
                'transport': 'stdio',
                'description': 'Git repository operations',
                'languages': ['*']  # Universal
            },
            'shadcn-ui': {
                'command': 'npx',
                'args': ['-y', '@modelcontextprotocol/server-shadcn-ui'],
                'transport': 'stdio',
                'description': 'shadcn/ui component library',
                'languages': ['javascript', 'typescript', 'react', 'web']
            },
            'filesystem': {
                'command': 'npx',
                'args': ['-y', '@modelcontextprotocol/server-filesystem'],
                'transport': 'stdio',
                'description': 'File system operations',
                'languages': ['*']  # Universal
            }
        }

    def configure_capsule(self, capsule_path: str, scope: str = 'project') -> Dict:
        """Auto-configure MCP servers for a specific capsule"""
        capsule_path = Path(capsule_path)
        
        # Detect language context
        language_context = self.detector.detect_capsule_language(str(capsule_path))
        
        # Get recommended servers
        recommended_servers = self._get_recommended_servers(language_context)
        
        # Generate configuration
        config = self._generate_mcp_config(recommended_servers, language_context, str(capsule_path))
        
        # Apply configuration based on scope
        if scope == 'project':
            config_path = capsule_path / '.claude' / 'settings.json'
        else:
            config_path = self.claude_config_dir / 'settings.json'
        
        self._apply_configuration(config, config_path)
        
        return {
            'language_context': language_context,
            'recommended_servers': recommended_servers,
            'config_path': str(config_path),
            'applied_config': config
        }

    def _get_recommended_servers(self, language_context) -> List[str]:
        """Get recommended MCP servers based on language context"""
        recommended = set()
        
        # Add universal servers
        recommended.add('filesystem')
        recommended.add('git-mcp')
        
        # Add language-specific servers
        for server_name, server_info in self.mcp_registry.items():
            server_languages = server_info.get('languages', [])
            
            if '*' in server_languages:
                recommended.add(server_name)
                continue
                
            # Check primary language
            if language_context.primary_language in server_languages:
                recommended.add(server_name)
                continue
                
            # Check technologies
            if any(tech in server_languages for tech in language_context.technologies):
                recommended.add(server_name)
                continue
                
            # Check frameworks
            if any(framework in server_languages for framework in language_context.frameworks):
                recommended.add(server_name)
                continue
        
        # Special cases based on capsule structure
        if 'swift' in language_context.technologies:
            recommended.update(['apple-doc-mcp', 'xcodebuild-mcp'])
        
        if 'automation' in language_context.technologies:
            recommended.add('n8n-mcp')
            
        if any(web in language_context.technologies for web in ['javascript', 'typescript', 'web']):
            recommended.add('shadcn-ui')
        
        return list(recommended)

    def _generate_mcp_config(self, servers: List[str], language_context, capsule_path: str) -> Dict:
        """Generate MCP configuration object"""
        config = {
            'mcpServers': {},
            'metadata': {
                'autoConfigured': True,
                'capsulePath': capsule_path,
                'detectedLanguage': language_context.primary_language,
                'confidence': language_context.confidence,
                'configuredServers': servers,
                'generatedAt': self._get_timestamp()
            }
        }
        
        for server_name in servers:
            if server_name in self.mcp_registry:
                server_info = self.mcp_registry[server_name]
                server_config = {
                    'transport': server_info.get('transport', 'stdio'),
                    'reason': f"Auto-configured for {language_context.primary_language}",
                    'description': server_info.get('description', f'{server_name} MCP server')
                }
                
                # Add command configuration
                if 'path' in server_info:
                    server_config['command'] = server_info['command']
                    server_config['args'] = [server_info['path']]
                elif 'args' in server_info:
                    server_config['command'] = server_info['command']
                    server_config['args'] = server_info['args']
                else:
                    server_config['command'] = server_name
                
                config['mcpServers'][server_name] = server_config
        
        return config

    def _apply_configuration(self, config: Dict, config_path: Path):
        """Apply MCP configuration to Claude Code settings"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing configuration if it exists
        existing_config = {}
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    existing_config = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                existing_config = {}
        
        # Merge MCP servers (preserve existing non-auto-configured servers)
        if 'mcpServers' not in existing_config:
            existing_config['mcpServers'] = {}
        
        # Remove old auto-configured servers
        to_remove = []
        for server_name, server_config in existing_config['mcpServers'].items():
            if server_config.get('reason', '').startswith('Auto-configured'):
                to_remove.append(server_name)
        
        for server_name in to_remove:
            del existing_config['mcpServers'][server_name]
        
        # Add new auto-configured servers
        existing_config['mcpServers'].update(config['mcpServers'])
        
        # Add metadata
        if 'metadata' not in existing_config:
            existing_config['metadata'] = {}
        existing_config['metadata'].update(config['metadata'])
        
        # Write configuration
        with open(config_path, 'w') as f:
            json.dump(existing_config, f, indent=2)

    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()

    def configure_project(self, project_path: str = None) -> Dict:
        """Configure MCP servers for entire project based on capsules"""
        if project_path is None:
            project_path = os.getcwd()
        
        project_path = Path(project_path)
        results = {}
        
        # Find all capsules in project
        capsule_paths = []
        for capsule_dir in ['capsules', 'testing/capsules']:
            capsule_base = project_path / capsule_dir
            if capsule_base.exists():
                for item in capsule_base.iterdir():
                    if item.is_dir() and (item / 'capsule.json').exists():
                        capsule_paths.append(item)
        
        if not capsule_paths:
            # No capsules found, analyze project directly
            capsule_paths = [project_path]
        
        # Aggregate language contexts
        all_languages = set()
        all_technologies = set()
        all_frameworks = set()
        
        for capsule_path in capsule_paths:
            try:
                context = self.detector.detect_capsule_language(str(capsule_path))
                all_languages.add(context.primary_language)
                all_technologies.update(context.technologies)
                all_frameworks.update(context.frameworks)
                
                results[str(capsule_path)] = {
                    'language_context': context,
                    'status': 'analyzed'
                }
            except Exception as e:
                results[str(capsule_path)] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Generate project-wide recommendations
        from types import SimpleNamespace
        aggregate_context = SimpleNamespace(
            primary_language=max(all_languages, key=lambda x: len([c for c in capsule_paths if x in str(c)]) if all_languages else 'unknown'),
            technologies=list(all_technologies),
            frameworks=list(all_frameworks),
            confidence=1.0
        )
        
        recommended_servers = self._get_recommended_servers(aggregate_context)
        
        # Apply project-level configuration
        config = self._generate_mcp_config(recommended_servers, aggregate_context, str(project_path))
        config_path = project_path / '.claude' / 'settings.json'
        self._apply_configuration(config, config_path)
        
        results['project_summary'] = {
            'aggregate_context': {
                'primary_language': aggregate_context.primary_language,
                'technologies': aggregate_context.technologies,
                'frameworks': aggregate_context.frameworks
            },
            'recommended_servers': recommended_servers,
            'config_path': str(config_path),
            'capsules_analyzed': len([r for r in results.values() if isinstance(r, dict) and r.get('status') == 'analyzed'])
        }
        
        return results

def main():
    """CLI interface for MCP auto-configuration"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto-configure MCP servers for Huxley capsules')
    parser.add_argument('--capsule', help='Configure specific capsule', metavar='PATH')
    parser.add_argument('--project', help='Configure entire project', action='store_true')
    parser.add_argument('--scope', choices=['project', 'user'], default='project', 
                       help='Configuration scope (default: project)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be configured without applying')
    
    args = parser.parse_args()
    
    configurator = MCPAutoConfigurator()
    
    try:
        if args.capsule:
            results = configurator.configure_capsule(args.capsule, args.scope)
            print("=== Capsule MCP Configuration ===")
            print(f"Capsule: {args.capsule}")
            print(f"Language: {results['language_context'].primary_language}")
            print(f"Servers: {', '.join(results['recommended_servers'])}")
            print(f"Config: {results['config_path']}")
            
        elif args.project:
            results = configurator.configure_project()
            print("=== Project MCP Configuration ===")
            summary = results['project_summary']
            print(f"Primary Language: {summary['aggregate_context']['primary_language']}")
            print(f"Technologies: {', '.join(summary['aggregate_context']['technologies'])}")
            print(f"Servers: {', '.join(summary['recommended_servers'])}")
            print(f"Capsules Analyzed: {summary['capsules_analyzed']}")
            print(f"Config: {summary['config_path']}")
            
        else:
            # Default: configure current directory as capsule
            current_dir = os.getcwd()
            results = configurator.configure_capsule(current_dir, args.scope)
            print("=== Auto MCP Configuration ===")
            print(f"Path: {current_dir}")
            print(f"Language: {results['language_context'].primary_language}")
            print(f"Servers: {', '.join(results['recommended_servers'])}")
            print(f"Config: {results['config_path']}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()