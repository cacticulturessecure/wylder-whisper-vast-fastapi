#!/bin/bash

# 01_vast_initial_setup.sh
# Initial setup script for Vast.ai GPU server

# Set up logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${BASE_DIR}/logs/setup.log"

# Ensure log directory exists
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
mkdir -p ${BASE_DIR}/{bin,config,services,scripts,received_data/{raw,processed},logs}

# Install required packages
log "Installing required packages..."
apt-get update || error "Failed to update package list"
apt-get install -y python3 python3-pip tmux curl || error "Failed to install packages"

# Create server.py
log "Creating server script..."
cat >${BASE_DIR}/bin/server.py <<'EOF'
#!/usr/bin/env python3

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
from datetime import datetime

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

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            json_data = json.loads(post_data.decode('utf-8'))
            json_data['received_at'] = datetime.now().isoformat()
            
            save_dir = Path.home() / "gpu-tunnel" / "received_data" / "raw"
            save_dir.mkdir(exist_ok=True)
            
            filename = f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(save_dir / filename, 'w') as f:
                json.dump(json_data, f, indent=2)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "success",
                "message": f"Data received and saved as {filename}",
                "received_data": json_data
            }
            self.wfile.write(json.dumps(response).encode())
            
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "error",
                "message": "Invalid JSON data"
            }
            self.wfile.write(json.dumps(response).encode())

def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, TestHandler)
    print(f"Starting test server on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server(8080)
EOF

# Create initial configuration
log "Creating initial configuration..."
cat >${BASE_DIR}/config/server_config.json <<EOF
{
    "server": {
        "listen_port": 8080,
        "host": "0.0.0.0",
        "data_dir": "../received_data"
    },
    "monitoring": {
        "log_file": "../logs/server.log",
        "check_interval": 60
    }
}
EOF

# Set permissions
log "Setting permissions..."
chmod 755 ${BASE_DIR}/bin/server.py
chmod 644 ${BASE_DIR}/config/server_config.json

log "Initial setup complete"
