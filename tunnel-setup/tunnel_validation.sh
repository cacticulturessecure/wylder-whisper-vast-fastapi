#!/bin/bash

# tunnel_validation.sh
OUTPUT_FILE="tunnel_validation_$(date +%Y%m%d_%H%M%S).log"

echo "=== SSH Tunnel Validation ===" >"$OUTPUT_FILE"
echo "Timestamp: $(date)" >>"$OUTPUT_FILE"

# Verify SSH key for GPU server
echo -e "\n=== SSH Key Verification ===" >>"$OUTPUT_FILE"
echo "Checking SSH directory permissions:" >>"$OUTPUT_FILE"
ls -la ~/.ssh >>"$OUTPUT_FILE"

# Test SSH connection to GPU server (replace with your GPU server details)
echo -e "\n=== SSH Connection Test ===" >>"$OUTPUT_FILE"
echo "Please enter your GPU server IP address:"
read GPU_SERVER_IP
echo "Testing SSH connection to $GPU_SERVER_IP..." >>"$OUTPUT_FILE"
ssh -v -o ConnectTimeout=5 ubuntu@$GPU_SERVER_IP "echo 'Connection successful'" >>"$OUTPUT_FILE" 2>&1

# Verify port 8000 is really free
echo -e "\n=== Port 8000 Availability ===" >>"$OUTPUT_FILE"
echo "Checking if anything is listening on port 8000:" >>"$OUTPUT_FILE"
sudo lsof -i :8000 >>"$OUTPUT_FILE" 2>&1
sudo netstat -tulpn | grep :8000 >>"$OUTPUT_FILE" 2>&1

# Check for required packages
echo -e "\n=== Required Packages ===" >>"$OUTPUT_FILE"
echo "Checking for required packages:" >>"$OUTPUT_FILE"
for package in openssh-client openssh-server autossh netcat-openbsd; do
  dpkg -s $package >/dev/null 2>&1
  if [ $? -eq 0 ]; then
    echo "$package is installed" >>"$OUTPUT_FILE"
  else
    echo "$package needs to be installed" >>"$OUTPUT_FILE"
  fi
done

# Check firewall status
echo -e "\n=== Firewall Status ===" >>"$OUTPUT_FILE"
echo "UFW Status:" >>"$OUTPUT_FILE"
sudo ufw status verbose >>"$OUTPUT_FILE"

# Test local port binding
echo -e "\n=== Local Port Binding Test ===" >>"$OUTPUT_FILE"
echo "Testing if we can bind to port 8000:" >>"$OUTPUT_FILE"
(
  nc -l 8000 &
  pid=$!
  sleep 1
  kill $pid 2>/dev/null
) >>"$OUTPUT_FILE" 2>&1
if [ $? -eq 0 ]; then
  echo "Successfully bound to port 8000" >>"$OUTPUT_FILE"
else
  echo "Failed to bind to port 8000" >>"$OUTPUT_FILE"
fi

echo -e "\nValidation complete. Results saved to $OUTPUT_FILE"
