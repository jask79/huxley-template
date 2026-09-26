#!/usr/bin/env python3
"""
Language Detection System for Huxley Capsules
Automatically detects programming languages and technologies in capsules
"""

import os
import json
import glob
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, asdict

@dataclass
class LanguageContext:
    """Language context information for a capsule"""
    primary_language: str
    technologies: List[str]
    frameworks: List[str]
    build_tools: List[str]
    mcp_servers: List[str]
    confidence: float

class CapsuleLanguageDetector:
    """Detects languages and technologies in Huxley capsules"""
    
    def __init__(self):
        # Language detection patterns
        self.file_patterns = {
            'swift': ['*.swift', '*.xcodeproj', '*.xcworkspace', '*.plist'],
            'python': ['*.py', 'requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
            'javascript': ['*.js', '*.ts', '*.jsx', '*.tsx', 'package.json', 'yarn.lock'],
            'go': ['*.go', 'go.mod', 'go.sum'],
            'rust': ['*.rs', 'Cargo.toml', 'Cargo.lock'],
            'java': ['*.java', 'pom.xml', 'build.gradle'],
            'c': ['*.c', '*.h', 'Makefile', 'CMakeLists.txt'],
            'cpp': ['*.cpp', '*.cxx', '*.hpp', '*.hxx'],
            'shell': ['*.sh', '*.bash', '*.zsh'],
            'docker': ['Dockerfile', 'docker-compose.yml', '.dockerignore'],
            'web': ['*.html', '*.css', '*.scss', '*.sass']
        }
        
        # Framework detection patterns
        self.framework_patterns = {
            'swiftui': ['SwiftUI'],
            'uikit': ['UIKit'],
            'react': ['react', 'React'],
            'vue': ['vue', 'Vue'],
            'angular': ['@angular', 'angular'],
            'django': ['django', 'Django'],
            'flask': ['flask', 'Flask'],
            'express': ['express'],
            'nextjs': ['next', 'Next.js'],
            'nuxtjs': ['nuxt', 'Nuxt.js'],
            'fastapi': ['fastapi', 'FastAPI'],
            'rails': ['rails', 'Rails'],
            'spring': ['spring', 'Spring'],
            'gin': ['gin-gonic'],
            'axum': ['axum'],
            'actix': ['actix-web']
        }
        
        # MCP server recommendations
        self.mcp_recommendations = {
            'swift': ['apple-doc-mcp', 'xcodebuild-mcp'],
            'python': ['python-doc-mcp'],
            'javascript': ['node-doc-mcp', 'shadcn-ui'],
            'typescript': ['node-doc-mcp', 'shadcn-ui'],
            'go': ['go-doc-mcp'],
            'rust': ['rust-doc-mcp'],
            'web': ['shadcn-ui', 'web-doc-mcp'],
            'automation': ['n8n-mcp', 'apple-doc-mcp']
        }
        
        # Build tool detection
        self.build_tools = {
            'xcode': ['*.xcodeproj', '*.xcworkspace'],
            'npm': ['package.json', 'package-lock.json'],
            'yarn': ['yarn.lock'],
            'pip': ['requirements.txt', 'setup.py'],
            'cargo': ['Cargo.toml'],
            'gradle': ['build.gradle'],
            'maven': ['pom.xml'],
            'make': ['Makefile'],
            'cmake': ['CMakeLists.txt'],
            'docker': ['Dockerfile']
        }

    def detect_capsule_language(self, capsule_path: str) -> LanguageContext:
        """Detect primary language and context for a capsule"""
        capsule_path = Path(capsule_path)
        
        # Get all files in capsule
        all_files = []
        for root, dirs, files in os.walk(capsule_path):
            # Skip certain directories
            if any(skip in root for skip in ['.git', 'node_modules', 'DerivedData', '__pycache__']):
                continue
            for file in files:
                all_files.append(os.path.join(root, file))
        
        # Count language indicators
        language_scores = {}
        detected_frameworks = set()
        detected_build_tools = set()
        
        for lang, patterns in self.file_patterns.items():
            score = 0
            for pattern in patterns:
                matches = []
                for file_path in all_files:
                    if self._matches_pattern(file_path, pattern):
                        matches.append(file_path)
                
                if matches:
                    # Weight by file count and type
                    if pattern.startswith('*.'):
                        score += len(matches) * 2  # Source files get more weight
                    else:
                        score += len(matches) * 5  # Config files get high weight
            
            if score > 0:
                language_scores[lang] = score
        
        # Detect frameworks by scanning file contents
        for file_path in all_files[:50]:  # Limit scanning for performance
            if file_path.endswith(('.swift', '.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs')):
                frameworks = self._detect_frameworks_in_file(file_path)
                detected_frameworks.update(frameworks)
        
        # Detect build tools
        for tool, patterns in self.build_tools.items():
            for pattern in patterns:
                for file_path in all_files:
                    if self._matches_pattern(file_path, pattern):
                        detected_build_tools.add(tool)
                        break
        
        # Determine primary language
        if not language_scores:
            primary_language = 'unknown'
            confidence = 0.0
        else:
            primary_language = max(language_scores, key=language_scores.get)
            total_score = sum(language_scores.values())
            confidence = language_scores[primary_language] / total_score if total_score > 0 else 0.0
        
        # Get technology stack
        technologies = list(language_scores.keys())
        
        # Recommend MCP servers
        mcp_servers = set()
        for lang in technologies:
            if lang in self.mcp_recommendations:
                mcp_servers.update(self.mcp_recommendations[lang])
        
        # Check capsule type for additional recommendations
        capsule_type = self._get_capsule_type(capsule_path)
        if capsule_type in self.mcp_recommendations:
            mcp_servers.update(self.mcp_recommendations[capsule_type])
        
        return LanguageContext(
            primary_language=primary_language,
            technologies=technologies,
            frameworks=list(detected_frameworks),
            build_tools=list(detected_build_tools),
            mcp_servers=list(mcp_servers),
            confidence=confidence
        )

    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file matches pattern"""
        if pattern.startswith('*.'):
            return file_path.endswith(pattern[1:])
        else:
            return os.path.basename(file_path) == pattern

    def _detect_frameworks_in_file(self, file_path: str) -> Set[str]:
        """Detect frameworks by scanning file content"""
        frameworks = set()
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for framework, indicators in self.framework_patterns.items():
                    if any(indicator in content for indicator in indicators):
                        frameworks.add(framework)
        except:
            pass  # Skip files we can't read
        return frameworks

    def _get_capsule_type(self, capsule_path: Path) -> Optional[str]:
        """Get capsule type from capsule.json"""
        try:
            capsule_json = capsule_path / 'capsule.json'
            if capsule_json.exists():
                with open(capsule_json, 'r') as f:
                    data = json.load(f)
                    return data.get('type', 'unknown')
        except:
            pass
        return 'unknown'

    def generate_mcp_config(self, language_context: LanguageContext, capsule_path: str) -> Dict:
        """Generate MCP configuration for the detected language context"""
        config = {
            "mcpServers": {},
            "detectedContext": asdict(language_context),
            "generatedFor": capsule_path,
            "autoConfigured": True
        }
        
        # Add recommended MCP servers
        for server in language_context.mcp_servers:
            config["mcpServers"][server] = {
                "command": self._get_mcp_server_command(server),
                "args": [],
                "env": {},
                "reason": f"Recommended for {language_context.primary_language}"
            }
        
        return config

    def _get_mcp_server_command(self, server_name: str) -> str:
        """Get command for MCP server based on name"""
        server_commands = {
            'apple-doc-mcp': 'node {{CATALYST_ROOT}}/global/apple-doc-mcp/dist/index.js',
            'xcodebuild-mcp': 'node {{CATALYST_ROOT}}/global/xcodebuildmcp/dist/index.js',
            'n8n-mcp': 'node {{CATALYST_ROOT}}/global/n8n-mcp/dist/index.js',
            'shadcn-ui': 'npx -y @modelcontextprotocol/server-shadcn-ui',
            'git-mcp': 'node {{CATALYST_ROOT}}/global/git-mcp/dist/index.js'
        }
        return server_commands.get(server_name, f'mcp-server-{server_name}')

def main():
    """CLI interface for language detection"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python language_detector.py <capsule_path>")
        sys.exit(1)
    
    capsule_path = sys.argv[1]
    detector = CapsuleLanguageDetector()
    context = detector.detect_capsule_language(capsule_path)
    
    print("=== Language Detection Results ===")
    print(f"Capsule: {capsule_path}")
    print(f"Primary Language: {context.primary_language} (confidence: {context.confidence:.2f})")
    print(f"Technologies: {', '.join(context.technologies)}")
    print(f"Frameworks: {', '.join(context.frameworks)}")
    print(f"Build Tools: {', '.join(context.build_tools)}")
    print(f"Recommended MCP Servers: {', '.join(context.mcp_servers)}")
    
    # Generate MCP config
    mcp_config = detector.generate_mcp_config(context, capsule_path)
    print("\n=== Generated MCP Configuration ===")
    print(json.dumps(mcp_config, indent=2))

if __name__ == '__main__':
    main()