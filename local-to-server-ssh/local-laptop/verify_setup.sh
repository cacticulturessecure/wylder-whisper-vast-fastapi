#!/bin/bash
# verify_setup.sh - Verify local setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "Verifying local setup..."

# Check directory structure
echo -n "Checking directories... "
for dir in config logs data/outgoing data/sent; do
  if [ ! -d "${BASE_DIR}/${dir}" ]; then
    echo "FAILED"
    echo "Missing directory: ${dir}"
    exit 1
  fi
done
echo "OK"

# Check SSH key
echo -n "Checking SSH key... "
if ! ls ${BASE_DIR}/config/vast_ai_* >/dev/null 2>&1; then
  echo "FAILED"
  echo "No SSH key found"
  exit 1
fi
echo "OK"

# Check configuration
echo -n "Checking configuration... "
if [ ! -f "${BASE_DIR}/config/tunnel_config.json" ]; then
  echo "FAILED"
  echo "Missing configuration file"
  exit 1
fi
echo "OK"

# Test SSH connection
echo "Testing SSH connection..."
KEY_PATH=$(ls ${BASE_DIR}/config/vast_ai_* | grep -v '.pub$' | head -1)
GPU_HOST=$(grep -o '"host": "[^"]*' "${BASE_DIR}/config/tunnel_config.json" | grep -o '[^"]*$')
GPU_PORT=$(grep -o '"port": "[^"]*' "${BASE_DIR}/config/tunnel_config.json" | grep -o '[^"]*$')

ssh -i "$KEY_PATH" -p "$GPU_PORT" "root@${GPU_HOST}" "echo 'SSH connection successful'" || {
  echo "SSH connection failed"
  exit 1
}

echo "Local setup verification complete"
