#!/usr/bin/env python3
"""
Huxley Advisor v1 - Read-only analysis and recommendations
Analyzes registry events and generates daily scorecards and playbook suggestions
"""

import os
import json
import datetime
import pathlib
from collections import defaultdict, Counter

CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")
REGISTRY_DIR = CATALYST_ROOT / "registry"
ADVISOR_DIR = CATALYST_ROOT / "ops" / "advisor"
SCORECARDS_DIR = ADVISOR_DIR / "scorecards"

def ensure_directories():
    """Create advisor directories if they don't exist"""
    ADVISOR_DIR.mkdir(parents=True, exist_ok=True)
    SCORECARDS_DIR.mkdir(parents=True, exist_ok=True)

def read_log_events(log_file, days_back=7):
    """Read and parse log events from the last N days"""
    if not log_file.exists():
        return []
    
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_back)
    events = []
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Parse log format: [TIMESTAMP] LEVEL slug=X msg=Y
                if line.startswith('[') and ']' in line:
                    timestamp_end = line.find(']')
                    timestamp_str = line[1:timestamp_end]
                    
                    try:
                        timestamp = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        if timestamp >= cutoff_date:
                            rest = line[timestamp_end+1:].strip()
                            level = rest.split()[0] if rest.split() else "INFO"
                            
                            event = {
                                'timestamp': timestamp,
                                'level': level,
                                'raw': line,
                                'slug': None,
                                'msg': None
                            }
                            
                            # Extract slug and msg
                            parts = rest.split(' ', 1)
                            if len(parts) > 1:
                                remaining = parts[1]
                                for part in remaining.split():
                                    if '=' in part:
                                        key, value = part.split('=', 1)
                                        if key == 'slug':
                                            event['slug'] = value
                                        elif key == 'msg':
                                            event['msg'] = value.replace('_', ' ')
                            
                            events.append(event)
                    except ValueError:
                        continue
                        
    except Exception as e:
        print(f"Error reading {log_file}: {e}")
    
    return events

def analyze_events(events):
    """Analyze events and extract insights"""
    analysis = {
        'total_events': len(events),
        'by_level': Counter(),
        'by_slug': Counter(),
        'error_patterns': Counter(),
        'success_patterns': Counter(),
        'mcp_grants': [],
        'agent_warnings': [],
        'recent_activity': []
    }
    
    for event in events:
        analysis['by_level'][event['level']] += 1
        if event['slug']:
            analysis['by_slug'][event['slug']] += 1
        
        # Categorize events
        msg = (event.get('msg') or '').lower()
        raw = (event.get('raw') or '').lower()
        
        if 'error' in event['level'].lower():
            analysis['error_patterns'][msg[:50]] += 1
        elif 'mcp servers granted' in raw:
            analysis['mcp_grants'].append(event)
        elif 'unmet_agent_tools' in raw:
            analysis['agent_warnings'].append(event)
        elif 'success' in msg or 'pass' in msg:
            analysis['success_patterns'][msg[:50]] += 1
    
    # Recent activity (last 24 hours)
    recent_cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
    analysis['recent_activity'] = [e for e in events if e['timestamp'] >= recent_cutoff]
    
    return analysis

def generate_scorecard(analysis, date_str):
    """Generate daily scorecard markdown"""
    
    total_errors = analysis['by_level'].get('ERROR', 0)
    total_warnings = analysis['by_level'].get('WARN', 0)
    total_events = analysis['total_events']
    
    # Calculate health score (0-100)
    if total_events == 0:
        health_score = 100
    else:
        error_penalty = min(total_errors * 10, 50)
        warning_penalty = min(total_warnings * 2, 30)  
        health_score = max(0, 100 - error_penalty - warning_penalty)
    
    # Determine status
    if health_score >= 90:
        status = "🟢 HEALTHY"
    elif health_score >= 70:
        status = "🟡 ATTENTION"  
    else:
        status = "🔴 ISSUES"
    
    scorecard = f"""# Huxley Daily Scorecard - {date_str}

## System Health: {status}
**Score: {health_score}/100**

## Activity Summary
- **Total Events**: {total_events}
- **Errors**: {total_errors}
- **Warnings**: {total_warnings}
- **Active Capsules**: {len(analysis['by_slug'])}

## Top Active Capsules
"""
    
    for slug, count in analysis['by_slug'].most_common(5):
        scorecard += f"- **{slug}**: {count} events\n"
    
    if analysis['error_patterns']:
        scorecard += "\n## Error Patterns\n"
        for error, count in analysis['error_patterns'].most_common(3):
            scorecard += f"- **{count}x**: {error}...\n"
    
    if analysis['mcp_grants']:
        scorecard += f"\n## MCP Activity\n- **MCP Grants**: {len(analysis['mcp_grants'])} capsules received MCP access\n"
    
    if analysis['agent_warnings']:
        scorecard += f"- **Agent Warnings**: {len(analysis['agent_warnings'])} MCP/agent mismatches detected\n"
    
    scorecard += f"\n## Recent Activity (24h)\n- **Events**: {len(analysis['recent_activity'])}\n"
    
    return scorecard

def generate_playbook_suggestions(analysis):
    """Generate actionable playbook suggestions"""
    
    suggestions = []
    
    # Error-based suggestions
    error_count = analysis['by_level'].get('ERROR', 0)
    if error_count > 5:
        suggestions.append({
            'priority': 'HIGH',
            'category': 'Stability',
            'issue': f'{error_count} errors detected in the last week',
            'action': 'Run system diagnostics and check error patterns',
            'command': './catalyst-doctor.sh'
        })
    
    # Warning-based suggestions  
    warning_count = analysis['by_level'].get('WARN', 0)
    if warning_count > 10:
        suggestions.append({
            'priority': 'MEDIUM',
            'category': 'Configuration',
            'issue': f'{warning_count} warnings suggest configuration issues',
            'action': 'Review MCP grants and agent configurations',
            'command': 'grep "unmet_agent_tools\\|excessive_mcp_grants" registry/planner-hooks.log'
        })
    
    # Activity-based suggestions
    if len(analysis['by_slug']) == 0:
        suggestions.append({
            'priority': 'LOW',
            'category': 'Usage',
            'issue': 'No capsule activity detected',
            'action': 'Consider creating a new project or checking import system',
            'command': './tools/test_builder.sh'
        })
    elif len(analysis['by_slug']) > 20:
        suggestions.append({
            'priority': 'LOW', 
            'category': 'Maintenance',
            'issue': f'{len(analysis["by_slug"])} active capsules may need cleanup',
            'action': 'Review and archive inactive capsules',
            'command': 'ls -la capsules/ | grep -E "$(date +%Y-%m)"'
        })
    
    # MCP-based suggestions
    if len(analysis['agent_warnings']) > 5:
        suggestions.append({
            'priority': 'MEDIUM',
            'category': 'Security',
            'issue': 'Multiple agent/MCP mismatches detected',
            'action': 'Review and optimize MCP grants for least privilege',
            'command': 'cat global/mcp/AGENT_MCP_MATRIX.md'
        })
    
    return suggestions

def format_playbook_suggestions(suggestions):
    """Format suggestions as markdown"""
    if not suggestions:
        return "# Huxley Playbook Suggestions\n\n✅ **All systems operating normally** - No immediate actions required.\n"
    
    playbook = "# Huxley Playbook Suggestions\n\n"
    
    # Group by priority
    high_priority = [s for s in suggestions if s['priority'] == 'HIGH']
    medium_priority = [s for s in suggestions if s['priority'] == 'MEDIUM'] 
    low_priority = [s for s in suggestions if s['priority'] == 'LOW']
    
    for priority, items in [('🔴 HIGH PRIORITY', high_priority), 
                           ('🟡 MEDIUM PRIORITY', medium_priority),
                           ('🟢 LOW PRIORITY', low_priority)]:
        if items:
            playbook += f"## {priority}\n\n"
            for i, suggestion in enumerate(items, 1):
                playbook += f"### {i}. {suggestion['category']}: {suggestion['issue']}\n"
                playbook += f"**Action**: {suggestion['action']}\n\n"
                playbook += f"```bash\n{suggestion['command']}\n```\n\n"
    
    return playbook

def main():
    ensure_directories()
    
    # Read events from all log files
    all_events = []
    for log_file in ['planner-hooks.log', 'inbox-sync.log', 'daily_audit.log']:
        log_path = REGISTRY_DIR / log_file
        events = read_log_events(log_path)
        all_events.extend(events)
    
    # Sort by timestamp
    all_events.sort(key=lambda x: x['timestamp'])
    
    # Analyze events
    analysis = analyze_events(all_events)
    
    # Generate date string
    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # Generate scorecard
    scorecard = generate_scorecard(analysis, date_str)
    scorecard_file = SCORECARDS_DIR / f"{date_str}.md"
    
    with open(scorecard_file, 'w') as f:
        f.write(scorecard)
    
    print(f"📊 Generated scorecard: {scorecard_file}")
    
    # Generate playbook suggestions
    suggestions = generate_playbook_suggestions(analysis)
    playbook = format_playbook_suggestions(suggestions)
    playbook_file = ADVISOR_DIR / "playbook_suggestions.md"
    
    with open(playbook_file, 'w') as f:
        f.write(playbook)
    
    print(f"📋 Updated playbook: {playbook_file}")
    
    # Show top 3 suggestions
    if suggestions:
        print(f"\n🎯 **Top 3 Actions:**")
        for i, suggestion in enumerate(suggestions[:3], 1):
            print(f"{i}. {suggestion['category']}: {suggestion['action']}")
    else:
        print(f"\n✅ **System Status**: All systems operating normally")

if __name__ == "__main__":
    main()