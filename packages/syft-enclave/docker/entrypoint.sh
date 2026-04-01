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

# Attestation server in background
uvicorn attestation_server:app --host 0.0.0.0 --port "$PORT" &

# Enclave runner as foreground process
POLL_INTERVAL="${POLL_INTERVAL:-10}"
ENCLAVE_EMAIL="${ENCLAVE_EMAIL:?ENCLAVE_EMAIL must be set}"

echo "Starting enclave runner for $ENCLAVE_EMAIL (poll=${POLL_INTERVAL}s)..."

RUNNER_ARGS="--email $ENCLAVE_EMAIL --poll-interval $POLL_INTERVAL"
if [ -n "$SYFTBOX_FOLDER" ]; then
    RUNNER_ARGS="$RUNNER_ARGS --syftbox-folder $SYFTBOX_FOLDER"
fi
if [ "${REQUIRE_TEE:-false}" = "true" ]; then
    RUNNER_ARGS="$RUNNER_ARGS --require-tee"
fi

exec python -m syft_enclaves $RUNNER_ARGS
