# syft-enclave

Enclave support for syft-client, enabling secure computation in Trusted Execution Environments (TEEs).

## About

- [Enclave Architecture](./docs/enclave_architecture.md)
- [API](./docs/api.md)

## Dev

**note: `[arg]` syntax in this document means that `arg` is optional (with default)**

```
uv pip install -e .
```

## Deploy

**note: `[arg]` syntax in this document means that `arg` is optional (with default)**

### Prerequisites

- Docker with buildx support (Docker Desktop includes this)
- `gcloud` [CLI installed](https://docs.cloud.google.com/sdk/docs/install-sdk)
- A GCP project with billing enabled
- [`just`](https://github.com/casey/just) and `jq`

All deploy / inspect / teardown commands below are `just` recipes defined in [`./Justfile`](./Justfile). Run them from this directory.

### One-time setup

```bash
just init YOUR_PROJECT_ID
```

This stores settings in `~/syft-enclaves/settings.json` and sets the active gcloud project. Every other recipe reads `project_id` and `zone` from this file — zone is **not** a per-call arg. To deploy in a different zone, re-run `just init YOUR_PROJECT_ID europe-west4-a`.

### Production deployment

#### Start

`just start` runs the one-time provisioning steps and then creates a Confidential Space VM

```bash
just start                          # defaults: syft-enclave-vm, n2d-standard-2
just start my-vm n2d-standard-4     # override name / machine type
```

#### stop

```bash
just stop [name]
```

Deletes the VM and all related objects.

### Inspect a running VM

Each of these takes an optional `name` (default: `syft-enclave-vm`). Zone is always read from `settings.json`.

```bash
just status [name]   # RUNNING / TERMINATED / etc.
just get-ip [name]   # external IP
just logs   [name]   # last 50 lines of serial output
just ssh    [name]   # debug image only
```
