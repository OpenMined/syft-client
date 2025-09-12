# Google OAuth2 Setup Guide

This guide explains how to set up OAuth2 authentication for the Google Personal platform in syft-client.

## Overview

The Google Personal platform now uses OAuth2 exclusively for authentication. This provides:
- Better security than app passwords
- Automatic token refresh
- Access to all Google APIs (Gmail, Drive, Sheets, Forms)
- Programmatic creation of Gmail filters and labels

## Setup Steps

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID

### 2. Enable Required APIs

In your Google Cloud project, enable these APIs:
1. Gmail API
2. Google Drive API
3. Google Sheets API
4. Google Forms API

You can enable them from the [API Library](https://console.cloud.google.com/apis/library).

### 3. Create OAuth2 Credentials

1. Go to [Credentials](https://console.cloud.google.com/apis/credentials)
2. Click "Create Credentials" → "OAuth client ID"
3. Choose "Desktop app" as the application type
4. Name it "Syft Client" (or any name you prefer)
5. Click "Create"
6. Download the credentials JSON file

### 4. Install Credentials

Place the downloaded `credentials.json` file in one of these locations:
- `~/.syft/credentials.json` (recommended)
- `~/.syft/google_oauth/credentials.json`
- Current working directory

### 5. First Login

```python
from syft_client import login

# This will open a browser for OAuth2 consent
client = login("your.email@gmail.com", verbose=True)
```

On first login:
1. A browser window will open
2. Sign in to your Google account
3. Grant permissions for Gmail, Drive, Sheets, and Forms
4. The token will be saved for future use

## Token Management

- Tokens are stored in `~/.syft/google_oauth/[your_email]/`
- Tokens are automatically refreshed when expired
- Only the 5 most recent tokens are kept
- Tokens are valid for 1 hour, refresh tokens last longer

## Email Categorization

The Gmail transport automatically:
1. Creates a "SyftBackend" label for backend emails
2. Sets up a filter to route `[SYFT-DATA]` emails to this label
3. Keeps notification emails `[SYFT]` in your inbox

## Environment Variables

- `SYFT_GOOGLE_USE_APP_PASSWORD=true` - Forces app password auth (only for SMTP platform now)

## Troubleshooting

### "OAuth2 credentials.json not found"
- Make sure you downloaded the credentials from Google Cloud Console
- Place it in `~/.syft/credentials.json`

### "Access blocked: This app's request is invalid"
- Make sure you're using "Desktop app" type credentials
- Check that all required APIs are enabled

### Browser doesn't open
- Make sure you're in an environment that supports browser launch
- You may need to manually copy the authorization URL

## Security Notes

- Never commit `credentials.json` to version control
- Tokens are stored with 600 permissions (owner read/write only)
- Each email account has its own token storage