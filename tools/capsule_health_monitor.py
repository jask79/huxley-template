#!/usr/bin/env python3
"""
Huxley - Capsule Health Monitor
Implements lifecycle maintenance monitoring for all capsules
"""

import json
import os
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

CATALYST_ROOT = Path("{{CATALYST_ROOT}}")

@dataclass
class HealthMetrics:
    uptime: float
    response_time_ms: int
    error_rate: float
    resource_usage: Dict[str, int]
    dependency_status: Dict[str, str]

@dataclass
class BusinessMetrics:
    category: str
    kpis: Dict[str, Dict[str, Any]]
    alerts: List[Dict[str, Any]]

class CapsuleHealthMonitor:
    def __init__(self):
        self.capsules_path = CATALYST_ROOT / "capsules"
        self.health_data_path = CATALYST_ROOT / "ops" / "health"
        self.health_data_path.mkdir(parents=True, exist_ok=True)
        
    def discover_capsules(self) -> List[Path]:
        """Discover all capsules with capsule.json"""
        capsules = []
        if self.capsules_path.exists():
            for item in self.capsules_path.iterdir():
                if item.is_dir() and (item / "capsule.json").exists():
                    capsules.append(item)
        return capsules
    
    def load_capsule_config(self, capsule_path: Path) -> Dict[str, Any]:
        """Load capsule configuration"""
        config_path = capsule_path / "capsule.json"
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def check_process_health(self, capsule_name: str) -> HealthMetrics:
        """Check health metrics for a capsule's processes"""
        # Placeholder implementation - would integrate with actual monitoring
        return HealthMetrics(
            uptime=0.998,
            response_time_ms=120,
            error_rate=0.001,
            resource_usage={"cpu": 15, "memory": 45, "storage": 60},
            dependency_status={"n8n": "healthy", "apis": "healthy"}
        )
    
    def check_business_metrics(self, capsule_config: Dict[str, Any]) -> BusinessMetrics:
        """Check business KPIs for a capsule"""
        # Placeholder - would integrate with analytics/business systems
        return BusinessMetrics(
            category=capsule_config.get("business_category", "automation"),
            kpis={
                "revenue": {"current": 1250, "target": 1500, "trend": "up"},
                "users": {"active": 45, "total": 120, "trend": "stable"}
            },
            alerts=[]
        )
    
    def evaluate_health_status(self, metrics: HealthMetrics) -> str:
        """Evaluate overall health status"""
        if metrics.error_rate > 0.05 or metrics.uptime < 0.95:
            return "failing"
        elif metrics.error_rate > 0.02 or metrics.response_time_ms > 1000:
            return "critical"
        elif metrics.error_rate > 0.01 or metrics.response_time_ms > 500:
            return "degraded"
        else:
            return "healthy"
    
    def check_maintenance_needed(self, capsule_config: Dict[str, Any], health_metrics: HealthMetrics) -> List[str]:
        """Check if maintenance is needed and return reasons"""
        maintenance_reasons = []
        
        # Check if scheduled maintenance is due
        lifecycle = capsule_config.get("lifecycle", {})
        next_maintenance = lifecycle.get("next_maintenance")
        if next_maintenance:
            next_date = datetime.fromisoformat(next_maintenance.replace('Z', '+00:00'))
            if datetime.now() > next_date:
                maintenance_reasons.append("scheduled_maintenance_due")
        
        # Check performance degradation
        if health_metrics.response_time_ms > 500:
            maintenance_reasons.append("performance_degradation")
        
        # Check error rate
        if health_metrics.error_rate > 0.02:
            maintenance_reasons.append("high_error_rate")
        
        return maintenance_reasons
    
    def generate_health_report(self, capsule_name: str, config: Dict[str, Any], 
                             health_metrics: HealthMetrics, business_metrics: BusinessMetrics) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        health_status = self.evaluate_health_status(health_metrics)
        maintenance_needed = self.check_maintenance_needed(config, health_metrics)
        
        return {
            "capsule": capsule_name,
            "timestamp": datetime.now().isoformat(),
            "status": config.get("status", "unknown"),
            "health": {
                "status": health_status,
                "metrics": {
                    "uptime": health_metrics.uptime,
                    "response_time_ms": health_metrics.response_time_ms,
                    "error_rate": health_metrics.error_rate,
                    "resource_usage": health_metrics.resource_usage
                },
                "dependencies": health_metrics.dependency_status
            },
            "business": {
                "category": business_metrics.category,
                "kpis": business_metrics.kpis,
                "alerts": business_metrics.alerts
            },
            "maintenance": {
                "needed": len(maintenance_needed) > 0,
                "reasons": maintenance_needed,
                "last_maintained": config.get("lifecycle", {}).get("last_maintained"),
                "next_scheduled": config.get("lifecycle", {}).get("next_maintenance")
            }
        }
    
    def save_health_report(self, report: Dict[str, Any]):
        """Save health report to file"""
        capsule_name = report["capsule"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save individual capsule report
        capsule_health_dir = self.health_data_path / capsule_name
        capsule_health_dir.mkdir(exist_ok=True)
        
        report_file = capsule_health_dir / f"health_{timestamp}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Update latest health status
        latest_file = capsule_health_dir / "health_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(report, f, indent=2)
    
    def generate_system_health_summary(self, reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate system-wide health summary"""
        total_capsules = len(reports)
        healthy = len([r for r in reports if r["health"]["status"] == "healthy"])
        degraded = len([r for r in reports if r["health"]["status"] == "degraded"])
        critical = len([r for r in reports if r["health"]["status"] == "critical"])
        failing = len([r for r in reports if r["health"]["status"] == "failing"])
        
        maintenance_needed = [r for r in reports if r["maintenance"]["needed"]]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_capsules": total_capsules,
                "healthy": healthy,
                "degraded": degraded,
                "critical": critical,
                "failing": failing
            },
            "maintenance": {
                "capsules_needing_maintenance": len(maintenance_needed),
                "capsules": [r["capsule"] for r in maintenance_needed]
            },
            "alerts": [
                r for r in reports 
                if r["health"]["status"] in ["critical", "failing"] or r["maintenance"]["needed"]
            ]
        }
    
    def send_alerts(self, report: Dict[str, Any]):
        """Send alerts for critical issues"""
        health_status = report["health"]["status"]
        capsule_name = report["capsule"]
        
        if health_status in ["critical", "failing"]:
            print(f"🚨 ALERT: Capsule {capsule_name} status: {health_status}")
            # Integrate with notification system
            self.log_alert(f"Health alert: {capsule_name} - {health_status}")
        
        if report["maintenance"]["needed"]:
            reasons = ", ".join(report["maintenance"]["reasons"])
            print(f"🔧 MAINTENANCE: Capsule {capsule_name} needs maintenance: {reasons}")
            self.log_alert(f"Maintenance needed: {capsule_name} - {reasons}")
    
    def log_alert(self, message: str):
        """Log alert to Huxley events"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "health_alert",
            "message": message,
            "source": "capsule_health_monitor"
        }
        
        events_file = CATALYST_ROOT / "global" / "events.log"
        with open(events_file, 'a') as f:
            f.write(json.dumps(log_entry) + "\\n")
    
    def run_health_check(self) -> Dict[str, Any]:
        """Run complete health check for all capsules"""
        print("🔍 Huxley - Capsule Health Check")
        
        capsules = self.discover_capsules()
        reports = []
        
        for capsule_path in capsules:
            capsule_name = capsule_path.name
            print(f"  📊 Checking {capsule_name}...")
            
            try:
                config = self.load_capsule_config(capsule_path)
                health_metrics = self.check_process_health(capsule_name)
                business_metrics = self.check_business_metrics(config)
                
                report = self.generate_health_report(
                    capsule_name, config, health_metrics, business_metrics
                )
                
                self.save_health_report(report)
                self.send_alerts(report)
                reports.append(report)
                
                status_icon = {
                    "healthy": "✅",
                    "degraded": "⚠️", 
                    "critical": "🚨",
                    "failing": "💥"
                }.get(report["health"]["status"], "❓")
                
                print(f"    {status_icon} {report['health']['status'].upper()}")
                
            except Exception as e:
                print(f"    ❌ ERROR: {e}")
                self.log_alert(f"Health check failed for {capsule_name}: {e}")
        
        # Generate system summary
        system_summary = self.generate_system_health_summary(reports)
        
        # Save system summary
        summary_file = self.health_data_path / "system_health_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(system_summary, f, indent=2)
        
        print(f"\\n📋 System Health Summary:")
        print(f"   Total Capsules: {system_summary['summary']['total_capsules']}")
        print(f"   ✅ Healthy: {system_summary['summary']['healthy']}")
        print(f"   ⚠️  Degraded: {system_summary['summary']['degraded']}")
        print(f"   🚨 Critical: {system_summary['summary']['critical']}")
        print(f"   💥 Failing: {system_summary['summary']['failing']}")
        print(f"   🔧 Need Maintenance: {system_summary['maintenance']['capsules_needing_maintenance']}")
        
        return system_summary

def main():
    monitor = CapsuleHealthMonitor()
    monitor.run_health_check()

if __name__ == "__main__":
    main()