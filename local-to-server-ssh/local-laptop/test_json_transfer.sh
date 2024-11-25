#!/bin/bash
# test_json_transfer.sh - Test script for generating and transferring JSON files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
OUTGOING_DIR="${BASE_DIR}/data/outgoing"

# Generate test JSON file
generate_test_json() {
  local timestamp=$(date -Iseconds)
  local filename="test_${timestamp}.json"

  cat >"${OUTGOING_DIR}/${filename}" <<EOF
{
    "test_id": "$(uuidgen || echo "test-${RANDOM}")",
    "timestamp": "${timestamp}",
    "data": {
        "message": "Test transfer at ${timestamp}",
        "random_value": ${RANDOM},
        "source": "local_laptop"
    }
}
EOF

  echo "Generated: ${filename}"
}

# Generate specified number of test files
count=${1:-1}
echo "Generating ${count} test JSON files..."

for ((i = 1; i <= count; i++)); do
  generate_test_json
  sleep 1
done

echo "Test files generated in ${OUTGOING_DIR}"
