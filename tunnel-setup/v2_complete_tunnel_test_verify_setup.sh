#!/bin/bash

# Set up error handling
set -e
trap 'echo "Error occurred on line $LINENO. Exit code: $?" >&2' ERR

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
  echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
  echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warn() {
  echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
  error "Please do not run this script as root"
  exit 1
fi

# Base directory setup
BASE_DIR="$HOME/gpu-tunnel"
log "Setting up directory structure in $BASE_DIR"

# Create directory structure with verbose output
mkdir -pv "$BASE_DIR"/{scripts,logs,config}

# Change to base directory
cd "$BASE_DIR" || {
  error "Failed to change to $BASE_DIR"
  exit 1
}

# Verify directory structure
log "Verifying directory structure..."
for dir in scripts logs config; do
  if [ ! -d "$dir" ]; then
    error "Failed to create $dir directory"
    exit 1
  fi
  log "✓ $dir directory created"
done

# Create configuration file
log "Creating configuration file..."
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

# Create validation script
log "Creating validation script..."
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

echo "1. Checking required packages..." | tee -a "$LOG_FILE"
check_packages

echo "2. Checking port availability..." | tee -a "$LOG_FILE"
check_ports

echo "3. Checking SSH configuration..." | tee -a "$LOG_FILE"
check_ssh

echo "=== System Validation Complete ===" | tee -a "$LOG_FILE"
EOF

# Create SSH setup script
log "Creating SSH setup script..."
cat >scripts/02_setup_ssh.sh <<'EOF'
#!/bin/bash
source ../config/tunnel_config.env

LOG_FILE="../$LOG_DIR/ssh_setup.log"

echo "=== SSH Setup Started ===" | tee -a "$LOG_FILE"

# Create SSH config
cat > ~/.ssh/config << SSHEOF
# Direct connection to GPU server
Host gpu-direct
    HostName \${GPU_DIRECT_HOST}
    Port \${GPU_DIRECT_PORT}
    User \${GPU_USER}
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 30
    ServerAliveCountMax 3

# Proxy connection via vast.ai
Host gpu-proxy
    HostName \${GPU_PROXY_HOST}
    Port \${GPU_PROXY_PORT}
    User \${GPU_USER}
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 30
    ServerAliveCountMax 3
SSHEOF

chmod 600 ~/.ssh/config

echo "=== SSH Setup Complete ===" | tee -a "$LOG_FILE"
EOF

# Create service setup script
log "Creating service setup script..."
cat >scripts/03_setup_service.sh <<'EOF'
#!/bin/bash
source ../config/tunnel_config.env

LOG_FILE="../$LOG_DIR/service_setup.log"

echo "=== Service Setup Started ===" | tee -a "$LOG_FILE"

# Create services
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
    -R \${TUNNEL_PORT}:localhost:\${TUNNEL_PORT} \\
    gpu-direct

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable gpu-tunnel

echo "=== Service Setup Complete ===" | tee -a "$LOG_FILE"
EOF

# Create monitor script
log "Creating monitor script..."
cat >scripts/monitor_tunnel.sh <<'EOF'
#!/bin/bash
source ../config/tunnel_config.env

LOG_FILE="../$LOG_DIR/gpu-tunnel-monitor.log"
LOCK_FILE="/var/run/gpu-tunnel-monitor.lock"
PID_FILE="/var/run/gpu-tunnel-monitor.pid"

trap 'rm -f $LOCK_FILE $PID_FILE; exit 0' SIGTERM SIGINT SIGHUP

if [ -f "$LOCK_FILE" ]; then
    exit 1
fi

echo $$ > "$PID_FILE"
touch "$LOCK_FILE"

check_tunnel() {
    if nc -z localhost $TUNNEL_PORT; then
        echo "$(date): Tunnel is UP on port $TUNNEL_PORT"
        return 0
    else
        echo "$(date): Tunnel is DOWN on port $TUNNEL_PORT"
        return 1
    fi
}

while true; do
    if ! check_tunnel >> "$LOG_FILE"; then
        echo "$(date): Attempting to restart tunnel..." >> "$LOG_FILE"
        sudo systemctl restart gpu-tunnel
    fi
    sleep $MONITOR_INTERVAL
done
EOF

# Create test script
log "Creating test script..."
cat >scripts/test_connection.sh <<'EOF'
#!/bin/bash
source ../config/tunnel_config.env

echo "=== Testing Connections ==="

echo "Testing direct connection..."
ssh -o ConnectTimeout=5 gpu-direct "echo 'Direct connection successful'" || echo "Direct connection failed"

echo "Testing proxy connection..."
ssh -o ConnectTimeout=5 gpu-proxy "echo 'Proxy connection successful'" || echo "Proxy connection failed"

echo "Testing tunnel..."
nc -zv localhost $TUNNEL_PORT
EOF

# Make scripts executable
log "Setting executable permissions..."
chmod +x scripts/*.sh

# Create initial log files
log "Creating log files..."
touch logs/system_validation.log
touch logs/ssh_setup.log
touch logs/service_setup.log
touch logs/gpu-tunnel-monitor.log

# Display next steps
echo
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo
echo "Next steps:"
echo "1. Edit configuration:"
echo "   nano $BASE_DIR/config/tunnel_config.env"
echo
echo "2. Run the setup scripts in order:"
echo "   cd $BASE_DIR"
echo "   ./scripts/01_validate_system.sh"
echo "   ./scripts/02_setup_ssh.sh"
echo "   ./scripts/03_setup_service.sh"
echo
echo "3. Test the connection:"
echo "   ./scripts/test_connection.sh"
echo
echo "4. Monitor the logs:"
echo "   tail -f $BASE_DIR/logs/gpu-tunnel-monitor.log"

# Display directory structure
log "Final directory structure:"
tree "$BASE_DIR" 2>/dev/null || ls -R "$BASE_DIR"
