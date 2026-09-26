#!/usr/bin/env bash
set -euo pipefail

slug="${1:?Usage: ./bootstrap_capsule_dirs.sh <slug> [automation|app|web]}"
branch="${2:-app}"
base="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/capsules"

root="$base/$slug"
mkdir -p "$root"/{spec,src,runs,docs,ops}

case "$branch" in
  automation)
    mkdir -p "$root/src/automation"/{n8n,macos,shortcuts}
    ;;
  app)
    mkdir -p "$root/src/app"/{ios,macos,shared}
    ;;
  web)
    mkdir -p "$root/src/web"/{app,site,shopify,cms}
    ;;
  *)
    echo "Unknown branch: $branch"; exit 1 ;;
esac

echo "Created capsule skeleton: $root"




