#!/bin/bash
# 02_vast_key_setup.sh
# Configure SSH keys and permissions for Vast.ai GPU server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${BASE_DIR}/logs/setup.log"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE"
  exit 1
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

# Function to add a new SSH key
add_ssh_key() {
  local key_file="${BASE_DIR}/config/keys/tunnel_key.pub"
  if [ -f "$key_file" ]; then
    log "Adding new SSH key to authorized_keys..."
    cat "$key_file" >>~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys
    log "SSH key added successfully"
  else
    error "No SSH key found at $key_file"
  fi
}

# Add key if present
add_ssh_key

log "SSH key setup complete"
