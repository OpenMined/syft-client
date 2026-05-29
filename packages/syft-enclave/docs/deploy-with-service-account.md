# Deploy the Enclave with a Service Account

## End-to-end flow

```bash
cd packages/syft-enclave
```

### Step 1 — Initialize the project (one-time)

```bash
just init YOUR_PROJECT_ID            # zone defaults to us-central1-a
```

Writes `~/.syft-enclaves/settings.json` with `project_id` and `zone`.

### Step 2 — Mint the syft-client token (if you don't have one already)

```bash
just credentials-to-token credentials.json token.json
chmod 600 token.json                 # treat as a credential
```

Converts a Google OAuth `credentials.json` into the runtime `token.json`
that the enclave will consume.

### Step 3 — Provision the secret + dedicated SA (one-time per project)

```bash
just provision-secret-sa token.json
```

### Step 4 — Deploy the VM

Debug image (SSH + container-log redirect to serial — use during testing):

```bash
just start-debug-sa ENCLAVE_EMAIL
```

Production image (hardened, no SSH):

```bash
just start-sa ENCLAVE_EMAIL
```

### Step 5 — Verify

```bash
just status                          # → RUNNING
just logs 500                        # check serial output
```

In the logs you want to see (in order):

```
bootstrap: provider=sa
bootstrap: wrote N bytes to /run/syft-enclave/token.json
... INFO syft_enclaves.runner: Enclave runner starting ...
... INFO syft_enclaves.runner: init step 1/3: initializing ...
```

### Tear down everything

```bash
just teardown-sa                      # interactive [y/N] prompt
# or
CONFIRM_TEARDOWN=yes just teardown-sa # for CI / automation
```

Mirrors `provision-secret-sa`: removes the IAM binding → deletes the SA →
deletes the secret (and all versions) → clears `sa_email`, `secret_name`,
`secret_resource` from `settings.json`.

`just teardown-sa` does **not** delete the VM. Run `just stop` first if
one is still running.
