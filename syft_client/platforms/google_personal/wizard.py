"""OAuth2 setup wizard for Google Personal accounts"""

import webbrowser
import time
from pathlib import Path
from typing import Optional


def check_or_create_credentials() -> Optional[Path]:
    """
    Interactive wizard to help users create OAuth2 credentials.
    
    Returns:
        Path to credentials file if created/found, None if cancelled
    """
    print("\n🔐 OAuth2 Credentials Setup")
    print("=" * 50)
    print("\nTo use Gmail and other Google services, you need OAuth2 credentials.")
    print("This is a one-time setup that creates a 'client secret' file.\n")
    
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
    print("2. Create a new project (or select an existing one)")
    print("3. Enable the Gmail API (and optionally Drive, Sheets, Forms APIs)")
    print("4. Create OAuth2 credentials (Desktop application type)")
    print("5. Download the credentials JSON file")
    
    open_browser = input("\nOpen Google Cloud Console in your browser? (y/n): ").lower()
    
    if open_browser == 'y':
        console_url = "https://console.cloud.google.com/apis/credentials"
        print(f"\n🌐 Opening: {console_url}")
        webbrowser.open(console_url)
        time.sleep(2)
        
        print("\n📝 Detailed instructions:")
        print("\n1️⃣  Create a new project:")
        print("   - Click 'Select a project' → 'New Project'")
        print("   - Name it (e.g., 'Syft Client')")
        print("   - Click 'Create'\n")
        
        print("2️⃣  Enable APIs:")
        print("   - Go to 'APIs & Services' → 'Library'")
        print("   - Search and enable: Gmail API")
        print("   - Optionally enable: Drive, Sheets, Forms APIs\n")
        
        print("3️⃣  Create credentials:")
        print("   - Go to 'APIs & Services' → 'Credentials'")
        print("   - Click '+ CREATE CREDENTIALS' → 'OAuth client ID'")
        print("   - If prompted, configure consent screen:")
        print("     • User Type: External")
        print("     • Add your email as a test user")
        print("   - Application type: 'Desktop app'")
        print("   - Name: 'Syft Client' (or any name)")
        print("   - Click 'Create'\n")
        
        print("4️⃣  Download credentials:")
        print("   - Click the download button (⬇️) next to your credential")
        print("   - Save as 'credentials.json'\n")
    
    print("\n⏳ Waiting for credentials file...")
    print("When ready, enter the path to your downloaded credentials.json file")
    print("(or press Enter to check default locations again)")
    
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
🔐 OAuth2 Setup Required
━━━━━━━━━━━━━━━━━━━━━━━

To use Google services, you need to:

1. Create OAuth2 credentials in Google Cloud Console
2. Download the credentials.json file
3. Place it in your current directory

Run with wizard=True for step-by-step guidance:
  sc.login('your@gmail.com', wizard=True)

Or see: https://developers.google.com/gmail/api/quickstart/python
"""