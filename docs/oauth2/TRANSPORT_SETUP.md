# Transport Setup Flow

## Overview

The transport setup flow guides users through configuring individual transport layers (Gmail, Drive, Sheets, Forms) either during initial authentication or later as needed.

## Transport Discovery

### Available Transports

```python
class TransportRegistry:
    """Registry of all available transports per platform"""
    
    TRANSPORTS = {
        'google_personal': {
            'gmail': {
                'name': 'Gmail',
                'description': 'Send and receive emails',
                'class': 'GmailTransport',
                'required_scopes': [
                    'https://www.googleapis.com/auth/gmail.send',
                    'https://www.googleapis.com/auth/gmail.readonly',
                    'https://www.googleapis.com/auth/gmail.modify'
                ],
                'features': ['send', 'receive', 'filters', 'labels'],
                'setup_complexity': 2  # Needs folder/filter creation
            },
            'gdrive_files': {
                'name': 'Google Drive',
                'description': 'Store and share files',
                'class': 'GDriveFilesTransport',
                'required_scopes': [
                    'https://www.googleapis.com/auth/drive'
                ],
                'features': ['upload', 'download', 'share', 'folders'],
                'setup_complexity': 1  # Just folder creation
            },
            'gsheets': {
                'name': 'Google Sheets',
                'description': 'Create and manage spreadsheets',
                'class': 'GSheetsTransport',
                'required_scopes': [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'  # For sharing
                ],
                'features': ['create', 'read', 'write', 'share'],
                'setup_complexity': 0  # No setup needed
            },
            'gforms': {
                'name': 'Google Forms',
                'description': 'Create forms for data collection',
                'class': 'GFormsTransport',
                'required_scopes': [
                    'https://www.googleapis.com/auth/forms.body'
                ],
                'features': ['create', 'responses'],
                'setup_complexity': 0  # No setup needed
            }
        },
        'smtp': {
            'email': {
                'name': 'SMTP/IMAP Email',
                'description': 'Generic email support',
                'class': 'EmailTransport',
                'features': ['send', 'receive', 'folders'],
                'setup_complexity': 3  # Server configuration
            }
        }
    }
```

## First-Time Setup Flow

### After OAuth2 Authentication

```python
def setup_transport_layers(client, first_time: bool = True) -> Dict[str, Any]:
    """Guide user through transport setup"""
    
    platform = client.platform
    available = TransportRegistry.TRANSPORTS.get(platform, {})
    
    if not available:
        return {}
    
    if first_time:
        print("\n🚀 Let's set up your communication channels!")
        print("You can add more later if needed.\n")
    
    # Check current status
    configured = check_transport_status(client)
    
    # Offer setup for each transport
    setup_results = {}
    
    for transport_id, transport_info in available.items():
        if transport_id in configured:
            continue
            
        # Ask user
        if prompt_transport_setup(transport_info):
            result = setup_single_transport(client, transport_id, transport_info)
            setup_results[transport_id] = result
    
    # Save preferences
    save_transport_preferences(client.email, setup_results)
    
    return setup_results
```

### Transport Setup Prompt

```python
def prompt_transport_setup(transport_info: Dict[str, Any]) -> bool:
    """Ask user if they want to set up a transport"""
    
    print(f"\n📦 {transport_info['name']}")
    print(f"   {transport_info['description']}")
    print(f"   Features: {', '.join(transport_info['features'])}")
    
    if transport_info['setup_complexity'] > 0:
        complexity = ['Simple', 'Moderate', 'Advanced'][min(transport_info['setup_complexity']-1, 2)]
        print(f"   Setup: {complexity} (~{transport_info['setup_complexity']} min)")
    
    response = input("\nSet this up now? (y/n/skip): ").lower()
    
    if response == 'skip':
        # Remember they skipped it
        return False
    
    return response in ['y', 'yes']
```

## Individual Transport Setup

### Gmail Setup

```python
class GmailTransportSetup:
    """Gmail-specific setup flow"""
    
    def setup(self, transport, credentials) -> bool:
        """Set up Gmail with folders and filters"""
        
        print("\n📧 Setting up Gmail...")
        
        # Step 1: Initialize service
        print("  1. Connecting to Gmail API...")
        transport.gmail_service = build('gmail', 'v1', credentials=credentials)
        
        # Step 2: Create labels
        print("  2. Creating Syft labels...")
        labels_created = self._create_labels(transport)
        
        # Step 3: Create filters  
        print("  3. Setting up email filters...")
        filters_created = self._create_filters(transport)
        
        # Step 4: Test
        print("  4. Testing Gmail access...")
        test_passed = self._test_gmail(transport)
        
        if test_passed:
            print("✅ Gmail setup complete!")
            return True
        else:
            print("❌ Gmail setup failed")
            return False
    
    def _create_labels(self, transport) -> bool:
        """Create Gmail labels for Syft"""
        try:
            # Check if label exists
            labels = transport.gmail_service.users().labels().list(
                userId='me'
            ).execute()
            
            existing_names = {l['name'] for l in labels.get('labels', [])}
            
            if transport.BACKEND_LABEL not in existing_names:
                # Create label
                label = {
                    'name': transport.BACKEND_LABEL,
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show'
                }
                
                transport.gmail_service.users().labels().create(
                    userId='me',
                    body=label
                ).execute()
                
                print(f"     ✓ Created label: {transport.BACKEND_LABEL}")
            else:
                print(f"     ✓ Label exists: {transport.BACKEND_LABEL}")
            
            return True
            
        except Exception as e:
            print(f"     ✗ Failed to create labels: {e}")
            return False
    
    def _create_filters(self, transport) -> bool:
        """Create Gmail filters for categorization"""
        try:
            # Filter for backend emails
            filter_body = {
                'criteria': {
                    'subject': transport.BACKEND_PREFIX
                },
                'action': {
                    'addLabelIds': [self._get_label_id(transport, transport.BACKEND_LABEL)],
                    'removeLabelIds': ['INBOX']
                }
            }
            
            transport.gmail_service.users().settings().filters().create(
                userId='me',
                body=filter_body
            ).execute()
            
            print(f"     ✓ Created filter for {transport.BACKEND_PREFIX}")
            return True
            
        except Exception as e:
            print(f"     ✗ Failed to create filters: {e}")
            return False
```

### Drive Setup

```python
class DriveTransportSetup:
    """Google Drive setup flow"""
    
    def setup(self, transport, credentials) -> bool:
        """Set up Drive with Syft folder"""
        
        print("\n📁 Setting up Google Drive...")
        
        # Step 1: Initialize service
        print("  1. Connecting to Drive API...")
        transport.drive_service = build('drive', 'v3', credentials=credentials)
        
        # Step 2: Create Syft folder
        print("  2. Creating Syft folder...")
        folder_created = self._create_syft_folder(transport)
        
        # Step 3: Test upload
        print("  3. Testing file operations...")
        test_passed = self._test_drive(transport)
        
        return folder_created and test_passed
    
    def _create_syft_folder(self, transport) -> bool:
        """Create or find Syft folder"""
        try:
            # Search for existing folder
            query = f"name='Syft' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = transport.drive_service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            if results.get('files'):
                transport.syft_folder_id = results['files'][0]['id']
                print("     ✓ Found existing Syft folder")
            else:
                # Create new folder
                folder_metadata = {
                    'name': 'Syft',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                
                folder = transport.drive_service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                
                transport.syft_folder_id = folder['id']
                print("     ✓ Created new Syft folder")
            
            return True
            
        except Exception as e:
            print(f"     ✗ Failed to set up folder: {e}")
            return False
```

## Adding Transports Later

### Method 1: Direct API

```python
# Add a specific transport
client.platforms['google_personal'].setup_transport('gsheets')

# Add multiple transports
client.platforms['google_personal'].setup_transports(['gsheets', 'gforms'])
```

### Method 2: Interactive Wizard

```python
def configure_transports(client) -> Dict[str, Any]:
    """Interactive transport configuration"""
    
    print("\n🔧 Transport Configuration")
    
    # Show current status
    configured = []
    not_configured = []
    
    for tid, transport in client.transports.items():
        if transport.is_configured():
            configured.append(tid)
        else:
            not_configured.append(tid)
    
    print(f"\n✅ Configured: {', '.join(configured) or 'None'}")
    print(f"❌ Not configured: {', '.join(not_configured) or 'None'}")
    
    if not not_configured:
        print("\nAll transports are configured!")
        return {}
    
    # Offer to set up
    print("\nWhich would you like to set up?")
    for i, tid in enumerate(not_configured):
        info = TransportRegistry.TRANSPORTS[client.platform][tid]
        print(f"{i+1}. {info['name']} - {info['description']}")
    
    print("0. Cancel")
    
    choice = input("\nSelect (0-{}): ".format(len(not_configured)))
    
    # Process choice...
```

### Method 3: Auto-Prompt on Use

```python
class LazyTransportSetup:
    """Prompt for setup when transport is first used"""
    
    def __init__(self, transport):
        self.transport = transport
        self._configured = False
    
    def send(self, *args, **kwargs):
        """Wrap send method with setup check"""
        
        if not self._configured:
            if not self._prompt_setup():
                raise RuntimeError(f"{self.transport.name} not configured")
        
        return self.transport.send(*args, **kwargs)
    
    def _prompt_setup(self) -> bool:
        """Prompt user to set up transport"""
        
        print(f"\n⚠️  {self.transport.name} is not configured.")
        response = input("Set it up now? (y/n): ").lower()
        
        if response in ['y', 'yes']:
            setup = get_transport_setup(self.transport.__class__.__name__)
            self._configured = setup.setup(self.transport, get_credentials())
            return self._configured
        
        return False
```

## Transport Status Tracking

### Configuration File

```json
{
    "email": "user@gmail.com",
    "platform": "google_personal",
    "transports": {
        "gmail": {
            "configured": true,
            "configured_at": "2024-12-11T10:30:00Z",
            "last_tested": "2024-12-11T10:31:00Z",
            "config": {
                "backend_label_id": "Label_123",
                "filter_ids": ["filter_456", "filter_789"]
            }
        },
        "gdrive_files": {
            "configured": true,
            "configured_at": "2024-12-11T10:32:00Z",
            "config": {
                "syft_folder_id": "1234567890abcdef"
            }
        },
        "gsheets": {
            "configured": false,
            "skip_reason": "user_deferred",
            "skip_until": "2024-12-18T00:00:00Z"
        }
    }
}
```

### Status Check Function

```python
def check_transport_status(client) -> Dict[str, Dict[str, Any]]:
    """Check configuration status of all transports"""
    
    status = {}
    config_path = get_transport_config_path(client.email)
    
    # Load saved config
    if config_path.exists():
        with open(config_path) as f:
            saved_config = json.load(f)
            status = saved_config.get('transports', {})
    
    # Verify actual status
    for transport_id, transport in client.transports.items():
        if transport_id not in status:
            status[transport_id] = {'configured': False}
        
        # Test if really configured
        try:
            if transport.test_connection():
                status[transport_id]['last_tested'] = datetime.now().isoformat()
            else:
                status[transport_id]['configured'] = False
                status[transport_id]['error'] = 'Connection test failed'
        except Exception as e:
            status[transport_id]['error'] = str(e)
    
    return status
```

## Transport Testing

### Standard Test Interface

```python
class TransportTester:
    """Test transport configuration"""
    
    @staticmethod
    def test_gmail(transport) -> Dict[str, Any]:
        """Test Gmail transport"""
        
        tests = {
            'connection': False,
            'labels': False,
            'send': False,
            'receive': False
        }
        
        try:
            # Test connection
            transport.gmail_service.users().getProfile(userId='me').execute()
            tests['connection'] = True
            
            # Test labels
            labels = transport.gmail_service.users().labels().list(userId='me').execute()
            tests['labels'] = transport.BACKEND_LABEL in [l['name'] for l in labels['labels']]
            
            # Test send (dry run)
            tests['send'] = hasattr(transport, 'send')
            
            # Test receive
            messages = transport.gmail_service.users().messages().list(
                userId='me',
                maxResults=1
            ).execute()
            tests['receive'] = True
            
        except Exception as e:
            tests['error'] = str(e)
        
        return tests
    
    @staticmethod
    def test_drive(transport) -> Dict[str, Any]:
        """Test Drive transport"""
        
        tests = {
            'connection': False,
            'folder': False,
            'upload': False,
            'download': False
        }
        
        try:
            # Test connection
            transport.drive_service.about().get(fields='user').execute()
            tests['connection'] = True
            
            # Test folder exists
            if hasattr(transport, 'syft_folder_id'):
                folder = transport.drive_service.files().get(
                    fileId=transport.syft_folder_id
                ).execute()
                tests['folder'] = folder['name'] == 'Syft'
            
            # Test operations
            tests['upload'] = hasattr(transport, 'send')
            tests['download'] = hasattr(transport, 'receive')
            
        except Exception as e:
            tests['error'] = str(e)
        
        return tests
```

## Transport Groups

### Bundled Setup Options

```python
TRANSPORT_BUNDLES = {
    'basic': {
        'name': 'Basic Communication',
        'transports': ['gmail'],
        'description': 'Email only'
    },
    'standard': {
        'name': 'Standard Features',
        'transports': ['gmail', 'gdrive_files'],
        'description': 'Email + File storage'
    },
    'full': {
        'name': 'Full Suite',
        'transports': ['gmail', 'gdrive_files', 'gsheets', 'gforms'],
        'description': 'All available features'
    },
    'data': {
        'name': 'Data Tools',
        'transports': ['gsheets', 'gforms'],
        'description': 'Spreadsheets and forms only'
    }
}

def prompt_bundle_selection() -> List[str]:
    """Let user choose a bundle of transports"""
    
    print("\n📦 Quick Setup Options:")
    
    for i, (bundle_id, bundle) in enumerate(TRANSPORT_BUNDLES.items()):
        print(f"\n{i+1}. {bundle['name']}")
        print(f"   {bundle['description']}")
        print(f"   Includes: {', '.join(bundle['transports'])}")
    
    print("\n0. Custom selection")
    
    choice = input("\nSelect option (0-{}): ".format(len(TRANSPORT_BUNDLES)))
    
    if choice == '0':
        return None  # Do custom selection
    
    try:
        bundle_id = list(TRANSPORT_BUNDLES.keys())[int(choice) - 1]
        return TRANSPORT_BUNDLES[bundle_id]['transports']
    except:
        return None
```

## Error Recovery

### Setup Failure Handling

```python
def handle_transport_setup_failure(
    transport_id: str, 
    error: Exception,
    retry_count: int = 0
) -> bool:
    """Handle transport setup failures gracefully"""
    
    print(f"\n❌ Failed to set up {transport_id}: {error}")
    
    # Offer solutions based on error type
    if "403" in str(error):
        print("\n📍 This might be a permissions issue.")
        print("   1. Check that all required APIs are enabled")
        print("   2. Verify OAuth consent screen is configured")
        print("   3. Ensure you granted all permissions")
    
    elif "Network" in str(error):
        print("\n📍 This appears to be a network issue.")
        print("   Check your internet connection and try again.")
    
    if retry_count < 3:
        retry = input("\nRetry setup? (y/n): ").lower()
        if retry in ['y', 'yes']:
            return True
    
    # Offer to skip
    print(f"\n{transport_id} setup can be completed later.")
    print("You can set it up with: client.setup_transport('{transport_id}')")
    
    return False
```