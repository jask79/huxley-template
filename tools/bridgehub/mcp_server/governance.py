"""
BridgeHub Governance Module

Enforces guardrails and governance rules for LLM requests.
Integrates with global/governance/guardrails.yaml.
"""

import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum


class DataSensitivity(Enum):
    """Data classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    CONFIDENTIAL = "confidential"


class RiskLevel(Enum):
    """Request risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GovernanceDecision:
    """Result of governance validation"""
    allowed: bool
    risk_level: RiskLevel
    data_sensitivity: DataSensitivity
    allowed_providers: List[str]
    warnings: List[str]
    blocks: List[str]
    reason: Optional[str] = None


class GovernanceEngine:
    """Enforces governance rules on LLM requests"""

    def __init__(self, config_path: str, guardrails_path: str):
        self.config = self._load_config(config_path)
        self.guardrails = self._load_guardrails(guardrails_path)
        self.cost_tracking: Dict[str, Dict[str, float]] = {}

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load BridgeHub configuration"""
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def _load_guardrails(self, path: str) -> Dict[str, Any]:
        """Load global guardrails"""
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def validate_request(
        self,
        request: Dict[str, Any],
        agent_id: str,
        capsule_id: Optional[str] = None
    ) -> GovernanceDecision:
        """
        Validate LLM request against governance rules

        Args:
            request: LLM request payload
            agent_id: ID of requesting agent
            capsule_id: Optional capsule context

        Returns:
            GovernanceDecision with validation results
        """
        warnings = []
        blocks = []

        # 1. Classify data sensitivity
        sensitivity = self._classify_data_sensitivity(request)

        # 2. Determine risk level
        risk_level = self._assess_risk_level(request, sensitivity)

        # 3. Check provider restrictions
        allowed_providers = self._get_allowed_providers(sensitivity)

        # 4. Check cost limits
        cost_check = self._check_cost_limits(agent_id, capsule_id)
        if not cost_check['allowed']:
            blocks.append(cost_check['reason'])

        # 5. Validate against guardrails
        guardrail_check = self._validate_guardrails(request, risk_level)
        warnings.extend(guardrail_check['warnings'])
        blocks.extend(guardrail_check['blocks'])

        # 6. Check for secrets/PII
        secret_check = self._scan_for_secrets(request)
        if secret_check['found']:
            blocks.append(f"Detected potential secrets: {secret_check['types']}")

        # Make final decision
        allowed = len(blocks) == 0

        return GovernanceDecision(
            allowed=allowed,
            risk_level=risk_level,
            data_sensitivity=sensitivity,
            allowed_providers=allowed_providers,
            warnings=warnings,
            blocks=blocks,
            reason=blocks[0] if blocks else None
        )

    def _classify_data_sensitivity(self, request: Dict[str, Any]) -> DataSensitivity:
        """Classify data sensitivity level"""
        content = str(request.get('messages', []))

        # Check for sensitive patterns
        sensitive_patterns = [
            'password', 'api_key', 'secret', 'token',
            'ssn', 'credit_card', 'private_key',
            '.env', 'credentials'
        ]

        for pattern in sensitive_patterns:
            if pattern.lower() in content.lower():
                return DataSensitivity.CONFIDENTIAL

        # Check for PII
        pii_patterns = ['email', 'phone', 'address', 'name', 'dob']
        pii_count = sum(1 for p in pii_patterns if p in content.lower())

        if pii_count >= 3:
            return DataSensitivity.SENSITIVE

        # Check for internal data markers
        if '[PRIVATE]' in content or 'internal' in content.lower():
            return DataSensitivity.INTERNAL

        return DataSensitivity.PUBLIC

    def _assess_risk_level(
        self,
        request: Dict[str, Any],
        sensitivity: DataSensitivity
    ) -> RiskLevel:
        """Assess risk level of request"""

        # Base risk on sensitivity
        if sensitivity == DataSensitivity.CONFIDENTIAL:
            return RiskLevel.CRITICAL
        elif sensitivity == DataSensitivity.SENSITIVE:
            return RiskLevel.HIGH

        # Check token count (larger requests = higher risk)
        token_count = request.get('max_tokens', 0)
        if token_count > 10000:
            return RiskLevel.MEDIUM

        # Check for system prompts or instructions
        messages = request.get('messages', [])
        for msg in messages:
            content = str(msg.get('content', ''))
            if 'system' in msg.get('role', ''):
                return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def _get_allowed_providers(self, sensitivity: DataSensitivity) -> List[str]:
        """Get allowed providers for data sensitivity level"""
        sensitivity_rules = self.config['governance']['data_sensitivity']

        if sensitivity == DataSensitivity.CONFIDENTIAL:
            return sensitivity_rules.get('sensitive', ['claude'])
        elif sensitivity == DataSensitivity.SENSITIVE:
            return sensitivity_rules.get('sensitive', ['claude'])
        elif sensitivity == DataSensitivity.INTERNAL:
            return sensitivity_rules.get('internal', ['claude', 'gpt4', 'gemini'])
        else:
            return sensitivity_rules.get('public', list(self.config['providers'].keys()))

    def _check_cost_limits(
        self,
        agent_id: str,
        capsule_id: Optional[str]
    ) -> Dict[str, Any]:
        """Check if cost limits are exceeded"""
        limits = self.config['cost_limits']

        # Get current costs
        agent_cost = self._get_agent_cost(agent_id)
        capsule_cost = self._get_capsule_cost(capsule_id) if capsule_id else 0

        # Check agent limits
        if agent_cost >= limits['agent']['block']:
            return {
                'allowed': False,
                'reason': f"Agent cost limit exceeded: ${agent_cost:.2f} >= ${limits['agent']['block']:.2f}"
            }

        # Check capsule limits
        if capsule_id and capsule_cost >= limits['capsule']['block']:
            return {
                'allowed': False,
                'reason': f"Capsule cost limit exceeded: ${capsule_cost:.2f} >= ${limits['capsule']['block']:.2f}"
            }

        return {'allowed': True}

    def _validate_guardrails(
        self,
        request: Dict[str, Any],
        risk_level: RiskLevel
    ) -> Dict[str, Any]:
        """Validate against global guardrails"""
        warnings = []
        blocks = []

        # Check bypass permissions (from guardrails.yaml)
        bypass = self.guardrails.get('bypass_permissions', {})
        if bypass.get('enabled_by_default', False):
            # Consultation mode - provide warnings but don't block
            if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                warnings.append(f"High risk request ({risk_level.value}) - proceeding with consultation mode")
        else:
            # Approval mode - block high risk requests
            if risk_level == RiskLevel.CRITICAL:
                blocks.append("Critical risk requests require explicit approval")

        # Check privacy rules
        privacy_rules = self.guardrails.get('privacy_rules', {})
        if privacy_rules.get('secrets'):
            # Already handled in secret scanning
            pass

        return {'warnings': warnings, 'blocks': blocks}

    def _scan_for_secrets(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Scan request for potential secrets"""
        content = str(request.get('messages', []))

        secret_patterns = {
            'api_key': r'[A-Za-z0-9_-]{32,}',
            'password': r'password["\s:=]+[A-Za-z0-9!@#$%^&*]+',
            'token': r'[A-Za-z0-9-_]{20,}',
            'private_key': r'-----BEGIN.*PRIVATE KEY-----'
        }

        found_types = []
        for secret_type, pattern in secret_patterns.items():
            import re
            if re.search(pattern, content, re.IGNORECASE):
                found_types.append(secret_type)

        return {
            'found': len(found_types) > 0,
            'types': found_types
        }

    def _get_agent_cost(self, agent_id: str) -> float:
        """Get agent's hourly cost"""
        now = datetime.now()
        hour_key = now.strftime('%Y-%m-%d-%H')

        if agent_id not in self.cost_tracking:
            self.cost_tracking[agent_id] = {}

        return self.cost_tracking[agent_id].get(hour_key, 0.0)

    def _get_capsule_cost(self, capsule_id: str) -> float:
        """Get capsule's hourly cost"""
        now = datetime.now()
        hour_key = now.strftime('%Y-%m-%d-%H')

        capsule_key = f"capsule_{capsule_id}"
        if capsule_key not in self.cost_tracking:
            self.cost_tracking[capsule_key] = {}

        return self.cost_tracking[capsule_key].get(hour_key, 0.0)

    def record_cost(
        self,
        agent_id: str,
        cost: float,
        capsule_id: Optional[str] = None
    ):
        """Record cost for agent and capsule"""
        now = datetime.now()
        hour_key = now.strftime('%Y-%m-%d-%H')

        # Record agent cost
        if agent_id not in self.cost_tracking:
            self.cost_tracking[agent_id] = {}
        self.cost_tracking[agent_id][hour_key] = \
            self.cost_tracking[agent_id].get(hour_key, 0.0) + cost

        # Record capsule cost
        if capsule_id:
            capsule_key = f"capsule_{capsule_id}"
            if capsule_key not in self.cost_tracking:
                self.cost_tracking[capsule_key] = {}
            self.cost_tracking[capsule_key][hour_key] = \
                self.cost_tracking[capsule_key].get(hour_key, 0.0) + cost

    def get_cost_status(self, agent_id: str, capsule_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current cost status with warnings"""
        limits = self.config['cost_limits']

        agent_cost = self._get_agent_cost(agent_id)
        agent_limit = limits['agent']['block']
        agent_warning = limits['agent']['warning']

        result = {
            'agent': {
                'cost': agent_cost,
                'limit': agent_limit,
                'warning_threshold': agent_warning,
                'status': 'ok'
            }
        }

        if agent_cost >= agent_limit:
            result['agent']['status'] = 'blocked'
        elif agent_cost >= limits['agent']['critical']:
            result['agent']['status'] = 'critical'
        elif agent_cost >= agent_warning:
            result['agent']['status'] = 'warning'

        if capsule_id:
            capsule_cost = self._get_capsule_cost(capsule_id)
            capsule_limit = limits['capsule']['block']
            capsule_warning = limits['capsule']['warning']

            result['capsule'] = {
                'cost': capsule_cost,
                'limit': capsule_limit,
                'warning_threshold': capsule_warning,
                'status': 'ok'
            }

            if capsule_cost >= capsule_limit:
                result['capsule']['status'] = 'blocked'
            elif capsule_cost >= limits['capsule']['critical']:
                result['capsule']['status'] = 'critical'
            elif capsule_cost >= capsule_warning:
                result['capsule']['status'] = 'warning'

        return result
