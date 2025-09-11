# Wallet System Design

## Overview

The wallet system provides a flexible abstraction for storing OAuth2 tokens and other sensitive credentials. Users can choose their preferred storage method based on their security needs and environment.

## Core Wallet Interface

```python
class BaseWallet:
    """Abstract base class for all wallet implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with wallet-specific configuration"""
        self.config = config
    
    def store_token(self, service: str, account: str, token_data: Dict) -> bool:
        """Store a token in the wallet"""
        raise NotImplementedError
    
    def retrieve_token(self, service: str, account: str) -> Optional[Dict]:
        """Retrieve a token from the wallet"""
        raise NotImplementedError
    
    def delete_token(self, service: str, account: str) -> bool:
        """Delete a token from the wallet"""
        raise NotImplementedError
    
    def list_tokens(self, service: Optional[str] = None) -> List[str]:
        """List available tokens"""
        raise NotImplementedError
    
    def test_connection(self) -> bool:
        """Test if wallet is accessible"""
        raise NotImplementedError
    
    @property
    def name(self) -> str:
        """Human-readable wallet name"""
        raise NotImplementedError
    
    @property
    def requires_setup(self) -> bool:
        """Whether wallet needs initial configuration"""
        return False
    
    def setup_wizard(self) -> Dict[str, Any]:
        """Interactive setup for wallet configuration"""
        return {}
```

## Built-in Wallet Implementations

### 1. LocalFileWallet (Default)

```python
class LocalFileWallet(BaseWallet):
    """Store tokens in encrypted local files"""
    
    name = "Local Encrypted Files"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_dir = Path(config.get('base_dir', '~/.syft'))
        self.encryption_key = self._get_or_create_key()
```

**Features:**
- Stores tokens in `~/.syft/[email]/tokens/`
- Uses Fernet encryption with machine-specific key
- Automatic key generation on first use
- File permissions set to 0600

**Security:**
- Encryption key derived from machine UUID + user ID
- Tokens encrypted at rest
- No external dependencies

### 2. OnePasswordWallet

```python
class OnePasswordWallet(BaseWallet):
    """Store tokens in 1Password vault"""
    
    name = "1Password"
    requires_setup = True
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.vault = config.get('vault', 'Personal')
        self.account = config.get('account')
        self.op_path = config.get('op_path', 'op')
```

**Features:**
- Uses 1Password CLI (`op`)
- Stores tokens as secure notes
- Supports multiple vaults
- Biometric unlock support

**Setup Requirements:**
- 1Password CLI installed
- Account URL configuration
- Vault selection

### 3. MacOSKeychainWallet

```python
class MacOSKeychainWallet(BaseWallet):
    """Store tokens in macOS Keychain"""
    
    name = "macOS Keychain"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.service_name = config.get('service_name', 'com.syft.tokens')
        self.keychain = config.get('keychain', 'login')
```

**Features:**
- Native macOS integration
- No additional tools required
- Syncs via iCloud Keychain (optional)
- Touch ID support

**Limitations:**
- macOS only
- Limited to 4KB per item

### 4. AWSSecretsWallet

```python
class AWSSecretsWallet(BaseWallet):
    """Store tokens in AWS Secrets Manager"""
    
    name = "AWS Secrets Manager"
    requires_setup = True
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.region = config.get('region', 'us-east-1')
        self.kms_key_id = config.get('kms_key_id')
        self.secret_prefix = config.get('prefix', 'syft/')
```

**Features:**
- Cloud storage with versioning
- KMS encryption
- IAM access control
- Cross-region replication

**Setup Requirements:**
- AWS credentials configured
- IAM permissions for Secrets Manager
- Optional: Custom KMS key

### 5. BitwolfWallet

```python
class BitwolfWallet(BaseWallet):
    """Store tokens in Bitwarden vault"""
    
    name = "Bitwarden"
    requires_setup = True
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.server = config.get('server', 'https://vault.bitwarden.com')
        self.bw_path = config.get('bw_path', 'bw')
```

**Features:**
- Open source password manager
- Self-hostable option
- Cross-platform support
- CLI integration

### 6. EnvironmentVariableWallet

```python
class EnvironmentVariableWallet(BaseWallet):
    """Read-only wallet for CI/CD environments"""
    
    name = "Environment Variables"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.prefix = config.get('prefix', 'SYFT_TOKEN_')
    
    def store_token(self, service: str, account: str, token_data: Dict) -> bool:
        # Read-only - cannot store
        print(f"⚠️  Environment variables are read-only. Set {self.prefix}{service}_{account}")
        return False
    
    def retrieve_token(self, service: str, account: str) -> Optional[Dict]:
        env_var = f"{self.prefix}{service}_{account}".upper()
        token_json = os.environ.get(env_var)
        if token_json:
            return json.loads(token_json)
        return None
```

**Features:**
- CI/CD friendly
- Docker compatible
- Read-only access
- No external dependencies

**Use Cases:**
- GitHub Actions
- GitLab CI
- Docker containers
- Kubernetes secrets

## Wallet Selection Flow

### First-Time Setup

After successful OAuth2 authentication, first-time users see:

```
✅ OAuth2 authentication successful!

Now, where would you like to store your access token?
This token allows Syft Client to access Google services on your behalf.

Options:
1. Local file (default) - Simple, works everywhere
2. 1Password - Secure, syncs across devices (requires 1Password CLI)
3. macOS Keychain - Secure, Mac only
4. Bitwarden - Open source, cross-platform (requires Bitwarden CLI) 
5. Environment variable (read-only) - For CI/CD

Your choice [1-5]: 2

Great! To use 1Password:
1. Install 1Password CLI: https://1password.com/downloads/command-line/
2. Run: op signin
3. Press Enter when ready...

✓ Token stored in 1Password
✓ Wallet preference saved

Future logins will automatically use 1Password.
```

### Implementation

```python
def configure_wallet_preference(email: str, verbose: bool = True) -> Dict[str, Any]:
    """Interactive wallet configuration"""
    
    # Step 1: Detect available wallets
    available_wallets = detect_available_wallets()
    
    # Step 2: Show options
    if verbose:
        print("\n🔐 Choose your token storage preference:")
        for i, wallet in enumerate(available_wallets):
            print(f"{i+1}. {wallet.name}")
    
    # Step 3: User selection
    choice = get_user_choice(len(available_wallets))
    selected_wallet = available_wallets[choice - 1]
    
    # Step 4: Wallet-specific setup
    if selected_wallet.requires_setup:
        config = selected_wallet.setup_wizard()
    else:
        config = {}
    
    # Step 5: Test connection
    wallet = selected_wallet(config)
    if not wallet.test_connection():
        # Fallback to default
        print("⚠️  Setup failed, using local file storage")
        return {"preferred_wallet": "local_file", "wallet_config": {}}
    
    # Step 6: Save preference to ~/.syft/[email]/config.json
    save_wallet_config(email, {
        "preferred_wallet": wallet.__class__.__name__,
        "wallet_config": config,
        "fallback_wallet": "local_file"
    })
    
    return config
```

### Wallet Detection

```python
def detect_available_wallets() -> List[BaseWallet]:
    """Detect which wallets are available on system"""
    
    available = [LocalFileWallet]  # Always available
    
    # Check 1Password CLI
    if shutil.which('op'):
        available.append(OnePasswordWallet)
    
    # Check macOS
    if platform.system() == 'Darwin':
        available.append(MacOSKeychainWallet)
    
    # Check AWS CLI/SDK
    try:
        import boto3
        available.append(AWSSecretsWallet)
    except ImportError:
        pass
    
    # Check Bitwarden CLI
    if shutil.which('bw'):
        available.append(BitwolfWallet)
    
    return available
```

## Wallet Configuration

Configuration is stored in `~/.syft/[email]/config.json`:

```json
{
    "preferred_wallet": "1password",
    "wallet_config": {
        "vault": "Personal",
        "account": "my.1password.com"
    },
    "fallback_wallet": "local_file"
}
```

## Token Storage Format

### Standard Token Structure

```json
{
    "platform": "google_personal",
    "email": "user@gmail.com",
    "token_data": {
        "token": "ya29.a0AfH6SMB...",
        "refresh_token": "1//0gLKJ...",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "1234567890.apps.googleusercontent.com",
        "client_secret": "GOCSPX-...",
        "scopes": ["https://www.googleapis.com/auth/gmail.send"],
        "expiry": "2024-12-11T12:30:00Z"
    },
    "metadata": {
        "created_at": "2024-12-11T10:30:00Z",
        "last_used": "2024-12-11T11:30:00Z",
        "created_by": "syft-client v0.1.0"
    }
}
```

### Wallet-Specific Storage

#### 1Password Item Format
```
Title: Syft Token - google_personal - user@gmail.com
Category: Secure Note
Fields:
  - platform: google_personal
  - email: user@gmail.com
  - token: [concealed]
  - refresh_token: [concealed]
  - metadata: JSON string
Tags: syft, oauth2
```

#### macOS Keychain Item
```
Service: com.syft.tokens
Account: google_personal:user@gmail.com
Password: <JSON-encoded token data>
Comment: Syft OAuth2 Token
Access Group: com.syft.client
```

#### AWS Secrets Manager
```
Secret Name: syft/google_personal/user@gmail.com
Secret Value: <JSON token data>
Tags:
  - syft-platform: google_personal
  - syft-email: user@gmail.com
KMS Key: alias/syft-tokens (optional)
```

## Wallet Fallback Strategy

```python
def get_or_create_wallet(email: str) -> BaseWallet:
    """Get configured wallet with fallback"""
    
    config = load_wallet_config(email)
    
    if not config:
        # First time - use default
        return LocalFileWallet({})
    
    # Try preferred wallet
    try:
        wallet_class = get_wallet_class(config['preferred_wallet'])
        wallet = wallet_class(config['wallet_config'])
        
        if wallet.test_connection():
            return wallet
    except Exception as e:
        print(f"⚠️  Preferred wallet unavailable: {e}")
    
    # Try fallback
    if 'fallback_wallet' in config:
        try:
            fallback_class = get_wallet_class(config['fallback_wallet'])
            return fallback_class({})
        except:
            pass
    
    # Final fallback
    return LocalFileWallet({})
```

## Security Considerations

### Access Control
- Each wallet implementation handles its own access control
- Syft never stores wallet master credentials
- Token access requires platform + email combination

### Encryption
- Local files: Fernet symmetric encryption
- 1Password: AES-256-GCM
- macOS Keychain: AES-128 (system managed)
- AWS Secrets Manager: KMS envelope encryption
- Bitwarden: AES-256

### Key Management
- Local: Machine-specific key derivation
- Cloud: Provider-managed keys
- No keys stored in code or config files

### Audit Trail
- All wallets track creation/access metadata
- Cloud wallets provide native audit logs
- Local wallet logs token operations

## Migration Support

```python
def migrate_tokens(from_wallet: BaseWallet, to_wallet: BaseWallet) -> Dict[str, Any]:
    """Migrate all tokens between wallets"""
    
    results = {
        'migrated': [],
        'failed': []
    }
    
    # List all tokens
    tokens = from_wallet.list_tokens()
    
    for token_info in tokens:
        try:
            # Retrieve from source
            token_data = from_wallet.retrieve_token(
                token_info['service'],
                token_info['account']
            )
            
            # Store in destination
            if to_wallet.store_token(
                token_info['service'],
                token_info['account'],
                token_data
            ):
                results['migrated'].append(token_info)
                
                # Optionally delete from source
                # from_wallet.delete_token(...)
            else:
                results['failed'].append(token_info)
                
        except Exception as e:
            results['failed'].append({
                **token_info,
                'error': str(e)
            })
    
    return results
```

## Wallet Development Guide

### Creating Custom Wallets

```python
from syft_client.auth.wallets import BaseWallet

class MyCustomWallet(BaseWallet):
    """Custom wallet implementation"""
    
    name = "My Custom Storage"
    requires_setup = True
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Initialize your storage backend
        self.backend = MyStorageBackend(config)
    
    def store_token(self, service: str, account: str, token_data: Dict) -> bool:
        key = f"{service}:{account}"
        encrypted_data = self.encrypt(json.dumps(token_data))
        return self.backend.store(key, encrypted_data)
    
    def setup_wizard(self) -> Dict[str, Any]:
        # Interactive setup
        config = {}
        config['server'] = input("Storage server URL: ")
        config['api_key'] = getpass("API Key: ")
        return config
```

### Registration

```python
# In wallets/__init__.py
AVAILABLE_WALLETS = {
    'local_file': LocalFileWallet,
    'onepassword': OnePasswordWallet,
    'keychain': MacOSKeychainWallet,
    'aws_secrets': AWSSecretsWallet,
    'bitwarden': BitwolfWallet,
    'env_vars': EnvironmentVariableWallet,
    'my_custom': MyCustomWallet  # Add your wallet
}
```