"""OAuth2 setup wizard for Google Workspace (organizational) accounts"""

import webbrowser
import time
from pathlib import Path
from typing import Optional


def check_or_create_credentials() -> Optional[Path]:
    """
    Interactive wizard to help users create OAuth2 credentials for Google Workspace.
    
    Returns:
        Path to credentials file if created/found, None if cancelled
    """
    print("\n🔐 OAuth2 Credentials Setup (Google Workspace)")
    print("=" * 50)
    print("\nTo use Gmail and other Google Workspace services, you need OAuth2 credentials.")
    print("This is a one-time setup that creates a 'client secret' file.\n")
    
    print("⚠️  Note: For Google Workspace accounts, you may need admin approval")
    print("    for the OAuth2 app to access organizational data.\n")
    
    # Check if credentials already exist
    default_paths = [
        Path("credentials.json"),
        Path("client_secret.json"),
        Path.home() / ".syft" / "credentials.json",
        Path.home() / "credentials.json",
    ]
    
    for path in default_paths:
        if path.exists():
            print(f"✓ Found existing credentials at: {path}")
            use_existing = input("\nUse this file? (y/n): ").lower()
            if use_existing == 'y':
                return path
    
    print("\n📋 Steps to create OAuth2 credentials:\n")
    print("1. Go to the Google Cloud Console")
    print("2. Create a new project (or select existing)")
    print("3. Enable required APIs")
    print("4. Create OAuth2 credentials")
    print("5. Configure consent screen for your organization")
    print("6. Download the credentials JSON file")
    
    open_browser = input("\nOpen Google Cloud Console in your browser? (y/n): ").lower()
    
    if open_browser == 'y':
        console_url = "https://console.cloud.google.com/apis/credentials"
        print(f"\n🌐 Opening: {console_url}")
        webbrowser.open(console_url)
        time.sleep(2)
        
        print("\n📝 Detailed instructions for Google Workspace:")
        print("\n1️⃣  Create a new project:")
        print("   - Click 'Select a project' → 'New Project'")
        print("   - Name it (e.g., 'Syft Client - Workspace')")
        print("   - Select your organization (if prompted)")
        print("   - Click 'Create'\n")
        
        print("2️⃣  Enable APIs:")
        print("   - Go to 'APIs & Services' → 'Library'")
        print("   - Search and enable: Gmail API")
        print("   - Also enable: Drive, Sheets, Forms APIs\n")
        
        print("3️⃣  Configure OAuth consent screen:")
        print("   - Go to 'APIs & Services' → 'OAuth consent screen'")
        print("   - User Type: 'Internal' (for org users only)")
        print("   - Fill in app information:")
        print("     • App name: 'Syft Client'")
        print("     • Support email: Your org email")
        print("     • Add your organization's domain")
        print("   - Add scopes: Gmail, Drive, Sheets, Forms")
        print("   - Add test users (if in testing mode)\n")
        
        print("4️⃣  Create credentials:")
        print("   - Go to 'APIs & Services' → 'Credentials'")
        print("   - Click '+ CREATE CREDENTIALS' → 'OAuth client ID'")
        print("   - Application type: 'Desktop app'")
        print("   - Name: 'Syft Client Desktop'")
        print("   - Click 'Create'\n")
        
        print("5️⃣  Download credentials:")
        print("   - Click the download button (⬇️)")
        print("   - Save as 'credentials.json'\n")
        
        print("⚠️  Admin Approval:")
        print("   If your app requires admin consent, you may need to:")
        print("   - Submit for OAuth app verification")
        print("   - Or have an admin pre-approve the app\n")
    
    print("\n⏳ Waiting for credentials file...")
    print("When ready, enter the path to your downloaded credentials.json file")
    
    while True:
        file_path = input("\n📁 Path to credentials.json (or 'q' to quit): ").strip()
        
        if file_path.lower() == 'q':
            print("Setup cancelled.")
            return None
            
        if not file_path:
            # Check default locations again
            for path in default_paths:
                if path.exists():
                    print(f"✓ Found credentials at: {path}")
                    return path
            print("No credentials file found in default locations.")
            continue
            
        path = Path(file_path).expanduser()
        if path.exists():
            # Validate it's a JSON file
            try:
                import json
                with open(path) as f:
                    data = json.load(f)
                    if 'installed' in data or 'web' in data:
                        print(f"✓ Valid credentials file: {path}")
                        
                        # Offer to copy to default location
                        if path.name != "credentials.json":
                            copy = input("\nCopy to ./credentials.json for easier access? (y/n): ").lower()
                            if copy == 'y':
                                import shutil
                                target = Path("credentials.json")
                                shutil.copy(path, target)
                                print(f"✓ Copied to: {target}")
                                return target
                        
                        return path
                    else:
                        print("❌ This doesn't appear to be a valid OAuth2 credentials file.")
            except Exception as e:
                print(f"❌ Error reading file: {e}")
        else:
            print(f"❌ File not found: {path}")
            
        retry = input("\nTry another file? (y/n): ").lower()
        if retry != 'y':
            print("Setup cancelled.")
            return None


def create_oauth_instructions():
    """Return formatted instructions for OAuth2 setup"""
    return """
🔐 OAuth2 Setup Required (Google Workspace)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

To use Google Workspace services, you need to:

1. Create OAuth2 credentials in Google Cloud Console
2. Configure consent screen for your organization
3. Download the credentials.json file
4. May require admin approval

Run with wizard=True for step-by-step guidance:
  sc.login('your@company.com', wizard=True)

Note: Internal apps (org-only) are easier to approve.
"""