# syft-bg

Background services for SyftBox: email notifications and auto-approval for peers and jobs.

## Installation

```bash
pip install syft-bg
```

## Quick Start

```bash
syft-bg init      # Interactive setup wizard
syft-bg start     # Start background services
syft-bg status    # Check what's running
```

### Headless Mode

```bash
# Fully automated (tokens must already exist)
syft-bg init --email user@example.com --quiet

# With custom settings
syft-bg init \
  --email user@example.com \
  --syftbox-root ~/SyftBox \
  --notify-jobs \
  --approve-jobs \
  --skip-oauth
```

### Pythonic API (Notebooks/Scripts)

```python
import syft_bg

result = syft_bg.init(
    email="user@example.com",
    notify_jobs=True,
    approve_jobs=True,
    skip_oauth=True,
)

if result.success:
    print(f"Config saved to {result.config_path}")
```

## Commands

```bash
syft-bg                    # TUI dashboard
syft-bg init               # Setup wizard (interactive or headless)
syft-bg setup              # Check environment (credentials, tokens, config)
syft-bg status             # Show service status
syft-bg start [service]    # Start all or specific service
syft-bg stop [service]     # Stop all or specific service
syft-bg restart [service]  # Restart all or specific service
syft-bg logs <service>     # View logs (notify or approve)
syft-bg hash <file>        # Generate script hash for auto-approval
syft-bg install            # Install systemd service (auto-start on boot)
syft-bg uninstall          # Remove systemd service
```

## CLI Flags for `syft-bg init`

| Flag                                     | Description                                     |
| ---------------------------------------- | ----------------------------------------------- |
| `--email, -e`                            | Data Owner email address                        |
| `--syftbox-root`                         | SyftBox directory path                          |
| `--yes, -y`                              | Auto-confirm config overwrite                   |
| `--quiet, -q`                            | No prompts, use defaults (implies --skip-oauth) |
| `--skip-oauth`                           | Skip OAuth setup (tokens must exist)            |
| `--notify-jobs/--no-notify-jobs`         | Job email notifications                         |
| `--notify-peers/--no-notify-peers`       | Peer email notifications                        |
| `--notify-interval`                      | Notification check interval (seconds)           |
| `--approve-jobs/--no-approve-jobs`       | Auto-approve jobs                               |
| `--jobs-peers-only/--no-jobs-peers-only` | Only approve jobs from approved peers           |
| `--approve-peers/--no-approve-peers`     | Auto-approve peers                              |
| `--approved-domains`                     | Comma-separated domains for peer approval       |
| `--approve-interval`                     | Approval check interval (seconds)               |
| `--filenames`                            | Required filenames (comma-separated)            |
| `--allowed-users`                        | Allowed users (comma-separated emails)          |
| `--credentials-path`                     | Path to credentials.json                        |
| `--gmail-token`                          | Path to existing Gmail token                    |
| `--drive-token`                          | Path to existing Drive token                    |

## Environment Check

```bash
$ syft-bg setup

SYFT-BG ENVIRONMENT CHECK
==================================================

Checking credentials...
  ✓ credentials.json found at ~/.syft-creds/credentials.json

Checking authentication tokens...
  ✓ Gmail token: ~/.syft-creds/gmail_token.json
  ✓ Drive token: ~/.syft-creds/token_do.json

Checking configuration...
  ✓ Config file: ~/.syft-creds/config.yaml

--------------------------------------------------
✅ Environment ready! Run 'syft-bg start' to begin.
```

## OAuth Setup

Two OAuth flows are required (same credentials.json, separate tokens):

1. **Gmail** → `gmail_token.json` (send email permission)
2. **Drive** → `token_do.json` (read/write files permission)

**Interactive mode**: Prints OAuth URL, you paste the authorization code back.

**Headless mode** (`--quiet`): Skips OAuth, requires tokens to already exist.

To get credentials.json:

1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download as credentials.json
4. Place at `~/.syft-creds/credentials.json`

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
do_email: you@example.com
syftbox_root: ~/SyftBox

notify:
  interval: 30
  monitor_jobs: true
  monitor_peers: true

approve:
  interval: 5
  jobs:
    enabled: true
    peers_only: true
    required_filenames:
      - main.py
      - params.json
    required_scripts: {} # sha256 hashes
    allowed_users: [] # empty = all approved peers
  peers:
    enabled: false
    approved_domains:
      - openmined.org
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

## Colab / Jupyter

```python
!pip install syft-bg

import syft_bg

# Initialize with Pythonic API
result = syft_bg.init(
    email="user@example.com",
    notify_jobs=True,
    approve_jobs=True,
    verbose=True,  # Show progress
)

# Or use CLI
!syft-bg init --email user@example.com --quiet
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
