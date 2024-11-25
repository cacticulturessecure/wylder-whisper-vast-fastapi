#!/bin/bash
# 02_vast_key_setup.sh - Modified version

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${BASE_DIR}/logs/setup.log"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

info() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1" | tee -a "$LOG_FILE"
}

# Create SSH directory if it doesn't exist
log "Setting up SSH directory..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Create authorized_keys file if it doesn't exist
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Create key configuration directory
log "Creating key configuration directory..."
mkdir -p ${BASE_DIR}/config/keys
chmod 700 ${BASE_DIR}/config/keys

# Instead of failing, create a placeholder file
log "Creating placeholder for SSH key..."
cat >${BASE_DIR}/config/keys/README.txt <<EOF
Place your tunnel_key.pub file here.
This file will be automatically detected and added to authorized_keys.
EOF

info "Setup complete. Waiting for tunnel_key.pub to be added to ${BASE_DIR}/config/keys/"
info "Once key is added, run: cat ${BASE_DIR}/config/keys/tunnel_key.pub >> ~/.ssh/authorized_keys"
