"""
Credential Manager for syft-client using syft-wallet

This module delegates ALL credential storage to syft-wallet.
No private keys or passwords are stored locally.
"""

from typing import Optional, Dict, Any
import syft_wallet as wallet


class CredentialManager:
    """
    Credential manager that delegates all storage to syft-wallet
    """
    
    def __init__(self, app_name: str = "syft-client"):
        """
        Initialize credential manager
        
        Args:
            app_name: Application name for syft-wallet approval dialogs
        """
        self.app_name = app_name
    
    def store_email_credentials(self, email: str, password: str, provider: str,
                               servers: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store email credentials in syft-wallet
        
        Args:
            email: Email address
            password: Password or app password
            provider: Provider name (e.g., 'google_personal')
            servers: Optional server configuration (not stored)
            
        Returns:
            Success status
        """
        # Use a safer name format to avoid JSON parsing issues
        safe_name = f"{provider}-{email.replace('@', '_at_').replace('.', '_')}"
        
        # Debug logging
        print(f"\n🔍 DEBUG: Attempting to store credentials in syft-wallet:")
        print(f"  Name: {safe_name}")
        print(f"  Username: {email}")
        print(f"  Password: {'*' * len(password)} ({len(password)} chars)")
        print(f"  Tags: ['email', '{provider}', 'syftclient']")
        
        try:
            # Store credentials as a JSON string using the simpler store() function
            import json
            cred_data = {
                'username': email,
                'password': password,
                'provider': provider,
                'type': 'email_credentials'
            }
            
            # Use the simple store() function which seems to work better
            result = wallet.store(
                name=safe_name,
                value=json.dumps(cred_data),
                tags=["email", provider, "syftclient"],
                description=f"{provider} email account"
            )
            print(f"  Result: {result}")
            return result
        except Exception as e:
            print(f"  ❌ Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_email_credentials(self, email: str, provider: str, 
                            reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get email credentials from syft-wallet (requires user approval)
        
        Args:
            email: Email address
            provider: Provider name
            reason: Reason for access (shown in approval dialog)
            
        Returns:
            Credential dictionary or None if denied/not found
        """
        reason = reason or f"Access {provider} email for file syncing"
        
        try:
            # Get credentials from syft-wallet with user approval
            # Use the same safe name format
            safe_name = f"{provider}-{email.replace('@', '_at_').replace('.', '_')}"
            
            # Use the simple get() function
            cred_json = wallet.get(
                name=safe_name,
                app_name=self.app_name,
                reason=reason
            )
            
            if cred_json:
                import json
                cred_data = json.loads(cred_json)
                # Return in expected format
                return {
                    'email': cred_data.get('username', email),
                    'password': cred_data['password'],
                    'provider': cred_data.get('provider', provider)
                }
        except Exception as e:
            # User denied or error occurred
            print(f"Failed to get credentials: {e}")
        
        return None
    
    def store_oauth_token(self, email: str, provider: str, 
                         refresh_token: str, access_token: Optional[str] = None) -> bool:
        """
        Store OAuth tokens in syft-wallet
        
        Args:
            email: Email address
            provider: Provider name
            refresh_token: OAuth refresh token
            access_token: Optional current access token
            
        Returns:
            Success status
        """
        # Store as a secret with structured value
        token_data = {
            'refresh_token': refresh_token,
            'access_token': access_token
        }
        
        # Convert to JSON string for storage
        import json
        token_json = json.dumps(token_data)
        
        # Use safe name format
        safe_name = f"{provider}-oauth-{email.replace('@', '_at_').replace('.', '_')}"
        
        return wallet.store(
            name=safe_name,
            value=token_json,
            tags=["oauth", provider, "email", "syft-client"],
            description=f"OAuth tokens for {provider} ({email})"
        )
    
    def get_oauth_token(self, email: str, provider: str,
                       reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get OAuth tokens from syft-wallet (requires user approval)
        
        Args:
            email: Email address
            provider: Provider name
            reason: Reason for access
            
        Returns:
            Dict with refresh_token and access_token or None
        """
        reason = reason or f"Refresh {provider} OAuth token for email sync"
        
        try:
            # Get token from syft-wallet with user approval
            safe_name = f"{provider}-oauth-{email.replace('@', '_at_').replace('.', '_')}"
            
            token_json = wallet.get(
                name=safe_name,
                app_name=self.app_name,
                reason=reason
            )
            
            if token_json:
                import json
                return json.loads(token_json)
        except Exception as e:
            print(f"Failed to get OAuth token: {e}")
        
        return None
    
    def delete_credentials(self, email: str, provider: str) -> bool:
        """
        Delete credentials from syft-wallet
        
        Args:
            email: Email address
            provider: Provider name
            
        Returns:
            Success status
        """
        try:
            # Delete both password and OAuth tokens using safe names
            safe_name = f"{provider}-{email.replace('@', '_at_').replace('.', '_')}"
            safe_oauth_name = f"{provider}-oauth-{email.replace('@', '_at_').replace('.', '_')}"
            
            wallet.delete(safe_name)
            wallet.delete(safe_oauth_name)
            return True
        except:
            return False
    
    def has_credentials(self, email: str, provider: str) -> bool:
        """
        Check if credentials exist in syft-wallet (no user approval needed)
        
        Args:
            email: Email address  
            provider: Provider name
            
        Returns:
            True if credentials exist
        """
        try:
            # Use wallet.exists() if available, otherwise try to list items
            if hasattr(wallet, 'exists'):
                safe_name = f"{provider}-{email.replace('@', '_at_').replace('.', '_')}"
                return wallet.exists(safe_name)
            elif hasattr(wallet, 'list'):
                # Try to list items and check if our item exists
                safe_name = f"{provider}-{email.replace('@', '_at_').replace('.', '_')}"
                items = wallet.list()
                return safe_name in items
            else:
                # Can't check without approval dialog
                return False
        except:
            return False


# Singleton instance
_credential_manager = None

def get_credential_manager(**kwargs) -> CredentialManager:
    """Get or create the credential manager singleton"""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager(**kwargs)
    return _credential_manager