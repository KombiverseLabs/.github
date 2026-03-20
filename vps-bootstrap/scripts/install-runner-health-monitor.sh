#!/bin/bash
# Install a timer-based runner host health monitor.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_SCRIPT="/usr/local/bin/kombify-runner-health-check"
ENV_FILE="/etc/default/kombify-runner-health"
SERVICE_FILE="/etc/systemd/system/kombify-runner-health.service"
TIMER_FILE="/etc/systemd/system/kombify-runner-health.timer"

sudo install -m 0755 "$SCRIPT_DIR/runner-health-check.sh" "$TARGET_SCRIPT"

cat <<EOF | sudo tee "$ENV_FILE" >/dev/null
RUNNER_SERVICES=${RUNNER_SERVICES:-actions.runner.KombiverseLabs.oci-build-core-1.service,actions.runner.KombiverseLabs.oci-build-core-2.service,actions.runner.KombiverseLabs.oci-build-tools-1.service}
DISK_USAGE_THRESHOLD_PERCENT=${DISK_USAGE_THRESHOLD_PERCENT:-85}
MEM_AVAILABLE_THRESHOLD_MB=${MEM_AVAILABLE_THRESHOLD_MB:-128}
PRUNE_IF_DISK_HIGH=${PRUNE_IF_DISK_HIGH:-true}
LOG_TAG=${LOG_TAG:-kombify-runner-health}
EOF

cat <<'EOF' | sudo tee "$SERVICE_FILE" >/dev/null
[Unit]
Description=Kombify Runner Health Check
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/default/kombify-runner-health
ExecStart=/usr/local/bin/kombify-runner-health-check
EOF

cat <<'EOF' | sudo tee "$TIMER_FILE" >/dev/null
[Unit]
Description=Run Kombify Runner Health Check every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=30s
Unit=kombify-runner-health.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kombify-runner-health.timer
sudo systemctl start kombify-runner-health.service
