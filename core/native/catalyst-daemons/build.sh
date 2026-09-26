#!/usr/bin/env bash
# build.sh — Build all 3 catalyst daemon binaries
# Output: bin/brave-socket-daemon, bin/chrome-mcp-watchdog, bin/service-health-push
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BIN_DIR="$SCRIPT_DIR/bin"
mkdir -p "$BIN_DIR"

GO=/opt/homebrew/bin/go

echo "Building catalyst daemons..."

# No CGo, static binary, arm64 darwin
export CGO_ENABLED=0
export GOOS=darwin
export GOARCH=arm64

$GO build -trimpath -ldflags="-s -w" -o "$BIN_DIR/brave-socket-daemon" ./cmd/brave-socket-daemon/
echo "  [OK] brave-socket-daemon"

$GO build -trimpath -ldflags="-s -w" -o "$BIN_DIR/chrome-mcp-watchdog"  ./cmd/chrome-mcp-watchdog/
echo "  [OK] chrome-mcp-watchdog"

$GO build -trimpath -ldflags="-s -w" -o "$BIN_DIR/service-health-push"  ./cmd/service-health-push/
echo "  [OK] service-health-push"

echo ""
echo "Binaries written to $BIN_DIR/"
ls -lh "$BIN_DIR/"

echo ""
echo "SIGTERM test (each binary must exit cleanly on SIGTERM):"
echo "  Run: $BIN_DIR/brave-socket-daemon &; sleep 1; kill -TERM \$!"
