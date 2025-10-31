"""Google Workspace API management - pure functions with no UI dependencies."""

import time
from typing import Optional

from google.auth.credentials import Credentials
from google.oauth2.credentials import Credentials as OAuth2Credentials
from googleapiclient.discovery import build


class APIManager:
    """Manages Google Workspace APIs - pure functions, no UI."""

    # Map friendly names to Google API service names
    WORKSPACE_APIS = {
        "gmail": "gmail.googleapis.com",
        "drive": "drive.googleapis.com",
        "sheets": "sheets.googleapis.com",
        "forms": "forms.googleapis.com",
    }

    @staticmethod
    def enable_api(
        credentials: Credentials, project_id: str, api_name: str
    ) -> tuple[bool, Optional[str]]:
        """
        Enable a Google API for a project.

        Args:
            credentials: Google credentials for Service Usage API
            project_id: GCP project ID
            api_name: API name (e.g., 'gmail', 'drive')

        Returns:
            Tuple of (success, error_message)
        """
        if api_name not in APIManager.WORKSPACE_APIS:
            return False, f"Unknown API: {api_name}"

        try:
            service_usage = build("serviceusage", "v1", credentials=credentials)
            api_service = APIManager.WORKSPACE_APIS[api_name]
            service_name = f"projects/{project_id}/services/{api_service}"

            # Check if already enabled
            try:
                service_info = service_usage.services().get(name=service_name).execute()
                if service_info.get("state") == "ENABLED":
                    return True, "already_enabled"
            except Exception:
                pass

            # Enable the API
            service_usage.services().enable(name=service_name).execute()
            time.sleep(2)  # Wait for API to propagate

            return True, None

        except Exception as e:
            return False, str(e)

    @staticmethod
    def enable_all(
        credentials: Credentials, project_id: str, api_names: list[str]
    ) -> dict[str, str]:
        """
        Enable multiple APIs and return results.

        Args:
            credentials: Google credentials for Service Usage API
            project_id: GCP project ID
            api_names: List of API names to enable

        Returns:
            Dict mapping api_name to status: 'enabled', 'already_enabled', or 'error'
        """
        results = {}

        for api_name in api_names:
            success, message = APIManager.enable_api(credentials, project_id, api_name)
            if success:
                results[api_name] = message or "enabled"
            else:
                results[api_name] = "error"

        # Wait for APIs to propagate
        time.sleep(5)

        return results

    @staticmethod
    def test_api(
        credentials: OAuth2Credentials, api_name: str
    ) -> tuple[bool, Optional[str]]:
        """
        Test if an API is working with given credentials.

        Args:
            credentials: OAuth2 credentials (not project credentials!)
            api_name: API name to test

        Returns:
            Tuple of (success, error_message)
        """
        try:
            if api_name == "gmail":
                service = build("gmail", "v1", credentials=credentials)
                service.users().getProfile(userId="me").execute()

            elif api_name == "drive":
                service = build("drive", "v3", credentials=credentials)
                service.files().list(pageSize=1, fields="files(id, name)").execute()

            elif api_name == "sheets":
                service = build("sheets", "v4", credentials=credentials)
                # Create a test spreadsheet
                sheet = (
                    service.spreadsheets()
                    .create(
                        body={"properties": {"title": "Test Sheet (can be deleted)"}}
                    )
                    .execute()
                )

                # Clean up immediately
                try:
                    drive_service = build("drive", "v3", credentials=credentials)
                    drive_service.files().delete(
                        fileId=sheet["spreadsheetId"]
                    ).execute()
                except Exception:
                    pass

            elif api_name == "forms":
                service = build("forms", "v1", credentials=credentials)
                # Create a test form
                form = (
                    service.forms()
                    .create(body={"info": {"title": "Test Form (can be deleted)"}})
                    .execute()
                )

                # Clean up immediately
                try:
                    drive_service = build("drive", "v3", credentials=credentials)
                    drive_service.files().delete(fileId=form["formId"]).execute()
                except Exception:
                    pass

            else:
                return False, f"Unknown API: {api_name}"

            return True, None

        except Exception as e:
            return False, str(e)

    @staticmethod
    def test_all(
        credentials: OAuth2Credentials, api_names: list[str]
    ) -> dict[str, str]:
        """
        Test multiple APIs and return results.

        Args:
            credentials: OAuth2 credentials
            api_names: List of API names to test

        Returns:
            Dict mapping api_name to status: 'working' or 'error'
        """
        results = {}

        for api_name in api_names:
            success, _ = APIManager.test_api(credentials, api_name)
            results[api_name] = "working" if success else "error"

        return results
