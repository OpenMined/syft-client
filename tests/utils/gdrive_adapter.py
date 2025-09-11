"""
Google Drive adapter for backward compatibility with integration tests.

This adapter wraps the new SyftClient API to provide the old interface
expected by existing integration tests.
"""

from typing import Any, Optional, List, Dict
from syft_client import SyftClient


class GDriveAdapter:
    """
    Adapter that provides backward compatibility for Google Drive integration tests.
    
    Wraps a SyftClient to expose the old API that tests expect.
    """
    
    def __init__(self, syft_client: SyftClient):
        """Initialize adapter with a SyftClient instance"""
        self.client = syft_client
        self._service = None
        self._authenticated = False
        
        # Try to get Google platform client (either personal or org)
        self.google_platform = None
        for platform_name in ['google_personal', 'google_org']:
            if platform_name in self.client.platforms:
                self.google_platform = self.client.platforms[platform_name]
                self._authenticated = True
                break
    
    @property
    def authenticated(self) -> bool:
        """Check if client is authenticated"""
        return self._authenticated and self.google_platform is not None
    
    @property
    def my_email(self) -> str:
        """Get the user's email address"""
        return self.client.email
    
    @property
    def service(self) -> Any:
        """Get Google Drive service object"""
        if not self._service and self.google_platform:
            # Try to get service from platform's transport
            try:
                # Check if platform has Google Drive transport
                transports = self.google_platform.get_transport_instances()
                for transport_name, transport in transports.items():
                    if 'GDrive' in transport_name or 'gdrive' in transport_name.lower():
                        # Try to get service from transport
                        if hasattr(transport, 'service'):
                            self._service = transport.service
                            break
                        elif hasattr(transport, 'get_service'):
                            self._service = transport.get_service()
                            break
                
                # If no transport found, try to create one
                if not self._service:
                    # This is a fallback - actual implementation depends on platform
                    self._create_service()
                    
            except Exception as e:
                print(f"Warning: Could not get Google Drive service: {e}")
        
        return self._service
    
    def _create_service(self):
        """Create Google Drive service from credentials"""
        try:
            # Import Google libraries
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            import json
            import os
            
            # Try to get credentials from platform auth data
            if hasattr(self.google_platform, '_auth_data'):
                auth_data = self.google_platform._auth_data
                
                # Check for OAuth2 token
                if 'token' in auth_data:
                    token_data = auth_data['token']
                    if isinstance(token_data, str):
                        token_data = json.loads(token_data)
                    
                    creds = Credentials.from_authorized_user_info(token_data)
                    self._service = build('drive', 'v3', credentials=creds)
                    return
            
            # Try to load from wallet location (CI setup)
            sanitized_email = self.my_email.replace("@", "_at_").replace(".", "_")
            token_path = os.path.expanduser(f"~/.syft/gdrive/{sanitized_email}/token.json")
            
            if os.path.exists(token_path):
                with open(token_path, 'r') as f:
                    token_data = json.load(f)
                creds = Credentials.from_authorized_user_info(token_data)
                self._service = build('drive', 'v3', credentials=creds)
                
        except Exception as e:
            print(f"Warning: Could not create Google Drive service: {e}")
    
    def reset_syftbox(self) -> str:
        """Reset the SyftBox (delete and recreate)"""
        try:
            if not self.service:
                raise ValueError("No Google Drive service available")
            
            # Delete existing SyftBox folder if it exists
            results = self.service.files().list(
                q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            for file in results.get('files', []):
                self.service.files().delete(fileId=file['id']).execute()
            
            # Create new SyftBox folder
            folder_metadata = {
                'name': 'SyftBoxTransportService',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id', '')
            
        except Exception as e:
            print(f"Error resetting SyftBox: {e}")
            return ""
    
    def add_friend(self, friend_email: str, verbose: bool = False) -> Dict[str, Any]:
        """Add a friend (create shared folders)"""
        try:
            if not self.service:
                raise ValueError("No Google Drive service available")
            
            if verbose:
                print(f"Adding {friend_email} as friend...")
            
            # Create friend folders
            folders_created = []
            
            # Outbox folder
            outbox_name = f"syft_{self.my_email}_to_{friend_email}_outbox_inbox"
            outbox_metadata = {
                'name': outbox_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            outbox = self.service.files().create(
                body=outbox_metadata,
                fields='id,name'
            ).execute()
            folders_created.append(outbox_name)
            
            # Share with friend
            permission = {
                'type': 'user',
                'role': 'writer',
                'emailAddress': friend_email
            }
            self.service.permissions().create(
                fileId=outbox['id'],
                body=permission
            ).execute()
            
            # Pending folder  
            pending_name = f"syft_{self.my_email}_to_{friend_email}_pending"
            pending_metadata = {
                'name': pending_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            pending = self.service.files().create(
                body=pending_metadata,
                fields='id,name'
            ).execute()
            folders_created.append(pending_name)
            
            if verbose:
                print(f"Created folders: {folders_created}")
            
            return {
                'success': True,
                'folders_created': folders_created,
                'friend_email': friend_email
            }
            
        except Exception as e:
            if verbose:
                print(f"Error adding friend: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_friends(self) -> List[str]:
        """Get list of friends based on shared folders"""
        try:
            if not self.service:
                return []
            
            # Look for outbox folders to determine friends
            results = self.service.files().list(
                q=f"name contains 'syft_{self.my_email}_to_' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(name)"
            ).execute()
            
            friends = []
            for file in results.get('files', []):
                # Extract friend email from folder name
                name = file['name']
                if '_to_' in name and '_outbox_inbox' in name:
                    parts = name.split('_to_')
                    if len(parts) > 1:
                        friend_part = parts[1].replace('_outbox_inbox', '')
                        if '@' in friend_part:
                            friends.append(friend_part)
            
            return list(set(friends))  # Remove duplicates
            
        except Exception as e:
            print(f"Error getting friends: {e}")
            return []
    
    def get_friend_requests(self) -> List[str]:
        """Get list of pending friend requests"""
        try:
            if not self.service:
                return []
            
            # Look for shared folders from others
            results = self.service.files().list(
                q=f"name contains '_to_{self.my_email}_outbox_inbox' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(name)"
            ).execute()
            
            requests = []
            for file in results.get('files', []):
                # Extract sender email from folder name
                name = file['name']
                if name.startswith('syft_') and '_to_' in name:
                    sender_part = name.replace('syft_', '').split('_to_')[0]
                    if '@' in sender_part:
                        requests.append(sender_part)
            
            return list(set(requests))  # Remove duplicates
            
        except Exception as e:
            print(f"Error getting friend requests: {e}")
            return []
    
    def _folder_exists(self, folder_name: str) -> bool:
        """Check if a folder exists in Google Drive"""
        try:
            if not self.service:
                return False
                
            results = self.service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id)"
            ).execute()
            
            return len(results.get('files', [])) > 0
            
        except Exception as e:
            print(f"Error checking folder: {e}")
            return False
    
    def _create_folder(self, folder_name: str) -> str:
        """Create a folder in Google Drive"""
        try:
            if not self.service:
                raise ValueError("No Google Drive service available")
            
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id', '')
            
        except Exception as e:
            print(f"Error creating folder: {e}")
            return ""