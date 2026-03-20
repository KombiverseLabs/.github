#!/bin/bash
# Install and register GitHub Actions self-hosted runner
# Requires: GITHUB_ORG, GITHUB_RUNNER_TOKEN environment variables
set -euo pipefail

RUNNER_VERSION="${RUNNER_VERSION:-2.332.0}"
RUNNER_USER="${RUNNER_USER:-runner}"
RUNNER_DIR="${RUNNER_DIR:-/opt/actions-runner}"
RUNNER_NAME="${RUNNER_NAME:-$(hostname)}"
RUNNER_GROUP="${RUNNER_GROUP:-Default}"
RUNNER_LABELS="${RUNNER_LABELS:-kombify-vps,$(hostname)}"
RUNNER_WORKDIR="${RUNNER_WORKDIR:-_work}"
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

if ! id "$RUNNER_USER" &>/dev/null; then
  sudo useradd -m -s /bin/bash "$RUNNER_USER"
fi
sudo usermod -aG docker "$RUNNER_USER"

sudo mkdir -p /var/lib/kombify-artifacts /var/lib/kombify-buildx-cache
sudo chown -R "$RUNNER_USER:$RUNNER_USER" /var/lib/kombify-artifacts /var/lib/kombify-buildx-cache

sudo mkdir -p "$RUNNER_DIR"
sudo chown -R "$RUNNER_USER:$RUNNER_USER" "$RUNNER_DIR"

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
if [ ! -x "$RUNNER_DIR/run.sh" ]; then
  echo "Downloading runner v${RUNNER_VERSION} (${RUNNER_ARCH}) into $RUNNER_DIR..."
  sudo -u "$RUNNER_USER" curl -fsSL "$RUNNER_URL" | sudo -u "$RUNNER_USER" tar xz
else
  echo "Runner binary already present in $RUNNER_DIR"
fi

if [ ! -f "$RUNNER_DIR/.runner" ]; then
  sudo -u "$RUNNER_USER" ./config.sh \
    --url "https://github.com/$GITHUB_ORG" \
    --token "$GITHUB_RUNNER_TOKEN" \
    --labels "$RUNNER_LABELS" \
    --name "$RUNNER_NAME" \
    --runnergroup "$RUNNER_GROUP" \
    --work "$RUNNER_WORKDIR" \
    --unattended \
    --replace
else
  echo "Runner $RUNNER_NAME already configured in $RUNNER_DIR"
fi

SERVICE_NAME="actions.runner.${GITHUB_ORG}.${RUNNER_NAME}.service"
if [ ! -f "/etc/systemd/system/${SERVICE_NAME}" ]; then
  sudo ./svc.sh install "$RUNNER_USER"
fi
sudo mkdir -p "/etc/systemd/system/${SERVICE_NAME}.d"
cat <<EOF | sudo tee "/etc/systemd/system/${SERVICE_NAME}.d/override.conf" >/dev/null
[Service]
Environment=FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true
Environment=KOMBIFY_ARTIFACTS_ROOT=/var/lib/kombify-artifacts
Environment=KOMBIFY_BUILDX_CACHE_ROOT=/var/lib/kombify-buildx-cache
EOF
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Runner installed and started"
echo "  Name:   $RUNNER_NAME"
echo "  Labels: $RUNNER_LABELS"
echo "  User:   $RUNNER_USER"
echo "  Dir:    $RUNNER_DIR"
echo ""
echo "Verify: sudo systemctl status $SERVICE_NAME"
