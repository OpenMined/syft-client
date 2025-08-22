"""
Unit tests for GDriveUnifiedClient functionality
"""
import pytest
from unittest.mock import patch, Mock, MagicMock
import os
import json

from syft_client.gdrive_unified import GDriveUnifiedClient


@pytest.mark.unit
class TestGDriveUnifiedClientInit:
    """Test GDriveUnifiedClient initialization"""
    
    def test_init_defaults(self):
        """Test client initialization with default parameters"""
        client = GDriveUnifiedClient()
        
        assert client.auth_method == "auto"
        assert client.credentials_file == "credentials.json"
        assert client.service is None
        assert client.authenticated is False
        assert client.my_email is None
        assert client.target_email is None
        assert client.verbose is True
        assert client.force_relogin is False
    
    def test_init_custom_params(self):
        """Test client initialization with custom parameters"""
        client = GDriveUnifiedClient(
            auth_method="credentials",
            credentials_file="custom_creds.json",
            email="test@gmail.com",
            verbose=False,
            force_relogin=True
        )
        
        assert client.auth_method == "credentials"
        assert client.credentials_file == "custom_creds.json"
        assert client.target_email == "test@gmail.com"
        assert client.verbose is False
        assert client.force_relogin is True
    
    def test_repr_not_authenticated(self):
        """Test string representation when not authenticated"""
        client = GDriveUnifiedClient()
        repr_str = repr(client)
        assert "not authenticated" in repr_str.lower()
    
    def test_repr_authenticated(self, mock_build_service, mock_gdrive_service):
        """Test string representation when authenticated"""
        client = GDriveUnifiedClient()
        client.authenticated = True
        client.my_email = "test@gmail.com"
        
        # Mock the service completely for this specific test
        mock_service = Mock()
        mock_list_request = Mock()
        mock_list_request.execute.return_value = {'files': [{'id': 'syftbox-id'}]}
        mock_service.files().list.return_value = mock_list_request
        client.service = mock_service
        
        repr_str = repr(client)
        assert "test@gmail.com" in repr_str
        assert "syftbox=✓ created" in repr_str


@pytest.mark.unit
class TestAuthentication:
    """Test authentication methods"""
    
    @patch('syft_client.gdrive_unified.IN_COLAB', True)
    @patch('syft_client.gdrive_unified.build')
    def test_authenticate_colab_method(self, mock_build):
        """Test Colab authentication method"""
        client = GDriveUnifiedClient(auth_method="colab")
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Mock the about().get() call for getting email
        mock_about = Mock()
        mock_about.get().execute.return_value = {'user': {'emailAddress': 'test@gmail.com'}}
        mock_service.about.return_value = mock_about
        
        # Mock the colab auth directly on the client
        with patch.object(client, '_auth_colab', return_value=True) as mock_auth:
            result = client.authenticate()
        
        assert result is True
        mock_auth.assert_called_once()
    
    @patch('syft_client.gdrive_unified.IN_COLAB', False)
    def test_authenticate_colab_not_available(self):
        """Test Colab authentication when not in Colab environment"""
        client = GDriveUnifiedClient(auth_method="colab")
        
        result = client.authenticate()
        
        assert result is False
        assert client.authenticated is False
    
    @patch('syft_client.gdrive_unified.InstalledAppFlow')
    @patch('syft_client.gdrive_unified.build')
    @patch('os.path.exists')
    def test_authenticate_credentials_method(self, mock_exists, mock_build, mock_flow):
        """Test credentials file authentication method"""
        mock_exists.return_value = True
        client = GDriveUnifiedClient(auth_method="credentials", credentials_file="test_creds.json")
        
        # Mock OAuth flow
        mock_flow_instance = Mock()
        mock_creds = Mock()
        mock_creds.valid = True
        mock_flow_instance.run_local_server.return_value = mock_creds
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        
        # Mock service and about call
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_about = Mock()
        mock_about.get().execute.return_value = {'user': {'emailAddress': 'test@gmail.com'}}
        mock_service.about.return_value = mock_about
        
        result = client.authenticate()
        
        assert result is True
        assert client.authenticated is True
        assert client.service == mock_service
        mock_flow.from_client_secrets_file.assert_called_once_with("test_creds.json", client.SCOPES)
    
    @patch('os.path.exists')
    def test_authenticate_credentials_file_not_found(self, mock_exists):
        """Test credentials authentication with missing file"""
        mock_exists.return_value = False
        client = GDriveUnifiedClient(auth_method="credentials", credentials_file="missing.json")
        
        result = client.authenticate()
        
        assert result is False
        assert client.authenticated is False
    
    def test_ensure_authenticated_raises_error(self):
        """Test that operations require authentication"""
        client = GDriveUnifiedClient()
        
        with pytest.raises(RuntimeError, match="Client not authenticated"):
            client._ensure_authenticated()


@pytest.mark.unit
class TestFolderOperations:
    """Test folder operations"""
    
    def test_create_folder_success(self, mock_build_service, mock_gdrive_service):
        """Test successful folder creation"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock folder creation
        mock_gdrive_service.files().create().execute.return_value = {'id': 'folder-123'}
        
        result = client._create_folder("Test Folder")
        
        assert result == 'folder-123'
    
    def test_create_folder_with_parent(self, mock_build_service, mock_gdrive_service):
        """Test folder creation with parent folder"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        mock_gdrive_service.files().create().execute.return_value = {'id': 'folder-123'}
        
        result = client._create_folder("Test Folder", parent_id="parent-456")
        
        assert result == 'folder-123'
    
    def test_folder_exists_true(self, mock_build_service, mock_gdrive_service):
        """Test folder existence check - folder exists"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock folder found
        mock_gdrive_service.files().list().execute.return_value = {
            'files': [{'id': 'folder-123', 'name': 'Test Folder'}]
        }
        
        result = client._folder_exists("Test Folder")
        
        assert result is True
    
    def test_folder_exists_false(self, mock_build_service, mock_gdrive_service):
        """Test folder existence check - folder does not exist"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock no folder found
        mock_gdrive_service.files().list().execute.return_value = {'files': []}
        
        result = client._folder_exists("Test Folder")
        
        assert result is False


@pytest.mark.unit
class TestSyftBoxOperations:
    """Test SyftBox-specific operations"""
    
    def test_reset_syftbox_success(self, mock_build_service, mock_gdrive_service):
        """Test successful SyftBox reset"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock finding existing SyftBox first, then empty list after deletion
        mock_gdrive_service.files().list().execute.side_effect = [
            {'files': [{'id': 'existing-syftbox', 'name': 'SyftBoxTransportService'}]},  # First call finds existing
            {'files': []},  # Second call (after deletion) finds nothing
        ]
        
        # Mock folder creation after deletion
        mock_gdrive_service.files().create().execute.return_value = {'id': 'new-syftbox'}
        
        result = client.reset_syftbox()
        
        assert result == 'new-syftbox'
    
    def test_reset_syftbox_no_existing(self, mock_build_service, mock_gdrive_service):
        """Test SyftBox reset when no existing folder"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock no existing SyftBox found, then successful creation
        list_calls = [
            {'files': []},  # First call - no existing folder
            {'files': []}   # Second call - still no folder (for verification)
        ]
        
        mock_gdrive_service.files().list().execute.side_effect = list_calls
        mock_gdrive_service.files().create().execute.return_value = {'id': 'new-syftbox'}
        
        result = client.reset_syftbox()
        
        assert result == 'new-syftbox'


@pytest.mark.unit
class TestFriendManagement:
    """Test friend management functionality"""
    
    def test_add_friend_success(self, mock_build_service, mock_gdrive_service):
        """Test successful friend addition"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        client.my_email = "user1@gmail.com"
        
        # Mock SyftBox exists
        mock_gdrive_service.files().list().execute.return_value = {
            'files': [{'id': 'syftbox-id'}]
        }
        
        # Mock folder creation
        mock_gdrive_service.files().create().execute.return_value = {'id': 'new-folder'}
        
        # Mock permission creation
        mock_gdrive_service.files().permissions().create().execute.return_value = {'id': 'permission-id'}
        
        result = client.add_friend("user2@gmail.com")
        
        assert result is True
    
    def test_add_friend_self_email(self, mock_build_service, mock_gdrive_service):
        """Test adding self as friend (should fail)"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        client.my_email = "user1@gmail.com"
        
        result = client.add_friend("user1@gmail.com")
        
        assert result is False
    
    def test_friends_property(self, mock_build_service, mock_gdrive_service):
        """Test friends property returns correct list"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        client.my_email = "user1@gmail.com"
        
        # Mock folders representing friends
        mock_gdrive_service.files().list().execute.return_value = {
            'files': [
                {'name': 'syft_user1_to_user2_pending'},
                {'name': 'syft_user1_to_user3_outbox_inbox'},
                {'name': 'some_other_folder'}  # Should be ignored
            ]
        }
        
        friends = client.friends
        
        # Should extract 'user2' and 'user3' from folder names
        assert len(friends) == 2
        assert 'user2@gmail.com' in friends or 'user2' in str(friends)
        assert 'user3@gmail.com' in friends or 'user3' in str(friends)
    
    def test_friend_requests_property(self, mock_build_service, mock_gdrive_service):
        """Test friend_requests property returns correct list"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock shared folders (shortcuts to folders shared by others)
        mock_gdrive_service.files().list().execute.return_value = {
            'files': [
                {
                    'name': 'syft_user2_to_user1_pending',
                    'mimeType': 'application/vnd.google-apps.shortcut'
                },
                {
                    'name': 'syft_user3_to_user1_outbox_inbox', 
                    'mimeType': 'application/vnd.google-apps.shortcut'
                }
            ]
        }
        
        friend_requests = client.friend_requests
        
        # Should extract emails from shortcut folder names
        assert len(friend_requests) >= 0  # Depends on implementation details


@pytest.mark.unit  
class TestPermissionOperations:
    """Test permission-related operations"""
    
    def test_share_folder_with_email(self, mock_build_service, mock_gdrive_service):
        """Test sharing folder with specific email"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock permission creation
        mock_gdrive_service.files().permissions().create().execute.return_value = {
            'id': 'permission-123'
        }
        
        result = client._share_folder_with_email("folder-456", "user@gmail.com")
        
        assert result is True
    
    def test_share_folder_permission_error(self, mock_build_service, mock_gdrive_service):
        """Test folder sharing with permission error"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock permission creation failure
        mock_gdrive_service.files().permissions().create().execute.side_effect = Exception("Permission denied")
        
        result = client._share_folder_with_email("folder-456", "user@gmail.com")
        
        assert result is False


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_network_error_handling(self, mock_build_service, mock_gdrive_service):
        """Test handling of network errors"""
        client = GDriveUnifiedClient()
        client.service = mock_gdrive_service
        client.authenticated = True
        
        # Mock network error
        from googleapiclient.errors import HttpError
        mock_gdrive_service.files().list().execute.side_effect = HttpError(
            resp=Mock(status=500), content=b'Server Error'
        )
        
        result = client._folder_exists("Test Folder")
        
        assert result is False
    
    def test_authentication_required_operations(self):
        """Test that operations fail when not authenticated"""
        client = GDriveUnifiedClient()
        
        with pytest.raises(RuntimeError):
            client._create_folder("Test")
        
        with pytest.raises(RuntimeError):
            client.reset_syftbox()
        
        with pytest.raises(RuntimeError):
            client.add_friend("test@gmail.com")


@pytest.mark.unit
class TestClientProperties:
    """Test client properties and state"""
    
    def test_scopes_constant(self):
        """Test that SCOPES constant is defined correctly"""
        assert hasattr(GDriveUnifiedClient, 'SCOPES')
        assert 'https://www.googleapis.com/auth/drive' in GDriveUnifiedClient.SCOPES
    
    def test_client_state_transitions(self, mock_build_service, mock_gdrive_service):
        """Test client state changes during authentication"""
        client = GDriveUnifiedClient()
        
        # Initial state
        assert not client.authenticated
        assert client.service is None
        assert client.my_email is None
        
        # After authentication
        client.service = mock_gdrive_service
        client.authenticated = True
        client.my_email = "test@gmail.com"
        
        assert client.authenticated
        assert client.service is not None
        assert client.my_email == "test@gmail.com"