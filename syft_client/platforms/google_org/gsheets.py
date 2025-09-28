"""Google Sheets transport layer implementation"""

from typing import Any, Dict, List, Optional
import json
import pickle
from datetime import datetime
from pathlib import Path

from googleapiclient.discovery import build
from ..transport_base import BaseTransportLayer
from ...environment import Environment
from ...transports.base import BaseTransport


class GSheetsTransport(BaseTransportLayer, BaseTransport):
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
    
    @staticmethod
    def check_api_enabled(platform_client: Any) -> bool:
        """
        Check if Google Sheets API is enabled.
        
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
                        sheets_service = build('sheets', 'v4')
                        # Try to get a non-existent spreadsheet - will return 404 if API is enabled
                        sheets_service.spreadsheets().get(spreadsheetId='test123').execute()
                        return True  # Unlikely to get here
                    except Exception as e:
                        # Check if it's a 404 error (spreadsheet not found = API is working)
                        if "404" in str(e) or "Requested entity was not found" in str(e):
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
                # If we get here, somehow the test spreadsheet exists (unlikely)
                return True
            except Exception as e:
                # Check if it's a 404 error (spreadsheet not found = API is working)
                if "404" in str(e) or "Requested entity was not found" in str(e):
                    return True
                else:
                    # API is disabled or other error
                    return False
        except Exception:
            return False
    
    @staticmethod
    def enable_api_static(transport_name: str, email: str) -> None:
        """Show instructions for enabling Google Sheets API"""
        print(f"\n🔧 To enable the Google Sheets API:")
        print(f"\n1. Open this URL in your browser:")
        print(f"   https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com?authuser={email}")
        print(f"\n2. Click the 'Enable' button")
        print(f"\n3. Wait for the API to be enabled (may take 5-10 seconds)")
        print(f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling")
    
    @staticmethod
    def disable_api_static(transport_name: str, email: str) -> None:
        """Show instructions for disabling Google Sheets API"""
        print(f"\n🔧 To disable the Google Sheets API:")
        print(f"\n1. Open this URL in your browser:")
        print(f"   https://console.cloud.google.com/apis/api/sheets.googleapis.com/overview?authuser={email}")
        print(f"\n2. Click 'Manage' or 'Disable API'")
        print(f"\n3. Confirm by clicking 'Disable'")
        print(f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling")
    
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
        """Check if Sheets transport is ready - NO CACHING, makes real API call"""
        if not self.sheets_service or not self.drive_service:
            return False
            
        try:
            # Try to get spreadsheet metadata for a non-existent sheet (fast operation)
            self.sheets_service.spreadsheets().get(spreadsheetId='test123').execute()
            # Should never reach here
            return True
        except Exception as e:
            # If it's just "not found", that means the API is working
            if "Requested entity was not found" in str(e) or "404" in str(e):
                return True
            else:
                return False
    
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
    
    def receive_from_sheets(self, contacts: Optional[List[str]] = None, archive_messages: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check message sheets for new messages from contacts.
        
        Args:
            contacts: List of peer emails to check (None = check all)
            archive_messages: Whether to move messages to archive tab after reading
            
        Returns:
            Dict mapping peer emails to list of messages
        """
        import base64
        
        # If no contacts specified, get all contacts
        if contacts is None:
            contacts = self.list_peers()
        
        if not contacts:
            return {}
        
        all_messages = {}
        my_email = self.email.replace('@', '_at_').replace('.', '_')
        
        for peer_email in contacts:
            try:
                their_email = peer_email.replace('@', '_at_').replace('.', '_')
                sheet_name = f"syft_{their_email}_to_{my_email}_messages"
                
                # Find the sheet
                sheet_id = self._find_message_sheet(sheet_name, from_email=peer_email)
                if not sheet_id:
                    continue
                
                # Get all messages from the sheet
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range='messages!A:D'
                ).execute()
                
                rows = result.get('values', [])
                if not rows:
                    continue
                
                messages = []
                rows_to_archive = []
                
                # Process each row (no header)
                for i, row in enumerate(rows, start=1):
                    if len(row) >= 4:  # timestamp, msg_id, size, data
                        timestamp, msg_id, size, encoded_data = row[:4]
                        
                        try:
                            # Decode the message
                            archive_data = base64.b64decode(encoded_data)
                            
                            message = {
                                'timestamp': timestamp,
                                'message_id': msg_id,
                                'size': int(size),
                                'data': archive_data,
                                'row_number': i
                            }
                            messages.append(message)
                            rows_to_archive.append(i)
                            
                        except Exception as e:
                            print(f"   ⚠️  Failed to decode message {msg_id}: {e}")
                
                if messages:
                    all_messages[peer_email] = messages
                    print(f"📬 Received {len(messages)} message(s) from {peer_email}")
                    
                    # Archive messages if requested
                    if archive_messages and rows_to_archive:
                        self._archive_sheet_messages(sheet_id, rows_to_archive)
                
            except Exception as e:
                print(f"⚠️  Error reading messages from {peer_email}: {e}")
        
        return all_messages
    
    def _archive_sheet_messages(self, sheet_id: str, row_numbers: List[int]) -> None:
        """
        Move messages to archive tab (following gdrive_unified.py pattern).
        
        Args:
            sheet_id: The spreadsheet ID
            row_numbers: List of row numbers to archive (1-indexed)
        """
        try:
            # First, ensure Archive tab exists
            spreadsheet = self.sheets_service.spreadsheets().get(
                spreadsheetId=sheet_id,
                fields='sheets.properties'
            ).execute()
            
            # Check if Archive sheet exists
            archive_exists = False
            messages_sheet_id = None
            
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == 'archive':
                    archive_exists = True
                elif sheet['properties']['title'] == 'messages':
                    messages_sheet_id = sheet['properties']['sheetId']
            
            # Create Archive sheet if it doesn't exist
            if not archive_exists:
                request = {
                    'addSheet': {
                        'properties': {
                            'title': 'archive',
                            'gridProperties': {
                                'columnCount': 4
                            }
                        }
                    }
                }
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body={'requests': [request]}
                ).execute()
            
            # Get the messages to archive
            ranges = [f"messages!A{row}:D{row}" for row in sorted(row_numbers)]
            result = self.sheets_service.spreadsheets().values().batchGet(
                spreadsheetId=sheet_id,
                ranges=ranges
            ).execute()
            
            # Prepare data for archive
            archive_data = []
            for value_range in result.get('valueRanges', []):
                values = value_range.get('values', [])
                if values:
                    archive_data.extend(values)
            
            if archive_data:
                # Append to archive
                self.sheets_service.spreadsheets().values().append(
                    spreadsheetId=sheet_id,
                    range='archive!A:D',
                    valueInputOption='USER_ENTERED',
                    insertDataOption='INSERT_ROWS',
                    body={'values': archive_data}
                ).execute()
                
                # Delete from messages tab (in reverse order to maintain row numbers)
                requests = []
                for row_num in sorted(row_numbers, reverse=True):
                    requests.append({
                        'deleteDimension': {
                            'range': {
                                'sheetId': messages_sheet_id,
                                'dimension': 'ROWS',
                                'startIndex': row_num - 1,  # 0-indexed
                                'endIndex': row_num
                            }
                        }
                    })
                
                if requests:
                    self.sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=sheet_id,
                        body={'requests': requests}
                    ).execute()
                
                print(f"   📦 Archived {len(row_numbers)} message(s)")
                
        except Exception as e:
            print(f"   ⚠️  Failed to archive messages: {e}")
    
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
    
    def _get_or_create_message_sheet(self, sheet_name: str, recipient_email: Optional[str] = None) -> Optional[str]:
        """
        Get or create a Google Sheet for messages following gdrive_unified.py pattern.
        
        Args:
            sheet_name: Name of the sheet (e.g., syft_alice_to_bob_messages)
            recipient_email: Email of recipient to grant write access (optional)
            
        Returns:
            Spreadsheet ID if successful
        """
        try:
            # First check if sheet already exists
            query = f"name='{sheet_name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = self.drive_service.files().list(
                q=query,
                fields="files(id)",
                pageSize=1
            ).execute()
            
            if results.get('files'):
                # Sheet exists, return its ID
                return results['files'][0]['id']
            
            # Create new sheet with structure from gdrive_unified.py
            spreadsheet = {
                'properties': {
                    'title': sheet_name
                },
                'sheets': [{
                    'properties': {
                        'title': 'messages',
                        'gridProperties': {
                            'columnCount': 4,
                            'frozenRowCount': 0  # No header row
                        }
                    }
                }]
            }
            
            # Create the spreadsheet
            sheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId'
            ).execute()
            sheet_id = sheet['spreadsheetId']
            
            # Grant recipient write access if specified
            if recipient_email and self.drive_service:
                try:
                    permission = {
                        'type': 'user',
                        'role': 'writer',
                        'emailAddress': recipient_email
                    }
                    self.drive_service.permissions().create(
                        fileId=sheet_id,
                        body=permission,
                        sendNotificationEmail=False
                    ).execute()
                except Exception as e:
                    print(f"   ⚠️  Could not grant access to {recipient_email}: {e}")
            
            return sheet_id
            
        except Exception as e:
            print(f"❌ Error creating sheet: {e}")
            return None
    
    def _find_message_sheet(self, sheet_name: str, from_email: Optional[str] = None) -> Optional[str]:
        """
        Find a message sheet, checking both owned and shared sheets.
        
        Args:
            sheet_name: Name of the sheet to find
            from_email: Email of the sheet owner (for shared sheets)
            
        Returns:
            Sheet ID if found, None otherwise
        """
        try:
            # First check owned sheets
            query = f"name='{sheet_name}' and mimeType='application/vnd.google-apps.spreadsheet' and 'me' in owners and trashed=false"
            results = self.drive_service.files().list(
                q=query,
                fields="files(id)",
                pageSize=1
            ).execute()
            
            if results.get('files'):
                return results['files'][0]['id']
            
            # Then check shared sheets
            query = f"name='{sheet_name}' and mimeType='application/vnd.google-apps.spreadsheet' and sharedWithMe and trashed=false"
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, owners)",
                pageSize=10  # Multiple sheets might have same name
            ).execute()
            
            # If from_email specified, filter by owner
            for file in results.get('files', []):
                if from_email:
                    owners = file.get('owners', [])
                    for owner in owners:
                        if owner.get('emailAddress', '').lower() == from_email.lower():
                            return file['id']
                else:
                    # No from_email specified, return first match
                    return file['id']
            
            return None
            
        except Exception:
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
                    'title': f'Test Sheet - {test_data} - {datetime.now().strftime("%Y%m%d_%H%M%S")}'
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
                [test_data, datetime.now().isoformat(), 'Google Sheets', self.email],
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
    
    # BaseTransport interface implementation
    def add_peer(self, email: str, verbose: bool = True) -> bool:
        """
        Add a peer for Google Sheets transport by creating message sheets.
        
        Creates two message sheets following gdrive_unified.py pattern:
        - Outgoing: syft_{my_email}_to_{their_email}_messages
        - Incoming: syft_{their_email}_to_{my_email}_messages (if possible)
        """
        try:
            # Create outgoing message sheet name
            my_email = self.email.replace('@', '_at_').replace('.', '_')
            their_email = email.replace('@', '_at_').replace('.', '_')
            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
            
            # Get or create the outgoing message sheet
            sheet_id = self._get_or_create_message_sheet(outgoing_sheet_name, recipient_email=email)
            
            if sheet_id and verbose:
                print(f"✅ Created/found outgoing message sheet for {email}")
                print(f"   Sheet ID: {sheet_id}")
                print(f"   Sheet name: {outgoing_sheet_name}")
            
            # Note: The incoming sheet will be created by the other party
            if verbose:
                incoming_sheet_name = f"syft_{their_email}_to_{my_email}_messages"
                print(f"   📋 Incoming messages will use: {incoming_sheet_name}")
            
            return bool(sheet_id)
            
        except Exception as e:
            if verbose:
                print(f"❌ Failed to add peer {email} for Sheets: {e}")
            return False
    
    def remove_peer(self, email: str, verbose: bool = True) -> bool:
        """
        Remove a peer by revoking access to message sheets.
        """
        try:
            removed = False
            my_email = self.email.replace('@', '_at_').replace('.', '_')
            their_email = email.replace('@', '_at_').replace('.', '_')
            
            # Find outgoing message sheet
            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
            sheet_id = self._find_message_sheet(outgoing_sheet_name)
            
            if sheet_id and self.drive_service:
                # Find and remove their permission
                try:
                    permissions = self.drive_service.permissions().list(
                        fileId=sheet_id,
                        fields='permissions(id,emailAddress)'
                    ).execute()
                    
                    for perm in permissions.get('permissions', []):
                        if perm.get('emailAddress', '').lower() == email.lower():
                            self.drive_service.permissions().delete(
                                fileId=sheet_id,
                                permissionId=perm['id']
                            ).execute()
                            removed = True
                            if verbose:
                                print(f"✅ Revoked {email}'s access to outgoing message sheet")
                            break
                except Exception as e:
                    if verbose:
                        print(f"⚠️  Could not revoke permissions: {e}")
            
            if verbose and removed:
                print(f"✅ Peer {email} removed from Sheets transport")
            elif verbose:
                print(f"ℹ️  No sheets found for {email}")
            
            return removed
            
        except Exception as e:
            if verbose:
                print(f"❌ Failed to remove contact: {e}")
            return False
    
    def list_peers(self) -> List[str]:
        """
        List contacts by scanning for message sheets.
        
        Returns email addresses extracted from sheet names.
        """
        try:
            contacts = set()
            my_email = self.email.replace('@', '_at_').replace('.', '_')
            
            # Search for outgoing message sheets I created
            query = f"name contains 'syft_{my_email}_to_' and name contains '_messages' and mimeType='application/vnd.google-apps.spreadsheet' and 'me' in owners and trashed=false"
            results = self.drive_service.files().list(
                q=query,
                fields="files(name)",
                pageSize=100
            ).execute()
            
            for file in results.get('files', []):
                # Extract recipient email from sheet name
                # Format: syft_{my_email}_to_{their_email}_messages
                parts = file['name'].split('_to_')
                if len(parts) == 2 and parts[1].endswith('_messages'):
                    their_email = parts[1].replace('_messages', '')
                    # Convert back to email format
                    their_email = their_email.replace('_at_', '@').replace('_', '.')
                    contacts.add(their_email)
            
            # Also search for incoming message sheets shared with me
            query = f"name contains '_to_{my_email}_messages' and mimeType='application/vnd.google-apps.spreadsheet' and sharedWithMe and trashed=false"
            results = self.drive_service.files().list(
                q=query,
                fields="files(name)",
                pageSize=100
            ).execute()
            
            for file in results.get('files', []):
                # Extract sender email from sheet name
                # Format: syft_{their_email}_to_{my_email}_messages
                if file['name'].startswith('syft_') and f'_to_{my_email}_messages' in file['name']:
                    their_email = file['name'].replace('syft_', '').replace(f'_to_{my_email}_messages', '')
                    # Convert back to email format
                    their_email = their_email.replace('_at_', '@').replace('_', '.')
                    contacts.add(their_email)
            
            return list(contacts)
            
        except Exception:
            return []
    
    def send_to(self, archive_path: str, recipient: str, message_id: Optional[str] = None) -> bool:
        """
        Send a pre-prepared archive via Google Sheets using gdrive_unified.py format.
        
        Stores message as: [timestamp, message_id, size, base64_data]
        """
        try:
            import os
            import base64
            
            if not os.path.exists(archive_path):
                print(f"❌ Archive not found: {archive_path}")
                return False
            
            # Read archive file
            with open(archive_path, 'rb') as f:
                archive_data = f.read()
            
            # Check size limit (conservative 37.5KB to stay under 50k char limit)
            max_sheets_size = 37_500
            if len(archive_data) > max_sheets_size:
                print(f"❌ File too large for sheets transport: {len(archive_data):,} bytes (limit: {max_sheets_size:,} bytes)")
                return False
            
            # Base64 encode the data
            encoded_data = base64.b64encode(archive_data).decode('utf-8')
            
            # Create sheet name following gdrive_unified.py pattern
            my_email = self.email.replace('@', '_at_').replace('.', '_')
            their_email = recipient.replace('@', '_at_').replace('.', '_')
            sheet_name = f"syft_{my_email}_to_{their_email}_messages"
            
            # Get or create the message sheet
            sheet_id = self._get_or_create_message_sheet(sheet_name, recipient_email=recipient)
            if not sheet_id:
                return False
            
            # Prepare row data following gdrive_unified.py format
            timestamp = datetime.now().isoformat()
            message_data = {
                'values': [[
                    timestamp,
                    message_id or f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    str(len(archive_data)),
                    encoded_data
                ]]
            }
            
            # Append to sheet
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range='messages!A:D',
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=message_data
            ).execute()
            
            print(f"📊 Sent message via sheets: {message_id}")
            print(f"   Size: {len(archive_data)} bytes")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to send via Sheets: {e}")
            return False
    
    @property
    def transport_name(self) -> str:
        """Get the name of this transport"""
        return "gsheets"
    
    # Legacy method for backward compatibility
    def _find_contact_sheet(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Legacy method - now we use message sheets instead of peer sheets.
        Redirects to find outgoing message sheet.
        """
        my_email = self.email.replace('@', '_at_').replace('.', '_')
        their_email = email.replace('@', '_at_').replace('.', '_')
        sheet_name = f"syft_{my_email}_to_{their_email}_messages"
        
        sheet_id = self._find_message_sheet(sheet_name)
        if sheet_id:
            return {
                'id': sheet_id,
                'name': sheet_name,
                'url': f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            }
        return None
    
    def is_available(self) -> bool:
        """Check if Sheets transport is available"""
        return self.is_setup()
    
    def get_peer_resource(self, email: str) -> Optional[Any]:
        """
        Get the message sheets associated with a contact.
        
        Returns PeerResource with:
        - outbox_inbox: Outgoing message sheet (syft_me_to_them_messages)
        - pending: Incoming message sheet (syft_them_to_me_messages)
        """
        from ...sync.peer_resource import PeerResource
        
        my_email = self.email.replace('@', '_at_').replace('.', '_')
        their_email = email.replace('@', '_at_').replace('.', '_')
        
        # Find outgoing sheet
        outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
        outgoing_sheet_id = self._find_message_sheet(outgoing_sheet_name)
        outgoing_sheet = None
        
        if outgoing_sheet_id:
            outgoing_sheet = {
                'id': outgoing_sheet_id,
                'name': outgoing_sheet_name,
                'url': f"https://docs.google.com/spreadsheets/d/{outgoing_sheet_id}",
                'type': 'outgoing_messages'
            }
        
        # Find incoming sheet
        incoming_sheet_name = f"syft_{their_email}_to_{my_email}_messages"
        incoming_sheet_id = self._find_message_sheet(incoming_sheet_name, from_email=email)
        incoming_sheet = None
        
        if incoming_sheet_id:
            incoming_sheet = {
                'id': incoming_sheet_id,
                'name': incoming_sheet_name,
                'url': f"https://docs.google.com/spreadsheets/d/{incoming_sheet_id}",
                'type': 'incoming_messages'
            }
        
        # Create PeerResource with both sheets
        return PeerResource(
            peer_email=email,
            transport_name=self.transport_name,
            platform_name=getattr(self._platform_client, 'platform', 'google_org') if hasattr(self, '_platform_client') else 'google_org',
            resource_type='message_sheets',
            available=bool(outgoing_sheet or incoming_sheet),
            # Map to folder structure for consistent display
            outbox_inbox=outgoing_sheet,  # Outgoing messages
            pending=incoming_sheet  # Incoming messages
        )
    
    def check_peer_requests(self) -> List[str]:
        """
        Check for incoming peer requests by looking for shared message sheets
        
        Returns:
            List of email addresses who have shared message sheets with us
        """
        if not self.is_setup():
            return []
        
        try:
            # Get our email
            my_email = self.email
            if not my_email:
                return []
            
            pending_requests = set()
            existing_contacts = set(self.list_peers())
            
            # Search for shared message sheets
            query = f"sharedWithMe=true and name contains 'syft_' and name contains '_messages' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, owners)",
                pageSize=1000
            ).execute()
            
            shared_sheets = results.get('files', [])
            
            # Check each shared sheet
            for sheet in shared_sheets:
                name = sheet['name']
                
                # Check if it follows syft message sheet pattern: syft_{sender}_to_{receiver}_messages
                if '_to_' in name and name.startswith('syft_') and name.endswith('_messages'):
                    parts = name.replace('_messages', '').split('_to_')
                    if len(parts) == 2:
                        sender = parts[0].replace('syft_', '')
                        receiver = parts[1]
                        
                        # If they're sharing with us and not already a contact
                        if receiver == my_email and sender not in existing_contacts:
                            # Verify it's from the owner
                            owners = sheet.get('owners', [])
                            for owner in owners:
                                if owner.get('emailAddress', '').lower() == sender.lower():
                                    pending_requests.add(sender)
                                    break
            
            return sorted(list(pending_requests))
            
        except Exception as e:
            # Silently fail - peer request checking is optional
            return []
    
    def check_inbox(self, sender_email: str, download_dir: Optional[str] = None, verbose: bool = True) -> List[Dict]:
        """
        Check for incoming messages from a specific sender in Google Sheets
        
        Args:
            sender_email: Email of the sender to check messages from
            download_dir: Directory to download messages to (defaults to SyftBox directory)
            verbose: Whether to print progress
            
        Returns:
            List of message info dicts with keys: id, timestamp, size, data, extracted_to
        """
        if not self.is_setup():
            return []
        
        downloaded_messages = []
        
        try:
            # Determine the message sheet name pattern
            my_email = self.email
            
            # Try both naming patterns
            sheet_names = [
                # New pattern with @ and . 
                f"syft_{sender_email}_to_{my_email}_outbox_inbox",
                # Legacy pattern with underscores and _messages suffix
                f"syft_{sender_email.replace('@', '_at_').replace('.', '_')}_to_{my_email.replace('@', '_at_').replace('.', '_')}_messages"
            ]
            
            sheet = None
            sheet_id = None
            
            # Try each pattern
            for sheet_name in sheet_names:
                query = f"name='{sheet_name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
                results = self.drive_service.files().list(
                    q=query,
                    fields="files(id, name, webViewLink)",
                    pageSize=10
                ).execute()
                
                sheets = results.get('files', [])
                if sheets:
                    sheet = sheets[0]
                    sheet_id = sheet['id']
                    if verbose:
                        print(f"   Found message sheet: {sheet['name']}")
                    break
            
            if not sheet:
                if verbose:
                    print(f"   No message sheet found for patterns: {sheet_names}")
                return []
            
            # Read messages from the sheet
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="messages!A:D"
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                return []
            
            # Skip header if present
            if values and values[0] == ['timestamp', 'message_id', 'size', 'data']:
                values = values[1:]
            
            # Set up download directory
            if download_dir is None:
                # Use SyftBox directory
                if hasattr(self._platform_client, '_client') and self._platform_client._client:
                    client = self._platform_client._client
                    if hasattr(client, 'local_syftbox_dir') and client.local_syftbox_dir:
                        download_dir = str(client.local_syftbox_dir)
                    else:
                        download_dir = str(Path.home() / f"SyftBox_{my_email}")
                else:
                    download_dir = str(Path.home() / f"SyftBox_{my_email}")
            
            download_path = Path(download_dir)
            download_path.mkdir(parents=True, exist_ok=True)
            
            # Process each message
            messages_to_archive = []
            
            for row in values:
                if len(row) >= 4:
                    timestamp, message_id, size_str, data = row
                    
                    try:
                        # Decode the base64 data
                        import base64
                        message_data = base64.b64decode(data)
                        
                        # Save to temporary file
                        temp_file = download_path / f"{message_id}.tar.gz"
                        with open(temp_file, 'wb') as f:
                            f.write(message_data)
                        
                        # Extract the archive
                        import tarfile
                        with tarfile.open(temp_file, 'r:gz') as tar:
                            # Extract to the download directory
                            tar.extractall(download_path)
                        
                        # Find the extracted message directory
                        extracted_dir = download_path / message_id
                        
                        # Read metadata if available
                        metadata = {}
                        metadata_file = extracted_dir / f"{message_id}.json"
                        if metadata_file.exists():
                            import json
                            with open(metadata_file, 'r') as f:
                                metadata = json.load(f)
                        
                        # Process the data files to their final destination
                        data_dir = extracted_dir / "data"
                        if data_dir.exists():
                            # Move files from data dir to their proper location
                            import shutil
                            for item in data_dir.iterdir():
                                # Determine destination based on metadata
                                if 'original_path' in metadata:
                                    # Use original path from metadata
                                    dest = download_path / metadata['original_path'] / item.name
                                else:
                                    # Default to root of download dir
                                    dest = download_path / item.name
                                
                                # Create parent directories
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                
                                # Move the file/directory
                                if item.is_dir():
                                    if dest.exists():
                                        shutil.rmtree(dest)
                                    shutil.move(str(item), str(dest))
                                else:
                                    shutil.move(str(item), str(dest))
                                
                                if verbose:
                                    print(f"   📥 Extracted: {dest.name}")
                        
                        # Clean up temporary files
                        temp_file.unlink()
                        if extracted_dir.exists():
                            import shutil
                            shutil.rmtree(extracted_dir)
                        
                        # Add to results
                        downloaded_messages.append({
                            'id': message_id,
                            'timestamp': timestamp,
                            'size': int(size_str) if size_str.isdigit() else 0,
                            'metadata': metadata,
                            'extracted_to': str(download_path)
                        })
                        
                        # Mark for archiving
                        messages_to_archive.append(row)
                        
                    except Exception as e:
                        if verbose:
                            print(f"   ❌ Error processing message {message_id}: {e}")
            
            # Archive processed messages
            if messages_to_archive:
                self._archive_messages(sheet_id, messages_to_archive, verbose)
            
            return downloaded_messages
            
        except Exception as e:
            if verbose:
                print(f"   ❌ Error checking inbox: {e}")
            return []
    
    def _archive_messages(self, sheet_id: str, messages: List[List[str]], verbose: bool = True):
        """Archive processed messages to the archive sheet"""
        try:
            # Check if archive sheet exists
            spreadsheet = self.sheets_service.spreadsheets().get(
                spreadsheetId=sheet_id
            ).execute()
            
            sheets = {sheet['properties']['title']: sheet['properties']['sheetId'] 
                     for sheet in spreadsheet.get('sheets', [])}
            
            if 'archive' not in sheets:
                # Create archive sheet
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': 'archive',
                            'gridProperties': {
                                'columnCount': 4,
                                'frozenRowCount': 0
                            }
                        }
                    }
                }]
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body={'requests': requests}
                ).execute()
                
                # Add header
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range='archive!A1:D1',
                    valueInputOption='RAW',
                    body={'values': [['timestamp', 'message_id', 'size', 'data']]}
                ).execute()
            
            # Append to archive
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range='archive!A:D',
                valueInputOption='RAW',
                body={'values': messages}
            ).execute()
            
            # Remove from messages sheet
            # Get current messages
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="messages!A:D"
            ).execute()
            
            current_values = result.get('values', [])
            
            # Filter out archived messages
            message_ids = {row[1] for row in messages}  # message_id is in column 2
            new_values = [row for row in current_values 
                         if len(row) < 2 or row[1] not in message_ids]
            
            # Clear and rewrite messages sheet
            self.sheets_service.spreadsheets().values().clear(
                spreadsheetId=sheet_id,
                range="messages!A:D"
            ).execute()
            
            if new_values:
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range='messages!A:D',
                    valueInputOption='RAW',
                    body={'values': new_values}
                ).execute()
            
            if verbose:
                print(f"   📦 Archived {len(messages)} message{'s' if len(messages) != 1 else ''}")
                
        except Exception as e:
            if verbose:
                print(f"   ⚠️  Error archiving messages: {e}")