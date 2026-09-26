"""
Rate Limiter for the Media Workflow Engine.

Production-ready rate limiter with persistent state and auto-fallback.
Tracks request counts per provider with daily reset windows. State is
persisted to a JSON file so limits survive across CLI invocations.

Auto-fallback: when a provider's quota is exceeded, the limiter can
suggest the next auth method in a configurable fallback chain
(e.g., subscription -> openrouter -> api_key).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Default daily limits per auth type
DEFAULT_LIMITS: dict[str, int] = {
    "subscription": 100,
    "api_key": 1000,
    "openrouter": 500,
    "gemini_direct": 200,
    "gemini_oauth": 1000,
}

# Warning threshold (percentage of limit)
WARNING_THRESHOLD = 0.8

# Default fallback chain: try these auth types in order
DEFAULT_FALLBACK_CHAIN: list[str] = ["subscription", "gemini_oauth", "gemini_direct", "openrouter", "api_key"]

# Persistent state file location
ENGINE_ROOT = Path("{{CATALYST_ROOT}}/tools/media-engine")
DEFAULT_STATE_PATH = ENGINE_ROOT / "eval" / "rate-limiter-state.json"


@dataclass
class ProviderState:
    """Tracks request count and reset time for a single provider."""
    count: int = 0
    reset_at: float = 0.0  # Unix timestamp for next reset
    limit: int = 500


class RateLimiter:
    """
    Persistent rate limiter for media generation providers.

    Tracks per-provider request counts with daily reset windows.
    Logs warnings when approaching limits. State is persisted to
    a JSON file so limits survive across CLI invocations.

    Supports auto-fallback: when a provider's quota is exceeded,
    the limiter suggests the next auth method in the fallback chain.

    Not thread-safe. For multi-process scenarios, use a persistent
    backing store with locking (future enhancement).
    """

    def __init__(
        self,
        limits: dict[str, int] | None = None,
        state_path: str | Path | None = None,
        fallback_chain: list[str] | None = None,
    ) -> None:
        """
        Args:
            limits: Optional dict mapping auth_type -> daily_limit.
                    Falls back to DEFAULT_LIMITS for unspecified types.
            state_path: Path to the persistent state JSON file.
                        Defaults to eval/rate-limiter-state.json.
            fallback_chain: Ordered list of auth types to try when
                            the primary is rate-limited. Defaults to
                            ["subscription", "openrouter", "api_key"].
        """
        self._custom_limits = limits or {}
        self._providers: dict[str, ProviderState] = {}
        self._state_path = Path(state_path) if state_path else DEFAULT_STATE_PATH
        self._fallback_chain = fallback_chain or list(DEFAULT_FALLBACK_CHAIN)

        # Load persisted state on init
        self._load_state()

    def can_proceed(self, provider: str, auth_type: str = "openrouter") -> bool:
        """
        Check whether a request to this provider is allowed.

        Args:
            provider: Provider identifier (e.g., "openrouter", "openai").
            auth_type: The auth type from config ("subscription", "api_key", "openrouter").

        Returns:
            True if the request is allowed, False if rate limit is exceeded.
        """
        state = self._get_or_create(provider, auth_type)
        self._maybe_reset(state)

        if state.count >= state.limit:
            print(
                f"Rate limit exceeded for '{provider}' "
                f"({state.count}/{state.limit} requests today). "
                f"Resets at {time.strftime('%H:%M:%S', time.localtime(state.reset_at))}."
            )
            return False

        # Warn when approaching limit
        usage_ratio = state.count / state.limit if state.limit > 0 else 1.0
        if usage_ratio >= WARNING_THRESHOLD:
            remaining = state.limit - state.count
            print(
                f"Warning: '{provider}' approaching rate limit "
                f"({state.count}/{state.limit}, {remaining} remaining)."
            )

        return True

    def record_request(self, provider: str, auth_type: str = "openrouter") -> None:
        """
        Record that a request was made to a provider.

        Increments the counter and persists state to disk.

        Args:
            provider: Provider identifier.
            auth_type: The auth type from config.
        """
        state = self._get_or_create(provider, auth_type)
        self._maybe_reset(state)
        state.count += 1
        self._save_state()

    def get_fallback_auth(self, current_auth: str) -> str | None:
        """
        Get the next auth type in the fallback chain.

        When the current auth type is rate-limited, this returns the
        next auth type to try. Returns None if all fallback options
        are exhausted.

        Args:
            current_auth: The current auth type that is rate-limited.

        Returns:
            The next auth type to try, or None if no fallbacks remain.
        """
        try:
            idx = self._fallback_chain.index(current_auth)
        except ValueError:
            # Current auth not in fallback chain, return the first one
            return self._fallback_chain[0] if self._fallback_chain else None

        next_idx = idx + 1
        if next_idx < len(self._fallback_chain):
            next_auth = self._fallback_chain[next_idx]
            print(
                f"Auto-fallback: '{current_auth}' rate-limited, "
                f"trying '{next_auth}'"
            )
            return next_auth

        return None

    def can_proceed_with_fallback(
        self, provider: str, auth_type: str = "openrouter"
    ) -> tuple[bool, str]:
        """
        Check if a request can proceed, trying fallback auth types.

        Walks the fallback chain until it finds an auth type with
        remaining quota, or exhausts all options.

        Args:
            provider: Provider identifier.
            auth_type: Starting auth type from config.

        Returns:
            Tuple of (can_proceed: bool, effective_auth_type: str).
            The effective_auth_type may differ from the input if
            fallback was needed.
        """
        current_auth = auth_type

        while current_auth is not None:
            if self.can_proceed(provider, current_auth):
                return True, current_auth

            current_auth = self.get_fallback_auth(current_auth)

        return False, auth_type

    def get_usage(self, provider: str) -> dict[str, Any]:
        """
        Get current usage stats for a provider.

        Returns dict with count, limit, remaining, and reset_at.
        """
        if provider not in self._providers:
            return {"count": 0, "limit": 0, "remaining": 0, "reset_at": 0}

        state = self._providers[provider]
        self._maybe_reset(state)

        return {
            "count": state.count,
            "limit": state.limit,
            "remaining": max(0, state.limit - state.count),
            "reset_at": state.reset_at,
        }

    def get_all_usage(self) -> dict[str, dict[str, Any]]:
        """Get usage stats for all tracked providers."""
        return {provider: self.get_usage(provider) for provider in self._providers}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """
        Load persisted rate limiter state from the JSON file.

        If the file doesn't exist or is corrupted, starts with
        empty state (no providers tracked).
        """
        if not self._state_path.exists():
            return

        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Corrupted state file -- start fresh
            return

        if not isinstance(data, dict):
            return

        providers = data.get("providers", {})
        for name, state_data in providers.items():
            if not isinstance(state_data, dict):
                continue

            self._providers[name] = ProviderState(
                count=state_data.get("count", 0),
                reset_at=state_data.get("reset_at", 0.0),
                limit=state_data.get("limit", 500),
            )

    def _save_state(self) -> None:
        """
        Persist rate limiter state to the JSON file.

        Writes atomically by writing to a temp file first, then
        renaming. Non-critical -- failures are logged but don't
        raise exceptions.
        """
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "saved_at": time.time(),
            "providers": {},
        }

        for name, state in self._providers.items():
            data["providers"][name] = {
                "count": state.count,
                "reset_at": state.reset_at,
                "limit": state.limit,
            }

        tmp_path = self._state_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(str(tmp_path), str(self._state_path))
        except OSError as exc:
            print(f"Warning: Could not persist rate limiter state: {exc}")
            # Clean up temp file if it exists
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_or_create(self, provider: str, auth_type: str) -> ProviderState:
        """Get or create a ProviderState for the given provider."""
        if provider not in self._providers:
            limit = self._custom_limits.get(
                auth_type, DEFAULT_LIMITS.get(auth_type, 500)
            )
            self._providers[provider] = ProviderState(
                count=0,
                reset_at=self._next_reset_time(),
                limit=limit,
            )
        return self._providers[provider]

    @staticmethod
    def _maybe_reset(state: ProviderState) -> None:
        """Reset the counter if the reset window has passed."""
        now = time.time()
        if now >= state.reset_at:
            state.count = 0
            state.reset_at = RateLimiter._next_reset_time()

    @staticmethod
    def _next_reset_time() -> float:
        """Calculate the next daily reset timestamp (midnight local time)."""
        now = time.time()
        local = time.localtime(now)
        # Seconds until midnight
        seconds_today = local.tm_hour * 3600 + local.tm_min * 60 + local.tm_sec
        seconds_until_midnight = 86400 - seconds_today
        return now + seconds_until_midnight
