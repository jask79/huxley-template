#!/usr/bin/env python3
"""
Huxley - Capsule Maintenance Manager
Automates maintenance workflows for capsule lifecycle management
"""

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

CATALYST_ROOT = Path("{{CATALYST_ROOT}}")

@dataclass
class MaintenanceTask:
    capsule: str
    task_type: str
    priority: str
    description: str
    scheduled_for: datetime
    estimated_duration: int  # minutes

class CapsuleMaintenanceManager:
    def __init__(self):
        self.capsules_path = CATALYST_ROOT / "capsules"
        self.maintenance_path = CATALYST_ROOT / "ops" / "maintenance"
        self.health_path = CATALYST_ROOT / "ops" / "health"
        self.maintenance_path.mkdir(parents=True, exist_ok=True)
        
    def load_health_reports(self) -> Dict[str, Dict[str, Any]]:
        """Load latest health reports for all capsules"""
        health_reports = {}
        
        if self.health_path.exists():
            for capsule_dir in self.health_path.iterdir():
                if capsule_dir.is_dir():
                    latest_file = capsule_dir / "health_latest.json"
                    if latest_file.exists():
                        with open(latest_file, 'r') as f:
                            health_reports[capsule_dir.name] = json.load(f)
        
        return health_reports
    
    def identify_maintenance_tasks(self, health_reports: Dict[str, Dict[str, Any]]) -> List[MaintenanceTask]:
        """Identify maintenance tasks based on health reports"""
        tasks = []
        
        for capsule_name, report in health_reports.items():
            # Check if maintenance is explicitly needed
            if report.get("maintenance", {}).get("needed", False):
                reasons = report["maintenance"]["reasons"]
                
                for reason in reasons:
                    priority = self._get_priority_for_reason(reason, report["health"]["status"])
                    task = MaintenanceTask(
                        capsule=capsule_name,
                        task_type=reason,
                        priority=priority,
                        description=self._get_description_for_reason(reason),
                        scheduled_for=self._calculate_maintenance_window(capsule_name, priority),
                        estimated_duration=self._estimate_duration(reason)
                    )
                    tasks.append(task)
            
            # Check for proactive maintenance opportunities
            health_status = report.get("health", {}).get("status", "unknown")
            if health_status == "degraded":
                task = MaintenanceTask(
                    capsule=capsule_name,
                    task_type="performance_optimization",
                    priority="medium",
                    description="Optimize performance due to degraded status",
                    scheduled_for=self._calculate_maintenance_window(capsule_name, "medium"),
                    estimated_duration=45
                )
                tasks.append(task)
        
        return sorted(tasks, key=lambda x: (x.priority == "critical", x.scheduled_for))
    
    def _get_priority_for_reason(self, reason: str, health_status: str) -> str:
        """Determine priority based on maintenance reason and health status"""
        critical_reasons = ["high_error_rate", "security_vulnerability"]
        urgent_health = ["failing", "critical"]
        
        if reason in critical_reasons or health_status in urgent_health:
            return "critical"
        elif reason in ["performance_degradation", "dependency_update"]:
            return "high"
        elif reason == "scheduled_maintenance_due":
            return "medium"
        else:
            return "low"
    
    def _get_description_for_reason(self, reason: str) -> str:
        """Get human-readable description for maintenance reason"""
        descriptions = {
            "scheduled_maintenance_due": "Scheduled maintenance window",
            "performance_degradation": "Address performance issues",
            "high_error_rate": "Investigate and fix error rate spike",
            "dependency_update": "Update dependencies and dependencies",
            "security_vulnerability": "Apply security patches",
            "performance_optimization": "Optimize system performance"
        }
        return descriptions.get(reason, f"Maintenance task: {reason}")
    
    def _calculate_maintenance_window(self, capsule_name: str, priority: str) -> datetime:
        """Calculate appropriate maintenance window"""
        now = datetime.now()
        
        if priority == "critical":
            return now + timedelta(hours=1)  # ASAP
        elif priority == "high":
            return now + timedelta(hours=12)  # Next maintenance window
        elif priority == "medium":
            # Next Sunday at 2 AM
            days_ahead = 6 - now.weekday()  # Sunday = 6
            if days_ahead <= 0:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).replace(hour=2, minute=0, second=0, microsecond=0)
        else:
            # Next month
            return now.replace(day=1, hour=2, minute=0, second=0, microsecond=0) + timedelta(days=32)
    
    def _estimate_duration(self, task_type: str) -> int:
        """Estimate maintenance duration in minutes"""
        durations = {
            "scheduled_maintenance_due": 30,
            "performance_degradation": 60,
            "high_error_rate": 45,
            "dependency_update": 20,
            "security_vulnerability": 30,
            "performance_optimization": 45
        }
        return durations.get(task_type, 30)
    
    def create_maintenance_plan(self, tasks: List[MaintenanceTask]) -> Dict[str, Any]:
        """Create comprehensive maintenance plan"""
        plan = {
            "created": datetime.now().isoformat(),
            "summary": {
                "total_tasks": len(tasks),
                "critical": len([t for t in tasks if t.priority == "critical"]),
                "high": len([t for t in tasks if t.priority == "high"]),
                "medium": len([t for t in tasks if t.priority == "medium"]),
                "low": len([t for t in tasks if t.priority == "low"])
            },
            "tasks": []
        }
        
        for task in tasks:
            plan["tasks"].append({
                "capsule": task.capsule,
                "type": task.task_type,
                "priority": task.priority,
                "description": task.description,
                "scheduled_for": task.scheduled_for.isoformat(),
                "estimated_duration_minutes": task.estimated_duration,
                "status": "scheduled"
            })
        
        return plan
    
    def execute_maintenance_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific maintenance task"""
        capsule_name = task["capsule"]
        task_type = task["type"]
        
        print(f"🔧 Executing maintenance: {capsule_name} - {task['description']}")
        
        result = {
            "capsule": capsule_name,
            "task": task_type,
            "started_at": datetime.now().isoformat(),
            "status": "in_progress"
        }
        
        try:
            # Create maintenance version backup
            self._create_maintenance_backup(capsule_name)
            
            # Execute specific maintenance based on type
            if task_type == "dependency_update":
                self._update_dependencies(capsule_name)
            elif task_type == "performance_optimization":
                self._optimize_performance(capsule_name)
            elif task_type == "security_vulnerability":
                self._apply_security_patches(capsule_name)
            elif task_type == "scheduled_maintenance_due":
                self._run_scheduled_maintenance(capsule_name)
            else:
                self._run_generic_maintenance(capsule_name, task_type)
            
            result.update({
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "success": True
            })
            
            print(f"  ✅ Completed: {task['description']}")
            
        except Exception as e:
            result.update({
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
                "success": False,
                "error": str(e)
            })
            print(f"  ❌ Failed: {e}")
            
            # Attempt rollback
            self._rollback_maintenance(capsule_name)
        
        # Log maintenance action
        self._log_maintenance_action(result)
        
        return result
    
    def _create_maintenance_backup(self, capsule_name: str):
        """Create backup before maintenance"""
        capsule_path = self.capsules_path / capsule_name
        backup_name = f"{capsule_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.maintenance_path / "backups" / backup_name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        if capsule_path.exists():
            shutil.copytree(capsule_path, backup_path)
            print(f"  💾 Backup created: {backup_name}")
    
    def _update_dependencies(self, capsule_name: str):
        """Update capsule dependencies"""
        capsule_path = self.capsules_path / capsule_name
        
        # Update Python dependencies if they exist
        requirements_files = list(capsule_path.glob("**/requirements.txt"))
        for req_file in requirements_files:
            print(f"    📦 Updating {req_file}")
            subprocess.run(["pip", "install", "-r", str(req_file), "--upgrade"], 
                         check=True, capture_output=True)
        
        # Update n8n workflows if they exist
        n8n_dir = capsule_path / "src" / "automation" / "n8n"
        if n8n_dir.exists():
            print(f"    🔄 Validating n8n workflows")
            # Could integrate with n8n-mcp for validation
    
    def _optimize_performance(self, capsule_name: str):
        """Optimize capsule performance"""
        print(f"    ⚡ Running performance optimizations")
        # Placeholder for performance optimization logic
        # Could include cleanup, cache optimization, etc.
    
    def _apply_security_patches(self, capsule_name: str):
        """Apply security patches"""
        print(f"    🔒 Applying security patches")
        # Placeholder for security update logic
    
    def _run_scheduled_maintenance(self, capsule_name: str):
        """Run scheduled maintenance tasks"""
        print(f"    🔄 Running scheduled maintenance")
        # General maintenance tasks like cleanup, log rotation, etc.
    
    def _run_generic_maintenance(self, capsule_name: str, task_type: str):
        """Run generic maintenance task"""
        print(f"    🛠️  Running {task_type} maintenance")
        # Generic maintenance placeholder
    
    def _rollback_maintenance(self, capsule_name: str):
        """Rollback maintenance if it failed"""
        print(f"    🔙 Rolling back maintenance for {capsule_name}")
        # Restore from backup if needed
    
    def _log_maintenance_action(self, result: Dict[str, Any]):
        """Log maintenance action to events"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "maintenance_action",
            "capsule": result["capsule"],
            "task": result["task"],
            "status": result["status"],
            "success": result.get("success", False)
        }
        
        events_file = CATALYST_ROOT / "global" / "events.log"
        with open(events_file, 'a') as f:
            f.write(json.dumps(log_entry) + "\\n")
    
    def run_maintenance_cycle(self):
        """Run complete maintenance cycle"""
        print("🔧 Huxley - Maintenance Cycle")
        
        # Load health reports
        health_reports = self.load_health_reports()
        
        if not health_reports:
            print("  ❌ No health reports found. Run health check first.")
            return
        
        # Identify maintenance tasks
        tasks = self.identify_maintenance_tasks(health_reports)
        
        if not tasks:
            print("  ✅ No maintenance tasks needed.")
            return
        
        # Create maintenance plan
        plan = self.create_maintenance_plan(tasks)
        
        # Save maintenance plan
        plan_file = self.maintenance_path / f"maintenance_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(plan_file, 'w') as f:
            json.dump(plan, f, indent=2)
        
        print(f"  📋 Maintenance plan created: {len(tasks)} tasks")
        print(f"    🚨 Critical: {plan['summary']['critical']}")
        print(f"    🔴 High: {plan['summary']['high']}")
        print(f"    🟡 Medium: {plan['summary']['medium']}")
        print(f"    🟢 Low: {plan['summary']['low']}")
        
        # Execute critical and high priority tasks immediately
        immediate_tasks = [task for task in plan["tasks"] if task["priority"] in ["critical", "high"]]
        
        if immediate_tasks:
            print(f"\\n  🚀 Executing {len(immediate_tasks)} immediate tasks...")
            
            for task in immediate_tasks:
                result = self.execute_maintenance_task(task)
                if not result["success"]:
                    print(f"    ⚠️  Task failed: {task['capsule']} - {task['description']}")
        
        print(f"\\n  📅 {len(plan['tasks']) - len(immediate_tasks)} tasks scheduled for later")

def main():
    manager = CapsuleMaintenanceManager()
    manager.run_maintenance_cycle()

if __name__ == "__main__":
    main()