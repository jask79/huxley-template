"""
Njalla Integration for Huxley

Privacy-focused domain registrar API integration.

Usage:
    from global.integrations.njalla import NjallaClient

    client = NjallaClient()
    domains = client.list_domains()
"""

from .njalla_client import NjallaClient, NjallaError

__all__ = ['NjallaClient', 'NjallaError']
