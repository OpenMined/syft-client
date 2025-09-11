"""Google Forms transport layer implementation"""

from typing import Any, Dict, List
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
        
        
    def send(self, recipient: str, data: Any) -> bool:
        """Submit data to a Google Form (can be done anonymously!)"""
        # TODO: Implement form submission
        # Note: This is special - can submit without auth if form is public
        raise NotImplementedError("Google Forms send not yet implemented")
        
    def receive(self) -> List[Dict[str, Any]]:
        """Read form responses (requires ownership)"""
        # TODO: Implement reading form responses
        raise NotImplementedError("Google Forms receive not yet implemented")