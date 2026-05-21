# syft-enclave

Enclave support for syft-client, enabling secure computation in Trusted Execution Environments (TEEs).

## Dev

```
uv pip install -e .
```

## Running the enclave runner

The runner is configured entirely through `SYFT_ENCLAVE_*` environment
variables — there is no command-line interface, because the runner is always
started programmatically (by the Confidential Spaces launcher in production,
or from a `.env` file during local development). Start it with:

```
python -m syft_enclaves
```

| Variable                      | Required | Default           | Description                             |
| ----------------------------- | -------- | ----------------- | --------------------------------------- |
| `SYFT_ENCLAVE_EMAIL`          | yes      | —                 | Enclave datasite email                  |
| `SYFT_ENCLAVE_SYFTBOX_FOLDER` | no       | `~/SyftBox_email` | Root SyftBox folder                     |
| `SYFT_ENCLAVE_TOKEN_PATH`     | yes      | —                 | Pre-authorized Google Drive OAuth token |
| `SYFT_ENCLAVE_POLL_INTERVAL`  | no       | `10`              | Seconds between poll cycles             |
| `SYFT_ENCLAVE_REQUIRE_TEE`    | no       | `false`           | Refuse to start outside a TEE           |
| `SYFT_ENCLAVE_LOG_LEVEL`      | no       | `INFO`            | Logging level                           |

For local development, place these in a `.env` file in the working directory.
The same `python -m syft_enclaves` entry point runs unchanged locally, inside
Docker, and in Confidential Spaces — only the environment differs.

## Architecture

See [Enclave Architecture](../../docs/enclave_architecture/README.md) for detailed deployment and architecture documentation.
