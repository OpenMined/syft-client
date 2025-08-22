"""
Test utilities for cleanup operations
"""
import os
import time
from typing import List, Optional, Dict, Any
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_test_folders(user1_client, user2_client, verbose: bool = True):
    """
    Clean up test folders created during integration tests
    
    Args:
        user1_client: First user's GDriveUnifiedClient
        user2_client: Second user's GDriveUnifiedClient  
        verbose: Whether to print cleanup progress
    """
    if verbose:
        print("\n🧹 Starting test data cleanup...")
    
    try:
        # Reset SyftBox for both users (this removes all syft_ folders)
        if verbose:
            print(f"   Resetting SyftBox for {user1_client.my_email}...")
        user1_client.reset_syftbox()
        
        if verbose:
            print(f"   Resetting SyftBox for {user2_client.my_email}...")
        user2_client.reset_syftbox()
        
        # Give Google Drive time to propagate changes
        time.sleep(3)
        
        if verbose:
            print("✅ Basic cleanup completed")
            
    except Exception as e:
        logger.error(f"Error during basic cleanup: {e}")
        if verbose:
            print(f"⚠️  Cleanup error: {e}")


def cleanup_all_test_data():
    """
    Comprehensive cleanup of all test data
    This function is called from CI to ensure clean state
    """
    print("🧹 Starting comprehensive test data cleanup...")
    
    try:
        # Import here to avoid circular dependencies
        import syft_client as sc
        
        # Get test user emails from environment
        user1_email = os.environ.get('TEST_USER1_EMAIL')
        user2_email = os.environ.get('TEST_USER2_EMAIL')
        
        if not user1_email or not user2_email:
            print("⚠️  Test user emails not found in environment")
            return
        
        print(f"   Cleaning up for users: {user1_email}, {user2_email}")
        
        # Authenticate both users
        try:
            user1 = sc.login(user1_email, verbose=False)
            user2 = sc.login(user2_email, verbose=False)
            
            print(f"   ✅ Authenticated both users")
            
            # Perform cleanup
            cleanup_test_folders(user1, user2, verbose=True)
            
            # Additional cleanup - remove test performance folders
            cleanup_performance_test_folders(user1)
            cleanup_performance_test_folders(user2)
            
            print("✅ Comprehensive cleanup completed")
            
        except Exception as e:
            logger.error(f"Authentication error during cleanup: {e}")
            print(f"⚠️  Could not authenticate users for cleanup: {e}")
            
    except Exception as e:
        logger.error(f"Error during comprehensive cleanup: {e}")
        print(f"❌ Cleanup failed: {e}")


def cleanup_performance_test_folders(client, verbose: bool = True):
    """
    Clean up folders created during performance tests
    
    Args:
        client: GDriveUnifiedClient instance
        verbose: Whether to print cleanup progress
    """
    try:
        if verbose:
            print(f"   Cleaning performance test folders for {client.my_email}...")
        
        # Search for test performance folders
        results = client.service.files().list(
            q="name contains 'test_performance_folder_' and trashed=false",
            fields="files(id,name)"
        ).execute()
        
        test_folders = results.get('files', [])
        
        if len(test_folders) > 0:
            if verbose:
                print(f"   Found {len(test_folders)} performance test folders to delete")
            
            for folder in test_folders:
                try:
                    client.service.files().delete(fileId=folder['id']).execute()
                    if verbose:
                        print(f"     🗑️  Deleted: {folder['name']}")
                except Exception as e:
                    logger.warning(f"Could not delete folder {folder['name']}: {e}")
                    if verbose:
                        print(f"     ⚠️  Could not delete {folder['name']}: {e}")
                
                time.sleep(0.5)  # Rate limit protection
        else:
            if verbose:
                print(f"   No performance test folders found")
                
    except Exception as e:
        logger.error(f"Error cleaning performance test folders: {e}")
        if verbose:
            print(f"   ⚠️  Error cleaning performance folders: {e}")


def deep_cleanup():
    """
    Perform deep cleanup of all test-related folders
    This is more aggressive and should only be used when needed
    """
    print("🧹 Starting deep cleanup...")
    
    try:
        import syft_client as sc
        
        # Get test user emails
        user1_email = os.environ.get('TEST_USER1_EMAIL')
        user2_email = os.environ.get('TEST_USER2_EMAIL')
        
        if not user1_email or not user2_email:
            print("⚠️  Test user emails not found")
            return
        
        # Authenticate users
        user1 = sc.login(user1_email, verbose=False)
        user2 = sc.login(user2_email, verbose=False)
        
        # Deep cleanup for each user
        for user, email in [(user1, user1_email), (user2, user2_email)]:
            print(f"   Deep cleaning for {email}...")
            
            try:
                # Find all folders that might be test-related
                results = user.service.files().list(
                    q="(name contains 'syft_' or name contains 'test_' or name='SyftBoxTransportService') and trashed=false",
                    fields="files(id,name,mimeType)"
                ).execute()
                
                folders = results.get('files', [])
                
                if len(folders) > 0:
                    print(f"     Found {len(folders)} potentially test-related folders")
                    
                    for folder in folders:
                        try:
                            # Be careful - only delete obvious test folders
                            if (folder['name'].startswith('syft_') or 
                                folder['name'].startswith('test_') or
                                folder['name'] == 'SyftBoxTransportService'):
                                
                                user.service.files().delete(fileId=folder['id']).execute()
                                print(f"       🗑️  Deleted: {folder['name']}")
                                
                                time.sleep(0.5)  # Rate limiting
                        except Exception as e:
                            logger.warning(f"Could not delete {folder['name']}: {e}")
                            print(f"       ⚠️  Could not delete {folder['name']}: {e}")
                else:
                    print(f"     No test folders found")
                    
            except Exception as e:
                logger.error(f"Error during deep cleanup for {email}: {e}")
                print(f"     ❌ Deep cleanup error for {email}: {e}")
        
        # Recreate clean SyftBoxes
        print("   Recreating clean SyftBox folders...")
        user1.reset_syftbox()
        user2.reset_syftbox()
        
        print("✅ Deep cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during deep cleanup: {e}")
        print(f"❌ Deep cleanup failed: {e}")


def verify_cleanup(client, verbose: bool = True) -> Dict[str, Any]:
    """
    Verify that cleanup was successful
    
    Args:
        client: GDriveUnifiedClient instance
        verbose: Whether to print verification progress
        
    Returns:
        Dictionary with cleanup verification results
    """
    results = {
        'syftbox_exists': False,
        'friend_folders_count': 0,
        'test_folders_count': 0,
        'friends_list_length': 0,
        'friend_requests_length': 0
    }
    
    try:
        if verbose:
            print(f"   Verifying cleanup for {client.my_email}...")
        
        # Check if SyftBox exists
        results['syftbox_exists'] = client._folder_exists("SyftBoxTransportService")
        
        # Count friend-related folders
        friend_results = client.service.files().list(
            q="name contains 'syft_' and trashed=false",
            fields="files(name)"
        ).execute()
        results['friend_folders_count'] = len(friend_results.get('files', []))
        
        # Count test folders
        test_results = client.service.files().list(
            q="name contains 'test_' and trashed=false", 
            fields="files(name)"
        ).execute()
        results['test_folders_count'] = len(test_results.get('files', []))
        
        # Check friends and requests lists
        results['friends_list_length'] = len(client.friends)
        results['friend_requests_length'] = len(client.friend_requests)
        
        if verbose:
            print(f"     SyftBox exists: {results['syftbox_exists']}")
            print(f"     Friend folders: {results['friend_folders_count']}")
            print(f"     Test folders: {results['test_folders_count']}")
            print(f"     Friends list: {results['friends_list_length']}")
            print(f"     Friend requests: {results['friend_requests_length']}")
        
        # Determine if cleanup was successful
        cleanup_successful = (
            results['syftbox_exists'] and  # SyftBox should exist after reset
            results['friend_folders_count'] == 0 and  # No friend folders
            results['test_folders_count'] == 0 and  # No test folders
            results['friends_list_length'] == 0 and  # No friends
            results['friend_requests_length'] == 0  # No requests
        )
        
        results['cleanup_successful'] = cleanup_successful
        
        if verbose:
            status = "✅" if cleanup_successful else "⚠️"
            print(f"     {status} Cleanup verification: {'PASSED' if cleanup_successful else 'ISSUES FOUND'}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error during cleanup verification: {e}")
        if verbose:
            print(f"     ❌ Verification error: {e}")
        
        results['error'] = str(e)
        results['cleanup_successful'] = False
        return results


def wait_for_propagation(seconds: int = 3, verbose: bool = True):
    """
    Wait for Google Drive changes to propagate
    
    Args:
        seconds: Number of seconds to wait
        verbose: Whether to show countdown
    """
    if verbose:
        print(f"   ⏳ Waiting {seconds} seconds for Google Drive propagation...")
    
    if verbose and seconds > 1:
        for i in range(seconds, 0, -1):
            print(f"     {i}...", end="", flush=True)
            time.sleep(1)
        print(" Done!")
    else:
        time.sleep(seconds)


def cleanup_with_verification(user1_client, user2_client, verbose: bool = True) -> bool:
    """
    Perform cleanup with verification
    
    Args:
        user1_client: First user's client
        user2_client: Second user's client
        verbose: Whether to show progress
        
    Returns:
        True if cleanup was successful for both users
    """
    if verbose:
        print("\n🧹 Starting cleanup with verification...")
    
    try:
        # Perform cleanup
        cleanup_test_folders(user1_client, user2_client, verbose)
        
        # Wait for propagation
        wait_for_propagation(5, verbose)
        
        # Verify cleanup for both users
        user1_results = verify_cleanup(user1_client, verbose)
        user2_results = verify_cleanup(user2_client, verbose)
        
        success = user1_results['cleanup_successful'] and user2_results['cleanup_successful']
        
        if verbose:
            status = "✅" if success else "⚠️"
            print(f"\n{status} Cleanup with verification: {'COMPLETED' if success else 'PARTIAL'}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error during cleanup with verification: {e}")
        if verbose:
            print(f"\n❌ Cleanup with verification failed: {e}")
        return False


# Helper functions for specific cleanup scenarios

def cleanup_failed_test_artifacts(client, test_name: str, verbose: bool = True):
    """
    Clean up artifacts from a specific failed test
    
    Args:
        client: GDriveUnifiedClient instance
        test_name: Name of the test that failed
        verbose: Whether to show progress
    """
    if verbose:
        print(f"   Cleaning up artifacts from failed test: {test_name}")
    
    try:
        # Search for folders related to the specific test
        search_terms = [
            f"name contains '{test_name}'",
            "name contains 'test_performance_'",
            "name contains 'syft_' and name contains 'test'"
        ]
        
        for search_term in search_terms:
            results = client.service.files().list(
                q=f"{search_term} and trashed=false",
                fields="files(id,name)"
            ).execute()
            
            folders = results.get('files', [])
            
            for folder in folders:
                try:
                    client.service.files().delete(fileId=folder['id']).execute()
                    if verbose:
                        print(f"     🗑️  Deleted test artifact: {folder['name']}")
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Could not delete test artifact {folder['name']}: {e}")
        
    except Exception as e:
        logger.error(f"Error cleaning test artifacts: {e}")
        if verbose:
            print(f"     ⚠️  Error cleaning test artifacts: {e}")


if __name__ == "__main__":
    # Allow running cleanup directly
    print("🧹 Running standalone cleanup...")
    cleanup_all_test_data()