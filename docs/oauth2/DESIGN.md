# OAuth2 Platform Design

## Overview

This document outlines the standardized OAuth2 authentication flow for syft-client platforms, including wallet integration and transport setup.

## Core Authentication Flow

### 1. Main Entry Point
```python
authenticate()  # Platform's main authentication method
```

### 2. Token Check Phase
```python
├── load_wallet_config()         # Check ~/.syft/[email]/config.json
├── get_or_create_wallet()       # Get configured wallet or default
├── check_cached_token()         # Look for existing valid token
│   ├── load_token_from_wallet() # Try preferred wallet
│   ├── refresh_token_if_needed() # Handle expiry
│   └── validate_token()         # Ensure it works
```

### 3. Credentials Discovery Phase
```python
├── find_oauth_credentials()     # Look for credentials.json
│   └── [If not found] → run_oauth_wizard()
│       ├── show_oauth_setup_steps()  # Platform-specific guide
│       ├── wait_for_credentials()    # User completes setup
│       └── verify_credentials()      # Validate file
```

### 4. OAuth2 Execution Phase
```python
├── execute_oauth_flow()         # Run OAuth2 flow
│   ├── create_oauth_client()    # Platform-specific
│   ├── get_authorization_url()  # Generate URL
│   ├── open_browser()           # User authorizes
│   └── exchange_code_for_token() # Get tokens
```

### 5. Storage & Setup Phase
```python
├── [First time] → configure_wallet_preference()
│   ├── show_wallet_options()    # Available wallets
│   ├── test_wallet_connection() # Verify it works
│   └── save_wallet_config()     # Store preference
│
├── store_token_in_wallet()      # Save token
│
└── [First time] → setup_transport_layers()
    ├── show_available_transports()
    ├── guide_transport_setup()   # Per-transport setup
    └── save_transport_config()   # Remember choices
```

## Standard Method Names

### Authentication Methods
- `authenticate()` - Main entry point
- `authenticate_oauth2()` - OAuth2-specific flow
- `check_cached_token()` - Look for existing token
- `find_oauth_credentials()` - Locate app credentials
- `execute_oauth_flow()` - Run OAuth2 process
- `refresh_token()` - Handle token refresh

### Wizard Methods
- `wizard()` - Public method to launch setup
- `run_oauth_wizard()` - Guide through credential creation
- `show_oauth_setup_steps()` - Display platform-specific steps

### Token Management
- `load_token()` - Load from storage
- `save_token()` - Save to storage
- `validate_token()` - Check if token works
- `serialize_token()` - Prepare for storage
- `deserialize_token()` - Load from storage

### Wallet Methods
- `load_wallet_config()` - Get saved preferences
- `get_or_create_wallet()` - Initialize wallet
- `configure_wallet_preference()` - First-time setup
- `detect_available_wallets()` - What's installed
- `store_token_in_wallet()` - Save using wallet
- `load_token_from_wallet()` - Retrieve from wallet

### Transport Methods
- `setup_transport_layers()` - Configure transports
- `check_transport_status()` - What's configured
- `show_available_transports()` - What can be added
- `setup_transport()` - Configure specific one
- `test_transport_connection()` - Verify it works

## Configuration Storage

### Wallet Configuration
```json
// ~/.syft/[email]/config.json
{
    "preferred_wallet": "1password",
    "wallet_config": {
        "vault": "Personal",
        "account": "my.1password.com"
    },
    "fallback_wallet": "local_file"
}
```

### Platform Preferences
```json
// ~/.syft/[email]/config.json (continued)
{
    "platform_preferences": {
        "google_personal": {
            "enabled_transports": ["gmail", "gdrive_files"],
            "transport_config": {
                "gmail": {
                    "backend_folder": "SyftBackend"
                }
            },
            "setup_completed": "2024-12-11T10:30:00Z"
        }
    }
}
```

### Transport Status
```json
{
    "transports": {
        "gmail": {
            "configured": true,
            "last_tested": "2024-12-11T10:30:00Z"
        },
        "gdrive_files": {
            "configured": true,
            "last_tested": "2024-12-11T10:31:00Z"
        },
        "gsheets": {
            "configured": false,
            "skip_reason": "user_deferred"
        }
    }
}
```

## First-Time User Flow

1. User runs `login("user@gmail.com")`
2. No wallet config found → use default LocalFileWallet
3. No cached token found
4. No credentials.json found → launch wizard
5. Wizard guides through OAuth2 app creation
6. Run OAuth2 browser flow
7. Ask user for wallet preference
8. Store token in chosen wallet
9. Ask which transports to set up
10. Configure selected transports
11. Save all preferences
12. Return authenticated client

## Returning User Flow

1. User runs `login("user@gmail.com")`
2. Load wallet config → "Using 1Password"
3. Load token from 1Password
4. Token valid → Done!
5. Token expired → Refresh → Done!

## Adding Transports Later

### Option 1: Direct Setup
```python
client.platforms['google_personal'].setup_transport('gsheets')
```

### Option 2: Interactive Setup
```python
client.platforms['google_personal'].configure_transports()
# Shows available transports and guides setup
```

### Option 3: Auto-prompt on Use
```python
# Using unconfigured transport prompts setup
sheets = client.platforms['google_personal'].transports['gsheets']
sheets.send(...)  # → "Sheets not configured. Set up now?"
```

## Standard Properties

Each OAuth2 platform should define:
- `oauth2_scopes` - Required permissions
- `credential_filename` - Expected file (e.g., "credentials.json")
- `oauth2_endpoints` - Auth/token URLs
- `token_directory` - Where to store tokens