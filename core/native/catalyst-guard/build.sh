#!/bin/bash
# Build catalyst-guard and install the binary.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY_DIR="$HOME/.local/bin"
BINARY_NAME="catalyst-guard"

export PATH="$HOME/.cargo/bin:$PATH"

echo "Building catalyst-guard..."
cd "$SCRIPT_DIR"
cargo build --release

mkdir -p "$BINARY_DIR"
cp "target/release/$BINARY_NAME" "$BINARY_DIR/$BINARY_NAME"
echo "Installed: $BINARY_DIR/$BINARY_NAME"

echo "Done."
