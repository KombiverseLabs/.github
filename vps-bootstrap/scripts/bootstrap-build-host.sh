#!/bin/bash
# Bootstrap a lightweight OCI build host for KombiverseLabs.
# Installs Docker, swap, Dagger CLI, runner health monitoring, and
# three restart-safe GitHub Actions runners with core/tools overflow labels.
set -euo pipefail

BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHUB_ORG="${GITHUB_ORG:-KombiverseLabs}"
RUNNER_USER="${RUNNER_USER:-runner}"
SWAPFILE_SIZE_GB="${SWAPFILE_SIZE_GB:-4}"
COMMON_LABELS="${COMMON_LABELS:-oci-build,oci-build-labs,kombify}"
CORE_LABELS="${CORE_LABELS:-oci-build-core,kombify-cloud,kombify-administration,kombify-ai,kombify-gateway,kombify-core}"
TOOLS_LABELS="${TOOLS_LABELS:-oci-build-tools,kombify-sim,kombify-stack,kombify-stackkits,kombify-me,kombify-blog}"

if [ -z "${GITHUB_RUNNER_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_RUNNER_TOKEN is required"
  exit 1
fi

sudo apt-get update -qq
sudo apt-get install -y -qq curl git jq unzip ca-certificates gnupg lsb-release

if ! swapon --show | grep -q '^/swapfile'; then
  sudo fallocate -l "${SWAPFILE_SIZE_GB}G" /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=$((SWAPFILE_SIZE_GB * 1024))
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  if ! grep -q '^/swapfile ' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  fi
fi

bash "$BOOTSTRAP_DIR/install-docker.sh"
bash "$BOOTSTRAP_DIR/install-dagger.sh"
bash "$BOOTSTRAP_DIR/install-doppler.sh"

sudo mkdir -p /etc/docker
cat <<'EOF' | sudo tee /etc/docker/daemon.json >/dev/null
{
  "features": {
    "buildkit": true
  },
  "live-restore": true,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
sudo systemctl restart docker

cat <<'EOF' | sudo tee /etc/sysctl.d/99-kombify-build-host.conf >/dev/null
vm.swappiness=10
fs.inotify.max_user_watches=1048576
fs.inotify.max_user_instances=1024
EOF
sudo sysctl --system >/dev/null

cat <<'EOF' | sudo tee /etc/profile.d/kombify-build-host.sh >/dev/null
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
EOF

sudo mkdir -p /opt/actions-runners

install_runner() {
  local name="$1"
  local dir="$2"
  local labels="$3"

  RUNNER_NAME="$name" \
  RUNNER_DIR="$dir" \
  RUNNER_USER="$RUNNER_USER" \
  RUNNER_LABELS="$labels" \
  GITHUB_ORG="$GITHUB_ORG" \
  GITHUB_RUNNER_TOKEN="$GITHUB_RUNNER_TOKEN" \
  bash "$BOOTSTRAP_DIR/install-runner.sh"
}

install_runner "oci-build-core-1" "/opt/actions-runners/oci-build-core-1" "$COMMON_LABELS,$CORE_LABELS"
install_runner "oci-build-core-2" "/opt/actions-runners/oci-build-core-2" "$COMMON_LABELS,$CORE_LABELS"
install_runner "oci-build-tools-1" "/opt/actions-runners/oci-build-tools-1" "$COMMON_LABELS,$TOOLS_LABELS"

RUNNER_SERVICES="actions.runner.${GITHUB_ORG}.oci-build-core-1.service,actions.runner.${GITHUB_ORG}.oci-build-core-2.service,actions.runner.${GITHUB_ORG}.oci-build-tools-1.service" \
bash "$BOOTSTRAP_DIR/install-runner-health-monitor.sh"

echo "=== Build host bootstrap complete ==="
docker --version
docker compose version
dagger version
swapon --show
systemctl --no-pager --full status actions.runner.${GITHUB_ORG}.oci-build-core-1.service | head -20
systemctl --no-pager --full status actions.runner.${GITHUB_ORG}.oci-build-core-2.service | head -20
systemctl --no-pager --full status actions.runner.${GITHUB_ORG}.oci-build-tools-1.service | head -20
systemctl --no-pager --full status kombify-runner-health.timer | head -20
