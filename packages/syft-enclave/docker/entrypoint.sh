#!/bin/bash
set -euo pipefail

TEE_SOCKET="/run/container_launcher/teeserver.sock"

echo "=== Syft Client Enclave Server ==="
echo "syft-client version: $(python -c 'from syft_client import __version__; print(__version__)' 2>/dev/null || echo 'unknown')"

# Token bootstrap: write SYFT_ENCLAVE_TOKEN_CONTENT (shipped via tee-env from
# `just start`) to SYFT_ENCLAVE_TOKEN_PATH. The default below MUST match the
# default in src/syft_enclaves/settings.py.
: "${SYFT_ENCLAVE_TOKEN_PATH:=/run/syft-enclave/token.json}"
export SYFT_ENCLAVE_TOKEN_PATH

if [ -n "${SYFT_ENCLAVE_TOKEN_CONTENT:-}" ]; then
    mkdir -p "$(dirname "$SYFT_ENCLAVE_TOKEN_PATH")"
    (umask 077 && printf '%s' "$SYFT_ENCLAVE_TOKEN_CONTENT" > "$SYFT_ENCLAVE_TOKEN_PATH")
    chmod 600 "$SYFT_ENCLAVE_TOKEN_PATH"
    unset SYFT_ENCLAVE_TOKEN_CONTENT
    echo "wrote token to $SYFT_ENCLAVE_TOKEN_PATH"
else
    echo "no SYFT_ENCLAVE_TOKEN_CONTENT provided, expecting token at $SYFT_ENCLAVE_TOKEN_PATH"
fi

if [ -S "$TEE_SOCKET" ]; then
    echo "Confidential Spaces detected: TEE socket found at $TEE_SOCKET"
else
    echo "WARNING: TEE socket not found at $TEE_SOCKET"
    echo "Attestation endpoint will return instructions instead of real attestation data."
    echo "To enable attestation, deploy this container on a GCP Confidential VM with Confidential Spaces."
fi

# Attestation server (background) — configured via PORT.
PORT="${PORT:-8080}"
echo "Starting attestation server on port $PORT..."
uvicorn attestation_server:app --host 0.0.0.0 --port "$PORT" &

# Enclave runner (foreground) — configured entirely via SYFT_ENCLAVE_* env vars.
# See syft_enclaves.settings.EnclaveSettings for the full list of variables.
echo "Starting enclave runner..."
exec python -m syft_enclaves
