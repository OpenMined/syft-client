# OAuth2 Platform Architecture

This directory contains comprehensive documentation for the OAuth2-based authentication and transport system in syft-client.

## Documentation Overview

### 📋 [DESIGN.md](./DESIGN.md)
Core OAuth2 authentication flow and standardized method names across platforms.

**Key Topics:**
- Authentication flow phases
- Standard method naming conventions
- Configuration file structure
- First-time vs returning user flows

### 🔐 [WALLETS.md](./WALLETS.md)
Flexible token storage system supporting multiple security backends.

**Key Topics:**
- Wallet interface specification
- Built-in wallet implementations (Local, 1Password, Keychain, AWS, Bitwarden)
- Token storage formats
- Migration between wallets

### 🎨 [WIZARD_CUSTOMIZATION.md](./WIZARD_CUSTOMIZATION.md)
Environment-specific UI customization for setup wizards.

**Key Topics:**
- Step definition format
- Terminal, Jupyter, and Colab renderers
- Complete OAuth2 setup wizard example
- Custom validation and actions

### 🚀 [TRANSPORT_SETUP.md](./TRANSPORT_SETUP.md)
Transport layer configuration and management.

**Key Topics:**
- Transport discovery and registration
- First-time setup flow
- Adding transports later
- Bundle options and testing

## Quick Start

### Basic OAuth2 Login

```python
from syft_client import login

# First time - will launch setup wizard if needed
client = login("your@gmail.com")

# Subsequent logins use cached token
client = login("your@gmail.com")
```

### Platform-Specific Implementation

```python
from syft_client.platforms.google_personal.client import GooglePersonalClient

# Create client
client = GooglePersonalClient("your@gmail.com", verbose=True)

# Authenticate (includes wizard if needed)
client.authenticate()

# Access transports
gmail = client.transports['gmail']
drive = client.transports['gdrive_files']
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Application                      │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│                   Platform Client                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Authentication Flow                 │   │
│  │  1. Check wallet for cached token              │   │
│  │  2. Find OAuth2 credentials                    │   │
│  │  3. Run setup wizard if needed                 │   │
│  │  4. Execute OAuth2 browser flow                │   │
│  │  5. Store token in wallet                      │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────┬───────────────────────────────────────┘
                  │
        ┌─────────┴─────────┬──────────┬──────────┐
        │                   │          │          │
┌───────▼────────┐ ┌────────▼───────┐ ┌▼─────────┐ ┌─────────┐
│     Gmail      │ │  Google Drive  │ │  Sheets  │ │  Forms  │
│   Transport    │ │   Transport    │ │Transport │ │Transport│
└────────────────┘ └────────────────┘ └──────────┘ └─────────┘
```

## Key Design Decisions

### 1. **OAuth2-First Authentication**
- Removed app password support for better security
- Integrated OAuth2 flow directly into platform client
- Single authentication for all Google services

### 2. **Wallet Abstraction**
- Flexible token storage (local files, 1Password, Keychain, etc.)
- User choice for security vs convenience
- Easy migration between storage methods

### 3. **Progressive Transport Setup**
- Users can start with just email
- Add more transports as needed
- No forced setup of unused features

### 4. **Environment-Aware Wizards**
- Different UIs for terminal vs Jupyter
- Step definitions separate from rendering
- Customizable for each platform's needs

### 5. **Email Categorization**
- Automatic separation of backend vs notification emails
- Gmail labels and SMTP folders
- Consistent prefixes across platforms

## Common Workflows

### Setting Up a New Platform

```python
# 1. Run login - wizard guides through setup
client = login("user@gmail.com")

# 2. Choose wallet preference (first time only)
# Terminal: Interactive prompt
# Jupyter: Widget selection

# 3. Select transports to set up
# Options: Basic (email), Standard (+files), Full (everything)

# 4. OAuth2 browser flow
# Automatic token storage and refresh
```

### Adding Transport Later

```python
# Option 1: Direct setup
client.platforms['google_personal'].setup_transport('gsheets')

# Option 2: Interactive
client.platforms['google_personal'].configure_transports()

# Option 3: Auto-prompt on first use
sheets = client.platforms['google_personal'].transports['gsheets']
sheets.send(...)  # Prompts for setup if not configured
```

### Switching Wallets

```python
from syft_client.auth.wallets import get_wallet, migrate_tokens

# Get current wallet
old_wallet = get_wallet("user@gmail.com")

# Configure new wallet
new_wallet = configure_wallet_preference("user@gmail.com")

# Migrate tokens
results = migrate_tokens(old_wallet, new_wallet)
print(f"Migrated {len(results['migrated'])} tokens")
```

## Security Best Practices

1. **Never commit credentials.json** - Add to .gitignore
2. **Use secure wallets** for production (1Password, AWS Secrets)
3. **Rotate tokens periodically** - OAuth2 handles this automatically
4. **Limit scopes** to only what's needed
5. **Encrypt local storage** - Default for LocalFileWallet

## Troubleshooting

### Common Issues

**"No credentials.json found"**
- Run the wizard: `client.wizard()`
- Or manually place credentials.json in ~/.syft/

**"Token expired"** 
- Should auto-refresh, but can force: `client.authenticate(force_relogin=True)`

**"Transport not configured"**
- Set up individually: `client.setup_transport('transport_name')`
- Or run full configuration: `client.configure_transports()`

**"Wallet not accessible"**
- Check wallet service is running (1Password, etc.)
- Falls back to local storage automatically

### Debug Mode

```python
# Enable verbose logging
client = GooglePersonalClient("user@gmail.com", verbose=True)

# Check token status
token_info = client.get_token_info()
print(f"Token valid: {token_info['valid']}")
print(f"Expires: {token_info['expiry']}")

# Test specific transport
gmail = client.transports['gmail']
test_results = gmail.test_connection()
print(f"Gmail test: {test_results}")
```

## Future Enhancements

### Planned Features

1. **Multi-account token management** - Switch between accounts easily
2. **Token sharing across devices** - Via secure wallet sync
3. **Automatic transport discovery** - Detect available APIs
4. **Custom OAuth2 providers** - Beyond Google
5. **Token usage analytics** - Track API calls and limits

### Extension Points

1. **Custom Wallets** - Implement BaseWallet interface
2. **New Transports** - Add any Google API service
3. **Platform Variants** - Google Workspace, other OAuth2 providers
4. **UI Frameworks** - Custom wizard renderers

## Contributing

When adding new features:

1. Follow the established patterns in DESIGN.md
2. Support all wallet types for token storage  
3. Provide both terminal and Jupyter wizard steps
4. Include transport setup/teardown methods
5. Add comprehensive error handling
6. Update relevant documentation

## Related Documentation

- [Google OAuth2 Flow](../GOOGLE_OAUTH2_FLOW.md) - Original implementation details
- Platform-specific docs in each platform directory
- API reference in the code docstrings