"""
State isolation and cleanup for agentic loops.

Provides temporary directories and environment isolation.
"""

import atexit
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StateIsolation:
    """
    Provides isolated state for agentic loop execution.

    Manages temporary directories, environment variables, and cleanup.
    """

    # Configuration
    base_dir: Path | None = None
    preserve_on_success: bool = False
    preserve_on_failure: bool = True

    # State
    temp_dir: Path | None = field(default=None, init=False)
    original_env: dict[str, str] = field(default_factory=dict, init=False)
    original_cwd: Path | None = field(default=None, init=False)
    cleanup_handlers: list[callable] = field(default_factory=list, init=False)
    _initialized: bool = field(default=False, init=False)

    def __post_init__(self):
        """Register cleanup on exit."""
        atexit.register(self.cleanup)

    def initialize(self) -> Path:
        """
        Initialize isolated state.

        Returns:
            Path to temporary directory
        """
        if self._initialized:
            return self.temp_dir

        # Create temp directory
        if self.base_dir:
            self.base_dir = Path(self.base_dir)
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.temp_dir = Path(tempfile.mkdtemp(dir=self.base_dir))
        else:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="agent_loop_"))

        # Store original working directory
        self.original_cwd = Path.cwd()

        # Store original environment
        self.original_env = os.environ.copy()

        self._initialized = True
        return self.temp_dir

    def get_temp_dir(self) -> Path:
        """
        Get temporary directory, initializing if needed.

        Returns:
            Path to temp directory
        """
        if not self._initialized:
            return self.initialize()
        return self.temp_dir

    def isolate_environment(self, env_vars: dict[str, str]) -> None:
        """
        Set environment variables for isolated execution.

        Args:
            env_vars: Environment variables to set
        """
        for key, value in env_vars.items():
            os.environ[key] = value

    def restore_environment(self) -> None:
        """Restore original environment variables."""
        # Clear current env
        os.environ.clear()

        # Restore original
        os.environ.update(self.original_env)

    def change_to_temp_dir(self) -> None:
        """Change working directory to temp dir."""
        if not self._initialized:
            self.initialize()
        os.chdir(self.temp_dir)

    def restore_cwd(self) -> None:
        """Restore original working directory."""
        if self.original_cwd:
            os.chdir(self.original_cwd)

    def register_cleanup_handler(self, handler: callable) -> None:
        """
        Register custom cleanup handler.

        Args:
            handler: Cleanup function to call
        """
        self.cleanup_handlers.append(handler)

    def cleanup(self, success: bool = False) -> None:
        """
        Cleanup isolated state.

        Args:
            success: Whether loop succeeded
        """
        if not self._initialized:
            return

        # Run custom cleanup handlers
        for handler in self.cleanup_handlers:
            try:
                handler()
            except Exception as e:
                print(f"Warning: Cleanup handler failed: {e}")

        # Restore environment
        self.restore_environment()

        # Restore working directory
        self.restore_cwd()

        # Clean up temp directory
        should_preserve = (success and self.preserve_on_success) or (
            not success and self.preserve_on_failure
        )

        if not should_preserve and self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"Warning: Failed to remove temp dir {self.temp_dir}: {e}")

        self._initialized = False

    def copy_file_to_temp(self, source: Path, dest_name: str | None = None) -> Path:
        """
        Copy file to temp directory.

        Args:
            source: Source file path
            dest_name: Optional destination filename

        Returns:
            Path to copied file
        """
        if not self._initialized:
            self.initialize()

        dest_path = self.temp_dir / (dest_name or source.name)
        shutil.copy2(source, dest_path)
        return dest_path

    def copy_directory_to_temp(self, source: Path, dest_name: str | None = None) -> Path:
        """
        Copy directory to temp directory.

        Args:
            source: Source directory path
            dest_name: Optional destination directory name

        Returns:
            Path to copied directory
        """
        if not self._initialized:
            self.initialize()

        dest_path = self.temp_dir / (dest_name or source.name)
        shutil.copytree(source, dest_path)
        return dest_path

    def create_subdirectory(self, name: str) -> Path:
        """
        Create subdirectory in temp dir.

        Args:
            name: Subdirectory name

        Returns:
            Path to subdirectory
        """
        if not self._initialized:
            self.initialize()

        subdir = self.temp_dir / name
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir

    def get_isolated_path(self, relative_path: str) -> Path:
        """
        Get path within isolated temp directory.

        Args:
            relative_path: Relative path

        Returns:
            Absolute path in temp dir
        """
        if not self._initialized:
            self.initialize()

        return self.temp_dir / relative_path

    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        success = exc_type is None
        self.cleanup(success=success)
