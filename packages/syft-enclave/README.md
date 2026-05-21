# syft-enclave

Enclave support for syft-client, enabling secure computation in Trusted Execution Environments (TEEs).

## About

- [Enclave Architecture](./docs/enclave_architecture.md)
- [API](.docs/api.md)

## Dev

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

This stores `project_id` (and zone, default `us-central1-a`) in `~/syft-enclaves/settings.json`, and runs `gcloud config set project`. Every other recipe reads `project_id` from this file. Pass a custom zone with `just init YOUR_PROJECT_ID europe-west4-a`.

### Production deployment

For production, use the hardened image. This disables SSH, log redirection, and debugging.

```bash
just start                                # defaults: syft-enclave-vm, n2d-standard-2
just start my-vm europe-west4-a n2d-standard-4   # override name / zone / machine type
```

`just start` runs the one-time provisioning steps (enable APIs, grant the default compute service account `roles/confidentialcomputing.workloadUser`, create the `allow-enclave-http` firewall rule on tcp:8080) and then creates a Confidential Space VM running the image at `docker.io/openminedreleasebot/syft-client-enclave:latest`.

Production image differences:

- No SSH access
- No container log redirection (serial logs only show launcher output)
- `tee-restart-policy=Never` shuts down the VM if the container exits
- `Hardened:true` in attestation claims

### Inspect a running VM

Each of these takes an optional `name` and `zone` (defaults: `syft-enclave-vm` and the zone from `settings.json`):

```bash
just status [name] [zone]   # RUNNING / TERMINATED / etc.
just get-ip [name] [zone]   # external IP
just logs   [name] [zone]   # last 50 lines of serial output
just ssh    [name] [zone]   # debug image only
```

## Debugging

### Debug deployment (recommended for initial setup)

The debug image allows SSH access and container log redirection to serial output, making it easier to troubleshoot issues.

```bash
just start-debug
```

Debug image features:

- SSH access via `just ssh`
- Container stdout/stderr visible in serial logs (`just logs`)
- `tee-restart-policy=Always` keeps the VM running if the container crashes
- `tee-container-log-redirect=true` redirects container logs to serial output

## Cleanup

```bash
just stop [name] [zone]
```

Deletes the VM and removes the `allow-enclave-http` firewall rule. The firewall rule is recreated automatically the next time you run `just start` or `just start-debug`.

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
