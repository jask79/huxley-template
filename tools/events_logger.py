#!/usr/bin/env python3
"""
Standardized event logging for Huxley capsules
Implements the registry/events.jsonl logging standard
"""

import json
import datetime
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

def _resolve_catalyst_root() -> Path:
    """Derive Huxley root directory with sensible fallbacks."""
    env_root = os.environ.get("CATALYST_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser()
        if candidate.exists():
            return candidate.resolve()

    script_root = Path(__file__).resolve().parents[1]
    if (script_root / "CLAUDE.md").exists():
        return script_root

    cwd = Path.cwd()
    if (cwd / "CLAUDE.md").exists():
        return cwd.resolve()

    return script_root.resolve()

CATALYST_ROOT = _resolve_catalyst_root()

class EventLogger:
    """Standardized event logger for Huxley capsules"""
    
    def __init__(self, capsule_slug: Optional[str] = None):
        self.capsule_slug = capsule_slug or self._detect_capsule()
        self.registry_dir = CATALYST_ROOT / "registry"
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        
        # Main event log
        self.events_log = self.registry_dir / "events.jsonl"
        
        # Specialized logs
        self.planner_log = self.registry_dir / "planner-hooks.log"
        self.inbox_log = self.registry_dir / "inbox-sync.log"
        self.audit_log = self.registry_dir / "daily_audit.log"
    
    def _detect_capsule(self) -> str:
        """Detect capsule slug from current directory or environment"""
        current_dir = Path.cwd()
        
        # Check if we're in a capsule directory
        if "capsules" in current_dir.parts:
            capsule_idx = current_dir.parts.index("capsules")
            if capsule_idx + 1 < len(current_dir.parts):
                return current_dir.parts[capsule_idx + 1]
        
        # Check environment variable
        return os.getenv('CAPSULE_SLUG', 'unknown')
    
    def log_event(self, event_type: str, metadata: Dict[str, Any] = None, 
                  level: str = "INFO", message: str = None):
        """Log a standardized event"""
        
        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event_type,
            "slug": self.capsule_slug,
            "level": level,
            "metadata": metadata or {}
        }
        
        if message:
            event["message"] = message
        
        # Write to main events log
        with open(self.events_log, 'a') as f:
            f.write(json.dumps(event) + '\n')
        
        # Also write to appropriate specialized log in legacy format for compatibility
        self._write_legacy_log(event_type, level, message or event_type, metadata)
    
    def _write_legacy_log(self, event_type: str, level: str, message: str, metadata: Dict):
        """Write to legacy log format for backward compatibility"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {level} slug={self.capsule_slug} msg={message.replace(' ', '_')}"
        
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    log_line += f" {key}={value}"
        
        log_line += "\n"
        
        # Route to appropriate log file
        if event_type.startswith('planner_') or event_type in ['agent_selected', 'mcp_grants']:
            with open(self.planner_log, 'a') as f:
                f.write(log_line)
        elif event_type.startswith('inbox_') or event_type in ['import_started', 'import_completed']:
            with open(self.inbox_log, 'a') as f:
                f.write(log_line)
        elif event_type.startswith('audit_') or event_type in ['daily_health_check', 'system_status']:
            with open(self.audit_log, 'a') as f:
                f.write(log_line)
        else:
            # Default to planner log
            with open(self.planner_log, 'a') as f:
                f.write(log_line)

# Standard event types
class EventsReader:
    """Read and parse events from Huxley event logs"""
    
    def __init__(self):
        self.registry_dir = CATALYST_ROOT / "registry"
        self.events_log = self.registry_dir / "events.jsonl"
    
    def read_events(self, hours=24):
        """Read events from the last N hours"""
        events = []
        if not self.events_log.exists():
            return events
        
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        with open(self.events_log, 'r') as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    event_time = datetime.datetime.fromisoformat(event.get('timestamp', ''))
                    if event_time >= cutoff:
                        events.append(event)
                except (json.JSONDecodeError, ValueError):
                    continue
        
        return events
    
    def read_events_since(self, since_timestamp):
        """Read events since a specific timestamp"""
        events = []
        if not self.events_log.exists():
            return events
        
        if isinstance(since_timestamp, str):
            cutoff = datetime.datetime.fromisoformat(since_timestamp)
        else:
            cutoff = since_timestamp
        
        with open(self.events_log, 'r') as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    event_time = datetime.datetime.fromisoformat(event.get('timestamp', ''))
                    if event_time >= cutoff:
                        events.append(event)
                except (json.JSONDecodeError, ValueError):
                    continue
        
        return events

class EventTypes:
    """Standard event type constants"""
    
    # Capsule lifecycle
    CAPSULE_CREATED = "capsule_created"
    CAPSULE_IMPORTED = "capsule_imported"
    CAPSULE_ACTIVATED = "capsule_activated"
    CAPSULE_COMPLETED = "capsule_completed"
    CAPSULE_ARCHIVED = "capsule_archived"
    
    # Agent routing
    AGENT_SELECTED = "agent_selected"
    AGENT_SWITCHED = "agent_switched"
    AGENT_FAILED = "agent_failed"
    
    # MCP operations
    MCP_GRANTS = "mcp_grants"
    MCP_SERVER_CONNECTED = "mcp_server_connected"
    MCP_SERVER_FAILED = "mcp_server_failed"
    
    # Build and deployment
    BUILD_STARTED = "build_started"
    BUILD_COMPLETED = "build_completed"
    BUILD_FAILED = "build_failed"
    DEPLOY_STARTED = "deploy_started"
    DEPLOY_COMPLETED = "deploy_completed"
    DEPLOY_FAILED = "deploy_failed"
    
    # Quality gates
    DOD_CHECK_STARTED = "dod_check_started"
    DOD_CHECK_PASSED = "dod_check_passed"
    DOD_CHECK_FAILED = "dod_check_failed"
    SECURITY_SCAN = "security_scan"
    PERFORMANCE_TEST = "performance_test"
    
    # System health
    HEALTH_CHECK = "health_check"
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"

def log_capsule_event(event_type: str, metadata: Dict = None, level: str = "INFO", 
                     message: str = None, capsule_slug: str = None):
    """Convenience function for logging capsule events"""
    logger = EventLogger(capsule_slug)
    logger.log_event(event_type, metadata, level, message)

def log_event(event_type: str, metadata: Dict = None, level: str = "INFO", 
              message: str = None):
    """Global convenience function for logging events"""
    logger = EventLogger()
    logger.log_event(event_type, metadata, level, message)

def main():
    """CLI interface for event logging"""
    if len(sys.argv) < 2:
        print("Usage: events_logger.py <event_type> [message] [--level LEVEL] [--slug SLUG] [--key=value ...]")
        print("\nCommon event types:")
        for attr_name in dir(EventTypes):
            if not attr_name.startswith('_'):
                print(f"  {getattr(EventTypes, attr_name)}")
        return
    
    event_type = sys.argv[1]
    message = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    
    # Parse arguments
    level = "INFO"
    capsule_slug = None
    metadata = {}
    
    for arg in sys.argv[2:]:
        if arg.startswith('--level'):
            level = arg.split('=', 1)[1] if '=' in arg else "INFO"
        elif arg.startswith('--slug'):
            capsule_slug = arg.split('=', 1)[1] if '=' in arg else None
        elif '=' in arg and not arg.startswith('--'):
            key, value = arg.split('=', 1)
            # Try to convert to appropriate type
            if value.lower() in ['true', 'false']:
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit():
                value = float(value)
            metadata[key] = value
    
    # Log the event
    log_capsule_event(event_type, metadata, level, message, capsule_slug)
    print(f"✅ Logged {event_type} event for capsule {capsule_slug or 'detected'}")

if __name__ == "__main__":
    main()
