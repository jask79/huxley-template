#!/bin/bash
# Huxley — Upgrade Script (template edition)
#
# Automatic in-place upgrades are NOT supported in this template version.
#
# Why: the previous implementation reversed your personalization with
# unbounded substring replacement across the whole tree (a short first name
# or orchestrator name could corrupt unrelated files), and it only reversed
# 6 of the 15 identity tokens — a lossy round-trip either way. Rather than
# ship that, this stub refuses and points you at the supported flow.
#
# The supported upgrade path (see docs/SETUP.md, "Updating from the template"):
#   git remote add template <template-repo-url>       # once
#   git fetch template
#   git log HEAD..template/main --oneline             # review what's new
#   git merge template/main --allow-unrelated-histories   # first merge only
#   #   ...resolve any conflicts and commit the merge BEFORE the next step
#   ./setup.sh --apply                                # re-personalize new files
#
# Your repo was created from the template rather than cloned from it, so the
# two histories are unrelated and git refuses the first merge without
# --allow-unrelated-histories. Later merges do not need the flag.
#
# Your personalization lives in .catalyst-config; setup.sh --apply only
# substitutes the declared brace placeholders and never rewrites a value it
# already substituted. It is not purely read-only, though: it also creates
# .env and the runtime directories if they are missing, materializes any
# global/config/*.example.* file that has no counterpart yet, and creates or
# repairs .venv (which installs packages with pip). Run it on a committed
# tree, not mid-conflict.

set -euo pipefail

# Everything below is a refusal diagnostic, so it goes to stderr. Colors are
# only emitted when stderr is a terminal, so a redirected run stays clean.
if [[ -t 2 ]]; then
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    BLUE=''
    NC=''
fi

{
    echo -e "${RED}[error]${NC} ./upgrade.sh is disabled in this template version."
    echo ""
    echo "Automatic in-place upgrades were removed: the de-personalize step they"
    echo "relied on could corrupt files that legitimately contain your name or"
    echo "orchestrator name."
    echo ""
    echo -e "${BLUE}Supported upgrade flow${NC} (details in docs/SETUP.md, \"Updating from the template\"):"
    echo "  git remote add template <template-repo-url>       # once"
    echo "  git fetch template"
    echo "  git log HEAD..template/main --oneline             # review what's new"
    echo "  git merge template/main --allow-unrelated-histories   # first merge only"
    echo "  #   resolve any conflicts and commit the merge before continuing"
    echo "  ./setup.sh --apply                                # re-personalize new files"
    echo ""
    echo "The --allow-unrelated-histories flag is needed because your repo was"
    echo "created from the template, not cloned from it. Later merges omit it."
    echo ""
    echo "Note that ./setup.sh --apply is not read-only: besides substituting the"
    echo "declared placeholders, it creates .env and the runtime directories if"
    echo "they are missing, materializes any global/config/*.example.* file that"
    echo "has no counterpart yet, and creates or repairs .venv (installing"
    echo "packages with pip). Run it on a committed tree, never mid-conflict."
} >&2
exit 1
