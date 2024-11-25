#!/bin/bash
# 03_vast_service_setup.sh - Modified version

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

# Create start script
log "Creating start script..."
cat >${BASE_DIR}/bin/start_server.sh <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 server.py
EOF

# Create monitor script
log "Creating monitor script..."
cat >${BASE_DIR}/bin/start_monitor.sh <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 server_monitor.py
EOF

# Set permissions
log "Setting permissions..."
chmod +x ${BASE_DIR}/bin/start_server.sh
chmod +x ${BASE_DIR}/bin/start_monitor.sh

# Start server in tmux
log "Starting server..."
tmux new-session -d -s gpu_server "${BASE_DIR}/bin/start_server.sh"

# Start monitor in tmux
log "Starting monitor..."
tmux new-session -d -s gpu_monitor "${BASE_DIR}/bin/start_monitor.sh"

# Verify server
log "Verifying server..."
sleep 5
if curl -s localhost:8080/health >/dev/null; then
  log "Server is responding correctly"
else
  error "Server is not responding"
fi

log "Service setup complete"
