#!/bin/bash
# 02_local_transfer.sh - File transfer script

# Set absolute paths
BASE_DIR="/home/securemeup/test/wylder-whisper-vast-fastapi/local-to-server-ssh"
CONFIG_FILE="${BASE_DIR}/config/tunnel_config.json"
LOG_FILE="${BASE_DIR}/logs/transfer.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE"
}

# GPU server details (hardcoded for reliability)
GPU_HOST="50.217.254.161"
GPU_PORT="41525"
GPU_USER="root"
GPU_PATH="/wylder-whisper-vast-fastapi/local-to-server-ssh/gpu-tunnel/received_data/raw"

# Find the most recent SSH key
KEY_PATH=$(ls -t ${BASE_DIR}/config/vast_ai_* | grep -v '\.pub$' | head -1)

# Transfer function
transfer_file() {
  local file="$1"
  local filename=$(basename "$file")
  local retry_count=0
  local max_retries=3

  while [ $retry_count -lt $max_retries ]; do
    log "Transferring $filename (attempt $((retry_count + 1))/${max_retries})"
    log "Using key: $KEY_PATH"

    # Debug output
    log "Command: scp -i \"$KEY_PATH\" -P \"$GPU_PORT\" \"$file\" \"${GPU_USER}@${GPU_HOST}:${GPU_PATH}/\""

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
  log "Looking for files in: ${BASE_DIR}/data/outgoing/"

  # Check if directory exists
  if [ ! -d "${BASE_DIR}/data/outgoing" ]; then
    error "Outgoing directory not found: ${BASE_DIR}/data/outgoing"
    return 1
  fi

  # Check if any JSON files exist
  shopt -s nullglob
  files=(${BASE_DIR}/data/outgoing/*.json)
  if [ ${#files[@]} -eq 0 ]; then
    log "No JSON files found in outgoing directory"
    return 0
  fi

  for file in "${files[@]}"; do
    count=$((count + 1))
    if ! transfer_file "$file"; then
      failed=$((failed + 1))
    fi
  done

  log "Transfer session complete. Processed: $count, Failed: $failed"
}

# Verify directories exist
mkdir -p "${BASE_DIR}/data/outgoing" "${BASE_DIR}/data/sent"

# Main
log "Starting transfer service"
log "Using SSH key: $KEY_PATH"
log "GPU Server: ${GPU_USER}@${GPU_HOST}:${GPU_PORT}"

while true; do
  process_directory
  sleep 5
done
