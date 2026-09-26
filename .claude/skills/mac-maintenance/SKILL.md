# Mac Maintenance Skill

Automated Mac RAM purging and cache cleanup powered by Mole + sudo purge.

## Commands

### Quick RAM Purge (optional: schedule hourly via a LaunchAgent you install)
```bash
{{CATALYST_ROOT}}/tools/mac-maintenance.sh --quick
```
Flushes inactive RAM via `sudo purge`. Takes <1 second.

### Full Maintenance (run from terminal)
```bash
{{CATALYST_ROOT}}/tools/mac-maintenance.sh
```
Runs Mole clean + optimize + dev cache cleanup + RAM purge. Requires TTY for Mole's interactive scanning.

### Check Status
```bash
{{CATALYST_ROOT}}/tools/mac-maintenance.sh --status
```
Shows RAM usage, memory pressure, swap, disk free, and last run stats.

### Dry Run
```bash
{{CATALYST_ROOT}}/tools/mac-maintenance.sh --dry-run
```
Preview mode — shows what would be cleaned without making changes.

### Direct Mole Commands (for deeper cleaning)
```bash
mo clean              # Deep disk cleanup (caches, logs, browser data, dev artifacts)
mo optimize           # System optimization (memory, DNS, app state, database tuning)
mo purge              # Remove old project artifacts (node_modules, build dirs)
mo analyze            # Explore disk usage visually
mo status             # System health dashboard
```

## Architecture

- **LaunchAgent (optional, not shipped):** create `~/Library/LaunchAgents/com.huxley.mac-maintenance.plist` to run `--quick` on a schedule
- **Script:** `tools/mac-maintenance.sh` — orchestrates Mole + purge + dev cache cleanup
- **Logs:** `~/.cache/catalyst-maintenance/maintenance.log`
- **Stats:** `~/.cache/catalyst-maintenance/last_run.json` (JSON with before/after RAM, disk, duration)
- **Mole binary:** `mo` (on your PATH; installed via Homebrew)
- **Passwordless purge (opt-in):** `--setup` writes `/etc/sudoers.d/catalyst-purge`; review it before accepting

## When to Use

- If Claude Code sessions are slow or Mac is sluggish → run `--quick`
- Before starting heavy workloads → run `--status` to check available RAM
- Weekly deep clean → run full mode from terminal (`mo clean` + `mo optimize`)
