#!/usr/bin/env python3
"""
Debug script for Colab authentication issues
Run this in Colab to see detailed error messages
"""

import traceback
from google.colab import auth as colab_auth
from googleapiclient.discovery import build
from syft_client.environment import detect_environment, Environment

def test_colab_auth():
    """Test basic Colab authentication"""
    print("=== Testing Colab Authentication ===")
    try:
        colab_auth.authenticate_user()
        print("✅ Colab authentication successful")
        return True
    except Exception as e:
        print(f"❌ Colab authentication failed: {e}")
        traceback.print_exc()
        return False

def test_drive_api():
    """Test Google Drive API"""
    print("\n=== Testing Google Drive API ===")
    try:
        service = build('drive', 'v3')
        print("✅ Drive service created")
        
        # Try to list files
        results = service.files().list(pageSize=1).execute()
        print(f"✅ Drive API working - found {len(results.get('files', []))} files")
        return True
    except Exception as e:
        print(f"❌ Drive API failed: {e}")
        traceback.print_exc()
        return False

def test_sheets_api():
    """Test Google Sheets API"""
    print("\n=== Testing Google Sheets API ===")
    try:
        service = build('sheets', 'v4')
        print("✅ Sheets service created")
        
        # Try to create a test spreadsheet
        spreadsheet = {
            'properties': {
                'title': 'Test Sheet'
            }
        }
        result = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        print(f"✅ Sheets API working - created sheet {result.get('spreadsheetId')}")
        
        # Clean up - delete the test sheet
        drive_service = build('drive', 'v3')
        drive_service.files().delete(fileId=result.get('spreadsheetId')).execute()
        print("✅ Cleaned up test sheet")
        
        return True
    except Exception as e:
        print(f"❌ Sheets API failed: {e}")
        traceback.print_exc()
        return False

def test_forms_api():
    """Test Google Forms API"""
    print("\n=== Testing Google Forms API ===")
    try:
        service = build('forms', 'v1')
        print("✅ Forms service created")
        
        # Note: Forms API might require additional setup
        print("⚠️  Forms API requires additional setup in Google Cloud Console")
        return True
    except Exception as e:
        print(f"❌ Forms API failed: {e}")
        traceback.print_exc()
        return False

def test_transport_setup():
    """Test transport setup logic"""
    print("\n=== Testing Transport Setup ===")
    
    # Test environment detection
    env = detect_environment()
    print(f"Environment: {env}")
    
    # Test the actual transport setup
    from syft_client.platforms.google_org.gdrive_files import GDriveFilesTransport
    from syft_client.platforms.google_org.gsheets import GSheetsTransport
    from syft_client.platforms.google_org.gforms import GFormsTransport
    
    # Test Drive
    print("\n--- Testing Drive Transport ---")
    try:
        transport = GDriveFilesTransport("test@example.com")
        success = transport.setup(None)  # None credentials for Colab
        print(f"Drive setup: {'✅ Success' if success else '❌ Failed'}")
        if success:
            print(f"Drive service ready: {transport.is_setup()}")
    except Exception as e:
        print(f"❌ Drive transport error: {e}")
        traceback.print_exc()
    
    # Test Sheets
    print("\n--- Testing Sheets Transport ---")
    try:
        transport = GSheetsTransport("test@example.com")
        success = transport.setup(None)  # None credentials for Colab
        print(f"Sheets setup: {'✅ Success' if success else '❌ Failed'}")
        if success:
            print(f"Sheets service ready: {transport.is_setup()}")
    except Exception as e:
        print(f"❌ Sheets transport error: {e}")
        traceback.print_exc()
    
    # Test Forms
    print("\n--- Testing Forms Transport ---")
    try:
        transport = GFormsTransport("test@example.com")
        success = transport.setup(None)  # None credentials for Colab
        print(f"Forms setup: {'✅ Success' if success else '❌ Failed'}")
        if success:
            print(f"Forms service ready: {transport.is_setup()}")
    except Exception as e:
        print(f"❌ Forms transport error: {e}")
        traceback.print_exc()

def main():
    """Run all tests"""
    print("🔍 Debugging Colab Authentication Issues")
    print("=" * 50)
    
    # Test basic auth
    if not test_colab_auth():
        print("\n⚠️  Basic Colab authentication failed. Please run:")
        print("from google.colab import auth")
        print("auth.authenticate_user()")
        return
    
    # Test APIs
    test_drive_api()
    test_sheets_api()
    test_forms_api()
    
    # Test transport setup
    test_transport_setup()
    
    print("\n" + "=" * 50)
    print("Debug session complete!")

if __name__ == "__main__":
    main()