# Systemd Service for syft-notify

This directory contains a systemd service file for running `syft-notify` as a system service on Linux servers.

## Installation

### 1. Install syft-client

```bash
pip install syft-client
# or
uv pip install syft-client
```

### 2. Run Initial Setup

```bash
syft-notify init
```

This creates:

- `~/.syft-creds/daemon.yaml` (config)
- `~/.syft-creds/gmail_token.json` (Gmail OAuth)
- `~/.syft-creds/token_do.json` (Drive OAuth)

### 3. Install Systemd Service

```bash
# Copy service file to systemd directory
sudo cp syft-notify.service /etc/systemd/system/syft-notify@.service

# If using a virtualenv, edit the service file first:
sudo nano /etc/systemd/system/syft-notify@.service
# Change ExecStart to: /path/to/venv/bin/syft-notify start

# Reload systemd
sudo systemctl daemon-reload

# Enable service for your user (replace USERNAME with your username)
sudo systemctl enable syft-notify@USERNAME

# Start service
sudo systemctl start syft-notify@USERNAME
```

## Usage

### Check Status

```bash
sudo systemctl status syft-notify@USERNAME
```

### View Logs

```bash
# View systemd journal
sudo journalctl -u syft-notify@USERNAME -f

# Or view daemon logs directly
tail -f ~/.syft-creds/syft-notify.log
```

### Stop/Start/Restart

```bash
sudo systemctl stop syft-notify@USERNAME
sudo systemctl start syft-notify@USERNAME
sudo systemctl restart syft-notify@USERNAME
```

### Disable Auto-Start

```bash
sudo systemctl disable syft-notify@USERNAME
```

## Service Features

- **Auto-start on boot**: Service starts automatically when the system boots
- **Auto-restart on failure**: If the daemon crashes, it will automatically restart after 10 seconds
- **Log persistence**: Logs are saved to `~/.syft-creds/syft-notify.log`
- **Security hardening**: Service runs with restricted permissions

## Troubleshooting

### Service fails to start

1. Check logs:

   ```bash
   sudo journalctl -u syft-notify@USERNAME -n 50
   ```

2. Verify config exists:

   ```bash
   ls -la ~/.syft-creds/daemon.yaml
   ```

3. Test manually first:
   ```bash
   syft-notify run --once
   ```

### Permission issues

Make sure the service file has the correct paths:

```bash
# Edit service file
sudo nano /etc/systemd/system/syft-notify@.service

# Verify User and WorkingDirectory match your setup
```

### Token expiration

If Gmail/Drive tokens expire, re-run setup:

```bash
syft-notify init
sudo systemctl restart syft-notify@USERNAME
```

## Alternative: User Service (No sudo required)

You can also install as a user service (doesn't require sudo):

```bash
# Create user systemd directory
mkdir -p ~/.config/systemd/user/

# Copy service file (without @ template)
cp syft-notify.service ~/.config/systemd/user/syft-notify.service

# Edit to remove %i placeholders and use absolute paths
nano ~/.config/systemd/user/syft-notify.service

# Reload and enable
systemctl --user daemon-reload
systemctl --user enable syft-notify
systemctl --user start syft-notify

# Check status
systemctl --user status syft-notify

# Enable lingering (service persists after logout)
loginctl enable-linger $USER
```

## Log Rotation

Logs automatically rotate when they reach 10MB (keeps 7 old files). This is handled by the daemon itself via Python's `RotatingFileHandler`.

To manually rotate logs:

```bash
syft-notify stop
mv ~/.syft-creds/syft-notify.log ~/.syft-creds/syft-notify.log.old
syft-notify start
```
