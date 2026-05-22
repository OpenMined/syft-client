# syft-enclave

Enclave support for syft-client, enabling secure computation in Trusted Execution Environments (TEEs).

## About

- [Enclave Architecture](./docs/enclave_architecture.md)
- [API](./docs/api.md)

## Prerequisites

- Docker with buildx support (Docker Desktop includes this)
- `gcloud` [CLI installed](https://docs.cloud.google.com/sdk/docs/install-sdk)
- A GCP project with billing enabled
- [`just`](https://github.com/casey/just) and `jq`

All commands are defined in the [`Justfile`](./Justfile). Run them from this directory.

## One-time setup

```bash
just init YOUR_PROJECT_ID
```

This stores settings in `~/.syft-enclaves/settings.json` and sets the active gcloud project. Every other recipe reads `project_id` and `zone` from this file — zone is **not** a per-call arg. To deploy in a different zone, re-run `just init YOUR_PROJECT_ID europe-west4-a`.

## Production deployment

Hardened image — no SSH access, TEE enforcement enabled.

```bash
just start EMAIL TOKEN_PATH                          # defaults: syft-enclave-vm, n2d-standard-2
just start EMAIL TOKEN_PATH my-vm n2d-standard-4     # override name / machine type
just stop [name]                                     # Teardown: Deletes VM and removes firewall rule.
```

The first run also provisions APIs, IAM roles, and firewall rules (idempotent).

## Debug deployment

Debug image — SSH enabled, container logs redirected to serial output.

```bash
just start-debug EMAIL TOKEN_PATH                          # defaults: syft-enclave-vm, n2d-standard-2
just start-debug EMAIL TOKEN_PATH my-vm n2d-standard-4     # override name / machine type
just stop [name]                                           # Teardown: Deletes VM and removes firewall rule.
```

## Inspect a running VM

All inspect commands take an optional `name` (default: `syft-enclave-vm`). Zone is always read from `settings.json`.

```bash
# Works on both production and debug
just status [name]   # RUNNING / TERMINATED / etc.
just get-ip [name]   # external IP
just attest [name]   # fetch TEE attestation report

# Debug only
just ssh    [name]   # SSH into the VM (production image disables SSH)
just logs   [name]   # last 50 lines of serial output (production only shows boot logs;
                     # debug redirects container logs to serial output)
```
