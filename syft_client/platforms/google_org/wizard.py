"""OAuth2 setup wizard for Google Workspace (organizational) accounts"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from ...environment import detect_environment, Environment


def create_oauth2_wizard(email: str, verbose: bool = True, is_workspace: bool = True) -> Optional[Path]:
    """
    Interactive wizard to create OAuth2 credentials for Google Workspace
    
    Args:
        email: The email address for the account
        verbose: Whether to print detailed instructions
        is_workspace: Whether this is for Google Workspace (vs personal)
    
    Returns:
        Path to credentials.json if created, None otherwise
    """
    print("\n🔧 Google Workspace OAuth2 Setup Wizard")
    print("=" * 60)
    print(f"Setting up OAuth2 for: {email}")
    print("\nThis wizard will help you create OAuth2 credentials for Google Workspace.")
    print("You'll need:")
    print("  • A Google Workspace account with admin privileges")
    print("  • Or permission from your Workspace admin")
    print("  • A Google Cloud Platform project")
    
    print("\n⚠️  Google Workspace accounts may require:")
    print("  • Admin consent for certain scopes")
    print("  • Domain-wide delegation for service accounts")
    print("  • Workspace-specific API enablement")
    
    # Check environment
    env = detect_environment()
    
    # Sanitize email for file paths
    sanitized_email = email.replace('@', '_at_').replace('.', '_')
    
    # Determine credentials path
    credentials_dir = Path.home() / ".syft" / sanitized_email
    credentials_dir.mkdir(parents=True, exist_ok=True)
    credentials_file = credentials_dir / "credentials.json"
    
    if credentials_file.exists():
        print(f"\n✓ Credentials already exist at: {credentials_file}")
        use_existing = input("\nUse existing credentials? (Y/n): ").strip().lower()
        if use_existing != 'n':
            return credentials_file
    
    print("\n📝 Let's create your OAuth2 app step by step:")
    print("=" * 60)
    
    # Extract domain for workspace
    domain = email.split('@')[1]
    
    # Step 1: Google Cloud Console
    print("\n🌐 Step 1: Go to Google Cloud Console")
    print(f"Open: https://console.cloud.google.com?authuser={email}")
    print(f"\nIMPORTANT: Sign in with your Workspace account: {email}")
    
    # Step 2: Create/Select Project
    print("\n📂 Step 2: Create or Select a Project")
    print("If you don't have a project:")
    print("  1. Click 'Select a project' dropdown (top bar)")
    print("  2. Click 'New Project'")
    print("  3. Enter a name (e.g., 'Syft Workspace Integration')")
    print("  4. Note your Project ID (e.g., 'syft-workspace-123456')")
    
    input("\nPress Enter when you have a project ready...")
    
    # Step to select the project FIRST
    print("\n🎯 IMPORTANT: Select your project")
    print("-" * 40)
    print("1. Look at the top bar of Google Cloud Console")
    print("2. Click the project dropdown (shows current project name)")
    print("3. Select your project from the list")
    print("4. Make sure it's selected before continuing")
    
    input("\nPress Enter AFTER you've selected your project...")
    
    # Now get project ID for URL construction
    print("\n📋 Now let's get your Project ID")
    print("Your Project ID is shown in the project selector dropdown")
    print("It's usually different from your project name (e.g., 'syft-workspace-123456')")
    
    project_id = input("\nEnter your Project ID (or press Enter to skip): ").strip()
    
    # Construct URLs with project
    if project_id:
        authuser = f"?authuser={email}&project={project_id}"
    else:
        authuser = f"?authuser={email}"
    
    # Step 3: Enable APIs
    print("\n🔌 Step 3: Enable Required APIs")
    print("You need to enable these Google Workspace APIs:")
    
    apis = [
        ("Gmail API", f"https://console.cloud.google.com/marketplace/product/google/gmail.googleapis.com{authuser}"),
        ("Google Drive API", f"https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com{authuser}"),
        ("Google Sheets API", f"https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com{authuser}"),
        ("Google Forms API", f"https://console.cloud.google.com/marketplace/product/google/forms.googleapis.com{authuser}")
    ]
    
    for api_name, url in apis:
        print(f"\n  • {api_name}")
        print(f"    Open: {url}")
        print("    Click 'ENABLE' if not already enabled")
    
    input("\nPress Enter when all APIs are enabled...")
    
    # Step 4: OAuth Consent Screen
    print("\n🔐 Step 4: Configure OAuth Consent Screen")
    oauth_url = f"https://console.cloud.google.com/auth/overview/create{authuser}"
    print(f"1. Open: {oauth_url}")
    print("2. Click '+ CREATE' or 'CONFIGURE CONSENT SCREEN'")
    print("3. Select 'Internal' user type (for your organization only)")
    print("   - This limits access to users in your Workspace domain")
    print("   - Click 'CREATE'")
    print("4. OAuth consent screen - App information:")
    print("   - App name: Syft Workspace Client")
    print(f"   - User support email: {email or 'your email'}")
    print("   - Click 'SAVE AND CONTINUE'")
    print("5. Scopes: Click 'SAVE AND CONTINUE' (no changes needed)")
    print("6. Summary: Click 'BACK TO DASHBOARD'")
    
    input("\nPress Enter when OAuth consent screen is configured...")
    
    # Note about admin consent (informational only)
    print("\n💡 Note: If your organization blocks OAuth apps, you may need admin approval later.")
    print("   For now, the app will work in testing mode with your account.")
    
    # Step 5: Create Credentials and Save File
    print("\n🔑 Step 5: Create OAuth2 Credentials")
    creds_url = f"https://console.cloud.google.com/apis/credentials{authuser}"
    print(f"Open: {creds_url}")
    print("\n1. Click '+ CREATE CREDENTIALS' → 'OAuth client ID'")
    print("2. Application type: 'Desktop app'")
    print("3. Name: 'Syft Workspace Desktop Client'")
    print("4. Click 'CREATE'")
    print("5. Click 'DOWNLOAD JSON' in the popup")
    
    input("\nPress Enter after downloading the credentials JSON file...")
    
    # Save credentials file
    print("\n📁 Now let's save your credentials")
    print("-" * 40)
    
    # Environment-specific instructions
    if env == Environment.JUPYTER or env == Environment.COLAB:
        print("\n6. Download the JSON file to your computer")
        
        if env == Environment.JUPYTER:
            print("\n📓 For Jupyter:")
            print("   a. Upload the downloaded JSON file to Jupyter")
            print("   b. Then run these commands:")
            print(f"      !mkdir -p ~/.syft/{sanitized_email}")
            print(f"      !mv client_secret*.json ~/.syft/{sanitized_email}/credentials.json")
        else:  # Colab
            print("\n📊 For Google Colab:")
            print("   a. Upload the file using the file browser (left sidebar)")
            print("   b. Then run these commands:")
            print(f"      !mkdir -p ~/.syft/{sanitized_email}")
            print(f"      !mv /content/client_secret*.json ~/.syft/{sanitized_email}/credentials.json")
    else:
        # For terminal/REPL environments - ask for file path
        print("Enter the path to the downloaded credentials JSON file")
        print("(typically in your Downloads folder, named 'client_secret_*.json')")
        
        while True:
            try:
                # Get the path from user
                downloaded_path = input("\nPath to credentials file: ").strip()
                
                # Handle ~ expansion and resolve path
                downloaded_path = Path(downloaded_path).expanduser().resolve()
                
                # Check if file exists
                if not downloaded_path.exists():
                    print(f"❌ File not found: {downloaded_path}")
                    print("Please check the path and try again.")
                    continue
                
                # Check if it's a JSON file
                if not downloaded_path.suffix.lower() == '.json':
                    print("❌ This doesn't appear to be a JSON file.")
                    print("Please provide the path to the credentials JSON file.")
                    continue
                
                # Copy the file to the expected location
                import shutil
                shutil.copy2(downloaded_path, credentials_file)
                print(f"✅ Credentials saved to: {credentials_file}")
                break
                
            except (KeyboardInterrupt, EOFError):
                print("\n\nSetup cancelled.")
                return None
            except Exception as e:
                print(f"❌ Error: {e}")
                print("Please try again.")
    
    # Wait for user to confirm file is in place (for Jupyter/Colab)
    if env == Environment.JUPYTER or env == Environment.COLAB:
        if verbose:
            print("\n⏳ Waiting for credentials file...")
            print(f"Expected location: {credentials_file}")
            
            # Keep checking until file exists
            while not credentials_file.exists():
                try:
                    input("\nPress Enter after you've saved the credentials.json file to the correct location...")
                    if credentials_file.exists():
                        print("✅ Credentials file found!")
                        break
                    else:
                        print(f"❌ File not found at: {credentials_file}")
                        print("Please make sure to save the file to the exact location shown above.")
                except (KeyboardInterrupt, EOFError):
                    print("\n\nSetup cancelled.")
                    return None
    
    # Verify credentials exist
    if credentials_file.exists():
        print(f"\n✅ Success! Credentials saved to: {credentials_file}")
        
        # Set secure permissions
        try:
            credentials_file.chmod(0o600)
            print("✓ Set secure file permissions")
        except:
            pass  # Windows doesn't support chmod
            
        return credentials_file
    else:
        print(f"\n❌ credentials.json not found at: {credentials_file}")
        print("\nPlease ensure you:")
        print("  1. Downloaded the JSON file from Google Cloud Console")
        print(f"  2. Saved it as: {credentials_file}")
        
        retry = input("\nRetry? (Y/n): ").strip().lower()
        if retry != 'n':
            return create_oauth2_wizard(email, verbose, is_workspace)
        
        return None


def check_or_create_credentials(email: str, verbose: bool = True, is_workspace: bool = True) -> Optional[Path]:
    """
    Check for existing credentials or run wizard to create them
    
    Args:
        email: The email address
        verbose: Whether to print messages
        is_workspace: Whether this is for Google Workspace
    
    Returns:
        Path to credentials.json if found/created, None otherwise
    """
    # Sanitize email for file paths
    sanitized_email = email.replace('@', '_at_').replace('.', '_')
    
    # Check for existing credentials
    possible_paths = [
        Path.home() / ".syft" / sanitized_email / "credentials.json",
        Path.home() / ".syft" / "credentials.json",  # Legacy location
        Path("credentials.json"),  # Current directory
    ]
    
    for path in possible_paths:
        if path.exists():
            if verbose:
                print(f"✓ Found existing credentials at: {path}")
            # Move to correct location if needed
            correct_path = Path.home() / ".syft" / sanitized_email / "credentials.json"
            if path != correct_path:
                correct_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(path, correct_path)
                if verbose:
                    print(f"✓ Moved credentials to: {correct_path}")
                return correct_path
            return path
    
    # No credentials found, run wizard
    if verbose:
        print("No OAuth2 credentials found. Starting setup wizard...")
    
    return create_oauth2_wizard(email, verbose, is_workspace)
