"""
Integration tests for two-user workflow with real Google Drive API
"""
import os
import pytest
import time
from typing import Dict, Any

import syft_client as sc


@pytest.mark.integration
@pytest.mark.two_user
class TestTwoUserWorkflow:
    """Test complete two-user communication workflow"""
    
    def test_bidirectional_friend_setup(self, integration_test_clients):
        """Test complete bidirectional friend setup between two users"""
        user1 = integration_test_clients['user1']
        user2 = integration_test_clients['user2']
        
        # Verify initial state - no friends
        assert len(user1.friends) == 0, f"User1 should have no friends initially, got: {user1.friends}"
        assert len(user2.friends) == 0, f"User2 should have no friends initially, got: {user2.friends}"
        assert len(user2.friend_requests) == 0, f"User2 should have no requests initially, got: {user2.friend_requests}"
        
        # Step 1: User1 adds User2 as friend
        print(f"\n🤝 User1 ({user1.my_email}) adding User2 ({user2.my_email}) as friend...")
        result1 = user1.add_friend(user2.my_email, verbose=True)
        assert result1 is True, "User1 should successfully add User2 as friend"
        
        # Give Google Drive a moment to propagate changes
        time.sleep(2)
        
        # Verify User1's perspective
        user1_friends = user1.friends
        assert user2.my_email in user1_friends, f"User2 should be in User1's friends list: {user1_friends}"
        
        # Verify User2 sees the friend request
        user2_requests = user2.friend_requests
        assert user1.my_email in user2_requests, f"User1 should be in User2's friend requests: {user2_requests}"
        
        # Step 2: User2 adds User1 back (completes the connection)
        print(f"\n🤝 User2 ({user2.my_email}) adding User1 ({user1.my_email}) back...")
        result2 = user2.add_friend(user1.my_email, verbose=True)
        assert result2 is True, "User2 should successfully add User1 as friend"
        
        # Give Google Drive a moment to propagate changes
        time.sleep(2)
        
        # Step 3: Verify bidirectional connection
        user1_friends_final = user1.friends
        user2_friends_final = user2.friends
        user2_requests_final = user2.friend_requests
        
        assert user2.my_email in user1_friends_final, f"User2 should remain in User1's friends: {user1_friends_final}"
        assert user1.my_email in user2_friends_final, f"User1 should be in User2's friends: {user2_friends_final}"
        assert len(user2_requests_final) == 0, f"User2 should have no pending requests after adding User1: {user2_requests_final}"
        
        print(f"✅ Bidirectional connection established successfully!")
        print(f"   User1 friends: {user1_friends_final}")
        print(f"   User2 friends: {user2_friends_final}")
    
    def test_folder_structure_creation(self, integration_test_clients):
        """Test that correct folder structure is created in Google Drive"""
        user1 = integration_test_clients['user1']
        user2 = integration_test_clients['user2']
        
        # Add friend relationship
        user1.add_friend(user2.my_email, verbose=False)
        time.sleep(2)
        
        # Extract username parts for folder naming
        user1_name = user1.my_email.split('@')[0].replace('.', '_').replace('+', '_')
        user2_name = user2.my_email.split('@')[0].replace('.', '_').replace('+', '_')
        
        # Expected folder structure in User1's drive
        expected_user1_folders = [
            f"syft_{user1_name}_to_{user2_name}_pending",
            f"syft_{user1_name}_to_{user2_name}_outbox_inbox",
            f"syft_{user1_name}_archive_{user2_name}"
        ]
        
        print(f"\n📁 Checking folder structure for User1...")
        for folder_name in expected_user1_folders:
            exists = user1._folder_exists(folder_name)
            print(f"   {folder_name}: {'✅' if exists else '❌'}")
            assert exists, f"Expected folder not found in User1's drive: {folder_name}"
        
        print(f"✅ All expected folders created successfully!")
    
    def test_syftbox_operations(self, integration_test_clients):
        """Test SyftBox creation and reset operations"""
        user1 = integration_test_clients['user1']
        
        print(f"\n📦 Testing SyftBox operations for User1...")
        
        # Test SyftBox exists (should be created in fixture)
        assert user1._folder_exists("SyftBoxTransportService"), "SyftBoxTransportService folder should exist"
        
        # Test reset operation
        print("🔄 Resetting SyftBox...")
        reset_result = user1.reset_syftbox()
        assert reset_result is not None, "Reset should return folder ID"
        
        time.sleep(2)  # Allow propagation
        
        # Verify SyftBox still exists after reset
        assert user1._folder_exists("SyftBoxTransportService"), "SyftBoxTransportService should exist after reset"
        
        print("✅ SyftBox operations completed successfully!")
    
    def test_friend_management_edge_cases(self, integration_test_clients):
        """Test edge cases in friend management"""
        user1 = integration_test_clients['user1']
        user2 = integration_test_clients['user2']
        
        print(f"\n🧪 Testing friend management edge cases...")
        
        # Test adding self as friend (should fail)
        self_add_result = user1.add_friend(user1.my_email, verbose=False)
        assert self_add_result is False, "Adding self as friend should fail"
        
        # Test adding duplicate friend
        user1.add_friend(user2.my_email, verbose=False)
        time.sleep(1)
        
        duplicate_add_result = user1.add_friend(user2.my_email, verbose=False)
        # This might return True or False depending on implementation - just ensure it doesn't crash
        assert duplicate_add_result in [True, False], "Duplicate friend addition should not crash"
        
        # Test adding invalid email format
        invalid_add_result = user1.add_friend("invalid-email", verbose=False)
        assert invalid_add_result is False, "Adding invalid email should fail"
        
        print("✅ Edge cases handled correctly!")
    
    def test_multiple_friends(self, integration_test_clients):
        """Test managing multiple friend connections"""
        user1 = integration_test_clients['user1']
        user2 = integration_test_clients['user2']
        
        # Create a mock third user email (won't actually work but tests the logic)
        mock_user3_email = "test-user3@example.com"
        
        print(f"\n👥 Testing multiple friend connections...")
        
        # Add real friend
        result_real = user1.add_friend(user2.my_email, verbose=False)
        assert result_real is True, "Adding real friend should succeed"
        
        time.sleep(2)
        
        # Try to add mock friend (will create folders but sharing might fail)
        result_mock = user1.add_friend(mock_user3_email, verbose=False)
        # This might succeed or fail depending on how sharing is handled
        print(f"   Mock friend addition result: {result_mock}")
        
        # Check friends list
        friends = user1.friends
        print(f"   User1 friends: {friends}")
        assert user2.my_email in friends, "Real friend should be in list"
        
        print("✅ Multiple friend handling tested!")


@pytest.mark.integration
@pytest.mark.auth
class TestAuthenticationIntegration:
    """Test authentication with real Google Drive"""
    
    def test_user_authentication(self, test_users):
        """Test that users can authenticate successfully"""
        user1_email = test_users['user1']['email']
        user2_email = test_users['user2']['email']
        
        print(f"\n🔐 Testing authentication for both users...")
        
        # Test User1 authentication
        try:
            user1 = sc.login(user1_email, verbose=False)
            assert user1.authenticated, "User1 should be authenticated"
            assert user1.my_email == user1_email, f"User1 email mismatch: {user1.my_email} vs {user1_email}"
            print(f"   ✅ User1 ({user1.my_email}) authenticated successfully")
        except Exception as e:
            pytest.fail(f"User1 authentication failed: {e}")
        
        # Test User2 authentication
        try:
            user2 = sc.login(user2_email, verbose=False)
            assert user2.authenticated, "User2 should be authenticated"
            assert user2.my_email == user2_email, f"User2 email mismatch: {user2.my_email} vs {user2_email}"
            print(f"   ✅ User2 ({user2.my_email}) authenticated successfully")
        except Exception as e:
            pytest.fail(f"User2 authentication failed: {e}")
        
        print("✅ Both users authenticated successfully!")
    
    def test_account_management(self, test_users):
        """Test account management functions"""
        print(f"\n👤 Testing account management...")
        
        # Test listing accounts
        accounts = sc.list_accounts()
        print(f"   Available accounts: {accounts}")
        assert isinstance(accounts, list), "list_accounts should return a list"
        
        # Both test users should be in the list
        user1_email = test_users['user1']['email']
        user2_email = test_users['user2']['email']
        
        assert user1_email in accounts, f"User1 ({user1_email}) should be in accounts list"
        assert user2_email in accounts, f"User2 ({user2_email}) should be in accounts list"
        
        print("✅ Account management working correctly!")


@pytest.mark.integration
@pytest.mark.syftbox
class TestSyftBoxIntegration:
    """Test SyftBox operations with real Google Drive"""
    
    def test_syftbox_lifecycle(self, integration_test_clients):
        """Test complete SyftBox lifecycle operations"""
        user1 = integration_test_clients['user1']
        
        print(f"\n📦 Testing SyftBox lifecycle for User1...")
        
        # Verify SyftBox exists initially (created by fixture)
        initial_exists = user1._folder_exists("SyftBoxTransportService")
        assert initial_exists, "SyftBox should exist initially"
        print("   ✅ Initial SyftBox exists")
        
        # Test reset (delete and recreate)
        print("   🔄 Performing reset...")
        reset_id = user1.reset_syftbox()
        assert reset_id is not None, "Reset should return new folder ID"
        
        time.sleep(3)  # Allow Google Drive to propagate changes
        
        # Verify SyftBox exists after reset
        post_reset_exists = user1._folder_exists("SyftBoxTransportService")
        assert post_reset_exists, "SyftBox should exist after reset"
        print("   ✅ SyftBox exists after reset")
        
        # Test multiple resets (stress test)
        print("   🔄 Performing second reset...")
        second_reset_id = user1.reset_syftbox()
        assert second_reset_id is not None, "Second reset should also work"
        assert second_reset_id != reset_id, "Each reset should create new folder"
        
        time.sleep(2)
        
        final_exists = user1._folder_exists("SyftBoxTransportService")
        assert final_exists, "SyftBox should exist after second reset"
        print("   ✅ Multiple resets work correctly")
        
        print("✅ SyftBox lifecycle tested successfully!")


@pytest.mark.integration
@pytest.mark.slow
class TestStressAndPerformance:
    """Stress tests and performance validation"""
    
    def test_rapid_friend_operations(self, integration_test_clients):
        """Test rapid friend addition and removal operations"""
        user1 = integration_test_clients['user1']
        user2 = integration_test_clients['user2']
        
        print(f"\n⚡ Testing rapid friend operations...")
        
        # Rapid friend additions (testing rate limits and consistency)
        start_time = time.time()
        
        for i in range(3):  # Limited iterations to avoid rate limits
            print(f"   Iteration {i+1}/3...")
            
            # Add friend
            add_result = user1.add_friend(user2.my_email, verbose=False)
            assert add_result in [True, False], f"Add result should be boolean, got: {add_result}"
            
            time.sleep(1)  # Brief pause to avoid rate limits
            
            # Check friends list
            friends = user1.friends
            assert isinstance(friends, list), "Friends should return a list"
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"   ✅ Completed 3 iterations in {duration:.2f} seconds")
        print(f"   ✅ No errors during rapid operations")
        
        # Final state check
        final_friends = user1.friends
        print(f"   Final friends list: {final_friends}")
    
    def test_folder_creation_performance(self, integration_test_clients):
        """Test performance of folder creation operations"""
        user1 = integration_test_clients['user1']
        
        print(f"\n📁 Testing folder creation performance...")
        
        start_time = time.time()
        
        # Create some test folders
        test_folders = []
        for i in range(5):  # Limited to avoid clutter
            folder_name = f"test_performance_folder_{i}"
            folder_id = user1._create_folder(folder_name)
            if folder_id:
                test_folders.append((folder_name, folder_id))
                print(f"   ✅ Created folder {i+1}/5: {folder_name}")
            
            time.sleep(0.5)  # Brief pause between operations
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"   ✅ Created {len(test_folders)} folders in {duration:.2f} seconds")
        print(f"   Average time per folder: {duration/max(len(test_folders), 1):.2f} seconds")
        
        # Cleanup test folders
        print("   🧹 Cleaning up test folders...")
        for folder_name, folder_id in test_folders:
            try:
                user1.service.files().delete(fileId=folder_id).execute()
                print(f"   🗑️  Deleted: {folder_name}")
            except Exception as e:
                print(f"   ⚠️  Could not delete {folder_name}: {e}")
        
        print("✅ Performance test completed!")


@pytest.mark.integration
@pytest.mark.cleanup
class TestCleanupOperations:
    """Test cleanup and maintenance operations"""
    
    def test_cleanup_verification(self, integration_test_clients):
        """Verify that test cleanup operations work correctly"""
        user1 = integration_test_clients['user1']
        user2 = integration_test_clients['user2']
        
        print(f"\n🧹 Testing cleanup operations...")
        
        # Create some test data
        user1.add_friend(user2.my_email, verbose=False)
        time.sleep(2)
        
        # Verify data exists
        initial_friends = user1.friends
        print(f"   Initial friends: {initial_friends}")
        assert len(initial_friends) > 0, "Should have created friend connection"
        
        # Test reset (which is our main cleanup mechanism)
        print("   Performing SyftBox reset...")
        user1.reset_syftbox()
        user2.reset_syftbox()
        
        time.sleep(3)  # Allow cleanup to complete
        
        # Verify cleanup
        post_cleanup_friends_1 = user1.friends
        post_cleanup_friends_2 = user2.friends
        
        print(f"   User1 friends after cleanup: {post_cleanup_friends_1}")
        print(f"   User2 friends after cleanup: {post_cleanup_friends_2}")
        
        # After reset, friends lists should be empty
        assert len(post_cleanup_friends_1) == 0, "User1 should have no friends after reset"
        assert len(post_cleanup_friends_2) == 0, "User2 should have no friends after reset"
        
        print("✅ Cleanup operations working correctly!")