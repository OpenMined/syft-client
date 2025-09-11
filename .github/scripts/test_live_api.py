#!/usr/bin/env python3
"""
Live API verification tests for CI.
Updated to work with new syft_client API.
"""
import syft_client as sc
import os
import sys

def test_live_api():
    """Test that the API works with live Google Drive"""
    user1_email = os.environ.get('TEST_USER1_EMAIL')
    user2_email = os.environ.get('TEST_USER2_EMAIL')
    
    print("🔍 Testing live API functionality...")
    
    # Test 1: Can authenticate
    print("  1️⃣ Testing authentication...")
    try:
        provider = 'google_personal' if '@gmail.com' in user1_email else 'google_org'
        client = sc.login(user1_email, provider=provider, verbose=False)
        
        # Check if we have a Google platform
        google_platform = client.platforms.get('google_personal') or client.platforms.get('google_org')
        assert google_platform is not None, "No Google platform found"
        
        print(f"     ✅ User1 authenticated: {client.email}")
    except Exception as e:
        print(f"     ❌ Authentication failed: {e}")
        return False
    
    # Test 2: Can access Google Drive API
    print("  2️⃣ Testing Google Drive API access...")
    try:
        # Get service from credentials
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import json
        
        sanitized_email = user1_email.replace('@', '_at_').replace('.', '_')
        token_path = os.path.expanduser(f'~/.syft/gdrive/{sanitized_email}/token.json')
        
        if os.path.exists(token_path):
            with open(token_path, 'r') as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data)
            service = build('drive', 'v3', credentials=creds)
            
            result = service.files().list(pageSize=1, fields="files(id,name)").execute()
            print(f"     ✅ Google Drive API accessible")
        else:
            print(f"     ❌ Token file not found")
            return False
    except Exception as e:
        print(f"     ❌ API access failed: {e}")
        return False
    
    # Test 3: Can create and delete folders
    print("  3️⃣ Testing folder operations...")
    try:
        folder_metadata = {
            'name': 'test_post_merge_folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        test_folder_id = folder.get('id')
        
        assert test_folder_id, "Folder creation failed"
        print(f"     ✅ Created test folder: {test_folder_id}")
        
        # Clean up
        service.files().delete(fileId=test_folder_id).execute()
        print(f"     ✅ Deleted test folder")
    except Exception as e:
        print(f"     ❌ Folder operations failed: {e}")
        return False
    
    # Test 4: SyftBox exists or can be created
    print("  4️⃣ Testing SyftBox functionality...")
    try:
        # Check if SyftBox folder exists
        results = service.files().list(
            q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id,name)"
        ).execute()
        
        if not results.get('files'):
            # Create SyftBox folder
            folder_metadata = {
                'name': 'SyftBoxTransportService',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            print(f"     ✅ Created SyftBox folder")
        else:
            print(f"     ✅ SyftBox folder exists")
        
        # Verify it exists now
        results = service.files().list(
            q="name='SyftBoxTransportService' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id,name)"
        ).execute()
        assert results.get('files'), "SyftBox not found after creation"
        print(f"     ✅ SyftBox verified")
    except Exception as e:
        print(f"     ❌ SyftBox test failed: {e}")
        return False
    
    print("\n✅ All live API tests passed!")
    return True

if __name__ == "__main__":
    success = test_live_api()
    sys.exit(0 if success else 1)