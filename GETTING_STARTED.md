# Getting Started with Syft-Client

Welcome to syft-client! This guide will help you set up secure, decentralized file sharing using Google Drive as your transport layer.

## 📋 Prerequisites

- Python 3.8 or higher
- A Google account
- Google Drive API access (we'll help you set this up)

## 🚀 Quick Installation

```bash
pip install syft-client
```

For development:
```bash
git clone https://github.com/OpenMined/syft-client.git
cd syft-client
pip install -e .
```

## 🔐 First-Time Authentication Setup

### Step 1: Import the Library

```python
import syft_client as sc
```

### Step 2: Login for the First Time

When you run `login()` for the first time, it will guide you through creating Google Drive API credentials:

```python
# First login - the wizard will guide you
client = sc.login("your_email@gmail.com")
```

The interactive wizard will:
1. Direct you to Google Cloud Console
2. Help you create a new project
3. Enable the Google Drive API
4. Create OAuth 2.0 credentials
5. Download and save your `credentials.json` file

### Step 3: Authenticate

After setting up credentials, the login process will:
1. Open a browser for Google authentication
2. Ask you to sign in and grant permissions
3. Save your authentication token for future use

```python
# Future logins are automatic
client = sc.login("your_email@gmail.com")
```

## 📦 Creating Your SyftBox

A SyftBox is your secure communication hub in Google Drive:

```python
# Create or reset your SyftBox folder
client.reset_syftbox()
```

This creates a `SyftBoxTransportService` folder in your Google Drive with the proper structure for secure communication.

## 👥 Managing Friends

### Adding a Friend

To set up a secure communication channel with someone:

```python
# Add a friend by their email
client.add_friend("friend@example.com")

# Check your friends list
print(client.friends)  # ['friend@example.com']
```

### Checking Friend Requests

See who wants to connect with you:

```python
# Check incoming friend requests
print(client.friend_requests)  # ['someone@example.com']

# Accept by adding them back
client.add_friend("someone@example.com")
```

## 🔄 Complete Two-User Setup Example

Here's how two users (Alice and Bob) set up bidirectional communication:

```python
# Alice's setup
alice = sc.login("alice@gmail.com")
alice.reset_syftbox()  # Fresh start
alice.add_friend("bob@gmail.com")

# Bob's setup (on Bob's machine)
bob = sc.login("bob@gmail.com") 
bob.reset_syftbox()  # Fresh start

# Bob checks friend requests
print(bob.friend_requests)  # ['alice@gmail.com']

# Bob adds Alice back to complete the channel
bob.add_friend("alice@gmail.com")

# Both can now see each other as friends
print(alice.friends)  # ['bob@gmail.com']
print(bob.friends)    # ['alice@gmail.com']
```

## 💾 Working with Credentials

### Multiple Accounts

You can manage multiple Google accounts:

```python
# List all accounts in your wallet
accounts = sc.list_accounts()
print(accounts)  # ['alice@gmail.com', 'bob@gmail.com']

# Login with a specific account
client = sc.login("alice@gmail.com")
```

### Credential Storage

Credentials are securely stored in `~/.syft/gdrive/` so you only need to authenticate once per account.

### Force Re-authentication

If you need to refresh your authentication:

```python
client = sc.login("your_email@gmail.com", force_relogin=True)
```

## 🔍 Understanding the Folder Structure

After setting up a friend connection, your Google Drive will have:

```
SyftBoxTransportService/
├── syft_you@gmail.com_to_friend@gmail.com_pending/     # Your outgoing messages
├── syft_you@gmail.com_to_friend@gmail.com_outbox_inbox/ # Active channel
└── syft_friend@gmail.com_to_you@gmail.com_archive/     # Processed messages from friend
```

## 🐛 Troubleshooting

### Common Issues and Solutions

1. **"credentials.json not found"**
   - Run `sc.wizard()` to create new credentials
   - Or download from Google Cloud Console

2. **"Not authenticated"**
   - Check if you're logged in: `client.authenticated`
   - Try force re-login: `sc.login(email, force_relogin=True)`

3. **"Friend not showing up"**
   - Ensure both users have added each other
   - Check `client.friend_requests` for pending requests

4. **"SyftBox already exists"**
   - Use `client.reset_syftbox()` to start fresh
   - This will delete and recreate the folder

5. **Token expired**
   - The client automatically refreshes expired tokens
   - If issues persist, use `force_relogin=True`

## 🎓 Next Steps

Once you have your basic setup:

1. **Explore the API**: Check out [API_REFERENCE.md](API_REFERENCE.md) for detailed documentation
2. **Try the Tutorial**: Open `syft_client_tutorial.ipynb` for interactive examples
3. **Learn about Messages**: See how to send files securely using `SyftMessage`
4. **Join the Community**: Report issues and get help at [GitHub Issues](https://github.com/OpenMined/syft-client/issues)

## 📚 Additional Resources

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Tutorial Notebook](syft_client_tutorial.ipynb) - Interactive examples
- [Message Tutorial](syft_message_tutorial.ipynb) - Deep dive into secure messaging
- [Project Repository](https://github.com/OpenMined/syft-client) - Source code and issues

## ⚡ Quick Command Reference

```python
# Authentication
client = sc.login(email)                    # Login
sc.list_accounts()                          # List saved accounts
sc.logout(email)                            # Remove saved credentials

# SyftBox Management  
client.reset_syftbox()                      # Create/reset SyftBox
client.authenticated                        # Check auth status
client.my_email                            # Get authenticated email

# Friend Management
client.add_friend(email)                    # Add a friend
client.friends                              # List friends
client.friend_requests                     # Check incoming requests

# Client Info
print(client)                               # Pretty print client status
```

Happy secure file sharing! 🚀