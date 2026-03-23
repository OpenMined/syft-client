# syft-bg

Background services for SyftBox: email notifications and auto-approval for peers and jobs.


## Installation

```bash
pip install syft-bg
```

##

**[Python API docs](docs/python-api.md)** — for python api docs, go here instead.

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

### Python API

For notebooks and scripts, see the [Python API docs](docs/python-api.md).

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
syft-bg hash <file>        # Generate script hash for a file
syft-bg set-script         # Set approved scripts for peers
syft-bg remove-script      # Remove approved scripts from peers
syft-bg remove-peer        # Remove a peer from config
syft-bg list-scripts       # List approved scripts per peer
syft-bg install            # Install systemd service (auto-start on boot)
syft-bg uninstall          # Remove systemd service
```

## Per-Peer Script Approval

Data owners can restrict job auto-approval on a per-peer basis.
Each peer gets a list of approved scripts (name + SHA256 hash).
Only jobs that match every submitted `.py` file against the approved list are auto-approved.

### Setting up approved scripts

```bash
# Approve a single script for one or more peers
syft-bg set-script main.py -p alice@uni.edu -p bob@co.com

# Approve multiple scripts
syft-bg set-script main.py utils.py -p charlie@org.com

# Approve all .py files in a directory
syft-bg set-script ./src/ -p alice@uni.edu

# Replace all existing scripts (instead of adding)
syft-bg set-script main.py -p alice@uni.edu --replace
```

### Managing scripts and peers

```bash
# List all peers and their approved scripts
syft-bg list-scripts

# List scripts for a specific peer
syft-bg list-scripts -p alice@uni.edu

# Remove a script from a peer
syft-bg remove-script utils.py -p alice@uni.edu

# Remove a peer entirely
syft-bg remove-peer alice@uni.edu
```

### How validation works

When a job is submitted, the approval service checks:

1. The submitting peer must be in the `peers` config
2. Every `.py` file in the job must match an approved script name
3. The SHA256 hash of each file must match the approved hash

Rejection reasons are specific: "unknown peer", "unapproved file", "hash mismatch".

## CLI Flags for `syft-bg init`

| Flag                                 | Description                                          |
| ------------------------------------ | ---------------------------------------------------- |
| `--email, -e`                        | Data Owner email address                             |
| `--syftbox-root`                     | SyftBox directory path                               |
| `--yes, -y`                          | Auto-confirm config overwrite                        |
| `--quiet, -q`                        | No prompts, use defaults (implies --skip-oauth)      |
| `--skip-oauth`                       | Skip OAuth setup (tokens must exist)                 |
| `--notify-jobs/--no-notify-jobs`     | Job email notifications                              |
| `--notify-peers/--no-notify-peers`   | Peer email notifications                             |
| `--notify-interval`                  | Notification check interval (seconds)                |
| `--approve-jobs/--no-approve-jobs`   | Auto-approve jobs                                    |
| `--approve-peers/--no-approve-peers` | Auto-approve peers                                   |
| `--approved-domains`                 | Approved domains for peer approval (comma-separated) |
| `--approve-interval`                 | Approval check interval (seconds)                    |
| `--credentials-path`                 | Path to credentials.json                             |
| `--gmail-token`                      | Path to existing Gmail token                         |
| `--drive-token`                      | Path to existing Drive token                         |

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
- A job is rejected (with reason sent to the data scientist)

DO notifications are threaded per job (new → approved/rejected → completed in one Gmail conversation).

### approve

Auto-approves peers and jobs based on your config:

- **Peers**: Auto-accept connection requests from approved domains
- **Jobs**: Auto-approve if every submitted script matches an approved name + hash for that peer

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
    peers:
      alice@uni.edu:
        mode: strict
        scripts:
          - name: main.py
            hash: 'sha256:a1b2c3d4...'
          - name: utils.py
            hash: 'sha256:e5f6a7b8...'
      bob@co.com:
        mode: strict
        scripts:
          - name: main.py
            hash: 'sha256:c9d0e1f2...'
  peers:
    enabled: false
    approved_domains:
      - openmined.org
```

After editing, restart services:

```bash
syft-bg restart
```

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

See the [Python API docs](docs/python-api.md) for programmatic usage. Drive credentials are handled natively in Colab.

## Development

Run services in foreground for debugging:

```bash
syft-bg run --service notify   # Run notify in foreground
syft-bg run --service approve  # Run approve in foreground
syft-bg run --once             # Single check cycle, then exit
```
