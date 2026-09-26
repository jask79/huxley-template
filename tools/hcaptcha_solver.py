#!/usr/bin/env python3
"""
hCaptcha Solver for Bowser Agent
================================

Integrates hcaptcha-challenger library with Playwright for automated hCaptcha solving.
Uses Google Gemini multimodal LLM for image understanding and challenge completion.

Requirements:
- hcaptcha-challenger package (pip install hcaptcha-challenger)
- Google Gemini API key (set GEMINI_API_KEY env var or pass directly)
- Playwright browser instance

Usage:
    from tools.hcaptcha_solver import HCaptchaSolver, solve_hcaptcha

    # Quick solve (async)
    result = await solve_hcaptcha(page)

    # With custom config
    solver = HCaptchaSolver(api_key="your-gemini-key")
    result = await solver.solve(page)

Author: Huxley
License: MIT
"""

from __future__ import annotations

import asyncio
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Literal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Try to import hcaptcha-challenger
try:
    from hcaptcha_challenger import AgentV, AgentConfig
    from hcaptcha_challenger.models import ChallengeSignal
    HCAPTCHA_CHALLENGER_AVAILABLE = True
except ImportError:
    HCAPTCHA_CHALLENGER_AVAILABLE = False
    logger.warning(
        "hcaptcha-challenger not installed. Install with: pip install hcaptcha-challenger"
    )

# Try to import Playwright
try:
    from playwright.async_api import Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Default cache directory for hcaptcha-challenger
DEFAULT_CACHE_DIR = Path("{{CATALYST_ROOT}}/.cache/hcaptcha")


@dataclass
class HCaptchaResult:
    """Result of hCaptcha solving attempt."""

    success: bool
    challenge_type: Optional[str] = None
    solve_time_ms: int = 0
    error_message: Optional[str] = None
    attempts: int = 1
    screenshots: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.success


@dataclass
class SolverConfig:
    """Configuration for hCaptcha solver."""

    # Gemini API key (required)
    gemini_api_key: Optional[str] = None

    # Model selection (use flash for speed, pro for accuracy)
    classifier_model: Literal["gemini-2.5-flash", "gemini-2.5-flash-lite"] = "gemini-2.5-flash"
    image_model: Literal["gemini-2.5-flash", "gemini-2.5-pro"] = "gemini-2.5-flash"

    # Timeouts
    execution_timeout: float = 120.0  # Max time for entire solve
    response_timeout: float = 30.0    # Max time waiting for response

    # Behavior
    retry_on_failure: bool = True
    max_attempts: int = 3

    # Cache directory for models/data
    cache_dir: Path = DEFAULT_CACHE_DIR

    # Debug mode
    debug: bool = False


class HCaptchaSolver:
    """
    Automated hCaptcha solver using Google Gemini multimodal LLM.

    Supports multiple challenge types:
    - Image label binary (click all matching images)
    - Image label area select (click specific area)
    - Image drag and drop
    - Image label single/multi select
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[SolverConfig] = None
    ):
        """
        Initialize hCaptcha solver.

        Args:
            api_key: Google Gemini API key. If not provided, reads from:
                     1. GEMINI_API_KEY env var
                     2. GOOGLE_API_KEY env var
            config: Optional SolverConfig for advanced settings
        """
        if not HCAPTCHA_CHALLENGER_AVAILABLE:
            raise ImportError(
                "hcaptcha-challenger is not installed. "
                "Install with: pip install hcaptcha-challenger"
            )

        self.config = config or SolverConfig()

        # Resolve API key
        self.api_key = api_key or self.config.gemini_api_key
        if not self.api_key:
            self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Ensure cache directory exists
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"HCaptchaSolver initialized (cache: {self.config.cache_dir})")

    def _create_agent_config(self) -> AgentConfig:
        """Create AgentConfig from SolverConfig."""
        return AgentConfig(
            GEMINI_API_KEY=self.api_key,
            cache_dir=self.config.cache_dir,
            challenge_dir=self.config.cache_dir / "challenges",
            captcha_response_dir=self.config.cache_dir / "responses",
            EXECUTION_TIMEOUT=self.config.execution_timeout,
            RESPONSE_TIMEOUT=self.config.response_timeout,
            RETRY_ON_FAILURE=self.config.retry_on_failure,
            CHALLENGE_CLASSIFIER_MODEL=self.config.classifier_model,
            IMAGE_CLASSIFIER_MODEL=self.config.image_model,
            SPATIAL_POINT_REASONER_MODEL=self.config.image_model,
            SPATIAL_PATH_REASONER_MODEL=self.config.image_model,
            enable_challenger_debug=self.config.debug,
        )

    async def solve(self, page: Page) -> HCaptchaResult:
        """
        Solve hCaptcha challenge on the given page.

        Args:
            page: Playwright Page with hCaptcha challenge

        Returns:
            HCaptchaResult with success status and details
        """
        import time
        start_time = time.time()

        result = HCaptchaResult(success=False)

        for attempt in range(1, self.config.max_attempts + 1):
            result.attempts = attempt

            try:
                logger.info(f"🔐 hCaptcha solve attempt {attempt}/{self.config.max_attempts}")

                # Create agent with config
                agent_config = self._create_agent_config()
                agent = AgentV(page=page, agent_config=agent_config)

                # Wait for and solve challenge
                challenge_signal: ChallengeSignal = await agent.wait_for_challenge()

                # Check result
                if challenge_signal and hasattr(challenge_signal, 'is_pass'):
                    if challenge_signal.is_pass:
                        result.success = True
                        result.challenge_type = getattr(challenge_signal, 'challenge_type', 'unknown')
                        logger.info(f"✅ hCaptcha solved successfully (type: {result.challenge_type})")
                        break
                    else:
                        logger.warning(f"⚠️ Challenge not passed on attempt {attempt}")
                        result.error_message = "Challenge verification failed"
                else:
                    # Assume success if no explicit failure
                    result.success = True
                    logger.info("✅ hCaptcha challenge completed")
                    break

            except asyncio.TimeoutError:
                result.error_message = f"Timeout on attempt {attempt}"
                logger.warning(f"⏱️ Timeout on attempt {attempt}")

            except Exception as e:
                result.error_message = str(e)
                logger.error(f"❌ Error on attempt {attempt}: {e}")

                if "api_key" in str(e).lower() or "authentication" in str(e).lower():
                    # Don't retry on auth errors
                    logger.error("API key error - not retrying")
                    break

        result.solve_time_ms = int((time.time() - start_time) * 1000)
        return result

    async def detect_hcaptcha(self, page: Page) -> bool:
        """
        Check if hCaptcha is present on the page.

        Args:
            page: Playwright Page to check

        Returns:
            True if hCaptcha detected
        """
        hcaptcha_selectors = [
            'iframe[src*="hcaptcha.com"]',
            'iframe[data-hcaptcha-widget-id]',
            '.h-captcha',
            '#hcaptcha',
            '[data-sitekey]',
        ]

        for selector in hcaptcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    logger.info(f"🔍 hCaptcha detected: {selector}")
                    return True
            except Exception:
                continue

        return False


async def solve_hcaptcha(
    page: Page,
    api_key: Optional[str] = None,
    timeout: float = 120.0
) -> HCaptchaResult:
    """
    Convenience function to solve hCaptcha on a page.

    Args:
        page: Playwright Page with hCaptcha challenge
        api_key: Optional Gemini API key (uses env var if not provided)
        timeout: Max solve time in seconds

    Returns:
        HCaptchaResult with success status
    """
    config = SolverConfig(
        gemini_api_key=api_key,
        execution_timeout=timeout,
    )
    solver = HCaptchaSolver(config=config)
    return await solver.solve(page)


async def detect_and_solve_hcaptcha(
    page: Page,
    api_key: Optional[str] = None
) -> Optional[HCaptchaResult]:
    """
    Detect hCaptcha and solve if present.

    Args:
        page: Playwright Page to check
        api_key: Optional Gemini API key

    Returns:
        HCaptchaResult if hCaptcha was found and solved, None if no hCaptcha
    """
    try:
        solver = HCaptchaSolver(api_key=api_key)

        if await solver.detect_hcaptcha(page):
            return await solver.solve(page)
        else:
            logger.info("No hCaptcha detected on page")
            return None

    except ValueError as e:
        # API key not configured
        logger.warning(f"Cannot solve hCaptcha: {e}")
        return HCaptchaResult(
            success=False,
            error_message=str(e)
        )


# CLI interface
if __name__ == "__main__":
    import sys

    print("hCaptcha Solver for Bowser Agent")
    print("=" * 50)
    print(f"hcaptcha-challenger available: {HCAPTCHA_CHALLENGER_AVAILABLE}")
    print(f"Playwright available: {PLAYWRIGHT_AVAILABLE}")

    # Check for API key
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        print(f"Gemini API key: configured ({len(api_key)} chars)")
    else:
        print("Gemini API key: NOT CONFIGURED")
        print("\nTo configure, set GEMINI_API_KEY environment variable")

    print()
    print("Usage:")
    print("  from tools.hcaptcha_solver import solve_hcaptcha")
    print("  result = await solve_hcaptcha(page)")
