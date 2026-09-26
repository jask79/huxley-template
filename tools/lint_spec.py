#!/usr/bin/env python3
import sys, yaml, json
from pathlib import Path

ROOT = Path("{{CATALYST_ROOT}}")
CAPS = ROOT / "capsules"

REQUIRED = [
  ("project.name", str),
  ("project.slug", str),
  ("project.branch", str),
  ("project.targets", list),
  ("definition_of_done", list),
]

def get(d, path):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

def check_cap(cap: Path):
    specp = cap/"spec"/"requirements.yaml"
    if not specp.exists():
        return (False, ["missing spec/requirements.yaml"])
    try:
        data = yaml.safe_load(specp.read_text()) or {}
    except Exception as e:
        return (False, [f"invalid YAML: {e}"])

    errs = []
    for key, typ in REQUIRED:
        val = get(data, key)
        if val is None:
            errs.append(f"missing {key}")
        elif typ is list and not isinstance(val, list):
            errs.append(f"{key} must be list")
        elif typ is str and not isinstance(val, str):
            errs.append(f"{key} must be string")
    # simple values sanity
    branch = get(data,"project.branch") or ""
    targets = get(data,"project.targets") or []
    valid_branches = {"automation","app","web"}
    if branch not in valid_branches:
        errs.append(f"project.branch must be one of {sorted(valid_branches)}")
    if not targets:
        errs.append("project.targets must not be empty")
    return (len(errs)==0, errs)

def main():
    any_fail = False
    for cap in sorted([d for d in CAPS.iterdir() if d.is_dir()]):
        ok, errs = check_cap(cap)
        if ok:
            print(f"{cap.name}: PASS")
        else:
            any_fail = True
            print(f"{cap.name}: FAIL -> {', '.join(errs)}")
    print("SUMMARY:", "PASS" if not any_fail else "FAIL")
    sys.exit(0 if not any_fail else 1)

if __name__ == "__main__":
    main()
