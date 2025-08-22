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
        self.files = {}    # file_id -> file_data
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
        self.files.clear()
        self.permissions.clear()
        self.next_id = 1000

class MockFilesResource:
    def __init__(self, service):
        self.service = service
    
    def create(self, body=None, fields=None):
        return MockCreateRequest(self.service, body, fields)
    
    def list(self, q=None, fields=None, pageSize=None, pageToken=None):
        return MockListRequest(self.service, q, fields, pageSize, pageToken)
    
    def get(self, fileId=None, fields=None):
        return MockGetRequest(self.service, fileId, fields)
    
    def delete(self, fileId=None):
        return MockDeleteRequest(self.service, fileId)
    
    def permissions(self):
        return MockPermissionsResource(self.service)

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
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "test-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
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

@pytest.fixture
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
    
    # Create clients
    user1_email = test_users['user1']['email']
    user2_email = test_users['user2']['email']
    
    try:
        user1 = sc.login(user1_email, force_relogin=True)
        user2 = sc.login(user2_email, force_relogin=True)
        
        # Clean slate
        user1.reset_syftbox()
        user2.reset_syftbox()
        
        yield {'user1': user1, 'user2': user2}
        
    except Exception as e:
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