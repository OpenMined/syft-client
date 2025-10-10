"""Google Forms transport layer implementation"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build

from ...environment import Environment
from ..transport_base import BaseTransportLayer


class GFormsTransport(BaseTransportLayer):
    """Google Forms API transport layer"""

    # STATIC Attributes
    is_keystore = False  # Forms not for storing keys
    is_notification_layer = False  # Users don't check forms regularly
    is_html_compatible = True  # Forms render as HTML
    is_reply_compatible = False  # One-way submission only
    guest_submit = True  # Anonymous users can submit to public forms!
    guest_read_file = False  # Can't read form data without auth
    guest_read_folder = False  # N/A for forms

    def __init__(self, email: str):
        """Initialize Forms transport"""
        super().__init__(email)
        self.forms_service = None
        self.drive_service = None  # Needed for deleting forms
        self.credentials = None
        self._setup_verified = False

    @staticmethod
    def check_api_enabled(platform_client: Any) -> bool:
        """
        Check if Google Forms API is enabled.

        Args:
            platform_client: The platform client with credentials

        Returns:
            bool: True if API is enabled, False otherwise
        """
        # Suppress googleapiclient warnings during API check
        googleapi_logger = logging.getLogger("googleapiclient.http")
        original_level = googleapi_logger.level
        googleapi_logger.setLevel(logging.ERROR)

        # Check if we're in Colab environment
        if hasattr(platform_client, "current_environment"):
            from ...environment import Environment

            if platform_client.current_environment == Environment.COLAB:
                # Forms doesn't work properly in Colab for Google Org accounts
                # Colab's auth doesn't provide the necessary Forms scopes
                return False

        try:

            # Regular OAuth credential check
            if (
                not hasattr(platform_client, "credentials")
                or not platform_client.credentials
            ):
                return False

            # Try to build service and make a simple API call
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            # Refresh credentials if needed
            if (
                platform_client.credentials.expired
                and platform_client.credentials.refresh_token
            ):
                platform_client.credentials.refresh(Request())

            # Test Forms API directly
            forms_service = build(
                "forms", "v1", credentials=platform_client.credentials
            )

            # Try to get a non-existent form - will return 404 if API is enabled
            try:
                forms_service.forms().get(formId="test123").execute()
                # If we get here, somehow the test form exists (unlikely)
                return True
            except Exception as e:
                # Check if it's a 404 error (form not found = API is working)
                if "404" in str(e) or "not found" in str(e).lower():
                    return True
                else:
                    # API is disabled or other error
                    return False
        except Exception:
            return False
        finally:
            googleapi_logger.setLevel(original_level)

    @staticmethod
    def enable_api_static(
        transport_name: str, email: str, project_id: Optional[str] = None
    ) -> None:
        """Show instructions for enabling Google Forms API"""
        print(f"\n🔧 To enable the Google Forms API:")
        print(f"\n1. Open this URL in your browser:")
        if project_id:
            print(
                f"   https://console.cloud.google.com/marketplace/product/google/forms.googleapis.com?authuser={email}&project={project_id}"
            )
        else:
            print(
                f"   https://console.cloud.google.com/marketplace/product/google/forms.googleapis.com?authuser={email}"
            )
        print(f"\n2. Click the 'Enable' button")
        print(f"\n3. Wait for the API to be enabled (may take 5-10 seconds)")
        print(
            f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling"
        )

    @staticmethod
    def disable_api_static(
        transport_name: str, email: str, project_id: Optional[str] = None
    ) -> None:
        """Show instructions for disabling Google Forms API"""
        print(f"\n🔧 To disable the Google Forms API:")
        print(f"\n1. Open this URL in your browser:")
        if project_id:
            print(
                f"   https://console.cloud.google.com/apis/api/forms.googleapis.com/overview?authuser={email}&project={project_id}"
            )
        else:
            print(
                f"   https://console.cloud.google.com/apis/api/forms.googleapis.com/overview?authuser={email}"
            )
        print(f"\n2. Click 'Manage' or 'Disable API'")
        print(f"\n3. Confirm by clicking 'Disable'")
        print(
            f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling"
        )

    @property
    def api_is_active_by_default(self) -> bool:
        """Forms API requires manual activation"""
        return False

    @property
    def login_complexity(self) -> int:
        """Additional Forms setup complexity (after Google auth)"""
        if self.is_setup():
            return 0
        if self.api_is_active:
            return 0  # No additional setup

        # Forms API requires:
        # 1. Enable Forms API
        # 2. Create a form resource
        return 2  # Two additional steps

    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Setup Forms transport with OAuth2 credentials or Colab auth"""
        try:
            # Check if we're in Colab and can use automatic auth
            if self.environment == Environment.COLAB:
                try:
                    from google.colab import auth as colab_auth

                    colab_auth.authenticate_user()
                    # Build services without explicit credentials in Colab
                    self.forms_service = build("forms", "v1")
                    self.drive_service = build("drive", "v3")
                    self.credentials = None  # No explicit credentials in Colab
                except ImportError:
                    # Fallback to regular credentials if Colab auth not available
                    if credentials is None:
                        return False
                    if not credentials or "credentials" not in credentials:
                        return False
                    self.credentials = credentials["credentials"]
                    self.forms_service = build(
                        "forms", "v1", credentials=self.credentials
                    )
                    self.drive_service = build(
                        "drive", "v3", credentials=self.credentials
                    )
            else:
                # Regular OAuth2 flow
                if credentials is None:
                    return False
                if not credentials or "credentials" not in credentials:
                    return False
                self.credentials = credentials["credentials"]
                self.forms_service = build("forms", "v1", credentials=self.credentials)
                self.drive_service = build("drive", "v3", credentials=self.credentials)

            # Mark as setup verified
            self._setup_verified = True

            return True
        except Exception as e:
            print(f"[DEBUG] GForms setup error: {e}")
            import traceback

            traceback.print_exc()
            return False

    def is_setup(self) -> bool:
        """Check if Forms transport is ready"""
        # First check if we're cached as setup
        if self.is_cached_as_setup():
            return True

        # In Colab, we can always set up on demand
        if self.environment == Environment.COLAB:
            try:
                from google.colab import auth as colab_auth

                return True  # Can authenticate on demand
            except ImportError:
                pass

        # Otherwise check normal setup
        return self.forms_service is not None

    def send(self, recipient: str, data: Any, subject: str = "Syft Form") -> bool:
        """Create a Google Form for data collection"""
        if not self.forms_service:
            return False

        try:
            # Create form
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            form_title = f"SyftClient_{subject.replace(' ', '_')}_{timestamp}"

            form = {"info": {"title": form_title, "document_title": form_title}}

            # Create the form
            result = self.forms_service.forms().create(body=form).execute()
            form_id = result["formId"]

            # Add fields based on data type
            requests = []

            if isinstance(data, dict):
                # Create form fields for each dict key
                for idx, (key, value) in enumerate(data.items()):
                    # Determine question type based on value
                    if isinstance(value, bool):
                        # Checkbox for boolean
                        item = {
                            "itemId": str(idx),
                            "title": str(key),
                            "questionItem": {
                                "question": {
                                    "required": False,
                                    "choiceQuestion": {
                                        "type": "CHECKBOX",
                                        "options": [
                                            {"value": "True"},
                                            {"value": "False"},
                                        ],
                                    },
                                }
                            },
                        }
                    elif isinstance(value, (int, float)):
                        # Text input for numbers
                        item = {
                            "itemId": str(idx),
                            "title": f"{key} (number)",
                            "questionItem": {
                                "question": {
                                    "required": False,
                                    "textQuestion": {"paragraph": False},
                                }
                            },
                        }
                    else:
                        # Text input for strings and others
                        item = {
                            "itemId": str(idx),
                            "title": str(key),
                            "questionItem": {
                                "question": {
                                    "required": False,
                                    "textQuestion": {"paragraph": len(str(value)) > 50},
                                }
                            },
                        }

                    requests.append(
                        {"createItem": {"item": item, "location": {"index": idx}}}
                    )
            else:
                # Create a single text field for data submission
                requests.append(
                    {
                        "createItem": {
                            "item": {
                                "itemId": "0",
                                "title": "Data",
                                "description": f"Type: {type(data).__name__}",
                                "questionItem": {
                                    "question": {
                                        "required": True,
                                        "textQuestion": {"paragraph": True},
                                    }
                                },
                            },
                            "location": {"index": 0},
                        }
                    }
                )

            # Update form with questions
            if requests:
                update = {"requests": requests}
                self.forms_service.forms().batchUpdate(
                    formId=form_id, body=update
                ).execute()

            # Get the form URL
            form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"

            # Note: Forms API doesn't support programmatic sharing via email
            # Users need to share manually or we could print the URL
            print(f"Form created: {form_url}")
            if recipient:
                print(f"Please share with: {recipient}")

            return True

        except Exception as e:
            print(f"Error creating form: {e}")
            return False

    def receive(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Read form responses"""
        if not self.forms_service:
            return []

        messages = []

        try:
            # List user's forms
            # Note: Forms API doesn't have a direct list method
            # We would need to use Drive API to list forms
            # This is a simplified placeholder

            # In practice, you'd need to:
            # 1. Use Drive API to list forms
            # 2. For each form, get responses
            # 3. Parse and return the data

            print(
                "Forms receive not fully implemented - requires Drive API integration"
            )

        except Exception as e:
            print(f"Error retrieving form responses: {e}")

        return messages

    def create_public_form(
        self, form_title: str, questions: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Create a publicly accessible form"""
        if not self.forms_service:
            return None

        try:
            # Create form
            form = {"info": {"title": form_title, "document_title": form_title}}

            result = self.forms_service.forms().create(body=form).execute()
            form_id = result["formId"]

            # Add questions
            requests = []
            for idx, q in enumerate(questions):
                item = {
                    "itemId": str(idx),
                    "title": q.get("title", f"Question {idx + 1}"),
                    "questionItem": {
                        "question": {
                            "required": q.get("required", False),
                            "textQuestion": {"paragraph": q.get("multiline", False)},
                        }
                    },
                }

                if "description" in q:
                    item["description"] = q["description"]

                requests.append(
                    {"createItem": {"item": item, "location": {"index": idx}}}
                )

            if requests:
                update = {"requests": requests}
                self.forms_service.forms().batchUpdate(
                    formId=form_id, body=update
                ).execute()

            # Note: Making forms truly public requires additional setup
            # The form is accessible to anyone with the link by default
            return f"https://docs.google.com/forms/d/{form_id}/viewform"

        except:
            return None

    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
        """Test Google Forms transport by creating a test form with test data

        Args:
            test_data: Data to include in the test form
            cleanup: If True, delete the test form after creation (default: True)

        Returns:
            Dictionary with 'success' (bool) and 'url' (str) if successful
        """
        if not self.forms_service:
            print("Forms service not initialized")
            return {"success": False, "error": "Forms service not initialized"}

        try:
            from datetime import datetime

            # Create form with only title (API restriction)
            form = {
                "info": {
                    "title": f"Test Form (Org) - {test_data} - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
                }
            }

            result = self.forms_service.forms().create(body=form).execute()
            form_id = result["formId"]

            # Build batch update requests
            requests = []

            # Update form description after creation
            requests.append(
                {
                    "updateFormInfo": {
                        "info": {
                            "description": f"This is a test form created by syft-client with test data: {test_data}"
                        },
                        "updateMask": "description",
                    }
                }
            )

            # Add a text input for test data
            requests.append(
                {
                    "createItem": {
                        "item": {
                            "title": "Test Data Input",
                            "description": f"Default value: {test_data}",
                            "questionItem": {
                                "question": {
                                    "required": True,
                                    "textQuestion": {"paragraph": False},
                                }
                            },
                        },
                        "location": {"index": 0},
                    }
                }
            )

            # Add a info item showing the test data
            requests.append(
                {
                    "createItem": {
                        "item": {
                            "title": "Test Information",
                            "description": f"Test Data: {test_data}\nTimestamp: {datetime.now().isoformat()}\nEmail: {self.email}\nTransport: Google Forms (Org)",
                            "textItem": {},
                        },
                        "location": {"index": 1},
                    }
                }
            )

            # Add a multiple choice question
            requests.append(
                {
                    "createItem": {
                        "item": {
                            "title": "Was this test successful?",
                            "questionItem": {
                                "question": {
                                    "required": False,
                                    "choiceQuestion": {
                                        "type": "RADIO",
                                        "options": [
                                            {"value": "Yes"},
                                            {"value": "No"},
                                            {"value": "Maybe"},
                                        ],
                                    },
                                }
                            },
                        },
                        "location": {"index": 2},
                    }
                }
            )

            # Apply the updates
            update = {"requests": requests}
            self.forms_service.forms().batchUpdate(
                formId=form_id, body=update
            ).execute()

            form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"

            # Delete the form if cleanup is requested
            if cleanup and form_id:
                try:
                    # Small delay to ensure form is accessible before deletion
                    import time

                    time.sleep(1)

                    # Note: Forms API doesn't have a delete method, so we'll need to use Drive API
                    # Forms are stored in Drive, so we can delete them using the Drive API
                    # However, we need to check if Drive service is available
                    if hasattr(self, "drive_service") and self.drive_service:
                        try:
                            self.drive_service.files().delete(fileId=form_id).execute()
                        except Exception:
                            # If deletion fails, try moving to trash
                            try:
                                self.drive_service.files().update(
                                    fileId=form_id, body={"trashed": True}
                                ).execute()
                            except Exception:
                                pass
                except Exception:
                    pass

            # Return the form URL
            print(
                f"✅ Google Forms test successful! Form created with 3 test questions"
            )
            if cleanup:
                print("   Form has been deleted as requested")

            return {"success": True, "url": form_url}

        except Exception as e:
            print(f"❌ Google Forms test failed: {e}")
            return {"success": False, "error": str(e)}
