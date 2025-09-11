"""
Pytest configuration and fixtures for syft-client tests
"""
import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import Mock, MagicMock, patch
import pytest

# Test environment detection
def is_integration_test():
    """Check if we're running integration tests"""
    return os.environ.get('SYFT_TEST_MODE') == 'integration'

def is_ci_environment():
    """Check if we're running in CI"""
    return os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'

# ========== Mock Google Drive Service ==========

class MockGoogleDriveService:
    """Mock Google Drive service for unit tests"""
    
    def __init__(self):
        self.folders = {}  # folder_id -> folder_data
        self.files_data = {}    # file_id -> file_data (renamed to avoid conflict)
        self.permissions = {}  # file_id -> [permissions]
        self.next_id = 1000
        
    def _generate_id(self) -> str:
        self.next_id += 1
        return str(self.next_id)
    
    def files(self):
        return MockFilesResource(self)
    
    def about(self):
        return MockAboutResource()
    
    def reset(self):
        """Reset mock service state"""
        self.folders.clear()
        self.files_data.clear()
        self.permissions.clear()
        self.next_id = 1000

class MockFilesResource:
    def __init__(self, service):
        self.service = service
    
    def create(self, body=None, fields=None):
        # Always return the same mock instance so tests can configure it
        if not hasattr(self.service, '_create_request'):
            self.service._create_request = Mock()
        return self.service._create_request
    
    def list(self, q=None, fields=None, pageSize=None, pageToken=None):
        if not hasattr(self.service, '_list_request'):
            self.service._list_request = Mock()
        return self.service._list_request
    
    def get(self, fileId=None, fields=None):
        if not hasattr(self.service, '_get_request'):
            self.service._get_request = Mock()
        return self.service._get_request
    
    def delete(self, fileId=None):
        if not hasattr(self.service, '_delete_request'):
            self.service._delete_request = Mock()
        return self.service._delete_request
    
    def permissions(self):
        if not hasattr(self.service, '_permissions_resource'):
            self.service._permissions_resource = Mock()
        return self.service._permissions_resource

class MockCreateRequest:
    def __init__(self, service, body, fields):
        self.service = service
        self.body = body
        self.fields = fields
    
    def execute(self):
        folder_id = self.service._generate_id()
        folder_data = {
            'id': folder_id,
            'name': self.body['name'],
            'mimeType': self.body.get('mimeType', 'application/vnd.google-apps.folder'),
            'parents': self.body.get('parents', ['root'])
        }
        self.service.folders[folder_id] = folder_data
        return folder_data

class MockListRequest:
    def __init__(self, service, q, fields, pageSize, pageToken):
        self.service = service
        self.q = q
        self.fields = fields
    
    def execute(self):
        # Simple query parsing for common cases
        files = []
        
        if self.q:
            # Parse common query patterns
            if "name=" in self.q:
                name_part = self.q.split("name=")[1].split(" ")[0].strip("'\"")
                files = [f for f in self.service.folders.values() if f['name'] == name_part]
            elif "name contains" in self.q:
                name_part = self.q.split("name contains ")[1].split(" ")[0].strip("'\"")
                files = [f for f in self.service.folders.values() if name_part in f['name']]
        else:
            files = list(self.service.folders.values())
        
        return {'files': files}

class MockGetRequest:
    def __init__(self, service, fileId, fields):
        self.service = service
        self.fileId = fileId
        self.fields = fields
    
    def execute(self):
        if self.fileId in self.service.folders:
            return self.service.folders[self.fileId]
        raise Exception(f"File not found: {self.fileId}")

class MockDeleteRequest:
    def __init__(self, service, fileId):
        self.service = service
        self.fileId = fileId
    
    def execute(self):
        if self.fileId in self.service.folders:
            del self.service.folders[self.fileId]
        return {}

class MockPermissionsResource:
    def __init__(self, service):
        self.service = service
    
    def create(self, fileId=None, body=None):
        return MockPermissionCreateRequest(self.service, fileId, body)

class MockPermissionCreateRequest:
    def __init__(self, service, fileId, body):
        self.service = service
        self.fileId = fileId
        self.body = body
    
    def execute(self):
        if self.fileId not in self.service.permissions:
            self.service.permissions[self.fileId] = []
        
        permission = {
            'id': self.service._generate_id(),
            'type': self.body.get('type', 'user'),
            'emailAddress': self.body.get('emailAddress'),
            'role': self.body.get('role', 'reader')
        }
        self.service.permissions[self.fileId].append(permission)
        return permission

class MockAboutResource:
    def get(self, fields=None):
        return MockAboutGetRequest(fields)

class MockAboutGetRequest:
    def __init__(self, fields):
        self.fields = fields
    
    def execute(self):
        return {
            'user': {
                'emailAddress': 'test-user@gmail.com'
            }
        }

# ========== Pytest Fixtures ==========

@pytest.fixture
def mock_gdrive_service():
    """Provide a mock Google Drive service"""
    return MockGoogleDriveService()

@pytest.fixture
def mock_credentials():
    """Provide mock Google credentials"""
    mock_creds = Mock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.client_id = "mock_client_id"
    mock_creds.client_secret = "mock_client_secret"
    mock_creds.token_uri = "https://oauth2.googleapis.com/token"
    mock_creds.scopes = ['https://www.googleapis.com/auth/drive']
    return mock_creds

@pytest.fixture
def mock_build_service(mock_gdrive_service):
    """Mock the googleapiclient.discovery.build function"""
    with patch('syft_client.gdrive_unified.build') as mock_build:
        mock_build.return_value = mock_gdrive_service
        yield mock_build

@pytest.fixture
def temp_credentials_file():
    """Create a temporary credentials file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        creds_data = {
            "installed": {
                "client_id": "test-client-id.apps.googleusercontent.com",
                "project_id": "test-project",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "test-client-secret",
                "redirect_uris": ["http://localhost"]
            }
        }
        json.dump(creds_data, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    try:
        os.unlink(temp_path)
    except:
        pass

@pytest.fixture
def mock_wallet_dir():
    """Create a temporary wallet directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        wallet_dir = Path(temp_dir) / ".syft" / "gdrive"
        wallet_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('syft_client.auth._get_wallet_dir', return_value=wallet_dir):
            yield wallet_dir

@pytest.fixture(scope="session")
def test_users():
    """Test user configuration for integration tests"""
    return {
        'user1': {
            'email': os.environ.get('TEST_USER1_EMAIL', 'test-user1@gmail.com'),
            'creds_file': '~/.syft/test/user1-creds.json'
        },
        'user2': {
            'email': os.environ.get('TEST_USER2_EMAIL', 'test-user2@gmail.com'), 
            'creds_file': '~/.syft/test/user2-creds.json'
        }
    }

@pytest.fixture(scope="session")
def integration_test_clients(test_users):
    """Set up real Google Drive clients for integration testing"""
    if not is_integration_test():
        pytest.skip("Integration tests require SYFT_TEST_MODE=integration")
    
    # Import here to avoid import errors when not in integration mode
    import syft_client as sc
    from tests.utils.cleanup import cleanup_test_folders
    from tests.utils.gdrive_adapter import GDriveAdapter
    
    # Create clients
    user1_email = test_users['user1']['email']
    user2_email = test_users['user2']['email']
    user1_creds = os.path.expanduser(test_users['user1']['creds_file'])
    user2_creds = os.path.expanduser(test_users['user2']['creds_file'])
    
    try:
        # In CI, tokens and credentials should be pre-configured
        if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
            print(f"🔍 CI Mode detected - using pre-configured tokens and credentials")
            print(f"   CI env var: {os.environ.get('CI')}")
            print(f"   GITHUB_ACTIONS env var: {os.environ.get('GITHUB_ACTIONS')}")
            print(f"   User1 email: {user1_email}")
            print(f"   User2 email: {user2_email}")
            
            # Check if tokens exist (they should be pre-configured by CI)
            # Need to use sanitized email addresses for directory names (same as CI workflow)
            sanitized_user1_email = user1_email.replace("@", "_at_").replace(".", "_")
            sanitized_user2_email = user2_email.replace("@", "_at_").replace(".", "_")
            
            user1_token_path = os.path.expanduser(f"~/.syft/gdrive/{sanitized_user1_email}/token.json")
            user2_token_path = os.path.expanduser(f"~/.syft/gdrive/{sanitized_user2_email}/token.json")
            print(f"   User1 token: {user1_token_path} (exists: {os.path.exists(user1_token_path)})")
            print(f"   User2 token: {user2_token_path} (exists: {os.path.exists(user2_token_path)})")
            
            # In CI, login should work directly with pre-configured tokens
            # No need to provide credentials_path as tokens are already in wallet
            # IMPORTANT: Don't use force_relogin=True in CI because it would try to open a browser
            print(f"🔐 Logging in user1 with pre-configured token...")
            # Determine if it's gmail.com (personal) or organization account
            provider1 = 'google_personal' if '@gmail.com' in user1_email else 'google_org'
            client1 = sc.login(user1_email, provider=provider1, verbose=False)
            user1 = GDriveAdapter(client1)  # Wrap in adapter for backward compatibility
            print(f"✅ User1 logged in successfully")
            
            print(f"🔐 Logging in user2 with pre-configured token...")
            provider2 = 'google_personal' if '@gmail.com' in user2_email else 'google_org'
            client2 = sc.login(user2_email, provider=provider2, verbose=False)
            user2 = GDriveAdapter(client2)  # Wrap in adapter for backward compatibility
            print(f"✅ User2 logged in successfully")
        else:
            # Local development - try with credentials files if they exist
            # Determine provider based on email domain
            print(f"🔐 Logging in user1 locally...")
            provider1 = 'google_personal' if '@gmail.com' in user1_email else 'google_org'
            client1 = sc.login(user1_email, provider=provider1, verbose=False)
            user1 = GDriveAdapter(client1)
                
            print(f"🔐 Logging in user2 locally...")
            provider2 = 'google_personal' if '@gmail.com' in user2_email else 'google_org'
            client2 = sc.login(user2_email, provider=provider2, verbose=False)
            user2 = GDriveAdapter(client2)
        
        # Clean slate
        user1.reset_syftbox()
        user2.reset_syftbox()
        
        yield {'user1': user1, 'user2': user2}
        
    except Exception as e:
        # In CI, this should be a failure, not a skip
        if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
            pytest.fail(f"Failed to set up integration test clients in CI: {e}")
        else:
            pytest.skip(f"Could not set up integration test clients: {e}")
    
    finally:
        # Cleanup
        try:
            cleanup_test_folders(user1, user2)
        except:
            pass

@pytest.fixture(autouse=True)
def reset_mocks():
    """Automatically reset mocks between tests"""
    yield
    # Reset happens after each test

# ========== Test Markers and Skip Logic ==========

def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "two_user: mark test as requiring two users"
    )
    config.addinivalue_line(
        "markers", "auth: mark test as authentication related"
    )
    config.addinivalue_line(
        "markers", "syftbox: mark test as SyftBox functionality test"
    )
    config.addinivalue_line(
        "markers", "cleanup: mark test as cleanup/teardown test"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection based on environment"""
    skip_integration = pytest.mark.skip(reason="Integration tests require SYFT_TEST_MODE=integration")
    skip_slow = pytest.mark.skip(reason="Slow tests skipped in quick mode")
    
    for item in items:
        # Skip integration tests unless explicitly running them
        if "integration" in item.keywords and not is_integration_test():
            item.add_marker(skip_integration)
        
        # Skip slow tests in CI PRs unless specifically requested
        if "slow" in item.keywords and is_ci_environment() and not is_integration_test():
            item.add_marker(skip_slow)

# ========== Test Utilities ==========

def assert_folder_structure(client, expected_folders):
    """Assert that expected folders exist in Google Drive"""
    for folder_name in expected_folders:
        assert client._folder_exists(folder_name), f"Missing folder: {folder_name}"

def create_test_folder(service, name, parent='root'):
    """Helper to create test folders"""
    return service.files().create(
        body={
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent]
        },
        fields='id'
    ).execute()