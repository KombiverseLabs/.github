#!/bin/bash
# Basic self-healing for the KombiverseLabs build runner hosts.
set -euo pipefail

RUNNER_SERVICES_CSV="${RUNNER_SERVICES:-actions.runner.KombiverseLabs.oci-build-core-1.service,actions.runner.KombiverseLabs.oci-build-core-2.service,actions.runner.KombiverseLabs.oci-build-tools-1.service}"
DISK_USAGE_THRESHOLD_PERCENT="${DISK_USAGE_THRESHOLD_PERCENT:-85}"
MEM_AVAILABLE_THRESHOLD_MB="${MEM_AVAILABLE_THRESHOLD_MB:-128}"
PRUNE_IF_DISK_HIGH="${PRUNE_IF_DISK_HIGH:-true}"
LOG_TAG="${LOG_TAG:-kombify-runner-health}"

IFS=',' read -r -a RUNNER_SERVICES <<< "$RUNNER_SERVICES_CSV"

log() {
  local message="$1"
  logger -t "$LOG_TAG" "$message"
  echo "[$(date -Is)] $message"
}

ensure_service_active() {
  local service="$1"
  if systemctl is-active --quiet "$service"; then
    return 0
  fi

  log "service $service inactive, restarting"
  systemctl reset-failed "$service" || true
  systemctl restart "$service"
  sleep 2

  if systemctl is-active --quiet "$service"; then
    log "service $service recovered"
    return 0
  fi

  log "service $service failed to recover"
  return 1
}

ensure_docker_healthy() {
  if systemctl is-active --quiet docker && docker info >/dev/null 2>&1; then
    return 0
  fi

  log "docker unhealthy, restarting docker.service"
  systemctl restart docker
  sleep 3
  docker info >/dev/null 2>&1
  log "docker recovered"
}

root_disk_usage="$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')"
mem_available_mb="$(awk '/MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo)"

log "starting health check: disk=${root_disk_usage}% mem_available=${mem_available_mb}MB"

ensure_docker_healthy

for service in "${RUNNER_SERVICES[@]}"; do
  ensure_service_active "$service"
done

if [ "$PRUNE_IF_DISK_HIGH" = "true" ] && [ "$root_disk_usage" -ge "$DISK_USAGE_THRESHOLD_PERCENT" ]; then
  log "disk usage ${root_disk_usage}% >= ${DISK_USAGE_THRESHOLD_PERCENT}%, pruning docker cache"
  docker builder prune -af >/dev/null 2>&1 || true
  docker image prune -af >/dev/null 2>&1 || true
  docker container prune -f >/dev/null 2>&1 || true
  docker volume prune -f >/dev/null 2>&1 || true
fi

if [ "$mem_available_mb" -lt "$MEM_AVAILABLE_THRESHOLD_MB" ]; then
  log "warning: available memory ${mem_available_mb}MB below threshold ${MEM_AVAILABLE_THRESHOLD_MB}MB"
fi

log "health check completed"
