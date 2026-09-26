#!/usr/bin/env python3
"""
Sync MCP configurations for Claude Code and Codex.

This script builds consolidated MCP maps from the central registry and writes:
- Huxley/.mcp.json (project-level Claude config)
- ~/.claude/mcp_servers.json (global Claude config, optional)
- ~/.code/config.toml (Codex config with aligned mcp_servers blocks)

Codex entries mirror the JSON configuration but are emitted as TOML tables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, Tuple, Any

import tomllib

from mcp_platform_loader import MCPPlatformLoader


ROOT = Path(__file__).resolve().parent.parent


def _combine_scopes(
    loader: MCPPlatformLoader,
    scopes: Iterable[str],
) -> Dict[str, Any]:
    """Merge multiple scope configs into a single map."""
    combined_servers: Dict[str, Dict[str, Any]] = {}
    skipped: set[str] = set()
    version = None
    description = []
    environment = None

    for scope in scopes:
        cfg = loader.generate_filtered_config(scope)
        version = version or cfg.get("version")
        if cfg.get("description"):
            description.append(f"{scope}: {cfg['description']}")
        environment = environment or cfg.get("environment")

        for name, entry in cfg.get("mcpServers", {}).items():
            combined_servers[name] = entry

        skipped.update(cfg.get("skipped_servers", []))

    merged = {
        "version": version or "1.0.0",
        "description": " + ".join(description) if description else "",
        "platform": loader.platform,
        "environment": environment or {},
        "mcpServers": combined_servers,
    }

    if skipped:
        merged["skipped_servers"] = sorted(skipped)

    return merged


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _format_scalar(value: Any) -> str:
    import json as _json

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return _json.dumps(value)


def _format_inline_table(mapping: Dict[str, Any]) -> str:
    import json as _json

    parts = []
    for key, value in mapping.items():
        if isinstance(value, dict):
            parts.append(f"{_json.dumps(key)} = {_format_inline_table(value)}")
        else:
            parts.append(f"{_json.dumps(key)} = {_format_scalar(value)}")
    return "{ " + ", ".join(parts) + " }"


def _render_nested_tables(prefix: str, table: Dict[str, Any]) -> str:
    """Render nested dicts as TOML tables (e.g., [tui.cached_terminal_background])."""
    lines: list[str] = []
    for key in sorted(table):
        value = table[key]
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            lines.append(f"[{full}]")
            for inner_key in sorted(value):
                inner_value = value[inner_key]
                if isinstance(inner_value, dict):
                    lines.append("")  # spacing before deeper nesting
                    lines.append(_render_nested_tables(full, {inner_key: inner_value}))
                else:
                    lines.append(f"{inner_key} = {_format_scalar(inner_value)}")
            lines.append("")
        else:
            lines.append(f"{full} = {_format_scalar(value)}")
    return "\n".join(line for line in lines if line.strip() != "")


def _render_non_mcp_config(data: Dict[str, Any]) -> str:
    """Serialize config entries excluding the MCP section."""
    order = [
        "projects",
        "model",
        "model_provider",
        "approval_policy",
        "sandbox_mode",
        "default_profile",
        "profiles",
        "tui",
    ]
    seen = set()
    lines: list[str] = []

    for key in order:
        if key not in data:
            continue
        value = data[key]
        seen.add(key)

        if key == "projects" and isinstance(value, dict):
            lines.append(f"projects = {_format_inline_table(value)}")
            lines.append("")
        elif key == "profiles" and isinstance(value, dict):
            for profile_name in sorted(value):
                lines.append(f"[profiles.{profile_name}]")
                profile_table = value[profile_name]
                for inner_key, inner_value in sorted(profile_table.items()):
                    if isinstance(inner_value, dict):
                        lines.append(
                            _render_nested_tables(f"profiles.{profile_name}.{inner_key}", inner_value)
                        )
                    else:
                        lines.append(f"{inner_key} = {_format_scalar(inner_value)}")
                lines.append("")
        elif key == "tui" and isinstance(value, dict):
            lines.append(_render_nested_tables("tui", value))
            lines.append("")
        else:
            lines.append(f"{key} = {_format_scalar(value)}")
            lines.append("")

    for key, value in sorted(data.items()):
        if key in seen or key == "mcp_servers":
            continue
        if isinstance(value, dict):
            lines.append(f"[{key}]")
            for inner_key, inner_value in sorted(value.items()):
                if isinstance(inner_value, dict):
                    lines.append(
                        _render_nested_tables(f"{key}.{inner_key}", inner_value)
                    )
                else:
                    lines.append(f"{inner_key} = {_format_scalar(inner_value)}")
            lines.append("")
        else:
            lines.append(f"{key} = {_format_scalar(value)}")
            lines.append("")

    return "\n".join(line for line in lines if line.strip() != "")


def _write_claude_configs(loader: MCPPlatformLoader) -> None:
    project_scopes = ["global", "project", "development"]
    project_config = _combine_scopes(loader, project_scopes)
    project_path = ROOT / ".mcp.json"
    _ensure_parent(project_path)
    project_path.write_text(json.dumps(project_config, indent=2) + "\n", encoding="utf-8")
    print(f"Updated Claude project config: {project_path}")

    claude_home = Path.home() / ".claude" / "mcp_servers.json"
    _ensure_parent(claude_home)
    # Only global scope for user-level config
    global_config = loader.generate_filtered_config("global")
    claude_home.write_text(json.dumps(global_config, indent=2) + "\n", encoding="utf-8")
    print(f"Updated Claude user config: {claude_home}")


def _write_codex_config(loader: MCPPlatformLoader) -> None:
    codex_home = Path.home() / ".code"
    codex_config_path = codex_home / "config.toml"

    if codex_config_path.exists():
        data = tomllib.loads(codex_config_path.read_text(encoding="utf-8"))
    else:
        data = {}

    scopes = ["global", "project", "development"]
    filtered = _combine_scopes(loader, scopes)

    codex_entries: Dict[str, Dict[str, Any]] = {}
    for name, entry in filtered.get("mcpServers", {}).items():
        command = entry.get("command")
        if not command:
            continue
        args = entry.get("args", [])
        env = entry.get("env") or {}
        codex_entries[name] = {"command": command}
        if args:
            codex_entries[name]["args"] = args
        if env:
            codex_entries[name]["env"] = env

    data["mcp_servers"] = codex_entries

    non_mcp = _render_non_mcp_config({k: v for k, v in data.items() if k != "mcp_servers"})
    filtered_dict = {
        "mcpServers": filtered.get("mcpServers", {}),
        "skipped_servers": filtered.get("skipped_servers", []),
    }
    mcp_toml = loader.generate_codex_toml_from_filtered(
        filtered_dict,
        profile="catalyst",
        scope_label="global+project+development",
    )

    lines = []
    if non_mcp.strip():
        lines.append(non_mcp.strip())
        lines.append("")

    lines.append("# === Autogenerated MCP configuration (Huxley) ===")
    lines.append(mcp_toml.rstrip())
    lines.append("")

    _ensure_parent(codex_config_path)
    codex_config_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Updated Codex config: {codex_config_path}")


def main() -> None:
    loader = MCPPlatformLoader(project_root=str(ROOT))
    _write_claude_configs(loader)
    _write_codex_config(loader)


if __name__ == "__main__":
    main()
