#!/bin/bash

OUTPUT_FILE="webserver_additional_checks.log"

echo "=== Additional System Checks ===" >"$OUTPUT_FILE"
echo "Timestamp: $(date)" >>"$OUTPUT_FILE"

# Check SSH key details
echo -e "\n=== SSH Key Details ===" >>"$OUTPUT_FILE"
ls -la ~/.ssh/ >>"$OUTPUT_FILE"

# Check UFW status
echo -e "\n=== UFW Firewall Status ===" >>"$OUTPUT_FILE"
sudo ufw status verbose >>"$OUTPUT_FILE"

# Check available ports we might want to use
echo -e "\n=== Testing Potential Tunnel Ports ===" >>"$OUTPUT_FILE"
for port in 8000 8001 8002 8003 3000; do
  nc -zv localhost $port 2>&1 >>"$OUTPUT_FILE"
done

# Check system resources
echo -e "\n=== System Resources ===" >>"$OUTPUT_FILE"
echo "Memory:" >>"$OUTPUT_FILE"
free -h >>"$OUTPUT_FILE"
echo -e "\nCPU:" >>"$OUTPUT_FILE"
nproc >>"$OUTPUT_FILE"
lscpu | grep "CPU MHz" >>"$OUTPUT_FILE"

# Check systemd service status
echo -e "\n=== Systemd Service Status ===" >>"$OUTPUT_FILE"
systemctl list-units --type=service --state=running | grep -E "nginx|docker|ssh" >>"$OUTPUT_FILE"

# Check SSH daemon configuration
echo -e "\n=== SSH Daemon Configuration ===" >>"$OUTPUT_FILE"
grep -v "^#" /etc/ssh/sshd_config | grep . >>"$OUTPUT_FILE"

# Check current established connections
echo -e "\n=== Current Established Connections ===" >>"$OUTPUT_FILE"
ss -tuln >>"$OUTPUT_FILE"

# Check if required packages are installed
echo -e "\n=== Required Packages Check ===" >>"$OUTPUT_FILE"
for pkg in netcat-openbsd openssh-server autossh; do
  dpkg -l | grep -E "^ii\s+$pkg" >>"$OUTPUT_FILE"
done

chmod 600 "$OUTPUT_FILE"
