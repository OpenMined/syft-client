"""
Simplified authentication interface for syft_client
"""

import os
import sys
import json
import shutil
import urllib.parse
from typing import Optional, List
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
    """Get the path to stored token for an email"""
    account_dir = _get_account_dir(email)
    token_path = account_dir / "token.json"
    
    if token_path.exists():
        return str(token_path)
    return None


def _save_token(email: str, token_data: dict) -> bool:
    """Save OAuth token to wallet"""
    account_dir = _get_account_dir(email)
    account_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        token_path = account_dir / "token.json"
        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)
        return True
    except Exception as e:
        return False


def _add_to_wallet(email: str, credentials_path: str, verbose: bool = True) -> bool:
    """Add credentials to the wallet"""
    if not os.path.exists(credentials_path):
        if verbose:
            print(f"❌ Credentials file not found: {credentials_path}")
        return False
        
    # Validate that the credentials file is valid JSON with required fields
    try:
        with open(credentials_path, 'r') as f:
            creds_data = json.load(f)
            
        # Check for required OAuth2 fields
        required_fields = ['installed', 'web']
        if not any(field in creds_data for field in required_fields):
            if verbose:
                print(f"❌ Invalid credentials file: missing 'installed' or 'web' configuration")
            return False
            
    except json.JSONDecodeError as e:
        if verbose:
            print(f"❌ Invalid JSON in credentials file: {e}")
        return False
    except Exception as e:
        if verbose:
            print(f"❌ Error reading credentials file: {e}")
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


def _get_credentials_setup_url(email: str) -> str:
    """
    Get the credentials setup URL (alias for _get_google_console_url for backwards compatibility)
    
    Args:
        email: Email address to use
        
    Returns:
        URL with authuser parameter
    """
    return _get_google_console_url(email)


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
    
    # If no email provided, check wallet for accounts
    if not email:
        accounts = _list_wallet_accounts()
        
        if len(accounts) == 0:
            raise RuntimeError("No accounts found in wallet. Please provide an email address.")
        elif len(accounts) == 1:
            # Auto-select the only account
            email = accounts[0]
            if verbose:
                print(f"🔑 Auto-selecting the only account in wallet: {email}")
        else:
            # Multiple accounts - prompt for selection
            print("\n📋 Multiple accounts found in wallet:")
            for i, account in enumerate(accounts, 1):
                print(f"{i}. {account}")
            
            while True:
                try:
                    choice = input(f"\nSelect account [1-{len(accounts)}]: ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(accounts):
                        email = accounts[idx]
                        break
                    else:
                        print(f"❌ Please enter a number between 1 and {len(accounts)}")
                except (ValueError, EOFError, KeyboardInterrupt):
                    print("\n❌ Cancelled")
                    raise RuntimeError("No account selected")
    
    # If credentials_path is provided, skip straight to using it
    if credentials_path:
        if not email:
            raise RuntimeError("Email address is required when providing a credentials_path")
        path = os.path.expanduser(credentials_path)
        if not os.path.exists(path):
            raise RuntimeError(f"Credentials file not found: {path}")
        
        if not verbose:
            # Use carriage return for progress updates
            print(f"[1/4] 🔐 Adding credentials for {email}...", end='', flush=True)
            if not _add_to_wallet(email, path, verbose=False):
                print(f"\r❌ Failed to add credentials for {email}" + " " * 50)
                raise RuntimeError(f"Invalid or malformed credentials file: {path}")
            print(f"\r[2/4] 🔑 Logging in as {email}..." + " " * 30, end='', flush=True)
            client = create_gdrive_client(email, verbose=False, force_relogin=force_relogin)
            print(f"\r[3/4] 🔐 Checking for new inboxes..." + " " * 30, end='', flush=True)
            # Automatically create shortcuts for shared folders
            shortcut_results = client._create_shortcuts_for_shared_folders(verbose=False)
            
            # Build login message with inbox count
            login_msg = f"\r[4/4] ✅ Logged in as {client.my_email}"
            if shortcut_results['created'] > 0:
                login_msg += f" ({shortcut_results['created']} new inbox{'es' if shortcut_results['created'] != 1 else ''} added!)"
            print(login_msg + " " * 50)  # Extra spaces to clear the line
        else:
            print(f"🔐 Using provided credentials file: {path}")
            if not _add_to_wallet(email, path, verbose=verbose):
                raise RuntimeError(f"Invalid or malformed credentials file: {path}")
            print(f"✅ Added {email} to wallet")
            client = create_gdrive_client(email, verbose=verbose, force_relogin=force_relogin)
            # Automatically create shortcuts for shared folders
            shortcut_results = client._create_shortcuts_for_shared_folders(verbose=False)
            
            # Build login message with inbox count
            login_msg = f"✅ Logged in as {client.my_email}"
            if shortcut_results['created'] > 0:
                login_msg += f" ({shortcut_results['created']} new inbox{'es' if shortcut_results['created'] != 1 else ''} added!)"
            print(login_msg)
        
        return client
    
    # 1. Check if email is in wallet
    if _get_stored_credentials_path(email):
        if not verbose:
            # Use carriage return for progress updates
            import sys
            print(f"[1/3] 🔑 Logging in as {email}...", end='', flush=True)
            client = create_gdrive_client(email, verbose=False, force_relogin=force_relogin)
            print(f"\r[2/3] 🔐 Checking for new inboxes..." + " " * 30, end='', flush=True)
            # Automatically create shortcuts for shared folders
            shortcut_results = client._create_shortcuts_for_shared_folders(verbose=False)
            
            # Build login message with inbox count
            login_msg = f"\r[3/3] ✅ Logged in as {client.my_email}"
            if shortcut_results['created'] > 0:
                login_msg += f" ({shortcut_results['created']} new inbox{'es' if shortcut_results['created'] != 1 else ''} added!)"
            print(login_msg + " " * 50)  # Extra spaces to clear the line
        else:
            # Verbose mode - show all messages
            print(f"🔑 Found stored credentials for {email}")
            client = create_gdrive_client(email, verbose=verbose, force_relogin=force_relogin)
            # Automatically create shortcuts for shared folders
            shortcut_results = client._create_shortcuts_for_shared_folders(verbose=False)
            
            # Build login message with inbox count
            login_msg = f"✅ Logged in as {client.my_email}"
            if shortcut_results['created'] > 0:
                login_msg += f" ({shortcut_results['created']} new inbox{'es' if shortcut_results['created'] != 1 else ''} added!)"
            print(login_msg)
        
        return client
    
    # 2. Not in wallet - add new credentials
    # Check if we're in a Jupyter notebook
    try:
        from IPython import get_ipython
        if get_ipython() is not None:
            # We're in IPython/Jupyter - show the wizard
            from .wizard import wizard
            print(f"❌ No credentials found for {email}")
            print(f"Run syft_client.wizard() or print your client object to create credentials")
            return wizard()
    except ImportError:
        pass
    
    # If not in Jupyter or verbose=False, show minimal message
    if verbose:
        print(f"❌ No credentials found for {email} in wallet")
    
    # Check if we're in a CI/non-interactive environment
    is_ci = os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS') or not sys.stdin.isatty()
    if is_ci:
        raise RuntimeError(f"No credentials found for {email} and running in non-interactive mode (CI={os.environ.get('CI')}, GITHUB_ACTIONS={os.environ.get('GITHUB_ACTIONS')}). "
                         f"Please provide credentials or add them to the wallet first.")
    
    # Terminal fallback
    print("\n🔧 Let's set up Google Drive access for this account")
    print("Choose an option:")
    print("1. I have a credentials.json file")
    print("2. I need to create a new Google Cloud project")
    print("3. Exit")
    
    try:
        # Double-check we're not in CI before trying to read input
        if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
            print("❌ Cancelled")
            raise RuntimeError(f"Cannot prompt for input in CI environment")
        choice = input("\nYour choice [1-3]: ").strip()
        
        if choice == "1":
            # Existing flow - add credentials
            path = input("\nEnter path to credentials.json: ").strip()
            if not path:
                print("❌ No path provided")
                raise RuntimeError(f"No credentials available for {email}")
            
            # Expand path
            path = os.path.expanduser(path)
            
            if os.path.exists(path):
                _add_to_wallet(email, path, verbose=verbose)
                if verbose:
                    print(f"✅ Added {email} to wallet")
                client = create_gdrive_client(email, verbose=verbose)
                # Automatically create shortcuts for shared folders
                shortcut_results = client._create_shortcuts_for_shared_folders(verbose=False)
                
                # Build login message with inbox count
                login_msg = f"✅ Logged in as {client.my_email}"
                if shortcut_results['created'] > 0:
                    login_msg += f" ({shortcut_results['created']} new inbox{'es' if shortcut_results['created'] != 1 else ''} added!)"
                print(login_msg)
                
                return client
            else:
                print(f"❌ File not found: {path}")
                raise RuntimeError(f"Could not find credentials at {path}")
                
        elif choice == "2":
            # New wizard for creating project
            print("\n📋 Google Cloud Project Setup Wizard")
            print("=" * 50)
            print(f"\nWe'll set up a Google Cloud project for {email}")
            print("This is a one-time setup that takes about 5 minutes.\n")
            
            print("📝 Step 1: Create a Google Cloud Project")
            print("-" * 40)
            print(f"1. Open: https://console.cloud.google.com/projectcreate?authuser={email}")
            print("2. Enter a project name (e.g., 'syftbox-drive')")
            print("3. Click 'CREATE'")
            print("4. Wait for the project to be created")
            input("\nPress Enter when done...")
            
            print("\n📝 Step 2: Enable Google Drive API")
            print("-" * 40)
            print(f"1. Open: https://console.cloud.google.com/apis/library/drive.googleapis.com?authuser={email}")
            print("2. Click 'ENABLE'")
            print("3. Wait for it to enable")
            input("\nPress Enter when done...")
            
            print("\n📝 Step 3: Configure OAuth Consent Screen")
            print("-" * 40)
            print(f"1. Open: https://console.cloud.google.com/apis/credentials/consent?authuser={email}")
            print("2. Choose User Type:")
            print("   - If you have a Google Workspace domain: Choose 'Internal'")
            print("   - For personal Gmail accounts: Choose 'External'")
            print("3. Click 'CREATE'")
            print("\n4. Fill in the required fields:")
            print("   - App name: SyftBox Drive (or any name)")
            print("   - User support email: (select your email)")
            print("   - Developer contact: (your email)")
            print("5. Click 'SAVE AND CONTINUE'")
            print("\n6. On Scopes page: Click 'SAVE AND CONTINUE'")
            print("\n7. On Test users page:")
            print(f"   - Click 'ADD USERS'")
            print(f"   - Add: {email}")
            print("   - Click 'SAVE AND CONTINUE'")
            print("\n8. Review and click 'BACK TO DASHBOARD'")
            input("\nPress Enter when done...")
            
            print("\n📝 Step 4: Create OAuth 2.0 Credentials")
            print("-" * 40)
            print(f"1. Open: https://console.cloud.google.com/apis/credentials?authuser={email}")
            print("2. Click '+ CREATE CREDENTIALS' → 'OAuth client ID'")
            print("3. Application type: 'Desktop app'")
            print("4. Name: 'SyftBox Client' (or any name)")
            print("5. Click 'CREATE'")
            print("6. Click 'DOWNLOAD JSON' on the popup")
            print("7. Save the file as 'credentials.json'")
            input("\nPress Enter when done...")
            
            print("\n✅ Setup complete! Now let's add your credentials.")
            
            # Try common download locations
            common_paths = [
                "~/Downloads/credentials.json",
                "~/Downloads/client_secret*.json",
                "./credentials.json"
            ]
            
            found_path = None
            for p in common_paths:
                expanded = os.path.expanduser(p)
                import glob
                matches = glob.glob(expanded)
                if matches:
                    found_path = matches[0]
                    break
            
            if found_path:
                print(f"\n🔍 Found credentials at: {found_path}")
                use_it = input("Use this file? [Y/n]: ").strip().lower()
                if use_it in ['', 'y', 'yes']:
                    wallet.add_credentials(email, found_path, verbose=verbose)
                    if verbose:
                        print(f"✅ Added {email} to wallet")
                    client = create_gdrive_client(email, verbose=verbose)
                    # Automatically create shortcuts for shared folders
                    shortcut_results = client._create_shortcuts_for_shared_folders(verbose=False)
                    
                    # Build login message with inbox count
                    login_msg = f"✅ Logged in as {client.my_email}"
                    if shortcut_results['created'] > 0:
                        login_msg += f" ({shortcut_results['created']} new inbox{'es' if shortcut_results['created'] != 1 else ''} added!)"
                    print(login_msg)
                    
                    return client
            
            # Manual path entry
            path = input("\nEnter path to downloaded credentials.json: ").strip()
            if path:
                path = os.path.expanduser(path)
                if os.path.exists(path):
                    _add_to_wallet(email, path, verbose=verbose)
                    if verbose:
                        print(f"✅ Added {email} to wallet")
                    client = create_gdrive_client(email, verbose=verbose)
                    # Automatically create shortcuts for shared folders
                    shortcut_results = client._create_shortcuts_for_shared_folders(verbose=False)
                    
                    # Build login message with inbox count
                    login_msg = f"✅ Logged in as {client.my_email}"
                    if shortcut_results['created'] > 0:
                        login_msg += f" ({shortcut_results['created']} new inbox{'es' if shortcut_results['created'] != 1 else ''} added!)"
                    print(login_msg)
                    
                    return client
                else:
                    print(f"❌ File not found: {path}")
                    
        else:
            print("\n👋 Exiting...")
            raise RuntimeError(f"Setup cancelled")
            
    except (EOFError, KeyboardInterrupt):
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


def logout(email: Optional[str] = None, clear_tokens_only: bool = True):
    """
    Logout from an account (remove from wallet)
    
    Args:
        email: Email to logout from
        clear_tokens_only: Deprecated - only full removal is supported now
    """
    if not email:
        print("❌ Please specify an email to logout")
        return False
        
    if not clear_tokens_only:
        # Remove entire account
        return _remove_from_wallet(email)
    else:
        print("ℹ️  Token caching is disabled. Use logout(email, clear_tokens_only=False) to remove account from wallet.")
        return True