"""Google platform implementation (Gmail, Google Workspace)"""

from .client import GoogleClient
from .gmail import GmailTransport
from .gdrive_files import GDriveFilesTransport
from .gsheets import GSheetsTransport
from .gforms import GFormsTransport

__all__ = [
    'GoogleClient',
    'GmailTransport', 
    'GDriveFilesTransport',
    'GSheetsTransport',
    'GFormsTransport'
]