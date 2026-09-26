"""
4-Layer Config Resolver for Media Workflow Configs.

Resolves the full configuration by merging four layers in order:

    base-defaults.yaml -> template.yaml -> capsule.yaml -> runtime overrides

Merge semantics:
  - Objects (dicts): deep merge (child fields override parent fields)
  - Arrays (lists): replace (child array fully replaces parent's)
  - Scalars: override (last layer wins)
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from engine.loader import ConfigLoader, ConfigLoadError
from engine.schema import validate, dict_to_workflow, WorkflowConfig


class ConfigResolver:
    """
    Resolves a 4-layer config inheritance chain into a single merged config.

    Layers (in order of increasing precedence):
      1. base-defaults.yaml   - Global fallback values
      2. workflow template     - The named workflow file
      3. capsule config        - Per-capsule overrides (optional)
      4. runtime overrides     - CLI/agent-provided overrides (optional)
    """

    def __init__(self, loader: ConfigLoader | None = None) -> None:
        self.loader = loader or ConfigLoader()

    def resolve_config(
        self,
        workflow: str,
        capsule_config: str | None = None,
        runtime_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Resolve the full 4-layer config for a workflow.

        Args:
            workflow: Name of the workflow template (looked up in workflows/).
            capsule_config: Optional path to a capsule-level config YAML file.
            runtime_overrides: Optional dict of runtime overrides (highest precedence).

        Returns:
            A fully merged config dict ready for use by the generator.

        Raises:
            ConfigLoadError: If any required config file is missing or invalid.
        """
        # Layer 1: base defaults
        try:
            base = self.loader.load_base_defaults()
        except ConfigLoadError:
            # If no base-defaults.yaml exists, start with empty dict.
            base = {}

        # Layer 2: workflow template
        template = self.loader.load_workflow(workflow)

        # If the template references a profile, load and merge it between
        # base defaults and the template itself.
        profile_name = template.get("profile", "") or base.get("profile", "")
        profile: dict[str, Any] = {}
        if profile_name:
            try:
                profile = self.loader.load_profile(profile_name)
            except ConfigLoadError:
                # Profile is optional; if it doesn't exist, skip silently.
                pass

        # Layer 3: capsule overrides
        capsule: dict[str, Any] = {}
        if capsule_config:
            capsule_path = Path(capsule_config)
            if capsule_path.exists():
                raw_capsule = self.loader.load_yaml(capsule_path)
                # Support two capsule config formats:
                #   1. Wrapper format: { extends: ..., overrides: { ... } }
                #   2. Flat format: { generation: ..., refinement: ..., ... }
                if "overrides" in raw_capsule and isinstance(raw_capsule["overrides"], dict):
                    capsule = raw_capsule["overrides"]
                else:
                    capsule = raw_capsule
            else:
                raise ConfigLoadError(f"Capsule config not found: {capsule_config}")

        # Layer 4: runtime overrides
        runtime = runtime_overrides or {}

        # Merge all layers: base <- profile <- template <- capsule <- runtime
        merged = base
        merged = deep_merge(merged, profile)
        merged = deep_merge(merged, template)
        merged = deep_merge(merged, capsule)
        merged = deep_merge(merged, runtime)

        # Final validation on the merged result
        errors = validate(merged)
        if errors:
            msg = "Validation errors in resolved config:\n"
            msg += "\n".join(f"  - {e}" for e in errors)
            raise ConfigLoadError(msg)

        return merged

    def resolve_to_dataclass(
        self,
        workflow: str,
        capsule_config: str | None = None,
        runtime_overrides: dict[str, Any] | None = None,
    ) -> WorkflowConfig:
        """
        Resolve the config and return it as a WorkflowConfig dataclass.

        Convenience wrapper around resolve_config() + dict_to_workflow().
        """
        merged = self.resolve_config(workflow, capsule_config, runtime_overrides)
        return dict_to_workflow(merged)

    @staticmethod
    def show_resolved(config: dict[str, Any]) -> str:
        """
        Pretty-print a resolved config dict for debugging.

        Returns a human-readable string representation.
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("  Resolved Media Workflow Config")
        lines.append("=" * 60)
        lines.append("")

        # Top-level scalars
        top_keys = ["name", "media_type", "model", "auth", "auth_provider", "profile"]
        for key in top_keys:
            if key in config:
                lines.append(f"  {key}: {config[key]}")

        lines.append("")

        # Nested sections
        sections = [
            "generation", "refinement", "consistency",
            "variants", "output", "provenance",
        ]
        for section in sections:
            if section in config and isinstance(config[section], dict):
                lines.append(f"  [{section}]")
                for k, v in config[section].items():
                    lines.append(f"    {k}: {_format_value(v)}")
                lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deep merge utility
# ---------------------------------------------------------------------------

def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dicts with the following semantics:

      - Dicts: recursively merge (child keys override parent keys)
      - Lists: replace entirely (child list replaces parent list)
      - Scalars: override (child value replaces parent value)

    Returns a new dict without mutating either input.
    """
    result = copy.deepcopy(base)

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result


def _format_value(v: Any) -> str:
    """Format a value for display in show_resolved output."""
    if isinstance(v, list):
        return json.dumps(v)
    if isinstance(v, bool):
        return str(v).lower()
    return str(v)
