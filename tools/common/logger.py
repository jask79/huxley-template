#!/usr/bin/env python3
"""
Huxley - Centralized Logging Framework
Provides consistent logging across all Huxley tools
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

class BuilderLogger:
    """Centralized logging for Huxley tools"""
    
    def __init__(self, name: str = "builder", level: str = None):
        self.name = name
        self.logger = logging.getLogger(name)
        
        # Set log level from env or default to INFO
        log_level = level or os.getenv("BUILDER_LOG_LEVEL", "INFO")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup console and file handlers"""
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        
        # File handler (optional)
        catalyst_root = os.getenv("CATALYST_ROOT", os.getcwd())
        log_dir = Path(catalyst_root) / "registry" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"{self.name}.log"
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def info(self, message: str, **kwargs):
        """Log info level message"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error level message"""
        self.logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug level message"""
        self.logger.debug(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical level message"""
        self.logger.critical(message, **kwargs)

# Global logger instance
def get_logger(name: str = "builder") -> BuilderLogger:
    """Get a logger instance for a tool"""
    return BuilderLogger(name)

# Convenience function for quick setup
def setup_logging(tool_name: str = "builder", level: str = "INFO") -> BuilderLogger:
    """Setup logging for a Huxley tool"""
    return BuilderLogger(tool_name, level)