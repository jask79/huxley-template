"""
BridgeHub Smart Router

Routes requests to optimal LLM provider based on:
- Task complexity
- Cost optimization
- Performance requirements
- Data sensitivity
- Rate limits
"""

import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"
    SPECIALIZED = "specialized"


@dataclass
class RoutingDecision:
    """Result of routing decision"""
    provider: str
    model: str
    reason: str
    fallback_providers: List[str]
    estimated_cost: float


class SmartRouter:
    """Routes LLM requests to optimal provider"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load BridgeHub configuration"""
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def route_request(
        self,
        request: Dict[str, Any],
        allowed_providers: List[str],
        optimization: str = 'cost_optimized'
    ) -> RoutingDecision:
        """
        Route request to optimal provider

        Args:
            request: LLM request payload
            allowed_providers: List of allowed providers (from governance)
            optimization: Routing strategy (cost_optimized, performance_optimized, latency_optimized)

        Returns:
            RoutingDecision with provider selection
        """
        # 1. Determine task complexity
        complexity = self._assess_complexity(request)

        # 2. Get candidate providers
        candidates = self._get_candidate_providers(complexity, allowed_providers)

        # 3. Select optimal provider
        selected = self._select_provider(
            candidates,
            request,
            optimization
        )

        # 4. Get fallback providers
        fallbacks = self._get_fallback_providers(
            selected,
            candidates,
            optimization
        )

        # 5. Estimate cost
        estimated_cost = self._estimate_cost(request, selected)

        return RoutingDecision(
            provider=selected,
            model=self._get_default_model(selected),
            reason=self._get_routing_reason(complexity, optimization),
            fallback_providers=fallbacks,
            estimated_cost=estimated_cost
        )

    def _assess_complexity(self, request: Dict[str, Any]) -> TaskComplexity:
        """Assess task complexity from request"""
        messages = request.get('messages', [])
        max_tokens = request.get('max_tokens', 2000)

        # Count total input tokens (rough estimate)
        total_chars = sum(len(str(m.get('content', ''))) for m in messages)
        estimated_input_tokens = total_chars // 4  # Rough estimate

        # Check for specialized tasks
        content = str(messages).lower()

        if 'code review' in content or 'architecture' in content:
            return TaskComplexity.SPECIALIZED

        if 'creative' in content or 'design' in content:
            return TaskComplexity.SPECIALIZED

        # Check token requirements
        if max_tokens > 10000 or estimated_input_tokens > 10000:
            return TaskComplexity.COMPLEX

        if max_tokens > 4000 or estimated_input_tokens > 4000:
            return TaskComplexity.STANDARD

        return TaskComplexity.SIMPLE

    def _get_candidate_providers(
        self,
        complexity: TaskComplexity,
        allowed_providers: List[str]
    ) -> List[str]:
        """Get candidate providers for complexity level"""
        routing_rules = self.config['routing']

        if complexity == TaskComplexity.SPECIALIZED:
            # Check for specialized routing
            content_lower = str(allowed_providers).lower()

            for task_type, providers in routing_rules['specialized'].items():
                if task_type in content_lower:
                    candidates = [p for p in providers if p in allowed_providers]
                    if candidates:
                        return candidates

            # Default to complex task providers
            candidates = routing_rules['complex_tasks']['providers']

        elif complexity == TaskComplexity.COMPLEX:
            candidates = routing_rules['complex_tasks']['providers']

        elif complexity == TaskComplexity.STANDARD:
            candidates = routing_rules['standard_tasks']['providers']

        else:  # SIMPLE
            candidates = routing_rules['simple_tasks']['providers']

        # Filter by allowed providers
        return [p for p in candidates if p in allowed_providers]

    def _select_provider(
        self,
        candidates: List[str],
        request: Dict[str, Any],
        optimization: str
    ) -> str:
        """Select optimal provider from candidates"""
        if not candidates:
            # Fallback to any allowed provider
            return 'claude'  # Safe default

        # Get optimization strategy
        fallback_config = self.config['fallback']
        strategy = fallback_config.get(optimization, fallback_config['cost_optimized'])

        # Order candidates by strategy
        ordered = []
        for provider in strategy['order']:
            if provider in candidates:
                ordered.append(provider)

        # Add remaining candidates
        for provider in candidates:
            if provider not in ordered:
                ordered.append(provider)

        return ordered[0] if ordered else candidates[0]

    def _get_fallback_providers(
        self,
        selected: str,
        candidates: List[str],
        optimization: str
    ) -> List[str]:
        """Get ordered list of fallback providers"""
        fallback_config = self.config['fallback']
        strategy = fallback_config.get(optimization, fallback_config['cost_optimized'])

        fallbacks = []
        for provider in strategy['order']:
            if provider in candidates and provider != selected:
                fallbacks.append(provider)

        return fallbacks[:3]  # Top 3 fallbacks

    def _estimate_cost(self, request: Dict[str, Any], provider: str) -> float:
        """Estimate request cost"""
        # Get provider costs
        provider_config = self.config['providers'][provider]
        cost_rates = provider_config['cost_per_1k_tokens']

        # Estimate input tokens
        messages = request.get('messages', [])
        total_chars = sum(len(str(m.get('content', ''))) for m in messages)
        estimated_input_tokens = total_chars // 4

        # Estimate output tokens
        max_tokens = request.get('max_tokens', 2000)

        # Calculate cost
        input_cost = (estimated_input_tokens / 1000) * cost_rates['input']
        output_cost = (max_tokens / 1000) * cost_rates['output']

        return input_cost + output_cost

    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider"""
        provider_config = self.config['providers'][provider]
        models = provider_config['models']
        return models[0] if models else 'default'

    def _get_routing_reason(
        self,
        complexity: TaskComplexity,
        optimization: str
    ) -> str:
        """Generate human-readable routing reason"""
        reasons = {
            TaskComplexity.SIMPLE: f"Simple task routed for {optimization.replace('_', ' ')}",
            TaskComplexity.STANDARD: f"Standard task routed for {optimization.replace('_', ' ')}",
            TaskComplexity.COMPLEX: f"Complex task requiring advanced reasoning",
            TaskComplexity.SPECIALIZED: "Specialized task requiring premium model"
        }
        return reasons.get(complexity, "Default routing")

    def get_provider_status(self, provider: str) -> Dict[str, Any]:
        """Get provider status and availability"""
        provider_config = self.config['providers'].get(provider)

        if not provider_config:
            return {
                'available': False,
                'reason': 'Provider not configured'
            }

        return {
            'available': True,
            'service': provider_config['service'],
            'models': provider_config['models'],
            'region': provider_config['region'],
            'cost_per_1k': provider_config['cost_per_1k_tokens']
        }

    def suggest_optimization(
        self,
        usage_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze usage and suggest optimizations

        Args:
            usage_history: List of recent usage records

        Returns:
            Optimization suggestions
        """
        if not usage_history:
            return {'suggestions': []}

        # Analyze usage patterns
        total_cost = sum(r.get('cost_total', 0) for r in usage_history)
        total_requests = len(usage_history)

        # Provider distribution
        provider_counts = {}
        provider_costs = {}

        for record in usage_history:
            provider = record.get('provider')
            cost = record.get('cost_total', 0)

            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            provider_costs[provider] = provider_costs.get(provider, 0.0) + cost

        suggestions = []

        # Check for cost optimization opportunities
        avg_cost = total_cost / total_requests if total_requests > 0 else 0

        if avg_cost > 0.02:  # $0.02 per request
            suggestions.append({
                'type': 'cost_optimization',
                'message': f"Average cost per request is ${avg_cost:.4f}. Consider using cheaper providers for simple tasks.",
                'recommendation': "Switch to llama-fast or gemini for routine tasks"
            })

        # Check for overuse of expensive providers
        expensive_providers = ['claude', 'gpt4']
        expensive_usage = sum(
            provider_counts.get(p, 0)
            for p in expensive_providers
        )

        if expensive_usage / total_requests > 0.7:  # >70% expensive
            suggestions.append({
                'type': 'provider_distribution',
                'message': f"{(expensive_usage/total_requests)*100:.1f}% of requests use premium providers",
                'recommendation': "Route more simple tasks to cost-effective providers"
            })

        # Check for rate limit issues (if errors present)
        error_count = sum(1 for r in usage_history if not r.get('success', True))
        if error_count / total_requests > 0.1:  # >10% errors
            suggestions.append({
                'type': 'reliability',
                'message': f"{(error_count/total_requests)*100:.1f}% error rate detected",
                'recommendation': "Consider adding more fallback providers"
            })

        return {
            'analysis': {
                'total_requests': total_requests,
                'total_cost': f"${total_cost:.4f}",
                'avg_cost': f"${avg_cost:.4f}",
                'provider_distribution': provider_counts,
                'error_rate': f"{(error_count/total_requests)*100:.1f}%"
            },
            'suggestions': suggestions
        }
