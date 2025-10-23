"""
Main GCP Transport class
"""

import subprocess
from pathlib import Path
from googleapiclient.discovery import build, Resource

from .constants import SERVICES, API_SERVICES
from . import auth
from . import gcloud_oauth


class GCPTransport:
    """
    GCP Transport Layer for Google APIs

    Handles authentication and service access for:
    - Gmail API
    - Google Sheets API
    - Google Drive API
    - Google Forms API
    """

    def __init__(
        self,
        project_id: str,
        credentials_path: str = "credentials.json",
        auto_create_credentials: bool = True,
    ):
        """
        Initialize GCP Transport

        Args:
            project_id: GCP project ID
            credentials_path: Path to OAuth credentials.json file
            auto_create_credentials: If True, automatically create credentials.json
                                    using gcloud if it doesn't exist (default: True)
        """
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.auto_create_credentials = auto_create_credentials
        self._creds = None
        self._services = {}

    def connect(self) -> "GCPTransport":
        """
        Connect to GCP services

        This method:
        1. Creates OAuth credentials if needed (using gcloud)
        2. Enables required APIs (if gcloud available)
        3. Authenticates via OAuth
        4. Initializes service connections

        Returns:
            Self for method chaining

        Raises:
            FileNotFoundError: If credentials.json not found and auto-creation fails
        """
        print(f"🔧 Connecting to GCP project: {self.project_id}\n")

        # Step 0: Check for credentials.json, create if needed
        if not Path(self.credentials_path).exists():
            if self.auto_create_credentials:
                print("⚠️  credentials.json not found\n")
                print("🤖 Attempting automatic credential creation...\n")

                success = gcloud_oauth.auto_create_credentials(
                    self.project_id, self.credentials_path
                )

                if not success:
                    print("\n❌ Automatic credential creation failed")
                    print("\nManual fallback:")
                    print(
                        f"1. Go to: https://console.cloud.google.com/apis/credentials?project={self.project_id}"
                    )
                    print("2. Create Credentials → OAuth client ID → Desktop app")
                    print("3. Download JSON as 'credentials.json'")
                    raise FileNotFoundError(
                        "credentials.json not found and auto-creation failed"
                    )
            else:
                print(f"\n❌ credentials.json not found at: {self.credentials_path}")
                print("\nTo create credentials:")
                print(
                    f"1. Go to: https://console.cloud.google.com/apis/credentials?project={self.project_id}"
                )
                print("2. Create Credentials → OAuth client ID → Desktop app")
                print("3. Download JSON as 'credentials.json'")
                raise FileNotFoundError(
                    f"credentials.json not found at: {self.credentials_path}"
                )

        # Step 1: Enable APIs
        self._enable_apis()

        # Step 2: Authenticate
        print("🔐 Authenticating...\n")
        self._creds = auth.authenticate(self.credentials_path)

        # Step 3: Build services
        print("\n📦 Building services...")
        self._build_all_services()

        print("\n✅ Connected successfully!\n")
        print("Available services:")
        for service_name in SERVICES.keys():
            print(f"  - transport.{service_name}")

        return self

    def _enable_apis(self):
        """Enable required GCP APIs"""
        # Check if gcloud is available
        try:
            subprocess.run(["gcloud", "--version"], capture_output=True, check=True)
            has_gcloud = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            has_gcloud = False

        if has_gcloud:
            print("🔌 Enabling APIs via gcloud...")
            for api_service in API_SERVICES:
                try:
                    subprocess.run(
                        [
                            "gcloud",
                            "services",
                            "enable",
                            api_service,
                            f"--project={self.project_id}",
                        ],
                        capture_output=True,
                        check=True,
                    )
                    print(f"  ✅ {api_service}")
                except subprocess.CalledProcessError:
                    print(f"  ⚠️  {api_service} (may already be enabled)")
        else:
            print("⚠️  gcloud CLI not found. Please enable APIs manually:\n")
            print(
                f"Go to: https://console.cloud.google.com/apis/library?project={self.project_id}"
            )
            print("Enable these APIs:")
            for api_service in API_SERVICES:
                print(f"  - {api_service}")
            print()

    def _build_all_services(self):
        """Build all service connections"""
        for service_name, (api_name, version) in SERVICES.items():
            service = build(api_name, version, credentials=self._creds)
            self._services[service_name] = service
            print(f"  ✅ {service_name}")

    @property
    def gmail(self) -> Resource:
        """Gmail API service"""
        if "gmail" not in self._services:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._services["gmail"]

    @property
    def sheets(self) -> Resource:
        """Google Sheets API service"""
        if "sheets" not in self._services:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._services["sheets"]

    @property
    def drive(self) -> Resource:
        """Google Drive API service"""
        if "drive" not in self._services:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._services["drive"]

    @property
    def forms(self) -> Resource:
        """Google Forms API service"""
        if "forms" not in self._services:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._services["forms"]

    def test_connection(self) -> dict:
        """
        Test all service connections

        Returns:
            Dict mapping service name to success status
        """
        results = {}

        # Test Gmail
        try:
            self.gmail.users().labels().list(userId="me").execute()
            results["gmail"] = True
        except Exception as e:
            results["gmail"] = False
            print(f"❌ Gmail test failed: {e}")

        # Test Sheets
        try:
            spreadsheet = (
                self.sheets.spreadsheets()
                .create(
                    body={"properties": {"title": "Test Spreadsheet (Safe to Delete)"}}
                )
                .execute()
            )
            # Clean up test spreadsheet
            self.drive.files().delete(fileId=spreadsheet["spreadsheetId"]).execute()
            results["sheets"] = True
        except Exception as e:
            results["sheets"] = False
            print(f"❌ Sheets test failed: {e}")

        # Test Drive
        try:
            self.drive.files().list(pageSize=1).execute()
            results["drive"] = True
        except Exception as e:
            results["drive"] = False
            print(f"❌ Drive test failed: {e}")

        # Test Forms
        try:
            form = (
                self.forms.forms()
                .create(body={"info": {"title": "Test Form (Safe to Delete)"}})
                .execute()
            )
            # Clean up test form
            self.drive.files().delete(fileId=form["formId"]).execute()
            results["forms"] = True
        except Exception as e:
            results["forms"] = False
            print(f"❌ Forms test failed: {e}")

        return results
