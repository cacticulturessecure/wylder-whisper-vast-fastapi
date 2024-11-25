#!/bin/bash

# Enhanced monitor_tunnel.sh
LOG_FILE="/var/log/gpu-tunnel-monitor.log"
LOCK_FILE="/var/run/gpu-tunnel-monitor.lock"
PID_FILE="/var/run/gpu-tunnel-monitor.pid"

# Setup signal handling
cleanup() {
  echo "$(date): Monitor shutdown initiated" >>"$LOG_FILE"
  rm -f "$LOCK_FILE"
  rm -f "$PID_FILE"
  exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP

# Ensure only one instance runs
if [ -f "$LOCK_FILE" ]; then
  existing_pid=$(cat "$PID_FILE" 2>/dev/null)
  if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "Monitor already running with PID $existing_pid"
    exit 1
  fi
fi

# Create lock and pid files
echo $$ >"$PID_FILE"
touch "$LOCK_FILE"

# Ensure log file exists and is writable
if [ ! -f "$LOG_FILE" ]; then
  sudo touch "$LOG_FILE"
  sudo chown $USER:$USER "$LOG_FILE"
fi

# Log rotation function
rotate_log() {
  if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE") -gt 10485760 ]; then
    cp "$LOG_FILE" "$LOG_FILE.$(date +%Y%m%d-%H%M%S)"
    echo "$(date): Log rotation performed" >"$LOG_FILE"
    find "$(dirname "$LOG_FILE")" -name "$(basename "$LOG_FILE").*" -mtime +7 -delete
  fi
}

check_tunnel() {
  local retries=3
  local retry_count=0

  while [ $retry_count -lt $retries ]; do
    if nc -z -w 5 localhost 8000; then
      echo "$(date): Tunnel is UP on port 8000"
      return 0
    fi
    retry_count=$((retry_count + 1))
    [ $retry_count -lt $retries ] && sleep 2
  done

  echo "$(date): Tunnel is DOWN on port 8000 after $retries attempts"
  return 1
}

check_gpu_connection() {
  local host=$1
  ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" "echo 'Connection test'" >/dev/null 2>&1
  return $?
}

restart_tunnel() {
  echo "$(date): Attempting to restart GPU tunnel service..." >>"$LOG_FILE"

  # First try direct connection
  if check_gpu_connection "gpu-direct"; then
    echo "$(date): Direct connection available, restarting service..." >>"$LOG_FILE"
    sudo systemctl restart gpu-tunnel
    sleep 5

    if check_tunnel; then
      echo "$(date): Tunnel successfully restored via direct connection" >>"$LOG_FILE"
      return 0
    fi
  fi

  # Try fallback to proxy
  echo "$(date): Attempting fallback to proxy connection..." >>"$LOG_FILE"
  if check_gpu_connection "gpu-proxy"; then
    sudo systemctl stop gpu-tunnel

    # Kill any existing autossh sessions
    pkill -f "autossh.*:8000"

    # Start new proxy connection
    autossh -M 0 -N \
      -o "ServerAliveInterval=30" \
      -o "ServerAliveCountMax=3" \
      -o "ExitOnForwardFailure=yes" \
      -R 8000:localhost:8000 gpu-proxy &

    sleep 5
    if check_tunnel; then
      echo "$(date): Tunnel successfully established via proxy" >>"$LOG_FILE"
      return 0
    fi
  fi

  echo "$(date): Failed to establish tunnel through either connection" >>"$LOG_FILE"
  return 1
}

# Main monitoring loop with error handling
main_loop() {
  local consecutive_failures=0
  local max_failures=5

  while true; do
    rotate_log

    if ! check_tunnel >>"$LOG_FILE" 2>&1; then
      consecutive_failures=$((consecutive_failures + 1))
      echo "$(date): Failure count: $consecutive_failures" >>"$LOG_FILE"

      if [ $consecutive_failures -ge $max_failures ]; then
        echo "$(date): Maximum failures reached. Alerting administrator..." >>"$LOG_FILE"
        # Add your alert mechanism here (email, SMS, etc.)
        consecutive_failures=0
      fi

      restart_tunnel
    else
      consecutive_failures=0
    fi

    sleep 60
  done
}

# Start the main loop with error handling
echo "$(date): Starting GPU tunnel monitor" >>"$LOG_FILE"
main_loop >>"$LOG_FILE" 2>&1

# Cleanup on exit
cleanup
