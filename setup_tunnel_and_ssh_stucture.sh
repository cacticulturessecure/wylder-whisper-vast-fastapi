#!/bin/bash

# Set up error handling
set -e
trap 'echo "Error occurred on line $LINENO. Exit code: $?"' ERR

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log() {
  echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
  echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warn() {
  echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Base directory setup
BASE_DIR="$HOME/gpu-tunnel"
log "Setting up GPU tunnel environment in $BASE_DIR"

# Create directory structure
mkdir -p "$BASE_DIR"/{bin,config,services,logs}

# Change to base directory
cd "$BASE_DIR" || {
  error "Failed to change to $BASE_DIR"
  exit 1
}

# Create configuration file
log "Creating configuration file..."
cat >config/tunnel_config.json <<'EOF'
{
    "gpu_server": {
        "direct": {
            "host": "50.217.254.161",
            "port": "41401",
            "user": "root"
        },
        "proxy": {
            "host": "ssh4.vast.ai",
            "port": "19434",
            "user": "root"
        },
        "internal_port": 8080
    },
    "local": {
        "port": 8080,
        "log_dir": "logs",
        "reconnect_attempts": 3,
        "reconnect_delay": 10
    },
    "monitor": {
        "check_interval": 30,
        "max_failures": 3
    }
}
EOF

# Create systemd service file
log "Creating systemd service file..."
cat >services/gpu-tunnel.service <<'EOF'
[Unit]
Description=GPU Server SSH Tunnel
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=%USER%
Environment="AUTOSSH_GATETIME=0"
Environment="AUTOSSH_POLL=60"
ExecStart=/usr/bin/autossh -M 0 -N \
    -o "ServerAliveInterval=30" \
    -o "ServerAliveCountMax=3" \
    -o "ExitOnForwardFailure=yes" \
    -L %LOCAL_PORT%:localhost:8080 \
    -p %REMOTE_PORT% %REMOTE_USER%@%REMOTE_HOST%

# Fallback configuration
ExecStartPre=/bin/bash -c 'if ! timeout 5 ssh -q -p %REMOTE_PORT% %REMOTE_USER%@%REMOTE_HOST% exit; then exit 1; fi'
ExecStartPost=/bin/bash -c 'if [ $EXIT_STATUS -eq 1 ]; then exec /usr/bin/autossh -M 0 -N -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "ExitOnForwardFailure=yes" -L %LOCAL_PORT%:localhost:8080 -p %PROXY_PORT% %REMOTE_USER%@%PROXY_HOST%; fi'

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create tunnel monitor script
log "Creating tunnel monitor script..."
cat >bin/tunnel_monitor.py <<'EOF'
#!/usr/bin/env python3

import json
import subprocess
import time
import sys
import logging
from pathlib import Path
import socket

class TunnelMonitor:
    def __init__(self):
        self.base_dir = Path.home() / "gpu-tunnel"
        self.config = self.load_config()
        self.setup_logging()

    def load_config(self):
        config_path = self.base_dir / "config" / "tunnel_config.json"
        with open(config_path) as f:
            return json.load(f)

    def setup_logging(self):
        log_path = self.base_dir / "logs" / "tunnel_monitor.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )

    def check_tunnel(self):
        """Check if tunnel is active by attempting to connect to the local port"""
        local_port = self.config["local"]["port"]
        try:
            with socket.create_connection(("localhost", local_port), timeout=5):
                return True
        except (socket.timeout, socket.error):
            return False

    def restart_tunnel(self):
        """Restart the tunnel service"""
        try:
            subprocess.run(["sudo", "systemctl", "restart", "gpu-tunnel"], check=True)
            logging.info("Tunnel service restarted")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to restart tunnel: {e}")
            return False

    def run(self):
        failures = 0
        max_failures = self.config["monitor"]["max_failures"]
        check_interval = self.config["monitor"]["check_interval"]

        while True:
            if not self.check_tunnel():
                failures += 1
                logging.warning(f"Tunnel check failed ({failures}/{max_failures})")
                
                if failures >= max_failures:
                    logging.error("Maximum failures reached, attempting restart")
                    if self.restart_tunnel():
                        failures = 0
                    else:
                        logging.error("Restart failed, manual intervention required")
                        sys.exit(1)
            else:
                failures = 0
                logging.info("Tunnel check successful")

            time.sleep(check_interval)

if __name__ == "__main__":
    monitor = TunnelMonitor()
    monitor.run()
EOF

# Create connection test script
log "Creating connection test script..."
cat >bin/test_connection.sh <<'EOF'
#!/bin/bash

source ../config/tunnel_config.json

echo "=== Testing GPU Server Connections ==="

# Test direct connection
echo "Testing direct connection..."
ssh -o ConnectTimeout=5 \
    -p "${gpu_server[direct][port]}" \
    "${gpu_server[direct][user]}@${gpu_server[direct][host]}" \
    "echo 'Direct connection successful'" || \
    echo "Direct connection failed"

# Test proxy connection
echo "Testing proxy connection..."
ssh -o ConnectTimeout=5 \
    -p "${gpu_server[proxy][port]}" \
    "${gpu_server[proxy][user]}@${gpu_server[proxy][host]}" \
    "echo 'Proxy connection successful'" || \
    echo "Proxy connection failed"

# Test tunnel
echo "Testing tunnel..."
nc -zv localhost "${local[port]}"
EOF

# Make scripts executable
chmod +x bin/{tunnel_monitor.py,test_connection.sh}

# Create empty log file
touch logs/tunnel_monitor.log

# Check for required packages
log "Checking required packages..."
REQUIRED_PACKAGES="autossh python3 netcat-openbsd"
for package in $REQUIRED_PACKAGES; do
  if ! dpkg -l | grep -q "^ii  $package"; then
    warn "$package is not installed. Installing..."
    sudo apt-get update && sudo apt-get install -y "$package"
  else
    log "$package is already installed"
  fi
done

# Set appropriate permissions
chmod 750 "$BASE_DIR"
chmod 640 config/tunnel_config.json
chmod 640 services/gpu-tunnel.service
chmod -R 750 bin/
chmod 770 logs/

log "Installation complete! Directory structure created at $BASE_DIR"
echo
echo "Next steps:"
echo "1. Review and edit configuration:"
echo "   nano $BASE_DIR/config/tunnel_config.json"
echo
echo "2. Install the systemd service:"
echo "   sudo cp $BASE_DIR/services/gpu-tunnel.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable gpu-tunnel"
echo "   sudo systemctl start gpu-tunnel"
echo
echo "3. Test the connection:"
echo "   $BASE_DIR/bin/test_connection.sh"
echo
echo "4. Monitor the tunnel:"
echo "   $BASE_DIR/bin/tunnel_monitor.py"
