"""Google Sheets transport layer implementation"""

from typing import Any, Dict, List, Optional
import json
import pickle
from datetime import datetime
import logging

from googleapiclient.discovery import build
from ..transport_base import BaseTransportLayer
from ...environment import Environment


class GSheetsTransport(BaseTransportLayer):
    """Google Sheets API transport layer"""
    
    # STATIC Attributes
    is_keystore = False  # Sheets not ideal for storing keys
    is_notification_layer = False  # Users don't check sheets regularly
    is_html_compatible = False  # Sheets format, not HTML
    is_reply_compatible = False  # No native reply mechanism
    guest_submit = False  # Requires authentication to write
    guest_read_file = True  # Can make sheets public
    guest_read_folder = False  # N/A for sheets
    
    # Syft spreadsheet name
    SYFT_SHEET_PREFIX = "SyftClient_"
    
    def __init__(self, email: str):
        """Initialize Sheets transport"""
        super().__init__(email)
        self.sheets_service = None
        self.drive_service = None
        self.credentials = None
        self._setup_verified = False
    
    @staticmethod
    def check_api_enabled(platform_client: Any) -> bool:
        """
        Check if Google Sheets API is enabled.
        
        Args:
            platform_client: The platform client with credentials
            
        Returns:
            bool: True if API is enabled, False otherwise
        """
        # Suppress googleapiclient warnings during API check
        googleapi_logger = logging.getLogger('googleapiclient.http')
        original_level = googleapi_logger.level
        googleapi_logger.setLevel(logging.ERROR)
        
        try:
            # Check if we're in Colab environment
            if hasattr(platform_client, 'current_environment'):
                from ...environment import Environment
                if platform_client.current_environment == Environment.COLAB:
                    # In Colab, try to use the API directly without credentials
                    try:
                        from googleapiclient.discovery import build
                        sheets_service = build('sheets', 'v4')
                        # Try to get a non-existent spreadsheet - will return 404 if API is enabled
                        sheets_service.spreadsheets().get(spreadsheetId='test123').execute()
                        return True  # Unlikely to get here
                    except Exception as e:
                        # Check if it's a 404 error (sheet not found = API is working)
                        if "404" in str(e) or "not found" in str(e).lower():
                            return True
                        else:
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
            
            # Test Sheets API directly
            sheets_service = build('sheets', 'v4', credentials=platform_client.credentials)
            
            # Try to get a non-existent spreadsheet - will return 404 if API is enabled
            try:
                sheets_service.spreadsheets().get(spreadsheetId='test123').execute()
                # If we get here, somehow the test sheet exists (unlikely)
                return True
            except Exception as e:
                # Check if it's a 404 error (sheet not found = API is working)
                if "404" in str(e) or "not found" in str(e).lower():
                    return True
                else:
                    # API is disabled or other error
                    return False
        except Exception as e:
            print(f"Error checking Sheets API: {e}")
            return False
        finally:
            googleapi_logger.setLevel(original_level)
    
    @staticmethod
    def enable_api_static(transport_name: str, email: str, project_id: Optional[str] = None) -> None:
        """Show instructions for enabling Google Sheets API"""
        print(f"\n🔧 To enable the Google Sheets API:")
        print(f"\n1. Open this URL in your browser:")
        if project_id:
            print(f"   https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com?authuser={email}&project={project_id}")
        else:
            print(f"   https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com?authuser={email}")
        print(f"\n2. Click the 'Enable' button")
        print(f"\n3. Wait for the API to be enabled (may take 5-10 seconds)")
        print(f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling")
    
    @staticmethod
    def disable_api_static(transport_name: str, email: str, project_id: Optional[str] = None) -> None:
        """Show instructions for disabling Google Sheets API"""
        print(f"\n🔧 To disable the Google Sheets API:")
        print(f"\n1. Open this URL in your browser:")
        if project_id:
            print(f"   https://console.cloud.google.com/apis/api/sheets.googleapis.com/overview?authuser={email}&project={project_id}")
        else:
            print(f"   https://console.cloud.google.com/apis/api/sheets.googleapis.com/overview?authuser={email}")
        print(f"\n2. Click 'Manage' or 'Disable API'")
        print(f"\n3. Confirm by clicking 'Disable'")
        print(f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling")
        
    @property
    def api_is_active_by_default(self) -> bool:
        """Sheets API requires manual activation"""
        return False
        
    @property
    def login_complexity(self) -> int:
        """Sheets requires same auth as GDrive"""
        if self.is_setup():
            return 0
        if self._cached_credentials:
            return 0  # Already logged in
            
        if self.environment == Environment.COLAB:
            return 1  # Can reuse GDrive auth in Colab
        else:
            return 2  # OAuth2 flow required
    
    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Setup Sheets transport with OAuth2 credentials or Colab auth"""
        try:
            # Check if we're in Colab and can use automatic auth
            if self.environment == Environment.COLAB:
                try:
                    from google.colab import auth as colab_auth
                    colab_auth.authenticate_user()
                    # Build services without explicit credentials in Colab
                    self.sheets_service = build('sheets', 'v4')
                    self.drive_service = build('drive', 'v3')
                    self.credentials = None  # No explicit credentials in Colab
                except ImportError:
                    # Fallback to regular credentials if Colab auth not available
                    if credentials is None:
                        return False
                    if not credentials or 'credentials' not in credentials:
                        return False
                    self.credentials = credentials['credentials']
                    self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
                    self.drive_service = build('drive', 'v3', credentials=self.credentials)
            else:
                # Regular OAuth2 flow
                if credentials is None:
                    return False
                if not credentials or 'credentials' not in credentials:
                    return False
                self.credentials = credentials['credentials']
                self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
                self.drive_service = build('drive', 'v3', credentials=self.credentials)
            
            # Mark as setup verified
            self._setup_verified = True
            
            return True
        except Exception as e:
            print(f"[DEBUG] GSheets setup error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def is_setup(self) -> bool:
        """Check if Sheets transport is ready"""
        # First check if we're cached as setup
        if self.is_cached_as_setup():
            return True
            
        # In Colab, we can always set up on demand
        if self.environment == Environment.COLAB:
            try:
                from google.colab import auth as colab_auth
                return True  # Can authenticate on demand
            except ImportError:
                pass
            
        # Otherwise check normal setup
        return self.sheets_service is not None and self.drive_service is not None
    
    def send(self, recipient: str, data: Any, subject: str = "Syft Data") -> bool:
        """Write data to a Google Sheet and share"""
        if not self.sheets_service or not self.drive_service:
            return False
            
        try:
            # Create spreadsheet
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            spreadsheet_name = f"{self.SYFT_SHEET_PREFIX}{subject.replace(' ', '_')}_{timestamp}"
            
            spreadsheet = {
                'properties': {
                    'title': spreadsheet_name
                }
            }
            
            spreadsheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet, fields='spreadsheetId'
            ).execute()
            
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            
            # Prepare data for sheets
            values = []
            
            if isinstance(data, str):
                # Split string into lines
                values = [[line] for line in data.split('\n')]
            elif isinstance(data, dict):
                # Convert dict to key-value pairs
                values = [['Key', 'Value']]
                for key, value in data.items():
                    values.append([str(key), str(value)])
            elif isinstance(data, list):
                # Handle list of dicts (common for tabular data)
                if data and isinstance(data[0], dict):
                    # Use dict keys as headers
                    headers = list(data[0].keys())
                    values = [headers]
                    for row in data:
                        values.append([str(row.get(h, '')) for h in headers])
                else:
                    # Simple list
                    values = [[str(item)] for item in data]
            else:
                # For complex types, pickle and store as base64
                pickled = pickle.dumps(data)
                import base64
                b64_data = base64.b64encode(pickled).decode('utf-8')
                values = [
                    ['Type', 'Pickled Data'],
                    [str(type(data).__name__), b64_data]
                ]
            
            # Write data to sheet
            body = {'values': values}
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='A1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            # Share with recipient
            if recipient and '@' in recipient:
                permission = {
                    'type': 'user',
                    'role': 'reader',
                    'emailAddress': recipient
                }
                
                self.drive_service.permissions().create(
                    fileId=spreadsheet_id,
                    body=permission,
                    sendNotificationEmail=True
                ).execute()
            
            return True
            
        except Exception as e:
            print(f"Error creating sheet: {e}")
            return False
    
    def receive(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Read data from shared Google Sheets"""
        if not self.sheets_service or not self.drive_service:
            return []
            
        messages = []
        
        try:
            # Find sheets shared with me
            query = "mimeType='application/vnd.google-apps.spreadsheet' and sharedWithMe=true and trashed=false"
            
            results = self.drive_service.files().list(
                q=query,
                pageSize=limit,
                fields="files(id, name, createdTime, owners)",
                orderBy="createdTime desc"
            ).execute()
            
            files = results.get('files', [])
            
            for file in files:
                # Check if it's a Syft sheet
                is_syft = file['name'].startswith(self.SYFT_SHEET_PREFIX)
                
                message = {
                    'id': file['id'],
                    'name': file['name'],
                    'from': file['owners'][0]['emailAddress'] if file.get('owners') else 'Unknown',
                    'date': file['createdTime'],
                    'is_syft': is_syft,
                    'data': None
                }
                
                # Read data from Syft sheets
                if is_syft:
                    try:
                        result = self.sheets_service.spreadsheets().values().get(
                            spreadsheetId=file['id'],
                            range='A:Z'  # Get all columns
                        ).execute()
                        
                        values = result.get('values', [])
                        
                        # Try to reconstruct original data format
                        if values:
                            if len(values[0]) == 2 and values[0] == ['Type', 'Pickled Data']:
                                # Pickled data
                                if len(values) > 1:
                                    import base64
                                    b64_data = values[1][1]
                                    pickled = base64.b64decode(b64_data)
                                    message['data'] = pickle.loads(pickled)
                            elif len(values) > 1 and len(values[0]) > 1:
                                # Tabular data - convert back to list of dicts
                                headers = values[0]
                                data = []
                                for row in values[1:]:
                                    row_dict = {}
                                    for i, header in enumerate(headers):
                                        row_dict[header] = row[i] if i < len(row) else ''
                                    data.append(row_dict)
                                message['data'] = data
                            else:
                                # Raw values
                                message['data'] = values
                    except:
                        pass
                
                messages.append(message)
                
        except Exception as e:
            print(f"Error retrieving sheets: {e}")
            
        return messages
    
    def create_public_sheet(self, sheet_name: str, data: List[List[str]]) -> Optional[str]:
        """Create a publicly accessible sheet and return its URL"""
        if not self.sheets_service or not self.drive_service:
            return None
            
        try:
            # Create spreadsheet
            spreadsheet = {
                'properties': {'title': sheet_name}
            }
            
            spreadsheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet, fields='spreadsheetId,spreadsheetUrl'
            ).execute()
            
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            
            # Write data
            if data:
                body = {'values': data}
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range='A1',
                    valueInputOption='RAW',
                    body=body
                ).execute()
            
            # Make public
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            self.drive_service.permissions().create(
                fileId=spreadsheet_id,
                body=permission
            ).execute()
            
            return spreadsheet.get('spreadsheetUrl')
            
        except:
            return None
    
    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
        """Test Google Sheets transport by creating a test spreadsheet with test data
        
        Args:
            test_data: Data to include in the test spreadsheet
            cleanup: If True, delete the test spreadsheet after creation (default: True)
            
        Returns:
            Dictionary with 'success' (bool) and 'url' (str) if successful
        """
        if not self.sheets_service or not self.drive_service:
            print("Sheets or Drive service not initialized")
            return {"success": False, "error": "Sheets or Drive service not initialized"}
            
        try:
            from datetime import datetime
            
            # Create spreadsheet
            spreadsheet_body = {
                'properties': {
                    'title': f'Test Sheet (Org) - {test_data} - {datetime.now().strftime("%Y%m%d_%H%M%S")}'
                },
                'sheets': [{
                    'properties': {
                        'title': 'Test Data'
                    }
                }]
            }
            
            spreadsheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet_body,
                fields='spreadsheetId,spreadsheetUrl,sheets'
            ).execute()
            
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            sheet_id = spreadsheet['sheets'][0]['properties']['sheetId']
            
            # Prepare test data
            values = [
                ['Test Data', 'Timestamp', 'Transport', 'Email'],
                [test_data, datetime.now().isoformat(), 'Google Sheets (Org)', self.email],
                ['', '', '', ''],
                ['This is a test spreadsheet created by syft-client', '', '', '']
            ]
            
            body = {
                'values': values
            }
            
            # Write data to sheet
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Test Data!A1:D4',
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            # Format the header row
            requests = [{
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
                            'textFormat': {
                                'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
                                'bold': True
                            }
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                }
            }]
            
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            spreadsheet_url = spreadsheet.get('spreadsheetUrl')
            
            # Delete the spreadsheet if cleanup is requested
            if cleanup and spreadsheet_id:
                try:
                    # Small delay to ensure spreadsheet is accessible before deletion
                    import time
                    time.sleep(1)
                    
                    # Use Drive API to delete the spreadsheet
                    self.drive_service.files().delete(fileId=spreadsheet_id).execute()
                except Exception:
                    # If deletion fails, try moving to trash
                    try:
                        self.drive_service.files().update(
                            fileId=spreadsheet_id,
                            body={'trashed': True}
                        ).execute()
                    except Exception:
                        pass
            
            # Return the spreadsheet URL
            print(f"✅ Google Sheets test successful! Spreadsheet created with test data")
            if cleanup:
                print("   Spreadsheet has been deleted as requested")
            
            return {"success": True, "url": spreadsheet_url}
            
        except Exception as e:
            print(f"❌ Google Sheets test failed: {e}")
            return {"success": False, "error": str(e)}