[![Unit Tests](https://github.com/OpenMined/syft-client/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/OpenMined/syft-client/actions/workflows/unit-tests.yml)
[![Integration Tests](https://github.com/OpenMined/syft-client/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/OpenMined/syft-client/actions/workflows/integration-tests.yml)
[![PyPI](https://img.shields.io/pypi/v/syft-client)](https://pypi.org/project/syft-client/)
[![Python 3.10+](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FOpenMined%2Fsyft-client%2Fmain%2Fpyproject.toml)](https://github.com/OpenMined/syft-client)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/OpenMined/syft-client/blob/main/pyproject.toml)

# Syft-client

Syft client lets data scientists submit computations which are ran by data owners on private data — all through cloud storage their organizations already use (Google Drive, Microsoft 365, etc.). No new infrastructure required.

## Docs

- [Workflow](docs/workflow.md) — End-to-end privacy-preserving data analysis workflow
- [API Reference](docs/API.md) — All public client methods and properties
- [Authentication & Setup](docs/auth.md) — Google Cloud OAuth setup for local/Jupyter usage
- [Background Services](packages/syft-bg/README.md) — Email notifications, auto-approval, and TUI dashboard

## Features

- **Privacy-preserving** — Private data never leaves the data owner's machine; only approved results are shared
- **Transport-agnostic** — Works over Google Drive today, extensible to any file-based transport
- **Offline-first** — Full functionality even when peers are offline; changes sync when connectivity resumes
- **Peer-to-peer with explicit auth** — Data owners must approve each collaborator before any data flows
- **Isolated job execution** — Jobs run in sandboxed Python virtual environments with controlled access to private data
- **Dataset sharing with mock/private separation** — Data scientists explore mock data, then submit jobs that run on the real thing

## Quick Start

```
uv pip install syft-client
```

```python
import syft_client as sc
```

```python
# Login (colab auth, for non-colab pass token_path)
do = sc.login_do(email="do@org.com")
ds = sc.login_ds(email="ds@org.com")

# Peer request & approve
ds.add_peer("do@org.com")
do.approve_peer_request("ds@org.com")

# Create dataset
do.create_dataset(
    name="census",
    mock_path="mock/",
    private_path="private/",
    users=["ds@org.com"],
)
do.sync(); ds.sync()
datasets = ds.datasets.get_all()

# Submit job
ds.submit_python_job(
    user="do@org.com",
    code_path="analysis.py",
)
ds.sync(); do.sync()

# Approve & run job
do.jobs[0].approve()
do.process_approved_jobs()
do.sync(); ds.sync()
result = open(ds.jobs[-1].output_paths[0]).read()
```

## Packages

| Package                                         | Description                                   |
| ----------------------------------------------- | --------------------------------------------- |
| [`syft-datasets`](packages/syft-datasets)       | Dataset management and sharing                |
| [`syft-job`](packages/syft-job)                 | Job submission and execution                  |
| [`syft-permissions`](packages/syft-permissions) | Permission system for Syft datasites          |
| [`syft-perm`](packages/syft-perm)               | User-facing permission API for Syft datasites |
| [`syft-bg`](packages/syft-bg)                   | Background services TUI dashboard for SyftBox |
| [`syft-notebook-ui`](packages/syft-notebook-ui) | Jupyter notebook display utilities            |

## Development

```bash
# Install in development mode
uv pip install -e .

# Run tests
just test-unit          # Unit tests (fast, mocked)
just test-integration   # Integration tests (slow, real API)
```

---

Built by [OpenMined](https://openmined.org) — building open-source technology for privacy-preserving data science and AI.
