"""OAuth2 setup wizard for Google Workspace (organizational) accounts"""

import json
import os
import glob
import shutil
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
    
    # Get project ID for URL construction
    project_id = input("\nEnter your Project ID (or press Enter to skip): ").strip()
    
    if project_id:
        print(f"\n⚠️  IMPORTANT: Make sure you've switched to your project!")
        print(f"Look at the top bar of Google Cloud Console")
        print(f"It should show: {project_id}")
        print(f"If not, click the project dropdown and select your project")
        input("\nPress Enter when you've switched to your project...")
    
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
    print(f"Open: {oauth_url}")
    
    print("\n⚠️  WORKSPACE-SPECIFIC SETTINGS:")
    print("  1. User Type: Choose 'Internal' (for your organization only)")
    print("     - This limits access to users in your Workspace domain")
    print("     - Requires fewer review steps than 'External'")
    print("  2. App Name: 'Syft Workspace Client'")
    print("  3. User Support Email: Your email")
    print("  4. Authorized domains: Your workspace domain will be pre-filled")
    print("  5. Developer Contact: Your email")
    
    print("\nFor Scopes:")
    print("  • You can skip adding scopes manually here")
    print("  • The app will request them during authentication")
    
    input("\nPress Enter when OAuth consent screen is configured...")
    
    # Note about admin consent (informational only)
    print("\n💡 Note: If your organization blocks OAuth apps, you may need admin approval later.")
    print("   For now, the app will work in testing mode with your account.")
    
    # Step 5: Create Credentials
    print("\n🔑 Step 5: Create OAuth2 Credentials")
    creds_url = f"https://console.cloud.google.com/apis/credentials{authuser}"
    print(f"Open: {creds_url}")
    print("\n1. Click '+ CREATE CREDENTIALS' → 'OAuth client ID'")
    print("2. Application type: 'Desktop app'")
    print("3. Name: 'Syft Workspace Desktop Client'")
    print("4. Click 'CREATE'")
    print("5. Click 'DOWNLOAD JSON' to save the credentials file")
    print("\nThe file will be named something like:")
    print("  client_secret_XXXXXXX.apps.googleusercontent.com.json")
    print("\nRemember where you save it - you'll need the path in the next step.")
    
    # Ask user for the path to their downloaded credentials file
    print("\n" + "="*50)
    print("📁 Step 6: Provide Path to Downloaded Credentials")
    print("="*50)
    print("\nPlease provide the full path to the JSON file you just downloaded.")
    print("Examples:")
    print("  - ~/Downloads/client_secret_XXXXXXX.apps.googleusercontent.com.json")
    print("  - /Users/you/Downloads/client_secret_*.json")
    print("  - C:\\Users\\you\\Downloads\\client_secret_*.json (Windows)")
    
    while True:
        try:
            downloaded_path = input("\nPath to your downloaded credentials file: ").strip()
            
            if not downloaded_path:
                print("❌ Please provide a path")
                continue
                
            # Expand user path and glob patterns
            expanded_path = os.path.expanduser(downloaded_path)
            matching_files = glob.glob(expanded_path)
            
            if not matching_files:
                print(f"❌ No file found at: {downloaded_path}")
                print("Please check the path and try again.")
                continue
            
            if len(matching_files) > 1:
                print(f"⚠️  Multiple files found. Using: {matching_files[0]}")
            
            source_file = Path(matching_files[0])
            if not source_file.exists():
                print(f"❌ File does not exist: {source_file}")
                continue
                
            # Create target directory and copy file
            credentials_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, credentials_file)
            print(f"✅ Credentials file copied to: {credentials_file}")
            break
            
        except (KeyboardInterrupt, EOFError):
            print("\n\nSetup cancelled.")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Please try again.")
    
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