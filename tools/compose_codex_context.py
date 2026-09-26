#!/usr/bin/env python3
import os, json, datetime, pathlib

ROOT = pathlib.Path(os.environ.get("CATALYST_ROOT", pathlib.Path(__file__).resolve().parent.parent))
OUT = pathlib.Path.home() / ".codex" / "context"
OUT.mkdir(parents=True, exist_ok=True)

def read(p):
    try:
        return pathlib.Path(p).read_text(encoding="utf-8").strip()
    except Exception:
        return ""

def collect_recent_events(days=7):
    ev = ROOT / "registry" / "events.jsonl"
    if not ev.exists(): return []
    import time
    cutoff = time.time() - days*86400
    rows = []
    for line in ev.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
            ts = obj.get("timestamp")
            # accept ISO or epoch_ms
            t = None
            if isinstance(ts, str):
                # crude parse
                from datetime import datetime as dt
                try:
                    t = dt.fromisoformat(ts.replace("Z","")).timestamp()
                except:
                    # Try other formats if needed
                    pass
            elif isinstance(ts, (int, float)):
                t = float(ts)/1000 if ts > 10_000_000_000 else float(ts)
            if t and t >= cutoff:
                rows.append(obj)
        except Exception:
            pass
    return rows[:500]

def main():
    compass = read(ROOT / "PROJECT_COMPASS_Huxley.md")
    claude_static = read(ROOT / "CLAUDE.md")
    system_state = read(ROOT / "global" / "system_state.md")
    decisions = read(ROOT / "global" / "decisions_log.md")
    session = read(ROOT / "global" / "session_context.md")

    events = collect_recent_events(7)
    events_brief = ""
    if events:
        def pick(*keys): 
            for k in keys:
                if k in e: return e[k]
            return None
        lines = []
        for e in events[:50]:
            lines.append(f"- {e.get('timestamp','')} slug={pick('slug','capsule','id')} event={e.get('event_type','?')} level={e.get('level','?')}")
        events_brief = "\n".join(lines)
    else:
        events_brief = "_(no events in last 7 days or registry missing)_"

    header = f"""# Huxley — Codex Context Bundle
Generated: {datetime.datetime.now().isoformat(timespec='seconds')}
Source of truth: PROJECT_COMPASS_Huxley.md

This file is auto-generated. Edit originals in the Huxley root.
"""

    bundle = [
        header,
        "\n## 1) Compass (authoritative)\n", compass or "_(missing Compass file)_",
        "\n\n## 2) Current System State\n", system_state or "_(no system_state.md yet)_",
        "\n\n## 3) Recent Decisions (why)\n", decisions or "_(no decisions_log.md yet)_",
        "\n\n## 4) Last Session Context\n", session or "_(no session_context.md yet)_",
        "\n\n## 5) Recent Events (last 7 days)\n", events_brief,
        "\n\n## 6) Claude Static Context (parity)\n", claude_static or "_(no CLAUDE.md yet)_",
    ]

    out = OUT / "builder_context.md"
    out.write_text("".join(bundle), encoding="utf-8")
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()