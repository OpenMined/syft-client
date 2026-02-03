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
syft-approve hash <file>   # Generate hash for script validation
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
    required_filenames:
      - main.py
      - params.json
    required_scripts:
      main.py: sha256:a1b2c3d4e5f6a1b2

  peers:
    enabled: false
    approved_domains:
      - openmined.org
    auto_share_datasets:
      - my_dataset
```

## Script Validation

To validate that submitted jobs contain the exact script you approved:

1. Generate hash of your approved script:

   ```bash
   syft-approve hash main.py
   # sha256:a1b2c3d4e5f6a1b2
   ```

2. Add to config:
   ```yaml
   required_filenames:
     - main.py
     - params.json
   required_scripts:
     main.py: sha256:a1b2c3d4e5f6a1b2
   ```

Jobs are approved only if:

- All files in `required_filenames` are present (no extra, no missing)
- Files in `required_scripts` match the expected hash
