details for setup and order of scripts here - https://claude.ai/chat/a0be14b3-ad06-4a34-8d7e-2b0fc59b8be1



# GPU-WebServer Tunnel Testing Guide

## System Overview

### GPU Server Setup
Location: `/root/gpu-tunnel/`

Files needed:
- `test_setup.py` - The FastAPI server that receives and responds to messages

Requirements:
```bash
pip install fastapi uvicorn pydantic
```

### Local/Web Server Setup
Location: `~/gpu-tunnel/tests/`

Files needed:
- `test_client.py` - Client that sends test messages
- `test_runner_v2.sh` - Script that orchestrates the tests

Requirements:
```bash
pip install requests
```

## Setup Instructions

### 1. GPU Server Setup

```bash
# SSH into GPU server
ssh -p 40124 root@50.217.254.161

# Create directory
mkdir -p /root/gpu-tunnel
cd /root/gpu-tunnel

# Install requirements
pip install fastapi uvicorn pydantic

# Create server file
nano test_setup.py
# Paste the test_setup.py content

# Start the server
python test_setup.py
```

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 2. Local/Web Server Setup

```bash
# In your local/web server
cd ~/gpu-tunnel
mkdir tests
cd tests

# Install requirements
pip install requests

# Create test files
nano test_client.py
# Paste the test_client.py content

nano test_runner_v2.sh
# Paste the test_runner_v2.sh content

# Make runner executable
chmod +x test_runner_v2.sh
```

### 3. Verify Tunnel Connection

```bash
# Check if tunnel is active
nc -zv localhost 8000

# If tunnel is not active, start it
cd ~/gpu-tunnel
./scripts/03_setup_service.sh
sudo systemctl start gpu-tunnel
```

### 4. Run Tests

```bash
cd ~/gpu-tunnel/tests
./test_runner_v2.sh
```

## Component Description

### test_setup.py (GPU Server)
- FastAPI server that receives JSON messages
- Provides /health endpoint for connection verification
- Echoes received messages back with timestamps
- Runs on port 8000
- Logs all activity

### test_client.py (Local/Web Server)
- Sends test messages through the tunnel
- Verifies responses
- Measures round-trip time
- Provides detailed logging

### test_runner_v2.sh (Local/Web Server)
- Orchestrates the testing process
- Verifies tunnel connection
- Checks dependencies
- Runs test sequence
- Provides formatted output

## Common Issues and Solutions

1. "Connection refused" error:
   - Check if GPU server is running: `ps aux | grep test_setup.py`
   - Verify tunnel status: `systemctl status gpu-tunnel`

2. "Import error" messages:
   - Verify Python packages: `pip list | grep -E "fastapi|uvicorn|requests|pydantic"`
   - Install missing packages using pip

3. Permission issues:
   - Check file permissions: `ls -la`
   - Ensure correct ownership: `chown -R $USER:$USER ~/gpu-tunnel`

## Logging

Logs are stored in:
- GPU Server: `/root/gpu-tunnel/tunnel_test.log`
- Local/Web Server: `~/gpu-tunnel/tests/client_test.log`

View logs:
```bash
# On GPU server
tail -f /root/gpu-tunnel/tunnel_test.log

# On local/web server
tail -f ~/gpu-tunnel/tests/client_test.log
```

## Test Sequence Flow

1. test_runner_v2.sh verifies tunnel connection
2. Checks for required dependencies
3. test_client.py sends test messages
4. test_setup.py processes messages and responds
5. test_client.py verifies responses
6. test_runner_v2.sh reports results

## Success Criteria

Tests are considered successful when:
1. All test messages receive valid responses
2. No connection errors occur
3. Round-trip times are reasonable (<1000ms)
4. Health check passes

## Development Notes

- The test suite is designed to be extensible
- Additional test cases can be added to test_client.py
- Message formats can be modified in both test_setup.py and test_client.py
- Logging levels can be adjusted in both components
