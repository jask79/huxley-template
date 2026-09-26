"""
BridgeHub Cost & Usage Tracker

Tracks token usage and costs to Huxley Memory.
Logs all requests for audit trail.
"""

import json
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class UsageRecord:
    """Record of LLM usage"""
    timestamp: str
    agent_id: str
    capsule_id: Optional[str]
    provider: str
    model: str
    tokens_input: int
    tokens_output: int
    tokens_total: int
    cost_input: float
    cost_output: float
    cost_total: float
    latency_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class AggregatedMetrics:
    """Aggregated usage metrics"""
    total_requests: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    success_rate: float
    by_provider: Dict[str, Dict[str, float]]
    by_agent: Dict[str, Dict[str, float]]
    by_capsule: Dict[str, Dict[str, float]]


class UsageTracker:
    """Tracks LLM usage and costs"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.memory_path = Path(self.config['tracking']['builder_memory_path'])
        self.registry_path = Path(self.config['tracking']['registry_path'])

        # Ensure directories exist
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self.registry_path.mkdir(parents=True, exist_ok=True)

        # Initialize tracking files
        self.usage_log_path = self.memory_path / 'usage_log.jsonl'
        self.metrics_path = self.memory_path / 'metrics.json'

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load BridgeHub configuration"""
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def record_usage(
        self,
        agent_id: str,
        provider: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        latency_ms: float,
        success: bool,
        capsule_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> UsageRecord:
        """
        Record LLM usage

        Args:
            agent_id: ID of requesting agent
            provider: Provider name (claude, gpt4, etc.)
            model: Model name
            tokens_input: Input tokens used
            tokens_output: Output tokens generated
            latency_ms: Request latency in milliseconds
            success: Whether request succeeded
            capsule_id: Optional capsule context
            error: Optional error message

        Returns:
            UsageRecord with cost calculations
        """
        # Calculate costs
        provider_config = self.config['providers'][provider]
        cost_rates = provider_config['cost_per_1k_tokens']

        cost_input = (tokens_input / 1000) * cost_rates['input']
        cost_output = (tokens_output / 1000) * cost_rates['output']
        cost_total = cost_input + cost_output

        # Create usage record
        record = UsageRecord(
            timestamp=datetime.utcnow().isoformat(),
            agent_id=agent_id,
            capsule_id=capsule_id,
            provider=provider,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_input + tokens_output,
            cost_input=cost_input,
            cost_output=cost_output,
            cost_total=cost_total,
            latency_ms=latency_ms,
            success=success,
            error=error
        )

        # Write to log
        self._append_to_log(record)

        # Update metrics
        self._update_metrics(record)

        # Write to Huxley Memory format
        self._write_to_builder_memory(record)

        return record

    def _append_to_log(self, record: UsageRecord):
        """Append usage record to JSONL log"""
        with open(self.usage_log_path, 'a') as f:
            f.write(json.dumps(asdict(record)) + '\n')

    def _update_metrics(self, record: UsageRecord):
        """Update aggregated metrics"""
        # Load existing metrics
        metrics = self._load_metrics()

        # Update totals
        metrics['total_requests'] += 1
        metrics['total_tokens'] += record.tokens_total
        metrics['total_cost'] += record.cost_total

        # Update latency (running average)
        n = metrics['total_requests']
        metrics['avg_latency_ms'] = (
            (metrics['avg_latency_ms'] * (n - 1) + record.latency_ms) / n
        )

        # Update success rate
        if 'success_count' not in metrics:
            metrics['success_count'] = 0
        if record.success:
            metrics['success_count'] += 1
        metrics['success_rate'] = metrics['success_count'] / metrics['total_requests']

        # Update by provider
        if 'by_provider' not in metrics:
            metrics['by_provider'] = {}
        if record.provider not in metrics['by_provider']:
            metrics['by_provider'][record.provider] = {
                'requests': 0,
                'tokens': 0,
                'cost': 0.0
            }
        metrics['by_provider'][record.provider]['requests'] += 1
        metrics['by_provider'][record.provider]['tokens'] += record.tokens_total
        metrics['by_provider'][record.provider]['cost'] += record.cost_total

        # Update by agent
        if 'by_agent' not in metrics:
            metrics['by_agent'] = {}
        if record.agent_id not in metrics['by_agent']:
            metrics['by_agent'][record.agent_id] = {
                'requests': 0,
                'tokens': 0,
                'cost': 0.0
            }
        metrics['by_agent'][record.agent_id]['requests'] += 1
        metrics['by_agent'][record.agent_id]['tokens'] += record.tokens_total
        metrics['by_agent'][record.agent_id]['cost'] += record.cost_total

        # Update by capsule
        if record.capsule_id:
            if 'by_capsule' not in metrics:
                metrics['by_capsule'] = {}
            if record.capsule_id not in metrics['by_capsule']:
                metrics['by_capsule'][record.capsule_id] = {
                    'requests': 0,
                    'tokens': 0,
                    'cost': 0.0
                }
            metrics['by_capsule'][record.capsule_id]['requests'] += 1
            metrics['by_capsule'][record.capsule_id]['tokens'] += record.tokens_total
            metrics['by_capsule'][record.capsule_id]['cost'] += record.cost_total

        # Save metrics
        self._save_metrics(metrics)

    def _load_metrics(self) -> Dict[str, Any]:
        """Load metrics from file"""
        if not self.metrics_path.exists():
            return {
                'total_requests': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
                'avg_latency_ms': 0.0,
                'success_rate': 0.0,
                'success_count': 0,
                'by_provider': {},
                'by_agent': {},
                'by_capsule': {}
            }

        with open(self.metrics_path, 'r') as f:
            return json.load(f)

    def _save_metrics(self, metrics: Dict[str, Any]):
        """Save metrics to file"""
        with open(self.metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)

    def _write_to_builder_memory(self, record: UsageRecord):
        """Write usage record to Huxley Memory format"""
        # Create daily log file
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        daily_log_path = self.memory_path / f'usage_{date_str}.jsonl'

        with open(daily_log_path, 'a') as f:
            f.write(json.dumps(asdict(record)) + '\n')

        # Create agent-specific log
        agent_log_path = self.memory_path / f'agent_{record.agent_id}_{date_str}.jsonl'
        with open(agent_log_path, 'a') as f:
            f.write(json.dumps(asdict(record)) + '\n')

        # Create capsule-specific log if applicable
        if record.capsule_id:
            capsule_log_path = self.memory_path / f'capsule_{record.capsule_id}_{date_str}.jsonl'
            with open(capsule_log_path, 'a') as f:
                f.write(json.dumps(asdict(record)) + '\n')

    def get_metrics(
        self,
        agent_id: Optional[str] = None,
        capsule_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get usage metrics

        Args:
            agent_id: Filter by agent
            capsule_id: Filter by capsule
            provider: Filter by provider

        Returns:
            Filtered metrics
        """
        metrics = self._load_metrics()

        if agent_id:
            return {
                'agent_id': agent_id,
                'metrics': metrics['by_agent'].get(agent_id, {
                    'requests': 0,
                    'tokens': 0,
                    'cost': 0.0
                })
            }

        if capsule_id:
            return {
                'capsule_id': capsule_id,
                'metrics': metrics['by_capsule'].get(capsule_id, {
                    'requests': 0,
                    'tokens': 0,
                    'cost': 0.0
                })
            }

        if provider:
            return {
                'provider': provider,
                'metrics': metrics['by_provider'].get(provider, {
                    'requests': 0,
                    'tokens': 0,
                    'cost': 0.0
                })
            }

        return metrics

    def get_hourly_costs(self, agent_id: str, hours: int = 1) -> float:
        """Get agent's cost over last N hours"""
        cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)

        total_cost = 0.0

        # Read from usage log
        if self.usage_log_path.exists():
            with open(self.usage_log_path, 'r') as f:
                for line in f:
                    record = json.loads(line)
                    if record['agent_id'] != agent_id:
                        continue

                    record_time = datetime.fromisoformat(record['timestamp']).timestamp()
                    if record_time >= cutoff_time:
                        total_cost += record['cost_total']

        return total_cost

    def generate_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate usage report for date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Comprehensive usage report
        """
        metrics = self._load_metrics()

        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'period': {
                'start': start_date or 'inception',
                'end': end_date or 'now'
            },
            'summary': {
                'total_requests': metrics['total_requests'],
                'total_tokens': metrics['total_tokens'],
                'total_cost': f"${metrics['total_cost']:.4f}",
                'avg_latency_ms': f"{metrics['avg_latency_ms']:.2f}",
                'success_rate': f"{metrics['success_rate'] * 100:.2f}%"
            },
            'by_provider': metrics['by_provider'],
            'by_agent': metrics['by_agent'],
            'by_capsule': metrics['by_capsule']
        }

        return report
