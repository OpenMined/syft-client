#!/bin/bash
set -euo pipefail

TEE_SOCKET="/run/container_launcher/teeserver.sock"

echo "=== Syft Client Enclave Server ==="
echo "syft-client version: $(python -c 'from syft_client import __version__; print(__version__)' 2>/dev/null || echo 'unknown')"

if [ -S "$TEE_SOCKET" ]; then
    echo "Confidential Spaces detected: TEE socket found at $TEE_SOCKET"
else
    echo "WARNING: TEE socket not found at $TEE_SOCKET"
    echo "Attestation endpoint will return instructions instead of real attestation data."
    echo "To enable attestation, deploy this container on a GCP Confidential VM with Confidential Spaces."
fi

PORT="${PORT:-8080}"
echo "Starting attestation server on port $PORT..."

exec uvicorn attestation_server:app --host 0.0.0.0 --port "$PORT"
