# syft-bg

Background service manager for SyftBox. Manages `syft-notify` (email notifications) and `syft-approve` (auto-approval).

## Setup

```bash
pip install syft-bg
syft-bg init
```

This prompts for your email, SyftBox directory, and runs OAuth for Gmail and Google Drive.

## Commands

```bash
syft-bg status         # Show service status
syft-bg start          # Start all services
syft-bg stop           # Stop all services
syft-bg restart        # Restart all services
syft-bg logs notify    # View notify logs
syft-bg logs approve   # View approve logs
syft-bg tui            # Launch TUI dashboard
```

Start/stop individual services:

```bash
syft-bg start notify
syft-bg stop approve
```

## Init Options

Skip interactive prompts for job validation:

```bash
syft-bg init -f main.py,params.json -j params.json:epsilon,delta -u alice@example.com
```

- `-f, --filenames`: Required files in jobs
- `-j, --json-keys`: Required keys in JSON files (`file:key1,key2`)
- `-u, --allowed-users`: Restrict to specific users

## Config

Stored at `~/.syft-creds/config.yaml` (Colab: `/content/drive/MyDrive/syft-creds/config.yaml`).

## Colab

Drive auth is handled natively:

```python
!pip install syft-bg
!syft-bg init
!syft-bg start
```
