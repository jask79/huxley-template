"""
Direct OpenRouter API Client for the Media Workflow Engine.

Provides a Python interface for calling OpenRouter's chat completions API
with multi-image reference support. The existing shell scripts (generate.sh,
edit-image.sh) don't support sending multiple reference images in a single
request, so this client handles that case directly.

Uses only stdlib (urllib.request) -- no 'requests' dependency.

Auth resolution:
  1. Explicit api_key parameter
  2. OPENROUTER_API_KEY environment variable
  3. macOS Keychain: security find-generic-password -s "openrouter-api" -a "huxley" -w
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


# Default endpoint and model
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3-pro-image-preview"

# Request headers
REFERER = "https://{{BRAND}}.example"
APP_TITLE = "Huxley Media Engine"

# Timeout for API requests (seconds)
REQUEST_TIMEOUT = 300


class APIClientError(Exception):
    """Raised when an API request fails."""


class OpenRouterClient:
    """
    Direct OpenRouter API client for image generation with reference support.

    Handles multi-image reference input for style consistency, which the
    shell scripts cannot do. Also provides simple generation and editing
    for cases where the Python path is preferred over shell scripts.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize the client with auto-discovered API key.

        Resolution order:
          1. Explicit api_key parameter
          2. OPENROUTER_API_KEY environment variable
          3. macOS Keychain lookup

        Args:
            api_key: Optional explicit API key. If None, auto-discovers.

        Raises:
            APIClientError: If no API key can be found.
        """
        self.api_key = api_key or self._discover_api_key()
        self.endpoint = OPENROUTER_ENDPOINT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_with_references(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        reference_images: list[str] | None = None,
        style_weight: float = 0.7,
        character_lock: bool = False,
    ) -> bytes:
        """
        Generate an image with reference images for style consistency.

        Builds a multi-image message containing all reference images and
        the generation prompt. Style weight and character lock modify the
        prompt text to influence how closely the output matches references.

        Args:
            prompt: The image generation prompt.
            model: OpenRouter model identifier.
            reference_images: List of file paths to reference images.
            style_weight: How closely to match reference style (0.0-1.0).
                Higher values add stronger style matching instructions.
            character_lock: If True, adds instructions to maintain exact
                character appearance from references.

        Returns:
            Raw image bytes (PNG data).

        Raises:
            APIClientError: If the API request fails or returns no image.
        """
        content_parts: list[dict[str, Any]] = []

        # Add reference images as base64 data URIs
        if reference_images:
            for ref_path in reference_images:
                data_uri = self._encode_image(ref_path)
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                })

        # Build the prompt text with style/consistency modifiers
        full_prompt = self._build_styled_prompt(
            prompt, style_weight, character_lock, has_refs=bool(reference_images)
        )
        content_parts.append({"type": "text", "text": full_prompt})

        # Build and send the request
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content_parts}],
        }

        response = self._send_request(payload)
        return self._parse_response(response)

    def generate_image(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
    ) -> bytes:
        """
        Generate an image from a text prompt (no references).

        Args:
            prompt: The image generation prompt.
            model: OpenRouter model identifier.

        Returns:
            Raw image bytes.

        Raises:
            APIClientError: If the request fails.
        """
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": f"Generate an image: {prompt}",
            }],
        }

        response = self._send_request(payload)
        return self._parse_response(response)

    def edit_image(
        self,
        input_image_path: str,
        prompt: str,
        model: str = DEFAULT_MODEL,
    ) -> bytes:
        """
        Edit an existing image using a text prompt.

        Args:
            input_image_path: Path to the source image to edit.
            prompt: The edit instruction.
            model: OpenRouter model identifier.

        Returns:
            Raw image bytes of the edited result.

        Raises:
            APIClientError: If the request fails.
            FileNotFoundError: If the input image doesn't exist.
        """
        if not Path(input_image_path).exists():
            raise FileNotFoundError(f"Input image not found: {input_image_path}")

        data_uri = self._encode_image(input_image_path)

        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": f"Edit this image: {prompt}"},
                ],
            }],
        }

        response = self._send_request(payload)
        return self._parse_response(response)

    def evaluate_image(
        self,
        image_path: str,
        criteria: list[str],
        model: str = DEFAULT_MODEL,
    ) -> dict[str, Any]:
        """
        Evaluate an image against quality criteria using vision analysis.

        Sends the image to Gemini for scoring against the provided criteria.

        Args:
            image_path: Path to the image to evaluate.
            criteria: List of evaluation criteria (e.g., "lighting_consistency").
            model: OpenRouter model identifier for evaluation.

        Returns:
            Dict with keys:
              - scores: dict mapping criterion name to score (0-10)
              - overall: float score 0.0-1.0
              - reasoning: str explanation

        Raises:
            APIClientError: If the request fails or response can't be parsed.
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        data_uri = self._encode_image(image_path)
        criteria_str = ", ".join(criteria)

        # Build a JSON example for the model to follow
        scores_example = ", ".join(
            '"{0}": 0'.format(c) for c in criteria
        )
        json_example = '{{"scores": {{{0}}}, "overall": 0.0, "reasoning": "..."}}'.format(
            scores_example
        )

        eval_prompt = (
            f"Evaluate this image on the following criteria: {criteria_str}. "
            f"Score each criterion from 0 to 10, and provide an overall score "
            f"from 0.0 to 1.0. Respond ONLY with valid JSON in this exact format, "
            f"no other text: {json_example}"
        )

        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": eval_prompt},
                ],
            }],
        }

        response = self._send_request(payload)

        # Parse the text response as JSON
        return self._parse_eval_response(response)

    def generate_video(
        self,
        prompt: str,
        model: str = "openai/sora-2",
        duration: str = "4",
        size: str = "1280x720",
    ) -> dict[str, Any]:
        """
        Generate a video from a text prompt via OpenRouter.

        Sends a chat completion request with video generation instructions.
        The response is expected to contain a video URL or data.

        Args:
            prompt: The video generation prompt.
            model: OpenRouter model identifier (e.g., 'openai/sora-2').
            duration: Duration in seconds as a string (e.g., '4', '15').
            size: Video dimensions (e.g., '1280x720').

        Returns:
            Dict with keys:
              - url: video URL if returned by the API
              - data: raw video bytes if returned inline
              - content: raw text content from the response

        Raises:
            APIClientError: If the request fails.
        """
        video_prompt = (
            f"Generate a video: {prompt}\n"
            f"Duration: {duration} seconds. Resolution: {size}."
        )

        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": video_prompt,
            }],
        }

        response = self._send_request(payload)
        return self._parse_video_response(response)

    def generate_video_from_image(
        self,
        image_path: str,
        prompt: str,
        model: str = "openai/sora-2",
        duration: str = "4",
        size: str = "1280x720",
    ) -> dict[str, Any]:
        """
        Generate a video using a source image as the starting frame.

        Sends the source image along with the prompt so the video model
        uses it as the first frame / visual anchor for the generated video.

        Args:
            image_path: Path to the source image (starting frame).
            prompt: The video generation prompt.
            model: OpenRouter model identifier.
            duration: Duration in seconds as a string.
            size: Video dimensions.

        Returns:
            Dict with keys:
              - url: video URL if returned by the API
              - data: raw video bytes if returned inline
              - content: raw text content from the response

        Raises:
            APIClientError: If the request fails.
            FileNotFoundError: If the source image doesn't exist.
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Source image not found: {image_path}")

        data_uri = self._encode_image(image_path)

        video_prompt = (
            f"Using the provided image as the starting frame, generate a video: {prompt}\n"
            f"Duration: {duration} seconds. Resolution: {size}."
        )

        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": video_prompt},
                ],
            }],
        }

        response = self._send_request(payload)
        return self._parse_video_response(response)

    @staticmethod
    def save_video(video_data: bytes, output_path: str) -> str:
        """
        Write raw video bytes to disk.

        Args:
            video_data: Raw MP4 data.
            output_path: Destination file path.

        Returns:
            Absolute path to the saved file.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with open(out, "wb") as f:
            f.write(video_data)

        return str(out.resolve())

    @staticmethod
    def save_image(image_bytes: bytes, output_path: str) -> str:
        """
        Write raw image bytes to disk.

        Args:
            image_bytes: Raw PNG/JPEG data.
            output_path: Destination file path.

        Returns:
            Absolute path to the saved file.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with open(out, "wb") as f:
            f.write(image_bytes)

        return str(out.resolve())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _discover_api_key(self) -> str:
        """
        Auto-discover the OpenRouter API key via Huxley secret_provider.

        Resolution order (handled by secret_provider):
          1. macOS Keychain (service: "openrouter-api", account: "huxley")
          2. OPENROUTER_API environment variable (auto-derived from service name)

        Raises:
            APIClientError: If no key is found.
        """
        try:
            import sys as _sys
            _sys.path.insert(0, "{{CATALYST_ROOT}}/global/lib")
            from secret_provider import get_secret
            return get_secret("openrouter-api")
        except Exception as exc:
            raise APIClientError(
                f"No OpenRouter API key found: {exc}\n"
                "Add to macOS Keychain:\n"
                "  security add-generic-password -s 'openrouter-api' -a 'huxley' -w 'your-key'\n"
                "Or set OPENROUTER_API environment variable."
            ) from exc

    def _send_request(
        self,
        payload: dict[str, Any],
        _max_attempts: int = 3,
    ) -> dict[str, Any]:
        """
        Send a request to the OpenRouter API with retry on transient errors.

        Retries up to 2 times (3 total attempts) on HTTP 429 (rate limit) and
        503 (service unavailable) using exponential backoff (2s, 4s). All other
        errors raise immediately.

        Args:
            payload: The JSON request body.
            _max_attempts: Maximum number of attempts (default 3 = 1 + 2 retries).

        Returns:
            Parsed JSON response dict.

        Raises:
            APIClientError: On network errors, HTTP errors, or invalid JSON.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": REFERER,
            "X-Title": APP_TITLE,
        }

        body = json.dumps(payload).encode("utf-8")

        last_exc: APIClientError | None = None

        for attempt in range(1, _max_attempts + 1):
            req = urllib.request.Request(
                self.endpoint,
                data=body,
                headers=headers,
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                    response_body = resp.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                # Retry on transient 429 / 503 errors
                if exc.code in (429, 503) and attempt < _max_attempts:
                    backoff = 2 ** attempt  # 2s, 4s
                    print(
                        f"  Retrying after HTTP {exc.code} "
                        f"(attempt {attempt}/{_max_attempts}, "
                        f"waiting {backoff}s)..."
                    )
                    time.sleep(backoff)
                    error_body = ""
                    try:
                        error_body = exc.read().decode("utf-8")
                    except Exception:
                        pass
                    last_exc = APIClientError(
                        f"OpenRouter API error (HTTP {exc.code}): {error_body}"
                    )
                    continue

                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8")
                except Exception:
                    pass
                raise APIClientError(
                    f"OpenRouter API error (HTTP {exc.code}): {error_body}"
                ) from exc
            except urllib.error.URLError as exc:
                raise APIClientError(
                    f"Network error connecting to OpenRouter: {exc.reason}"
                ) from exc
            except TimeoutError as exc:
                raise APIClientError(
                    f"Request timed out after {REQUEST_TIMEOUT}s"
                ) from exc

            try:
                result = json.loads(response_body)
            except json.JSONDecodeError as exc:
                raise APIClientError(
                    f"Invalid JSON response from OpenRouter: {response_body[:500]}"
                ) from exc

            # Check for API-level errors
            if "error" in result:
                error_msg = result["error"]
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                raise APIClientError(f"OpenRouter API error: {error_msg}")

            return result

        # All retries exhausted (should only reach here for 429/503)
        raise last_exc or APIClientError(
            "Request failed after all retry attempts"
        )

    @staticmethod
    def _parse_response(response: dict[str, Any]) -> bytes:
        """
        Parse image data from an OpenRouter chat completion response.

        Handles two response formats:
          1. .choices[0].message.images[0].image_url.url -> data URI
          2. .choices[0].message.content -> data URI (fallback)

        Returns:
            Raw image bytes decoded from base64.

        Raises:
            APIClientError: If no image data is found in the response.
        """
        choices = response.get("choices", [])
        if not choices:
            raise APIClientError("No choices in API response")

        message = choices[0].get("message", {})

        # Format 1: images array
        images = message.get("images", [])
        if images:
            image_url = images[0].get("image_url", {}).get("url", "")
            if image_url and image_url.startswith("data:image/"):
                return _decode_data_uri(image_url)

        # Format 2: content field as data URI
        content = message.get("content", "")
        if isinstance(content, str) and content.startswith("data:image/"):
            return _decode_data_uri(content)

        # Format 3: content is a list with image parts
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    url = part.get("image_url", {}).get("url", "")
                    if url and url.startswith("data:image/"):
                        return _decode_data_uri(url)

        raise APIClientError(
            "No image data found in API response. "
            "The model may not support image generation."
        )

    @staticmethod
    def _parse_eval_response(response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse an evaluation response, extracting JSON scores.

        Handles cases where the model wraps JSON in markdown code fences
        or includes extra text before/after the JSON.

        Returns:
            Parsed evaluation dict with scores, overall, and reasoning.

        Raises:
            APIClientError: If the response cannot be parsed as evaluation JSON.
        """
        choices = response.get("choices", [])
        if not choices:
            raise APIClientError("No choices in evaluation response")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if not isinstance(content, str) or not content.strip():
            raise APIClientError("Empty evaluation response")

        text = content.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            text = "\n".join(lines).strip()

        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = text[start:end]
            try:
                result = json.loads(json_str)
                # Validate expected structure
                if "overall" in result:
                    # Clamp overall to 0.0-1.0
                    result["overall"] = max(0.0, min(1.0, float(result["overall"])))
                    return result
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        raise APIClientError(
            f"Could not parse evaluation response as JSON: {text[:300]}"
        )

    @staticmethod
    def _parse_video_response(response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse video data from an OpenRouter chat completion response.

        Handles multiple response formats:
          1. Video URL in content text
          2. Base64-encoded video data URI
          3. Raw text content (URL or description)

        Returns:
            Dict with keys:
              - url: str or None, video URL
              - data: bytes or None, decoded video data
              - content: str, raw text content from the response

        Raises:
            APIClientError: If no usable response content is found.
        """
        choices = response.get("choices", [])
        if not choices:
            raise APIClientError("No choices in video API response")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        result: dict[str, Any] = {"url": None, "data": None, "content": ""}

        if isinstance(content, str):
            result["content"] = content.strip()

            # Check for base64 video data URI
            if content.strip().startswith("data:video/"):
                try:
                    result["data"] = _decode_data_uri(content.strip())
                except APIClientError:
                    pass

            # Check for a URL in the content
            elif content.strip().startswith("http"):
                result["url"] = content.strip().split()[0]

        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    # Check for video URL in structured content
                    url = part.get("video_url", {}).get("url", "")
                    if not url:
                        url = part.get("url", "")
                    if url:
                        if url.startswith("data:video/"):
                            try:
                                result["data"] = _decode_data_uri(url)
                            except APIClientError:
                                pass
                        elif url.startswith("http"):
                            result["url"] = url
                    # Also check text parts
                    text = part.get("text", "")
                    if text:
                        result["content"] = text

        if not result["url"] and not result["data"] and not result["content"]:
            raise APIClientError(
                "No video data or URL found in API response. "
                "The model may not support video generation."
            )

        return result

    @staticmethod
    def _encode_image(image_path: str) -> str:
        """
        Read an image file and encode it as a base64 data URI.

        Args:
            image_path: Path to the image file.

        Returns:
            Data URI string (e.g., "data:image/png;base64,...")

        Raises:
            APIClientError: If the file can't be read or format is unknown.
        """
        path = Path(image_path)
        if not path.exists():
            raise APIClientError(f"Image file not found: {image_path}")

        # Determine MIME type from extension
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }

        mime_type = mime_map.get(path.suffix.lower())
        if not mime_type:
            raise APIClientError(
                f"Unsupported image format: {path.suffix}. "
                f"Supported: {sorted(mime_map.keys())}"
            )

        try:
            with open(path, "rb") as f:
                image_data = f.read()
        except OSError as exc:
            raise APIClientError(f"Cannot read image file: {exc}") from exc

        encoded = base64.b64encode(image_data).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _build_styled_prompt(
        prompt: str,
        style_weight: float,
        character_lock: bool,
        has_refs: bool,
    ) -> str:
        """
        Build a generation prompt with style/consistency modifiers.

        The style_weight parameter influences how aggressively the prompt
        instructs the model to match reference image style:
          - 0.0-0.3: Subtle influence ("Take inspiration from the reference images")
          - 0.3-0.6: Moderate matching ("Match the general style and color palette")
          - 0.6-0.8: Strong matching ("Closely match the style and aesthetic")
          - 0.8-1.0: Maximum fidelity ("Exactly replicate the style, lighting, and mood")

        Args:
            prompt: The base generation prompt.
            style_weight: Style matching intensity (0.0-1.0).
            character_lock: Whether to lock character appearance.
            has_refs: Whether reference images are included.

        Returns:
            Modified prompt string.
        """
        parts: list[str] = []

        if has_refs:
            if style_weight <= 0.3:
                parts.append(
                    "Take inspiration from the reference images provided."
                )
            elif style_weight <= 0.6:
                parts.append(
                    "Match the general style, color palette, and composition "
                    "of the reference images."
                )
            elif style_weight <= 0.8:
                parts.append(
                    "Closely match the style, aesthetic, lighting, and visual "
                    "language of the reference images."
                )
            else:
                parts.append(
                    "Exactly replicate the style, lighting, color grading, mood, "
                    "and visual treatment of the reference images."
                )

            if character_lock:
                parts.append(
                    "Maintain exact character appearance, facial features, "
                    "proportions, and clothing from the reference images."
                )

        parts.append(f"Generate an image: {prompt}")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _decode_data_uri(data_uri: str) -> bytes:
    """
    Decode a base64 data URI to raw bytes.

    Args:
        data_uri: A data URI string (e.g., "data:image/png;base64,...")

    Returns:
        Decoded bytes.

    Raises:
        APIClientError: If the data URI format is invalid.
    """
    try:
        # Split off the header: "data:image/png;base64,XXXXX"
        _, encoded = data_uri.split(",", 1)
        return base64.b64decode(encoded)
    except (ValueError, Exception) as exc:
        raise APIClientError(
            f"Failed to decode image data URI: {exc}"
        ) from exc
