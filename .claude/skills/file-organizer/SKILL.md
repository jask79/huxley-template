---
name: file-organizer
description: AI-powered file organization pipeline with OCR, taxonomy classification, and smart routing
when: Use when organizing files, classifying documents, or managing file taxonomy
tools: ["Bash", "Read", "Write", "Edit"]
---

# File Organizer Skill

4-phase AI-powered file organization pipeline.

## Usage
```bash
python3 {{CATALYST_ROOT}}/tools/file-organizer/organize.py [options]
```

## Phases
1. **Scan** — Discover files to organize
2. **Classify** — AI-based taxonomy classification
3. **Route** — Smart file routing based on classification
4. **Execute** — Move/rename files to destination

See `python3 {{CATALYST_ROOT}}/tools/file-organizer/organize.py --help` for full options.
