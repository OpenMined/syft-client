# Syft Client Enclave - Confidential Spaces Deployment

This directory contains a Docker image that packages `syft-client` with an HTTP attestation server. When deployed on Google Confidential Spaces, the `/attestation` endpoint returns a cryptographically signed TEE attestation report.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  GCP Confidential VM (AMD SEV - encrypted memory)   │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  Confidential Space OS (hardened, read-only)  │  │
│  │                                               │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │  TEE Container Launcher                 │  │  │
│  │  │  - Pulls & verifies container image     │  │  │
│  │  │  - Exposes attestation Unix socket      │  │  │
│  │  │  - Manages container lifecycle          │  │  │
│  │  └──────────────┬──────────────────────────┘  │  │
│  │                 │                              │  │
│  │  ┌──────────────▼──────────────────────────┐  │  │
│  │  │  syft-client-enclave container          │  │  │
│  │  │  - FastAPI server on port 8080          │  │  │
│  │  │  - Fetches attestation via Unix socket  │  │  │
│  │  │  - Returns signed JWT with TEE claims   │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

- Docker with buildx support (Docker Desktop includes this)
- A Docker Hub account (or GCP Artifact Registry)
- A GCP project with billing enabled
- `gcloud` CLI installed and authenticated

### Enable required GCP APIs

```bash
gcloud services enable \
  compute.googleapis.com \
  confidentialcomputing.googleapis.com
```

### Grant attestation permissions to the default compute service account

```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='get(projectNumber)')

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/confidentialcomputing.workloadUser"
```

## Building the Docker Image

The image must be built for `linux/amd64` since GCP Confidential VMs run on AMD EPYC CPUs. If you're on an Apple Silicon Mac, use `docker buildx` to build a multi-architecture image:

```bash
# Create a buildx builder (one-time setup)
docker buildx create --name multiarch --use

# Build for both amd64 (GCP) and arm64 (Mac) and push
docker buildx build --platform linux/amd64,linux/arm64 \
  -t docker.io/YOUR_DOCKERHUB_USERNAME/syft-client-enclave:latest \
  -f docker/Dockerfile \
  --push \
  .
```

If you only need amd64 (for GCP only):

```bash
docker build --platform linux/amd64 \
  -t docker.io/YOUR_DOCKERHUB_USERNAME/syft-client-enclave:latest \
  -f docker/Dockerfile .

docker push docker.io/YOUR_DOCKERHUB_USERNAME/syft-client-enclave:latest
```

## Deploying to Google Confidential Spaces

### Confidential Computing support

Confidential Spaces supports the following confidential compute types:

| Type  | Description                         | Machine Types       |
| ----- | ----------------------------------- | ------------------- |
| `SEV` | AMD Secure Encrypted Virtualization | `n2d-*` (AMD Milan) |
| `TDX` | Intel Trust Domain Extensions       | `c3-*`              |

> **Note:** AMD SEV-SNP is NOT supported by Confidential Spaces (only by raw Confidential VMs). Use `SEV` for Confidential Spaces deployments.

### Debug deployment (recommended for initial setup)

The debug image allows SSH access and container log redirection to serial output, making it easier to troubleshoot issues.

```bash
gcloud compute instances create syft-enclave-vm \
  --zone=us-central1-a \
  --machine-type=n2d-standard-2 \
  --confidential-compute-type=SEV \
  --shielded-secure-boot \
  --maintenance-policy=MIGRATE \
  --min-cpu-platform="AMD Milan" \
  --image-family=confidential-space-debug \
  --image-project=confidential-space-images \
  --scopes=cloud-platform \
  --tags=http-server \
  --metadata="^~^tee-image-reference=docker.io/YOUR_DOCKERHUB_USERNAME/syft-client-enclave:latest~tee-restart-policy=Always~tee-container-log-redirect=true"
```

Debug image features:

- SSH access via `gcloud compute ssh syft-enclave-vm --zone=us-central1-a`
- Container stdout/stderr visible in serial logs
- `tee-restart-policy=Always` keeps the VM running if the container crashes
- `tee-container-log-redirect=true` redirects container logs to serial output

### Production deployment

For production, use the hardened image. This disables SSH, log redirection, and debugging.

```bash
gcloud compute instances create syft-enclave-vm \
  --zone=us-central1-a \
  --machine-type=n2d-standard-2 \
  --confidential-compute-type=SEV \
  --shielded-secure-boot \
  --maintenance-policy=MIGRATE \
  --min-cpu-platform="AMD Milan" \
  --image-family=confidential-space \
  --image-project=confidential-space-images \
  --scopes=cloud-platform \
  --tags=http-server \
  --metadata="^~^tee-image-reference=docker.io/YOUR_DOCKERHUB_USERNAME/syft-client-enclave:latest~tee-restart-policy=Never"
```

Production image differences:

- No SSH access
- No container log redirection (serial logs only show launcher output)
- `tee-restart-policy=Never` shuts down the VM if the container exits
- `Hardened:true` in attestation claims

### Firewall rule (one-time setup)

Allow external traffic to port 8080:

```bash
gcloud compute firewall-rules create allow-enclave-http \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:8080 \
  --target-tags=http-server \
  --source-ranges=0.0.0.0/0
```

## Checking Logs and Status

### Get the VM's external IP

```bash
gcloud compute instances describe syft-enclave-vm \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

### Check VM status

```bash
gcloud compute instances describe syft-enclave-vm \
  --zone=us-central1-a \
  --format='get(status)'
```

### View serial port logs

This shows the Confidential Space launcher output and (with debug image) container logs:

```bash
gcloud compute instances get-serial-port-output syft-enclave-vm \
  --zone=us-central1-a 2>&1 | tail -50
```

To see only new output since the last check:

```bash
gcloud compute instances get-serial-port-output syft-enclave-vm \
  --zone=us-central1-a --start=OFFSET 2>&1 | tail -30
```

### SSH into the VM (debug image only)

```bash
gcloud compute ssh syft-enclave-vm --zone=us-central1-a
```

## API Endpoints

Once the container is running, the following endpoints are available at `http://EXTERNAL_IP:8080`:

| Endpoint           | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| `GET /`            | Landing page with syft-client version and available endpoints     |
| `GET /attestation` | TEE attestation report (signed JWT with hardware/software claims) |
| `GET /health`      | Health check                                                      |
| `GET /docs`        | FastAPI auto-generated Swagger UI                                 |

### Example: Fetching the attestation report

```bash
curl http://EXTERNAL_IP:8080/attestation | python3 -m json.tool
```

The response includes:

- `attestation.hardware.hwmodel` - TEE hardware type (`GCP_AMD_SEV`)
- `attestation.hardware.secboot` - Secure boot status
- `attestation.hardware.dbgstat` - Debug status (`enabled` for debug image, `disabled-since-boot` for production)
- `attestation.container.image_digest` - SHA256 of the running container image
- `attestation.gce.*` - GCP project, zone, instance info
- `raw_token` - Full JWT for independent verification against Google's JWKS

## Cleanup

```bash
# Delete the VM
gcloud compute instances delete syft-enclave-vm --zone=us-central1-a --quiet

# Optionally remove the firewall rule
gcloud compute firewall-rules delete allow-enclave-http --quiet
```

## Troubleshooting

| Symptom                                                 | Cause                                                         | Fix                                                                                        |
| ------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `exec format error` in serial logs                      | Docker image built for wrong architecture (arm64 on amd64 VM) | Rebuild with `--platform linux/amd64`                                                      |
| `unexpected_snp_attestation`                            | Used `SEV_SNP` instead of `SEV`                               | Confidential Spaces only supports `SEV` and `TDX`, not `SEV_SNP`                           |
| `logging redirection only allowed on debug environment` | Used `tee-container-log-redirect=true` with production image  | Either remove the flag or use `confidential-space-debug` image                             |
| `403 Forbidden` pulling image                           | VM service account lacks Artifact Registry access             | Grant `roles/artifactregistry.reader` or use a public Docker Hub image                     |
| VM terminates immediately                               | Container crashed with `tee-restart-policy=Never`             | Switch to debug image with `tee-restart-policy=Always` to investigate                      |
| `OnHostMaintenance` error                               | Missing `--maintenance-policy` flag                           | Add `--maintenance-policy=MIGRATE` (SEV) or `--maintenance-policy=TERMINATE` (SEV_SNP/TDX) |
