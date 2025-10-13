"""Google Personal platform implementation (personal Gmail accounts)"""

from .client import GooglePersonalClient
from .gdrive_files import GDriveFilesTransport
from .gforms import GFormsTransport
from .gmail import GmailTransport
from .gsheets import GSheetsTransport

__all__ = [
    "GooglePersonalClient",
    "GmailTransport",
    "GDriveFilesTransport",
    "GSheetsTransport",
    "GFormsTransport",
]
