"""Google Drive Files transport layer implementation"""

from typing import Any, Dict, List, Optional
import json
import pickle
import io
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload
from ..transport_base import BaseTransportLayer
from ...environment import Environment


class GDriveFilesTransport(BaseTransportLayer):
    """Google Drive Files API transport layer"""
    
    # STATIC Attributes
    is_keystore = True  # GDrive can store auth keys
    is_notification_layer = False  # Users don't regularly check Drive
    is_html_compatible = False  # File storage, not rendering
    is_reply_compatible = False  # No native reply mechanism
    guest_submit = False  # Requires Google account
    guest_read_file = True  # Can share files publicly
    guest_read_folder = True  # Can share folders publicly
    
    # Syft folder name
    SYFT_FOLDER = "SyftClient"
    
    def __init__(self, email: str):
        """Initialize Drive transport"""
        super().__init__(email)
        self.drive_service = None
        self.credentials = None
        self._folder_id = None
        self._setup_verified = False
        
    @property
    def api_is_active_by_default(self) -> bool:
        """GDrive API active by default in Colab"""
        return self.environment == Environment.COLAB
        
    @property
    def login_complexity(self) -> int:
        """Additional GDrive setup complexity (after Google auth)"""
        # If already set up, no steps remaining
        if self.is_setup():
            return 0
            
        if self.api_is_active:
            return 0  # No additional setup
            
        # In Colab, Drive API is pre-enabled
        if self.environment == Environment.COLAB:
            return 0  # No additional setup needed
        else:
            # Need to enable Drive API in Console
            return 1  # One additional step
    
    @staticmethod
    def check_api_enabled(platform_client: Any) -> bool:
        """
        Check if Google Drive API is enabled.
        
        Args:
            platform_client: The platform client with credentials
            
        Returns:
            bool: True if API is enabled, False otherwise
        """
        try:
            # Check if we're in Colab environment
            if hasattr(platform_client, 'current_environment'):
                from ...environment import Environment
                if platform_client.current_environment == Environment.COLAB:
                    # In Colab, try to use the API directly without credentials
                    try:
                        from googleapiclient.discovery import build
                        drive_service = build('drive', 'v3')
                        # Try to list files - will work if API is enabled
                        drive_service.files().list(pageSize=1).execute()
                        return True
                    except Exception:
                        return False
            
            # Regular OAuth credential check
            if not hasattr(platform_client, 'credentials') or not platform_client.credentials:
                return False
            
            # Try to build service and make a simple API call
            from googleapiclient.discovery import build
            from google.auth.transport.requests import Request
            
            # Refresh credentials if needed
            if platform_client.credentials.expired and platform_client.credentials.refresh_token:
                platform_client.credentials.refresh(Request())
            
            # Test Drive API directly
            drive_service = build('drive', 'v3', credentials=platform_client.credentials)
            drive_service.files().list(pageSize=1).execute()
            return True
        except Exception:
            return False
    
    @staticmethod
    def enable_api_static(transport_name: str, email: str) -> None:
        """Show instructions for enabling Google Drive API"""
        print(f"\n🔧 To enable the Google Drive API:")
        print(f"\n1. Open this URL in your browser:")
        print(f"   https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com?authuser={email}")
        print(f"\n2. Click the 'Enable' button")
        print(f"\n3. Wait for the API to be enabled (may take 5-10 seconds)")
        print(f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling")
    
    @staticmethod
    def disable_api_static(transport_name: str, email: str) -> None:
        """Show instructions for disabling Google Drive API"""
        print(f"\n🔧 To disable the Google Drive API:")
        print(f"\n1. Open this URL in your browser:")
        print(f"   https://console.cloud.google.com/apis/api/drive.googleapis.com/overview?authuser={email}")
        print(f"\n2. Click 'Manage' or 'Disable API'")
        print(f"\n3. Confirm by clicking 'Disable'")
        print(f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling")
    
    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Setup Drive transport with OAuth2 credentials or Colab auth"""
        try:
            # Check if we're in Colab and can use automatic auth
            if self.environment == Environment.COLAB:
                try:
                    from google.colab import auth as colab_auth
                    colab_auth.authenticate_user()
                    # Build service without explicit credentials in Colab
                    self.drive_service = build('drive', 'v3')
                    self.credentials = None  # No explicit credentials in Colab
                except ImportError:
                    # Fallback to regular credentials if Colab auth not available
                    if credentials is None:
                        return False
                    if not credentials or 'credentials' not in credentials:
                        return False
                    self.credentials = credentials['credentials']
                    self.drive_service = build('drive', 'v3', credentials=self.credentials)
            else:
                # Regular OAuth2 flow
                if credentials is None:
                    return False
                if not credentials or 'credentials' not in credentials:
                    return False
                self.credentials = credentials['credentials']
                self.drive_service = build('drive', 'v3', credentials=self.credentials)
            
            # Create Syft folder if needed
            self._ensure_syft_folder()
            
            # Mark as setup verified
            self._setup_verified = True
            
            return True
        except Exception as e:
            print(f"[DEBUG] GDrive setup error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def is_setup(self) -> bool:
        """Check if Drive transport is ready - NO CACHING, makes real API call"""
        if not self.drive_service:
            return False
            
        try:
            # Simple API call - list 1 file
            self.drive_service.files().list(pageSize=1).execute()
            return True
        except Exception:
            return False
    
    def _ensure_syft_folder(self) -> None:
        """Create SyftClient folder if it doesn't exist"""
        try:
            # Search for existing folder
            query = f"name='{self.SYFT_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get('files', [])
            
            if items:
                self._folder_id = items[0]['id']
            else:
                # Create folder
                file_metadata = {
                    'name': self.SYFT_FOLDER,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.drive_service.files().create(
                    body=file_metadata, fields='id'
                ).execute()
                self._folder_id = folder.get('id')
        except:
            pass
    
    def send(self, recipient: str, data: Any, subject: str = "Syft Data") -> bool:
        """Upload file to GDrive and share with recipient"""
        if not self.drive_service:
            return False
            
        try:
            # Prepare data
            if isinstance(data, str):
                file_data = data.encode('utf-8')
                mime_type = 'text/plain'
                extension = '.txt'
            elif isinstance(data, dict):
                file_data = json.dumps(data, indent=2).encode('utf-8')
                mime_type = 'application/json'
                extension = '.json'
            else:
                # Pickle for other data types
                file_data = pickle.dumps(data)
                mime_type = 'application/octet-stream'
                extension = '.pkl'
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"syft_{subject.replace(' ', '_')}_{timestamp}{extension}"
            
            # Upload file
            file_metadata = {
                'name': filename,
                'parents': [self._folder_id] if self._folder_id else []
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(file_data),
                mimetype=mime_type,
                resumable=True
            )
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            
            # Share with recipient
            if recipient and '@' in recipient:
                permission = {
                    'type': 'user',
                    'role': 'reader',
                    'emailAddress': recipient
                }
                
                self.drive_service.permissions().create(
                    fileId=file_id,
                    body=permission,
                    sendNotificationEmail=True
                ).execute()
            
            return True
            
        except Exception as e:
            print(f"Error uploading to Drive: {e}")
            return False
    
    def receive(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Check for new shared files in GDrive"""
        if not self.drive_service:
            return []
            
        messages = []
        
        try:
            # Query for files shared with me
            query = "sharedWithMe=true and trashed=false"
            
            results = self.drive_service.files().list(
                q=query,
                pageSize=limit,
                fields="files(id, name, createdTime, owners, mimeType, size)",
                orderBy="createdTime desc"
            ).execute()
            
            files = results.get('files', [])
            
            for file in files:
                # Check if it's a Syft file
                is_syft = file['name'].startswith('syft_')
                
                message = {
                    'id': file['id'],
                    'filename': file['name'],
                    'from': file['owners'][0]['emailAddress'] if file.get('owners') else 'Unknown',
                    'date': file['createdTime'],
                    'mime_type': file['mimeType'],
                    'size': file.get('size', 0),
                    'is_syft': is_syft,
                    'data': None  # Will be loaded on demand
                }
                
                # For small files, load data directly
                if is_syft and int(file.get('size', 0)) < 10 * 1024 * 1024:  # 10MB
                    try:
                        message['data'] = self._download_file(file['id'], file['mimeType'])
                    except:
                        pass
                
                messages.append(message)
                
        except Exception as e:
            print(f"Error retrieving from Drive: {e}")
            
        return messages
    
    def _download_file(self, file_id: str, mime_type: str) -> Any:
        """Download and decode file from Drive"""
        try:
            request = self.drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            fh.seek(0)
            data = fh.read()
            
            # Decode based on mime type
            if mime_type == 'text/plain':
                return data.decode('utf-8')
            elif mime_type == 'application/json':
                return json.loads(data.decode('utf-8'))
            elif mime_type == 'application/octet-stream':
                return pickle.loads(data)
            else:
                return data
                
        except:
            return None
    
    def create_public_folder(self, folder_name: str) -> Optional[str]:
        """Create a publicly accessible folder and return its URL"""
        if not self.drive_service:
            return None
            
        try:
            # Create folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self._folder_id] if self._folder_id else []
            }
            
            folder = self.drive_service.files().create(
                body=file_metadata, fields='id, webViewLink'
            ).execute()
            
            folder_id = folder.get('id')
            
            # Make it public
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            self.drive_service.permissions().create(
                fileId=folder_id,
                body=permission
            ).execute()
            
            return folder.get('webViewLink')
            
        except:
            return None
    
    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
        """Test Google Drive transport by creating a test file with test data
        
        Args:
            test_data: Data to include in the test file
            cleanup: If True, delete the test file after creation (default: True)
            
        Returns:
            Dictionary with 'success' (bool) and 'url' (str) if successful
        """
        if not self.drive_service:
            print("Drive service not initialized")
            return {"success": False, "error": "Drive service not initialized"}
            
        try:
            from datetime import datetime
            
            # Create test file content
            test_content = {
                "test_data": test_data,
                "timestamp": datetime.now().isoformat(),
                "transport": "Google Drive Files",
                "email": self.email
            }
            
            # Create filename
            filename = f"test_file_{test_data}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Create file metadata
            file_metadata = {
                'name': filename,
                'parents': [self._folder_id] if self._folder_id else []
            }
            
            # Upload the file
            import json
            import io
            
            file_data = json.dumps(test_content, indent=2).encode('utf-8')
            media = MediaIoBaseUpload(
                io.BytesIO(file_data),
                mimetype='application/json',
                resumable=True
            )
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            file_id = file.get('id')
            web_link = file.get('webViewLink')
            
            # Delete the file if cleanup is requested
            if cleanup and file_id:
                try:
                    # Small delay to ensure file is accessible before deletion
                    import time
                    time.sleep(1)
                    
                    self.drive_service.files().delete(fileId=file_id).execute()
                except Exception:
                    # If deletion fails, try moving to trash
                    try:
                        self.drive_service.files().update(
                            fileId=file_id,
                            body={'trashed': True}
                        ).execute()
                    except Exception:
                        pass
            
            # Return the web view link
            print(f"✅ Google Drive test successful! File created in {self.SYFT_FOLDER if self._folder_id else 'root'}")
            if cleanup:
                print("   File has been deleted as requested")
            
            return {"success": True, "url": web_link}
            
        except Exception as e:
            print(f"❌ Google Drive test failed: {e}")
            return {"success": False, "error": str(e)}