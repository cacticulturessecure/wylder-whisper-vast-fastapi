#!/bin/bash

# main_setup.sh - Main orchestration script
# Create directory structure
mkdir -p ~/gpu-tunnel/{scripts,logs,config}
cd ~/gpu-tunnel

# Configuration file
cat >config/tunnel_config.env <<'EOF'
# System Configuration
SYSTEM_TYPE="webserver"  # Options: webserver, gpuserver
LOG_DIR="logs"
SCRIPTS_DIR="scripts"

# SSH Connection Details
GPU_DIRECT_HOST="50.217.254.161"
GPU_DIRECT_PORT="40124"
GPU_PROXY_HOST="ssh4.vast.ai"
GPU_PROXY_PORT="11392"
GPU_USER="root"

# Tunnel Configuration
TUNNEL_PORT="8000"
MONITOR_INTERVAL="60"
MAX_RETRIES="3"
LOG_ROTATE_SIZE="10485760"  # 10MB
LOG_RETAIN_DAYS="7"

# Alert Configuration
ALERT_EMAIL=""  # Add email for notifications
ALERT_MAX_FAILURES="5"
EOF

# 1. System Validation Script
cat >scripts/01_validate_system.sh <<'EOF'
#!/bin/bash
source ../config/tunnel_config.env

LOG_FILE="../$LOG_DIR/system_validation.log"

echo "=== System Validation Started ===" | tee -a "$LOG_FILE"
echo "Timestamp: $(date)" | tee -a "$LOG_FILE"

# Function to check required packages
check_packages() {
    local packages=("openssh-client" "openssh-server" "autossh" "netcat-openbsd")
    for package in "${packages[@]}"; do
        if dpkg -s "$package" >/dev/null 2>&1; then
            echo "✓ $package installed" | tee -a "$LOG_FILE"
        else
            echo "✗ $package needs to be installed" | tee -a "$LOG_FILE"
            sudo apt-get install -y "$package"
        fi
    done
}

# Function to check port availability
check_ports() {
    local port=$TUNNEL_PORT
    if nc -z localhost "$port" 2>/dev/null; then
        echo "✗ Port $port is in use" | tee -a "$LOG_FILE"
        echo "Currently using port $port:" | tee -a "$LOG_FILE"
        sudo lsof -i ":$port" | tee -a "$LOG_FILE"
    else
        echo "✓ Port $port is available" | tee -a "$LOG_FILE"
    fi
}

# Function to check SSH configuration
check_ssh() {
    if [ ! -d ~/.ssh ]; then
        mkdir -p ~/.ssh
        chmod 700 ~/.ssh
    fi
    
    if [ ! -f ~/.ssh/id_rsa ]; then
        echo "No SSH key found. Generating new key..." | tee -a "$LOG_FILE"
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
    fi
    
    echo "SSH directory permissions:" | tee -a "$LOG_FILE"
    ls -la ~/.ssh | tee -a "$LOG_FILE"
}

# Run checks
echo "1. Checking required packages..." | tee -a "$LOG_FILE"
check_packages

echo "2. Checking port availability..." | tee -a "$LOG_FILE"
check_ports

echo "3. Checking SSH configuration..." | tee -a "$LOG_FILE"
check_ssh

echo "=== System Validation Complete ===" | tee -a "$LOG_FILE"
EOF

# 2. SSH Setup Script
cat >scripts/02_setup_ssh.sh <<'EOF'
#!/bin/bash
source ../config/tunnel_config.env

LOG_FILE="../$LOG_DIR/ssh_setup.log"

echo "=== SSH Setup Started ===" | tee -a "$LOG_FILE"

# Create SSH config
cat > ~/.ssh/config << SSHEOF
# Direct connection to GPU server
Host gpu-direct
    HostName ${GPU_DIRECT_HOST}
    Port ${GPU_DIRECT_PORT}
    User ${GPU_USER}
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 30
    ServerAliveCountMax 3

# Proxy connection via vast.ai
Host gpu-proxy
    HostName ${GPU_PROXY_HOST}
    Port ${GPU_PROXY_PORT}
    User ${GPU_USER}
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 30
    ServerAliveCountMax 3
SSHEOF

chmod 600 ~/.ssh/config

echo "=== SSH Setup Complete ===" | tee -a "$LOG_FILE"
EOF

# 3. Service Setup Script
cat >scripts/03_setup_service.sh <<'EOF'
#!/bin/bash
source ../config/tunnel_config.env

LOG_FILE="../$LOG_DIR/service_setup.log"

echo "=== Service Setup Started ===" | tee -a "$LOG_FILE"

# Create tunnel service
sudo tee /etc/systemd/system/gpu-tunnel.service << SERVICEEOF
[Unit]
Description=SSH tunnel to GPU server
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USER
Environment="AUTOSSH_GATETIME=0"
Environment="AUTOSSH_POLL=60"
ExecStart=/usr/bin/autossh -M 0 -N \\
    -o "ServerAliveInterval=30" \\
    -o "ServerAliveCountMax=3" \\
    -o "ExitOnForwardFailure=yes" \\
    -R ${TUNNEL_PORT}:localhost:${TUNNEL_PORT} \\
    gpu-direct

ExecStartPre=/bin/bash -c 'if ! timeout 5 ssh -q gpu-direct exit; then exit 1; fi'
ExecStartPost=/bin/bash -c 'if [ \$EXIT_STATUS -eq 1 ]; then exec /usr/bin/autossh -M 0 -N -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "ExitOnForwardFailure=yes" -R ${TUNNEL_PORT}:localhost:${TUNNEL_PORT} gpu-proxy; fi'

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Create monitor service
sudo tee /etc/systemd/system/gpu-tunnel-monitor.service << MONITOREOF
[Unit]
Description=GPU Tunnel Monitor
After=network.target gpu-tunnel.service

[Service]
Type=simple
User=$USER
ExecStart=$(pwd)/scripts/monitor_tunnel.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
MONITOREOF

sudo systemctl daemon-reload
sudo systemctl enable gpu-tunnel gpu-tunnel-monitor

echo "=== Service Setup Complete ===" | tee -a "$LOG_FILE"
EOF

# 4. Monitor Script (Enhanced version from previous discussion)
cat >scripts/monitor_tunnel.sh <<'EOF'
[Previous enhanced monitor script content]
EOF

# 5. Test Script
cat >scripts/test_connection.sh <<'EOF'
#!/bin/bash
source ../config/tunnel_config.env

echo "=== Testing Connections ==="

# Test direct connection
echo "Testing direct connection..."
ssh -o ConnectTimeout=5 gpu-direct "echo 'Direct connection successful'" || echo "Direct connection failed"

# Test proxy connection
echo "Testing proxy connection..."
ssh -o ConnectTimeout=5 gpu-proxy "echo 'Proxy connection successful'" || echo "Proxy connection failed"

# Test tunnel
echo "Testing tunnel..."
nc -zv localhost $TUNNEL_PORT
EOF

# Make all scripts executable
chmod +x scripts/*.sh

# Create README
cat >README.md <<'EOF'
# GPU Tunnel Setup

This package contains scripts to set up and maintain an SSH tunnel between a web server and GPU server.

## Setup Instructions

1. Edit `config/tunnel_config.env` with your specific settings
2. Run the scripts in order:
   ```bash
   ./scripts/01_validate_system.sh
   ./scripts/02_setup_ssh.sh
   ./scripts/03_setup_service.sh
   ```

3. Test the connection:
   ```bash
   ./scripts/test_connection.sh
   ```

4. Monitor the logs:
   ```bash
   tail -f logs/gpu-tunnel-monitor.log
   ```

## Directory Structure
- `config/` - Configuration files
- `scripts/` - Setup and monitoring scripts
- `logs/` - Log files

## Services
- `gpu-tunnel.service` - Main tunnel service
- `gpu-tunnel-monitor.service` - Tunnel monitoring service

## Troubleshooting
Check the logs in the `logs/` directory for detailed information about any issues.
EOF

echo "Setup suite created. Please edit config/tunnel_config.env before running the scripts."
