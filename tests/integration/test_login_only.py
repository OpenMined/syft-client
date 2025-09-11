"""
Minimal integration test to verify login works in CI environment
"""
import os
import pytest
import syft_client as sc


@pytest.mark.integration
class TestLoginOnly:
    """Test only the login functionality in CI"""
    
    def test_login_works_in_ci(self, integration_test_clients):
        """Test that both users can login successfully in CI environment"""
        user1 = integration_test_clients['user1']
        user2 = integration_test_clients['user2']
        
        # Check if we're in CI
        is_ci = os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'
        
        print(f"\n🔍 Testing login in CI mode")
        print(f"   CI environment: {is_ci}")
        print(f"   CI env var: {os.environ.get('CI', 'not set')}")
        print(f"   GITHUB_ACTIONS env var: {os.environ.get('GITHUB_ACTIONS', 'not set')}")
        
        # Test User1 is authenticated
        assert user1.authenticated, "User1 should be authenticated"
        assert user1.my_email is not None, "User1 should have an email"
        print(f"   ✅ User1 authenticated as: {user1.my_email}")
        
        # Test User2 is authenticated
        assert user2.authenticated, "User2 should be authenticated"
        assert user2.my_email is not None, "User2 should have an email"
        print(f"   ✅ User2 authenticated as: {user2.my_email}")
        
        # Test service is available
        assert user1.service is not None, "User1 should have a Drive service"
        assert user2.service is not None, "User2 should have a Drive service"
        print(f"   ✅ Both users have Drive service initialized")
        
        # Test basic Drive operation (list files)
        try:
            # Just list a few files to verify API access works
            results1 = user1.service.files().list(
                pageSize=1,
                fields="files(id, name)"
            ).execute()
            print(f"   ✅ User1 can access Google Drive API")
            
            results2 = user2.service.files().list(
                pageSize=1,
                fields="files(id, name)"
            ).execute()
            print(f"   ✅ User2 can access Google Drive API")
            
        except Exception as e:
            pytest.fail(f"Failed to access Google Drive API: {e}")
        
        print(f"\n✅ Login test passed successfully!")
        print(f"   User1: {user1.my_email}")
        print(f"   User2: {user2.my_email}")
        
    def test_no_browser_opened_in_ci(self, test_users):
        """Verify that login doesn't try to open browser in CI"""
        if not (os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'):
            pytest.skip("This test only runs in CI environment")
            
        from tests.utils.gdrive_adapter import GDriveAdapter
        
        user1_email = test_users['user1']['email']
        
        print(f"\n🔍 Testing that no browser is opened in CI")
        
        # This should use cached token and not open browser
        try:
            provider = 'google_personal' if '@gmail.com' in user1_email else 'google_org'
            syft_client = sc.login(user1_email, provider=provider, verbose=True)
            client = GDriveAdapter(syft_client)
            assert client.authenticated, "Should authenticate with cached token"
            print(f"   ✅ Authenticated without browser: {client.my_email}")
        except Exception as e:
            # If it fails, make sure it's not trying to open a browser
            error_msg = str(e)
            assert "browser" not in error_msg.lower(), f"Should not try to open browser in CI: {error_msg}"
            assert "oauth2" not in error_msg.lower(), f"Should not do OAuth flow in CI: {error_msg}"
            raise