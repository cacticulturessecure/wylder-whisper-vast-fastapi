#!/bin/bash

# test_runner_v2.sh
set -e

# Colors and logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

LOG_FILE="tunnel_tests_$(date +%Y%m%d_%H%M%S).log"

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"; }

# Function to check if port is in use
check_port() {
    local port=$1
    nc -z localhost $port 2>/dev/null
    return $?
}

# Function to verify tunnel
verify_tunnel() {
    log "Verifying SSH tunnel..."
    if ! check_port 8000; then
        error "Port 8000 is not accessible. Is the tunnel running?"
        return 1
    fi
    log "Tunnel verification successful"
    return 0
}

# Function to check dependencies
check_dependencies() {
    log "Checking Python dependencies..."
    pip install -q requests fastapi uvicorn pydantic
    
    if ! command -v python3 >/dev/null 2>&1; then
        error "Python3 is not installed"
        return 1
    fi
    
    if ! command -v nc >/dev/null 2>&1; then
        error "netcat is not installed"
        return 1
    }
    
    log "Dependencies verified"
    return 0
}

# Main test sequence
main() {
    log "Starting improved test sequence"
    
    # Verify dependencies
    if ! check_dependencies; then
        error "Dependency check failed"
        exit 1
    fi
    
    # Verify tunnel
    if ! verify_tunnel; then
        error "Tunnel verification failed"
        exit 1
    }
    
    # Start test server (in background)
    log "Starting test server..."
    python3 test_setup.py &
    SERVER_PID=$!
    
    # Wait for server to start
    sleep 2
    
    # Run client tests
    log "Running client tests..."
    python3 test_client.py 5
    TEST_RESULT=$?
    
    # Cleanup
    kill $SERVER_PID 2>/dev/null
    
    if [ $TEST_RESULT -eq 0 ]; then
        log "All tests completed successfully"
    else
        error "Some tests failed"
        exit 1
    fi
}

# Run main function
main "$@"
