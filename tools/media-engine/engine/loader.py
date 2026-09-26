"""
YAML Loader for Media Workflow Configs.

Handles loading workflow definitions, parameter profiles, and base defaults
from the filesystem. Validates each file against the schema on load.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from engine.schema import validate

# Engine root directory (absolute)
ENGINE_ROOT = Path("{{CATALYST_ROOT}}/tools/media-engine")
WORKFLOWS_DIR = ENGINE_ROOT / "workflows"
PROFILES_DIR = ENGINE_ROOT / "profiles"
BASE_DEFAULTS_PATH = ENGINE_ROOT / "base-defaults.yaml"


class ConfigLoadError(Exception):
    """Raised when a config file cannot be loaded or is invalid."""


class ConfigLoader:
    """
    Loads and validates YAML configuration files for the media engine.

    Provides access to workflows, profiles, and the base defaults file.
    All paths are resolved relative to the engine root directory.
    """

    def __init__(
        self,
        engine_root: str | Path | None = None,
    ) -> None:
        self.engine_root = Path(engine_root) if engine_root else ENGINE_ROOT
        self.workflows_dir = self.engine_root / "workflows"
        self.profiles_dir = self.engine_root / "profiles"
        self.base_defaults_path = self.engine_root / "base-defaults.yaml"

    # ------------------------------------------------------------------
    # Low-level loader
    # ------------------------------------------------------------------

    @staticmethod
    def load_yaml(path: str | Path) -> dict[str, Any]:
        """
        Load a single YAML file and return its contents as a dict.

        Raises ConfigLoadError if the file does not exist, is not valid YAML,
        or is empty.
        """
        path = Path(path)
        if not path.exists():
            raise ConfigLoadError(f"File not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ConfigLoadError(f"Invalid YAML in {path}: {exc}") from exc

        if data is None:
            raise ConfigLoadError(f"Empty YAML file: {path}")

        if not isinstance(data, dict):
            raise ConfigLoadError(
                f"Expected a mapping at top level in {path}, got {type(data).__name__}"
            )

        return data

    # ------------------------------------------------------------------
    # Profile loader
    # ------------------------------------------------------------------

    def load_profile(self, name: str) -> dict[str, Any]:
        """
        Load a parameter profile from the profiles/ directory.

        The profile name can include or omit the .yaml/.yml extension.
        Profile files are NOT validated against the full workflow schema
        because they contain partial parameter sets intended to be merged.
        """
        path = self._resolve_yaml_path(self.profiles_dir, name)
        return self.load_yaml(path)

    # ------------------------------------------------------------------
    # Workflow loader
    # ------------------------------------------------------------------

    def load_workflow(self, name: str) -> dict[str, Any]:
        """
        Load a workflow definition from the workflows/ directory.

        Validates the loaded config against the schema. Raises ConfigLoadError
        if validation fails.
        """
        path = self._resolve_yaml_path(self.workflows_dir, name)
        data = self.load_yaml(path)

        errors = validate(data)
        if errors:
            msg = f"Validation errors in {path}:\n"
            msg += "\n".join(f"  - {e}" for e in errors)
            raise ConfigLoadError(msg)

        return data

    # ------------------------------------------------------------------
    # Base defaults loader
    # ------------------------------------------------------------------

    def load_base_defaults(self) -> dict[str, Any]:
        """
        Load the base-defaults.yaml file from the engine root.

        This file provides fallback values for all config fields.
        """
        return self.load_yaml(self.base_defaults_path)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def list_workflows(self) -> list[str]:
        """Return the names of all available workflow files (without extension)."""
        return self._list_yamls(self.workflows_dir)

    def list_profiles(self) -> list[str]:
        """Return the names of all available profile files (without extension)."""
        return self._list_yamls(self.profiles_dir)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_yaml_path(directory: Path, name: str) -> Path:
        """
        Resolve a YAML filename inside a directory.

        Tries name as-is, then with .yaml, then with .yml extension.
        """
        # If the name already has an extension and exists, use it directly.
        candidate = directory / name
        if candidate.exists():
            return candidate

        for ext in (".yaml", ".yml"):
            candidate = directory / f"{name}{ext}"
            if candidate.exists():
                return candidate

        raise ConfigLoadError(
            f"No YAML file found for '{name}' in {directory}. "
            f"Tried: {name}, {name}.yaml, {name}.yml"
        )

    @staticmethod
    def _list_yamls(directory: Path) -> list[str]:
        """List YAML files in a directory, returning stem names."""
        if not directory.exists():
            return []

        names: list[str] = []
        for entry in sorted(directory.iterdir()):
            if entry.suffix in (".yaml", ".yml") and entry.is_file():
                names.append(entry.stem)
        return names
