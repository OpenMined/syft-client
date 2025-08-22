"""
Integration tests for authentication with real Google Drive
"""
import os
import pytest
import tempfile
from pathlib import Path

import syft_client as sc


@pytest.mark.integration
@pytest.mark.auth
class TestRealAuthentication:
    """Test authentication with real Google credentials"""
    
    def test_login_with_stored_credentials(self, test_users):
        """Test login using stored credentials from wallet"""
        user1_email = test_users['user1']['email']
        
        print(f"\n🔐 Testing stored credential login for {user1_email}")
        
        try:
            client = sc.login(user1_email, verbose=True)
            
            # Verify authentication success
            assert client.authenticated, "Client should be authenticated"
            assert client.service is not None, "Google Drive service should be available"
            assert client.my_email == user1_email, f"Email mismatch: {client.my_email} vs {user1_email}"
            
            print(f"   ✅ Successfully authenticated as {client.my_email}")
            
        except Exception as e:
            pytest.fail(f"Authentication failed: {e}")
    
    def test_force_relogin(self, test_users):
        """Test force re-authentication"""
        user1_email = test_users['user1']['email']
        
        print(f"\n🔄 Testing force relogin for {user1_email}")
        
        try:
            # First login
            client1 = sc.login(user1_email, verbose=False)
            assert client1.authenticated, "First login should succeed"
            
            # Force relogin
            client2 = sc.login(user1_email, verbose=True, force_relogin=True)
            assert client2.authenticated, "Force relogin should succeed"
            assert client2.my_email == user1_email, "Email should match"
            
            print(f"   ✅ Force relogin successful")
            
        except Exception as e:
            pytest.fail(f"Force relogin failed: {e}")
    
    def test_multiple_user_authentication(self, test_users):
        """Test authentication with multiple users"""
        user1_email = test_users['user1']['email']
        user2_email = test_users['user2']['email']
        
        print(f"\n👥 Testing multiple user authentication")
        
        try:
            # Authenticate both users
            client1 = sc.login(user1_email, verbose=False)
            client2 = sc.login(user2_email, verbose=False)
            
            # Verify both are authenticated
            assert client1.authenticated, "User1 should be authenticated"
            assert client2.authenticated, "User2 should be authenticated"
            
            assert client1.my_email == user1_email, f"User1 email mismatch"
            assert client2.my_email == user2_email, f"User2 email mismatch"
            
            # Verify they are different clients
            assert client1.my_email != client2.my_email, "Clients should have different emails"
            
            print(f"   ✅ User1 authenticated: {client1.my_email}")
            print(f"   ✅ User2 authenticated: {client2.my_email}")
            
        except Exception as e:
            pytest.fail(f"Multiple user authentication failed: {e}")


@pytest.mark.integration
@pytest.mark.auth
class TestAccountManagement:
    """Test account management with real credentials"""
    
    def test_list_accounts_integration(self):
        """Test listing accounts with real wallet"""
        print(f"\n📋 Testing account listing")
        
        try:
            accounts = sc.list_accounts()
            
            assert isinstance(accounts, list), "Should return a list"
            print(f"   Found {len(accounts)} accounts in wallet")
            
            for account in accounts:
                print(f"   📧 {account}")
                assert "@" in account, f"Account should be valid email: {account}"
            
            # Should have at least our test accounts
            assert len(accounts) >= 2, "Should have at least 2 test accounts"
            
            print(f"   ✅ Account listing successful")
            
        except Exception as e:
            pytest.fail(f"Account listing failed: {e}")
    
    def test_account_wallet_structure(self):
        """Test that wallet directory structure is correct"""
        print(f"\n📁 Testing wallet structure")
        
        try:
            # Get wallet directory
            from syft_client.auth import _get_wallet_dir
            wallet_dir = _get_wallet_dir()
            
            assert wallet_dir.exists(), f"Wallet directory should exist: {wallet_dir}"
            print(f"   Wallet directory: {wallet_dir}")
            
            # List account directories
            account_dirs = [d for d in wallet_dir.iterdir() if d.is_dir()]
            print(f"   Found {len(account_dirs)} account directories")
            
            for account_dir in account_dirs:
                print(f"   📂 {account_dir.name}")
                
                # Check for required files
                creds_file = account_dir / "credentials.json"
                info_file = account_dir / "account_info.json"
                token_file = account_dir / "token.json"
                
                assert creds_file.exists(), f"Credentials file should exist: {creds_file}"
                assert info_file.exists(), f"Account info should exist: {info_file}"
                
                if token_file.exists():
                    print(f"     ✅ Token file found")
                else:
                    print(f"     ⚠️  No token file (will need OAuth)")
            
            print(f"   ✅ Wallet structure is correct")
            
        except Exception as e:
            pytest.fail(f"Wallet structure check failed: {e}")


@pytest.mark.integration
@pytest.mark.auth
class TestAuthenticationMethods:
    """Test different authentication methods"""
    
    def test_credentials_path_authentication(self, test_users):
        """Test authentication with explicit credentials path"""
        user1_email = test_users['user1']['email']
        creds_path = test_users['user1']['creds_file']
        
        # Expand user path
        expanded_path = os.path.expanduser(creds_path)
        
        if not os.path.exists(expanded_path):
            pytest.skip(f"Credentials file not found: {expanded_path}")
        
        print(f"\n🔑 Testing explicit credentials path authentication")
        print(f"   Email: {user1_email}")
        print(f"   Credentials: {expanded_path}")
        
        try:
            client = sc.login(user1_email, expanded_path, verbose=True)
            
            assert client.authenticated, "Client should be authenticated"
            assert client.my_email == user1_email, f"Email mismatch"
            
            print(f"   ✅ Authentication with explicit path successful")
            
        except Exception as e:
            pytest.fail(f"Explicit path authentication failed: {e}")
    
    def test_auto_account_selection(self):
        """Test automatic account selection when only one account"""
        print(f"\n🎯 Testing automatic account selection")
        
        # This test depends on wallet state, so we'll just verify the behavior
        # doesn't crash when multiple accounts are available
        try:
            accounts = sc.list_accounts()
            
            if len(accounts) == 1:
                print(f"   Only one account available: {accounts[0]}")
                client = sc.login(verbose=False)  # Should auto-select
                assert client.authenticated, "Auto-selection should work"
                print(f"   ✅ Auto-selected: {client.my_email}")
            else:
                print(f"   Multiple accounts available: {accounts}")
                print(f"   ⚠️  Auto-selection would prompt (skipping interactive test)")
            
        except Exception as e:
            # This might fail in CI if interactive input is required
            if "No account selected" in str(e):
                print(f"   ✅ Correctly prompted for account selection")
            else:
                pytest.fail(f"Auto-selection test failed: {e}")


@pytest.mark.integration
@pytest.mark.auth
class TestAuthenticationErrors:
    """Test authentication error handling"""
    
    def test_invalid_email_authentication(self):
        """Test authentication with invalid email"""
        invalid_email = "nonexistent@example.com"
        
        print(f"\n❌ Testing authentication with invalid email: {invalid_email}")
        
        try:
            # This should fail because the email is not in the wallet
            with pytest.raises(Exception):  # Could be RuntimeError or other
                sc.login(invalid_email, verbose=False)
            
            print(f"   ✅ Correctly rejected invalid email")
            
        except Exception as e:
            # The test passes if it raises any exception
            print(f"   ✅ Authentication failed as expected: {type(e).__name__}")
    
    def test_missing_credentials_file(self):
        """Test authentication with missing credentials file"""
        test_email = "test@example.com"
        fake_creds_path = "/nonexistent/credentials.json"
        
        print(f"\n❌ Testing authentication with missing credentials file")
        
        with pytest.raises(RuntimeError, match="Credentials file not found"):
            sc.login(test_email, fake_creds_path)
        
        print(f"   ✅ Correctly rejected missing credentials file")
    
    def test_malformed_credentials_file(self):
        """Test authentication with malformed credentials file"""
        test_email = "test@example.com"
        
        print(f"\n❌ Testing authentication with malformed credentials file")
        
        # Create a temporary malformed credentials file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name
        
        try:
            with pytest.raises(Exception):  # Could be JSON decode error or other
                sc.login(test_email, temp_path, verbose=False)
            
            print(f"   ✅ Correctly rejected malformed credentials file")
            
        finally:
            # Cleanup
            try:
                os.unlink(temp_path)
            except:
                pass


@pytest.mark.integration
@pytest.mark.auth
class TestTokenManagement:
    """Test OAuth token management"""
    
    def test_token_refresh_cycle(self, test_users):
        """Test that tokens can be refreshed"""
        user1_email = test_users['user1']['email']
        
        print(f"\n🔄 Testing token refresh cycle")
        
        try:
            # Login (may use cached token)
            client1 = sc.login(user1_email, verbose=False)
            assert client1.authenticated, "Initial login should succeed"
            
            # Force a new login (should refresh token if needed)
            client2 = sc.login(user1_email, verbose=False, force_relogin=True)
            assert client2.authenticated, "Refreshed login should succeed"
            
            print(f"   ✅ Token refresh cycle completed")
            
        except Exception as e:
            pytest.fail(f"Token refresh failed: {e}")
    
    def test_token_storage(self, test_users):
        """Test that tokens are properly stored and retrieved"""
        user1_email = test_users['user1']['email']
        
        print(f"\n💾 Testing token storage")
        
        try:
            from syft_client.auth import _get_account_dir
            
            # Get account directory
            account_dir = _get_account_dir(user1_email)
            token_file = account_dir / "token.json"
            
            print(f"   Account dir: {account_dir}")
            print(f"   Token file: {token_file}")
            
            # Login to ensure token exists
            client = sc.login(user1_email, verbose=False)
            assert client.authenticated, "Login should succeed"
            
            # Check if token file was created/updated
            if token_file.exists():
                print(f"   ✅ Token file exists")
                
                # Verify token file is valid JSON
                import json
                with open(token_file, 'r') as f:
                    token_data = json.load(f)
                
                assert isinstance(token_data, dict), "Token should be a dictionary"
                assert 'type' in token_data, "Token should have type field"
                
                print(f"   ✅ Token file is valid JSON")
            else:
                print(f"   ⚠️  No token file found (using service account or other method)")
            
        except Exception as e:
            pytest.fail(f"Token storage test failed: {e}")