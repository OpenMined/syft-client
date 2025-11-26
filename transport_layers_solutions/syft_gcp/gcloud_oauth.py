"""
Automatic OAuth credential creation using gcloud CLI
"""

import subprocess
import json
import re
from typing import Optional, Tuple


def check_gcloud_installed() -> bool:
    """Check if gcloud CLI is installed"""
    try:
        subprocess.run(["gcloud", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def gcloud_auth_login() -> bool:
    """
    Run gcloud auth login to authenticate user
    Opens browser for Google sign-in

    Returns:
        True if successful, False otherwise
    """
    print("🔐 Running gcloud auth login...")
    print("🌐 Browser will open for Google sign-in\n")

    try:
        result = subprocess.run(["gcloud", "auth", "login"], check=True)
        print("\n✅ gcloud authentication successful!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ gcloud auth login failed: {e}")
        return False


def get_authenticated_email() -> Optional[str]:
    """Get the currently authenticated email from gcloud"""
    try:
        result = subprocess.run(
            [
                "gcloud",
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        email = result.stdout.strip()
        return email if email else None
    except subprocess.CalledProcessError:
        return None


def create_oauth_brand(
    project_id: str, app_title: str = "Syft Client"
) -> Optional[str]:
    """
    Create OAuth consent screen (brand)

    Returns:
        Brand name if successful, None otherwise
    """
    email = get_authenticated_email()
    if not email:
        print("❌ No authenticated gcloud account found")
        return None

    print("📋 Creating OAuth consent screen...")
    print(f"   App title: {app_title}")
    print(f"   Support email: {email}")

    try:
        # Try to create brand
        result = subprocess.run(
            [
                "gcloud",
                "alpha",
                "iap",
                "oauth-brands",
                "create",
                f"--application_title={app_title}",
                f"--support_email={email}",
                f"--project={project_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Extract brand name from output
        # Format: "name: projects/PROJECT_NUMBER/brands/BRAND_ID"
        match = re.search(r"name:\s*(projects/\d+/brands/\d+)", result.stdout)
        if match:
            brand_name = match.group(1)
            print(f"✅ OAuth brand created: {brand_name}\n")
            return brand_name
        else:
            print("⚠️  Brand created but couldn't parse name\n")
            return None

    except subprocess.CalledProcessError as e:
        # Brand might already exist
        if "already exists" in e.stderr or "ALREADY_EXISTS" in e.stderr:
            print("✅ OAuth brand already exists")
            # Try to list brands to get the name
            return list_oauth_brands(project_id)
        else:
            print(f"❌ Failed to create OAuth brand: {e.stderr}")
            return None


def list_oauth_brands(project_id: str) -> Optional[str]:
    """List OAuth brands and return the first one"""
    try:
        result = subprocess.run(
            [
                "gcloud",
                "alpha",
                "iap",
                "oauth-brands",
                "list",
                f"--project={project_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse output to find brand name
        match = re.search(r"(projects/\d+/brands/\d+)", result.stdout)
        if match:
            brand_name = match.group(1)
            print(f"   Found existing brand: {brand_name}\n")
            return brand_name
        return None
    except subprocess.CalledProcessError:
        return None


def create_oauth_client(
    brand_name: str, display_name: str = "Syft Client Desktop"
) -> Optional[Tuple[str, str]]:
    """
    Create OAuth client credentials

    Returns:
        Tuple of (client_id, client_secret) if successful, None otherwise
    """
    print("🔑 Creating OAuth client credentials...")
    print(f"   Display name: {display_name}")

    try:
        result = subprocess.run(
            [
                "gcloud",
                "alpha",
                "iap",
                "oauth-clients",
                "create",
                brand_name,
                f"--display_name={display_name}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse client ID and secret from output
        # Format:
        # name: projects/.../brands/.../identityAwareProxyClients/CLIENT_ID
        # secret: CLIENT_SECRET

        client_id_match = re.search(
            r"identityAwareProxyClients/([^\s\n]+)", result.stdout
        )
        secret_match = re.search(r"secret:\s*([^\s\n]+)", result.stdout)

        if client_id_match and secret_match:
            client_id = client_id_match.group(1)
            client_secret = secret_match.group(1)
            print("✅ OAuth client created")
            print(f"   Client ID: {client_id[:20]}...")
            print(f"   Secret: {client_secret[:10]}...\n")
            return (client_id, client_secret)
        else:
            print("⚠️  Client created but couldn't parse credentials\n")
            return None

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create OAuth client: {e.stderr}")
        return None


def save_credentials_json(
    client_id: str, client_secret: str, output_path: str = "credentials.json"
):
    """
    Save OAuth credentials as credentials.json file

    Format matches what you download from Google Cloud Console
    """
    credentials = {
        "installed": {
            "client_id": client_id,
            "project_id": "syft-client",  # Generic, doesn't matter much
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
        }
    }

    with open(output_path, "w") as f:
        json.dump(credentials, f, indent=2)

    print(f"💾 Saved credentials to: {output_path}\n")


def auto_create_credentials(
    project_id: str, credentials_path: str = "credentials.json"
) -> bool:
    """
    Fully automated credential creation workflow

    Steps:
    1. Check if gcloud is installed
    2. Run gcloud auth login
    3. Create OAuth brand (consent screen)
    4. Create OAuth client
    5. Save credentials.json

    Returns:
        True if successful, False otherwise
    """
    print("🚀 Starting automated OAuth credential creation\n")

    # Step 1: Check gcloud
    if not check_gcloud_installed():
        print("❌ gcloud CLI not found. Please install it first:")
        print("   https://cloud.google.com/sdk/docs/install\n")
        return False

    print("✅ gcloud CLI found\n")

    # Step 2: Authenticate with gcloud
    if not get_authenticated_email():
        print("⚠️  No active gcloud authentication found")
        if not gcloud_auth_login():
            return False
    else:
        email = get_authenticated_email()
        print(f"✅ Already authenticated as: {email}\n")

    # Step 3: Create OAuth brand
    brand_name = create_oauth_brand(project_id)
    if not brand_name:
        print("\n❌ Failed to create/find OAuth brand")
        print("\nManual fallback:")
        print(
            f"1. Go to: https://console.cloud.google.com/apis/credentials/consent?project={project_id}"
        )
        print("2. Configure OAuth consent screen manually")
        return False

    # Step 4: Create OAuth client
    credentials = create_oauth_client(brand_name)
    if not credentials:
        print("\n❌ Failed to create OAuth client")
        return False

    client_id, client_secret = credentials

    # Step 5: Save credentials.json
    save_credentials_json(client_id, client_secret, credentials_path)

    print("✅ Automated credential creation complete!\n")
    return True
