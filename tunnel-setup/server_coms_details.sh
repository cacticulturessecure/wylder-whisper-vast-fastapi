#!/bin/bash

# system_port_coms_details.sh
# Run this script on both web server and GPU server to gather system information

OUTPUT_FILE="$(hostname)_system_details.log"

echo "=== System Communication Details ===" >"$OUTPUT_FILE"
echo "Timestamp: $(date)" >>"$OUTPUT_FILE"
echo "Hostname: $(hostname)" >>"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"

# System Details
echo "=== System Information ===" >>"$OUTPUT_FILE"
echo "Operating System:" >>"$OUTPUT_FILE"
cat /etc/os-release >>"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"

# Network Interface Information
echo "=== Network Interfaces ===" >>"$OUTPUT_FILE"
ip addr show | grep -E "^[0-9]+:|inet " >>"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"

# Current Listening Ports
echo "=== Currently Listening Ports ===" >>"$OUTPUT_FILE"
ss -tulpn >>"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"

# Check if specific ports are available
echo "=== Port Availability Check ===" >>"$OUTPUT_FILE"
for port in 22 8000 3000 8001 8002 8003; do
  nc -zv localhost $port &>/dev/null
  if [ $? -eq 0 ]; then
    echo "Port $port is in use" >>"$OUTPUT_FILE"
  else
    echo "Port $port is available" >>"$OUTPUT_FILE"
  fi
done
echo "" >>"$OUTPUT_FILE"

# Check SSH Configuration
echo "=== SSH Configuration ===" >>"$OUTPUT_FILE"
if [ -f /etc/ssh/sshd_config ]; then
  echo "SSH Server Configuration:" >>"$OUTPUT_FILE"
  grep -v "^#" /etc/ssh/sshd_config | grep . >>"$OUTPUT_FILE"
fi
echo "" >>"$OUTPUT_FILE"

# Check Firewall Status
echo "=== Firewall Status ===" >>"$OUTPUT_FILE"
if command -v ufw &>/dev/null; then
  echo "UFW Status:" >>"$OUTPUT_FILE"
  ufw status >>"$OUTPUT_FILE"
elif command -v firewall-cmd &>/dev/null; then
  echo "FirewallD Status:" >>"$OUTPUT_FILE"
  firewall-cmd --list-all >>"$OUTPUT_FILE"
fi
echo "" >>"$OUTPUT_FILE"

# Test SSH Keys
echo "=== SSH Key Configuration ===" >>"$OUTPUT_FILE"
if [ -d ~/.ssh ]; then
  echo "Available SSH Keys:" >>"$OUTPUT_FILE"
  ls -l ~/.ssh/ >>"$OUTPUT_FILE"
  echo "" >>"$OUTPUT_FILE"
  echo "SSH Key Permissions:" >>"$OUTPUT_FILE"
  ls -la ~/.ssh >>"$OUTPUT_FILE"
fi
echo "" >>"$OUTPUT_FILE"

# Check if netcat is installed
echo "=== Required Tools Check ===" >>"$OUTPUT_FILE"
for tool in nc ssh netstat lsof; do
  if command -v $tool &>/dev/null; then
    echo "$tool is installed" >>"$OUTPUT_FILE"
  else
    echo "$tool is NOT installed" >>"$OUTPUT_FILE"
  fi
done
echo "" >>"$OUTPUT_FILE"

# Memory and CPU Information
echo "=== System Resources ===" >>"$OUTPUT_FILE"
echo "Memory Information:" >>"$OUTPUT_FILE"
free -h >>"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"
echo "CPU Information:" >>"$OUTPUT_FILE"
lscpu | grep -E "^CPU\(s\):|^Thread|^Core|^Model name" >>"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"

# Current System Load
echo "=== System Load ===" >>"$OUTPUT_FILE"
uptime >>"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"

echo "=== Test SSH Connection ===" >>"$OUTPUT_FILE"
# Don't store actual credentials in the script
echo "To test SSH connection, run manually:" >>"$OUTPUT_FILE"
echo "ssh -v -p 22 user@remote_host" >>"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"

echo "System details have been saved to $OUTPUT_FILE"

# Make the file readable only by the owner
chmod 600 "$OUTPUT_FILE"
