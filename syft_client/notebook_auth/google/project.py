"""GCP project management - pure functions with no UI dependencies."""

import time
from typing import Optional

from google.auth.credentials import Credentials
from google.cloud import resourcemanager_v3
from googleapiclient.discovery import build


class ProjectManager:
    """Manages GCP project operations - pure functions, no UI."""

    @staticmethod
    def check_tos(
        credentials: Credentials, user_email: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user has accepted GCP Terms of Service.

        Args:
            credentials: Google credentials for GCP API
            user_email: User's email address

        Returns:
            Tuple of (tos_accepted, error_message)
            - (True, None) if ToS accepted
            - (False, console_url) if ToS needs to be accepted
            - (False, error_msg) if error occurred
        """
        try:
            # Try to create a test project - this will fail if ToS not accepted
            test_project_id = f"tos-test-{int(time.time())}"
            service = build("cloudresourcemanager", "v1", credentials=credentials)
            body = {"projectId": test_project_id, "name": "ToS Test"}

            operation = service.projects().create(body=body).execute()
            time.sleep(2)
            status = service.operations().get(name=operation["name"]).execute()

            # Wait for operation to complete
            if not status.get("done"):
                time.sleep(2)
                status = service.operations().get(name=operation["name"]).execute()

            # Check result
            if status.get("done"):
                if "error" in status:
                    error = status["error"]
                    # Code 9 = FAILED_PRECONDITION, check for ToS message
                    if error.get("code") == 9 and "Terms of Service" in error.get(
                        "message", ""
                    ):
                        console_url = (
                            f"https://console.cloud.google.com/?authuser={user_email}"
                        )
                        return False, console_url
                    else:
                        return False, error.get("message", "Unknown error")
                else:
                    # Success - clean up test project
                    try:
                        service.projects().delete(projectId=test_project_id).execute()
                    except Exception:
                        pass
                    return True, None

            return False, "Operation timed out"

        except Exception as e:
            return False, str(e)

    @staticmethod
    def list_projects(credentials: Credentials) -> list[dict]:
        """
        List user's GCP projects.

        Args:
            credentials: Google credentials for GCP API

        Returns:
            List of project dicts with 'project_id' and 'name' keys
        """
        try:
            client = resourcemanager_v3.ProjectsClient(credentials=credentials)
            projects_list = []

            for project in client.search_projects():
                if project.state == resourcemanager_v3.Project.State.ACTIVE:
                    projects_list.append(
                        {
                            "project_id": project.project_id,
                            "name": project.display_name or project.project_id,
                        }
                    )

            return projects_list
        except Exception:
            return []

    @staticmethod
    def create_project(
        credentials: Credentials, project_id: str, project_name: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Create new GCP project.

        Args:
            credentials: Google credentials for GCP API
            project_id: Unique project ID
            project_name: Display name (defaults to project_id)

        Returns:
            Tuple of (success, error_message)
        """
        try:
            service = build("cloudresourcemanager", "v1", credentials=credentials)
            body = {
                "projectId": project_id,
                "name": project_name or project_id,
            }

            operation = service.projects().create(body=body).execute()
            time.sleep(3)

            # Wait for operation to complete
            op_status = service.operations().get(name=operation["name"]).execute()

            if not op_status.get("done"):
                time.sleep(3)
                op_status = service.operations().get(name=operation["name"]).execute()

            if "error" in op_status:
                error = op_status["error"]
                return False, error.get("message", "Unknown error")

            return True, None

        except Exception as e:
            return False, str(e)

    @staticmethod
    def generate_project_id(prefix: str = "workspace") -> str:
        """
        Generate a unique project ID.

        Args:
            prefix: Prefix for the project ID

        Returns:
            Generated project ID in format: {prefix}-YYYYMMDD-XXXX
        """
        from datetime import datetime

        date_str = datetime.now().strftime("%Y%m%d")
        random_digits = str(int(time.time()))[-4:]
        return f"{prefix}-{date_str}-{random_digits}"

    @staticmethod
    def get_user_info(credentials: Credentials) -> dict:
        """
        Get user information from OAuth2.

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            Dict with 'email' and 'name' keys
        """
        try:
            oauth2 = build("oauth2", "v2", credentials=credentials)
            user_info = oauth2.userinfo().get().execute()

            email = user_info.get("email", "")
            full_name = user_info.get("name", "")

            # Extract first name
            if full_name and len(full_name.split()) > 0:
                first_name = full_name.split()[0]
            else:
                first_name = email.split("@")[0] if email else "there"

            return {"email": email, "name": full_name, "first_name": first_name}

        except Exception:
            return {"email": "", "name": "", "first_name": "there"}
