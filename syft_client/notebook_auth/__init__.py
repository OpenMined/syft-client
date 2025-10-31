from google.oauth2.credentials import Credentials
from .google.authenticate import authenticate
from .google.authenticator import GoogleWorkspaceAuth


# Export the main function and types
__all__ = [
    "authenticate",
    "GoogleWorkspaceAuth",  # For advanced users who want more control
    "Credentials",  # Type hint convenience
]
