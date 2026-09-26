---
description: RAM cleanup — aggressive memory reclaim, orphan kill, cache purge, swap report
---

Run the deep maintenance cycle. Execute ALL steps — don't just suggest them.

1. **Run deep maintenance** — Execute:
   ```bash
   tools/mac-maintenance.sh --deep
   ```
   This does: memory pressure signal → orphan process kill → Finder/Dock restart → DNS/QuickLook/font flush → dev cache clean → system cache clean → RAM purge → top consumers → swap kill recommendations.

2. **Present a tight summary** from the script output:
   - Before → After: RAM, swap, disk
   - Total freed (RAM + swap)
   - Top 5 memory hogs (app name + MB only)
   - If swap > 4GB: relay the kill recommendations from the script

Keep it short. No prose. Just the numbers and the wins.
