"""
Unified Google Drive client with multiple authentication methods
"""

import os
import json
import io
import tarfile
import tempfile
import shutil
import threading
import yaml
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Union

# Try importing Colab auth
def _is_colab():
    """Check if running in Google Colab"""
    try:
        import google.colab
        return True
    except ImportError:
        return False

try:
    from google.colab import auth as colab_auth
except ImportError:
    colab_auth = None

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

class GDriveUnifiedClient:
    """
    Unified Google Drive client supporting multiple authentication methods
    with high-level API for file operations and permissions
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, auth_method: str = "auto", credentials_file: str = "credentials.json", 
                 email: Optional[str] = None, verbose: bool = True, force_relogin: bool = False):
        """
        Initialize the unified client
        
        Args:
            auth_method: "auto", "colab", or "credentials"
            credentials_file: Path to credentials.json (for credentials method)
            email: Email address to authenticate as (uses wallet if provided)
            verbose: Whether to print status messages
            force_relogin: Force fresh authentication even if token exists
        """
        self.auth_method = auth_method
        self.credentials_file = credentials_file
        self.service = None
        self.authenticated = False
        self.my_email = None
        self.target_email = email
        self.verbose = verbose
        self.force_relogin = force_relogin
        self.local_syftbox_dir = None
        self._syftbox_folder_id = None  # Cache for SyftBoxTransportService folder ID
        self._folder_cache = {}  # General cache for folder paths to IDs
        self._friends_cache = None  # Cache for friends list
        self._friends_cache_time = None  # Timestamp for friends cache
        self.creds = None  # Store credentials for background threads
        self._sheets_service = None  # Cache for Google Sheets service
        self._sheet_cache = {}  # Cache for sheet lookups
        self._sheet_cache_time = {}  # Timestamps for sheet cache entries
        self._spreadsheet_info_cache = {}  # Cache for spreadsheet properties
        self._spreadsheet_info_cache_time = {}  # Timestamps for spreadsheet info cache
        self._metadata_cache = {}  # Cache for parsed message metadata
        self._path_cache = {}  # Cache for string paths
        self._dir_structure = set()  # Pre-created directories
        
    def __repr__(self) -> str:
        """Pretty representation of the client"""
        if not self.authenticated:
            return f"<GDriveUnifiedClient(not authenticated)>"
        
        # Get SyftBox info
        syftbox_info = "not created"
        syftbox_id = None
        try:
            # Use cached lookup
            syftbox_id = self._get_syftbox_folder_id()
            if syftbox_id:
                syftbox_info = "✓ created"
        except:
            pass
        
        
        auth_method = "wallet" if self.target_email else self.auth_method
        
        return (
            f"<GDriveUnifiedClient(\n"
            f"  email='{self.my_email}',\n"
            f"  auth_method='{auth_method}',\n"
            f"  syftbox={syftbox_info}\n"
            f")>"
        )
    
    def _repr_html_(self) -> str:
        """HTML representation for Jupyter notebooks"""
        if not self.authenticated:
            return """
            <div style="border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px; background-color: #f9f9f9;">
                <h3 style="margin-top: 0;">🔐 GDriveUnifiedClient</h3>
                <p style="color: #666;"><em>Not authenticated</em></p>
            </div>
            """
        
        # Get SyftBox info
        syftbox_id = None
        syftbox_status = "❌ Not created"
        try:
            # Use cached lookup
            syftbox_id = self._get_syftbox_folder_id()
            if syftbox_id:
                syftbox_status = "✅ Created"
        except:
            pass
        
        
        auth_method = "wallet" if self.target_email else self.auth_method
        
        # Build HTML
        html = f"""
        <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; background-color: #f9f9f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <h3 style="margin-top: 0; color: #333;">📁 Google Drive Client</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <tr>
                    <td style="padding: 5px 10px 5px 0; font-weight: bold; color: #555;">Email:</td>
                    <td style="padding: 5px;">{self.my_email}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 10px 5px 0; font-weight: bold; color: #555;">Auth Method:</td>
                    <td style="padding: 5px;">{auth_method}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 10px 5px 0; font-weight: bold; color: #555;">SyftBox:</td>
                    <td style="padding: 5px;">{syftbox_status}</td>
                </tr>
        """
        
        if syftbox_id:
            drive_url = f"https://drive.google.com/drive/folders/{syftbox_id}"
            html += f"""
                <tr>
                    <td style="padding: 5px 10px 5px 0; font-weight: bold; color: #555;">Drive Folder:</td>
                    <td style="padding: 5px;">
                        <a href="{drive_url}" target="_blank" style="color: #1a73e8; text-decoration: none;">
                            🔗 Open in Google Drive
                        </a>
                    </td>
                </tr>
            """
        
        # Add local SyftBox directory info
        if self.local_syftbox_dir:
            html += f"""
                <tr>
                    <td style="padding: 5px 10px 5px 0; font-weight: bold; color: #555;">Local Directory:</td>
                    <td style="padding: 5px;">{self.local_syftbox_dir}</td>
                </tr>
            """
        
        html += """
            </table>
        </div>"""
        
        return html
        
    def authenticate(self, known_email: Optional[str] = None) -> bool:
        """
        Authenticate using the appropriate method
        
        Returns:
            bool: True if authentication successful
        """
        # If auth_method is explicitly set to colab, use Colab auth
        if self.auth_method == "colab":
            if not _is_colab():
                if self.verbose:
                    print("❌ Not running in Google Colab")
                return False
            return self._auth_colab()
        
        # If email is provided and not using Colab, try to use stored credentials first
        if self.target_email and self.auth_method != "colab":
            # Import here to avoid circular dependency
            from .auth import _get_stored_credentials_path
            wallet_creds = _get_stored_credentials_path(self.target_email)
            if wallet_creds:
                self.credentials_file = wallet_creds
                return self._auth_credentials()
            else:
                if self.verbose:
                    if self.verbose:
                        print(f"❌ No stored credentials found for {self.target_email}")
                        print(f"   Use login('{self.target_email}', 'path/to/credentials.json')")
                return False
        
        if self.auth_method == "auto":
            # Auto-detect best method
            if _is_colab():
                return self._auth_colab()
            elif os.path.exists(self.credentials_file):
                return self._auth_credentials()
            else:
                if self.verbose:
                    if self.verbose:
                        print("❌ No authentication method available")
                        print("   - Not in Google Colab")
                        print(f"   - No {self.credentials_file} found")
                return False
                
        elif self.auth_method == "credentials":
            return self._auth_credentials()
            
        else:
            if self.verbose:
                if self.verbose:
                    print(f"❌ Unknown auth method: {self.auth_method}")
            return False
    
    def _auth_colab(self) -> bool:
        """Authenticate using Google Colab"""
        try:
            if self.verbose:
                if self.verbose:
                    print("🔐 Authenticating with Google Colab...")
            colab_auth.authenticate_user()
            self.service = build('drive', 'v3')
            self.authenticated = True
            self._get_my_email()
            if self.verbose:
                if self.verbose:
                    print("✅ Authenticated via Google Colab")
            return True
        except Exception as e:
            if self.verbose:
                if self.verbose:
                    print(f"❌ Colab authentication failed: {e}")
            return False
    
    def _auth_credentials(self) -> bool:
        """Authenticate using credentials.json with token caching"""
        try:
            if self.verbose:
                if self.target_email:
                    if self.verbose:
                        print(f"🔐 Authenticating as {self.target_email}...")
                else:
                    if self.verbose:
                        print("🔐 Authenticating with credentials.json...")

            creds = None
            
            # Check if force_relogin is set
            if self.force_relogin and self.verbose:
                if self.verbose:
                    print("🔄 Force relogin requested - ignoring cached token")
            
            # First, try to load cached token if we have a target email and not forcing relogin
            if self.target_email and not self.force_relogin:
                from .auth import _get_stored_token_path, _save_token, _update_token_timestamp
                token_path = _get_stored_token_path(self.target_email)
                
                if token_path and os.path.exists(token_path):
                    try:
                        # Check token age from filename
                        from pathlib import Path
                        from datetime import datetime
                        
                        filename = Path(token_path).name
                        timestamp_str = filename.replace("token_", "").replace(".json", "")
                        token_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        token_age_minutes = (datetime.now() - token_time).total_seconds() / 60
                        
                        with open(token_path, 'r') as token:
                            token_data = json.load(token)
                        creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
                        
                        # Skip refresh check if token is less than 59 minutes old
                        if token_age_minutes < 59:
                            if self.verbose:
                                if self.verbose:
                                    print(f"✅ Using cached authentication token (created {int(token_age_minutes)} minutes ago)")
                            self.service = build('drive', 'v3', credentials=creds)
                            self.creds = creds  # Store for background threads
                            self.authenticated = True
                            self._get_my_email(known_email=self.target_email)
                            # Don't update timestamp for very recent tokens
                            if token_age_minutes > 30:
                                _update_token_timestamp(token_path)
                            return True
                        
                        # For older tokens, check if they need refresh
                        if creds and creds.expired and creds.refresh_token:
                            if self.verbose:
                                if self.verbose:
                                    print("🔄 Refreshing expired token...")
                            creds.refresh(Request())
                            # Save the refreshed token as a new file
                            _save_token(self.target_email, {
                                'type': 'authorized_user',
                                'client_id': creds.client_id,
                                'client_secret': creds.client_secret,
                                'refresh_token': creds.refresh_token,
                                'token': creds.token,
                                'token_uri': creds.token_uri,
                                'scopes': creds.scopes
                            })
                        
                        if creds and creds.valid:
                            if self.verbose:
                                if self.verbose:
                                    print("✅ Using cached authentication token")
                            self.service = build('drive', 'v3', credentials=creds)
                            self.creds = creds  # Store for background threads
                            self.authenticated = True
                            self._get_my_email()
                            # Update the token timestamp since it was successfully used
                            _update_token_timestamp(token_path)
                            return True
                    except Exception as e:
                        if self.verbose:
                            if self.verbose:
                                print(f"⚠️  Could not use cached token: {e}")
                        creds = None
            
            # If no valid cached token, do the full OAuth flow
            if not os.path.exists(self.credentials_file):
                if self.verbose:
                    if self.verbose:
                        print(f"❌ {self.credentials_file} not found")
                return False
                
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file, self.SCOPES)
            
            # Run the OAuth flow
            if self.verbose:
                if self.verbose:
                    print(f"\n🌐 Opening browser for authentication...")
                    if self.target_email:
                        print(f"   📧 Please select or sign in as: {self.target_email}")
                    print(f"   ⚠️  Make sure to choose the correct account!")
            
            # Configure messages based on verbose setting
            if self.verbose:
                auth_msg = 'Please sign in with the correct Google account'
                success_msg = 'The auth flow is complete; you may close this window.'
            else:
                # Use minimal but valid messages when not verbose
                auth_msg = None
                success_msg = 'Authentication complete. You can close this window.'
            
            creds = flow.run_local_server(
                port=0,
                authorization_prompt_message=auth_msg,
                success_message=success_msg
            )
            
            self.service = build('drive', 'v3', credentials=creds)
            self.creds = creds  # Store for background threads
            self.authenticated = True
            self._get_my_email()
            
            # Save the token for future use if we have a target email
            if self.target_email and creds:
                try:
                    _save_token(self.target_email, {
                        'type': 'authorized_user',
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'refresh_token': creds.refresh_token,
                        'token': creds.token,
                        'token_uri': creds.token_uri,
                        'scopes': creds.scopes
                    })
                    if self.verbose:
                        print("💾 Saved authentication token for future use")
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️  Could not save token: {e}")
            
            # Verify we authenticated as the expected user
            if self.target_email and self.my_email != self.target_email:
                if self.verbose:
                    print(f"⚠️  Warning: Authenticated as {self.my_email}, expected {self.target_email}")
            
            if self.verbose:
                print(f"✅ Authenticated via credentials.json")
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Credentials authentication failed: {e}")
            return False
    
    def _ensure_authenticated(self):
        """Ensure client is authenticated before operations"""
        # print("ENSUREAUTH-1 " + str(time.time()))
        if not self.authenticated:
            raise RuntimeError("Client not authenticated. Call authenticate() first.")
        # print("ENSUREAUTH-2 " + str(time.time()))
    
    def _get_sheets_service(self):
        """Get or create cached Google Sheets service"""
        # print("GETSHEETS-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("GETSHEETS-2 " + str(time.time()))
        if self._sheets_service is None:
            # print("GETSHEETS-3 " + str(time.time()))
            self._sheets_service = build('sheets', 'v4', credentials=self.creds)
            # print("GETSHEETS-4 " + str(time.time()))
        # print("GETSHEETS-5 " + str(time.time()))
        return self._sheets_service
    
    def _get_syftbox_folder_id(self, use_cache: bool = True) -> Optional[str]:
        """
        Get the SyftBoxTransportService folder ID, using cache if available
        
        Args:
            use_cache: Whether to use cached value if available
            
        Returns:
            Folder ID if found, None otherwise
        """
        # print("GETFOLDERID-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("GETFOLDERID-2 " + str(time.time()))
        
        # Return cached value if available and cache is enabled
        if use_cache and self._syftbox_folder_id:
            # print("GETFOLDERID-3 " + str(time.time()))
            return self._syftbox_folder_id
        
        try:
            # Search for SyftBoxTransportService folder
            # print("GETFOLDERID-4 " + str(time.time()))
            results = self.service.files().list(
                q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            # print("GETFOLDERID-5 " + str(time.time()))
            
            syftbox_folders = results.get('files', [])
            
            if syftbox_folders:
                # Cache and return the first folder ID
                self._syftbox_folder_id = syftbox_folders[0]['id']
                # print("GETFOLDERID-6 " + str(time.time()))
                return self._syftbox_folder_id
            
            # Clear cache if folder not found
            self._syftbox_folder_id = None
            # print("GETFOLDERID-7 " + str(time.time()))
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error getting SyftBox folder ID: {e}")
            return None
    
    def _clear_syftbox_cache(self):
        """Clear the cached SyftBox folder ID"""
        self._syftbox_folder_id = None
    
    def _clear_sheet_cache(self):
        """Clear the cached sheet lookups"""
        self._sheet_cache = {}
        self._sheet_cache_time = {}
        self._spreadsheet_info_cache = {}
        self._spreadsheet_info_cache_time = {}
    
    def _get_folder_id(self, folder_name: str, parent_id: str = 'root', use_cache: bool = True) -> Optional[str]:
        """
        Get folder ID by name and parent, using cache if available
        
        Args:
            folder_name: Name of the folder
            parent_id: Parent folder ID (default: 'root')
            use_cache: Whether to use cached value if available
            
        Returns:
            Folder ID if found, None otherwise
        """
        self._ensure_authenticated()
        
        # Create cache key from folder path
        cache_key = f"{parent_id}/{folder_name}"
        
        # Return cached value if available and cache is enabled
        if use_cache and cache_key in self._folder_cache:
            return self._folder_cache[cache_key]
        
        try:
            # Query for the folder
            results = self.service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                # Cache and return the first folder ID
                folder_id = folders[0]['id']
                self._folder_cache[cache_key] = folder_id
                return folder_id
            
            # Clear cache entry if folder not found
            if cache_key in self._folder_cache:
                del self._folder_cache[cache_key]
            return None
            
        except Exception as e:
            # On error, invalidate cache entry
            if cache_key in self._folder_cache:
                del self._folder_cache[cache_key]
            if self.verbose:
                print(f"❌ Error getting folder ID for {folder_name}: {e}")
            return None
    
    def _invalidate_folder_cache(self, folder_name: Optional[str] = None, parent_id: Optional[str] = None):
        """
        Invalidate folder cache entries
        
        Args:
            folder_name: Specific folder name to invalidate (optional)
            parent_id: Specific parent ID to invalidate (optional)
            If both are None, clears entire cache
        """
        if folder_name is None and parent_id is None:
            # Clear entire cache
            self._folder_cache.clear()
        elif folder_name and parent_id:
            # Clear specific entry
            cache_key = f"{parent_id}/{folder_name}"
            if cache_key in self._folder_cache:
                del self._folder_cache[cache_key]
        elif parent_id:
            # Clear all entries under a parent
            keys_to_delete = [k for k in self._folder_cache.keys() if k.startswith(f"{parent_id}/")]
            for key in keys_to_delete:
                del self._folder_cache[key]
    
    def _set_folder_cache(self, folder_name: str, folder_id: str, parent_id: str = 'root'):
        """
        Set a folder cache entry
        
        Args:
            folder_name: Name of the folder
            folder_id: ID of the folder
            parent_id: Parent folder ID (default: 'root')
        """
        cache_key = f"{parent_id}/{folder_name}"
        self._folder_cache[cache_key] = folder_id
    
    def _invalidate_friends_cache(self):
        """
        Invalidate the friends cache to force a refresh on next access
        """
        self._friends_cache = None
        self._friends_cache_time = None
    
    def reset_credentials(self):
        """
        Clear all cached credentials to force re-authentication with new scopes
        """
        if not self.my_email:
            print("❌ Not authenticated - no credentials to reset")
            return False
        
        try:
            # Import the auth module functions
            from .auth import _get_account_dir
            
            # Get the account directory
            account_dir = _get_account_dir(self.my_email)
            
            if account_dir.exists():
                # Remove all token files
                token_count = 0
                for token_file in account_dir.glob("token_*.json"):
                    try:
                        token_file.unlink()
                        token_count += 1
                    except:
                        pass
                
                print(f"🗑️  Cleared {token_count} cached token(s) for {self.my_email}")
                print(f"📝 Please re-authenticate to get new credentials with Sheets access:")
                print(f"   client = login('{self.my_email}', force_relogin=True)")
                
                # Clear the current authentication
                self.authenticated = False
                self.service = None
                self.creds = None
                
                return True
            else:
                print(f"📁 No credentials found for {self.my_email}")
                return False
                
        except Exception as e:
            print(f"❌ Error resetting credentials: {e}")
            return False
    
    def _archive_message_async(self, msg_file_id: str, archive_id: str, inbox_folder_id: str, msg_id: str, archive_name: str):
        """
        Archive a message in a background thread
        
        Args:
            msg_file_id: File ID of the message to archive
            archive_id: ID of the archive folder
            inbox_folder_id: ID of the inbox folder (to remove from)
            msg_id: Message ID for logging
            archive_name: Archive folder name for logging
        """
        try:
            # Note: We need to create a new service instance for thread safety
            # The Google API client is not thread-safe
            if hasattr(self, 'creds') and self.creds:
                from googleapiclient.discovery import build
                service = build('drive', 'v3', credentials=self.creds)
                
                result = service.files().update(
                    fileId=msg_file_id,
                    addParents=archive_id,
                    removeParents=inbox_folder_id,
                    fields='id, parents',
                    supportsAllDrives=True
                ).execute()
                
                if self.verbose:
                    print(f"   ✅ [Background] Archived {msg_id} to {archive_name}")
            else:
                if self.verbose:
                    print(f"   ⚠️  [Background] Could not archive {msg_id} - no credentials")
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  [Background] Failed to archive {msg_id}: {str(e)[:100]}")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        friends_cache_age = None
        if self._friends_cache_time:
            friends_cache_age = int(time.time() - self._friends_cache_time)
        
        return {
            'folder_cache_entries': len(self._folder_cache),
            'syftbox_cached': 1 if self._syftbox_folder_id else 0,
            'friends_cached': len(self._friends_cache) if self._friends_cache else 0,
            'friends_cache_age_seconds': friends_cache_age,
            'total_cached_items': len(self._folder_cache) + (1 if self._syftbox_folder_id else 0) + (len(self._friends_cache) if self._friends_cache else 0)
        }
    
    def _get_my_email(self, known_email: Optional[str] = None):
        """Get the authenticated user's email address"""
        if known_email:
            self.my_email = known_email
            return

        try:
            about = self.service.about().get(fields="user(emailAddress)").execute()
            self.my_email = about['user']['emailAddress']
            if self.verbose:
                print(f"👤 Authenticated as: {self.my_email}")
            
            # Create local SyftBox directory after successful authentication
            self._create_local_syftbox_directory()
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Could not get email address: {e}")
            self.my_email = None
    
    def _create_local_syftbox_directory(self):
        """Create the local SyftBox directory structure"""
        if not self.my_email:
            return
            
        # Create ~/SyftBox_{email} directory
        home_dir = Path.home()
        syftbox_dir = home_dir / f"SyftBox_{self.my_email}"
        
        if not syftbox_dir.exists():
            try:
                syftbox_dir.mkdir(exist_ok=True)
                if self.verbose:
                    print(f"📁 Created local SyftBox directory: {syftbox_dir}")
                
                # Create subdirectories
                subdirs = ["datasites", "apps"]
                for subdir in subdirs:
                    (syftbox_dir / subdir).mkdir(exist_ok=True)
                    
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Could not create SyftBox directory: {e}")
        else:
            if self.verbose:
                print(f"📁 Using existing SyftBox directory: {syftbox_dir}")
                
        # Store the path for later use
        self.local_syftbox_dir = syftbox_dir
    
    def get_syftbox_directory(self) -> Optional[Path]:
        """Get the local SyftBox directory path"""
        # print("GETSYFTBOXDIR-1 " + str(time.time()))
        if self.local_syftbox_dir:
            # print("GETSYFTBOXDIR-2 " + str(time.time()))
            return self.local_syftbox_dir
        elif self.my_email:
            # Calculate the path even if not created yet
            # print("GETSYFTBOXDIR-3 " + str(time.time()))
            return Path.home() / f"SyftBox_{self.my_email}"
        # print("GETSYFTBOXDIR-4 " + str(time.time()))
        return None
    
    def resolve_syft_path(self, path: str) -> str:
        """
        Resolve a syft:// URL to a full file path
        
        Supports:
        - syft://filename.txt -> /path/to/SyftBox_email/datasites/filename.txt
        - syft://folder/filename.txt -> /path/to/SyftBox_email/datasites/folder/filename.txt
        - Regular paths are returned unchanged
        
        Args:
            path: Path that may start with syft://
            
        Returns:
            Resolved full path
        """
        if not path.startswith("syft://"):
            # Not a syft URL, return as-is
            return path
        
        # Get SyftBox directory
        syftbox_dir = self.get_syftbox_directory()
        if not syftbox_dir:
            raise ValueError("Could not determine SyftBox directory")
        
        # Extract the relative path after syft://
        relative_path = path[7:]  # Remove "syft://"
        
        # Build the full path (always in datasites)
        full_path = syftbox_dir / "datasites" / relative_path
        
        return str(full_path)
    
    # ========== File Operations ==========
    
    def _create_folder(self, name: str, parent_id: str = 'root') -> Optional[str]:
        """
        Create a folder
        
        Args:
            name: Folder name
            parent_id: Parent folder ID (default: root)
            
        Returns:
            Folder ID if successful, None otherwise
        """
        self._ensure_authenticated()
        
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            if folder_id:
                # Cache the newly created folder
                self._set_folder_cache(name, folder_id, parent_id)
            if self.verbose:
                print(f"✅ Created folder '{name}' (ID: {folder_id})")
            return folder_id
            
        except HttpError as e:
            if self.verbose:
                print(f"❌ Error creating folder: {e}")
            return None
    
    def _folder_exists(self, name: str, parent_id: str = 'root') -> bool:
        """
        Check if a folder exists
        
        Args:
            name: Folder name to check
            parent_id: Parent folder ID (default: root)
            
        Returns:
            True if folder exists, False otherwise
        """
        self._ensure_authenticated()
        
        try:
            results = self.service.files().list(
                q=f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false",
                fields="files(id,name)"
            ).execute()
            
            return len(results.get('files', [])) > 0
            
        except HttpError as e:
            if self.verbose:
                print(f"❌ Error checking folder existence: {e}")
            return False
    
    def _share_folder_with_email(self, folder_id: str, email: str) -> bool:
        """
        Share a folder with a specific email address
        
        Args:
            folder_id: Google Drive folder ID to share
            email: Email address to share with
            
        Returns:
            True if sharing successful, False otherwise
        """
        self._ensure_authenticated()
        
        try:
            permission = {
                'type': 'user',
                'role': 'writer',
                'emailAddress': email
            }
            
            self.service.files().permissions().create(
                fileId=folder_id,
                body=permission
            ).execute()
            
            if self.verbose:
                print(f"✅ Shared folder {folder_id} with {email}")
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error sharing folder: {e}")
            return False
    
    def _upload_file(self, local_path: str, name: str = None, 
                    parent_id: str = 'root', mimetype: str = 'text/plain') -> Optional[str]:
        """
        Upload a file
        
        Args:
            local_path: Path to local file
            name: Name in Drive (default: use local filename)
            parent_id: Parent folder ID (default: root)
            mimetype: MIME type of file
            
        Returns:
            File ID if successful, None otherwise
        """
        
        self._ensure_authenticated()
        
        if not os.path.exists(local_path):
            print(f"❌ Local file not found: {local_path}")
            return None
        
        if name is None:
            name = os.path.basename(local_path)
        
        try:
            file_metadata = {
                'name': name,
                'parents': [parent_id]
            }
            
            media = MediaIoBaseUpload(
                io.FileIO(local_path, 'rb'),
                mimetype=mimetype,
                resumable=True  # Enable resumable uploads for large files
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            if self.verbose:
                print(f"✅ Uploaded '{name}' (ID: {file_id})")
            return file_id
            print("8")
        except HttpError as e:
            print(f"❌ Error uploading file: {e}")
            return None
    
    def _upload_folder_as_archive(self, local_folder_path: str, parent_id: str, folder_name: str = None) -> Optional[str]:
        """
        Upload a folder as a compressed archive to Google Drive
        
        Args:
            local_folder_path: Path to local folder
            parent_id: Parent folder ID in Google Drive
            folder_name: Name for the archive in Drive (default: use local folder name + .tar.gz)
            
        Returns:
            File ID if successful, None otherwise
        """
        self._ensure_authenticated()
        
        if not os.path.isdir(local_folder_path):
            print(f"❌ Not a directory: {local_folder_path}")
            return None
            
        if folder_name is None:
            folder_name = os.path.basename(local_folder_path)
        
        try:
            # Create a temporary tar.gz file
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                
            # Create the tar.gz archive
            if self.verbose:
                print(f"   📦 Creating archive for {folder_name}...")
            
            with tarfile.open(tmp_path, 'w:gz') as tar:
                # Add the entire folder to the archive
                tar.add(local_folder_path, arcname=folder_name)
            
            # Get file size for progress reporting
            file_size = os.path.getsize(tmp_path)
            if self.verbose:
                size_mb = file_size / (1024 * 1024)
                print(f"   📦 Archive size: {size_mb:.1f} MB")
            
            # Upload the archive as a single file
            archive_name = f"{folder_name}.tar.gz"
            if self.verbose:
                print(f"   📤 Uploading {archive_name}...")
            
            file_id = self._upload_file(
                local_path=tmp_path,
                name=archive_name,
                parent_id=parent_id,
                mimetype='application/gzip'
            )
            
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            if file_id and self.verbose:
                print(f"   ✅ Uploaded folder as {archive_name}")
            
            return file_id
            
        except Exception as e:
            print(f"❌ Error creating/uploading archive: {e}")
            # Clean up temporary file on error
            try:
                if 'tmp_path' in locals():
                    os.unlink(tmp_path)
            except:
                pass
            return None
    def _download_archive_and_extract(self, file_id: str, local_parent: str, extract_name: str = None) -> bool:
        """
        Download a tar.gz archive and extract it
        
        Args:
            file_id: Google Drive file ID of the archive
            local_parent: Parent directory to extract into
            extract_name: Name for the extracted folder (optional)
            
        Returns:
            True if successful
        """
        self._ensure_authenticated()
        
        try:
            # Create a temporary file for the archive
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            # Download the archive file
            if self.verbose:
                print(f"      📥 Downloading tar.gz file...")
            
            request = self.service.files().get_media(fileId=file_id)
            with io.FileIO(tmp_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status and self.verbose:
                        print(f"      📊 Download progress: {int(status.progress() * 100)}%")
            
            # Extract the archive
            if self.verbose:
                print(f"      📦 Extracting files...")
            
            with tarfile.open(tmp_path, 'r:gz') as tar:
                # If extract_name is provided, extract to that specific folder
                if extract_name:
                    # Get the first member to find the archive's root folder
                    members = tar.getmembers()
                    if members:
                        # Find the common prefix (root folder in archive)
                        root_folder = members[0].name.split('/')[0]
                        
                        # Extract to a temporary location first
                        with tempfile.TemporaryDirectory() as temp_dir:
                            tar.extractall(temp_dir)
                            
                            # Move the extracted folder to the desired location with new name
                            src_path = os.path.join(temp_dir, root_folder)
                            dst_path = os.path.join(local_parent, extract_name)
                            
                            # Remove destination if it exists
                            if os.path.exists(dst_path):
                                shutil.rmtree(dst_path)
                            
                            # Move to final location
                            shutil.move(src_path, dst_path)
                else:
                    # Extract directly to parent directory
                    tar.extractall(local_parent)
            
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            if self.verbose:
                print(f"      ✅ Extraction complete")
            
            return True
            
        except Exception as e:
            print(f"❌ Error downloading/extracting archive: {e}")
            # Clean up temporary file on error
            try:
                if 'tmp_path' in locals():
                    os.unlink(tmp_path)
            except:
                pass
            return False
    
    def _download_file(self, file_id: str, local_path: str) -> bool:
        """
        Download a file
        
        Args:
            file_id: Google Drive file ID
            local_path: Where to save the file
            
        Returns:
            True if successful
        """
        self._ensure_authenticated()
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            with io.FileIO(local_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status and self.verbose:
                        print(f"Download progress: {int(status.progress() * 100)}%")
            if self.verbose:
                print(f"✅ Downloaded to '{local_path}'")
            return True
            
        except HttpError as e:
            print(f"❌ Error downloading file: {e}")
            return False
    
    def _get_permissions(self, file_id: str) -> List[Dict]:
        """
        Get all permissions for a file/folder
        
        Args:
            file_id: Google Drive file/folder ID
            
        Returns:
            List of permission dictionaries
        """
        self._ensure_authenticated()
        
        try:
            permissions = self.service.permissions().list(
                fileId=file_id,
                fields="permissions(id, type, role, emailAddress)"
            ).execute()
            
            return permissions.get('permissions', [])
            
        except HttpError as e:
            print(f"❌ Error getting permissions: {e}")
            return []
    
    def _add_permission(self, file_id: str, email: str, role: str = 'reader', verbose: bool = True) -> bool:
        """
        Add permission for a user
        
        Args:
            file_id: Google Drive file/folder ID
            email: User's email address
            role: 'reader', 'writer', or 'owner'
            verbose: Whether to print status messages (default: True)
            
        Returns:
            True if successful
        """
        # print("ADDPERM-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("ADDPERM-2 " + str(time.time()))
        
        if role not in ['reader', 'writer', 'owner']:
            print(f"❌ Invalid role: {role}")
            return False
        
        try:
            # print("ADDPERM-3 " + str(time.time()))
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            
            # print("ADDPERM-4 " + str(time.time()))
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                sendNotificationEmail=False
            ).execute()
            # print("ADDPERM-5 " + str(time.time()))
            
            if verbose:
                print(f"✅ Added {role} permission for {email}")
            # print("ADDPERM-6 " + str(time.time()))
            return True
            
        except HttpError as e:
            print(f"❌ Error adding permission: {e}")
            return False
    
    def delete_syftbox(self) -> bool:
        """
        Delete the SyftBoxTransportService folder and all its contents
        
        Returns:
            True if successful
        """
        self._ensure_authenticated()
        
        if self.verbose:
            print("🗑️  Deleting SyftBoxTransportService...")
        
        try:
            # Get folder ID using cache
            folder_id = self._get_syftbox_folder_id()
            
            if not folder_id:
                if self.verbose:
                    print("📁 No SyftBoxTransportService folder found to delete")
                return True
            
            if self.verbose:
                print(f"🗑️  Deleting SyftBoxTransportService (ID: {folder_id})...")
            
            try:
                self.service.files().delete(fileId=folder_id).execute()
            
                # Clear the cache after successful deletion
                self._clear_syftbox_cache()
                # Also invalidate all folders under SyftBox
                self._invalidate_folder_cache(parent_id=folder_id)
                
                if self.verbose:
                    print(f"   ✅ Deleted successfully")
                    print(f"\n✅ Delete complete! Deleted SyftBoxTransportService folder")
                return True
                
            except HttpError as e:
                if self.verbose:
                    print(f"   ❌ Error deleting: {e}")
                return False
                
        except HttpError as e:
            if self.verbose:
                print(f"❌ Error during delete: {e}")
            return False
    
    def reset_syftbox(self) -> Optional[str]:
        """
        Reset SyftBoxTransportService by deleting and recreating it
        
        Returns:
            SyftBoxTransportService folder ID if successful, None otherwise
        """
        self._ensure_authenticated()
        
        if self.verbose:
            print("🔄 Resetting SyftBoxTransportService...")
        
        # First delete existing SyftBox
        self.delete_syftbox()
        
        # Then create a new one — skip existence check since we just deleted it
        folder_id = self.setup_syftbox(skip_syftbox_existence_check=True)
        
        # Always print success message for reset
        if folder_id:
            print("✅ SyftBoxTransportService has been reset (deleted and recreated)")
        
        return folder_id
    
    def reset_credentials(self) -> bool:
        """
        Delete stored credentials (credentials.json)
        
        Returns:
            True if any files were deleted
        """
        print("🗑️  Resetting credentials...")
        
        deleted_files = []
        
        # If using wallet (email-based auth), don't delete wallet files
        if self.target_email:
            print("ℹ️  Using wallet-based authentication. No local files to delete.")
            # Clear current authentication
            if self.authenticated:
                self.service = None
                self.authenticated = False
                print("🔓 Cleared current authentication")
            return True
        else:
            # Delete credentials.json
            if os.path.exists(self.credentials_file):
                try:
                    os.remove(self.credentials_file)
                    deleted_files.append(self.credentials_file)
                    print(f"🗑️  Deleted {self.credentials_file}")
                except Exception as e:
                    print(f"❌ Error deleting {self.credentials_file}: {e}")
        
        # Clear current authentication
        if self.authenticated:
            self.service = None
            self.authenticated = False
            print("🔓 Cleared current authentication")
        
        if deleted_files:
            print(f"\n✅ Reset credentials complete! Deleted {len(deleted_files)} file(s)")
            return True
        else:
            print("📁 No credential files found to delete")
            return False
    
    def setup_syftbox(self, skip_syftbox_existence_check: bool = False) -> Optional[str]:
        """
        Set up SyftBoxTransportService folder structure (creates only if doesn't exist)
        
        Returns:
            SyftBoxTransportService folder ID if successful, None otherwise
        """
        self._ensure_authenticated()
        
        try:
            if not skip_syftbox_existence_check:
                # Try to get folder ID from cache first
                syftbox_id = self._get_syftbox_folder_id()
                
                if syftbox_id:
                    # Folder already exists
                    if self.verbose:
                        print(f"✅ SyftBoxTransportService folder already exists (ID: {syftbox_id})")
                        print(f"🔗 Open in Google Drive: https://drive.google.com/drive/folders/{syftbox_id}")
                    return syftbox_id
                
                # Create SyftBoxTransportService folder
                if self.verbose:
                    print("🚀 Creating SyftBoxTransportService folder...\n")
            
            syftbox_id = self._create_folder("SyftBoxTransportService")
            if not syftbox_id:
                if self.verbose:
                    print("❌ Failed to create SyftBoxTransportService folder")
                return None
            
            # Cache the folder ID
            self._syftbox_folder_id = syftbox_id
            
            if self.verbose:
                print(f"\n✅ SyftBoxTransportService setup complete!")
                print(f"🔗 Open in Google Drive: https://drive.google.com/drive/folders/{syftbox_id}")
            
            return syftbox_id
            
        except HttpError as e:
            if self.verbose:
                print(f"❌ Error setting up SyftBoxTransportService: {e}")
            return None
    
    def _setup_communication_channel(self, their_email: str, my_email: str = None, verbose: bool = False) -> Optional[Dict[str, str]]:
        """
        Set up unidirectional communication channel from me to them
        
        Args:
            their_email: Receiver's email address
            my_email: Sender's email address (optional, defaults to authenticated user)
            verbose: Whether to print progress messages (default: False)
            
        Returns:
            Dictionary with folder IDs if successful, None otherwise
        """
        self._ensure_authenticated()
        
        # Use authenticated user's email if not provided
        if my_email is None:
            if self.my_email is None:
                if verbose:
                    print("❌ Could not determine sender email address")
                return None
            my_email = self.my_email
        
        # Validate not messaging yourself
        if my_email.lower() == their_email.lower():
            if verbose:
                print(f"❌ Cannot create channel to yourself ({my_email})")
                print("   Communication channels must be between different users")
            return None
        
        try:
            # First ensure SyftBox exists
            syftbox_id = self.setup_syftbox()
            if not syftbox_id:
                return None
            
            
            # Create flat folder names with syft_ prefix
            pending_name = f"syft_{my_email}_to_{their_email}_pending"
            outbox_inbox_name = f"syft_{my_email}_to_{their_email}_outbox_inbox"
            
            folder_ids = {
                'sender': my_email,
                'receiver': their_email,
                'syftbox_id': syftbox_id
            }
            
            # Create/check pending folder (private to sender)
            pending_id = self._get_folder_id(pending_name, parent_id=syftbox_id)
            
            if pending_id:
                folder_ids['pending'] = pending_id
                if verbose:
                    print(f"✅ Pending folder already exists: {pending_name}")
            else:
                pending_id = self._create_folder(pending_name, parent_id=syftbox_id)
                if pending_id:
                    folder_ids['pending'] = pending_id
                    # Cache the newly created folder
                    self._set_folder_cache(pending_name, pending_id, parent_id=syftbox_id)
                    if verbose:
                        print(f"📁 Created pending folder: {pending_name}")
                        print(f"   ⏳ For preparing messages (private)")
            
            # Create/check outbox_inbox folder (shared with receiver)
            outbox_id = self._get_folder_id(outbox_inbox_name, parent_id=syftbox_id)
            
            if outbox_id:
                folder_ids['outbox_inbox'] = outbox_id
                created = False
                if verbose:
                    print(f"✅ Outbox/Inbox folder already exists: {outbox_inbox_name}")
            else:
                outbox_id = self._create_folder(outbox_inbox_name, parent_id=syftbox_id)
                if outbox_id:
                    folder_ids['outbox_inbox'] = outbox_id
                    # Cache the newly created folder
                    self._set_folder_cache(outbox_inbox_name, outbox_id, parent_id=syftbox_id)
                    created = True
                    if verbose:
                        print(f"📁 Created outbox/inbox folder: {outbox_inbox_name}")
                        print(f"   📬 For active communication (shared)")
            
            # Grant receiver write access to outbox_inbox
            if outbox_id:
                try:
                    permissions = self._get_permissions(outbox_id)
                    has_permission = any(
                        p.get('emailAddress', '').lower() == their_email.lower() 
                        for p in permissions
                    )
                    
                    if not has_permission:
                        if self._add_permission(outbox_id, their_email, role='writer', verbose=verbose):
                            if verbose:
                                print(f"   ✅ Granted write access to {their_email}")
                    elif created:
                        if verbose:
                            print(f"   ℹ️  {their_email} already has access")
                except Exception as e:
                    if verbose:
                        print(f"   ⚠️  Could not set permissions: {e}")
            
            # Check for incoming archive folder (created by the other party)
            archive_name = f"syft_{their_email}_to_{my_email}_archive"
            archive_id = self._get_folder_id(archive_name, parent_id=syftbox_id)
            
            if archive_id:
                folder_ids['archive'] = archive_id
                if verbose:
                    print(f"✅ Archive folder found: {archive_name}")
            else:
                if verbose:
                    print(f"⏳ Archive folder will be created by {their_email}")
            
            if verbose:
                print(f"✅ Communication channel ready: {my_email} → {their_email}")
            
            return folder_ids
            
        except HttpError as e:
            if verbose:
                print(f"❌ Error setting up communication channel: {e}")
            return None
    
    def _setup_incoming_archive(self, their_email: str, my_email: str = None, verbose: bool = True) -> Optional[str]:
        """
        Create archive folder for incoming messages from another person
        
        Args:
            their_email: Sender's email address
            my_email: Your email address (optional, defaults to authenticated user)
            verbose: Whether to print status messages (default: True)
            
        Returns:
            Archive folder ID if successful
        """
        self._ensure_authenticated()
        
        # Use authenticated user's email if not provided
        if my_email is None:
            if self.my_email is None:
                print("❌ Could not determine your email address")
                return None
            my_email = self.my_email
        
        try:
            # First ensure SyftBox exists
            syftbox_id = self.setup_syftbox()
            if not syftbox_id:
                return None
            
            
            # Create archive folder name
            archive_name = f"syft_{their_email}_to_{my_email}_archive"
            
            # Check if archive already exists
            results = self.service.files().list(
                q=f"name='{archive_name}' and mimeType='application/vnd.google-apps.folder' and '{syftbox_id}' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            
            archive_folders = results.get('files', [])
            if archive_folders:
                archive_id = archive_folders[0]['id']
                if verbose:
                    print(f"✅ Archive folder already exists: {archive_name}")
            else:
                # Create archive folder
                archive_id = self._create_folder(archive_name, parent_id=syftbox_id)
                if archive_id:
                    if verbose:
                        print(f"📁 Created archive folder: {archive_name}")
                        print(f"   📚 For storing processed messages from {their_email}")
                    
                    # Grant sender write access to archive
                    try:
                        if self._add_permission(archive_id, their_email, role='writer', verbose=verbose):
                            if verbose:
                                print(f"   ✅ Granted write access to {their_email}")
                    except Exception as e:
                        if verbose:
                            print(f"   ⚠️  Could not set permissions: {e}")
                else:
                    if verbose:
                        print(f"❌ Failed to create archive folder")
                    return None
            
            return archive_id
            
        except HttpError as e:
            print(f"❌ Error setting up archive: {e}")
            return None
    
    def add_friend(self, friend_email: str, verbose: bool = False) -> bool:
        """
        Add a friend by setting up bidirectional communication
        
        This method:
        1. Creates your outgoing channel to them
        2. Creates your archive for their messages
        3. Creates shortcuts for their shared folders
        
        Args:
            friend_email: Email address of the friend to add
            verbose: Whether to print detailed progress messages (default: False)
            
        Returns:
            True if successful
        """
        self._ensure_authenticated()
        
        if not self.my_email:
            print("❌ Could not determine your email address")
            return False
            
        if friend_email.lower() == self.my_email.lower():
            print("❌ Cannot add yourself as a friend")
            return False
        
        try:
            # 1. Set up outgoing channel (your folders)
            result = self._setup_communication_channel(friend_email, verbose=False)
            if not result:
                print(f"❌ Failed to create channel to {friend_email}")
                return False
            
            # 2. Set up incoming archive
            archive_id = self._setup_incoming_archive(friend_email, verbose=verbose)
            
            # 3. Create shortcuts for any existing shared folders from them
            shortcut_results = self._create_shortcuts_for_friend(friend_email, syftbox_id=result.get('syftbox_id'))
            if verbose and shortcut_results['created'] > 0:
                print(f"   🔗 Created {shortcut_results['created']} shortcut(s) for shared folders")
            
            if verbose:
                print(f"✅ Added {friend_email} as a friend!")
                print(f"   📤 Your outgoing channel is ready")
                print(f"   📥 Your incoming archive is ready")
                if shortcut_results['created'] > 0:
                    print(f"   🔗 Created {shortcut_results['created']} shortcut{'s' if shortcut_results['created'] != 1 else ''} for their shared folders")
                print(f"\n💡 Ask {friend_email} to run: client.add_friend('{self.my_email}')")
            else:
                print(f"✅ Added {friend_email} as a friend")
            
            # Invalidate friends cache
            self._invalidate_friends_cache()
            
            return True
            
        except Exception as e:
            print(f"❌ Error adding friend: {e}")
            return False
    
    def send_file_or_folder_auto(self, path: str, recipient_email: str) -> bool:
        """
        Send a file or folder automatically choosing the best transport method
        
        Small files (<37.5KB compressed) use sheets for faster delivery
        Large files use direct Google Drive upload
        
        Args:
            path: Path to the file or folder to send (supports syft:// URLs)
            recipient_email: Email address of the recipient (must be a friend)
            
        Returns:
            bool: True if successful, False otherwise
        """
        import tempfile
        
        self._ensure_authenticated()
        
        # Resolve syft:// URLs
        resolved_path = self.resolve_syft_path(path)
        
        # Check if recipient is in friends list
        if recipient_email not in self.friends:
            print(f"❌ We don't have an outbox for {recipient_email}")
            return False
        
        # Create a temporary directory to check size
        with tempfile.TemporaryDirectory() as temp_dir:
            # Prepare the message to check size
            result = self._prepare_message(resolved_path, recipient_email, temp_dir)
            if not result:
                return False
            
            message_id, archive_path, archive_size = result
            
            # Decide which method to use based on size
            # Google Sheets has a 50,000 character limit per cell
            # Base64 encoding increases size by ~33% (4/3 ratio)
            # So max raw size = 50,000 / (4/3) = 37,500 bytes
            max_sheets_size = 37_500  # Conservative limit to stay under 50k chars
            if archive_size <= max_sheets_size:
                if self.verbose:
                    print(f"📊 Using sheets transport (size: {archive_size:,} bytes)")
                # Small file - use sheets (faster)
                return self.send_file_or_folder_via_sheets(resolved_path, recipient_email)
            else:
                if self.verbose:
                    if archive_size < 1024 * 1024:
                        print(f"📦 Using direct upload (size: {archive_size:,} bytes)")
                    else:
                        print(f"📦 Using direct upload (size: {archive_size / (1024*1024):.1f}MB)")
                # Large file - use direct upload
                return self.send_file_or_folder(resolved_path, recipient_email)
    
    def send_file_or_folder_to_friends(self, path: str) -> Dict[str, bool]:
        """
        Send a file or folder to all friends using the best transport method
        
        Args:
            path: Path to the file or folder to send (supports syft:// URLs)
            
        Returns:
            Dict mapping friend emails to success status
        """
        self._ensure_authenticated()
        
        # Resolve syft:// URLs
        resolved_path = self.resolve_syft_path(path)
        
        # Check if path exists
        if not os.path.exists(resolved_path):
            print(f"❌ Path not found: {resolved_path}")
            if path.startswith("syft://"):
                print(f"   (resolved from: {path})")
            return {}
        
        # Get list of friends
        friends_list = self.friends
        if not friends_list:
            print("❌ No friends to send to. Add friends first with add_friend()")
            return {}
        
        if self.verbose:
            print(f"📤 Sending {os.path.basename(resolved_path)} to {len(friends_list)} friend(s)...")
        
        results = {}
        successful = 0
        failed = 0
        
        for i, friend_email in enumerate(friends_list, 1):
            if self.verbose:
                print(f"\n[{i}/{len(friends_list)}] Sending to {friend_email}...")
            
            try:
                # Use auto method to choose best transport
                success = self.send_file_or_folder_auto(resolved_path, friend_email)
                results[friend_email] = success
                
                if success:
                    if self.verbose:
                        print(f"   ✅ Successfully sent to {friend_email}")
                    successful += 1
                else:
                    if self.verbose:
                        print(f"   ❌ Failed to send to {friend_email}")
                    failed += 1
                    
            except Exception as e:
                if self.verbose:
                    print(f"   ❌ Error sending to {friend_email}: {str(e)}")
                results[friend_email] = False
                failed += 1
        
        # Summary
        if self.verbose:
            print(f"\n📊 Summary:")
            print(f"   ✅ Successful: {successful}")
            print(f"   ❌ Failed: {failed}")
            print(f"   📨 Total: {len(friends_list)}")
        
        return results
    
    def _prepare_message(self, path: str, recipient_email: str, temp_dir: str) -> Optional[tuple]:
        """
        Prepare a SyftMessage archive for sending
        
        Args:
            path: Path to the file or folder to send
            recipient_email: Email address of the recipient
            temp_dir: Temporary directory to create the message in
            
        Returns:
            Tuple of (message_id, archive_path, archive_size) if successful, None otherwise
        """
        from .syft_message import SyftMessage
        
        # Check if path exists
        if not os.path.exists(path):
            print(f"❌ Path not found: {path}")
            return None
        
        # Validate that the file is within THIS client's SyftBox folder
        abs_path = os.path.abspath(path)
        expected_syftbox = self.get_syftbox_directory()
        
        if expected_syftbox is None:
            print(f"❌ Error: Could not determine SyftBox directory")
            return None
        
        expected_syftbox_str = str(expected_syftbox)
        
        # Check if the file is within this specific client's SyftBox
        if not abs_path.startswith(expected_syftbox_str + os.sep):
            print(f"❌ Error: Files must be within YOUR SyftBox folder to be sent")
            print(f"   Your SyftBox: {expected_syftbox_str}")
            print(f"   File path: {path}")
            print(f"   Tip: Move your file to {expected_syftbox_str}/datasites/ or use syft:// URLs")
            print(f"   Example: syft://filename.txt")
            return None
        
        is_directory = os.path.isdir(path)
        temp_path = Path(temp_dir)
        
        # Create SyftMessage
        message = SyftMessage.create(
            sender_email=self.my_email,
            recipient_email=recipient_email,
            message_root=temp_path
        )
        
        if self.verbose:
            print(f"📦 Creating message: {message.message_id}")
        
        # Check if the path is within a datasites directory
        datasites_marker = os.sep + "datasites" + os.sep
        
        if datasites_marker not in abs_path:
            print(f"❌ Error: Files must be within a SyftBox datasites folder to be sent")
            print(f"   Path: {path}")
            print(f"   Tip: Move your file to {self.get_syftbox_directory()}/datasites/")
            return None
        
        # Extract the path relative to datasites
        parts = abs_path.split(datasites_marker, 1)
        if len(parts) == 2:
            relative_to_datasites = parts[1]
        else:
            relative_to_datasites = os.path.basename(path)
        
        # Add files to the message
        if is_directory:
            # For directories, use the relative path if within datasites
            if datasites_marker in abs_path:
                self._add_folder_to_message(message, path, None, parent_path=relative_to_datasites)
            else:
                # Not in datasites, use directory name as base
                base_name = os.path.basename(path.rstrip('/'))
                self._add_folder_to_message(message, path, base_name)
        else:
            # Add single file with correct datasites path
            syftbox_path = f"datasites/{relative_to_datasites}"
            message.add_file(
                source_path=Path(path),
                path=syftbox_path,
                permissions={
                    "read": [recipient_email],
                    "write": [self.my_email]
                }
            )
            
            if self.verbose:
                print(f"   📄 Added file: {relative_to_datasites}")
        
        # Finalize the message
        message.finalize()
        
        # Create tar.gz archive
        archive_path = os.path.join(temp_dir, f"{message.message_id}.tar.gz")
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(str(message.path), arcname=message.message_id)
        
        # Get archive size
        archive_size = os.path.getsize(archive_path)
        
        return (message.message_id, archive_path, archive_size)
    
    def send_file_or_folder(self, path: str, recipient_email: str) -> bool:
        """
        Send a file or folder to a friend by creating a SyftMessage
        
        Args:
            path: Path to the file or folder to send
            recipient_email: Email address of the recipient (must be a friend)
            
        Returns:
            bool: True if successful, False otherwise
        """
        import tempfile
        
        self._ensure_authenticated()
        
        # Check if recipient is in friends list
        if recipient_email not in self.friends:
            print(f"❌ We don't have an outbox for {recipient_email}")
            return False
        
        # Get the outbox folder ID
        if not self.my_email:
            print("❌ Could not determine your email address")
            return False
        
        outbox_inbox_name = f"syft_{self.my_email}_to_{recipient_email}_outbox_inbox"
        
        try:
            # Get SyftBox ID using cache
            syftbox_id = self._get_syftbox_folder_id()
            
            if not syftbox_id:
                print("❌ SyftBoxTransportService not found")
                return False
            
            # Find the outbox folder using cache
            outbox_id = self._get_folder_id(outbox_inbox_name, parent_id=syftbox_id)
            
            if not outbox_id:
                print(f"❌ Outbox folder not found for {recipient_email}")
                return False
            
            # Create a temporary directory for the SyftMessage
            with tempfile.TemporaryDirectory() as temp_dir:
                # Prepare the message
                result = self._prepare_message(path, recipient_email, temp_dir)
                if not result:
                    return False
                
                message_id, archive_path, archive_size = result
                
                # Check size before uploading (5MB limit for sheets)
                if archive_size > 5 * 1024 * 1024:
                    if self.verbose:
                        print(f"📦 Message size: {archive_size / (1024*1024):.1f}MB - using direct upload")
                
                # Check if there's already a message with this ID and delete it
                existing_messages = self.service.files().list(
                    q=f"name='{message_id}' and '{outbox_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(id, name)"
                ).execute()
                
                for existing in existing_messages.get('files', []):
                    try:
                        self.service.files().delete(fileId=existing['id']).execute()
                        if self.verbose:
                            print(f"   ♻️  Replacing existing message: {message_id}")
                    except Exception as e:
                        if self.verbose:
                            print(f"   ⚠️  Could not delete existing message: {e}")
                
                # Upload the entire SyftMessage folder
                file_id = self._upload_folder_as_archive(str(Path(temp_dir) / message_id), outbox_id, message_id)
                
                if file_id:
                    if self.verbose:
                        print(f"✅ Message sent to {recipient_email}")
                    return True
                else:
                    print(f"❌ Failed to upload message")
                    return False
                
        except Exception as e:
            print(f"❌ Error sending: {e}")
            return False
    
    def _add_folder_to_message(self, message, folder_path: str, base_path: str, parent_path: str = ""):
        """
        Recursively add all files from a folder to a SyftMessage
        
        Args:
            message: SyftMessage instance
            folder_path: Local folder path to add
            base_path: Base folder name for syftbox paths
            parent_path: Parent path for recursive calls
        """
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            
            # Skip hidden files
            if item.startswith('.'):
                continue
                
            if os.path.isfile(item_path):
                # Calculate relative path for syftbox
                relative_path = os.path.join(parent_path, item) if parent_path else item
                
                # Build syftbox path based on whether we have a base_path
                if base_path:
                    syftbox_path = f"datasites/{base_path}/{relative_path}"
                else:
                    # No base path, parent_path contains the full relative path
                    syftbox_path = f"datasites/{relative_path}"
                
                try:
                    message.add_file(
                        source_path=Path(item_path),
                        path=syftbox_path,
                        permissions={
                            "read": [message.recipient_email],
                            "write": [message.sender_email]
                        }
                    )
                    if self.verbose:
                        print(f"   📄 Added: {relative_path}")
                except Exception as e:
                    if self.verbose:
                        print(f"   ⚠️  Skipped {relative_path}: {e}")
                        
            elif os.path.isdir(item_path):
                # Recursively add subdirectory
                new_parent = os.path.join(parent_path, item) if parent_path else item
                self._add_folder_to_message(message, item_path, base_path, new_parent)

    def update_inbox(self, inbox_dir: str = None, archive_messages: bool = True, fast_mode: bool = False) -> Dict[str, List[str]]:
        """
        Check all friend inboxes for new SyftMessage objects and download them
        
        Args:
            inbox_dir: Local directory to store messages (default: {syftbox_dir}/inbox)
            archive_messages: Whether to archive messages after downloading (default: True)
            fast_mode: Skip validation and download everything (default: False)
            
        Returns:
            Dict mapping friend emails to list of downloaded message IDs
        """
        from .syft_message import SyftMessage
        from googleapiclient.http import BatchHttpRequest
        
        self._ensure_authenticated()
        
        # Set default inbox directory using get_syftbox_directory
        if inbox_dir is None:
            syftbox_dir = self.get_syftbox_directory()
            if syftbox_dir is None:
                print("❌ Could not determine SyftBox directory")
                return {}
            inbox_dir = str(syftbox_dir / "inbox")
        
        # Create inbox directory if it doesn't exist
        os.makedirs(inbox_dir, exist_ok=True)
        
        if not self.my_email:
            print("❌ Could not determine your email address")
            return {}
        
        # Get list of friends
        friends_list = self.friends
        if not friends_list:
            if self.verbose:
                print("No friends found - nothing to check")
            return {}
        
        if self.verbose:
            print(f"📥 Checking inboxes from {len(friends_list)} friend(s)...")
        
        # Get SyftBox folder ID
        try:
            results = self.service.files().list(
                q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            
            if not results.get('files'):
                print("❌ SyftBoxTransportService not found")
                return {}
                
            syftbox_id = results['files'][0]['id']
        except Exception as e:
            print(f"❌ Error finding SyftBox folder: {e}")
            return {}
        
        # Prepare batch request to check all inboxes
        downloaded_messages = {}
        
        def process_batch_in_chunks(friends, chunk_size=100):
            """Process friends in chunks of 100 (batch request limit)"""
            for i in range(0, len(friends), chunk_size):
                chunk = friends[i:i + chunk_size]
                
                # Create batch request
                batch = self.service.new_batch_http_request()
                callbacks = {}
                
                # Add requests for each friend's inbox
                for friend_email in chunk:
                    # Look for the inbox folder shared by this friend
                    inbox_name = f"syft_{friend_email}_to_{self.my_email}_outbox_inbox"
                    
                    def make_callback(email, inbox):
                        def callback(request_id, response, exception):
                            if exception is None:
                                callbacks[email] = (inbox, response)
                            else:
                                if self.verbose:
                                    print(f"   ⚠️  Error checking {email}: {exception}")
                                callbacks[email] = (inbox, None)
                        return callback
                    
                    # First get the inbox folder ID, then search within it
                    def make_inbox_callback(email, inbox):
                        def callback(request_id, response, exception):
                            if exception is None and response.get('files'):
                                file_info = response['files'][0]
                                inbox_id = file_info['id']
                                
                                # If it's a shortcut, get the target ID
                                if file_info.get('mimeType') == 'application/vnd.google-apps.shortcut':
                                    shortcut_details = file_info.get('shortcutDetails', {})
                                    target_id = shortcut_details.get('targetId')
                                    if target_id:
                                        inbox_id = target_id
                                        if self.verbose:
                                            print(f"   📎 Found inbox shortcut for {email}, using target: {target_id}")
                                
                                callbacks[email] = (inbox, inbox_id)
                            else:
                                if self.verbose and exception:
                                    print(f"   ⚠️  Error finding inbox for {email}: {exception}")
                                callbacks[email] = (inbox, None)
                        return callback
                    
                    # Find the inbox folder first (could be a folder or shortcut)
                    batch.add(
                        self.service.files().list(
                            q=f"name='{inbox_name}' and (mimeType='application/vnd.google-apps.folder' or mimeType='application/vnd.google-apps.shortcut') and trashed=false",
                            fields="files(id, mimeType, shortcutDetails)",
                            pageSize=1
                        ),
                        callback=make_inbox_callback(friend_email, inbox_name)
                    )
                
                # Execute batch request
                try:
                    batch.execute()
                except Exception as e:
                    print(f"❌ Batch request failed: {e}")
                    continue
                
                # Process results - now we need to search within each inbox
                for friend_email, (inbox_name, inbox_folder_id) in callbacks.items():
                    if inbox_folder_id is None:
                        continue
                    
                    # Now search for messages within this specific inbox folder
                    try:
                        # Just get ALL files in the folder - no filtering at all (fastest query)
                        messages_response = self.service.files().list(
                            q=f"'{inbox_folder_id}' in parents",
                            fields="files(id, name)",
                            pageSize=1000  # Get more at once
                        ).execute()
                        
                        # Filter locally for tar.gz syft_message files
                        all_files = messages_response.get('files', [])
                        inbox_messages = [
                            f for f in all_files 
                            if f.get('name', '').startswith('syft_message_') and 
                               f.get('name', '').endswith('.tar.gz')
                        ]
                        
                        if inbox_messages:
                            if self.verbose:
                                print(f"\n📬 Found {len(inbox_messages)} message(s) from {friend_email}")
                            downloaded_messages[friend_email] = []
                            
                            # Download each message
                            for msg in inbox_messages:
                                msg_filename = msg['name']  # e.g., syft_message_12345.tar.gz
                                msg_file_id = msg['id']
                                
                                # Extract message ID from filename (remove .tar.gz)
                                msg_id = msg_filename.replace('.tar.gz', '')
                                
                                # Note: Archives are already finalized, no need to check for lock.json
                                
                                # Check if already extracted
                                local_msg_path = os.path.join(inbox_dir, msg_id)
                                already_downloaded = os.path.exists(local_msg_path)
                                
                                # In fast mode, skip if already downloaded
                                if already_downloaded and (not archive_messages or fast_mode):
                                    if self.verbose:
                                        print(f"   ⏭️  Skipping {msg_id} - already downloaded")
                                    continue
                                
                                # Download if not already downloaded
                                download_success = True
                                if not already_downloaded:
                                    if self.verbose:
                                        print(f"   📥 Processing {msg_id}...")
                                    
                                    # Download and extract the archive
                                    download_success = self._download_archive_and_extract(msg_file_id, inbox_dir, msg_id)
                                    if download_success:
                                        downloaded_messages[friend_email].append(msg_id)
                                else:
                                    if self.verbose:
                                        print(f"   📥 Already downloaded {msg_id}, checking for archiving...")
                                
                                if download_success:
                                    # Validate the downloaded message (skip in fast mode)
                                    is_valid = fast_mode  # In fast mode, assume valid
                                    if not fast_mode:
                                        try:
                                            received_msg = SyftMessage(Path(local_msg_path))
                                            is_valid, error = received_msg.validate()
                                            if is_valid:
                                                if self.verbose:
                                                    print(f"   ✅ Valid message from {received_msg.sender_email}")
                                            else:
                                                print(f"   ❌ Invalid message: {error}")
                                        except Exception as e:
                                            print(f"   ❌ Error validating message: {e}")
                                    
                                    # Archive the message if it was valid and archiving is enabled
                                    if is_valid and archive_messages:
                                        # Archive folder follows pattern: syft_{sender}_to_{receiver}_archive
                                        archive_name = f"syft_{friend_email}_to_{self.my_email}_archive"
                                        
                                        # Check if archive folder exists, create if not
                                        try:
                                            archive_results = self.service.files().list(
                                                q=f"name='{archive_name}' and mimeType='application/vnd.google-apps.folder' and '{syftbox_id}' in parents and trashed=false",
                                                fields="files(id)",
                                                pageSize=1
                                            ).execute()
                                            
                                            if archive_results.get('files'):
                                                archive_id = archive_results['files'][0]['id']
                                            else:
                                                # Create archive folder
                                                archive_id = self._create_folder(archive_name, parent_id=syftbox_id)
                                                if self.verbose and archive_id:
                                                    print(f"   📁 Created archive folder: {archive_name}")
                                            
                                            if archive_id:
                                                # Move message archive file from inbox to archive folder (non-blocking)
                                                if self.verbose:
                                                    print(f"   📦 Scheduling background archive for {msg_id}...")
                                                
                                                # Create and start background thread for archiving
                                                archive_thread = threading.Thread(
                                                    target=self._archive_message_async,
                                                    args=(msg_file_id, archive_id, inbox_folder_id, msg_id, archive_name),
                                                    daemon=True  # Daemon thread will not block program exit
                                                )
                                                archive_thread.start()
                                        except Exception as e:
                                            if self.verbose:
                                                print(f"   ⚠️  Error creating archive: {e}")
                                else:
                                    print(f"   ❌ Failed to download {msg_id}")
                        else:
                            if self.verbose:
                                print(f"   📭 No messages from {friend_email}")
                    except Exception as e:
                        if self.verbose:
                            print(f"   ⚠️  Error checking messages from {friend_email}: {e}")
        
        # Process all friends (in chunks if > 100)
        process_batch_in_chunks(friends_list)
        
        # Summary
        total_messages = sum(len(msgs) for msgs in downloaded_messages.values())
        if total_messages > 0 and self.verbose:
            print(f"\n✅ Downloaded {total_messages} message(s) to {inbox_dir}")
        elif total_messages == 0 and self.verbose:
            print("✅ No messages to download")
        
        return downloaded_messages
    
    def autoapprove_inbox(self, syftbox_dir: Optional[Path] = None) -> Dict[str, int]:
        """
        Automatically approve all messages in the inbox by moving them to the approved folder
        
        Args:
            syftbox_dir: Optional SyftBox directory path (defaults to get_syftbox_directory())
            
        Returns:
            Dict mapping message types to counts of approved messages
        """
        import shutil
        from collections import defaultdict
        
        # print("AUTOAPPROVE-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("AUTOAPPROVE-2 " + str(time.time()))
        
        # Get SyftBox directory
        if syftbox_dir is None:
            # print("AUTOAPPROVE-3 " + str(time.time()))
            syftbox_dir = self.get_syftbox_directory()
            # print("AUTOAPPROVE-4 " + str(time.time()))
            if syftbox_dir is None:
                print("❌ Could not determine SyftBox directory")
                return {}
        
        # Ensure we're working with the correct user's SyftBox
        expected_dir_name = f"SyftBox_{self.my_email}"
        if syftbox_dir.name != expected_dir_name:
            print(f"❌ SyftBox directory name mismatch. Expected '{expected_dir_name}' but got '{syftbox_dir.name}'")
            return {}
        
        inbox_dir = syftbox_dir / "inbox"
        approved_dir = syftbox_dir / "approved"
        
        # Check if inbox exists
        # print("AUTOAPPROVE-5 " + str(time.time()))
        if not inbox_dir.exists():
            print(f"📥 No inbox found at {inbox_dir}")
            return {}
        
        # Create approved directory if it doesn't exist
        # print("AUTOAPPROVE-6 " + str(time.time()))
        approved_dir.mkdir(exist_ok=True)
        
        # Count messages by type
        approved_counts = defaultdict(int)
        total_moved = 0
        
        if self.verbose:
            print(f"📥 Auto-approving messages from {inbox_dir}")
        
        # List all items in inbox
        # print("AUTOAPPROVE-7 " + str(time.time()))
        try:
            # print("AUTOAPPROVE-8 " + str(time.time()))
            for item in inbox_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    # Determine message type
                    if item.name.startswith("syft_message_"):
                        message_type = "syft_message"
                    elif item.name.startswith("syft_") and "_to_" in item.name:
                        message_type = "syft_folder"
                    else:
                        message_type = "other"
                    
                    # Move to approved folder
                    # print("AUTOAPPROVE-9 " + str(time.time()))
                    dest_path = approved_dir / item.name
                    
                    # If destination exists, remove it first
                    if dest_path.exists():
                        if dest_path.is_dir():
                            shutil.rmtree(dest_path)
                        else:
                            dest_path.unlink()
                    
                    # Move the folder
                    # print("AUTOAPPROVE-10 " + str(time.time()))
                    shutil.move(str(item), str(dest_path))
                    # print("AUTOAPPROVE-11 " + str(time.time()))
                    
                    approved_counts[message_type] += 1
                    total_moved += 1
                    
                    if self.verbose:
                        print(f"   ✓ Approved: {item.name}")
            
            # Print summary
            # print("AUTOAPPROVE-12 " + str(time.time()))
            if total_moved > 0:
                if self.verbose:
                    print(f"\n✅ Auto-approved {total_moved} message(s):")
                    for msg_type, count in approved_counts.items():
                        print(f"   - {msg_type}: {count}")
            else:
                print("✅ No messages to approve")
                
        except Exception as e:
            print(f"❌ Error during auto-approval: {e}")
        
        # print("AUTOAPPROVE-13 " + str(time.time()))
        return dict(approved_counts)
    
    def _get_sync_history_path(self, file_path: Path) -> Path:
        """
        Get the sync history directory path for a file
        
        Args:
            file_path: Path to the file in datasites
            
        Returns:
            Path to the sync history directory
        """
        # Create .sync_history directory in the same directory as the file
        return file_path.parent / ".sync_history" / file_path.name
    
    def _get_sync_timestamp(self, message_path: Path) -> Optional[float]:
        """
        Get the timestamp from a SyftMessage
        
        Args:
            message_path: Path to the message directory
            
        Returns:
            Timestamp as float or None if not found
        """
        # Try to get from cached metadata first
        message_id = str(message_path.name)
        if message_id in self._metadata_cache:
            metadata = self._metadata_cache[message_id]
            return metadata.get("timestamp")
        
        # Try reading metadata files
        for metadata_file in ["metadata.json", "metadata.yaml"]:
            metadata_path = message_path / metadata_file
            if metadata_path.exists():
                try:
                    if metadata_file.endswith(".json"):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                    else:
                        with open(metadata_path, 'r') as f:
                            metadata = yaml.safe_load(f) or {}
                    return metadata.get("timestamp")
                except:
                    continue
        
        return None
    
    def _should_apply_sync(self, file_path: Path, message_path: Path) -> bool:
        """
        Check if a sync should be applied based on history
        
        Args:
            file_path: Path to the file in datasites
            message_path: Path to the incoming message
            
        Returns:
            True if sync should be applied, False otherwise
        """
        history_path = self._get_sync_history_path(file_path)
        
        # If no history exists, always apply
        if not history_path.exists():
            return True
        
        # Get timestamp of incoming message
        incoming_timestamp = self._get_sync_timestamp(message_path)
        if incoming_timestamp is None:
            # If no timestamp, apply it (for backward compatibility)
            return True
        
        # Check existing syncs in history
        try:
            for entry in os.listdir(history_path):
                entry_path = history_path / entry
                if entry_path.is_dir() and entry.endswith(".syftmessage"):
                    # Get timestamp of existing sync
                    existing_timestamp = self._get_sync_timestamp(entry_path)
                    if existing_timestamp and existing_timestamp >= incoming_timestamp:
                        # We already have a sync that's newer or equal
                        if self.verbose:
                            print(f"      ⏭️  Skipping older sync for: {file_path.name}")
                        return False
        except:
            # If we can't read history, apply the sync
            return True
        
        return True
    
    def _store_sync_history(self, file_path: Path, message_path: Path) -> None:
        """
        Store a copy of the SyftMessage in sync history
        
        Args:
            file_path: Path to the file in datasites
            message_path: Path to the message directory
        """
        history_path = self._get_sync_history_path(file_path)
        
        # Create history directory
        history_path.mkdir(parents=True, exist_ok=True)
        
        # Create unique name for this sync
        timestamp = self._get_sync_timestamp(message_path) or time.time()
        sync_name = f"{timestamp}_{message_path.name}.syftmessage"
        sync_dest = history_path / sync_name
        
        # Copy the message directory to history
        try:
            if not sync_dest.exists():
                shutil.copytree(message_path, sync_dest)
        except Exception as e:
            if self.verbose:
                print(f"      ⚠️  Could not store sync history: {e}")
    
    def _clean_sync_history_for_datasite(self, datasite_path: Path, keep_latest: bool = True) -> int:
        """
        Clean up sync history for a datasite when receiving a full update
        
        Args:
            datasite_path: Path to the datasite directory
            keep_latest: Whether to keep the latest sync (default: True)
            
        Returns:
            Number of sync history entries cleaned
        """
        cleaned_count = 0
        
        # Walk through all .sync_history directories in the datasite
        for root, dirs, files in os.walk(datasite_path):
            if ".sync_history" in dirs:
                history_dir = Path(root) / ".sync_history"
                
                # Process each file's history
                for file_history in history_dir.iterdir():
                    if file_history.is_dir():
                        syncs = []
                        
                        # Collect all syncs for this file
                        for sync_entry in file_history.iterdir():
                            if sync_entry.is_dir() and sync_entry.name.endswith(".syftmessage"):
                                timestamp = self._get_sync_timestamp(sync_entry)
                                if timestamp:
                                    syncs.append((timestamp, sync_entry))
                        
                        # Sort by timestamp
                        syncs.sort(key=lambda x: x[0])
                        
                        # Remove all but the latest if keep_latest is True
                        to_remove = syncs[:-1] if keep_latest and syncs else syncs
                        
                        for _, sync_path in to_remove:
                            try:
                                shutil.rmtree(sync_path)
                                cleaned_count += 1
                            except Exception as e:
                                if self.verbose:
                                    print(f"⚠️  Could not remove sync history: {e}")
        
        if self.verbose and cleaned_count > 0:
            print(f"🧹 Cleaned {cleaned_count} old sync history entries")
        
        return cleaned_count

    def _extract_message_directly(self, message_path: Path, datasites_dir: Path) -> Dict[str, int]:
        """
        Extract files directly from a message without creating SyftMessage object
        
        Args:
            message_path: Path to the message directory
            datasites_dir: Path to datasites directory
            
        Returns:
            Dict with counts of files processed
        """
        # print("MERGE-8a " + str(time.time()))
        stats = {
            "files_merged": 0,
            "files_overwritten": 0,
            "errors": 0
        }
        
        # Check memory cache first
        message_id = str(message_path.name)
        metadata = None
        
        # print("MERGE-8a1 " + str(time.time()))
        if message_id in self._metadata_cache:
            # Use cached metadata (instant!)
            metadata = self._metadata_cache[message_id]
            # print("MERGE-8b-cached " + str(time.time()))
        else:
            # Need to read from disk
            json_metadata_path = str(message_path) + "/metadata.json"  # String ops
            yaml_metadata_path = str(message_path) + "/metadata.yaml"
            
            # print("MERGE-8b " + str(time.time()))
            
            # Try JSON first (no existence check - just try to open)
            try:
                with open(json_metadata_path, 'r') as f:
                    # print("MERGE-8b-json-opened " + str(time.time()))
                    metadata = json.load(f)
                    # print("MERGE-8b2-json " + str(time.time()))
                    # Cache it
                    self._metadata_cache[message_id] = metadata
            except FileNotFoundError:
                # print("MERGE-8b-json-not-found " + str(time.time()))
                # JSON doesn't exist, try YAML
                try:
                    # print("MERGE-8b1-yaml-start " + str(time.time()))
                    with open(yaml_metadata_path, 'r') as f:
                        metadata = yaml.safe_load(f) or {}
                    # print("MERGE-8b2-yaml " + str(time.time()))
                    # Cache it
                    self._metadata_cache[message_id] = metadata
                    
                    # Convert to JSON for next time (write in background to not block)
                    try:
                        def write_json_cache():
                            time.sleep(0.2)  # Delay to avoid I/O contention
                            with open(json_metadata_path, 'w') as f:
                                json.dump(metadata, f, indent=2)
                        
                        # Start background thread to write JSON cache
                        cache_thread = threading.Thread(target=write_json_cache)
                        cache_thread.daemon = True
                        cache_thread.start()
                    except:
                        pass  # Ignore cache write errors
                except FileNotFoundError:
                    # Neither file exists
                    return stats
            except Exception as e:
                stats["errors"] += 1
                return stats
        
        if not metadata:
            return stats
        
        # print("MERGE-8c " + str(time.time()))
        # Get sender for logging
        sender = metadata.get("from", "unknown")
        # print("MERGE-8c1 " + str(time.time()))
        if self.verbose:
            print(f"\n   📦 Processing message from {sender}")
        
        # print("MERGE-8c2 " + str(time.time()))
        # Process files directly
        files_info = metadata.get("files", [])
        # print("MERGE-8c3 " + str(time.time()))
        
        # Use string operations instead of Path objects
        files_dir_str = str(message_path) + "/data/files"
        datasites_dir_str = str(datasites_dir)
        
        # print("MERGE-8d " + str(time.time()))
        
        # First pass: validate and prepare all operations
        operations = []
        for file_entry in files_info:
            try:
                file_path = file_entry["path"]
                
                # Check if path starts with "datasites/"
                if not file_path.startswith("datasites/"):
                    print(f"      ⚠️  Skipping file with non-datasites path: {file_path}")
                    continue
                
                # Get source and destination paths using strings
                internal_name = file_entry.get("_internal_name", os.path.basename(file_path))
                source_path_str = files_dir_str + "/" + internal_name
                
                # Calculate destination
                relative_path = file_path[len("datasites/"):]
                dest_path_str = datasites_dir_str + "/" + relative_path
                
                operations.append({
                    'source': source_path_str,
                    'dest': dest_path_str,
                    'relative_path': relative_path
                })
            except Exception as e:
                print(f"      ❌ Error preparing file: {e}")
                stats["errors"] += 1
        
        # print("MERGE-8e " + str(time.time()))
        
        # Pre-compute unique parent directories using string operations
        unique_parents = set()
        for op in operations:
            parent_dir = os.path.dirname(op['dest'])
            unique_parents.add(parent_dir)
        
        # Create directories only if not already created
        for parent_dir in unique_parents:
            if parent_dir not in self._dir_structure:
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    self._dir_structure.add(parent_dir)
                except:
                    pass  # Directory might already exist
        
        # print("MERGE-8e2 " + str(time.time()))
        
        # Second pass: Use hard links (instant!) instead of move
        for op in operations:
            try:
                # Check sync history before applying
                dest_path = Path(op['dest'])
                if not self._should_apply_sync(dest_path, message_path):
                    stats["messages_skipped"] = stats.get("messages_skipped", 0) + 1
                    continue
                
                # Try hard link first (instant operation)
                try:
                    os.link(op['source'], op['dest'])
                    stats["files_merged"] += 1
                    if self.verbose:
                        print(f"      ✓ Linked: {op['relative_path']}")
                    # Store in sync history after successful merge
                    self._store_sync_history(dest_path, message_path)
                except FileExistsError:
                    # Destination exists, remove and retry
                    os.unlink(op['dest'])
                    os.link(op['source'], op['dest'])
                    stats["files_overwritten"] += 1
                    if self.verbose:
                        print(f"      ✓ Re-linked: {op['relative_path']}")
                    # Store in sync history after successful merge
                    self._store_sync_history(dest_path, message_path)
                except OSError as e:
                    # Hard link failed (maybe cross-filesystem), fall back to move
                    shutil.move(op['source'], op['dest'])
                    stats["files_merged"] += 1
                    if self.verbose:
                        print(f"      ✓ Moved: {op['relative_path']}")
                    # Store in sync history after successful merge
                    self._store_sync_history(dest_path, message_path)
                        
            except FileNotFoundError:
                print(f"      ❌ Source file not found: {op['source']}")
                stats["errors"] += 1
            except Exception as e:
                print(f"      ❌ Error linking file: {e}")
                stats["errors"] += 1
        
        # print("MERGE-8f " + str(time.time()))
        return stats
    
    def merge_new_syncs(self, syftbox_dir: Optional[Path] = None) -> Dict[str, int]:
        """
        Merge approved SyftMessages into the datasites directory
        
        This method:
        1. Reads all SyftMessage folders from the approved directory
        2. Validates each message
        3. Extracts files to their correct locations in datasites
        4. Overwrites existing files if they exist
        
        Args:
            syftbox_dir: Optional SyftBox directory path (defaults to get_syftbox_directory())
            
        Returns:
            Dict with counts of processed messages and files
        """
        from .syft_message import SyftMessage
        import shutil
        from collections import defaultdict
        
        # print("MERGE-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("MERGE-2 " + str(time.time()))
        
        # Get SyftBox directory
        if syftbox_dir is None:
            # print("MERGE-3 " + str(time.time()))
            syftbox_dir = self.get_syftbox_directory()
            # print("MERGE-4 " + str(time.time()))
            if syftbox_dir is None:
                print("❌ Could not determine SyftBox directory")
                return {}
        
        # Ensure we're working with the correct user's SyftBox
        expected_dir_name = f"SyftBox_{self.my_email}"
        if syftbox_dir.name != expected_dir_name:
            print(f"❌ SyftBox directory name mismatch. Expected '{expected_dir_name}' but got '{syftbox_dir.name}'")
            return {}
        
        approved_dir = syftbox_dir / "approved"
        datasites_dir = syftbox_dir / "datasites"
        
        # Check if approved directory exists
        # print("MERGE-5 " + str(time.time()))
        if not approved_dir.exists():
            print(f"📥 No approved directory found at {approved_dir}")
            return {}
        
        # Create datasites directory if it doesn't exist
        # print("MERGE-6 " + str(time.time()))
        datasites_dir.mkdir(exist_ok=True)
        
        # Track statistics
        stats = {
            "messages_processed": 0,
            "messages_skipped": 0,
            "files_merged": 0,
            "files_overwritten": 0,
            "errors": 0
        }
        if self.verbose:
            print(f"🔄 Merging approved syncs to {datasites_dir}")
        
        # Process each item in approved directory using faster os.scandir
        # print("MERGE-7 " + str(time.time()))
        items_processed = 0
        with os.scandir(str(approved_dir)) as entries:
            for entry in entries:
                
                try:
                    # Skip non-directories
                    if not entry.is_dir():
                        continue
                    
                    items_processed += 1
                    if items_processed == 1:
                        # print("MERGE-7a-first-item " + str(time.time()))
                        pass
                    
                    # print("MERGE-8 " + str(time.time()))
                    
                    # Convert DirEntry to Path for compatibility
                    item = Path(entry.path)
                    
                    # Use optimized direct extraction (no SyftMessage object)
                    file_stats = self._extract_message_directly(item, datasites_dir)
                    
                    # print("MERGE-9 " + str(time.time()))
                    
                    # Update overall stats
                    stats["files_merged"] += file_stats["files_merged"]
                    stats["files_overwritten"] += file_stats["files_overwritten"]
                    stats["errors"] += file_stats["errors"]
                    
                    # Check if any files were skipped due to sync history
                    files_skipped_due_to_history = file_stats.get("messages_skipped", 0)
                    
                    if file_stats["files_merged"] > 0 or file_stats["files_overwritten"] > 0:
                        stats["messages_processed"] += 1
                    elif files_skipped_due_to_history > 0:
                        # Message was skipped due to sync history
                        stats["messages_skipped"] += 1
                    else:
                        stats["messages_skipped"] += 1
                    
                    # Move processed message to merged_archive
                    # print("MERGE-10 " + str(time.time()))
                    merged_archive_dir = syftbox_dir / "merged_archive"
                    merged_archive_dir.mkdir(exist_ok=True)
                    
                    try:
                        archive_path = merged_archive_dir / item.name
                    
                        # If archive already exists, remove it first
                        if archive_path.exists():
                            if archive_path.is_dir():
                                shutil.rmtree(archive_path)
                            else:
                                archive_path.unlink()
                        
                        # Move to archive (instant operation)
                        # print("MERGE-11 " + str(time.time()))
                        shutil.move(str(item), str(archive_path))
                        # print("MERGE-12 " + str(time.time()))
                        
                        # The original folder is now empty (files were moved)
                        # Schedule async re-extraction from the archive file if it exists
                        archive_file = None
                        # Look for corresponding .tar.gz file in archive or inbox
                        for archive_dir in [syftbox_dir / "archive", syftbox_dir / "inbox"]:
                            if archive_dir.exists():
                                potential_archive = archive_dir / f"{item.name}.tar.gz"
                                if potential_archive.exists():
                                    archive_file = potential_archive
                                    break
                        
                        # Since we used hard links, the files still exist in approved
                        # We don't need to restore from archive immediately
                        # Just clean up if the directory is truly empty
                        try:
                            # Check if directory has any remaining files/subdirs
                            if not any(item.iterdir()):
                                item.rmdir()  # Remove if empty
                        except:
                            pass  # Directory not empty or other error
                        
                        if self.verbose:
                            print(f"   📁 Moved to merged_archive/{item.name}")
                            
                    except Exception as archive_error:
                        print(f"   ⚠️  Could not archive {item.name}: {archive_error}")
                    
                except Exception as e:
                    print(f"   ❌ Error processing {item.name}: {e}")
                    stats["errors"] += 1
        
        # Print summary
        # print("MERGE-13 " + str(time.time()))
        if self.verbose:
            print(f"\n✅ Merge completed:")
            print(f"   - Messages processed: {stats['messages_processed']}")
            print(f"   - Messages skipped: {stats['messages_skipped']}")
            print(f"   - Files merged: {stats['files_merged']}")
            print(f"   - Files overwritten: {stats['files_overwritten']}")
            if stats['errors'] > 0:
                print(f"   - Errors: {stats['errors']}")
        
        # print("MERGE-14 " + str(time.time()))
        return stats
    
    def _download_folder_recursive(self, folder_id: str, local_parent: str, folder_name: str) -> bool:
        """
        Recursively download a folder and its contents from Google Drive
        
        Args:
            folder_id: Google Drive folder ID
            local_parent: Local parent directory
            folder_name: Name for the local folder
            
        Returns:
            True if successful, False otherwise
        """
        self._ensure_authenticated()
        
        local_folder_path = os.path.join(local_parent, folder_name)
        
        try:
            # Create local folder
            os.makedirs(local_folder_path, exist_ok=True)
            
            # List all items in the folder
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType)"
            ).execute()
            
            items = results.get('files', [])
            
            # Separate items into folders and files
            folders = []
            files = []
            
            for item in items:
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    folders.append(item)
                else:
                    files.append(item)
            
            # Download subfolders
            for item in folders:
                if not self._download_folder_recursive(item['id'], local_folder_path, item['name']):
                    print(f"   ⚠️  Failed to download folder: {item['name']}")
            
            # Download files
            for item in files:
                local_file_path = os.path.join(local_folder_path, item['name'])
                if not self._download_file(item['id'], local_file_path):
                    print(f"   ⚠️  Failed to download file: {item['name']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error downloading folder: {e}")
            return False                

    @property
    def friends(self) -> List[str]:
        """
        List all friends (people you have set up outgoing channels to)
        
        Returns:
            List of email addresses you've added as friends
        """
        if not self.authenticated:
            return []
        
        if not self.my_email:
            return []
        
        # Check if cache is valid (less than 1 hour old)
        current_time = time.time()
        if (self._friends_cache is not None and 
            self._friends_cache_time is not None and 
            current_time - self._friends_cache_time < 3600):  # 3600 seconds = 1 hour
            return self._friends_cache
        
        try:
            # First check if SyftBoxTransportService exists using cache
            syftbox_id = self._get_syftbox_folder_id()
            
            if not syftbox_id:
                # No SyftBoxTransportService = no friends
                return []
            
            friends_set = set()
            
            # Get folders inside SyftBoxTransportService
            try:
                results = self.service.files().list(
                    q=f"'{syftbox_id}' in parents and name contains 'syft_' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(name)"
                ).execute()
                
                for folder in results.get('files', []):
                    name = folder['name']
                    # Look for your outgoing folders
                    if name.startswith(f'syft_{self.my_email}_to_'):
                        # Extract the recipient email
                        parts = name.split('_to_')
                        if len(parts) == 2:
                            # Remove the suffix (_pending, _outbox_inbox, etc)
                            email_with_suffix = parts[1]
                            # Handle both _outbox_inbox and _outbox suffixes
                            if '_outbox_inbox' in email_with_suffix:
                                email_part = email_with_suffix.replace('_outbox_inbox', '')
                            elif '_outbox' in email_with_suffix:
                                email_part = email_with_suffix.replace('_outbox', '')
                            elif '_pending' in email_with_suffix:
                                email_part = email_with_suffix.replace('_pending', '')
                            elif '_archive' in email_with_suffix:
                                email_part = email_with_suffix.replace('_archive', '')
                            else:
                                # No known suffix, try generic approach
                                email_part = email_with_suffix.rsplit('_', 1)[0]
                            friends_set.add(email_part)
            except:
                pass
            
            # Cache the results
            self._friends_cache = sorted(list(friends_set))
            self._friends_cache_time = time.time()
            return self._friends_cache
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error listing friends: {e}")
            # Return cached value if available, even if expired
            if self._friends_cache is not None:
                return self._friends_cache
            return []
    
    @property
    def friend_requests(self) -> List[str]:
        """
        List emails of people who have shared folders with you but you haven't shared back
        
        Returns:
            List of email addresses with pending friend requests
        """
        if not self.authenticated:
            return []
        
        if not self.my_email:
            return []
        
        try:
            # Get all syft folders
            all_folders = self._list_syft_folders()
            
            # Track who has shared with us
            shared_with_me = set()
            # Track who we've shared with
            shared_by_me = set()
            
            # Check folders in "Shared with me" - these are folders others created
            for folder in all_folders['shared_with_me']:
                name = folder['name']
                if '_to_' in name and name.startswith('syft_'):
                    parts = name.split('_to_')
                    if len(parts) == 2:
                        sender = parts[0].replace('syft_', '')
                        recipient_with_suffix = parts[1]
                        
                        # Remove suffixes
                        if '_outbox_inbox' in recipient_with_suffix:
                            recipient = recipient_with_suffix.replace('_outbox_inbox', '')
                        elif '_outbox' in recipient_with_suffix:
                            recipient = recipient_with_suffix.replace('_outbox', '')
                        elif '_pending' in recipient_with_suffix:
                            recipient = recipient_with_suffix.replace('_pending', '')
                        elif '_archive' in recipient_with_suffix:
                            recipient = recipient_with_suffix.replace('_archive', '')
                        else:
                            recipient = recipient_with_suffix.rsplit('_', 1)[0]
                        
                        # If they're sharing with us, track them
                        if recipient == self.my_email:
                            shared_with_me.add(sender)
            
            # Check if SyftBoxTransportService exists using cache
            syftbox_id = self._get_syftbox_folder_id()
            
            if syftbox_id:
                # Get folders inside SyftBoxTransportService
                try:
                    results = self.service.files().list(
                        q=f"'{syftbox_id}' in parents and name contains 'syft_' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                        fields="files(name)"
                    ).execute()
                    
                    for folder in results.get('files', []):
                        name = folder['name']
                        # Look for folders we created (either outgoing or archive for incoming)
                        if name.startswith(f'syft_{self.my_email}_to_'):
                            # This is our outgoing folder
                            parts = name.split('_to_')
                            if len(parts) == 2:
                                email_with_suffix = parts[1]
                                
                                # Remove suffixes
                                if '_outbox_inbox' in email_with_suffix:
                                    email_part = email_with_suffix.replace('_outbox_inbox', '')
                                elif '_outbox' in email_with_suffix:
                                    email_part = email_with_suffix.replace('_outbox', '')
                                elif '_pending' in email_with_suffix:
                                    email_part = email_with_suffix.replace('_pending', '')
                                elif '_archive' in email_with_suffix:
                                    email_part = email_with_suffix.replace('_archive', '')
                                else:
                                    email_part = email_with_suffix.rsplit('_', 1)[0]
                                
                                shared_by_me.add(email_part)
                        elif '_to_' in name and name.endswith(f'_to_{self.my_email}_archive'):
                            # This is an archive folder we created for someone else's messages
                            parts = name.split('_to_')
                            if len(parts) == 2:
                                sender = parts[0].replace('syft_', '')
                                # We have an archive for them, so we've reciprocated
                                shared_by_me.add(sender)
                except:
                    pass
            
            # Friend requests = people who shared with us but we haven't shared back
            friend_requests = shared_with_me - shared_by_me
            
            return sorted(list(friend_requests))
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error listing friend requests: {e}")
            return []
    
    def _list_syft_folders(self, print_summary: bool = False) -> Dict[str, List[Dict]]:
        """
        List all folders starting with 'syft_' in both My Drive and Shared with me
        
        Args:
            print_summary: Whether to print a summary of found folders (default: False)
            
        Returns:
            Dictionary with 'my_drive' and 'shared_with_me' lists
        """
        self._ensure_authenticated()
        
        result = {
            'my_drive': [],
            'shared_with_me': []
        }
        
        try:
            # First, find all syft_ folders in My Drive
            if print_summary:
                print("🔍 Searching for syft_ folders in My Drive...")
            my_drive_results = self.service.files().list(
                q="name contains 'syft_' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name, parents, permissions, owners)",
                pageSize=100
            ).execute()
            
            for folder in my_drive_results.get('files', []):
                # Only include folders that START with syft_
                if not folder['name'].startswith('syft_'):
                    continue
                    
                # Get parent folder name
                parent_name = "root"
                if folder.get('parents'):
                    try:
                        parent = self.service.files().get(
                            fileId=folder['parents'][0],
                            fields='name'
                        ).execute()
                        parent_name = parent.get('name', 'unknown')
                    except:
                        parent_name = "unknown"
                
                folder_info = {
                    'id': folder['id'],
                    'name': folder['name'],
                    'parent': parent_name,
                    'owner': folder.get('owners', [{}])[0].get('emailAddress', 'unknown')
                }
                result['my_drive'].append(folder_info)
            
            # Now search in Shared with me
            if print_summary:
                print("\n🔍 Searching for syft_ folders in Shared with me...")
            shared_results = self.service.files().list(
                q="name contains 'syft_' and mimeType='application/vnd.google-apps.folder' and sharedWithMe and trashed=false",
                fields="files(id, name, permissions, owners)",
                pageSize=100
            ).execute()
            
            for folder in shared_results.get('files', []):
                # Only include folders that START with syft_
                if not folder['name'].startswith('syft_'):
                    continue
                    
                folder_info = {
                    'id': folder['id'],
                    'name': folder['name'],
                    'owner': folder.get('owners', [{}])[0].get('emailAddress', 'unknown'),
                    'shared': True
                }
                result['shared_with_me'].append(folder_info)
            
            # Print summary if requested
            if print_summary and self.verbose:
                print(f"\n📁 Found {len(result['my_drive'])} syft_ folders in My Drive:")
                for folder in result['my_drive']:
                    print(f"   - {folder['name']}")
                    print(f"     Parent: {folder['parent']}")
                    print(f"     Owner: {folder['owner']}")
                    print(f"     ID: {folder['id']}")
                
                print(f"\n🤝 Found {len(result['shared_with_me'])} syft_ folders in Shared with me:")
                for folder in result['shared_with_me']:
                    print(f"   - {folder['name']}")
                    print(f"     Owner: {folder['owner']}")
                    print(f"     ID: {folder['id']}")
                
                # Check for incoming channels without shortcuts
                if result['shared_with_me']:
                    print("\n💡 Incoming channels that might need shortcuts:")
                    for folder in result['shared_with_me']:
                        if '_to_' in folder['name'] and self.my_email:
                            if f"_to_{self.my_email}_" in folder['name']:
                                print(f"   - {folder['name']} (from {folder['owner']})")
            
            return result
            
        except HttpError as e:
            if print_summary:
                print(f"❌ Error listing syft folders: {e}")
            return result
    
    def _create_shortcuts_for_friend(self, friend_email: str, syftbox_id: Optional[str] = None) -> Dict[str, int]:
        """
        Create shortcuts in SyftBoxTransportService for folders shared by a specific friend
        
        Args:
            friend_email: Email of the friend whose folders to create shortcuts for
            syftbox_id: Optional SyftBoxTransportService folder ID (will find if not provided)
            
        Returns:
            Dictionary with counts of shortcuts created, skipped, and failed
        """
        self._ensure_authenticated()
        
        results = {
            'created': 0,
            'skipped': 0,
            'failed': 0
        }
        
        try:
            # Get or find SyftBox folder
            if not syftbox_id:
                syftbox_id = self.setup_syftbox()
                if not syftbox_id:
                    return results
            
            # Find folders shared by this friend
            shared_results = self.service.files().list(
                q=f"name contains 'syft_{friend_email}_to_' and mimeType='application/vnd.google-apps.folder' and sharedWithMe and trashed=false",
                fields="files(id, name)",
                pageSize=100
            ).execute()
            
            # Get existing shortcuts in SyftBox to avoid duplicates
            existing_shortcuts = {}
            try:
                existing_results = self.service.files().list(
                    q=f"'{syftbox_id}' in parents and mimeType='application/vnd.google-apps.shortcut' and trashed=false",
                    fields="files(name, shortcutDetails)"
                ).execute()
                
                for shortcut in existing_results.get('files', []):
                    target_id = shortcut.get('shortcutDetails', {}).get('targetId')
                    if target_id:
                        existing_shortcuts[target_id] = shortcut['name']
            except:
                pass
            
            # Create shortcuts for each shared folder
            for folder in shared_results.get('files', []):
                if not folder['name'].startswith('syft_'):
                    continue
                    
                folder_id = folder['id']
                folder_name = folder['name']
                
                # Check if shortcut already exists
                if folder_id in existing_shortcuts:
                    results['skipped'] += 1
                    continue
                
                # Create shortcut
                try:
                    shortcut_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.shortcut',
                        'parents': [syftbox_id],
                        'shortcutDetails': {
                            'targetId': folder_id
                        }
                    }
                    
                    self.service.files().create(
                        body=shortcut_metadata,
                        fields='id'
                    ).execute()
                    
                    results['created'] += 1
                    
                except Exception as e:
                    results['failed'] += 1
            
            return results
            
        except Exception as e:
            return results
    
    def _create_shortcuts_for_shared_folders(self, verbose: bool = True) -> Dict[str, int]:
        """
        Create shortcuts in SyftBoxTransportService for all syft_ folders in 'Shared with me'
        
        Args:
            verbose: Whether to print detailed progress messages (default: True)
        
        Returns:
            Dictionary with counts of shortcuts created, skipped, and failed
        """
        self._ensure_authenticated()
        
        results = {
            'created': 0,
            'skipped': 0,
            'failed': 0
        }
        
        try:
            # First ensure SyftBox exists
            syftbox_id = self.setup_syftbox()
            if not syftbox_id:
                print("❌ Could not create/find SyftBoxTransportService folder")
                return results
            
            # Get list of all syft_ folders (default is silent)
            all_folders = self._list_syft_folders()
            shared_folders = all_folders['shared_with_me']
            
            if not shared_folders:
                if verbose:
                    print("✅ No shared syft_ folders found that need shortcuts")
                return results
            
            if verbose:
                print(f"\n🔗 Creating shortcuts for {len(shared_folders)} shared folders...")
            
            # Get existing shortcuts in SyftBoxTransportService to avoid duplicates
            existing_shortcuts = {}
            try:
                existing = self.service.files().list(
                    q=f"'{syftbox_id}' in parents and mimeType='application/vnd.google-apps.shortcut' and trashed=false",
                    fields="files(id, name, shortcutDetails)"
                ).execute()
                
                for shortcut in existing.get('files', []):
                    details = shortcut.get('shortcutDetails', {})
                    target_id = details.get('targetId')
                    if target_id:
                        existing_shortcuts[target_id] = shortcut['name']
            except:
                pass
            
            # Create shortcuts for each shared folder
            for folder in shared_folders:
                folder_name = folder['name']
                folder_id = folder['id']
                folder_owner = folder['owner']
                
                # Check if shortcut already exists
                if folder_id in existing_shortcuts:
                    if verbose:
                        print(f"⏭️  Skipping {folder_name} - shortcut already exists")
                    results['skipped'] += 1
                    continue
                
                # Check if folder name already exists in SyftBox (non-shortcut)
                try:
                    existing_folder = self.service.files().list(
                        q=f"name='{folder_name}' and '{syftbox_id}' in parents and trashed=false",
                        fields="files(id, mimeType)"
                    ).execute()
                    
                    if existing_folder.get('files'):
                        if verbose:
                            print(f"⏭️  Skipping {folder_name} - folder/shortcut with same name already exists")
                        results['skipped'] += 1
                        continue
                except:
                    pass
                
                # Create the shortcut
                try:
                    shortcut_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.shortcut',
                        'parents': [syftbox_id],
                        'shortcutDetails': {
                            'targetId': folder_id,
                            'targetMimeType': 'application/vnd.google-apps.folder'
                        }
                    }
                    
                    shortcut = self.service.files().create(
                        body=shortcut_metadata,
                        fields='id, name'
                    ).execute()
                    
                    if verbose:
                        print(f"✅ Created shortcut for {folder_name} (from {folder_owner})")
                    results['created'] += 1
                    
                except HttpError as e:
                    if verbose:
                        print(f"❌ Failed to create shortcut for {folder_name}: {e}")
                    results['failed'] += 1
            
            # Summary - only show if verbose
            if verbose and (results['created'] > 0 or results['failed'] > 0 or results['skipped'] > 0):
                print(f"\n📊 Shortcut creation summary:")
                print(f"   ✅ Created: {results['created']}")
                print(f"   ⏭️  Skipped: {results['skipped']}")
                print(f"   ❌ Failed: {results['failed']}")
                
                if results['created'] > 0:
                    print(f"\n🎉 Successfully linked {results['created']} shared folders to SyftBoxTransportService!")
                    print(f"🔗 View in Google Drive: https://drive.google.com/drive/folders/{syftbox_id}")
            
            return results
            
        except HttpError as e:
            print(f"❌ Error creating shortcuts: {e}")
            return results

# Convenience function for quick setup
    # ========== Google Sheets Transport Methods ==========
    
    def _archive_sheet_messages_async(self, sheet_id: str, row_numbers: List[int]):
        """
        Move downloaded messages to Archive tab in background
        
        Args:
            sheet_id: The spreadsheet ID
            row_numbers: List of row numbers to archive
        """
        # print("ARCHIVE-1 " + str(time.time()))
        def archive_worker():
            # print("ARCHIVE-2 " + str(time.time()))
            try:
                # print("ARCHIVE-3 " + str(time.time()))
                sheets_service = build('sheets', 'v4', credentials=self.creds)
                # print("ARCHIVE-4 " + str(time.time()))
                
                # First, ensure Archive tab exists
                try:
                    # Check cache for spreadsheet info
                    # print("ARCHIVE-5 " + str(time.time()))
                    spreadsheet = None
                    if sheet_id in self._spreadsheet_info_cache and sheet_id in self._spreadsheet_info_cache_time:
                        cache_age_minutes = (datetime.now() - self._spreadsheet_info_cache_time[sheet_id]).total_seconds() / 60
                        if cache_age_minutes < 60:  # Cache valid for 1 hour
                            spreadsheet = self._spreadsheet_info_cache[sheet_id]
                    
                    # If not cached, fetch from API
                    if not spreadsheet:
                        # print("ARCHIVE-6 " + str(time.time()))
                        spreadsheet = sheets_service.spreadsheets().get(
                            spreadsheetId=sheet_id,
                            fields='sheets.properties'
                        ).execute()
                        # print("ARCHIVE-7 " + str(time.time()))
                        # Cache the result
                        self._spreadsheet_info_cache[sheet_id] = spreadsheet
                        self._spreadsheet_info_cache_time[sheet_id] = datetime.now()
                    
                    # Check if Archive sheet exists and get messages sheet ID
                    archive_exists = False
                    messages_sheet_id = None
                    for sheet in spreadsheet.get('sheets', []):
                        if sheet['properties']['title'] == 'archive':
                            archive_exists = True
                        elif sheet['properties']['title'] == 'messages':
                            messages_sheet_id = sheet['properties']['sheetId']
                    
                    # Create Archive sheet if it doesn't exist
                    # print("ARCHIVE-8 " + str(time.time()))
                    if not archive_exists:
                        request = {
                            'addSheet': {
                                'properties': {
                                    'title': 'archive',
                                    'gridProperties': {
                                        'columnCount': 4,
                                        'frozenRowCount': 1
                                    }
                                }
                            }
                        }
                        
                        # print("ARCHIVE-9 " + str(time.time()))
                        sheets_service.spreadsheets().batchUpdate(
                            spreadsheetId=sheet_id,
                            body={'requests': [request]}
                        ).execute()
                        # print("ARCHIVE-10 " + str(time.time()))
                        
                        # No header row in archive either
                        
                        if self.verbose:
                            print(f"   📁 Created Archive tab")
                        
                        # Invalidate the spreadsheet cache since we modified it
                        if sheet_id in self._spreadsheet_info_cache:
                            del self._spreadsheet_info_cache[sheet_id]
                            del self._spreadsheet_info_cache_time[sheet_id]
                
                except Exception as e:
                    print(f"   ⚠️  Error creating archive tab: {e}")
                    return
                
                # Get the rows to archive
                # print("ARCHIVE-11 " + str(time.time()))
                ranges = [f'messages!A{row}:E{row}' for row in sorted(row_numbers)]
                
                # Batch get all rows
                # print("ARCHIVE-12 " + str(time.time()))
                result = sheets_service.spreadsheets().values().batchGet(
                    spreadsheetId=sheet_id,
                    ranges=ranges
                ).execute()
                # print("ARCHIVE-13 " + str(time.time()))
                
                rows_to_archive = []
                for value_range in result.get('valueRanges', []):
                    values = value_range.get('values', [])
                    if values:
                        rows_to_archive.extend(values)
                
                if rows_to_archive:
                    # Append to archive
                    # print("ARCHIVE-14 " + str(time.time()))
                    sheets_service.spreadsheets().values().append(
                        spreadsheetId=sheet_id,
                        range='archive!A:D',
                        valueInputOption='USER_ENTERED',
                        insertDataOption='INSERT_ROWS',
                        body={'values': rows_to_archive}
                    ).execute()
                    # print("ARCHIVE-15 " + str(time.time()))
                    
                    # Clear the original rows - batch all deletes into one request
                    if messages_sheet_id is not None:
                        # Sort row numbers and group consecutive rows for efficient deletion
                        sorted_rows = sorted(row_numbers, reverse=True)
                        delete_requests = []
                        
                        # Create a delete request for each row (from bottom to top)
                        for row_num in sorted_rows:
                            delete_requests.append({
                                'deleteDimension': {
                                    'range': {
                                        'sheetId': messages_sheet_id,
                                        'dimension': 'ROWS',
                                        'startIndex': row_num - 1,  # 0-based
                                        'endIndex': row_num
                                    }
                                }
                            })
                        
                        # Execute all deletes in a single batch
                        if delete_requests:
                            # print("ARCHIVE-16 " + str(time.time()))
                            sheets_service.spreadsheets().batchUpdate(
                                spreadsheetId=sheet_id,
                                body={'requests': delete_requests}
                            ).execute()
                            # print("ARCHIVE-17 " + str(time.time()))
                        
                        if self.verbose:
                            print(f"   🗄️  Archived {len(rows_to_archive)} messages to Archive tab")
                    else:
                        print(f"   ⚠️  Could not find messages sheet ID for archiving")
                        
            except Exception as e:
                print(f"   ⚠️  Error archiving messages: {e}")
        
        # Start background thread with a small delay to avoid GIL contention
        # print("ARCHIVE-18 " + str(time.time()))
        def delayed_start():
            time.sleep(0.1)  # Small delay to let main operation complete
            archive_worker()
        
        thread = threading.Thread(target=delayed_start, daemon=True)
        thread.start()
        # print("ARCHIVE-19 " + str(time.time()))
    
    def _find_message_sheet(self, sheet_name: str, from_email: str = None) -> Optional[str]:
        """
        Find an existing Google Sheet for messages (without creating)
        
        Args:
            sheet_name: Name of the sheet to find
            from_email: Email of the sender (to search in shared files)
            
        Returns:
            Spreadsheet ID if found, None otherwise
        """
        # print("FINDSHEET-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("FINDSHEET-2 " + str(time.time()))
        
        # Check cache first
        # print("FINDSHEET-3 " + str(time.time()))
        cache_key = f"{sheet_name}:{from_email or 'none'}"
        if cache_key in self._sheet_cache and cache_key in self._sheet_cache_time:
            cache_age_minutes = (datetime.now() - self._sheet_cache_time[cache_key]).total_seconds() / 60
            if cache_age_minutes < 60:  # Cache valid for 1 hour
                cached_id = self._sheet_cache[cache_key]
                if self.verbose:
                    print(f"   📋 Using cached sheet ID: {cached_id}")
                return cached_id
        
        try:
            # First, search in SyftBox folder (for shortcuts or owned sheets)
        # print("FINDSHEET-4 " + str(time.time()))
            syftbox_id = self._get_syftbox_folder_id()
        # print("FINDSHEET-5 " + str(time.time()))
            if syftbox_id:
                # Search for existing sheet or shortcut
        # print("FINDSHEET-6 " + str(time.time()))
                results = self.service.files().list(
                    q=f"name='{sheet_name}' and '{syftbox_id}' in parents and trashed=false",
                    fields="files(id, mimeType, shortcutDetails)",
                    pageSize=1
                ).execute()
        # print("FINDSHEET-7 " + str(time.time()))
                
                if results.get('files'):
                    file_info = results['files'][0]
                    # If it's a shortcut, return the target ID
                    if file_info.get('shortcutDetails'):
                        sheet_id = file_info['shortcutDetails']['targetId']
                    else:
                        sheet_id = file_info['id']
                    
                    # Cache the result
                    self._sheet_cache[cache_key] = sheet_id
                    self._sheet_cache_time[cache_key] = datetime.now()
        # print("FINDSHEET-8 " + str(time.time()))
                    return sheet_id
            
            # If not found in SyftBox folder and we have a sender email, 
            # search in "Shared with me" from that specific user
        # print("FINDSHEET-9 " + str(time.time()))
            if from_email:
                if self.verbose:
                    print(f"   🔍 Searching in files shared by {from_email}...")
                
                # Search for sheets shared by the sender
        # print("FINDSHEET-10 " + str(time.time()))
                results = self.service.files().list(
                    q=f"name='{sheet_name}' and '{from_email}' in owners and mimeType='application/vnd.google-apps.spreadsheet' and sharedWithMe and trashed=false",
                    fields="files(id, name)",
                    pageSize=1
                ).execute()
        # print("FINDSHEET-11 " + str(time.time()))
                
                if results.get('files'):
                    shared_sheet_id = results['files'][0]['id']
                    if self.verbose:
                        print(f"   ✅ Found shared sheet: {shared_sheet_id}")
                    
                    # Create a shortcut in SyftBox folder if we have one
                    if syftbox_id:
                        try:
                            shortcut_metadata = {
                                'name': sheet_name,
                                'mimeType': 'application/vnd.google-apps.shortcut',
                                'shortcutDetails': {
                                    'targetId': shared_sheet_id
                                },
                                'parents': [syftbox_id]
                            }
                            
                            shortcut = self.service.files().create(
                                body=shortcut_metadata,
                                fields='id'
                            ).execute()
                            
                            if self.verbose:
                                print(f"   🔗 Created shortcut in SyftBox folder")
                        except Exception as e:
                            if self.verbose:
                                print(f"   ⚠️  Could not create shortcut: {e}")
                    
                    # Cache the result
                    self._sheet_cache[cache_key] = shared_sheet_id
                    self._sheet_cache_time[cache_key] = datetime.now()
        # print("FINDSHEET-12 " + str(time.time()))
                    return shared_sheet_id
            
        # print("FINDSHEET-13 " + str(time.time()))
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error finding sheet: {e}")
            return None
    
    def _get_or_create_message_sheet(self, sheet_name: str, recipient_email: str = None) -> Optional[str]:
        """
        Get or create a Google Sheet for messages
        
        Args:
            sheet_name: Name of the sheet (e.g., syft_alice_to_bob_messages)
            recipient_email: Email of recipient to grant write access (optional)
            
        Returns:
            Spreadsheet ID if successful
        """
        # print("GETSHEET-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("GETSHEET-2 " + str(time.time()))
        
        # Check cache first for owned sheets
        cache_key = f"owned:{sheet_name}"
        if cache_key in self._sheet_cache and cache_key in self._sheet_cache_time:
            cache_age_minutes = (datetime.now() - self._sheet_cache_time[cache_key]).total_seconds() / 60
            if cache_age_minutes < 60:  # Cache valid for 1 hour
                cached_id = self._sheet_cache[cache_key]
                if self.verbose:
                    print(f"   📋 Using cached owned sheet ID: {cached_id}")
                return cached_id
        
        try:
            # First check if sheet already exists in SyftBox folder
            syftbox_id = self._get_syftbox_folder_id()
            if not syftbox_id:
                print("❌ SyftBox folder not found")
                return None
            # Search for existing sheet
            results = self.service.files().list(
                q=f"name='{sheet_name}' and '{syftbox_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
                fields="files(id)",
                pageSize=1
            ).execute()
            if results.get('files'):
                sheet_id = results['files'][0]['id']
                # Cache the result
                self._sheet_cache[cache_key] = sheet_id
                self._sheet_cache_time[cache_key] = datetime.now()
                return sheet_id
            # Create new sheet
            try:
                sheets_service = self._get_sheets_service()
            except Exception as e:
                print("❌ Google Sheets API not available. You may need to re-authenticate with sheets scope.")
                print("   Run: client = login(email, force_relogin=True)")
                return None
            spreadsheet = {
                'properties': {
                    'title': sheet_name
                },
                'sheets': [{
                    'properties': {
                        'title': 'messages',
                        'gridProperties': {
                            'columnCount': 4
                        }
                    },
                    # No initial data - no header row
                }]
            }
            # Create the spreadsheet
            sheet = sheets_service.spreadsheets().create(body=spreadsheet).execute()
            sheet_id = sheet['spreadsheetId']
            # Move to SyftBox folder
            self.service.files().update(
                fileId=sheet_id,
                addParents=syftbox_id,
                removeParents='root',
                fields='id, parents'
            ).execute()
            # Grant recipient write access if specified
            if recipient_email:
                try:
                    self._add_permission(sheet_id, recipient_email, role='writer', verbose=False)
                    if self.verbose:
                        print(f"   ✅ Granted write access to {recipient_email}")
                except Exception as e:
                    if self.verbose:
                        print(f"   ⚠️  Could not grant access to {recipient_email}: {e}")
            if self.verbose:
                print(f"📊 Created message sheet: {sheet_name}")
            
            # Cache the newly created sheet
            self._sheet_cache[cache_key] = sheet_id
            self._sheet_cache_time[cache_key] = datetime.now()
            
            return sheet_id
        except Exception as e:
            print(f"❌ Error creating sheet: {e}")
            return None
    
    def send_file_or_folder_via_sheets(self, path: str, recipient_email: str) -> bool:
        """
        Send a file or folder using Google Sheets as transport
        
        Args:
            path: Path to file/folder to send
            recipient_email: Recipient's email address
            
        Returns:
            True if successful
        """
        import base64
        # print("SEND-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("SEND-2 " + str(time.time()))
        if recipient_email.lower() not in [f.lower() for f in self.friends]:
            print(f"❌ {recipient_email} is not in your friends list")
            return False
        try:
            # print("SEND-5 " + str(time.time()))
            with tempfile.TemporaryDirectory() as temp_dir:
                # print("SEND-6 " + str(time.time()))
                # Prepare the message (shared logic)
                result = self._prepare_message(path, recipient_email, temp_dir)
                if not result:
                    return False
                
                message_id, archive_path, archive_size = result
                
                # Check size limit for sheets (50k char limit per cell)
                max_sheets_size = 37_500  # Conservative limit to stay under 50k chars after base64
                if archive_size > max_sheets_size:
                    print(f"❌ File too large for sheets transport: {archive_size:,} bytes (limit: {max_sheets_size:,} bytes)")
                    print(f"   Consider using send_file_or_folder() instead for larger files")
                    return False
                
                # print("SEND-18 " + str(time.time()))
                # Read and encode archive
                # print("SEND-19 " + str(time.time()))
                with open(archive_path, 'rb') as f:
                    archive_data = f.read()
                # print("SEND-20 " + str(time.time()))
                # Base64 encode for sheets
                encoded_data = base64.b64encode(archive_data).decode('utf-8')
                # print("SEND-21 " + str(time.time()))
                # Get or create sheet (permissions are handled in the method)
                # print("SEND-22 " + str(time.time()))
                sheet_name = f"syft_{self.my_email}_to_{recipient_email}_messages"
                # print("SEND-23 " + str(time.time()))
                sheet_id = self._get_or_create_message_sheet(sheet_name, recipient_email)
                # print("SEND-24 " + str(time.time()))
                if not sheet_id:
                    return False
                # Prepare row data
                # print("SEND-25 " + str(time.time()))
                timestamp = datetime.now().isoformat()
                # print("SEND-26 " + str(time.time()))
                message_data = {
                    'values': [[
                        timestamp,
                        message_id,
                        str(len(archive_data)),
                        encoded_data
                    ]]
                }
                # print("SEND-27 " + str(time.time()))
                # Append to sheet in one API call
                # print("SEND-28 " + str(time.time()))
                sheets_service = self._get_sheets_service()
                # print("SEND-29 " + str(time.time()))
                sheets_service.spreadsheets().values().append(
                    spreadsheetId=sheet_id,
                    range='messages!A:D',
                    valueInputOption='USER_ENTERED',
                    insertDataOption='INSERT_ROWS',
                    body=message_data
                ).execute()
                # print("SEND-30 " + str(time.time()))
                if self.verbose:
                    print(f"📊 Sent message via sheets: {message_id}")
                    print(f"   Size: {len(archive_data)} bytes")
                # print("SEND-31 " + str(time.time()))
                return True
                
        except Exception as e:
            print(f"❌ Error sending via sheets: {e}")
            return False
    
    def update_inbox_from_sheets(self, inbox_dir: str = None) -> Dict[str, List[str]]:
        """
        Check all friend sheets for new messages
        
        Args:
            inbox_dir: Directory to extract messages to
            
        Returns:
            Dict mapping friend emails to downloaded message IDs
        """
        import base64
        # print("UPDATEINBOX-1 " + str(time.time()))
        self._ensure_authenticated()
        # print("UPDATEINBOX-2 " + str(time.time()))
        # Set default inbox directory
        if inbox_dir is None:
            # print("UPDATEINBOX-3 " + str(time.time()))
            syftbox_dir = self.get_syftbox_directory()
            # print("UPDATEINBOX-4 " + str(time.time()))
            if syftbox_dir is None:
                print("❌ Could not determine SyftBox directory")
                return {}
            inbox_dir = str(syftbox_dir / "inbox")
        # print("UPDATEINBOX-5 " + str(time.time()))
        os.makedirs(inbox_dir, exist_ok=True)
        if not self.friends:
            return {}
        downloaded_messages = {}
        # print("UPDATEINBOX-6 " + str(time.time()))
        sheets_service = self._get_sheets_service()
        # print("UPDATEINBOX-7 " + str(time.time()))
        # Build batch request for all friends
        # print("UPDATEINBOX-8 " + str(time.time()))
        ranges = []
        friend_sheets = {}
        for friend_email in self.friends:
            sheet_name = f"syft_{friend_email}_to_{self.my_email}_messages"
            if self.verbose:
                print(f"🔍 Looking for sheet: {sheet_name}")
            # Pass the friend's email to search in shared files
            # print("UPDATEINBOX-9 " + str(time.time()))
            sheet_id = self._find_message_sheet(sheet_name, from_email=friend_email)
            # print("UPDATEINBOX-10 " + str(time.time()))
            if sheet_id:
                ranges.append(f"messages!A:E")
                friend_sheets[friend_email] = sheet_id
                if self.verbose:
                    print(f"   ✅ Found sheet ID: {sheet_id}")
            else:
                if self.verbose:
                    print(f"   ❌ Sheet not found")
        if not ranges:
            return {}
        # print("UPDATEINBOX-11 " + str(time.time()))
        try:
            # Single batch get for all sheets
            if self.verbose:
                print(f"📊 Checking {len(friend_sheets)} friend sheets...")
            for friend_email, sheet_id in friend_sheets.items():
                try:
                    # Get all rows from this friend's sheet
                    # print("UPDATEINBOX-12 " + str(time.time()))
                    result = sheets_service.spreadsheets().values().get(
                        spreadsheetId=sheet_id,
                        range='messages!A:D'
                    ).execute()
                    # print("UPDATEINBOX-13 " + str(time.time()))
                    rows = result.get('values', [])
                    if self.verbose:
                        if len(rows) == 0:
                            print(f"   📭 No messages")
                        else:
                            print(f"   📋 Found {len(rows)} message(s)")
                    if len(rows) == 0:  # No messages
                        continue
                    # Process all messages (no header to skip)
                    # print("UPDATEINBOX-14 " + str(time.time()))
                    pending_messages = []
                    for i, row in enumerate(rows, start=1):
                        if self.verbose and len(row) >= 2:
                            print(f"   Row {i}: msg_id = '{row[1] if len(row) > 1 else 'N/A'}'")
                        if len(row) >= 4:  # timestamp, msg_id, size, data
                            pending_messages.append((i, row))
                    if pending_messages:
                        if self.verbose:
                            print(f"\n📬 Found {len(pending_messages)} message(s) from {friend_email}")
                        downloaded_messages[friend_email] = []
                        rows_to_archive = []
                        # print("UPDATEINBOX-15 " + str(time.time()))
                        for row_num, row in pending_messages:
                            timestamp, msg_id, size, encoded_data = row[:4]
                            # Check if already downloaded
                            local_path = os.path.join(inbox_dir, msg_id)
                            if os.path.exists(local_path):
                                if self.verbose:
                                    print(f"   ⏭️  Skipping {msg_id} - already downloaded")
                                continue
                            try:
                                if self.verbose:
                                    print(f"   📥 Processing {msg_id}...")
                                # Decode and extract
                                # print("UPDATEINBOX-16 " + str(time.time()))
                                archive_data = base64.b64decode(encoded_data)
                                # print("UPDATEINBOX-17 " + str(time.time()))
                                # Save to temp file and extract
                                with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
                                    tmp.write(archive_data)
                                    tmp_path = tmp.name
                                # Extract archive
                                # print("UPDATEINBOX-18 " + str(time.time()))
                                with tarfile.open(tmp_path, 'r:gz') as tar:
                                    tar.extractall(inbox_dir)
                                # print("UPDATEINBOX-19 " + str(time.time()))
                                os.unlink(tmp_path)
                                
                                # Pre-cache metadata if it's JSON
                                extracted_path = Path(inbox_dir) / msg_id
                                json_metadata_path = extracted_path / "metadata.json"
                                if json_metadata_path.exists():
                                    try:
                                        with open(json_metadata_path, 'r') as f:
                                            self._metadata_cache[msg_id] = json.load(f)
                                    except:
                                        pass  # Ignore cache errors
                                
                                downloaded_messages[friend_email].append(msg_id)
                                rows_to_archive.append(row_num)
                                if self.verbose:
                                    print(f"   ✅ Downloaded {msg_id}")
                                    
                            except Exception as e:
                                if self.verbose:
                                    print(f"   ❌ Error processing {msg_id}: {e}")
                        
                        # Dispatch archiving task if we downloaded any messages
                        if rows_to_archive:
                            if self.verbose:
                                print(f"   🗄️  Dispatching archive task for {len(rows_to_archive)} messages...")
                            # print("UPDATEINBOX-20 " + str(time.time()))
                            self._archive_sheet_messages_async(sheet_id, rows_to_archive)
                            # print("UPDATEINBOX-21 " + str(time.time()))
                    
                except Exception as e:
                    if self.verbose:
                        print(f"   ⚠️  Error checking {friend_email}: {e}")
            
            # print("UPDATEINBOX-22 " + str(time.time()))
            return downloaded_messages
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error updating from sheets: {e}")
            return {}
    
    def launch_watcher_sender(self) -> Dict[str, any]:
        """
        Launch a background file watcher that automatically sends file changes to all friends
        
        Returns:
            Dict with status, message, and server URL
        """
        import threading
        import time
        
        result = {"status": "pending", "message": "Launching watcher...", "url": None}
        
        def _launch_watcher():
            try:
                # Import here to avoid circular dependencies
                from . import watcher
                
                # Create the watcher endpoint
                server = watcher.create_watcher_sender_endpoint(self.my_email)
                
                # Update result
                result["status"] = "started"
                result["message"] = f"Watcher launched successfully for {self.my_email}"
                result["url"] = server.url
                
                if self.verbose:
                    print(f"✅ Watcher launched at: {server.url}")
                    
            except Exception as e:
                result["status"] = "error"
                result["message"] = f"Failed to launch watcher: {str(e)}"
                if self.verbose:
                    print(f"❌ Failed to launch watcher: {e}")
        
        # Launch in background thread
        thread = threading.Thread(target=_launch_watcher, daemon=True)
        thread.start()
        
        # Give it a moment to start
        time.sleep(0.1)
        
        return result
    
    def terminate_watcher_sender(self) -> Dict[str, any]:
        """
        Terminate the background file watcher
        
        Returns:
            Dict with status and message
        """
        import threading
        import time
        
        result = {"status": "pending", "message": "Terminating watcher..."}
        
        def _terminate_watcher():
            try:
                # Import here to avoid circular dependencies
                from . import watcher
                
                # Destroy the watcher endpoint
                success = watcher.destroy_watcher_sender_endpoint(self.my_email)
                
                if success:
                    result["status"] = "terminated"
                    result["message"] = f"Watcher terminated successfully for {self.my_email}"
                    if self.verbose:
                        print(f"✅ Watcher terminated for {self.my_email}")
                else:
                    result["status"] = "not_found"
                    result["message"] = f"No watcher found for {self.my_email}"
                    if self.verbose:
                        print(f"⚠️  No watcher found for {self.my_email}")
                        
            except Exception as e:
                result["status"] = "error"
                result["message"] = f"Failed to terminate watcher: {str(e)}"
                if self.verbose:
                    print(f"❌ Failed to terminate watcher: {e}")
        
        # Launch in background thread
        thread = threading.Thread(target=_terminate_watcher, daemon=True)
        thread.start()
        
        # Give it a moment to complete
        time.sleep(0.1)
        
        return result
    
    def launch_receiver(self, interval_seconds: float = 1.0) -> Dict[str, any]:
        """
        Launch a background receiver that automatically processes incoming messages
        
        Args:
            interval_seconds: How often to run sync operations (default: 1 second)
            
        Returns:
            Dict with status, message, and server URL
        """
        import threading
        import time
        
        result = {"status": "pending", "message": "Launching receiver...", "url": None}
        
        def _launch_receiver():
            try:
                # Import here to avoid circular dependencies
                from . import receiver
                
                # Create the receiver endpoint
                server = receiver.create_receiver_endpoint(self.my_email, interval_seconds)
                
                # Update result
                result["status"] = "started"
                result["message"] = f"Receiver launched successfully for {self.my_email} (interval: {interval_seconds}s)"
                result["url"] = server.url
                
                if self.verbose:
                    print(f"✅ Receiver launched at: {server.url}")
                    
            except Exception as e:
                result["status"] = "error"
                result["message"] = f"Failed to launch receiver: {str(e)}"
                if self.verbose:
                    print(f"❌ Failed to launch receiver: {e}")
        
        # Launch in background thread
        thread = threading.Thread(target=_launch_receiver, daemon=True)
        thread.start()
        
        # Give it a moment to start
        time.sleep(0.1)
        
        return result
    
    def terminate_receiver(self) -> Dict[str, any]:
        """
        Terminate the background receiver
        
        Returns:
            Dict with status and message
        """
        import threading
        import time
        
        result = {"status": "pending", "message": "Terminating receiver..."}
        
        def _terminate_receiver():
            try:
                # Import here to avoid circular dependencies
                from . import receiver
                
                # Destroy the receiver endpoint
                success = receiver.destroy_receiver_endpoint(self.my_email)
                
                if success:
                    result["status"] = "terminated"
                    result["message"] = f"Receiver terminated successfully for {self.my_email}"
                    if self.verbose:
                        print(f"✅ Receiver terminated for {self.my_email}")
                else:
                    result["status"] = "not_found"
                    result["message"] = f"No receiver found for {self.my_email}"
                    if self.verbose:
                        print(f"⚠️  No receiver found for {self.my_email}")
                        
            except Exception as e:
                result["status"] = "error"
                result["message"] = f"Failed to terminate receiver: {str(e)}"
                if self.verbose:
                    print(f"❌ Failed to terminate receiver: {e}")
        
        # Launch in background thread
        thread = threading.Thread(target=_terminate_receiver, daemon=True)
        thread.start()
        
        # Give it a moment to complete
        time.sleep(0.1)
        
        return result
    
    def get_receiver_stats(self) -> Dict[str, any]:
        """
        Get statistics from the running receiver
        
        Returns:
            Dict with receiver statistics or None if not running
        """
        try:
            from . import receiver
            return receiver.get_receiver_stats(self.my_email)
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to get receiver stats: {e}")
            return None


def create_gdrive_client(email_or_auth_method: str = "auto", verbose: bool = True, force_relogin: bool = False) -> GDriveUnifiedClient:
    """
    Create and authenticate a GDrive client
    
    Args:
        email_or_auth_method: Email address (e.g. "user@gmail.com") or auth method ("auto", "colab", "credentials")
        verbose: Whether to print status messages
        force_relogin: Force fresh authentication even if token exists (default: False)
        
    Returns:
        Authenticated GDriveUnifiedClient
    """
    # Check if it's an email address
    if "@" in email_or_auth_method:
        client = GDriveUnifiedClient(auth_method="credentials", email=email_or_auth_method, verbose=verbose, force_relogin=force_relogin)
    else:
        client = GDriveUnifiedClient(auth_method=email_or_auth_method, verbose=verbose, force_relogin=force_relogin)
    
    if client.authenticate(known_email=email_or_auth_method):
        return client
    else:
        raise RuntimeError("Failed to authenticate")