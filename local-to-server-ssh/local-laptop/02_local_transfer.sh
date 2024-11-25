#!/bin/bash
# 02_local_transfer.sh - File transfer script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${BASE_DIR}/config/tunnel_config.json"
LOG_FILE="${BASE_DIR}/logs/transfer.log"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE"
}

# Load configuration
if [ ! -f "$CONFIG_FILE" ]; then
  error "Configuration file not found: $CONFIG_FILE"
  exit 1
fi

GPU_HOST=$(grep -o '"host": "[^"]*' "$CONFIG_FILE" | grep -o '[^"]*$')
GPU_PORT=$(grep -o '"port": "[^"]*' "$CONFIG_FILE" | grep -o '[^"]*$')
GPU_USER=$(grep -o '"user": "[^"]*' "$CONFIG_FILE" | grep -o '[^"]*$')
GPU_PATH=$(grep -o '"data_path": "[^"]*' "$CONFIG_FILE" | grep -o '[^"]*$')
KEY_PATH="${BASE_DIR}/config/vast_ai_*"

# Transfer function
transfer_file() {
  local file="$1"
  local filename=$(basename "$file")
  local retry_count=0
  local max_retries=3

  while [ $retry_count -lt $max_retries ]; do
    log "Transferring $filename (attempt $((retry_count + 1))/${max_retries})"

    scp -i "$KEY_PATH" -P "$GPU_PORT" "$file" "${GPU_USER}@${GPU_HOST}:${GPU_PATH}/"

    if [ $? -eq 0 ]; then
      mv "$file" "${BASE_DIR}/data/sent/"
      log "Successfully transferred: $filename"
      return 0
    else
      retry_count=$((retry_count + 1))
      if [ $retry_count -lt $max_retries ]; then
        log "Transfer failed, retrying in 10 seconds..."
        sleep 10
      fi
    fi
  done

  error "Failed to transfer $filename after $max_retries attempts"
  return 1
}

# Process directory
process_directory() {
  local count=0
  local failed=0

  log "Starting file transfer process..."

  for file in "${BASE_DIR}/data/outgoing"/*.json; do
    if [ -f "$file" ]; then
      count=$((count + 1))
      if ! transfer_file "$file"; then
        failed=$((failed + 1))
      fi
    fi
  done

  log "Transfer session complete. Processed: $count, Failed: $failed"
}

# Main
log "Starting transfer service"
while true; do
  process_directory
  sleep 5
done
