"""Google Organizational platform implementation (Google Workspace)"""

from .client import GoogleOrgClient
from .gdrive_files import GDriveFilesTransport
from .gforms import GFormsTransport
from .gmail import GmailTransport
from .gsheets import GSheetsTransport

__all__ = [
    "GoogleOrgClient",
    "GmailTransport",
    "GDriveFilesTransport",
    "GSheetsTransport",
    "GFormsTransport",
]
