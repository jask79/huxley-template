#!/usr/bin/env bash
set -euo pipefail

ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
REGISTRY="$ROOT/registry/workflows.json"

echo "📋 Huxley Workflows"
echo "==================="

if [ ! -f "$REGISTRY" ]; then
  echo "No workflows registry found. Run scan-workflows.sh first."
  exit 1
fi

# Parse workflows.json and display summary
if command -v jq >/dev/null 2>&1; then
  echo "Total workflows: $(jq -r '.stats.total_workflows' "$REGISTRY")"
  echo "Active workflows: $(jq -r '.stats.active_workflows' "$REGISTRY")"
  echo ""
  
  # List all workflows
  jq -r '.workflows | to_entries[] | "\(.key): \(.value.type) (\(.value.status))"' "$REGISTRY" 2>/dev/null | while read -r line; do
    echo "  • $line"
  done
else
  echo "Install jq for detailed workflow listing"
  echo "Found workflows in:"
  find "$ROOT/capsules" -name "workflow.yaml" -o -name "requirements.yaml" | while read -r file; do
    capsule=$(basename "$(dirname "$(dirname "$file")")")
    echo "  • $capsule"
  done
fi





