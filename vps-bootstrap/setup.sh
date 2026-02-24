#!/bin/bash
# =============================================================================
# Kombify VPS Bootstrap Script
# =============================================================================
# Sets up a fresh VPS for running Kombify services via Docker + Traefik.
#
# Usage:
#   curl -sL https://raw.githubusercontent.com/KombiverseLabs/.github/main/vps-bootstrap/setup.sh | bash
#
# Or clone and run:
#   git clone https://github.com/KombiverseLabs/.github.git
#   cd .github/vps-bootstrap
#   ./setup.sh [options]
#
# Options:
#   --with-runner     Install GitHub Actions self-hosted runner
#   --domain DOMAIN   Set the base domain (default: kombify.io)
#   --email EMAIL     Let's Encrypt email for TLS certificates
#   --skip-docker     Skip Docker installation
#   --skip-doppler    Skip Doppler CLI installation
#   --skip-traefik    Skip Traefik setup
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# Defaults
INSTALL_RUNNER=false
DOMAIN="kombify.io"
ACME_EMAIL=""
SKIP_DOCKER=false
SKIP_DOPPLER=false
SKIP_TRAEFIK=false
BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" 2>/dev/null || echo ".")" && pwd)"

# Parse args
for arg in "$@"; do
  case $arg in
    --with-runner)  INSTALL_RUNNER=true ;;
    --domain)       shift; DOMAIN="$1" ;;
    --email)        shift; ACME_EMAIL="$1" ;;
    --skip-docker)  SKIP_DOCKER=true ;;
    --skip-doppler) SKIP_DOPPLER=true ;;
    --skip-traefik) SKIP_TRAEFIK=true ;;
    --help|-h)
      echo "Usage: $0 [--with-runner] [--domain DOMAIN] [--email EMAIL] [--skip-docker] [--skip-doppler] [--skip-traefik]"
      exit 0
      ;;
  esac
done

echo ""
echo "========================================"
echo "  Kombify VPS Bootstrap"
echo "========================================"
echo "  Domain:  $DOMAIN"
echo "  Runner:  $INSTALL_RUNNER"
echo "========================================"
echo ""

# --- Step 1: System update ---
log_info "Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq curl wget git jq unzip apt-transport-https ca-certificates gnupg lsb-release

# --- Step 2: Docker ---
if [ "$SKIP_DOCKER" = false ]; then
  if command -v docker &> /dev/null; then
    log_warn "Docker already installed: $(docker --version)"
  else
    log_info "Installing Docker..."
    bash "$BOOTSTRAP_DIR/scripts/install-docker.sh"
  fi
else
  log_info "Skipping Docker installation"
fi

# --- Step 3: Doppler ---
if [ "$SKIP_DOPPLER" = false ]; then
  if command -v doppler &> /dev/null; then
    log_warn "Doppler already installed: $(doppler --version)"
  else
    log_info "Installing Doppler CLI..."
    bash "$BOOTSTRAP_DIR/scripts/install-doppler.sh"
  fi
else
  log_info "Skipping Doppler installation"
fi

# --- Step 4: Create shared Docker network ---
log_info "Creating kombify-shared Docker network..."
docker network create kombify-shared 2>/dev/null || log_warn "Network kombify-shared already exists"

# --- Step 5: Firewall ---
log_info "Configuring firewall..."
bash "$BOOTSTRAP_DIR/scripts/configure-firewall.sh"

# --- Step 6: Traefik ---
if [ "$SKIP_TRAEFIK" = false ]; then
  log_info "Setting up Traefik reverse proxy..."
  mkdir -p /opt/kombify/traefik
  cp "$BOOTSTRAP_DIR/traefik/docker-compose.yml" /opt/kombify/traefik/
  cp "$BOOTSTRAP_DIR/traefik/traefik.yml" /opt/kombify/traefik/

  # Substitute domain and email
  sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" /opt/kombify/traefik/traefik.yml
  sed -i "s/EMAIL_PLACEHOLDER/$ACME_EMAIL/g" /opt/kombify/traefik/traefik.yml

  # Create acme storage file
  touch /opt/kombify/traefik/acme.json
  chmod 600 /opt/kombify/traefik/acme.json

  cd /opt/kombify/traefik
  docker compose up -d
  log_success "Traefik is running"
else
  log_info "Skipping Traefik setup"
fi

# --- Step 7: Deploy directory structure ---
log_info "Creating deploy directory structure..."
mkdir -p /opt/kombify/{api,stack,cloud,core,admin,ai,blog,db,me,sim}

# --- Step 8: Self-hosted runner (optional) ---
if [ "$INSTALL_RUNNER" = true ]; then
  log_info "Installing GitHub Actions self-hosted runner..."
  bash "$BOOTSTRAP_DIR/scripts/install-runner.sh"
fi

echo ""
echo "========================================"
log_success "VPS Bootstrap Complete"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Configure Doppler: doppler login && doppler setup"
echo "  2. Deploy services using GitHub Actions workflows"
echo "  3. Verify Traefik dashboard at https://traefik.$DOMAIN"
if [ "$INSTALL_RUNNER" = true ]; then
  echo "  4. Verify runner is registered: sudo systemctl status actions.runner.*"
fi
echo ""
