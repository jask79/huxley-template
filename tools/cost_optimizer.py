#!/usr/bin/env python3
"""
Cost Attribution and Optimization System for Huxley
Real-time cost tracking, attribution, and optimization recommendations
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CostCategory(Enum):
    """Cost categories for attribution"""
    DEVELOPMENT = "development"
    INFRASTRUCTURE = "infrastructure"
    TOOLS = "tools"
    STORAGE = "storage"
    COMPUTE = "compute"
    NETWORK = "network"
    LICENSING = "licensing"
    MAINTENANCE = "maintenance"

@dataclass
class CostEntry:
    """Individual cost entry"""
    timestamp: datetime
    capsule_name: str
    category: CostCategory
    resource_type: str
    quantity: float
    unit_cost: float
    total_cost: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'capsule_name': self.capsule_name,
            'category': self.category.value,
            'resource_type': self.resource_type,
            'quantity': self.quantity,
            'unit_cost': self.unit_cost,
            'total_cost': self.total_cost,
            'metadata': self.metadata
        }

@dataclass
class CostOptimization:
    """Cost optimization recommendation"""
    capsule_name: str
    optimization_type: str
    current_cost: float
    optimized_cost: float
    savings: float
    savings_percentage: float
    recommendation: str
    implementation_effort: str  # 'low', 'medium', 'high'
    risk_level: str  # 'low', 'medium', 'high'
    priority_score: float

@dataclass
class CostBudget:
    """Cost budget configuration"""
    capsule_name: str
    category: CostCategory
    monthly_limit: float
    alert_threshold: float  # percentage (0-1)
    hard_limit: bool  # stop when exceeded

class CostOptimizer:
    """Advanced cost attribution and optimization system"""
    
    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.cost_path = self.catalyst_root / "registry/costs"
        self.cost_path.mkdir(parents=True, exist_ok=True)
        
        # Database for cost tracking
        self.db_path = self.cost_path / "cost_tracking.db"
        self._init_database()
        
        # Cost configuration
        self.cost_rates = self._load_cost_rates()
        self.budgets = self._load_budgets()
        
        # Optimization cache
        self.optimization_cache = {}
        
        logger.info("Cost Optimizer initialized")
    
    def _init_database(self):
        """Initialize SQLite database for cost tracking"""
        with sqlite3.connect(self.db_path) as conn:
            # Cost entries table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cost_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    capsule_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    unit_cost REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Budgets table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capsule_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    monthly_limit REAL NOT NULL,
                    alert_threshold REAL NOT NULL,
                    hard_limit BOOLEAN NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(capsule_name, category)
                )
            ''')
            
            # Cost optimizations table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS optimizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capsule_name TEXT NOT NULL,
                    optimization_type TEXT NOT NULL,
                    current_cost REAL NOT NULL,
                    optimized_cost REAL NOT NULL,
                    savings REAL NOT NULL,
                    recommendation TEXT NOT NULL,
                    implementation_effort TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    priority_score REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            conn.execute('CREATE INDEX IF NOT EXISTS idx_cost_capsule_time ON cost_entries(capsule_name, timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_cost_category ON cost_entries(category)')
    
    def _load_cost_rates(self) -> Dict[str, Dict[str, float]]:
        """Load cost rates configuration"""
        config_path = self.cost_path / "cost_rates.json"
        
        # Default cost rates (per hour/unit)
        default_rates = {
            CostCategory.DEVELOPMENT.value: {
                "junior_developer": 75.0,
                "senior_developer": 150.0,
                "architect": 200.0,
                "pm": 125.0
            },
            CostCategory.INFRASTRUCTURE.value: {
                "aws_ec2_t3_small": 0.0208,
                "aws_ec2_t3_medium": 0.0416,
                "aws_ec2_t3_large": 0.0832,
                "aws_rds_t3_micro": 0.017,
                "aws_s3_storage": 0.023,  # per GB/month
                "aws_lambda_requests": 0.0000002,  # per request
                "aws_lambda_duration": 0.0000166667,  # per GB-second
            },
            CostCategory.TOOLS.value: {
                "github_pro": 4.0,  # per user/month
                "slack_pro": 7.25,  # per user/month
                "figma_pro": 12.0,  # per user/month
                "datadog": 15.0,  # per host/month
                "sentry": 26.0,  # per month
            },
            CostCategory.STORAGE.value: {
                "s3_standard": 0.023,  # per GB/month
                "s3_ia": 0.0125,  # per GB/month
                "ebs_gp3": 0.08,  # per GB/month
                "backup_storage": 0.05,  # per GB/month
            },
            CostCategory.COMPUTE.value: {
                "cpu_hour": 0.10,
                "gpu_hour": 2.50,
                "memory_gb_hour": 0.05,
                "network_gb": 0.09,
            },
            CostCategory.LICENSING.value: {
                "code_analysis": 50.0,  # per month
                "security_scanning": 100.0,  # per month
                "performance_monitoring": 75.0,  # per month
            }
        }
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    user_rates = json.load(f)
                
                # Merge with defaults
                for category, rates in user_rates.items():
                    if category in default_rates:
                        default_rates[category].update(rates)
                    else:
                        default_rates[category] = rates
                        
            except Exception as e:
                logger.warning(f"Failed to load cost rates: {e}")
        
        # Save defaults if file doesn't exist
        if not config_path.exists():
            with open(config_path, 'w') as f:
                json.dump(default_rates, f, indent=2)
        
        return default_rates
    
    def _load_budgets(self) -> Dict[str, Dict[str, CostBudget]]:
        """Load budget configurations"""
        budgets = {}
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT capsule_name, category, monthly_limit, alert_threshold, hard_limit
                FROM budgets
            ''')
            
            for row in cursor.fetchall():
                capsule_name, category, monthly_limit, alert_threshold, hard_limit = row
                
                if capsule_name not in budgets:
                    budgets[capsule_name] = {}
                
                budgets[capsule_name][category] = CostBudget(
                    capsule_name=capsule_name,
                    category=CostCategory(category),
                    monthly_limit=monthly_limit,
                    alert_threshold=alert_threshold,
                    hard_limit=bool(hard_limit)
                )
        
        return budgets
    
    def record_cost(self, capsule_name: str, category: CostCategory, 
                   resource_type: str, quantity: float, 
                   metadata: Optional[Dict[str, Any]] = None) -> float:
        """Record a cost entry"""
        # Get unit cost
        unit_cost = self.cost_rates.get(category.value, {}).get(resource_type, 0.0)
        total_cost = quantity * unit_cost
        
        # Create cost entry
        entry = CostEntry(
            timestamp=datetime.now(),
            capsule_name=capsule_name,
            category=category,
            resource_type=resource_type,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            metadata=metadata or {}
        )
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO cost_entries 
                (timestamp, capsule_name, category, resource_type, quantity, unit_cost, total_cost, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.timestamp.isoformat(),
                entry.capsule_name,
                entry.category.value,
                entry.resource_type,
                entry.quantity,
                entry.unit_cost,
                entry.total_cost,
                json.dumps(entry.metadata)
            ))
        
        # Check budget alerts
        self._check_budget_alerts(capsule_name, category, total_cost)
        
        logger.debug(f"Recorded cost: {capsule_name} - {resource_type}: ${total_cost:.2f}")
        return total_cost
    
    def _check_budget_alerts(self, capsule_name: str, category: CostCategory, new_cost: float):
        """Check for budget threshold breaches"""
        if capsule_name not in self.budgets:
            return
        
        if category.value not in self.budgets[capsule_name]:
            return
        
        budget = self.budgets[capsule_name][category.value]
        
        # Get current month's spending
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_spending = self.get_cost_summary(
            capsule_name=capsule_name,
            category=category.value,
            start_date=start_of_month
        )['total_cost']
        
        # Check thresholds
        threshold_amount = budget.monthly_limit * budget.alert_threshold
        
        if current_spending >= threshold_amount:
            alert_level = 'critical' if current_spending >= budget.monthly_limit else 'warning'
            
            logger.warning(f"Budget alert [{alert_level}] {capsule_name}/{category.value}: "
                          f"${current_spending:.2f} / ${budget.monthly_limit:.2f} "
                          f"({current_spending/budget.monthly_limit:.1%})")
            
            # Store alert (could trigger notifications)
            self._create_budget_alert(capsule_name, category, current_spending, budget)
    
    def _create_budget_alert(self, capsule_name: str, category: CostCategory, 
                           current_spending: float, budget: CostBudget):
        """Create a budget alert"""
        # This could integrate with notification systems
        alert_data = {
            'timestamp': datetime.now().isoformat(),
            'capsule_name': capsule_name,
            'category': category.value,
            'current_spending': current_spending,
            'budget_limit': budget.monthly_limit,
            'percentage_used': current_spending / budget.monthly_limit,
            'hard_limit': budget.hard_limit
        }
        
        # Save alert
        alerts_path = self.cost_path / "budget_alerts.jsonl"
        with open(alerts_path, 'a') as f:
            f.write(json.dumps(alert_data) + '\n')
    
    def set_budget(self, capsule_name: str, category: CostCategory, 
                   monthly_limit: float, alert_threshold: float = 0.8,
                   hard_limit: bool = False):
        """Set budget for a capsule category"""
        budget = CostBudget(
            capsule_name=capsule_name,
            category=category,
            monthly_limit=monthly_limit,
            alert_threshold=alert_threshold,
            hard_limit=hard_limit
        )
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO budgets 
                (capsule_name, category, monthly_limit, alert_threshold, hard_limit)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                budget.capsule_name,
                budget.category.value,
                budget.monthly_limit,
                budget.alert_threshold,
                budget.hard_limit
            ))
        
        # Update cache
        if capsule_name not in self.budgets:
            self.budgets[capsule_name] = {}
        self.budgets[capsule_name][category.value] = budget
        
        logger.info(f"Set budget for {capsule_name}/{category.value}: ${monthly_limit:.2f}")
    
    def get_cost_summary(self, capsule_name: Optional[str] = None,
                        category: Optional[str] = None,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get cost summary with filtering"""
        # Build query
        query = 'SELECT capsule_name, category, resource_type, SUM(total_cost) as total_cost, COUNT(*) as entries FROM cost_entries WHERE 1=1'
        params = []
        
        if capsule_name:
            query += ' AND capsule_name = ?'
            params.append(capsule_name)
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date.isoformat())
        
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date.isoformat())
        
        query += ' GROUP BY capsule_name, category, resource_type ORDER BY total_cost DESC'
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            return {
                'total_cost': 0.0,
                'breakdown': {},
                'entries_count': 0
            }
        
        # Calculate summary
        total_cost = df['total_cost'].sum()
        entries_count = df['entries'].sum()
        
        # Breakdown by category
        category_breakdown = df.groupby('category')['total_cost'].sum().to_dict()
        
        # Breakdown by capsule
        capsule_breakdown = df.groupby('capsule_name')['total_cost'].sum().to_dict()
        
        # Top resources
        top_resources = df.nlargest(10, 'total_cost')[['resource_type', 'total_cost']].to_dict('records')
        
        return {
            'total_cost': total_cost,
            'entries_count': int(entries_count),
            'breakdown': {
                'by_category': category_breakdown,
                'by_capsule': capsule_breakdown,
                'top_resources': top_resources
            }
        }
    
    def identify_cost_optimizations(self, capsule_name: Optional[str] = None) -> List[CostOptimization]:
        """Identify cost optimization opportunities"""
        optimizations = []
        
        # Get recent cost data (last 30 days)
        start_date = datetime.now() - timedelta(days=30)
        summary = self.get_cost_summary(capsule_name=capsule_name, start_date=start_date)
        
        if summary['total_cost'] == 0:
            return optimizations
        
        # Get detailed data for analysis
        query = '''
            SELECT capsule_name, category, resource_type, 
                   AVG(quantity) as avg_quantity, SUM(total_cost) as total_cost,
                   COUNT(*) as usage_count
            FROM cost_entries 
            WHERE timestamp >= ?
        '''
        params = [start_date.isoformat()]
        
        if capsule_name:
            query += ' AND capsule_name = ?'
            params.append(capsule_name)
        
        query += ' GROUP BY capsule_name, category, resource_type HAVING total_cost > 10'
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        # Analyze each cost center
        for _, row in df.iterrows():
            caps_name = row['capsule_name']
            category = row['category']
            resource_type = row['resource_type']
            avg_quantity = row['avg_quantity']
            total_cost = row['total_cost']
            usage_count = row['usage_count']
            
            # Infrastructure optimizations
            if category == CostCategory.INFRASTRUCTURE.value:
                opt = self._analyze_infrastructure_optimization(
                    caps_name, resource_type, avg_quantity, total_cost, usage_count
                )
                if opt:
                    optimizations.append(opt)
            
            # Development optimizations
            elif category == CostCategory.DEVELOPMENT.value:
                opt = self._analyze_development_optimization(
                    caps_name, resource_type, avg_quantity, total_cost, usage_count
                )
                if opt:
                    optimizations.append(opt)
            
            # Storage optimizations
            elif category == CostCategory.STORAGE.value:
                opt = self._analyze_storage_optimization(
                    caps_name, resource_type, avg_quantity, total_cost, usage_count
                )
                if opt:
                    optimizations.append(opt)
        
        # Sort by potential savings
        optimizations.sort(key=lambda x: x.savings, reverse=True)
        
        # Store optimizations
        self._store_optimizations(optimizations)
        
        return optimizations
    
    def _analyze_infrastructure_optimization(self, capsule_name: str, resource_type: str,
                                           avg_quantity: float, total_cost: float,
                                           usage_count: int) -> Optional[CostOptimization]:
        """Analyze infrastructure cost optimizations"""
        # Check for oversized instances
        if 'ec2' in resource_type.lower():
            if avg_quantity < 50:  # Low CPU utilization
                # Suggest smaller instance
                current_cost = total_cost
                optimized_cost = current_cost * 0.5  # 50% savings
                savings = current_cost - optimized_cost
                
                return CostOptimization(
                    capsule_name=capsule_name,
                    optimization_type="downsize_instance",
                    current_cost=current_cost,
                    optimized_cost=optimized_cost,
                    savings=savings,
                    savings_percentage=savings / current_cost,
                    recommendation=f"Downsize {resource_type} due to low utilization ({avg_quantity:.1f}%)",
                    implementation_effort="low",
                    risk_level="low",
                    priority_score=savings * 0.8  # High savings, low risk
                )
        
        # Check for reserved instance opportunities
        if usage_count > 20:  # Consistent usage
            current_cost = total_cost
            optimized_cost = current_cost * 0.7  # 30% savings with reserved instances
            savings = current_cost - optimized_cost
            
            return CostOptimization(
                capsule_name=capsule_name,
                optimization_type="reserved_instances",
                current_cost=current_cost,
                optimized_cost=optimized_cost,
                savings=savings,
                savings_percentage=savings / current_cost,
                recommendation=f"Use reserved instances for consistent {resource_type} usage",
                implementation_effort="medium",
                risk_level="low",
                priority_score=savings * 0.9
            )
        
        return None
    
    def _analyze_development_optimization(self, capsule_name: str, resource_type: str,
                                        avg_quantity: float, total_cost: float,
                                        usage_count: int) -> Optional[CostOptimization]:
        """Analyze development cost optimizations"""
        # Check for automation opportunities
        if avg_quantity > 20:  # High manual effort
            current_cost = total_cost
            optimized_cost = current_cost * 0.6  # 40% savings through automation
            savings = current_cost - optimized_cost
            
            return CostOptimization(
                capsule_name=capsule_name,
                optimization_type="automation",
                current_cost=current_cost,
                optimized_cost=optimized_cost,
                savings=savings,
                savings_percentage=savings / current_cost,
                recommendation=f"Automate {resource_type} tasks to reduce manual effort",
                implementation_effort="high",
                risk_level="medium",
                priority_score=savings * 0.6  # High savings but high effort
            )
        
        return None
    
    def _analyze_storage_optimization(self, capsule_name: str, resource_type: str,
                                    avg_quantity: float, total_cost: float,
                                    usage_count: int) -> Optional[CostOptimization]:
        """Analyze storage cost optimizations"""
        # Check for tiering opportunities
        if 's3_standard' in resource_type and avg_quantity > 100:  # Large storage
            current_cost = total_cost
            optimized_cost = current_cost * 0.5  # 50% savings with intelligent tiering
            savings = current_cost - optimized_cost
            
            return CostOptimization(
                capsule_name=capsule_name,
                optimization_type="storage_tiering",
                current_cost=current_cost,
                optimized_cost=optimized_cost,
                savings=savings,
                savings_percentage=savings / current_cost,
                recommendation=f"Enable intelligent tiering for {resource_type}",
                implementation_effort="low",
                risk_level="low",
                priority_score=savings * 0.9
            )
        
        return None
    
    def _store_optimizations(self, optimizations: List[CostOptimization]):
        """Store optimization recommendations"""
        with sqlite3.connect(self.db_path) as conn:
            for opt in optimizations:
                conn.execute('''
                    INSERT OR REPLACE INTO optimizations 
                    (capsule_name, optimization_type, current_cost, optimized_cost, 
                     savings, recommendation, implementation_effort, risk_level, priority_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    opt.capsule_name,
                    opt.optimization_type,
                    opt.current_cost,
                    opt.optimized_cost,
                    opt.savings,
                    opt.recommendation,
                    opt.implementation_effort,
                    opt.risk_level,
                    opt.priority_score
                ))
    
    def get_cost_forecast(self, capsule_name: str, days: int = 30) -> Dict[str, Any]:
        """Forecast future costs based on historical trends"""
        # Get historical data
        start_date = datetime.now() - timedelta(days=days*2)  # Use 2x period for trend analysis
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query('''
                SELECT DATE(timestamp) as date, SUM(total_cost) as daily_cost
                FROM cost_entries 
                WHERE capsule_name = ? AND timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            ''', conn, params=[capsule_name, start_date.isoformat()])
        
        if len(df) < 7:  # Need at least a week of data
            return {
                'forecast_available': False,
                'reason': 'Insufficient historical data'
            }
        
        # Calculate trend
        df['date'] = pd.to_datetime(df['date'])
        df['days_from_start'] = (df['date'] - df['date'].min()).dt.days
        
        # Linear regression for trend
        coeffs = np.polyfit(df['days_from_start'], df['daily_cost'], 1)
        trend_slope = coeffs[0]
        
        # Calculate forecast
        current_daily_avg = df['daily_cost'].tail(7).mean()  # Last week average
        forecast_daily = current_daily_avg + (trend_slope * days / 2)  # Projected average
        forecast_total = forecast_daily * days
        
        # Calculate confidence
        recent_std = df['daily_cost'].tail(14).std()
        confidence = max(0.1, 1 - (recent_std / current_daily_avg)) if current_daily_avg > 0 else 0.5
        
        return {
            'forecast_available': True,
            'forecast_period_days': days,
            'current_daily_average': current_daily_avg,
            'forecast_daily_average': forecast_daily,
            'forecast_total': forecast_total,
            'trend_direction': 'increasing' if trend_slope > 0 else 'decreasing' if trend_slope < 0 else 'stable',
            'trend_slope': trend_slope,
            'confidence': confidence,
            'range': {
                'low': forecast_total * 0.8,
                'high': forecast_total * 1.3
            }
        }
    
    def generate_cost_report(self, period_days: int = 30) -> str:
        """Generate comprehensive cost report"""
        start_date = datetime.now() - timedelta(days=period_days)
        
        # Get summary data
        summary = self.get_cost_summary(start_date=start_date)
        optimizations = self.identify_cost_optimizations()
        
        # Generate report
        report_path = self.cost_path / f"cost_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        report = f"""# Huxley Cost Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Period: {period_days} days

## Executive Summary
- **Total Costs**: ${summary['total_cost']:.2f}
- **Daily Average**: ${summary['total_cost'] / period_days:.2f}
- **Cost Entries**: {summary['entries_count']:,}
- **Optimization Potential**: ${sum(opt.savings for opt in optimizations):.2f}

## Cost Breakdown
"""
        
        # Category breakdown
        if summary['breakdown']['by_category']:
            report += "\n### By Category\n"
            for category, cost in sorted(summary['breakdown']['by_category'].items(), 
                                       key=lambda x: x[1], reverse=True):
                percentage = (cost / summary['total_cost']) * 100
                report += f"- **{category.replace('_', ' ').title()}**: ${cost:.2f} ({percentage:.1f}%)\n"
        
        # Capsule breakdown
        if summary['breakdown']['by_capsule']:
            report += "\n### By Capsule\n"
            for capsule, cost in sorted(summary['breakdown']['by_capsule'].items(), 
                                      key=lambda x: x[1], reverse=True)[:10]:
                percentage = (cost / summary['total_cost']) * 100
                report += f"- **{capsule}**: ${cost:.2f} ({percentage:.1f}%)\n"
        
        # Optimization opportunities
        if optimizations:
            report += "\n## Cost Optimization Opportunities\n"
            total_potential_savings = sum(opt.savings for opt in optimizations)
            report += f"**Total Potential Savings**: ${total_potential_savings:.2f}\n\n"
            
            # Group by priority
            high_priority = [opt for opt in optimizations if opt.priority_score > 100]
            medium_priority = [opt for opt in optimizations if 50 <= opt.priority_score <= 100]
            
            if high_priority:
                report += "### 🔥 High Priority\n"
                for opt in high_priority[:5]:
                    report += f"- **{opt.capsule_name}**: {opt.recommendation}\n"
                    report += f"  - Savings: ${opt.savings:.2f} ({opt.savings_percentage:.1%})\n"
                    report += f"  - Effort: {opt.implementation_effort}, Risk: {opt.risk_level}\n\n"
            
            if medium_priority:
                report += "### 📊 Medium Priority\n"
                for opt in medium_priority[:3]:
                    report += f"- **{opt.capsule_name}**: {opt.recommendation}\n"
                    report += f"  - Savings: ${opt.savings:.2f} ({opt.savings_percentage:.1%})\n\n"
        
        # Budget status
        report += "\n## Budget Status\n"
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_summary = self.get_cost_summary(start_date=current_month_start)
        
        budget_alerts = []
        for capsule_name, categories in self.budgets.items():
            for category_name, budget in categories.items():
                capsule_month_cost = self.get_cost_summary(
                    capsule_name=capsule_name,
                    category=category_name,
                    start_date=current_month_start
                )['total_cost']
                
                usage_pct = (capsule_month_cost / budget.monthly_limit) * 100
                status = "🔴 Over budget" if usage_pct > 100 else "🟡 Near limit" if usage_pct > 80 else "🟢 On track"
                
                report += f"- **{capsule_name}/{category_name}**: ${capsule_month_cost:.2f} / ${budget.monthly_limit:.2f} ({usage_pct:.1f}%) {status}\n"
        
        # Save report
        with open(report_path, 'w') as f:
            f.write(report)
        
        logger.info(f"Cost report generated: {report_path}")
        return str(report_path)


def main():
    """CLI interface for cost optimizer"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cost Attribution and Optimization")
    parser.add_argument("command", choices=["record", "summary", "optimize", "budget", "forecast", "report"],
                       help="Command to execute")
    parser.add_argument("--capsule", help="Capsule name")
    parser.add_argument("--category", choices=[c.value for c in CostCategory], help="Cost category")
    parser.add_argument("--resource", help="Resource type")
    parser.add_argument("--quantity", type=float, help="Resource quantity")
    parser.add_argument("--limit", type=float, help="Budget limit")
    parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    
    args = parser.parse_args()
    
    optimizer = CostOptimizer()
    
    if args.command == "record":
        if not all([args.capsule, args.category, args.resource, args.quantity]):
            print("Error: --capsule, --category, --resource, and --quantity required")
            return
        
        cost = optimizer.record_cost(
            args.capsule, 
            CostCategory(args.category), 
            args.resource, 
            args.quantity
        )
        print(f"Recorded cost: ${cost:.2f}")
    
    elif args.command == "summary":
        summary = optimizer.get_cost_summary(
            capsule_name=args.capsule,
            category=args.category,
            start_date=datetime.now() - timedelta(days=args.days)
        )
        print(json.dumps(summary, indent=2, default=str))
    
    elif args.command == "optimize":
        optimizations = optimizer.identify_cost_optimizations(args.capsule)
        
        if optimizations:
            print("COST OPTIMIZATION OPPORTUNITIES:")
            total_savings = sum(opt.savings for opt in optimizations)
            print(f"Total potential savings: ${total_savings:.2f}\n")
            
            for opt in optimizations[:10]:
                print(f"• {opt.capsule_name}: {opt.recommendation}")
                print(f"  Savings: ${opt.savings:.2f} ({opt.savings_percentage:.1%})")
                print(f"  Effort: {opt.implementation_effort}, Risk: {opt.risk_level}")
                print()
        else:
            print("No optimization opportunities found")
    
    elif args.command == "budget":
        if not all([args.capsule, args.category, args.limit]):
            print("Error: --capsule, --category, and --limit required")
            return
        
        optimizer.set_budget(args.capsule, CostCategory(args.category), args.limit)
        print(f"Set budget: {args.capsule}/{args.category} = ${args.limit:.2f}")
    
    elif args.command == "forecast":
        if not args.capsule:
            print("Error: --capsule required for forecast")
            return
        
        forecast = optimizer.get_cost_forecast(args.capsule, args.days)
        
        if forecast['forecast_available']:
            print(f"COST FORECAST for {args.capsule} ({args.days} days):")
            print(f"Current daily average: ${forecast['current_daily_average']:.2f}")
            print(f"Forecast daily average: ${forecast['forecast_daily_average']:.2f}")
            print(f"Forecast total: ${forecast['forecast_total']:.2f}")
            print(f"Trend: {forecast['trend_direction']}")
            print(f"Confidence: {forecast['confidence']:.1%}")
        else:
            print(f"Forecast not available: {forecast['reason']}")
    
    elif args.command == "report":
        report_path = optimizer.generate_cost_report(args.days)
        print(f"Cost report generated: {report_path}")


if __name__ == "__main__":
    main()