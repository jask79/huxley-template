#!/usr/bin/env python3
"""
Huxley Common Utilities
Centralized utilities for configuration, validation, logging, and error handling
"""

import os
import sys
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from datetime import datetime

# Core environment setup
CATALYST_ROOT = os.environ.get('CATALYST_ROOT', '{{CATALYST_ROOT}}')
HOME_DIR = os.environ.get('HOME', '{{HOME_DIR}}')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('builder')


class BuilderSecurityError(Exception):
    """Security violation in Huxley"""
    pass


class BuilderValidationError(Exception):
    """Validation error in Huxley"""
    pass


class BuilderConfigError(Exception):
    """Configuration error in Huxley"""
    pass


class PathValidator:
    """Secure path validation for Huxley operations"""
    
    @staticmethod
    def validate_path(path: str, description: str = "Path") -> Path:
        """
        Validate that a path is safe and within Huxley boundaries
        
        Args:
            path: Path to validate
            description: Description for error messages
            
        Returns:
            Validated Path object
            
        Raises:
            BuilderSecurityError: If path is unsafe
        """
        # Convert to absolute path
        abs_path = os.path.abspath(os.path.expanduser(path))
        
        # Check for dangerous characters
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in abs_path for char in dangerous_chars):
            raise BuilderSecurityError(f"{description} contains unsafe characters: {path}")
        
        # Check for path traversal attempts
        if '..' in abs_path:
            raise BuilderSecurityError(f"{description} contains path traversal: {path}")
        
        # Ensure path is within Huxley directory or HOME for configs
        allowed_roots = [CATALYST_ROOT, HOME_DIR]
        if not any(abs_path.startswith(root) for root in allowed_roots):
            raise BuilderSecurityError(f"{description} outside allowed directories: {path}")
        
        return Path(abs_path)
    
    @staticmethod
    def validate_command(command: str) -> str:
        """
        Validate shell command for safety
        
        Args:
            command: Command to validate
            
        Returns:
            Validated command
            
        Raises:
            BuilderSecurityError: If command is unsafe
        """
        # Block dangerous commands
        dangerous_patterns = [
            r'rm\s+-rf\s+/',  # rm -rf /
            r'rm\s+-rf\s+\*',  # rm -rf *
            r'chmod\s+777',  # chmod 777
            r'sudo\s+',  # sudo commands
            r'eval\s+',  # eval
            r'exec\s+',  # exec
            r'>\s*/dev/s',  # overwrite devices
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise BuilderSecurityError(f"Dangerous command pattern detected: {pattern}")
        
        return command


class ConfigManager:
    """Centralized configuration management for Huxley"""
    
    def __init__(self):
        self.config_cache = {}
        self.validator = PathValidator()
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load Huxley configuration with validation
        
        Args:
            config_path: Optional path to config file
            
        Returns:
            Configuration dictionary
        """
        if config_path is None:
            config_path = os.path.join(CATALYST_ROOT, 'global', 'config', 'config.json')
        
        # Validate path
        safe_path = self.validator.validate_path(config_path, "Config file")
        
        # Check cache
        cache_key = str(safe_path)
        if cache_key in self.config_cache:
            return self.config_cache[cache_key]
        
        # Load and validate config
        try:
            with open(safe_path, 'r') as f:
                config = json.load(f)
            
            # Validate required fields
            self._validate_config_schema(config)
            
            # Cache and return
            self.config_cache[cache_key] = config
            return config
            
        except FileNotFoundError:
            raise BuilderConfigError(f"Config file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise BuilderConfigError(f"Invalid JSON in config: {e}")
    
    def _validate_config_schema(self, config: Dict[str, Any]) -> None:
        """Validate configuration schema"""
        required_sections = ['system', 'features', 'security']
        for section in required_sections:
            if section not in config:
                raise BuilderConfigError(f"Missing required config section: {section}")


class ErrorHandler:
    """Centralized error handling for Huxley"""
    
    @staticmethod
    def handle_error(operation: str, error: Exception, context: Optional[Dict] = None):
        """
        Handle errors consistently across Huxley
        
        Args:
            operation: Operation that failed
            error: Exception that occurred
            context: Optional context information
        """
        # Log error with context
        error_msg = f"Operation '{operation}' failed: {str(error)}"
        if context:
            error_msg += f" | Context: {context}"
        
        logger.error(error_msg)
        
        # Determine severity and response
        if isinstance(error, BuilderSecurityError):
            logger.critical(f"SECURITY VIOLATION: {error_msg}")
            sys.exit(1)  # Exit immediately for security issues
        elif isinstance(error, (BuilderValidationError, BuilderConfigError)):
            logger.error(f"VALIDATION ERROR: {error_msg}")
            raise error  # Re-raise for handling by caller
        else:
            logger.exception(f"UNEXPECTED ERROR: {error_msg}")
            raise error


class CapsuleManager:
    """Utilities for capsule operations"""
    
    def __init__(self):
        self.validator = PathValidator()
    
    def get_capsule_info(self, capsule_path: str) -> Dict[str, Any]:
        """
        Get capsule information safely
        
        Args:
            capsule_path: Path to capsule
            
        Returns:
            Capsule information dictionary
        """
        safe_path = self.validator.validate_path(capsule_path, "Capsule path")
        
        info = {
            'path': str(safe_path),
            'name': safe_path.name,
            'exists': safe_path.exists(),
        }
        
        # Check for capsule.json
        capsule_json = safe_path / 'capsule.json'
        if capsule_json.exists():
            try:
                with open(capsule_json, 'r') as f:
                    capsule_data = json.load(f)
                info['metadata'] = capsule_data
            except Exception as e:
                logger.warning(f"Could not read capsule.json: {e}")
        
        return info
    
    def validate_capsule_structure(self, capsule_path: str) -> bool:
        """
        Validate capsule directory structure
        
        Args:
            capsule_path: Path to capsule
            
        Returns:
            True if valid structure
        """
        safe_path = self.validator.validate_path(capsule_path, "Capsule path")
        
        required_dirs = ['docs', 'src', 'tests', 'logs']
        for dir_name in required_dirs:
            if not (safe_path / dir_name).exists():
                logger.warning(f"Missing required directory: {dir_name}")
                return False
        
        return True


class AgentRegistry:
    """Utilities for agent management"""
    
    def __init__(self):
        self.validator = PathValidator()
        self.agents = {}
    
    def discover_agents(self) -> List[Dict[str, Any]]:
        """
        Discover available agents
        
        Returns:
            List of agent information
        """
        agent_dirs = [
            os.path.join(CATALYST_ROOT, 'global', 'agent-os'),
            os.path.join(HOME_DIR, '.claude', 'agents'),
        ]
        
        agents = []
        for agent_dir in agent_dirs:
            if os.path.exists(agent_dir):
                try:
                    safe_dir = self.validator.validate_path(agent_dir, "Agent directory")
                    for item in safe_dir.iterdir():
                        if item.is_dir() and (item / 'prompt.md').exists():
                            agents.append({
                                'name': item.name,
                                'path': str(item),
                                'scope': 'global' if 'global' in str(item) else 'local'
                            })
                except Exception as e:
                    logger.warning(f"Could not scan agent directory {agent_dir}: {e}")
        
        return agents


def setup_environment():
    """Setup Huxley environment variables"""
    os.environ['CATALYST_ROOT'] = CATALYST_ROOT
    os.environ['BUILDER_HOME'] = HOME_DIR
    
    # Add tools to PATH if not already there
    tools_dir = os.path.join(CATALYST_ROOT, 'tools')
    if tools_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = f"{tools_dir}:{os.environ.get('PATH', '')}"


def get_timestamp(format_str: str = "%Y%m%d_%H%M%S") -> str:
    """Get formatted timestamp"""
    return datetime.now().strftime(format_str)


def safe_json_dump(data: Any, indent: int = 2) -> str:
    """Safely dump data to JSON string"""
    try:
        return json.dumps(data, indent=indent, default=str)
    except Exception as e:
        logger.error(f"JSON serialization failed: {e}")
        return "{}"


# Initialize on import
setup_environment()

# Export main classes and functions
__all__ = [
    'CATALYST_ROOT',
    'HOME_DIR',
    'logger',
    'BuilderSecurityError',
    'BuilderValidationError',
    'BuilderConfigError',
    'PathValidator',
    'ConfigManager',
    'ErrorHandler',
    'CapsuleManager',
    'AgentRegistry',
    'setup_environment',
    'get_timestamp',
    'safe_json_dump',
]