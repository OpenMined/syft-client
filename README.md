# Syft-client

Peer-to-peer data science and AI via channels your organization already trusts (Google Workspace, Microsoft 365, etc.)

## Install

```
uv pip install syft-client
```

## Dev

```
uv pip install -e .
```

## Packages

- [`syft-datasets`](packages/syft-datasets) - Dataset management and sharing
- [`syft-job`](packages/syft-job) - Job submission and execution
- [`syft-permissions`](packages/syft-permissions) - Permission system for Syft datasites
- [`syft-perm`](packages/syft-perm) - User-facing permission API for Syft datasites
- [`syft-bg`](packages/syft-bg) - Background services TUI dashboard for SyftBox
- [`syft-notebook-ui`](packages/syft-notebook-ui) - Jupyter notebook display utilities

## Test

```
just test-unit
just test-integration
```
