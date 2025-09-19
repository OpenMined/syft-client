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
        
    @property
    def api_is_active_by_default(self) -> bool:
        """GDrive API active by default in Colab"""
        return self.environment == Environment.COLAB
        
    @property
    def login_complexity(self) -> int:
        """Additional GDrive setup complexity (after Google auth)"""
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
            
            return True
        except Exception as e:
            print(f"[DEBUG] GDrive setup error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def is_setup(self) -> bool:
        """Check if Drive transport is ready"""
        return self.drive_service is not None
    
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