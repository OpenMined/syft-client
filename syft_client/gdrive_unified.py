"""
Unified Google Drive client with multiple authentication methods
"""

import os
import json
import io
from pathlib import Path
from typing import Optional, List, Dict, Union

# Try importing Colab auth
try:
    from google.colab import auth as colab_auth
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

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
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
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
        
    def __repr__(self) -> str:
        """Pretty representation of the client"""
        if not self.authenticated:
            return f"<GDriveUnifiedClient(not authenticated)>"
        
        # Get SyftBox info
        syftbox_info = "not created"
        try:
            results = self.service.files().list(
                q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            if results.get('files'):
                syftbox_info = "✓ created"
        except:
            pass
        
        # Count communication channels
        channel_count = 0
        if syftbox_info == "✓ created":
            try:
                # Search for syft_ folders
                results = self.service.files().list(
                    q="name contains 'syft_' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(name)"
                ).execute()
                
                # Count unique channels (outgoing only)
                channels = set()
                for file in results.get('files', []):
                    name = file['name']
                    if name.startswith('syft_') and '_to_' in name and (name.endswith('_pending') or name.endswith('_outbox_inbox')):
                        # Extract channel identifier
                        parts = name.split('_to_')
                        if len(parts) == 2:
                            channel = parts[1].rsplit('_', 1)[0]  # Remove suffix
                            channels.add(channel)
                channel_count = len(channels)
            except:
                pass
        
        auth_method = "wallet" if self.target_email else self.auth_method
        
        return (
            f"<GDriveUnifiedClient(\n"
            f"  email='{self.my_email}',\n"
            f"  auth_method='{auth_method}',\n"
            f"  syftbox={syftbox_info},\n"
            f"  channels={channel_count}\n"
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
            results = self.service.files().list(
                q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            if results.get('files'):
                syftbox_id = results['files'][0]['id']
                syftbox_status = "✅ Created"
        except:
            pass
        
        # Count communication channels
        channel_count = 0
        channel_list = []
        if syftbox_id:
            try:
                # Search for syft_ folders
                results = self.service.files().list(
                    q="name contains 'syft_' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(name)"
                ).execute()
                
                # Count unique channels (outgoing only)
                channels = set()
                for file in results.get('files', []):
                    name = file['name']
                    if name.startswith('syft_') and '_to_' in name and (name.endswith('_pending') or name.endswith('_outbox_inbox')):
                        # Extract channel identifier
                        parts = name.split('_to_')
                        if len(parts) == 2:
                            channel = parts[1].rsplit('_', 1)[0]  # Remove suffix
                            channels.add(channel)
                channel_count = len(channels)
                channel_list = sorted(list(channels))
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
        
        html += f"""
                <tr>
                    <td style="padding: 5px 10px 5px 0; font-weight: bold; color: #555;">Channels:</td>
                    <td style="padding: 5px;">{channel_count} active</td>
                </tr>
            </table>
        """
        
        if channel_list:
            html += """
            <details style="margin-top: 10px;">
                <summary style="cursor: pointer; color: #1a73e8;">Show channels</summary>
                <ul style="margin: 5px 0; padding-left: 20px;">
            """
            for channel in channel_list:
                html += f"<li style='color: #666;'>{channel}</li>"
            html += """
                </ul>
            </details>
            """
        
        html += "</div>"
        
        return html
        
    def authenticate(self) -> bool:
        """
        Authenticate using the appropriate method
        
        Returns:
            bool: True if authentication successful
        """
        # If email is provided, try to use stored credentials first
        if self.target_email:
            # Import here to avoid circular dependency
            from .auth import _get_stored_credentials_path
            wallet_creds = _get_stored_credentials_path(self.target_email)
            if wallet_creds:
                self.credentials_file = wallet_creds
                return self._auth_credentials()
            else:
                if self.verbose:
                    print(f"❌ No stored credentials found for {self.target_email}")
                    print(f"   Use login('{self.target_email}', 'path/to/credentials.json')")
                return False
        
        if self.auth_method == "auto":
            # Auto-detect best method
            if IN_COLAB:
                return self._auth_colab()
            elif os.path.exists(self.credentials_file):
                return self._auth_credentials()
            else:
                if self.verbose:
                    print("❌ No authentication method available")
                    print("   - Not in Google Colab")
                    print(f"   - No {self.credentials_file} found")
                return False
                
        elif self.auth_method == "colab":
            if not IN_COLAB:
                if self.verbose:
                    print("❌ Not running in Google Colab")
                return False
            return self._auth_colab()
            
        elif self.auth_method == "credentials":
            return self._auth_credentials()
            
        else:
            if self.verbose:
                print(f"❌ Unknown auth method: {self.auth_method}")
            return False
    
    def _auth_colab(self) -> bool:
        """Authenticate using Google Colab"""
        try:
            if self.verbose:
                print("🔐 Authenticating with Google Colab...")
            colab_auth.authenticate_user()
            self.service = build('drive', 'v3')
            self.authenticated = True
            self._get_my_email()
            if self.verbose:
                print("✅ Authenticated via Google Colab")
            return True
        except Exception as e:
            if self.verbose:
                print(f"❌ Colab authentication failed: {e}")
            return False
    
    def _auth_credentials(self) -> bool:
        """Authenticate using credentials.json with token caching"""
        try:
            if self.verbose:
                if self.target_email:
                    print(f"🔐 Authenticating as {self.target_email}...")
                else:
                    print("🔐 Authenticating with credentials.json...")

            creds = None
            
            # Check if force_relogin is set
            if self.force_relogin and self.verbose:
                print("🔄 Force relogin requested - ignoring cached token")
            
            # First, try to load cached token if we have a target email and not forcing relogin
            if self.target_email and not self.force_relogin:
                from .auth import _get_stored_token_path, _save_token
                token_path = _get_stored_token_path(self.target_email)
                
                if token_path and os.path.exists(token_path):
                    try:
                        with open(token_path, 'r') as token:
                            token_data = json.load(token)
                        creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
                        
                        # Check if token needs refresh
                        if creds and creds.expired and creds.refresh_token:
                            if self.verbose:
                                print("🔄 Refreshing expired token...")
                            creds.refresh(Request())
                            # Save the refreshed token
                            _save_token(self.target_email, {
                                'type': 'authorized_user',
                                'client_id': creds.client_id,
                                'client_secret': creds.client_secret,
                                'refresh_token': creds.refresh_token,
                                'token': creds.token,
                                'token_uri': creds.token_uri,
                                'client_id': creds.client_id,
                                'client_secret': creds.client_secret,
                                'scopes': creds.scopes
                            })
                        
                        if creds and creds.valid:
                            if self.verbose:
                                print("✅ Using cached authentication token")
                            self.service = build('drive', 'v3', credentials=creds)
                            self.authenticated = True
                            self._get_my_email()
                            return True
                    except Exception as e:
                        if self.verbose:
                            print(f"⚠️  Could not use cached token: {e}")
                        creds = None
            
            # If no valid cached token, do the full OAuth flow
            if not os.path.exists(self.credentials_file):
                if self.verbose:
                    print(f"❌ {self.credentials_file} not found")
                return False
                
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file, self.SCOPES)
            
            # Run the OAuth flow
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
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
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
        if not self.authenticated:
            raise RuntimeError("Client not authenticated. Call authenticate() first.")
    
    def _get_my_email(self):
        """Get the authenticated user's email address"""
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
                subdirs = ["inbox", "outbox", "shared", "private"]
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
        if self.local_syftbox_dir:
            return self.local_syftbox_dir
        elif self.my_email:
            # Calculate the path even if not created yet
            return Path.home() / f"SyftBox_{self.my_email}"
        return None
    
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
                mimetype=mimetype
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            print(f"✅ Uploaded '{name}' (ID: {file_id})")
            return file_id
            
        except HttpError as e:
            print(f"❌ Error uploading file: {e}")
            return None
    
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
                    if status:
                        print(f"Download progress: {int(status.progress() * 100)}%")
            
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
        self._ensure_authenticated()
        
        if role not in ['reader', 'writer', 'owner']:
            print(f"❌ Invalid role: {role}")
            return False
        
        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                sendNotificationEmail=False
            ).execute()
            
            if verbose:
                print(f"✅ Added {role} permission for {email}")
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
            # Search for SyftBoxTransportService folder(s) in root
            results = self.service.files().list(
                q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            syftbox_folders = results.get('files', [])
            
            if not syftbox_folders:
                if self.verbose:
                    print("📁 No SyftBoxTransportService folder found to delete")
                return True
            
            # Delete all SyftBox folders found
            deleted_count = 0
            for folder in syftbox_folders:
                folder_id = folder['id']
                folder_name = folder['name']
                
                if self.verbose:
                    print(f"🗑️  Deleting {folder_name} (ID: {folder_id})...")
                
                try:
                    self.service.files().delete(fileId=folder_id).execute()
                    deleted_count += 1
                    if self.verbose:
                        print(f"   ✅ Deleted successfully")
                except HttpError as e:
                    if self.verbose:
                        print(f"   ❌ Error deleting: {e}")
            
            if deleted_count > 0:
                if self.verbose:
                    print(f"\n✅ Delete complete! Deleted {deleted_count} SyftBoxTransportService folder(s)")
                return True
            else:
                if self.verbose:
                    print("\n❌ No folders were deleted")
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
        
        # Then create a new one
        folder_id = self.setup_syftbox()
        
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
    
    def setup_syftbox(self) -> Optional[str]:
        """
        Set up SyftBoxTransportService folder structure (creates only if doesn't exist)
        
        Returns:
            SyftBoxTransportService folder ID if successful, None otherwise
        """
        self._ensure_authenticated()
        
        try:
            # Check if SyftBoxTransportService folder already exists
            results = self.service.files().list(
                q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            syftbox_folders = results.get('files', [])
            
            if syftbox_folders:
                # Folder already exists
                syftbox_id = syftbox_folders[0]['id']
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
            results = self.service.files().list(
                q=f"name='{pending_name}' and mimeType='application/vnd.google-apps.folder' and '{syftbox_id}' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            
            pending_folders = results.get('files', [])
            if pending_folders:
                folder_ids['pending'] = pending_folders[0]['id']
                if verbose:
                    print(f"✅ Pending folder already exists: {pending_name}")
            else:
                pending_id = self._create_folder(pending_name, parent_id=syftbox_id)
                if pending_id:
                    folder_ids['pending'] = pending_id
                    if verbose:
                        print(f"📁 Created pending folder: {pending_name}")
                        print(f"   ⏳ For preparing messages (private)")
            
            # Create/check outbox_inbox folder (shared with receiver)
            results = self.service.files().list(
                q=f"name='{outbox_inbox_name}' and mimeType='application/vnd.google-apps.folder' and '{syftbox_id}' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            
            outbox_folders = results.get('files', [])
            if outbox_folders:
                folder_ids['outbox_inbox'] = outbox_folders[0]['id']
                outbox_id = outbox_folders[0]['id']
                created = False
                if verbose:
                    print(f"✅ Outbox/Inbox folder already exists: {outbox_inbox_name}")
            else:
                outbox_id = self._create_folder(outbox_inbox_name, parent_id=syftbox_id)
                if outbox_id:
                    folder_ids['outbox_inbox'] = outbox_id
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
            results = self.service.files().list(
                q=f"name='{archive_name}' and mimeType='application/vnd.google-apps.folder' and '{syftbox_id}' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            
            archive_folders = results.get('files', [])
            if archive_folders:
                folder_ids['archive'] = archive_folders[0]['id']
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
            
            return True
            
        except Exception as e:
            print(f"❌ Error adding friend: {e}")
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
        
        try:
            # First check if SyftBoxTransportService exists
            syftbox_id = None
            try:
                results = self.service.files().list(
                    q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false",
                    fields="files(id)"
                ).execute()
                if results.get('files'):
                    syftbox_id = results['files'][0]['id']
            except:
                pass
            
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
            
            return sorted(list(friends_set))
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error listing friends: {e}")
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
            
            # Check if SyftBoxTransportService exists
            syftbox_id = None
            try:
                results = self.service.files().list(
                    q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false",
                    fields="files(id)"
                ).execute()
                if results.get('files'):
                    syftbox_id = results['files'][0]['id']
            except:
                pass
            
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
            if print_summary:
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
    
    if client.authenticate():
        return client
    else:
        raise RuntimeError("Failed to authenticate")