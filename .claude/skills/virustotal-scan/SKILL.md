---
name: virustotal-scan
description: VirusTotal file and URL scanning with 2-tier credential fallback
when: Use when scanning files for malware, checking URLs for threats, or performing security analysis
tools: ["Bash", "Read"]
---

# VirusTotal Scan Skill

Scan files and URLs using the VirusTotal API.

## Usage
```bash
python3 {{CATALYST_ROOT}}/tools/virustotal_scan.py [scan|check|report] [target]
```

## Commands
- `scan` — Submit file or URL for scanning
- `check` — Check scan status
- `report` — Get detailed report

See `python3 {{CATALYST_ROOT}}/tools/virustotal_scan.py --help` for full options.
