# Google Personal OAuth2 Authentication Flow

## Overview

The Google Personal platform now has a complete OAuth2 authentication flow with an interactive wizard for credentials setup.

## Authentication Flow Steps

### 1. **Check for Cached Token**
- Location: `~/.syft/google_oauth/[email]/token_*.json`
- If valid token exists and not expired → **Success**
- If token expired → Refresh token automatically

### 2. **Check for credentials.json**
Searches in order:
1. `~/.syft/credentials.json` (recommended)
2. `~/.syft/google_oauth/credentials.json`
3. `./credentials.json` (current directory)

If found → Proceed to OAuth2 browser flow

### 3. **Launch Interactive Wizard**
If no credentials.json found:
- Detects if in interactive environment (terminal, Jupyter, IPython)
- Prompts user to run setup wizard
- Guides through Google Cloud Console setup:
  - Project creation
  - API enablement (Gmail, Drive, Sheets, Forms)
  - OAuth consent screen configuration
  - Credentials creation and download

### 4. **OAuth2 Browser Flow**
- Opens browser for Google sign-in
- User grants permissions for requested scopes
- Receives authorization code
- Exchanges for access/refresh tokens

### 5. **Save and Use Token**
- Saves token with timestamp: `token_YYYYMMDD_HHMMSS.json`
- Keeps only 5 most recent tokens
- Future logins use cached token

## Usage Examples

### Basic Login
```python
from syft_client import login

# First time - will guide through setup if needed
client = login("your@gmail.com")
```

### Manual Wizard
```python
from syft_client.platforms.google_personal.wizard import create_oauth2_wizard

# Run wizard manually
create_oauth2_wizard("your@gmail.com")
```

### Client Wizard Method
```python
from syft_client.platforms.google_personal.client import GooglePersonalClient

client = GooglePersonalClient("your@gmail.com")
client.wizard()  # Launch wizard
```

## Special Cases

### Google Colab
- Detects Colab environment automatically
- Shows message that credentials.json not needed
- Uses Colab's built-in authentication

### Non-Interactive Mode
- If not in interactive environment, shows error
- Provides instructions to run wizard manually
- Returns None instead of raising exception

### Multi-Account Support
- Adds `?authuser=email` to Google Console URLs
- Helps users stay in correct account during setup

## File Structure

```
~/.syft/
├── credentials.json                    # OAuth2 app credentials
└── google_oauth/
    └── your_at_gmail_com/             # Per-email token storage
        ├── token_20240101_120000.json # Most recent token
        ├── token_20240101_100000.json # Previous tokens...
        └── ...
```

## Security Notes

- Tokens stored with 0600 permissions (owner read/write only)
- Credentials.json should never be committed to version control
- Each email has separate token storage
- Tokens auto-refresh when expired

## Wizard Features

- **Interactive prompts** with clear instructions
- **URL auto-opening** option (user consent required)
- **Step-by-step guidance** through Google Cloud Console
- **Email-specific URLs** for multi-account users
- **Progress tracking** with Enter prompts between steps
- **Command examples** for moving credentials file

## Error Handling

- Clear error messages at each step
- Graceful cancellation (Ctrl+C supported)
- Fallback instructions if wizard fails
- Detailed verbose mode for debugging