"""Adaptive OAuth2 credentials.json creation wizard for Google Personal platform"""

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...environment import Environment, detect_environment


class WizardState:
    """Track the current state of the setup"""

    def __init__(self):
        self.has_credentials = False
        self.credentials_valid = False
        self.project_id = None
        self.api_status = {
            "gmail": False,
            "drive": False,
            "sheets": False,
            "forms": False,
        }
        self.environment = detect_environment()
        self.credentials_path = None
        self.email = None
        self.step6_start_time = None  # Track when step 6 started


def find_credentials(email: Optional[str] = None) -> Optional[Path]:
    """Search for existing credentials.json in all possible locations"""
    possible_paths = []

    if email:
        safe_email = email.replace("@", "_at_").replace(".", "_")
        possible_paths.append(Path.home() / ".syft" / safe_email / "credentials.json")

    possible_paths.extend(
        [
            Path.home() / ".syft" / "credentials.json",
            Path.home() / ".syft" / "google_oauth" / "credentials.json",
            Path("credentials.json"),
        ]
    )

    for path in possible_paths:
        if path.exists():
            return path

    return None


def validate_credentials_json(
    creds_path: Path,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate credentials.json structure and extract project_id

    Returns:
        (is_valid, project_id, error_message)
    """
    try:
        with open(creds_path, "r") as f:
            data = json.load(f)

        # Check if it's OAuth2 credentials (not service account)
        if "installed" in data:
            project_id = data["installed"].get("project_id")
            if project_id:
                return True, project_id, None
            else:
                return False, None, "No project_id found in credentials"
        elif "type" in data and data["type"] == "service_account":
            return (
                False,
                None,
                "Service account credentials found. OAuth2 credentials required.",
            )
        else:
            return False, None, "Invalid credentials format"

    except json.JSONDecodeError:
        return False, None, "Invalid JSON file"
    except Exception as e:
        return False, None, str(e)


def test_api_access(state: WizardState, credentials_path: Path) -> Dict[str, bool]:
    """Test which APIs are working with current credentials"""
    try:
        import os

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        # Set up credentials
        SCOPES = [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/forms.body",
            "https://www.googleapis.com/auth/forms.responses.readonly",
        ]

        creds = None
        token_path = credentials_path.parent / "token.json"

        # Load existing token if available
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                # Use run_console instead of run_local_server for better compatibility
                try:
                    creds = flow.run_local_server(port=0)
                except Exception:
                    creds = flow.run_console()

            # Save the credentials for the next run
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        # Now test each API
        api_status = {}

        # Test Gmail
        try:
            gmail = build("gmail", "v1", credentials=creds)
            gmail.users().messages().list(userId="me", maxResults=1).execute()
            api_status["gmail"] = True
        except Exception as e:
            api_status["gmail"] = False

        # Test Drive
        try:
            drive = build("drive", "v3", credentials=creds)
            drive.files().list(pageSize=1).execute()
            api_status["drive"] = True
        except Exception as e:
            api_status["drive"] = False

        # Test Sheets
        try:
            sheets = build("sheets", "v4", credentials=creds)
            # Try to get a non-existent sheet - 404 means API works
            try:
                sheets.spreadsheets().get(spreadsheetId="test123").execute()
                api_status["sheets"] = False  # Should not succeed
            except Exception as e:
                if "404" in str(e) or "was not found" in str(e):
                    api_status["sheets"] = True
                else:
                    api_status["sheets"] = False
        except Exception:
            api_status["sheets"] = False

        # Test Forms
        try:
            forms = build("forms", "v1", credentials=creds)
            # Try to get a non-existent form - 404 means API works
            try:
                forms.forms().get(formId="test123").execute()
                api_status["forms"] = False  # Should not succeed
            except Exception as e:
                if "404" in str(e) or "not found" in str(e).lower():
                    api_status["forms"] = True
                else:
                    api_status["forms"] = False
        except Exception:
            api_status["forms"] = False

        return api_status

    except Exception as e:
        print(f"Error testing API access: {e}")
        # Return all False if we can't test
        return {"gmail": False, "drive": False, "sheets": False, "forms": False}


def print_api_status(api_status: Dict[str, bool]) -> None:
    """Print API status with checkmarks"""
    print("\nAPI Status:")
    for api, enabled in api_status.items():
        status = "✓" if enabled else "✗"
        print(f"  {status} {api.title()} API")


def ask_yes_no(question: str, default: bool = None) -> bool:
    """Ask a yes/no question"""
    if default is True:
        prompt = f"{question} (Y/n): "
    elif default is False:
        prompt = f"{question} (y/N): "
    else:
        prompt = f"{question} (y/n): "

    while True:
        response = input(prompt).lower().strip()
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
        elif response == "" and default is not None:
            return default
        else:
            print("Please answer 'y' or 'n'")


def search_for_project_credentials(project_id: str) -> Optional[Path]:
    """Search for existing credentials that match a project ID"""
    search_dirs = [
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / ".syft",
        Path.cwd(),
    ]

    found_credentials = []

    for search_dir in search_dirs:
        if search_dir.exists():
            try:
                # Look for Google OAuth client files with specific pattern
                # Pattern: client_secret_*.apps.googleusercontent.com.json
                for file in search_dir.glob(
                    "client_secret_*.apps.googleusercontent.com.json"
                ):
                    try:
                        is_valid, file_project_id, _ = validate_credentials_json(file)
                        if is_valid and file_project_id == project_id:
                            found_credentials.append(file)
                    except:
                        pass

                # Also check for credentials.json files (non-recursive)
                for file in search_dir.glob("credentials.json"):
                    try:
                        is_valid, file_project_id, _ = validate_credentials_json(file)
                        if is_valid and file_project_id == project_id:
                            found_credentials.append(file)
                    except:
                        pass

                # Check .syft subdirectories for credentials
                if search_dir == Path.home():
                    syft_dir = search_dir / ".syft"
                    if syft_dir.exists():
                        # Check all subdirs in .syft
                        for subdir in syft_dir.iterdir():
                            if subdir.is_dir():
                                for file in subdir.glob("credentials.json"):
                                    try:
                                        is_valid, file_project_id, _ = (
                                            validate_credentials_json(file)
                                        )
                                        if is_valid and file_project_id == project_id:
                                            found_credentials.append(file)
                                    except:
                                        pass
            except:
                pass

    if found_credentials:
        print(f"\n✅ Found existing credentials for project {project_id}!")
        if len(found_credentials) == 1:
            print(f"   File: {found_credentials[0]}")
            if ask_yes_no("Use this existing credentials file?", default=True):
                return found_credentials[0]
        else:
            print("   Multiple files found:")
            for i, file in enumerate(found_credentials[:3]):
                print(f"   {i+1}. {file}")
            choice = input(
                "\nEnter number to use (1-3) or press Enter to create new: "
            ).strip()
            if choice in ["1", "2", "3"]:
                idx = int(choice) - 1
                if idx < len(found_credentials):
                    return found_credentials[idx]

    return None


def find_existing_project(email: Optional[str] = None) -> Optional[str]:
    """Guide user to find their existing project ID"""
    print("\n🔍 Let's find your existing project")
    print("-" * 40)

    # Build URL with authuser - use /welcome endpoint
    authuser = f"?authuser={email}" if email else ""
    welcome_url = f"https://console.cloud.google.com/welcome{authuser}"

    print(f"1. Open: {welcome_url}")
    print("2. Look at the project selector dropdown at the top of the page")
    print("3. Click the dropdown to see all your projects")
    print("4. Look for projects named like 'syft-client' or similar")
    print("5. Note the project ID (shown under the project name)")
    print("\nThe project ID is usually like 'syft-client-123456'")

    project_id = input(
        "\nEnter the project ID you found (or press Enter to create new): "
    ).strip()
    return project_id if project_id else None


def create_project_step(state: WizardState) -> str:
    """Step 1: Create Google Cloud Project"""
    print("\n📝 Step 1: Create a Google Cloud Project")
    print("-" * 40)

    authuser = f"?authuser={state.email}" if state.email else "?authuser=0"
    project_url = f"https://console.cloud.google.com/projectcreate{authuser}"

    print(f"1. Open: {project_url}")
    print("2. Enter a project name (e.g., 'Syft Client')")
    print("3. Click 'CREATE'")
    print("4. Wait for project creation (takes ~30 seconds)")

    input("\nPress Enter when your project is created...")
    return "select_project"


def select_project_step(state: WizardState) -> str:
    """Step 2: Select the project"""
    print("\n🎯 Step 2: Select your project")
    print("-" * 40)
    print("1. Look at the top bar of Google Cloud Console")
    print("2. Click the project dropdown (shows current project name)")
    print("3. Select your project from the list")
    print("4. Make sure it's selected before continuing")

    input("\nPress Enter AFTER you've selected your project...")
    return "get_project_id"


def get_project_id_step(state: WizardState) -> str:
    """Step 3: Get project ID"""
    print("\n📋 Step 3: Note your Project ID")
    print("-" * 40)
    print("Your Project ID is shown in the project selector dropdown")
    print("It's usually different from your project name (e.g., 'syft-client-123456')")

    project_id = input("\nEnter your Project ID: ").strip()
    if project_id:
        state.project_id = project_id

        # Check if we already have credentials for this project
        print("\n🔍 Checking for existing credentials...")
        existing_creds = search_for_project_credentials(project_id)
        if existing_creds:
            state.credentials_path = existing_creds
            state.has_credentials = True
            state.credentials_valid = True
            return "verify_setup"
        else:
            print("No existing credentials found. Continuing with setup...")

    return "enable_apis"


def enable_apis_step(state: WizardState) -> str:
    """Step 4: Enable required APIs"""
    print("\n🔌 Step 4: Enable Required APIs")
    print("-" * 40)

    # Build URLs with project ID
    authuser = f"authuser={state.email}&" if state.email else ""
    project = f"project={state.project_id}" if state.project_id else ""
    base_params = f"?{authuser}{project}".rstrip("&")

    apis_to_enable = []

    # Check which APIs need enabling
    if not state.api_status["gmail"]:
        apis_to_enable.append(
            (
                "Gmail",
                f"https://console.cloud.google.com/marketplace/product/google/gmail.googleapis.com{base_params}",
            )
        )
    if not state.api_status["drive"]:
        apis_to_enable.append(
            (
                "Drive",
                f"https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com{base_params}",
            )
        )
    if not state.api_status["sheets"]:
        apis_to_enable.append(
            (
                "Sheets",
                f"https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com{base_params}",
            )
        )
    if not state.api_status["forms"]:
        apis_to_enable.append(
            (
                "Forms",
                f"https://console.cloud.google.com/marketplace/product/google/forms.googleapis.com{base_params}",
            )
        )

    if not apis_to_enable:
        print("✅ All APIs are already enabled!")
        return "oauth_consent_screen"

    print("Please enable the following APIs:")
    for api_name, url in apis_to_enable:
        print(f"\n{api_name} API:")
        print(f"  1. Open: {url}")
        print(f"  2. Click 'ENABLE'")
        print(f"  3. Wait for confirmation")

    print("\n📍 Note: APIs tend to flicker for 5-10 seconds before enabling")
    input("\nPress Enter after enabling all APIs...")

    return "oauth_consent_screen"


def oauth_consent_screen_step(state: WizardState) -> str:
    """Step 5: Configure OAuth consent screen"""
    print("\n🔐 Step 5: Configure OAuth Consent Screen")
    print("-" * 40)

    authuser = f"authuser={state.email}&" if state.email else ""
    project = f"project={state.project_id}" if state.project_id else ""
    base_params = f"?{authuser}{project}".rstrip("&")

    consent_url = f"https://console.cloud.google.com/auth/overview/create{base_params}"

    print(f"1. Open: {consent_url}")
    print("\n2. Fill in the consent screen:")
    print("   a. Enter app name (e.g., 'Syft Client')")
    print("   b. Enter user support email (your email)")
    print("   c. Select 'External' user type")

    input("\nPress Enter after completing the first page...")

    print("\n3. Add developer contact information:")
    print("   - Enter your email address")

    print("\n4. Click through remaining sections:")
    print("   - Scopes: Skip (click 'SAVE AND CONTINUE')")
    print("   - Test users: Skip (click 'SAVE AND CONTINUE')")
    print("   - Summary: Click 'BACK TO DASHBOARD'")

    input("\nPress Enter when consent screen is created...")

    return "add_test_users"


def add_test_users_step(state: WizardState) -> str:
    """Step 6: Add test users to OAuth consent screen"""
    print("\n👥 Step 6: Add Test Users")
    print("-" * 40)

    authuser = f"authuser={state.email}&" if state.email else ""
    project = f"project={state.project_id}" if state.project_id else ""
    base_params = f"?{authuser}{project}".rstrip("&")

    test_users_url = f"https://console.cloud.google.com/auth/audience{base_params}"

    print(f"1. Open: {test_users_url}")
    print("\n2. Add yourself as a test user:")
    print("   - Click '+ ADD USERS' button")
    print(f"   - Enter your email: {state.email}")
    print("   - Click 'ADD'")
    print("\n3. Verify your email appears in the test users list")
    print("\n⚠️  Important: Only test users can use the app while it's in testing mode")

    input("\nPress Enter after adding yourself as a test user...")

    return "create_credentials"


def create_credentials_step(state: WizardState) -> str:
    """Step 7: Create OAuth credentials"""
    import time

    # Record when this step started
    state.step6_start_time = time.time()

    print("\n🔑 Step 7: Create OAuth2 Credentials")
    print("-" * 40)

    authuser = f"authuser={state.email}&" if state.email else ""
    project = f"project={state.project_id}" if state.project_id else ""
    base_params = f"?{authuser}{project}".rstrip("&")

    creds_url = f"https://console.cloud.google.com/apis/credentials{base_params}"

    print(f"1. Open: {creds_url}")
    print("2. Click '+ CREATE CREDENTIALS' button")
    print("3. Choose 'OAuth client ID'")
    print("4. Select 'Desktop app' as application type")
    print("5. Name it 'Syft Client' (or any name you prefer)")
    print("6. Click 'CREATE'")

    input("\nPress Enter after creating the OAuth client...")

    return "download_credentials"


def download_credentials_step(state: WizardState) -> str:
    """Step 8: Download and place credentials"""
    import time
    from datetime import datetime

    # Use timestamp from when step 6 started (or current time if not set)
    download_start_time = (
        state.step6_start_time if state.step6_start_time else time.time()
    )

    print("\n📥 Step 8: Download Credentials")
    print("-" * 40)
    print("1. In the credentials list, find your new OAuth 2.0 Client ID")
    print("2. Click the download button (⬇) on the right")
    print("3. Save the file (it may be named like 'client_secret_*.json')")

    input("\nPress Enter after downloading the file...")

    # Search for credentials files
    print("\n🔍 Searching for credentials files...")

    download_dirs = [
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.cwd(),
        Path.home(),  # Sometimes saved to home
    ]

    valid_credentials = []

    for download_dir in download_dirs:
        if download_dir.exists():
            try:
                # Look for Google OAuth client files with specific pattern
                for file in download_dir.glob(
                    "client_secret_*.apps.googleusercontent.com.json"
                ):
                    # Skip if file is too old (before step 6)
                    if (
                        state.step6_start_time
                        and file.stat().st_mtime < download_start_time - 60
                    ):  # 60s buffer
                        continue

                    # Try to validate and check if it matches our project
                    is_valid, project_id, _ = validate_credentials_json(file)

                    if is_valid and project_id:
                        # If we have a project ID, check if it matches
                        if state.project_id and project_id == state.project_id:
                            valid_credentials.append(
                                (file, project_id, True)
                            )  # Perfect match
                        elif not state.project_id:
                            # No project ID set, any valid creds are good
                            valid_credentials.append((file, project_id, False))

                # Also check for credentials.json files
                for file in download_dir.glob("credentials.json"):
                    # Skip if file is too old (before step 6)
                    if (
                        state.step6_start_time
                        and file.stat().st_mtime < download_start_time - 60
                    ):  # 60s buffer
                        continue

                    # Try to validate and check if it matches our project
                    is_valid, project_id, _ = validate_credentials_json(file)

                    if is_valid and project_id:
                        # If we have a project ID, check if it matches
                        if state.project_id and project_id == state.project_id:
                            valid_credentials.append(
                                (file, project_id, True)
                            )  # Perfect match
                        elif not state.project_id:
                            # No project ID set, any valid creds are good
                            valid_credentials.append((file, project_id, False))
            except:
                pass

    # Sort by: exact match first, then modification time
    valid_credentials.sort(key=lambda x: (x[2], x[0].stat().st_mtime), reverse=True)

    creds_path = None

    # If we found valid credentials
    if valid_credentials:
        if len(valid_credentials) == 1:
            file, proj_id, is_match = valid_credentials[0]
            msg = f"\n✅ Found credentials file: {file.name}"
            if is_match:
                msg += f" (matches project: {proj_id})"
            else:
                msg += f" (project: {proj_id})"
            print(msg)

            if ask_yes_no("Is this your credentials file?", default=True):
                creds_path = file
                if not state.project_id:
                    state.project_id = proj_id
        else:
            # Multiple valid files found
            print("\n✅ Found multiple valid credential files:")
            for i, (file, proj_id, is_match) in enumerate(valid_credentials[:3]):
                mod_time = datetime.fromtimestamp(file.stat().st_mtime).strftime(
                    "%H:%M:%S"
                )
                msg = f"   {i+1}. {file.name} (downloaded at {mod_time}"
                if is_match:
                    msg += f", matches project: {proj_id})"
                else:
                    msg += f", project: {proj_id})"
                print(msg)

            choice = input(
                "\nEnter number to use (1-3) or press Enter to specify manually: "
            ).strip()
            if choice in ["1", "2", "3"]:
                idx = int(choice) - 1
                if idx < len(valid_credentials):
                    creds_path = valid_credentials[idx][0]
                    if not state.project_id:
                        state.project_id = valid_credentials[idx][1]
    else:
        print("\n⚠️  No valid credentials files found automatically.")

    # If no file selected yet, ask for manual input
    if not creds_path:
        while True:
            path_input = input(
                "\nEnter the path to the downloaded credentials file: "
            ).strip()
            creds_path = Path(path_input).expanduser()

            if not creds_path.exists():
                print(f"❌ File not found: {creds_path}")
                continue

            break

    # Validate the credentials
    while True:
        is_valid, project_id, error_msg = validate_credentials_json(creds_path)

        if not is_valid:
            print(f"❌ Invalid credentials: {error_msg}")
            path_input = input(
                "\nEnter a different path (or press Ctrl+C to cancel): "
            ).strip()
            creds_path = Path(path_input).expanduser()
            continue

        # Update state with found project ID
        if project_id:
            state.project_id = project_id

        break

    # Copy to correct location
    target_dir = Path.home() / ".syft"
    if state.email:
        safe_email = state.email.replace("@", "_at_").replace(".", "_")
        target_dir = target_dir / safe_email

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "credentials.json"

    if creds_path != target_path:
        shutil.copy2(creds_path, target_path)
        print(f"✅ Credentials copied to: {target_path}")

    state.credentials_path = target_path
    state.has_credentials = True
    state.credentials_valid = True

    # Only mark as newly downloaded if we went through the full wizard
    # (i.e., created a new project). If using existing project, skip API test
    if hasattr(state, "went_through_full_wizard"):
        state.newly_downloaded = True

    return "verify_setup"


def verify_setup_step(state: WizardState) -> str:
    """Final verification of the setup"""
    print("\n✅ Setup Complete!")
    print("-" * 40)

    if state.credentials_path and state.credentials_path.exists():
        print(f"✅ Credentials saved to: {state.credentials_path}")
        print(f"✅ Project ID: {state.project_id}")

    # Never test APIs in the wizard - let login() handle it
    print("\n📌 Next steps:")
    print("1. Run the login command below")
    print("2. Authorize in your browser when prompted")
    print("3. Your tokens will be saved for future use")

    # Show next steps
    print("\n" + "=" * 50)
    print("\nYour OAuth2 credentials are ready. You can now run:")
    print(f"  >>> from syft_client import login")
    print(f"  >>> client = login('{state.email or 'your@gmail.com'}')")

    return "done"


def run_adaptive_wizard(
    email: Optional[str] = None, verbose: bool = True
) -> Optional[Path]:
    """
    Run the adaptive setup wizard

    Returns:
        Path to credentials.json if successful, None if cancelled
    """
    state = WizardState()
    state.email = email

    print("\n🔐 OAuth2 Credentials Setup Wizard")
    print("=" * 50)

    # Initialize next_step
    next_step = None

    # Check environment
    if state.environment == Environment.COLAB:
        try:
            import google.colab

            print("\n🎉 Good news! You're using Google Colab")
            print("Google Colab provides built-in authentication.")

            # But still need to check for project
            print(
                f"\nHave you created a Google Cloud project for Syft with {state.email} before?"
            )
            print(
                "(If you're not sure, say 'No' - it doesn't break anything, it'll just mean a few more steps)"
            )
            if ask_yes_no(""):
                project_id = find_existing_project(state.email)
                if project_id:
                    state.project_id = project_id
                    next_step = "enable_apis"
                else:
                    next_step = "create_project"
            else:
                next_step = "create_project"
        except ImportError:
            pass

    # Check for existing credentials (only if not already handling Colab)
    if next_step is None:
        creds_path = find_credentials(email)
    else:
        creds_path = None

    if creds_path:
        print(f"\n📁 Found existing credentials at: {creds_path}")

        # Validate credentials
        is_valid, project_id, error_msg = validate_credentials_json(creds_path)

        if is_valid:
            print("✅ Credentials are valid")
            print(f"📋 Project ID: {project_id}")

            state.has_credentials = True
            state.credentials_valid = True
            state.credentials_path = creds_path
            state.project_id = project_id

            # Test API access with real calls
            print(
                "\nChecking API status (this may open a browser for authentication)..."
            )
            api_status = test_api_access(state, creds_path)
            state.api_status = api_status

            print_api_status(state.api_status)

            if not all(state.api_status.values()):
                print("\n⚠️ Some APIs are not enabled. Let's fix them.")
                next_step = "enable_apis"
            else:
                print("\n✅ All APIs are enabled!")
                next_step = "done"

        else:
            print(f"\n❌ {error_msg}")
            print("You'll need to download new credentials.")

            if project_id or ask_yes_no("\nDo you know your Google Cloud project ID?"):
                if not project_id:
                    project_id = input("Enter your project ID: ").strip()

                if project_id:
                    state.project_id = project_id
                    next_step = "create_credentials"
                else:
                    next_step = "find_project"
            else:
                next_step = "find_project"
    else:
        # No credentials found
        print("\n❌ No OAuth2 credentials found.")
        print("Let's set them up!")

        print(
            f"\nHave you created a Google Cloud project for Syft with {state.email} before?"
        )
        print(
            "(If you're not sure, say 'No' - it doesn't break anything, it'll just mean a few more steps)"
        )
        if ask_yes_no(""):
            if ask_yes_no("Do you remember your Google Cloud project ID?"):
                project_id = input("\nEnter your project ID: ").strip()
                if project_id:
                    state.project_id = project_id
                    # Search for existing credentials for this project
                    existing_creds = search_for_project_credentials(project_id)
                    if existing_creds:
                        state.credentials_path = existing_creds
                        state.has_credentials = True
                        state.credentials_valid = True
                        next_step = "verify_setup"
                    else:
                        print("\nNo existing credentials found for this project.")
                        next_step = "create_credentials"
                else:
                    next_step = "find_project"
            else:
                project_id = find_existing_project(state.email)
                if project_id:
                    state.project_id = project_id
                    # Search for existing credentials for this project
                    existing_creds = search_for_project_credentials(project_id)
                    if existing_creds:
                        state.credentials_path = existing_creds
                        state.has_credentials = True
                        state.credentials_valid = True
                        next_step = "verify_setup"
                    else:
                        print("\nNo existing credentials found for this project.")
                        next_step = "create_credentials"
                else:
                    next_step = "create_project"
        else:
            state.went_through_full_wizard = True
            next_step = "create_project"

    # Execute wizard steps
    step_map = {
        "create_project": create_project_step,
        "select_project": select_project_step,
        "get_project_id": get_project_id_step,
        "find_project": lambda s: find_existing_project(s.email) or "create_project",
        "enable_apis": enable_apis_step,
        "oauth_consent_screen": oauth_consent_screen_step,
        "add_test_users": add_test_users_step,
        "create_credentials": create_credentials_step,
        "download_credentials": download_credentials_step,
        "verify_setup": verify_setup_step,
    }

    while next_step != "done":
        if next_step in step_map:
            try:
                next_step = step_map[next_step](state)
            except KeyboardInterrupt:
                print("\n\nSetup cancelled.")
                return None
        else:
            break

    return state.credentials_path


def create_oauth2_wizard(
    email: Optional[str] = None, verbose: bool = True
) -> Optional[Path]:
    """
    Backward compatible entry point
    """
    return run_adaptive_wizard(email, verbose)


def scan_for_any_client_secrets(
    email: Optional[str] = None,
) -> Optional[Tuple[Path, str]]:
    """
    Scan for any client_secret files and check if they work with the given email

    Returns:
        (credentials_path, project_id) if found, None otherwise
    """
    search_dirs = [
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.cwd(),
    ]

    found_secrets = []

    print("\n🔍 Scanning for existing Google credentials...")

    for search_dir in search_dirs:
        if search_dir.exists():
            try:
                # Look for client_secret files
                for file in search_dir.glob(
                    "client_secret_*.apps.googleusercontent.com.json"
                ):
                    try:
                        is_valid, project_id, _ = validate_credentials_json(file)
                        if is_valid:
                            found_secrets.append((file, project_id))
                    except:
                        pass
            except:
                pass

    if not found_secrets:
        return None

    # If email is provided, we could try to test which credentials work with this email
    # For now, we'll show all found credentials and let user choose
    if len(found_secrets) == 1:
        file, project_id = found_secrets[0]
        print(f"\n✅ Found Google credentials file!")
        print(f"   File: {file.name}")
        print(f"   Project: {project_id}")
        if ask_yes_no(f"\nUse this for {email}?", default=True):
            return file, project_id
    else:
        print(f"\n✅ Found {len(found_secrets)} Google credential files:")
        for i, (file, proj_id) in enumerate(found_secrets[:5]):  # Show max 5
            print(f"   {i+1}. {file.name}")
            print(f"      Project: {proj_id}")

        print(f"\nWhich one is for {email}?")
        choice = input("Enter number (1-5) or press Enter to skip: ").strip()
        if choice in ["1", "2", "3", "4", "5"]:
            idx = int(choice) - 1
            if idx < len(found_secrets):
                return found_secrets[idx]

    return None


def check_or_create_credentials(
    email: Optional[str] = None, verbose: bool = True
) -> Optional[Path]:
    """
    Check for credentials.json and run wizard if needed

    Returns:
        Path to credentials.json if found/created, None if wizard cancelled
    """
    # Quick check if credentials exist in expected locations
    creds_path = find_credentials(email)

    if creds_path:
        is_valid, _, _ = validate_credentials_json(creds_path)
        if is_valid:
            if verbose:
                print(f"✅ Found valid credentials at: {creds_path}")
            return creds_path

    # No credentials in .syft, scan for client_secret files
    found_creds = scan_for_any_client_secrets(email)
    if found_creds:
        file_path, project_id = found_creds

        # Copy to the correct location
        target_dir = Path.home() / ".syft"
        if email:
            safe_email = email.replace("@", "_at_").replace(".", "_")
            target_dir = target_dir / safe_email

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / "credentials.json"

        import shutil

        shutil.copy2(file_path, target_path)
        print(f"\n✅ Credentials copied to: {target_path}")

        return target_path

    # Check if we're in an interactive environment
    is_interactive = (
        hasattr(sys, "ps1")
        or sys.flags.interactive
        or (hasattr(sys, "stdin") and sys.stdin.isatty())
    )

    if not is_interactive:
        if verbose:
            print("\n❌ No credentials.json found and not in interactive mode.")
            print("Please run the wizard manually: create_oauth2_wizard()")
        return None

    # Run the adaptive wizard automatically
    print("\nNo credentials found. Starting setup wizard...")
    try:
        return run_adaptive_wizard(email, verbose)
    except (KeyboardInterrupt, EOFError):
        print("\n\nSetup cancelled.")
        print("\nTo run the wizard later:")
        print(
            "  >>> from syft_client.platforms.google_personal.wizard import create_oauth2_wizard"
        )
        print("  >>> create_oauth2_wizard()")

    return None
