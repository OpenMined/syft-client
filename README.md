# Syft Client

A simple client library for setting up secure communication channels using Google Drive.

## Installation

```bash
pip install -e .
```

## Quick Start

```python
import syft_client as sc

# Login with your email
client = sc.login("your_email@gmail.com", "credentials.json", verbose=False)

# Reset/create your SyftBoxTransportService folder
client.reset_syftbox()

# Add a friend
client.add_friend("friend@gmail.com")

# Check your friends
client.friends  # Returns: ['friend@gmail.com']

# Check friend requests (people who shared with you)
client.friend_requests  # Returns: ['other@gmail.com']
```

## Core Features

### Login
The `login()` function handles authentication:
```python
# With credentials file
client = sc.login("your_email@gmail.com", "credentials.json")

# Without verbose output
client = sc.login("your_email@gmail.com", verbose=False)
```

### Friend Management
```python
# Add a friend (creates folders and permissions)
client.add_friend("friend@gmail.com")

# List your friends
client.friends  # ['friend@gmail.com']

# See who wants to connect with you
client.friend_requests  # ['person@gmail.com']
```

### Reset SyftBox
```python
# Delete and recreate your SyftBoxTransportService folder
client.reset_syftbox()
```

## How It Works

When you add a friend, the system creates:
1. **Your outgoing channel** - Folders you control for sending
2. **Your archive** - Where you store processed messages from them
3. **Shortcuts** - Links to any folders they've shared with you

Your friend does the same on their side to complete the bidirectional setup.

## First Time Setup

If you don't have Google Drive API credentials yet, the `login()` function will guide you through creating them when you first run it.

## Credential Storage

Credentials are stored securely in `~/.syft/gdrive/` so you only need to authenticate once per account.