"""Custom project-aware tagger — multi-signal classification using a YAML taxonomy.

Signal priority:
  1. File path matching (near 100% confidence)
  2. File content scanning — text extraction + keyword search (primary signal)
  3. Filename keyword matching (secondary)
  4. AI vision description → keyword matching (for images with no text)
  5. Fallback → Unsorted
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from database import get_connection
from categorizer import (
    VISION_EXTENSIONS,
    PDF_EXTENSIONS,
    DOC_EXTENSIONS,
    MAX_TEXT_LENGTH,
    _extract_pdf_text,
    _read_text_file,
    _resize_image_for_llava,
    _ollama_available,
    _ollama_generate,
    _model_available,
    _openai_available,
    analyze_file as categorizer_analyze_file,
    VISION_MODEL,
    VISION_FALLBACK,
    TEXT_MODEL,
    DEFAULT_BACKEND,
)
from utils import ProgressReporter


# ---------------------------------------------------------------------------
# Taxonomy loader
# ---------------------------------------------------------------------------

def load_taxonomy(taxonomy_path: str) -> Dict:
    """Load and validate the custom taxonomy YAML."""
    with open(taxonomy_path, "r") as f:
        data = yaml.safe_load(f)

    categories = data.get("categories", {})
    if not categories:
        raise ValueError(f"No categories found in {taxonomy_path}")

    # Sort by priority (descending) so higher-priority categories are checked first
    sorted_cats = sorted(
        categories.items(),
        key=lambda x: x[1].get("priority", 0),
        reverse=True,
    )

    # Pre-compile path patterns and content keywords as lowercase
    for key, cat in sorted_cats:
        cat["_path_patterns"] = [p.lower() for p in cat.get("path_patterns", [])]
        cat["_content_keywords"] = [k.lower() for k in cat.get("content_keywords", [])]
        cat["_id"] = key

    return {"sorted": sorted_cats, "raw": categories}


# ---------------------------------------------------------------------------
# Signal 1: Path matching
# ---------------------------------------------------------------------------

def match_by_path(filepath: str, taxonomy: Dict) -> Optional[Tuple[str, str, float]]:
    """Check if the file path contains any project-specific patterns.

    Returns (category_id, label, confidence) or None.
    """
    path_lower = filepath.lower()

    for cat_id, cat in taxonomy["sorted"]:
        for pattern in cat["_path_patterns"]:
            if pattern in path_lower:
                return (cat_id, cat["label"], 0.95)

    return None


# ---------------------------------------------------------------------------
# Signal 2: Content scanning (PRIMARY signal per {{USER_NAME}})
# ---------------------------------------------------------------------------

def _ocr_image(filepath: str) -> Optional[str]:
    """Extract text from an image using Tesseract OCR.

    Returns extracted text or None if tesseract isn't available or finds no text.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["tesseract", filepath, "stdout", "--psm", "3", "-l", "eng"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.strip()
            # Tesseract sometimes returns garbage on non-text images — filter short junk
            if len(text) >= 10:
                return text[:MAX_TEXT_LENGTH]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def extract_content(filepath: str) -> Optional[str]:
    """Extract readable text from a file for keyword scanning."""
    ext = Path(filepath).suffix.lower()

    # Images — OCR via Tesseract (screenshots are full of classifiable text)
    if ext in VISION_EXTENSIONS:
        return _ocr_image(filepath)

    # PDF
    if ext in PDF_EXTENSIONS:
        return _extract_pdf_text(filepath)

    # Text-based files
    if ext in DOC_EXTENSIONS:
        return _read_text_file(filepath)

    # Office docs — try to extract text via textutil (macOS built-in)
    if ext in {".doc", ".docx", ".rtf", ".pages"}:
        try:
            import subprocess
            result = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", filepath],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout[:MAX_TEXT_LENGTH]
        except Exception:
            pass

    # Spreadsheets — read as text if possible (CSV, TSV)
    if ext in {".csv", ".tsv"}:
        return _read_text_file(filepath)

    # Excel — try openpyxl if available
    if ext in {".xlsx", ".xls", ".xlsm"}:
        try:
            import subprocess
            # Use mdls to get metadata as a rough content signal
            result = subprocess.run(
                ["mdls", "-name", "kMDItemTextContent", filepath],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                text = result.stdout.replace("kMDItemTextContent =", "").strip().strip('"')
                if text and text != "(null)":
                    return text[:MAX_TEXT_LENGTH]
        except Exception:
            pass

    return None


def match_by_content(filepath: str, taxonomy: Dict) -> Optional[Tuple[str, str, float, List[str]]]:
    """Scan file content for taxonomy keywords.

    Returns (category_id, label, confidence, matched_keywords) or None.
    """
    text = extract_content(filepath)
    if not text or len(text.strip()) < 10:
        return None

    text_lower = text.lower()

    # Score each category by keyword hits
    scores: List[Tuple[str, str, int, List[str]]] = []
    for cat_id, cat in taxonomy["sorted"]:
        matched = []
        for keyword in cat["_content_keywords"]:
            if keyword in text_lower:
                matched.append(keyword)
        if matched:
            scores.append((cat_id, cat["label"], len(matched), matched))

    if not scores:
        return None

    # Sort by number of keyword hits (descending)
    scores.sort(key=lambda x: x[2], reverse=True)
    best = scores[0]

    # Confidence scales with number of keyword hits
    hit_count = best[2]
    if hit_count >= 3:
        confidence = 0.92
    elif hit_count >= 2:
        confidence = 0.85
    else:
        confidence = 0.72

    # If there's a close second, lower confidence (ambiguous)
    if len(scores) > 1 and scores[1][2] >= best[2] - 1:
        confidence -= 0.10

    return (best[0], best[1], confidence, best[3])


# ---------------------------------------------------------------------------
# Signal 3: Filename keyword matching
# ---------------------------------------------------------------------------

def match_by_filename(filepath: str, taxonomy: Dict) -> Optional[Tuple[str, str, float]]:
    """Check if the filename contains project-specific keywords."""
    filename_lower = os.path.basename(filepath).lower()
    # Also check parent directory name
    parent_lower = os.path.basename(os.path.dirname(filepath)).lower()
    combined = filename_lower + " " + parent_lower

    for cat_id, cat in taxonomy["sorted"]:
        for pattern in cat["_path_patterns"]:
            if pattern in combined:
                return (cat_id, cat["label"], 0.80)
        # Also check content keywords against filename (some are descriptive)
        for keyword in cat["_content_keywords"]:
            if len(keyword) >= 5 and keyword in combined:  # Skip short keywords to avoid false positives
                return (cat_id, cat["label"], 0.70)

    return None


# ---------------------------------------------------------------------------
# Signal 4: AI vision → keyword matching (images only)
# ---------------------------------------------------------------------------

AI_DESCRIBE_PROMPT = """Describe this image in 2-3 sentences. Focus on:
- What type of content it shows (product photo, screenshot, logo, document, etc.)
- Any visible text, brand names, or business names
- Key objects or subjects visible
- If it's a screenshot, what application or website is shown

Be specific and factual. Just describe what you see."""


def match_by_ai_vision(
    filepath: str,
    taxonomy: Dict,
    vision_model: str,
) -> Optional[Tuple[str, str, float, str]]:
    """Use AI vision to describe an image, then match description against taxonomy keywords.

    Returns (category_id, label, confidence, ai_description) or None.
    """
    ext = Path(filepath).suffix.lower()
    if ext not in VISION_EXTENSIONS:
        return None

    img_b64 = _resize_image_for_llava(filepath)
    if not img_b64:
        return None

    # Get AI description
    description = _ollama_generate(vision_model, AI_DESCRIBE_PROMPT, images=[img_b64])
    if not description:
        return None

    description_lower = description.lower()

    # Score each category by keyword hits in the AI description
    scores: List[Tuple[str, str, int, List[str]]] = []
    for cat_id, cat in taxonomy["sorted"]:
        matched = []
        for keyword in cat["_content_keywords"]:
            if keyword in description_lower:
                matched.append(keyword)
        # Also check path patterns as potential content descriptors
        for pattern in cat["_path_patterns"]:
            if len(pattern) >= 4 and pattern in description_lower:
                matched.append(pattern)
        if matched:
            scores.append((cat_id, cat["label"], len(matched), matched))

    if not scores:
        return None

    scores.sort(key=lambda x: x[2], reverse=True)
    best = scores[0]

    confidence = 0.65 if best[2] >= 2 else 0.55
    return (best[0], best[1], confidence, description.strip())


# ---------------------------------------------------------------------------
# Single file classifier (multi-signal)
# ---------------------------------------------------------------------------

def classify_file(
    filepath: str,
    taxonomy: Dict,
    vision_model: Optional[str] = None,
    use_ai: bool = True,
    backend: str = "ollama",
) -> Dict:
    """Classify a single file using the multi-signal approach.

    When backend="openai", Signal 4 uses GPT-5 via Codex OAuth for superior
    content understanding. When backend="ollama", uses local LLaVA as before.

    Returns dict with: project, label, confidence, signal, tags, description
    """
    result = {
        "project": "unsorted",
        "label": "Unsorted",
        "confidence": 0.0,
        "signal": "none",
        "tags": [],
        "description": "",
    }

    # Signal 1: Path matching (fastest, most reliable)
    path_match = match_by_path(filepath, taxonomy)
    if path_match:
        cat_id, label, conf = path_match
        return {
            "project": cat_id,
            "label": label,
            "confidence": conf,
            "signal": "path",
            "tags": [label.lower().replace(" & ", "-").replace(" ", "-")],
            "description": f"Matched by file path",
        }

    # Signal 2: Content scanning (primary signal for non-path matches)
    content_match = match_by_content(filepath, taxonomy)
    if content_match:
        cat_id, label, conf, keywords = content_match
        return {
            "project": cat_id,
            "label": label,
            "confidence": conf,
            "signal": "content",
            "tags": [label.lower().replace(" & ", "-").replace(" ", "-")] + keywords[:2],
            "description": f"Content keywords: {', '.join(keywords[:3])}",
        }

    # Signal 3: Filename matching
    filename_match = match_by_filename(filepath, taxonomy)
    if filename_match:
        cat_id, label, conf = filename_match
        return {
            "project": cat_id,
            "label": label,
            "confidence": conf,
            "signal": "filename",
            "tags": [label.lower().replace(" & ", "-").replace(" ", "-")],
            "description": f"Matched by filename/parent directory",
        }

    # Signal 4: AI classification (images, PDFs, text files)
    if use_ai:
        if backend == "openai":
            # Use GPT-5 via Codex OAuth — handles vision + text in one model
            ai_result = categorizer_analyze_file(filepath, backend="openai")
            if ai_result and ai_result.get("category", "Unsorted") != "Unsorted":
                label = ai_result["category"]
                # Find the taxonomy cat_id for this label
                cat_id = "unsorted"
                for cid, cat in taxonomy["sorted"]:
                    if cat["label"] == label:
                        cat_id = cid
                        break
                return {
                    "project": cat_id,
                    "label": label,
                    "confidence": ai_result.get("confidence", 0.8),
                    "signal": "ai-openai",
                    "tags": ai_result.get("tags", [label.lower().replace(" & ", "-").replace(" ", "-")]),
                    "description": ai_result.get("description", "")[:150],
                }
        elif vision_model:
            # Ollama: images only
            ext = Path(filepath).suffix.lower()
            if ext in VISION_EXTENSIONS:
                ai_match = match_by_ai_vision(filepath, taxonomy, vision_model)
                if ai_match:
                    cat_id, label, conf, ai_desc = ai_match
                    return {
                        "project": cat_id,
                        "label": label,
                        "confidence": conf,
                        "signal": "ai-vision",
                        "tags": [label.lower().replace(" & ", "-").replace(" ", "-")],
                        "description": ai_desc[:150],
                    }

    # No match
    return result


# ---------------------------------------------------------------------------
# Main reclassify function
# ---------------------------------------------------------------------------

def reclassify(
    taxonomy_path: str,
    dry_run: bool = True,
    json_output: bool = False,
    db_path: Optional[str] = None,
    limit: int = 0,
    use_ai: bool = True,
    backend: str = DEFAULT_BACKEND,
    directory: Optional[str] = None,
    categories: Optional[List[str]] = None,
) -> Dict:
    """Reclassify all files using the custom taxonomy.

    This overwrites the generic category with a project-specific one.
    """
    # Load taxonomy
    taxonomy = load_taxonomy(taxonomy_path)
    cat_count = len(taxonomy["sorted"])

    if not json_output:
        print(f"\n  Loaded taxonomy: {cat_count} categories from {os.path.basename(taxonomy_path)}")
        for cat_id, cat in taxonomy["sorted"]:
            kw_count = len(cat["_content_keywords"])
            pp_count = len(cat["_path_patterns"])
            print(f"    {cat['label']:<25s}  {pp_count} path patterns, {kw_count} content keywords")
        print()

    # Check AI availability
    vision_model = None
    if use_ai:
        if backend == "openai":
            if _openai_available():
                if not json_output:
                    print(f"  AI backend: OpenAI GPT-5 (ChatGPT Plus OAuth)")
            else:
                # Fall back to Ollama
                backend = "ollama"
                if not json_output:
                    print("  OpenAI unavailable, falling back to Ollama")
        if backend == "ollama":
            if _ollama_available():
                if _model_available(VISION_MODEL):
                    vision_model = VISION_MODEL
                elif _model_available(VISION_FALLBACK):
                    vision_model = VISION_FALLBACK
                if vision_model and not json_output:
                    print(f"  AI vision model: {vision_model} (for images without text)")
            if not vision_model and not json_output:
                print("  AI vision: disabled (Ollama not available or no model)")
        print()

    conn = get_connection(db_path) if db_path else get_connection()

    # Get files to reclassify (optionally scoped to a directory)
    query = "SELECT path, size, extension, category FROM files WHERE status != 'staged'"
    params = []

    if directory:
        # Normalize path and add trailing slash for LIKE match
        dir_path = os.path.abspath(os.path.expanduser(directory))
        if not dir_path.endswith("/"):
            dir_path += "/"
        query += " AND path LIKE ?"
        params.append(dir_path + "%")
        if not json_output:
            print(f"  Directory filter: {dir_path}")

    if categories:
        placeholders = ",".join("?" for _ in categories)
        query += f" AND category IN ({placeholders})"
        params.extend(categories)
        if not json_output:
            print(f"  Category filter: {', '.join(categories)}")

    if limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(query, params).fetchall()
    total_files = len(rows)

    if total_files == 0:
        if not json_output:
            print("  No files in database. Run 'scan' first.")
        conn.close()
        return {"total_files": 0}

    if not json_output:
        mode_str = "DRY-RUN (preview)" if dry_run else "APPLY (updating database)"
        print(f"  Reclassifying {total_files:,} files  |  Mode: {mode_str}")
        print()

    # Process files
    progress = ProgressReporter(total=total_files, label="Classifying")
    results = []
    project_counts = defaultdict(int)
    signal_counts = defaultdict(int)
    changed = 0
    errors = 0
    total_time = 0.0

    for row in rows:
        filepath = row["path"]
        old_category = row["category"] or ""

        if not os.path.exists(filepath):
            errors += 1
            progress.update()
            continue

        start = time.time()
        try:
            result = classify_file(filepath, taxonomy, vision_model=vision_model, use_ai=use_ai, backend=backend)
        except Exception as e:
            if not json_output:
                sys.stderr.write(f"\n  Error classifying {filepath}: {e}\n")
            result = {"project": "unsorted", "label": "Unsorted", "confidence": 0.0,
                      "signal": "error", "tags": [], "description": str(e)[:100]}
            errors += 1
        elapsed = time.time() - start
        total_time += elapsed

        project_counts[result["label"]] += 1
        signal_counts[result["signal"]] += 1

        is_changed = result["label"] != old_category
        if is_changed:
            changed += 1

        file_result = {
            "path": filepath,
            "old_category": old_category,
            "new_project": result["project"],
            "new_label": result["label"],
            "confidence": result["confidence"],
            "signal": result["signal"],
            "tags": result["tags"],
            "description": result["description"],
            "changed": is_changed,
        }
        results.append(file_result)

        # Update database
        if not dry_run:
            conn.execute(
                "UPDATE files SET category = ?, tags = ?, description = ?, status = 'categorized' WHERE path = ?",
                (result["label"], json.dumps(result["tags"]), result.get("description", ""), filepath),
            )
            if len(results) % 25 == 0:
                conn.commit()

        progress.update()

    if not dry_run:
        conn.commit()

    progress.finish()
    conn.close()

    # Build report
    avg_time = total_time / max(total_files, 1)
    report = {
        "dry_run": dry_run,
        "total_files": total_files,
        "changed": changed,
        "errors": errors,
        "avg_time_per_file": round(avg_time, 3),
        "project_counts": dict(sorted(project_counts.items(), key=lambda x: x[1], reverse=True)),
        "signal_counts": dict(sorted(signal_counts.items(), key=lambda x: x[1], reverse=True)),
        "results": results,
    }

    if not json_output:
        _print_reclassify_report(report, dry_run)
    else:
        output = {k: v for k, v in report.items() if k != "results"}
        output["sample_results"] = [
            {k: v for k, v in r.items()}
            for r in results[:30]
        ]
        print(json.dumps(output, indent=2))

    return report


def _print_reclassify_report(report: Dict, dry_run: bool) -> None:
    """Print human-readable reclassification report."""
    print("\n" + "=" * 65)
    print("  PROJECT RECLASSIFICATION REPORT")
    print("=" * 65)
    print(f"  Mode:            {'Dry-run (preview)' if dry_run else 'Applied'}")
    print(f"  Total files:     {report['total_files']:,}")
    print(f"  Reclassified:    {report['changed']:,}")
    print(f"  Avg time/file:   {report['avg_time_per_file']:.3f}s")
    if report["errors"]:
        print(f"  Errors:          {report['errors']:,}")
    print()

    # Project breakdown
    print("  Projects:")
    print("  " + "-" * 55)
    for label, count in report["project_counts"].items():
        bar = "#" * min(count // 5 + 1, 40)
        print(f"    {label:<25s}  {count:>5,}  {bar}")
    print()

    # Signal breakdown
    print("  Classification Signals:")
    print("  " + "-" * 55)
    for signal, count in report["signal_counts"].items():
        pct = count / max(report["total_files"], 1) * 100
        print(f"    {signal:<15s}  {count:>5,}  ({pct:.1f}%)")
    print()

    # Sample of changed files
    changed_results = [r for r in report["results"] if r["changed"]]
    if changed_results:
        shown = min(len(changed_results), 25)
        print(f"  Sample Changes ({shown} of {len(changed_results):,}):")
        print("  " + "-" * 55)
        for r in changed_results[:shown]:
            fname = os.path.basename(r["path"])
            if len(fname) > 30:
                fname = fname[:27] + "..."
            old = r["old_category"] or "(none)"
            new = r["new_label"]
            sig = r["signal"]
            print(f"    {fname:<30s}  {old:<15s} → {new:<20s}  [{sig}]")
        if len(changed_results) > shown:
            print(f"    ... {len(changed_results) - shown:,} more changes")
        print()

    if dry_run:
        print("  This was a DRY RUN — no changes were made.")
        print("  Run with --apply to update the database.")

    print("=" * 65)
