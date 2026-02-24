#!/bin/bash
# Install and register GitHub Actions self-hosted runner
# Requires: GITHUB_ORG, GITHUB_RUNNER_TOKEN environment variables
set -euo pipefail

RUNNER_VERSION="2.321.0"
RUNNER_USER="runner"
RUNNER_DIR="/opt/actions-runner"
RUNNER_LABELS="${RUNNER_LABELS:-kombify-vps,$(hostname)}"
GITHUB_ORG="${GITHUB_ORG:-KombiverseLabs}"

if [ -z "${GITHUB_RUNNER_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_RUNNER_TOKEN is required."
  echo ""
  echo "Generate a registration token:"
  echo "  gh api -X POST orgs/$GITHUB_ORG/actions/runners/registration-token --jq '.token'"
  echo ""
  echo "Then run:"
  echo "  GITHUB_RUNNER_TOKEN=<token> GITHUB_ORG=$GITHUB_ORG $0"
  exit 1
fi

# Create runner user
if ! id "$RUNNER_USER" &>/dev/null; then
  sudo useradd -m -s /bin/bash "$RUNNER_USER"
  sudo usermod -aG docker "$RUNNER_USER"
fi

# Download runner
sudo mkdir -p "$RUNNER_DIR"
sudo chown "$RUNNER_USER:$RUNNER_USER" "$RUNNER_DIR"

cd "$RUNNER_DIR"
ARCH=$(dpkg --print-architecture)
if [ "$ARCH" = "amd64" ]; then
  RUNNER_ARCH="x64"
elif [ "$ARCH" = "arm64" ]; then
  RUNNER_ARCH="arm64"
else
  echo "Unsupported architecture: $ARCH"
  exit 1
fi

RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
echo "Downloading runner v${RUNNER_VERSION} (${RUNNER_ARCH})..."
sudo -u "$RUNNER_USER" curl -sL "$RUNNER_URL" | sudo -u "$RUNNER_USER" tar xz

# Configure runner
sudo -u "$RUNNER_USER" ./config.sh \
  --url "https://github.com/$GITHUB_ORG" \
  --token "$GITHUB_RUNNER_TOKEN" \
  --labels "$RUNNER_LABELS" \
  --name "$(hostname)" \
  --work "_work" \
  --unattended \
  --replace

# Install as systemd service
sudo ./svc.sh install "$RUNNER_USER"
sudo ./svc.sh start

echo "Runner installed and started"
echo "  Labels: $RUNNER_LABELS"
echo "  User:   $RUNNER_USER"
echo "  Dir:    $RUNNER_DIR"
echo ""
echo "Verify: sudo systemctl status actions.runner.$GITHUB_ORG.$(hostname).service"
