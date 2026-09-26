#!/usr/bin/env python3
"""
Advanced Performance Analytics for Huxley
Real-time monitoring, trend analysis, and bottleneck identification
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from collections import defaultdict, deque
import sqlite3
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_PLOTTING = True
except ImportError:
    HAS_PLOTTING = False
from dataclasses import dataclass, asdict
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Performance metric data point"""
    timestamp: datetime
    capsule_name: str
    metric_type: str
    value: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'capsule_name': self.capsule_name,
            'metric_type': self.metric_type,
            'value': self.value,
            'metadata': self.metadata
        }

@dataclass
class TrendAnalysis:
    """Trend analysis result"""
    metric_type: str
    trend_direction: str  # 'improving', 'degrading', 'stable'
    trend_strength: float  # 0-1
    current_value: float
    average_value: float
    change_rate: float  # % change per day
    prediction_7d: float
    confidence: float

@dataclass
class BottleneckAlert:
    """Bottleneck identification alert"""
    severity: str  # 'critical', 'warning', 'info'
    component: str
    issue: str
    impact: str
    recommendations: List[str]
    metrics: Dict[str, float]

class PerformanceAnalytics:
    """Advanced performance analytics engine"""
    
    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.analytics_path = self.catalyst_root / "registry/analytics"
        self.analytics_path.mkdir(parents=True, exist_ok=True)
        
        # Database for time series data
        self.db_path = self.analytics_path / "performance_metrics.db"
        self._init_database()
        
        # In-memory caches for real-time analysis
        self.metric_buffers = defaultdict(lambda: deque(maxlen=1000))
        self.trend_cache = {}
        self.bottleneck_cache = {}
        
        # Analytics configuration
        self.config = {
            'trend_analysis_window': 7,  # days
            'bottleneck_threshold': 0.8,  # 80th percentile
            'alert_cooldown': 3600,  # 1 hour
            'metrics_retention': 90,  # days
        }
        
        logger.info("Performance Analytics initialized")
    
    def _init_database(self):
        """Initialize SQLite database for metrics storage"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    capsule_name TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON metrics(timestamp)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_metrics_capsule 
                ON metrics(capsule_name, metric_type)
            ''')
            
            # Performance events table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS performance_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    component TEXT NOT NULL,
                    description TEXT NOT NULL,
                    metrics TEXT,
                    resolved_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    def record_metric(self, capsule_name: str, metric_type: str, 
                     value: float, metadata: Optional[Dict[str, Any]] = None):
        """Record a performance metric"""
        timestamp = datetime.now()
        metric = PerformanceMetric(
            timestamp=timestamp,
            capsule_name=capsule_name,
            metric_type=metric_type,
            value=value,
            metadata=metadata or {}
        )
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO metrics (timestamp, capsule_name, metric_type, value, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                timestamp.isoformat(),
                capsule_name,
                metric_type,
                value,
                json.dumps(metadata) if metadata else '{}'
            ))
        
        # Add to real-time buffer
        buffer_key = f"{capsule_name}:{metric_type}"
        self.metric_buffers[buffer_key].append(metric)
        
        # Trigger real-time analysis
        self._analyze_real_time_metric(metric)
    
    def _analyze_real_time_metric(self, metric: PerformanceMetric):
        """Analyze metric in real-time for immediate alerts"""
        buffer_key = f"{metric.capsule_name}:{metric.metric_type}"
        buffer = self.metric_buffers[buffer_key]
        
        if len(buffer) < 5:  # Need minimum data points
            return
        
        recent_values = [m.value for m in list(buffer)[-10:]]
        
        # Check for sudden spikes or drops
        if len(recent_values) >= 3:
            current = recent_values[-1]
            previous_avg = np.mean(recent_values[-3:-1])
            
            if previous_avg > 0:
                change_pct = (current - previous_avg) / previous_avg
                
                # Alert thresholds
                if abs(change_pct) > 0.5:  # 50% change
                    severity = 'critical' if abs(change_pct) > 1.0 else 'warning'
                    direction = 'spike' if change_pct > 0 else 'drop'
                    
                    self._create_performance_alert(
                        severity=severity,
                        component=metric.capsule_name,
                        event_type=f"{metric.metric_type}_{direction}",
                        description=f"{metric.metric_type} {direction} detected: {change_pct:.1%} change",
                        metrics={'current': current, 'previous_avg': previous_avg, 'change_pct': change_pct}
                    )
    
    def _create_performance_alert(self, severity: str, component: str, 
                                 event_type: str, description: str, 
                                 metrics: Dict[str, float]):
        """Create a performance alert"""
        timestamp = datetime.now()
        
        # Check cooldown to avoid spam
        cache_key = f"{component}:{event_type}"
        if cache_key in self.bottleneck_cache:
            last_alert = self.bottleneck_cache[cache_key]
            if (timestamp - last_alert).total_seconds() < self.config['alert_cooldown']:
                return
        
        self.bottleneck_cache[cache_key] = timestamp
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO performance_events 
                (timestamp, event_type, severity, component, description, metrics)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                timestamp.isoformat(),
                event_type,
                severity,
                component,
                description,
                json.dumps(metrics)
            ))
        
        logger.warning(f"Performance alert [{severity}] {component}: {description}")
    
    def get_trend_analysis(self, capsule_name: Optional[str] = None, 
                          metric_type: Optional[str] = None,
                          days: int = 7) -> List[TrendAnalysis]:
        """Analyze performance trends"""
        start_time = datetime.now() - timedelta(days=days)
        
        # Build query
        query = '''
            SELECT capsule_name, metric_type, timestamp, value
            FROM metrics 
            WHERE timestamp >= ?
        '''
        params = [start_time.isoformat()]
        
        if capsule_name:
            query += ' AND capsule_name = ?'
            params.append(capsule_name)
        
        if metric_type:
            query += ' AND metric_type = ?'
            params.append(metric_type)
        
        query += ' ORDER BY timestamp'
        
        # Get data
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            return []
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Analyze trends by capsule and metric type
        trends = []
        for (capsule, metric), group in df.groupby(['capsule_name', 'metric_type']):
            if len(group) < 3:  # Need minimum data points
                continue
            
            trend = self._analyze_trend(group, capsule, metric)
            if trend:
                trends.append(trend)
        
        return trends
    
    def _analyze_trend(self, data: pd.DataFrame, capsule_name: str, 
                      metric_type: str) -> Optional[TrendAnalysis]:
        """Analyze trend for a specific metric"""
        if len(data) < 3:
            return None
        
        # Sort by timestamp
        data = data.sort_values('timestamp')
        
        # Calculate basic statistics
        current_value = data['value'].iloc[-1]
        average_value = data['value'].mean()
        
        # Linear regression for trend
        x = np.arange(len(data))
        y = data['value'].values
        
        if np.var(y) == 0:  # No variation
            return TrendAnalysis(
                metric_type=metric_type,
                trend_direction='stable',
                trend_strength=0.0,
                current_value=current_value,
                average_value=average_value,
                change_rate=0.0,
                prediction_7d=current_value,
                confidence=1.0
            )
        
        # Fit linear regression
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs
        
        # Calculate R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Determine trend direction and strength
        trend_strength = abs(slope) / (np.std(y) + 1e-8)  # Normalized slope
        
        if abs(slope) < np.std(y) * 0.1:  # Small change relative to variance
            trend_direction = 'stable'
        elif slope > 0:
            trend_direction = 'improving' if metric_type in ['success_rate', 'performance_score'] else 'degrading'
        else:
            trend_direction = 'degrading' if metric_type in ['success_rate', 'performance_score'] else 'improving'
        
        # Calculate change rate (per day)
        time_span = (data['timestamp'].iloc[-1] - data['timestamp'].iloc[0]).total_seconds() / 86400
        if time_span > 0:
            change_rate = (slope * len(data) / time_span) / average_value * 100 if average_value != 0 else 0
        else:
            change_rate = 0
        
        # Predict 7 days ahead
        future_x = len(data) + 7 * (len(data) / max(1, time_span))
        prediction_7d = slope * future_x + intercept
        
        return TrendAnalysis(
            metric_type=metric_type,
            trend_direction=trend_direction,
            trend_strength=min(1.0, trend_strength),
            current_value=current_value,
            average_value=average_value,
            change_rate=change_rate,
            prediction_7d=prediction_7d,
            confidence=r_squared
        )
    
    def identify_bottlenecks(self, lookback_hours: int = 24) -> List[BottleneckAlert]:
        """Identify system bottlenecks"""
        start_time = datetime.now() - timedelta(hours=lookback_hours)
        
        # Get recent metrics
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query('''
                SELECT capsule_name, metric_type, value, timestamp
                FROM metrics 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', conn, params=[start_time.isoformat()])
        
        if df.empty:
            return []
        
        bottlenecks = []
        
        # Analyze by metric type
        for metric_type, group in df.groupby('metric_type'):
            bottleneck = self._analyze_metric_bottlenecks(metric_type, group)
            if bottleneck:
                bottlenecks.append(bottleneck)
        
        # Analyze by capsule
        for capsule_name, group in df.groupby('capsule_name'):
            bottleneck = self._analyze_capsule_bottlenecks(capsule_name, group)
            if bottleneck:
                bottlenecks.append(bottleneck)
        
        return bottlenecks
    
    def _analyze_metric_bottlenecks(self, metric_type: str, 
                                   data: pd.DataFrame) -> Optional[BottleneckAlert]:
        """Analyze bottlenecks for a specific metric type"""
        if len(data) < 5:
            return None
        
        values = data['value']
        
        # Calculate percentiles
        p95 = np.percentile(values, 95)
        p80 = np.percentile(values, 80)
        p50 = np.percentile(values, 50)
        
        # Identify outliers (values above 95th percentile)
        outliers = data[data['value'] > p95]
        
        if len(outliers) / len(data) > 0.2:  # More than 20% outliers
            severity = 'critical'
            issue = f"High variability in {metric_type}"
            impact = f"{len(outliers)} capsules showing extreme {metric_type} values"
            
            recommendations = [
                f"Investigate capsules with {metric_type} > {p95:.2f}",
                "Check for resource constraints or configuration issues",
                "Consider load balancing or scaling"
            ]
            
            return BottleneckAlert(
                severity=severity,
                component=f"system_{metric_type}",
                issue=issue,
                impact=impact,
                recommendations=recommendations,
                metrics={
                    'p95': p95,
                    'p80': p80,
                    'p50': p50,
                    'outlier_count': len(outliers),
                    'outlier_percentage': len(outliers) / len(data)
                }
            )
        
        return None
    
    def _analyze_capsule_bottlenecks(self, capsule_name: str, 
                                    data: pd.DataFrame) -> Optional[BottleneckAlert]:
        """Analyze bottlenecks for a specific capsule"""
        if len(data) < 3:
            return None
        
        # Look for concerning patterns
        metric_issues = []
        
        for metric_type, group in data.groupby('metric_type'):
            values = group['value']
            
            if metric_type in ['error_rate', 'failure_rate']:
                if values.mean() > 0.05:  # 5% error rate
                    metric_issues.append(f"High {metric_type}: {values.mean():.1%}")
            
            elif metric_type in ['response_time', 'completion_time']:
                if values.mean() > values.quantile(0.8):  # Above 80th percentile
                    metric_issues.append(f"Slow {metric_type}: {values.mean():.1f}")
            
            elif metric_type in ['cpu_usage', 'memory_usage']:
                if values.mean() > 80:  # 80% usage
                    metric_issues.append(f"High {metric_type}: {values.mean():.1f}%")
        
        if metric_issues:
            severity = 'critical' if len(metric_issues) > 2 else 'warning'
            
            recommendations = [
                "Review capsule resource allocation",
                "Check for inefficient algorithms or queries",
                "Consider optimization or scaling"
            ]
            
            if 'error_rate' in str(metric_issues):
                recommendations.append("Investigate error logs and failure patterns")
            
            return BottleneckAlert(
                severity=severity,
                component=capsule_name,
                issue=f"Multiple performance issues detected",
                impact=f"Issues: {'; '.join(metric_issues)}",
                recommendations=recommendations,
                metrics={
                    'issue_count': len(metric_issues),
                    'affected_metrics': [issue.split(':')[0] for issue in metric_issues]
                }
            )
        
        return None
    
    def get_performance_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        start_time = datetime.now() - timedelta(days=days)
        
        # Get metrics data
        with sqlite3.connect(self.db_path) as conn:
            metrics_df = pd.read_sql_query('''
                SELECT capsule_name, metric_type, value, timestamp
                FROM metrics 
                WHERE timestamp >= ?
            ''', conn, params=[start_time.isoformat()])
            
            events_df = pd.read_sql_query('''
                SELECT event_type, severity, component, timestamp
                FROM performance_events 
                WHERE timestamp >= ?
            ''', conn, params=[start_time.isoformat()])
        
        summary = {
            'period': f"{days} days",
            'generated_at': datetime.now().isoformat(),
            'metrics_collected': len(metrics_df),
            'events_recorded': len(events_df),
            'capsules_monitored': metrics_df['capsule_name'].nunique() if not metrics_df.empty else 0,
            'metric_types_tracked': metrics_df['metric_type'].nunique() if not metrics_df.empty else 0
        }
        
        # Performance statistics
        if not metrics_df.empty:
            summary['performance_stats'] = {}
            
            for metric_type, group in metrics_df.groupby('metric_type'):
                summary['performance_stats'][metric_type] = {
                    'mean': group['value'].mean(),
                    'median': group['value'].median(),
                    'std': group['value'].std(),
                    'min': group['value'].min(),
                    'max': group['value'].max(),
                    'count': len(group)
                }
        
        # Event summary
        if not events_df.empty:
            summary['events_summary'] = {
                'by_severity': events_df['severity'].value_counts().to_dict(),
                'by_type': events_df['event_type'].value_counts().to_dict(),
                'by_component': events_df['component'].value_counts().to_dict()
            }
        
        # Top performing capsules
        if not metrics_df.empty:
            capsule_performance = metrics_df.groupby('capsule_name')['value'].agg(['mean', 'count'])
            top_performers = capsule_performance.nlargest(5, 'mean')
            summary['top_performers'] = top_performers.to_dict('index')
        
        # Trend analysis
        trends = self.get_trend_analysis(days=days)
        summary['trends'] = {
            'improving': len([t for t in trends if t.trend_direction == 'improving']),
            'degrading': len([t for t in trends if t.trend_direction == 'degrading']),
            'stable': len([t for t in trends if t.trend_direction == 'stable'])
        }
        
        # Current bottlenecks
        bottlenecks = self.identify_bottlenecks(lookback_hours=24)
        summary['current_bottlenecks'] = {
            'critical': len([b for b in bottlenecks if b.severity == 'critical']),
            'warning': len([b for b in bottlenecks if b.severity == 'warning']),
            'total': len(bottlenecks)
        }
        
        return summary
    
    def generate_performance_report(self, output_path: Optional[Path] = None) -> str:
        """Generate detailed performance report"""
        if output_path is None:
            output_path = self.analytics_path / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        summary = self.get_performance_summary()
        trends = self.get_trend_analysis(days=7)
        bottlenecks = self.identify_bottlenecks()
        
        report = f"""# Huxley Performance Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Monitoring Period**: {summary['period']}
- **Capsules Monitored**: {summary['capsules_monitored']}
- **Metrics Collected**: {summary['metrics_collected']:,}
- **Performance Events**: {summary['events_recorded']}

## Overall Health Score
"""
        
        # Calculate health score
        health_factors = []
        
        if summary.get('current_bottlenecks', {}).get('critical', 0) == 0:
            health_factors.append(25)  # No critical issues
        elif summary.get('current_bottlenecks', {}).get('critical', 0) < 3:
            health_factors.append(15)  # Few critical issues
        else:
            health_factors.append(0)   # Many critical issues
        
        improving_trends = summary.get('trends', {}).get('improving', 0)
        total_trends = sum(summary.get('trends', {}).values())
        if total_trends > 0:
            trend_score = (improving_trends / total_trends) * 25
            health_factors.append(trend_score)
        else:
            health_factors.append(15)  # Neutral score
        
        # Add other factors
        health_factors.extend([25, 25])  # Baseline scores
        
        health_score = sum(health_factors)
        health_status = "Excellent" if health_score >= 80 else "Good" if health_score >= 60 else "Fair" if health_score >= 40 else "Poor"
        
        report += f"**{health_score:.0f}/100** - {health_status}\n\n"
        
        # Performance trends
        report += "## Performance Trends\n"
        if trends:
            for trend in trends[:10]:  # Top 10 trends
                direction_emoji = "📈" if trend.trend_direction == "improving" else "📉" if trend.trend_direction == "degrading" else "➡️"
                report += f"- {direction_emoji} **{trend.metric_type}**: {trend.trend_direction} ({trend.change_rate:.1f}%/day, confidence: {trend.confidence:.2f})\n"
        else:
            report += "No significant trends detected.\n"
        
        report += "\n"
        
        # Current bottlenecks
        report += "## Current Bottlenecks\n"
        if bottlenecks:
            critical_bottlenecks = [b for b in bottlenecks if b.severity == 'critical']
            warning_bottlenecks = [b for b in bottlenecks if b.severity == 'warning']
            
            if critical_bottlenecks:
                report += "### 🚨 Critical Issues\n"
                for bottleneck in critical_bottlenecks:
                    report += f"- **{bottleneck.component}**: {bottleneck.issue}\n"
                    report += f"  - Impact: {bottleneck.impact}\n"
                    report += f"  - Recommendations: {'; '.join(bottleneck.recommendations[:2])}\n\n"
            
            if warning_bottlenecks:
                report += "### ⚠️ Warning Issues\n"
                for bottleneck in warning_bottlenecks:
                    report += f"- **{bottleneck.component}**: {bottleneck.issue}\n"
        else:
            report += "✅ No current bottlenecks detected.\n"
        
        report += "\n"
        
        # Performance statistics
        if 'performance_stats' in summary:
            report += "## Key Metrics\n"
            for metric_type, stats in summary['performance_stats'].items():
                report += f"### {metric_type.replace('_', ' ').title()}\n"
                report += f"- Mean: {stats['mean']:.2f}\n"
                report += f"- Median: {stats['median']:.2f}\n"
                report += f"- Range: {stats['min']:.2f} - {stats['max']:.2f}\n"
                report += f"- Samples: {stats['count']:,}\n\n"
        
        # Save report
        with open(output_path, 'w') as f:
            f.write(report)
        
        logger.info(f"Performance report generated: {output_path}")
        return str(output_path)
    
    def cleanup_old_data(self, days: int = 90):
        """Clean up old performance data"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            # Clean up old metrics
            cursor = conn.execute('''
                DELETE FROM metrics WHERE timestamp < ?
            ''', [cutoff_time.isoformat()])
            metrics_deleted = cursor.rowcount
            
            # Clean up old events
            cursor = conn.execute('''
                DELETE FROM performance_events WHERE timestamp < ?
            ''', [cutoff_time.isoformat()])
            events_deleted = cursor.rowcount
            
            # Vacuum database to reclaim space
            conn.execute('VACUUM')
        
        logger.info(f"Cleaned up {metrics_deleted} old metrics and {events_deleted} old events")


def main():
    """CLI interface for performance analytics"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Analytics")
    parser.add_argument("command", choices=["record", "trends", "bottlenecks", "summary", "report", "cleanup"],
                       help="Command to execute")
    parser.add_argument("--capsule", help="Capsule name")
    parser.add_argument("--metric", help="Metric type")
    parser.add_argument("--value", type=float, help="Metric value")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    
    args = parser.parse_args()
    
    analytics = PerformanceAnalytics()
    
    if args.command == "record":
        if not all([args.capsule, args.metric, args.value]):
            print("Error: --capsule, --metric, and --value required for record")
            return
        
        analytics.record_metric(args.capsule, args.metric, args.value)
        print(f"Recorded {args.metric}={args.value} for {args.capsule}")
    
    elif args.command == "trends":
        trends = analytics.get_trend_analysis(args.capsule, args.metric, args.days)
        
        if trends:
            print("PERFORMANCE TRENDS:")
            for trend in trends:
                print(f"- {trend.metric_type}: {trend.trend_direction} "
                      f"({trend.change_rate:.1f}%/day, conf: {trend.confidence:.2f})")
        else:
            print("No trends detected")
    
    elif args.command == "bottlenecks":
        bottlenecks = analytics.identify_bottlenecks(args.days * 24)
        
        if bottlenecks:
            print("CURRENT BOTTLENECKS:")
            for bottleneck in bottlenecks:
                print(f"[{bottleneck.severity.upper()}] {bottleneck.component}: {bottleneck.issue}")
                print(f"  Impact: {bottleneck.impact}")
                print(f"  Recommendations: {bottleneck.recommendations[0] if bottleneck.recommendations else 'None'}")
        else:
            print("No bottlenecks detected")
    
    elif args.command == "summary":
        summary = analytics.get_performance_summary(args.days)
        print(json.dumps(summary, indent=2, default=str))
    
    elif args.command == "report":
        report_path = analytics.generate_performance_report()
        print(f"Performance report generated: {report_path}")
    
    elif args.command == "cleanup":
        analytics.cleanup_old_data(args.days)
        print(f"Cleaned up data older than {args.days} days")


if __name__ == "__main__":
    main()