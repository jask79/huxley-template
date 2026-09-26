#!/usr/bin/env python3
"""
System Health Rollup - Quick health/status snapshots for Huxley
Complements the existing advisor_rollup.py with real-time health checks
"""

import json
import datetime
import pathlib
from collections import defaultdict, Counter
import subprocess

CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")
REGISTRY_DIR = CATALYST_ROOT / "registry"
CAPSULES_DIR = CATALYST_ROOT / "capsules"

def check_system_processes():
    """Check if critical Huxley processes are running"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = result.stdout
        
        # Look for Huxley-related processes
        builder_processes = []
        for line in processes.split('\n'):
            if any(keyword in line.lower() for keyword in ['claude', 'mcp', 'n8n', 'builder']):
                if 'grep' not in line and line.strip():
                    builder_processes.append(line.strip())
        
        return {
            'total_processes': len(builder_processes),
            'processes': builder_processes[:5],  # First 5 for brevity
            'status': 'healthy' if len(builder_processes) > 0 else 'warning'
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def check_capsule_health():
    """Check health of active capsules"""
    if not CAPSULES_DIR.exists():
        return {'status': 'error', 'error': 'Capsules directory not found'}
    
    capsule_health = {
        'total_capsules': 0,
        'active_capsules': 0,
        'recent_activity': 0,
        'errors': [],
        'status': 'healthy'
    }
    
    try:
        # Count all capsules
        all_capsules = [d for d in CAPSULES_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]
        capsule_health['total_capsules'] = len(all_capsules)
        
        # Check for recent activity (last 24 hours)
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
        
        for capsule_dir in all_capsules:
            # Check if capsule has been modified recently
            try:
                mtime = datetime.datetime.fromtimestamp(capsule_dir.stat().st_mtime)
                if mtime >= cutoff_time:
                    capsule_health['recent_activity'] += 1
                    capsule_health['active_capsules'] += 1
            except Exception as e:
                capsule_health['errors'].append(f"{capsule_dir.name}: {e}")
        
        # Set overall status
        if capsule_health['errors']:
            capsule_health['status'] = 'warning'
        elif capsule_health['total_capsules'] == 0:
            capsule_health['status'] = 'warning'
            
    except Exception as e:
        capsule_health['status'] = 'error'
        capsule_health['error'] = str(e)
    
    return capsule_health

def check_mcp_health():
    """Check MCP server health using Claude CLI"""
    try:
        result = subprocess.run(['claude', 'mcp', 'list'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return {'status': 'error', 'error': 'Claude MCP command failed'}
        
        output = result.stdout
        lines = output.strip().split('\n')
        
        mcp_health = {
            'total_servers': 0,
            'connected_servers': 0,
            'failed_servers': 0,
            'servers': {},
            'status': 'healthy'
        }
        
        for line in lines:
            if ':' in line and (' - ' in line):
                parts = line.split(' - ')
                if len(parts) == 2:
                    server_info = parts[0].strip()
                    status = parts[1].strip()
                    
                    server_name = server_info.split(':')[0]
                    mcp_health['servers'][server_name] = status
                    mcp_health['total_servers'] += 1
                    
                    if '✓' in status:
                        mcp_health['connected_servers'] += 1
                    else:
                        mcp_health['failed_servers'] += 1
        
        # Set overall status
        if mcp_health['failed_servers'] > 0:
            mcp_health['status'] = 'warning'
        elif mcp_health['total_servers'] == 0:
            mcp_health['status'] = 'warning'
            
        return mcp_health
        
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'error': 'MCP health check timed out'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def check_disk_space():
    """Check available disk space for Huxley directory"""
    try:
        result = subprocess.run(['df', '-h', str(CATALYST_ROOT)], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            return {'status': 'error', 'error': 'Disk space check failed'}
        
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2:
            data_line = lines[1].split()
            if len(data_line) >= 5:
                usage_percent = int(data_line[4].rstrip('%'))
                available = data_line[3]
                
                status = 'healthy'
                if usage_percent > 90:
                    status = 'critical'
                elif usage_percent > 80:
                    status = 'warning'
                
                return {
                    'usage_percent': usage_percent,
                    'available': available,
                    'status': status
                }
        
        return {'status': 'error', 'error': 'Could not parse disk usage'}
        
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def check_recent_events():
    """Check recent events from the registry"""
    events_file = REGISTRY_DIR / "events.jsonl"
    
    if not events_file.exists():
        return {'status': 'warning', 'error': 'No events log found'}
    
    try:
        # Read last 100 events
        with open(events_file, 'r') as f:
            lines = f.readlines()
        
        recent_events = []
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        
        for line in lines[-100:]:  # Last 100 lines
            try:
                event = json.loads(line.strip())
                event_time = datetime.datetime.fromisoformat(event['timestamp'])
                if event_time >= cutoff_time:
                    recent_events.append(event)
            except Exception:
                continue
        
        # Analyze recent events
        event_counts = Counter()
        error_events = []
        
        for event in recent_events:
            event_counts[event.get('event_type', 'unknown')] += 1
            if event.get('level') in ['ERROR', 'CRITICAL']:
                error_events.append(event)
        
        status = 'healthy'
        if error_events:
            status = 'warning' if len(error_events) < 5 else 'critical'
        elif not recent_events:
            status = 'quiet'  # No recent activity
        
        return {
            'total_events': len(recent_events),
            'event_types': dict(event_counts.most_common(5)),
            'errors': len(error_events),
            'recent_errors': error_events[:3],  # Last 3 errors
            'status': status
        }
        
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def generate_health_summary():
    """Generate overall system health summary"""
    print("🏥 Huxley Health Check")
    print("=" * 50)
    
    checks = {
        'System Processes': check_system_processes(),
        'Capsule Health': check_capsule_health(),
        'MCP Servers': check_mcp_health(),
        'Disk Space': check_disk_space(),
        'Recent Events': check_recent_events()
    }
    
    overall_status = 'healthy'
    critical_issues = []
    warnings = []
    
    for check_name, result in checks.items():
        status = result.get('status', 'unknown')
        
        # Status indicators
        if status == 'healthy':
            indicator = "✅"
        elif status == 'warning':
            indicator = "⚠️"
            warnings.append(check_name)
        elif status == 'critical':
            indicator = "🔴"
            critical_issues.append(check_name)
            overall_status = 'critical'
        elif status == 'quiet':
            indicator = "🔵"
        else:
            indicator = "❌"
            critical_issues.append(check_name)
            if overall_status != 'critical':
                overall_status = 'error'
        
        print(f"{indicator} {check_name}")
        
        # Show key metrics
        if check_name == 'Capsule Health':
            print(f"    Total: {result.get('total_capsules', 0)}, Active: {result.get('active_capsules', 0)}")
        elif check_name == 'MCP Servers':
            connected = result.get('connected_servers', 0)
            total = result.get('total_servers', 0)
            print(f"    Connected: {connected}/{total}")
        elif check_name == 'Disk Space':
            if 'usage_percent' in result:
                print(f"    Usage: {result['usage_percent']}%, Available: {result['available']}")
        elif check_name == 'Recent Events':
            events = result.get('total_events', 0)
            errors = result.get('errors', 0)
            print(f"    Events: {events} (last hour), Errors: {errors}")
    
    print(f"\n📊 Overall Status: {overall_status.upper()}")
    
    if critical_issues:
        print(f"🔴 Critical Issues: {', '.join(critical_issues)}")
    if warnings:
        print(f"⚠️  Warnings: {', '.join(warnings)}")
    
    # Store health check result
    health_result = {
        'timestamp': datetime.datetime.now().isoformat(),
        'overall_status': overall_status,
        'checks': checks,
        'critical_issues': critical_issues,
        'warnings': warnings
    }
    
    health_file = REGISTRY_DIR / "system_health.json"
    with open(health_file, 'w') as f:
        json.dump(health_result, f, indent=2)
    
    print(f"\n📝 Health report saved to: {health_file}")
    
    return overall_status == 'healthy'

def main():
    # Ensure registry directory exists
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate health summary
    is_healthy = generate_health_summary()
    
    # Exit with appropriate code
    exit(0 if is_healthy else 1)

if __name__ == "__main__":
    main()