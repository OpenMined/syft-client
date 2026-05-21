# syft-enclave

Enclave support for syft-client, enabling secure computation in Trusted Execution Environments (TEEs).

## About

- [Enclave Architecture](./docs/enclave_architecture.md)
- [API](.docs/api.md)

## Dev

**note: `[arg]` syntax in this document means that `arg` is optional (with default)**

```
uv pip install -e .
```

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

## Debugging

Production image features:

- No SSH access
- No container log redirection (serial logs only show launcher output)
- `tee-restart-policy=Never` shuts down the VM if the container exits
- `Hardened:true` in attestation claims

Debug image features:

- SSH access via `just ssh`
- Container stdout/stderr visible in serial logs (`just logs`)
- `tee-restart-policy=Always` keeps the VM running if the container crashes
- `tee-container-log-redirect=true` redirects container logs to serial output

### Debug deployment (recommended for initial setup)

The debug image allows SSH access and container log redirection to serial output, making it easier to troubleshoot issues.

```bash
just start-debug
```

## Building & pushing a new Docker Image

The image must be built for `linux/amd64` since GCP Confidential VMs run on AMD EPYC CPUs. On Apple Silicon, use the multi-arch recipe so the same tag works locally (arm64) and on GCP (amd64):

```bash
just build-push        # multi-arch (linux/amd64 + linux/arm64)
just build-push-amd    # amd64 only
```

Both push to `docker.io/openminedreleasebot/syft-client-enclave:latest`. You need push access to that Docker Hub namespace.

## Troubleshooting

| Symptom                                                 | Cause                                                         | Fix                                                                                       |
| ------------------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `exec format error` in serial logs                      | Docker image built for wrong architecture (arm64 on amd64 VM) | Rebuild with `just build-push` (multi-arch) or `just build-push-amd`                      |
| `unexpected_snp_attestation`                            | Used `SEV_SNP` instead of `SEV`                               | Confidential Spaces only supports `SEV` and `TDX`, not `SEV_SNP`                          |
| `logging redirection only allowed on debug environment` | Used `tee-container-log-redirect=true` with production image  | Use `just start-debug` instead of `just start`                                            |
| `403 Forbidden` pulling image                           | VM service account lacks Artifact Registry access             | Grant `roles/artifactregistry.reader` or use a public Docker Hub image                    |
| VM terminates immediately                               | Container crashed with `tee-restart-policy=Never`             | Switch to `just start-debug` to investigate                                               |
| `OnHostMaintenance` error                               | Missing `--maintenance-policy` flag                           | The recipes already set `--maintenance-policy=MIGRATE` for SEV; check you didn't override |
