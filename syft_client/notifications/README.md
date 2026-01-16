# Syft Notifications

Email notifications for Syft jobs and peer events.

## Prerequisites

Get Google OAuth credentials:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select existing)
3. Enable **Gmail API** and **Google Drive API**
4. Go to **APIs & Services → Credentials**
5. Create **OAuth 2.0 Client ID** (Desktop app)
6. Download as `credentials.json`
7. Place in `~/.syft-creds/credentials.json`

## Install

```bash
uv pip install -e .
source .venv/bin/activate
```

## Setup

```bash
syft-notify init
```

This will:

- Prompt for your Data Owner email
- Run OAuth flow for Google Drive (opens browser)
- Run OAuth flow for Gmail (opens browser)
- Create `~/.syft-creds/daemon.yaml`

## Run as Background Daemon

```bash
syft-notify start
```

Other commands:

- `syft-notify stop` - Stop daemon
- `syft-notify status` - Check status
- `syft-notify logs -f` - Follow logs
- `syft-notify run` - Run in foreground (for debugging)
