"""Gemini synthesizer: trajectory + outcome -> draft SKILL.md.

Stdlib-only HTTP via `urllib.request` per the ADR's "no new dependencies" rule.
The API key is pulled from macOS Keychain at call time.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .extractor import SessionSummary, format_tool_sequence_for_prompt

GEMINI_MODEL = "gemini-2.0-flash-exp"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={{api_key}}"
)
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "proposer.md"

MIN_BODY_CHARS = 200
SKIP_SENTINEL = "SKIP: not reusable"


@dataclass
class SynthesisResult:
    ok: bool
    skill_md: str = ""
    error: str = ""
    skipped: bool = False  # True when Gemini returned SKIP_SENTINEL
    # Token usage (for cost reporting)
    input_tokens: int = 0
    output_tokens: int = 0


def get_gemini_api_key() -> str:
    """Read the Gemini API key from macOS Keychain."""
    try:
        out = subprocess.check_output(
            ["security", "find-generic-password", "-s", "gemini-api", "-a", "huxley", "-w"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to read gemini-api from Keychain: {e}") from e


def _build_prompt(summary: SessionSummary, proposed_at: str, outcome_signal: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    tool_seq = format_tool_sequence_for_prompt(summary)
    final_user = summary.last_user_message or "(no final user message)"
    return (
        template.replace("{{PROPOSED_AT}}", proposed_at)
        .replace("{{SOURCE_SESSION}}", summary.session_id)
        .replace("{{FINAL_USER_MESSAGE}}", final_user[:1000])
        .replace("{{TOOL_SEQUENCE}}", tool_seq)
        .replace("{{OUTCOME_SIGNAL}}", outcome_signal)
    )


def _post_to_gemini(api_key: str, prompt: str, timeout: int = 30) -> dict:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
        },
    }
    data = json.dumps(body).encode("utf-8")
    url = GEMINI_URL.format(api_key=api_key)
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _extract_text(response: dict) -> str:
    candidates = response.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


def _strip_markdown_fence(text: str) -> str:
    """Gemini sometimes wraps the SKILL.md in ```markdown ... ```. Unwrap it."""
    fence = re.compile(r"^```(?:markdown|md)?\s*\n(.*?)\n```\s*$", re.DOTALL)
    m = fence.match(text.strip())
    if m:
        return m.group(1).strip()
    return text.strip()


def _validate_skill_md(skill_md: str) -> tuple[bool, str]:
    """Sanity-check the Gemini output before writing it to disk.

    Required:
      - Starts with `---` frontmatter delimiter
      - Frontmatter contains `name:` and `description:`
      - Body (post-frontmatter) >= MIN_BODY_CHARS
    """
    if not skill_md.startswith("---"):
        return False, "missing frontmatter opening delimiter"

    parts = skill_md.split("---", 2)
    if len(parts) < 3:
        return False, "incomplete frontmatter (no closing ---)"

    frontmatter = parts[1]
    body = parts[2].strip()

    if "name:" not in frontmatter:
        return False, "frontmatter missing `name:` field"
    if "description:" not in frontmatter:
        return False, "frontmatter missing `description:` field"
    if len(body) < MIN_BODY_CHARS:
        return False, f"body too short ({len(body)} < {MIN_BODY_CHARS})"

    return True, ""


def synthesize(
    summary: SessionSummary, proposed_at: str, outcome_signal: str
) -> SynthesisResult:
    """End-to-end: build prompt, call Gemini, validate result."""
    try:
        api_key = get_gemini_api_key()
    except RuntimeError as e:
        return SynthesisResult(ok=False, error=str(e))

    prompt = _build_prompt(summary, proposed_at, outcome_signal)

    try:
        resp = _post_to_gemini(api_key, prompt)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return SynthesisResult(ok=False, error=f"Gemini HTTP error: {e}")
    except json.JSONDecodeError as e:
        return SynthesisResult(ok=False, error=f"Gemini returned invalid JSON: {e}")

    text = _extract_text(resp)
    if not text:
        return SynthesisResult(ok=False, error="Gemini returned empty response")

    # Token usage (best-effort — Gemini may or may not include this)
    usage = resp.get("usageMetadata", {})
    input_tokens = int(usage.get("promptTokenCount", 0))
    output_tokens = int(usage.get("candidatesTokenCount", 0))

    if text.strip().startswith(SKIP_SENTINEL):
        return SynthesisResult(
            ok=True,
            skipped=True,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    skill_md = _strip_markdown_fence(text)
    valid, why = _validate_skill_md(skill_md)
    if not valid:
        return SynthesisResult(
            ok=False,
            error=f"Gemini output failed validation: {why}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return SynthesisResult(
        ok=True,
        skill_md=skill_md,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
