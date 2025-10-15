"""Google Organizational platform implementation (Google Workspace)"""

from .client import GoogleOrgClient
from .gmail import GmailTransport
from .gdrive_files import GDriveFilesTransport
from .gsheets import GSheetsTransport
from .gforms import GFormsTransport

__all__ = [
    'GoogleOrgClient',
    'GmailTransport', 
    'GDriveFilesTransport',
    'GSheetsTransport',
    'GFormsTransport'
]