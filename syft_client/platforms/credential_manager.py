"""
Credential Manager for syft-client using syft-wallet with extended caching

This module provides credential management with enhanced caching capabilities
for email providers and other authentication needs.
"""

from typing import Optional, Dict, Any, List
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
from cryptography.fernet import Fernet

# Note: This will use syft-wallet when available
# For now, we implement a compatible interface
try:
    import syft_wallet as wallet
    HAS_SYFT_WALLET = True
except ImportError:
    HAS_SYFT_WALLET = False


class CacheDuration(Enum):
    """Predefined cache durations"""
    NO_CACHE = 0
    MINUTES_5 = 300
    MINUTES_30 = 1800
    HOURS_1 = 3600
    HOURS_8 = 28800
    HOURS_24 = 86400
    DAYS_7 = 604800
    DAYS_30 = 2592000
    
    @classmethod
    def from_string(cls, duration: str) -> 'CacheDuration':
        """Convert string like '5m', '1h', '7d' to CacheDuration"""
        duration = duration.lower().strip()
        
        if duration.endswith('m'):
            minutes = int(duration[:-1])
            seconds = minutes * 60
        elif duration.endswith('h'):
            hours = int(duration[:-1])
            seconds = hours * 3600
        elif duration.endswith('d'):
            days = int(duration[:-1])
            seconds = days * 86400
        else:
            seconds = int(duration)
        
        # Find closest matching duration
        for dur in cls:
            if dur.value >= seconds:
                return dur
        return cls.DAYS_30


class PersistentCache:
    """
    Persistent encrypted cache for credentials
    
    This extends syft-wallet's in-memory cache with disk persistence
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize persistent cache"""
        self.cache_dir = cache_dir or Path.home() / ".syft" / "credential_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load encryption key
        self._init_encryption()
        
        # Cache index file
        self.index_file = self.cache_dir / "cache_index.json"
        self.index = self._load_index()
    
    def _init_encryption(self):
        """Initialize Fernet encryption"""
        key_file = self.cache_dir / ".key"
        
        if key_file.exists():
            # Load existing key
            with open(key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(key_file, 0o600)
        
        self.cipher = Fernet(key)
    
    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        """Load cache index from disk"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_index(self):
        """Save cache index to disk"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
        os.chmod(self.index_file, 0o600)
    
    def _get_cache_key(self, provider: str, credential_type: str, identifier: str) -> str:
        """Generate cache key"""
        return f"{provider}:{credential_type}:{identifier}"
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """Get path to cache file"""
        # Use hash to avoid filesystem issues with special characters
        import hashlib
        filename = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{filename}.cache"
    
    def get(self, provider: str, credential_type: str, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get cached credential if valid
        
        Args:
            provider: Provider name (e.g., 'google_personal')
            credential_type: Type of credential (e.g., 'app_password', 'oauth_token')
            identifier: Unique identifier (e.g., email address)
            
        Returns:
            Cached credential data or None if expired/not found
        """
        cache_key = self._get_cache_key(provider, credential_type, identifier)
        
        # Check index
        if cache_key not in self.index:
            return None
        
        entry = self.index[cache_key]
        
        # Check expiration
        if time.time() > entry['expires_at']:
            # Expired - remove from cache
            self.delete(provider, credential_type, identifier)
            return None
        
        # Load encrypted data
        cache_file = self._get_cache_file(cache_key)
        if not cache_file.exists():
            # Index out of sync - clean up
            del self.index[cache_key]
            self._save_index()
            return None
        
        try:
            # Decrypt and return
            with open(cache_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted.decode())
        except Exception as e:
            # Corruption or key change - remove entry
            self.delete(provider, credential_type, identifier)
            return None
    
    def set(self, provider: str, credential_type: str, identifier: str, 
            data: Dict[str, Any], duration: CacheDuration = CacheDuration.HOURS_24):
        """
        Cache credential data
        
        Args:
            provider: Provider name
            credential_type: Type of credential
            identifier: Unique identifier
            data: Credential data to cache
            duration: How long to cache
        """
        if duration == CacheDuration.NO_CACHE:
            return
        
        cache_key = self._get_cache_key(provider, credential_type, identifier)
        cache_file = self._get_cache_file(cache_key)
        
        # Encrypt data
        json_data = json.dumps(data).encode()
        encrypted = self.cipher.encrypt(json_data)
        
        # Save to disk
        with open(cache_file, 'wb') as f:
            f.write(encrypted)
        os.chmod(cache_file, 0o600)
        
        # Update index
        self.index[cache_key] = {
            'provider': provider,
            'credential_type': credential_type,
            'identifier': identifier,
            'created_at': time.time(),
            'expires_at': time.time() + duration.value,
            'duration': duration.name
        }
        self._save_index()
    
    def delete(self, provider: str, credential_type: str, identifier: str):
        """Delete cached credential"""
        cache_key = self._get_cache_key(provider, credential_type, identifier)
        
        # Remove from index
        if cache_key in self.index:
            del self.index[cache_key]
            self._save_index()
        
        # Remove file
        cache_file = self._get_cache_file(cache_key)
        if cache_file.exists():
            cache_file.unlink()
    
    def clear_expired(self):
        """Remove all expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.index.items()
            if current_time > entry['expires_at']
        ]
        
        for key in expired_keys:
            # Parse key to get components
            parts = key.split(':', 2)
            if len(parts) == 3:
                self.delete(parts[0], parts[1], parts[2])
    
    def clear_all(self):
        """Clear all cached credentials"""
        # Remove all cache files
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink()
        
        # Clear index
        self.index = {}
        self._save_index()


class CredentialManager:
    """
    Manages credentials for syft-client with enhanced caching
    """
    
    def __init__(self, app_name: str = "syft-client", 
                 cache_dir: Optional[Path] = None,
                 default_cache_duration: CacheDuration = CacheDuration.HOURS_24):
        """
        Initialize credential manager
        
        Args:
            app_name: Application name for syft-wallet
            cache_dir: Directory for persistent cache
            default_cache_duration: Default cache duration
        """
        self.app_name = app_name
        self.cache = PersistentCache(cache_dir)
        self.default_cache_duration = default_cache_duration
        
        # Provider-specific cache policies
        self.cache_policies = {
            'google_personal': {
                'app_password': CacheDuration.DAYS_30,  # App passwords are stable
                'oauth_token': CacheDuration.DAYS_7,    # OAuth tokens last a while
            },
            'google_org': {
                'app_password': CacheDuration.DAYS_7,   # Org policies may be stricter
                'oauth_token': CacheDuration.HOURS_24,  # Org tokens may expire faster
            },
            'smtp': {
                'credentials': CacheDuration.DAYS_30,   # SMTP passwords are stable
            }
        }
    
    def get_cache_duration(self, provider: str, credential_type: str) -> CacheDuration:
        """Get cache duration for a specific credential type"""
        if provider in self.cache_policies:
            if credential_type in self.cache_policies[provider]:
                return self.cache_policies[provider][credential_type]
        return self.default_cache_duration
    
    def store_email_credentials(self, email: str, password: str, provider: str,
                               servers: Optional[Dict[str, Any]] = None,
                               cache: bool = True) -> bool:
        """
        Store email credentials
        
        Args:
            email: Email address
            password: Password or app password
            provider: Provider name (e.g., 'google_personal')
            servers: Optional server configuration
            cache: Whether to cache the credentials
            
        Returns:
            Success status
        """
        # Store in syft-wallet if available
        if HAS_SYFT_WALLET:
            success = wallet.store_credentials(
                name=f"{provider}:{email}",
                username=email,
                password=password,
                tags=["email", provider, "syft-client"],
                description=f"{provider} email account for syft-client"
            )
            if not success:
                return False
        
        # Cache if requested
        if cache:
            cache_data = {
                'email': email,
                'password': password,
                'provider': provider,
                'timestamp': time.time()
            }
            
            if servers:
                cache_data['servers'] = servers
            
            duration = self.get_cache_duration(provider, 'app_password')
            self.cache.set(provider, 'app_password', email, cache_data, duration)
        
        return True
    
    def get_email_credentials(self, email: str, provider: str, 
                            use_cache: bool = True,
                            reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get email credentials with caching
        
        Args:
            email: Email address
            provider: Provider name
            use_cache: Whether to check cache first
            reason: Reason for access (for syft-wallet approval)
            
        Returns:
            Credential dictionary or None
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get(provider, 'app_password', email)
            if cached:
                return cached
        
        # Try syft-wallet
        if HAS_SYFT_WALLET:
            reason = reason or f"Access {provider} email for file syncing"
            
            try:
                creds = wallet.get_credentials(
                    name=f"{provider}:{email}",
                    app_name=self.app_name,
                    reason=reason
                )
                
                if creds:
                    # Build return format
                    result = {
                        'email': creds.get('username', email),
                        'password': creds['password'],
                        'provider': provider,
                        'timestamp': time.time()
                    }
                    
                    # Cache for next time
                    duration = self.get_cache_duration(provider, 'app_password')
                    self.cache.set(provider, 'app_password', email, result, duration)
                    
                    return result
            except Exception as e:
                pass
        
        return None
    
    def clear_cache(self, email: Optional[str] = None, provider: Optional[str] = None):
        """
        Clear cached credentials
        
        Args:
            email: Specific email to clear (optional)
            provider: Specific provider to clear (optional)
        """
        if email and provider:
            # Clear specific credential
            self.cache.delete(provider, 'app_password', email)
            self.cache.delete(provider, 'oauth_token', email)
        elif provider:
            # Clear all for provider
            for key, entry in list(self.cache.index.items()):
                if entry['provider'] == provider:
                    parts = key.split(':', 2)
                    if len(parts) == 3:
                        self.cache.delete(parts[0], parts[1], parts[2])
        else:
            # Clear all
            self.cache.clear_all()
    
    def list_cached_credentials(self) -> List[Dict[str, Any]]:
        """List all cached credentials"""
        credentials = []
        
        for key, entry in self.cache.index.items():
            # Calculate remaining time
            remaining = entry['expires_at'] - time.time()
            
            credentials.append({
                'provider': entry['provider'],
                'type': entry['credential_type'],
                'identifier': entry['identifier'],
                'created': datetime.fromtimestamp(entry['created_at']).strftime('%Y-%m-%d %H:%M:%S'),
                'expires': datetime.fromtimestamp(entry['expires_at']).strftime('%Y-%m-%d %H:%M:%S'),
                'remaining': f"{remaining/3600:.1f} hours" if remaining > 0 else "Expired"
            })
        
        return credentials


# Singleton instance
_credential_manager = None

def get_credential_manager(**kwargs) -> CredentialManager:
    """Get or create the credential manager singleton"""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager(**kwargs)
    return _credential_manager