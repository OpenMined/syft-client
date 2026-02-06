# syft-bg

Background services for SyftBox: email notifications and auto-approval for peers and jobs.

## Installation

```bash
pip install syft-bg
```

## Quick Start

```bash
syft-bg init      # Configure email, SyftBox path, OAuth for Gmail/Drive
syft-bg start     # Start background services
syft-bg status    # Check what's running
```

## Commands

```bash
syft-bg                    # TUI dashboard
syft-bg init               # Setup wizard
syft-bg status             # Show service status
syft-bg start [service]    # Start all or specific service
syft-bg stop [service]     # Stop all or specific service
syft-bg restart [service]  # Restart all or specific service
syft-bg logs <service>     # View logs (notify or approve)
syft-bg hash <file>        # Generate script hash for auto-approval
syft-bg install            # Install systemd service (auto-start on boot)
syft-bg uninstall          # Remove systemd service
```

## Services

### notify

Sends email notifications via Gmail when:

- A peer requests to connect with you
- Your peer request is approved by someone
- A data scientist submits a job to you
- A job you submitted is approved
- A job completes (results ready)

### approve

Auto-approves peers and jobs based on your config:

- **Peers**: Auto-accept connection requests
- **Jobs**: Auto-approve if script hash and filenames match allowed criteria

## Configuration

Config stored at `~/.syft-creds/config.yaml` (Colab: `/content/drive/MyDrive/syft-creds/config.yaml`).

```yaml
user_email: you@example.com
syftbox_folder: ~/SyftBox

# Auto-approval rules
approve:
  peers:
    auto_approve: true # Accept all peer requests
  jobs:
    allowed_script_hashes:
      - 'sha256:abc123...' # Only approve matching hashes
    required_filenames:
      - main.py
      - params.json
    allowed_users: [] # Empty = allow all users

# Notification settings
notify:
  enabled: true
```

After editing, restart services:

```bash
syft-bg restart
```

## Script Hash Validation

Data owners can restrict auto-approval to specific scripts:

```bash
# Generate hash for a script
syft-bg hash main.py
# Output: sha256:a1b2c3d4...

# Add to config.yaml
approve:
  jobs:
    allowed_script_hashes:
      - "sha256:a1b2c3d4..."
```

Jobs with non-matching scripts require manual approval.

## Systemd Integration

Auto-start syft-bg on boot (Linux):

```bash
syft-bg install    # Creates ~/.config/systemd/user/syft-bg.service
systemctl --user enable syft-bg
systemctl --user start syft-bg

# Check status
systemctl --user status syft-bg

# Remove
syft-bg uninstall
```

## Logs

```bash
syft-bg logs notify     # Notification service logs
syft-bg logs approve    # Approval service logs
syft-bg logs notify -f  # Follow logs in real-time
```

Log files stored at `~/.syft-creds/logs/`.

## Colab

```python
!pip install syft-bg
!syft-bg init
!syft-bg start
!syft-bg status
```

Drive credentials are handled natively in Colab.

## Development

Run services in foreground for debugging:

```bash
syft-bg run --service notify   # Run notify in foreground
syft-bg run --service approve  # Run approve in foreground
syft-bg run --once             # Single check cycle, then exit
```
