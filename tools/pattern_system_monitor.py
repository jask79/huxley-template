#!/usr/bin/env python3
"""
Pattern System Monitor for Huxley  
Real-time performance monitoring and health tracking for pattern recognition system
"""

import json
import logging
import sqlite3
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """System health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class PerformanceMetric:
    """Performance metric data point"""
    name: str
    value: float
    unit: str
    timestamp: str
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class SystemAlert:
    """System alert notification"""
    alert_id: str
    level: AlertLevel
    title: str
    description: str
    component: str
    timestamp: str
    resolved: bool
    resolution_time: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['level'] = self.level.value
        return result

@dataclass
class ComponentHealth:
    """Health status of system component"""
    component_name: str
    status: HealthStatus
    last_check: str
    response_time: float
    error_rate: float
    uptime_percentage: float
    metrics: Dict[str, float]
    issues: List[str]

class PatternSystemMonitor:
    """Real-time monitoring and health tracking for pattern system"""
    
    def __init__(self, monitoring_interval: int = 60):
        self.db_path = Path(__file__).parent.parent / "registry" / "pattern_monitor.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        self.monitoring_interval = monitoring_interval
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Performance tracking
        self.metric_history = defaultdict(lambda: deque(maxlen=1000))
        self.alert_handlers: List[Callable[[SystemAlert], None]] = []
        
        # Component tracking
        self.components = {
            "pattern_recognition_engine": None,
            "pattern_application_engine": None,
            "execution_tracker": None,
            "context_intelligence": None,
            "agent_effectiveness": None
        }
        
        self._init_database()
        logger.info("Pattern System Monitor initialized")
    
    def _init_database(self):
        """Initialize SQLite database for monitoring data"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Performance metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tags TEXT
                )
            """)
            
            # System alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_alerts (
                    alert_id TEXT PRIMARY KEY,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    component TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    resolved BOOLEAN NOT NULL,
                    resolution_time TEXT
                )
            """)
            
            # Component health table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS component_health (
                    component_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_check TEXT NOT NULL,
                    response_time REAL NOT NULL,
                    error_rate REAL NOT NULL,
                    uptime_percentage REAL NOT NULL,
                    metrics TEXT,
                    issues TEXT
                )
            """)
            
            conn.commit()
    
    def start_monitoring(self):
        """Start continuous monitoring"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Pattern system monitoring started")
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Pattern system monitoring stopped")
    
    def record_performance_metric(self, name: str, value: float, unit: str = "seconds",
                                 tags: Dict[str, str] = None):
        """Record a performance metric"""
        try:
            timestamp = datetime.utcnow().isoformat()
            metric = PerformanceMetric(
                name=name,
                value=value,
                unit=unit,
                timestamp=timestamp,
                tags=tags or {}
            )
            
            # Store in memory for real-time analysis
            self.metric_history[name].append((timestamp, value))
            
            # Store in database
            self._store_metric(metric)
            
            # Check for anomalies
            self._check_metric_anomalies(name, value)
            
        except Exception as e:
            logger.error(f"Failed to record metric: {e}")
    
    def create_alert(self, level: AlertLevel, title: str, description: str, 
                    component: str) -> str:
        """Create a system alert"""
        try:
            alert_id = f"alert_{datetime.utcnow().timestamp()}"
            alert = SystemAlert(
                alert_id=alert_id,
                level=level,
                title=title,
                description=description,
                component=component,
                timestamp=datetime.utcnow().isoformat(),
                resolved=False,
                resolution_time=None
            )
            
            self._store_alert(alert)
            
            # Notify alert handlers
            for handler in self.alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Alert handler failed: {e}")
            
            logger.warning(f"Alert created: {title}")
            return alert_id
            
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            return ""
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve a system alert"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE system_alerts 
                    SET resolved = 1, resolution_time = ?
                    WHERE alert_id = ?
                """, (datetime.utcnow().isoformat(), alert_id))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to resolve alert: {e}")
            return False
    
    def check_component_health(self, component_name: str) -> ComponentHealth:
        """Check health of a specific component"""
        try:
            start_time = time.time()
            status = HealthStatus.HEALTHY
            issues = []
            metrics = {}
            
            # Component-specific health checks
            if component_name == "pattern_recognition_engine":
                status, issues, metrics = self._check_pattern_engine_health()
            elif component_name == "pattern_application_engine":
                status, issues, metrics = self._check_application_engine_health()
            elif component_name == "execution_tracker":
                status, issues, metrics = self._check_execution_tracker_health()
            elif component_name == "context_intelligence":
                status, issues, metrics = self._check_context_intelligence_health()
            elif component_name == "agent_effectiveness":
                status, issues, metrics = self._check_effectiveness_tracker_health()
            
            response_time = (time.time() - start_time) * 1000  # milliseconds
            
            # Calculate error rate and uptime
            error_rate = self._calculate_error_rate(component_name)
            uptime_percentage = self._calculate_uptime(component_name)
            
            health = ComponentHealth(
                component_name=component_name,
                status=status,
                last_check=datetime.utcnow().isoformat(),
                response_time=response_time,
                error_rate=error_rate,
                uptime_percentage=uptime_percentage,
                metrics=metrics,
                issues=issues
            )
            
            self._store_component_health(health)
            return health
            
        except Exception as e:
            logger.error(f"Health check failed for {component_name}: {e}")
            return ComponentHealth(
                component_name=component_name,
                status=HealthStatus.DOWN,
                last_check=datetime.utcnow().isoformat(),
                response_time=0.0,
                error_rate=1.0,
                uptime_percentage=0.0,
                metrics={},
                issues=[f"Health check failed: {str(e)}"]
            )
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get comprehensive system overview"""
        try:
            overview = {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_health": HealthStatus.HEALTHY.value,
                "components": {},
                "active_alerts": 0,
                "performance_summary": {},
                "recommendations": []
            }
            
            # Check all components
            worst_status = HealthStatus.HEALTHY
            for component_name in self.components.keys():
                health = self.check_component_health(component_name)
                overview["components"][component_name] = health.__dict__
                
                # Track worst status
                if health.status.value == "critical":
                    worst_status = HealthStatus.CRITICAL
                elif health.status.value == "warning" and worst_status != HealthStatus.CRITICAL:
                    worst_status = HealthStatus.WARNING
            
            overview["overall_health"] = worst_status.value
            
            # Count active alerts
            overview["active_alerts"] = self._count_active_alerts()
            
            # Performance summary
            overview["performance_summary"] = self._get_performance_summary()
            
            # Generate recommendations
            overview["recommendations"] = self._generate_recommendations(overview)
            
            return overview
            
        except Exception as e:
            logger.error(f"Failed to get system overview: {e}")
            return {"error": str(e)}
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Check all component health
                for component_name in self.components.keys():
                    self.check_component_health(component_name)
                
                # Generate periodic reports
                if datetime.utcnow().minute % 10 == 0:  # Every 10 minutes
                    self._generate_periodic_report()
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(5)  # Brief pause before retrying
    
    def _check_pattern_engine_health(self) -> tuple:
        """Check pattern recognition engine health"""
        try:
            from pattern_recognition_engine import PatternRecognitionEngine
            engine = PatternRecognitionEngine()
            
            # Test basic functionality
            stats = engine.get_performance_stats()
            
            status = HealthStatus.HEALTHY
            issues = []
            metrics = {
                "total_patterns": stats.get("total_patterns", 0),
                "components_available": stats.get("components_available", False)
            }
            
            if not stats.get("components_available", False):
                status = HealthStatus.WARNING
                issues.append("Some components not available")
            
            return status, issues, metrics
            
        except Exception as e:
            return HealthStatus.DOWN, [f"Engine unavailable: {str(e)}"], {}
    
    def _check_application_engine_health(self) -> tuple:
        """Check pattern application engine health"""
        try:
            # This would check if the application engine is responsive
            # For now, return basic status
            return HealthStatus.HEALTHY, [], {"status": "operational"}
        except Exception as e:
            return HealthStatus.DOWN, [f"Application engine error: {str(e)}"], {}
    
    def _check_execution_tracker_health(self) -> tuple:
        """Check execution tracker health"""
        try:
            from execution_tracker import ExecutionTracker
            tracker = ExecutionTracker()
            
            # Test basic functionality
            stats = tracker.get_agent_performance_summary("test", 1)
            
            return HealthStatus.HEALTHY, [], {"executions_tracked": stats.get("total_executions", 0)}
        except Exception as e:
            return HealthStatus.DOWN, [f"Tracker error: {str(e)}"], {}
    
    def _check_context_intelligence_health(self) -> tuple:
        """Check context intelligence health"""
        try:
            from context_intelligence_engine import ContextIntelligenceEngine
            engine = ContextIntelligenceEngine()
            
            stats = engine.get_performance_stats()
            return HealthStatus.HEALTHY, [], {
                "total_entities": stats.get("total_entities", 0),
                "chroma_available": stats.get("chroma_available", False)
            }
        except Exception as e:
            return HealthStatus.DOWN, [f"Context intelligence error: {str(e)}"], {}
    
    def _check_effectiveness_tracker_health(self) -> tuple:
        """Check agent effectiveness tracker health"""
        try:
            from agent_effectiveness_tracker import AgentEffectivenessTracker
            tracker = AgentEffectivenessTracker()
            
            return HealthStatus.HEALTHY, [], {"status": "operational"}
        except Exception as e:
            return HealthStatus.DOWN, [f"Effectiveness tracker error: {str(e)}"], {}
    
    def _store_metric(self, metric: PerformanceMetric):
        """Store performance metric in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO performance_metrics
                    (name, value, unit, timestamp, tags)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    metric.name, metric.value, metric.unit, 
                    metric.timestamp, json.dumps(metric.tags)
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store metric: {e}")
    
    def _store_alert(self, alert: SystemAlert):
        """Store alert in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO system_alerts
                    (alert_id, level, title, description, component, timestamp, resolved, resolution_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert.alert_id, alert.level.value, alert.title, alert.description,
                    alert.component, alert.timestamp, alert.resolved, alert.resolution_time
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    def _store_component_health(self, health: ComponentHealth):
        """Store component health in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO component_health
                    (component_name, status, last_check, response_time, error_rate,
                     uptime_percentage, metrics, issues)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    health.component_name, health.status.value, health.last_check,
                    health.response_time, health.error_rate, health.uptime_percentage,
                    json.dumps(health.metrics), json.dumps(health.issues)
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store component health: {e}")
    
    def _check_metric_anomalies(self, metric_name: str, value: float):
        """Check for metric anomalies and create alerts if needed"""
        history = self.metric_history[metric_name]
        
        if len(history) < 10:  # Need enough data points
            return
        
        values = [v for _, v in history]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        
        # Simple anomaly detection: value is more than 2 standard deviations from mean
        if stdev > 0 and abs(value - mean) > 2 * stdev:
            self.create_alert(
                AlertLevel.WARNING,
                f"Anomaly detected in {metric_name}",
                f"Value {value} is significantly different from historical average {mean:.2f}",
                "pattern_system"
            )
    
    def _calculate_error_rate(self, component_name: str) -> float:
        """Calculate error rate for component"""
        # This would analyze recent errors for the component
        # For now, return a placeholder
        return 0.01  # 1% error rate
    
    def _calculate_uptime(self, component_name: str) -> float:
        """Calculate uptime percentage for component"""
        # This would track component availability over time
        # For now, return a placeholder
        return 99.5  # 99.5% uptime
    
    def _count_active_alerts(self) -> int:
        """Count active (unresolved) alerts"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM system_alerts WHERE resolved = 0")
                return cursor.fetchone()[0]
        except Exception:
            return 0
    
    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary from recent metrics"""
        summary = {}
        
        for metric_name, history in self.metric_history.items():
            if history:
                values = [v for _, v in history]
                summary[metric_name] = {
                    "current": values[-1] if values else 0,
                    "average": statistics.mean(values),
                    "min": min(values),
                    "max": max(values)
                }
        
        return summary
    
    def _generate_recommendations(self, overview: Dict[str, Any]) -> List[str]:
        """Generate system recommendations based on overview"""
        recommendations = []
        
        if overview["overall_health"] != "healthy":
            recommendations.append("System health requires attention - check component details")
        
        if overview["active_alerts"] > 0:
            recommendations.append(f"Resolve {overview['active_alerts']} active alerts")
        
        # Add component-specific recommendations
        for comp_name, comp_data in overview["components"].items():
            if comp_data["status"] != "healthy":
                recommendations.append(f"Investigate {comp_name} component issues")
        
        return recommendations
    
    def _generate_periodic_report(self):
        """Generate periodic monitoring report"""
        logger.info("Generating periodic monitoring report")
        overview = self.get_system_overview()
        
        # Log summary
        logger.info(f"System Health: {overview['overall_health']}")
        logger.info(f"Active Alerts: {overview['active_alerts']}")
        
        # Could send to external monitoring systems here

# Convenience functions
def start_monitoring(interval: int = 60) -> PatternSystemMonitor:
    """Start pattern system monitoring"""
    monitor = PatternSystemMonitor(interval)
    monitor.start_monitoring()
    return monitor

def quick_health_check() -> Dict[str, Any]:
    """Quick health check of pattern system"""
    monitor = PatternSystemMonitor()
    return monitor.get_system_overview()

if __name__ == "__main__":
    # Test the monitor
    logging.basicConfig(level=logging.INFO)
    
    print("Pattern System Monitor Test")
    print("=" * 50)
    
    monitor = PatternSystemMonitor()
    
    # Test performance metric
    monitor.record_performance_metric("test_metric", 42.5, "seconds", {"test": "true"})
    print("✓ Recorded test metric")
    
    # Test health check
    health = monitor.check_component_health("pattern_recognition_engine")
    print(f"✓ Component health: {health.status.value}")
    
    # Test system overview
    overview = monitor.get_system_overview()
    print(f"✓ System overview: {overview['overall_health']}")
    
    print("\nPattern System Monitor ready for integration")