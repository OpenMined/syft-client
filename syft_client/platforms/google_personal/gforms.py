"""Google Forms transport layer implementation"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from googleapiclient.discovery import build
from ..transport_base import BaseTransportLayer
from ...environment import Environment


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
        self.credentials = None
        
    @property
    def api_is_active_by_default(self) -> bool:
        """Forms API requires manual activation"""
        return False
        
    @property
    def login_complexity(self) -> int:
        """Additional Forms setup complexity (after Google auth)"""
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
                    # Build service without explicit credentials in Colab
                    self.forms_service = build('forms', 'v1')
                    self.credentials = None  # No explicit credentials in Colab
                except ImportError:
                    # Fallback to regular credentials if Colab auth not available
                    if not credentials or 'credentials' not in credentials:
                        return False
                    self.credentials = credentials['credentials']
                    self.forms_service = build('forms', 'v1', credentials=self.credentials)
            else:
                # Regular OAuth2 flow
                if not credentials or 'credentials' not in credentials:
                    return False
                self.credentials = credentials['credentials']
                self.forms_service = build('forms', 'v1', credentials=self.credentials)
            
            return True
        except Exception:
            return False
    
    def is_setup(self) -> bool:
        """Check if Forms transport is ready"""
        return self.forms_service is not None
    
    def send(self, recipient: str, data: Any, subject: str = "Syft Form") -> bool:
        """Create a Google Form for data collection"""
        if not self.forms_service:
            return False
            
        try:
            # Create form
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            form_title = f"SyftClient_{subject.replace(' ', '_')}_{timestamp}"
            
            form = {
                "info": {
                    "title": form_title,
                    "document_title": form_title
                }
            }
            
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
                                        "options": [{"value": "True"}, {"value": "False"}]
                                    }
                                }
                            }
                        }
                    elif isinstance(value, (int, float)):
                        # Text input for numbers
                        item = {
                            "itemId": str(idx),
                            "title": f"{key} (number)",
                            "questionItem": {
                                "question": {
                                    "required": False,
                                    "textQuestion": {
                                        "paragraph": False
                                    }
                                }
                            }
                        }
                    else:
                        # Text input for strings and others
                        item = {
                            "itemId": str(idx),
                            "title": str(key),
                            "questionItem": {
                                "question": {
                                    "required": False,
                                    "textQuestion": {
                                        "paragraph": len(str(value)) > 50
                                    }
                                }
                            }
                        }
                    
                    requests.append({
                        "createItem": {
                            "item": item,
                            "location": {"index": idx}
                        }
                    })
            else:
                # Create a single text field for data submission
                requests.append({
                    "createItem": {
                        "item": {
                            "itemId": "0",
                            "title": "Data",
                            "description": f"Type: {type(data).__name__}",
                            "questionItem": {
                                "question": {
                                    "required": True,
                                    "textQuestion": {
                                        "paragraph": True
                                    }
                                }
                            }
                        },
                        "location": {"index": 0}
                    }
                })
            
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
            
            print("Forms receive not fully implemented - requires Drive API integration")
            
        except Exception as e:
            print(f"Error retrieving form responses: {e}")
            
        return messages
    
    def create_public_form(self, form_title: str, questions: List[Dict[str, Any]]) -> Optional[str]:
        """Create a publicly accessible form"""
        if not self.forms_service:
            return None
            
        try:
            # Create form
            form = {
                "info": {
                    "title": form_title,
                    "document_title": form_title
                }
            }
            
            result = self.forms_service.forms().create(body=form).execute()
            form_id = result["formId"]
            
            # Add questions
            requests = []
            for idx, q in enumerate(questions):
                item = {
                    "itemId": str(idx),
                    "title": q.get('title', f'Question {idx + 1}'),
                    "questionItem": {
                        "question": {
                            "required": q.get('required', False),
                            "textQuestion": {
                                "paragraph": q.get('multiline', False)
                            }
                        }
                    }
                }
                
                if 'description' in q:
                    item['description'] = q['description']
                
                requests.append({
                    "createItem": {
                        "item": item,
                        "location": {"index": idx}
                    }
                })
            
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