"""
Provenance Logger for the Media Workflow Engine.

Tracks what produced each generated asset: model, prompt, config hash,
reference images, evaluation scores, timestamps, and iteration counts.

Each generated asset gets a .provenance.json sidecar file alongside it.
All records are also appended to a central audit log (JSONL format).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Central audit log location
AUDIT_LOG_DIR = Path("{{CATALYST_ROOT}}/tools/media-engine/eval/audit-log")
AUDIT_LOG_PATH = AUDIT_LOG_DIR / "audit.jsonl"


class ProvenanceLogger:
    """
    Records provenance metadata for generated media assets.

    Two output locations:
      1. Sidecar file: {output_path}.provenance.json (next to the asset)
      2. Audit log: eval/audit-log/audit.jsonl (append-only JSONL)
    """

    def __init__(self, audit_log_path: str | Path | None = None) -> None:
        self.audit_log_path = Path(audit_log_path) if audit_log_path else AUDIT_LOG_PATH

    def record_provenance(
        self,
        output_path: str,
        config: dict[str, Any],
        prompt: str,
        eval_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a provenance record for a generated asset.

        Writes:
          - A .provenance.json sidecar file next to the output
          - An entry in the append-only audit log

        Args:
            output_path: Path to the generated asset.
            config: The resolved workflow config that produced it.
            prompt: The generation prompt used.
            eval_result: Evaluation results dict from the evaluator
                         (output_path, final_score, iterations, eval_log).

        Returns:
            The provenance record dict.
        """
        provenance_config = config.get("provenance", {})
        if not provenance_config.get("enabled", True):
            return {}

        record = self._build_record(output_path, config, prompt, eval_result)

        # Write sidecar file
        self._write_sidecar(output_path, record)

        # Append to audit log
        self._append_audit_log(record)

        return record

    # ------------------------------------------------------------------
    # Record construction
    # ------------------------------------------------------------------

    def _build_record(
        self,
        output_path: str,
        config: dict[str, Any],
        prompt: str,
        eval_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the provenance metadata record."""
        provenance_config = config.get("provenance", {})

        record: dict[str, Any] = {
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "output_path": output_path,
            "model": config.get("model", "unknown"),
            "media_type": config.get("media_type", "image"),
            "auth_provider": config.get("auth_provider", "unknown"),
            "prompt": prompt,
            "workflow_name": config.get("name", ""),
            "iteration_count": eval_result.get("iterations", 1),
        }

        # Config hash (deterministic snapshot of the resolved config)
        if provenance_config.get("snapshot_config", True):
            record["resolved_config_hash"] = self._hash_config(config)

        # Evaluation scores
        if provenance_config.get("log_eval_scores", True):
            record["eval_scores"] = {
                "final_score": eval_result.get("final_score", 0.0),
                "eval_log": eval_result.get("eval_log", []),
            }

        # Reference images used
        consistency = config.get("consistency", {})
        ref_count = consistency.get("reference_images", 0)
        if ref_count > 0:
            record["reference_images"] = {
                "count": ref_count,
                "style_weight": consistency.get("style_weight", 0.5),
                "character_lock": consistency.get("character_lock", False),
            }

        # Generation parameters
        gen = config.get("generation", {})
        record["generation_params"] = {
            "resolution": gen.get("resolution", "2K"),
            "aspect_ratios": gen.get("aspect_ratios", ["1:1"]),
        }

        # Add video-specific params if applicable
        if config.get("media_type") == "video":
            record["generation_params"]["duration"] = gen.get("duration")
            record["generation_params"]["fps"] = gen.get("fps")
            record["generation_params"]["camera_motion"] = gen.get("camera_motion")

        # Add vector-specific params if applicable
        if config.get("media_type") == "vector":
            vec = config.get("vector", {})
            record["vector_params"] = {
                "grid_size": vec.get("grid_size"),
                "stroke_weight": vec.get("stroke_weight"),
                "corner_radius": vec.get("corner_radius"),
                "icon_style": vec.get("icon_style"),
                "export_formats": vec.get("export_formats", []),
                "type": vec.get("type", ""),
            }
            record["model"] = "local/svgwrite"  # Vector is local, no external model

            # Phase 3: Track print-ready operations and Inkscape usage
            print_cfg = vec.get("print", {})
            is_print_ready = (
                print_cfg.get("print_ready", False)
                or vec.get("print_ready", False)
                or config.get("_print_ready", False)
            )
            if is_print_ready:
                record["print_production"] = {
                    "print_ready": True,
                    "bleed_mm": print_cfg.get("bleed_mm", vec.get("bleed_mm", 3.0)),
                    "cmyk": print_cfg.get("cmyk", vec.get("cmyk", False)),
                    "text_to_path": print_cfg.get("text_to_path", vec.get("text_to_path", False)),
                    "color_profile": print_cfg.get("color_profile", vec.get("color_profile")),
                }
                # Check Inkscape availability for the record
                try:
                    from engine.inkscape_cli import get_inkscape
                    inkscape = get_inkscape()
                    record["print_production"]["inkscape_available"] = inkscape.is_available()
                    if inkscape.is_available():
                        record["print_production"]["inkscape_version"] = inkscape.get_version()
                except Exception:
                    record["print_production"]["inkscape_available"] = False

        # YouTube source metadata (injected by CLI when --yt-source is used)
        yt_source = config.get("_youtube_source")
        if yt_source and isinstance(yt_source, dict):
            record["youtube_source"] = {
                "video_id": yt_source.get("video_id", ""),
                "url": yt_source.get("url", ""),
                "title": yt_source.get("title", ""),
                "channel": yt_source.get("channel", ""),
                "duration": yt_source.get("duration", ""),
                "upload_date": yt_source.get("upload_date", ""),
                "transcript_length": yt_source.get("transcript_length", 0),
                "chapter_count": yt_source.get("chapter_count", 0),
            }

        # Output file info
        output = Path(output_path)
        if output.exists():
            record["file_info"] = {
                "size_bytes": output.stat().st_size,
                "format": output.suffix.lstrip("."),
            }

        return record

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_sidecar(output_path: str, record: dict[str, Any]) -> None:
        """Write a .provenance.json sidecar file next to the generated asset."""
        sidecar_path = Path(output_path + ".provenance.json")

        try:
            with open(sidecar_path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, default=str)
        except OSError as exc:
            # Log but don't fail -- provenance is non-critical
            print(f"Warning: Could not write provenance sidecar: {exc}")

    def _append_audit_log(self, record: dict[str, Any]) -> None:
        """Append a record to the central audit log (JSONL format)."""
        # Ensure directory exists
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            print(f"Warning: Could not append to audit log: {exc}")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_config(config: dict[str, Any]) -> str:
        """
        Generate a deterministic SHA-256 hash of the resolved config.

        Excludes volatile fields (output paths, timestamps) so that
        identical configurations produce identical hashes.
        """
        # Create a copy without volatile fields
        hashable = {
            k: v for k, v in config.items()
            if k not in ("output", "_capsule_name", "_runtime")
        }

        # Sort keys for determinism
        config_str = json.dumps(hashable, sort_keys=True, default=str)
        return hashlib.sha256(config_str.encode("utf-8")).hexdigest()[:16]
