#!/usr/bin/env bash
# Huxley — grep-based fallback secret scan.
# Prefer gitleaks (`gitleaks detect --no-git --redact`); this is the lighter
# fallback for machines without it.
#
# Exit codes (consumed by scripts and CI — never treat 2 as clean):
#   0  clean — prints the explicit all-clear line
#   1  potential secrets found — prints redacted match lines
#   2  the scanner itself failed to run
#
# Notes:
# - LC_ALL=C pins bracket-range semantics: under some UTF-8 locales macOS
#   /usr/bin/grep rejects ranges it accepts under C, and a pattern-compile
#   error must never read as "no secrets found".
# - stderr stays visible: a grep failure is a scan failure, not an all-clear.
set -u
export LC_ALL=C

ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT" || { echo "Secret scan FAILED: cannot cd to $ROOT" >&2; exit 2; }

echo "Scanning for potential secrets (single-pass)..."

MATCHES="$(grep -RInE \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude-dir=.venv \
  --exclude-dir=__pycache__ \
  --exclude-dir='.cache' \
  --exclude='*.tar.gz' \
  --exclude='*.zip' \
  --exclude='*.db' \
  --exclude='*.pyc' \
  --exclude='*.woff2' \
  --exclude='*.woff' \
  -e 'AKIA[0-9A-Z]{16}' \
  -e 'AIza[0-9A-Za-z_-]{35}' \
  -e 'xox[baprs]-[0-9A-Za-z-]{10,48}' \
  -e '-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----' \
  -e 'sk-(ant|proj|svcacct)-[A-Za-z0-9_-]{20,}' \
  -e 'sk-[A-Za-z0-9]{20,}' \
  -e 'ghp_[A-Za-z0-9]{36}' \
  -e 'gho_[A-Za-z0-9]{36}' \
  -e 'github_pat_[A-Za-z0-9_]{20,}' \
  . )"
GREP_RC=$?

if [ "$GREP_RC" -ge 2 ]; then
    echo "Secret scan FAILED to run (grep exited $GREP_RC) — do NOT treat this as a clean result." >&2
    exit 2
fi

if [ "$GREP_RC" -eq 0 ] && [ -n "$MATCHES" ]; then
    printf '%s\n' "$MATCHES" | sed 's/\(.\{0,80\}\).*/\1 [REDACTED]/' | head -n 50
    echo "Potential secrets matched the patterns above — review each line before pushing." >&2
    exit 1
fi

echo "No obvious secrets matched common patterns."
exit 0
