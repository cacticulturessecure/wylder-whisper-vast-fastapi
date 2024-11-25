#!/bin/bash

# setup_gpu_tunnel.sh
LOG_FILE="tunnel_setup.log"

echo "=== Starting GPU Tunnel Setup ===" | tee -a "$LOG_FILE"
echo "Timestamp: $(date)" | tee -a "$LOG_FILE"

# Install required package
echo "Installing autossh..." | tee -a "$LOG_FILE"
sudo apt-get update && sudo apt-get install -y autossh

# Set up SSH config for easier connection management
echo "Configuring SSH..." | tee -a "$LOG_FILE"
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Create SSH config file
cat >~/.ssh/config <<EOF
# Direct connection to GPU server
Host gpu-direct
    HostName 50.217.254.161
    Port 40124
    User root
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 30
    ServerAliveCountMax 3

# Proxy connection via vast.ai
Host gpu-proxy
    HostName ssh4.vast.ai
    Port 11392
    User root
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 30
    ServerAliveCountMax 3
EOF

chmod 600 ~/.ssh/config

# Create systemd service for primary tunnel
sudo tee /etc/systemd/system/gpu-tunnel.service <<EOF
[Unit]
Description=SSH tunnel to GPU server
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=ubuntu
Environment="AUTOSSH_GATETIME=0"
Environment="AUTOSSH_POLL=60"
ExecStart=/usr/bin/autossh -M 0 -N \
    -o "ServerAliveInterval=30" \
    -o "ServerAliveCountMax=3" \
    -o "ExitOnForwardFailure=yes" \
    -R 8000:localhost:8000 \
    gpu-direct

# Fallback to proxy if primary fails
ExecStartPre=/bin/bash -c 'if ! timeout 5 ssh -q gpu-direct exit; then exit 1; fi'
ExecStartPost=/bin/bash -c 'if [ $EXIT_STATUS -eq 1 ]; then exec /usr/bin/autossh -M 0 -N -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "ExitOnForwardFailure=yes" -R 8000:localhost:8000 gpu-proxy; fi'

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create a test script
cat >~/test_gpu_connection.sh <<EOF
#!/bin/bash

echo "Testing GPU server connections..."

# Test direct connection
echo "Testing direct connection..."
ssh -o ConnectTimeout=5 gpu-direct "echo 'Direct connection successful'" || echo "Direct connection failed"

# Test proxy connection
echo "Testing proxy connection..."
ssh -o ConnectTimeout=5 gpu-proxy "echo 'Proxy connection successful'" || echo "Proxy connection failed"

# Test tunnel
echo "Testing tunnel (should be running on port 8000)..."
nc -zv localhost 8000
EOF

chmod +x ~/test_gpu_connection.sh

# Start the service
echo "Starting GPU tunnel service..." | tee -a "$LOG_FILE"
sudo systemctl daemon-reload
sudo systemctl enable gpu-tunnel
sudo systemctl start gpu-tunnel

# Monitor the service status
echo "Checking service status..." | tee -a "$LOG_FILE"
sudo systemctl status gpu-tunnel | tee -a "$LOG_FILE"

echo -e "\nSetup complete! To test connections, run: ./test_gpu_connection.sh"
