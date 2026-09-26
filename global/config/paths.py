#!/usr/bin/env python3
"""
Centralized path configuration for Huxley
Replaces hardcoded paths with environment-aware configuration

"""

import os
from pathlib import Path
from typing import Optional

class CatalystPaths:
    """Centralized path management for Huxley"""

    def __init__(self, base_path: Optional[str] = None):
        # Determine base path from environment or current working directory
        if base_path:
            self.base = Path(base_path)
        elif os.getenv('CATALYST_ROOT'):
            self.base = Path(os.getenv('CATALYST_ROOT', ''))
        else:
            # Try to find Huxley root by looking for characteristic files
            current = Path.cwd()
            while current != current.parent:
                if (current / 'CLAUDE.md').exists() and (current / 'capsules').exists():
                    self.base = current
                    break
                current = current.parent
            else:
                # Fallback to current directory
                self.base = Path.cwd()

        self.base = self.base.resolve()

    # Core directories
    @property
    def capsules(self) -> Path:
        return self.base / 'capsules'

    @property
    def testing(self) -> Path:
        return self.base / 'testing'

    @property
    def tools(self) -> Path:
        return self.base / 'tools'

    @property
    def global_dir(self) -> Path:
        return self.base / 'global'

    @property
    def registry(self) -> Path:
        return self.base / 'registry'

    @property
    def templates(self) -> Path:
        return self.base / 'templates'

    # RAG system paths
    @property
    def rag(self) -> Path:
        return self.global_dir / 'rag'

    @property
    def rag_service(self) -> Path:
        return self.rag / 'service'

    @property
    def rag_data(self) -> Path:
        """RAG data directory - configurable via env"""
        return Path(os.getenv('CATALYST_RAG_DATA', str(self.rag / 'data')))

    @property
    def global_rag_config(self) -> Path:
        """RAG configuration directory"""
        return self.rag / 'config'

    # Security paths
    @property
    def security(self) -> Path:
        return self.global_dir / 'security'

    # Config paths
    @property
    def config(self) -> Path:
        return self.global_dir / 'config'

    @property
    def claude_config(self) -> Path:
        return self.global_dir / 'claude-config'

    # Log paths
    @property
    def events_log(self) -> Path:
        return self.registry / 'events.jsonl'

    @property
    def daily_logs(self) -> Path:
        return self.registry / 'daily'

    # Memory paths
    @property
    def memory_data(self) -> Path:
        """MCP memory data - respects user's ~/.claude/mcp-data"""
        home_mcp = Path.home() / '.claude' / 'mcp-data'
        return Path(os.getenv('CATALYST_MEMORY_PATH', str(home_mcp)))

    def __str__(self) -> str:
        return str(self.base)

    def relative_to_base(self, path: Path) -> Path:
        """Convert absolute path to relative from base"""
        try:
            return path.relative_to(self.base)
        except ValueError:
            return path


# Global instance
paths = CatalystPaths()

# Environment configuration
class CatalystConfig:
    """Environment-aware configuration"""

    # RAG Service Config
    RAG_HOST = os.getenv('CATALYST_RAG_HOST', '127.0.0.1')
    RAG_PORT = int(os.getenv('CATALYST_RAG_PORT', '8000'))
    RAG_AUTH_TOKEN = os.getenv('CATALYST_RAG_AUTH_TOKEN')
    RAG_ALLOWED_ORIGINS = (os.getenv('CATALYST_RAG_ALLOWED_ORIGINS', '*')).split(',')

    # Model Configuration
    EMBEDDING_MODEL = os.getenv('CATALYST_EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')

    # Logging
    LOG_LEVEL = os.getenv('CATALYST_LOG_LEVEL', 'INFO')

    # Lane Configuration
    DEFAULT_LANE = os.getenv('CATALYST_DEFAULT_LANE', 'standard')

    # Paths
    CATALYST_ROOT = str(paths.base)


config = CatalystConfig()
