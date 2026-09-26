#!/usr/bin/env python3
"""
MCP Platform Loader - Dynamically load MCPs based on platform detection
Implements profile gating for cross-platform compatibility
"""

import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class MCPPlatformLoader:
    """Loads MCPs with platform-specific profile gating"""
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.platform = platform.system().lower()
        self.is_ci = os.getenv('CI', '').lower() in ('true', '1', 'yes')
        self.node_env = os.getenv('NODE_ENV', 'development')
        
    def load_registry(self) -> Dict[str, Any]:
        """Load the central server registry"""
        registry_path = self.project_root / "global" / "mcp" / "server-registry.json"
        
        if not registry_path.exists():
            raise FileNotFoundError(f"Server registry not found: {registry_path}")
            
        with open(registry_path) as f:
            return json.load(f)
    
    def should_load_profile(self, profile_name: str, profile_config: Dict[str, Any]) -> bool:
        """Determine if a profile should be loaded based on current environment"""
        condition = profile_config.get('condition', '')
        
        # Parse condition string (basic implementation)
        if 'process.platform' in condition:
            if 'darwin' in condition and self.platform != 'darwin':
                return False
            if 'linux' in condition and self.platform != 'linux': 
                return False
            if 'win32' in condition and self.platform != 'windows':
                return False
                
        if 'NODE_ENV' in condition:
            if 'production' in condition and self.node_env == 'production':
                return '!== \'production\'' not in condition
            if 'development' in condition and self.node_env == 'development':
                return '!== \'development\'' not in condition
                
        # CI environment check
        if self.is_ci and profile_name == 'macos':
            return False
            
        return True
    
    def filter_servers_by_profiles(self, registry: Dict[str, Any]) -> List[str]:
        """Filter servers based on active profiles"""
        active_servers = []
        profiles = registry.get('profiles', {})
        
        for profile_name, profile_config in profiles.items():
            if self.should_load_profile(profile_name, profile_config):
                profile_servers = profile_config.get('servers', [])
                active_servers.extend(profile_servers)
                print(f"✓ Profile '{profile_name}' active - loaded {len(profile_servers)} servers")
            else:
                profile_servers = profile_config.get('servers', [])
                print(f"✗ Profile '{profile_name}' skipped ({len(profile_servers)} servers)")
                
        return active_servers
    
    def generate_filtered_config(self, scope: str = "project") -> Dict[str, Any]:
        """Generate MCP config filtered by platform and profiles"""
        registry = self.load_registry()
        active_profile_servers = set(self.filter_servers_by_profiles(registry))
        
        servers = registry.get('servers', {})
        scopes = registry.get('scopes', {})
        scope_servers = scopes.get(scope, {}).get('servers', [])
        
        filtered_servers = {}
        skipped_servers = []
        
        for server_name in scope_servers:
            server_config = servers.get(server_name, {})
            server_profile = server_config.get('profile')
            
            # Check if server requires a profile that's not active
            if server_profile and server_name not in active_profile_servers:
                skipped_servers.append(f"{server_name} (profile: {server_profile})")
                continue
                
            # Include server in filtered config
            filtered_entry: Dict[str, Any] = {}

            if "command" in server_config and server_config.get("command"):
                filtered_entry["command"] = server_config.get("command")

            args = server_config.get("args", [])
            if args:
                filtered_entry["args"] = args

            env = server_config.get("env", {})
            if env:
                filtered_entry["env"] = env

            description = server_config.get("description")
            if description:
                filtered_entry["description"] = description

            filtered_servers[server_name] = filtered_entry
            
            # Handle special server types
            if "url" in server_config:
                filtered_servers[server_name]["url"] = server_config["url"]
            if "headers" in server_config:
                filtered_servers[server_name]["headers"] = server_config["headers"]
        
        result = {
            "version": "1.0.0",
            "description": f"Platform-filtered MCP config for {self.platform} ({scope} scope)",
            "platform": self.platform,
            "environment": {
                "NODE_ENV": self.node_env,
                "CI": self.is_ci
            },
            "mcpServers": filtered_servers
        }
        
        if skipped_servers:
            result["skipped_servers"] = skipped_servers
            
        return result

    def _format_toml_array(self, values: List[str]) -> str:
        """Render a Python list of strings as a TOML array."""
        import json
        return "[" + ", ".join(json.dumps(v) for v in values) + "]"

    def _format_toml_inline_table(self, mapping: Dict[str, str]) -> str:
        """Render a mapping as a TOML inline table."""
        import json
        items = []
        for key in sorted(mapping):
            items.append(f"{json.dumps(key)} = {json.dumps(mapping[key])}")
        return "{ " + ", ".join(items) + " }"

    def generate_codex_toml_from_filtered(
        self,
        filtered: Dict[str, Any],
        profile: str = "catalyst",
        scope_label: str | None = None,
    ) -> str:
        """Render a Codex TOML string from a pre-filtered server set."""
        servers: Dict[str, Dict[str, Any]] = filtered.get("mcpServers", {})

        lines: List[str] = []
        scope_text = scope_label or "combined"
        lines.append(
            f"# Autogenerated by tools/mcp_platform_loader.py for Codex (scope={scope_text}, platform={self.platform})"
        )
        lines.append("# Do not edit manually; re-run the loader to refresh.")
        lines.append("")
        lines.append(f'default_profile = "{profile}"')
        lines.append("")

        skipped_for_codex: List[str] = []

        for name in sorted(servers):
            entry = servers[name]
            command = entry.get("command")
            args = entry.get("args", [])
            env = entry.get("env") or {}

            if not command:
                skipped_for_codex.append(f"{name} (missing command)")
                continue

            lines.append(f"[mcp_servers.{name}]")
            lines.append(f'command = "{command}"')

            if args:
                lines.append(f"args = {self._format_toml_array(args)}")

            if env:
                lines.append(f"env = {self._format_toml_inline_table(env)}")

            description = entry.get("description")
            if description:
                lines.append(f"# {description}")

            lines.append("")

        if filtered.get("skipped_servers"):
            lines.append("# Skipped due to inactive profiles:")
            for server in filtered["skipped_servers"]:
                lines.append(f"# - {server}")
            lines.append("")

        if skipped_for_codex:
            lines.append("# Skipped in Codex export (unsupported transport or missing command):")
            for server in skipped_for_codex:
                lines.append(f"# - {server}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def generate_codex_toml(
        self,
        scope: str = "project",
        profile: str = "catalyst",
    ) -> str:
        """
        Generate a Codex-compatible TOML configuration.

        Mirrors the filtered JSON config but emits `[mcp_servers.<name>]` blocks.
        Only stdio-based servers are included because Codex currently expects
        command/args/env configuration for each entry.
        """
        filtered = self.generate_filtered_config(scope)
        return self.generate_codex_toml_from_filtered(filtered, profile, scope_label=scope)
    
    def validate_environment(self) -> Dict[str, Any]:
        """Validate current environment for MCP compatibility"""
        issues = []
        warnings = []
        
        # Check for macOS-specific requirements
        if self.platform == 'darwin':
            # Check for required macOS tools
            macos_tools = ['osascript', 'shortcuts']
            for tool in macos_tools:
                if not self.command_exists(tool):
                    warnings.append(f"macOS tool '{tool}' not found - some MCPs may fail")
        
        # Check CI compatibility  
        if self.is_ci:
            ci_incompatible = ['applescript', 'iterm-mcp', 'siri-shortcuts']
            for server in ci_incompatible:
                issues.append(f"Server '{server}' not compatible with CI environment")
        
        return {
            "platform": self.platform,
            "ci_environment": self.is_ci,
            "node_env": self.node_env,
            "issues": issues,
            "warnings": warnings,
            "compatible": len(issues) == 0
        }
    
    def command_exists(self, command: str) -> bool:
        """Check if command exists in PATH"""
        return shutil.which(command) is not None


def main():
    """CLI interface for MCP platform loader"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Platform Loader")
    parser.add_argument("--scope", default="project", choices=["global", "project", "capsule"],
                       help="Configuration scope to generate")
    parser.add_argument("--validate", action="store_true",
                       help="Validate environment compatibility")
    parser.add_argument("--output", help="Output file path for Claude configuration (JSON)")
    parser.add_argument("--codex-output", help="Output file path for Codex configuration (TOML)")
    parser.add_argument("--codex-profile", default="catalyst",
                       help="Codex profile name to mark as default in generated TOML")
    parser.add_argument("--project-root", help="Project root directory")
    
    args = parser.parse_args()
    
    try:
        loader = MCPPlatformLoader(args.project_root)
        
        if args.validate:
            validation = loader.validate_environment()
            print(json.dumps(validation, indent=2))
            
            if not validation["compatible"]:
                print("\n❌ Environment has compatibility issues")
                sys.exit(1)
            else:
                print("\n✅ Environment is compatible")
                
        else:
            config = loader.generate_filtered_config(args.scope)
            codex_toml = None

            if args.codex_output:
                codex_toml = loader.generate_codex_toml(
                    scope=args.scope,
                    profile=args.codex_profile,
                )
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"Generated {args.scope} config (Claude): {args.output}")
            else:
                print(json.dumps(config, indent=2))

            if args.codex_output and codex_toml is not None:
                Path(args.codex_output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.codex_output).write_text(codex_toml, encoding="utf-8")
                print(f"Generated {args.scope} config (Codex): {args.codex_output}")
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
