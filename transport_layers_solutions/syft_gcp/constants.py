"""
Constants for GCP Transport Layer
"""

# OAuth scopes required for all services
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/forms.body",
]

# Service definitions: name -> (service_name, version)
SERVICES = {
    "gmail": ("gmail", "v1"),
    "sheets": ("sheets", "v4"),
    "drive": ("drive", "v3"),
    "forms": ("forms", "v1"),
}

# GCP API service names for enabling
API_SERVICES = [
    "gmail.googleapis.com",
    "sheets.googleapis.com",
    "drive.googleapis.com",
    "forms.googleapis.com",
]

# Default config directory
CONFIG_DIR_NAME = ".syft-gcp"

# Token file name
TOKEN_FILE_NAME = "token.pickle"

# Keyring service name
KEYRING_SERVICE = "syft-gcp"
KEYRING_TOKEN_KEY = "oauth-token"
