#\!/usr/bin/env python3
import argparse, json, os, shutil, sys
from pathlib import Path
import yaml

ROOT = Path("{{CATALYST_ROOT}}")
CAPS = ROOT / "capsules"

def load_spec(cap: Path):
    y = cap / "spec" / "requirements.yaml"
    if not y.exists(): return None
    try: return yaml.safe_load(y.read_text()) or {}
    except Exception: return {}

def target_path(cap: Path, branch: str, targets):
    targets = targets or []
    if branch == "automation":
        if "n8n" in targets: return cap/"src"/"automation"/"n8n"
        if "shortcuts" in targets: return cap/"src"/"automation"/"shortcuts"
        # default macOS automation
        return cap/"src"/"automation"/"macos"/"python"
    if branch == "app":
        if "ios_app" in targets: return cap/"src"/"app"/"ios"
        if "macos_app" in targets: return cap/"src"/"app"/"macos"
        return cap/"src"/"app"/"macos"
    if branch == "web":
        if "site" in targets: return cap/"src"/"web"/"site"
        if "shopify" in targets: return cap/"src"/"web"/"shopify"
        return cap/"src"/"web"/"app"
    return cap/"src"/"misc"

SKIP_DIRS = {".git",".idea",".vscode","node_modules","dist","build",".next",".nuxt",".vercel","__pycache__"}

def lone_top_level_folder(src_root: Path):
    if not src_root.exists(): return None
    children = [p for p in src_root.iterdir() if p.is_dir() and p.name not in SKIP_DIRS]
    files = [p for p in src_root.iterdir() if p.is_file()]
    # if there's exactly one meaningful folder and few/no files at top level, treat as the project root
    if len(children) == 1 and len(files) == 0:
        return children[0]
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="Apply changes (otherwise dry-run)")
    args = ap.parse_args()

    changed = 0; skipped = 0
    for cap in sorted([d for d in CAPS.iterdir() if d.is_dir()]):
        spec = load_spec(cap) or {}
        proj = spec.get("project") or {}
        branch = (proj.get("branch") or "automation").strip()
        targets = proj.get("targets") or []
        dest_base = target_path(cap, branch, targets)

        src_root = cap/"src"
        # If dest already contains something, skip to avoid clobber
        if dest_base.exists() and any(dest_base.iterdir()):
            skipped += 1
            print(f"[SKIP] {cap.name}: target already populated -> {dest_base}")
            continue

        # Heuristic: if src has a single real folder, treat that as the project, move it under dest_base/<name>
        candidate = lone_top_level_folder(src_root)
        if candidate:
            dest = dest_base / candidate.name
            print(f"[PLAN] {cap.name}: move {candidate} -> {dest}")
            if args.yes:
                dest_base.mkdir(parents=True, exist_ok=True)
                shutil.move(str(candidate), str(dest))
                changed += 1
            continue

        # Otherwise, if src has mixed content, skip (we won't rearrange)
        skipped += 1
        print(f"[SKIP] {cap.name}: mixed src layout; no action")

    print(f"\nDone. {'APPLIED' if args.yes else 'DRY-RUN'}  changes={changed}, skipped={skipped}")
if __name__ == "__main__":
    main()
