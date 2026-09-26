#!/usr/bin/env python3
"""
MCP Audit Logger - Tracks MCP server usage, permissions, and security events
Integrates with Huxley events.jsonl logging
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class MCPAuditLogger:
    """Audit logging for MCP server operations and security events"""
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.events_log = self.project_root / "global" / "events.log"
        self.audit_log = self.project_root / "global" / "mcp-audit.jsonl"
        
        # Ensure log directories exist
        self.events_log.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
    
    def log_event(self, event_type: str, data: Dict[str, Any], 
                  server_name: Optional[str] = None, agent_role: Optional[str] = None):
        """Log MCP audit event in structured format"""
        
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": f"mcp.{event_type}",
            "server": server_name,
            "agent_role": agent_role,
            "session_id": os.getenv("CLAUDE_SESSION_ID"),
            "user": os.getenv("USER"),
            "project_root": str(self.project_root),
            **data
        }
        
        # Write to MCP-specific audit log
        with open(self.audit_log, 'a') as f:
            f.write(json.dumps(event, separators=(',', ':')) + '\n')
            
        # Also write to Huxley events log for integration
        with open(self.events_log, 'a') as f:
            f.write(f"{event['timestamp']} MCP_AUDIT {event_type.upper()} "
                   f"server={server_name or 'unknown'} role={agent_role or 'unknown'} "
                   f"data={json.dumps(data, separators=(',', ':'))}\n")
    
    def log_server_access(self, server_name: str, agent_role: str, 
                         operation: str, success: bool, **kwargs):
        """Log MCP server access attempts"""
        self.log_event("server_access", {
            "operation": operation,
            "success": success,
            "duration_ms": kwargs.get("duration_ms"),
            "error": kwargs.get("error"),
            "resource": kwargs.get("resource"),
            "method": kwargs.get("method")
        }, server_name, agent_role)
    
    def log_permission_check(self, server_name: str, agent_role: str, 
                           requested_mode: str, granted: bool, reason: str):
        """Log permission validation results"""
        self.log_event("permission_check", {
            "requested_mode": requested_mode,
            "granted": granted,
            "reason": reason
        }, server_name, agent_role)
    
    def log_security_violation(self, server_name: str, agent_role: str, 
                             violation_type: str, details: Dict[str, Any]):
        """Log security policy violations"""
        self.log_event("security_violation", {
            "violation_type": violation_type,
            "severity": details.get("severity", "medium"),
            "details": details
        }, server_name, agent_role)
    
    def log_config_change(self, change_type: str, old_config: Dict[str, Any], 
                         new_config: Dict[str, Any], changed_by: str):
        """Log MCP configuration changes"""
        self.log_event("config_change", {
            "change_type": change_type,
            "old_config": old_config,
            "new_config": new_config,
            "changed_by": changed_by
        })
    
    def generate_usage_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate MCP usage report from audit logs"""
        if not self.audit_log.exists():
            return {"error": "No audit log found"}
            
        cutoff_time = time.time() - (hours * 3600)
        events = []
        
        try:
            with open(self.audit_log, 'r') as f:
                for line in f:
                    event = json.loads(line.strip())
                    event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                    if event_time.timestamp() >= cutoff_time:
                        events.append(event)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return {"error": f"Failed to parse audit log: {e}"}
        
        # Analyze events
        server_usage = {}
        role_usage = {}
        security_events = 0
        total_operations = 0
        failed_operations = 0
        
        for event in events:
            server = event.get('server', 'unknown')
            role = event.get('agent_role', 'unknown')
            event_type = event.get('event_type', '')
            
            if server not in server_usage:
                server_usage[server] = {'operations': 0, 'failures': 0, 'last_used': None}
            if role not in role_usage:
                role_usage[role] = {'operations': 0, 'servers': set()}
                
            if event_type == 'mcp.server_access':
                total_operations += 1
                server_usage[server]['operations'] += 1
                role_usage[role]['operations'] += 1
                role_usage[role]['servers'].add(server)
                server_usage[server]['last_used'] = event['timestamp']
                
                if not event.get('success', True):
                    failed_operations += 1
                    server_usage[server]['failures'] += 1
            elif event_type == 'mcp.security_violation':
                security_events += 1
        
        # Convert sets to lists for JSON serialization
        for role_data in role_usage.values():
            role_data['servers'] = list(role_data['servers'])
        
        return {
            "report_period_hours": hours,
            "total_events": len(events),
            "total_operations": total_operations,
            "failed_operations": failed_operations,
            "success_rate": round((total_operations - failed_operations) / max(total_operations, 1) * 100, 2),
            "security_events": security_events,
            "server_usage": server_usage,
            "role_usage": role_usage,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    
    def check_security_policies(self, server_name: str, agent_role: str, 
                              operation: str, resource: str = None) -> Dict[str, Any]:
        """Check operation against security policies"""
        
        # Load current configuration
        try:
            config_path = self.project_root / ".mcp.json"
            if not config_path.exists():
                return {"allowed": False, "reason": "No MCP configuration found"}
                
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            return {"allowed": False, "reason": f"Failed to load config: {e}"}
        
        roles_access = config.get("roles_access", {})
        role_config = roles_access.get(agent_role, {})
        
        # Check if role is allowed to access this server
        allowed_servers = role_config.get("allowedServers", [])
        overrides = role_config.get("overrides", {})
        default_mode = role_config.get("mode", "none")
        
        # Determine effective permission mode
        if server_name in overrides:
            effective_mode = overrides[server_name]
        elif server_name in allowed_servers:
            effective_mode = default_mode
        else:
            effective_mode = "none"
        
        # Check operation against mode
        allowed = False
        reason = ""
        
        if effective_mode == "none":
            reason = f"Role '{agent_role}' has no access to server '{server_name}'"
        elif effective_mode == "read" and operation in ["read", "list", "get", "search"]:
            allowed = True
            reason = "Read operation allowed"
        elif effective_mode == "write":
            allowed = True 
            reason = "Write operation allowed"
        else:
            reason = f"Operation '{operation}' not allowed in mode '{effective_mode}'"
        
        return {
            "allowed": allowed,
            "reason": reason,
            "effective_mode": effective_mode,
            "role": agent_role,
            "server": server_name,
            "operation": operation
        }


class MCPCapsuleOverrides:
    """Manage capsule-level MCP overrides and permissions"""
    
    def __init__(self, capsule_path: Path):
        self.capsule_path = capsule_path
        self.overrides_file = capsule_path / ".claude" / "mcp-overrides.json"
    
    def load_overrides(self) -> Dict[str, Any]:
        """Load capsule-specific MCP overrides"""
        if not self.overrides_file.exists():
            return {}
            
        try:
            with open(self.overrides_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def set_server_override(self, server_name: str, config: Dict[str, Any]):
        """Set capsule-specific server override"""
        overrides = self.load_overrides()
        
        if "servers" not in overrides:
            overrides["servers"] = {}
            
        overrides["servers"][server_name] = config
        overrides["last_modified"] = datetime.utcnow().isoformat() + "Z"
        
        # Ensure directory exists
        self.overrides_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.overrides_file, 'w') as f:
            json.dump(overrides, f, indent=2)
    
    def set_role_permission(self, role_name: str, permissions: Dict[str, Any]):
        """Set capsule-specific role permissions"""
        overrides = self.load_overrides()
        
        if "roles" not in overrides:
            overrides["roles"] = {}
            
        overrides["roles"][role_name] = permissions
        overrides["last_modified"] = datetime.utcnow().isoformat() + "Z"
        
        # Ensure directory exists
        self.overrides_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.overrides_file, 'w') as f:
            json.dump(overrides, f, indent=2)


def main():
    """CLI interface for MCP audit logger"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Audit Logger")
    parser.add_argument("--report", action="store_true", help="Generate usage report")
    parser.add_argument("--hours", type=int, default=24, help="Report period in hours")
    parser.add_argument("--check-policy", help="Check policy for server:role:operation")
    parser.add_argument("--project-root", help="Project root directory")
    
    args = parser.parse_args()
    
    logger = MCPAuditLogger(args.project_root)
    
    if args.report:
        report = logger.generate_usage_report(args.hours)
        print(json.dumps(report, indent=2))
    elif args.check_policy:
        try:
            server, role, operation = args.check_policy.split(":")
            result = logger.check_security_policies(server, role, operation)
            print(json.dumps(result, indent=2))
        except ValueError:
            print("Error: --check-policy format should be server:role:operation")
            sys.exit(1)
    else:
        print("No action specified. Use --report or --check-policy")


if __name__ == "__main__":
    main()