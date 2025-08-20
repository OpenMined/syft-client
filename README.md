# Syft Client

A transport-agnostic client library for decentralized file syncing, currently supporting Google Drive as the transport layer.

## Features

- **Multiple Account Support**: Manage multiple Google Drive accounts simultaneously
- **Credential Wallet**: Securely store and manage credentials for different accounts
- **Unidirectional Channels**: Each user controls their outgoing communication infrastructure
- **Simple Setup**: Easy-to-use API for setting up secure communication channels

## Installation

```bash
pip install -e .
```

## Quick Start

### Simplest Usage - Just Login!

```python
from syft_client import login

# Login with your email - it handles everything automatically
client = login("your_email@gmail.com")

# Set up SyftBoxTransportService
client.setup_syftbox()

# Set up communication with another user
client.setup_communication_channel("their_email@gmail.com")
```

### Login with Direct Credentials Path

```python
from syft_client import login

# Skip the wizard by providing credentials directly
client = login("your_email@gmail.com", credentials_path="~/Downloads/credentials.json")

# The credentials will be automatically added to your wallet for future use
```

### Silent Login (No Output)

```python
from syft_client import login

# Login without any printed output
client = login("your_email@gmail.com", verbose=False)

# Note: This will raise an error if credentials aren't already in wallet
```

The `login()` function automatically:
1. Uses provided credentials_path if specified (skips all other steps)
2. Checks if you're in Google Colab and the email matches
3. Looks for stored credentials in the wallet
4. Checks for credentials.json in current directory
5. Guides you through setup if no credentials found

### Multiple Account Usage

```python
from syft_client import login, list_accounts

# See available accounts
print("Available accounts:", list_accounts())

# Login as different users
client1 = login("user1@gmail.com")
client2 = login("user2@gmail.com")

# Use both clients independently
client1.setup_syftbox()
client2.setup_syftbox()
```

### Managing Credentials

```python
from syft_client import CredentialWallet, logout

# Create wallet instance
wallet = CredentialWallet()

# Add credentials for new accounts
wallet.add_credentials("user@gmail.com", "path/to/credentials.json")

# List all accounts
accounts = wallet.list_accounts()

# Logout (clear tokens)
logout("user@gmail.com")

# Remove account completely
logout("user@gmail.com", clear_tokens_only=False)
```

## Credential Wallet

The credential wallet stores Google Drive credentials in `~/.syft/gdrive/` allowing you to:

- Store credentials for multiple accounts
- Switch between accounts easily
- Authenticate as multiple users simultaneously
- Maintain separate authentication tokens for each account

### Wallet Commands

```python
# List all stored accounts
accounts = wallet.list_accounts()

# Add new credentials
wallet.add_credentials("email@gmail.com", "path/to/credentials.json")

# Import credentials.json from current directory
wallet.import_current_credentials("email@gmail.com")

# Remove specific account
wallet.remove_account("email@gmail.com")

# Reset entire wallet (remove all accounts)
wallet.reset_wallet()
```

## Folder Structure

When you set up communication between two users, the following folder structure is created:

```
SyftBoxTransportService/
├── syft_sender@gmail.com_to_receiver@gmail.com_pending/      # Sender's drafts (private)
├── syft_sender@gmail.com_to_receiver@gmail.com_outbox_inbox/ # Active messages (shared)
└── syft_receiver@gmail.com_to_sender@gmail.com_archive/      # Processed messages (shared)
```

## Communication Setup

### Quick Setup - Add a Friend

The easiest way to set up bidirectional communication:

```python
# Add a friend (sets up everything)
client.add_friend("friend@gmail.com")

# Your friend does the same
# They run: client.add_friend("your_email@gmail.com")
```

This single command:
- Creates your outgoing channel to them
- Sets up your archive for their messages
- Creates shortcuts for any folders they've shared
- Shows clear instructions for your friend

### Manual Setup

For more control, you can set up channels manually:

```python
# Set up outgoing channel
client.setup_communication_channel("friend@gmail.com")

# Set up incoming archive
client.setup_incoming_archive("friend@gmail.com")
```

## Communication Protocol

1. **Sender** creates:
   - `pending` folder (private) for drafts
   - `outbox_inbox` folder (shared) for active messages

2. **Receiver** creates:
   - `archive` folder (shared) for processed messages

3. Message flow:
   - Sender uploads to `pending` for review
   - Sender moves to `outbox_inbox` when ready
   - Receiver processes from `outbox_inbox`
   - Receiver moves to `archive` when done

## Examples

See the `examples/` directory for more detailed examples:
- `multi_account_example.py` - Working with multiple accounts
- `setup_syftbox.ipynb` - Interactive setup notebook
- `wallet_demo.ipynb` - Credential wallet demonstration
- `fix_credentials.ipynb` - Fix credential file issues
- `login_demo.ipynb` - Simple login demonstration

## Troubleshooting

### Multiple Credential Files

If you download new credentials but login still uses the old account:

```python
from syft_client import organize_credentials

# This will find and organize credential files for the target email
organize_credentials("your_email@gmail.com")

# Now login should work
client = login("your_email@gmail.com")
```

Common scenarios:
- Browser saves new credentials as `credentials (1).json`
- Multiple credential files in the same directory
- Wrong credentials.json is being used

See `fix_credentials.ipynb` for more solutions.

## Security Notes

- Credentials are stored locally in `~/.syft/gdrive/`
- Each account has its own directory with separate tokens
- Never share your credentials.json files
- Use appropriate file permissions on the ~/.syft directory