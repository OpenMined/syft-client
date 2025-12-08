# SyftBox Notification System

Email notifications for SyftBox job and peer events between Data Owners (DO) and Data Scientists (DS).

## Three Usage Patterns

### 1. Notebook Integration (Embedded)

Run notifications directly in Jupyter notebooks alongside your DO/DS code.

**Use when:**

- Developing/testing in notebooks
- Want immediate feedback
- Running short-lived sessions

**Example:**

```python
import syft_client as sc
from syft_client.notifications import NotificationMonitor

# Login as DO
client_do = sc.login_do(email="do@example.com", token_path="token.json")

# Start notification monitor
monitor = NotificationMonitor.from_client(client_do)
monitor.start()  # Runs in background threads

# ... do your work ...

# Stop when done
monitor.stop()
```

**Features:**

- ✅ Integrated with syft-client
- ✅ Runs in background threads
- ✅ Easy setup
- ❌ Stops when notebook stops
- ❌ Requires keeping notebook running

See: `notebooks/e2e/notifications_e2e.ipynb`

---

### 2. CLI Foreground Mode (Terminal)

Run daemon in foreground attached to terminal (like `syft-notify run`).

**Use when:**

- Debugging issues
- Monitoring in real-time
- Testing configuration changes
- Short-term sessions

**Example:**

```bash
# First time setup
syft-notify init

# Run in terminal (see output live)
syft-notify run

# Custom options
syft-notify run --interval 60        # Every 60 seconds
syft-notify run --jobs-only          # Only monitor jobs
syft-notify run --once               # Single check, then exit
```

**Features:**

- ✅ Real-time output to terminal
- ✅ Easy to debug
- ✅ Ctrl+C to stop
- ❌ Stops when terminal closes
- ❌ Not suitable for production

See: `DAEMON_README.md#debugging`

---

### 3. Background Daemon (Production)

True background daemon that survives terminal closure using `python-daemon` library.

**Use when:**

- Production deployments on VMs
- Need 24/7 monitoring
- Remote servers (SSH sessions)
- Systemd integration

**Example:**

```bash
# Setup (one time)
syft-notify init

# Start background daemon
syft-notify start

# Close terminal - daemon keeps running!

# Later: check status
syft-notify status
# ✅ Daemon is running (PID 12345)

# View logs
syft-notify logs
syft-notify logs --follow

# Stop when needed
syft-notify stop

# Restart
syft-notify restart
```

**Features:**

- ✅ Survives terminal closure (uses `python-daemon` library)
- ✅ Auto log rotation
- ✅ PID file management
- ✅ Systemd integration
- ✅ Production-ready

See: `DAEMON_README.md`

---

## Comparison

| Feature                     | Notebook         | CLI Foreground | Background Daemon  |
| --------------------------- | ---------------- | -------------- | ------------------ |
| **Survives terminal close** | ❌               | ❌             | ✅                 |
| **Shows real-time output**  | ❌               | ✅             | Log file           |
| **Easy debugging**          | ✅               | ✅             | ❌                 |
| **Production ready**        | ❌               | ❌             | ✅                 |
| **Setup complexity**        | Low              | Medium         | Medium             |
| **Use case**                | Development      | Testing        | Production         |
| **Stop method**             | `monitor.stop()` | Ctrl+C         | `syft-notify stop` |
| **Implementation**          | Threads          | Main process   | `python-daemon`    |

---

## Quick Start by Role

### For Data Scientists (Testing)

```bash
# Notebook only - no daemon needed
jupyter notebook notebooks/e2e/notifications_e2e.ipynb
```

### For Data Owners (Development)

```bash
# Setup
syft-notify init

# Run in terminal while testing
syft-notify run
```

### For DevOps (Production VMs)

```bash
# Setup
syft-notify init

# Start background daemon
syft-notify start

# Or install systemd service
sudo cp systemd/syft-notify.service /etc/systemd/system/syft-notify@.service
sudo systemctl enable syft-notify@USERNAME
sudo systemctl start syft-notify@USERNAME
```

---

## Notification Types

### Jobs

| Event             | Recipient | Method           |
| ----------------- | --------- | ---------------- |
| New job submitted | DO        | Drive polling    |
| Job approved      | DS        | Local filesystem |
| Job executed      | DS        | Local filesystem |

### Peers

| Event                     | Recipient | Method        |
| ------------------------- | --------- | ------------- |
| Peer request              | DO        | Drive polling |
| Request sent confirmation | DS        | Drive polling |
| Peer granted              | DS        | Manual call\* |

\*Peer grants require manual call: `monitor.notify_peer_granted(ds_email)`

---

## Architecture

All three patterns use the same core components:

```
┌─────────────────────────────────────────────────────────────────┐
│  Google Drive (Data Layer)                                      │
│  ├─ syft_outbox_inbox_DS_to_DO/  (job messages)                │
│  └─ SyftBox_DO/app_data/job/     (local jobs)                  │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │ Poll / Check
                            │
┌─────────────────────────────────────────────────────────────────┐
│  Notification Monitors                                          │
│  ├─ JobMonitor    → Polls Drive + checks local filesystem      │
│  └─ PeerMonitor   → Polls Drive for inbox folders              │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼ Send email
┌─────────────────────────────────────────────────────────────────┐
│  GmailSender → HTML Templates → Gmail API                       │
└─────────────────────────────────────────────────────────────────┘
```

**What differs between patterns:**

- **Notebook**: Runs monitors in threads, stops with notebook
- **CLI Foreground**: Runs monitors in main loop, stops with Ctrl+C
- **Background Daemon**: Uses `python-daemon` library to detach from terminal

---

## Configuration

All patterns use the same config format:

```yaml
# ~/.syft-creds/daemon.yaml
do_email: test1@openmined.org
syftbox_root: /home/user/SyftBox_test1@openmined.org
drive_token_path: /home/user/.syft-creds/token_do.json
gmail_token_path: /home/user/.syft-creds/gmail_token.json
interval: 30 # Check every 30 seconds
```

**Setup:**

```bash
# Interactive setup (all patterns)
syft-notify init

# Or manual setup for notebooks
from syft_client.notifications import NotificationMonitor
NotificationMonitor.setup()  # One-time Gmail OAuth
```

---

## Files Created

```
~/.syft-creds/
├── daemon.yaml                 # Config (all patterns)
├── gmail_token.json            # Gmail OAuth token
├── token_do.json               # Google Drive OAuth token
├── notification_state.json     # Tracks sent notifications
│
# Daemon mode only:
├── syft-notify.pid             # Process ID
├── syft-notify.log             # Main log (rotates at 10MB)
├── syft-notify.log.1-7         # Rotated logs
└── syft-notify.error.log       # Error log
```

---

## Common Tasks

### Send peer grant notification (all patterns)

```python
# In notebook
monitor.notify_peer_granted(ds_email)
```

### Check notification state

```bash
cat ~/.syft-creds/notification_state.json
```

### Reset notifications (re-send)

```bash
# Clear peer notifications
python << EOF
import json
from pathlib import Path

state_path = Path.home() / ".syft-creds" / "notification_state.json"
state = json.load(open(state_path))

if "peer_snapshot" in state:
    del state["peer_snapshot"]

jobs = state.get("notified_jobs", {})
for key in [k for k in jobs if k.startswith("peer_")]:
    del jobs[key]

json.dump(state, open(state_path, "w"), indent=2)
EOF

# Restart monitor/daemon to pick up changes
```

### Change check interval

```bash
# Daemon mode
syft-notify start --interval 60

# Foreground mode
syft-notify run --interval 60

# Notebook mode
monitor = NotificationMonitor.from_client(client_do, interval=60)
```

---

## Documentation

- **This file**: Overview of all patterns
- `DAEMON_README.md`: Deep dive into background daemon mode
- `LOGGING_INTEGRATION.md`: Centralized logging setup
- `systemd/README.md`: Systemd service installation
- `notebooks/e2e/notifications_e2e.ipynb`: Notebook pattern demo
- `notebooks/e2e/notifications_cli_e2e.ipynb`: Daemon pattern demo

---

## Choosing Your Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│  START HERE                                                     │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │ Where are you running?  │
              └─────────────────────────┘
                     /              \
                    /                \
             Jupyter                VM/Server
            Notebook                    │
                │                       ▼
                │            ┌──────────────────────┐
                │            │ Need 24/7 uptime?    │
                │            └──────────────────────┘
                │                  /           \
                │                 /             \
                │               Yes             No
                │                │               │
                ▼                ▼               ▼
    ┌──────────────────┐  ┌──────────┐  ┌────────────┐
    │ Notebook Pattern │  │ Daemon   │  │ Foreground │
    │                  │  │ Mode     │  │ Mode       │
    │ from_client()    │  │ start    │  │ run        │
    └──────────────────┘  └──────────┘  └────────────┘
```

---

## Support

- **Issues**: https://github.com/OpenMined/syft-client/issues
- **Docs**: https://docs.openmined.org
- **Community**: https://slack.openmined.org

---

## Security

- OAuth tokens stored with 0600 permissions
- No secrets in logs
- PID files protected
- Systemd service runs with security hardening
- Logs contain only emails and job names (no sensitive data)
