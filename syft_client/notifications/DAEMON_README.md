# SyftBox Notification Daemon

Background daemon for monitoring SyftBox job and peer events with email notifications.

## Features

- ✅ **Background daemon**: Survives terminal closure
- ✅ **Auto-restart**: Automatically recovers from crashes
- ✅ **Log rotation**: Automatically manages log files (10MB x 7 files)
- ✅ **Direct Drive polling**: Lightweight, no full sync needed
- ✅ **Email notifications**: HTML templated emails via Gmail
- ✅ **Systemd integration**: Optional system service setup

## Quick Start

### 1. Install

```bash
pip install syft-client
# or
uv pip install syft-client
```

### 2. Setup

```bash
syft-notify init
```

This creates:

- `~/.syft-creds/daemon.yaml` - Configuration
- `~/.syft-creds/gmail_token.json` - Gmail OAuth token
- `~/.syft-creds/token_do.json` - Google Drive OAuth token

### 3. Start Daemon

```bash
# Background mode (survives terminal closure)
syft-notify start

# Foreground mode (for testing)
syft-notify run
```

## Commands

### Daemon Management

```bash
# Start daemon in background
syft-notify start
syft-notify start --interval 60  # Custom interval

# Stop daemon
syft-notify stop

# Restart daemon
syft-notify restart

# Check status
syft-notify status
```

### Logs

```bash
# View last 50 lines
syft-notify logs

# View last 100 lines
syft-notify logs --lines 100

# Follow logs (like tail -f)
syft-notify logs --follow
```

### Debugging

```bash
# Run in foreground (Ctrl+C to stop)
syft-notify run

# Run with custom config
syft-notify run --config /path/to/config.yaml

# Run with custom interval
syft-notify run --interval 60

# Single check (no loop)
syft-notify run --once

# Monitor only jobs
syft-notify run --jobs-only

# Monitor only peers
syft-notify run --peers-only
```

## Configuration

Edit `~/.syft-creds/daemon.yaml`:

```yaml
do_email: test1@openmined.org
syftbox_root: /home/user/SyftBox_test1@openmined.org
drive_token_path: /home/user/.syft-creds/token_do.json
gmail_token_path: /home/user/.syft-creds/gmail_token.json
interval: 30 # Check every 30 seconds
```

## File Locations

```
~/.syft-creds/
├── daemon.yaml                 # Configuration
├── gmail_token.json            # Gmail OAuth token
├── token_do.json               # Google Drive OAuth token
├── notification_state.json     # Tracks sent notifications
├── syft-notify.pid             # Daemon process ID
├── syft-notify.log             # Main log file (rotates at 10MB)
├── syft-notify.log.1-7         # Rotated logs (kept)
└── syft-notify.error.log       # Error log (stderr)
```

## Notification Types

### Job Notifications

| Event        | Recipient | Trigger                  |
| ------------ | --------- | ------------------------ |
| New Job      | DO        | DS submits job via Drive |
| Job Approved | DS        | DO runs `job.approve()`  |
| Job Executed | DS        | DO runs job              |

### Peer Notifications

| Event        | Recipient | Trigger                           |
| ------------ | --------- | --------------------------------- |
| Peer Request | DO        | DS adds DO as peer                |
| Request Sent | DS        | DO receives peer request          |
| Peer Granted | DS        | DO accepts (manual call required) |

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Google Drive                                    │
│  ├─ syft_outbox_inbox_DS_to_DO/                 │
│  │   └─ msgv2_*.tar.gz  (job submissions)       │
│  └─ SyftBox_DO/                                  │
│      └─ app_data/job/  (local jobs)             │
└──────────────────────────────────────────────────┘
                    ▲
                    │ Poll every 30s
                    │
┌──────────────────────────────────────────────────┐
│  syft-notify daemon                              │
│  ├─ JobMonitor    (polls Drive + local)         │
│  ├─ PeerMonitor   (polls Drive)                 │
│  └─ GmailSender   (sends emails)                │
└──────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────┐
│  Email (Gmail API)                               │
│  ✉️  HTML templated notifications                │
└──────────────────────────────────────────────────┘
```

## Production Deployment

### Option 1: Systemd Service (Recommended)

See [systemd/README.md](./systemd/README.md) for full instructions.

```bash
# Install service
sudo cp syft_client/notifications/systemd/syft-notify.service \
  /etc/systemd/system/syft-notify@.service

# Enable and start
sudo systemctl enable syft-notify@USERNAME
sudo systemctl start syft-notify@USERNAME

# Check status
sudo systemctl status syft-notify@USERNAME
```

### Option 2: Screen/Tmux

```bash
# Start in screen session
screen -dmS syft-notify syft-notify start

# Reattach
screen -r syft-notify

# Or with tmux
tmux new -s syft-notify -d syft-notify start
tmux attach -t syft-notify
```

### Option 3: Supervisor

```ini
; /etc/supervisor/conf.d/syft-notify.conf
[program:syft-notify]
command=/usr/local/bin/syft-notify run
directory=/home/user
user=user
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/user/.syft-creds/syft-notify.log
```

## Logging Integration

The daemon outputs structured logs suitable for centralized logging systems.

See [LOGGING_INTEGRATION.md](./LOGGING_INTEGRATION.md) for:

- Filebeat (Elasticsearch)
- Fluentd
- CloudWatch Logs (AWS)
- Google Cloud Logging
- Grafana Loki
- Syslog

## Monitoring

### Health Check Script

```bash
#!/bin/bash
# check_syft_notify.sh

if syft-notify status > /dev/null 2>&1; then
    echo "OK: syft-notify is running"
    exit 0
else
    echo "CRITICAL: syft-notify is not running"
    exit 2
fi
```

### Nagios/Icinga Plugin

```bash
# Add to Nagios
define command {
    command_name    check_syft_notify
    command_line    /usr/local/bin/check_syft_notify.sh
}
```

### Metrics from Logs

```bash
# Count notifications per hour
grep "✅ Sent" ~/.syft-creds/syft-notify.log | \
  awk '{print $1" "$2}' | cut -d':' -f1 | uniq -c

# Count errors
grep "ERROR" ~/.syft-creds/syft-notify.log | wc -l

# Check last notification time
grep "✅ Sent" ~/.syft-creds/syft-notify.log | tail -1
```

## Troubleshooting

### Daemon won't start

```bash
# Check if already running
syft-notify status

# Check logs for errors
syft-notify logs --lines 100

# Test in foreground mode
syft-notify run --once

# Verify config
cat ~/.syft-creds/daemon.yaml
```

### No notifications received

1. Check Gmail spam folder
2. Verify tokens are valid:
   ```bash
   ls -la ~/.syft-creds/*.json
   ```
3. Run in foreground to see real-time output:
   ```bash
   syft-notify run
   ```
4. Check notification state:
   ```bash
   cat ~/.syft-creds/notification_state.json
   ```

### Stale PID file

```bash
# Remove stale PID file
rm ~/.syft-creds/syft-notify.pid

# Try starting again
syft-notify start
```

### Token expired

```bash
# Re-run setup
syft-notify init

# Restart daemon
syft-notify restart
```

## Development

### Run from source

```bash
cd /path/to/syft-client
uv run syft-notify run
```

### Debug mode

```python
# In monitor.py, increase logging verbosity
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test notifications

```bash
# Single check (no loop)
syft-notify run --once

# Watch specific monitor
syft-notify run --jobs-only
syft-notify run --peers-only
```

## Security Considerations

1. **Token security**: OAuth tokens stored with 0600 permissions
2. **PID file**: Only owner can read/write
3. **Logs**: Contains email addresses but no sensitive data
4. **Systemd hardening**: Service runs with restricted permissions

## Performance

- **Memory**: ~50-100 MB
- **CPU**: <1% (polls every 30s)
- **Disk**: ~80 MB (logs with rotation)
- **Network**: Minimal (only API calls during polls)

## Comparison: Foreground vs Background

| Feature           | `run` (foreground) | `start` (background) |
| ----------------- | ------------------ | -------------------- |
| Terminal required | ✅ Yes             | ❌ No                |
| Survives logout   | ❌ No              | ✅ Yes               |
| Shows output      | ✅ Terminal        | 📝 Log file          |
| Stop method       | Ctrl+C             | `syft-notify stop`   |
| Use case          | Development        | Production           |

## Support

- **Issues**: https://github.com/OpenMined/syft-client/issues
- **Docs**: https://docs.openmined.org
- **Community**: https://slack.openmined.org
