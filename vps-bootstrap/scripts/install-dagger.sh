#!/bin/bash
# Install Dagger CLI for container-native builds
set -euo pipefail

if command -v dagger >/dev/null 2>&1; then
  dagger version
  exit 0
fi

curl -fsSL https://dl.dagger.io/dagger/install.sh | BIN_DIR=/usr/local/bin sudo -E sh
dagger version
