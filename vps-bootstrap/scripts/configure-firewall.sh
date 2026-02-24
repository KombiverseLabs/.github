#!/bin/bash
# Configure UFW firewall for Kombify VPS
set -euo pipefail

if ! command -v ufw &> /dev/null; then
  sudo apt-get install -y -qq ufw
fi

# Allow SSH (don't lock yourself out)
sudo ufw allow 22/tcp

# HTTP/HTTPS for Traefik
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall (non-interactive)
echo "y" | sudo ufw enable

sudo ufw status verbose
echo "Firewall configured"
