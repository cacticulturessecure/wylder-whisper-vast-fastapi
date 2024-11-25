#!/bin/bash
# 01_local_setup.sh - Local laptop initial setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${BASE_DIR}/logs/setup.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE"
  exit 1
}

# Create directory structure
log "Creating directory structure..."
mkdir -p ${BASE_DIR}/{bin,config,logs,data/{outgoing,sent}}

# Generate SSH key
log "Generating SSH key..."
KEY_NAME="vast_ai_$(date +%Y%m%d_%H%M%S)"
ssh-keygen -t rsa -b 4096 -f "${BASE_DIR}/config/${KEY_NAME}" -N "" -C "vast_ai_tunnel" || error "Failed to generate SSH key"

# Copy public key to config
log "Copying public key..."
cp "${BASE_DIR}/config/${KEY_NAME}.pub" "${BASE_DIR}/config/tunnel_key.pub"

# Create configuration
log "Creating configuration..."
cat >"${BASE_DIR}/config/tunnel_config.json" <<EOF
{
    "gpu_server": {
        "host": "50.217.254.161",
        "port": "40035",
        "user": "root",
        "data_path": "/wylder-whisper-vast-fastapi/local-to-server-ssh/gpu-tunnel/received_data/raw"
    },
    "local": {
        "key_path": "${BASE_DIR}/config/${KEY_NAME}",
        "data_path": "${BASE_DIR}/data",
        "log_path": "${BASE_DIR}/logs"
    },
    "transfer": {
        "retry_attempts": 3,
        "retry_delay": 10,
        "check_interval": 5
    }
}
EOF

# Set permissions
log "Setting permissions..."
chmod 700 ${BASE_DIR}/config
chmod 600 ${BASE_DIR}/config/${KEY_NAME}
chmod 644 ${BASE_DIR}/config/${KEY_NAME}.pub
chmod 755 ${BASE_DIR}/data/{outgoing,sent}

log "Local setup complete"
echo -e "\nPublic key to add to GPU server:"
cat "${BASE_DIR}/config/tunnel_key.pub"
