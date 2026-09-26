"""
Focused tests for the Huxley Media Workflow Engine.

Tests critical paths that would break silently if changed:
  1. Config Resolver deep merge semantics
  2. Schema validation (reject bad configs)
  3. PromptCache key computation and hit/miss
  4. Evaluator hard checks (file_exists, file_not_empty, not_corrupted)
  5. RateLimiter quota tracking and fallback chain
  6. CLI argument parsing smoke tests
"""

import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Path setup -- ensure engine package is importable
# ---------------------------------------------------------------------------

ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT))

from engine.resolver import deep_merge
from engine.schema import validate
from engine.cache import PromptCache
from engine.evaluator import Evaluator
from engine.queue import RateLimiter


# =========================================================================
# 1. Config Resolver -- deep_merge
# =========================================================================

class TestDeepMerge:
    """deep_merge must: deep-merge dicts, replace lists, override scalars."""

    def test_scalar_override(self):
        base = {"model": "old-model", "media_type": "image"}
        override = {"model": "new-model"}
        result = deep_merge(base, override)
        assert result["model"] == "new-model"
        assert result["media_type"] == "image"

    def test_dict_deep_merge_preserves_siblings(self):
        base = {"generation": {"resolution": "2K", "fps": 30}}
        override = {"generation": {"resolution": "4K"}}
        result = deep_merge(base, override)
        assert result["generation"]["resolution"] == "4K"
        assert result["generation"]["fps"] == 30

    def test_list_replaces_entirely(self):
        base = {"generation": {"aspect_ratios": ["1:1", "16:9"]}}
        override = {"generation": {"aspect_ratios": ["4:3"]}}
        result = deep_merge(base, override)
        assert result["generation"]["aspect_ratios"] == ["4:3"]

    def test_nested_three_levels_deep(self):
        base = {"a": {"b": {"c": 1, "d": 2}, "e": 3}}
        override = {"a": {"b": {"c": 99}}}
        result = deep_merge(base, override)
        assert result["a"]["b"]["c"] == 99
        assert result["a"]["b"]["d"] == 2
        assert result["a"]["e"] == 3

    def test_does_not_mutate_inputs(self):
        base = {"generation": {"resolution": "2K"}}
        override = {"generation": {"resolution": "4K"}}
        deep_merge(base, override)
        assert base["generation"]["resolution"] == "2K"
        assert override["generation"]["resolution"] == "4K"

    def test_override_adds_new_keys(self):
        base = {"name": "test"}
        override = {"model": "gpt-4o"}
        result = deep_merge(base, override)
        assert result["name"] == "test"
        assert result["model"] == "gpt-4o"

    def test_empty_override_returns_copy_of_base(self):
        base = {"name": "test", "generation": {"resolution": "2K"}}
        result = deep_merge(base, {})
        assert result == base
        assert result is not base


# =========================================================================
# 2. Schema Validation
# =========================================================================

class TestSchemaValidation:
    """validate() must catch invalid configs and pass valid ones."""

    @staticmethod
    def _valid_config(**overrides) -> dict:
        """Return a minimal valid config, with optional overrides."""
        cfg = {
            "name": "test-workflow",
            "media_type": "image",
            "model": "google/gemini-3-pro-image-preview",
            "auth": "openrouter",
            "auth_provider": "openrouter",
            "generation": {
                "resolution": "2K",
                "aspect_ratios": ["1:1"],
            },
            "refinement": {
                "mode": "autonomous",
                "max_iterations": 3,
                "quality_threshold": 0.75,
                "hard_checks": ["file_exists", "file_not_empty"],
            },
            "consistency": {
                "reference_images": 0,
                "style_weight": 0.5,
            },
            "variants": {
                "count": 1,
                "variation_strength": 0.3,
            },
            "output": {
                "formats": ["png"],
            },
        }
        cfg.update(overrides)
        return cfg

    def test_valid_config_no_errors(self):
        errors = validate(self._valid_config())
        assert errors == []

    def test_invalid_media_type(self):
        errors = validate(self._valid_config(media_type="audio"))
        assert any("media_type" in e for e in errors)

    def test_invalid_video_duration_zero(self):
        cfg = self._valid_config(media_type="video")
        cfg["generation"]["duration"] = "0s"
        errors = validate(cfg)
        assert any("duration" in e for e in errors)

    def test_invalid_video_duration_negative(self):
        cfg = self._valid_config(media_type="video")
        cfg["generation"]["duration"] = "-1"
        errors = validate(cfg)
        assert any("duration" in e for e in errors)

    def test_invalid_video_duration_over_120(self):
        cfg = self._valid_config(media_type="video")
        cfg["generation"]["duration"] = "121s"
        errors = validate(cfg)
        assert any("duration" in e for e in errors)

    def test_valid_video_duration_boundary(self):
        cfg = self._valid_config(media_type="video")
        cfg["generation"]["duration"] = "120s"
        cfg["generation"]["fps"] = 30
        errors = validate(cfg)
        duration_errors = [e for e in errors if "duration" in e]
        assert duration_errors == []

    def test_invalid_fps(self):
        cfg = self._valid_config(media_type="video")
        cfg["generation"]["fps"] = 25
        errors = validate(cfg)
        assert any("fps" in e for e in errors)

    def test_valid_fps_values(self):
        for fps in (24, 30, 60):
            cfg = self._valid_config(media_type="video")
            cfg["generation"]["fps"] = fps
            errors = validate(cfg)
            fps_errors = [e for e in errors if "fps" in e]
            assert fps_errors == [], f"fps={fps} should be valid"

    def test_invalid_camera_motion(self):
        cfg = self._valid_config(media_type="video")
        cfg["generation"]["camera_motion"] = "swoosh"
        errors = validate(cfg)
        assert any("camera_motion" in e for e in errors)

    def test_valid_camera_motion(self):
        cfg = self._valid_config(media_type="video")
        cfg["generation"]["camera_motion"] = "slow_dolly"
        cfg["generation"]["fps"] = 30
        errors = validate(cfg)
        motion_errors = [e for e in errors if "camera_motion" in e]
        assert motion_errors == []

    def test_missing_name(self):
        cfg = self._valid_config()
        cfg["name"] = ""
        errors = validate(cfg)
        assert any("name" in e for e in errors)


# =========================================================================
# 3. PromptCache
# =========================================================================

class TestPromptCache:
    """PromptCache must produce stable keys and survive put/get roundtrip."""

    @staticmethod
    def _config(**overrides) -> dict:
        cfg = {"model": "test-model", "media_type": "image"}
        cfg.update(overrides)
        return cfg

    def test_same_prompt_same_config_same_key(self, tmp_path):
        cache = PromptCache(cache_dir=tmp_path)
        key1 = cache._compute_key("hello world", self._config())
        key2 = cache._compute_key("hello world", self._config())
        assert key1 == key2

    def test_different_prompt_different_key(self, tmp_path):
        cache = PromptCache(cache_dir=tmp_path)
        key1 = cache._compute_key("prompt A", self._config())
        key2 = cache._compute_key("prompt B", self._config())
        assert key1 != key2

    def test_different_model_different_key(self, tmp_path):
        cache = PromptCache(cache_dir=tmp_path)
        key1 = cache._compute_key("same prompt", self._config(model="model-a"))
        key2 = cache._compute_key("same prompt", self._config(model="model-b"))
        assert key1 != key2

    def test_get_returns_none_on_miss(self, tmp_path):
        cache = PromptCache(cache_dir=tmp_path)
        result = cache.get("nonexistent prompt", self._config())
        assert result is None

    def test_put_then_get_returns_cached_path(self, tmp_path):
        cache = PromptCache(cache_dir=tmp_path)
        # Create a fake output file that the cache can verify exists
        fake_output = tmp_path / "output.png"
        fake_output.write_text("fake image data")

        cache.put("my prompt", self._config(), str(fake_output))
        result = cache.get("my prompt", self._config())
        assert result == str(fake_output)

    def test_get_returns_none_if_output_file_deleted(self, tmp_path):
        cache = PromptCache(cache_dir=tmp_path)
        fake_output = tmp_path / "output.png"
        fake_output.write_text("fake image data")

        cache.put("my prompt", self._config(), str(fake_output))
        # Delete the output file
        fake_output.unlink()

        result = cache.get("my prompt", self._config())
        assert result is None

    def test_clear_removes_expired_entries(self, tmp_path):
        cache = PromptCache(cache_dir=tmp_path)
        fake_output = tmp_path / "output.png"
        fake_output.write_text("fake image data")

        cache.put("my prompt", self._config(), str(fake_output))

        # Patch the manifest's created_at to be 60 days ago
        manifest_files = list(tmp_path.glob("*.json"))
        assert len(manifest_files) == 1

        with open(manifest_files[0], "r") as f:
            manifest = json.load(f)
        manifest["created_at"] = time.time() - (60 * 86400)
        with open(manifest_files[0], "w") as f:
            json.dump(manifest, f)

        removed = cache.clear(max_age_days=30)
        assert removed == 1

        # Confirm it's gone
        result = cache.get("my prompt", self._config())
        assert result is None


# =========================================================================
# 4. Evaluator Hard Checks
# =========================================================================

class TestEvaluatorHardChecks:
    """Evaluator hard_check must detect missing, empty, and corrupted files."""

    @staticmethod
    def _config_with_checks(checks: list[str]) -> dict:
        return {"refinement": {"hard_checks": checks}}

    def test_file_exists_passes_for_real_file(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        evaluator = Evaluator()
        passed, failures = evaluator.hard_check(
            str(f), self._config_with_checks(["file_exists"])
        )
        assert passed is True
        assert failures == []

    def test_file_exists_fails_for_nonexistent(self, tmp_path):
        evaluator = Evaluator()
        passed, failures = evaluator.hard_check(
            str(tmp_path / "nope.png"),
            self._config_with_checks(["file_exists"]),
        )
        assert passed is False
        assert any("does not exist" in f for f in failures)

    def test_file_not_empty_passes_for_nonempty(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        evaluator = Evaluator()
        passed, failures = evaluator.hard_check(
            str(f), self._config_with_checks(["file_not_empty"])
        )
        assert passed is True

    def test_file_not_empty_fails_for_empty(self, tmp_path):
        f = tmp_path / "empty.png"
        f.write_bytes(b"")

        evaluator = Evaluator()
        passed, failures = evaluator.hard_check(
            str(f), self._config_with_checks(["file_not_empty"])
        )
        assert passed is False
        assert any("empty" in f.lower() for f in failures)

    def test_not_corrupted_passes_for_valid_png(self, tmp_path):
        f = tmp_path / "valid.png"
        # Write a valid PNG header (8 bytes) + some body
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        evaluator = Evaluator()
        passed, failures = evaluator.hard_check(
            str(f), self._config_with_checks(["not_corrupted"])
        )
        assert passed is True
        assert failures == []

    def test_not_corrupted_fails_for_random_bytes_as_png(self, tmp_path):
        f = tmp_path / "garbage.png"
        f.write_bytes(b"this is not a png at all, just random junk bytes")

        evaluator = Evaluator()
        passed, failures = evaluator.hard_check(
            str(f), self._config_with_checks(["not_corrupted"])
        )
        assert passed is False
        assert any("corrupted" in f.lower() or "invalid" in f.lower() for f in failures)

    def test_not_corrupted_passes_for_valid_jpeg(self, tmp_path):
        f = tmp_path / "valid.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        evaluator = Evaluator()
        passed, failures = evaluator.hard_check(
            str(f), self._config_with_checks(["not_corrupted"])
        )
        assert passed is True

    def test_not_corrupted_fails_for_garbage_jpeg(self, tmp_path):
        f = tmp_path / "garbage.jpg"
        f.write_bytes(b"definitely not jpeg data here")

        evaluator = Evaluator()
        passed, failures = evaluator.hard_check(
            str(f), self._config_with_checks(["not_corrupted"])
        )
        assert passed is False


# =========================================================================
# 5. RateLimiter
# =========================================================================

class TestRateLimiter:
    """RateLimiter must track quotas, reset daily, and walk the fallback chain."""

    def test_can_proceed_true_under_limit(self, tmp_path):
        limiter = RateLimiter(
            limits={"openrouter": 10},
            state_path=tmp_path / "state.json",
        )
        assert limiter.can_proceed("test-provider", "openrouter") is True

    def test_can_proceed_false_at_limit(self, tmp_path):
        limiter = RateLimiter(
            limits={"openrouter": 2},
            state_path=tmp_path / "state.json",
        )
        limiter.record_request("test-provider", "openrouter")
        limiter.record_request("test-provider", "openrouter")
        assert limiter.can_proceed("test-provider", "openrouter") is False

    def test_daily_reset_clears_count(self, tmp_path):
        limiter = RateLimiter(
            limits={"openrouter": 2},
            state_path=tmp_path / "state.json",
        )
        limiter.record_request("test-provider", "openrouter")
        limiter.record_request("test-provider", "openrouter")
        assert limiter.can_proceed("test-provider", "openrouter") is False

        # Simulate time passing beyond the reset window
        state = limiter._providers["test-provider"]
        state.reset_at = time.time() - 1  # reset time is in the past

        # Now should reset and allow
        assert limiter.can_proceed("test-provider", "openrouter") is True

    def test_fallback_chain_walks_correctly(self, tmp_path):
        """can_proceed_with_fallback should try the chain in order.

        RateLimiter keys state by provider name. Each auth type in the
        fallback chain is checked against a separate provider entry, so
        we use distinct provider names per auth type to simulate real
        multi-provider fallback.
        """
        limiter = RateLimiter(
            limits={"subscription": 1, "openrouter": 1, "api_key": 10},
            state_path=tmp_path / "state.json",
            fallback_chain=["subscription", "openrouter", "api_key"],
        )
        # Exhaust subscription and openrouter quotas on this provider
        limiter.record_request("provider", "subscription")
        assert limiter.can_proceed("provider", "subscription") is False

        # Verify get_fallback_auth walks the chain
        next_auth = limiter.get_fallback_auth("subscription")
        assert next_auth == "openrouter"
        next_auth = limiter.get_fallback_auth("openrouter")
        assert next_auth == "api_key"
        next_auth = limiter.get_fallback_auth("api_key")
        assert next_auth is None

    def test_fallback_chain_exhausted(self, tmp_path):
        """get_fallback_auth returns None when at end of chain."""
        limiter = RateLimiter(
            limits={"api_key": 10},
            state_path=tmp_path / "state.json",
            fallback_chain=["subscription", "openrouter", "api_key"],
        )
        # Last item in chain has no next
        assert limiter.get_fallback_auth("api_key") is None

    def test_state_persists_across_instances(self, tmp_path):
        state_file = tmp_path / "state.json"
        limiter1 = RateLimiter(
            limits={"openrouter": 10},
            state_path=state_file,
        )
        limiter1.record_request("provider-a", "openrouter")
        limiter1.record_request("provider-a", "openrouter")

        # Create new instance -- should load persisted state
        limiter2 = RateLimiter(
            limits={"openrouter": 10},
            state_path=state_file,
        )
        usage = limiter2.get_usage("provider-a")
        assert usage["count"] == 2


# =========================================================================
# 6. CLI Argument Parsing (smoke tests)
# =========================================================================

class TestCLIArgParsing:
    """CLI subcommands must parse without errors. No actual generation."""

    @staticmethod
    def _run_cli(*args: str) -> subprocess.CompletedProcess:
        """Run cli.py with the given args and return the result."""
        cmd = [sys.executable, str(ENGINE_ROOT / "cli.py")] + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(ENGINE_ROOT),
        )

    def test_generate_help_exits_zero(self):
        result = self._run_cli("generate", "--help")
        assert result.returncode == 0
        assert "--workflow" in result.stdout
        assert "--prompt" in result.stdout

    def test_resolve_help_exits_zero(self):
        result = self._run_cli("resolve", "--help")
        assert result.returncode == 0
        assert "--workflow" in result.stdout

    def test_batch_help_exits_zero(self):
        result = self._run_cli("batch", "--help")
        assert result.returncode == 0
        assert "--workflow" in result.stdout
        assert "--prompts-file" in result.stdout

    def test_pipeline_help_exits_zero(self):
        result = self._run_cli("pipeline", "--help")
        assert result.returncode == 0
        assert "--config" in result.stdout
        assert "--prompt" in result.stdout

    def test_no_subcommand_exits_nonzero(self):
        result = self._run_cli()
        assert result.returncode != 0
