This is a complete, self-contained authentication system for setting up
Google Workspace APIs (Gmail, Drive, Sheets, Forms) in Colab and Jupyter notebooks.

Features:

- One-line authentication: authenticate(email="user@example.com")
- Automatic environment detection (Colab vs Jupyter)
- Persistent credential storage (Google Drive for Colab, local for Jupyter)
- Interactive setup wizard with step-by-step guidance
- Automatic API enabling and testing
- Complete OAuth 2.0 flow with manual redirect handling

Usage:

```
from syft_client.notebook_auth import authenticate

# One-liner that does everything!
credentials = authenticate(email="user@example.com")

# Use with Google API clients
from googleapiclient.discovery import build
gmail = build('gmail', 'v1', credentials=credentials)
drive = build('drive', 'v3', credentials=credentials)
sheets = build('sheets', 'v4', credentials=credentials)
forms = build('forms', 'v1', credentials=credentials)
```

What it does:

1. Mounts Google Drive (Colab only) for credential persistence
2. Checks for cached credentials and reuses them if valid
3. If no cache, guides through complete setup:
   - GCP project creation or selection
   - OAuth consent screen configuration
   - OAuth client ID creation
   - OAuth authentication flow
   - Enables all 4 Workspace APIs (Gmail, Drive, Sheets, Forms)
   - Tests all APIs to confirm they work
4. Saves credentials for future use
5. Returns ready-to-use OAuth2 credentials

The entire flow is interactive with clear UI guidance at each step.
