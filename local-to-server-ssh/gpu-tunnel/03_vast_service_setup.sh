#!/bin/bash
# 03_vast_service_setup.sh
# Set up and start the GPU server service

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

# Create systemd service file
log "Creating systemd service file..."
cat >/etc/systemd/system/gpu-server.service <<EOF
[Unit]
Description=GPU Server JSON Service
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
WorkingDirectory=${BASE_DIR}/bin
ExecStart=/usr/bin/tmux new-session -d -s gpu_server 'python3 server.py'
ExecStop=/usr/bin/tmux kill-session -t gpu_server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create server monitor service
log "Creating monitor service..."
cat >${BASE_DIR}/bin/server_monitor.py <<'EOF'
#!/usr/bin/env python3

import json
import time
import logging
import subprocess
from pathlib import Path
import requests

class ServerMonitor:
    def __init__(self):
        self.setup_logging()
        self.load_config()

    def setup_logging(self):
        log_file = Path("../logs/server_monitor.log")
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def load_config(self):
        config_file = Path("../config/server_config.json")
        with open(config_file) as f:
            self.config = json.load(f)

    def check_server(self):
        try:
            response = requests.get(f"http://localhost:{self.config['server']['listen_port']}/health")
            return response.status_code == 200
        except:
            return False

    def restart_server(self):
        try:
            subprocess.run(["systemctl", "restart", "gpu-server"], check=True)
            logging.info("Server restarted")
            return True
        except:
            logging.error("Failed to restart server")
            return False

    def run(self):
        while True:
            if not self.check_server():
                logging.warning("Server health check failed")
                self.restart_server()
            time.sleep(self.config['monitoring']['check_interval'])

if __name__ == "__main__":
    monitor = ServerMonitor()
    monitor.run()
EOF

# Create monitor service file
log "Creating monitor service file..."
cat >/etc/systemd/system/gpu-server-monitor.service <<EOF
[Unit]
Description=GPU Server Monitor Service
After=gpu-server.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
WorkingDirectory=${BASE_DIR}/bin
ExecStart=/usr/bin/python3 server_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
log "Setting permissions..."
chmod 755 ${BASE_DIR}/bin/server_monitor.py
chmod 644 /etc/systemd/system/gpu-server.service
chmod 644 /etc/systemd/system/gpu-server-monitor.service

# Reload systemd and enable services
log "Enabling services..."
systemctl daemon-reload || error "Failed to reload systemd"
systemctl enable gpu-server || error "Failed to enable gpu-server service"
systemctl enable gpu-server-monitor || error "Failed to enable monitor service"

# Start services
log "Starting services..."
systemctl start gpu-server || error "Failed to start gpu-server service"
systemctl start gpu-server-monitor || error "Failed to start monitor service"

# Verify services
log "Verifying services..."
sleep 5
if ! systemctl is-active --quiet gpu-server; then
  error "GPU server service failed to start"
fi
if ! systemctl is-active --quiet gpu-server-monitor; then
  error "Monitor service failed to start"
fi

# Test server
log "Testing server..."
if curl -s localhost:8080/health >/dev/null; then
  log "Server is responding correctly"
else
  error "Server is not responding"
fi

log "Service setup complete"
