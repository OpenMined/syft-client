# syft-approve

Auto-approval daemon for SyftBox jobs and peer requests.

## Features

- **Job auto-approval**: Automatically approve jobs from peers that match criteria
- **Peer auto-approval**: Automatically approve peer requests from trusted domains
- **Auto-share datasets**: Share datasets with newly approved peers

## Installation

```bash
pip install syft-approve
```

## CLI Usage

```bash
syft-approve init          # Interactive setup
syft-approve start         # Start daemon in background
syft-approve stop          # Stop daemon
syft-approve status        # Check daemon status
syft-approve run [--once]  # Run in foreground
syft-approve logs [-f]     # View logs
```

## Configuration

Edit `~/.syft-creds/config.yaml`:

```yaml
do_email: owner@example.com
syftbox_root: ~/SyftBox_owner@example.com

approve:
  interval: 5

  jobs:
    enabled: true
    peers_only: true
    required_scripts:
      main.py: |
        # expected script content
    required_filenames:
      - main.py
      - params.json

  peers:
    enabled: false
    approved_domains:
      - openmined.org
    auto_share_datasets:
      - my_dataset
```
