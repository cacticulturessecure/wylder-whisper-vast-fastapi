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
log "Setting up GPU server environment in $BASE_DIR"

# Create directory structure
mkdir -p "$BASE_DIR"/{bin,config,services,logs}

# Change to base directory
cd "$BASE_DIR" || {
    error "Failed to change to $BASE_DIR"
    exit 1
}

# Create GPU server configuration
log "Creating configuration file..."
cat >config/tunnel_config.json <<'EOF'
{
    "server": {
        "listen_port": 8080,
        "log_dir": "logs",
        "allowed_users": ["root"]
    },
    "monitor": {
        "check_interval": 30,
        "max_failures": 3
    }
}
EOF

# Create server monitor script
log "Creating server monitor script..."
cat >bin/server_monitor.py <<'EOF'
#!/usr/bin/env python3

import json
import subprocess
import time
import sys
import logging
from pathlib import Path
import socket

class ServerMonitor:
    def __init__(self):
        self.base_dir = Path.home() / "gpu-tunnel"
        self.config = self.load_config()
        self.setup_logging()

    def load_config(self):
        config_path = self.base_dir / "config" / "tunnel_config.json"
        with open(config_path) as f:
            return json.load(f)

    def setup_logging(self):
        log_path = self.base_dir / "logs" / "server_monitor.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )

    def check_port(self):
        """Check if the service port is listening"""
        port = self.config["server"]["listen_port"]
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('localhost', port)) == 0
        except Exception as e:
            logging.error(f"Port check error: {e}")
            return False

    def run(self):
        while True:
            if not self.check_port():
                logging.warning(f"Port {self.config['server']['listen_port']} is not listening")
            else:
                logging.info("Service port check successful")
            time.sleep(self.config["monitor"]["check_interval"])

if __name__ == "__main__":
    monitor = ServerMonitor()
    monitor.run()
EOF

# Create test script
log "Creating test script..."
cat >bin/test_server.sh <<'EOF'
#!/bin/bash

source ../config/tunnel_config.json

echo "=== Testing GPU Server Setup ==="

# Check if port is listening
PORT="${server[listen_port]}"
echo "Checking port $PORT..."
if nc -z localhost $PORT; then
    echo "✓ Port $PORT is listening"
else
    echo "✗ Port $PORT is not listening"
fi

# Check server process
if pgrep -f "python.*server.py" > /dev/null; then
    echo "✓ Server process is running"
else
    echo "✗ Server process is not running"
fi
EOF

# Create simple test server
log "Creating test server..."
cat >bin/server.py <<'EOF'
#!/usr/bin/env python3

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {
            "status": "running",
            "message": "GPU server is operational"
        }
        self.wfile.write(json.dumps(response).encode())

def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, TestHandler)
    print(f"Starting test server on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    config_path = Path.home() / "gpu-tunnel" / "config" / "tunnel_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    run_server(config["server"]["listen_port"])
EOF

# Make scripts executable
chmod +x bin/{server_monitor.py,test_server.sh,server.py}

# Create empty log file
touch logs/server_monitor.log

# Check required packages
log "Checking required packages..."
REQUIRED_PACKAGES="python3 netcat-openbsd"
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
chmod -R 750 bin/
chmod 770 logs/

log "Installation complete! Directory structure created at $BASE_DIR"
echo
echo "Next steps:"
echo "1. Start the test server:"
echo "   nohup $BASE_DIR/bin/server.py > $BASE_DIR/logs/server.log 2>&1 &"
echo
echo "2. Test the setup:"
echo "   $BASE_DIR/bin/test_server.sh"
echo
echo "3. Monitor the server:"
echo "   $BASE_DIR/bin/server_monitor.py"
EOF

The main differences in this version:
1. No systemd service (since we're just running a test server)
2. Simplified configuration focused on server-side settings
3. Basic HTTP server that listens on port 8080
4. Server-specific monitoring

To use:
1. Copy this script to the GPU server
2. Run it
3. Start the test server
4. Then try the tunnel connection from the local side

Would you like me to:
1. Add more robust server functionality?
2. Add authentication checks?
3. Add more detailed logging?
