"""OAuth2 credentials.json creation wizard for Google Personal platform"""

from typing import Optional
import webbrowser
from pathlib import Path
from ...environment import detect_environment, Environment


def create_oauth2_wizard(email: Optional[str] = None, verbose: bool = True) -> None:
    """
    Interactive wizard to guide users through creating OAuth2 credentials
    
    Args:
        email: User's email for account-specific URLs
        verbose: Whether to show detailed instructions
    """
    print("\n🔐 OAuth2 Credentials Setup Wizard")
    print("=" * 50)
    print("\nThis wizard will guide you through creating OAuth2 credentials for Google APIs.")
    
    # Check if in Colab
    try:
        import google.colab
        print("\n🎉 Good news! You're using Google Colab")
        print("Google Colab provides built-in authentication. You don't need credentials.json!")
        print(f"Simply run: login('{email or 'your@gmail.com'}')")
        return
    except ImportError:
        pass
    
    # Email-specific URL parameter
    authuser = f"?authuser={email}" if email else "?authuser=0"
    
    print("\n📋 Prerequisites:")
    print("  • A Google account")
    print("  • Access to Google Cloud Console")
    print("  • 5-10 minutes to complete setup")
    
    if verbose:
        print("\n🚀 Ready to start? Press Enter to continue...")
        input()
    
    # Step 1: Create Project
    print("\n📝 Step 1: Create a Google Cloud Project")
    print("-" * 40)
    project_url = f"https://console.cloud.google.com/projectcreate{authuser}"
    print(f"1. Open: {project_url}")
    print("2. Enter a project name (e.g., 'Syft Client')")
    print("3. Click 'CREATE'")
    print("4. Wait for project creation (takes ~30 seconds)")
    
    if _ask_to_open_url(project_url):
        webbrowser.open(project_url)
    
    if verbose:
        input("\nPress Enter when your project is created...")
    
    # Get project ID and ensure user switches to it
    project_id = input("\nEnter your Project ID (you can find it in the project selector): ").strip()
    
    if project_id:
        print(f"\n⚠️  IMPORTANT: Make sure you've switched to your project!")
        print(f"Look at the top bar of Google Cloud Console")
        print(f"It should show: {project_id}")
        print(f"If not, click the project dropdown and select your project")
        input("\nPress Enter when you've switched to your project...")
        
        # Update authuser to include project
        authuser = f"?authuser={email}&project={project_id}"
    
    # Step 2: Enable APIs
    print("\n🔌 Step 2: Enable Required APIs")
    print("-" * 40)
    apis = ["gmail", "drive", "sheets.googleapis.com", "forms.googleapis.com"]
    
    for api in apis:
        api_name = api.replace(".googleapis.com", "").title()
        if api == "gmail":
            # Use marketplace URL for Gmail API
            api_url = f"https://console.cloud.google.com/marketplace/product/google/gmail.googleapis.com{authuser}"
        elif api == "drive":
            api_url = f"https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com{authuser}"
        elif api == "sheets.googleapis.com":
            api_url = f"https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com{authuser}"
        elif api == "forms.googleapis.com":
            api_url = f"https://console.cloud.google.com/marketplace/product/google/forms.googleapis.com{authuser}"
        else:
            # Fallback to library URL
            api_url = f"https://console.cloud.google.com/apis/library/{api}{authuser}"
        
        print(f"\n  {api_name} API:")
        print(f"  1. Open: {api_url}")
        print(f"  2. Click 'ENABLE'")
        
        if _ask_to_open_url(api_url, f"Open {api_name} API page?"):
            webbrowser.open(api_url)
            if verbose:
                input(f"  Press Enter when {api_name} API is enabled...")
    
    # Step 3: Create OAuth Consent Screen
    print("\n🛡️ Step 3: Configure OAuth Consent Screen")
    print("-" * 40)
    consent_url = f"https://console.cloud.google.com/auth/overview/create{authuser}"
    print(f"1. Open: {consent_url}")
    print("2. Select 'External' user type")
    print("3. Click 'CREATE'")
    print("4. Fill in:")
    print("   - App name: Syft Client")
    print(f"   - User support email: {email or 'your email'}")
    print(f"   - Developer contact: {email or 'your email'}")
    print("5. Click 'SAVE AND CONTINUE' through all sections")
    print("6. Click 'BACK TO DASHBOARD' when done")
    
    if _ask_to_open_url(consent_url):
        webbrowser.open(consent_url)
    
    if verbose:
        input("\nPress Enter when OAuth consent screen is configured...")
    
    # Step 4: Create Credentials
    print("\n🔑 Step 4: Create OAuth2 Credentials")
    print("-" * 40)
    creds_url = f"https://console.cloud.google.com/apis/credentials{authuser}"
    print(f"1. Open: {creds_url}")
    print("2. Click '+ CREATE CREDENTIALS' → 'OAuth client ID'")
    print("3. Select 'Desktop app' as application type")
    print("4. Name: 'Syft Client Desktop'")
    print("5. Click 'CREATE'")
    print("6. Click 'DOWNLOAD JSON' in the popup")
    
    if _ask_to_open_url(creds_url):
        webbrowser.open(creds_url)
    
    # Step 5: Add Test Users
    print("\n👤 Step 5: Add Test Users (Required for Testing Mode)")
    print("-" * 40)
    test_users_url = f"https://console.cloud.google.com/auth/audience{authuser}"
    print(f"1. Open: {test_users_url}")
    print("2. Scroll down to 'Test users' section")
    print("3. Click '+ ADD USERS'")
    print(f"4. Enter your email: {email or 'your@gmail.com'}")
    print("5. Click 'ADD'")
    print("\n⚠️  Important: Only test users can use your app while in testing mode")
    
    if _ask_to_open_url(test_users_url):
        webbrowser.open(test_users_url)
    
    if verbose:
        input("\nPress Enter when you've added yourself as a test user...")
    
    # Step 6: Save credentials file
    print("\n📁 Step 6: Download Credentials")
    print("-" * 40)
    print("Click 'DOWNLOAD JSON' to save the credentials file to your computer.")
    print("\nThe file will be named something like:")
    print("  client_secret_XXXXXXX.apps.googleusercontent.com.json")
    print("\nRemember where you save it - you'll need the path in the next step.")
    
    # Create email-specific directory
    safe_email = (email or "your_at_gmail_com").replace('@', '_at_').replace('.', '_')
    syft_dir = Path.home() / ".syft" / safe_email
    syft_dir.mkdir(parents=True, exist_ok=True)
    credentials_file = syft_dir / "credentials.json"
    
    # Ask user for the path to their downloaded credentials file
    print("\n" + "="*50)
    print("📁 Step 7: Provide Path to Downloaded Credentials")
    print("="*50)
    print("\nYou should have downloaded a JSON file that looks like:")
    print("  client_secret_XXXXXXX.apps.googleusercontent.com.json")
    print("\nPlease provide the full path to this file.")
    print("Examples:")
    print("  - ~/Downloads/client_secret_287888791426.apps.googleusercontent.com.json")
    print("  - /Users/you/Downloads/client_secret_*.json")
    print("  - C:\\Users\\you\\Downloads\\client_secret_*.json (Windows)")
    
    while True:
        try:
            downloaded_path = input("\nPath to your downloaded credentials file: ").strip()
            
            if not downloaded_path:
                print("❌ Please provide a path")
                continue
                
            # Expand user path and glob patterns
            import glob
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
            import shutil
            shutil.copy2(source_file, credentials_file)
            print(f"✅ Credentials file copied to: {credentials_file}")
            break
            
        except (KeyboardInterrupt, EOFError):
            print("\n\nSetup cancelled.")
            return
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Please try again.")
    
    # Completion
    print("\n✅ Setup Complete!")
    print("=" * 50)
    print("\nYour OAuth2 credentials are ready. You can now run:")
    print(f"  >>> from syft_client import login")
    print(f"  >>> client = login('{email or 'your@gmail.com'}')")
    print("\nThe first login will open a browser for authorization.")
    print("Future logins will use cached tokens.\n")
    
    # Return the credentials file path for the caller
    return credentials_file


def _ask_to_open_url(url: str, prompt: str = "Open this URL in your browser?") -> bool:
    """Ask user if they want to open a URL"""
    try:
        response = input(f"\n{prompt} (y/n): ").lower().strip()
        return response == 'y'
    except (KeyboardInterrupt, EOFError):
        return False


def check_or_create_credentials(email: Optional[str] = None, verbose: bool = True) -> Optional[Path]:
    """
    Check for credentials.json and run wizard if not found
    
    Returns:
        Path to credentials.json if found/created, None if wizard cancelled
    """
    # Build paths to check, including email-specific directory
    possible_paths = []
    
    if email:
        safe_email = email.replace('@', '_at_').replace('.', '_')
        possible_paths.append(Path.home() / ".syft" / safe_email / "credentials.json")
    
    # Also check legacy/fallback locations
    possible_paths.extend([
        Path.home() / ".syft" / "credentials.json",
        Path.home() / ".syft" / "google_oauth" / "credentials.json",
        Path("credentials.json"),
    ])
    
    # Check if credentials exist
    for path in possible_paths:
        if path.exists():
            if verbose:
                print(f"✓ Found credentials at: {path}")
            return path
    
    # No credentials found - check if we're in an interactive environment
    try:
        # Check for Jupyter/IPython
        get_ipython()
        in_notebook = True
    except NameError:
        in_notebook = False
    
    # Check if we can interact with user
    import sys
    is_interactive = sys.stdin.isatty() or in_notebook
    
    if not is_interactive:
        if verbose:
            print("\n❌ No credentials.json found and not in interactive mode.")
            print("Please run the wizard manually: create_oauth2_wizard()")
        return None
    
    # Run wizard
    print("\n❌ No OAuth2 credentials found.")
    print("Let's create them now!")
    
    try:
        response = input("\nRun setup wizard? (y/n): ").lower().strip()
        if response == 'y':
            # Run wizard and get the credentials file path
            creds_file = create_oauth2_wizard(email, verbose)
            if creds_file and creds_file.exists():
                return creds_file
            
            # Fallback: Check again after wizard
            for path in possible_paths:
                if path.exists():
                    return path
        else:
            print("\nTo run the wizard later:")
            print("  >>> from syft_client.platforms.google_personal.wizard import create_oauth2_wizard")
            print("  >>> create_oauth2_wizard()")
    except (KeyboardInterrupt, EOFError):
        print("\n\nSetup cancelled.")
    
    return None