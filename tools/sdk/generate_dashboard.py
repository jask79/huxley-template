#!/usr/bin/env python3
"""
SDK Monitoring Dashboard Generator

Generates HTML monitoring dashboard for SDK workflows.
Reads data from sdk_memory_bridge and creates interactive visualization.

Features:
- Workflow status overview
- Success rate charts
- Recent observations timeline
- Metrics visualization
- Auto-refresh capability

Usage:
    # Generate dashboard
    ./generate_dashboard.py

    # Generate with custom output path
    ./generate_dashboard.py --output /path/to/dashboard.html

    # Generate with auto-refresh
    ./generate_dashboard.py --refresh 30
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import argparse

# Add SDK tools to path
SDK_DIR = Path(__file__).parent
sys.path.insert(0, str(SDK_DIR))

from view_sdk_events import SDKEventsViewer


class DashboardGenerator:
    """
    Generates HTML monitoring dashboard for SDK workflows.
    """

    def __init__(self):
        """Initialize dashboard generator"""
        self.viewer = SDKEventsViewer()

    def generate_html(self, refresh_seconds: int = 0) -> str:
        """
        Generate HTML dashboard.

        Args:
            refresh_seconds: Auto-refresh interval (0 = disabled)

        Returns:
            HTML string
        """
        # Get data
        summary = self.viewer.get_summary()
        workflows = self.viewer.list_workflows()

        # Build workflow details
        workflow_details = []
        for wf in workflows:
            metrics = self.viewer.view_workflow_metrics(wf)
            history = self.viewer.view_workflow_history(wf, days=7, limit=10)
            workflow_details.append({
                "name": wf,
                "metrics": metrics,
                "recent_history": history
            })

        # Generate HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SDK Monitoring Dashboard</title>
    {"<meta http-equiv='refresh' content='" + str(refresh_seconds) + "'>" if refresh_seconds > 0 else ""}
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        h1 {{
            font-size: 2rem;
            margin-bottom: 10px;
            color: #fff;
        }}

        .timestamp {{
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 30px;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .summary-card {{
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
        }}

        .summary-card h3 {{
            font-size: 0.85rem;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 10px;
            letter-spacing: 0.5px;
        }}

        .summary-card .value {{
            font-size: 2.5rem;
            font-weight: 600;
            color: #fff;
        }}

        .summary-card .value.success {{
            color: #4ade80;
        }}

        .summary-card .value.warning {{
            color: #fbbf24;
        }}

        .workflows {{
            display: grid;
            gap: 30px;
        }}

        .workflow-card {{
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 25px;
        }}

        .workflow-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }}

        .workflow-name {{
            font-size: 1.3rem;
            font-weight: 600;
            color: #fff;
        }}

        .workflow-status {{
            display: flex;
            gap: 20px;
        }}

        .status-badge {{
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 500;
        }}

        .status-badge.success {{
            background: #166534;
            color: #4ade80;
        }}

        .status-badge.warning {{
            background: #713f12;
            color: #fbbf24;
        }}

        .status-badge.error {{
            background: #7f1d1d;
            color: #f87171;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}

        .metric {{
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 6px;
            padding: 15px;
        }}

        .metric-label {{
            font-size: 0.8rem;
            color: #888;
            margin-bottom: 5px;
        }}

        .metric-value {{
            font-size: 1.5rem;
            font-weight: 600;
            color: #fff;
        }}

        .observations {{
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 6px;
            padding: 15px;
        }}

        .observations h4 {{
            font-size: 0.9rem;
            color: #888;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .observation {{
            padding: 10px;
            border-left: 3px solid #333;
            margin-bottom: 10px;
            background: #1a1a1a;
        }}

        .observation-time {{
            font-size: 0.75rem;
            color: #666;
            margin-bottom: 5px;
        }}

        .observation-text {{
            font-size: 0.9rem;
            color: #e0e0e0;
        }}

        .observation.success {{
            border-left-color: #4ade80;
        }}

        .observation.error {{
            border-left-color: #f87171;
        }}

        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #333;
            text-align: center;
            color: #666;
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>SDK Monitoring Dashboard</h1>
        <div class="timestamp">Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

        <div class="summary-grid">
            <div class="summary-card">
                <h3>Total Workflows</h3>
                <div class="value">{summary['total_workflows']}</div>
            </div>
            <div class="summary-card">
                <h3>Total Runs</h3>
                <div class="value">{summary['total_runs']}</div>
            </div>
            <div class="summary-card">
                <h3>Success Rate</h3>
                <div class="value {'success' if summary['overall_success_rate'] >= 80 else 'warning'}">{summary['overall_success_rate']}%</div>
            </div>
        </div>

        <div class="workflows">
"""

        # Add workflow cards
        for wf in workflow_details:
            metrics = wf["metrics"]
            success_rate = metrics.get("success_rate", 0)

            # Determine status badge
            if success_rate >= 80:
                status_class = "success"
                status_text = "Healthy"
            elif success_rate >= 50:
                status_class = "warning"
                status_text = "Degraded"
            else:
                status_class = "error"
                status_text = "Critical"

            html += f"""
            <div class="workflow-card">
                <div class="workflow-header">
                    <div class="workflow-name">{wf['name']}</div>
                    <div class="workflow-status">
                        <span class="status-badge {status_class}">{status_text}</span>
                    </div>
                </div>

                <div class="metrics-grid">
                    <div class="metric">
                        <div class="metric-label">Run Count</div>
                        <div class="metric-value">{metrics.get('run_count', 0)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Success Rate</div>
                        <div class="metric-value">{metrics.get('success_rate', 0)}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Avg Duration</div>
                        <div class="metric-value">{metrics.get('avg_duration_ms', 0):.0f}ms</div>
                    </div>
                </div>

                <div class="observations">
                    <h4>Recent Observations</h4>
"""

            # Add observations
            for obs in wf["recent_history"][-5:]:
                obs_time = datetime.fromisoformat(obs["timestamp"]).strftime("%H:%M:%S")
                obs_text = obs.get("observation", "")
                obs_class = "success" if "success" in obs_text.lower() else "error" if "fail" in obs_text.lower() else ""

                html += f"""
                    <div class="observation {obs_class}">
                        <div class="observation-time">{obs_time}</div>
                        <div class="observation-text">{obs_text}</div>
                    </div>
"""

            html += """
                </div>
            </div>
"""

        html += f"""
        </div>

        <div class="footer">
            SDK Monitoring Dashboard • Huxley
            {" • Auto-refresh: " + str(refresh_seconds) + "s" if refresh_seconds > 0 else ""}
        </div>
    </div>
</body>
</html>
"""

        return html

    def save_dashboard(self, output_path: Path, refresh_seconds: int = 0):
        """
        Generate and save dashboard to file.

        Args:
            output_path: Output file path
            refresh_seconds: Auto-refresh interval (0 = disabled)
        """
        html = self.generate_html(refresh_seconds=refresh_seconds)

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write HTML
        with open(output_path, 'w') as f:
            f.write(html)

        print(f"✓ Dashboard generated: {output_path}")
        if refresh_seconds > 0:
            print(f"  Auto-refresh: every {refresh_seconds} seconds")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="SDK Monitoring Dashboard Generator")
    parser.add_argument("--output", default="{{CATALYST_ROOT}}/registry/dashboard/sdk_monitor.html",
                       help="Output file path")
    parser.add_argument("--refresh", type=int, default=0,
                       help="Auto-refresh interval in seconds (0 = disabled)")

    args = parser.parse_args()

    generator = DashboardGenerator()
    generator.save_dashboard(Path(args.output), refresh_seconds=args.refresh)

    return 0


if __name__ == "__main__":
    sys.exit(main())
