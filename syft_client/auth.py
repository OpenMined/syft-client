"""
Simplified authentication interface for syft_client
"""

import os
import json
import shutil
import urllib.parse
import time
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

# Try importing Colab auth
try:
    from google.colab import auth as colab_auth
    from google.colab import userdata
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

from .gdrive_unified import GDriveUnifiedClient, create_gdrive_client

# Wallet helper functions (previously in credential_wallet.py)
def _get_wallet_dir() -> Path:
    """Get the wallet directory path"""
    return Path.home() / ".syft" / "gdrive"


def _get_account_dir(email: str) -> Path:
    """Get the directory path for a specific account"""
    # Sanitize email for use as directory name
    safe_email = email.replace("@", "_at_").replace(".", "_")
    return _get_wallet_dir() / safe_email


def _get_stored_credentials_path(email: str) -> Optional[str]:
    """Get the path to stored credentials for an email"""
    account_dir = _get_account_dir(email)
    creds_path = account_dir / "credentials.json"
    
    if creds_path.exists():
        return str(creds_path)
    return None


def _get_stored_token_path(email: str) -> Optional[str]:
    """Get the path to the most recent valid stored token for an email"""
    account_dir = _get_account_dir(email)
    if not account_dir.exists():
        return None
    
    # Get all token files
    token_files = sorted([f for f in account_dir.glob("token_*.json")], reverse=True)
    
    # Try each token file, starting with the most recent
    for token_file in token_files:
        try:
            # Extract timestamp from filename
            filename = token_file.name
            timestamp_str = filename.replace("token_", "").replace(".json", "")
            
            # Parse timestamp and check age
            token_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            token_age_minutes = (datetime.now() - token_time).total_seconds() / 60
            
            # If token is less than 59 minutes old, assume it's still valid
            if token_age_minutes < 59:
                return str(token_file)
            
            # For older tokens, check if they can be loaded
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            # If we can load it, return this path
            return str(token_file)
        except:
            # If token is corrupted or can't parse timestamp, continue to next one
            continue
    
    return None


def _save_token(email: str, token_data: dict) -> bool:
    """Save OAuth token to wallet with timestamp"""
    account_dir = _get_account_dir(email)
    account_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        token_path = account_dir / f"token_{timestamp}.json"
        
        # Save the new token
        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        # Clean up old tokens - keep only the 5 most recent
        token_files = sorted([f for f in account_dir.glob("token_*.json")], reverse=True)
        if len(token_files) > 5:
            for old_token in token_files[5:]:
                try:
                    old_token.unlink()
                except:
                    pass
        
        return True
    except Exception as e:
        return False


def _update_token_timestamp(token_path: str) -> bool:
    """Update the timestamp of a token file when it's successfully used"""
    try:
        # Read the token data
        with open(token_path, 'r') as f:
            token_data = json.load(f)
        
        # Get the directory and create new filename with current timestamp
        token_file = Path(token_path)
        account_dir = token_file.parent
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_path = account_dir / f"token_{timestamp}.json"
        
        # Save to new file
        with open(new_path, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        # Remove old file if it's different
        if str(new_path) != str(token_file):
            token_file.unlink()
        
        # Clean up old tokens - keep only the 5 most recent
        token_files = sorted([f for f in account_dir.glob("token_*.json")], reverse=True)
        if len(token_files) > 5:
            for old_token in token_files[5:]:
                try:
                    old_token.unlink()
                except:
                    pass
        
        return True
    except Exception as e:
        return False


def _list_recent_tokens(email: str) -> List[Dict[str, str]]:
    """List recent tokens for an email with their timestamps"""
    account_dir = _get_account_dir(email)
    if not account_dir.exists():
        return []
    
    tokens = []
    token_files = sorted([f for f in account_dir.glob("token_*.json")], reverse=True)
    
    for token_file in token_files[:5]:  # Only show up to 5 most recent
        try:
            # Extract timestamp from filename
            filename = token_file.name
            timestamp_str = filename.replace("token_", "").replace(".json", "")
            
            # Parse timestamp
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            
            tokens.append({
                "filename": filename,
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "path": str(token_file)
            })
        except:
            continue
    
    return tokens


def _add_to_wallet(email: str, credentials_path: str, verbose: bool = True) -> bool:
    """Add credentials to the wallet"""
    if not os.path.exists(credentials_path):
        if verbose:
            print(f"❌ Credentials file not found: {credentials_path}")
        return False
        
    account_dir = _get_account_dir(email)
    account_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Copy credentials.json to account directory
        dest_path = account_dir / "credentials.json"
        shutil.copy2(credentials_path, dest_path)
        
        # Save email info
        info_path = account_dir / "account_info.json"
        with open(info_path, 'w') as f:
            json.dump({"email": email}, f, indent=2)
            
        if verbose:
            print(f"✅ Added credentials for {email}")
        return True
        
    except Exception as e:
        if verbose:
            print(f"❌ Error adding credentials: {e}")
        return False


def _list_wallet_accounts() -> List[str]:
    """List all accounts with stored credentials"""
    accounts = []
    wallet_dir = _get_wallet_dir()
    
    if not wallet_dir.exists():
        return accounts
        
    for account_dir in wallet_dir.iterdir():
        if account_dir.is_dir():
            info_path = account_dir / "account_info.json"
            if info_path.exists():
                try:
                    with open(info_path, 'r') as f:
                        info = json.load(f)
                        accounts.append(info.get("email", account_dir.name))
                except:
                    # Fallback to directory name
                    email = account_dir.name.replace("_at_", "@").replace("_", ".")
                    accounts.append(email)
                    
    return sorted(accounts)


def _remove_from_wallet(email: str) -> bool:
    """Remove credentials for a specific account"""
    account_dir = _get_account_dir(email)
    
    if not account_dir.exists():
        print(f"📁 No credentials found for {email}")
        return False
        
    try:
        shutil.rmtree(account_dir)
        print(f"🗑️  Removed credentials for {email}")
        return True
    except Exception as e:
        print(f"❌ Error removing account: {e}")
        return False


def _get_google_console_url(email: str) -> str:
    """
    Get the Google Cloud Console URL with the correct account pre-selected
    
    Args:
        email: Email address to use
        
    Returns:
        URL with authuser parameter
    """
    # URL encode the email to handle special characters
    encoded_email = urllib.parse.quote(email)
    return f"https://console.cloud.google.com/apis/credentials?authuser={encoded_email}"


def login(email: Optional[str] = None, credentials_path: Optional[str] = None, verbose: bool = False, force_relogin: bool = False) -> GDriveUnifiedClient:
    """
    Simple login function that checks wallet or adds new credentials
    
    Args:
        email: Email address to authenticate as. If not provided:
               - If only one account exists in wallet, uses that automatically
               - If multiple accounts exist, prompts for selection
        credentials_path: Optional path to credentials.json file (skips wizard if provided)
        verbose: Whether to print status messages (default: False)
        force_relogin: Force fresh authentication even if token exists (default: False)
        
    Returns:
        Authenticated GDriveUnifiedClient
    """
    # Early validation for credentials_path
    if credentials_path and not email:
        raise RuntimeError("Email address is required when providing a credentials_path")
    
    # If no email provided, check wallet for accounts
    if not email:
        accounts = _list_wallet_accounts()
        if not accounts:
            raise RuntimeError("No accounts found in wallet. Please provide an email address.")
        elif len(accounts) == 1:
            email = accounts[0]
            if verbose:
                print(f"🔑 Auto-selecting the only account in wallet: {email}")
        else:
            print("\n📋 Multiple accounts found in wallet:")
            for i, account in enumerate(accounts, 1):
                print(f"{i}. {account}")
            while True:
                try:
                    idx = int(input(f"\nSelect account [1-{len(accounts)}]: ").strip()) - 1
                    if 0 <= idx < len(accounts):
                        email = accounts[idx]
                        break
                    print(f"❌ Please enter a number between 1 and {len(accounts)}")
                except (ValueError, EOFError, KeyboardInterrupt):
                    print("\n❌ Cancelled")
                    raise RuntimeError("No account selected")
    
    # If credentials_path is provided, add to wallet first
    if credentials_path:
        path = os.path.expanduser(credentials_path)
        if not os.path.exists(path):
            raise RuntimeError(f"Credentials file not found: {path}")
        print(f"[1/3] 🔐 Adding credentials for {email}...", end='', flush=True)
        _add_to_wallet(email, path, verbose=verbose)
    
    # Common login flow for both wallet and credentials_path cases
    if _get_stored_credentials_path(email):
        steps = (["[2/3]", "[3/3]"] if credentials_path else ["[1/2]", "[2/2]"])
        
        print(f"\r{steps[0]} 🔑 Logging in as {email}..." + " " * 30, end='', flush=True)
        client = create_gdrive_client(email, verbose=verbose, force_relogin=force_relogin)
        
        print(f"\r{steps[1]} ✅ Logged in as {client.my_email}" + " " * 50)
        
        return client
    
    # Not in wallet - try wizard if in IPython
    try:
        from IPython import get_ipython
        if get_ipython() is not None:
            from .wizard import wizard
            print(f"❌ No credentials found for {email}\nRun syft_client.wizard() or print your client object to create credentials")
            return wizard(email=email)
    except ImportError:
        pass
    print("\n❌ Cancelled")
    raise RuntimeError(f"No credentials available for {email}")

def list_accounts() -> list:
    """
    List all accounts available for login
    
    Returns:
        List of email addresses
    """
    accounts = _list_wallet_accounts()
    
    if IN_COLAB:
        # Also check if we can get Colab user
        try:
            from googleapiclient.discovery import build
            colab_auth.authenticate_user()
            service = build('drive', 'v3')
            about = service.about().get(fields="user(emailAddress)").execute()
            colab_email = about['user']['emailAddress']
            if colab_email not in accounts:
                accounts.append(f"{colab_email} (Colab)")
        except:
            pass
    
    return accounts


def add_current_credentials_to_wallet() -> Optional[str]:
    """
    Add the current credentials.json to the wallet interactively
    
    Returns:
        Email address if successfully added, None otherwise
    """
    if not os.path.exists("credentials.json"):
        print("❌ No credentials.json found in current directory")
        return None
    
    # Try to authenticate and get the email
    try:
        temp_client = GDriveUnifiedClient(auth_method="credentials")
        if temp_client.authenticate():
            email = temp_client.my_email
            print(f"📧 Found credentials for: {email}")
            
            # Check if already in wallet
            if _get_stored_credentials_path(email):
                print(f"✅ {email} is already in the wallet")
                return email
            
            # Ask to add
            try:
                response = input(f"\nAdd {email} to wallet? [Y/n]: ").strip().lower()
                if response in ['', 'y', 'yes']:
                    _add_to_wallet(email, "credentials.json")
                    print(f"✅ Added {email} to wallet")
                    print(f"\nYou can now login from anywhere with:")
                    print(f'>>> client = login("{email}")')
                    return email
                else:
                    print("⏭️  Skipped")
                    return None
            except (EOFError, KeyboardInterrupt):
                print("\n⏭️  Cancelled")
                return None
        else:
            print("❌ Could not authenticate with credentials.json")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def reset_credentials(email: str):
    """
    Clear all cached credentials for an account to force re-authentication
    
    This is useful when you need to get new credentials with additional scopes
    (e.g., adding Google Sheets access)
    
    Args:
        email: Email address to reset credentials for
    """
    if not email:
        print("❌ Please specify an email to reset credentials for")
        return
    
    # Clear all tokens for the account
    account_dir = _get_account_dir(email)
    if account_dir.exists():
        token_count = 0
        for token_file in account_dir.glob("token_*.json"):
            try:
                token_file.unlink()
                token_count += 1
            except:
                pass
        if token_count > 0:
            print(f"🗑️  Cleared {token_count} cached token(s) for {email}")
            print(f"📝 Please re-authenticate to get new credentials:")
            print(f"   client = login('{email}', force_relogin=True)")
        else:
            print(f"📁 No cached tokens found for {email}")
    else:
        print(f"📁 No account found for {email}")


def logout(email: Optional[str] = None, clear_tokens_only: bool = True):
    """
    Logout from an account (remove from wallet)
    
    Args:
        email: Email to logout from
        clear_tokens_only: If True, only clear tokens. If False, remove entire account
    """
    if not email:
        print("❌ Please specify an email to logout")
        return
        
    if clear_tokens_only:
        # Clear all tokens for the account
        account_dir = _get_account_dir(email)
        if account_dir.exists():
            token_count = 0
            for token_file in account_dir.glob("token_*.json"):
                try:
                    token_file.unlink()
                    token_count += 1
                except:
                    pass
            if token_count > 0:
                print(f"🗑️  Cleared {token_count} cached token{'s' if token_count != 1 else ''} for {email}")
            else:
                print(f"📁 No cached tokens found for {email}")
        else:
            print(f"📁 No account found for {email}")
    else:
        # Remove entire account
        _remove_from_wallet(email)


def list_recent_tokens(email: str) -> None:
    """
    List recent cached tokens for an email
    
    Args:
        email: Email address to check tokens for
    """
    tokens = _list_recent_tokens(email)
    
    if not tokens:
        print(f"📁 No cached tokens found for {email}")
        return
    
    print(f"\n🔑 Recent tokens for {email}:")
    for i, token in enumerate(tokens, 1):
        print(f"{i}. {token['timestamp']} - {token['filename']}")