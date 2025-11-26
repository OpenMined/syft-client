# SyftBox Job Notifications

Email notifications for SyftBox job events using Gmail.

## ✨ Features

- 📧 **Gmail integration** - Send emails via Gmail API (not SMTP)
- 🔐 **OAuth2 authentication** - Secure browser-based authentication
- 🚫 **Duplicate prevention** - State tracking prevents repeat notifications
- 🔄 **Real-time monitoring** - Continuous or scheduled checking
- 🎯 **Three notification types**:
  - New job arrives → Email to Data Owner
  - Job approved → Email to Data Scientist
  - Job executed → Email to Data Scientist
- 🧩 **Extensible architecture** - Easy to add Slack, Discord, SMS, etc.

---

## 🚀 Quick Start

### 1. Setup (3 steps, ~5 minutes)

**Step 1: Get Google credentials.json**

```bash
# Visit: https://console.cloud.google.com/apis/credentials
# 1. Create project → Enable Gmail API
# 2. Create OAuth 2.0 Client ID (Desktop app)
# 3. Download as credentials.json
```

**Step 2: Configure**

```bash
# Copy example config
cp notification_config.yaml my_notifications.yaml

# Edit with your details
nano my_notifications.yaml
# Change: do_email, syftbox_root, credentials_file path
```

**Step 3: Authenticate (one-time)**

```python
from syft_client.notifications import setup_oauth

setup_oauth("my_notifications.yaml")
# Browser opens → Sign in → Grant Gmail permissions
# Token saved to ~/.syftbox/notifications/gmail_token.json
```

### 2. Start Monitoring

```python
from syft_client.notifications import start_monitoring

# Create monitor
monitor = start_monitoring("my_notifications.yaml")

# Option 1: Check once
monitor.check()

# Option 2: Check every 10 seconds (runs forever)
monitor.check(interval=10)

# Option 3: Run for 1 hour, checking every 10s
monitor.check(interval=10, duration=3600)
```

**That's it!** 🎉 You'll now receive emails for job events.

---

## 📋 Configuration Reference

```yaml
# notification_config.yaml

# Path to SyftBox root directory
syftbox_root: '~/SyftBox'

# Your email address (Data Owner)
do_email: 'owner@example.com'

# Google OAuth credentials (download from Google Cloud Console)
credentials_file: 'credentials.json'

# Where to save the OAuth token (auto-generated)
token_file: '~/.syftbox/notifications/gmail_token.json'

# State file (tracks sent notifications)
state_file: '~/.syftbox/notifications/state.json'

# Toggle notifications on/off
notify_on_new_job: true # Email DO when job arrives
notify_on_approved: true # Email DS when job approved
notify_on_executed: true # Email DS when job completes
```

---

## 📚 API Documentation

### High-Level API (Recommended)

#### `setup_oauth(config_path)`

One-time OAuth setup. Opens browser for Gmail authentication.

```python
from syft_client.notifications import setup_oauth

setup_oauth("notification_config.yaml")
```

**Raises:**

- `FileNotFoundError` - Config or credentials file not found
- `ValueError` - Config missing required keys

---

#### `start_monitoring(config_path)`

Creates configured JobMonitor ready to use.

```python
from syft_client.notifications import start_monitoring

monitor = start_monitoring("notification_config.yaml")
```

**Returns:** `JobMonitor` instance

**Raises:**

- `FileNotFoundError` - Config or token file not found
- `ValueError` - Config missing required keys

---

### Low-Level API (Advanced)

For full control over components:

```python
from syft_client.notifications import (
    GmailAuth, GmailSender, JsonStateManager, JobMonitor
)

# Manual authentication
auth = GmailAuth()
credentials = auth.load_credentials("token.json")

# Create sender
sender = GmailSender(credentials)

# Create state tracker
state = JsonStateManager("state.json")

# Create monitor
monitor = JobMonitor(
    syftbox_root="~/SyftBox",
    do_email="owner@example.com",
    sender=sender,
    state=state,
    config={
        "notify_on_new_job": True,
        "notify_on_approved": True,
        "notify_on_executed": True,
    }
)

# Run monitoring
monitor.check(interval=10)
```

---

## 🎨 Notification Examples

### New Job Notification (to Data Owner)

```
Subject: New Job: analyze_diabetes_data

Body:
You have a new job request in SyftBox!

Job: analyze_diabetes_data
From: scientist@university.edu

Log in to SyftBox to review and approve this job.
```

### Job Approved (to Data Scientist)

```
Subject: Job Approved: analyze_diabetes_data

Body:
Your job has been approved!

Job: analyze_diabetes_data

The data owner has reviewed and approved your job request.
Your job will be executed soon.
```

### Job Executed (to Data Scientist)

```
Subject: Job Completed: analyze_diabetes_data

Body:
Your job has finished execution!

Job: analyze_diabetes_data

Your job has completed successfully. Results are available.
```

---

## 🔧 Troubleshooting

### OAuth browser doesn't open

**Symptoms:** `setup_oauth()` hangs, no browser window

**Solutions:**

1. Check you're not in SSH/headless environment
2. Try: `BROWSER=firefox python script.py` (or chrome/safari)
3. Use port forwarding: `ssh -L 8080:localhost:8080 user@server`

---

### Emails not arriving

**Symptoms:** No errors, but emails don't appear

**Solutions:**

1. ✅ Check spam/junk folder
2. ✅ Verify token exists: `ls ~/.syftbox/notifications/gmail_token.json`
3. ✅ Check state file: `cat ~/.syftbox/notifications/state.json`
   - If job already marked as notified, delete state file to resend
4. ✅ Test Gmail API directly:

   ```python
   from syft_client.notifications import GmailSender, GmailAuth

   auth = GmailAuth()
   creds = auth.load_credentials("~/.syftbox/notifications/gmail_token.json")
   sender = GmailSender(creds)

   success = sender.send_email("test@example.com", "Test", "Testing!")
   print(f"Sent: {success}")
   ```

---

### OAuth token expired

**Symptoms:** `Token has been expired or revoked`

**Solution:**

```bash
# Delete old token
rm ~/.syftbox/notifications/gmail_token.json

# Re-authenticate
python -c "from syft_client.notifications import setup_oauth; setup_oauth('notification_config.yaml')"
```

---

### Import errors

**Symptoms:** `ModuleNotFoundError: No module named 'yaml'`

**Solution:**

```bash
pip install pyyaml>=6.0
# Or reinstall syft-client
pip install -e .
```

---

### Test user not authorized (OAuth consent screen)

**Symptoms:** `Error 403: access_denied`

**Solution:**

1. Go to Google Cloud Console → OAuth consent screen
2. Add test user email under "Test users"
3. Or publish app (for production use)

---

### Job directory not found

**Symptoms:** Monitor runs but never sends emails

**Solution:**

1. Verify `syftbox_root` in config points to correct directory
2. Check jobs directory exists: `ls ~/SyftBox/<do_email>/app_data/job/`
3. Verify DO email matches: `do_email` in config = folder name in SyftBox

---

## 🏗️ Architecture

### Abstract Base Classes

The system uses ABC pattern for extensibility:

```python
# Base classes in base.py
Monitor(ABC)           # Base for all monitors
NotificationSender(ABC)  # Base for all senders
StateManager(ABC)      # Base for state tracking
AuthProvider(ABC)      # Base for authentication

# Implementations
JobMonitor(Monitor)              # Watches job directory
GmailSender(NotificationSender)  # Sends via Gmail
JsonStateManager(StateManager)   # JSON file state
GmailAuth(AuthProvider)          # OAuth2 flow
```

### Extension Examples

**Add Slack notifications:**

```python
from syft_client.notifications.base import NotificationSender

class SlackSender(NotificationSender):
    def send_notification(self, to, subject, body):
        # Slack API implementation
        pass
```

**Add peer monitoring:**

```python
from syft_client.notifications.base import Monitor

class PeerMonitor(Monitor):
    def _check_all_entities(self):
        # Check for new peers joining/leaving
        pass
```

**Add SQLite state:**

```python
from syft_client.notifications.base import StateManager

class SqliteStateManager(StateManager):
    def was_notified(self, entity_id, event_type):
        # SQLite query
        pass
```

---

## 📦 Dependencies

Required (auto-installed with syft-client):

- `google-api-python-client>=2.95.0` - Gmail API
- `google-auth>=2.22.0` - Authentication
- `google-auth-oauthlib>=1.0.0` - OAuth2 flow
- `pyyaml>=6.0` - Config parsing

---

## 🧪 Testing

### Unit Tests

```bash
# Run all tests (12 tests)
python3 tests/unit/test_notifications.py

# Run specific phase
python3 tests/unit/test_notifications.py --phase=1  # OAuth
python3 tests/unit/test_notifications.py --phase=2  # Sender
python3 tests/unit/test_notifications.py --phase=3  # State
```

### Manual Testing

```python
# Test 1: OAuth flow
from syft_client.notifications import setup_oauth
setup_oauth("notification_config.yaml")

# Test 2: Send test email
from syft_client.notifications import GmailAuth, GmailSender

auth = GmailAuth()
creds = auth.load_credentials("~/.syftbox/notifications/gmail_token.json")
sender = GmailSender(creds)

success = sender.send_email("your-email@example.com", "Test", "Hello from SyftBox!")
print(f"Email sent: {success}")

# Test 3: Full monitoring (dry run)
from syft_client.notifications import start_monitoring

monitor = start_monitoring("notification_config.yaml")
monitor.check()  # Single check
print("Monitoring check complete!")
```

---

## 🔮 Roadmap

### Planned Features

- [ ] **Jinja2 email templates** - HTML emails with styling
- [ ] **Logging support** - Debug and error logging
- [ ] **Retry logic** - Exponential backoff for failed sends
- [ ] **Batch notifications** - Daily digest emails
- [ ] **CLI interface** - `syft-notifications run --config config.yaml`
- [ ] **Other channels** - Slack, Discord, SMS, Webhook
- [ ] **Email customization** - User-defined templates

### Future Monitors

- [ ] `PeerMonitor` - Notify when peers join/leave
- [ ] `DatasetMonitor` - Notify on dataset updates
- [ ] `ErrorMonitor` - Alert on system errors

---

## 📄 License

Part of syft-client. Licensed under Apache-2.0.

---

## 🤝 Contributing

Found a bug? Have a feature request?

- File issue: https://github.com/OpenMined/syft-client/issues
- Pull requests welcome!

---

## 📞 Support

**Questions?**

- Check troubleshooting section above
- Review example: `test_notification_system.ipynb`
- See config: `notification_config.yaml`

**Need help?**

- GitHub Issues: https://github.com/OpenMined/syft-client/issues
- Community: https://openmined.slack.com

---

**Version:** 0.1.0
**Last Updated:** 2025-11-24
