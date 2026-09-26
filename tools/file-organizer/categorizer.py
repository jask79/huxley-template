"""Phase 2 — AI categorization: analyze files with LLMs (OpenAI GPT-5 or local Ollama).

Supports two backends controlled by FILE_ORGANIZER_BACKEND env var or --backend CLI flag:
  - openai  (default): GPT-5 via ChatGPT Plus OAuth (reads ~/.codex/auth.json)
  - ollama:            Local LLaVA + Llama 3.2 via Ollama

Falls back automatically: OpenAI → Ollama → extension-based.
"""

import base64
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

from database import get_connection
from utils import IMAGE_EXTENSIONS, ProgressReporter, human_size

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434"

# Vision model for images/screenshots
VISION_MODEL = "llava-llama3:8b"
VISION_FALLBACK = "llava:7b"

# Text model for PDFs/documents
TEXT_MODEL = "llama3.2:3b"

# OpenAI model (used for both vision and text)
OPENAI_MODEL = "gpt-5"

# Codex OAuth auth file (checked for availability — actual auth handled by codex CLI)
CODEX_AUTH_PATH = os.path.expanduser("~/.codex/auth.json")

# Default taxonomy file path
DEFAULT_TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomy.yaml")

# Backend selection: "openai" or "ollama"
DEFAULT_BACKEND = os.environ.get("FILE_ORGANIZER_BACKEND", "openai")

# Top-level category buckets (legacy fallback — overridden by taxonomy.yaml when available)
# These MUST match taxonomy.yaml labels so fallback behavior is consistent.
CATEGORIES = [
    "Project A",
    "Project B",
    "Huxley",
    "Health & Fitness",
    "Finance",
    "Personal",
    "Design",
    "Development",
    "Reference",
    "Media & Entertainment",
    "Unsorted",
]

# Extensions that need vision model
VISION_EXTENSIONS = frozenset([
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".webp", ".heic", ".heif", ".avif",
])

# Extensions for text extraction + text model
PDF_EXTENSIONS = frozenset([".pdf"])
DOC_EXTENSIONS = frozenset([
    ".txt", ".md", ".rtf", ".csv", ".json", ".yaml", ".yml",
    ".xml", ".html", ".htm", ".log", ".ini", ".cfg", ".conf",
    ".py", ".js", ".ts", ".sh", ".rb", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".swift", ".kt",
])

# Confidence threshold — below this goes to Unsorted
CONFIDENCE_THRESHOLD = 0.6

# Max image dimension for resizing before sending to LLaVA
MAX_IMAGE_DIM = 1024

# Max text length sent to text model
MAX_TEXT_LENGTH = 4000


# ---------------------------------------------------------------------------
# Taxonomy loader — builds dynamic category list from taxonomy.yaml
# ---------------------------------------------------------------------------

_taxonomy_cache: Optional[Dict] = None
_taxonomy_categories: Optional[List[str]] = None


def _load_taxonomy() -> Tuple[List[str], Dict[str, str]]:
    """Load taxonomy.yaml and return (category_labels, {label: description}).

    Falls back to hardcoded CATEGORIES if taxonomy.yaml is missing or invalid.
    Results are cached after first load.
    """
    global _taxonomy_cache, _taxonomy_categories

    if _taxonomy_categories is not None and _taxonomy_cache is not None:
        return _taxonomy_categories, _taxonomy_cache

    try:
        import yaml  # available in this project (used by project_tagger.py)
    except ImportError:
        # No yaml — fall back to hardcoded
        _taxonomy_categories = list(CATEGORIES)
        _taxonomy_cache = {}
        return _taxonomy_categories, _taxonomy_cache

    if not os.path.exists(DEFAULT_TAXONOMY_PATH):
        _taxonomy_categories = list(CATEGORIES)
        _taxonomy_cache = {}
        return _taxonomy_categories, _taxonomy_cache

    try:
        with open(DEFAULT_TAXONOMY_PATH, "r") as f:
            data = yaml.safe_load(f)

        cats_raw = data.get("categories", {})
        if not cats_raw:
            _taxonomy_categories = list(CATEGORIES)
            _taxonomy_cache = {}
            return _taxonomy_categories, _taxonomy_cache

        # Sort by priority descending, extract labels + descriptions
        sorted_items = sorted(
            cats_raw.items(),
            key=lambda x: x[1].get("priority", 0),
            reverse=True,
        )

        labels = []
        descriptions = {}
        for key, cat in sorted_items:
            label = cat.get("label", key)
            labels.append(label)
            desc = cat.get("description", "")
            if desc:
                descriptions[label] = desc

        _taxonomy_categories = labels
        _taxonomy_cache = descriptions
        return _taxonomy_categories, _taxonomy_cache

    except Exception:
        _taxonomy_categories = list(CATEGORIES)
        _taxonomy_cache = {}
        return _taxonomy_categories, _taxonomy_cache


def _build_category_prompt_block() -> str:
    """Build the category list + guidelines section for AI prompts dynamically."""
    cat_labels, cat_descs = _load_taxonomy()

    lines = []
    lines.append("Classify it into exactly ONE of these categories: " + ", ".join(cat_labels))
    lines.append("")
    lines.append("Category descriptions:")

    for label in cat_labels:
        desc = cat_descs.get(label, "")
        if desc:
            lines.append(f"- {label}: {desc}")
        else:
            lines.append(f"- {label}")

    return "\n".join(lines)


def _get_valid_categories() -> List[str]:
    """Return the list of valid category labels (from taxonomy or fallback)."""
    cat_labels, _ = _load_taxonomy()
    return cat_labels


# O(1) case-insensitive category lookup — built lazily from taxonomy
_valid_categories_lower: Optional[Dict[str, str]] = None


def _get_category_lookup() -> Dict[str, str]:
    """Return a {lowercase_label: canonical_label} dict for O(1) validation."""
    global _valid_categories_lower
    if _valid_categories_lower is None:
        _valid_categories_lower = {
            cat.lower(): cat for cat in _get_valid_categories()
        }
    return _valid_categories_lower


def _validate_category(category_str: str) -> str:
    """O(1) case-insensitive category validation.

    Returns the canonical category label if valid, otherwise "Unsorted".
    """
    lookup = _get_category_lookup()
    # Exact match first (fast path)
    if category_str in lookup.values():
        return category_str
    # Case-insensitive lookup
    return lookup.get(category_str.lower(), "Unsorted")


# ---------------------------------------------------------------------------
# OpenAI backend via Codex CLI (ChatGPT Plus subscription)
# ---------------------------------------------------------------------------
#
# The Codex CLI handles OAuth auth internally (including token refresh,
# proxy setup, and scope management). We shell out to `codex exec` rather
# than calling the OpenAI API directly, because the ChatGPT Plus OAuth
# token requires the Codex responses-api-proxy for API access.
#

# Path to codex binary (resolved once)
_codex_bin: Optional[str] = None


def _find_codex() -> Optional[str]:
    """Find the codex CLI binary. Caches result."""
    global _codex_bin
    if _codex_bin is not None:
        return _codex_bin if _codex_bin != "" else None

    # Check well-known paths
    candidates = [
        "/opt/homebrew/bin/codex",
        os.path.expanduser("~/.local/bin/codex"),
        "/usr/local/bin/codex",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            _codex_bin = path
            return _codex_bin

    # Try PATH
    try:
        result = subprocess.run(
            ["which", "codex"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            _codex_bin = result.stdout.strip()
            return _codex_bin
    except Exception:
        pass

    _codex_bin = ""  # sentinel: not found
    return None


def _openai_available() -> bool:
    """Check if OpenAI backend is usable (codex CLI installed + auth present)."""
    if not _find_codex():
        return False
    if not os.path.exists(CODEX_AUTH_PATH):
        return False
    try:
        with open(CODEX_AUTH_PATH, "r") as f:
            data = json.load(f)
        return bool(data.get("tokens", {}).get("access_token"))
    except Exception:
        return False


def _codex_exec(
    prompt: str,
    image_path: Optional[str] = None,
    model: str = OPENAI_MODEL,
    timeout: int = 120,
) -> Optional[str]:
    """Run a prompt through codex exec and return the text response.

    Uses `codex exec` with --skip-git-repo-check, read-only sandbox,
    and -o to capture the last message. The prompt is piped via stdin
    to avoid shell escaping issues.
    """
    codex = _find_codex()
    if not codex:
        return None

    import tempfile
    # Write response to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        output_path = tmp.name

    try:
        cmd = [
            codex, "exec",
            "-m", model,
            "-s", "read-only",
            "--skip-git-repo-check",
            "-o", output_path,
            "-",  # read prompt from stdin
        ]

        if image_path and os.path.isfile(image_path):
            cmd.insert(-1, "-i")
            cmd.insert(-1, image_path)

        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1"},
        )

        # Read the output file
        if os.path.exists(output_path):
            with open(output_path, "r") as f:
                response = f.read().strip()
            if response:
                return response

        # Fall back to stdout if output file is empty
        if result.stdout and result.stdout.strip():
            return result.stdout.strip()

        return None

    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# OpenAI image analysis (via Codex CLI)
# ---------------------------------------------------------------------------

def _analyze_image_openai(filepath: str) -> Optional[dict]:
    """Analyze an image using GPT-5 vision via Codex CLI.

    Passes the image file directly to codex exec --image, which handles
    the vision input natively.
    """
    filename = os.path.basename(filepath).replace('"', '').replace('\\', '')
    category_block = _build_category_prompt_block()

    prompt = f"""Analyze this image file named "{filename}" and respond with ONLY valid JSON (no markdown, no explanation).

{category_block}

Also provide 1-3 descriptive tags (short, lowercase) and a one-line description.

Respond ONLY with this JSON format:
{{"category": "...", "tags": ["tag1", "tag2"], "description": "...", "confidence": 0.85}}"""

    response = _codex_exec(prompt, image_path=filepath)
    if not response:
        return None

    return _parse_ai_response(response)


# ---------------------------------------------------------------------------
# OpenAI text analysis (via Codex CLI)
# ---------------------------------------------------------------------------

def _analyze_text_openai(filepath: str, text: str) -> Optional[dict]:
    """Analyze text content using GPT-5 via Codex CLI."""
    filename = os.path.basename(filepath).replace('"', '').replace('\\', '')
    ext = Path(filepath).suffix.lower()
    category_block = _build_category_prompt_block()

    text_preview = text[:2000] if len(text) > 2000 else text

    prompt = f"""Analyze this file and respond with ONLY valid JSON (no markdown, no explanation).

File: "{filename}" (type: {ext})
Content preview:
---
{text_preview}
---

{category_block}

Also provide 1-3 descriptive tags (short, lowercase) and a one-line description.

Respond ONLY with this JSON format:
{{"category": "...", "tags": ["tag1", "tag2"], "description": "...", "confidence": 0.85}}"""

    response = _codex_exec(prompt, timeout=60)
    if not response:
        return None

    return _parse_ai_response(response)


# ---------------------------------------------------------------------------
# Ollama API client
# ---------------------------------------------------------------------------

def _ollama_available() -> bool:
    """Check if Ollama is running."""
    try:
        req = Request(f"{OLLAMA_URL}/api/tags")
        with urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _ollama_generate(
    model: str,
    prompt: str,
    images: Optional[List[str]] = None,
    timeout: int = 120,
) -> Optional[str]:
    """Call Ollama generate API. images is a list of base64-encoded strings."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 300,
        },
    }
    if images:
        payload["images"] = images

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            return result.get("response", "")
    except Exception as e:
        return None


def _model_available(model: str) -> bool:
    """Check if a specific model is available in Ollama."""
    try:
        req = Request(f"{OLLAMA_URL}/api/tags")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            names = [m["name"] for m in data.get("models", [])]
            return model in names or any(n.startswith(model) for n in names)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Image analysis
# ---------------------------------------------------------------------------

def _resize_image_for_llava(filepath: str) -> Optional[str]:
    """Load and resize an image, return base64 string. Uses Pillow."""
    try:
        from PIL import Image
        img = Image.open(filepath)

        # Convert HEIC/HEIF to RGB (Pillow handles this with pillow-heif)
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")

        # Resize if larger than MAX_IMAGE_DIM
        w, h = img.size
        if max(w, h) > MAX_IMAGE_DIM:
            ratio = MAX_IMAGE_DIM / max(w, h)
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # Convert to JPEG bytes
        import io
        buf = io.BytesIO()
        if img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    except Exception:
        # Fallback: read raw bytes (skip large files to avoid memory exhaustion)
        try:
            file_size = os.path.getsize(filepath)
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                return None
            with open(filepath, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return None


def _analyze_image(filepath: str, model: str) -> Optional[dict]:
    """Analyze an image file using LLaVA vision model."""
    img_b64 = _resize_image_for_llava(filepath)
    if not img_b64:
        return None

    filename = os.path.basename(filepath).replace('"', '').replace('\\', '')
    category_block = _build_category_prompt_block()

    prompt = f"""Analyze this image file named "{filename}" and respond with ONLY valid JSON (no markdown, no explanation).

{category_block}

Also provide 1-3 descriptive tags (short, lowercase) and a one-line description.

Respond ONLY with this JSON format:
{{"category": "...", "tags": ["tag1", "tag2"], "description": "...", "confidence": 0.85}}"""

    response = _ollama_generate(model, prompt, images=[img_b64])
    if not response:
        return None

    return _parse_ai_response(response)


# ---------------------------------------------------------------------------
# Text/PDF analysis
# ---------------------------------------------------------------------------

def _extract_pdf_text(filepath: str) -> Optional[str]:
    """Extract text from a PDF file."""
    # Try PyMuPDF (fitz) first
    try:
        import fitz
        with fitz.open(filepath) as doc:
            text = ""
            for page in doc:
                text += page.get_text()
                if len(text) > MAX_TEXT_LENGTH:
                    break
        return text[:MAX_TEXT_LENGTH] if text.strip() else None
    except ImportError:
        pass

    # Fallback: try pdftotext CLI
    try:
        result = subprocess.run(
            ["pdftotext", "-l", "3", filepath, "-"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout[:MAX_TEXT_LENGTH]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _read_text_file(filepath: str) -> Optional[str]:
    """Read text from a text-based file."""
    try:
        with open(filepath, "r", errors="replace") as f:
            return f.read(MAX_TEXT_LENGTH)
    except Exception:
        return None


def _analyze_text(filepath: str, text: str, model: str) -> Optional[dict]:
    """Analyze text content using Llama 3.2 text model."""
    filename = os.path.basename(filepath).replace('"', '').replace('\\', '')
    ext = Path(filepath).suffix.lower()
    category_block = _build_category_prompt_block()

    # Truncate text for prompt
    text_preview = text[:2000] if len(text) > 2000 else text

    prompt = f"""Analyze this file and respond with ONLY valid JSON (no markdown, no explanation).

File: "{filename}" (type: {ext})
Content preview:
---
{text_preview}
---

{category_block}

Also provide 1-3 descriptive tags (short, lowercase) and a one-line description.

Respond ONLY with this JSON format:
{{"category": "...", "tags": ["tag1", "tag2"], "description": "...", "confidence": 0.85}}"""

    response = _ollama_generate(model, prompt, timeout=60)
    if not response:
        return None

    return _parse_ai_response(response)


# ---------------------------------------------------------------------------
# Batch text analysis — reduces API calls by grouping text files
# ---------------------------------------------------------------------------

# Max files per batch (balance prompt size vs. API overhead)
BATCH_SIZE = 8
# Max total text chars per batch prompt to stay within context limits
BATCH_MAX_CHARS = 12000


def _prepare_text_batch(
    file_rows: List[dict],
) -> List[Tuple[str, str]]:
    """Read text content for a batch of files.

    Returns list of (filepath, text_preview) tuples for files that have
    readable content. Skips files that don't exist or have no text.
    """
    items: List[Tuple[str, str]] = []
    for row in file_rows:
        filepath = row["path"]
        ext = row["extension"]

        if not os.path.exists(filepath):
            continue

        if ext in PDF_EXTENSIONS:
            text = _extract_pdf_text(filepath)
        elif ext in DOC_EXTENSIONS:
            text = _read_text_file(filepath)
        else:
            continue

        if text and len(text.strip()) > 20:
            # Use shorter previews in batch mode to fit more files
            preview = text[:800] if len(text) > 800 else text
            items.append((filepath, preview))

    return items


def _batch_analyze_text_openai(
    file_items: List[Tuple[str, str]],
) -> Dict[str, Optional[dict]]:
    """Analyze multiple text files in a single GPT-5 call.

    Args:
        file_items: List of (filepath, text_preview) tuples.

    Returns:
        Dict mapping filepath -> categorization result (or None on failure).
    """
    if not file_items:
        return {}

    category_block = _build_category_prompt_block()

    # Build multi-file prompt
    file_sections = []
    for idx, (filepath, text_preview) in enumerate(file_items, 1):
        filename = os.path.basename(filepath).replace('"', '').replace('\\', '')
        ext = Path(filepath).suffix.lower()
        file_sections.append(
            f'FILE {idx}: "{filename}" (type: {ext})\n'
            f'---\n{text_preview}\n---'
        )

    files_block = "\n\n".join(file_sections)

    prompt = f"""Analyze each file below and respond with ONLY a valid JSON array (no markdown, no explanation).

{files_block}

{category_block}

For EACH file, provide category, 1-3 tags (short, lowercase), a one-line description, and confidence.

Respond ONLY with a JSON array in this format (one object per file, in order):
[{{"file": 1, "category": "...", "tags": ["tag1"], "description": "...", "confidence": 0.85}}, ...]"""

    response = _codex_exec(prompt, timeout=180)
    if not response:
        return {fp: None for fp, _ in file_items}

    return _parse_batch_response(response, file_items)


def _batch_analyze_text_ollama(
    file_items: List[Tuple[str, str]],
    model: str,
) -> Dict[str, Optional[dict]]:
    """Analyze multiple text files in a single Ollama call.

    Args:
        file_items: List of (filepath, text_preview) tuples.
        model: Ollama model name to use.

    Returns:
        Dict mapping filepath -> categorization result (or None on failure).
    """
    if not file_items:
        return {}

    category_block = _build_category_prompt_block()

    file_sections = []
    for idx, (filepath, text_preview) in enumerate(file_items, 1):
        filename = os.path.basename(filepath).replace('"', '').replace('\\', '')
        ext = Path(filepath).suffix.lower()
        file_sections.append(
            f'FILE {idx}: "{filename}" (type: {ext})\n'
            f'---\n{text_preview}\n---'
        )

    files_block = "\n\n".join(file_sections)

    prompt = f"""Analyze each file below and respond with ONLY a valid JSON array (no markdown, no explanation).

{files_block}

{category_block}

For EACH file, provide category, 1-3 tags (short, lowercase), a one-line description, and confidence.

Respond ONLY with a JSON array in this format (one object per file, in order):
[{{"file": 1, "category": "...", "tags": ["tag1"], "description": "...", "confidence": 0.85}}, ...]"""

    response = _ollama_generate(model, prompt, timeout=180)
    if not response:
        return {fp: None for fp, _ in file_items}

    return _parse_batch_response(response, file_items)


def _parse_batch_response(
    response: str,
    file_items: List[Tuple[str, str]],
) -> Dict[str, Optional[dict]]:
    """Parse a batch JSON array response and map results to filepaths.

    Falls back to treating the response as individual JSON objects if
    array parsing fails.
    """
    results: Dict[str, Optional[dict]] = {}
    text = response.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # Try parsing as JSON array first
    start = text.find("[")
    end = text.rfind("]") + 1

    if start != -1 and end > 0:
        try:
            items_data = json.loads(text[start:end])
            if isinstance(items_data, list):
                for idx, (filepath, _) in enumerate(file_items):
                    if idx < len(items_data) and isinstance(items_data[idx], dict):
                        parsed = _normalize_result(items_data[idx])
                        results[filepath] = parsed
                    else:
                        results[filepath] = None
                return results
        except json.JSONDecodeError:
            pass

    # Fallback: try to find individual JSON objects in the response
    # This handles cases where the model outputs objects separated by newlines
    json_objects = []
    depth = 0
    obj_start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and obj_start >= 0:
                try:
                    obj = json.loads(text[obj_start:i + 1])
                    json_objects.append(obj)
                except json.JSONDecodeError:
                    pass
                obj_start = -1

    for idx, (filepath, _) in enumerate(file_items):
        if idx < len(json_objects):
            results[filepath] = _normalize_result(json_objects[idx])
        else:
            results[filepath] = None

    return results


def _normalize_result(data: dict) -> Optional[dict]:
    """Normalize a single result dict from a batch response.

    Applies the same validation as _parse_ai_response but on pre-parsed data.
    """
    category = _validate_category(data.get("category", "Unsorted"))

    tags = data.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).lower().strip() for t in tags[:3]]

    description = str(data.get("description", ""))[:200]
    confidence = float(data.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))

    if confidence < CONFIDENCE_THRESHOLD:
        category = "Unsorted"

    return {
        "category": category,
        "tags": tags,
        "description": description,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Extension-based fallback
# ---------------------------------------------------------------------------

# Extension → taxonomy category mapping (matches taxonomy.yaml labels)
EXTENSION_CATEGORY_MAP = {
    # Personal photos (camera RAW formats) → Personal
    ".heic": "Personal", ".heif": "Personal", ".raw": "Personal",
    ".cr2": "Personal", ".nef": "Personal", ".arw": "Personal",
    ".dng": "Personal", ".orf": "Personal", ".rw2": "Personal",
    # Design tools → Design
    ".psd": "Design", ".ai": "Design", ".sketch": "Design",
    ".fig": "Design", ".xd": "Design", ".indd": "Design",
    ".svg": "Design", ".eps": "Design",
    # Source code & configs → Development
    ".py": "Development", ".js": "Development", ".ts": "Development",
    ".jsx": "Development", ".tsx": "Development", ".sh": "Development",
    ".rb": "Development", ".go": "Development", ".rs": "Development",
    ".java": "Development", ".c": "Development", ".cpp": "Development",
    ".h": "Development", ".swift": "Development", ".kt": "Development",
    ".json": "Development", ".yaml": "Development", ".yml": "Development",
    ".xml": "Development", ".toml": "Development", ".ini": "Development",
    ".cfg": "Development", ".conf": "Development", ".env": "Development",
    ".gitignore": "Development", ".dockerfile": "Development",
    # Office documents → Reference (could be anything — AI should ideally classify these)
    ".doc": "Reference", ".docx": "Reference",
    ".xls": "Reference", ".xlsx": "Reference",
    ".ppt": "Reference", ".pptx": "Reference",
    ".odt": "Reference", ".ods": "Reference", ".odp": "Reference",
    ".rtf": "Reference", ".pages": "Reference", ".numbers": "Reference",
    ".key": "Reference",
    # Media files → Media & Entertainment
    ".mp4": "Media & Entertainment", ".mov": "Media & Entertainment", ".avi": "Media & Entertainment",
    ".mkv": "Media & Entertainment", ".webm": "Media & Entertainment", ".flv": "Media & Entertainment",
    ".mp3": "Media & Entertainment", ".wav": "Media & Entertainment", ".flac": "Media & Entertainment",
    ".aac": "Media & Entertainment", ".ogg": "Media & Entertainment", ".m4a": "Media & Entertainment",
    # Archives & installers → Unsorted (need context to categorize properly)
    ".dmg": "Unsorted", ".pkg": "Unsorted", ".app": "Unsorted",
    ".zip": "Unsorted", ".tar": "Unsorted", ".gz": "Unsorted",
    ".rar": "Unsorted", ".7z": "Unsorted", ".bz2": "Unsorted",
    ".iso": "Unsorted", ".deb": "Unsorted", ".rpm": "Unsorted",
    ".exe": "Unsorted", ".msi": "Unsorted",
    # Finance (detected by AI, not by extension usually)
}


def _fallback_categorize(filepath: str) -> dict:
    """Categorize by extension when AI is unavailable. Uses taxonomy labels."""
    ext = Path(filepath).suffix.lower()
    filename = os.path.basename(filepath).lower()

    # Screenshot naming patterns → Reference (screenshots are usually reference material)
    if any(pat in filename for pat in ["screenshot", "screen shot", "screen_", "capture"]):
        return {"category": "Reference", "tags": ["screenshot"], "description": "Screen capture (extension fallback)", "confidence": 0.5}

    category = EXTENSION_CATEGORY_MAP.get(ext, "Unsorted")
    tag = ext.lstrip(".") if ext and ext != "(none)" else "unknown"
    return {
        "category": category,
        "tags": [tag] if tag else [],
        "description": f"Categorized by extension ({ext})",
        "confidence": 0.5 if category != "Unsorted" else 0.2,
    }


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_ai_response(response: str) -> Optional[dict]:
    """Parse JSON from AI response, handling common formatting issues."""
    text = response.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # Find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None

    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError:
        return None

    # Validate category against taxonomy — O(1) lookup
    category = _validate_category(data.get("category", "Unsorted"))

    tags = data.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).lower().strip() for t in tags[:3]]

    description = str(data.get("description", ""))[:200]
    confidence = float(data.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))

    # Override to Unsorted if confidence too low
    if confidence < CONFIDENCE_THRESHOLD:
        category = "Unsorted"

    return {
        "category": category,
        "tags": tags,
        "description": description,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Single file analysis dispatcher
# ---------------------------------------------------------------------------

def analyze_file(
    filepath: str,
    vision_model: str = VISION_MODEL,
    text_model: str = TEXT_MODEL,
    backend: str = "ollama",
) -> dict:
    """Analyze a single file and return categorization result.

    Args:
        filepath: Path to the file to analyze.
        vision_model: Ollama vision model name (only used when backend="ollama").
        text_model: Ollama text model name (only used when backend="ollama").
        backend: "openai" to use GPT-5 via OAuth, "ollama" for local models.
    """
    ext = Path(filepath).suffix.lower()
    filename = os.path.basename(filepath).lower()

    # Screenshot by filename pattern — skip expensive AI call regardless of backend
    # Still send to AI so it can classify the *content* (e.g., a screenshot of
    # a bank statement should be "Finance", not "Reference").  The filename hint
    # is only used as an absolute fallback when AI is unavailable.
    if ext in VISION_EXTENSIONS and any(
        pat in filename for pat in ["screenshot", "screen shot", "screen_", "capture"]
    ):
        # Let the AI classify the screenshot content
        if backend == "openai":
            result = _analyze_image_openai(filepath)
            if result:
                return result
        elif backend == "ollama":
            result = _analyze_image(filepath, vision_model)
            if result:
                return result
        # AI unavailable — fall back to generic Reference (screenshots are usually reference material)
        return {
            "category": "Reference",
            "tags": ["screenshot"],
            "description": "Screen capture (detected by filename, AI unavailable)",
            "confidence": 0.6,
        }

    if backend == "openai":
        return _analyze_file_openai(filepath, ext)
    else:
        return _analyze_file_ollama(filepath, ext, vision_model, text_model)


def _analyze_file_openai(filepath: str, ext: str) -> dict:
    """Route file analysis through OpenAI GPT-5."""
    # Images → GPT-5 vision
    if ext in VISION_EXTENSIONS:
        result = _analyze_image_openai(filepath)
        if result:
            return result
        return _fallback_categorize(filepath)

    # PDFs → extract text, then GPT-5 text
    if ext in PDF_EXTENSIONS:
        text = _extract_pdf_text(filepath)
        if text:
            result = _analyze_text_openai(filepath, text)
            if result:
                return result
        return _fallback_categorize(filepath)

    # Text files → GPT-5 text
    if ext in DOC_EXTENSIONS:
        text = _read_text_file(filepath)
        if text and len(text.strip()) > 20:
            result = _analyze_text_openai(filepath, text)
            if result:
                return result
        return _fallback_categorize(filepath)

    # Everything else → extension-based fallback
    return _fallback_categorize(filepath)


def _analyze_file_ollama(filepath: str, ext: str, vision_model: str, text_model: str) -> dict:
    """Route file analysis through local Ollama models (original behavior)."""
    # Images → vision model
    if ext in VISION_EXTENSIONS:
        result = _analyze_image(filepath, vision_model)
        if result:
            return result
        return _fallback_categorize(filepath)

    # PDFs → extract text, then text model
    if ext in PDF_EXTENSIONS:
        text = _extract_pdf_text(filepath)
        if text:
            result = _analyze_text(filepath, text, text_model)
            if result:
                return result
        return _fallback_categorize(filepath)

    # Text files → text model
    if ext in DOC_EXTENSIONS:
        text = _read_text_file(filepath)
        if text and len(text.strip()) > 20:
            result = _analyze_text(filepath, text, text_model)
            if result:
                return result
        return _fallback_categorize(filepath)

    # Everything else → extension-based fallback
    return _fallback_categorize(filepath)


# ---------------------------------------------------------------------------
# Main categorize function
# ---------------------------------------------------------------------------

def _resolve_backend(requested: str, json_output: bool = False) -> str:
    """Resolve which backend to actually use, with automatic fallback.

    Priority: requested backend → fallback chain.
    Returns "openai", "ollama", or "extension" (last resort).
    """
    if requested == "openai":
        if _openai_available():
            return "openai"
        if not json_output:
            sys.stderr.write(
                "  OpenAI backend unavailable (no ~/.codex/auth.json or invalid token).\n"
                "  Falling back to Ollama...\n"
            )
        if _ollama_available():
            return "ollama"
        if not json_output:
            sys.stderr.write("  Ollama also unavailable. Using extension-based fallback.\n")
        return "extension"

    if requested == "ollama":
        if _ollama_available():
            return "ollama"
        if not json_output:
            sys.stderr.write(
                "  Ollama is not running. Start it with: open -a Ollama\n"
                "  Falling back to extension-based categorization.\n"
            )
        return "extension"

    # Unknown backend name — try openai first
    return _resolve_backend("openai", json_output)


def categorize(
    directories: Optional[List[str]] = None,
    dry_run: bool = True,
    json_output: bool = False,
    db_path: Optional[str] = None,
    limit: int = 0,
    category_filter: Optional[str] = None,
    backend: Optional[str] = None,
) -> dict:
    """Categorize files using AI analysis.

    Args:
        directories: Not used (reads from database). Kept for CLI compat.
        dry_run: If True (default), only analyze and report. If False, update DB.
        json_output: If True, return machine-readable JSON.
        db_path: Override database path.
        limit: Max files to process (0 = all).
        category_filter: Only process files matching this extension type
                         ("images", "pdfs", "text", "all").
        backend: "openai" (GPT-5 via OAuth), "ollama" (local), or None (use default).

    Returns:
        Report dictionary with categorization results.
    """
    # Determine backend
    if backend is None:
        backend = DEFAULT_BACKEND
    active_backend = _resolve_backend(backend, json_output)

    if active_backend == "extension":
        # No AI available at all — still process files with extension fallback
        pass

    # For Ollama backend, check model availability
    vision_model = None
    text_model = None
    if active_backend == "ollama":
        vision_model = VISION_MODEL
        if not _model_available(vision_model):
            if _model_available(VISION_FALLBACK):
                vision_model = VISION_FALLBACK
                if not json_output:
                    sys.stderr.write(f"  Using fallback vision model: {vision_model}\n")
            else:
                if not json_output:
                    sys.stderr.write(
                        f"  Warning: No vision model found. Pull with: ollama pull {VISION_MODEL}\n"
                        f"  Image files will use extension-based fallback.\n"
                    )
                vision_model = None

        text_model = TEXT_MODEL
        if not _model_available(text_model):
            if not json_output:
                sys.stderr.write(
                    f"  Warning: Text model {text_model} not found. Pull with: ollama pull {text_model}\n"
                    f"  Text files will use extension-based fallback.\n"
                )
            text_model = None

    conn = get_connection(db_path) if db_path else get_connection()

    # Get uncategorized files from DB
    query = "SELECT path, size, extension FROM files WHERE category = '' AND status = 'scanned'"
    params = []

    if category_filter == "images":
        placeholders = ",".join("?" for _ in VISION_EXTENSIONS)
        query += f" AND extension IN ({placeholders})"
        params.extend(VISION_EXTENSIONS)
    elif category_filter == "pdfs":
        query += " AND extension = ?"
        params.append(".pdf")
    elif category_filter == "text":
        placeholders = ",".join("?" for _ in DOC_EXTENSIONS)
        query += f" AND extension IN ({placeholders})"
        params.extend(DOC_EXTENSIONS)

    query += " ORDER BY size ASC"  # Process smaller files first (faster feedback)

    if limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(query, params).fetchall()
    total_files = len(rows)

    if total_files == 0:
        if not json_output:
            print("\nNo uncategorized files found in database.")
            print("Run 'scan' first to add files to the database.\n")
        conn.close()
        return {"total_files": 0, "categorized": 0}

    # Print header
    backend_label = {
        "openai": f"OpenAI {OPENAI_MODEL} (ChatGPT Plus OAuth)",
        "ollama": "Ollama (local)",
        "extension": "Extension-based fallback (no AI)",
    }.get(active_backend, active_backend)

    if not json_output:
        sys.stderr.write(f"\n  Found {total_files:,} uncategorized files\n")
        sys.stderr.write(f"  Backend:      {backend_label}\n")
        if active_backend == "ollama":
            if vision_model:
                sys.stderr.write(f"  Vision model: {vision_model}\n")
            if text_model:
                sys.stderr.write(f"  Text model:   {text_model}\n")
        sys.stderr.write(f"  Mode:         {'dry-run (preview)' if dry_run else 'APPLY (updating database)'}\n\n")

    # ---------------------------------------------------------------
    # Partition files: text-batchable vs. non-batchable (images, etc.)
    # Text files (PDFs + documents) can be batched to reduce API calls.
    # Images require individual vision calls and cannot be batched.
    # ---------------------------------------------------------------
    TEXT_BATCHABLE_EXTS = PDF_EXTENSIONS | DOC_EXTENSIONS
    text_rows = []
    other_rows = []
    missing_count = 0

    for row in rows:
        if not os.path.exists(row["path"]):
            missing_count += 1
            continue
        if row["extension"] in TEXT_BATCHABLE_EXTS:
            text_rows.append(row)
        else:
            other_rows.append(row)

    # Process files
    progress = ProgressReporter(total=total_files, label="Categorizing")
    results = []
    category_counts = defaultdict(int)
    errors = missing_count
    skipped_no_model = 0
    total_time = 0.0
    batch_count = 0

    # Account for missing files in progress
    progress.update(missing_count)

    def _record_result(filepath, ext, size, result):
        """Helper to record a single result and update DB."""
        nonlocal errors
        category_counts[result["category"]] += 1
        file_result = {
            "path": filepath,
            "size": size,
            "extension": ext,
            **result,
        }
        results.append(file_result)
        if not dry_run:
            conn.execute(
                "UPDATE files SET category = ?, tags = ?, description = ?, status = 'categorized' WHERE path = ?",
                (result["category"], json.dumps(result["tags"]), result.get("description", ""), filepath),
            )
            if len(results) % 10 == 0:
                conn.commit()

    # ---------------------------------------------------------------
    # Phase A: Batch-process text files (PDFs + documents)
    # ---------------------------------------------------------------
    if text_rows and active_backend in ("openai", "ollama"):
        # Check if we have the text model for Ollama
        can_batch = True
        if active_backend == "ollama" and text_model is None:
            can_batch = False

        if can_batch:
            if not json_output:
                sys.stderr.write(f"  Batch-processing {len(text_rows):,} text files (batch size {BATCH_SIZE})...\n")

            # Process text files in batches
            for batch_start in range(0, len(text_rows), BATCH_SIZE):
                batch_rows = text_rows[batch_start:batch_start + BATCH_SIZE]

                # Prepare text content for the batch
                file_items = _prepare_text_batch(
                    [{"path": r["path"], "extension": r["extension"]} for r in batch_rows]
                )

                # Trim batch by total chars to stay within context limits
                trimmed_items = []
                total_chars = 0
                for fp, preview in file_items:
                    if total_chars + len(preview) > BATCH_MAX_CHARS:
                        break
                    trimmed_items.append((fp, preview))
                    total_chars += len(preview)

                # Paths that got into the batch
                batched_paths = {fp for fp, _ in trimmed_items}

                # Run batch API call
                if trimmed_items:
                    batch_start_time = time.time()
                    try:
                        if active_backend == "openai":
                            batch_results = _batch_analyze_text_openai(trimmed_items)
                        else:
                            effective_text = text_model if text_model else TEXT_MODEL
                            batch_results = _batch_analyze_text_ollama(trimmed_items, effective_text)
                        batch_count += 1
                    except Exception as e:
                        if not json_output:
                            sys.stderr.write(f"\n  Batch error: {e}\n")
                        batch_results = {fp: None for fp, _ in trimmed_items}
                        errors += 1
                    batch_elapsed = time.time() - batch_start_time
                    total_time += batch_elapsed

                    # Record batch results
                    for fp, _ in trimmed_items:
                        result = batch_results.get(fp)
                        if result is None:
                            result = _fallback_categorize(fp)
                            errors += 1
                        row_info = next((r for r in batch_rows if r["path"] == fp), None)
                        if row_info:
                            _record_result(fp, row_info["extension"], row_info["size"], result)
                        progress.update()

                # Process files that didn't make it into the batch individually
                for row in batch_rows:
                    fp = row["path"]
                    if fp in batched_paths:
                        continue
                    # Fall through to single-file analysis
                    start = time.time()
                    try:
                        if active_backend == "openai":
                            result = analyze_file(fp, backend="openai")
                        else:
                            effective_vision = vision_model if vision_model else VISION_MODEL
                            effective_text = text_model if text_model else TEXT_MODEL
                            result = analyze_file(fp, vision_model=effective_vision,
                                                  text_model=effective_text, backend="ollama")
                    except Exception as e:
                        if not json_output:
                            sys.stderr.write(f"\n  Error analyzing {fp}: {e}\n")
                        result = _fallback_categorize(fp)
                        errors += 1
                    total_time += time.time() - start
                    _record_result(fp, row["extension"], row["size"], result)
                    progress.update()
        else:
            # No text model — fallback all text files
            for row in text_rows:
                result = _fallback_categorize(row["path"])
                skipped_no_model += 1
                _record_result(row["path"], row["extension"], row["size"], result)
                progress.update()
    elif text_rows:
        # extension backend — no AI
        for row in text_rows:
            result = _fallback_categorize(row["path"])
            skipped_no_model += 1
            _record_result(row["path"], row["extension"], row["size"], result)
            progress.update()

    # ---------------------------------------------------------------
    # Phase B: Process non-text files individually (images, etc.)
    # Images require vision model — cannot be batched.
    # ---------------------------------------------------------------
    for row in other_rows:
        filepath = row["path"]
        ext = row["extension"]

        if active_backend == "extension":
            result = _fallback_categorize(filepath)
            skipped_no_model += 1
        elif active_backend == "openai":
            start = time.time()
            try:
                result = analyze_file(filepath, backend="openai")
            except Exception as e:
                if not json_output:
                    sys.stderr.write(f"\n  Error analyzing {filepath}: {e}\n")
                result = _fallback_categorize(filepath)
                errors += 1
            total_time += time.time() - start
        else:
            # Ollama backend
            if ext in VISION_EXTENSIONS and vision_model is None:
                result = _fallback_categorize(filepath)
                skipped_no_model += 1
            else:
                start = time.time()
                try:
                    effective_vision = vision_model if vision_model else VISION_MODEL
                    effective_text = text_model if text_model else TEXT_MODEL
                    result = analyze_file(
                        filepath,
                        vision_model=effective_vision,
                        text_model=effective_text,
                        backend="ollama",
                    )
                except Exception as e:
                    if not json_output:
                        sys.stderr.write(f"\n  Error analyzing {filepath}: {e}\n")
                    result = _fallback_categorize(filepath)
                    errors += 1
                total_time += time.time() - start

        _record_result(filepath, ext, row["size"], result)
        progress.update()

    if not dry_run:
        conn.commit()

    progress.finish()
    conn.close()

    # Build report — use dynamic categories from taxonomy
    valid_cats = _get_valid_categories()
    avg_time = total_time / max(len(results), 1)
    report = {
        "dry_run": dry_run,
        "backend": active_backend,
        "total_files": total_files,
        "categorized": len(results),
        "errors": errors,
        "skipped_no_model": skipped_no_model,
        "avg_time_per_file": round(avg_time, 2),
        "batch_calls": batch_count,
        "text_files_batched": len(text_rows),
        "categories": [
            {"category": cat, "count": category_counts.get(cat, 0)}
            for cat in valid_cats
            if category_counts.get(cat, 0) > 0
        ],
        "low_confidence": sum(1 for r in results if r["confidence"] < CONFIDENCE_THRESHOLD),
        "results": results[:100] if not json_output else results,  # Limit for display
    }

    if not json_output:
        _print_report(report, dry_run)
    else:
        # For JSON, strip results to keep output manageable
        output = {k: v for k, v in report.items() if k != "results"}
        output["sample_results"] = results[:20]
        print(json.dumps(output, indent=2))

    return report


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def _print_report(report: dict, dry_run: bool) -> None:
    """Print a human-readable categorization report."""
    print("\n" + "=" * 60)
    print("  AI CATEGORIZATION REPORT")
    print("=" * 60)
    backend = report.get("backend", "unknown")
    backend_display = {
        "openai": f"OpenAI {OPENAI_MODEL} (ChatGPT Plus OAuth)",
        "ollama": "Ollama (local LLMs)",
        "extension": "Extension-based (no AI)",
    }.get(backend, backend)
    print(f"  Backend:        {backend_display}")
    print(f"  Mode:           {'Dry-run (preview)' if dry_run else 'Applied'}")
    print(f"  Files analyzed: {report['categorized']:,}")
    print(f"  Avg time/file:  {report['avg_time_per_file']:.1f}s")
    if report.get("batch_calls", 0) > 0:
        print(f"  Batch API calls: {report['batch_calls']:,} (covering {report.get('text_files_batched', 0):,} text files)")
    if report["errors"]:
        print(f"  Errors:         {report['errors']:,}")
    if report["skipped_no_model"]:
        print(f"  Fallback (no model): {report['skipped_no_model']:,}")
    print()

    # Category breakdown
    cats = report["categories"]
    if cats:
        print("  Categories:")
        print("  " + "-" * 40)
        for item in cats:
            bar = "#" * min(item["count"], 40)
            print(f"    {item['category']:>15s}  {item['count']:>5,}  {bar}")
        print()

    # Low confidence
    if report["low_confidence"]:
        print(f"  Low confidence (→ Unsorted): {report['low_confidence']:,} files")
        print()

    # Sample results (first 20)
    results = report.get("results", [])
    if results:
        shown = min(len(results), 20)
        print(f"  Sample Results ({shown} of {report['categorized']:,}):")
        print("  " + "-" * 50)
        for r in results[:shown]:
            fname = os.path.basename(r["path"])
            if len(fname) > 35:
                fname = fname[:32] + "..."
            tags_str = ", ".join(r.get("tags", []))
            conf = r.get("confidence", 0)
            print(f"    {fname:<35s} → {r['category']:<13s} [{conf:.0%}] {tags_str}")
        if report["categorized"] > shown:
            print(f"    ... {report['categorized'] - shown:,} more files")
        print()

    if dry_run:
        print("  This was a DRY RUN — no changes were made.")
        print("  Run with --apply to update the database.")

    print("=" * 60)
