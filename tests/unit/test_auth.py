"""
Unit tests for authentication functionality
"""
import os
import json
import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

import syft_client.auth as auth
from syft_client.gdrive_unified import GDriveUnifiedClient


class TestWalletFunctions:
    """Test wallet management functions"""
    
    def test_get_wallet_dir(self):
        """Test wallet directory path generation"""
        wallet_dir = auth._get_wallet_dir()
        expected = Path.home() / ".syft" / "gdrive"
        assert wallet_dir == expected
    
    def test_get_account_dir(self):
        """Test account directory path generation"""
        email = "test@gmail.com"
        account_dir = auth._get_account_dir(email)
        expected = Path.home() / ".syft" / "gdrive" / "test_at_gmail_com"
        assert account_dir == expected
    
    def test_get_account_dir_sanitizes_email(self):
        """Test that email is properly sanitized for directory names"""
        email = "user.name+tag@example.co.uk"
        account_dir = auth._get_account_dir(email)
        expected = Path.home() / ".syft" / "gdrive" / "user_name+tag_at_example_co_uk"
        assert account_dir == expected

@pytest.mark.unit
class TestCredentialsManagement:
    """Test credential storage and retrieval"""
    
    def test_get_stored_credentials_path_exists(self, mock_wallet_dir):
        """Test retrieving existing credentials"""
        email = "test@gmail.com"
        account_dir = mock_wallet_dir / "test_at_gmail_com"
        account_dir.mkdir(parents=True)
        creds_path = account_dir / "credentials.json"
        creds_path.write_text('{"test": "data"}')
        
        result = auth._get_stored_credentials_path(email)
        assert result == str(creds_path)
    
    def test_get_stored_credentials_path_not_exists(self, mock_wallet_dir):
        """Test retrieving non-existent credentials"""
        email = "test@gmail.com"
        result = auth._get_stored_credentials_path(email)
        assert result is None
    
    def test_save_token_success(self, mock_wallet_dir):
        """Test successful token saving"""
        email = "test@gmail.com"
        token_data = {
            "type": "authorized_user",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "refresh_token": "test-refresh-token"
        }
        
        result = auth._save_token(email, token_data)
        assert result is True
        
        # Verify token was saved
        account_dir = mock_wallet_dir / "test_at_gmail_com"
        token_path = account_dir / "token.json"
        assert token_path.exists()
        
        saved_data = json.loads(token_path.read_text())
        assert saved_data == token_data
    
    def test_add_to_wallet_success(self, mock_wallet_dir, temp_credentials_file):
        """Test successful credential addition to wallet"""
        email = "test@gmail.com"
        
        result = auth._add_to_wallet(email, temp_credentials_file, verbose=False)
        assert result is True
        
        # Verify files were created
        account_dir = mock_wallet_dir / "test_at_gmail_com"
        assert account_dir.exists()
        assert (account_dir / "credentials.json").exists()
        assert (account_dir / "account_info.json").exists()
        
        # Verify account info
        info_data = json.loads((account_dir / "account_info.json").read_text())
        assert info_data["email"] == email
    
    def test_add_to_wallet_missing_file(self, mock_wallet_dir):
        """Test adding non-existent credentials file"""
        email = "test@gmail.com"
        fake_path = "/nonexistent/credentials.json"
        
        result = auth._add_to_wallet(email, fake_path, verbose=False)
        assert result is False
    
    def test_list_wallet_accounts(self, mock_wallet_dir):
        """Test listing accounts in wallet"""
        # Create test accounts
        accounts = ["user1@gmail.com", "user2@example.com"]
        for email in accounts:
            account_dir = mock_wallet_dir / email.replace("@", "_at_").replace(".", "_")
            account_dir.mkdir(parents=True)
            info_path = account_dir / "account_info.json"
            info_path.write_text(json.dumps({"email": email}))
        
        result = auth._list_wallet_accounts()
        assert set(result) == set(accounts)
    
    def test_list_wallet_accounts_empty(self, mock_wallet_dir):
        """Test listing accounts from empty wallet"""
        result = auth._list_wallet_accounts()
        assert result == []


@pytest.mark.unit 
class TestLoginFunction:
    """Test the main login function"""
    
    @patch('syft_client.auth.create_gdrive_client')
    @patch('syft_client.auth._get_stored_credentials_path')
    def test_login_with_stored_credentials(self, mock_get_creds, mock_create_client):
        """Test login with existing stored credentials"""
        email = "test@gmail.com"
        mock_get_creds.return_value = "/path/to/creds.json"
        
        mock_client = Mock()
        mock_client.my_email = email
        mock_client._create_shortcuts_for_shared_folders.return_value = {'created': 1}
        mock_create_client.return_value = mock_client
        
        with patch('builtins.print'):  # Suppress print output
            result = auth.login(email, verbose=False)
        
        assert result == mock_client
        mock_create_client.assert_called_once_with(email, verbose=False, force_relogin=False)
        mock_client._create_shortcuts_for_shared_folders.assert_called_once_with(verbose=False)
    
    @patch('syft_client.auth._list_wallet_accounts')
    @patch('syft_client.auth.create_gdrive_client')
    @patch('syft_client.auth._get_stored_credentials_path')
    def test_login_auto_select_single_account(self, mock_get_creds, mock_create_client, mock_list_accounts):
        """Test auto-selecting single account when no email provided"""
        email = "test@gmail.com"
        mock_list_accounts.return_value = [email]
        mock_get_creds.return_value = "/path/to/creds.json"
        
        mock_client = Mock()
        mock_client.my_email = email
        mock_client._create_shortcuts_for_shared_folders.return_value = {'created': 0}
        mock_create_client.return_value = mock_client
        
        with patch('builtins.print'):
            result = auth.login(verbose=False)
        
        assert result == mock_client
        mock_create_client.assert_called_once_with(email, verbose=False, force_relogin=False)
    
    @patch('syft_client.auth._list_wallet_accounts')
    def test_login_no_accounts_raises_error(self, mock_list_accounts):
        """Test that login raises error when no accounts in wallet"""
        mock_list_accounts.return_value = []
        
        with pytest.raises(RuntimeError, match="No accounts found in wallet"):
            auth.login()
    
    @patch('syft_client.auth._add_to_wallet') 
    @patch('syft_client.auth.create_gdrive_client')
    def test_login_with_credentials_path(self, mock_create_client, mock_add_wallet, temp_credentials_file):
        """Test login with provided credentials path"""
        email = "test@gmail.com"
        mock_add_wallet.return_value = True
        
        mock_client = Mock()
        mock_client.my_email = email
        mock_client._create_shortcuts_for_shared_folders.return_value = {'created': 0}
        mock_create_client.return_value = mock_client
        
        with patch('builtins.print'):
            result = auth.login(email, temp_credentials_file, verbose=False)
        
        assert result == mock_client
        mock_add_wallet.assert_called_once_with(email, temp_credentials_file, verbose=False)
        mock_create_client.assert_called_once_with(email, verbose=False, force_relogin=False)
    
    def test_login_missing_credentials_file_raises_error(self):
        """Test login with non-existent credentials file"""
        email = "test@gmail.com"
        fake_path = "/nonexistent/credentials.json"
        
        with pytest.raises(RuntimeError, match="Credentials file not found"):
            auth.login(email, fake_path)


@pytest.mark.unit
class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_get_credentials_setup_url(self):
        """Test credentials setup URL generation"""
        email = "test@gmail.com"
        url = auth._get_credentials_setup_url(email)
        expected = "https://console.cloud.google.com/apis/credentials?authuser=test%40gmail.com"
        assert url == expected
    
    def test_get_credentials_setup_url_special_chars(self):
        """Test URL generation with special characters in email"""
        email = "user+tag@example.com"
        url = auth._get_credentials_setup_url(email)
        expected = "https://console.cloud.google.com/apis/credentials?authuser=user%2Btag%40example.com"
        assert url == expected


@pytest.mark.unit
class TestAccountManagement:
    """Test account management functions"""
    
    def test_list_accounts(self, mock_wallet_dir):
        """Test list_accounts function"""
        # Create test accounts
        emails = ["user1@gmail.com", "user2@example.com"]
        for email in emails:
            account_dir = mock_wallet_dir / email.replace("@", "_at_").replace(".", "_")
            account_dir.mkdir(parents=True)
            info_path = account_dir / "account_info.json"
            info_path.write_text(json.dumps({"email": email}))
        
        result = auth.list_accounts()
        assert set(result) == set(emails)
    
    @patch('syft_client.auth._get_account_dir')
    @patch('shutil.rmtree')
    def test_logout(self, mock_rmtree, mock_get_account_dir):
        """Test logout function"""
        email = "test@gmail.com"
        account_dir = Path("/fake/path")
        mock_get_account_dir.return_value = account_dir
        
        with patch.object(account_dir, 'exists', return_value=True):
            with patch('builtins.print'):
                result = auth.logout(email, verbose=False)
        
        assert result is True
        mock_rmtree.assert_called_once_with(account_dir)
    
    @patch('syft_client.auth._get_account_dir')
    def test_logout_account_not_found(self, mock_get_account_dir):
        """Test logout with non-existent account"""
        email = "test@gmail.com"
        account_dir = Path("/fake/path")
        mock_get_account_dir.return_value = account_dir
        
        with patch.object(account_dir, 'exists', return_value=False):
            with patch('builtins.print'):
                result = auth.logout(email, verbose=False)
        
        assert result is False
    
    def test_add_current_credentials_to_wallet(self, temp_credentials_file, mock_wallet_dir):
        """Test adding current credentials to wallet"""
        email = "test@gmail.com"
        
        with patch('builtins.print'):
            result = auth.add_current_credentials_to_wallet(email, temp_credentials_file, verbose=False)
        
        assert result is True
        
        # Verify credentials were added
        account_dir = mock_wallet_dir / "test_at_gmail_com"
        assert (account_dir / "credentials.json").exists()
        assert (account_dir / "account_info.json").exists()